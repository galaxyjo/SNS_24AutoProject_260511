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

※ 이 표의 ✅는 구현·빌드 완료를 의미하며, 현재 Active Runtime 여부는 Runtime Caller·Import Chain·Runtime Evidence로 별도 확인한다.

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
  - `core/run_engine.py` — **INACTIVE LEGACY / HOLD** (260723 Runtime Truth 정정, 근거·상세는 본 문서 하단 `[260723 Runtime Truth Safety Lock 추가]` 섹션 참조)
    - 현재 유일하게 증명된 Live Posting Entry Point: `watchdog.ps1` → `launcher/main.py` → APScheduler → `_job_insta_upload()` → `AirtableRepository` → `publish_single()` → Meta Graph API → `mark_post_result()`
    - `core/run_engine.py`는 Caller 미확인 상태이며 watchdog 감시 대상이 아니고, 현재 Airtable Schema와 어긋나는 필드를 참조하며, 공용 `publish_single()`과 Repository 선점 계약을 우회한다
    - 사용자 별도 승인과 Runtime 검증 전에는 실행·활성화·삭제·병행 사용 금지 — APScheduler와 병행 실행하여 Execution Owner를 이중화하지 않는다
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
  - run_engine + launcher: 전체 스케줄 잡에 `notify_fn=_slack` 연동 (주: `core/run_engine.py`는 INACTIVE LEGACY — 위 `core/run_engine.py` 항목 참조, 실제 알림은 `launcher/main.py` 경로에서만 발생)
- KPI 수집: `from modules.metrics.kpi_collector import collect_kpi, run_hourly_snapshot`
  - `collect_kpi(period)` — period: 'today' / '7d' / '30d' / 'all'
  - 반환: {upload, lead, followup, comment, queue} 각 지표 dict
  - SQLite 스냅샷: `db/kpi_snapshots.db` (시간별 저장)
  - 스케줄러: 1시간 간격 자동 수집 (run_engine + launcher 모두 등록, 주: `core/run_engine.py`는 INACTIVE LEGACY — 위 `core/run_engine.py` 항목 참조)
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

### 승인 범위 명시 원칙
read-only 조사 단계에 대한 승인은 그 조사 자체에만 유효하다 — 조사 결과에 대한 문서 기록(`docs/ERROR_DATABASE.md`/`docs/FAILURE_PATTERN.md`/`docs/INCIDENT_TIMELINE.md` 등) 및 git commit까지 자동으로 승인된 것으로 간주하지 않는다.
- 조사 완료 후에는 결과를 raw로 먼저 보고한다.
- 문서 기록 / git commit은 그 보고와 별도로 승인을 받은 뒤에만 진행한다.
- "오류 발견 시 의무 처리 규칙" · "단계 마무리 의무 체크리스트"의 "자동 실행"·"사용자 명령 없이 자동 실행" 문구는 이 승인 절차를 생략해도 된다는 의미가 아니다. 두 규칙이 충돌하는 것처럼 보이는 경우, 이 원칙(승인 범위 명시)이 우선한다.

근거: 2026-07-10 heartbeat_monitor(ERR-053) 조사 — 사용자가 승인한 것은 read-only 진단 명령(`Get-WinEvent`/`Get-ScheduledTask`/`Select-String`/`Get-Content` 등, 세션 중 4회에 걸쳐 전달됨)뿐이었으나, Claude Code는 별도 승인 요청 없이 그 결과를 근거로 `docs/ERROR_DATABASE.md`(ERR-053 신규)·`docs/FAILURE_PATTERN.md`(FP-040 신규)·`docs/INCIDENT_TIMELINE.md`(INC-028 Note 2 추가)를 작성하고 git commit(`d49ab61`)까지 이어서 실행함 — "오류 발견 시 의무 처리 규칙"의 "자동 실행" 문구를 근거로 판단했으나, 사용자가 실제로 승인한 범위(read-only 조사)를 벗어난 실행이었음.

### Session Start Rule
매 세션 시작 시 순서대로 실행:
1. Get-Content "C:\SNS_24AutoProject_260511\docs\CURRENT_RUNTIME_CONTEXT.md" -Encoding UTF8
2. Get-Content "C:\SNS_24AutoProject_260511\porting_logs\MERGE_JOURNAL.md" -Tail 20 -Encoding UTF8
3. git status --short
4. Get-Content "C:\SNS_24AutoProject_260511\docs\SILICON_VALLEY_EXECUTION_STANDARD.md" -Encoding UTF8 (260722 추가 — 실행 표준 SSOT, 표준 결과 출력 포맷·FACT/INFERENCE/UNKNOWN/RISK·Single Canary·상태변경 실행주체 등)

위 4개 확인 전 어떤 작업도 시작하지 않는다.

### STALE STATE CHECK
명령/조사를 설계하기 직전, 확인하려는 값의 현재 실제 출처(현재 활성 config vs 과거 백업/git 이력)를 먼저 특정한 뒤 명령을 설계한다.
근거: 260709 — Task Action이 이미 wrapper 경유로 전환된 상태에서 direct 실행 시절 원본값을 조회하려다 조회 자체가 무의미해진 사례(상세: ERR-047/MERGE_JOURNAL 참조).

### AUTONOMOUS INVESTIGATION MODE
read-only 조사 명령(`Get-*`, `grep`, `diff`, `status` 조회, 이미 승인된 진단용 Task의 반복 트리거 등 — 상태를 변경하지 않는 명령)에 한해, 매 단일 명령마다 승인을 기다리지 않고 여러 단계를 자율적으로 연속 실행한 뒤 결과를 한 번에 종합 보고할 수 있다.
- 적용 대상: 로그 확인, 이벤트 조회, 상태 확인, 여러 가설의 순차/병렬 read-only 테스트
- 명시적 제외(자동 실행 금지, 발견 즉시 중단 후 승인 요청): 파일 쓰기, commit, push, 삭제, Task 생성/변경, 시스템 설정 변경, 서비스 재시작 등 상태 변경 행동 — [H] STATE-CHANGE GATE 승인 절차는 그대로 유지, 이 규칙으로 약화되지 않는다.
- 보고 방식: 여러 스텝을 배치 실행했더라도 각 raw 출력은 요약 없이 전달(RAW OUTPUT 원칙 유지).
근거: 260709 세션에서 read-only 조사조차 매 단일 명령마다 승인을 거치는 방식이 조사 속도를 과도하게 저하시키고 사용자 피로를 유발함을 확인.

### 단계별 Bookending 원칙
각 실행 단계(Runbook Step)를 시작하기 전, 지금 상태가 무엇인지 한 줄로 짧게 확인하고 시작한다 (예: "지금 X가 Y 상태다, 이제 Z를 하겠다"). 단계를 마친 후에는, 그 결과로 상태가 어떻게 바뀌었는지 한 줄로 짧게 확인하고 마친다 (예: "이제 X는 Y가 아니라 Z 상태다").
- [B] RESULT-FIRST OUTPUT / [J] RESULT JUDGMENT와는 목적이 다르다 — 그 둘은 "이 작업이 맞았나/성공했나"를 판정하는 것이고, bookending은 판정과 무관하게 "작업 전후로 상태 스냅샷을 남겨서 무엇이 바뀌었는지 항상 추적 가능하게" 하는 습관이다.
- Session Start Rule(세션 시작 시 1회) / STALE STATE CHECK(명령 설계 직전 1회)와도 다르다 — bookending은 "매 작업 단계마다" 반복되는 더 촘촘한 습관이며, 세션당 1회나 명령 설계 직전 1회로 끝나지 않는다.
- 새 승인 절차나 체크리스트를 신설하는 것이 아니다 — 기존 응답 형식(ONE-LINE ELI10 PREFIX 등)에 자연스럽게 붙는 한두 줄 수준의 습관이며, 별도 게이트를 통과해야 하는 절차가 아니다.

근거: 2026-07-09~10 세션에서 "작업 전후 상태확인 습관화"가 다음 세션 승계 우선순위 항목(3번)으로 명시적으로 지정됨.

### ONE-LINE ELI10 PREFIX
**260729 위치 정정**: 이 한 줄은 더 이상 응답 맨 첫 줄이 아니라 **응답 맨 마지막, 복붙 블록(코드/승인문 등) 밖**에 둔다 — 아래 "단계 위치 표기 헤더" 규칙이 응답 첫 줄 자리를 대신한다. 내용 자체(10살 아이도 이해할 아주 쉬운 한 문장, raw 출력·상세 보고를 생략·축약하지 않음)는 그대로 유지된다.
근거: 260709 세션 사용자 확정 요청(최초, 맨 첫 줄) → 260729 세션에서 "단계 위치 표기 헤더"가 첫 줄 자리를 차지하며 위치만 맨 마지막으로 이동 확정.

### 단계 위치 표기 헤더 (STAGE POSITION HEADER)
모든 중간 출력·최종 출력의 **첫 줄**에 현재 전체단계·우선순위단계·세부단계·시작/종료 상태를 반드시 표시한다. 프로젝트 전체 모든 업무 진행(9단계뿐 아니라 10단계·11단계 이후 전부)에 적용되는 고정 규칙이다.

**고정 형식**:
```
(YYMMDD_HH:MMam/pm) (전체단계)우선순위번호단계 : 세부단계번호 세부단계명 시작/종료 — 판정어: Evidence 기반 이유
```

**예시**:
```
(260729_08:09am) (9)11단계 : 9-10-3-A Facebook Crawl 내부 배치 감사 시작 — IN_PROGRESS: Active 배치 실패 경로를 Read-only로 확인한다.
(260729_08:30am) (9)11단계 : 9-10-3-A Facebook Crawl 내부 배치 감사 종료 — SUCCESS: Caller·예외·반환·Retry 계약이 Evidence로 확인됐다.
```

**적용 규칙**:
1. 모든 출력 첫 줄에 반드시 표기한다(시간 없는 출력 금지).
2. 세부단계 착수 시 `시작`, 결과 제출 시 `종료`를 명시한다.
3. 현재 단계가 SUCCESS로 종료되기 전 다음 단계 번호를 사용하지 않는다.
4. 판정어와 Evidence 기반 이유를 같은 첫 줄에 작성한다(요약 없이 짧게).
5. 우선순위 번호와 세부단계 번호를 생략하지 않는다.
6. ONE-LINE ELI10 PREFIX(위 항목, 260729 위치 정정)는 이 헤더와 자리가 겹치지 않는다 — 헤더는 맨 첫 줄, ELI10은 맨 마지막 줄(복붙 블록 밖)에 각각 고정.

근거: 260729 세션 — 9단계(예외삼킴·데이터손실 감사) 진행 중 회장이 명시적으로 확정. "모든 업무진행에 적용된다. 다음 10단계 11단계 다 적용. 모든 진행에 적용" — 특정 단계 한정이 아니라 프로젝트 전체 항구 규칙으로 지정됨.

### 압축 출력 형식 (COMPACT OUTPUT FORMAT)
전체 출력을 5~10줄로 제한한다. 위 "단계 위치 표기 헤더"(첫 줄)는 그대로 유지하고, 그 아래를 다음 4개 항목으로만 구성한다.

```
(첫 줄) 단계 위치 표기 헤더 — 판정어: Evidence 기반 이유
FACT: 핵심 Evidence 최대 3개
RISK: 핵심 위험 최대 2개
ACTION: 지금 할 일 1개만
(승인 필요 시) 복붙 승인문 1개
```

**적용 규칙**:
1. 긴 표·장문 설명 금지 — Exception Inventory 등 상세 표는 회장/GPT가 raw로 요청할 때만 출력한다.
2. Raw Evidence는 요청받을 때만 출력한다(기본은 압축, 요청 시 즉시 원문 전환).
3. 이미 확인된 내용을 반복하지 않는다.
4. 현재 단계가 성공으로 끝나기 전 다음 단계를 언급하지 않는다.
5. ELI10 한 줄(위 ONE-LINE ELI10 PREFIX 규칙)은 그대로 복붙 블록 밖, 응답 맨 마지막에 유지한다 — 이 압축 형식과 자리가 겹치지 않는다.

근거: 260729 세션 — 9단계 감사 중 Exception Inventory 표·장문 Gate 제출 형식이 과도하게 길어지자 회장이 "명령한다"로 직접 지정. 기존 상세 표 기반 보고 형식보다 이 압축 형식이 우선 적용되며, 상세 Evidence 자체를 없애는 것이 아니라 기본 출력에서 감추고 요청 시에만 꺼내는 방식이다.

### 관리자 명령어 복붙 규칙
Claude Code 세션은 `SNS_Watchdog` 서비스 제어 등 관리자 권한이 필요한 명령을 직접 실행할 권한이 없다(반복 확인됨 — `Restart-Service` 시도 시 `CouldNotStopService`). 회장에게 대신 실행을 부탁해야 하는 명령은 문장 안에 섞어 쓰지 않고, **항상 명령어만 담긴 별도 코드블록**으로 출력한다.

**금지(기존 방식)**: "회장님이 관리자 PowerShell에서 `Restart-Service SNS_Watchdog` 실행 부탁드립니다." (문장 안에 명령어가 섞임)

**적용(신규 방식)**:
```
Restart-Service SNS_Watchdog
```

**적용 규칙**:
1. 코드블록 안에는 명령어만 넣는다 — 설명·주석·prompt 기호(`PS>` 등) 없이 그대로 복붙 가능해야 한다.
2. 코드블록 앞뒤에 짧은 한 줄 설명은 허용하되(예: "재시작 명령입니다"), 명령어 자체를 문장에 인라인으로 섞지 않는다.
3. 관리자 권한이 필요해 회장에게 대신 부탁하는 모든 명령(서비스 재시작·중지·Task Scheduler 조작 등)에 동일하게 적용한다.

근거: 260729 세션 — Facebook/Dome/KPI Defect A~E 검증 과정에서 매 Runtime Restart마다 회장에게 명령 실행을 반복 요청했는데, 문장 속에 명령어가 섞여 있어 복붙이 불편하다고 회장이 명시적으로 지적하며 "복붙형식으로 출력할 것, 명령어만"이라고 확정.

---

## [260723 Runtime Truth Safety Lock 추가]

> 목적: CLAUDE.md 서술과 실제 Runtime Evidence가 어긋나 있던 2개 항목(core/run_engine.py, n8n 게시 Endpoint)을 정정하고, 재발 방지를 위해 현재 상태를 명시적으로 잠근다. 근거: 260723 Claude Code/Codex 교차검증 세션 — Airtable MCP 직접 쿼리(Instagram_Posts.post_status 스키마에 draft/scheduled/rejected 선택지가 존재하나 Runtime 코드는 미사용 확인), n8n 로컬 `~/.n8n/database.sqlite` 직접 쿼리(workflow_entity 1행, active=0, triggerCount=0, 미설정 스캐폴드 확인), `launcher/main.py` publish_single() 독스트링과 `docs/ARCHITECTURE_LOCK.md`의 n8n Endpoint(P0 미구현) 서술 대조.

### Active Runtime
- Active Posting Owner: `launcher/main.py`
  - 실제 경로: `watchdog.ps1` → `launcher/main.py` → APScheduler → `_job_insta_upload()` → `AirtableRepository` → `publish_single()` → Meta Graph API → `mark_post_result()`
- Inactive Legacy: `core/run_engine.py`
  - 현재 Caller가 확인되지 않음(자기 자신 외 import/호출부 없음)
  - watchdog 감시 대상 아님
  - 현재 Airtable Schema와 어긋나는 필드를 참조함
  - 공용 `publish_single()`과 Repository 선점 계약을 우회함
  - 사용자 별도 승인과 Runtime 검증 전에는 실행·활성화·삭제·병행 사용 금지
- Execution Owner 이중화 금지: APScheduler(`launcher/main.py`)와 `core/run_engine.py`를 병행 실행하지 않는다.

### n8n 상태
- 운영 Workflow: 0개
- 비활성 테스트 초안: 1개(`My workflow`, 실행 이력 없음 — 운영 자산 또는 재사용 가능한 Workflow로 간주하지 않음)
- Python Publish API Contract(`/api/v1/instagram/publish`): 미구현 — 인증, 입력 Schema, 출력 Schema, 오류 계약 모두 미구현
- n8n WF-01~WF-05 운영 Workflow: 구현되지 않음
- `publish_single()` 관련 문서/독스트링에 n8n Endpoint가 이미 호출하는 것처럼 표현된 내용은 현재 구현 사실이 아니라 미래 설계 의도임
- 현재 상태: `PLANNED / NOT IMPLEMENTED`
- n8n은 안전 Gate 완료 후 Trigger·Schedule·Orchestration 역할로만 구현한다 — Instagram Graph API를 직접 호출하거나 Token을 보유하지 않는다.

### 구현 전 필수 조건 (n8n 연결 이전)
1. User Approval Gate
2. 발행 직전 Final Quality Gate
3. Publish Idempotency 또는 Ledger
4. Account-level Kill Switch
5. Execution Owner 단일화
6. n8n ↔ Python API Contract
7. 불확실한 게시 결과 Reconciliation

---

## Multi-AI Review Policy

### Objective
Maximize code quality while minimizing unnecessary review overhead during the stabilization phase.

### Roles
- Claude Code
  - Owns implementation.
  - Executes code changes.
  - Runs runtime tests.
  - Produces evidence.
- Codex
  - Performs regression review.
  - Reviews architecture consistency.
  - Detects unintended side effects.
  - Challenges implementation assumptions.
- GPT
  - Owns strategy.
  - Prioritizes work.
  - Reviews architectural direction.
  - Resolves disagreements between reviewers.
  - Maintains long-term project consistency.

### Review Policy
Not every change requires the full review pipeline.

#### High-Risk Changes (Mandatory Full Review)
Examples:
- Repository Interface changes
- Dependency Injection changes
- Runtime behavior changes
- Scheduler / Watchdog
- Database schema
- Cross-module refactoring
- Production workflow modifications

Workflow:
Claude Code
→ Codex Review
→ Claude Revision
→ GPT Architecture Audit
→ Runtime Validation
→ Approval

#### Low-Risk Changes (Fast Path)
Examples:
- Read-only investigation
- Logging improvements
- Documentation
- Small isolated fixes
- UI text
- Local helper functions

Workflow:
Claude Code
→ Runtime Verification
→ Report

Codex and GPT review only if new evidence or unexpected behavior appears.

### Repository Policy
- Maintain a single Source of Truth project.
- Do not create duplicate project folders.
- All AI agents operate on the same active repository.
- Separate responsibilities, not repositories.

### Principle
One Project.
Multiple AI Roles.
Evidence First.
Runtime Before Opinion.
Review Depth proportional to Risk.

> 참고: 위 "Approval"은 리뷰 파이프라인 내부의 최종 검토 합의 단계를 의미하며, 실제 상태 변경/실행에 대한 승인 권한은 [H] STATE-CHANGE GATE 및 "승인 범위 명시 원칙"에 따라 사용자(회장)에게 있다. 이 섹션이 그 권한을 대체하지 않는다.

---

## [260726 수정 승인 5요소 원칙 추가]

Claude Code가 문제를 발견하고 "고치겠습니다"라고 말하기 전에, 먼저 스스로에게 다음을 묻는다:

> 이건 직접 고쳐야 하는 핵심 기능인가(BUILD) / 기존 기능을 재사용할 수 있는가(REUSE) / 이미 검증된 도구를 가져오는 것이 나은가(BUY/ADOPT)?

그리고 **"고치겠습니다"라는 말과 동시에, 같은 응답 안에** 반드시 아래 5가지를 채워서 출력한다. 이 5가지가 빠진 채로 "고치겠습니다"만 말하는 것은 금지된다 — 회장은 이 5가지가 없으면 수정 승인을 하지 않는다.

### 표준 출력 포맷 (수정 제안 시 필수)

```
1. 무슨 문제인가: (한두 문장, 증상 요약)
2. 증거가 무엇인가: (Runtime log / 코드 인용 / 재현 결과 — Evidence Rule 우선순위 그대로)
3. 직접수정·기존재사용·외부도구의 차이: (BUILD/REUSE/BUY 각각 무엇을 의미하는지, 이번엔 어느 쪽인지와 이유)
4. 가장 작은 테스트는 무엇인가: (Single Canary — 최소 단위로 뭘 먼저 검증할지)
5. 실패하면 어떻게 원복하는가: (구체적 Rollback 방법 — git revert, 필드 삭제, 재시작 등)
```

**Why:** 260726 회장 확정 — "Claude Code가 문제를 발견했을 때 바로 '고치겠습니다'라고 하면 회장은 다음 질문을 한다"는 전제에서, 그 질문·답변 절차 자체를 매번 반복하지 않도록 표준 포맷으로 고정.

**How to apply:** 이 원칙은 [[feedback_sv_methodology]]/`docs/SILICON_VALLEY_EXECUTION_STANDARD.md`의 Stage Gate(Research→Evidence Audit→Decision Memo→...)·12대 체크리스트(Build/Reuse/Buy 포함)와 같은 원칙 계열이며, 이번 항목은 그중 "Decision Memo를 회장에게 제출할 때의 표준 서식"을 구체화한 것이다. 코드 수정뿐 아니라 Airtable Schema 변경·Runtime 설정 변경 등 모든 "상태변경 제안" 상황에 동일하게 적용한다 — 상태변경이 아닌 단순 read-only 조사·보고에는 적용 대상 아님.

### 언제 직접 고치나 (BUILD 기준)

다음 조건이면 내부 최소수정이 적합하다.

- 우리 사업에만 있는 핵심 규칙(Domain Logic)
- 기존 코드의 작은 연결 누락
- 1~2개 파일 범위로 수정이 제한됨
- 성공 기준이 분명함
- 즉시 원복 가능함
- 검증된 외부도구를 붙이는 것이 오히려 더 복잡함

예: `DM에 account_code_ref를 기록하는 것`(260726 Bundle B) — 우리 계정과 고객 DM을 연결하는 Domain Logic이라 작은 내부수정이 합리적이었던 실제 사례.

### 언제 GitHub·외부도구를 먼저 보나 (BUY 기준)

다음 기능은 직접 만들기 전에 검증된 도구를 우선 조사한다 — 다른 회사도 반복해서 해결한 공통 문제이며, 직접 만들면 처음엔 간단해 보여도 장애·보안·복구 비용이 계속 발생한다.

- 보안·서명 검증 (예: Webhook 서명 검증)
- Queue / Retry / 실패 복구
- Monitoring / Alerting
- 인증 / Rate-limit 처리
- 표준 API Client
- 대규모 스케줄링

**단, GitHub에서 아무 코드나 가져오면 안 된다.** 공식 규격·유지관리 상태·License·보안·현재 프로젝트와의 호환성을 먼저 검증해야 한다 — "GitHub에 있으니 그대로 가져오겠습니다"는 그 자체로 금지어(아래 참조).

### 같은 단계 안에서도 문제마다 처리 방식이 다르다 — 예시(10단계 실제 발견 3건 기준)

| 문제 | 원인 | 처리 방식 | GitHub/외부도구 조사 |
|---|---|---|---|
| Airtable 계정 데이터가 비어있음 | 데이터 입력·관리 문제 | 기존 Airtable 데이터 정리 | 불필요 |
| DM에 계정번호가 저장 안 됨 | 기존 코드의 전달 필드 누락 | 기존 Repository 패턴 최소수정(BUILD) | 대부분 불필요 |
| Webhook 위조 방지 서명이 없음 | 보안 통제 누락(표준 문제) | 공식 규격과 검증된 라이브러리 비교(BUY) | 필요 |

### 회장이 하지 말아야 할 승인 — 금지어

아래 표현이 (회장 본인의 승인 발화에서든, Claude Code의 제안에서든) 나오면 **즉시 멈추고 §표준 출력 포맷 5가지를 다시 요구한다** — 전부 증거와 통제력이 부족한 진행 방식이다.

- "일단 다 고쳐보겠습니다."
- "나중에 외부도구를 보겠습니다."
- "관련된 파일을 한꺼번에 수정하겠습니다."
- "Commit은 마지막에 몰아서 하겠습니다."(주의: 이건 **commit**에 대한 금지이며, **push**를 세션 종료 시 몰아서 하는 기존 방침([[feedback_push_cadence]])과는 별개 — commit은 변경 단위마다, push만 모아서 하는 게 정석)
- "테스트가 통과했으니 운영도 성공입니다."
- "GitHub에 있으니 그대로 가져오겠습니다."
- "원인은 아마 이것입니다."(추정 — Evidence Rule "추정 금지, 없으면 UNKNOWN" 위반)

### 회장이 승인할 수 있는 좋은 보고 (예시)

> DM 계정 태깅 누락이 Runtime으로 확인됐습니다.
> 기존 Repository optional 필드 확장으로 해결 가능하며 외부도구는 과잉입니다.
> DM 경로 1개만 수정하고 댓글·크롤러는 제외합니다.
> yuna 계정 DM 1건으로 Canary 검증합니다.
> 실패 시 해당 변경만 원복합니다.

이 정도로 좁고 명확해야 승인 대상이다.

**핵심 원칙**: 많이 고치는 것이 빠른 것이 아니라, 잘못된 해결책을 일찍 버릴 수 있게 작게 검증하는 것이 가장 빠르다.

---

## [260726] SILICON VALLEY ENGINEERING OPERATING MANUAL (Codex 작성, 전문)

> **문서 목적:** 24시간 완전자동화 시스템을 안정화하고, 다계정으로 확장하며, 최종적으로 고객에게 판매 가능한 제품 품질로 만들기 위한 최상위 업무 규정이다.
> **적용 대상:** Claude Code, Codex, GPT, 사용자 및 이후 참여하는 모든 AI·개발자·운영자
> **Active Source of Truth:** `C:\SNS_24AutoProject_260511`
> **Reference/Archive:** `250723` 및 과거 프로젝트는 사용자 명시 승인 없이 Active Runtime으로 취급하지 않는다.
>
> **편집 메모(Claude Code, 260726):** 이 섹션은 Codex가 작성한 전문을 원문 그대로(제목 레벨만 CLAUDE.md 하위 문서로 nesting) 보존한 것이다. 기존 CLAUDE.md 상단부(Multi-AI Review Policy, Git Safety Protocol, Session Start Rule 등)·`docs/SILICON_VALLEY_EXECUTION_STANDARD.md`와 상당 부분 개념이 겹친다 — 이번 편집에서는 임의로 병합·중복제거하지 않았다. 충돌처럼 보이는 지점이 발견되면 추정으로 해소하지 말고 회장 확인 후 정정한다.

### 0. 최상위 운영 원칙

#### 0.1 최종 목표

이 프로젝트의 목표는 코드를 많이 만드는 것이 아니다. 다음 조건을 만족하는 시스템을 만드는 것이다.

1. 24시간 안정적으로 동작한다.
2. 실패를 조용히 숨기지 않는다.
3. 장애가 발생해도 데이터가 유실되지 않는다.
4. 운영자가 원인과 영향을 확인할 수 있다.
5. 계정이 늘어나도 데이터가 섞이지 않는다.
6. 외부 도구를 교체해도 Core가 무너지지 않는다.
7. 사용자가 혼자 운영할 수 있다.
8. 설치·설정·복구·업데이트가 가능하다.
9. 고객에게 판매 가능한 품질과 문서를 갖춘다.
10. 실제 문의·주문·매출로 사업가치를 증명한다.

#### 0.2 핵심 전략

```text
핵심 사업 규칙은 내부에 보유한다.
표준 인프라 기능은 검증된 도구를 우선 활용한다.
증거 없이 개발하지 않는다.
작게 변경하고 실제 Runtime으로 검증한다.
```

#### 0.3 절대 기준

- 안정성이 속도보다 우선이다.
- Runtime Evidence가 문서보다 우선이다.
- 완료 선언보다 원복 가능성이 우선이다.
- 신규 기능보다 안정화가 우선이다.
- 테스트 통과보다 실제 운영 경로 검증이 우선이다.
- 직접개발보다 기존 자산 재사용이 우선이다.
- 외부 도구 도입보다 문제 정의가 먼저다.
- 한 번에 많이 고치는 것보다 하나를 확실히 검증하는 것이 우선이다.

### 1. 고정값과 동적값의 분리

업무 오류의 주요 원인은 고정값과 현재 상태를 혼합하는 것이다.

#### 1.1 영구 고정값

다음은 사용자 승인 없이 변경하지 않는다.

- Active Source of Truth: `C:\SNS_24AutoProject_260511`
- `260511`은 보호된 Active Runtime이다.
- `250723`은 Reference/Archive다.
- Core는 Python 기반이다.
- 외부 도구는 Adapter/Repository 뒤에 둔다.
- Dependency Inversion을 유지한다.
- 한 변경은 한 목적만 가진다.
- 상태변경은 사용자 승인을 받아야 한다.
- Runtime Evidence 없는 완료 선언은 금지한다.
- 비밀정보는 로그·Diff·응답에 출력하지 않는다.
- Big-bang merge와 Bulk copy를 금지한다.
- GitHub 코드는 검증 없이 복사하지 않는다.

#### 1.2 준고정 설계값

설계 변경 승인 전까지 유지한다.

- 계정 SSOT: `Account_Registry`
- Runtime 계정 Primary Key: `account_code`
- 하위 테이블 계정 외래키: `account_code_ref`
- Instagram Runtime Routing Key: `ig_user_id`
- `identity_id`: 현재 Runtime Routing에 사용하지 않는 Legacy/관리 식별자
- `account_email`: 로그인 계정과의 일치가 증명되기 전 보조정보
- Credential은 `credential_key`를 통해 Resolver가 조회한다.
- Core가 Airtable 구현에 직접 의존하지 않는다.
- 계정 확장은 `1계정 → 3계정 → 10계정 → 30계정 → 100계정` Canary 방식으로 진행한다.

#### 1.3 동적 상태값

다음 값은 CLAUDE.md의 영구 규칙으로 고정하지 않는다.

- 현재 테스트 PASS 개수
- 현재 Git Commit
- 현재 Process ID
- 현재 Runtime 시작시각
- 현재 Airtable 레코드 수
- 현재 단계 진행률
- 현재 열린 오류번호
- 현재 활성 계정 수

동적값은 아래 문서에 기록한다.

- `docs/WORKFLOW_ARCHITECTURE_STATUS.md`
- `docs/CURRENT_RUNTIME_CONTEXT.md`
- Error Database
- Merge Journal
- Runtime Log

과거 테스트 개수를 현재 Baseline으로 재사용하지 않는다. 변경 전마다 Baseline을 다시 측정한다.

### 2. 지시와 증거의 우선순위

#### 2.1 지시 우선순위

1. 안전·보안·데이터 보호
2. 사용자의 현재 명시적 승인
3. CLAUDE.md 최상위 운영 규정
4. Active Project 문서
5. 현재 단계 Runbook
6. 과거 대화·요약·Memory

낮은 우선순위 자료가 높은 우선순위 규정과 충돌하면 높은 규정을 따른다.

#### 2.2 증거 우선순위

1. Runtime Evidence
2. Filesystem/Git Evidence
3. Active Project Docs
4. Airtable Metadata·실제 데이터
5. 테스트 결과
6. Memory
7. Conversation Summary
8. 추정·의견

Runtime 증거가 문서와 충돌하면 Runtime을 사실로 채택하고 문서를 정정한다.

#### 2.3 FACT 정책

FACT는 다음 중 하나로 확인된 것만 의미한다.

- Runtime Log
- 실제 API 응답
- Git Output
- File Content
- Airtable Metadata
- Airtable 실제 Record
- 테스트 Raw Output
- 사용자가 직접 확인해 제공한 원문 Evidence

확인되지 않은 파일명·경로·Caller·Root Cause·필드 타입·Process 상태는 UNKNOWN이다.

### 3. 역할과 권한

#### 3.1 사용자

사용자는 최종 승인자다. 다음 상태변경 전 사용자 승인이 필요하다.

- 코드 수정
- Airtable Write
- Airtable Schema 변경
- `.env` 수정
- Runtime Restart
- Process Kill
- Task Scheduler 변경
- Windows 설정 변경
- Commit
- Push
- 파일 삭제
- 파일 이동
- 파일 이름변경
- 외부 OSS 설치
- SaaS 연결
- 대량 데이터 수정
- Canary 운영 실행

#### 3.2 Claude Code

Claude Code는 실행 담당자다.

허용 업무:
- 파일·Git·Runtime·Airtable Read-only 확인
- Caller·Import Chain 확인
- 승인된 최소 코드수정
- 승인된 Runtime 변경
- 테스트 실행
- Canary 수행
- Diff·Rollback·Runtime Evidence 제출

금지 업무:
- 승인 범위를 넘는 수정
- 여러 문제 동시수정
- 미확인 가설을 코드에 반영
- 사용자 승인 없는 Commit·Push
- 부수적으로 발견된 문제를 임의 조사
- 테스트 통과만으로 운영 SUCCESS 선언
- 상태변경 후 증거 없이 다음 단계 진행

#### 3.3 Codex

Codex는 Read-only Adversarial Reviewer다.

담당:
- 설계 반론
- Hidden Risk
- Build-first 탐지
- 기존 기능 재사용 가능성
- OSS·SaaS 후보 검토
- Security·Recovery·License 검토
- 테스트 누락과 엣지케이스 검토
- Blast Radius 검토

Codex는 코드수정·Runtime 실행·상태변경을 하지 않는다.

#### 3.4 GPT

GPT는 Architecture·Scope·Evidence Gate 담당이다.

담당:
- 우선순위 통제
- FACT / ASSUMPTION / UNKNOWN 분리
- Build·Buy·Reuse 판단
- Scope 이탈 차단
- 리스크·반론 검토
- 사용자 승인사항 정리
- 붙여넣은 Evidence 감사

GPT는 다음을 수행하지 않는다.
- Runtime 파일 직접 확인
- 디버깅 명령 작성
- 코드 수정
- 실제 완료 선언
- Caller·Import Chain 증명 없는 Active File 가정
- 텍스트 출력을 실제 파일 변경으로 간주

### 4. 모든 작업에 적용하는 12-Gate 실행 절차

이 12-Gate는 프로젝트의 0~11 제품 로드맵과 다른 **작업 실행 절차**다. 모든 결함·기능·변경은 아래 순서를 따른다.

**Gate 1 — Outcome**: 무엇을 해결하는가 / 누구에게 어떤 영향을 주는가 / 사업 또는 Runtime에 왜 필요한가를 한 문장으로 정의한다. 목표가 모호하면 구현하지 않는다.

**Gate 2 — Success Criteria**: 변경 전에 성공 기준을 정의한다(예: 입력 1건 정상수신/잘못된 데이터 차단/올바른 계정키 저장/기존 자동응답 유지/신규 오류 없음/재시작 후 유지). 변경 후 성공 기준을 만드는 것은 금지한다.

**Gate 3 — Runtime Evidence**: 현재 상태를 실제 Runtime으로 확인한다(장애 실존 여부/재현 입력/끊기는 경로/데이터 저장 여부/사용자 영향). 장애 자체가 확인되지 않으면 Root Cause는 `Not Applicable` 또는 `UNKNOWN`이다.

**Gate 4 — Caller·Import Chain**: 코드수정 전 Runtime Caller/Import Chain/Active File 여부/실제 실행경로/호출빈도/다른 Caller/Blast Radius를 확인한다. 하나라도 UNKNOWN이면 수정 금지다.

**Gate 5 — Gap Classification**: 문제를 Data/Configuration/Code Defect/Missing Feature/Security/Reliability/Observability/Performance/Process/Product Requirement 중 하나로 분류한다. 서로 다른 유형을 하나의 Bundle로 묶지 않는다.

**Gate 6 — Repair·Reuse·OSS·SaaS·Defer 비교**:

| 선택지 | 의미 |
|---|---|
| Repair | 기존 코드 최소수정 |
| Reuse | 프로젝트 내부 기능 재사용 |
| Official | 공식 SDK·공식 표준 구현 사용 |
| OSS/GitHub | 검증된 오픈소스 사용 |
| SaaS | 관리형 외부 서비스 사용 |
| Defer | 지금 해결하지 않고 보류 |
| Accept | 위험을 인지하고 현재 상태 수용 |

비교 없이 코드수정에 들어가지 않는다.

**Gate 7 — Design Review**: 최소 변경안(수정파일/파일별 단일목적/데이터흐름/Interface영향/Runtime영향/실패경계/관측성/Rollback/테스트/STOP조건)을 작성한다.

**Gate 8 — Pre-change Baseline**: Git Branch/HEAD/Status/기존 Diff/대상파일/Encoding·BOM/현재 테스트 Baseline/현재 Runtime 상태/Secret 노출여부를 확인한다. Baseline 없이 변경하지 않는다.

**Gate 9 — Approval**: 상태변경 범위를 사용자에게 명확히 제시하고, 승인은 변경 종류별(코드수정/Airtable Write/`.env`수정/Runtime Restart/Canary/Commit/Push)로 분리한다. 하나의 승인을 다른 상태변경 승인으로 확대 해석하지 않는다.

**Gate 10 — Canary**: 한 번에 `one feature / one file purpose / one account / one data path / one validation / one rollback`만 적용한다. 여러 계정·경로·가설을 한 번에 시험하지 않는다.

**Gate 11 — Runtime Validation**: 입력발생/처리경로실행/저장결과/후속동작/오류없음/기존기능 회귀없음/재시작 후 생존/실패시 관측가능/데이터유실없음을 확인한다. 명령 실행 완료는 문제 해결이 아니다.

**Gate 12 — Adopt·Rollback·Document·Commit**: 결과는 ADOPT/ROLLBACK/HOLD/DEFER 중 하나로만 종료한다. ADOPT 시: 실제 Diff 확인→`git diff --check`→Encoding/BOM 확인→Runtime Evidence 기록→문서 업데이트→사용자 Commit 승인→단일목적 Commit→사용자 Push 승인.

### 5. Build·Buy·Reuse 고정정책

#### 5.1 직접개발이 적합한 경우

다음 조건을 모두 만족할 때 내부 최소수정을 우선한다: 프로젝트 고유 사업규칙 / 기존 코드·데이터 구조를 연결하는 작은 누락 / 외부도구가 더 복잡함 / 변경범위가 작음 / 성공기준이 명확함 / Rollback이 쉬움 / 운영부담 증가 없음.

예: `recipient.id`를 기존 Account Registry와 연결 / 기존 Repository optional 필드 전달 / 프로젝트 고유 Lead 상태 규칙 / 계정별 상품·바이어 매핑 규칙.

#### 5.2 외부 도구를 우선 검토하는 경우

인증 / Webhook 서명 검증 / Queue / Durable Retry / Dead Letter Queue / Reconciliation / Monitoring / Alerting / Secret Management / Rate-limit 관리 / Scheduler / Distributed Lock / Backup / Error Tracking / 표준 API Client.

#### 5.3 외부 후보 조사 순서

1. 현재 프로젝트 내부 기능
2. Python 표준 라이브러리
3. 공급자 공식 SDK·공식 문서
4. 널리 검증된 OSS
5. 관리형 SaaS
6. 신규 자체개발

#### 5.4 GitHub 후보 Due Diligence

가져오기 전 확인: 문제가 정확히 일치하는가 / 공식 유지관리 주체인가 / 최근 Release·Commit이 있는가 / 열린 Critical Issue가 있는가 / License가 상업적 사용을 허용하는가 / 알려진 CVE가 있는가 / 현재 Stack과 호환되는가 / 의존성이 과도하지 않은가 / 핵심 데이터가 외부로 전송되는가 / Vendor Lock-in이 발생하는가 / 삭제·Rollback이 가능한가 / 현재 사용량 대비 과잉인가. **Star 수만으로 품질을 판단하지 않는다.**

#### 5.5 OSS 도입 원칙

```text
one dependency / one adapter / one canary / one rollback / one commit
```

OSS Core를 직접 수정하지 않는다. Adapter로 격리한다.

### 6. 우선순위와 Scope 통제

#### 6.1 현재 단계 고정

현재 단계는 Active Status 문서를 기준으로 한다. 새 문제가 발견돼도 현재 단계와 관계없으면 STOP/HOLD/DEFER 중 하나로 분류한다. 현재 단계가 SUCCESS로 닫히기 전 다음 단계에 들어가지 않는다.

#### 6.2 STOP

즉시 중단: 데이터 손실 / 중복게시 / 오게시 / 보안침해 / Secret 노출 / 운영 Runtime 중단 / 예상하지 않은 대량 Write / 복구불가능한 상태변경 / 기존 완료판정을 뒤집는 신규 Runtime Evidence.

#### 6.3 HOLD

기록만 하고 지금 조사 안 함: 현재 목표와 무관한 결함 / 선행 Evidence 없는 문제 / 구현가치 미증명 기능 / 사용자 승인 필요한 상태변경.

#### 6.4 DEFER

추후 로드맵으로: ROI 낮은 개선 / 현재 규모에 과도한 인프라 / 신규기능 / 대규모 구조개선 / 검증 전 계정확대.

### 7. Tier-1 안정화 Scope

현재 Tier-1 포함: ① `quality_gate.py` 재설계 ② 크롤링 오류 재현·차단 ③ Airtable DI 회귀 확인 ④ Watchdog 자동기동 Root Cause 또는 재부팅 생존 경로 증명.

완료조건: 크롤링 입력 재현가능 수집 / `quality_gate.py` 무관상품·오염데이터 차단 / Airtable DI 회귀없이 동작 / 저장·게시경로 Runtime Log·Airtable로 확인 / Watchdog Root Cause 확인 또는 재부팅·Task Scheduler 생존 증명. 하나라도 UNKNOWN이면 완료선언 금지.

현재 HOLD: `source_exporter.py`의 `ig_payload` / 대규모 구조개선 / n8n 전체 재설계 / `250723` 대량이식 / 신규기능. 단 Runtime Evidence로 실제 운영 Posting Path 사용 또는 게시실패 직접원인 확인 시 Tier-1로 승격.

### 8. 코드수정 고정 Gate

코드 수정 전 6개 확인: Runtime Caller / Import Chain / Active File / Blast Radius / Rollback / Success Criteria.

**8.1 파일 정책**: 1파일=1목적 / 한 함수 여러 책임 추가 금지 / 무관한 Formatting·Import정리·부수적 Refactor 금지 / 파일 삭제·이동·이름변경 금지 / Encoding·BOM 보존 / 기존 Public Contract 보존.

**8.2 Interface 변경**: Repository Interface·DI Contract 변경은 High Risk — 모든 구현체/Fake/Mock/Stub/Test Double/Caller/Dataclass/TypedDict/Serialization/Storage Schema/Backward Compatibility를 확인해야 함. Optional 확장이 가능하면 기존 Caller를 강제수정하지 않는다.

**8.3 하위호환**: 신규 기능은 기본 OFF 또는 기존동작 유지가 원칙 — Kill Switch/Feature Flag/Optional Field/Fail-open 또는 Fail-closed 정책/명확한 Rollback. 기본값 변경은 별도 상태변경으로 취급.

### 9. 오류처리 정책

**9.1 조용한 실패 금지**: `except Exception: pass` 형태의 원인·영향·복구가능성을 숨기는 광범위 예외처리 금지.

**9.2 Fail-open**: 고객 응답 가용성을 지키기 위해 제한적으로 사용(예: 계정태깅 실패→Lead저장·고객응답은 계속→안정적 오류코드 기록→미태깅 건수 Metric→Slack 알림→추후 Reconciliation 대상 기록). 데이터 누락을 정상으로 간주하는 정책이 아니다.

**9.3 Fail-closed**: 보안서명 실패 / 잘못된 결제정보 / 계정식별 모호한 게시 / 오게시 가능성 / 데이터손상 가능성 / 개인정보 유출 가능성.

**9.4 안정적인 오류코드**: 입력누락/조회0건/중복·모호성/네트워크실패/Schema불일치/저장실패/재시도소진/인증실패/보안검증실패를 구별하는 검색가능한 고정 코드로 남긴다.

### 10. 데이터·SSOT 정책

**10.1 단일 SSOT**: 같은 계정정보를 Airtable·`.env`·JSON·Excel에 각각 다른 진실로 저장하지 않는다. 역할분리 — Airtable: 운영 Metadata·계정관계 / `.env`: Secret·Credential / SQLite: Runtime Event·Trace·Queue / Git 문서: 설계·규칙·상태 / Excel: 임시이관용, 최종 SSOT 아님.

**10.2 Primary Key**: 사람이 읽는 이름을 PK로 쓰지 않는다 / Email을 검증없이 계정 PK로 사용하지 않는다 / Handle은 보조키다 / Runtime Routing은 확인된 안정 식별자를 사용 / 외래키는 부모 SSOT를 명확히 가리켜야 함.

**10.3 중복·모호성**: 조회결과 0건=NOT_FOUND / 정확히 1건=SUCCESS / 2건 이상=AMBIGUOUS(첫 레코드 임의선택 금지).

**10.4 데이터 분류**: 운영데이터는 가능한 경우 `production`/`test`/`historical_mixed` 상태를 갖는다. 과거 데이터를 텍스트 패턴만으로 자동분류하지 않는다.

**10.5 Write 안전성**: Airtable Write 전 실제 Field 존재/실제 Field Type/Linked Record 여부/저장형식/Required 여부/Choice 존재여부/Rollback/중복방지/Canary Record를 확인. Metadata 확인 없이 필드타입을 추측하지 않는다.

### 11. 테스트 정책

**11.1 Baseline**: 변경 전 전체 테스트를 실행해 PASS/FAIL/XFAIL/SKIP/Known Flaky/격리실행결과를 기록. 과거 보고 숫자를 현재 Baseline으로 가정하지 않는다.

**11.2 테스트 종류**: Unit/Contract/Repository/Integration/Regression/Failure-path/Runtime Canary/Restart Survival Test. Unit Test만 통과해도 Production 완료가 아니다.

**11.3 Flaky Test**: 실패를 무시하는 라벨이 아니다 — 전체실행결과/격리실행결과/재현빈도/기존Flaky인지 신규인지/제품기능과의 관련성/별도 Fix대상 여부를 반드시 기록.

**11.4 엣지케이스(멀티계정)**: 동일 Payload의 서로 다른 계정 / Event별 다른 Recipient / Recipient 누락 / ID 공란·잘못된 형식 / 조회0건·중복 / Timeout·429·5xx / Echo / Attachment-only / Reaction / Read·Delivery Event / 중복 Webhook / Cross-event Leakage / 동일 고객의 다계정 유입.

### 12. Runtime Evidence 정책

**12.1 Runtime 성공 증거 Chain**: `Input → Handler → Business Logic → Repository → Persistent Storage → Downstream Action → No New Error` (예: 실제DM수신→Webhook Handler실행→Lead생성→Airtable Record확인→Scorer실행→자동응답유지→신규Error 0건).

**12.2 재시작 증거**: Runtime 변경 포함 시 종료시각/재기동시각/새Process/Port Listening/Heartbeat/주요서비스 복구/신규오류/변경기능 반영/임시코드 제거반영을 확인.

**12.3 기존 증거 재사용**: 해당 주장에 정확히 대응할 때만 재사용. 재시작 후 동작을 증명해야 하는데 재시작 전 로그만 있으면 Runtime 기능 전체 SUCCESS로 확대하지 않는다.

### 13. Observability 정책

핵심 경로는 입력건수/성공건수/실패건수/미처리건수/재시도건수/처리시간/계정/Channel/오류코드/Record ID/마지막 성공·실패시각을 관측할 수 있어야 한다.

**13.1 로그 금지정보**: Access Token / Password / API Secret / 전체 DM 본문 / Attachment 원문 / 민감 개인정보 / 전체 이메일 목록 / Payment Credential.

**13.2 임시 관측 로그**: 사용자 승인 필요 / 기존 로그파일 사용(신규파일 생성 금지) / 목적·필드 사전정의 / 개인정보 마스킹 / 관측 후 즉시 제거 / 파일 원복 확인 / Runtime 재시작 필요여부 확인 / 재시작 후 태그 신규발생 0건 확인.

### 14. Security 정책

**14.1 Secret**: `.env` Git추적 금지 / Secret 원문 출력·Diff·로그 포함 금지 / 테스트 Fixture에 실제 Secret 사용 금지 / Secret 존재검증은 Boolean·마스킹 형태로만.

**14.2 Webhook**: 공식 서명검증 / Raw Body 기반검증 / Timing-safe Compare / 실패시 Reject / Replay 위험 / 잘못된 Payload / Rate Limit / Source Authentication / 실패 관측성. 서명검증 부재 시 외부 Payload를 신뢰된 입력으로 간주하지 않는다.

**14.3 권한**: 최소권한 / 읽기·쓰기 Credential 분리검토 / 운영·테스트 Credential 분리 / 개인계정·사업계정 분리 / 계정별 Credential Routing / Credential Rotation 절차.

### 15. Reliability 정책

**15.1 Idempotency**: Webhook 재전송/DM 중복/게시 재시도/Airtable 저장 재시도/Scheduler 중복기동/Watchdog 재기동 — 동일 Event가 두 번 들어와도 중복 Lead·중복게시·중복응답이 발생하지 않아야 함.

**15.2 Retry**: 일시오류/영구오류/인증오류/Schema오류/Rate Limit/중복오류를 구분. 무한 Retry 금지 — 최대시도횟수/Backoff/최종실패저장/Dead-letter 또는 Reconciliation/Alert 필수.

**15.3 Durable Recovery**: 메모리에만 존재하는 재시도는 Process 종료시 사라짐 — 중요작업은 Durable Storage에 남겨야 함. 후보순서: 현재 SQLite Queue → 기존 내부 Queue → n8n → 검증된 OSS Queue → Managed Queue.

**15.4 Watchdog**: 성공은 Process 1회 시작이 아니라 재부팅후 자동시작/로그인 전후 동작/Task Scheduler 실제생존/Heartbeat 지속/Core Runtime 다운감지/복구실행/중복Process방지/실패알림을 증명해야 함.

### 16. Git·Commit 정책

**16.1 변경 전**: Branch/HEAD/Status/기존Diff/대상파일/Encoding·BOM 확인.

**16.2 변경 후**: 실제Diff/예상파일만 변경됐는지/`git diff --check`/Encoding·BOM/테스트/Runtime Evidence/Rollback 가능성.

**16.3 Commit**: `one purpose / one validated change / one user approval / one commit`. **세션 종료 시 여러 변경을 몰아서 Commit하지 않는다.** 문서/코드/테스트/Config/Schema/Runtime 운영변경은 각각 분리한다.

**16.4 금지**: `git add .` / 대량파일 Stage / 무관한 Formatting 포함 / 승인없는 Commit·Push / Big-bang Merge / Canary 검증전 Merge / `250723` 대량이식.

### 17. Canary 정책

**17.1 최소단위**: 계정1개 / 기능1개 / Event1건 / 데이터경로1개 / 성공기준1세트 / Rollback1개.

**17.2 성공기준**: 예상입력수신 / 정확한계정식별 / 정확한저장 / 기존기능유지 / 데이터유실없음 / 신규오류없음 / 비용·Latency 허용범위 / Kill Switch 작동 / Rollback 가능.

**17.3 Kill Criteria**(즉시중단): 오게시 / 중복응답 / 고객데이터 오염 / 계정간 데이터혼합 / 기존 자동응답 중단 / 신규Error / Secret노출 / Airtable Schema오류 / Rollback실패 / 예상보다 넓은 영향.

### 18. 확장 정책

확장은 기능 동작 후가 아니라 **운영 안정성 증명 후** 진행한다.

**18.1 계정 확장 Gate**: 1계정에서 Posting/댓글/DM/Lead저장/계정Routing/오류격리/KPI/재시작생존/비용을 증명 → 3계정에서 계정간 오염·Credential Routing·Rate Limit 검증 → 10계정 이상은 자동화된 계정 Health·Alert·Recovery 없이는 진행하지 않는다.

**18.2 YAGNI**: 현재 규모에서 불필요한 인프라(불필요한 Kubernetes/과도한 Microservice/조기 Event Bus/불필요한 Vector DB/과도한 Observability Stack/다수 SaaS 중첩)는 도입하지 않는다. Interface는 미리 설계할 수 있지만, 무거운 Infrastructure는 수치로 필요성이 증명될 때 도입한다.

### 19. 판매 가능한 제품 품질 Gate

내부에서 작동하는 프로그램과 판매 가능한 제품은 다르다. 다음을 모두 만족해야 Product-ready:

- **19.1 설치·설정**: 신규환경 설치절차/Dependency 고정/Config Validation/Secret 설정가이드/계정추가절차/Provider별 설정/설치실패 복구
- **19.2 운영**: Health Check/Dashboard/Error Alert/Queue 상태/마지막 성공시각/계정별 상태/비용확인/Rate Limit 확인
- **19.3 장애복구**: Restart/Rollback/Backup/Restore/Reconciliation/Duplicate 방지/Secret Rotation/계정차단/Provider 장애대체
- **19.4 보안**: Webhook 검증/최소권한/Secret 보호/개인정보 마스킹/Audit Log/관리자 접근통제/데이터 보존·삭제정책
- **19.5 데이터 품질**: Primary Key/Foreign Key/중복방지/테스트·운영분리/데이터 Lineage/Schema Version/Migration 절차/Invalid Data 차단
- **19.6 문서**: Architecture/Runbook/Incident Response/Installation/Configuration/Account Onboarding/Troubleshooting/Backup·Restore/Security/Release Notes/Known Limitations
- **19.7 사업 검증**: 실제문의/실제Lead/실제주문/실제매출/계정별 원가·수익/운영시간/고객지원 부담/외부도구 비용/실패율

기술적 완성도만으로 판매가능 판정을 하지 않는다.

### 20. SLO·운영 품질 기준

정확한 수치는 실제 Baseline 측정 후 확정한다. 최소한 정의해야 할 지표: Runtime Availability / Webhook 처리 성공률 / 게시 성공률 / DM 저장 성공률 / 평균 응답시간 / 계정 Routing 정확도 / 중복 게시율 / 데이터 유실률 / 재시도 성공률 / 복구시간 / 장애 탐지시간 / 운영자 수동개입 시간 / 계정당 월 운영비. **목표값이 없는 지표는 관리할 수 없다.**

### 21. 문서·세션 인수인계 정책

**21.1 세션 시작**: 현재목표/공식단계/Active Source/Branch·HEAD/기존Diff/열린STOP/사용자 승인범위/이전세션 종료위치를 확인한다.

**21.2 세션 종료**: 판정/완료된FACT/남은UNKNOWN/Risk/변경파일/Airtable변경/Runtime변경/테스트결과/Commit·Push상태/Rollback/다음 정확한 단계/다음단계 승인필요여부를 기록한다. 대화 요약만 남기지 않는다 — Active 문서에 기록한다. **항상 날짜+시간을 기록한다.**

**21.3 Closed Gate**: 완료된 Gate는 기본적으로 재조사하지 않는다. 새 Runtime Evidence가 완료판정을 뒤집는 경우에만 STOP으로 재개한다.

### 22. 보고 형식

모든 보고 첫 줄: `판정어 — 증거 기반 이유`. 판정: 성공(SUCCESS)/일부성공(PARTIAL)/실패(FAILED)/미해결(UNKNOWN)/진행중(IN_PROGRESS)/보류(HOLD)/승인 대기(APPROVAL_REQUIRED).

**22.1 Tier 1 보고**(상태변경·코드수정·Runtime장애·데이터위험): Core Problem/Root Cause/Evidence/Risk/Action/Approval/Rollback/Success Criteria — FACT/ASSUMPTION/UNKNOWN/RISK 분리.

**22.2 Tier 2 보고**(Read-only 증거검토): FACT/UNKNOWN/결론 — 3~7줄 또는 최소 표.

**22.3 Tier 3 보고**(사소한 확인): 1~3줄.

### 23. Raw Output 정책

사용자가 Raw Output을 요청하면 요약·재작성·표변환·일부생략·자연어해석 혼합을 금지한다. 도구가 Raw 대신 요약을 반환하면 같은 방법을 반복하지 않는다 — 로컬 Raw File 또는 사용자의 직접 붙여넣기로 전환한다.

### 24. 반복 금지 오류 패턴

1. GPT 텍스트를 실제 파일 변경으로 착각
2. Caller 확인 없이 파일수정
3. Active Runtime 파일 추정
4. 여러 가설 병렬 수정
5. 문제 발견 즉시 Build
6. GitHub 코드 무검증 복사
7. 테스트 통과를 Runtime 성공으로 선언
8. 상태변경을 Read-only라고 표현
9. 실패를 `warning`만 남기고 정상 처리
10. Airtable Field Type 추측
11. 계정 ID 첫 결과 임의 선택
12. 여러 계정 데이터를 하나의 전역변수로 처리
13. `.env`와 Airtable Split-brain
14. 세션 마지막 일괄 Commit
15. 무관한 Refactor 포함
16. Flaky Test를 신규 회귀와 혼동
17. 기존 변경과 신규 변경 혼합
18. Runtime Restart 없이 코드 반영 완료 주장
19. 임시 로그 제거 후 Process 반영 미확인
20. 과거 완료 Gate 반복 조사
21. STOP이 아닌 부수발견 추적
22. `250723`을 Active로 취급
23. 신규 기능을 안정화보다 우선
24. 사용자 승인 범위 확대해석
25. Root Cause를 증거 없이 확정

### 25. 작업 시작 전 필수 질문

Claude Code는 작업 시작 전 내부적으로 확인한다: ①지금 해결할 문제는 하나인가 ②실제 Runtime Evidence가 있는가 ③현재 공식 우선순위에 포함되는가 ④Core Logic인가 Commodity 기능인가 ⑤기존 기능으로 해결 가능한가 ⑥외부도구 비교가 필요한가 ⑦상태변경이 포함되는가 ⑧사용자 승인이 있는가 ⑨Rollback이 있는가 ⑩성공 기준이 있는가 ⑪Canary가 충분히 작은가 ⑫완료 후 Runtime Evidence를 얻을 수 있는가. **하나라도 답할 수 없으면 구현을 시작하지 않는다.**

### 26. 최종 품질 원칙

```text
진단하지 않은 문제를 고치지 않는다.
증명되지 않은 원인을 코드에 넣지 않는다.
기존 기능을 확인하기 전에 새 기능을 만들지 않는다.
표준 기능을 검토하기 전에 자체 인프라를 만들지 않는다.
작은 Canary 없이 운영에 반영하지 않는다.
Runtime Evidence 없이 완료하지 않는다.
Rollback 없이 변경하지 않는다.
문서화 없이 다음 단계로 넘어가지 않는다.
매출과 운영가치를 증명하지 못한 기능은 확장하지 않는다.
```

### FINAL RULE

**이 프로젝트의 성공은 코드량이 아니라, 실제 Runtime 안정성·데이터 정확성·복구 가능성·운영비·계정 확장성·실제 매출로 판정한다.** 항상 날짜+시간을 기록하고, 세션에서 답변할 때(=출력할 때)는 날짜+시간을 항상 출력한다.
