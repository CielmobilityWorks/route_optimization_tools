# Cumulative Time/Distance 계산 수정

## 문제점

기존 코드에서 `cumulative_time`과 `cumulative_distance` 값이 부정확하게 계산되는 문제가 발생했습니다:

1. **균등 분할 로직의 문제**: waypoint 개수로 총 시간/거리를 균등하게 나누는 로직 사용
   - 실제 구간별 시간/거리가 다른데 균등 분할하면 부정확
   - 예: Start→Via1(10분), Via1→Via2(20분), Via2→End(5분)을 균등 분할하면 각 11.67분으로 계산되어 Via2가 23.33분이 되지만, 실제로는 30분이어야 함

2. **CSV 값의 부정확성**: `optimization_routes.csv`의 `Route_Time_s`, `Route_Distance_m`은 VRP solver의 근사값
   - T-map API를 호출하는 이유는 정확한 경로 정보를 얻기 위함
   - CSV 값을 먼저 주입한 후 조건부로 균등 분할하는 로직이 혼재

## 해결 방법

### 1. 균등 분할 로직 완전 제거

**수정 위치**: `app.py`
- `generate_routes_from_csv_internal()` 함수 (라인 ~1925-1938)
- `regenerate_edited_routes()` 함수 (라인 ~2470-2485)

**변경 전**:
```python
# If waypoints don't have cumulative_time, calculate them
for i, waypoint in enumerate(all_waypoints):
    if 'cumulative_time' not in waypoint:
        waypoint['cumulative_time'] = (i / max(1, len(all_waypoints) - 1)) * total_route_time
    if 'cumulative_distance' not in waypoint:
        waypoint['cumulative_distance'] = (i / max(1, len(all_waypoints) - 1)) * total_route_distance
```

**변경 후**:
```python
# T-map API 응답에서 이미 cumulative_time과 cumulative_distance가 설정되어 있음
# tmap_route.py의 get_route()에서 각 waypoint에 대한 좌표 기반 매칭으로 설정됨

# Get total time and distance from route properties
total_route_time = float(route_result.get('properties', {}).get('totalTime', 0))
total_route_distance = float(route_result.get('properties', {}).get('totalDistance', 0))
```

### 2. CSV 값 주입 제거

**수정 위치**: `app.py` (라인 ~1797-1840)

**변경 전**:
```python
# demand, cumulative_time, cumulative_distance 주입
detail_seq = vehicle_data[['Location_Name', 'Location_Type', 'Load', 'Route_Time_s', 'Route_Distance_m']].to_dict('records')
# ... cumulative_time과 cumulative_distance를 CSV에서 읽어서 주입
```

**변경 후**:
```python
# demand 주입: routes_df의 Load 값을 Stop_Order 순서로 매칭
# cumulative_time과 cumulative_distance는 T-map API 응답에서만 가져옴 (CSV 값은 부정확함)
detail_seq = vehicle_data[['Location_Name', 'Location_Type', 'Load']].to_dict('records')
# ... demand만 주입, cumulative 값은 T-map에서 자동으로 설정됨
```

### 3. T-map API 활용

**데이터 흐름**:
1. `tmap_route.py`의 `get_route()` 함수가 T-map API 호출
2. API 응답에서 각 feature의 좌표와 시간/거리 정보 추출
3. 각 waypoint의 좌표와 route 좌표를 매칭하여 해당 지점의 `cumulative_time`, `cumulative_distance` 자동 계산
4. `app.py`에서는 이미 설정된 값을 그대로 사용

**관련 코드**: `utils/tmap_route.py` (라인 240-285)
```python
# Annotate waypoints (in-place) with cumulative_time/cumulative_distance
all_points = [start_point] + list(via_points or []) + [end_point]
if unique_coords and cumulative_time_per_coord:
    for i, wp in enumerate(all_points):
        # 각 waypoint 좌표와 가장 가까운 route 좌표를 찾아서
        # 해당 지점의 cumulative 값을 설정
        nearest = _closest_index(unique_coords, [wp['x'], wp['y']])
        wp['cumulative_time'] = float(cumulative_time_per_coord[nearest])
        wp['cumulative_distance'] = float(cumulative_dist_per_coord[nearest])
```

## 변경 사항 정리

### 파일: `app.py`

1. **`generate_routes_from_csv_internal()` 함수**
   - CSV에서 `cumulative_time`, `cumulative_distance` 주입 제거
   - demand만 CSV에서 주입
   - 균등 분할 로직 제거
   - T-map API 결과의 `cumulative_time`/`cumulative_distance`를 그대로 사용

2. **`regenerate_edited_routes()` 함수**
   - 균등 분할 로직 제거
   - T-map API 결과를 그대로 사용
   - demand는 CSV에서 주입

### 파일: `utils/tmap_route.py`
- 변경 없음 (이미 정확한 로직 구현됨)
- `get_route()` 함수에서 각 waypoint에 대한 좌표 기반 cumulative 값 계산 수행

## 기대 효과

1. **정확성 향상**: T-map API의 실제 경로 데이터 기반 계산
2. **일관성**: 모든 경로에서 동일한 방식으로 cumulative 값 계산
3. **문제 해결**: 중간 경유지의 `cumulative_time`이 end_point보다 큰 문제 해결

## 테스트 방법

1. 기존 프로젝트 데이터 삭제 또는 새 프로젝트 생성
2. 경로 최적화 실행
3. `generated_routes.json` 확인:
   - 각 waypoint의 `cumulative_time`이 순차적으로 증가하는지 확인
   - 마지막 waypoint(end_point)가 가장 큰 값인지 확인
4. Edit 시나리오에서 Reload 실행
5. `edited_routes.json` 확인: 동일한 조건 검증

## 날짜
2025년 10월 15일
