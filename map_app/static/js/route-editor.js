(function () {
    const ROUTE_FETCH_URL = '/get-routes';
    
    // 현재 활성화된 edit 시나리오 (전역 접근 가능하도록 window에도 설정)
    let currentEditId = null;
    let availableEdits = [];
    
    // 전역 접근을 위해 window 객체에도 설정
    Object.defineProperty(window, 'currentEditId', {
        get: () => currentEditId,
        set: (value) => { currentEditId = value; }
    });

    function resolveProjectQuery() {
        // 1) 현재 위치의 쿼리스트링 사용
        if (window.location && window.location.search && window.location.search.length > 1) {
            return window.location.search;
        }
        // 2) opener 창의 쿼리스트링 확인 (새 창에서 열린 경우)
        try {
            if (window.opener && window.opener.location && window.opener.location.search && window.opener.location.search.length > 1) {
                return window.opener.location.search;
            }
        } catch (e) {
            // cross-origin block
        }
        // 3) window.currentProjectId (메인 앱에서 설정) 활용
        try {
            if (window.currentProjectId) {
                return '?projectId=' + encodeURIComponent(window.currentProjectId);
            }
        } catch (e) {
            // ignore
        }
        // 4) cookie에서 projectId 추출
        try {
            const match = document.cookie.match(/(?:^|; )projectId=([^;]+)/);
            if (match && match[1]) {
                return '?projectId=' + encodeURIComponent(match[1]);
            }
        } catch (e) {
            // ignore
        }
        return '';
    }

    function buildUrlWithEditId(baseUrl, editId) {
        const params = new URLSearchParams();
        const query = resolveProjectQuery();
        if (query) {
            const existing = new URLSearchParams(query.startsWith('?') ? query.slice(1) : query);
            existing.forEach((value, key) => params.set(key, value));
        }
        if (editId) {
            params.set('editId', editId);
        }
        return `${baseUrl}?${params.toString()}`;
    }

    // Load available edit scenarios
    async function loadEditScenarios() {
        try {
            const url = buildUrlWithEditId('/api/edits', null);
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error('Failed to load edit scenarios');
            }
            const data = await response.json();
            if (data.success) {
                availableEdits = data.edits || [];
                renderTabs();
                
                // If no edits exist and user clicks, create first one
                if (availableEdits.length === 0) {
                    console.log('No edit scenarios found. Will create on first interaction.');
                } else {
                    // Auto-select first edit
                    if (!currentEditId && availableEdits.length > 0) {
                        switchToEdit(availableEdits[0].id);
                    }
                }
            }
        } catch (error) {
            console.error('Failed to load edit scenarios:', error);
        }
    }

    // Render tabs
    function renderTabs() {
        const tabList = document.getElementById('tab-list');
        if (!tabList) return;
        
        tabList.innerHTML = '';
        
        availableEdits.forEach(edit => {
            const tabBtn = document.createElement('button');
            tabBtn.className = 'tab-btn';
            if (edit.id === currentEditId) {
                tabBtn.classList.add('active');
            }
            
            const label = document.createElement('span');
            label.textContent = edit.id;
            tabBtn.appendChild(label);
            
            // Close button
            const closeBtn = document.createElement('span');
            closeBtn.className = 'tab-close';
            closeBtn.textContent = '×';
            closeBtn.onclick = async (e) => {
                e.stopPropagation();
                await deleteEdit(edit.id);
            };
            tabBtn.appendChild(closeBtn);
            
            tabBtn.onclick = () => {
                if (edit.id !== currentEditId) {
                    switchToEdit(edit.id);
                }
            };
            
            tabList.appendChild(tabBtn);
        });
    }

    // Switch to a different edit scenario
    async function switchToEdit(editId) {
        currentEditId = editId;
        renderTabs();
        await loadGeneratedRoutes();
    }

    // Create new edit scenario
    async function createNewEdit() {
        try {
            const url = buildUrlWithEditId('/api/edits', null);
            const sourceEditId = availableEdits.length > 0 ? availableEdits[availableEdits.length - 1].id : null;
            
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    sourceEditId: sourceEditId
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to create edit scenario');
            }
            
            const data = await response.json();
            if (data.success) {
                console.log('✅ Created new edit:', data.editId);
                await loadEditScenarios();
                switchToEdit(data.editId);
            }
        } catch (error) {
            console.error('Failed to create edit scenario:', error);
            alert('편집 시나리오를 생성하는데 실패했습니다: ' + error.message);
        }
    }

    // Delete edit scenario
    async function deleteEdit(editId) {
        if (!confirm(`정말 ${editId} 시나리오를 삭제하시겠습니까?`)) {
            return;
        }
        
        try {
            const url = buildUrlWithEditId(`/api/edits/${editId}`, null);
            const response = await fetch(url, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error('Failed to delete edit scenario');
            }
            
            const data = await response.json();
            if (data.success) {
                console.log('✅ Deleted edit:', editId);
                
                // If deleted current edit, switch to another
                if (editId === currentEditId) {
                    currentEditId = null;
                }
                
                await loadEditScenarios();
                
                // Select first available edit
                if (availableEdits.length > 0 && !currentEditId) {
                    switchToEdit(availableEdits[0].id);
                }
            }
        } catch (error) {
            console.error('Failed to delete edit scenario:', error);
            alert('편집 시나리오를 삭제하는데 실패했습니다: ' + error.message);
        }
    }

    function waitForMapStyle(mapInstance) {
        if (!mapInstance) return Promise.resolve();
        return new Promise((resolve) => {
            if (mapInstance.isStyleLoaded && mapInstance.isStyleLoaded()) {
                resolve();
                return;
            }
            if (typeof mapInstance.once === 'function') {
                mapInstance.once('load', () => resolve());
            }
            setTimeout(resolve, 200);
        });
    }

    function getRouteVisualizationMapInstance() {
        try {
            if (typeof routeVisualizationMap !== 'undefined' && routeVisualizationMap) {
                return routeVisualizationMap;
            }
        } catch (e) {
            // ignore reference errors
        }
        if (window.routeMap) return window.routeMap;
        if (window.map) return window.map;
        return null;
    }

    function buildEditedRoutesUrl() {
        const params = new URLSearchParams();
        const query = resolveProjectQuery();
        if (query) {
            const existing = new URLSearchParams(query.startsWith('?') ? query.slice(1) : query);
            existing.forEach((value, key) => params.set(key, value));
        }
        params.set('source', 'edited');
        if (currentEditId) {
            params.set('editId', currentEditId);
        }
        return `${ROUTE_FETCH_URL}?${params.toString()}`;
    }

    async function regenerateEditedRoutes() {
        if (!currentEditId) {
            alert('먼저 편집 시나리오를 선택하거나 생성하세요.');
            return;
        }
        
        const reloadBtn = document.getElementById('route-editor-reload');
        if (reloadBtn) {
            reloadBtn.disabled = true;
            reloadBtn.textContent = '재생성 중...';
        }
        try {
            // 1. edited_routes.csv를 기반으로 T-map API 호출하여 edited_routes.json 재생성
            const regenerateUrl = buildUrlWithEditId('/regenerate-edited-routes', currentEditId);
            console.log('🔄 경로 재생성 요청:', regenerateUrl);
            
            const regenerateResponse = await fetch(regenerateUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    options: {} // 필요시 옵션 추가 가능
                })
            });
            
            if (!regenerateResponse.ok) {
                const errorData = await regenerateResponse.json();
                throw new Error(errorData.error || '경로 재생성에 실패했습니다.');
            }
            
            const regenerateData = await regenerateResponse.json();
            if (!regenerateData.success) {
                throw new Error(regenerateData.error || '경로 재생성에 실패했습니다.');
            }
            
            // 재생성 통계 표시
            const stats = [];
            if (regenerateData.regenerated_count > 0) {
                stats.push(`재생성: ${regenerateData.regenerated_count}개`);
            }
            if (regenerateData.reused_count > 0) {
                stats.push(`재사용: ${regenerateData.reused_count}개`);
            }
            if (regenerateData.deleted_count > 0) {
                stats.push(`삭제: ${regenerateData.deleted_count}개`);
            }
            if (regenerateData.failed_count > 0) {
                stats.push(`실패: ${regenerateData.failed_count}개`);
            }
            
            const message = stats.length > 0 
                ? `✅ 경로 업데이트 완료 (${stats.join(', ')})`
                : '✅ 경로 업데이트 완료';
            
            console.log(message, regenerateData);
            
            // 사용자에게 알림
            if (regenerateData.regenerated_count === 0 && regenerateData.reused_count > 0) {
                alert(`변경사항이 없어 재생성을 건너뛰었습니다.\n${stats.join(', ')}`);
            } else if (regenerateData.failed_count > 0) {
                alert(`${message}\n\n실패한 차량: ${regenerateData.failed_vehicles.join(', ')}`);
            }
            
            // 2. 재생성된 edited_routes.json을 바탕으로 시각화 및 하단 패널 갱신
            await loadGeneratedRoutes();
            
        } catch (error) {
            console.error('경로 재생성 오류:', error);
            alert(error.message || '경로를 재생성하는 중 오류가 발생했습니다.');
        } finally {
            if (reloadBtn) {
                reloadBtn.disabled = false;
                reloadBtn.textContent = 'Reload';
            }
        }
    }

    async function loadGeneratedRoutes() {
        if (!currentEditId) {
            console.log('No edit scenario selected yet.');
            return;
        }
        
        try {
            let mapInstance = getRouteVisualizationMapInstance();
            if (!mapInstance) {
                window.initializeStandaloneRouteMap();
                mapInstance = getRouteVisualizationMapInstance();
            }
            await waitForMapStyle(mapInstance);

            const response = await fetch(buildEditedRoutesUrl());
            if (!response.ok) {
                throw new Error('경로 데이터를 불러오지 못했습니다.');
            }
            const data = await response.json();
            if (!data || !data.success || !data.vehicle_routes) {
                throw new Error(data && data.error ? data.error : '경로 데이터가 비어 있습니다.');
            }

            mapInstance = getRouteVisualizationMapInstance();
            window.displayAndManageRoutes(data.vehicle_routes, mapInstance);
            // Also render the bottom horizontal panel placeholder
            if (typeof renderBottomRoutePanel === 'function') {
                try {
                    renderBottomRoutePanel(data.vehicle_routes);
                } catch (e) {
                    console.error('Failed to render bottom route panel:', e);
                }
            }
        } catch (error) {
            console.error('Route editor load error:', error);
            if (typeof showMapError === 'function') {
                showMapError(error.message || '경로를 불러오는 중 오류가 발생했습니다.');
            } else {
                alert(error.message || '경로를 불러오는 중 오류가 발생했습니다.');
            }
        }
    }

    document.addEventListener('DOMContentLoaded', async () => {
        window.initializeStandaloneRouteMap();
        
        // Setup reload button
        const reloadBtn = document.getElementById('route-editor-reload');
        if (reloadBtn) {
            reloadBtn.addEventListener('click', () => {
                regenerateEditedRoutes();
            });
        }
        
        // Setup add tab button
        const addTabBtn = document.getElementById('add-tab-btn');
        if (addTabBtn) {
            addTabBtn.addEventListener('click', () => {
                createNewEdit();
            });
        }
        
        // Load edit scenarios
        await loadEditScenarios();
        
        // If no edits available, create first one automatically
        if (availableEdits.length === 0) {
            console.log('📝 No edit scenarios found, creating first one...');
            await createNewEdit();
        } else {
            // Load routes for current edit
            await loadGeneratedRoutes();
        }
    });
    
/* Bottom panel rendering: creates rows for each vehicle with left meta and right timeline with time scale and stop markers */
function renderBottomRoutePanel(vehicleRoutes) {
    const panel = document.getElementById('route-bottom-panel');
    if (!panel) return;
    // Rows container inside panel
    let rowsContainer = panel.querySelector('.rbp-rows');
    if (!rowsContainer) {
        rowsContainer = document.createElement('div');
        rowsContainer.className = 'rbp-rows';
        panel.appendChild(rowsContainer);
    }
    // Clear only rows
    rowsContainer.innerHTML = '';

    const colors = window.ROUTE_COLORS || ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F'];
    let idx = 0;

    // 1) Find maximum time across all vehicles for timeline scale
    let maxTime = 0;
    Object.values(vehicleRoutes).forEach((vr) => {
        const totalTime = vr.total_time || 0;
        if (totalTime > maxTime) maxTime = totalTime;
    });

    // If no time data, use a default
    if (maxTime === 0) maxTime = 3600; // 1 hour default

    // 2) Create time scale ticks (every 10 minutes or appropriate interval)
    const timeInterval = calculateTimeInterval(maxTime);
    
    Object.values(vehicleRoutes).forEach((vr) => {
        const vehicleId = vr.vehicle_id || (`v_${idx}`);
        const row = document.createElement('div');
        row.className = 'rbp-row';

        // Create cells directly on the row to align with header grid
        // 1) Checkbox cell
        const chk = document.createElement('div');
        chk.className = 'rbp-cell rbp-cell-check';
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.checked = true;
        input.dataset.vehicleId = vehicleId;
        input.className = 'route-checkbox';
        input.id = `route-check-${vehicleId}`;
        
        // Add event listener for checkbox toggle
        input.addEventListener('change', function() {
            console.log(`📋 Bottom panel checkbox changed: Vehicle ${vehicleId}, checked: ${this.checked}`);
            if (typeof toggleRouteVisibility === 'function') {
                toggleRouteVisibility(vehicleId, this.checked);
            } else {
                console.warn('toggleRouteVisibility function not found');
            }
        });
        
        chk.appendChild(input);
        row.appendChild(chk);

        // 2) Vehicle cell (swatch + name)
        const vcell = document.createElement('div');
        vcell.className = 'rbp-cell rbp-cell-vehicle';
        const sw = document.createElement('span');
        sw.className = 'rbp-swatch';
        sw.style.background = colors[idx % colors.length];
        vcell.appendChild(sw);
        const vname = document.createElement('span');
        vname.textContent = vr.vehicle_name || `Vehicle ${vehicleId}`;
        vcell.appendChild(vname);
        row.appendChild(vcell);

        // 3) Dist
        const dcell = document.createElement('div');
        dcell.className = 'rbp-cell rbp-cell-dist';
        // total_distance is in meters; format as 00.0km
        let distText = '-';
        if (vr.total_distance != null && !isNaN(Number(vr.total_distance))) {
            const km = Number(vr.total_distance) / 1000.0;
            distText = `${km.toFixed(1)}km`;
        } else if (vr.total_distance && typeof vr.total_distance === 'string' && vr.total_distance.includes('km')) {
            distText = vr.total_distance;
        } else if (vr.dist) {
            distText = vr.dist;
        }
        dcell.textContent = distText;
        row.appendChild(dcell);

        // 4) Time
        const tcell = document.createElement('div');
        tcell.className = 'rbp-cell rbp-cell-time';
        // total_time may be in seconds; convert to MM분 SS초
        let timeText = '-';
        const totalTime = vr.total_time || 0;
        if (vr.total_time != null && !isNaN(Number(vr.total_time))) {
            const secs = Number(vr.total_time);
            const totalSeconds = secs;
            const minutes = Math.floor(totalSeconds / 60);
            const seconds = Math.floor(totalSeconds % 60);
            timeText = `${String(minutes).padStart(2,'0')}분 ${String(seconds).padStart(2,'0')}초`;
        } else if (vr.total_time && typeof vr.total_time === 'string' && vr.total_time.includes('min')) {
            timeText = vr.total_time;
        } else if (vr.time) {
            timeText = vr.time;
        }
        tcell.textContent = timeText;
        row.appendChild(tcell);

        // 5) Load
        const lcell = document.createElement('div');
        lcell.className = 'rbp-cell rbp-cell-load';
        // prefer route_load, fallback to load
        let loadText = '-';
        if (vr.route_load != null) {
            loadText = String(vr.route_load);
        } else if (vr.load != null) {
            loadText = String(vr.load);
        } else if (vr.load_description) {
            loadText = String(vr.load_description);
        }
        lcell.textContent = loadText;
        row.appendChild(lcell);

        // 6) Timeline cell (fills remaining space)
        const timelineCell = document.createElement('div');
        timelineCell.className = 'rbp-cell rbp-cell-timeline';
        const timelineOuter = document.createElement('div');
        timelineOuter.className = 'rbp-timeline';
        
        // Add background bar
        const bar = document.createElement('div');
        bar.className = 'rbp-bar';
        bar.style.background = colors[idx % colors.length];
        bar.style.width = `${(totalTime / maxTime) * 100}%`;
        timelineOuter.appendChild(bar);
        
        // Add stop markers along the timeline
        if (vr.waypoints && Array.isArray(vr.waypoints)) {
            addStopMarkers(timelineOuter, vr.waypoints, maxTime, colors[idx % colors.length]);
        }

        // Add 15-minute vertical grid ticks (no text) -> 15 minutes = 900 seconds
        (function addGridTicks(timelineEl, totalSeconds) {
            try {
                const intervalSec = 10 * 60; // 600 seconds
                if (!timelineEl || !totalSeconds || totalSeconds <= 0) return;
                // Remove existing ticks if any
                const existing = timelineEl.querySelectorAll('.rbp-grid-tick');
                existing.forEach(n => n.remove());

                // Create ticks across 0..totalSeconds inclusive
                let tickIndex = 0;
                for (let t = intervalSec; t < totalSeconds; t += intervalSec) {
                    tickIndex += 1;
                    const leftPercent = (t / totalSeconds) * 100;
                    const tick = document.createElement('div');
                    tick.className = 'rbp-grid-tick';
                    // every 6th 10-min tick = 60 minutes -> mark as hour tick
                    if (tickIndex % 6 === 0) {
                        tick.classList.add('rbp-grid-tick-hour');
                    }
                    tick.style.left = `${leftPercent}%`;
                    timelineEl.appendChild(tick);
                }
            } catch (e) {
                // non-fatal
                console.warn('Grid ticks render error:', e);
            }
        })(timelineOuter, maxTime);
        
        timelineCell.appendChild(timelineOuter);
        row.appendChild(timelineCell);

        rowsContainer.appendChild(row);
        idx += 1;
    });
}

/**
 * Calculate appropriate time interval for timeline ticks based on max time
 */
function calculateTimeInterval(maxTimeSeconds) {
    // Choose interval based on total time duration
    if (maxTimeSeconds <= 600) return 60; // 1 min for <= 10 min
    if (maxTimeSeconds <= 1800) return 300; // 5 min for <= 30 min
    if (maxTimeSeconds <= 3600) return 600; // 10 min for <= 1 hour
    if (maxTimeSeconds <= 7200) return 900; // 15 min for <= 2 hours
    return 1800; // 30 min for longer durations
}

/**
 * Format time in seconds to display label (e.g., "15분", "1시간")
 */
function formatTimeLabel(seconds) {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        if (mins > 0) {
            return `${hours}시간 ${mins}분`;
        }
        return `${hours}시간`;
    }
    if (mins > 0) {
        return `${mins}분`;
    }
    return `${secs}초`;
}

/**
 * Format seconds to MM분 SS초 (zero-padded minutes and seconds)
 */
function formatTimeMMSS(seconds) {
    const totalSec = Math.max(0, Math.floor(Number(seconds) || 0));
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${String(mins).padStart(2,'0')}분 ${String(secs).padStart(2,'0')}초`;
}

/**
 * Add stop markers to timeline based on cumulative_time of each waypoint
 */
function addStopMarkers(timelineContainer, waypoints, maxTime, vehicleColor) {
    waypoints.forEach((waypoint, index) => {
        const isDepot = waypoint.type === 'depot';
        
        // Get cumulative time - if not available, estimate based on position
        let cumulativeTime = 0;
        if (waypoint.cumulative_time != null) {
            cumulativeTime = waypoint.cumulative_time;
        } else if (waypoint.cumulative_distance != null && waypoint.total_distance) {
            // Estimate time based on distance proportion
            const distProportion = waypoint.cumulative_distance / waypoint.total_distance;
            cumulativeTime = distProportion * maxTime;
        } else {
            // Fallback: distribute evenly
            cumulativeTime = (index / (waypoints.length - 1)) * maxTime;
        }
            
            // Create marker element
            const marker = document.createElement('div');
            marker.className = 'rbp-stop-marker';
            if (isDepot) marker.classList.add('depot-marker');

            // Set visual label: start(S), middle numbers, end(G)
            let label = '';
            if (index === 0) {
                label = 'S';
            } else if (index === waypoints.length - 1) {
                label = 'G';
            } else {
                label = String(index);
            }
            marker.textContent = label;

            marker.style.left = `${(cumulativeTime / maxTime) * 100}%`;
            marker.style.borderColor = vehicleColor;

            // Add tooltip with stop info: name, demand, time (MM분 SS초), distance (00.00km)
            const nameText = waypoint.name || `정류장 ${index + 1}`;
            const demandText = (waypoint.demand != null) ? String(waypoint.demand) : '-';
            const timeText = formatTimeMMSS(cumulativeTime);
            let distanceText = '-';
            if (waypoint.cumulative_distance != null && !isNaN(Number(waypoint.cumulative_distance))) {
                distanceText = `${(Number(waypoint.cumulative_distance) / 1000).toFixed(2)}km`;
            } else if (waypoint.cumulative_distance && typeof waypoint.cumulative_distance === 'string' && waypoint.cumulative_distance.includes('km')) {
                distanceText = waypoint.cumulative_distance;
            }
            marker.title = `${nameText}\n수요량: ${demandText}\n시간: ${timeText}\n거리: ${distanceText}`;
        
        // Add click event to toggle tooltip and highlight on map
        marker.addEventListener('click', (ev) => {
            ev.stopPropagation(); // prevent document click handler from immediately closing
            // Close any other open tooltips
            document.querySelectorAll('.rbp-stop-marker.show-tooltip').forEach(el => {
                if (el !== marker) el.classList.remove('show-tooltip');
            });
            // Toggle this marker's tooltip
            marker.classList.toggle('show-tooltip');
            console.log('Stop marker clicked (tooltip toggled):', waypoint);
            // TODO: Highlight this stop on the map
        });
        
        timelineContainer.appendChild(marker);
    });

    // Close tooltips when clicking outside any marker
    if (!document._rbp_tooltip_click_listener_installed) {
        document.addEventListener('click', (ev) => {
            document.querySelectorAll('.rbp-stop-marker.show-tooltip').forEach(el => el.classList.remove('show-tooltip'));
        });
        document._rbp_tooltip_click_listener_installed = true;
    }
}

// Initialize collapse/expand toggle for bottom panel

})();

/**
 * Route Editor에서만 사용하는 기능: 마커를 드래그 가능하게 만들고, 위치 변경 시 서버에 업데이트
 */
(function initializeMarkerDragging() {
    // displayAndManageRoutes 함수를 래핑하여 마커 생성 후 드래그 기능 추가
    const originalDisplayAndManageRoutes = window.displayAndManageRoutes;
    
    if (!originalDisplayAndManageRoutes) {
        console.warn('⚠️ displayAndManageRoutes 함수를 찾을 수 없습니다.');
        return;
    }
    
    // 원본 함수를 오버라이드
    window.displayAndManageRoutes = function(vehicleRoutes, mapInstance) {
        // 원본 함수 실행 (경로 및 마커 표시)
        originalDisplayAndManageRoutes.call(this, vehicleRoutes, mapInstance);
        
        // Route Editor에서만 마커를 드래그 가능하게 설정
        if (!isRouteEditorPage()) {
            return;
        }
        
        console.log('🎯 Route Editor 감지됨 - 마커 드래그 기능 활성화');
        
        // 모든 마커를 드래그 가능하게 설정
        if (window.routeMarkers) {
            Object.entries(window.routeMarkers).forEach(([vehicleId, markers]) => {
                markers.forEach((marker, markerIndex) => {
                    // 마커 요소에서 정류장 정보 추출
                    const markerElement = marker.getElement();
                    const markerType = markerElement?.querySelector('[data-marker-type]')?.getAttribute('data-marker-type');
                    
                    // depot 마커는 드래그 불가 (시작/종료점)
                    if (markerType === 'start' || markerType === 'end') {
                        return;
                    }
                    
                    // 마커를 드래그 가능하게 설정
                    marker.setDraggable(true);
                    
                    // 드래그 종료 이벤트 리스너 추가
                    marker.on('dragend', async function() {
                        const lngLat = marker.getLngLat();
                        console.log(`📍 마커 드래그 완료: Vehicle ${vehicleId}, Marker ${markerIndex}, 새 위치: [${lngLat.lng}, ${lngLat.lat}]`);
                        
                        // 해당 차량의 경로 데이터에서 정류장 정보 찾기
                        const vehicleRoute = vehicleRoutes[vehicleId];
                        if (!vehicleRoute || !vehicleRoute.waypoints) {
                            console.error('❌ 차량 경로 데이터를 찾을 수 없습니다.');
                            return;
                        }
                        
                        const waypoint = vehicleRoute.waypoints[markerIndex];
                        if (!waypoint) {
                            console.error('❌ 정류장 데이터를 찾을 수 없습니다.');
                            return;
                        }
                        
                        const stopId = waypoint.id || waypoint.location_id;
                        if (!stopId) {
                            console.error('❌ 정류장 ID를 찾을 수 없습니다.');
                            return;
                        }
                        
                        // 서버에 위치 업데이트 요청
                        try {
                            await updateStopLocationOnServer(stopId, lngLat.lat, lngLat.lng);
                            
                            // 성공 메시지 표시 (optional)
                            showTemporaryMessage(`✅ 정류장 ${waypoint.name || stopId}의 위치가 업데이트되었습니다.`);
                        } catch (error) {
                            console.error('❌ 위치 업데이트 실패:', error);
                            alert(`위치 업데이트에 실패했습니다: ${error.message}`);
                            
                            // 실패 시 마커를 원래 위치로 되돌림
                            marker.setLngLat([waypoint.x, waypoint.y]);
                        }
                    });
                });
            });
        }
    };
    
    /**
     * Route Editor 페이지인지 확인
     */
    function isRouteEditorPage() {
        // URL에 route_editor가 포함되어 있는지 확인
        return window.location.pathname.includes('route_editor') || 
               document.getElementById('route-editor-reload') !== null;
    }
    
    /**
     * 서버에 정류장 위치 업데이트 요청
     */
    async function updateStopLocationOnServer(stopId, lat, lon) {
        const params = new URLSearchParams();
        const query = resolveProjectQuery();
        if (query) {
            const existing = new URLSearchParams(query.startsWith('?') ? query.slice(1) : query);
            existing.forEach((value, key) => params.set(key, value));
        }
        
        // window.currentEditId 사용
        if (window.currentEditId) {
            params.set('editId', window.currentEditId);
        } else {
            throw new Error('편집 시나리오(editId)가 선택되지 않았습니다.');
        }
        
        const url = `/api/update-stop-location?${params.toString()}`;
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                stopId: stopId,
                lat: lat,
                lon: lon
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || '위치 업데이트에 실패했습니다.');
        }
        
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || '위치 업데이트에 실패했습니다.');
        }
        
        console.log('✅ 서버 업데이트 성공:', data);
        return data;
    }
    
    /**
     * resolveProjectQuery 함수 (route-editor.js에서 가져옴)
     */
    function resolveProjectQuery() {
        if (window.location && window.location.search && window.location.search.length > 1) {
            return window.location.search;
        }
        try {
            if (window.opener && window.opener.location && window.opener.location.search && window.opener.location.search.length > 1) {
                return window.opener.location.search;
            }
        } catch (e) {
            // cross-origin block
        }
        try {
            if (window.currentProjectId) {
                return '?projectId=' + encodeURIComponent(window.currentProjectId);
            }
        } catch (e) {
            // ignore
        }
        try {
            const match = document.cookie.match(/(?:^|; )projectId=([^;]+)/);
            if (match && match[1]) {
                return '?projectId=' + encodeURIComponent(match[1]);
            }
        } catch (e) {
            // ignore
        }
        return '';
    }
    
    /**
     * 임시 메시지 표시 (3초 후 자동 사라짐)
     */
    function showTemporaryMessage(message) {
        // 기존 메시지가 있으면 제거
        const existingMsg = document.getElementById('temp-message');
        if (existingMsg) {
            existingMsg.remove();
        }
        
        // 새 메시지 생성
        const msgDiv = document.createElement('div');
        msgDiv.id = 'temp-message';
        msgDiv.textContent = message;
        msgDiv.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            background: #28a745;
            color: white;
            padding: 12px 20px;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            z-index: 10000;
            font-size: 14px;
            font-weight: 500;
            animation: slideIn 0.3s ease-out;
        `;
        
        document.body.appendChild(msgDiv);
        
        // 3초 후 제거
        setTimeout(() => {
            msgDiv.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => msgDiv.remove(), 300);
        }, 3000);
    }
    
    // CSS 애니메이션 추가
    if (!document.getElementById('temp-message-styles')) {
        const style = document.createElement('style');
        style.id = 'temp-message-styles';
        style.textContent = `
            @keyframes slideIn {
                from {
                    transform: translateX(400px);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            @keyframes slideOut {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(400px);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }
})();
