/**
 * Route Visualization JavaScript Module
 * 독립적인 route visualization 기능을 제공
 */

// Mapbox access token (빠른 통합: 앱과 동일 토큰 사용)
mapboxgl.accessToken = window.MAPBOX_ACCESS_TOKEN;

let routeVisualizationMap = null;
// legacy routeData 제거됨 (내보내기 기능 삭제와 함께 불필요)

/**
 * 중앙 정렬된 번호 마커 요소(SVG) 생성
 * - 원형 배경 + 가운데 숫자
 * - 토글/정리 로직 호환을 위해 data-vehicle-id 유지
 */
function createNumberedMarkerElement(number, color, vehicleId) {
    const wrapper = document.createElement('div');
    wrapper.className = 'custom-marker';
    wrapper.setAttribute('data-vehicle-id', vehicleId);
    wrapper.setAttribute('data-marker-type', 'stop');

    // SVG를 사용해 텍스트를 정확히 중앙 배치 (text-anchor, dominant-baseline)
    const size = 32; // 외곽 크기
    const radius = 14; // 원 반지름 (stroke 고려)
    const strokeWidth = 3;
    const label = String(number);
    // 자릿수에 따라 폰트 크기 조정 (2자리/3자리 대응)
    const fontSize = label.length <= 1 ? 12 : (label.length === 2 ? 11 : 10);
    wrapper.innerHTML = `
        <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" style="display:block;overflow:visible;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.3))">
            <circle cx="${size/2}" cy="${size/2}" r="${radius}" fill="${color}" stroke="#ffffff" stroke-width="${strokeWidth}" />
            <text x="${size/2}" y="${size/2}"
                  fill="#ffffff" font-size="${fontSize}" font-weight="700"
                  text-anchor="middle" dominant-baseline="central"
                  style="font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;">
                ${label}
            </text>
        </svg>
    `;

    return wrapper;
}

/**
 * 독립적인 route visualization 지도 초기화
 */
function initializeStandaloneRouteMap() {
    const container = document.getElementById('route-map');
    if (!container) {
        console.error('Route map container not found');
        return;
    }

    // 기존 지도가 있으면 제거
    if (routeVisualizationMap) {
        try {
            routeVisualizationMap.remove();
        } catch (error) {
            console.warn('Error removing existing map:', error);
        }
        routeVisualizationMap = null;
        window.routeVisualizationMap = null;
    }

    try {
        // 새로운 지도 생성
        routeVisualizationMap = new mapboxgl.Map({
            container: 'route-map',
            style: 'mapbox://styles/mapbox/light-v11',
            center: [126.9779, 37.5547], // 서울 중심
            zoom: 11,
            attributionControl: true
        });
        window.routeVisualizationMap = routeVisualizationMap;

        // 지도 로드 완료 후 추가 초기화
        routeVisualizationMap.on('load', () => {
            console.log('Standalone route map initialized successfully');
            
            // 컨트롤 좌측 배치
            routeVisualizationMap.addControl(new mapboxgl.NavigationControl(), 'top-left');
            routeVisualizationMap.addControl(new mapboxgl.ScaleControl({ maxWidth: 80, unit: 'metric' }), 'bottom-left');
            routeVisualizationMap.addControl(new mapboxgl.FullscreenControl(), 'top-left');
        });

        // 에러 핸들링
        routeVisualizationMap.on('error', (e) => {
            console.error('Route map error:', e);
        });

    } catch (error) {
        console.error('Failed to initialize route map:', error);
        showMapError('지도를 초기화할 수 없습니다. 인터넷 연결을 확인해주세요.');
    }
}

/**
 * 팝업 모달용 route visualization 지도 초기화
 */
// initializeModalRouteMap: 사용처가 없어 제거

/**
 * 라우트 데이터 로드 및 지도에 표시
 */
// loadRouteData: 통합 경로 렌더(displayAndManageRoutes) 도입으로 제거

/**
 * 지도에 라우트 표시
 */
// displayRoutesOnMap: 통합 경로 렌더 사용으로 제거

/**
 * 라우트 라인을 지도에 추가
 */
// addRouteLineToMap: 통합 경로 렌더 사용으로 제거

/**
 * 정류장/포인트를 지도에 추가
 */
// addStopsToMap: 통합 경로 렌더 사용으로 제거

/**
 * 라우트에 맞게 지도 범위 조정
 */
// fitMapToRoutes: 통합 경로 렌더 사용으로 제거

/**
 * 라우트 색상 생성
 */
// getRouteColor: 사용처 제거됨

/**
 * 지도 레이어 초기화
 */
// clearMapLayers: clearAllRouteLayers 사용으로 대체

/**
 * 지도 에러 메시지 표시
 */
function showMapError(message) {
    const container = document.getElementById('route-map');
    if (container) {
        container.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: center; height: 100%; background: #f8f9fa; color: #666; text-align: center; padding: 20px;">
                <div>
                    <div style="font-size: 18px; margin-bottom: 10px;">⚠️</div>
                    <div>${message}</div>
                </div>
            </div>
        `;
    }
}

/**
 * 라우트 통계 업데이트
 */
// updateRouteStatistics: 전체 뷰에서 통계 UI 제거로 불필요

/**
 * 라우트 데이터 내보내기
 */
// exportRouteData: 사용처 없음으로 제거

/**
 * 라우트 데이터를 CSV로 변환
 */
// convertRoutesToCSV: export 기능 제거와 함께 삭제

/**
 * 라우팅 정보 테이블 업데이트
 */
function updateRouteInfoTable(vehicleRoutes) {
    console.log('🔄 updateRouteInfoTable 호출됨:', vehicleRoutes);
    
    // 먼저 오버레이가 존재하는지 확인
    const overlay = document.getElementById('route-info-overlay');
    console.log('🎭 오버레이 요소 존재?:', overlay);
    
    const tbody = document.getElementById('route-info-tbody');
    console.log('📋 테이블 tbody 요소:', tbody);
    
    // HTML 구조 전체 확인
    console.log('🏗️ 현재 HTML에서 route-info 관련 요소들:');
    console.log('- route-info-overlay:', !!document.getElementById('route-info-overlay'));
    console.log('- route-info-table:', !!document.getElementById('route-info-table'));
    console.log('- route-info-tbody:', !!document.getElementById('route-info-tbody'));
    
    if (!tbody) {
        console.error('❌ route-info-tbody 요소를 찾을 수 없습니다!');
        return;
    }
    
    if (!vehicleRoutes) {
        console.error('❌ vehicleRoutes 데이터가 없습니다!');
        return;
    }
    
    // 기존 테이블 내용 초기화
    tbody.innerHTML = '';
    
    const colors = window.ROUTE_COLORS || ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F'];
    let routeIndex = 0;
    
    Object.values(vehicleRoutes).forEach((vehicleRoute) => {
        const vehicleId = vehicleRoute.vehicle_id;
        const color = colors[routeIndex % colors.length];
        
        console.log(`🚗 차량 정보 처리 중: Vehicle ${vehicleId}`);
        
        // 거리와 시간 계산
        const totalDistance = vehicleRoute.total_distance || 0;
        const totalTime = vehicleRoute.total_time || 0;
        
        // Load 계산: 백엔드에서 제공하는 차량별 최종 누적값(route_load)이 있으면 사용
        // 없다면 폴백으로 waypoints의 demand 합계를 사용
        let totalLoad = 0;
        if (typeof vehicleRoute.route_load === 'number' && !isNaN(vehicleRoute.route_load)) {
            totalLoad = vehicleRoute.route_load;
        } else if (vehicleRoute.waypoints) {
            vehicleRoute.waypoints.forEach(waypoint => {
                if (waypoint.type !== 'depot') {
                    totalLoad += waypoint.demand || 0;
                }
            });
        }
        
        // 거리 포맷팅 (미터 -> km)
        const distanceText = totalDistance >= 1000 
            ? `${(totalDistance / 1000).toFixed(1)}km`
            : `${totalDistance}m`;
        
        // 시간 포맷팅 (초 -> 분)
        const timeText = totalTime >= 60 
            ? `${Math.floor(totalTime / 60)}분 ${totalTime % 60}초`
            : `${totalTime}초`;
        
        // 테이블 행 생성
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <input type="checkbox" 
                       class="route-checkbox" 
                       id="route-check-${vehicleId}" 
                       data-vehicle-id="${vehicleId}"
                       checked>
            </td>
            <td>
                <div style="display: flex; align-items: center; gap: 6px;">
                    <div style="width: 12px; height: 12px; background-color: ${color}; border-radius: 2px;"></div>
                    Vehicle ${vehicleId}
                </div>
            </td>
            <td>${distanceText}</td>
            <td>${timeText}</td>
            <td>${totalLoad}</td>
        `;
        
        tbody.appendChild(row);
        
        // 체크박스 이벤트 바인딩 (더 안전한 방식)
        const checkbox = document.getElementById(`route-check-${vehicleId}`);
        console.log(`🔍 체크박스 찾기: route-check-${vehicleId}`, checkbox);
        
        if (checkbox) {
            console.log(`✅ 체크박스 발견, 이벤트 바인딩 중: Vehicle ${vehicleId}`);
            checkbox.addEventListener('change', function() {
                console.log(`📋 체크박스 변경 이벤트 발생! Vehicle ${vehicleId}, checked: ${this.checked}`);
                toggleRouteVisibility(vehicleId, this.checked);
            });
            
            // 테스트를 위해 클릭 이벤트도 추가
            checkbox.addEventListener('click', function() {
                console.log(`🖱️ 체크박스 클릭 이벤트! Vehicle ${vehicleId}`);
            });
        } else {
            console.error(`❌ 체크박스를 찾을 수 없음: route-check-${vehicleId}`);
        }
        routeIndex++;
    });
    
    console.log(`✅ 라우팅 정보 테이블 업데이트 완료. 총 ${routeIndex}개 차량 처리됨`);
    
    // 이벤트 위임 방식으로도 체크박스 이벤트 바인딩
    const table = document.getElementById('route-info-table');
    if (table) {
        // 기존 이벤트 제거 (중복 방지)
        table.removeEventListener('change', handleCheckboxChange);
        // 새 이벤트 추가
        table.addEventListener('change', handleCheckboxChange);
        console.log('📋 테이블에 이벤트 위임 방식으로 체크박스 이벤트 바인딩 완료');
    }
}

// (삭제됨) 테스트 버튼 관련 로직 제거

// 체크박스 변경 이벤트 핸들러
function handleCheckboxChange(event) {
    if (event.target.classList.contains('route-checkbox')) {
        const vehicleId = event.target.getAttribute('data-vehicle-id');
        const isChecked = event.target.checked;
        console.log(`🔄 이벤트 위임으로 체크박스 변경 감지: Vehicle ${vehicleId}, checked: ${isChecked}`);
        toggleRouteVisibility(vehicleId, isChecked);
    }
}

/**
 * 경로 표시/숨김 토글 함수
 */
function toggleRouteVisibility(vehicleId, isVisible) {
    console.log(`🔄 toggleRouteVisibility 호출: Vehicle ${vehicleId}, visible: ${isVisible}`);
    
    // 여러 방법으로 지도 객체 찾기
    console.log('🔍 지도 객체 탐색 중...');
    console.log('- window.routeMap:', window.routeMap);
    console.log('- routeVisualizationMap:', routeVisualizationMap);
    console.log('- window.map:', window.map);
    
    const currentMap = window.routeMap || routeVisualizationMap || window.map;
    
    if (!currentMap) {
        console.error('❌ 지도 객체를 찾을 수 없습니다!');
        console.log('🔍 사용 가능한 전역 객체들:');
        console.log('- window 객체의 키들:', Object.keys(window).filter(k => k.includes('map') || k.includes('Map')));
        return;
    }
    
    console.log('✅ 지도 객체 찾음:', currentMap);
    
    // 가시성 상태 업데이트
    if (window.vehicleVisibility) {
        window.vehicleVisibility[vehicleId] = isVisible;
    }
    
    try {
        // 1. 경로 라인 표시/숨김
        const layerId = `route-layer-${vehicleId}`;
        if (currentMap.getLayer(layerId)) {
            currentMap.setLayoutProperty(layerId, 'visibility', isVisible ? 'visible' : 'none');
            console.log(`✅ 라인 레이어 ${layerId}: ${isVisible ? 'visible' : 'hidden'}`);
        }
        
        // 2. 마커들 표시/숨김 (새로운 방식)
        if (window.routeMarkers && window.routeMarkers[vehicleId]) {
            window.routeMarkers[vehicleId].forEach(marker => {
                const element = marker.getElement();
                if (element) {
                    element.style.display = isVisible ? 'block' : 'none';
                }
            });
            console.log(`✅ 차량 ${vehicleId}의 ${window.routeMarkers[vehicleId].length}개 마커: ${isVisible ? 'visible' : 'hidden'}`);
        }
        
        // 3. 대안으로 DOM 요소 직접 제어 (지도 내 마커로 한정)
        //    체크박스 등 오버레이 UI는 data-vehicle-id를 공유하므로 절대 건드리지 않음
        const mapContainer = document.getElementById('route-map');
        if (mapContainer) {
            const markerElements = mapContainer.querySelectorAll(`.mapboxgl-marker [data-vehicle-id="${vehicleId}"], .mapboxgl-marker[data-vehicle-id="${vehicleId}"]`);
            markerElements.forEach(element => {
                const wrapper = element.classList.contains('mapboxgl-marker') ? element : element.closest('.mapboxgl-marker');
                if (wrapper) {
                    wrapper.style.display = isVisible ? 'block' : 'none';
                }
            });
        }
        
        console.log(`✅ Vehicle ${vehicleId} 가시성 변경 완료: ${isVisible}`);
        
    } catch (error) {
        console.error('❌ 가시성 변경 중 오류:', error);
    }
}

/**
 * 통합된 경로 표출 및 관리 함수
 */
function displayAndManageRoutes(vehicleRoutes, mapInstance) {
    console.log('🗺️ displayAndManageRoutes 시작:', vehicleRoutes, mapInstance);
    
    if (!mapInstance || !vehicleRoutes) {
        console.error('❌ 지도 인스턴스 또는 경로 데이터가 없습니다');
        return;
    }
    
    // 기존 경로 레이어들 제거
    clearAllRouteLayers(mapInstance);
    
    const bounds = new mapboxgl.LngLatBounds();
    const colors = window.ROUTE_COLORS || ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F'];
    const vehicleVisibility = {}; // 각 차량의 표시 상태 관리
    
    let routeIndex = 0;
    
    Object.values(vehicleRoutes).forEach((vehicleRoute) => {
        const color = colors[routeIndex % colors.length];
        const vehicleId = vehicleRoute.vehicle_id;
        vehicleVisibility[vehicleId] = true; // 초기에는 모든 경로 표시
        
        console.log(`🚗 차량 ${vehicleId} 경로 처리 중...`);
        
        // 1. 경로 라인 추가
        if (vehicleRoute.route_geometry && vehicleRoute.route_geometry.coordinates) {
            const sourceId = `route-source-${vehicleId}`;
            const layerId = `route-layer-${vehicleId}`;
            
            try {
                // 소스 추가
                mapInstance.addSource(sourceId, {
                    type: 'geojson',
                    data: {
                        type: 'Feature',
                        geometry: vehicleRoute.route_geometry
                    }
                });
                
                // 레이어 추가
                mapInstance.addLayer({
                    id: layerId,
                    type: 'line',
                    source: sourceId,
                    layout: {
                        'line-join': 'round',
                        'line-cap': 'round'
                    },
                    paint: {
                        'line-color': color,
                        'line-width': 4,
                        'line-opacity': 0.8
                    }
                });
                
                console.log(`✅ 차량 ${vehicleId} 경로 라인 추가 완료`);
                
            } catch (error) {
                console.error(`❌ 차량 ${vehicleId} 경로 라인 추가 실패:`, error);
            }
        }
        
        // 2. 마커들 추가
        if (vehicleRoute.waypoints) {
            vehicleRoute.waypoints.forEach((waypoint, index) => {
                const isDepot = waypoint.type === 'depot';
                const isStart = index === 0;
                const isEnd = index === vehicleRoute.waypoints.length - 1;

                // 마커 요소 생성 (정류장은 SVG 기반 번호 마커로 생성)
                let markerElement;
                if (isDepot) {
                    // 출발지/도착지 마커 (기존 스타일 유지)
                    markerElement = document.createElement('div');
                    markerElement.className = 'custom-marker';
                    markerElement.setAttribute('data-vehicle-id', vehicleId);
                    markerElement.setAttribute('data-marker-type', 'depot');
                    markerElement.style.cssText = `
                        width: 24px;
                        height: 24px;
                        background-color: ${isStart ? '#28a745' : '#dc3545'};
                        border: 2px solid white;
                        border-radius: 3px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: white;
                        font-weight: bold;
                        font-size: 9px;
                        box-shadow: 0 2px 6px rgba(0,0,0,0.4);
                    `;
                    markerElement.textContent = isStart ? 'START' : 'END';
                } else if (isEnd) {
                    // 경로의 마지막 종료 지점: 사각형, 붉은 색, 텍스트 'G' (크기 유지)
                    markerElement = document.createElement('div');
                    markerElement.className = 'custom-marker';
                    markerElement.setAttribute('data-vehicle-id', vehicleId);
                    markerElement.setAttribute('data-marker-type', 'end');
                    // SVG 기반으로 생성해 크기/텍스트 정렬을 기존 번호 마커와 동일하게 유지
                    const size = 32;
                    const rectSize = 28; // 내부 사각형 크기
                    const strokeWidth = 3;
                    const fillColor = '#dc3545'; // 통일된 붉은 색
                    markerElement.innerHTML = `\n                        <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" style="display:block;overflow:visible;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.3))">\n                            <rect x="${(size-rectSize)/2}" y="${(size-rectSize)/2}" width="${rectSize}" height="${rectSize}" rx="2" ry="2" fill="${fillColor}" stroke="#ffffff" stroke-width="${strokeWidth}" />\n                            <text x="${size/2}" y="${size/2}"\n                                  fill="#ffffff" font-size="12" font-weight="700"\n                                  text-anchor="middle" dominant-baseline="central"\n                                  style="font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;">\n                                G\n                            </text>\n                        </svg>\n                    `;
                } else {
                    // 번호 마커: 시작 지점은 'S'로 표시하고 나머지는 번호로 표시
                    const labelForMarker = isStart ? 'S' : index;
                    markerElement = createNumberedMarkerElement(labelForMarker, color, vehicleId);
                }

                // 팝업 생성
                const popupContent = isDepot 
                    ? `<div style="font-size: 12px;">
                         <strong>🏢 DEPOT</strong><br>
                         <strong>${waypoint.name}</strong><br>
                         <span style="color: ${isStart ? '#28a745' : '#dc3545'};">
                           ${isStart ? '🚀 출발지' : '🏁 도착지'}
                         </span>
                       </div>`
                    : `<div style="font-size: 12px;">
                         <strong>🚏 정류장 ${index}</strong><br>
                         <strong>${waypoint.name}</strong><br>
                         수요량: ${waypoint.demand || 0}
                       </div>`;
                
                const popup = new mapboxgl.Popup({ offset: 25 }).setHTML(popupContent);
                
                // 마커 추가
                const marker = new mapboxgl.Marker(markerElement)
                    .setLngLat([waypoint.x, waypoint.y])
                    .setPopup(popup)
                    .addTo(mapInstance);
                
                // 마커 객체를 저장하여 나중에 제어할 수 있도록
                if (!window.routeMarkers) window.routeMarkers = {};
                if (!window.routeMarkers[vehicleId]) window.routeMarkers[vehicleId] = [];
                window.routeMarkers[vehicleId].push(marker);
                
                bounds.extend([waypoint.x, waypoint.y]);
            });
        }
        
        routeIndex++;
    });
    
    // 지도 범위 조정
    if (!bounds.isEmpty()) {
        mapInstance.fitBounds(bounds, {
            padding: 50,
            maxZoom: 15
        });
    }
    
    // 차량 가시성 상태 저장
    window.vehicleVisibility = vehicleVisibility;
    
    // 정보 테이블 업데이트
    updateRouteInfoTable(vehicleRoutes);
    
    console.log(`✅ 모든 경로 표출 완료. 총 ${routeIndex}개 차량`);
}

/**
 * 모든 경로 관련 레이어와 마커 제거
 */
function clearAllRouteLayers(mapInstance) {
    console.log('🧹 기존 경로 레이어들 정리 중...');
    
    if (!mapInstance) return;
    
    // 기존 마커들 제거
    if (window.routeMarkers) {
        Object.values(window.routeMarkers).forEach(markers => {
            markers.forEach(marker => marker.remove());
        });
        window.routeMarkers = {};
    }
    
    // 기존 레이어들 제거
    const layers = mapInstance.getStyle().layers;
    const sources = mapInstance.getStyle().sources;
    
    layers.forEach(layer => {
        if (layer.id.startsWith('route-layer-')) {
            try {
                mapInstance.removeLayer(layer.id);
            } catch (e) {
                console.warn('레이어 제거 실패:', layer.id);
            }
        }
    });
    
    Object.keys(sources).forEach(sourceId => {
        if (sourceId.startsWith('route-source-')) {
            try {
                mapInstance.removeSource(sourceId);
            } catch (e) {
                console.warn('소스 제거 실패:', sourceId);
            }
        }
    });

    // 레거시(미추적) 마커 DOM도 정리: data-vehicle-id를 가진 marker 래퍼 제거
    try {
        const orphanMarkers = document.querySelectorAll('.mapboxgl-marker [data-vehicle-id], .mapboxgl-marker[data-vehicle-id]');
        orphanMarkers.forEach(child => {
            const wrapper = child.classList.contains('mapboxgl-marker') ? child : child.closest('.mapboxgl-marker');
            if (wrapper && wrapper.parentElement) {
                wrapper.parentElement.removeChild(wrapper);
            }
        });
    } catch (e) {
        console.warn('레거시 마커 DOM 정리 중 경고:', e);
    }
}

// 전역 함수로 노출 (하위 호환성을 위해)
window.initializeStandaloneRouteMap = initializeStandaloneRouteMap;
window.updateRouteInfoTable = updateRouteInfoTable;
window.toggleRouteVisibility = toggleRouteVisibility;
window.handleCheckboxChange = handleCheckboxChange;
window.displayAndManageRoutes = displayAndManageRoutes;
window.clearAllRouteLayers = clearAllRouteLayers;

// --- Route Info Collapse/Expand ---
(function setupRouteInfoToggle() {
    function init() {
        // 지원되는 두 템플릿 모두에서 동작
        const overlay = document.getElementById('route-info-overlay');
        if (!overlay) return;
        const toggleBtn = overlay.querySelector('.route-info-toggle');
        if (!toggleBtn) return;

        // 초기 상태: 세션 스토리지로 유지 (페이지별 분리)
        const key = location.pathname + '#route-info-collapsed';
        const collapsed = sessionStorage.getItem(key) === 'true';
        if (collapsed) {
            overlay.classList.add('collapsed');
            toggleBtn.setAttribute('aria-expanded', 'false');
            toggleBtn.textContent = '▲';
        } else {
            toggleBtn.setAttribute('aria-expanded', 'true');
            toggleBtn.textContent = '▼';
        }

        toggleBtn.addEventListener('click', () => {
            const isCollapsed = overlay.classList.toggle('collapsed');
            const expanded = !isCollapsed;
            toggleBtn.setAttribute('aria-expanded', String(expanded));
            toggleBtn.textContent = expanded ? '▼' : '▲';
            sessionStorage.setItem(key, String(isCollapsed));
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        // DOM이 이미 준비된 경우 즉시 실행
        try { init(); } catch (_) {}
    }
})();