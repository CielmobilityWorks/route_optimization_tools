# End Point Cumulative 값 사용으로 정확도 개선

## 날짜
2025년 10월 16일

## 문제 상황

Vehicle 1 기준 데이터 불일치:
- **Timeline (정확)**: 113분 43초 (6823.89초), 27.16km
- **다른 테이블 (부정확)**: 114분 35초 (6875초), 27.34km

### 원인 분석

T-map API가 반환하는 값:
```json
{
  "properties": {
    "totalTime": 6875,      // 전체 route geometry의 시간
    "totalDistance": 27343   // 전체 route geometry의 거리
  }
}
```

Waypoint의 실제 cumulative 값 (좌표 매칭 기반):
```json
{
  "end_point": {
    "cumulative_time": 6823.89,      // Depot 좌표와 매칭된 실제 시간
    "cumulative_distance": 27160.85   // Depot 좌표와 매칭된 실제 거리
  }
}
```

**차이 발생 이유**:
1. T-map API의 `totalTime`/`totalDistance`는 **전체 route geometry**의 길이
2. End point의 `cumulative_time`/`cumulative_distance`는 **Depot 좌표와 매칭된 지점**까지의 값
3. Route geometry가 Depot을 지나쳐서 조금 더 연장될 수 있음
4. **End point의 cumulative 값이 더 정확함** (실제 도착 지점 기준)

## 해결 방법

모든 UI 요소에서 `total_time`/`total_distance` 대신 **`end_point.cumulative_time`/`cumulative_distance`**를 우선 사용하도록 변경.

## 수정된 파일

### 1. `static/js/route-editor.js` (Editor 하단 패널)

**변경 전**:
```javascript
// 거리
if (vr.total_distance != null) {
    const km = Number(vr.total_distance) / 1000.0;
    distText = `${km.toFixed(1)}km`;
}

// 시간
if (vr.total_time != null) {
    const secs = Number(vr.total_time);
    const minutes = Math.floor(secs / 60);
    const seconds = Math.floor(secs % 60);
    timeText = `${minutes}분 ${seconds}초`;
}
```

**변경 후**:
```javascript
// 거리: end_point의 cumulative_distance 우선
const endPoint = vr.end_point || vr.waypoints?.[vr.waypoints.length - 1];
if (endPoint?.cumulative_distance != null) {
    const km = Number(endPoint.cumulative_distance) / 1000.0;
    distText = `${km.toFixed(2)}km`;  // 소수점 2자리로 변경
} else if (vr.total_distance != null) {
    // fallback
}

// 시간: end_point의 cumulative_time 우선
if (endPoint?.cumulative_time != null) {
    const secs = Number(endPoint.cumulative_time);
    const minutes = Math.floor(secs / 60);
    const seconds = Math.floor(secs % 60);
    timeText = `${minutes}분 ${seconds}초`;
} else if (vr.total_time != null) {
    // fallback
}
```

### 2. `static/js/route-visualization.js` (Route Information 레이어)

**변경 전**:
```javascript
const totalDistance = vehicleRoute.total_distance || 0;
const totalTime = vehicleRoute.total_time || 0;

const distanceText = totalDistance >= 1000 
    ? `${(totalDistance / 1000).toFixed(1)}km`
    : `${totalDistance}m`;

const timeText = totalTime >= 60 
    ? `${Math.floor(totalTime / 60)}분 ${totalTime % 60}초`
    : `${totalTime}초`;
```

**변경 후**:
```javascript
// end_point의 cumulative 값 우선 사용
const endPoint = vehicleRoute.end_point || vehicleRoute.waypoints?.[vehicleRoute.waypoints.length - 1];
const totalDistance = endPoint?.cumulative_distance ?? vehicleRoute.total_distance ?? 0;
const totalTime = endPoint?.cumulative_time ?? vehicleRoute.total_time ?? 0;

const distanceText = totalDistance >= 1000 
    ? `${(totalDistance / 1000).toFixed(2)}km`  // 소수점 2자리
    : `${Math.round(totalDistance)}m`;

const timeText = totalTime >= 60 
    ? `${Math.floor(totalTime / 60)}분 ${Math.floor(totalTime % 60)}초`
    : `${Math.floor(totalTime)}초`;
```

### 3. `utils/report_generator.py` (Report Summary & Per-Vehicle)

**변경 전**:
```python
# Summary 계산
for route in vehicle_routes.values():
    td = None
    for k in ('total_distance', 'totalDistance', ...):
        if k in route:
            td = float(route.get(k))
    total_distance_m += td
```

**변경 후**:
```python
# Summary 계산: end_point 우선
for route in vehicle_routes.values():
    td = None
    end_point = route.get('end_point')
    if end_point and 'cumulative_distance' in end_point:
        td = float(end_point.get('cumulative_distance'))
    # fallback to total_distance
    if td is None:
        for k in ('total_distance', 'totalDistance', ...):
            ...
    total_distance_m += td
```

동일한 패턴으로 per-vehicle 테이블도 수정:
```python
# Per-vehicle total 계산
end_point = route.get('end_point')
if end_point and isinstance(end_point, dict):
    if 'cumulative_distance' in end_point:
        total_distance = float(end_point.get('cumulative_distance'))
    if 'cumulative_time' in end_point:
        total_time = float(end_point.get('cumulative_time'))
```

## 데이터 우선순위

모든 UI 요소에서 동일한 우선순위 사용:

1. **`end_point.cumulative_time` / `cumulative_distance`** (최우선, 가장 정확)
2. `total_time` / `total_distance` (fallback)
3. `properties.totalTime` / `totalDistance` (fallback)

## 기대 효과

### Before (문제)
```
Vehicle 1:
- Timeline:    113분 43초, 27.16km  ← 정확 (end_point cumulative)
- Editor Panel: 114분 35초, 27.34km  ← 부정확 (total_time/distance)
- Visualization: 114분 35초, 27.3km  ← 부정확 (total_time/distance)
- Report:       114분 35초, 27.34km  ← 부정확 (total_time/distance)
```

### After (해결)
```
Vehicle 1:
- Timeline:      113분 43초, 27.16km  ← end_point cumulative ✅
- Editor Panel:  113분 43초, 27.16km  ← end_point cumulative ✅
- Visualization: 113분 43초, 27.16km  ← end_point cumulative ✅
- Report:        113분 43초, 27.16km  ← end_point cumulative ✅
```

**모든 UI 요소가 동일한 정확한 값 표시!**

## 검증 방법

### 1. 브라우저에서 확인
```bash
# 서버 재시작
# F5로 페이지 새로고침 (캐시 클리어)

# Editor에서 확인:
- Timeline의 마지막 마커 시간/거리
- 하단 패널의 시간/거리
→ 두 값이 일치해야 함

# Visualization에서 확인:
- Route Information 테이블의 시간/거리
→ Editor와 동일한 값이어야 함

# Report 생성 후 확인:
- Summary의 Total Time/Distance
- Per-vehicle 테이블의 Total 행
→ 모두 동일한 값이어야 함
```

### 2. 콘솔에서 검증
```javascript
// Browser Console
const v1 = vehicleRoutes['1'];
console.log('End point cumulative:', 
  v1.end_point.cumulative_time, 
  v1.end_point.cumulative_distance);
console.log('Total (route geometry):', 
  v1.total_time, 
  v1.total_distance);
// End point 값이 더 작고 정확해야 함
```

## 정확도 향상

| 항목 | Before | After | 개선 |
|------|--------|-------|------|
| **데이터 정확성** | Route geometry 전체 | 실제 도착 지점 | ✅ 더 정확 |
| **UI 일관성** | 4곳 다른 값 | 4곳 동일 값 | ✅ 완전 일치 |
| **사용자 혼란** | 값 불일치로 혼란 | 모든 곳 동일 | ✅ 신뢰도 향상 |
| **Timeline 정합성** | Timeline만 정확 | 모두 정확 | ✅ 완벽 통일 |

## 관련 이슈
- CUMULATIVE_TIME_FIX.md - cumulative_time 계산 개선
- TMAP_DATA_UNIFICATION.md - T-map 데이터 통일화
- 좌표 매칭 알고리즘 개선 (순차 검색)

## 주의사항

### Fallback 처리
End point가 없거나 cumulative 값이 없는 경우를 대비한 fallback 구현:
```javascript
const value = endPoint?.cumulative_time ?? route.total_time ?? 0;
```

### 소수점 표시
- 거리: `.toFixed(2)` → "27.16km" (더 정확)
- 시간: `Math.floor()` → "113분 43초" (정수)

### 호환성
- 기존 파일들은 이미 cumulative 값 포함
- 매우 오래된 파일의 경우 fallback으로 total 값 사용
- 모든 브라우저에서 `?.` (optional chaining) 지원 확인 필요
