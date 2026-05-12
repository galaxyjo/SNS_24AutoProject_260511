# CLAUDE.md — SNS_24AutoProject

## 프로젝트 개요

**SNS_24AutoProject** — 24/7 Lead Acquisition Operating System

Facebook 콘텐츠 자동 크롤링 → Instagram 자동 업로드 → DM Webhook 수신 → 리드 자동응답/팔로업 → CRM 전환까지 이어지는 완전 자동화 운영 시스템.

```
Content → Lead → CRM → Revenue
```

핵심 전략: 최소비용 최대효율 / Event Driven / Airtable Control Tower / 다계정 확장 가능 구조

---

## 저장소 규칙

| 저장소 | 역할 | 규칙 |
|--------|------|------|
| `C:\SNS_24AutoProject_260511` | **Active** — 실행·운영·배포 기준 (Single Source of Truth) | git 관리, 실제 실행 |
| `C:\SNS_24AutoProject_250723` | **Reference Only** — GPT 1년치 설계/로직 참조용 | 실행 금지 / 배포 금지 / 자동 이식 금지 |

> 250723 저장소 코드는 반드시 manual review 후 수동 이식. 자동 복사 금지.

---

## 환경 설정

```bash
cp .env.example .env
# .env 편집: Airtable / Instagram / Gemini / Meta Webhook 키 입력
```

**실행:**
```powershell
.\run_scheduler.ps1       # 전체 스케줄러 실행
.\watchdog.ps1            # 프로세스 감시 / 자동 재시작 (별도 터미널)
python insta_scheduler.py # 직접 실행
python dashboard.py       # Streamlit 대시보드
```

**핵심 환경변수:**
- `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`
- `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ID`
- `GEMINI_API_KEY`
- `META_VERIFY_TOKEN`

---

## MasterTree 구조

> 기준: `docs/MASTER_TREE.md` (251015 수정판)

```
C:\SNS_24AutoProject_260511\
├── launcher\                        ▶ 전체 실행 진입점 (main.py 예정)
│   └── scheduler\
├── core\                            ▶ 실행 컨트롤러 / 태스크 라우터 (구현 예정)
├── modules\
│   ├── sns\         [F-01~F-04]     ▶ FB 크롤링 / Instagram 업로드  ✅ 구현됨
│   ├── dm\          [F-05~F-06]     ▶ DM 수신 / 자동응답 / 팔로업   ✅ 구현됨
│   ├── comment\                     ▶ 자동 댓글 관리                 ✅ 구현됨
│   ├── crm\                         ▶ Lead CRM / 주문감지 / 리포트   ✅ 구현됨
│   ├── common\                      ▶ Airtable 브릿지 / 중앙 로거 / 공통 유틸   ✅ 구현됨
│   ├── trade\       [F-07]          ▶ 거래/상품 견적 엔진            🔲 폴더만 생성
│   ├── avatar\      [F-08]          ▶ 아바타 AI 반응                 🔲 폴더만 생성
│   ├── metrics\     [F-10]          ▶ 통계 수집                      🔲 폴더만 생성
│   └── interaction_engine\ [F-11]  ▶ 좋아요·댓글·공유 자동화        🔲 폴더만 생성
├── services\                        ▶ GPT / SMTP / Slack / 번역      🔲 폴더만 생성
├── configs\                         ▶ YAML/JSON 설정 파일
├── data\
│   └── exported_data\
├── db\                              ▶ SQLite 스키마 / 마이그레이션
├── docs\                            ▶ MASTER_TREE.md 등 문서
├── logs\
│   ├── summary\
│   ├── error\
│   └── function\
├── tools\
│   └── integrity\                   ▶ SHA256 무결성 검증
├── tests\
└── backup\
```

---

## 현재 구현 상태

### 완료된 단계 (git log 기준)

| 단계 | 내용 | 상태 |
|------|------|------|
| 1~10 | FB 크롤링 → Airtable → Instagram 업로드 파이프라인 | ✅ |
| 11~12 | Instagram DM 수신 / 자동응답 (Webhook) | ✅ |
| 13 | 팔로업 DM 스케줄러 | ✅ |
| 14 | Lead CRM 고도화 (lead_scorer, order_detector) | ✅ |
| 15 | 자동 댓글 관리 (comment_poller, comment_auto_reply) | ✅ |
| 16 | Streamlit 대시보드 고도화 | ✅ |
| — | watchdog.ps1 (Flask/Streamlit/ngrok/insta_scheduler 자동 재시작) | ✅ |
| — | 중앙 로거 (modules/common/logger.py) | ✅ |
| — | retry queue (modules/common/retry_queue.py) | ✅ |
| — | health monitor (modules/common/health_monitor.py) | ✅ |
| — | dm/crm 모듈 중앙 로거 + retry queue 연동 | ✅ |
| — | 다계정 확장 (account_manager + facebook_crawler 다계정 지원) | ✅ |

### 검증 완료 항목

- FB Crawling / AdsPower + Selenium Attach
- Airtable Source_Feeds Pipeline / Content Mapping
- Instagram Upload (재시도 3회 / 실패 마킹)
- Meta Webhook Verify / DM Webhook Receive
- Lead_Interactions Logging / State Machine Structure
- CRM Base Structure / Architecture Lock

### 미구현 (MasterTree 기준 예정)

- `modules/trade/` — 견적 엔진 / 상품 DB
- `modules/avatar/` — AI 아바타 반응
- `modules/metrics/` — 통계 수집기
- `modules/interaction_engine/` — 좋아요·댓글·공유 자동화 (F-11)
- `core/` — run_engine, task_router, error_handler
- `services/` — gpt_connector, smtp_mailer, slack_notifier
- `launcher/main.py` — 통합 실행 진입점

---

## 현재 단계: Pre-Production Stabilization

기능 구현보다 **운영 안정성**이 우선.

### 핵심 위험 요소

- Selenium UI 변경 (Facebook 크롤러 취약)
- ngrok disconnect
- Meta access token 만료
- queue deadlock / process crash
- Gemini API 429 (rate limit)

### 로드맵

| Phase | 목표 |
|-------|------|
| Phase 1 | ~~watchdog~~ ✅ / ~~auto restart~~ ✅ / ~~centralized logging~~ ✅ / ~~retry queue~~ ✅ / ~~monitoring~~ ✅ |
| Phase 2 | ~~auto reply~~ ✅ / ~~follow-up~~ ✅ / ~~lead qualification~~ ✅ / ~~revenue tracking~~ ✅ / ~~중앙 로거·retry queue 연동~~ ✅ |
| Phase 3 | ~~다계정 확장~~ ✅ / proxy scaling / distributed queue / AI 응답 최적화 |

---

## KPI

- 일일 DM 수신 수
- Lead 전환율 / 주문 전환율
- Follow-up 성공률
- Queue 안정성 / Upload 성공률

---

## 운영 규칙

- `.env` 파일은 커밋하지 않는다 (`.gitignore` 적용)
- `load_dotenv(override=True)` 사용 — 시스템 환경변수보다 `.env` 우선
- 파일 읽기 시 인코딩 문제 발생 시 `latin-1` 우회 후 한국어 처리
- Gemini API 호출은 429 에러 시 재시도 + 스로틀 적용
- 250723 참조 저장소 코드는 manual review 없이 자동 이식 금지
- `db/`, `logs/`, `backup/` 폴더는 gitignore 대상 (빈 폴더는 git 미추적)
- 모든 모듈 로거는 `from modules.common.logger import get_logger` 사용
  - `logs/summary/app.log` — INFO+ 통합
  - `logs/error/error.log` — ERROR+ 전용
  - `logs/function/{모듈명}.log` — DEBUG+ 모듈별 상세
- retry queue: `from modules.common.retry_queue import get_retry_queue`
  - 실패 태스크 `db/retry_queue.db` 에 영속 저장, 백오프 10s/60s/300s
- health monitor: `from modules.common.health_monitor import get_health`
  - 단독 실행: `python -m modules.common.health_monitor`
  - 반환: services(Flask/Streamlit/ngrok/insta_scheduler) / retry_queue 통계 / 최근 에러
- 다계정 관리: `from modules.common.account_manager import get_active_accounts`
  - 설정 파일: `configs/accounts.json` (없으면 .env 단일 계정 자동 폴백)
  - 계정 추가 후 `reload()` 또는 프로세스 재시작
  - `run_all_accounts()` — 전체 계정 일괄 크롤링
