# FP-047 댓글 이벤트 Idempotency 설계 (RFC) — 260715 v4

**상태:** `Implementation Complete — disabled default, shadow/enforce validation pending`. GPT/Codex 총 12라운드 교차검토(설계 8라운드 + 구현 후 코드 리뷰 4라운드) 거쳐 코드 sign-off 완료(260715). 구현은 `COMMENT_EVENT_STORE_MODE=disabled`(기본값)로 커밋되며, 기존 운영 동작은 전혀 바뀌지 않는다. **shadow/enforce 전환 및 실계정 Runtime Proof는 이 커밋과 별도로 승인 대상.** enforce 진입 전 반드시 해결해야 할 잔여 OPEN 항목: (1) 댓글 원문 평문 저장(Telegram/로그/retry payload, ERR-066과 같은 클래스) (2) Airtable `source_event_id` 필드 존재 여부 startup preflight 미구현. 마이그레이션 CLI 도구·comment_event_migrations 테이블·완전한 dead-alert 원자적 상태머신도 아직 미구현(fast-follow).

## 배경

`comment_poller.py`/`comment_auto_reply.py`의 댓글 리드 영구유실(FP-047, ERR-062/INC-035 실손실 2건)을 고치는 설계. v1(단순 캐시순서 변경) → v2(이중진입/effect분리 도입, 그러나 health_monitor 주기 존재를 잘못 가정) → v3(런타임 검증 후 신규 monitor 잡·eager 등록·3-way 조회 도입) → **v4(동시성 정합성 마감: fencing token, stale-STARTED 처리, shadow cutover, dead-alert 자체의 원자성, 스키마 정합)**.

## Goals

1. 댓글 리드가 Airtable 기록에 실패해도 재시도되어 최종적으로는 저장되게 한다.
2. 재시도 과정에서 손님에게 Private Reply/Telegram 알림이 중복 발송되지 않게 한다.
3. 웹훅(`dm_receiver.py`)과 폴러(`comment_poller.py`)가 같은 댓글을 동시에 처리해도 이중 처리가 안 되게 한다.
4. **(v4 정정)** 처리 도중 프로세스가 죽어도 **내부 상태(Airtable 기록)는 유실 없이 정확히 재개된다.** 단, **외부 발송(Private Reply/Telegram)의 성공 여부가 모호한 경우는 자동으로 재개하지 않고 `UNKNOWN`으로 격리해 손님에게 중복발송(스팸)이 가지 않게 한다** — 외부 API의 모호한 성공 자체를 우리 시스템이 사후에 완전히 판별할 수는 없다는 한계를 인정한다(v3까지의 "유실도 중복도 없이 정확히 재개"는 과대약속이었음).
5. Airtable 응답이 유실된 모호한 실패에서도 중복 레코드를 만들지 않는다.
6. 재시도 태스크가 dead 상태에 도달하면 아무도 모른 채 방치되지 않고 능동적으로(최소 1회, 중복 최소화 기준) 알림이 간다.

## Non-Goals

- DM 채널 idempotency, `retry_queue.py` 내부 스키마 변경, 기존 `ig_auto_reply`/`ig_followup`의 지연등록 패턴 리팩터(범위 밖으로 재확인, 기록만), 상세 대시보드/장기 SLA, `processed_comment_ids.json` 완전 제거, DM 채널 확장, 운영자 수동 재처리 UI, Gate G 안전장치 로직 변경.

## 런타임 제약 재확인 (260715, 직접 코드 검증)

- `get_health()` 1회성 확인(`launcher/main.py:378`), 주기 잡 없음.
- retry handler 지연등록(`dm_auto_reply.py:312`, `dm_followup_scheduler.py:204`)이 `rq.start()`(`launcher/main.py:362-363`)보다 늦게 실행됨 — 신규 핸들러는 eager 등록 필수.
- `.gitignore:10`에 `*.db` 이미 있음 — 신규 db 파일 자동 제외.
- **(v4 신규 확인)** `max_instances=1, coalesce=True`는 이미 `_job_dome_export`(`launcher/main.py:340-342`)에서 실사용 중인 검증된 패턴 — 신규 `comment_retry_dead_monitor` 잡에도 그대로 적용 가능.
- **(v4 배경)** 이 프로젝트는 "같은 스크립트/잡의 이중 실행"으로 이미 한 번 사고를 겪은 전례가 있음(ERR-057, NSSM 서비스와 구 Task Scheduler가 watchdog.ps1을 동시 이중 실행) — dead monitor 자체의 경쟁조건(v4 결함4)은 이 전례와 같은 클래스.

## 설계

### 1. 신규 모듈: `modules/comment/comment_event_store.py`

별도 SQLite(`db/comment_events.db`).

**스키마 (v4 — fencing token, manual_review, first_seen_mode 추가):**
```sql
CREATE TABLE comment_events (
    source                TEXT NOT NULL,        -- 'instagram_comment' 고정
    source_event_id       TEXT NOT NULL,        -- Meta comment_id
    status                TEXT NOT NULL DEFAULT 'RECEIVED',  -- RECEIVED|PROCESSING|COMPLETED|DEAD
    claim_token           TEXT NOT NULL,         -- v4: fencing token(UUID), claim/reclaim마다 신규 발급
    claimed_by            TEXT,                  -- 'webhook' | 'poller' (진단용)
    claimed_at            TEXT NOT NULL,
    lease_expires_at      TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    private_reply_status  TEXT NOT NULL DEFAULT 'NOT_APPLICABLE',  -- NOT_APPLICABLE|STARTED|DONE|UNKNOWN
    telegram_status       TEXT NOT NULL DEFAULT 'NOT_APPLICABLE',  -- NOT_APPLICABLE|STARTED|DONE|UNKNOWN
    airtable_status       TEXT NOT NULL DEFAULT 'PENDING',   -- PENDING|DONE|RETRY_PENDING|RETRY_ENQUEUE_FAILED
    manual_review_required INTEGER NOT NULL DEFAULT 0,  -- v4: UNKNOWN effect 발생 시 1
    retry_task_id         INTEGER,
    last_error            TEXT,
    migration_tag         TEXT,                  -- NULL|LEGACY_SUPPRESSED|PRE_ENFORCE_SUPPRESSED
    first_seen_mode       TEXT,                  -- v4: 'shadow'|'enforce' (진단/감사용, 영구 보존, migration_tag와 별개)
    deployment_epoch      TEXT,
    PRIMARY KEY (source, source_event_id)
);
CREATE INDEX idx_events_lease ON comment_events(status, lease_expires_at);

CREATE TABLE comment_event_migrations (   -- v4 신규: 마이그레이션 메타데이터를 comment_events에서 분리
    migration_version TEXT PRIMARY KEY,
    input_hash         TEXT NOT NULL,
    input_count        INTEGER NOT NULL,
    applied_at          TEXT NOT NULL,
    verified_at         TEXT,
    status              TEXT NOT NULL   -- 'applying'|'verified'|'mismatch'
);
```

**인터페이스 (v4 — 반환값이 token, 모든 mutate는 claim_token 조건부):**
```python
def try_claim(source, source_event_id, claimed_by, lease_seconds=60) -> str | None:
    """성공 시 claim_token(UUID) 반환, 실패(이미 claim됨) 시 None.
    INSERT OR IGNORE 후 rowcount로 판정 — 최초 성공 시에만 token 발급."""

def reclaim_stale(source, max_age_seconds=60) -> list[tuple[str, str]]:
    """PROCESSING+lease만료 행을 새 claim_token으로 재발급하며 복구.
    이 과정에서 STARTED인 effect는 UNKNOWN으로 전이 + manual_review_required=1
    (v4 결함2 반영). 반환: [(source_event_id, new_claim_token), ...]."""

def mark_effect_started(source, source_event_id, claim_token, effect) -> bool: ...  # False=fenced out
def mark_effect_done(source, source_event_id, claim_token, effect) -> bool: ...
def mark_airtable_retry_pending(source, source_event_id, claim_token, retry_task_id) -> bool: ...
def mark_airtable_done(source, source_event_id, claim_token) -> bool: ...
def mark_retry_enqueue_failed(source, source_event_id, claim_token, error) -> bool: ...
def mark_dead(source, source_event_id) -> None: ...  # claim_token 불필요 — comment_retry_dead_monitor 전용, event 소유권과 무관한 별도 판정
def get_status(source, source_event_id) -> dict | None: ...
```

모든 `mark_*` 함수는 `UPDATE comment_events SET ... WHERE source=? AND source_event_id=? AND claim_token=?` 형태로 실행하고 **rowcount==1일 때만 True 반환** — 0이면(fencing 실패, 이미 reclaim되어 token이 바뀐 경우) False를 반환하고 **호출부는 그 즉시 나머지 처리를 중단**(더 이상 그 이벤트에 대한 소유권이 없으므로).

### 2. 단일 진입점

```python
def process_comment_event(source, source_event_id, ingress, username, text, media_id, commenter_id="") -> None:
    token = try_claim(source, source_event_id, claimed_by=ingress)
    if token is None:
        return  # 이미 처리 중/완료/억제 대상(LEGACY_SUPPRESSED·PRE_ENFORCE_SUPPRESSED 포함 — 마이그레이션이 미리 행을 만들어두므로 자연히 스킵됨, 별도 분기 불필요)
    _handle_comment_impl(token, username, text, media_id, commenter_id)
```
`handle_comment()`는 `_handle_comment_impl`로 내부화. 모든 `mark_*` 호출에 `token` 전달, `False` 반환 시 즉시 return.

### 3. Effect별 정책 (v4 — stale STARTED 처리 명문화)

- Private Reply·Telegram = **at-most-once**. 발송 직전 `mark_effect_started(token, effect)` — **False(fenced)면 발송 자체를 하지 않음**(이미 다른 worker가 이 이벤트를 넘겨받은 상태). 성공/명확한 실패는 `DONE`/유지, **모호하면 `mark_effect_unknown()`**.
- **`reclaim_stale()`가 PROCESSING 행을 복구할 때, `STARTED` 상태인 effect는 자동으로 `UNKNOWN`+`manual_review_required=1`로 전이** — 자동 재실행 금지. Airtable(`airtable_status`)만 안전하게 재개 가능(멱등 재시도 설계이므로).
- Airtable = **at-least-once + idempotency**, 3-way 조회(`FOUND`/`NOT_FOUND`/`LOOKUP_FAILED`, `LOOKUP_FAILED`는 생성 금지·재시도 유지).

### 4. Airtable 기록 실패 → retry_queue

최초 처리 경로에서 실패 시 `mark_airtable_retry_pending(token, ...)` + `retry_queue.enqueue("comment_airtable_record", payload)`. `_retry_record_comment(payload)`는 Airtable 쓰기만(Reply/Telegram 없음), 3-way 조회 선행. `enqueue()` 자체 실패 시 `mark_retry_enqueue_failed(token, ...)` — lease 만료 후 `reclaim_stale()`로 재회수(단, 이미 `DONE`인 effect는 재개 시 스킵, fencing token으로 보호됨).

### 5. `comment_retry_dead_monitor` — 알림 자체의 원자성 (v4, 결함4 반영)

**순서 분리(Slack 장애가 DEAD 기록 자체를 막지 않도록):**
1. `retry_queue.db` 읽기전용 쿼리(`task_type='comment_airtable_record' AND status='dead'`) → 해당 `retry_task_id`로 `comment_events.status='DEAD'` **무조건·즉시** 반영(Slack 성공 여부와 무관, 멱등 UPDATE).
2. `comment_dead_alerts` 테이블에서 **원자적 claim** 시도(`INSERT OR IGNORE` + `status='PENDING'→'CLAIMED'` 조건부 UPDATE, claim 실패 시 다른 인스턴스가 이미 처리 중이므로 skip).
3. claim 성공 시에만 Slack 전송 시도 → 성공하면 `status='SENT'`, 실패하면 `status='PENDING'`으로 되돌려 다음 주기 재시도(claim에 자체 lease 만료도 둬서 전송 중 프로세스 죽어도 회수 가능).

```sql
CREATE TABLE comment_dead_alerts (
    retry_task_id     INTEGER PRIMARY KEY,
    status             TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING|CLAIMED|SENT
    claim_expires_at   TEXT,
    sent_at            TEXT
);
```

**운영 배치:** `sched.add_job(_job_comment_retry_dead_monitor, "interval", minutes=N, max_instances=1, coalesce=True)` — `_job_dome_export`와 동일 옵션(기존 검증된 패턴 재사용). 프로세스 간 경쟁은 SQLite 원자적 claim으로, 동일 프로세스 내 중복 스케줄 실행은 `max_instances=1`로 이중 차단.

**문서화:** Slack 알림은 "정확히 1회 전달 보장 불가, 중복을 최소화하는 at-least-once 경보"로 명시(외부 시스템 특성상 exactly-once는 약속하지 않음 — Private Reply/Telegram과 같은 원칙).

### 6. eager 핸들러 등록

`register_retry_handlers(rq)`를 `launcher/main.py`(`rq=get_retry_queue()` 직후, `rq.start()` 이전)와 `core/run_engine.py`에서 호출. enforce인데 미등록 확인 시 fail-fast. **부수 발견(범위 밖, 기록만):** 기존 `ig_auto_reply`/`ig_followup`도 같은 지연등록 위험 있음.

### 7. Kill-switch: 3모드

`.env`: `COMMENT_EVENT_STORE_MODE = disabled(기본) | shadow | enforce`. `shadow`는 배관 연결만 관측(`would_claim` 로그, 기존 경로 그대로 실행), 로직 정확성은 Phase 1 자동 테스트 + Phase 3 enforce Canary가 증명. event store 장애 시 enforce에서도 fail-closed.

**(v4, shadow row 생성 시)** claim된 shadow row는 `migration_tag=NULL`(아직 최종 disposition 없음), `first_seen_mode='shadow'`(영구 진단 기록)만 남김 — **migration_tag는 cutover 시점에 한 번만, 아래 8번 절차로 확정.**

### 8. 마이그레이션 — v4: shadow cutover 모순 해소

**핵심 정정(v3 모순 해소):** shadow 기간 동안 그 댓글의 Reply/Telegram/Airtable은 **기존(레거시) 코드 경로가 그대로 처리**했음(shadow는 관측만 하고 실제 동작을 바꾸지 않으므로) — 즉 그 손님은 **이미 실제로 응대받은 상태**. 따라서 enforce 전환 시 이 이벤트들을 "새 이벤트"로 재처리하면 그게 바로 중복발송이다. `migration_tag`는 "이 신규 시스템 기준으로 재처리해야 하는가"를 나타내는 **단일 disposition 필드**로, `first_seen_mode`(진단용, 무엇으로 처음 관측됐는지 영구 기록)와 명확히 분리:

- `first_seen_mode` — 절대 덮어쓰지 않음(감사 기록).
- `migration_tag` — cutover 시점에 **정확히 한 번**, `NULL`(shadow row) → `PRE_ENFORCE_SUPPRESSED`로 CLI 마이그레이션 도구가 전이. 이 이후 그 `(source, source_event_id)` 행이 이미 존재하므로, 향후 `try_claim()`이 `INSERT OR IGNORE`로 자연히 no-op — **런타임 코드에 별도 분기 불필요**, 순수히 시딩 완결성의 문제.

**Phase 2 시작 — 1차 시딩(CLI, 수동):** 기존 `processed_comment_ids.json` → `migration_tag='LEGACY_SUPPRESSED'`(Airtable 저장 성공 증거 아님, 자동재실행만 억제). `comment_event_migrations`에 `migration_version`/`input_hash`/`input_count`/`applied_at` 기록.

**Phase 2 종료(Phase 3 직전) — cutover:** JSON delta 시딩 + **shadow row(`migration_tag IS NULL AND first_seen_mode='shadow'`) 전체를 `PRE_ENFORCE_SUPPRESSED`로 일괄 전이** + `deployment_epoch` 기록. `comment_event_migrations.verified_at`/`status` 갱신. 건수·해시 불일치 시 enforce 진입 차단.

### 9. PII 보존 정책 (v4 — 구체화)

- `comment_events`에는 댓글 원문을 저장하지 않음(현재 스키마에 이미 없음 — 불변조건으로 명문화).
- **재시도 payload 원칙: 원문을 저장하지 않고, 재시도 시점에 Meta Graph API `GET /{comment-id}`로 재조회한다.** (댓글은 공개 게시물의 공개 댓글이라 재조회 자체는 저장보다 안전 — DM 원문과 다른 성격이지만, 그래도 로컬 평문 보관 기간을 최소화하는 게 원칙) 재조회가 실패하면(댓글 삭제됨 등) 그 자체를 `LOOKUP_FAILED`류로 처리, 무리하게 로컬 캐시 텍스트로 폴백하지 않음.
- 위 재조회 방식이 구현 단계에서 API 비용/신뢰성 문제로 불가하다고 판명되면 대안: payload에 최소 텍스트만 저장 + **재시도 성공 즉시 payload 필드 redaction**(빈 문자열로 덮어쓰기) + dead 상태 payload는 N일(값은 구현 시 확정) 후 자동 redaction.
- 로그·Slack 알림에는 원문 미노출(comment_id/사유코드만) — ERR-066과 동일 원칙.
- DB 백업 접근권한은 기존 `db/*.db` 백업과 동일 취급, 동일 보존기간 적용.

## Risk-Tiered Review

CLAUDE.md 기준 High-Risk — Repository Interface 변경 + Airtable 스키마 변경 + cross-module + 운영 동작 변경 + 신규 스케줄러 잡.

## 출시 전략 — 4 Phase

**Phase 1 — 코드 수준 증명 (17개 enforce 차단 테스트):**
1. webhook+poller 동시 claim — 정확히 1번만 성공
2. 서로 다른 OS 프로세스의 동시 claim
3. claim 직후 crash → lease 만료 → `reclaim_stale()` 복구(새 claim_token 발급 확인)
4. Private Reply 성공 직후 crash → 재발송 없음, `UNKNOWN` 격리 확인
5. Airtable 실패 → retry_queue 경유 최종 저장 성공
6. **(v4 분리)** Airtable **create 성공, 응답만 유실** → 재시도 lookup=`FOUND` → 추가 생성 없이 `DONE`
6-b. **(v4 신규)** lookup 자체가 실패(`LOOKUP_FAILED`) → 생성 안 하고 재시도 유지(6과 별개 테스트)
7. retry enqueue 실패 → `RETRY_ENQUEUE_FAILED` → lease 만료 후 재개
8. SQLite locked/corrupt/disk-full → fail-closed
9. Airtable `source_event_id` 필드 실존·타입일치 + 필드없으면 startup gate fail-closed
10. `register_retry_handlers()` 실제 진입점에서 `rq.start()` 이전 호출 확인, enforce인데 미등록이면 fail-fast
11. launcher 재시작 시 이전 프로세스의 pending task 정상 재시도(dead 처리 안 됨)
12. `comment_retry_dead_monitor`가 재시작 후에도 동일 dead task 중복 알림 안 함
13. Slack 전송 실패 시 "완료"로 거짓 기록 안 되고 재시도
14. **(v4 신규)** lease 만료 후 이전 worker의 늦은 상태갱신이 fencing token 불일치로 거절됨(rowcount=0 확인)
15. **(v4 신규)** stale `STARTED`가 `UNKNOWN`+`manual_review_required=1`로 전이되고 자동 재발송 안 됨
16. **(v4 신규)** shadow 이벤트가 cutover 후 `PRE_ENFORCE_SUPPRESSED`로 전이되어 자동 재처리 안 됨(`first_seen_mode`는 보존)
17. **(v4 신규)** `comment_retry_dead_monitor` 2개 인스턴스 동시 실행에도 Slack 중복 안 됨(원자적 claim 확인)

**Phase 2 — 마이그레이션 + 짧은 Shadow:** CLI 1차 LEGACY_SUPPRESSED 시딩 → `shadow` 최소 2주기 → delta 시딩+cutover(위 8번 절차).

**Phase 3 — 제한 Enforce:** 캠페인 게시물 1개·최소예산·테스트 계정, 웹훅+폴러 동시 주입 검증, 재시작 후 lease 복구 확인.

**Phase 4 — 확대(fast-follow):** 대시보드, legacy reconciliation, JSON 제거, DM 확장.

## 결정 필요 항목

1. 이 설계 전체 구현 착수 승인 여부(신규 필드·태스크·SQLite·스케줄러 잡 포함).
2. `db/comment_events.db` — `.gitignore:10`의 `*.db`로 이미 자동 제외 확인됨. 스키마/migration 코드/테스트/Runbook은 git 추적, db 파일은 미추적+운영백업 대상.
3. 마이그레이션 — 수동 CLI(`--dry-run/--apply/--verify/--migration-version/--input-hash`), Phase2 시작 1차 + Phase3 직전 delta+cutover, 자동 startup 없음.

## 관련 문서
- FP-047, ERR-062, INC-035, ERR-066, ERR-057(dual-instance 전례)
- `docs/CURRENT_RUNTIME_CONTEXT.md` [260713~260715]
- memory: `feedback_sv_methodology`
