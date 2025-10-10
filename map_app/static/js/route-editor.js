(function () {
    const ROUTE_FETCH_URL = '/get-routes';

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
        return `${ROUTE_FETCH_URL}?${params.toString()}`;
    }

    async function loadGeneratedRoutes() {
        const reloadBtn = document.getElementById('route-editor-reload');
        if (reloadBtn) {
            reloadBtn.disabled = true;
            reloadBtn.textContent = 'Loading...';
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
        } finally {
            if (reloadBtn) {
                reloadBtn.disabled = false;
                reloadBtn.textContent = 'Reload';
            }
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        window.initializeStandaloneRouteMap();
        const reloadBtn = document.getElementById('route-editor-reload');
        if (reloadBtn) {
            reloadBtn.addEventListener('click', () => {
                loadGeneratedRoutes();
            });
        }
        loadGeneratedRoutes();
    });
    
/* Bottom panel rendering: creates rows for each vehicle with left meta and right timeline placeholder bars */
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
        if (vr.total_time != null && !isNaN(Number(vr.total_time))) {
            const secs = Number(vr.total_time);
            // If value seems like minutes (e.g., <= 1440), we still treat as seconds if > 60? heuristic: if > 1000 treat as seconds
            const totalSeconds = (secs > 1000) ? secs : secs; // keep as seconds; data shows values like 4169
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
        const bar = document.createElement('div');
        bar.className = 'rbp-bar';
        bar.style.background = colors[idx % colors.length];
        timelineOuter.appendChild(bar);
        timelineCell.appendChild(timelineOuter);
        row.appendChild(timelineCell);

        rowsContainer.appendChild(row);
        idx += 1;
    });
}

// Initialize collapse/expand toggle for bottom panel

})();
