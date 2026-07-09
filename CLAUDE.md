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
python launcher/main.py   # 직접 실행 (통합 진입점)
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
├── launcher\                        ▶ 전체 실행 진입점               ✅ main.py 구현 완료
│   └── scheduler\
├── core\                            ▶ 실행 컨트롤러 / 태스크 라우터  ✅ 구현 완료
├── modules\
│   ├── sns\         [F-01~F-04]     ▶ FB 크롤링 / Instagram 업로드   ✅ 구현됨
│   ├── dm\          [F-05~F-06]     ▶ DM 수신 / 자동응답 / 팔로업    ✅ 구현됨
│   ├── comment\                     ▶ 자동 댓글 관리                  ✅ 구현됨
│   ├── crm\                         ▶ Lead CRM / 주문감지 / 리포트    ✅ 구현됨
│   ├── common\                      ▶ Airtable 브릿지 / 중앙 로거 / 공통 유틸  ✅ 구현됨
│   ├── metrics\     [F-10]          ▶ KPI 통계 수집기                 ✅ 구현됨
│   ├── interaction_engine\ [F-11]  ▶ 좋아요·댓글·공유 자동화         ✅ 구현됨
│   ├── trade\       [F-07]          ▶ 거래/상품 견적 엔진             ⏸ 보류 (Phase 3 이후)
│   └── avatar\      [F-08]          ▶ 아바타 AI 반응                  ⏸ 보류 (Phase 3 이후)
├── services\                        ▶ Slack 알림 구현됨               ✅ slack_notifier
│                                      smtp_mailer / gpt_connector      ⏸ 보류
├── configs\                         ▶ YAML/JSON 설정 파일
├── data\
│   └── exported_data\
├── db\                              ▶ SQLite (retry_queue / kpi_snapshots / liked_comments)
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
| — | watchdog.ps1 (Flask/Streamlit/ngrok/launcher 자동 재시작) | ✅ |
| — | 중앙 로거 (modules/common/logger.py) | ✅ |
| — | retry queue (modules/common/retry_queue.py) | ✅ |
| — | health monitor (modules/common/health_monitor.py) | ✅ |
| — | dm/crm 모듈 중앙 로거 + retry queue 연동 | ✅ |
| — | 다계정 확장 (account_manager + facebook_crawler 다계정 지원) | ✅ |
| — | proxy scaling (계정별 proxy 설정 + Selenium 적용) | ✅ |
| — | parallel runner (ThreadPoolExecutor 다계정 병렬 실행) | ✅ |
| — | AI 응답 최적화 (Gemini 문맥 인식 응답 + 템플릿 폴백) | ✅ |
| — | core/ 모듈 (log_initializer / error_handler / task_router / run_engine) | ✅ |
| — | launcher/main.py (통합 진입점: BackgroundScheduler + Flask + retry_queue) | ✅ |
| — | modules/metrics/ KPI 수집기 (kpi_collector: 집계 + SQLite 스냅샷 + 대시보드 탭) | ✅ |
| — | modules/interaction_engine/ F-11 (engagement_tracker / auto_liker / interaction_scheduler) | ✅ |
| — | services/slack_notifier (Incoming Webhook: 운영 알림 + error_handler + watchdog 연동) | ✅ |
| — | Airtable Instagram_Posts 필드 추가 (ig_media_id / like_count / comments_count) | ✅ |
| — | 전체 파이프라인 운영 투입 검증 (launcher/main.py + watchdog + ngrok + Slack) | ✅ |
| — | Meta Webhook 등록 확인 (Callback URL / Verify Token / messages·comments 구독) | ✅ |
| — | FB crawler lazy-load 대응 + MAX_POSTS=10 환경변수화 | ✅ |

### 검증 완료 항목

- FB Crawling / AdsPower + Selenium Attach
- Airtable Source_Feeds Pipeline / Content Mapping
- Instagram Upload (재시도 3회 / 실패 마킹)
- Meta Webhook Verify / DM Webhook Receive ✅ 2026-05-13 운영 확인
- Lead_Interactions Logging / State Machine Structure
- CRM Base Structure / Architecture Lock
- launcher/main.py 통합 기동 (Flask + 8잡 + RetryQueue) ✅ 2026-05-13
- watchdog.ps1 자동 재시작 + Slack 알림 ✅ 2026-05-13
- Airtable Meta API 필드 자동 추가 (tools/add_instagram_posts_fields.py) ✅ 2026-05-13

### 보류 항목 (Phase 3 이후 — 현재 구현 대상 아님)

| 항목 | 내용 | 사유 |
|------|------|------|
| `modules/trade/` | 견적 엔진 / 상품 DB | Phase 3 이후 별도 기획 필요 |
| `modules/avatar/` | AI 아바타 반응 | Phase 3 이후 별도 기획 필요 |
| `services/smtp_mailer` | 이메일 알림 | Telegram + Slack으로 운영 알림 충분 |
| `services/gpt_connector` | GPT 연동 | Gemini로 현재 충족, 필요 시 추가 |


---

## 현재 단계: Production ✅

**[260512_16단계_운영안정화+문서화] 완료** — 2026-05-13

전체 파이프라인 운영 투입 완료.

### 핵심 위험 요소

- Selenium UI 변경 (Facebook 크롤러 취약)
- ngrok disconnect
- Meta access token 만료 (무제한 토큰 발급 완료 — 실질적 위험 낮음)
- queue deadlock / process crash
- Gemini API 429 (rate limit)

### 로드맵

| Phase | 목표 |
|-------|------|
| Phase 1 | ~~watchdog~~ ✅ / ~~auto restart~~ ✅ / ~~centralized logging~~ ✅ / ~~retry queue~~ ✅ / ~~monitoring~~ ✅ |
| Phase 2 | ~~auto reply~~ ✅ / ~~follow-up~~ ✅ / ~~lead qualification~~ ✅ / ~~revenue tracking~~ ✅ / ~~중앙 로거·retry queue 연동~~ ✅ |
| Phase 3 | ~~다계정 확장~~ ✅ / ~~proxy scaling~~ ✅ / ~~distributed queue~~ ✅ / ~~AI 응답 최적화~~ ✅ |

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
  - 반환: services(Flask/Streamlit/ngrok/launcher) / retry_queue 통계 / 최근 에러
  - watchdog 생존 확인: `get_watchdog_status()` (`get_health()`와 별개 함수, 기존 4개 서비스 카드 미영향) — `logs/watchdog.log` 마지막 줄 타임스탬프 기준, 90초 초과 시 비정상(`down`) 판정
  - 대시보드 `🐕 워치독` 탭(260709 추가, http://localhost:8501) — 명령어 없이 watchdog.ps1 생존 여부를 UI에서 확인 가능. 근거: ERR-047/ERR-050/ERR-051 조사에서 반복된 "감시 주체(watchdog) 자체가 죽어도 알 방법이 없었다" 문제(FP-033 계열) 해소 목적
  - 주의: 이 기능은 watchdog이 죽었을 때 이를 **감지**하는 용도이며, watchdog이 죽지 않도록 **방지**하는 기능이 아님 — 근본원인(ERR-050/ERR-051, 여전히 UNKNOWN)은 이 기능과 별개로 미해결 상태
- 다계정 관리: `from modules.common.account_manager import get_active_accounts`
  - 설정 파일: `configs/accounts.json` (없으면 .env 단일 계정 자동 폴백)
  - 계정 추가 후 `reload()` 또는 프로세스 재시작
  - `run_all_accounts()` — 전체 계정 일괄 크롤링
  - `acct.selenium_proxy_options()` — 계정별 proxy → Selenium 적용
- 병렬 실행: `from modules.common.parallel_runner import run_parallel`
  - `run_parallel(task_fn)` — 활성 계정 전체 병렬 실행, ThreadPoolExecutor 기반
  - `PARALLEL_MAX_WORKERS` env로 동시 실행 수 제어 (기본 3)
- AI 응답: `from modules.dm.ai_reply_generator import generate_reply`
  - Gemini 문맥 인식 개인화 응답, 실패 시 템플릿 자동 폴백
  - `dm_auto_reply.py`에서 자동 사용 (별도 설정 불필요)
- core/ 실행 구조:
  - `core/log_initializer.py` — 시작 시 중앙 로거 1회 초기화
  - `core/error_handler.py` — `@handle_errors` 데코레이터 / `safe_run()` 헬퍼
  - `core/task_router.py` — 태스크 이름 → 핸들러 분기 (register/dispatch)
  - `core/run_engine.py` — APScheduler 오케스트레이터, retry_queue 연동
    - `python -m core.run_engine` 으로 `launcher/main.py` 대신 단독 실행 가능
- interaction_engine (F-11):
  - `engagement_tracker.py` — Graph API로 like_count / comments_count 갱신 (30분 간격)
  - `auto_liker.py` — 게시물 댓글 자동 좋아요 (15분 간격), 중복 방지: `db/liked_comments.db`
  - 업로드 성공 시 `ig_media_id` Airtable 저장 (engagement 조회 전제)
  - Airtable Instagram_Posts 필드 추가 필요: `ig_media_id`, `like_count`, `comments_count`
  - `AUTO_LIKE_MAX_POSTS` env로 처리 게시물 수 제어 (기본 10)
- Slack 알림: `from services.slack_notifier import notify_error, notify_info, get_notify_fn`
  - `SLACK_WEBHOOK_URL` env 필수 (미설정 시 모든 알림 자동 생략)
  - `get_notify_fn()` — error_handler.notify_fn 연동용 callable (단일 문자열 인자)
  - `notify_daily_kpi(kpi)` — 일일 KPI 요약 발송
  - `notify_process_restart(name, status)` — watchdog 재시작 이벤트
  - watchdog.ps1: `Send-SlackAlert` 함수 추가, `$env:SLACK_WEBHOOK_URL` 참조
  - run_engine + launcher: 전체 스케줄 잡에 `notify_fn=_slack` 연동
- KPI 수집: `from modules.metrics.kpi_collector import collect_kpi, run_hourly_snapshot`
  - `collect_kpi(period)` — period: 'today' / '7d' / '30d' / 'all'
  - 반환: {upload, lead, followup, comment, queue} 각 지표 dict
  - SQLite 스냅샷: `db/kpi_snapshots.db` (시간별 저장)
  - 스케줄러: 1시간 간격 자동 수집 (run_engine + launcher 모두 등록)
  - 대시보드: dashboard.py KPI 탭 — 지표 카드 / 등급·파이프라인 차트 / 시계열 추이

---

## 오류 발견 시 의무 처리 규칙

오류가 발견되면 자동으로 아래 순서 실행:

1. `docs/ERROR_DATABASE.md` 에 ERR-NNN 항목 추가
2. `docs/FAILURE_PATTERN.md` 에 FP-NNN 항목 추가 (반복 패턴인 경우)
3. `docs/INCIDENT_TIMELINE.md` 에 INC-NNN 항목 추가 (운영 영향 발생 시)
4. git commit 필수 — 오류 기록 없는 수정 커밋 금지

수정 전 반드시 실제 entry point 확인:
- import chain 추적 후 실제 실행 파일 특정
- `instagram_uploader.py` 수정했는데 실제 runtime은 `main.py` 같은 오류 방지

Evidence 없는 완료 선언 금지:
- `Get-ChildItem` 파일 실존 확인
- `git log` 커밋 확인
- DB / Runtime 상태 직접 확인
- 대화 기록은 증거가 아님

---

## 단계 마무리 의무 체크리스트 (자동 실행)

모든 작업 단계 완료 시 반드시 순서대로 실행:

1. `docs/ERROR_DATABASE.md` 업데이트 (새 오류 또는 해결 내용)
2. `docs/FAILURE_PATTERN.md` 업데이트 (반복 패턴)
3. `docs/INCIDENT_TIMELINE.md` 업데이트 (운영 영향)
4. `docs/VALIDATION_STATUS.md` 업데이트 (단계 PASS)
5. `porting_logs/MERGE_JOURNAL.md` 업데이트 (이식/수정 기록)
6. git commit (증거 확정)
7. `Get-ChildItem` 실존 확인

이 체크리스트는 사용자 명령 없이 자동 실행.
생략 금지. 순서 변경 금지.

---
## [260527 Runtime Governance 추가]

### Absolute Forbidden
- 250723 삭제/dead 판정 금지
- 폴더 merge/전체 복사 금지
- 이름 기준 판단 금지
- git add/commit 선행 금지
- Evidence 없는 완료 선언 금지
- 승인 없는 destructive/merge 실행 금지

### Evidence Rule
우선순위: Runtime log > DB/API > grep > file > git > docs
추정 금지. 없으면 UNKNOWN.

### Session Start Rule
매 세션 시작 시 순서대로 실행:
1. Get-Content "C:\SNS_24AutoProject_260511\docs\CURRENT_RUNTIME_CONTEXT.md" -Encoding UTF8
2. Get-Content "C:\SNS_24AutoProject_260511\porting_logs\MERGE_JOURNAL.md" -Tail 20 -Encoding UTF8
3. git status --short

위 3개 확인 전 어떤 작업도 시작하지 않는다.

### STALE STATE CHECK
명령/조사를 설계하기 직전, 확인하려는 값의 현재 실제 출처(현재 활성 config vs 과거 백업/git 이력)를 먼저 특정한 뒤 명령을 설계한다.
근거: 260709 — Task Action이 이미 wrapper 경유로 전환된 상태에서 direct 실행 시절 원본값을 조회하려다 조회 자체가 무의미해진 사례(상세: ERR-047/MERGE_JOURNAL 참조).

### AUTONOMOUS INVESTIGATION MODE
read-only 조사 명령(`Get-*`, `grep`, `diff`, `status` 조회, 이미 승인된 진단용 Task의 반복 트리거 등 — 상태를 변경하지 않는 명령)에 한해, 매 단일 명령마다 승인을 기다리지 않고 여러 단계를 자율적으로 연속 실행한 뒤 결과를 한 번에 종합 보고할 수 있다.
- 적용 대상: 로그 확인, 이벤트 조회, 상태 확인, 여러 가설의 순차/병렬 read-only 테스트
- 명시적 제외(자동 실행 금지, 발견 즉시 중단 후 승인 요청): 파일 쓰기, commit, push, 삭제, Task 생성/변경, 시스템 설정 변경, 서비스 재시작 등 상태 변경 행동 — [H] STATE-CHANGE GATE 승인 절차는 그대로 유지, 이 규칙으로 약화되지 않는다.
- 보고 방식: 여러 스텝을 배치 실행했더라도 각 raw 출력은 요약 없이 전달(RAW OUTPUT 원칙 유지).
근거: 260709 세션에서 read-only 조사조차 매 단일 명령마다 승인을 거치는 방식이 조사 속도를 과도하게 저하시키고 사용자 피로를 유발함을 확인.

### ONE-LINE ELI10 PREFIX
Claude Code가 작업 결과를 보고하거나 다음 행동을 제안하는 모든 응답의 맨 첫 줄에, 지금 하려는/한 작업이 무엇인지 10살 아이도 이해할 수 있는 아주 쉬운 한 문장을 먼저 쓴다. 그다음 빈 줄 하나, 그다음부터는 기존 응답 형식(결과 보고, raw 로그, 진행 상황 등)을 그대로 이어간다 — 순서·내용 변경 없이 맨 위에 한 줄만 추가하는 것이며, 이 한 줄 때문에 기존 raw 출력이나 상세 보고가 생략·축약되지 않는다.
근거: 260709 세션 사용자 확정 요청 — 매 응답을 이해하기 쉽게 하기 위함.
