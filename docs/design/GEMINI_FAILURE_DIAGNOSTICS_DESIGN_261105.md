# Gemini/구글 실패 진단 장치 — 설계 메모 (Decision Memo, 261105 23:xx KST)

> 상태: **DESIGN ONLY.** 코드·.env·Airtable·재시작·Commit·Push 없음. 이 파일만 신규 작성(문서).
> 근거 문서: ERR-203, FP-127/129, INC-076, `docs/design/ERROR_EVENT_LEDGER_DESIGN_261103.md`.

## 1. 문제 (한두 문장)
Producer 실패의 67%(18/27)가 구글 쪽 계정 상태였는데, 운영 로그에 **어느 계정이·어느 지역 한도가·몇으로** 막혔는지 남지 않아 원인 확정에 하루가 걸렸다.

## 2. 증거 (FACT / UNKNOWN 분리)
FACT (코드·로그 직접 확인, 261105 23:xx)
1. `carousel_content_builder._log_generation_exception`(L438~455)은 메시지를 `[:200]`으로 자른다. 실제 로그(app.log 2430~2446행)는 `quota metric … and limit …`까지만 남고 **`quota_location`·`quotaValue`·프로젝트 번호는 잘려 나간다**.
2. `generate_carousel_content()`(L1014)는 **계정 인자가 없다** → 로그 한 줄에 account_code가 없다(호출부 `content_package_builder.py:561, 860`만 계정을 안다). 병렬 실행 시 어느 줄이 어느 계정인지 시간대로 추정해야 한다.
3. `caption_generator._classify_retry`는 **모든 429를 retryable**로 본다. 한도 0(재시도해도 영원히 실패)과 일시 분당 초과를 구분하지 못해 슬롯마다 4회 재시도(로그상 5~20초 대기)를 반복한다.
4. 429 상세 추출기는 이미 있다: `research_to_topic_adapter._extract_gemini_quota_fields`(L187~215) — `QuotaFailure.violations[0]`의 `quotaMetric/quotaId/quotaValue`와 `RetryInfo.retryDelay`를 읽는다. **다만 `quotaDimensions`(location)·consumer(프로젝트)는 읽지 않고, research 어댑터에서만 호출된다.**
5. 오류 원장 `modules/common/error_events.py` 존재(`events` 테이블, `safe_text` 마스킹, 계정·분류별 하루 1회 알림 `alert_log`, Slack은 별도 스레드). 현재 Caller는 Meta 게시 실패(`launcher/main.py` `_record_meta_failure`)뿐이며, 설계 문서가 `GEMINI_QUOTA_429`/`GEMINI_AUTH`를 **3단계(별도 승인)** 로 예고해 두었다.
6. 사전 점검 `account_preflight.py`의 Gemini 항목은 **`{prefix}_GEMINI_API_KEY` 환경변수 존재 여부만**(L71~75) 본다. 키 유효성·쿼터는 보지 않는다.
7. 8프로젝트 `quota_location=asia-east1`, `quota_limit_value=0`(ERR-203, 승인된 1토큰 probe). 018·023 "리소스 정지" CONFIRMED.

UNKNOWN
- 429 본문의 `quotaDimensions`·consumer 필드가 **운영 429에서 항상 같은 위치**에 오는지(probe 때 읽은 구조 1회분만 확인). → Canary 1단계에서 실제 예외 객체로 확인.
- 정지 사유 조항, 나머지 6프로젝트의 정지 여부, 복구 시점.
- 403(정지) 시 응답 형태가 429와 같은지(별도 분류 필요 여부).

## 3. 옵션 비교 (CLAUDE.md Gate 6)
| 항목 | 권장 선택 | 이유 |
|---|---|---|
| (a) 구조화 로그 | **REUSE+소수정**: 기존 `_extract_gemini_quota_fields`를 공용 위치로 옮기지 않고 import해서 재사용, `quotaDimensions.region/location`·`consumer` 필드만 추가 | 파서가 이미 있고, 새 파서를 만들면 형식이 둘이 된다. Allowlist 필드만 기록 → 키·본문 미저장 |
| (b) 연속 실패 알림 | **REUSE**: `error_events` 원장에 `source=gemini`, 분류 `GEMINI_QUOTA_ZERO / GEMINI_RATE / GEMINI_AUTH / GEMINI_5XX` 추가 + 기존 `alert_log`(계정·분류·하루 1회) + `get_notify_fn()` | 설계 문서의 3단계와 일치. "N회 연속" 대신 **한도 0은 1회 확정 즉시 알림**(분류가 이미 확정적), 나머지는 일 1회로 충분 |
| (c) circuit breaker | **DEFER(후속 승인)**. 먼저 (a)(b)로 "한도 0" 판정을 확정 로그로 만든 뒤, `quota_limit_value=0`이 같은 날 2회 이상일 때만 해당 계정 슬롯을 Fail-closed 스킵(계정 단위, Airtable 쓰기 없음, SQLite 보류 목록) | 구글 쪽 오탐(일시 0 표시) 위험을 아직 모름 → 자동 격리는 증거 후에. Fail-closed가 맞는 이유: 한도 0은 재시도해도 성공 불가, 슬롯 4회 재시도는 순수 낭비 |
| (d) preflight probe | **옵션(Canary 후 결정)**: 슬롯 첫 Producer 전 1회만, 비용 1토큰·호출 22회/일 이하. 키는 마스킹, 본 장치 (a)가 쌓은 상태가 있으면 probe 생략 | 호출 빈도·키 노출·무료 쿼터 소모를 고려하면 "실패 로그가 최신 상태 근거"가 먼저. probe는 회장 승인 수동 도구(`tools/`)로 시작 |
| (e) BUY | **제외(YAGNI)**: Sentry/Datadog 등은 22계정 규모에 과잉, 이미 Slack+SQLite 원장 보유 | CLAUDE.md 18.2 |

## 4. 권장안 (1개)
**1단계 = (a)+(b)의 "기록+알림만"**. 게시·재시도·상태 변경 로직은 건드리지 않는다.
- `_log_generation_exception`에 계정 코드를 받는 optional 인자 추가(기본 빈 값 → 기존 호출 무영향) + Allowlist 필드 1줄 로그: `acct, http_code, quota_metric, quota_id, quota_location, quota_limit_value, consumer, retry_delay`.
- 같은 정보를 `error_events.record_event(source="gemini", stage="carousel_generate")`로 기록. 분류: `quota_limit_value == 0` → `GEMINI_QUOTA_ZERO`(P1, 계정당 하루 1회 Slack), 그 외 429 → `GEMINI_RATE`(P3, 알림 없음), 401/403 → `GEMINI_AUTH`(P1), 5xx → `GEMINI_TRANSIENT`(P3).
- 로그·DB·Slack에 키·프롬프트·응답 본문 미저장(`safe_text` 재사용).
- 재시도 동작·`_next_retry_delay`·`GENERATION_FAILED` 반환값은 **변경하지 않는다**(회귀 격리).

## 5. 가장 작은 Canary (Gate 10)
1. 로컬 pytest(운영 로그·네트워크 차단): 가짜 `APIError` 3종(한도 0 / 분당 초과 / 403) → 분류·필드·마스킹·`error_events` 기록, optional 인자 없는 기존 호출이 이전과 동일 로그 형식인지 baseline 비교.
2. Runtime Canary: **1계정(한도 0으로 확인된 018 또는 038)** 의 다음 Producer 1회 → app.log 1줄 + `db/error_events.db` 1행 + Slack 1회 확인. 성공 기준: 필드 `quota_location=asia-east1`, `quota_limit_value=0`, account 일치, 키·본문 0건, 신규 ERROR 0건.
3. 승인 필요 구분: 코드수정 / 로컬 테스트 / 재시작(관리자 `Restart-Service SNS_Watchdog`) / Runtime Canary / Commit 각각 별도.

## 6. Rollback
- 코드: 해당 커밋 `git revert`(optional 인자·기록 호출만 추가했으므로 단일 커밋 단위). 재시작 1회.
- 데이터: `db/error_events.db`의 `source='gemini'` 행은 삭제 가능(원장은 기록 전용, 다른 로직이 읽지 않음). `.env`·Airtable 변경 없음.

## 7. 위험 / 제약
- 계정 인자 전달을 위해 `generate_carousel_content`(Interface)와 호출부 2곳(`content_package_builder.py` L561·L860)이 닿는다 → **High-Risk 경로(Producer 런타임)**. optional 인자·기본값으로 기존 Caller 강제 수정을 피하고, Codex 리뷰 필수.
- 8프로젝트가 정지/한도 0인 동안은 `GEMINI_QUOTA_ZERO` 알림이 8건 한꺼번에 나갈 수 있음 → 계정당 하루 1회 제한이 이미 있어 허용, 첫날은 의도된 소음.
- 공유 `GEMINI_API_KEY` fallback 금지(규칙 9)는 영향 없음. 키·Credential·Model 변경 없음.
- 본 메모는 코드 수정 제안이며, 별개 미결건(Retry-After 상한 30초, `.env` 의존 테스트 8건)과 한 번들로 묶지 않는다(Gate 5).

## 8. 승인 요청 문구 (회장 복붙)
```
Gemini 진단 장치 1단계(기록+알림만, 계정 인자 optional 추가, 재시도 로직 불변)의
로컬 테스트 포함 구현을 승인합니다. 재시작·Runtime Canary(018 또는 038 1회)·Commit·Push는 별도 승인.
```
