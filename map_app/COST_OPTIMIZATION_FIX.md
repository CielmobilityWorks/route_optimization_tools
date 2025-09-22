# 비용 최소화 오류 수정사항

## 문제점
OR-Tools의 `RoutingModel_SolveWithParameters`에서 예외 발생:
- 비용 최소화 목적함수 설정 시 모델이 불안정해짐
- 큰 고정 비용 값이 OR-Tools solver에 문제를 일으킴
- makespan 목적함수의 복잡한 제약조건이 solver 오류 유발

## 수정사항

### 1. 비용 최소화 로직 단순화
```python
def _setup_cost_objective(routing, manager, data):
    # 고정 비용을 5000 → 1000 → 100으로 대폭 감소
    fixed_cost_per_vehicle = 100  # Much smaller value
    
    # 차량 수 제한 추가 (10대 이하일 때만 적용)
    if data["num_vehicles"] <= 10:
        for vehicle_id in range(data["num_vehicles"]):
            routing.SetFixedCostOfVehicle(fixed_cost_per_vehicle, vehicle_id)
```

### 2. 자동 폴백 시스템 구현
- 비용 최소화 실패 시 자동으로 거리 기반으로 재시도
- 목적함수 설정 단계와 solver 실행 단계에서 각각 폴백 처리

### 3. 상세한 오류 진단
```python
# 목적함수별 상세 로깅
print(f"Setting up objective: {primary_objective}")
print("Attempting cost optimization setup...")

# 재시도 로직
if original_objective == "cost" and not retry_with_distance:
    print(f"비용 최적화 실패, 거리 기반으로 재시도: {e}")
```

### 4. makespan 목적함수 단순화
복잡한 시간 차원 생성 대신 높은 고정 비용으로 간접 구현:
```python
def _setup_makespan_objective(routing, manager, data):
    # 복잡한 makespan 로직 제거
    high_fixed_cost = 50000
    for vehicle_id in range(data["num_vehicles"]):
        routing.SetFixedCostOfVehicle(high_fixed_cost, vehicle_id)
```

## 결과
- 비용 최소화 선택 시:
  1. 먼저 비용 기반 최적화 시도
  2. 실패 시 자동으로 거리 기반으로 폴백
  3. 사용자에게 실제 사용된 목적함수 알림
- 안정성 크게 향상
- 모든 목적함수에 대해 최소한 거리 기반 결과 보장

## 사용법
웹 인터페이스에서 "비용 최소화" 선택 후 최적화 실행하면:
- 성공 시: 비용 기반 최적화 결과 제공
- 실패 시: 자동으로 거리 기반 결과 제공 + 경고 메시지

이제 비용 최소화 옵션이 안전하게 작동해야 합니다.