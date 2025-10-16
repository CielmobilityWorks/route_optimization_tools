from datetime import datetime
import os
import json


def generate_standalone_route_html(route_data):
    """외부 의존성 없이 독립적으로 실행 가능한 HTML 생성"""
    # Mapbox access token: 환경변수에서 읽고 없으면 빈 문자열로 둠
    mapbox_token = os.getenv('MAPBOX_ACCESS_TOKEN') or ''

    routes_json = str(route_data.get('routes', [])).replace("'", '"') if route_data.get('routes') else '[]'

    # Use a non-f string template to avoid Python interpreting JS template literals like ${...}
    html_content = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Route Visualization Results</title>
    <script src='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js'></script>
    <link href='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css' rel='stylesheet' />
    <style>
        body { margin: 0; padding: 20px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f5f5f5; }
        .header { text-align: center; margin-bottom: 20px; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .map-container { width: 100%; height: 600px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow: hidden; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Route Visualization Results</h1>
        <div class="subtitle">Generated on __GEN_TIME__</div>
    </div>
    <div class="map-container">
        <div id="route-map" style="width: 100%; height: 100%;"></div>
    </div>
    <script>
    mapboxgl.accessToken = '__MAPBOX_TOKEN__';
    const routeData = __ROUTES_JSON__;
    function initializeMap(){
        const routeMap = new mapboxgl.Map({ container: 'route-map', style: 'mapbox://styles/mapbox/light-v11', center:[126.9779,37.5547], zoom:11 });
        routeMap.on('load', ()=>{ routeMap.addControl(new mapboxgl.NavigationControl()); if(routeData && routeData.length>0){ /* display routes if desired */ } });
    }
    document.addEventListener('DOMContentLoaded', initializeMap);
    </script>
</body>
</html>"""

    gen_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    html_content = html_content.replace('__GEN_TIME__', gen_time)
    html_content = html_content.replace('__MAPBOX_TOKEN__', mapbox_token)
    html_content = html_content.replace('__ROUTES_JSON__', routes_json)
    return html_content


def _haversine_meters(lat1, lon1, lat2, lon2):
    """Return distance in meters between two lat/lon pairs."""
    from math import radians, sin, cos, sqrt, atan2
    R = 6371000.0
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


def _extract_coord(wp):
    """Return (lat, lon) from a waypoint dict supporting various keys."""
    if wp is None:
        return None, None
    lon = None
    lat = None
    for k in ('x', 'lon', 'longitude'):
        if k in wp and wp.get(k) is not None:
            lon = float(wp.get(k))
            break
    for k in ('y', 'lat', 'latitude'):
        if k in wp and wp.get(k) is not None:
            lat = float(wp.get(k))
            break
    return lat, lon


def generate_route_table_report_html(project_id: str | None = None, route_data: dict | None = None):
    """
    Generate an HTML report containing per-route tables.

    Creates one collapsible table per vehicle. Distances are shown in km with 2 decimals.
    Numeric columns are right-aligned.
    """
    # Load data if necessary
    if route_data is None:
        pid = project_id or 'default'
        gen_path = os.path.join('projects', pid, 'generated_routes.json')
        if not os.path.exists(gen_path):
            raise FileNotFoundError(f"generated_routes.json not found for project '{pid}' at {gen_path}")
        with open(gen_path, 'r', encoding='utf-8') as f:
            route_data = json.load(f)

    vehicle_routes = route_data.get('vehicle_routes', {})

    parts = []
    parts.append('<!DOCTYPE html>')
    parts.append('<html lang="ko">')
    parts.append('<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
    parts.append('<title>Route Table Report</title>')
    parts.append('<style>')
    parts.append("body{font-family:Segoe UI,Helvetica,Arial;margin:12px;color:#222;font-size:13px}")
    parts.append("h1{font-size:18px;margin-bottom:6px}")
    # add button styles compatible with app 'editor-btn editor-btn-success'
    parts.append(".editor-btn{padding:6px 12px;border:none;border-radius:4px;font-size:12px;cursor:pointer;background-color:#007bff;color:#ffffff;transition:background-color .3s}")
    parts.append(".editor-btn:hover{background-color:#0056b3}")
    parts.append(".editor-btn-success{background-color:#28a745}")
    parts.append(".editor-btn-success:hover{background-color:#218838}")
    # header actions container to position download button at top-right
    parts.append(".report-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}")
    parts.append(".report-header .actions{display:flex;gap:8px}")
    parts.append(".report-container{display:flex;flex-direction:column;align-items:center}")
    # wrapper to unify widths of summary, charts and tables
    parts.append(".report-wrapper{width:800px;max-width:100%;box-sizing:border-box}")
    parts.append(".report-box{width:100%;background:#fff;padding:12px;border-radius:6px;box-shadow:0 1px 3px rgba(0,0,0,0.08);margin-bottom:14px;box-sizing:border-box}")
    parts.append("table{width:100%;border-collapse:collapse;margin-top:8px}")
    parts.append("th,td{border:1px solid #e6e6e6;padding:6px 8px;font-size:12px}")
    parts.append("th{background:#f7fafc;font-weight:600}")
    parts.append("small.meta{color:#666;font-size:11px}")
    parts.append(".vehicle-header{display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:4px;color:#fff;font-weight:700}")
    parts.append(".vehicle-color-pill{width:12px;height:12px;border-radius:3px;display:inline-block;margin-right:8px}")
    parts.append(".summary{margin-top:8px;color:#444;font-size:12px}")
    parts.append(".toggle-btn{margin-left:auto;background:rgba(255,255,255,0.12);border:0;color:#fff;padding:4px 8px;border-radius:4px;cursor:pointer;font-weight:700}")
    # animation: collapse/expand using max-height transition
    parts.append(".vehicle-body{margin-top:8px;overflow:hidden;max-height:2000px;transition:max-height 260ms ease;padding-top:6px}")
    parts.append(".vehicle-body.collapsed{max-height:0;padding-top:0}")
    parts.append("th.num, td.num{text-align:right}")
    parts.append(".global-summary-grid{width:100%;display:flex;gap:10px;margin:10px 0;padding:0;flex-wrap:wrap}")
    parts.append(".summary-card{flex:1;background:#fff;padding:12px;border-radius:8px;box-shadow:0 2px 6px rgba(0,0,0,0.06);text-align:center;color:#222}")
    parts.append(".summary-card .label{font-size:12px;color:#666;margin-bottom:8px}")
    parts.append(".summary-card .value{font-size:18px;font-weight:800;color:#222}")
    parts.append('</style>')
    # JS: toggle by toggling a CSS class for smooth animation
    parts.append('<script>function toggleVehicleBody(id){var el=document.getElementById(id);var btn=document.getElementById(id+"-btn");if(!el) return; if(el.classList.contains("collapsed")){el.classList.remove("collapsed"); if(btn) btn.textContent="▼";} else {el.classList.add("collapsed"); if(btn) btn.textContent="▲";}} </script>')
    parts.append('</head><body>')
    # Header with title on left and download button at top-right
    parts.append('<div class="report-header">')
    parts.append(f'<div><h1 style="margin:0">Route Table Report</h1><div class="meta"><small class="meta">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</small></div></div>')
    parts.append('<div class="actions"><button id="download-report-btn" class="editor-btn editor-btn-success">Download HTML</button></div>')
    parts.append('</div>')
    # JS for download (split into multiple parts to avoid quoting/paren issues)
    parts.append('<script>')
    parts.append('function downloadReport(){')
    parts.append('  try{')
    parts.append('    var filename="route_table_report.html";')
    parts.append('    var html=document.documentElement.outerHTML;')
    parts.append('    var blob=new Blob([html],{type:"text/html;charset=utf-8"});')
    parts.append('    var url=URL.createObjectURL(blob);')
    parts.append('    var a=document.createElement("a");')
    parts.append('    a.href=url; a.download=filename; document.body.appendChild(a); a.click();')
    parts.append('    setTimeout(function(){ document.body.removeChild(a); URL.revokeObjectURL(url); }, 1000);')
    parts.append('  } catch(e) { console.error(e); alert("Download failed: "+(e && e.message ? e.message : e)); }')
    parts.append('}')
    parts.append('document.addEventListener("DOMContentLoaded", function(){')
    parts.append('  var btn=document.getElementById("download-report-btn"); if(btn) btn.addEventListener("click", downloadReport);')
    parts.append('});')
    parts.append('</script>')
    # (note: generated meta included in header)

    # Compute overall summary: total vehicles, total distance (m), total time (s), total demand
    total_vehicles = len(vehicle_routes)
    total_distance_m = 0.0
    total_time_s = 0.0
    total_demand_sum = 0.0
    for route in vehicle_routes.values():
        # distance: prefer end_point's cumulative_distance (most accurate)
        td = None
        end_point = route.get('end_point')
        if end_point and isinstance(end_point, dict) and 'cumulative_distance' in end_point:
            try:
                td = float(end_point.get('cumulative_distance'))
            except Exception:
                pass
        # fallback to total_distance if end_point not available
        if td is None:
            for k in ('total_distance', 'totalDistance', 'total_distance_m', 'distance_m'):
                if k in route and route.get(k) is not None:
                    try:
                        td = float(route.get(k))
                        break
                    except Exception:
                        pass
        if td is None and isinstance(route.get('properties'), dict):
            for k in ('totalDistance', 'total_time', 'total_distance_m'):
                try:
                    v = route['properties'].get(k)
                    if v is not None:
                        td = float(v)
                        break
                except Exception:
                    continue
        try:
            if td is not None:
                total_distance_m += float(td)
        except Exception:
            pass

        # time: prefer end_point's cumulative_time (most accurate)
        tt = None
        if end_point and isinstance(end_point, dict) and 'cumulative_time' in end_point:
            try:
                tt = float(end_point.get('cumulative_time'))
            except Exception:
                pass
        # fallback to total_time if end_point not available
        if tt is None:
            for k in ('total_time', 'totalTime', 'total_time_s'):
                if k in route and route.get(k) is not None:
                    try:
                        tt = float(route.get(k))
                        break
                    except Exception:
                        pass
        if tt is None and isinstance(route.get('properties'), dict):
            for k in ('totalTime', 'total_time_s'):
                try:
                    v = route['properties'].get(k)
                    if v is not None:
                        tt = float(v)
                        break
                except Exception:
                    continue
        try:
            if tt is not None:
                total_time_s += float(tt)
        except Exception:
            pass

        # demand per waypoint
        try:
            waypoints = route.get('waypoints') or route.get('stops') or route.get('via_points') or []
            for wp in waypoints:
                if isinstance(wp, dict):
                    for dk in ('demand', 'quantity', 'qty'):
                        if dk in wp and wp.get(dk) is not None:
                            try:
                                total_demand_sum += float(str(wp.get(dk)).replace(',', ''))
                                break
                            except Exception:
                                continue
        except Exception:
            pass

    # format totals
    try:
        total_distance_km = f"{(total_distance_m/1000):,.2f}"
    except Exception:
        total_distance_km = 'N/A'
    try:
        # total_time_s -> hours and minutes
        total_minutes = int(total_time_s // 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        total_time_fmt = f"{hours:02d}시간 {minutes:02d}분"
    except Exception:
        total_time_fmt = 'N/A'
    try:
        if abs(total_demand_sum - round(total_demand_sum)) < 1e-9:
            total_demand_display = f"{int(round(total_demand_sum)):,}"
        else:
            total_demand_display = f"{total_demand_sum:,.2f}"
    except Exception:
        total_demand_display = 'N/A'

    parts.append('<div class="report-wrapper">')
    parts.append('<div class="global-summary-grid">')
    parts.append(f'<div class="summary-card"><div class="label">Total Vehicle(EA)</div><div class="value">{total_vehicles}</div></div>')
    parts.append(f'<div class="summary-card"><div class="label">Total Distance(km)</div><div class="value">{total_distance_km}</div></div>')
    parts.append(f'<div class="summary-card"><div class="label">Total Time</div><div class="value">{total_time_fmt}</div></div>')
    parts.append(f'<div class="summary-card"><div class="label">Total Demand(EA)</div><div class="value">{total_demand_display}</div></div>')
    parts.append('</div>')

    def _sort_key(k):
        try:
            return int(k)
        except Exception:
            return k

    # Prepare per-vehicle data for charting (labels and distances in km)
    vehicle_order = sorted(vehicle_routes.keys(), key=_sort_key)
    chart_labels = []
    chart_values = []
    for vid in vehicle_order:
        r = vehicle_routes.get(vid) or {}
        lbl = r.get('vehicle_id', vid)

        # Prefer end_point's cumulative_distance (most accurate)
        total_m = None
        end_point = r.get('end_point')
        if end_point and isinstance(end_point, dict) and 'cumulative_distance' in end_point:
            try:
                total_m = float(end_point.get('cumulative_distance'))
            except Exception:
                pass
        
        # Fallback: Try to find a total distance value from known keys
        if total_m is None:
            for key in ('total_distance', 'totalDistance', 'total_distance_m', 'distance_m'):
                if key in r and r.get(key) is not None:
                    try:
                        total_m = float(r.get(key))
                        break
                    except Exception:
                        pass
        if total_m is None and isinstance(r.get('properties'), dict):
            for k in ('totalDistance', 'total_distance_m', 'distance_m'):
                try:
                    v = r['properties'].get(k)
                    if v is not None:
                        total_m = float(v)
                        break
                except Exception:
                    continue

        # Fallback: compute from waypoints if needed
        if total_m is None:
            try:
                waypoints = r.get('waypoints') or r.get('stops') or r.get('via_points') or []
                coords = []
                for wp in waypoints:
                    lat, lon = _extract_coord(wp)
                    coords.append((lat, lon))
                s = 0.0
                for j in range(1, len(coords)):
                    lat1, lon1 = coords[j-1]
                    lat2, lon2 = coords[j]
                    if None in (lat1, lon1, lat2, lon2):
                        continue
                    s += _haversine_meters(lat1, lon1, lat2, lon2)
                if s > 0:
                    total_m = s
            except Exception:
                total_m = None

        if total_m is None:
            km = 0.0
        else:
            try:
                km = float(total_m) / 1000.0
            except Exception:
                km = 0.0

        chart_labels.append(str(lbl))
        # Round to 2 decimals for neat display in chart tooltip/scale
        chart_values.append(round(km, 2))

    # Prepare per-vehicle demand data (sum of numeric 'demand' fields)
    chart_demand_values = []
    for vid in vehicle_order:
        r = vehicle_routes.get(vid) or {}
        waypoints = r.get('waypoints') or r.get('stops') or r.get('via_points') or []
        demand_sum = 0.0
        found = False
        try:
            for wp in waypoints:
                if isinstance(wp, dict):
                    for dk in ('demand', 'quantity', 'qty'):
                        if dk in wp and wp.get(dk) is not None:
                            try:
                                val = float(str(wp.get(dk)).replace(',', ''))
                                demand_sum += val
                                found = True
                                break
                            except Exception:
                                continue
        except Exception:
            pass
        # If no numeric demand found, push 0 to keep arrays aligned
        chart_demand_values.append(round(demand_sum, 2) if found else 0)

    # Insert chart area between the global summary cards and the detailed tables
    # Display two canvases side-by-side: distance (left) and time (right)
    # Render three equal-width charts: Distance | Time | Demand
    parts.append('<div class="chart-box report-box" style="padding:10px;display:flex;gap:10px;">')
    parts.append('<div style="flex:1;padding:6px;box-sizing:border-box;"><canvas id="distanceChart" style="width:100%;height:260px"></canvas></div>')
    parts.append('<div style="flex:1;padding:6px;box-sizing:border-box;"><canvas id="timeChart" style="width:100%;height:260px"></canvas></div>')
    parts.append('<div style="flex:1;padding:6px;box-sizing:border-box;"><canvas id="demandChart" style="width:100%;height:260px"></canvas></div>')
    parts.append('</div>')

    # Chart.js (UMD, pinned version) and render script: generate both distance and time charts
    parts.append('<script src="https://cdn.jsdelivr.net/npm/chart.js@4.3.0/dist/chart.umd.min.js"></script>')
    parts.append('<script>')
    parts.append(f'const _chartLabels = {json.dumps(chart_labels, ensure_ascii=False)};')
    parts.append(f'const _chartData = {json.dumps(chart_values)};')
    parts.append(f'const _chartDemandData = {json.dumps(chart_demand_values)};')
    # prepare time data (minutes) from vehicle_routes when possible
    time_values = []
    for vid in vehicle_order:
        r = vehicle_routes.get(vid) or {}
        tt = None
        # Prefer end_point's cumulative_time (most accurate)
        end_point = r.get('end_point')
        if end_point and isinstance(end_point, dict) and 'cumulative_time' in end_point:
            try:
                tt = float(end_point.get('cumulative_time'))
            except Exception:
                pass
        # Fallback to total_time if end_point not available
        if tt is None:
            for k in ('total_time', 'totalTime', 'total_time_s'):
                if k in r and r.get(k) is not None:
                    try:
                        tt = float(r.get(k))
                        break
                    except Exception:
                        pass
        if tt is None and isinstance(r.get('properties'), dict):
            for k in ('totalTime', 'total_time_s'):
                try:
                    v = r['properties'].get(k)
                    if v is not None:
                        tt = float(v)
                        break
                except Exception:
                    continue
        # convert seconds to minutes (T-map returns seconds)
        if tt is None:
            time_values.append(None)
        else:
            # T-map returns time in seconds, so convert to minutes
            time_values.append(round(tt/60.0, 2))
    parts.append(f'const _chartTimeData = {json.dumps(time_values)};')

    parts.append('document.addEventListener("DOMContentLoaded", function(){')
    parts.append('  try{')
    parts.append('    const ctxDist = document.getElementById("distanceChart").getContext("2d");')
    parts.append('    const ctxTime = document.getElementById("timeChart").getContext("2d");')
    parts.append('    const avgDist = _chartData.length ? (_chartData.reduce((a,b)=>a+b,0)/_chartData.length) : 0;')
    parts.append('    const avgTime = _chartTimeData && _chartTimeData.filter(v=>v!==null).length ? (_chartTimeData.filter(v=>v!==null).reduce((a,b)=>a+b,0)/_chartTimeData.filter(v=>v!==null).length) : 0;')
    parts.append('    // plugin to draw value labels above each bar and average at right')
    parts.append('    const dataLabelPlugin = {')
    parts.append('      id: "dataLabelPlugin",')
    parts.append('      afterDatasetDraw(chart, args, options) {')
    parts.append('        const ctx = chart.ctx;')
    parts.append('        chart.data.datasets.forEach((dataset, i) => {')
    parts.append('          const meta = chart.getDatasetMeta(i);')
    parts.append('          if (!meta || meta.type !== "bar") return;')
    parts.append('          meta.data.forEach((bar, idx) => {')
    parts.append('            const val = dataset.data[idx];')
    parts.append('            if (val === null || val === undefined) return;')
    parts.append('            ctx.save();')
    parts.append('            ctx.fillStyle = "#111"; ctx.font = "12px Arial"; ctx.textAlign = "center"; ctx.textBaseline = "bottom";')
    parts.append('            ctx.fillText(String(val), bar.x, bar.y - 6);')
    parts.append('            ctx.restore();')
    parts.append('          });')
    parts.append('        });')
    parts.append('        try {')
    parts.append('          const ds = chart.data && chart.data.datasets && chart.data.datasets[0] ? chart.data.datasets[0].data : null;')
    parts.append('          const avgVal = ds && ds.length ? (ds.reduce((a,b)=>a+(b||0),0)/ds.length) : null;')
    parts.append('          const avgDisplay = (avgVal !== null) ? (Math.round(avgVal * 100) / 100).toFixed(2) : null;')
    parts.append('          if (avgDisplay !== null) {')
    parts.append('            // place average label at the canvas top-right corner (avoids overlapping bars/lines)')
    parts.append('            const x = chart.width - 8;')
    parts.append('            const y = 8;')
    parts.append('            ctx.save(); ctx.fillStyle = "#c00"; ctx.font = "12px Arial"; ctx.textAlign = "right"; ctx.textBaseline = "top";')
    parts.append("            ctx.fillText('Avr: ' + avgDisplay, x, y);")
    parts.append('            ctx.restore();')
    parts.append('          }')
    parts.append('        } catch(e) { /* ignore drawing average failures */ }')
    parts.append('      }')
    parts.append('    };')
    parts.append('    Chart.register(dataLabelPlugin);')

    parts.append('    const distChart = new Chart(ctxDist, { type: "bar", data: { labels: _chartLabels, datasets: [ { label: "Distance (km)", data: _chartData, backgroundColor: "rgba(54,162,235,0.8)", borderColor: "rgba(54,162,235,1)", borderWidth: 1 }, { type: "line", label: "Average", data: Array(_chartData.length).fill(avgDist), borderColor: "rgba(255,99,132,0.9)", borderWidth: 1, pointRadius: 0, borderDash: [6,4], order: 0 } ] }, options: { responsive:true, maintainAspectRatio:false, plugins:{ title:{ display:true, text:"Distance", align:"start", font:{ size:14 } }, legend:{ display:false } }, scales:{ x:{ grid:{ display:false, drawBorder:false } }, y:{ beginAtZero:true, grid:{ display:false, drawBorder:false }, ticks:{ display:false } } } } });')

    parts.append('    const timeChart = new Chart(ctxTime, { type: "bar", data: { labels: _chartLabels, datasets: [ { label: "Time (min)", data: _chartTimeData, backgroundColor: "rgba(75,192,192,0.8)", borderColor: "rgba(75,192,192,1)", borderWidth: 1 }, { type: "line", label: "Average", data: Array(_chartTimeData.length).fill(avgTime), borderColor: "rgba(255,159,64,0.9)", borderWidth: 1, pointRadius: 0, borderDash: [6,4], order: 0 } ] }, options: { responsive:true, maintainAspectRatio:false, plugins:{ title:{ display:true, text:"Time (min)", align:"start", font:{ size:14 } }, legend:{ display:false } }, scales:{ x:{ grid:{ display:false, drawBorder:false } }, y:{ beginAtZero:true, grid:{ display:false, drawBorder:false }, ticks:{ display:false } } } } });')

    # Demand chart (per-vehicle total demand)
    parts.append('    try{')
    parts.append('      const ctxDemand = document.getElementById("demandChart").getContext("2d");')
    parts.append('      const avgDemand = _chartDemandData.length ? (_chartDemandData.reduce((a,b)=>a+b,0)/_chartDemandData.length) : 0;')
    parts.append('      const demandChart = new Chart(ctxDemand, { type: "bar", data: { labels: _chartLabels, datasets: [ { label: "Demand (EA)", data: _chartDemandData, backgroundColor: "rgba(255,205,86,0.9)", borderColor: "rgba(255,205,86,1)", borderWidth: 1 }, { type: "line", label: "Average", data: Array(_chartDemandData.length).fill(avgDemand), borderColor: "rgba(153,102,255,0.9)", borderWidth: 1, pointRadius: 0, borderDash: [6,4], order: 0 } ] }, options: { responsive:true, maintainAspectRatio:false, plugins:{ title:{ display:true, text:"Demand (EA)", align:"start", font:{ size:14 } }, legend:{ display:false } }, scales:{ x:{ grid:{ display:false, drawBorder:false } }, y:{ beginAtZero:true, grid:{ display:false, drawBorder:false }, ticks:{ display:false } } } } });')
    parts.append('    } catch(e) { console.warn("Demand chart failed:", e); }')

    parts.append('  } catch(e) { console.error("Chart rendering failed:", e); }')
    parts.append('});')
    parts.append('</script>')

    parts.append('<div class="report-container">')

    palette = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']

    for i, vid in enumerate(sorted(vehicle_routes.keys(), key=_sort_key)):
        route = vehicle_routes.get(vid) or {}
        vehicle_id_display = route.get('vehicle_id', vid)
        color = palette[i % len(palette)]

        parts.append('<div class="report-box">')
        parts.append(f'<div class="vehicle-header" style="background:{color};">')
        parts.append(f'<span class="vehicle-color-pill" style="background:{color};"></span>')
        parts.append(f'Vehicle {vehicle_id_display}')
        parts.append(f'<button id="vehicle-body-{i}-btn" class="toggle-btn" onclick="toggleVehicleBody(\'vehicle-body-{i}\')">▼</button>')
        parts.append('</div>')
        parts.append(f'<div id="vehicle-body-{i}" class="vehicle-body">')

        waypoints = route.get('waypoints') or route.get('stops') or route.get('via_points') or []

        # Use end_point's cumulative values for accuracy (prefer over total_distance/total_time)
        total_distance = None
        total_time = None
        end_point = route.get('end_point')
        if end_point and isinstance(end_point, dict):
            if 'cumulative_distance' in end_point:
                try:
                    total_distance = float(end_point.get('cumulative_distance'))
                except Exception:
                    pass
            if 'cumulative_time' in end_point:
                try:
                    total_time = float(end_point.get('cumulative_time'))
                except Exception:
                    pass
        
        # Fallback to total_distance/total_time if end_point not available
        if total_distance is None:
            for key in ('total_distance', 'totalDistance', 'total_distance_m'):
                if key in route and route.get(key) is not None:
                    try:
                        total_distance = float(route.get(key))
                        break
                    except Exception:
                        pass
        if total_distance is None and isinstance(route.get('properties'), dict):
            for k in ('totalDistance', 'total_distance_m', 'distance_m'):
                if k in route['properties'] and route['properties'].get(k) is not None:
                    try:
                        total_distance = float(route['properties'].get(k))
                        break
                    except Exception:
                        pass

        if total_time is None:
            for key in ('total_time', 'totalTime', 'total_time_s'):
                if key in route and route.get(key) is not None:
                    try:
                        total_time = float(route.get(key))
                        break
                    except Exception:
                        pass
        if total_time is None and isinstance(route.get('properties'), dict):
            for k in ('totalTime', 'total_time_s'):
                if k in route['properties'] and route['properties'].get(k) is not None:
                    try:
                        total_time = float(route['properties'].get(k))
                        break
                    except Exception:
                        pass

        # Note: We now use T-map API's cumulative_time and cumulative_distance from waypoints directly
        # The following segment distance/time calculation is kept for reference but not used
        # coords = []
        # for wp in waypoints:
        #     lat, lon = _extract_coord(wp)
        #     coords.append((lat, lon))
        #
        # segment_dists = []
        # for j in range(1, len(coords)):
        #     lat1, lon1 = coords[j-1]
        #     lat2, lon2 = coords[j]
        #     if None in (lat1, lon1, lat2, lon2):
        #         segment_dists.append(None)
        #     else:
        #         d = _haversine_meters(lat1, lon1, lat2, lon2)
        #         segment_dists.append(d)
        #
        # if total_distance is None:
        #     try:
        #         total_distance = sum(d for d in segment_dists if d is not None)
        #     except Exception:
        #         total_distance = None
        #
        # segment_times = []
        # if total_time is not None and total_distance and total_distance > 0:
        #     for d in segment_dists:
        #         if d is None:
        #             segment_times.append(None)
        #         else:
        #             segment_times.append(total_time * (d / total_distance))
        # else:
        #     segment_times = [None] * len(segment_dists)

        # Aggregate total demand for this vehicle (sum numeric demands only)
        total_demand = None
        try:
            demand_sum = 0.0
            found = False
            for wp in waypoints:
                if isinstance(wp, dict):
                    for dk in ('demand', 'quantity', 'qty'):
                        if dk in wp and wp.get(dk) is not None:
                            try:
                                val = float(wp.get(dk))
                                demand_sum += val
                                found = True
                                break
                            except Exception:
                                # try parse strings with commas
                                try:
                                    s = str(wp.get(dk)).replace(',', '')
                                    val = float(s)
                                    demand_sum += val
                                    found = True
                                    break
                                except Exception:
                                    continue
            if found:
                # prefer integer display when values are integral
                if abs(demand_sum - round(demand_sum)) < 1e-9:
                    total_demand = int(round(demand_sum))
                else:
                    total_demand = demand_sum
        except Exception:
            total_demand = None

        parts.append('<table>')
        parts.append('<thead><tr><th class="num">No</th><th>ID</th><th>Name</th><th class="num">Time (min)</th><th class="num">Time (cum, min)</th><th class="num">Distance (km)</th><th class="num">Distance (cum, km)</th><th class="num">Demand</th></tr></thead>')
        parts.append('<tbody>')

        prev_cum_time = 0.0
        prev_cum_dist = 0.0
        
        def fmt_time(t):
            if t is None:
                return 'N/A'
            return f"{(t/60):.1f}"

        def fmt_dist(d):
            if d is None:
                return 'N/A'
            try:
                return f"{(d/1000):,.2f}"
            except Exception:
                return 'N/A'

        for idx, wp in enumerate(waypoints, start=1):
            wid = wp.get('id') if isinstance(wp, dict) else ''
            name = wp.get('name') if isinstance(wp, dict) else str(wp)
            demand = wp.get('demand') if isinstance(wp, dict) and 'demand' in wp else ''

            # Use T-map API's cumulative values directly from waypoint
            cum_time = wp.get('cumulative_time') if isinstance(wp, dict) else None
            cum_dist = wp.get('cumulative_distance') if isinstance(wp, dict) else None
            
            # Calculate segment time and distance (difference from previous waypoint)
            seg_time = None
            seg_dist = None
            if cum_time is not None:
                seg_time = cum_time - prev_cum_time
                prev_cum_time = cum_time
            if cum_dist is not None:
                seg_dist = cum_dist - prev_cum_dist
                prev_cum_dist = cum_dist

            parts.append('<tr>')
            parts.append(f'<td class="num">{idx}</td>')
            parts.append(f'<td>{wid}</td>')
            parts.append(f'<td>{name}</td>')
            parts.append(f'<td class="num">{fmt_time(seg_time)}</td>')
            parts.append(f'<td class="num">{fmt_time(cum_time)}</td>')
            parts.append(f'<td class="num">{fmt_dist(seg_dist)}</td>')
            parts.append(f'<td class="num">{fmt_dist(cum_dist)}</td>')
            parts.append(f'<td class="num">{demand}</td>')
            parts.append('</tr>')

        parts.append('</tbody></table>')

        # Summary (show total distance in km)
        summary_items = []
        if total_distance is not None:
            try:
                summary_items.append(f'Total distance: {(total_distance/1000):,.2f} km')
            except Exception:
                summary_items.append(f'Total distance: {int(round(total_distance)):,} m')
        if total_time is not None:
            try:
                summary_items.append(f'Total time: {int(round(total_time/60))} min')
            except Exception:
                summary_items.append(f'Total time: {total_time} s')
        if summary_items:
            # append total demand if available
            if total_demand is not None:
                summary_items.append(f'Total demand: {total_demand}')
            parts.append('<div class="summary">' + ' | '.join(summary_items) + '</div>')

        parts.append('</div>')
        parts.append('</div>')

    parts.append('</div>')
    # close report-wrapper
    parts.append('</div>')
    parts.append('</body></html>')
    return '\n'.join(parts)
