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

    // Expose to other modules/IFRAMEs so marker-dragging section can reuse
    try {
        window.resolveProjectQuery = resolveProjectQuery;
    } catch (e) {
        // ignore in non-window environments
    }

    function buildUrlWithEditId(baseUrl, editId) {
        const params = new URLSearchParams();
    const query = (typeof window.resolveProjectQuery === 'function') ? window.resolveProjectQuery() : (typeof resolveProjectQuery === 'function' ? resolveProjectQuery() : '');
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

    async function generateAndViewReport() {
        if (!currentEditId) {
            alert('먼저 편집 시나리오를 선택하거나 생성하세요.');
            return;
        }
        
        const viewReportBtn = document.getElementById('route-editor-view-report');
        if (viewReportBtn) {
            viewReportBtn.disabled = true;
            viewReportBtn.textContent = '리포트 생성 중...';
        }
        
        try {
            const url = buildUrlWithEditId('/generate-edit-report', currentEditId);
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.message || '리포트 생성 실패');
            }
            
            const data = await response.json();
            if (data.success && data.reportUrl) {
                // 새 창(팝업)으로 리포트 열기 - visualization과 동일한 팝업 옵션 사용
                // 일부 브라우저는 팝업을 차단할 수 있으므로 실패 시 새 탭으로 열도록 폴백 추가
                const popupOptions = 'width=1500,height=800';
                const newWin = window.open(data.reportUrl, '_blank', popupOptions);
                if (!newWin) {
                    // 팝업이 차단된 경우 같은 탭에서 열기(또는 사용자가 새 탭을 선호하면 location.href 교체)
                    window.open(data.reportUrl, '_blank');
                }
            } else {
                throw new Error(data.message || '리포트 URL을 가져올 수 없습니다.');
            }
        } catch (error) {
            console.error('Failed to generate report:', error);
            alert(error.message || '리포트 생성 중 오류가 발생했습니다.');
        } finally {
            if (viewReportBtn) {
                viewReportBtn.disabled = false;
                viewReportBtn.textContent = 'View Report';
            }
        }
    }

    function downloadEditedRoutesCSV() {
        if (!currentEditId) {
            alert('먼저 편집 시나리오를 선택하거나 생성하세요.');
            return;
        }
        
        const urlParams = new URLSearchParams(window.location.search);
        const projectId = urlParams.get('projectId') || 'default';
        const downloadUrl = `/download-edited-routes?projectId=${encodeURIComponent(projectId)}&editId=${encodeURIComponent(currentEditId)}`;
        window.location.href = downloadUrl;
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
        
        // Setup download CSV button
        const downloadCsvBtn = document.getElementById('route-editor-download-csv');
        if (downloadCsvBtn) {
            downloadCsvBtn.addEventListener('click', () => {
                downloadEditedRoutesCSV();
            });
        }
        
        // Setup view report button
        const viewReportBtn = document.getElementById('route-editor-view-report');
        if (viewReportBtn) {
            viewReportBtn.addEventListener('click', async () => {
                await generateAndViewReport();
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

/* ========== VIS-TIMELINE INTEGRATION ========== */

// Global timeline instance and data
let timelineInstance = null;
let timelineGroups = new vis.DataSet();
let timelineItems = new vis.DataSet();
let vehicleRoutesData = {}; // Store current route data
let hasUnsavedChanges = false; // Track unsaved changes

/* Initialize vis-timeline */
function initializeTimeline() {
    const container = document.getElementById('vis-timeline-container');
    if (!container) {
        console.error('Timeline container not found');
        return;
    }

    // Timeline options
    const options = {
        editable: {
            add: false,         // Don't allow adding new items
            updateTime: true,   // Allow dragging items horizontally (time)
            updateGroup: true,  // Allow dragging items between groups (vehicles)
            remove: false,      // Don't allow removing items
            overrideItems: false
        },
        stack: false,          // Don't stack items (for cleaner line view)
        horizontalScroll: true,
        zoomable: true,
        moveable: true,
        groupHeightMode: 'fixed',  // Fixed height for groups
        height: '100%',
        selectable: true,
        multiselect: false,
        snap: null,            // No snapping - free movement
        onMove: function(item, callback) {
            // Validate collision only on drop (when movement is complete)
            if (item.type === 'point' && item.editable !== false) {
                const collision = checkMarkerCollisionOnDrop(item);
                if (collision) {
                    // Revert the move
                    callback(null);
                    showNotification('Cannot place marker: too close to another stop (min 1 minute gap required)', 'warning');
                    return;
                }
            }
            
            // Accept the move
            callback(item);
            
            // Auto-save immediately after successful drop
            console.log('✅ Drop accepted, updating data and saving...');
            setTimeout(() => {
                // Update vehicleRoutesData from current timeline order
                updateVehicleRoutesDataFromTimeline();
                // Save to backend
                saveTimelineChangesImmediate();
            }, 100);
        },
        timeAxis: {
            scale: 'minute',
            step: 10            // Show time labels every 10 minutes
        },
        format: {
            minorLabels: {
                minute: 'HH:mm',
                hour: 'HH:mm'
            },
            majorLabels: {
                minute: 'HH:mm',
                hour: 'ddd D MMMM'
            }
        },
        locale: 'ko',
        margin: {
            item: {
                horizontal: 0,
                vertical: 18
            },
            axis: 10
        },
        orientation: 'top',
        verticalScroll: false,
        zoomKey: 'ctrlKey',    // Zoom with Ctrl + scroll
        height: '100%'
    };

    // Initialize timeline
    timelineInstance = new vis.Timeline(container, timelineItems, timelineGroups, options);

    // Add CSS to ensure consistent row height (20px - matching left table)
    if (!document.getElementById('vis-timeline-custom-height')) {
        const style = document.createElement('style');
        style.id = 'vis-timeline-custom-height';
        style.textContent = `
            /* 1) 라벨 영역(왼쪽 테이블) */
            .vis-timeline .vis-labelset .vis-label {
                height: 20px !important;
                border: none !important;
                background-color: white !important;
            }
            .vis-timeline .vis-labelset .vis-label .vis-inner {
                line-height: 20px !important;  /* 텍스트 수직 가운데 */
                padding: 0 8px !important;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            /* 2) 그룹 배경/전경(오른쪽 타임라인의 행 배경) */
            .vis-timeline .vis-itemset .vis-background .vis-group,
            .vis-timeline .vis-itemset .vis-foreground .vis-group {
                height: 20px !important;
                border: none !important;
            }

            /* 3) range 아이템 높이(단순 배경 막대 - 시각화용) */
            .vis-timeline .vis-item.vis-range {
                height: 4px !important;
                line-height: 4px !important;
                padding: 0 !important;
            }

            /* range 아이템 내 dot 숨김 (불필요) */
            .vis-timeline .vis-item.vis-range .vis-dot {
                display: none !important;
            }
            
            /* ===== Waypoint Markers (원형 마커) ===== */
            /* Point 타입 아이템: arrival_time에 표시되는 원형 마커 */
            .vis-timeline .vis-item.vis-point {
                background: transparent;
                border: none;
                padding: 0;
            }
            
            /* 좌측 테이블과 우측 타임라인 테두리 제거 */
            .timeline-left-table-container {
                border-right: none !important;
                background: white !important;
            }
            
            /* 좌측 테이블 헤더 하단 테두리 (강제 적용) */
            #route-timeline-panel .timeline-table-header {
                border: none !important;
                border-bottom: 2px solid #dee2e6 !important;
                background: #f8f9fa !important;
            }
            
            .timeline-table-row {
                border: none !important;
                border-bottom: none !important;
            }
            
            .timeline-table-header .th-cell,
            .timeline-table-row .td-cell {
                border: none !important;
                border-right: none !important;
            }
            
            /* vis-timeline 전체 테두리 제거 */
            .vis-timeline,
            #vis-timeline-container {
                border: none !important;
            }
            
            .vis-panel {
                border: none !important;
            }
            
            /* vis-top (시간축 헤더) 하단 테두리 (강제 적용) */
            #vis-timeline-container .vis-panel.vis-top {
                border: none !important;
                border-bottom: 2px solid #dee2e6 !important;
                background: #f8f9fa !important;
            }

            /* ===== Unified Point Marker Style ===== */
            /* Use highly specific selector to override vis-timeline default styles */
            #vis-timeline-container .vis-timeline .vis-item.unified-waypoint .vis-dot {
                width: 12px !important;
                height: 12px !important;
                border-radius: 50% !important;
                background-color: white !important;
                border-width: 2px !important;
                border-style: solid !important;
                border-color: inherit !important;
                box-sizing: border-box !important;
                z-index: 100 !important;
                top: 50% !important;
                transform: translateY(-25%) !important;
                transition: all 0.2s ease !important;
            }
            
            /* Hover effect for draggable markers */
            #vis-timeline-container .vis-timeline .vis-item.unified-waypoint .vis-dot:hover {
                width: 16px !important;
                height: 16px !important;
                cursor: move !important;
                box-shadow: 0 0 8px rgba(0,0,0,0.3) !important;
            }
            
            /* Active/dragging effect */
            #vis-timeline-container .vis-timeline .vis-item.unified-waypoint.vis-selected .vis-dot {
                width: 16px !important;
                height: 16px !important;
                box-shadow: 0 0 12px rgba(0,0,0,0.4) !important;
            }
            
            /* Non-editable markers (depot, start, end) */
            #vis-timeline-container .vis-timeline .vis-item.unified-waypoint.vis-readonly .vis-dot {
                opacity: 0.6 !important;
            }
            
            #vis-timeline-container .vis-timeline .vis-item.unified-waypoint.vis-readonly .vis-dot:hover {
                width: 12px !important;
                height: 12px !important;
                cursor: not-allowed !important;
                box-shadow: none !important;
            }
            
            /* Collision effect */
            .marker-collision .vis-dot {
                animation: collisionPulse 0.5s ease-out !important;
            }
            
            @keyframes collisionPulse {
                0%, 100% {
                    box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.7);
                }
                50% {
                    box-shadow: 0 0 0 10px rgba(255, 0, 0, 0);
                }
            }
        `;
        document.head.appendChild(style);
    }

    // Force redraw after initialization to ensure proper rendering
    setTimeout(() => {
        if (timelineInstance) {
            timelineInstance.redraw();
            timelineInstance.fit();
        }
    }, 100);

    // Event listeners
    timelineInstance.on('changed', onTimelineChanged);
    
    // Drag and drop event listener
    timelineInstance.on('itemover', function (properties) {
        // Change cursor to indicate draggable
        if (properties.item) {
            const item = timelineItems.get(properties.item);
            if (item && item.type === 'point') {
                properties.event.target.style.cursor = 'move';
            }
        }
    });
    
    timelineInstance.on('itemout', function (properties) {
        properties.event.target.style.cursor = 'default';
    });
    
    // Handle item moved (drag and drop)
    timelineInstance.on('drop', function (properties) {
        console.log('📦 Item dropped:', properties);
    });
    
    // Handle group change (drag between vehicles)
    let draggedItem = null;
    let originalGroup = null;
    
    timelineInstance.on('select', function (properties) {
        if (properties.items && properties.items.length > 0) {
            const itemId = properties.items[0];
            const item = timelineItems.get(itemId);
            if (item && item.type === 'point' && item.originalData) {
                draggedItem = item;
                originalGroup = item.group;
                console.log('🎯 Selected item:', itemId, 'from vehicle:', originalGroup);
            }
        }
    });
    
    timelineInstance.on('timechange', function (properties) {
        if (draggedItem && properties.id) {
            const updatedItem = timelineItems.get(properties.id);
            if (updatedItem && updatedItem.group !== originalGroup) {
                console.log('🚚 Item moved from', originalGroup, 'to', updatedItem.group);
                handleWaypointGroupChange(properties.id, originalGroup, updatedItem.group);
                originalGroup = updatedItem.group;
            }
        }
    });
    
    timelineInstance.on('timechanged', function (properties) {
        console.log('📍 timechanged event fired:', properties);
        if (draggedItem && properties.id) {
            const updatedItem = timelineItems.get(properties.id);
            if (updatedItem) {
                console.log('⏰ Time changed for item:', properties.id, 'New time:', updatedItem.start);
                handleWaypointTimeChange(properties.id, updatedItem.start);
            }
        }
        draggedItem = null;
        originalGroup = null;
    });
    
    // Control button handlers
    document.getElementById('timeline-zoom-in')?.addEventListener('click', () => {
        timelineInstance.zoomIn(0.5);
    });
    
    document.getElementById('timeline-zoom-out')?.addEventListener('click', () => {
        timelineInstance.zoomOut(0.5);
    });
    
    document.getElementById('timeline-fit')?.addEventListener('click', () => {
        timelineInstance.fit();
    });
    
    document.getElementById('timeline-save-changes')?.addEventListener('click', () => {
        saveTimelineChanges();
    });

    console.log('✅ vis-timeline initialized with drag & drop support');
}

/* Update vehicleRoutesData from current timeline order */
function updateVehicleRoutesDataFromTimeline() {
    console.log('🔄 Updating vehicleRoutesData from timeline...');
    
    // Get all point items from timeline
    const allItems = timelineItems.get({
        filter: (item) => item.type === 'point'
    });
    
    // Group items by vehicle
    const itemsByVehicle = {};
    allItems.forEach(item => {
        if (!itemsByVehicle[item.group]) {
            itemsByVehicle[item.group] = [];
        }
        itemsByVehicle[item.group].push(item);
    });
    
    // Sort each vehicle's items by start time (arrival_time)
    Object.keys(itemsByVehicle).forEach(vehicleId => {
        const items = itemsByVehicle[vehicleId];
        items.sort((a, b) => {
            const timeA = new Date(a.start).getTime();
            const timeB = new Date(b.start).getTime();
            return timeA - timeB;
        });
        
        // Update waypoints array in order
        if (vehicleRoutesData[vehicleId]) {
            const newWaypoints = items.map(item => {
                if (item.originalData && item.originalData.waypoint) {
                    return {
                        ...item.originalData.waypoint,
                        arrival_time: item.start.toISOString(),
                        location_id: item.originalData.waypoint.location_id || item.originalData.waypoint.id
                    };
                }
                return null;
            }).filter(wp => wp !== null);
            
            vehicleRoutesData[vehicleId].waypoints = newWaypoints;
            console.log(`  🚗 Vehicle ${vehicleId}: ${newWaypoints.length} waypoints reordered`);
        }
    });
    
    console.log('✅ vehicleRoutesData updated from timeline');
}

/* Check for marker collision on drop (simple and fast) */
function checkMarkerCollisionOnDrop(droppedItem) {
    if (!droppedItem || !droppedItem.start || !droppedItem.group) {
        return false;
    }
    
    const MIN_TIME_DIFF = 60 * 1000; // Minimum 1 minute between markers
    const droppedTime = new Date(droppedItem.start).getTime();
    const droppedGroup = droppedItem.group;
    
    // Get all point items in the same group
    const allItems = timelineItems.get({
        filter: (item) => {
            return item.type === 'point' && 
                   item.group === droppedGroup && 
                   item.id !== droppedItem.id;
        }
    });
    
    // Check each item for collision
    for (let item of allItems) {
        const itemTime = new Date(item.start).getTime();
        const timeDiff = Math.abs(droppedTime - itemTime);
        
        if (timeDiff < MIN_TIME_DIFF) {
            console.log('❌ Drop rejected: too close to', item.id, '(', timeDiff, 'ms gap, need', MIN_TIME_DIFF, 'ms)');
            return true; // Collision detected
        }
    }
    
    return false; // No collision
}

/* Add row to custom left table */
function addTableRow(vehicleId, vehicleNumber, color, distText, timeText, loadText) {
    const tbody = document.getElementById('timeline-table-body');
    if (!tbody) return;
    
    const row = document.createElement('div');
    row.className = 'timeline-table-row';
    row.dataset.vehicleId = vehicleId;
    
    row.innerHTML = `
        <div class="td-cell td-check">
            <input type="checkbox" checked data-vehicle-id="${vehicleId}" class="route-checkbox">
        </div>
        <div class="td-cell td-no">
            <span class="td-swatch" style="background:${color};"></span>
            <span>${vehicleNumber}</span>
        </div>
        <div class="td-cell td-dist">${distText}</div>
        <div class="td-cell td-time">${timeText}</div>
        <div class="td-cell td-load">${loadText}</div>
    `;
    
    tbody.appendChild(row);
    
    // Add checkbox event listener
    const checkbox = row.querySelector('.route-checkbox');
    if (checkbox) {
        checkbox.addEventListener('change', function() {
            const vid = this.dataset.vehicleId;
            const isChecked = this.checked;
            console.log(`📋 Checkbox changed: Vehicle ${vid}, checked: ${isChecked}`);
            
            if (typeof toggleRouteVisibility === 'function') {
                toggleRouteVisibility(vid, isChecked);
            }
        });
    }
}

/* Convert vehicle routes to vis-timeline format */
function renderBottomRoutePanel(vehicleRoutes) {
    // Store data globally for recalculation
    // Normalize the data: ensure waypoints array exists
    vehicleRoutesData = {};
    
    Object.entries(vehicleRoutes).forEach(([vehicleId, vehicleRoute]) => {
        // Create normalized waypoints array
        let waypoints = [];
        
        // Include start_point first (if exists)
        if (vehicleRoute.start_point) {
            waypoints.push({
                ...vehicleRoute.start_point,
                location_id: vehicleRoute.start_point.id,
                isStart: true
            });
        }
        
        // Add via_points or waypoints
        if (vehicleRoute.via_points && Array.isArray(vehicleRoute.via_points)) {
            waypoints.push(...vehicleRoute.via_points.map(wp => ({
                ...wp,
                location_id: wp.id
            })));
        } else if (vehicleRoute.waypoints && Array.isArray(vehicleRoute.waypoints)) {
            waypoints.push(...vehicleRoute.waypoints.map(wp => ({
                ...wp,
                location_id: wp.id || wp.location_id
            })));
        }
        
        // Include end_point last (if exists)
        if (vehicleRoute.end_point) {
            waypoints.push({
                ...vehicleRoute.end_point,
                location_id: vehicleRoute.end_point.id,
                isEnd: true
            });
        }
        
        // Store normalized data
        vehicleRoutesData[vehicleId] = {
            ...vehicleRoute,
            waypoints: waypoints  // Normalized waypoints array with location_id
        };
    });
    
    console.log('📊 Normalized vehicleRoutesData:', vehicleRoutesData);
    
    if (!timelineInstance) {
        initializeTimeline();
    }
    
    if (!timelineInstance) {
        console.error('Failed to initialize timeline');
        return;
    }

    // Clear existing data
    timelineGroups.clear();
    timelineItems.clear();
    
    // Clear custom table
    const tbody = document.getElementById('timeline-table-body');
    if (tbody) {
        tbody.innerHTML = '';
    }

    const colors = window.ROUTE_COLORS || ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F'];
    
    // Sort vehicle routes by vehicle_id to match map rendering order
    const sortedVehicleEntries = Object.entries(vehicleRoutes).sort((a, b) => {
        const idA = a[1].vehicle_id || a[0];
        const idB = b[1].vehicle_id || b[0];
        return String(idA).localeCompare(String(idB));
    });
    
    let groupIndex = 0;

    // Convert each vehicle route to timeline format
    sortedVehicleEntries.forEach(([vehicleId, vehicleRoute]) => {
        const color = colors[groupIndex % colors.length];
        
        // Add group (vehicle)
        const endPoint = vehicleRoute.end_point || (vehicleRoute.waypoints && vehicleRoute.waypoints.length > 0 ? vehicleRoute.waypoints[vehicleRoute.waypoints.length - 1] : null);
        
        let distText = '-';
        if (endPoint && endPoint.cumulative_distance != null) {
            const km = Number(endPoint.cumulative_distance) / 1000.0;
            distText = `${km.toFixed(2)}km`;
        } else if (vehicleRoute.total_distance != null) {
            const km = Number(vehicleRoute.total_distance) / 1000.0;
            distText = `${km.toFixed(1)}km`;
        }
        
        let timeText = '-';
        const endPointTime = endPoint ? endPoint.cumulative_time : null;
        if (endPointTime != null) {
            const minutes = Math.floor(endPointTime / 60);
            timeText = `${minutes}분`;
        } else if (vehicleRoute.total_time != null) {
            const minutes = Math.floor(vehicleRoute.total_time / 60);
            timeText = `${minutes}분`;
        }
        
        let loadText = vehicleRoute.route_load != null ? String(vehicleRoute.route_load) : '-';
        
        // Extract vehicle number from vehicleId (e.g., "vehicle_1" -> "1")
        const vehicleNumber = String(vehicleId).replace(/[^0-9]/g, '') || groupIndex + 1;
        
        // Add to timeline groups (hidden labels)
        timelineGroups.add({
            id: vehicleId,
            content: '',  // Empty content (we'll use custom table)
            style: `background-color: ${color}10; border-left: 3px solid ${color};`
        });
        
        // Add to custom left table
        addTableRow(vehicleId, vehicleNumber, color, distText, timeText, loadText);

        // Add single range bar to show vehicle's total travel time (visualization only)
        // Use start_point and end_point's arrival_time for accurate time range
        if (vehicleRoute.start_point && vehicleRoute.end_point) {
            try {
                let rangeStart = null;
                let rangeEnd = null;
                
                // Parse start_point arrival_time
                if (vehicleRoute.start_point.arrival_time) {
                    const startArrivalStr = vehicleRoute.start_point.arrival_time;
                    let startTimeMatch;
                    
                    if (startArrivalStr.includes('T')) {
                        // ISO format: "2025-10-17T09:22:17"
                        startTimeMatch = startArrivalStr.split('T')[1];
                    } else if (startArrivalStr.includes(' ')) {
                        // Space separated: "2025-10-17 09:22:17"
                        startTimeMatch = startArrivalStr.split(' ')[1];
                    } else {
                        // Already time only: "09:22:17"
                        startTimeMatch = startArrivalStr;
                    }
                    
                    const startTimeParts = startTimeMatch.split(':');
                    const startHours = parseInt(startTimeParts[0], 10);
                    const startMinutes = parseInt(startTimeParts[1], 10);
                    const startSecondsParts = startTimeParts[2] ? startTimeParts[2].split('.') : ['0'];
                    const startSeconds = parseInt(startSecondsParts[0], 10);
                    
                    const baseDate = new Date(2025, 0, 1); // January 1, 2025
                    rangeStart = new Date(baseDate.getFullYear(), baseDate.getMonth(), baseDate.getDate(), startHours, startMinutes, startSeconds);
                } else if (vehicleRoute.start_point.cumulative_time != null) {
                    // Fallback: Calculate from cumulative_time
                    const startDate = new Date(2025, 0, 1, 9, 0, 0); // Start at 9:00 AM
                    rangeStart = new Date(startDate.getTime() + vehicleRoute.start_point.cumulative_time * 1000);
                }
                
                // Parse end_point arrival_time
                if (vehicleRoute.end_point.arrival_time) {
                    const endArrivalStr = vehicleRoute.end_point.arrival_time;
                    let endTimeMatch;
                    
                    if (endArrivalStr.includes('T')) {
                        // ISO format: "2025-10-17T09:22:17"
                        endTimeMatch = endArrivalStr.split('T')[1];
                    } else if (endArrivalStr.includes(' ')) {
                        // Space separated: "2025-10-17 09:22:17"
                        endTimeMatch = endArrivalStr.split(' ')[1];
                    } else {
                        // Already time only: "09:22:17"
                        endTimeMatch = endArrivalStr;
                    }
                    
                    const endTimeParts = endTimeMatch.split(':');
                    const endHours = parseInt(endTimeParts[0], 10);
                    const endMinutes = parseInt(endTimeParts[1], 10);
                    const endSecondsParts = endTimeParts[2] ? endTimeParts[2].split('.') : ['0'];
                    const endSeconds = parseInt(endSecondsParts[0], 10);
                    
                    const baseDate = new Date(2025, 0, 1); // January 1, 2025
                    rangeEnd = new Date(baseDate.getFullYear(), baseDate.getMonth(), baseDate.getDate(), endHours, endMinutes, endSeconds);
                } else if (vehicleRoute.end_point.cumulative_time != null) {
                    // Fallback: Calculate from cumulative_time
                    const startDate = new Date(2025, 0, 1, 9, 0, 0); // Start at 9:00 AM
                    rangeEnd = new Date(startDate.getTime() + vehicleRoute.end_point.cumulative_time * 1000);
                }
                
                // Add range item if both start and end times are available
                if (rangeStart && rangeEnd && rangeStart < rangeEnd) {
                    timelineItems.add({
                        id: `${vehicleId}_journey`,
                        group: vehicleId,
                        content: '',  // No label
                        start: rangeStart,
                        end: rangeEnd,
                        type: 'range',
                        className: 'vehicle-journey',
                        style: `background-color: ${color}; border-color: ${color}; border-width: 2px;`,  // Solid color matching border
                        editable: false  // Not editable
                    });
                } else {
                    console.warn(`⚠️ Invalid range times for vehicle ${vehicleId}:`, {rangeStart, rangeEnd});
                }
            } catch (error) {
                console.warn(`⚠️ Failed to create range bar for vehicle ${vehicleId}:`, error);
            }
        }
        
        // Add circular markers for each waypoint's arrival_time
        // Only include via_points / waypoints. Do NOT include start_point or end_point to avoid duplicates.
        const allWaypoints = [];

        if (vehicleRoute.waypoints && Array.isArray(vehicleRoute.waypoints)) {
            vehicleRoute.waypoints.forEach((wp, idx) => {
                allWaypoints.push({ ...wp, wpIndex: idx });
            });
        } else if (vehicleRoute.via_points && Array.isArray(vehicleRoute.via_points)) {
            vehicleRoute.via_points.forEach((wp, idx) => {
                allWaypoints.push({ ...wp, wpIndex: idx });
            });
        }
        
        // Create point markers for each waypoint
        allWaypoints.forEach((waypoint) => {
            // Calculate arrival date from cumulative_time if arrival_time is not present
            let arrivalDate;
            let arrivalTimeStr = waypoint.arrival_time;
            
            try {
                if (arrivalTimeStr) {
                    // Parse arrival_time if available
                    let timeMatch;
                    
                    // Extract time from ISO format or time-only format
                    if (arrivalTimeStr.includes('T')) {
                        // ISO format: "2025-10-17T09:22:17"
                        timeMatch = arrivalTimeStr.split('T')[1];
                    } else if (arrivalTimeStr.includes(' ')) {
                        // Space separated: "2025-10-17 09:22:17"
                        timeMatch = arrivalTimeStr.split(' ')[1];
                    } else {
                        // Assume it's already time only: "09:22:17"
                        timeMatch = arrivalTimeStr;
                    }
                    
                    // Parse HH:MM:SS or HH:MM:SS.ffffff
                    const timeParts = timeMatch.split(':');
                    const hours = parseInt(timeParts[0], 10);
                    const minutes = parseInt(timeParts[1], 10);
                    const secondsParts = timeParts[2] ? timeParts[2].split('.') : ['0'];
                    const seconds = parseInt(secondsParts[0], 10);
                    
                    // Create date with base date (2025-01-01) and parsed time
                    const baseDate = new Date(2025, 0, 1); // January 1, 2025
                    arrivalDate = new Date(baseDate.getFullYear(), baseDate.getMonth(), baseDate.getDate(), hours, minutes, seconds);
                } else if (waypoint.cumulative_time != null) {
                    // Fallback: Calculate from cumulative_time (in seconds)
                    // Assume start time is 9:00 AM
                    const startDate = new Date(2025, 0, 1, 9, 0, 0); // Start at 9:00 AM
                    arrivalDate = new Date(startDate.getTime() + waypoint.cumulative_time * 1000);
                    
                    // Generate arrival_time string for tooltip
                    const hours = String(arrivalDate.getHours()).padStart(2, '0');
                    const minutes = String(arrivalDate.getMinutes()).padStart(2, '0');
                    const seconds = String(arrivalDate.getSeconds()).padStart(2, '0');
                    arrivalTimeStr = `${hours}:${minutes}:${seconds}`;
                } else {
                    // No time information available, skip this waypoint
                    console.warn('⚠️ Waypoint has no arrival_time or cumulative_time:', waypoint);
                    return;
                }
                
                const isDepot = waypoint.type === 'depot' || waypoint.name?.includes('Depot') || waypoint.name?.includes('depot');
                const isStartEnd = waypoint.isStart || waypoint.isEnd;
                const isEditable = !isDepot && !isStartEnd;
                
                // Create tooltip with arrival_time string
                const tooltipContent = createTooltipContent(waypoint, arrivalTimeStr);
                
                // Create point marker item
                timelineItems.add({
                    id: `${vehicleId}_marker_${waypoint.wpIndex}`,
                    group: vehicleId,
                    content: '', // No label needed, just the marker
                    start: arrivalDate,
                    type: 'point',
                    // Use unified class for all point markers, add readonly class if not editable
                    className: isEditable ? 'unified-waypoint' : 'unified-waypoint vis-readonly',
                    // Apply vehicle color directly to border (currentColor won't work, needs explicit color)
                    style: `border-color: ${color};`,
                    title: tooltipContent,
                    // Only allow dragging for non-depot waypoints
                    editable: {
                        updateTime: isEditable,  // Can drag horizontally (time) if not depot/start/end
                        updateGroup: isEditable, // Can drag between vehicles if not depot/start/end
                        remove: false
                    },
                    originalData: {
                        vehicleId: vehicleId,
                        waypointIndex: waypoint.wpIndex,
                        waypoint: waypoint,
                        isDepot: isDepot,
                        isStartEnd: isStartEnd
                    }
                });
            } catch (error) {
                console.warn(`⚠️ Failed to create timeline marker for waypoint:`, waypoint, error);
            }
        });

        groupIndex++;
    });

    // Fit timeline to show all items
    setTimeout(() => {
        timelineInstance.fit();
    }, 100);
    
    console.log('✅ Timeline rendered with', timelineGroups.length, 'vehicles and', timelineItems.length, 'stops');
}

/* Create tooltip content for waypoint */
function createTooltipContent(waypoint, arrivalTimeStr) {
    // Parse arrival_time string to extract time
    let hours = 0, minutes = 0, seconds = 0;
    
    if (arrivalTimeStr) {
        let timeMatch;
        
        // Extract time from ISO format or time-only format
        if (arrivalTimeStr.includes('T')) {
            // ISO format: "2025-10-17T09:22:17"
            timeMatch = arrivalTimeStr.split('T')[1];
        } else if (arrivalTimeStr.includes(' ')) {
            // Space separated: "2025-10-17 09:22:17"
            timeMatch = arrivalTimeStr.split(' ')[1];
        } else {
            // Assume it's already time only: "09:22:17"
            timeMatch = arrivalTimeStr;
        }
        
        // Parse HH:MM:SS or HH:MM:SS.ffffff
        const timeParts = timeMatch.split(':');
        hours = parseInt(timeParts[0], 10);
        minutes = parseInt(timeParts[1], 10);
        const secondsParts = timeParts[2] ? timeParts[2].split('.') : ['0'];
        seconds = parseInt(secondsParts[0], 10);
    }
    
    let tooltip = `<strong>${waypoint.name || 'Stop'}</strong>\n`;
    tooltip += `Arrival: ${String(hours).padStart(2,'0')}:${String(minutes).padStart(2,'0')}:${String(seconds).padStart(2,'0')}\n`;
    
    if (waypoint.demand) {
        tooltip += `Demand: ${waypoint.demand}\n`;
    }
    
    if (waypoint.cumulative_distance) {
        const km = (waypoint.cumulative_distance / 1000).toFixed(2);
        tooltip += `Distance: ${km}km\n`;
    }
    
    if (waypoint.address) {
        tooltip += `Address: ${waypoint.address}`;
    }
    
    return tooltip;
}

/* Handle timeline changes (drag & drop) */
function onTimelineChanged() {
    console.log('📊 Timeline changed - items moved');
    // Timeline 변경 시 Reload 버튼을 사용하여 처리
    // 순서는 CSV 저장 후 Reload에서 처리됨
}

/* Handle waypoint group change (drag between vehicles) */
function handleWaypointGroupChange(itemId, fromVehicleId, toVehicleId) {
    console.log('🔄 Waypoint group change:', itemId, 'from', fromVehicleId, 'to', toVehicleId);
    
    const item = timelineItems.get(itemId);
    if (!item || !item.originalData) {
        console.warn('⚠️ No original data found for item:', itemId);
        return;
    }
    
    const { vehicleId: oldVehicleId, waypointIndex, waypoint } = item.originalData;
    
    // Update the waypoint in vehicleRoutesData
    if (!vehicleRoutesData[oldVehicleId] || !vehicleRoutesData[toVehicleId]) {
        console.warn('⚠️ Vehicle data not found');
        return;
    }
    
    // Remove waypoint from old vehicle
    const oldWaypoints = vehicleRoutesData[oldVehicleId].waypoints || [];
    const waypointToMove = oldWaypoints[waypointIndex];
    
    if (!waypointToMove) {
        console.warn('⚠️ Waypoint not found at index:', waypointIndex);
        return;
    }
    
    oldWaypoints.splice(waypointIndex, 1);
    
    // Add waypoint to new vehicle
    const newWaypoints = vehicleRoutesData[toVehicleId].waypoints || [];
    newWaypoints.push(waypointToMove);
    
    // Log change (no popup notification)
    console.log(`✅ ${waypoint.name || 'Waypoint'} moved from Vehicle ${oldVehicleId} to Vehicle ${toVehicleId}`);
    
    // Recalculate and re-render timeline
    recalculateRoutes();
}

/* Handle waypoint time change (drag horizontally) */
function handleWaypointTimeChange(itemId, newTime) {
    console.log('⏰ Waypoint time change:', itemId, 'to', newTime);
    
    const item = timelineItems.get(itemId);
    if (!item || !item.originalData) {
        console.warn('⚠️ No original data found for item:', itemId);
        return;
    }
    
    const { vehicleId, waypointIndex, waypoint } = item.originalData;
    
    // Update the waypoint's arrival time
    if (!vehicleRoutesData[vehicleId]) {
        console.warn('⚠️ Vehicle data not found');
        return;
    }
    
    const waypoints = vehicleRoutesData[vehicleId].waypoints || [];
    const targetWaypoint = waypoints[waypointIndex];
    
    if (!targetWaypoint) {
        console.warn('⚠️ Waypoint not found at index:', waypointIndex);
        return;
    }
    
    // Format new time
    const hours = String(newTime.getHours()).padStart(2, '0');
    const minutes = String(newTime.getMinutes()).padStart(2, '0');
    const seconds = String(newTime.getSeconds()).padStart(2, '0');
    const newTimeStr = `2025-01-01T${hours}:${minutes}:${seconds}`;
    
    targetWaypoint.arrival_time = newTimeStr;
    
    showNotification(`${waypoint.name || 'Waypoint'} time updated to ${hours}:${minutes}`, 'info');
    
    // Recalculate cumulative times
    recalculateCumulativeTimes(vehicleId);
}

/* Recalculate cumulative times for a vehicle */
function recalculateCumulativeTimes(vehicleId) {
    const vehicleData = vehicleRoutesData[vehicleId];
    if (!vehicleData || !vehicleData.waypoints) return;
    
    let cumulativeTime = 0;
    const baseDate = new Date(2025, 0, 1, 9, 0, 0); // 9:00 AM base
    
    vehicleData.waypoints.forEach((waypoint, index) => {
        if (waypoint.arrival_time) {
            const arrivalDate = new Date(waypoint.arrival_time);
            const timeDiff = (arrivalDate - baseDate) / 1000; // seconds
            waypoint.cumulative_time = timeDiff;
            cumulativeTime = timeDiff;
        }
    });
    
    console.log('✅ Recalculated cumulative times for', vehicleId);
}

/* Recalculate all routes after changes */
function recalculateRoutes() {
    console.log('🔄 Recalculating routes...');
    
    // Re-render the timeline with updated data
    if (typeof renderBottomRoutePanel === 'function') {
        renderBottomRoutePanel(vehicleRoutesData);
    }
    
    // Update the map if needed
    if (typeof window.displayAndManageRoutes === 'function' && window.map) {
        window.displayAndManageRoutes(vehicleRoutesData, window.map);
    }
}

/* Show notification to user */
function showNotification(message, type = 'info') {
    console.log(`📢 [${type.toUpperCase()}] ${message}`);
    
    const colorMap = {
        'info': '#17a2b8',
        'success': '#28a745',
        'error': '#dc3545',
        'warning': '#ffc107'
    };
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        background-color: ${colorMap[type] || colorMap['info']};
        color: white;
        border-radius: 4px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
        max-width: 400px;
    `;
    
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => {
            if (notification.parentNode) {
                document.body.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

// Add notification animations
if (!document.getElementById('notification-animations')) {
    const style = document.createElement('style');
    style.id = 'notification-animations';
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
        .timeline-btn-save {
            background-color: #28a745 !important;
            color: white !important;
            font-weight: bold !important;
            animation: pulse 2s infinite;
        }
        .timeline-btn-save:hover {
            background-color: #218838 !important;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
    `;
    document.head.appendChild(style);
}

/* Mark timeline as having unsaved changes */
function markAsUnsaved() {
    hasUnsavedChanges = true;
    const saveBtn = document.getElementById('timeline-save-changes');
    const indicator = document.getElementById('timeline-changes-indicator');
    
    if (saveBtn) {
        saveBtn.style.display = 'inline-block';
    }
    if (indicator) {
        indicator.style.display = 'inline';
        indicator.title = 'Unsaved changes';
    }
}

/* Mark timeline as saved */
function markAsSaved() {
    hasUnsavedChanges = false;
    const saveBtn = document.getElementById('timeline-save-changes');
    const indicator = document.getElementById('timeline-changes-indicator');
    
    if (saveBtn) {
        saveBtn.style.display = 'none';
    }
    if (indicator) {
        indicator.style.display = 'none';
    }
}

/* Save timeline changes to server */
async function saveTimelineChanges() {
    if (!hasUnsavedChanges) {
        showNotification('No changes to save', 'info');
        return;
    }
    
    await saveTimelineChangesImmediate();
}

/* Save timeline changes immediately (without checking hasUnsavedChanges) */
async function saveTimelineChangesImmediate() {
    console.log('💾 Saving timeline changes immediately...');
    console.log('📊 Current vehicleRoutesData:', vehicleRoutesData);
    
    try {
        // Convert vehicleRoutesData to the format expected by the server
        const routesToSave = {};
        
        Object.entries(vehicleRoutesData).forEach(([vehicleId, vehicleData]) => {
            routesToSave[vehicleId] = {
                ...vehicleData,
                waypoints: vehicleData.waypoints || [],
                vehicle_id: vehicleId
            };
        });
        
        console.log('📤 Sending to server:', routesToSave);
        
        // Build URL with project and edit parameters
        const params = new URLSearchParams();
        const query = resolveProjectQuery();
        if (query) {
            const existing = new URLSearchParams(query.startsWith('?') ? query.slice(1) : query);
            existing.forEach((value, key) => params.set(key, value));
        }
        if (window.currentEditId) {
            params.set('editId', window.currentEditId);
        }
        
        const url = `/api/save-timeline-changes?${params.toString()}`;
        console.log('🌐 POST URL:', url);
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                routes: routesToSave
            })
        });
        
        console.log('📥 Response status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('❌ Server error:', errorText);
            throw new Error('Failed to save changes: ' + errorText);
        }
        
        const data = await response.json();
        console.log('📥 Response data:', data);
        
        if (data.success) {
            // 성공 시 콘솔 로그만 출력 (팝업 알림 제거)
            console.log(`✅ Timeline changes saved: ${data.updated_count || 0} waypoints updated, ${data.vehicle_changes || 0} vehicle changes, ${data.order_changes || 0} order changes`);
        } else {
            throw new Error(data.error || 'Unknown error');
        }
    } catch (error) {
        console.error('❌ Failed to save timeline changes:', error);
        // 에러 시에만 알림 표시
        showNotification('⚠️ Save failed: ' + error.message, 'error');
    }
}

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
                    const markerTypeElement = markerElement ? markerElement.querySelector('[data-marker-type]') : null;
                    const markerType = markerTypeElement ? markerTypeElement.getAttribute('data-marker-type') : null;
                    
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
    
    // Use the top-level resolveProjectQuery (exposed to window) to avoid duplication
    
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
