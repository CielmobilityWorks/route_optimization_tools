from utils.report_generator import generate_standalone_route_html, generate_route_table_report_html
import json

# Minimal route_data to exercise both functions
route_data = {
    "routes": [
        {"vehicle_id": "V1", "waypoints": [{"id": "A", "name": "Start", "lat": 37.5665, "lon": 126.9780}, {"id": "B", "name": "Stop1", "lat": 37.5651, "lon": 126.9895}], "total_distance": 1500, "total_time": 600, "properties": {}},
        {"vehicle_id": "V2", "waypoints": [{"id": "C", "name": "Start2", "lat": 37.5700, "lon": 126.9768}, {"id": "D", "name": "Stop2", "lat": 37.5710, "lon": 126.9820}], "total_distance": 1200, "total_time": 500, "properties": {}}
    ],
    "vehicle_routes": {
        "1": {"vehicle_id": "V1", "waypoints": [{"id": "A", "name": "Start", "lat": 37.5665, "lon": 126.9780}, {"id": "B", "name": "Stop1", "lat": 37.5651, "lon": 126.9895}], "total_distance": 1500, "total_time": 600},
        "2": {"vehicle_id": "V2", "waypoints": [{"id": "C", "name": "Start2", "lat": 37.5700, "lon": 126.9768}, {"id": "D", "name": "Stop2", "lat": 37.5710, "lon": 126.9820}], "total_distance": 1200, "total_time": 500}
    }
}

html1 = generate_standalone_route_html(route_data)
with open('test_standalone.html', 'w', encoding='utf-8') as f:
    f.write(html1)
print('Generated test_standalone.html, length=', len(html1))

html2 = generate_route_table_report_html(route_data=route_data)
with open('test_route_table_report.html', 'w', encoding='utf-8') as f:
    f.write(html2)
print('Generated test_route_table_report.html, length=', len(html2))

# Print first 400 chars of second file for quick inspection
print('\n--- HTML preview ---\n')
print(html2[:400])
