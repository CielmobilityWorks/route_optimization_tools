mapboxgl.accessToken = window.MAPBOX_ACCESS_TOKEN;

const map = new mapboxgl.Map({
    container: 'map',
    style: 'mapbox://styles/mapbox/light-v11',
    center: [126.9779, 37.5547],
    zoom: 11
});

let markers = [];
let currentPopup = null;
let lastDragEndedAt = 0; // 드래그 직후 클릭/맵클릭 무시용 타임스탬프(ms)

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    closePopup();
    checkMatrixFileExists();
    checkRoutesFileExists();
    setupKeyboardEvents();
    // Initialize counter
    updateLocationCounter(0);
});

async function initializeApp() {
    try {
        const response = await fetch('/api/locations');
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Failed to load data.' }));
            throw new Error(errorData.error);
        }
        const data = await response.json();
        updateTable(data);
        updateMarkers(data);
        
        // Auto-fit map to show all locations if data exists (앱 시작 시만)
        if (data && data.length > 0) {
            fitMapToLocations(data);
        }
    } catch (error) {
        console.error('Could not fetch locations:', error);
        alert(error.message);
    }
}

map.on('click', (e) => {
    // 드래그 직후 발생한 클릭은 무시하여 팝업이 열리지 않도록 함
    if (Date.now() - lastDragEndedAt < 300) return;
    if (e.defaultPrevented) return;

    const { lng, lat } = e.lngLat;
    openPopup({ lon: lng, lat: lat });
});

async function fetchLocations() {
    try {
        const response = await fetch('/api/locations');
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Failed to load data.' }));
            throw new Error(errorData.error);
        }
        const data = await response.json();
        updateTable(data);
        updateMarkers(data);
    } catch (error) {
        console.error('Could not fetch locations:', error);
        alert(error.message);
    }
}

function updateTable(locations) {
    const tbody = document.querySelector('#location-table tbody');
    tbody.innerHTML = '';
    locations.forEach((loc, index) => {
        const isDepot = index === 0;
        // ID 컬럼: depot은 그대로, 숫자는 5자리까지만 표시하고 나머지는 … 처리
    const fullIdStr = String(loc.id ?? '');
    const truncatedIdStr = fullIdStr.length > 5 ? fullIdStr.slice(0, 5) + '...' : fullIdStr;
        const displayId = isDepot ? 'depot' : truncatedIdStr;
        const rowClass = isDepot ? 'depot-row' : '';
        const idClass = isDepot ? 'depot-id' : '';
        const deleteButton = isDepot ? '' : `<button onclick="deleteLocation(${loc.id}); event.stopPropagation();">Delete</button>`;
        
        const row = `
            <tr class="${rowClass}" onclick="panToLocation(${loc.lon}, ${loc.lat})" style="cursor: pointer;">
                <td class="${idClass}" title="${isDepot ? 'depot' : fullIdStr}">${displayId}</td>
                <td title="${loc.name}">${loc.name}</td>
                <td>${loc.lon.toFixed(2)}</td>
                <td>${loc.lat.toFixed(2)}</td>
                <td>${loc.demand}</td>
                <td>
                    <button onclick="editLocation(${loc.id}); event.stopPropagation();">Edit</button>
                    ${deleteButton}
                </td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
    
    // Update location counter
    updateLocationCounter(locations.length);
}

function updateLocationCounter(count) {
    const counter = document.getElementById('location-counter');
    if (counter) {
        counter.textContent = `Total: ${count}`;
    }
}

function fitMapToLocations(locations) {
    if (!locations || locations.length === 0) return;
    
    if (locations.length === 1) {
        // 위치가 하나만 있으면 해당 위치로 이동
        map.flyTo({
            center: [locations[0].lon, locations[0].lat],
            zoom: 15
        });
        return;
    }
    
    // 모든 위치의 경계 계산
    const bounds = new mapboxgl.LngLatBounds();
    
    locations.forEach(location => {
        bounds.extend([location.lon, location.lat]);
    });
    
    // 지도를 모든 위치가 보이도록 조정 (여백 추가)
    map.fitBounds(bounds, {
        padding: {
            top: 50,
            bottom: 50,
            left: 50,
            right: 400 // 사이드바 공간 고려
        },
        maxZoom: 15 // 최대 줌 레벨 제한
    });
}

function updateMarkers(locations) {
    markers.forEach(marker => marker.remove());
    markers = [];

    locations.forEach((loc, index) => {
        const el = document.createElement('div');
        const isDepot = index === 0;
        el.className = isDepot ? 'marker depot' : 'marker';

        const popup = new mapboxgl.Popup({
            closeButton: false,
            closeOnClick: false,
            offset: 25,
            anchor: 'bottom'
        }).setText(loc.name);

        const marker = new mapboxgl.Marker({ element: el, draggable: !isDepot })
            .setLngLat([loc.lon, loc.lat])
            .setPopup(popup)
            .addTo(map);

        marker.getElement().addEventListener('mouseenter', () => marker.togglePopup());
        marker.getElement().addEventListener('mouseleave', () => marker.togglePopup());

        marker.getElement().addEventListener('click', (e) => {
            // 드래그 직후 클릭은 무시(자동 저장 후 편집 팝업이 뜨지 않게)
            if (Date.now() - lastDragEndedAt < 300) return;
            e.preventDefault();
            editLocation(loc.id);
        });
        
        // 드래그 앤 드롭으로 좌표 업데이트 (Depot은 드래그 불가)
        if (!isDepot) {
            const original = { lon: loc.lon, lat: loc.lat };
            marker.on('dragend', async () => {
                const p = marker.getLngLat();
                // 드래그 종료 타임스탬프 기록(직후 클릭 무시)
                lastDragEndedAt = Date.now();
                try {
                    const resp = await fetch(`/api/locations/${loc.id}` ,{
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ lon: p.lng, lat: p.lat })
                    });
                    if (!resp.ok) {
                        const err = await resp.json().catch(() => ({}));
                        throw new Error(err.error || '좌표 업데이트 실패');
                    }
                    await fetchLocations();
                } catch (e) {
                    console.error('좌표 업데이트 실패:', e);
                    alert('위치 업데이트 중 오류가 발생했습니다.');
                    // 실패 시 원래 좌표로 되돌림
                    marker.setLngLat([original.lon, original.lat]);
                }
            });
        }
        
        markers.push(marker);
    });
}

function openPopup(data = {}) {
    const popup = document.getElementById('popup');
    const isNew = !data.id;
    const isDepot = data.id === 1; // First location (ID=1) is depot
    
    document.getElementById('popup-id').value = data.id || '';
    document.getElementById('popup-name').value = data.name || '';
    document.getElementById('popup-lon').value = data.lon || '';
    document.getElementById('popup-lat').value = data.lat || '';
    document.getElementById('popup-demand').value = isDepot ? 0 : (data.demand || '');
    
    // Set readonly properties
    document.getElementById('popup-lon').readOnly = !isNew;
    document.getElementById('popup-lat').readOnly = !isNew;
    document.getElementById('popup-demand').readOnly = isDepot;
    
    // Disable demand field for depot visually
    if (isDepot) {
        document.getElementById('popup-demand').style.backgroundColor = '#f8f9fa';
        document.getElementById('popup-demand').style.color = '#6c757d';
    } else {
        document.getElementById('popup-demand').style.backgroundColor = '';
        document.getElementById('popup-demand').style.color = '';
    }

    popup.classList.remove('popup-hidden');
    popup.style.display = 'flex';
    
    // 포커스를 name 입력 필드로 이동
    setTimeout(() => {
        document.getElementById('popup-name').focus();
        document.getElementById('popup-name').select();
    }, 100);
}

function closePopup() {
    const popup = document.getElementById('popup');
    popup.classList.add('popup-hidden');
    popup.style.display = 'none';
}


async function saveData() {
    const id = document.getElementById('popup-id').value;
    const name = document.getElementById('popup-name').value;
    const lon = document.getElementById('popup-lon').value;
    const lat = document.getElementById('popup-lat').value;
    const demand = document.getElementById('popup-demand').value;

    if (!name || name.trim() === '') {
        alert('Name is required.');
        return;
    }

    const isDepot = id === '1'; // First location (ID=1) is depot
    const finalDemand = isDepot ? 0 : (demand ? parseInt(demand) : 0);

    const payload = { 
        name, 
        lon: parseFloat(lon), 
        lat: parseFloat(lat), 
        demand: finalDemand
    };

    let url = '/api/locations';
    let method = 'POST';

    if (id) {
        url = `/api/locations/${id}`;
        method = 'PUT';
        delete payload.lon;
        delete payload.lat;
    }

    try {
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            await fetchLocations();
            closePopup();
            console.log('Data saved successfully');
        } else {
            const contentType = response.headers.get('content-type');
            let errorMessage;
            
            if (contentType && contentType.includes('application/json')) {
                const errorData = await response.json();
                errorMessage = errorData.error || 'Failed to save data.';
            } else {
                errorMessage = `Server error: ${response.status} ${response.statusText}`;
            }
            
            throw new Error(errorMessage);
        }

    } catch (error) {
        console.error('Error saving data:', error);
        alert(error.message);
    }
}

function editLocation(id) {
     fetch(`/api/locations`)
        .then(response => response.json())
        .then(locations => {
            const location = locations.find(loc => loc.id === id);
            if (location) {
                openPopup(location);
            }
        });
}

function panToLocation(lon, lat) {
    map.flyTo({
        center: [lon, lat],
        zoom: 15
    });
}

async function deleteLocation(id) {
    if (confirm('Are you sure you want to delete this location?')) {
        try {
            const response = await fetch(`/api/locations/${id}`, { method: 'DELETE' });
            if (!response.ok) {
                throw new Error('Failed to delete location.');
            }
            await fetchLocations();
        } catch (error) {
            console.error('Error deleting location:', error);
            alert(error.message);
        }
    }
}

function uploadFile() {
    const fileInput = document.getElementById('file-upload');
    const file = fileInput.files[0];
    if (!file) {
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(async response => {
        if (response.ok) {
            alert('File uploaded successfully.');
            // 파일 입력 리셋(같은 파일 재업로드 허용 및 UX 개선)
            try { fileInput.value = ''; } catch (_) {}

            // 업로드로 인해 매트릭스/경로 캐시가 초기화되므로 버튼 상태 재확인
            checkMatrixFileExists();
            checkRoutesFileExists();

            // CSV 업로드 후 최신 데이터 반영 및 맵 자동 맞춤
            try {
                const locationResponse = await fetch('/api/locations');
                if (!locationResponse.ok) throw new Error('Failed to reload locations');
                const data = await locationResponse.json();
                updateTable(data);
                updateMarkers(data);
                if (data && data.length > 0) {
                    fitMapToLocations(data);
                }
            } catch (error) {
                console.error('Error fetching locations after upload:', error);
            }
        } else {
            const text = await response.text().catch(() => 'Unknown error');
            alert(`Upload failed: ${text}`);
        }
    })
    .catch(error => {
        console.error('Error uploading file:', error);
        alert('An error occurred during upload.');
    });
}

function openMatrixPopup() {
    const popup = document.getElementById('matrix-popup');
    popup.classList.remove('popup-hidden');
    popup.style.display = 'flex';
    
    document.querySelector('input[name="transportMode"][value="car"]').checked = true;
    document.querySelector('input[name="metric"][value="Recommendation"]').checked = true;
    updateMetricOptions();
    
    // 첫 번째 라디오 버튼에 포커스
    setTimeout(() => {
        document.querySelector('input[name="transportMode"][value="car"]').focus();
    }, 100);
}

function closeMatrixPopup() {
    const popup = document.getElementById('matrix-popup');
    popup.classList.add('popup-hidden');
    popup.style.display = 'none';
}

function updateMetricOptions() {
    const transportMode = document.querySelector('input[name="transportMode"]:checked').value;
    const metricRadios = document.querySelectorAll('input[name="metric"]');
    
    metricRadios.forEach(radio => {
        radio.disabled = false;
        radio.parentElement.style.opacity = '1';
    });
    
    if (transportMode === 'car') {
        ['HighStreet', 'ShortestDistance', 'ExcludeStairs'].forEach(metric => {
            const radio = document.querySelector(`input[name="metric"][value="${metric}"]`);
            radio.disabled = true;
            radio.parentElement.style.opacity = '0.5';
            if (radio.checked) {
                document.querySelector('input[name="metric"][value="Recommendation"]').checked = true;
            }
        });
    } else if (transportMode === 'pedestrian') {
        const staticRadio = document.querySelector('input[name="metric"][value="Static"]');
        staticRadio.disabled = true;
        staticRadio.parentElement.style.opacity = '0.5';
        if (staticRadio.checked) {
            document.querySelector('input[name="metric"][value="Recommendation"]').checked = true;
        }
    }
}

async function createMatrix() {
    const transportMode = document.querySelector('input[name="transportMode"]:checked').value;
    const metric = document.querySelector('input[name="metric"]:checked').value;
    
    console.log('Creating matrix with:', { transportMode, metric });
    
    try {
        const response = await fetch('/api/create-matrix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transportMode, metric })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`매트릭스가 성공적으로 생성되었습니다!\n위치 수: ${result.locations.length}\n저장 위치: time_matrix.csv, distance_matrix.csv`);
            console.log('Generated time matrix:', result.time_matrix);
            console.log('Generated distance matrix:', result.distance_matrix);
            console.log('Locations:', result.locations);
            // 매트릭스 생성 후 Optimization 버튼 상태 확인
            checkMatrixFileExists();
        } else {
            alert(`매트릭스 생성 실패: ${result.message}`);
        }
        
    } catch (error) {
        console.error('Matrix creation error:', error);
        alert(`매트릭스 생성 중 오류가 발생했습니다: ${error.message}`);
    }
    
    closeMatrixPopup();
}

// Optimization functions
async function checkMatrixFileExists() {
    try {
        const response = await fetch('/api/check-matrix-file');
        const result = await response.json();
        
        const optimizationButton = document.getElementById('optimization-button');
        optimizationButton.disabled = !result.exists;
        
    } catch (error) {
        console.error('Error checking matrix file:', error);
        document.getElementById('optimization-button').disabled = true;
    }
}

async function checkRoutesFileExists() {
    try {
        const response = await fetch('/api/check-routes');
        const result = await response.json();
        
        const routeViewButton = document.getElementById('route-view-button');
        const routeRefreshButton = document.getElementById('route-refresh-button');
        
        // View 버튼 존재 확인 (필수)
        if (!routeViewButton) {
            console.error('route-view-button 요소를 찾을 수 없습니다!');
            return;
        }
        
        // 버튼 활성화 상태 설정
        const hasRoutes = result.has_routes;
        routeViewButton.disabled = !hasRoutes;
        
        // Refresh 버튼은 모달 내부에 있으므로 존재할 때만 처리
        if (routeRefreshButton) {
            routeRefreshButton.disabled = !hasRoutes;
        }
        
        console.log('🔍 Route button status check:');
        console.log('  - Has routes:', hasRoutes);
        console.log('  - View button disabled:', routeViewButton.disabled);
        console.log('  - Refresh button disabled:', routeRefreshButton ? routeRefreshButton.disabled : 'N/A (not loaded)');
        console.log('  - API message:', result.message);
        
        if (hasRoutes) {
            console.log('✅ Routes file found - Route buttons enabled');
        } else {
            console.log('❌ No routes file found:', result.message);
        }
        
    } catch (error) {
        console.error('Error checking routes file:', error);
        const viewButton = document.getElementById('route-view-button');
        const refreshButton = document.getElementById('route-refresh-button');
        
        if (viewButton) viewButton.disabled = true;
        if (refreshButton) refreshButton.disabled = true;
    }
}

function openOptimizationPopup() {
    const popup = document.getElementById('optimization-popup');
    popup.classList.remove('popup-hidden');
    popup.style.display = 'flex';
    
    // 기본값 설정
    document.getElementById('vehicle-count').value = 1;
    document.getElementById('vehicle-capacity').value = 10;
    const tl = document.getElementById('time-limit-sec');
    if (tl) tl.value = 60;
    
    // 기본 선택값 설정 (총 거리 최소화)
    document.querySelector('input[name="primaryObjective"][value="distance"]').checked = true;
    document.querySelector('input[name="tiebreaker1"][value="none"]').checked = true;
    document.querySelector('input[name="tiebreaker2"][value="none"]').checked = true;
    
    // 체크박스 초기화
    document.querySelectorAll('input[name="additionalObjectives"]').forEach(cb => cb.checked = false);
    
    // 타이브레이커 기본값 설정 및 미리보기 업데이트
    updateTiebreakerDefaults();
    
    // 첫 번째 입력 필드에 포커스
    setTimeout(() => {
        document.getElementById('vehicle-count').focus();
        document.getElementById('vehicle-count').select();
    }, 100);
}

function closeOptimizationPopup() {
    const popup = document.getElementById('optimization-popup');
    popup.classList.add('popup-hidden');
    popup.style.display = 'none';
}

async function runOptimization() {
    const vehicleCount = parseInt(document.getElementById('vehicle-count').value);
    const vehicleCapacity = parseInt(document.getElementById('vehicle-capacity').value);
    const timeLimitInput = document.getElementById('time-limit-sec');
    let timeLimitSec = timeLimitInput ? parseInt(timeLimitInput.value) : 60;
    if (!Number.isFinite(timeLimitSec) || timeLimitSec < 1) {
        timeLimitSec = 60;
    }
    
    if (!vehicleCount || vehicleCount < 1) {
        alert('Vehicle count must be at least 1.');
        return;
    }
    
    if (!vehicleCapacity || vehicleCapacity < 1) {
        alert('Vehicle capacity must be at least 1.');
        return;
    }
    
    // 목적함수 설정 수집
    const primaryObjective = document.querySelector('input[name="primaryObjective"]:checked').value;
    const tiebreaker1 = document.querySelector('input[name="tiebreaker1"]:checked').value;
    const tiebreaker2 = document.querySelector('input[name="tiebreaker2"]:checked').value;
    const additionalObjectives = Array.from(document.querySelectorAll('input[name="additionalObjectives"]:checked')).map(cb => cb.value);
    
    // Close optimization parameter popup and show loading popup with exact timer
    closeOptimizationPopup();
    showLoadingPopup(timeLimitSec);
    
    console.log('Running optimization with:', { 
        vehicleCount, 
        vehicleCapacity, 
        timeLimitSec,
        primaryObjective, 
        tiebreaker1, 
        tiebreaker2, 
        additionalObjectives 
    });
    
    try {
        // Start with data validation message
        updateLoadingMessage('입력 데이터를 검증하고 있습니다...');
        
        // Simulate some initial processing time
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        updateLoadingMessage('서버에 최적화 요청을 전송하고 있습니다...');
        
    // Route mode from radio selection
    const routeMode = (document.querySelector('input[name="routeMode"]:checked') || {}).value || 'FREE_START_DEPOT_END';

        const response = await fetch('/api/optimize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                vehicleCount: vehicleCount,
                vehicleCapacity: vehicleCapacity,
                timeLimitSec: timeLimitSec,
                primaryObjective: primaryObjective,
                tiebreaker1: tiebreaker1,
                tiebreaker2: tiebreaker2,
                additionalObjectives: additionalObjectives,
                routeMode: routeMode
            })
        });
        
        updateLoadingMessage('최적화 결과를 처리하고 있습니다...');
        
        const result = await response.json();
        
        // Complete progress and show result
        if (result.success) {
            // Set progress to 100% and show completion
            document.getElementById('progress-fill').style.width = '100%';
            document.getElementById('progress-percentage').textContent = '100%';
            document.getElementById('current-step').textContent = '완료';
            updateLoadingMessage('최적화 결과를 CSV 파일로 저장하고 있습니다...');
            
            // Wait a moment to show completion, then hide loading and show success message
            setTimeout(() => {
                hideLoadingPopup();
                
                // Check routes file and update View Routes button state
                checkRoutesFileExists();
                
                const totalTimeMinutes = Math.round(result.total_time / 60);
                alert(`최적화가 성공적으로 완료되었습니다!\n\n결과 요약:\n- 총 거리: ${result.total_distance.toLocaleString()}m\n- 총 시간: ${totalTimeMinutes}분\n- 총 적재량: ${result.total_load}\n- 차량 수: ${result.vehicleCount}대\n\n상세 결과가 CSV 파일로 저장되었습니다.`);
            }, 1000);
        } else {
            hideLoadingPopup();
            alert(`최적화 실패: ${result.message}`);
        }
        
    } catch (error) {
        console.error('Optimization error:', error);
        hideLoadingPopup();
        alert(`최적화 중 오류가 발생했습니다: ${error.message}`);
    }
}



let optimizationTimer = null;
let startTime = null;
let optimizationTotalMs = null; // 전체 진행 타이머 목표 시간(ms)

function showLoadingPopup(totalSeconds) {
    const popup = document.getElementById('loading-popup');
    popup.classList.remove('popup-hidden');
    popup.style.display = 'flex';
    
    // 총 타이머 시간 설정 (기본 60초)
    if (Number.isFinite(totalSeconds) && totalSeconds > 0) {
        optimizationTotalMs = totalSeconds * 1000;
    } else {
        optimizationTotalMs = 60000;
    }

    // Initialize progress tracking
    resetProgressIndicators();
    startProgressTimer(totalSeconds);
}

function hideLoadingPopup() {
    const popup = document.getElementById('loading-popup');
    popup.classList.add('popup-hidden');
    popup.style.display = 'none';
    
    // Stop progress timer
    if (optimizationTimer) {
        clearInterval(optimizationTimer);
        optimizationTimer = null;
    }
}

function resetProgressIndicators() {
    document.getElementById('progress-fill').style.width = '0%';
    document.getElementById('progress-percentage').textContent = '0%';
    document.getElementById('progress-time').textContent = '00:00';
    document.getElementById('current-step').textContent = '준비 중';
    document.getElementById('estimated-time').textContent = '계산 중...';
}

function startProgressTimer(totalSeconds) {
    startTime = Date.now();
    const totalMs = (Number.isFinite(totalSeconds) && totalSeconds > 0)
        ? totalSeconds * 1000
        : (optimizationTotalMs || 60000);

    optimizationTimer = setInterval(() => {
        const now = Date.now();
        const elapsed = now - startTime;

        // 선형 진행: 설정한 총 시간 대비 진행률, 백엔드 완료 전에는 최대 99%
        const ratio = Math.min(elapsed / totalMs, 0.99);
        const progress = Math.max(0, Math.min(99, Math.floor(ratio * 100)));

        // 경과 시간 표시 (mm:ss)
        const minutes = Math.floor(elapsed / 60000);
        const seconds = Math.floor((elapsed % 60000) / 1000);
        document.getElementById('progress-time').textContent =
            `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

        // 단계 라벨은 간단한 구간 기준으로 표시
        let stepLabel = '데이터 검증';
        if (progress >= 10 && progress < 30) stepLabel = '서버 요청';
        else if (progress >= 30 && progress < 70) stepLabel = '경로 계산 중';
        else if (progress >= 70 && progress < 90) stepLabel = '결과 최적화';
        else if (progress >= 90) stepLabel = '완료 준비';

        // UI 갱신 (남은 시간은 updateProgressDisplay에서 계산)
        updateProgressDisplay(progress, stepLabel, elapsed);

        // 총 시간을 초과해도 백엔드 완료 전에는 99%로 유지
        // 타이머는 hideLoadingPopup()/성공 처리에서 정리됨
    }, 100);
}

function updateProgressDisplay(progress, step, elapsed) {
    // Update progress bar
    document.getElementById('progress-fill').style.width = `${progress}%`;
    document.getElementById('progress-percentage').textContent = `${Math.round(progress)}%`;
    
    // Update current step
    document.getElementById('current-step').textContent = step;
    
    // Display remaining time: 설정된 총 시간(optimizationTotalMs) 기준으로 정확 계산
    if (optimizationTotalMs && elapsed >= 0) {
        const remaining = Math.max(optimizationTotalMs - elapsed, 0);
        const remainingMinutes = Math.floor(remaining / 60000);
        const remainingSeconds = Math.floor((remaining % 60000) / 1000);
        document.getElementById('estimated-time').textContent = 
            remaining > 0 ? `약 ${remainingMinutes}:${remainingSeconds.toString().padStart(2, '0')} 남음` : '곧 완료';
    } else if (progress > 5) {
        // 백업 로직 (총 시간이 없을 때 기존 추정 공식을 사용)
        const estimatedTotal = progress > 0 ? (elapsed / (progress / 100)) : elapsed;
        const remaining = estimatedTotal - elapsed;
        const remainingMinutes = Math.floor(remaining / 60000);
        const remainingSeconds = Math.floor((remaining % 60000) / 1000);
        document.getElementById('estimated-time').textContent = 
            remaining > 0 ? `약 ${remainingMinutes}:${remainingSeconds.toString().padStart(2, '0')} 남음` : '곧 완료';
    }
}

function updateLoadingMessage(message) {
    const messageElement = document.getElementById('loading-message');
    if (messageElement) {
        messageElement.textContent = message;
    }
}

function updateTiebreakerDefaults() {
    const primaryObjective = document.querySelector('input[name="primaryObjective"]:checked').value;
    
    // 타이브레이커 기본값 설정
    const tiebreakerDefaults = {
        'distance': { t1: 'vehicles', t2: 'none' },
        'time': { t1: 'makespan', t2: 'vehicles' },
        'vehicles': { t1: 'distance', t2: 'none' },
        'cost': { t1: 'distance', t2: 'vehicles' },
        'makespan': { t1: 'time', t2: 'vehicles' }
    };
    
    const defaults = tiebreakerDefaults[primaryObjective];
    if (defaults) {
        document.querySelector(`input[name="tiebreaker1"][value="${defaults.t1}"]`).checked = true;
        document.querySelector(`input[name="tiebreaker2"][value="${defaults.t2}"]`).checked = true;
    }
    
    updateOptimizationPreview();
}

function applyIndustrySettings(industry) {
    const settings = {
        'food': {
            primary: 'time',
            tiebreaker1: 'makespan',
            tiebreaker2: 'none',
            additional: ['timeWindow', 'waitTime', 'co2']
        },
        'delivery': {
            primary: 'distance',
            tiebreaker1: 'vehicles',
            tiebreaker2: 'none',
            additional: ['timeWindow', 'workloadBalance']
        },
        'medical': {
            primary: 'makespan',
            tiebreaker1: 'time',
            tiebreaker2: 'none',
            additional: ['timeWindow', 'overtime']
        },
        'waste': {
            primary: 'time',
            tiebreaker1: 'distance',
            tiebreaker2: 'none',
            additional: ['workloadBalance', 'fixedCost']
        }
    };
    
    const setting = settings[industry];
    if (!setting) return;
    
    // 주 목적 설정
    document.querySelector(`input[name="primaryObjective"][value="${setting.primary}"]`).checked = true;
    
    // 타이브레이커 설정
    document.querySelector(`input[name="tiebreaker1"][value="${setting.tiebreaker1}"]`).checked = true;
    document.querySelector(`input[name="tiebreaker2"][value="${setting.tiebreaker2}"]`).checked = true;
    
    // 추가 목적 초기화 후 설정
    document.querySelectorAll('input[name="additionalObjectives"]').forEach(cb => cb.checked = false);
    setting.additional.forEach(value => {
        const checkbox = document.querySelector(`input[name="additionalObjectives"][value="${value}"]`);
        if (checkbox) checkbox.checked = true;
    });
    
    updateOptimizationPreview();
}

function updateOptimizationPreview() {
    const primary = document.querySelector('input[name="primaryObjective"]:checked').value;
    const tiebreaker1 = document.querySelector('input[name="tiebreaker1"]:checked').value;
    const tiebreaker2 = document.querySelector('input[name="tiebreaker2"]:checked').value;
    const additional = Array.from(document.querySelectorAll('input[name="additionalObjectives"]:checked')).map(cb => cb.value);
    
    // 목적함수 텍스트 생성
    const objectiveNames = {
        'distance': '총거리',
        'time': '총시간',
        'vehicles': '차량수',
        'cost': '총비용',
        'makespan': 'makespan',
        'none': '없음'
    };
    
    const additionalNames = {
        'timeWindow': '시간창위반',
        'waitTime': '대기시간',
        'workloadBalance': '작업량균등화',
        'overtime': '오버타임',
        'co2': 'CO₂배출',
        'fixedCost': '차량고정비',
        'utilization': '차량이용률'
    };
    
    let objectiveText = `Min [${objectiveNames[primary]}`;
    if (additional.length > 0) {
        const additionalText = additional.map(a => additionalNames[a]).join(' + ');
        objectiveText += ` + ${additionalText}`;
    }
    objectiveText += ']';
    
    // 타이브레이커 텍스트
    let tiebreakerText = '타이브레이커: ';
    if (tiebreaker1 !== 'none') {
        tiebreakerText += objectiveNames[tiebreaker1];
        if (tiebreaker2 !== 'none') {
            tiebreakerText += ` → ${objectiveNames[tiebreaker2]}`;
        }
    } else {
        tiebreakerText += '없음';
    }
    
    document.getElementById('optimization-preview').textContent = `${objectiveText}, ${tiebreakerText}`;
    
    // 경고 메시지 생성
    updateOptimizationWarnings(primary, additional);
}

function updateOptimizationWarnings(primary, additional) {
    const warnings = [];
    
    // 시간창 관련 경고
    if (!additional.includes('timeWindow')) {
        warnings.push('시간창 위반 패널티 미포함 상태입니다.');
    }
    
    // 상충 가능성 체크
    if (primary === 'vehicles' && additional.includes('fixedCost')) {
        warnings.push('차량 수 최소화와 차량 고정비 고려는 효과가 중복될 수 있어요.');
    }
    
    if (additional.includes('vehicles') && additional.includes('utilization')) {
        warnings.push('차량 수 최소화와 차량 이용률 향상은 상충할 수 있습니다.');
    }
    
    if (additional.includes('co2') && !additional.includes('distance')) {
        warnings.push('CO₂ 배출 최소화는 일반적으로 거리와 연관됩니다.');
    }
    
    const warningsDiv = document.getElementById('optimization-warnings');
    if (warnings.length > 0) {
        warningsDiv.innerHTML = warnings.map(w => `<div class="warning-item">${w}</div>`).join('');
    } else {
        warningsDiv.innerHTML = '<div style="color: #28a745;">✓ 설정이 적절합니다.</div>';
    }
}

// 페이지 로드 시 미리보기 업데이트
document.addEventListener('DOMContentLoaded', () => {
    // 기존 코드...
    
    // 라디오 버튼과 체크박스 변경 시 미리보기 업데이트
    setTimeout(() => {
        if (document.querySelector('input[name="primaryObjective"]')) {
            updateOptimizationPreview();
            
            // 이벤트 리스너 등록
            document.querySelectorAll('input[name="primaryObjective"], input[name="tiebreaker1"], input[name="tiebreaker2"], input[name="additionalObjectives"]').forEach(input => {
                input.addEventListener('change', updateOptimizationPreview);
            });
        }
    }, 100);
});

function setupKeyboardEvents() {
    document.addEventListener('keydown', (e) => {
        // 현재 열려있는 팝업 확인
        const popup = document.getElementById('popup');
        const matrixPopup = document.getElementById('matrix-popup');
        const optimizationPopup = document.getElementById('optimization-popup');
        const loadingPopup = document.getElementById('loading-popup');
        const routeSettingsPopup = document.getElementById('route-settings-popup');
        
        const isPopupVisible = !popup.classList.contains('popup-hidden');
        const isMatrixPopupVisible = !matrixPopup.classList.contains('popup-hidden');
        const isOptimizationPopupVisible = !optimizationPopup.classList.contains('popup-hidden');
        const isLoadingPopupVisible = !loadingPopup.classList.contains('popup-hidden');
        const isRouteSettingsVisible = routeSettingsPopup && !routeSettingsPopup.classList.contains('popup-hidden');
        
        // 로딩 팝업이 열려있을 때는 키보드 이벤트 무시
        if (isLoadingPopupVisible) {
            return;
        }
        
        // ESC 키 - 팝업 닫기
        if (e.key === 'Escape') {
            if (isRouteSettingsVisible) {
                closeRouteSettingsPopup();
            } else if (isPopupVisible) {
                closePopup();
            } else if (isMatrixPopupVisible) {
                closeMatrixPopup();
            } else if (isOptimizationPopupVisible) {
                closeOptimizationPopup();
            }
        }
        
        // Enter 키 - 확인 버튼 실행
        if (e.key === 'Enter') {
            // 라디오 버튼이나 일반 버튼에 포커스가 있을 때만 실행
            if (e.target.tagName !== 'INPUT' || e.target.type === 'radio' || e.target.type === 'button') {
                if (isPopupVisible) {
                    e.preventDefault();
                    saveData();
                } else if (isMatrixPopupVisible) {
                    e.preventDefault();
                    createMatrix();
                } else if (isOptimizationPopupVisible) {
                    e.preventDefault();
                    runOptimization();
                }
            }
            // 텍스트/숫자 입력 필드에서는 자연스럽게 다음 필드로 이동하거나 확인 실행
            else if (e.target.tagName === 'INPUT' && (e.target.type === 'text' || e.target.type === 'number')) {
                // 마지막 입력 필드에서 Enter를 누르면 저장/실행
                const inputs = Array.from(e.target.closest('.popup-content').querySelectorAll('input[type="text"], input[type="number"]:not([readonly])'));
                const currentIndex = inputs.indexOf(e.target);
                
                if (currentIndex === inputs.length - 1) {
                    e.preventDefault();
                    if (isPopupVisible) {
                        saveData();
                    } else if (isOptimizationPopupVisible) {
                        runOptimization();
                    }
                }
            }
        }
    });
}

// Route Visualization Modal Functions
let routeMap = null;
// 전역으로도 노출
window.routeMap = null;

function openRouteViewModal() {
    const modal = document.getElementById('route-modal');
    modal.classList.remove('route-modal-hidden');
    
    // 모달이 완전히 렌더링된 후 지도 초기화 및 경로 로드
    setTimeout(() => {
        initializeRouteMap();
        loadAndDisplayRoutes();
    }, 300);
}

// Refresh Routes 버튼 클릭 시: 설정 팝업 열기(UI만 동작)
function refreshRoutes() {
    openRouteSettingsPopup();
}

function closeRouteViewModal() {
    const modal = document.getElementById('route-modal');
    modal.classList.add('route-modal-hidden');
    
    // 지도 인스턴스 정리
    if (routeMap) {
        routeMap.remove();
        routeMap = null;
    }
}

// Route Settings Popup 제어
function openRouteSettingsPopup() {
    const popup = document.getElementById('route-settings-popup');
    if (!popup) return;
    
    // 기본값 설정
    // searchoption 기본: 교통최적+추천
    const defaultSearch = document.querySelector('input[name="searchoption"][value="교통최적+추천"]');
    if (defaultSearch) defaultSearch.checked = true;
    // carType 기본: 승용차
    const defaultCar = document.querySelector('input[name="carType"][value="승용차"]');
    if (defaultCar) defaultCar.checked = true;
    // viaTime 기본: 60
    const viaInput = document.getElementById('via-time-input');
    if (viaInput) viaInput.value = 60;
    // startTime 기본: 현재시간 (datetime-local 형식)
    const startInput = document.getElementById('start-time-input');
    if (startInput) startInput.value = getCurrentDateTimeForDatetimeLocal();

    popup.classList.remove('popup-hidden');
    popup.style.display = 'flex';

    // Routes 버튼(적용)은 일단 동작하지 않음 — 닫기만 수행
    const applyBtn = document.getElementById('route-settings-apply-button');
    if (applyBtn) {
        applyBtn.onclick = async () => {
            const selectedSearch = document.querySelector('input[name="searchoption"]:checked')?.value || '';
            const selectedCar = document.querySelector('input[name="carType"]:checked')?.value || '';
            const viaTime = (document.getElementById('via-time-input')?.value || '').toString();
            const startRaw = document.getElementById('start-time-input')?.value; // e.g. 2025-09-21T14:30
            const startTime = startRaw ? formatDatetimeLocalToYYYYMMDDHHMM(startRaw) : '';

            // 라벨을 T-map 코드 문자열로 매핑
            const searchOption = mapSearchOptionLabelToCode(selectedSearch);
            const carType = mapCarTypeLabelToCode(selectedCar);

            // 백엔드 호출: 옵션을 그대로 문자열로 전달
            try {
                // UI: 로딩 표시
                showRouteLoading(true);
                const resp = await fetch('/generate-routes-from-csv', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        searchOption: searchOption,
                        carType: carType,
                        viaTime: viaTime,
                        startTime: startTime
                    })
                });
                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({}));
                    throw new Error(err.error || '경로 재생성 실패');
                }
                const data = await resp.json();
                if (!data.success) {
                    throw new Error(data.error || '경로 재생성 실패');
                }
                // 성공 시: 모달 지도에 반영
                if (!routeMap) {
                    initializeRouteMap();
                }
                displayTmapRoutes(data.vehicle_routes);
                closeRouteSettingsPopup();
            } catch (e) {
                console.error(e);
                showRouteError(e.message || '경로 재생성 중 오류');
            } finally {
                showRouteLoading(false);
            }
        };
    }
}

function closeRouteSettingsPopup() {
    const popup = document.getElementById('route-settings-popup');
    if (!popup) return;
    popup.classList.add('popup-hidden');
    popup.style.display = 'none';
}

// YYYYMMDDHHMM 포맷 현재시간
function getCurrentDateTimeForDatetimeLocal() {
    const d = new Date();
    const yyyy = d.getFullYear().toString();
    const mm = (d.getMonth() + 1).toString().padStart(2, '0');
    const dd = d.getDate().toString().padStart(2, '0');
    const HH = d.getHours().toString().padStart(2, '0');
    const MM = d.getMinutes().toString().padStart(2, '0');
    // datetime-local 값 형식: YYYY-MM-DDTHH:MM
    return `${yyyy}-${mm}-${dd}T${HH}:${MM}`;
}

function formatDatetimeLocalToYYYYMMDDHHMM(value) {
    // 입력 예시: 2025-09-21T14:30
    if (!value || !value.includes('T')) return '';
    const [date, time] = value.split('T');
    const [yyyy, mm, dd] = date.split('-');
    const [HH, MM] = time.split(':');
    return `${yyyy}${mm}${dd}${HH}${MM}`;
}

// 매핑 함수: 한글 라벨 -> T-map 코드(문자열)
function mapCarTypeLabelToCode(label) {
    const map = {
        '승용차': '1',
        '중형승합차': '2',
        '대형승합차': '3',
        '대형화물차': '4',
        '특수화물차': '5'
    };
    return map[label] || '3'; // 기본값: 대형승합차(3)
}

function mapSearchOptionLabelToCode(label) {
    const map = {
        '교통최적+추천': '0',
        '교통최적+무료우선': '1',
        '교통최적+최소시간': '2',
        '교통최적+초보': '3',
        '교통최적+화물차': '17'
    };
    return map[label] || '0'; // 기본값: 0
}

function initializeRouteMap() {
    // 컨테이너가 존재하는지 확인
    const container = document.getElementById('route-map');
    if (!container) {
        console.error('Route map container not found');
        return;
    }
    
    // 기존 지도가 있으면 제거
    if (routeMap) {
        try {
            routeMap.remove();
        } catch (error) {
            console.warn('Error removing existing map:', error);
        }
        routeMap = null;
    }
    
    try {
        // 새로운 지도 생성
        routeMap = new mapboxgl.Map({
            container: 'route-map',
            style: 'mapbox://styles/mapbox/light-v11',
            center: [126.9779, 37.5547], // 서울 중심
            zoom: 11
        });
        
        // 전역 변수에도 할당
        window.routeMap = routeMap;
        console.log('🗺️ 지도 객체를 전역 변수에 할당:', window.routeMap);
        
        // 지도 로드 완료 후 추가 초기화
        routeMap.on('load', () => {
            console.log('Route map initialized successfully');
            // 여기에 나중에 경로 데이터 로드 로직 추가
        });
        
        // 에러 핸들링
        routeMap.on('error', (e) => {
            console.error('Route map error:', e);
        });
        
    } catch (error) {
        console.error('Failed to initialize route map:', error);
    }
}

// 모달 외부 클릭 시 닫기
document.addEventListener('click', (e) => {
    const modal = document.getElementById('route-modal');
    if (e.target === modal) {
        closeRouteViewModal();
    }
});

// ESC 키로 모달 닫기
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const modal = document.getElementById('route-modal');
        const routeSettingsPopup = document.getElementById('route-settings-popup');
        const isRouteSettingsVisible = routeSettingsPopup && !routeSettingsPopup.classList.contains('popup-hidden');
        // 설정 팝업이 열려있으면 모달은 닫지 않음
        if (!modal.classList.contains('route-modal-hidden') && !isRouteSettingsVisible) {
            closeRouteViewModal();
        }
    }
});

// 스마트 경로 로딩: 캐시된 데이터 우선, 없으면 생성
async function loadAndDisplayRoutes() {
    if (!routeMap) {
        console.error('Route map not initialized');
        return;
    }
    
    try {
        // 로딩 표시
        showRouteLoading(true);
        
        console.log('📍 경로 데이터 로딩 중...');
        
        // 스마트 경로 로딩 API 호출
        const response = await fetch('/get-routes', {
            method: 'GET'
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || '경로 로딩에 실패했습니다.');
        }
        
        const routeData = await response.json();
        
        if (!routeData.success) {
            throw new Error('경로 로딩에 실패했습니다.');
        }
        
        // 캐시 여부에 따른 로그 출력 및 상태 표시
        if (routeData.from_cache) {
            console.log('✅ 캐시된 경로 로드 완료:', routeData);
            console.log('📅 생성 시간:', routeData.generated_at);
            
            const generatedTime = new Date(routeData.generated_at).toLocaleString('ko-KR');
            console.log(`💾 캐시된 데이터 (${generatedTime})`);
        } else {
            console.log('✅ 새로운 경로 생성 완료:', routeData);
        }
        
        // 지도에 경로 표시
        displayTmapRoutes(routeData.vehicle_routes);
        
        // 통계 정보 업데이트 (만약 UI에 있다면)
        if (typeof updateRouteStatistics === 'function') {
            updateRouteStatistics(routeData.statistics);
        }
        
    } catch (error) {
        console.error('❌ 경로 로드 실패:', error);
        showRouteError(error.message);
    } finally {
        showRouteLoading(false);
    }
}

// 강제로 새로운 경로 생성 (Refresh Routes용)
async function refreshAndDisplayRoutes() {
    if (!routeMap) {
        console.error('Route map not initialized');
        return;
    }
    
    try {
        // 로딩 표시
        showRouteLoading(true);
        
        console.log('� T-map API로 새로운 경로 생성 중...');
        
        // 강제 경로 재생성 API 호출
        const response = await fetch('/generate-routes-from-csv', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || '경로 생성에 실패했습니다.');
        }
        
        const routeData = await response.json();
        
        if (!routeData.success) {
            throw new Error('경로 생성에 실패했습니다.');
        }
        
        console.log('✅ 새로운 경로 생성 완료:', routeData);
        
        // 지도에 경로 표시
        displayTmapRoutes(routeData.vehicle_routes);
        
        // 통계 정보 업데이트
        if (typeof updateRouteStatistics === 'function') {
            updateRouteStatistics(routeData.statistics);
        }
        
    } catch (error) {
        console.error('❌ 경로 생성 실패:', error);
        showRouteError(error.message);
    } finally {
        showRouteLoading(false);
    }
}

// T-map 경로들을 지도에 표시
function displayTmapRoutes(vehicleRoutes) {
    if (!routeMap || !vehicleRoutes) return;

    // 먼저 가능한 한 통합 클리너 사용(레이어/소스/마커 모두 정리)
    if (typeof window.clearAllRouteLayers === 'function') {
        window.clearAllRouteLayers(routeMap);
    } else {
        clearRouteMapLayers();
    }

    // 통합 경로 표출/관리 함수에 위임하여
    // 1) 라인 레이어와 2) 마커를 차량별로 함께 등록/추적하게 함
    if (typeof window.displayAndManageRoutes === 'function') {
        // DOM 렌더 안정화를 위해 약간 지연 후 실행
        setTimeout(() => {
            window.displayAndManageRoutes(vehicleRoutes, routeMap);
            console.log(`✅ ${Object.keys(vehicleRoutes).length}개 차량 경로 표시 완료 (통합 함수 사용)`);
        }, 50);
    } else {
        console.error('❌ displayAndManageRoutes 함수를 찾을 수 없습니다!');
        // 폴백: 최소한 기존 레이어만 정리
        clearRouteMapLayers();
    }
}

// 기존 경로 레이어들 제거
function clearRouteMapLayers() {
    if (!routeMap) return;

    // 통합 클리너가 있으면 우선 사용(마커까지 정리)
    if (typeof window.clearAllRouteLayers === 'function') {
        window.clearAllRouteLayers(routeMap);
        return;
    }

    const layers = routeMap.getStyle().layers;
    const sources = routeMap.getStyle().sources;

    // route- 로 시작하는 레이어들 제거
    layers.forEach(layer => {
        if (layer.id.startsWith('route-')) {
            try {
                routeMap.removeLayer(layer.id);
            } catch (e) {
                console.warn('Layer removal failed:', layer.id);
            }
        }
    });

    // route- 로 시작하는 소스들 제거
    Object.keys(sources).forEach(sourceId => {
        if (sourceId.startsWith('route-')) {
            try {
                routeMap.removeSource(sourceId);
            } catch (e) {
                console.warn('Source removal failed:', sourceId);
            }
        }
    });

    // 마커도 가능하면 정리(과거 버전에서 생성한 비추적 마커는 제거가 어려움)
    if (window.routeMarkers) {
        Object.values(window.routeMarkers).forEach(markers => {
            try { markers.forEach(m => m.remove()); } catch (_) {}
        });
        window.routeMarkers = {};
    }
}

// 로딩 상태 표시
function showRouteLoading(isLoading) {
    const container = document.getElementById('route-map');
    if (!container) return;
    
    let loadingDiv = document.getElementById('route-loading');
    
    if (isLoading) {
        if (!loadingDiv) {
            loadingDiv = document.createElement('div');
            loadingDiv.id = 'route-loading';
            loadingDiv.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(255, 255, 255, 0.9);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 1000;
                font-size: 16px;
                color: #333;
            `;
            loadingDiv.innerHTML = `
                <div style="text-align: center;">
                    <div style="width: 30px; height: 30px; border: 3px solid #e0e0e0; border-top: 3px solid #007bff; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 10px;"></div>
                    <div>T-map에서 경로를 생성하고 있습니다...</div>
                </div>
            `;
            container.appendChild(loadingDiv);
        }
    } else {
        if (loadingDiv) {
            loadingDiv.remove();
        }
    }
}

// 에러 메시지 표시
function showRouteError(message) {
    const container = document.getElementById('route-map');
    if (!container) return;
    
    // 기존 에러 메시지 제거
    const existingError = document.getElementById('route-error');
    if (existingError) {
        existingError.remove();
    }
    
    const errorDiv = document.createElement('div');
    errorDiv.id = 'route-error';
    errorDiv.style.cssText = `
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        text-align: center;
        z-index: 1001;
        max-width: 300px;
    `;
    errorDiv.innerHTML = `
        <div style="color: #dc3545; font-size: 18px; margin-bottom: 10px;">⚠️</div>
        <div style="color: #333; margin-bottom: 15px;">${message}</div>
        <button onclick="this.parentElement.remove()" style="
            padding: 8px 16px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        ">확인</button>
    `;
    
    container.appendChild(errorDiv);
}

// 경로 상태 업데이트
// 페이지 로드 시 경로 상태 확인
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎯 Second DOMContentLoaded event - Checking route status and buttons');
    checkRouteStatus();
    
    // 페이지 로드 시 버튼 상태도 함께 확인
    checkRoutesFileExists();
});

// 경로 캐시 상태 확인
async function checkRouteStatus() {
    try {
        console.log('🔍 Checking route cache status...');
        const response = await fetch('/check-route-cache');
        if (response.ok) {
            const data = await response.json();
            console.log('Cache status response:', data);
            
            if (data.has_cache) {
                const generatedTime = new Date(data.generated_at).toLocaleString('ko-KR');
                console.log(`💾 캐시됨 (${generatedTime})`);
            } else {
                console.log('경로 생성 필요');
            }
        }
    } catch (error) {
        console.log('경로 상태 확인 실패:', error);
    }
}
