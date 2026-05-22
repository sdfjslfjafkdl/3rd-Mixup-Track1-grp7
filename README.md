# BizScope - 입찰공고 자동 수집 & 제안서 작성 Agent

> Solar Pro3 API 기반 Human-in-the-Loop 제안서 자동화 플랫폼

## 🎯 프로젝트 개요

- **목표**: 나라장터 입찰공고를 자동 수집 → 자격 필터링 → 제안서 자동 작성
- **핵심**: Solar Pro3 Agent가 스스로 도구(tool)를 호출해 작업을 수행 (단순 챗봇 ✗)
- **방식**: PM과 Agent가 협업하는 Human-in-the-Loop 구조
- **형식**: 12시간 해커톤 MVP

## 📋 5 Phase 파이프라인

| Phase | 담당 | 기능 |
|-------|------|------|
| Phase 1 | 자동 | 나라장터 입찰공고 수집 → 구조화 |
| Phase 2 | Agent | RAG 기반 자격 필터링 (충족/미달 판단) |
| Phase 3 | PM | 대시보드에서 공고 선택 |
| Phase 4 | Agent | 선택된 공고에 대해 제안서 초안 + 평가 매트릭스 생성 |
| Phase 5 | Loop | PM 피드백 → Agent 재작성 (보너스) |

## 🚀 빠른 시작

### 1. 환경 설정

```bash
cd /Users/hansalang/Downloads/MIXUP

# Python 환경 준비
python3 -m venv venv
source venv/bin/activate

# 라이브러리 설치
pip install -r requirements.txt
```

### 2. API 키 설정

```bash
cp .env.example .env
# .env 파일에 API 키 입력
# - SOLAR_API_KEY (필수)
# - UPSTAGE_API_KEY (선택)
# - NARAJANGTEO_SERVICE_KEY (선택)
```

### 3. 서버 실행

```bash
cd backend
python main.py
# 또는
uvicorn main:app --reload --port 8000
```

### 4. 웹 접속

```
http://localhost:8000
```

## 📚 기술 스택

- **백엔드**: Python + FastAPI
- **LLM**: Solar Pro3 API (tool calling / function calling)
- **문서 구조화**: Upstage Document Parse API (mock부터 시작)
- **RAG**: 회사 정보 검색 (벡터 DB 또는 프롬프트 기반)
- **문서 생성**: python-docx (제안서), openpyxl (평가 매트릭스)
- **프론트엔드**: HTML/JS (의존성 최소)

## 🏗️ 프로젝트 구조

```
MIXUP/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── agents/           # Solar Pro3 Agent 로직
│   ├── tools/            # Tool 함수들 (mock → 실제 API)
│   ├── models/           # Pydantic 데이터 모델
│   ├── services/         # 파일 생성 등 비즈니스 로직
│   └── routes/           # API 엔드포인트
├── frontend/             # HTML/JS 대시보드
├── requirements.txt
├── .env.example
└── README.md
```

## 🔧 개발 진행 순서 (각 STEP마다 테스트)

- **STEP 0**: ✅ 폴더 구조 + 라이브러리
- **STEP 1**: FastAPI + Solar Pro3 연결 테스트
- **STEP 2**: Tool 정의 + mock 데이터
- **STEP 3**: [Phase 1] 공고 수집
- **STEP 4**: [Phase 2] 자격 필터링 Agent
- **STEP 5**: [Phase 3] PM 대시보드
- **STEP 6**: [Phase 4] 제안서 작성 Agent
- **STEP 7**: [Phase 4] docx/xlsx 파일 생성
- **STEP 8**: 웹 화면 통합
- **STEP 9**: 나라장터 API 연동
- **STEP 10**: [Phase 5] PM 피드백 반복 루프 (보너스)

## 📝 주요 설계 원칙

1. **Mock 우선**: 모든 외부 API는 먼저 mock으로 구현, 나중에 실제 API로 교체
2. **Agent 중심**: Solar Pro3가 도구를 자율적으로 선택·호출 (Human-in-the-Loop)
3. **환각 방지**: 모든 판단·제안은 수집된 자료에 근거해 출처 명시
4. **한국어 주석**: 초보 팀을 위해 코드에 충분히 한국어 주석 포함
5. **API 키 보안**: 모든 외부 키는 .env로 관리, 하드코딩 금지

## 📞 연락처

BizScope MVP Team
