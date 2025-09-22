# VRP 최적화 결과 누적값 수정사항

## 문제점
기존 VRP 최적화 결과에서 각 경유지별로:
- Route_Distance_m: 전체 경로의 총 거리가 모든 행에 동일하게 표시
- Route_Time_s: 전체 경로의 총 시간이 모든 행에 동일하게 표시
- Cumulative_Load: 올바르게 누적값으로 표시됨

## 수정사항
### 1. VRP Solver 수정 (`utils/vrp_solver.py`)
- `extract_solution_data()` 함수에 누적 거리/시간 계산 로직 추가
- `_create_waypoint_info()` 함수에 누적값 파라미터 추가
- 각 waypoint별로 누적 거리와 시간을 계산하여 저장

### 2. CSV 저장 로직 수정 (`app.py`)
- `save_optimization_result_to_csv()` 함수 수정
- Route_Distance_m: `waypoint.get('cumulative_distance', 0)` 사용
- Route_Time_s: `waypoint.get('cumulative_time', 0)` 사용

## 결과
이제 최적화 결과 테이블에서:
- Route_Distance_m: 출발지부터 해당 지점까지의 누적 거리 (미터)
- Route_Time_s: 출발지부터 해당 지점까지의 누적 시간 (초)
- Cumulative_Load: 해당 지점까지의 누적 승객 수 (기존과 동일)

## 예시
수정 전:
```
Vehicle_ID  Route_Distance_m  Route_Time_s  Stop_Order  Location_Name
1          13611.7           2953          1           의정부여고.가능역
1          13611.7           2953          2           송산역
1          13611.7           2953          3           신도브래뉴아파트입구
```

수정 후:
```
Vehicle_ID  Route_Distance_m  Route_Time_s  Stop_Order  Location_Name
1          0                 0             1           의정부여고.가능역
1          2500              480           2           송산역
1          5200              920           3           신도브래뉴아파트입구
```

## 주의사항
- 새로운 최적화를 실행해야 수정된 결과가 반영됩니다.
- 기존 CSV 파일들은 이전 버전의 결과이므로 새로 생성해야 합니다.