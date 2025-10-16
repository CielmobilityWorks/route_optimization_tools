# T-map 데이터 통일화

## 개요
모든 UI 요소와 리포트에서 T-map API의 실제 경로 데이터를 일관되게 사용하도록 통일했습니다.

## 날짜
2025년 10월 16일

## 변경 사항

### 1. Timeline (이미 완료)
- **위치**: Route Editor 하단 Timeline
- **상태**: ✅ 이미 T-map `cumulative_time`, `cumulative_distance` 사용 중
- **데이터 소스**: `waypoint.cumulative_time`, `waypoint.cumulative_distance`

### 2. Editor 하단 패널 데이터 테이블
- **위치**: `static/js/route-editor.js` - `renderBottomRoutePanel()` 함수
- **상태**: ✅ 이미 T-map 데이터 사용 중
- **데이터 소스**: 
  - 거리: `vr.total_distance` (T-map API의 totalDistance)
  - 시간: `vr.total_time` (T-map API의 totalTime)
  - Load: `vr.route_load`

### 3. Route Visualization - Route Information 레이어
- **위치**: `static/js/route-visualization.js` - `updateRouteInfo()` 함수
- **상태**: ✅ 이미 T-map 데이터 사용 중
- **데이터 소스**:
  - 거리: `vehicleRoute.total_distance`
  - 시간: `vehicleRoute.total_time`
  - Load: `vehicleRoute.route_load`

### 4. Report Generator (수정 완료)
- **위치**: `utils/report_generator.py`
- **상태**: ✅ 수정 완료

#### 4.1 Summary Cards
- **변경 전**: Haversine 거리 계산 + 비례 분할 시간
- **변경 후**: T-map의 `total_distance`, `total_time` 사용
- **코드**: 이미 165-220행에서 T-map 데이터 사용 중

#### 4.2 Per-Vehicle Waypoint Tables (주요 변경)
- **변경 전** (라인 574-620):
  ```python
  # Haversine으로 segment 거리 계산
  segment_dists = []
  for j in range(1, len(coords)):
      d = _haversine_meters(lat1, lon1, lat2, lon2)
      segment_dists.append(d)
  
  # 비례 분할로 segment 시간 계산
  segment_times = []
  for d in segment_dists:
      segment_times.append(total_time * (d / total_distance))
  
  # 누적 계산
  cum_time += seg_time
  cum_dist += seg_dist
  ```

- **변경 후**:
  ```python
  # T-map waypoint의 cumulative 값 직접 사용
  cum_time = wp.get('cumulative_time')
  cum_dist = wp.get('cumulative_distance')
  
  # Segment 값은 이전 waypoint와의 차이로 계산
  seg_time = cum_time - prev_cum_time
  seg_dist = cum_dist - prev_cum_dist
  ```

## 데이터 흐름

### Before (문제점)
```
T-map API → cumulative_time/distance → waypoints
                ↓
            (무시됨)
                ↓
Report: Haversine 계산 + 비례 분할 → 부정확한 값
```

### After (개선)
```
T-map API → cumulative_time/distance → waypoints
                ↓
            (모든 UI에서 사용)
                ↓
Timeline: cumulative 값 ✓
Editor Panel: total_distance/time ✓
Visualization: total_distance/time ✓
Report Tables: cumulative 값 ✓
```

## 수정된 파일
1. ✅ `utils/report_generator.py` (라인 512-620)
   - Haversine 계산 코드 주석 처리
   - Waypoint의 cumulative 값 직접 사용

## 기대 효과

### 1. 데이터 정확성
- **Before**: Haversine 직선 거리 ≠ 실제 도로 거리
- **After**: T-map의 실제 도로 경로 기반 정확한 거리/시간

### 2. 데이터 일관성
- **Before**: Timeline과 Report의 값이 다름
- **After**: 모든 UI에서 동일한 T-map 데이터 사용

### 3. 성능
- **Before**: 매번 Haversine 계산 필요
- **After**: 이미 계산된 cumulative 값 사용

## 검증 방법

### 1. Report 생성 테스트
```bash
# 1. 경로 생성
POST /generate-routes-from-csv
  { "project_id": "default" }

# 2. Report 생성
POST /generate-route-table-report
  { "project_id": "default" }

# 3. 확인 사항
- Per-vehicle 테이블의 cumulative time/distance 확인
- 마지막 waypoint의 cumulative 값이 total과 일치하는지 확인
```

### 2. Edit Report 테스트
```bash
# 1. Edit 생성 및 Reload
POST /regenerate-edited-routes
  { "projectId": "default", "editId": "edit01" }

# 2. Edit Report 생성
POST /generate-edit-report
  { "projectId": "default", "editId": "edit01" }

# 3. 확인 사항
- Timeline의 시간과 Report 테이블의 cumulative time 일치 확인
- Edit Report와 Timeline의 데이터 일관성 확인
```

### 3. 시각적 확인
- Timeline 마커 위치
- Report 테이블의 cumulative 값
- Visualization의 Route Information 값
- Editor 하단 패널의 거리/시간 값

→ **모두 동일한 T-map 데이터를 반영해야 함**

## 주의사항

### Backward Compatibility
- 기존 `generated_routes.json` 및 `edited_routes.json` 파일은 T-map API를 통해 생성되었으므로 이미 cumulative 값 포함
- 단, 매우 오래된 파일의 경우 cumulative 값이 없을 수 있음
- 이 경우 Report에서 "N/A" 표시됨

### Fallback 처리
Report Generator는 다음 우선순위로 데이터를 가져옴:
1. `waypoint.cumulative_time` / `cumulative_distance` (T-map)
2. None → "N/A" 표시

## 관련 파일
- `map_app/utils/report_generator.py`
- `map_app/static/js/route-editor.js`
- `map_app/static/js/route-visualization.js`
- `map_app/utils/tmap_route.py`

## 관련 이슈
- CUMULATIVE_TIME_FIX.md - cumulative_time 계산 오류 수정
- 균등 분할 로직 제거
- CSV 값 주입 제거
- T-map API 좌표 매칭 개선
