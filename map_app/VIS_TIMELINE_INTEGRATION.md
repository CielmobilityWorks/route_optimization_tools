# 🎯 vis-timeline 통합 가이드

## 📋 개요

Route Editor에 **vis-timeline** 라이브러리를 통합하여 드래그 앤 드롭으로 정류장 순서를 변경하고, TMAP API를 통해 경로를 재계산하는 기능을 구현했습니다.

## ✨ 주요 기능

### 1. **대화형 Timeline UI**
- ✅ 차량별로 그룹화된 timeline 뷰
- ✅ 각 정류장을 시간축 위에 시각화
- ✅ 드래그 앤 드롭으로 정류장 순서 변경 가능
- ✅ 차량 간 정류장 이동 지원

### 2. **Timeline 컨트롤**
- 🔍 **Zoom In/Out**: timeline 확대/축소
- ⬌ **Fit All**: 전체 경로를 화면에 맞춤
- 🔄 **Recalculate**: 변경된 순서로 TMAP 경로 재계산

### 3. **실시간 경로 재계산**
- 정류장 순서 변경 후 "Recalculate" 버튼 클릭
- 백엔드에서 TMAP API 호출
- 새로운 경로 계산 및 저장
- 지도와 timeline 자동 업데이트

## 🏗️ 구현 구조

### Frontend (JavaScript)
```
route-editor.js
├── initializeTimeline()          // vis-timeline 초기화
├── renderBottomRoutePanel()      // 경로 데이터를 timeline 형식으로 변환
├── onTimelineChanged()           // 드래그 앤 드롭 이벤트 처리
├── recalculateRoutes()           // 백엔드 API 호출
└── extractRouteOrderFromTimeline() // timeline에서 새 순서 추출
```

### Backend (Python)
```
app.py
└── /api/recalculate-routes       // 경로 재계산 API

utils/tmap_route.py
└── get_route_with_order()        // 순서대로 TMAP 경로 계산
```

## 🚀 사용 방법

### 1. 애플리케이션 실행
```powershell
python app.py
```

### 2. Route Editor 열기
- 메인 페이지에서 경로 최적화 완료 후
- "Route Editor" 버튼 클릭

### 3. Timeline에서 정류장 순서 변경
1. Timeline에서 정류장 박스를 드래그
2. 원하는 시간대 또는 다른 차량으로 이동
3. 여러 정류장의 순서를 조정

### 4. 경로 재계산
1. 상단의 **"🔄 Recalculate"** 버튼 클릭
2. 백엔드에서 TMAP API를 통해 경로 재계산
3. 완료 후 페이지 자동 새로고침
4. 새로운 경로가 지도와 timeline에 표시됨

## 📊 데이터 흐름

```
Timeline UI (드래그 앤 드롭)
    ↓
JavaScript: extractRouteOrderFromTimeline()
    ↓
POST /api/recalculate-routes
    {
        "vehicle_1": [
            {"name": "Depot", "location": [lng, lat], ...},
            {"name": "Stop 1", "location": [lng, lat], ...},
            ...
        ],
        "vehicle_2": [...]
    }
    ↓
Backend: get_route_with_order()
    ↓
TMAP API 호출 (각 차량별)
    ↓
결과 저장: edited_routes.json
    ↓
Response → Frontend
    ↓
페이지 새로고침 → 업데이트된 경로 표시
```

## 🎨 UI 커스터마이징

### Timeline 스타일 변경
`route_editor.html`의 스타일 섹션에서 수정:

```css
/* vis-timeline 기본 스타일 */
.vis-item {
    border-radius: 6px;      /* 박스 모서리 둥글기 */
    border-width: 2px;       /* 테두리 두께 */
    font-size: 12px;         /* 글자 크기 */
}

/* Depot 스타일 */
.vis-item.depot-item {
    background-color: #28a745;  /* 녹색 배경 */
    border-color: #1e7e34;
}

/* Stop 스타일 */
.vis-item.stop-item {
    background-color: #007bff;  /* 파란색 배경 */
    border-color: #0056b3;
}
```

### Timeline 옵션 변경
`route-editor.js`의 `initializeTimeline()` 함수:

```javascript
const options = {
    editable: {
        updateTime: true,   // 시간축 드래그 허용
        updateGroup: true,  // 그룹 간 이동 허용
    },
    stack: true,           // 아이템 겹침 방지
    zoomable: true,        // 줌 기능 활성화
    snap: function(date) {
        // 스냅 간격 조정 (현재: 1분)
        const minute = 60 * 1000;
        return Math.round(date / minute) * minute;
    }
};
```

## 🔧 설정 및 최적화

### Timeline 성능 최적화
- 많은 정류장(100개 이상)이 있는 경우, `stack: false`로 설정하여 성능 향상
- `snap` 함수를 조정하여 더 큰 간격으로 스냅

### TMAP API 호출 최적화
- `utils/tmap_route.py`의 `get_route_with_order()` 함수에서 timeout 조정
- 여러 차량의 경로를 동시에 계산하는 경우, 병렬 처리 고려

## 🐛 트러블슈팅

### Timeline이 표시되지 않는 경우
1. 브라우저 콘솔에서 vis-timeline CDN 로드 확인
2. `vis-timeline-container` 요소가 존재하는지 확인
3. `initializeTimeline()` 함수가 호출되었는지 확인

### 드래그가 작동하지 않는 경우
1. `editable` 옵션이 올바르게 설정되었는지 확인
2. Depot 아이템은 `editable: false`로 설정되어 이동 불가
3. 브라우저 콘솔에서 에러 메시지 확인

### 재계산이 실패하는 경우
1. 백엔드 콘솔에서 TMAP API 호출 로그 확인
2. `TMAP_API_KEY` 환경변수가 올바르게 설정되었는지 확인
3. 네트워크 연결 및 TMAP API 할당량 확인

## 📚 vis-timeline 문서

- 공식 문서: https://visjs.github.io/vis-timeline/docs/timeline/
- GitHub: https://github.com/visjs/vis-timeline
- Examples: https://visjs.github.io/vis-timeline/examples/

## 🎓 추가 기능 아이디어

### 구현 가능한 확장 기능:
1. **정류장 추가/삭제**: timeline에서 직접 정류장 추가/삭제
2. **시간 제약 설정**: 특정 정류장의 방문 시간대 제한
3. **차량 용량 시각화**: timeline에서 각 차량의 적재량 표시
4. **실시간 미리보기**: 드래그 중 예상 거리/시간 표시
5. **실행 취소/다시 실행**: 변경 히스토리 관리
6. **템플릿 저장**: 자주 사용하는 경로 패턴 저장

## 💡 팁

- **빠른 수정**: Ctrl+Z (실행 취소) 기능을 원하면 변경 히스토리를 저장하세요
- **대량 편집**: 여러 정류장을 한 번에 선택하려면 Ctrl+클릭 사용 (multiselect 옵션 활성화 필요)
- **정밀 조정**: 줌인 후 드래그하면 더 정밀한 시간 조정 가능

## 📞 지원

문제가 발생하거나 질문이 있는 경우:
1. 브라우저 개발자 도구 콘솔 확인
2. 백엔드 터미널 로그 확인
3. GitHub Issues에 문의

---

**구현 완료일**: 2025년 10월 17일
**버전**: 1.0.0
**라이브러리**: vis-timeline v7.7.3
