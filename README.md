# BidWin — 입찰공고 자동 수집 & 제안서 작성 Agent

> Solar Pro3 기반 Human-in-the-Loop 입찰 제안서 자동화 플랫폼

🔗 **라이브 데모**: https://winbid-assistant.lovable.app/

## 프로젝트 개요

- **목표**: 나라장터 입찰공고를 검색 → 자격 판별 → 제안서 초안/평가표 자동 생성 → PM 피드백 반영
- **핵심**: 8개의 전문 Agent를 Orchestrator가 조율하는 멀티 에이전트 파이프라인 (단순 챗봇이 아님)
- **방식**: PM과 Agent가 협업하는 Human-in-the-Loop 구조 (피드백 → 재작성 루프)
- **형식**: 12시간 해커톤 MVP

## 파이프라인 흐름

`Orchestrator.run_by_search()`가 아래 순서로 각 Agent에 작업을 위임합니다. 모든 단계의 로그와 툴 호출 이력은 Orchestrator가 누적해 결과로 반환합니다.

1. **공고 검색** — `SearchAgent` → 나라장터 OpenAPI에서 공고 목록 수집
2. **공고 자동 선택** — 수집된 목록의 첫 번째 공고(`bids[0]`)를 분석 대상으로 선택
3. **문서 파싱** — `DocumentAgent` → 업로드된 PDF를 Upstage Document Parse로 구조화 (PDF 미업로드 시 공고 메타데이터만으로 최소 컨텍스트 구성)
4. **회사 정보 조회** — `ProfileAgent` → 회사 프로필 로드 (mock 프로필 + 사용자 입력 override)
5. **요구사항 추출** — `RequirementAgent` → 문서 본문에서 자격/평가/제출서류 요건과 가중치 추출
6. **매칭 + 자격 판별** — `MatchingAgent` → `match_requirements`(승률) + `assess_eligibility`(자격) 호출
7. **충분성 판단 & 재시도 루프** — 자격 미충족·요건 누락 시 문서/프로필을 재수집해 최대 2회 재시도
8. **제안서 생성** — `ProposalAgent` → Solar Pro3로 초안 작성 (실패 시 룰 기반 폴백)
9. **본문 반영 재계산** — 생성된 제안서 본문을 근거에 포함해 매칭/자격 점수 재산출
10. **Red Team 평가** — `EvaluatorAgent` → 리스크 탐지 및 권고사항 생성
11. **산출물 생성** — `ArtifactAgent` → 제안서(docx) + 평가표(xlsx) 파일 생성

피드백 루프(`revise_with_feedback()`)는 PM 피드백을 받아 8~11단계를 다시 수행하고, 모든 버전을 `memory.versions`에 누적해 버전 간 비교가 가능하도록 보존합니다.

## 핵심 판별 로직

세 가지 점수는 모두 `backend/tools/` 안의 룰 기반 함수로 산출됩니다.

### 승률 (Win Probability) — `matching.py`

요구사항별 0~100점을 매긴 뒤 가중평균을 내고 휴리스틱 보정을 더합니다.

- **항목별 점수** (최댓값 채택): 회사 skills 단어가 요건에 포함되면 80, certifications 포함 90, projects 제목 포함 85. 직접 매칭이 약하면 토큰 겹침 비율로 보완(≥0.5 → 90, ≥0.3 → 75, 일부 겹침 → 60). 매칭이 없으면 항목 성격별 기본점수(절차성 45, 실적·경험 35, 그 외 20)를 부여합니다.
- **전체 점수**: `overall_score = Σ(항목점수 × weight) / Σ(weight)`
- **승률**: `win_probability = overall_score + (인증 ≥ 1건 AND 프로젝트 ≥ 1건이면 +10, 상한 100)`

### 자격 판별 (Eligibility) — `assess_eligibility.py`

각 요건을 세 상태로 분류합니다. skill/cert 직접 포함 또는 토큰 겹침비율 ≥ 0.45면 `matched`(가중치 전액), 절차성 항목(제출/서류/평가/심사/계획서)은 `review_needed`(가중치 50%), 그 외 미충족은 `missing`으로 처리합니다. 인증·면허·등록·자격·허가류가 누락되면 치명 요건(`critical_missing`)으로 별도 추적합니다.

- `match_score = (matched_weight 합계 / total_weight) × 100`
- `eligible = (match_score ≥ 60) AND (치명 요건 누락 없음)`

### 리스크 (Risk Score) — `evaluator.py`

Red Team 관점에서 제안서 본문과 매칭/자격 결과를 받아 누적 가산 방식으로 점수를 매깁니다. 과다약속 표현("완벽"/"100%"/"절대"/"보장"), 요구사항 누락, 낮은 적합도(overall_score < 50), 낮은 자격 점수(match_score < 50)를 리스크로 잡습니다.

```
risk_score = (리스크 항목 수 × 10)
           + (적합도 60 미만 항목 수 × 5)
           + max(0, 60 - overall_score) // 3
           + max(0, 50 - match_score)  // 4
```

리스크 항목별로 증빙 보강·문구 완화 등의 권고사항(중복 제거)도 함께 생성합니다.

## 빠른 시작

### 1. 환경 설정

```bash
# Python 가상환경 준비
python3 -m venv venv
source venv/bin/activate

# 라이브러리 설치
pip install -r requirements.txt
```

### 2. API 키 설정

```bash
cp .env.example .env
# .env 파일에 키 입력
```

| 환경변수 | 용도 | 필수 여부 |
|----------|------|-----------|
| `SOLAR_API_KEY` | Solar Pro3 제안서 생성/수정 | 권장 (없으면 룰 기반 폴백) |
| `UPSTAGE_API_KEY` | Document Parse (미설정 시 SOLAR_API_KEY 재사용) | 선택 |
| `NARAJANGTEO_SERVICE_KEY` | 나라장터 공고 검색 | 선택 |
| `SERVER_PORT` | 서버 포트 (기본 8000) | 선택 |
| `CORS_ORIGINS` | 허용 도메인 (콤마 구분, 비우면 전체 허용) | 선택 |

### 3. 서버 실행

```bash
# 프로젝트 루트에서
uvicorn backend.main:app --reload --port 8000
```

### 4. 접속

서버 실행 후 라이브 데모(https://winbid-assistant.lovable.app/)에서 회사 프로필을 등록하면 맞춤 공고 검색과 AI 제안서 생성을 사용할 수 있습니다.

## API 엔드포인트

모든 엔드포인트는 `/api` 프리픽스 아래에 있습니다 (`backend/routes/orchestrator.py`).

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/bids/search` | 나라장터 공고 검색 (외부 API 실패 시 빈 목록 + 안내 메시지 반환) |
| POST | `/api/orchestrator/start` | 파이프라인 실행, 전체 결과를 한 번에 반환 |
| POST | `/api/orchestrator/stream` | 파이프라인 실행, 로그를 NDJSON으로 스트리밍 |
| POST | `/api/orchestrator/stream-upload` | PDF 업로드 + 회사 프로필 입력을 받아 스트리밍 실행 |
| POST | `/api/orchestrator/revise` | PM 피드백을 반영해 제안서 재작성 및 재평가 |

## 기술 스택

- **백엔드**: Python + FastAPI + Uvicorn
- **LLM**: Solar Pro3 (Upstage, OpenAI 호환 인터페이스) — 제안서 생성/수정/변경요약
- **문서 구조화**: Upstage Document Parse API (PDF 텍스트 추출 폴백 포함)
- **공고 수집**: 나라장터 입찰공고 OpenAPI (용역/공사/물품/외자 업종별)
- **회사 정보(RAG)**: mock 프로필 + 프론트 입력 override
- **문서 생성**: python-docx (제안서), openpyxl (평가 매트릭스)
- **프론트엔드**: HTML / JS / CSS (의존성 최소)

## 프로젝트 구조

```
.
├── backend/
│   ├── main.py                 # FastAPI 앱 진입점 (정적 서빙 + 라우터 등록)
│   ├── config.py               # 환경변수 로드
│   ├── agents/                 # Orchestrator + 8개 전문 Agent
│   │   ├── orchestrator.py     #   파이프라인 조율 + 재시도 루프 + 버전 관리
│   │   ├── search_agent.py     #   공고 검색
│   │   ├── document_agent.py   #   PDF 파싱 / 메타데이터 폴백 / 캐시
│   │   ├── profile_agent.py    #   회사 정보 조회
│   │   ├── requirement_agent.py#   요구사항 추출
│   │   ├── matching_agent.py   #   매칭(승률) + 자격 판별
│   │   ├── proposal_agent.py   #   제안서 생성/수정
│   │   ├── evaluator_agent.py  #   Red Team 리스크 평가
│   │   ├── artifact_agent.py   #   docx/xlsx 산출물 생성
│   │   └── solar_client.py     #   Solar Pro3 클라이언트
│   ├── tools/                  # 각 Agent가 호출하는 도구 함수
│   │   ├── search_bids.py      #   나라장터 API 검색
│   │   ├── document_parser.py  #   Upstage Document Parse
│   │   ├── requirement_extractor.py  # 요구사항/메타데이터 추출
│   │   ├── company_rag.py      #   회사 프로필 조회
│   │   ├── matching.py         #   승률 산출
│   │   ├── assess_eligibility.py     # 자격 판별
│   │   ├── evaluator.py        #   리스크 산출
│   │   └── proposal_generator.py     # 제안서 초안/수정/변경요약
│   ├── services/
│   │   ├── file_generator.py   #   docx/xlsx 파일 생성
│   │   └── mock_data.py        #   샘플 공고/회사 프로필
│   └── routes/
│       └── orchestrator.py     #   API 엔드포인트
├── frontend/                   # HTML/JS 대시보드
│   ├── index.html
│   ├── script.js
│   └── styles.css
├── output/                     # 생성된 docx/xlsx (런타임 자동 생성)
├── requirements.txt
├── .env.example
└── README.md
```

## 설계 원칙

1. **Agent 중심 위임** — Orchestrator는 얇은 코디네이터, 실제 작업은 전용 Agent와 tool 함수가 담당
2. **폴백 우선** — 외부 API(LLM·Document Parse·나라장터) 실패 시 룰 기반 폴백·빈 목록 처리로 데모 중단 방지
3. **근거 기반 판단** — 매칭/자격/리스크 점수는 회사 프로필과 제안서 본문을 근거 텍스트로 사용
4. **본문 반영 재계산** — 제안서 생성 후 본문을 근거에 포함해 점수 재산출, 최종 점수는 항상 본문 반영 버전
5. **버전 보존** — 원본과 모든 수정본을 `memory.versions`에 누적해 버전 간 비교 지원
6. **API 키 보안** — 외부 키는 `.env`로 관리, 하드코딩 금지
