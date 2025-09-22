# Route Optimization Tool

경로 최적화를 위한 Flask 웹 애플리케이션입니다.

## 설치 및 실행

### 1. 필수 요구사항
- Python 3.7 이상
- 가상환경 (.venv 폴더가 상위 디렉토리에 있어야 함)

### 2. API 키 설정

#### 2.1 환경변수 파일 설정
1. `.env.example` 파일을 `.env`로 복사
2. `.env` 파일에서 다음 API 키들을 실제 키로 교체:

```bash
# T-map API 키 (SK Open API에서 발급)
TMAP_API_KEY=your_tmap_api_key_here

# Mapbox Access Token (Mapbox 계정에서 발급)
MAPBOX_ACCESS_TOKEN=your_mapbox_access_token_here
```

#### 2.2 API 키 발급 방법

**T-map API 키:**
1. [SK Open API](https://openapi.sk.com/) 회원가입
2. T-map 서비스 신청
3. 발급받은 앱키를 `TMAP_API_KEY`에 입력

**Mapbox Access Token:**
1. [Mapbox](https://www.mapbox.com/) 계정 생성
2. Account > Access tokens 페이지에서 토큰 생성
3. 발급받은 토큰을 `MAPBOX_ACCESS_TOKEN`에 입력

### 3. 실행
```bash
# 배치 파일로 실행 (Windows)
run_app.bat

# 또는 PowerShell 스크립트로 실행
.\run_app.ps1
```

배치 파일이 자동으로:
- 필요한 종속성 확인 및 설치
- Flask 애플리케이션 시작

### 4. 접속
웹 브라우저에서 `http://127.0.0.1:5000` 접속

## 기능

- 지도상에서 위치 추가/편집
- T-map API를 사용한 거리/시간 매트릭스 생성
- Google OR-Tools를 사용한 차량 경로 최적화
- 최적화 결과 시각화

## 주의사항

⚠️ **보안**: `.env` 파일은 절대 Git에 커밋하지 마세요. 이미 `.gitignore`에 포함되어 있습니다.

## 파일 구조

```
map_app/
├── .env.example          # 환경변수 템플릿
├── .env                  # 실제 환경변수 (Git 제외)
├── .gitignore           # Git 제외 파일 목록
├── app.py               # Flask 메인 애플리케이션
├── requirements.txt     # Python 패키지 의존성
├── run_app.bat         # Windows 실행 스크립트
├── static/             # CSS, JavaScript 파일
├── templates/          # HTML 템플릿
└── utils/              # 유틸리티 모듈
```