# 2026-08-03 20:26 ICT — Track B 6F Claude Code 인계: 2/3 SUCCESS, Source 3.6 추가, #3 Gemini 503 소진 후 Fail-closed

_이 항목이 Track B 6F의 최신 Runtime/Git 인계 상태다. 아래 과거 기록의 ERR-101/ERR-102 OPEN 및 #1 재개 지시는 이 항목으로 대체한다._

## 현재 기준
- Active Runtime: `C:\SNS_24AutoProject_260511`, branch `master`. 이 인계 문서 작업 직전 기준 `HEAD=origin/master=09f03c0d05217980317c4da03e82fe7957665c00`, tracked 변경은 Sourcebook 3.6 추가 1건뿐이었다.
- 완료 Gate: 6F #1/3 SUCCESS, ERR-101 Production Resilience 수정·Push(`b98afa178a28b3206cbbe5a327994e425b4cdb43`), ERR-102 Provider/Safety 분류 수정·Push 및 Production 재시작 적용(`09f03c0d05217980317c4da03e82fe7957665c00`), 6F #2/3 SUCCESS.
- `SNS_Watchdog`/SYSTEM Scheduler는 `09f03c0` 적용 후 정상 heartbeat·HTTP 200을 확인했다. 6F #2/3과 #3 사이 서비스 재시작·코드 수정은 없었다.

## 6F 게시 결과
- **#1/3 SUCCESS:** `content_id=3-4-260803-b501c92f`, Airtable `recfFdfTkJoKk4biu`, Instagram `ig_media_id=17976679115901401`, 최종 `posted`, 중복 0건.
- **#2/3 SUCCESS:** `content_id=3-5-260803-54c5b2e9`, Source `https://www.ycombinator.com/library`, Airtable `recDFi8IWZ8qXeEOz`, Instagram `ig_media_id=18109337171018360`, 최종 `posted`. Canary 수동 호출 1회, 기존 Scheduler 자동 처리 1회, Record/Source/image URL/media ID 각각 1건, ready/uploading 0건.
- **전체 현재 판정:** 6F는 **2/3 SUCCESS**. 3/3 완료나 6G 진입으로 해석하면 안 된다.

## Source 3.6과 #3 실패
- 기존 선택 가능한 3.1~3.5가 모두 Vault에서 사용 완료되어, NIST 공식 원문을 신규 Source `3.6 NIST AI Risk Management Framework (AI RMF 1.0)`으로 Sourcebook에 추가했다. URL은 `https://www.nist.gov/itl/ai-risk-management-framework`; 기존 Sourcebook·Vault·Ledger URL/주제 중복 0건. Source 파서·선택 Target Test `10/10 PASS`.
- 다음 후보는 `topic_id=3.6`, 예정 `content_id=3-6-260803-54dbc154`. #3 Canary는 2026-08-03 20:19:52~20:21:28 ICT에 정확히 1회 실행됐다.
- Gemini Caption 호출이 HTTP 503으로 4/4 소진되어 `CAPTION_GENERATION_FAILED`로 중단됐다. 마지막 성공 지점은 P0 Boot Policy·P1 Account Context·Source 3.6 선택이다. Vault md/image 0건, ImgBB 0건, Airtable Source Record 0건, Meta 0건, ready/uploading 0건, 이미지 사용량 2/3 — 부분상태와 중복은 없다.
- 계약대로 Canary 재실행·수동 Airtable 복구·수동 Meta 게시·Commit은 실패 직후 수행하지 않았다. Source 3.6은 당시 미커밋이었으며, 사용자의 후속 인계 문서화 승인으로 이 문서들과 함께 Commit·Push 대상이 됐다.

## Claude Code 다음 단일 작업
Gemini Provider가 503에서 회복된 시점에 사용자 승인을 받은 뒤 **6F #3/3 Canary 1회만 재시도**한다. 실행 직전 Delta는 이미지 사용량 `2/3`, Airtable ready/uploading `0`, 다음 후보 `3.6`/`3-6-260803-54dbc154`만 다시 확인한다. 하나라도 다르면 HOLD한다. 실패·결과불명 시 재실행/수동 상태복구/수동 Meta 게시 금지. 성공 시 Record·Source·image URL·media ID 1:1, ready/uploading 0, 이미지 사용량 3/3을 확인하고 6F 전체 3/3 판정만 제출한다. **6G는 별도 승인 전 시작 금지.**

---

# 2026-08-03 12:19pm ICT — Gemini Retry 구현 Commit·Push 완료, 6F #1/3 재실행도 429 지속 — DEFER

_기록 시각: 2026-08-03 12:19pm ICT · 상태: Gemini transient-error Retry 구현(`_classify_retry`/`_next_retry_delay`, `_MAX_ATTEMPTS=4`) GPT 3회 재검수(Blocker 3건 순차 수정: 120초 clamp+jitter 분리, `final_exhausted` 정확성, 테스트명 오해소지 제거) 끝에 SUCCESS 판정 → 회장 승인으로 4개 파일(`caption_generator.py`/`test_generate_hook_caption.py`/`test_dome_export_batch_isolation.py`/이 문서) commit(`b99058a`)·push 완료(HEAD=origin/master 동기화 확인). 승인 하에 6F #1/3 즉시 재실행했으나 4회 전부 실제 Gemini `429`(Retry-After 실측값 정확히 사용, 4회 소진 후 `final_exhausted=True` 정확 기록, Airtable/Vault 부분기록 0건) — **Retry 구현 자체는 설계대로 정상 동작 확인됨**, 근본 원인(Provider 과부하 vs 오늘 세션 중 자체 발생한 Live-call 12회를 포함한 누적 호출로 인한 일일 Quota 소진)은 GPT 판정으로 **UNKNOWN**. 회장 지시로 오늘 6F 추가 실행 없이 다음 세션으로 DEFER, 다음 세션 시작 시 Gemini Quota/리셋 상태 Read-only 확인부터 선행. 이 항목이 최신 상태이며, 아래 260803 09:39(6F 1차 재개 시도) 이하는 이전 기록으로 보존._

## Commit·Push 확정 Evidence
- Commit `b99058aba4e99f3457bacfdbad9b2422d6c5689d`(4 files changed, 395 insertions/37 deletions) — `git push origin master` 완료(`414be99..b99058a`), `git status -sb` ahead/behind 0/0, Working Tree clean.

## 6F #1/3 재실행 결과(260803 12:16~12:18pm ICT, 새 Retry 로직 적용 후 최초 실행)
- 4회 시도 전부 실제 Gemini `429 Too Many Requests`(`category=provider_http_429`), Retry-After 실측값 사용(0.0s/56.0s 등, jitter 미적용 — 설계대로), 4회 소진 후 `final_exhausted=True` 정확 기록, 빈 캡션으로 Fail-closed 종료 → `content_package_builder`가 `CAPTION_GENERATION_FAILED`로 즉시 중단(Airtable 호출 전, 부분기록 0건).
- **판정(GPT)**: Retry·상한·Fail-closed 전부 정상 — 문제는 여전히 Gemini 쪽(Provider 과부하 또는 오늘 세션 자체 사고로 발생한 Live-call 12회 포함 누적 호출로 인한 Quota 소진), Root Cause는 현재 Evidence로 구분 불가 → **UNKNOWN**.
- 회장 지시: 오늘 6F 추가 재시도 금지(무한 Retry 우회 위험), 다음 세션 Gemini Quota/리셋 상태 확인 후 재승인받아 실행.
- **별개(기존 알려진 문제, 미수정)**: `tools/_canary_260801_queue_aijomoojin_post_6f.py:36` em-dash 콘솔 크래시 재발(ad-hoc gitignore 스크립트, 이번 커밋 범위 밖, 계속 DEFER).

## 다음 세션 시작 시 확인할 것
1. Gemini API Quota/Rate-limit 상태 Read-only 확인(가능하면 — 공식 콘솔/문서로 RPD/RPM 리셋 여부 판단, 추정 금지).
2. 확인 후 6F #1/3 재승인 요청 → 1건씩 순차 검증 재개(기존 Canary 최소단위 원칙 그대로).
3. 6F 3/3 성공 후 6G(정식 운영 전환) 승인 여부 결정은 여전히 미착수.
4. `tools/_canary_260801_queue_aijomoojin_post_6f.py:36` em-dash 출력버그는 여전히 미수정(선택, 승인 필요).

---

# 2026-08-03 09:39 ICT — 6F #1/3 재개 시도 3연속 실패(Gemini 외부장애) — HOLD/DEFER

_기록 시각: 2026-08-03 09:39 ICT · 상태: 6D+6E는 260801 20:19 ICT에 commit(`6360c58`)·push 완료(Step6B Delta `414be99`도 동일 시점 commit·push 완료, 이전 기록의 "미커밋" 서술은 이 시점 이후 갱신되지 않은 것이었음 — git log로 재확인). 6F #1/3 재개: DAILY_IMAGE_CAP은 SQLite 직접조회로 리셋 확인(오늘 UTC count=0/3)했으나, `create_content_package()`의 캡션 생성(Gemini) 단계에서 3회 연속 실패(503×2 + WinError 10054×1) — 코드결함·Airtable Write 0건, 전부 Gemini 쪽 외부 문제로 판정. 회장 지시로 오늘 추가 재시도 없이 다음 세션으로 DEFER. 이 항목이 최신 상태이며, 아래 260801 20:11(6D/6E SUCCESS·6F HOLD) 이하는 이전 기록으로 보존._

## 6F #1/3 재개 시도(260803, 이번 세션)
- **DAILY_IMAGE_CAP 리셋 확인(Evidence)**: `db/image_gen_quota.db` 직접조회 — 마지막 생성 `2026-08-01 12:03:08`(그날 4회), 오늘(SQLite `datetime('now')`=UTC `2026-08-03 01:59:09`) 카운트 `0`. 리셋 확인됨, cap 문제 아님.
- **3회 연속 실패**(전부 Airtable 호출 이전 `create_content_package()` 캡션 생성 단계에서 중단, 부분기록 0건):
  1. 09:00:12 — Gemini `503 UNAVAILABLE`("This model is currently experiencing high demand...")
  2. 09:30:09 — `WinError 10054`(기존 연결이 원격 호스트에 의해 강제로 끊김)
  3. 09:39:40 — Gemini `503 UNAVAILABLE`(동일 메시지)
- **회장 결정**: 즉시 4차 재시도 대신 오늘은 중단, 다음 세션으로 DEFER.
- **별개 발견(코드결함, 낮은 위험, 미수정)**: `tools/_canary_260801_queue_aijomoojin_post_6f.py:36`의 실패 시 print 문이 em-dash(—)를 포함해 Windows cp949 콘솔에서 `UnicodeEncodeError`로 크래시 — 실제 `result.error_code` 값이 화면에 안 보이고 스택트레이스로 대체됨(원인 자체는 stdout의 Gemini 원문 로그로 대체 확인 가능했음). 다음 세션에서 회장 승인 시 1줄 수정 대상(gitignore 대상 ad-hoc 스크립트라 커밋 영향 없음).

## 6D/6E Commit·Push 상태 정정(Evidence: git log)
- `6360c58`(6D+6E 코드변경) / `414be99`(Step6B Delta, 격리) 둘 다 `2026-08-01 20:19` commit, 현재 `git status -sb`상 `origin/master`와 diff 0(push 완료 확인).
- 이전 기록(260801 20:11 항목)의 "Commit·Push 0건/미승인" 서술은 그 기록 시각 **직후**(같은 세션 8분 뒤, 20:19) 진행된 것으로 확인 — 문서 자체를 소급 수정하지 않고 이 최신 항목에 정정 사실만 기록.

## Gemini Retry 정책 — GPT 검수 완료(APPROVAL_REQUIRED, 코드 미착수)
- 회장 지시로 근본원인(429 문자열 매칭만 재시도, 503/연결오류는 즉시 포기 — `caption_generator.py:160` 부근) 조사 후 GPT에 검수 요청, GPT가 260803 10:12 ICT 설계 승인 초안 회신:
  - **1(재시도 구조)**: 무한 금지 — 실행당 3회(5s→20s→60s+jitter) 후 종료 → 기존 Scheduler에서 최대 2~3회 재기회 → 최종 실패 시 Alert. 총 상한 6~9회, 영구 반복 금지.
  - **2(에러 분류)**: 503=Provider overload(Retry-After 우선, 긴 backoff) / WinError 10054=Transport reset(짧은 backoff, 반복 시 네트워크 장애로 종료) — 둘 다 Retryable이지만 분류는 분리.
  - **3(실행 위치)**: 긴 내부 Loop 금지(Worker 점유·재시작 시 상태소실·Watchdog 영향 위험) — 기존 APScheduler REUSE + 짧은 내부 Retry만.
  - **4(Circuit Breaker)**: 완전한 CB(Half-open 상태머신 등)는 이 규모에 YAGNI — 연속 3회 transient 실패 시 15~30분 Gemini 호출 자체를 쉬는 최소 Cooldown만.
  - **FACT**: Airtable/Vault 0건·Fail-closed 중단은 정상(변경 대상 아님). Retry는 Caption 단계에만 적용, Meta 게시 이후 전체 Pipeline 재실행 금지.
  - **RISK**: 다음 tick을 영구 허용하면 이름만 바뀐 무한 Retry(CLAUDE.md 15.2 위반). 10054가 방화벽/Proxy/TLS 문제면 반복호출은 복구가 아니라 장애 증폭.
  - GPT 260803 10:23 ICT 추가 지시: "재시도 범위·상한·실패처리 설계를 GPT가 먼저 확정·승인한 뒤 Claude Code가 구현" — 즉 이 표는 방향 승인이며, **회장이 별도로 구체 설계(diff 수준)를 줄 때까지 코드 수정 착수 금지**.
- **현재 상태**: 코드 변경 0건(대기), 다음 세션(또는 이번 세션 후속)에서 회장이 구체 설계를 전달하면 그때 5요소 승인 포맷으로 재제출 후 구현.

## Gemini Retry 구현 — 실제 반영 내용(SSOT 정정, 260803 12:00pm ICT)

> 위 260803 10:12/10:23 항목은 **최초 방향 승인 초안**이며, 회장이 260803 11:33 ICT 이후 전달한 **구체 설계(성공기준 5개, 승인범위 2파일)**로 대체·구체화됐다. 아래가 실제 구현 상태다 — 위 초안 항목(3회/Scheduler 재기회/Cooldown/Alert)은 **채택되지 않았다**, 혼동 방지를 위해 명시 정정한다.

- **적용 범위**: `modules/sns/caption_generator.py`의 `generate_caption()`/`generate_hook_caption()` 2개 함수만. Scheduler(`launcher/main.py`) 변경 없음. Circuit Breaker/Cooldown 없음. Slack Alert 신규 연결 없음(전부 이번 구현 범위 밖으로 확정, 초안의 "Scheduler 2~3회 재기회"·"15~30분 Cooldown"·"최종실패 Alert"는 미구현).
- **실제 재시도 상한**: 최초 호출 포함 **총 4회**(`_MAX_ATTEMPTS=4`, 초안의 "3회"가 아님) — SDK 자체 재시도는 기본 비활성화 확인됨(코드 근거: `google/genai/_api_client.py:529-530` `retry_args(None)`→`stop_after_attempt(1)`), 따라서 실제 외부 호출 상한도 4회로 일치.
- **재시도 대상 분류**(`_classify_retry()`): HTTP 408/429/500/502/503/504, `httpx.TimeoutException`, `httpx.TransportError`, WinError 10053/10054 — 재시도. 400/401/403·Safety 차단(빈 응답)·기타는 즉시 실패(재시도 안 함).
- **대기시간**: 기본 5s→20s→60s(±20% jitter) 또는 Provider의 Retry-After/retryDelay 우선 사용. Provider 명시값은 **120초 상한 내에서 jitter 없이 그대로** 사용(260803 11:58am ICT GPT 2차 지적으로 수정 — 최초 구현은 Provider 값에도 ±20% jitter를 적용해 120초 지시가 96초로 줄어들 수 있는 결함이 있었음). jitter는 Provider 값이 없을 때(기본 backoff 경로)만 적용.
- **로그 정확성**: `final_exhausted` 필드가 항상 `True`였던 결함을 수정 — 이제 `retryable` 값을 그대로 반영(영구오류로 1회만에 실패한 경우 `final_exhausted=False`, 재시도를 다 쓰고 실패한 경우만 `True`).
- **부수 수정**: `tests/test_dome_export_batch_isolation.py`의 `sys.modules` 주입 기반 Mock이 import 순서에 따라 무력화돼(Python 모듈 캐싱) 실제 Gemini Live 호출 12회가 발생한 사고 발견 → `monkeypatch.setattr(source_exporter, "generate_caption", ...)` 방식(같은 저장소의 `test_package_b_post_attribution.py`에서 이미 검증된 패턴, REUSE)으로 교체, import 순서 무관하게 항상 격리되도록 수정(단독 실행 4/4 PASS, Live-call 0건 확인).
- **Commit·Push**: 이 기록 시점까지 여전히 0건(GPT 최종검수 대기 중, 260803 11:58am ICT 기준 2차 재검수까지 완료·3차 검수 대기).

## 다음 세션 우선순위(260803 12:00pm ICT 정정 — 구현 완료 반영)
1. **GPT 최종 Commit 승인 대기** — Retry 구현(`caption_generator.py`)·신규 target test(`test_generate_hook_caption.py`)·Mock 격리 수정(`test_dome_export_batch_isolation.py`)·이 문서, 4개 파일 전부 코드레벨 완료·단위테스트 PASS 확인됨. 승인 즉시 Commit·Push만 남음(추가 구현 작업 없음).
2. Commit·Push 승인 후 6F #1/3 재시도 — 동일 명령: `C:\SNS_24AutoProject_260511\.venv\Scripts\python.exe C:\SNS_24AutoProject_260511\tools\_canary_260801_queue_aijomoojin_post_6f.py`
3. (선택, 승인 필요) `tools/_canary_260801_queue_aijomoojin_post_6f.py:36` em-dash 출력버그 수정 — ad-hoc 스크립트라 낮은 위험이나 코드수정이므로 승인 절차 그대로 적용.
4. 6F 3/3 성공 후 6G(정식 운영 전환) 승인 여부 결정은 여전히 미착수.

---

# 2026-08-01 20:11 ICT — 6D SUCCESS / 6E SUCCESS / 6F HOLD(DEFER) — 세션 종료 기록

_기록 시각: 2026-08-01 20:11 ICT · 상태: 6D(중복사고 방지)·6E(AI_CONTENT Gate v1 언어검사) 코드레벨 SUCCESS, 6F(3-post 자동게시 Canary) #1/3 큐잉 시도 중 기존 안전상한(DAILY_IMAGE_CAP=3/일)에 걸려 HOLD, 회장 지시로 다음 세션(UTC 리셋 후, 약 260802 07:00 ICT)으로 DEFER. 이 항목이 최신 상태이며, 아래 260801 19:17(Gate v0 최소조립) 이하는 이전 기록으로 보존._

## 6D — 중복사고 방지(HTTP 4xx → outcome_unknown)
- 실사고 근거(이전 기록): media_publish HTTP 400을 "명확한 실패"로 분류하던 기존 로직이 실제로는 부정확(400 직후 서버측 조용한 성공 2건 실측) → 재시도가 실제 중복게시를 만듦.
- 수정: `launcher/main.py::publish_single()` — HTTP≥400 응답을 기존 5xx/timeout과 동일하게 `outcome_unknown=True`로 반환(정의된 실패 아님, 재시도 안 함, 사람 확인 대기로 격리).
- 검증: 신규/갱신 테스트 PASS(`test_publish_outcome_unknown.py`), 타겟 회귀 0건(기존 T4 PermissionError baseline 3건만 잔존, 무관).
- 실측 재발검증(라이브)은 미실행 — 코드레벨 수정만 확인됨, 실제 검증은 6F Canary에서.

## 6E — AI_CONTENT Gate v1(언어일치 검사)
- 실사고 근거(이전 기록): `Persona_Profile.language="ko"`(PER-002) 값이 Airtable에 이미 있었는데 Gate가 읽지 않아 영어 게시 사고 발생.
- Airtable Read-only 확인(Evidence): `Persona_Profile.language`(fldZv0QunGbvVxhtG) 실존, PER-002="ko".
- 수정(전부 additive/하위호환): `repository_interface.py`(PersonaProfile.language 옵션필드) / `airtable_repository.py`(get_active_persona_by_account_code_v2가 language 반환) / `content_filter.py`(passes_ai_content_gate_v0·resolve_publish_gate에 required_language 옵션 kwarg, 기존 `_korean_ratio()` REUSE, 임계값 0.2) / `launcher/main.py`(persona.language를 Gate 호출에 전달).
- 검증: 신규 테스트 8건 PASS(영어차단/한국어통과/kwarg미전달시 스킵/resolve_publish_gate 경유/Repository language 반환), 타겟 회귀 68 passed / 3 failed(전부 기존 T4 baseline, 무관).

## 6F — 3-post 자동게시 Canary(HOLD/DEFER)
- 준비: `tools/_canary_260801_queue_aijomoojin_post_6f.py`(신규, gitignore 대상 `tools/_*.py`) — create_content_package(target_language="ko" 명시)→imgbb 업로드→Instagram_Posts ready 레코드 1건 큐잉만 수행(게시는 기존 APScheduler가 자동 수행해야 증명 성립). Canary 최소단위 원칙에 따라 3건을 한 번에 큐잉하지 않고 1건씩 순차 실행+검증 설계.
- 실행 결과: #1/3 시도 → Gemini 캡션 생성 성공 → 이미지 생성 단계에서 `DAILY_IMAGE_CAP_EXCEEDED`(cap=3, UTC 기준 오늘 이미 4회 사용) → Fail-closed 설계대로 Vault/Airtable 어디에도 부분기록 없이 즉시 중단(롤백 불필요, 확인됨).
- 결정: 코드결함 아님, 기존 안전상한 정상작동 — 회장 지시로 오늘 추가 시도 없이 다음 세션(UTC 리셋 이후)으로 DEFER.

## 남은 미결(다음 세션 우선순위)
1. 6F 재개: `C:\SNS_24AutoProject_260511\.venv\Scripts\python.exe C:\SNS_24AutoProject_260511\tools\_canary_260801_queue_aijomoojin_post_6f.py`로 #1/3부터, 매 1건마다 자동게시(ig_media_id) 확인 후 다음 건 진행.
2. 6F 3/3 성공 후 6G(정식 운영 전환: 매일 08:00 ICT, 하루 1건) 승인 여부 결정.
3. Step6B Delta(`publish_ledger.py`/`aijomoojin_scheduled_publish_job.py`/`fetch_due_scheduled_post`) 재승인 또는 폐기 결정 — 여전히 미사용.
4. 이번 세션 전체 코드 변경(6D+6E) **Commit·Push 0건** — 별도 승인 필요.

---

# 2026-08-01 19:17 ICT — AI_CONTENT Gate v0 조립 완료(최소 구현) — 정식 안전검사는 후속 별도 진행

_기록 시각: 2026-08-01 19:17 ICT · 상태: Gate v0는 "최소 조립"으로 명시 확정 — Gemini `finish_reason` 재사용 + Sourcebook 출처확인 + 계정/Persona 일치, 4개 조건뿐. 키워드 정책엔진·컨텍츠 분류기·점수모델 등 정식 안전검사는 아직 없음(의도적 DEFER, 회장 지시). 이 항목이 최신 상태이며, 아래 260801 18:28(Step6C SUCCESS) 이하는 이전 기록으로 보존._

## Gate v0 최종 상태(기록)
- 위치: `modules/sns/content_filter.py::passes_ai_content_gate_v0()` + `modules/sns/caption_generator.py::check_caption_safety()`.
- 확인 항목 4개뿐: ①Gemini `finish_reason==STOP`(유해성만, 주제 적합성 아님) ②Sourcebook `source_url` 존재 ③`account_code_ref==IDN-000036` ④`persona_code==PER-002`.
- **명시적으로 하지 않은 것**(정식 안전검사에서 다뤄야 할 항목, 이번엔 DEFER): 콘텐츠 언어 검증(아래 사고 참조), 브랜드/경쟁사 언급 필터, 카테고리·주제 적합성 분류, 반복/유사 콘텐츠 탐지, 실제 발행 전 사람 승인(Approval Gate) 등.

## 이번 세션 실사고 2건(다음 세션·정식 안전검사 설계 시 반드시 반영)
1. **언어 불일치 사고**: `content_package_builder.create_content_package()`가 Persona(PER-002)의 Airtable `language="ko"` 필드를 확인하지 않고, 호출자(이 세션)가 `target_language="EN"`을 임의 지정 — 실제 계정에 영어 캡션이 게시됨(1차 실패작, 회장이 직접 삭제). **근본원인**: Persona 데이터에 이미 있는 값을 Runtime이 자동으로 반영하는 연결이 없음(T1에서 이미 지적된 "Persona 적용 경로 NOT IMPLEMENTED" 문제의 실제 발현).
2. **모호한 실패 재시도 → 실제 중복게시 사고**: `publish_single()`의 media_publish HTTP 400을 "명확한 실패(안전하게 재시도 가능)"로 분류하는 기존 로직이 실제로는 **부정확했음** — 2건 모두 400 응답 직후(수십 초 이내) 실제로는 서버에서 게시가 조용히 성공한 상태였고, 재시도가 진짜 중복 게시를 만듦. **교훈**: HTTP 400이어도 재시도 전에 반드시 계정의 실제 최근 게시물 목록(`GET /{ig_user_id}/media`)으로 이미 올라갔는지 확인해야 한다 — 이번 세 번째 시도부터는 이 확인을 먼저 하도록 절차를 바꿨고(교훈 반영), `publish_single()` 코드 자체의 400 분류 로직 수정은 이번 세션에서 하지 않음(DEFER, 별도 승인 필요).

## 최종 성공 확정 Evidence(재확인)
- media_id: `17924318079395000`(Radical Candor, 한국어) — 실제 계정 `GET /media` 조회로 최근 게시물 1건만 존재함을 확인, 이전 3개(영어/넷플릭스 1 + 중복 한국어 2)는 회장이 앱에서 직접 삭제 완료(API 삭제 미지원 확인됨).

## 다음 세션 우선순위
1. **정식 안전검사 설계**(회장 지시, "정석대로") — 언어 검증, 콘텐츠 분류, 발행 전 승인 Gate 등을 Gate v0에 이어 REUSE→ADOPT→ADAPT→BUILD 순서로 재검토.
2. `publish_single()`의 HTTP 400 분류 로직 재검토(실사고 기반 — outcome_unknown으로 재분류할지 검토).
3. `content_package_builder.create_content_package()`가 Persona.language를 자동 반영하도록 연결.

---

# 2026-08-01 18:28 ICT — Step 6C SUCCESS — aijomoojin 최초 실계시 게시 성공(media_id 확보, 회장 확인)

_기록 시각: 2026-08-01 18:28 ICT · 상태: **IDN-000036(aijomoojin) 계정, 기존 APScheduler(`_job_insta_upload`) 자동실행으로 실제 Instagram 게시 성공** — 수동 `publish_single()` 호출 없이 자동 claim→Persona Gate→AI_CONTENT Gate v0→Meta 게시까지 전부 자동 경로로 완료. 이 항목이 최신 상태이며, 아래 260801 14:45(Step4 SUCCESS) 이하는 이전 기록으로 보존._

## 최종 결과
- **media_id: `17919000633413180`**(실제 Instagram, 회장이 앱에서 직접 확인·"성공" 확정)
- 계정: IDN-000036 / aijomoojin, Airtable Record `recYKIHJYw8G4MrE3` → `post_status=posted`, `ig_media_id=17919000633413180`
- 콘텐츠: Sourcebook 3.1 "Netflix Culture Memo"(source_url: jobs.netflix.com/culture), Track B 기존 함수(source_selector/caption_generator/visual_brief/image_provider_cloudflare) REUSE로 생성한 실제 콘텐츠 1건

## 이번 세션 핵심 경로(요약)
1. **T1 Account Binding**: `IDN-000036↔aijomoojin↔PER-002` Airtable Linked Record 실증 확인 → `aijomoojin_binding_adapter.py`(신규, Feature Flag 기본 false) 구현·19테스트 PASS.
2. **Step6B External-First 위반 자체교정**: 첫 시도(Publish Ledger·예약게시 오케스트레이터·로컬이미지→ImgBB 직접업로드)를 외부후보 비교 없이 먼저 BUILD해 회장이 `ISOLATED_UNAPPROVED`로 격리 지시 → GitHub Actions/obsidian-git/n8n 3개 공식 비교 후 전부 탈락, 기존 APScheduler REUSE가 정답으로 재확인됨(이 Delta 파일들은 실제 성공 경로에서 사용 안 됨, 재검토 대상으로 잔존).
3. **T4 Root Cause 완전확정**: `runtime_boot_policy.json` PermissionError는 파일 손상이 아니라 Claude Code 세션의 비상승(UAC deny-only) 토큰 vs `C:\ProgramData\SNS_24AutoProject` ACL(SYSTEM+Administrators만 Allow) 차이 — 회장이 관리자 PowerShell에서 직접 실증(동일 계정, 상승 시 정상).
4. **Safe Mode "armed" 정책파일 생성 도구가 코드베이스에 없음 확인** → 새 보안시스템을 만들지 않고 `data_classification="production"` 경로(Safe Mode 불필요)로 우회 없이 재설계.
5. **DOMAIN_GATE_NOT_READY 발견**: `content_filter.py`가 AI_CONTENT 도메인(aijomoojin)을 "Domain Gate 미구현"으로 영구 하드블록하고 있었음(의도된 설계, 주석에 우회금지 명시) — GPT 검수 승인 후 **AI_CONTENT Gate v0** 구현(Gemini `finish_reason` REUSE + Sourcebook source_url 존재 + account/persona 일치 5조건, 신규 외부부품·키워드엔진 0개), 15개 신규 테스트 + 기존 3개 테스트 갱신, 32/32 PASS, 기존 baseline(6개 무관 실패) 회귀 0건.
6. **실행**: Airtable production 분류 Record 1건 생성 → 관리자 2회 재시작(Flag+코드 반영) → 자동 실행 1차 시도 media_publish HTTP 400(컨테이너는 FINISHED, 원인은 응답본문 미저장으로 불명) → 회장 승인 후 동일 creation_id로 media_publish 재호출(신규 컨테이너 생성 아님, 중복게시 아님) → **HTTP 200, media_id 확보**.

## 남은 미결 항목(다음 세션)
- `.env`의 `AIJOMOOJIN_BINDING_ADAPTER_ENABLED=true`가 현재 Live에 적용된 상태 — "매일 08:00 ICT·하루 1건" 정식 운영 전환 여부는 별도 결정 필요.
- Step6B Delta(`publish_ledger.py`/`aijomoojin_scheduled_publish_job.py`/`image_hosting.upload_local_file_to_imgbb`/`fetch_due_scheduled_post`)는 실제 성공 경로에 쓰이지 않음 — 재승인 또는 폐기 결정 필요.
- `.env`의 `CANARY_SAFE_MODE`/`CANARY_RUN_ID`/`CANARY_EXPIRES_AT` 3줄은 무효(파일 기반 정책이 우선)로 잔존 — DEFER 유지.
- 이번 세션 전체 코드 변경(Gate v0, T1 Adapter, Step6B Delta 포함) **Commit·Push 0건** — 전부 미승인 상태로 세션 종료.

---

# 2026-08-01 14:45 ICT — Step 4 SUCCESS / APPROVED — T1 Persona 조회 승인, Adapter 다음구현 허용(회장 최종 승인)

_기록 시각: 2026-08-01 14:45 ICT · 상태: **Step 4 SUCCESS/APPROVED**(회장 최종 승인) — T1 Account Binding 중 Persona 조회 부분(신규 메서드+전용 테스트)만 승인·보존, 나머지는 다음 단계 구현 허용범위로 확정. 이 항목이 최신 상태이며, 아래 260801 12:30(Step 3 종료) 이하는 이전 기록으로 보존._

## 회장 최종 승인 범위
- 보존: `modules/infra/airtable_repository.py`의 신규 Persona 조회 메서드(`get_active_persona_by_account_code_v2`) + 전용 테스트(`tests/test_airtable_repository_persona_binding.py`).
- 다음 구현 허용범위: aijomoojin 전용 Binding Adapter 1개, 확인된 Active Caller 연결부, 전용 테스트.
- 금지: 기존 DM 핵심함수·기존 게시 핵심함수(`publish_single()` 등)·다른 계정 경로 변경.
- Rollback 범위: 이번 신규 hunk·신규 파일·연결 import/call만 원복(전체 checkout 금지).
- 신규 부품 도입 순서: `REUSE → ADOPT → ADAPT → BUILD` — 공식·OSS 후보 3개 비교 후 부적합할 때만 최소 Glue Code 작성.
- 기존 Token·계정·Airtable·실게시 Evidence는 `PASS_REUSED` — 재검증 금지.

## 상태
Step 4(T1 범위): SUCCESS/APPROVED. 코드 구현은 이 기록 시점까지 시작 안 함(문서 기록만).

---

# 2026-08-01 12:30 ICT — Step 3 종료(SUCCESS/CLOSED) — 남은 4개 기술 Gate Step 4 이관(회장 승인)

_기록 시각: 2026-08-01 12:30 ICT · 상태: **Step 3 SUCCESS/CLOSED(회장 최종 승인)** — Obsidian Content OS MVP Architecture 조사·Scope 확정 단계 종료, T1~T4는 해결완료 아닌 Step 4 구현·검증 Gate로 명시 이관. 이 항목이 최신 상태이며, 아래 260801 11:59(MVP Scope 확정) 이하는 이전 기록으로 보존._

## 회장 최종 승인 결정
- Step 3(Architecture 조사·Scope 확정)을 종료한다.
- 현재 MVP Sourcebook(입력): `docs/design/SNS_AI_STARTUP_CONTENT_SOURCEBOOK_260723.md`
- 현재 Output: `vault/content`, `vault/images`
- Obsidian Vault Runtime 연결·Automation Input은 현재 MVP OUT_OF_SCOPE 유지(Critical UNKNOWN 아님).
- Obsidian 중심 Content OS 장기 목표는 폐기하지 않으며, 별도 Scope·Approval·Canary Gate로 재개한다.
- 남은 4개 기술항목은 Step 3 미해결 방치가 아니라 **Step 4 구현·검증 Gate로 명시 이관**한다(해결 완료 아님, Step 4 진입을 위한 확정된 작업범위).

## Step 4로 이관된 기술 Gate(해결 완료 아님)
- T1 Account Binding Gate — IDN-000036/@aijomoojin/IG User ID/credential_key=AI/Persona PER-002 게시직전 Fail-closed, 실Meta username 대조는 Live Canary 전 검증.
- T2 Receipt Gate — Post ID 영속, Airtable 실패시 RECEIPT_SYNC_PENDING, Receipt만 재시도(Instagram 재호출 0), 완료후 PUBLISHED 전이.
- T3 Publish Ledger Gate — unique_publish_key 중복차단, Atomic Reserve(BEGIN IMMEDIATE), version/fencing, UNKNOWN 자동재게시 금지, Crash·동시실행·재시작 검증.
- T4 R6·R8 Test Isolation Gate — runtime_boot_policy.json 의존성 격리(policy_path Fixture), 핵심 Assertion 실행, 제품로직 PASS/FAIL과 환경결함 분리.

## 상태 구분
Step 3 공식 상태: SUCCESS/CLOSED. Step 4 Entry: READY(구현은 아직 시작 안 함). T1~T4는 Step 4의 확정된 작업범위이며 현재 해결 완료 아님.

---

# 2026-08-01 11:59 ICT — Obsidian Content OS MVP Scope 확정(회장 결정) — 문서 기록

_기록 시각: 2026-08-01 11:59 ICT · 상태: **회장이 현재 MVP 입력·출력·OUT_OF_SCOPE 범위를 확정**(코드·Runtime 변경 없음, 문서 기록만). 이 항목이 최신 상태이며, 아래 260731 16:37(Track B-5/B-6/B-6R) 이하는 이전 기록으로 보존._

## 회장 확정 결정(이번 세션)
- **현재 MVP 입력**: `docs/design/SNS_AI_STARTUP_CONTENT_SOURCEBOOK_260723.md`(기존 Sourcebook 그대로 사용).
- **현재 MVP 출력**: `vault/content`(Caption·Metadata), `vault/images`(Image) — 기존 Track B-5/B-6 산출물 경로 그대로 재사용.
- **현재 MVP OUT_OF_SCOPE**(회장 확정, 실패조건 아님): Obsidian Vault Runtime 연결 / Automation Input / Obsidian Git / git archive / Allowlist Manifest / Daily Journal·Life OS·Finance 개인정보 Canary.
- **장기 방향**: Obsidian 중심 Content OS 목표는 폐기하지 않는다 — 현재 MVP 성공 이후 별도 승인 단계에서 재개한다.
- **Scope Drift 교정**: 위 OUT_OF_SCOPE 항목은 현재 Step 3의 Critical UNKNOWN 또는 실패조건으로 계산하지 않는다.
- R5(`content_package_builder.py`) 판정은 기존 ADAPT 상태 그대로 유지 — 이번 결정으로 재판정하지 않음.
- Account Binding·Airtable Receipt·Publish Ledger·SQLite concurrency/fencing·R6·R8 테스트 격리는 이 Scope 확정과 별개의 미해결 기술 Gate로 유지.

## 근거
회장 채팅 지시(2026-08-01 세션) — Claude Code Read-only 조사(Step 3 REVISE) 결과 제출 이후 회장이 직접 MVP Scope를 위와 같이 확정. 코드·Runtime·Airtable 변경 0건, 이 세션은 문서 기록만 수행.

---

# 2026-07-31 16:37 ICT — Track B-5/B-6/B-6R 완료 + CLAUDE.md Objective Lock 규칙 추가 — 세션 종료 인계

_기록 시각: 2026-07-31 16:37 ICT · 상태: **Track B 0~10 순서표 중 5~6단계 SUCCESS**(B-6R은 6단계에 대한 Build-vs-Buy-vs-Reuse 재검증, 7단계 이후 미착수). 이 항목이 최신 상태이며, 아래 260731 17:10(Track B 2~4) 이하는 이전 기록으로 보존._

## 완료 FACT(이번 세션)
- **Track B-5**(Obsidian Vault 데이터 계약): `vault/content/`, `vault/images/` 생성, `.gitignore`에 `vault/` 추가(git 비추적, `db`/`logs`/`backup`과 동일 패턴). Frontmatter 계약 확정(`content_id`/`topic_id`/`title`/`source_url`/`claims`/`status`/`caption`/`image_path`/`created_at`/`channel_status`).
- **Track B-6**(`modules/sns/content_package_builder.py`, 신규): 기존 Track B-1~4(select_next_topic/generate_hook_caption/build_visual_brief+build_image_prompt/generate_image)를 순서대로 호출하는 조립 코드. 회장 승인 수정조건 7개 전부 반영 — 이미지 실패 시 `.md`/`.png` 둘 다 저장 안 함(draft_text_only 폐기, source_url 재시도 가능하게 유지) / Atomic Write(임시파일+`os.replace`, 부분파일 0건 테스트로 확인) / `content_id = topic_id(.→-)+날짜+sha256(source_url)[:8]`(stdlib만, 외부 의존성 0) / Frontmatter는 `json.dumps()`로 YAML-safe 인코딩(PyYAML 미설치) / Vault 스캔은 `status: complete`만 인정, 파싱 실패 시 `VaultScanError`로 즉시 중단. 신규 테스트(`tests/test_content_package_builder.py`) 9/9 PASS, 관련 회귀(source_selector+visual_brief+image_provider_cloudflare 포함) 39/39 PASS. Track B-1~4 기존 파일 diff 0건.
- **Track B-6R**(Build-vs-Buy-vs-Reuse 재검토): python-frontmatter(MIT, 관리양호)·atomicwrites·obsidian-git(MIT, 관리 매우양호)·webpub·naver-blog-xmlrpc(비공식) 등 외부 후보 조사 — python-frontmatter는 PyYAML 강제 의존이 회장의 "PyYAML 설치 금지" 지침과 충돌해 REJECT(회장 재확인), atomicwrites/webpub은 이미 구현된 stdlib 패턴과 동등하거나 범위 과잉이라 REJECT, obsidian-git은 ADOPT 후보(회장 Obsidian 앱에 직접 설치, Python 코드 무관)이나 설치 가이드는 "나중에"로 보류. naver-blog-xmlrpc는 공식 API 부재 확인 + ToS 위험으로 REJECT(Browser Automation HOLD 유지 근거 강화). **최종 결정: `content_package_builder.py`+테스트 HOLD 해제, 현재 구현 그대로 채택.**
- CLAUDE.md에 "단계 시작 전 Objective Lock 프리앰블"(최종목적/현재단계·작업/Success Criteria/금지·HOLD범위, 4줄) 규칙 신규 추가 — 회장 채팅 지시(3줄) + 같은 날 `docs/gpt 업무지침서_260731_0731pm.txt`(회장 개인 참고자료, 통합 금지 확정) 대조로 4줄 버전 채택.
- 전체 프로젝트 백업 `C:\backup_(18)_260731_1432_SNS_24AutoProject_260511.zip`(22.8MB, 4218 entries, 무결성 확인) — `.venv`(677MB, 재설치 가능)/`db`(락)/`logs`(락) 제외.

## 발견(미해결, 다음 세션 우선 확인 대상)
전체 `tests/` 실행 시 **95 failed / 8 collection error** 관찰(`C:\ProgramData\SNS_24AutoProject\runtime_boot_policy.json` PermissionError로 보임, Root Cause는 Hypothesis). **주의**: `docs/VALIDATION_STATUS.md`의 `instagram_provider_routing_design_260725` 항목에는 그 시점 전체 회귀가 "557 passed/**5 failed**(기존 무관 baseline: test_dm_close.py 4 + test_review_grid_ui.py flaky 1)/3 xfailed"로 문서화되어 있어, 이번 세션의 95 failed는 그 baseline(5)과 크게 다르다 — **"기존 환경 문제"로 단정하지 말 것**, Track B-6 신규 파일 제외 상태에서도 재현되는지, 그리고 baseline 기록 시점 이후 무엇이 바뀌었는지 다음 세션에서 반드시 먼저 확인.

## 현재 상태
`IDN-000036`(aijomoojin)은 여전히 `DOMAIN_GATE_NOT_READY`로 Fail-closed — 무인게시 불가 그대로. Track B-7(블로그·SNS용 변환, Draft Canary) 미착수. 회장이 제기한 "Obsidian을 제2두뇌·1000 페르소나 원천으로" 쓰는 더 큰 그림(`Multi-AI Operating Charter v1.0`, GPT 초안)은 논의만 됐고 Architecture 확정·Claude Code 실행 없음 — Charter 자체 순서(Section 5)상 Claude Code 차례가 아직 오지 않음.

## 다음 세션 시작 시 확인할 것
1. 이 문서(최상단) + `git status`/`git log`
2. 위 "전체 테스트 95 failed" 발견 — 문서화된 Baseline(5 failed) 대비 회귀인지 우선 확인(추정 금지)
3. Track B-7 착수는 회장 승인·Architecture 확정 이후에만
4. Push 여부: 이번 세션 Commit·Push 전혀 없음(재확인 필요)

---

# 2026-07-31 17:10 ICT — Track B 2~4(Source Pipeline/후킹카피/이미지생성) 완료 — 세션 종료 인계

_기록 시각: 2026-07-31 17:10 ICT · 상태: **Track B 0~10 순서표(260731 06:38 확정판) 중 0~3단계 SUCCESS**(4~10단계 미착수, Track B 전체 Close Gate 아님). 이 항목이 최신 상태이며, 아래 260731 11:31(Track B-1) 이하는 이전 기록으로 보존._

## 완료 FACT(이번 세션 후반)
- **Source Pipeline**(`modules/sns/source_selector.py`, commit `85456bf`): `docs/design/SNS_AI_STARTUP_CONTENT_SOURCEBOOK_260723.md`을 섹션 단위로 파싱해 topic_id/title/status/source_url/core_message/prohibited_expression 추출. HOLD 상태·URL공란·core_message공란 항목은 Fail-closed 제외 — 실제 13개 항목 중 5개(3.1~3.5)만 선택 가능. source_url 기준 중복 방지. 10/10 PASS.
- **후킹 카피 생성**(`caption_generator.py::generate_hook_caption()`, commit `bb8b2e0`): 기존 Gemini client/throttle/재시도 REUSE, core_message 밖 사실 생성 금지 프롬프트 제약. 6/6 PASS(mock).
- **이미지 자동생성**(`visual_brief.py`+`image_provider_cloudflare.py`, commit `320984c`): Cloudflare Workers AI(FLUX.1-schnell, 무료 10,000 neurons/일) Provider 채택 — 공식 문서로 상업이용·무료한도 확인(Gemini Imagen 계열은 무료 없음+로컬 SDK 예제 모델명이 이미 폐기된 걸 발견해 기각). SQLite로 하루 3장 상한 영속(Fail-closed). **실제 이미지 3장 생성 성공**(Canary #1~#3, 회장 육안검수 완료) — Canary #1에서 Netflix 로고·일본어 텍스트 노출 발견 → 근본원인(Cloudflare FLUX.1-schnell은 negative_prompt 미지원, 공식문서 확인) 특정 → v2 프롬프트(안전지시를 전부 positive prompt로 이동, 브랜드명 명시 회피)로 수정 후 Canary #2/#3 재검증. 20/20 PASS(mock, 실제 API 호출 없음).
- 3개 커밋 전부 push 완료(`aa7caf5..320984c`).

## Track B 순서표 갱신(260731 06:38 확정판 기준)
| 순서 | 작업 | 상태 |
|---:|---|---|
| 0 | Baseline 확인 | ✅ |
| 1 | 계정별 콘텐츠 필터 분리 | ✅ commit `99d96b2` |
| 2 | 후킹 카피 자동생성 | ✅ commit `85456bf`(Source Pipeline, 이 표엔 없었으나 2단계 선행 작업으로 실제 수행됨)+`bb8b2e0`(캡션) |
| 3 | 이미지 자동생성 | ✅ commit `320984c` — Cloudflare FLUX.1-schnell, 하루 3장 상한 |
| 4 | 자동 품질검수 | 미착수 — **다음 세션 시작 지점** |
| 5 | 무인 승인 정책 | 미착수 |
| 6 | 기존 게시 파이프라인 연결 | 미착수 |
| 7 | 무인 Soak | 미착수 |
| 8 | Track B Close Gate | 미착수(4~7 선행 필요) |
| 9 | Comment Provider Routing | 미착수 |
| 10 | 11단계 | 미착수 |

**표기 불일치 메모(다음 세션 참고)**: 이 표(260731 06:38 확정판)에는 "Source Pipeline"이 별도 행으로 없어서, 실제로는 2단계(후킹카피) 착수 전 선행작업으로 함께 수행됨 — 세션 중 "Track B-2/3/4"라는 별도 넘버링(제 편의상 명칭, source_selector→caption→image 순서)도 혼용됐음. 다음 세션은 이 표(0~10)를 SSOT로 삼는다.

## 부가 산출물(코드 아님)
- "새글" 대화형 트리거(회장 인수인계, Codex 수동운영 대체) — 실사례형(케이스스터디) 콘텐츠, Track B 자동화와 별개 트랙, 코드화 안 함. 상세는 memory `feedback_new_post_trigger_phrase.md`.

## 현재 상태
`IDN-000036`(aijomoojin)은 여전히 `DOMAIN_GATE_NOT_READY`로 Fail-closed — **무인게시 불가 그대로**(4단계 자동품질검수 구현 전까지 유지, 의도된 상태). `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID`가 `.env`에 신규 설정됨(값 미기록). 오늘 이미지 생성 쿼터 3/3 소진(내일 UTC 00:00 리셋).

## 다음 세션 시작 시 확인할 것
1. 이 문서(최상단) + `git status`/`git log`
2. 다음 작업은 Track B 순서 4(자동 품질검수) — 출처·금칙어·중복·허위주장 차단 Design Memo부터 시작(신규 코드 바로 작성 금지)
3. Push 여부는 이미 완료 확인됨(재확인만)

---

# 2026-07-31 11:31 ICT — Track B-1(계정별 콘텐츠 필터 분리) 완료 — 세션 진행 중 인계

_기록 시각: 2026-07-31 11:31 ICT · 상태: **Track B 0~14단계 중 1단계 SUCCESS**(Track B 전체 Close Gate 아님, 2~7단계 미착수). 이 항목이 최신 상태이며, 아래 260731 06:26(10.6 Close Gate) 이하는 이전 기록으로 보존._

## 완료 FACT
`launcher/main.py`의 발행 직전 텍스트 Gate가 계정 무관하게 yuna 도매 키워드만 요구하던 구조적 결함(ERR-099)을 Track B 착수 전 사전 발견 → `resolve_publish_gate()`(Global Safety→Domain Routing→Domain Gate) 신규 구현, Identity(공란/미등록/Kill Switch)는 `launcher/main.py` 소유로 Router보다 항상 우선 실행(GPT Adversarial Review 3라운드 거쳐 확정). 상세는 `porting_logs/MERGE_JOURNAL.md`(260731 11:31 항목)·`docs/VALIDATION_STATUS.md`(`track_b_1_account_content_gate_260731`)·`docs/ERROR_DATABASE.md`(ERR-099)·`docs/FAILURE_PATTERN.md`(FP-072) 참조.

## Track B 순서표 갱신 (0번 표 기준, 1번 완료로 갱신)
| 순서 | 작업 | 상태 |
|---:|---|---|
| 0 | Baseline 확인 | ✅ |
| 1 | 계정별 콘텐츠 필터 분리 | ✅ 260731 완료(commit `99d96b2`) — `IDN-000041→PRODUCT`/`IDN-000036→AI_CONTENT`, 미등록·공란은 `IDENTITY_REJECTED` |
| 2 | 후킹 카피 자동생성 | 미착수 |
| 3 | 이미지 자동생성 | 미착수 |
| 4 | 자동 품질검수 | 미착수 |
| 5 | 무인 승인 정책 | 미착수 |
| 6 | 기존 게시 파이프라인 연결 | 미착수 |
| 7 | 무인 Soak | 미착수 |
| 8 | Track B Close Gate | 미착수(2~7 선행 필요) |
| 9 | Comment Provider Routing | 미착수 |
| 10 | 11단계 | 미착수 |

## 현재 상태
`IDN-000036`(aijomoojin)은 여전히 `DOMAIN_GATE_NOT_READY`로 Fail-closed — **무인게시 불가 그대로**(의도된 상태, 4단계 자동품질검수 구현 전까지 유지). Commit `99d96b2` push 완료(11:45 ICT), 인접 Red Baseline 3개 파일은 HOLD(오늘 변경과 무관, A/B로 확인).

## 다음 세션 시작 시 확인할 것
1. 이 문서(최상단) + `git status`/`git log`
2. 다음 작업은 Track B 순서 2(후킹 카피 자동생성) — Design Memo부터 시작(신규 코드 바로 작성 금지, 지금까지의 Gate 절차 동일 적용)
3. Push 여부는 이미 완료 확인됨(재확인만)

---

# 2026-07-31 06:26 ICT — 10.6단계 Close Gate SUCCESS 선언(GPT 최종 검수 승인) — 세션 종료 인계

_기록 시각: 2026-07-31 06:26 ICT · 상태: **10.6단계 SUCCESS/Closed(회장·GPT 확정)** — SUCCESS 기준 12개 항목 전부 Runtime Evidence로 충족. 이 항목이 최신 상태이며, 아래 260730 18:23 이하는 이 세션의 진행 기록으로 보존._

## Close Gate 판정 경위
1차 요약 제출 시 GPT가 "#8(중복·오발송 0건) 수정 후 라이브 재검증 없음, 테스트로만 대체 불가"로 **PARTIAL** 판정 → 11단계 착수 HOLD 확정, 우선순위를 "Persona 중복방지 라이브 재검증 → Close Gate 재판정"으로 명확히 지정. 통제된 Canary 설계(대상/횟수/간격/중단기준/증거위치 사전 제출 후 승인) → 실행 → **실제 4건 연속 문의 중 발송 정확히 1건, 나머지 3건 dedup 차단 확인**(10.6-6A) → GPT 재검수 **SUCCESS 12/12 확정(260731 06:26)**.

## 10.6 SUCCESS 12개 항목 최종 상태
전부 PASS — 상세 근거는 `docs/VALIDATION_STATUS.md`(`kpi_canary_exclusion_reimplement_260731`/`persona_dedup_postfix_runtime_gate_260731`/`10_6_close_gate_success_260731` 행) 참조.

## 오늘 세션 전체 요약(260730 오후~260731 새벽)
- Publishing Soak SUCCESS, 승인 없는 Scope 이탈 1건 발생 후 완전 원복(ERR-095/FP-068)
- Account-level `reply_mode` + Observability 신규 기능(Airtable Schema 6필드 승인)
- 오래된 회귀테스트 3건 무력화 발견·복구(ERR-096/FP-069)
- Persona 실측 SUCCESS + 중복발송 경합조건 발견·수정·**라이브 재검증까지 완료**(ERR-097/FP-070)
- retry_queue 6개 핸들러 재시작 생존성 결함 발견·수정(ERR-098/FP-071)
- KPI Canary 오염 재해결(ERR-095 후속, Scope 안에서 재구현)
- **10.6단계 Close Gate SUCCESS 선언**

## Commit 이력(이 세션, 최신 커밋까지)
`68172d6`~`6304172`(9개, 이미 push 완료) + 이번 Close Gate 문서화 커밋(다음).

## Track 상태 — 260731 06:38 ICT 회장이 우선순위 재확정(정정)
GPT가 Close Gate 검수 때 제안했던 "Comment Routing → 11단계 → Track B" 순서는 **회장이 아래로 대체 확정**:

**확정 순서: Track B 단일계정 무인게시 완성 → 안정성 Soak → 11단계 3계정 확장**

| 순서 | 작업 | 완료 기준 |
|---:|---|---|
| 0 | Baseline 확인 | HEAD·origin `0/0`·Working Tree 상태 확인 |
| 1 | 계정별 콘텐츠 필터 분리 | yuna 도매 경로 회귀 0건 |
| 2 | 후킹 카피 자동생성 | Sourcebook 기반 초안 품질 기준 통과 |
| 3 | 이미지 자동생성 | 비용·쿼터·품질 Canary 통과 |
| 4 | 자동 품질검수 | 출처·금칙어·중복·허위 주장 차단 |
| 5 | 무인 승인 정책 | 기준 통과 시 `draft→ready` 자동 전환 |
| 6 | 기존 게시 파이프라인 연결 | `IDN-000036` 자동 게시 성공 |
| 7 | 무인 Soak | 반복 게시 중 중복·오계정·유실 0건 |
| 8 | Track B Close Gate | 사람 개입 없이 수집→생성→게시 증명 |
| 9 | Comment Provider Routing | 3계정 확장 전 다계정 댓글 경로 확보 |
| 10 | 11단계 | 1계정→3계정 Canary 확장 |

**핵심 결정(회장)**: 사람 승인 단계는 개발 초기 Canary에만 유지 — 최종 Track B 성공 기준은 **자동 품질검수 통과 후 무인게시**(사람이 매번 승인하는 구조가 아님).

**RISK(회장 명시)**: 생성 기능만 만들고 자동 승인·중복방지·비용 제한을 빼면 "콘텐츠 생성기"일 뿐 무인게시 시스템이 아니다 — 5(무인 승인 정책)·7(무인 Soak)을 건너뛰고 8(Close Gate)로 가면 안 됨.

**Comment Provider Routing**은 폐기되지 않고 순서 9번으로 유지(11단계 3계정 확장 전 선행조건이라는 논리는 그대로, 다만 Track B 뒤로 재배치됨).

## 다음 세션 시작 시 확인할 것
1. 이 문서(최상단) + `git status`/`git log`
2. **다음 세션 첫 작업은 신규 코드 작성이 아니라 `Track B-0: 무인게시 Scope·성공 기준 Read-only 확정`이다** — 회장이 명시적으로 "신규 코드 작성부터 시작하면 안 된다"고 지정.
3. Push 여부 확인(이번 커밋 포함)

---

# 2026-07-30 18:23 ICT — 10.6 Track A(aijomoojin Publishing Soak) 세션 종료 인계

_기록 시각: 2026-07-30 18:23 ICT · 상태: **10.6 Track A 진행중(오늘 세션 다수 항목 SUCCESS, Close Gate는 아직)** — 마스터 Critical Path 10개 중 완료 6개/부분 2개/미완료 2개(신규기능 영역, HOLD). 이 항목이 최신 상태이며, 아래 260730 19:53(10.5 Close Gate) 이하는 이전 세션 기록으로 보존._

## 기준점
- Active Root `C:\SNS_24AutoProject_260511` / Branch `master` / HEAD는 이 세션 커밋 8개 반영 후 `9570a7c`(2026-07-30 세션 시작 시점 HEAD `711ca34`에서 진행)
- **Push 미실행** — 오늘 커밋 8개 전부 로컬에만 존재, 다음 세션 시작 시 push 여부 확인 필요
- 10.5단계는 여전히 Closed Gate(재조사 안 함)

## 오늘(260730 오후~저녁) 완료 FACT
1. **Publishing Soak SUCCESS**: aijomoojin 실제 게시 1건(`ig_media_id=18106786787117918`). 계정/Credential 교차오염 0건 코드 확인.
2. **승인 없는 Scope 이탈 사고 + 완전 원복**(ERR-095/FP-068): Publishing Soak 도중 공용 `kpi_collector.py`를 승인 오해로 수정 → 회장이 Scope 이탈로 판정 → `git checkout`으로 전량 원복, 문서화.
3. **Account-level reply_mode + Observability 신규 기능**(commit `68172d6`): `Account_Registry.reply_mode`(template/persona/disabled) + `Lead_Interactions` Observability 필드 6개(Airtable Schema Write 승인됨, 본문 미저장). `dm_auto_reply.py::handle_price_inquiry()`가 전역 `PRICE_AUTO_REPLY_ENABLED` 대신 계정별 값 우선 사용, 공란/실패 시 기존 동작 100% fallback.
4. **오래된 회귀테스트 3건 무력화 발견·복구**(commit `bcf6c70`, ERR-096/FP-069): `test_dm_rules.py`의 mock이 `ae2bec2`(같은 세션 초반 커밋)의 시그니처 변경을 반영 못 해 몇 시간째 조용히 실패 중이었음.
5. **Persona 실측 SUCCESS**: `reply_mode=persona` 설정 후 실제 DM으로 종단간 확인 — `Lead_Interactions` Observability로 `reply_mode_used=persona`/`persona_code_ref=PER-002`/`persona_check_pass=true` 확인, 실제 Instagram 발송.
6. **Persona 경합조건 발견·수정**(commit `efb85fe`, ERR-097/FP-070): 실측 도중 동일 문의가 4회 중복 발송되는 것을 실제로 목격 — `generate_reply()` 처리 중(수십 초) 후속 문의가 Airtable 쿼리 기반 dedup을 통과하던 구조적 결함(260713 Gate C 설계 이후 처음 실제 트래픽을 받아 노출). `_PERSONA_REPLY_DEDUP`(즉시 선점) 신설.
7. **retry_queue 재시작 생존성 결함 발견·수정**(commit `f8bee58`, ERR-098/FP-071): Operations Soak 중 `lead_update_score` dead 작업 30건 발견 — `comment_airtable_record`(FP-047)만 적용됐던 즉시등록 패턴이 나머지 6개 핸들러엔 없었음. 6개 전부 이관, launcher 시작 시 즉시등록.
8. **회장 재시작 2회 + Runtime 검증**: 매 코드변경마다 `Restart-Service SNS_Watchdog` + pytest 재실행으로 확인(72 passed 최종). retry_queue 수정은 재시작 후 로그로 "no handler" 오류 소멸 직접 확인.

## Track 상태
- **Track A(aijomoojin 단일계정 안정성 증명)**: Critical Path 10개 중 완료 6개(게시/DM/팔로업/Persona/Airtable저장/계정격리) + 부분 2개(retry_queue는 오늘 해결, Scheduler 지속관찰은 세션 내내 크래시 0건이나 정식 "기간" 관찰은 계속 필요) + 미완료 2개(콘텐츠수집·댓글, 아래 HOLD).
- **Comment(댓글 처리)**: `comment_poller.py`가 전역 yuna 토큰+facebook host 하드코딩, 계정별 라우팅 전무 — 구조적 미지원으로 격리, BUILD는 HOLD(GPT 결정).
- **Track B(aijomoojin 콘텐츠 자동화)**: 후킹카피 생성(BUILD 후보, Gemini client 패턴 REUSE)/이미지 생성(BUY 후보, 같은 Gemini SDK로 `generate_images` 존재 확인) 설계만 완료, 착수 안 함. `CANARY-FB-*`류 KPI 미분리 문제도 별도 HOLD.

## Commit 이력(이 세션, 전부 push 미실행)
`68172d6` reply_mode+Observability → `bcf6c70` mock 수정(ERR-096) → `efb85fe` persona race fix(ERR-097) → `9fd824c` docs → `f8bee58` retry eager reg(ERR-098) → `9570a7c` docs.
(정확한 순서·해시는 `git log --oneline -8` 재확인 권장)

## 다음 세션 시작 시 확인할 것
1. 이 문서(최상단) + `porting_logs/MERGE_JOURNAL.md`(tail) + `git status`/`git log`
2. **Push 여부 결정** — 오늘 커밋 8개 로컬에만 존재
3. 10.6 Close Gate 도달 여부는 Scheduler 지속관찰 기간을 회장이 얼마나 요구하는지에 달림 — 재소환 시 확인
4. Track B(콘텐츠 자동화) 착수는 10.6 Close Gate 이후로 계속 보류 중

---

# 2026-07-30 19:53 ICT — 10.5단계 Close Gate SUCCESS 선언(GPT 3차 재판정 최종 승인) — 세션 종료 인계

_기록 시각: 2026-07-30 19:53 ICT · 상태: **10.5단계 SUCCESS(회장/GPT 확정)** — 마스터 우선순위 9개 중 0~6번 완료(2~6번은 이 세션에서 처리), 7번(ERR-090)은 회장 결정으로 Scope 제외, 8번(Close Gate)은 GPT가 260730 19:48 ICT SUCCESS로 최종 판정. 9번(11단계 검토)은 착수하지 않음(회장 별도 승인 대상). 이 항목이 최신 상태이며, 아래 260730 18:57 이전 항목들은 이 세션 진행 기록으로 보존._

## 최종 완료 FACT(이 세션 전체 요약)
- **DM Routing Close Gate SUCCESS**(commit `8e90402`, ERR-091/FP-065) — fallback-gate 구현+mock 13 passed+실제 aijomoojin 가격문의 DM Runtime Canary.
- **댓글 Routing SUCCESS**(commit `0c085b9`, ERR-092/FP-066) — instagram_login Private Reply 구조적 불가 발견·차단, mock 53 passed.
- **팔로업 Routing SUCCESS**(위 commit 포함 + 이번 세션 실측 Canary) — DM과 동일 Resolver REUSE, `PRICE_AUTO_REPLY_ENABLED=false`로 자연 발생 대상 없어 통제된 방식(`tools/run_followup_routing_canary.py`)으로 aijomoojin 실제 계정 발송 성공 확인(`sent=True`, fallback 0건).
- **Persona 연결 코드 SUCCESS / 콘텐츠 PARTIAL**(commit `8d0ed91`, ERR-093) — Repository+wiring 완료, mock 15/15 passed. 회장 지시로 초안 콘텐츠 2건(PER-001/PER-002) 입력 완료. **30개 페르소나 아바타 일괄 등록은 회장이 별도로 진행 예정**(시점 미정).
- **Integration Validation SUCCESS** — Lead_Interactions/retry_queue/Instagram_Posts 교차오염 0건, 전체 회귀 717 passed(11개 실패 파일 전부 기존 `runtime_boot_policy.json` PermissionError로 수렴, 신규 회귀 0건).
- **신규 발견 ERR-094/FP-067**(OPEN, 비차단) — 시스템 `PYTHONPATH`가 250723(Reference Only)을 가리킴. 라이브 프로세스·pytest는 안전(실측 확인), `tools/`의 향후 일회성 스크립트만 위험. 회장이 별도 환경 무결성 Gate로 처리 예정.
- **GPT 감사 이력(Multi-AI Review Policy)**: 1차 제출 PARTIAL(Persona 테스트 5건 미실행+ERR-090 OPEN) → 보완 후 2차 PARTIAL(팔로업 실측 Canary 누락) → 팔로업 Canary 완료 후 3차 **SUCCESS 최종 승인**.

## Scope 제외/HOLD
- **ERR-090**(YUNA/AI 토큰 노출) — 회장이 "아주 나중에 직접 처리"로 명시 — 10.5 Close Gate 판정에서 공식 제외. OPEN 유지, 재발급 절대 금지(회장 별도 승인 전).
- **ERR-089**(Scheduler Stall 근본원인) — 신규 Evidence 없어 HOLD 유지.
- **ERR-094**(PYTHONPATH→250723) — OPEN, 별도 환경 무결성 Gate 예정(Claude Code 권한 밖, Windows 시스템 설정).

## 다음 세션 시작 시 확인할 것
1. `docs/CURRENT_RUNTIME_CONTEXT.md`(이 문서, 최상단) — 10.5 SUCCESS 확정 상태
2. `git log`— commit `8e90402`/`0c085b9`/`8d0ed91` push 여부 확인(이 세션 종료 시점까지는 미푸시 상태였을 수 있음, 세션 종료 처리에서 확인)
3. **11단계(3계정 확장) 착수는 이 세션에서 결정되지 않았다** — 회장이 명시 승인하기 전까지 시작하지 않는다
4. ERR-090/ERR-094는 각각 회장이 별도 시점에 처리하기로 한 상태 — 다음 세션에서 임의로 재소환하지 않는다(회장이 먼저 꺼내지 않는 한)

---

# 2026-07-30 18:57 ICT — 10.5-5단계(Persona 연결): ERR-093(콘텐츠 0건) 확인 후 Repository+wiring 선구현, 전체 회귀 재확인(11개 파일 모두 기존 원인)

_기록 시각: 2026-07-30 18:57 ICT · 상태: **PARTIAL/IN_PROGRESS** — 댓글 Routing(아래 18:00 항목) SUCCESS 이후 10.5-5단계(Persona 연결) 착수. Persona_Profile 실제 콘텐츠가 없어 코드만 선구현(회장 결정), 콘텐츠 입력은 회장 담당으로 남음. 이 항목이 최신 상태이며, 아래 260730 18:00 항목은 그 이전 기록으로 보존._

## 완료된 FACT(이 세션, 260730 18:57)
- **Persona_Profile 콘텐츠 0건 확인**: Airtable 직접조회 — `Persona_Profile` 레코드 1건(`PER-001`, "엔틱")뿐이고 그마저 `account_code_ref`(Linked Record) 공란·`tone_style`/`greeting_template`/`followup_template` 전부 공란. yuna18253/aijomoojin 둘 다 `Account_Registry.Persona_Profile` 링크 공란 — 어느 계정에도 연결된 Persona 없음(ERR-093).
- **회장 결정(선택형)**: 콘텐츠 입력 전에 코드부터 구현 — 지금은 빈 값이라 기존 동작과 100% 동일, 회장이 나중에 Airtable만 채우면 바로 반영.
- **구현**: `get_persona_by_account_code()`(Repository, Linked Record 역조회 — 필드타입 실측 확인 후 구현) + `dm_auto_reply.py::_get_persona_kwargs()`로 `generate_reply()` 호출에 실제 배선. Fail-open(조회 실패/미연결/inactive는 전부 빈 문자열).
- **전체 회귀 재확인, 중요 정정**: 이전 두 항목(DM/댓글)에서 "실패 파일 4개, 기존 baseline과 동일"이라 보고했던 것이 `tail -25` 출력 절단으로 인한 불완전 확인이었음을 이번에 전체 `grep`으로 발견 — 실제로는 **11개 파일**이 실패하지만, 5개 파일을 직접 표본 재현(`test_meta_graph_version.py`/`test_dome_export_batch_isolation.py`/`test_package_b_post_attribution.py`/`test_package_s5_write_budget_idempotency.py` 등)한 결과 **전부 동일하게 `runtime_boot_policy.json` PermissionError**(이 세션 환경의 기존 제약, 오늘 코드와 무관)로 수렴함을 확인 — **신규 회귀 0건 결론 자체는 유지**. 717 passed / 93~96 failed(재실행 간 소폭 변동) / 3 xfailed / 7 errors.

## 남은 UNKNOWN
- Persona_Profile 실제 콘텐츠(tone_style/greeting_template/followup_template) 입력 담당·시점 — 여전히 회장 담당, 미정.
- `test_dm_persona_kwargs.py`(신규 5개)는 이 세션 환경 제약으로 미실행 — 회장 터미널 확인 필요.

## 다음 정확한 단계
문서화·commit 승인 대기 → 이후 6번(Integration Validation) 착수.

## 다음 단계 승인 필요 여부
필요 — 문서화·commit은 코드 구현 승인과 별개 게이트.

---

# 2026-07-30 18:00 ICT — 10.5-6단계(댓글 Routing): ERR-092/FP-066 발견·해결, aijomoojin 댓글 캠페인 0건 확인

_기록 시각: 2026-07-30 18:00 ICT · 상태: **PARTIAL/IN_PROGRESS** — DM Routing Close Gate(아래 17:36 항목) 완료 후 10.5-6단계(댓글 Routing) 착수, 설계 전제 재검토로 새 구조적 한계 발견·해결까지 완료. 이 항목이 최신 상태이며, 아래 260730 17:36 항목은 그 이전 기록으로 보존._

## 완료된 FACT(이 세션, 260730 18:00)
- **지난 세션 설계 전제 파기 확인**: "`media_id`→`account_code_ref` 역조회 1단계만 추가하면 DM의 `_resolve_dm_send_target()` 그대로 REUSE 가능"이라던 계획이 실제로는 성립하지 않음을 발견 — 라이브 댓글 자동응답이 유일하게 쓰는 `reply_privately_to_comment()`(Private Reply)는 Meta 공식문서상 **Facebook Page 연동이 필수**(WebFetch로 재확인)인데, aijomoojin(instagram_login)은 Facebook Page 자체가 없어 자격증명을 아무리 정확히 골라도 이 API 자체를 호출할 방법이 없음(ERR-092). 대안인 공개 답글(`reply_to_comment()`)은 Instagram API with Instagram Login에서 지원되지만, 260714 Gate G 이후 "손님을 DM으로 유도" 목적으로 라이브 경로에서 이미 미사용(죽은 코드).
- **회장 결정(선택형 질문)**: 지금은 yuna18253만 범위, instagram_login 계정은 Private Reply를 시도 자체를 하지 않고 스킵(공개 답글 전환 등 대안은 별도 논의) — 리뷰는 DM 때와 동일하게 회장 직접승인으로 진행(Codex/GPT 정식 리뷰 생략).
- **구현 완료**: 신규 Repository `get_account_code_ref_by_media_id()`(`repository_interface.py`+`airtable_repository.py`) + `comment_auto_reply.py::_is_private_reply_supported()` 헬퍼로 `_try_private_reply()`에 게이트 추가. 레거시(계정 미태깅)·facebook_login은 Fail-open으로 기존 동작 100% 유지.
- **중요 발견**: `configs/comment_campaign_posts.json`의 등록 캠페인 게시물 6개를 Airtable 직접 조회 — **전부 `account_code_ref` 공란**(260714~15 생성, 다계정 이전 데이터). 즉 지금 이 순간 aijomoojin 소유 댓글 캠페인은 0건이라, 이번 발견은 실제 장애가 아니라 **향후 aijomoojin 댓글 캠페인이 등록되는 순간 발생했을 잠재 위험을 사전 차단**한 것.
- **검증**: mock 단위테스트 신규 16개(`tests/test_get_account_code_ref_by_media_id.py` 8 + `tests/test_comment_auto_reply.py` 8) 포함 `pytest tests/test_comment_auto_reply.py tests/test_get_account_code_ref_by_media_id.py tests/test_get_publish_account_by_ig_user_id.py` **53 passed**. 전체 회귀 `706 passed/94 failed/3 xfailed/6 errors` — 실패·에러 파일 목록이 기존 baseline과 정확히 동일(신규 회귀 0건). **실측 Canary는 위 이유로 불가능(캠페인 0건) — Accept, aijomoojin 댓글 캠페인이 실제 등록되는 시점에 재검증 필요.**

## 남은 UNKNOWN
- aijomoojin 댓글 캠페인이 실제로 등록된 뒤의 실측 Runtime Canary는 미실행(현재 대상 자체가 없음).
- 공개 답글(`reply_to_comment()`) 전환 여부는 회장이 "별도 논의 대상"으로 남김 — 이번 세션에서 결정 안 함.

## 다음 정확한 단계
문서화·commit 승인 대기 → 이후 팔로업(followup) 계정별 Routing(마스터 우선순위 4번) 착수.

## 다음 단계 승인 필요 여부
필요 — 문서화·commit은 코드 구현 승인과 별개 게이트.

---

# 2026-07-30 17:36 ICT — DM Routing Close Gate: fallback 정책 구현+실측 Canary SUCCESS, 신규 백로그(전체 문의유형 자동응답 챗봇) 기록

_기록 시각: 2026-07-30 17:36 ICT · 상태: **PARTIAL/IN_PROGRESS** — DM Routing Close Gate의 fallback 위험(아래 260730 16:46 FACT 참조)에 대한 승인된 정책을 구현·검증까지 완료. 댓글·팔로업 Routing(10.5-6)은 여전히 다음 단계. 이 항목이 최신 상태이며, 아래 260730 16:46 항목은 이 세션 시작 시점의 인계 기록으로 보존._

## 완료된 FACT(이 세션, 260730 17:xx)
- **fallback-gate 코드 구현**: `modules/dm/dm_auto_reply.py`(`GLOBAL_FALLBACK_ACCOUNT_CODE_REF="IDN-000041"` 상수 + `send_ig_reply()` 조건분기)와 `modules/dm/dm_followup_scheduler.py`(`_send_ig_dm()` 동일 조건분기, REUSE) — `account_code_ref`가 있고 해석 실패했는데 yuna18253(`IDN-000041`) 자신이 아니면 전역 fallback 시도 없이 즉시 `False`(retry_queue 위임), 공란/yuna18253은 기존 동작 100% 보존. 신규 테스트 5개(`tests/test_dm_multi_account_send.py` 2개 추가, `tests/test_dm_followup_fallback_gate.py` 신규 3개) 포함 회장 터미널에서 **13 passed, 0 failed**(Raw Output 확인).
- **aijomoojin 실제 가격문의 DM Runtime Canary SUCCESS**: 실제 DM "가격 얼마예요?" → `Lead_Interactions`(`recObauwGlbvU1Djs`, Airtable 직접 조회) `account_code_ref=IDN-000036` 정확히 태깅 → `[AutoReply] 단가 문의 감지` → `[AutoReply] IG DM 발송 완료`(msg_id 확인) — 이 구간 로그에 fallback 경고 **0건**, 즉 `_resolve_dm_send_target()`이 aijomoojin 자신의 `instagram_login`(graph.instagram.com) 경로로 1차 시도에서 정상 성공. 오늘 구현한 fallback-차단 분기는 실제로는 발동되지 않았음(정상 경로 성공 = 안전장치가 필요조차 없었다는 뜻, 좋은 신호) — 그 분기 자체는 여전히 mock 테스트로만 검증된 상태.
- **문서화·commit은 아직 미승인 — 회장 확인 대기 중**(이 세션에서 재확인 필요).

## 신규 백로그(회장 지시, 260730 17:3x, DEFER — 이번 세션 범위 아님)
- **"가격만 답하지 말고 모든 의뢰(문의) 유형에 DM 자동응답이 되어야 한다"** — 현재 `dm_auto_reply.py`는 `PRICE_KEYWORDS` 매칭(가격/단가/얼마/비용/견적 등)에 걸린 문의만 자동응답(그마저 `PRICE_AUTO_REPLY_ENABLED=false`라 상품확인 요청으로 대체)하고, 그 외 일반 문의는 자동응답 없이 Lead_Interactions 기록·스코어링만 된다. 회장은 이걸 "모든 의뢰도(문의 유형)"로 확장해야 한다고 판단.
- **회장 지시**: "우선 기록해놓고 챗봇설계는 갖고오자" — 지금 구현하지 말고 기록만 해둔 뒤, 별도로 챗봇 설계(안)를 가져와서 검토하기로 함. 즉 이번 DM Routing Close Gate 범위 밖이며, 코드 착수 전 별도 설계 리뷰가 선행 조건.
- **Scope 메모**: aijomoojin은 컨설팅 업종이라 "가격 얼마예요" 같은 문구가 실제로는 부자연스럽다는 점이 이 세션에서 확인됨(회장 발언) — 새 챗봇 설계는 업종별(제품판매 vs 컨설팅) 문의 패턴 차이를 반영해야 할 가능성이 있음(추정 표시, 확정 아님).

---

# 2026-07-30 16:46 ICT — 세션 종료 인계: DM Multi-account Routing Runtime SUCCESS, 댓글 Routing(10.5-6)은 다음 세션

_기록 시각: 2026-07-30 16:46 ICT · 상태: **PARTIAL/IN_PROGRESS** — 마스터 12단계 기준 0~6번 완료, 7번(Multi-account Routing) 중 **DM 채널만 완료**(댓글·팔로업 세부는 다음 세션 10.5-6단계). 11단계(다계정 확장) 실행은 계속 HOLD. 이 항목이 최신 상태이며, 아래 260730 10:36 항목은 그 이전(오전) 기록으로 보존._

## 완료된 FACT(오늘 오후 추가분, 260730)
- **DM Multi-account Routing(자동응답+팔로업) Runtime SUCCESS**: 착수 전 블로커(`fb_page_id` 공백) 실측 해소 — yuna18253(facebook_login)의 실제 Page `868456346356581`(기존 전역값과 일치) Airtable 저장, aijomoojin(instagram_login)은 Facebook Page 개념 자체가 없음을 실측 확인(`graph.facebook.com`이 IGAA 토큰 파싱 불가) → `graph.instagram.com` 직접 호출로 설계. 신규 `_resolve_dm_send_target()`(Provider 분기, 실패 시 전역 fallback, 회장 승인 정책) 구현. **라이브 Canary**: 회장이 실제 yuna18253으로 가격문의 DM 발송 → 수신·Lead Scoring·계정별 경로 발송 성공(fallback 경고 로그 0건, `account_code_ref=IDN-000041` 정확히 태깅) Runtime 확인. commit `ae2bec2`/`cf7155c`.
- **10.5단계 Canary Gate 5개 전부 PASS**: ①Commit 감사(`cf7155c`=문서만, `ae2bec2`=실코드 7파일, Secret 노출 0건) ②DM Runtime Canary(위) ③Fail-open 검증(오전 Mock 5개로 충분, 회장 확정) ④데이터 정리·Rollback(코드는 `git revert --no-commit` dry-run 충돌 0건 확인, 테스트 DM 2건은 실제 계정 대화라 삭제 안 하고 보존 결정) ⑤Push(`42472d2..cf7155c`, 0/0 동기화).
- **ERR-090(신규, OPEN)**: Claude Code가 `.env` grep 중 실수로 YUNA/AI 토큰 원문을 tool 출력에 노출(대화 기록 내, 외부 유출 증거 없음). ERR-077/FP-059와 동일 클래스. 토큰 재발급은 회장 지시로 **보류**(나중에 처리). commit `34c8901`.
- **댓글 Routing(6번) 재조사(설계만, 코드 미착수)**: 당초 "폴링 루프 자체를 계정별로 재구성해야 함(Blast Radius 중간)"으로 예상했으나 재확인 결과 **더 작음** — `comment_poller.py`는 이미 `comment_poll_targets`(캠페인 media_id 상태머신)를 순회해 계정이 섞여도 폴링 루프 자체는 안 건드려도 됨. `_try_private_reply()`에 `media_id`가 이미 파라미터로 있어 `media_id`→`Instagram_Posts.account_code_ref` 역조회 1단계만 추가하면 `_resolve_dm_send_target()`를 그대로 REUSE 가능. **회장이 우선순위를 재조정 — 댓글 Routing보다 DM Close Gate가 먼저**(아래 참조).
- **DM Routing Close Gate 발견(회장 지시로 우선순위 최상위 재조정, 정책 승인·구현은 다음 세션)**: 전역 fallback의 실제 목적지를 실측 — `INSTA_IG_USER_ID`(공개 ID)가 yuna18253의 ig_user_id와 정확히 일치, 즉 **전역 fallback은 항상 yuna18253 고정**. yuna18253 자신의 해석 실패는 fallback도 결과가 같아 문제 없으나, **aijomoojin의 계정 해석이 실패하면 fallback이 yuna18253 Page 토큰으로 잘못 시도**(Instagram igsid는 Page별 스코프라 Graph API가 거절할 가능성 높음 — "오계정 전달"보다 "aijomoojin 고객이 조용히 답장 못 받음" 쪽에 가까움, Hypothesis). **회장이 제안 정책을 승인**: account_code_ref가 있는데(어느 계정인지 이미 알고 있는데) 해석 실패 시 — yuna18253이면 그대로 fallback 유지(결과 동일), **그 외 계정(aijomoojin 등)이면 fallback 시도 없이 명확한 오류로 retry_queue行**(account_code_ref 자체가 없는 레거시/미해석 DM만 지금처럼 전역 fallback 유지). **아직 코드 미구현** — 다음 세션 착수 대상.

## 남은 UNKNOWN
- ERR-089 Root Cause(블로킹 I/O·GIL 경합·OS 레벨 정지 중 무엇인지) — 관측만 확보, 재발 자체는 못 막음. HOLD(재발 시 착수).
- 마스터 2번(Critical Path 부모그룹 5개 재구성)은 여전히 PROVISIONAL.
- aijomoojin 실제 DM Runtime Canary — 아직 미실행(코드·데이터 선결조건은 없음 확인됨, 회장이 실제 DM만 보내면 됨, yuna18253과 동일 절차).

## 다음 정확한 단계(우선순위 재조정됨, 회장 확정 260730 17:10 ICT)
1. **DM Routing Close Gate**(최우선, 댓글보다 먼저) — ①aijomoojin 실제 가격문의 DM Canary(yuna18253과 동일 절차, 코드 선결조건 없음) ②승인된 fallback 정책(위 FACT) 구현 — `_resolve_dm_send_target()` 호출부에서 account_code_ref 존재+해석실패+yuna18253 아님 조건일 때 fallback 생략하고 즉시 retry_queue 위임 ③의도적 실패 재현으로 정책 동작 확인.
2. 그 다음 **10.5-6단계: 댓글 계정별 Routing**(신규 Repository 메서드 `ig_media_id`→`account_code_ref` 역조회 + `comment_auto_reply.py` 연결).
3. **ERR-090 토큰 재발급** — 10.5 Close Gate 이전까지는 완료해야 함(회장 지시, 순서는 자유이나 마감 있음).

## 다음 단계 승인 필요 여부
필요 — DM Close Gate 착수 전 5요소/Gate 제출 후 승인.

---

# 2026-07-30 10:36 ICT — 계정별 Kill Switch Runtime SUCCESS + ERR-089 관측 보강 완료 + Regression Baseline PASS

_기록 시각: 2026-07-30 10:36 ICT · 상태: **PARTIAL/IN_PROGRESS** — 마스터 12단계 기준 0~4·5·6번 완료, 7번(Multi-account Routing) 착수 전. 11단계(다계정 확장) 실행은 여전히 HOLD. 이 항목이 최신 상태이며, 아래 260729 22:35 항목은 그 이전 기록으로 보존._

## 완료된 FACT(오늘, 260730)
- **계정별 Kill Switch(IG 발행) Runtime SUCCESS**: `Account_Registry.automation_enabled` Fail-closed 채택(Airtable checkbox unchecked=missing, 우회 방지 우선, 회장 확정) — `PublishAccountV2` 옵션 서브타입으로 Blast Radius 0. 배포 전 라이브 계정 2개(`yuna18253`/`aijomoojin`) 명시 `true` 설정. **라이브 Canary(10:02:17 ICT)**: `automation_enabled=false` 테스트 계정 레코드가 정확히 차단(`ready` 유지, `ig_media_id` 공란) — PASS. 테스트 레코드 사후 삭제. commit `e9b8fb8`/`1ba3c96`/`f15cb7b`.
- **ERR-089(Scheduler Stall, PARTIAL)**: Kill Switch Canary 도중 우연히 발견 — `launcher/main.py` 내부 두 `BackgroundScheduler`가 07:48:10~08:16:18 약 28분간 Job 실행 0건. Root Cause **UNKNOWN**(Thread Dump·리소스 시계열 부재). watchdog이 launcher 내부 응답성을 감시하지 않던 공백을 Confirmed. 관측 보강 4단계 전부 구현·라이브 검증 완료(Flask Alert-only/Scheduler Heartbeat 60초·7분 임계값/Gemini 호출 소요시간 로그/재발 판정 기준) — commit `d7d038a`/`c00a734`/`e4d324e`/`cee92ee`.
- **Regression Baseline(마스터 5번) SUCCESS**: 전체 690 passed/95 failed/3 xfailed/4 errors. 95개 표본 6개 재검증 — 전부 기존 `runtime_boot_policy.json` PermissionError(오늘 코드 무관). 오늘 변경 파일은 개별 `git stash` 대조로 이미 확인. **신규 회귀 0건**(95개 전수 재실행은 아님, 명시).

## 남은 UNKNOWN
- ERR-089 Root Cause(블로킹 I/O·GIL 경합·OS 레벨 정지 중 무엇인지) — 관측성만 확보, 재발 자체는 못 막음.
- 마스터 12단계 2번(Critical Path 부모그룹 5개 재구성)은 여전히 PROVISIONAL — GPT 최종 확정 없음.

## 다음 정확한 단계
마스터 12단계 **7번(Multi-account Routing 설계)** — DM·댓글·팔로업 3곳이 전부 단일 전역 `INSTA_ACCESS_TOKEN`만 쓰는 문제. 5요소(①Ingress 계정식별 ②계정별 Credential 선택 ③`account_code_ref` 저장·전파 ④계정별 Queue·Idempotency·Log 격리 ⑤Fail-closed) 설계 필요 — High Risk(Repository Interface 변경 가능성) 분류, Codex Full Review 대상.

## 다음 단계 승인 필요 여부
필요 — 7번 착수는 회장 승인 대상(대형 작업, 오늘 세션에서 "미착수" 확정 후 5번으로 우회했었음).

---

# 2026-07-29 22:35 ICT — 세션 종료 인계: 10.5단계(필수 부품 조립·통합) 착수, 11단계 여전히 HOLD

_기록 시각: 2026-07-29 22:35 ICT · 상태: **PARTIAL/IN_PROGRESS** — 10단계 Closed Gate 이후 11단계 착수 전 선행 Gate 4개를 오늘 전부 처리했고, 이어서 GPT Master Execution Directive로 "10.5단계(필수 부품 조립·통합)"가 공식 우선순위로 고정됐다. 11단계(다계정 확장) 실행은 계속 HOLD. 이 항목이 최신 상태이며, 아래 9단계 항목은 그 이전 기록으로 그대로 보존한다._

## 판정
IN_PROGRESS — 오늘 처리한 5개 작업(Persona/account_email/ERR-076/Kill Switch/WEBHOOK_APP_SECRET) 전부 종료됐으나, 10.5단계 자체는 아직 Close Gate(§5 체크리스트 11번) 도달 전이다.

## 완료된 FACT(오늘, 260729 저녁 세션)
- **Persona Runtime 최소연결(PARTIAL)**: `dm_receiver.py`→`dm_auto_reply.py`→`ai_reply_generator.py` 3파일에 `account_code_ref`/`tone_style`/`greeting_template`/`followup_template` optional 파라미터 배선(기본값 전부 빈 문자열, 기존 동작 100% 동일). Airtable Persona_Profile 조회 로직·콘텐츠 입력은 범위 밖. commit `c3e711d`/`e093d2d`.
- **account_email SSOT(RESOLVED)**: Runtime 편입 계정 2/2(yuna18253/aijomoojin) 전부 회장 직접 확인, `modules/` 코드 참조 0건으로 Blast Radius 0 확정. commit `aad08e0`.
- **ERR-076 관측성(PARTIAL)**: `publish_single()` http_4xx "명확한 실패" 분기에 `creation_id` 전파 + Slack 알림 확장(기존 outcome_unknown 패턴 재사용, Airtable Schema 변경 없음 — ERR-075/041 재발 방지). 근본 분류로직(폴링/error_subcode)은 Raw Evidence 부족으로 미착수. commit `987eec7`/`a6fcf4c`.
- **계정별 Kill Switch(설계 확정, 코드 미착수)**: Entry Point 8곳 전수 매핑 — 계정별 라우팅이 실제로 살아있는 곳은 IG 발행(`_job_insta_upload`) 1곳뿐임을 확인. `PublishAccount` TypedDict 직접 확장(23개 참조파일 High Risk) 대신 옵션 필드 서브타입 설계(Blast Radius 0)로 축소. DM·댓글·팔로업 계정별 라우팅은 별도 HOLD로 분리. commit `3b79e43`.
- **GPT Master Execution Directive 수용**: 11단계 실행 HOLD 유지, "10.5단계(필수 부품 조립·통합)"를 공식 우선순위로 고정. Assembly Inventory(15열 통합표, 31개 기능) 1차 작성 — 원본 P0 표기 오류(6개→실제 9개)를 GPT 감사가 지적, 번호나열+합계로 재확인. commit `8a4ba60`.
- **11단계 Scope 확정(회장 직접결정, FACT)**: 3계정 Canary는 **IG 발행뿐 아니라 DM·댓글·팔로업까지 포함**한다. 이 결정으로 Critical Path(P0)가 9개→13개로 재집계됨(번호나열+합계로 Confirmed) — 핵심 신규 발견: **DM·댓글·팔로업이 전역 토큰(`INSTA_ACCESS_TOKEN`) 1개로만 도는 문제**가 Kill Switch보다 큰 신규 작업으로 드러남. 부모그룹 5개 재구성은 여전히 PROVISIONAL(Architecture 해석, GPT/회장 최종 확정 대기). commit `8a4ba60`(§10-19).
- **WEBHOOK_APP_SECRET 안전검증(현재 시점 확인)**: `object="probe"` 최소 바디로 Business Logic 진입을 원천 차단하는 Boolean-only Canary를 살아있는 `/webhook`·`/webhook/ai-strategist`에 실행 — 둘 다 200(라이브 프로세스 값=현재 `.env` 값 일치), Secret 원문·서명값 미출력. 원래 불일치의 근본원인·시점·`task_b24dbf54` 조치 여부는 여전히 UNKNOWN. commit `f9c91cf`.

## 남은 UNKNOWN
- Critical Path 부모그룹 5개·"신규작업 2개(Kill Switch+DM/댓글/팔로업 라우팅)" 결론은 PROVISIONAL — GPT/회장의 §5 체크리스트 2단계(Critical Path 확정) 승인 전까지 SSOT로 취급하지 않는다.
- `WEBHOOK_APP_SECRET` 원래 불일치의 근본원인·`task_b24dbf54` 세션 결론 — 이 저장소 안에서 확인 불가, 재발 방지책(재시작 누락 감지 등) 미착수.
- Persona_Profile 실제 콘텐츠(tone/greeting/followup) 입력 담당·시점 미정.
- FB 크롤링·Domeggook이 3계정별로 다른 콘텐츠를 받아야 하는지 — Scope 확정에서 명시적으로 다루지 않음, 재검토 표시만 해둔 상태.

## RISK
- DM·댓글·팔로업 계정별 라우팅(전역 토큰 → 계정별 분리) 미착수 상태로 11단계에 진입하면 다계정 DM 오응답·계정 혼선 위험이 실제로 발생한다 — Scope Gate 확정 후 확인된 가장 중요한 RISK.
- WEBHOOK_APP_SECRET 일치 확인은 "지금 이 순간"의 스냅샷이며, `.env` 수정 후 재시작 누락 시 재발 가능(모니터링 메커니즘 없음).

## 변경 파일(오늘 세션 전체)
`modules/dm/dm_receiver.py` / `modules/dm/dm_auto_reply.py` / `modules/dm/ai_reply_generator.py` / `launcher/main.py` / `tests/test_publish_outcome_unknown.py` / `docs/WORKFLOW_ARCHITECTURE_STATUS.md` / `docs/ERROR_DATABASE.md` / `docs/CURRENT_RUNTIME_CONTEXT.md`(이 파일) — Airtable Write **0건**, Runtime Restart **0건**(WEBHOOK_APP_SECRET 검증은 기존 살아있는 프로세스에 읽기성 Canary 요청만 전송).

## Commit·Push 상태
오늘 세션 commit 9개: `c3e711d`/`e093d2d`/`aad08e0`/`987eec7`/`a6fcf4c`/`3b79e43`/`8a4ba60`(→ 여기까지 push 완료, `git push origin master` 실행됨) / `f9c91cf`(WEBHOOK_APP_SECRET) + 이 인계 문서 commit(다음) — **최신 2개는 세션 종료 처리 시점에 push 여부 확인 필요**.

## 다음 정확한 단계
10.5-2 **Critical Path 최종 확정** — PROVISIONAL 상태인 5개 부모그룹·신규작업 2개(Kill Switch/DM·댓글·팔로업 라우팅) 결론을 GPT가 감사하고 P0/P1/HOLD/DEFER를 승인 확정한 뒤에만 §5 체크리스트 3단계(Reuse·Buy·Build 결정)로 진행한다. **11단계 다계정 확장 실행은 여전히 착수하지 않는다.**

## 다음 단계 승인 필요 여부
필요 — Critical Path 확정은 GPT 감사 + 회장 승인 대상(이번 세션에서 반복된 패턴 그대로).

---

# 2026-07-29 13:35 ICT — 9단계(예외삼킴·데이터손실 감사) 완료 선언

_기록 시각: 2026-07-29 13:35 ICT · 상태: **9단계 완료(회장 확정)** — 8단계 완료 직후 착수한 예외삼킴·데이터손실 감사 트랙을 종료한다. 이 "9단계"는 아래 §Source of Truth/§Runtime 상태와 무관하게 `docs/WORKFLOW_ARCHITECTURE_STATUS.md` §1의 0~11단계 로드맵과는 별개 트랙이다(번호가 우연히 같을 뿐)._

## 완료 요약

- **9-10-3 배치 감사 Defect A~F(전부 RESOLVED)**: `launcher/main.py` Active 스케줄 잡 8개 전수 감사 — Facebook Crawl(`09cae6f`)/Account Manager(`56b7497`)/Dome Crawl(`dd06816`)/Dome Export(`ba8b95c`)/KPI Snapshot(`4375642`)/Instagram Upload(`c857aef`) 6개 예외삼킴·배치격리 결함을 개별 최소수정 + mock 테스트 + Runtime 재시작 라이브 검증으로 확인 후 개별 commit.
- **ERR-085~088(CRM/DM 쓰기 실패 예외삼킴, 전부 RESOLVED)**: `lead_closer`/`lead_scorer`/`order_detector`/`dm_receiver` 4곳에 `retry_queue` 위임 추가(`75c60d2`), 문서 갱신(`9c2c99a`). ERR-087은 Production Caller 0건으로 `NOT_ACTIVE` 유지, ERR-088은 기존 Telegram 알림 계약을 의도적으로 보존(회장/GPT 지시) — 둘 다 알려진 잔존사항.
- **uploading 고착 11건 remediation(코드 변경 없음, Airtable 데이터만 수정)**: 9-12에서 발견. 로그로 11/11 전부 실제 게시 이력 0건(중복게시 위험 없음) 확정 → Canary 재시도 중 9단계 다계정 안전장치(`account_code_ref` 필수)에 걸리는 신규 현상 발견 → `account_code_ref=IDN-000041`+`post_status=ready`로 재설정 → 11/11 전부 실제 Instagram 게시 성공(`post_status=posted`, 고유 `ig_media_id` 확인).
- **9-14 최종 Closure 감사(Read-only)**: git status clean, 관련 테스트 88 passed/6 failed(전부 pre-existing 환경제약, 회귀 아님)/3 xfailed, Runtime 재시작(11:43:51) 이후 실제 신규 ERROR 0건, Airtable 11/11 `posted` 확정, 문서 정합성 확인.

## HOLD(9단계 결론과 분리)

- `WEBHOOK_APP_SECRET` 라이브 프로세스 값과 `.env` 파일 값의 불일치를 ERR-085 라이브 검증 중 발견(운영 트래픽 영향 여부 미확인) — 별도 세션(`task_b24dbf54`)에서 조사 진행 중. **260729 22:32 ICT 추가 확인**: `/webhook`·`/webhook/ai-strategist` 양쪽 다 Boolean-only 서명 Canary(`object` 값을 `"instagram"`이 아니게 만들어 Business Logic 진입 원천 차단, Secret 원문 미출력)로 재검증한 결과 **현재 시점 기준 라이브 프로세스 값=`.env` 파일 값 일치(둘 다 200)** — 단, 이건 점검 시점의 스냅샷이며 원래 불일치가 언제·왜 있었는지와 `task_b24dbf54`의 조치 여부는 여전히 UNKNOWN. `.env` 수정 후 재시작 누락 시 재발 가능.
- ERR-087은 Production Caller가 생기는 시점(`dm_followup_scheduler.py` 연동 등) 재감사 필요.
- FP-063 예방책(3)(리뷰 체크리스트에 "fail-open이 맞는가, retry_queue가 필요한가" 항목화)은 미착수(DEFER).

## 판정

9단계(예외삼킴·데이터손실 감사) **완료 선언**(회장 확정, 260729 13:35 ICT). 상세 Evidence는 `porting_logs/MERGE_JOURNAL.md` [260729_9단계_예외삼킴_데이터손실_감사_완료] 항목 / `docs/WORKFLOW_ARCHITECTURE_STATUS.md` §10-15 참조.

---

# 2026-07-29 06:09 ICT — 8단계 P1-1 완료 선언 (C1 Facebook Exact-Post Canary + anchor-scan Gate 해소)

_기록 시각: 2026-07-29 06:09 ICT · 상태: **8단계 완료(회장 확정)** — C1 Runtime SUCCESS(260728 21:37 ICT)에 이어 260728 21:39 ICT UNKNOWN으로 보류했던 anchor-scan 오매칭 근본원인을 실제 DOM으로 재현·규명·코드로 차단했다. 회장이 8단계 완료를 선언했으며, Commit·Push는 회장 지시로 별도 보류한다._

## Root Cause(Confirmed) 및 수정

- **원인**: Facebook의 "게시물 숨기기" 등 JS 전용 UI 액션 anchor가 실제 목적지 없이 현재 보고 있는 permalink 자체를 href로 재사용하며(`.../posts/<현재글ID>#`처럼 빈 `#`로 끝남), `extract_facebook_post_id()`가 `urlparse()`로 `#` 뒷부분을 제거하고 파싱하기 때문에 이 placeholder href도 "진짜 그 게시물 링크"로 오인됐다. 화면에 뜬 무관한 다른 게시물(오늘 "Cielo Anne Areno", "China Sixsix" 등 매번 다르게 재현)이 이 때문에 반복적으로 오매칭됐다.
- **재현 Evidence**: `aria-label='China Sixsix님의 게시물 숨기기'`, `href='https://www.facebook.com/groups/1827528710833477/posts/4051001165152876#'`인 anchor가 무관한 "China Sixsix" article 안에서 발견되어 실제 오매칭을 코드 레벨로 확정했다(260729 05:24 ICT).
- **수정**(`modules/sns/facebook_crawler.py::_find_exact_permalink_article()`): href가 빈 `#`로 끝나는 anchor(실제 목적지 없는 UI 액션 placeholder)와, aria-label에 "숨기기"가 포함된 anchor를 게시물 식별 근거에서 제외하도록 최소 수정. 이 필터 없이는 화면에 게시물이 하나라도 뜨면 사실상 항상 매칭되는 상태였다.
- **회귀 테스트**: `tests/test_package_s3_facebook_exact_runner.py`에 오늘 실측 재현 케이스 3건 추가(단일 숨기기 anchor 거부/실제 링크와 공존 시 실제 링크 선택/aria-label 없이 href만으로도 거부) — 대상 파일 31/31 PASS(기존 28 + 신규 3), 관련 전체 Suite 626 passed(기존 실패 9건과 동일, 신규 실패 0건).
- **수정 후 실측 재확인(260729 05:58~05:59 ICT, 2회)**: 같은 permalink에 실제 브라우저로 재접속해 수정된 함수를 직접 호출한 결과, 더 이상 "China Sixsix" 같은 무관 게시물을 선택하지 않는다(2회 모두 `found=0`으로 Fail-closed — 페이지 로딩 타이밍상 진짜 대상 게시물이 이 대기시간 안에 렌더링되지 않은 것으로 추정되며, 이는 오늘 이전에도 별도로 문서화된 DOM 로딩 비결정성 문제이지 이번 수정의 부작용이 아니다). **핵심 성공 기준인 "무관 게시물 오매칭 재현 안 됨"은 2회 모두 확인됐다.**
- **C1 Draft 오염 여부**: 이 오매칭은 애초에 실제 저장 함수(`run_exact_permalink_canary`)의 payload에 영향을 준 적이 없음(260728 Adversarial 단위테스트로 별도 증명 완료, DOM 텍스트·이미지가 payload에 섞일 코드 경로 자체가 없음) — 오늘 저장된 draft(`recFHv9AvW891KaHW`)는 계속 안전하다.

## 판정

8단계 완료 선언 보류 사유였던 "자동 anchor-scan 오매칭 근본원인 UNKNOWN"이 Confirmed로 규명되고 코드로 차단됐다. 남은 것은 페이지 로딩 타이밍에 따른 DOM 콘텐츠 비결정성(이미 별도 문서화된 기존 이슈, 이번 수정과 무관)뿐이며, 이는 Fail-closed로 안전하게 처리된다. **회장이 8단계 완료를 선언했다(260729 06:09 ICT). Commit·Push는 회장 지시로 별도 보류.**

---

# 2026-07-28 21:39 ICT — 8단계 P1-1 C1 Facebook Exact-Post Canary Runtime SUCCESS (완료 선언 보류)

_기록 시각: 2026-07-28 21:39 ICT · 상태: **PARTIAL(Runtime SUCCESS, 8단계 완료 선언은 보류)** — C1 draft 1건이 정확한 계약대로 Airtable에 저장됐고 Production으로 안전 복귀했으나, 조사 중 발견된 "자동 anchor-scan 오매칭" 근본원인이 UNKNOWN으로 남아 회장이 8단계 완료 선언을 별도 Gate 이후로 보류시켰다._

## C1 최종 결과

**입력 Lock**: `permalink=https://www.facebook.com/groups/1827528710833477/posts/4051001165152876`, `expected_post_id=4051001165152876`, `source_account=account1(Cho Eunha)`, `target_publish_account_code_ref=IDN-000041`, `approved_caption="[C1 CONTROLLED CANARY] Facebook exact-post account attribution validation"`(고정 테스트 caption), `approved_image_url=https://i.ibb.co/k2D2nkhZ/image.jpg`(승인된 ImgBB Upload 1건 결과, 원본 fbcdn 이미지와 Content-Length 37,799 bytes 동일 확인됨).

**Runtime Evidence(Read-only 직접 확인)**:
```text
db/canary_runs.db: canary_run_id=c1fb-260728-2111, status=COMPLETED, terminal_code=SUCCESS
write_counts: instagram_post_create=1, 나머지 전부 0
Airtable Instagram_Posts(recFHv9AvW891KaHW): account_code_ref=IDN-000041, data_classification=test,
  post_status=draft, insta_post_code=CANARY-FB-4051001165152876, caption·image_url 승인값 그대로
```

**Safe Context(W2) → Watchdog 재기동(R2) → C1 → Production 복귀 전체 체인**: 이 세션(Claude Code) 계정은 `C:\ProgramData\SNS_24AutoProject\runtime_boot_policy.json` 읽기·`SNS_Watchdog` 서비스 제어 권한이 없음을 반복 확인(`PermissionError`) — Boot Policy 생성·활성화·C1 CLI 실행·Production 복귀까지 전부 **회장이 직접 관리자 권한 PowerShell에서 수행**했고, Claude Code는 JSON 사전 dry-run 검증 + 사후 Read-only 대조(`/health`, `watchdog.log`, `canary_runs.db`, Airtable GET)만 담당했다. `/health`로 Safe Mode 진입(`canary_safe_mode=true`, Webhook 503)과 Production 복귀(`canary_safe_mode=false`, Webhook 403 정상)를 각각 실측 확인했다.

## 미해결 Gate — 8단계 완료 선언 보류 사유

조사 과정에서 Claude Code 자체 진단 스크립트(레포 밖 scratchpad, Production 코드 아님)가 동일 Permalink를 스캔하다가 1회, `expected_post_id`와 일치하는 article 안에서 실제로는 무관한 다른 위젯 텍스트("Cielo Anne Areno")를 읽어온 사례가 있었다. 회장이 직접 같은 URL로 2회 재접속해 확인한 결과("김정현/TIELA" 게시물)와 불일치했었다.

- **Production 함수 자체는 안전함을 별도 증명 완료**: `run_exact_permalink_canary()`에 Adversarial 단위테스트(가짜 DOM에 "틀린 상품" 텍스트·이미지를 심어 검증)를 실행한 결과, payload의 `caption`/`image_url`은 오직 `approved_caption`/`approved_image_url` 파라미터만 사용하며 DOM에서 읽은 텍스트·이미지가 섞일 코드 경로 자체가 없음을 확인했다(`_find_exact_permalink_article()`의 반환값이 애초에 사용되지 않음). 오늘 저장된 실제 draft 레코드는 오염되지 않았다.
- **그러나 왜 진단 스캔이 중첩/추천 위젯을 오매칭했는지의 정확한 DOM 원인은 UNKNOWN으로 남아 있다.** 회장이 이를 8단계 완료 선언 전 별도 Gate로 다루기로 결정했다(260728 21:39 ICT).
- Blast Radius는 현재 "진단 스크립트의 신뢰도" 문제로 한정되나(Production 경로 무관), 향후 유사 진단·자동화 로직을 재사용할 경우 반드시 선결돼야 한다.

## Next Gate
- 8단계 완료 선언: 위 anchor-scan 오매칭 Root Cause Gate 해소 후 진행
- `docs/ERROR_DATABASE.md`: 이 이슈에 정확히 대응하는 기존 항목 없음 — 다음 사용 가능 ID `ERR-084`로 확인만 됨, 회장 별도 승인 전 미생성
- Commit·Push: 미실행, 별도 승인 대상

---

# 2026-07-28 16:49 ICT — 8단계 P1-1 C1 Facebook 중복 Article Selector 수정 (PARTIAL)

_기록 시각: 2026-07-28 16:49 ICT · 상태: **PARTIAL** — Codex가 토큰 소진으로 중단한 지점부터 Claude Code가 이어받아 중복 article Selector 코드·테스트만 수정했다. Runtime Restart·C1 Canary 재실행·Airtable Write·Commit·Push는 전부 미실행이다._

## 인계 시점 FACT (Codex 중단, 사용자 전달 요약 — 이번 세션에서 Runtime으로 재검증하지 않음)

- 선택 Facebook 게시물 Post ID(마스킹) 및 Expected Post ID 일치: Codex 보고
- `account1 = Cho Eunha`: Codex 보고
- 동일 논리 게시물이 DOM `div[role='article']` 요소 2개로 렌더링됨: Codex 보고
- Airtable Create·Update 0건, Run ID 소비 0회, Safe Mode 유지, 코드·Commit·Push 없음: Codex 보고
- 위 항목들은 이번 세션에서 Claude Code가 Runtime으로 직접 재확인하지 않았다 — Evidence Priority상 8순위(대화·요약)이며, 아래 "이번 세션 FACT"만 이번 세션의 직접 증거다.

## 이번 세션 FACT (Claude Code, Read-only + 코드수정 + 로컬 테스트만)

- 대상 파일: `modules/sns/facebook_crawler.py`의 `_find_exact_permalink_article()` — Runtime Caller: `run_exact_permalink_canary()` → `tools/run_facebook_canary.py::execute_facebook_canary()`(둘 다 현재 미커밋 신규 코드, `git log -S` 이력 없음 — Package S3 자체가 아직 Runtime에 배포되지 않은 신규 기능).
- Root Cause 확정(코드 직접 확인): 수정 전 로직이 `len(matches) != 1`이면 무조건 실패 처리해 **DOM 요소 개수**를 논리 게시물 개수로 오판했다. `matches`는 이미 `expected_post_id`와 정확히 일치하는 anchor를 가진 article만 포함하므로, 그 개수가 1보다 크다는 것은 "다른 게시물"이 아니라 "같은 Post ID의 중복 렌더링"을 의미한다.
- 수정: `if len(matches) != 1` → `if not matches`로 변경(1줄) — Post ID가 이미 `expected_post_id`로 확정된 후보가 1개 이상이면 모두 동일 논리 게시물로 간주해 첫 후보를 반환하고, 후보가 0개일 때만 fail-closed 유지.
- 기존 테스트 `test_exact_selector_rejects_zero_or_multiple_matches`의 파라미터 중 "동일 Post ID article 2개(다른 URL 형식)" 케이스가 수정 전 로직(구 버그)을 PASS로 검증하고 있었음을 확인 — 이 케이스를 신규 "dedup PASS" 테스트로 이전하고, 해당 파라미터 테스트는 "found=0" fail-closed 케이스만 남도록 재구성.
- 신규/변경 테스트: `tests/test_package_s3_facebook_exact_runner.py`에 dedup PASS 테스트(동일 Post ID article 2개/3개), selector-level 0-match 테스트(서로 다른 ID 2개/추출불가 2개 포함), canary-level 중복 DOM PASS 테스트(ImgBB 0회 확인), canary-level selector 실패 시 Run ID·Write 0건 확인 테스트 추가 — 파일 자체는 Codex가 이미 만든 미커밋 신규 파일이라 git상 여전히 `??`(untracked)로 표시된다.
- Pre-change Baseline(수정 전, Codex 산출물 그대로 실행): `test_package_s3_facebook_exact_runner.py` 23 passed / 0 failed. 전체 Suite(collection이 아래 RISK로 막히는 3개 파일 및 동일 원인으로 실패하는 5개 Package 파일 제외) 618 passed / 10 failed / 3 xfailed — 10개 실패는 전부 이미 미커밋 상태였던 다른 파일(`test_provider_routing.py`/`test_publish_gate_and_approval.py`/`test_publish_outcome_unknown.py`/`test_meta_graph_version.py`/`test_review_grid_ui.py`)의 기존 실패로, 이번 대상 파일과 무관.
- Post-change 결과(동일 제외 목록): `test_package_s3_facebook_exact_runner.py` 28 passed / 0 failed(신규 5테스트 포함). 동일 전체 Suite 624 passed / 9 failed / 3 xfailed — 신규 실패 0건, 기존 실패 목록과 정확히 동일(단 `test_review_grid_ui.py` 1건은 Streamlit AppTest 3초 타임아웃성 flaky로 이번 실행에서 우연히 PASS, 코드변경과 무관).
- `git diff --check` 0건. 변경 파일은 `modules/sns/facebook_crawler.py`(기존 M) + `tests/test_package_s3_facebook_exact_runner.py`(기존 untracked, 그 안에서만 수정) 2개뿐 — 승인 Scope 내부. AST 파싱 PASS 양쪽 파일.

## RISK / UNKNOWN (이번 세션)

- `C:\ProgramData\SNS_24AutoProject\runtime_boot_policy.json`에 대해 이번 세션 환경에서 `PermissionError: [WinError 5] 액세스가 거부되었습니다`가 발생 — `canary_safe_mode.py::get_canary_safe_mode_state()`(Runtime 진입점이 `require_boot_policy=True`로 호출하는 경로)가 이 파일 존재 여부를 확인하는 지점에서 막힌다. 이 때문에 `test_package_s1/s2/c0/b/s5`와 `test_dm_*` 3개 파일은 이번 세션에서 실행 자체가 불가능했고(수정 전·후 동일 증상, 코드변경과 무관), **현재 Runtime의 실제 Safe Mode 상태(정상/Canary)는 이번 세션에서 직접 확인 불가 — UNKNOWN**이다. 이 ACL 문제 자체는 이번 승인 Scope 밖이므로 조사·수정하지 않았다.
- "Frozen Inventory 상태"는 이번 세션에서 별도로 재확인할 대상을 특정하지 못해 UNKNOWN으로 남긴다 — 인계 요약의 표현을 그대로 재인용하지 않는다.

## 다음 Gate

- C1 Runtime 재실행: 별도 승인 필요
- Runtime Restart: 금지(이번 승인 범위 밖)
- Package C2 Dome Canary: 금지
- Commit / Push: 금지 — 전부 미실행
- 다음 담당자: GPT 감사 → 회장 별도 승인 후 C1 재실행

---

# 2026-07-28 ERR-082 / Bundle B Runtime Closure Snapshot

_기록 시각: 2026-07-28 07:30 ICT · 상태: **7단계 SUCCESS / ERR-082 RESOLVED** — 정의된 Runtime 종료조건을 모두 충족했다. 8단계는 시작하지 않았다._

## 상태

- **Active Runtime:** `C:\SNS_24AutoProject_260511`
- **Git 기준선:** branch `master` / HEAD `8c19808ccff14848083bccf2843407d1a28a00a0`
- `.env`의 `DM_ACCOUNT_ROUTING_ENABLED=true` 적용 후 `SNS_Watchdog`를 재시작했고, 새 launcher Runtime에서 두 Webhook Route가 HTTP 200으로 생존했다.

## Runtime Closure FACT

- AI Strategist 실제 Meta DM: `POST /webhook/ai-strategist → 200`, Route 전용 Signature 검증 통과.
- 기존 yuna 실제 Meta DM: `POST /webhook → 200`, AI Route 오라우팅 0건.
- Cross-secret Runtime 검증: `/webhook` + AI Secret → 403, `/webhook/ai-strategist` + Galaxy Secret → 403, Business Logic 진입 0건.
- yuna 수신 매핑은 `account_code_ref=IDN-000041`로 저장됐고 잘못된 계정 저장은 0건이었다.
- 가격 문의별 기존 자동응답이 각각 1건씩 도착했으며, Runtime 발송 로그와 사용자 화면 Evidence가 일치했다.
- 실제 Secret·Token·Signature·DM Raw Body 노출은 0건이며, 이번 Runtime Canary의 신규 코드 변경·Commit·Push는 0건이다.

## RISK / HOLD

- Canary 구간에서 Signature 실패 경고 8건이 관측됐으나 발생 주체는 **UNKNOWN**이다. 해당 요청의 Business Logic 진입·Lead 생성·계정 오염 Evidence는 없으며, ERR-082 종료와 분리해 후속 조사 HOLD로 유지한다.
- `docs/INSTAGRAM_ACCOUNT_WEBHOOK_ONBOARDING_RUNBOOK.md`의 과거 미검증 표시는 이번 7-CLOSE 문서 반영에서 Runtime FACT로 갱신한다.

## CODEX Temporary Execution Exception

- 임시 실행 기간: `2026-07-28 04:48~16:48 ICT`
- 승인자: 회장
- Claude Code 실행 역할의 12시간 한정 임시 대행이며 영구 역할 변경이나 향후 선례가 아니다.
- `2026-07-28 16:48 ICT` 도달 즉시 CODEX는 기존 Read-only 감사 역할로 복귀한다.

## Next Gate

- 7단계 종료 문서 반영만 수행하며, 8단계 실행·Commit·Push는 각각 별도 승인 전 시작하지 않는다.

---

# 2026-07-28 ERR-082 Runtime Partial-Success Snapshot

_기록 시각: 2026-07-28 05:47 ICT · 상태: **PARTIAL / IN_PROGRESS** — AI Strategist 경로만 실제 Canary SUCCESS이며, ERR-082 전체는 RESOLVED가 아님._

## 상태

- **Active Runtime:** `C:\SNS_24AutoProject_260511`
- **Git 기준선:** branch `master` / HEAD `8c19808ccff14848083bccf2843407d1a28a00a0`
- **단계 1 기준선:** Active Runtime 기준선 확인 **9/9 SUCCESS**

## 완료된 FACT

- AI Strategist 계정의 실제 Meta DM이 도착했고, `POST /webhook/ai-strategist → 200` 및 Signature 검증 통과를 확인했다. **AI Strategist 경로만 실제 Canary SUCCESS**로 판정한다.
- Signature Root Cause는 **상위 Meta App Secret: NO MATCH / Instagram App Secret: MATCH**로 확정했다. 실제 Secret 값은 이 문서에 기록하지 않는다.
- 표준 절차 문서 `docs/INSTAGRAM_ACCOUNT_WEBHOOK_ONBOARDING_RUNBOOK.md`가 존재하며 작성 완료 상태다.
- 단계 1 자동 Transcript `logs/AI_chat/session_20260728_0503.txt`는 Git ignored PowerShell 운영 로그로 확인됐고, 회장이 운영 예외로 승인했다. Source·설정·문서 변경 계산에서 제외하며 민감정보 노출은 0건이다.

## 남은 UNKNOWN

- 기존 yuna 계정의 실제 Meta DM 회귀 성공 여부
- Route별 잘못된 Signature/Secret 차단 Runtime 재확인
- Account_Registry에 잘못된 계정으로 저장된 레코드가 0건인지 여부

## HOLD

- Runbook 내부의 Cross-secret Runtime 확인 표현과 재검증 체크리스트 사이 충돌은 이번 단계에서 수정하지 않고 HOLD한다.
- 위 UNKNOWN 3건이 확인되기 전까지 ERR-082 전체 SUCCESS·RESOLVED 선언을 금지한다.

## Backup Evidence

- 파일: `C:\backup_(17)_260728_0439_SNS_24AutoProject_260511.zip`
- 크기: `241,965,060 bytes`
- SHA-256: `1CD43E6D1B23F28A6A590E32B8E8000C212D5E28AB3A009629A14E7E7975A713`
- 전체 `28,882`개 항목 읽기 검사 PASS, `.env` 및 `.git/HEAD` 포함 확인, 프로그램 중단 없음

## CODEX Temporary Execution Exception

- 임시 실행 시작: `2026-07-28 04:48 ICT`
- 임시 실행 종료 예정: `2026-07-28 16:48 ICT`
- 승인자: 회장
- Claude Code 실행 역할을 12시간 한정으로 임시 대행하며, 영구 역할 변경이나 향후 선례가 아니다.
- `2026-07-28 16:48 ICT` 도달 즉시 CODEX는 기존 Read-only 감사 역할로 복귀한다.

## Next Gate

- 다음 Runtime Canary·문서 수정·Git 작업은 각각 별도 승인 전 실행하지 않는다.

---

# CURRENT_RUNTIME_CONTEXT.md
_마지막 업데이트: 260727_ERR-082_2-App_Webhook_Signature_Validation_로컬_구현_SUCCESS(배포_미완료)_(⚠️ 260706~260709 구간 여전히 별도 미반영, 아래 [260710] 섹션 Backlog #5 참조 — 이번 갱신 범위 밖, 그대로 승계)

## 현재 단계
**260727 14:32pm: ERR-082(Webhook 서명검증 부재) 2-App(Galaxy/yuna·AI Strategist) Route 분리 서명검증 로컬 구현·테스트 SUCCESS. 실제 `.env` Secret 입력·Meta Dashboard 등록·Runtime Restart·실제 Canary는 전부 미완료(회장 별도 승인 대상). 세션 계속 중.**

- **ERR-082 로컬 구현(260727)**: GPT가 결정한 Target Architecture(기존 `POST /webhook` 보존 + 신규 `POST /webhook/ai-strategist` additive 추가 + Route별 고정 App Secret + 공통 Fail-closed Validator)를 회장 승인 범위(코드·테스트 5파일+`.env.example` 1파일)대로 구현. 신규 `modules/common/webhook_signature.py`(순수함수) + `modules/dm/dm_receiver.py`(+51/-3, Business Logic `_process_webhook_event()` 바이트 단위 무변경) + `.env.example`(`WEBHOOK_APP_SECRET`/`AI_WEBHOOK_APP_SECRET`/`AI_WEBHOOK_VERIFY_TOKEN` placeholder).
- **검증**: 신규 `tests/test_webhook_signature.py`(10) + 기존 2파일 Signed Request 전환(8→23/10→10) 전부 PASS. 전체 Suite Before(원복) 606 passed/3 xfailed/0 failed → After 631 passed/3 xfailed/0 failed(재현 3회 일치, 신규 실패 0건). `git diff --check` 0건, 허용 6파일 외 Diff 0건, Secret 로그노출 0건, 환경변수 이름 코드·`.env.example` 100% 일치. 상세: `docs/ERROR_DATABASE.md` ERR-082 / `docs/WORKFLOW_ARCHITECTURE_STATUS.md` §10-9~10-10.
- **미완료(회장만 수행 가능한 항목 포함)**: 실제 `.env` Secret 값 입력(Claude Code 절대 금지 영역) / Meta Dashboard AI Callback·Verify Token 등록(Claude Code 접근권한 없음) / Runtime Restart(재시작 직전 별도 확인 필요) / 실제 Meta 서명 Payload Runtime Canary. 4개 전부 완료돼야 ERR-082 RESOLVED.
- **상태변경 범위**: 이번 세션 코드·테스트·`.env.example`은 전부 uncommitted 유지(HEAD `8c19808` 무변경). 문서 갱신(이 파일 포함)은 회장 명시 승인("7단계 진행 승인" → "문서화+안내자료" 선택) 하에 진행, Commit·Push는 별도 승인 대상으로 보류 중.

## 260726 마일스톤(이전 기록, 그대로 유효)
**260726: CLAUDE.md 거버넌스 대량 확장 + Bundle B(DM 계정 태깅) 구현·테스트 완료(킬스위치 OFF, 미배포) + ERR-082(Webhook 서명검증 부재) FAILED 확정 + CLAUDE.md↔SVES 문서 중복 정리(D2) + Meta App Topology B 확정.**

- **CLAUDE.md 거버넌스 추가(전부 uncommitted)**: "수정 승인 5요소 원칙"(회장 확정) + Codex 작성 26개 섹션 "SILICON VALLEY ENGINEERING OPERATING MANUAL" 원문 그대로 append(603줄) + "완료된 단계" 표(라인110 하단) 오독방지 각주 1줄(B안, 표 문구는 무변경).
- **Bundle B(DM `account_code_ref` 태깅, 260726)**: `modules/dm/dm_receiver.py`+`modules/infra/airtable_repository.py`+`modules/infra/repository_interface.py` 수정 + 신규 테스트 3파일(23 tests). `DM_ACCOUNT_ROUTING_ENABLED`(기본 false) 킬스위치로 기존 동작 무변화, fail-open 설계. 댓글·크롤러 경로는 이번 Bundle에서 제외(Codex 승인 조건). **미배포 상태로 uncommitted 유지** — ERR-082(아래) 해결 전까지 프로덕션 전환 HOLD.
- **ERR-082(Webhook `X-Hub-Signature-256` 서명검증 부재) — FAILED 확정**: `/webhook` POST(DM·댓글 공용, `receive_webhook()`)에 서명검증 코드·App Secret 저장소·HMAC 계산 로직이 전부 없음을 코드 전수확인(Grep 2회, 백그라운드 전체탐색 포함)으로 확정. 위조 Payload가 Airtable Write·자동응답·댓글처리까지 무방비 도달 가능(Blast Radius 확인) — **이 노출은 Bundle B 이전부터 있던 기존 운영 DM 경로의 위험**. Build·Buy·Reuse 비교 결과 Python 표준 `hmac`/`hashlib`로 Meta 공식 스펙 충족 가능(신규 OSS/SaaS 불필요, 유력후보). **구현 자체는 미착수, 회장 승인 대기.** (260727 로컬 구현으로 진행됨, 위 참조)
- **Meta App Topology 조사 — Topology B 확정**: Account_Registry 실측(`yuna18253`=IDN-000041/`facebook_login`/App ID `860604299884476`"Galaxy International", `aijomoojin`=IDN-000036/`instagram_login`/App ID `4522543077982497`"AI Strategist") — 회장이 Meta Dashboard 스크린샷으로 두 계정이 **서로 다른 Meta App**임을 직접 확인. 이어서 Callback→Runtime→Route 매핑 조사: **yuna18253은 이 260511 Runtime과의 연결이 Runtime Evidence로 CONFIRMED**(과거 `recipient.id` 실측 수신 기록), **aijomoojin은 이 Runtime 연결 여부 UNKNOWN**(인바운드 웹훅 수신 증거 0건, 발신 `publish_single()` 증거만 존재). `credential_resolver.py`에 App Secret 개념 자체가 코드에 없음도 확인. 복수 App Secret Keyring 설계는 aijomoojin 쪽 Mapping 미확정이라 **HOLD**(추측으로 만들지 않음).
- **CLAUDE.md↔`docs/SILICON_VALLEY_EXECUTION_STANDARD.md` 문서 중복 정리(D2 완료)**: CLAUDE.md 신규 매뉴얼과 SVES.md가 Evidence 우선순위·보고형식·Stage/Gate 절차를 서로 다르게 중복 규정하고 있던 것을 Claude Code가 Read-only로 전수조사 → GPT [260726_D2_EXECUTION] 지시서에 따라 **SVES.md 1개 파일만** 편집: §1에 7-Stage×12-Gate 매핑 신설, §3 Canonical Reporting Format, §5 Canonical Evidence Priority(9단계 단일화), §10~12 승인순서/Atomic Commit/Read-only Batch 규칙 신설, 구 원문 512줄은 §13으로 이동(비규범 표시, 내용 무손상). 15/15 성공기준 충족, 다른 파일 무변경.

## 260721 마일스톤(이전 기록, 그대로 유효)
- **배경**: Codex가 "AdsPower 시작프로그램 바로가기 대상 오류 수정 / n8n watchdog 무한재시도 원인 확정+비활성화 / Airtable Engagement 무효 ID 6개 정리"를 수행하며 git commit(`5165b8e`)까지 직접 실행 — CLAUDE.md "승인 범위 명시 원칙"·"git add/commit 선행 금지" 위반. 회장이 결과 재검토 및 이후 실행 주체 인계를 Claude Code에 지시.
- **Claude Code 독립 재검증(전부 read-only)**: commit `5165b8e` 실존·파일범위(`git show --stat`) 일치 확인 / AdsPower 바로가기 TargetPath·`TargetExists=True`·포트 50325 LISTENING 직접 재확인 / `SNS_Watchdog` 서비스 Running·Automatic 확인 / `watchdog.ps1` UTF-8 BOM(`EF BB BF`) 직접 hex 확인 / `tests/test_watchdog_encoding.py` 직접 재실행 3 passed 재현 / `watchdog.log` 원본에서 n8n 마지막 실패(12:16:37)→비활성화 로그(12:16:54) 이후 재시도 0건 확인 / Airtable MCP로 Codex가 명시한 6개 record ID의 `ig_media_id` 공란 직접 재조회 + `posted+ig_media_id 있음` 카운트 재집계 = **289 정확히 일치**. **결론: 절차 위반(권한 범위 초과)은 사실이나 보고 내용 자체의 허위·과장 없음, 6건 전부 CONFIRMED.**
- **AdsPower 재부팅 자동기동 실증(회장 명시 승인 후 실행, `AskUserQuestion`으로 영향 고지 후 진행)**: `Restart-Computer -Force` 실행(13:13) → `watchdog.log` 원본: `13:14:41 FATAL 종료` → `13:15:13 SNS_Watchdog 자동 재기동` → `13:15:18~37 Streamlit/ngrok/launcher 자동 복구` → `13:17:32~40 AdsPower Global 프로세스 8개 자동 실행`(수정된 바로가기 경로로 정상 작동). 재부팅 후 50325/5000/8501/4040 전부 LISTENING 재확인. **ERR-073/FP-054/INC-040의 "재부팅 자동기동 미검증(PENDING)"이 실증 PASS로 완전 종결.**
- **기록·커밋·push**: `docs/ERROR_DATABASE.md`(ERR-073)/`docs/FAILURE_PATTERN.md`(FP-054)/`docs/INCIDENT_TIMELINE.md`(INC-040)/`docs/VALIDATION_STATUS.md`/`porting_logs/MERGE_JOURNAL.md` 갱신, commit `2d57648`, `origin/master`에 push 완료(`1ebdc95..2d57648`). 커밋 시 기존 미커밋 상태였던 `docs/ERROR_DATABASE.md`의 ERR-068 부분은 blob 재구성 방식으로 정확히 제외하고 보존(git working tree에는 여전히 미커밋 상태로 남아있음, 의도된 상태).
- **여전히 보존·미커밋 상태(건드리지 않음)**: `configs/comment_campaign_posts.json`, `docs/ERROR_DATABASE.md`의 ERR-068 섹션, `docs/design/MANYCHAT_ACCOUNT_ROUTING_260715.md`(untracked).
- **여전히 미구현**: n8n 기능 자체(감시만 임시 중지, 워크플로우 WF-01~05는 미착수).
- 이전 마일스톤 — **FP-047 enforce 전제조건 A+B 완료(260716) → ManyChat kbeautiquewholesale Canary 성공 → RFC 웜핸드오프 설계변경(260717, 파일 미반영)은 이번 세션과 무관하게 그대로 유효**, 상세는 아래 "260717 마일스톤(이전 기록)" 참조.
- **[신규 백로그, 260721 13:51 회장 지정] 옴니채널 메시징(Omnichannel Messaging)**: 카카오톡/WhatsApp/Messenger 등 여러 채널로 들어오는 DM을 하나로 맵핑해 통합 대화 스레드로 응대하는 기능(에어비앤비 호스트-게스트 메시징 방식 참고). **현재 미구현 확인**(코드 전수조사 결과 — `modules/sns/content_filter.py`의 kakao/whatsapp/zalo/line 관련 코드는 FB 크롤링 중 판매자 연락처 노출을 걸러내는 스팸필터일 뿐, 실제 그 채널의 DM을 수신·통합하는 기능이 아님. 현재 실제로 살아있는 채널은 Instagram DM 1개뿐). 회장이 작업 착수를 지시했으나, 채널별로 각각 별도 Business API 심사(WhatsApp Business Platform/Kakao 비즈니스 채널/Messenger Platform)가 필요해 지금 진행 중인 Meta App Review(6일째 대기)와 유사한 규모의 대기시간이 각 채널마다 추가로 발생할 가능성이 높음 — 착수 전 회장과 범위·우선순위 재확인 필요(다음 세션 시작 시 first-touch 대상).

## 260717 마일스톤(이전 기록, 그대로 유효)
- **FP-047 enforce 전제조건 A**(커밋 `ab3c25d`, 260716): 댓글 원문이 로그/Telegram/retry payload 3곳에 평문으로 남던 문제(ERR-066과 같은 클래스) 해소. 공용 마스킹 유틸 `modules/common/pii_mask.py`(신규, ERR-070/FP-051 순환임포트 해결 겸용) + Fernet 암호화(retry payload, `enc_version` 엄격검증, fail-closed). enforce 모드 키검증 실패 시 launcher 전체가 아니라 댓글 처리만 거부(blast radius 한정 원칙 확립).
- **FP-047 enforce 전제조건 B**(커밋 `d456102`, 260716): `repository_interface.py`에 `verify_field_exists()` 추가, Airtable `Lead_Interactions.source_event_id` 필드 존재를 launcher 시작 시 Metadata API로 확인(startup preflight). A-2와 동일한 blast-radius 원칙 재사용.
- **부수 발견 — ERR-071/FP-052**(커밋 `e70f733`): B단계 신규 테스트 파일 추가로 pytest 수집 순서가 바뀌며 무관 테스트 2건이 일시 실패 — 근본원인은 `comment_safety_guard.COOLDOWN_HOURS`가 모듈 import 시점에 실제 `.env`(현재 0) 값으로 고정되는 구조였음. 테스트에 명시적 override 추가로 해결, 전체 회귀 원래 베이스라인(4 failed, `test_dm_close.py`만 무관)으로 복귀 확인.
- **ManyChat 전략 확정**: 자체 시스템과 ManyChat **병행 사용**(양자택일 아님) — 계정 1개(kbeautiquewholesale)는 ManyChat "Auto-DM links from comments"로 실운영 Canary 성공(실제 테스트 계정 댓글→Contact 등록→Inbox DM 확인). 도매/소매 qualifying 문구 반영("Wholesale"/"Retail" 표준 용어, "웜 핸드오프" 대화패턴 적용), FREE 플랜은 버튼 1개만 지원함을 확인(2버튼+태그 분기는 정식 Flow Builder 필요, 이번엔 버튼 1개+텍스트질문으로 타협). **남은 미완료: `View Details` 링크가 아직 `ubk.com` 플레이스홀더 — Shopify 결제 연동 완료 후 회장 직접 교체 예정.**
- **ManyChat 1000계정 확장 비용조사**: FREE는 활성 contact 25개로 제한(2026-03 정책변경), 유료 최저 $14/월(워크스페이스=계정당 별도과금) — 1000계정이면 월 $14,000+로 "마중물" 전략에 경제적으로 불가능함을 확정. **결론: 소수 대표계정(kbeautiquewholesale 등)=ManyChat, 대량 확장(1000계정 목표)=자체 시스템 필수. 단, 자체 시스템으로 1000계정을 실제로 뒷받침하는 인프라 설계는 "지금 필요 없음"으로 판단(회장 260717 확정) — 계정 1~2개조차 아직 매출 전환 증거가 없어 ROI-Gated Rollout 원칙상 시기상조.**
- **DM_RELAY_COMMERCE_RFC 설계 변경(260717, 파일 미반영 — 메모리만)**: 불변조건 #7("Supplier 답변 매번 회장님 수동승인") 폐기 → **"웜 핸드오프(Warm Handoff)"** 방식 확정 — Buyer 정보 확인 버튼 클릭이 트리거가 되어 실Supplier에게 DM 발송, 이후 Buyer↔Supplier 직접 소통. 불변조건 #1("Buyer에게 나가는 메시지는 항상 회장님 계정에서 발송")과 충돌 가능성 있어 재검토 필요. **다음 세션 최우선 작업: RFC 파일(`docs/design/DM_RELAY_COMMERCE_RFC.md`) 본문에 이 변경 정식 반영** — 세션 시작 프롬프트 이미 작성돼 회장님이 다음 세션 첫 메시지로 사용 예정.
- Meta App Review(4개 권한 신청 — `instagram_manage_comments`/`instagram_content_publish`/`instagram_manage_messages`/`instagram_basic`, 260715 00:35 제출)는 **260721 13:45 회장 직접 재확인(스크린샷) 기준으로도 여전히 "검토 진행 중"(상태: 정상, 대부분 20일 이내 소요 예상)** — 이용 사례별로 제출한 동영상 검수도 아직 안 끝남. 260716 최초 확인 이후 6일째 미결론, 다음 세션에도 재확인 필요.
- Gate C~G(260713~715, 이전 요약 그대로 유효) + 이전 마일스톤(260711 NSSM 전환, 260624 Repository Interface 전체 작업)은 그대로 유효.

## 최종 확인 커밋
2419ab2 (feat(dm): Bundle B — DM account_code_ref 계정 태깅 [260726], push 예정) — 직전 3f62213(docs: ERR-082 FAILED확정+세션인계), 519bf0b(docs: SVES D2 통합), 594be15(docs: CLAUDE.md 거버넌스 확장) 순으로 이어짐. 그 이전은 2d57648(docs(runtime): Codex 260721 작업 재검증 + AdsPower 재부팅 자동기동 실증 [260721]) — 직전 5165b8e(Codex: AdsPower/n8n/Engagement, 재검증 완료), 7f72976(watchdog UTF-8 BOM), 1ebdc95(FP-047 A+B/ManyChat/RFC 요약) 순으로 이어짐

## Source of Truth
- Runtime: C:\SNS_24AutoProject_260511
- Archive: C:\SNS_24AutoProject_250723 (삭제/dead 판정 금지)

## 마지막 확인 커밋 체인
- 9cc4ee9 (feat: CRAWL_TARGET_SOURCE Feature Flag — Airtable crawl_urls 동적 로드 [260619])
- 9d65cb4 (refactor: publish_single() 분리 — APScheduler/n8n 공용 게시 함수 [260617])
- 20bef95 (fix: last_error_msg L191 잔존 참조 제거 [260616])
- 463c350 (fix: retry_count/last_error_msg 필드 제거 + Graph API 실패 로깅 보강 [260616])
- 25c6779 (fix: image_url_hash FB CDN 중복 감지 개선 — URL 전체 대신 미디어ID 추출 [260616])
- 366c617 (fix: facebook_crawler import re 누락 추가 [260616])
- a126754 (fix: IMAGE_BLOCK_KEYWORDS에 M&Y GLOBAL 워터마크 패턴 추가 [260616])
- 0688849 (fix: clean_fb_metadata 호출 추가 — FB UI 잔여물 제거 [260616])

## Runtime 상태 (260622 기준)
| 구간 | 상태 | 근거 |
|---|---|---|
| Flask (dm_receiver) | ✅ LIVE | :5000 확인 |
| launcher/main.py | ✅ LIVE | watchdog.ps1 기동 중 |
| ngrok | ✅ LIVE | :4040 확인 |
| Streamlit | ✅ LIVE | :8501 확인 |
| n8n | ⚠️ 미구현(설계만, WF-01~05) | watchdog이 계속 재시작 시도하나 260711(LocalSystem 전환) 이후 성공 0건·실패 5,298건+ 누적 중(ERR-065, OPEN) — 실사용 대상 아님, 안정화 우선 후 진행+설계 재검토 예정(260715 회장 방침) |

## Dual Scheduler 해소 (260527)
| 항목 | Before | After |
|---|---|---|
| process_due_followups 실행 횟수/5분 | 2회 (27초 간격) | 1회 |
| :5000 바인딩 수 | 2 (watchdog Start-Flask + launcher) | 1 (launcher만) |
| watchdog.ps1 Start-Flask | ACTIVE | 주석 처리 완료 |
| 근거 | app.log 22:00:34 / 22:05:34 단일 실행 2사이클 확인 | ERR-021 / FP-017 / INC-011 |

## E2E AutoReply 증거
| 증거 | 상태 | 내용 |
|---|---|---|
| 화면 증거 | ✅ CONFIRMED | "단가 기준가는 11,000원" (5/12) |
| 로그 증거 | ❌ LOST | overwrite 구조로 소멸 |
| 코드 경로 | ✅ CONFIRMED | get_base_price() → Airtable → 응답 정상 |

## 250723 스캔 결과
- 전체 스캔 완료
- 이식 대상 없음 확정
- pytest: 613 passed / 17 failed / 6 errors — Green Build 아님
- 역할: Archive / Evidence 참고용만

## Known Fact
- DEFAULT_BASE_PRICE=50000 .env 설정 확인
- dual scheduler 중복 발송 → **260527 해소 완료** (watchdog.ps1 Start-Flask 주석 처리)
- webhook_stderr.log overwrite 구조 확인됨
- Windows venv shim: .venv\Scripts\python.exe(268KB) → Python310\python.exe(103KB) 자식 프로세스 — 2 PID 정상 (1 논리 인스턴스)
- 중복 발송 버그 → **260528 해소 완료** (_has_recent_auto_replied() CREATED_TIME() 기준 3분 window)
- _rule.reason AttributeError → **260528 해소 완료** (getattr fallback)
- SNS_Watchdog_AutoStart 작업 스케줄러 등록 → ✅ **등록 완료** (260529 관리자 권한으로 등록) → ⚠️ **260705 정정: "등록 완료"≠"실제 재기동 보장" 확인** — 06-29 이후 실제 재부팅 9회에도 Last Run Time 갱신 없음, watchdog.log 07-01 23:36 이후 4일+ 무기록. 상세: ERR-047 / FP-035 / INC-025 (미해결, OPEN)
- accounts.json 빈 배열 → crawl_urls skip → **260529 해소 완료** (account1 + crawl_url 등록)
- Airtable caption 필드 없음 → 422 UNKNOWN_FIELD_NAME → **260529 해소** → **260612 재발 → 재해소** (API로 multilineText 필드 추가, field_id=fldcxTzLzYCzD9aYe)
- FB 크롤러 2회 연속 정상 완료 → **260529 19:43 / 20:13 확인**
- crawl_urls 4개 그룹 확장 → **260602 완료** (3dbe72a)
- accounts.json BOM 제거 → **260602 완료** (c6a30d1) — PowerShell Set-Content UTF8 금지
- facebook_crawler.py load_dotenv 추가 → **260602 완료** (f5d59f2)
- pytest 104 passed / 1 xfailed / 2 xpassed 확인 (260602)
- deep-translator 1.11.4 설치 완료 (260602)
- 시스템 환경변수 AIRTABLE_API_KEY 플레이스홀더(`pat여기에전체토큰`) → **260602 제거 완료** (User scope + 세션 제거)
- bot_uploader.py → insta_uploader.py 체인: **dead stub 확인** — 실제 Graph API 호출 없음, launcher/main.py가 실제 업로더
- caption clean_fb_metadata() → **260602 완료** (349fedf) — 작성자명·경과시간·구분점(·) 제거
- Airtable ready 레코드 caption 오염 일괄 정정 → **260602 완료** (2건: recKLX1OsOvfRu5k1, recsmA4WIlrur1wHO)
- Instagram 업로드 Runtime Proof → **260602 완료** — recFyw7OUaZ666JDJ / ig_media_id=18101360630320704 / post_status=posted ✅
- 백업 완료: C:\backup_(12)_260602_2207_SNS_24AutoProject_260511.zip
- 최종 commit: 2695d87
- Supplier_Blocklist 실제 차단 적용 → **260611 완료** (11fc204) — DRY_RUN 제거, continue 적용
- LOST 72h 타임아웃 구현 → **260611 완료** (0e5133b) — DRY_RUN 모드, 실운영은 LOST_DRY_RUN=false 설정 후 활성화
- Lead_Interactions lost_reason / lost_at / disqualified 필드 추가 → **260611 완료** (Airtable UI)
- filter_rules.json + generate_filter_rules.py 추가 → **260611 완료** (3840a6a) — 운영 연동 금지, 분석용 전용
- FB그룹 1676627532598134 제거 → **260612 완료** (c71f2c7) — 인도 비율 높음, accounts.json + Crawl_Targets 동시 삭제
- ig_media_id 17863634121631171 클리어 → **260612 완료** — rectwruMD3uua54sv, engagement_tracker 반복 오류 해소
- crawl_urls 현재 5개 운영 중 (FB_GROUP_POOL_V1): 610113703703488(Hold) / 345179878828208 / 755455243345993 / 3289570041331131 / 1827528710833477
- upload_rate 6.2% → caption 필드 복구로 다음 크롤링부터 회복 예상 (260612)
- post_status ready/uploading 옵션 소실 → **260616 해소** (typecast 더미 레코드 방식으로 강제 복구)
- uploading 고착 28건 (Regine Kim 포스트 동일 이미지) → **260616 failed 일괄 마킹** (200 OK 전부)
- retry_count/last_error_msg UNKNOWN_FIELD_NAME → **260616 해소** (463c350 — 두 필드 코드에서 제거)
- image_url_hash URL 전체 해시 → CDN 노드 달라 중복 미탐지 → **260616 해소** (25c6779 — FB 미디어 ID 추출로 변경)
- import re 누락 → [FB Crawler] 크롤링 실패 | name 're' is not defined → **260616 해소** (366c617)
- Instagram 업로드 성공 → **260616 02:07 KST 확인** | recw3EHD8d9uiP2FX | post_id=18122871268709171 ✅
- M&Y GLOBAL / Mooncher Kim Supplier_Blocklist 등록 → **260616 완료** | recEDhkour93vZR74 | reason_code=BLOCK_WATERMARK_SUPPLIER
- _IMAGE_BLOCK_KEYWORDS에 `r'm&y\s*global'` 추가 → **260616 완료** (a126754)
- `clean_fb_metadata()` facebook_crawler.py L202 호출 추가 → **260616 완료** (0688849) — raw_text 추출 직후 작성자명·경과시간 제거
- `modules/sns/image_hosting.py` 신규 추가 → **260616 완료** — imgbb 업로드 유틸 (다운로드→MIME검증→SHA256→업로드→URL검증)
- `publish_single()` 분리 → **260617 완료** (9d65cb4) — launcher/main.py 게시 로직 독립 함수화, APScheduler + n8n Endpoint 공용 호출 가능
- `last_error_msg` L191 잔존 참조 제거 → **260616/17 완료** (20bef95)
- n8n Architecture 설계 → **260617 확정** (DESIGN_COMPLETE) — WF-01 Posting Scheduler / WF-02 DM Webhook / WF-03 Credential Health / WF-04 Failure Recovery / WF-05 Runtime Alert
- Credential 구조 Option B 확정 — Python이 Graph API Token 소유 (.env CRED_{ref}_TOKEN), n8n Token 비보유
- Canonical Status: post_status 단일 사용 (publish_status 미사용)
- `execution_owner` 필드 — **미구현 (P0 Backlog)**
- FB_MAX_POSTS=20 .env 설정 완료 (260619)
- Crawl_Targets 스키마 확장: platform/max_posts/account_ref/last_run_at/last_result 필드 추가 (260619)
- account_manager.py _load_crawl_urls_from_airtable() + _shadow_compare() 추가 (260619) — 9cc4ee9
- CRAWL_TARGET_SOURCE Feature Flag 구현 (260619): accounts_json(기본)/shadow(비교 로그)/airtable(URL 교체)
- Shadow 모드 검증 완료 (260619): accounts.json=5건 vs Airtable=4건, 누락 그룹 610113703703488 감지
- CRAWL_TARGET_SOURCE=airtable 전환 → Airtable 4건 URL 기반 크롤링 Runtime Proof 완료 (260619)
- accounts.json: 계정/세션 정보 전용 유지 / crawl_urls: Airtable Crawl_Targets 단일 소스 (260619)
- heartbeat_monitor.py 신규 추가 (b2aa30d) — watchdog.ps1과 독립된 Task Scheduler 기반(5분 주기) heartbeat 정지 감지 + Slack 알림
- ERR-052/FP-039/INC-029: 250723 참조 활성 Task 2건(SNS_AUTO_PRODUCTION/SNS_Auto_Run) 발견 → Disable-ScheduledTask로 비활성화 완료
- ERR-053/FP-040: heartbeat_monitor.py 예약 작업이 WakeToRun=False로 Modern Standby 중 71회(5시간47분) 미실행 근본원인 확정 → WakeToRun=True로 변경 완료(260710), 실제 절전 구간 재현 검증은 다음 세션 대기
- INC-028 Note 3: 1차 다운(20:09:40)의 실제 원인 확정 — Modern Standby 아님, 실제 OS shutdown(StartMenuExperienceHost.exe 명의, 20:09:52 개시). 사람의 조작 가능성 Hypothesis(확정 아님)
- PENDING-A(docs/PENDING_INVESTIGATIONS.md 신규): watchdog/heartbeat_monitor NSSM 전환 검토 — AdsPower Local API의 Session 0(S4U) 응답성 실증 SUCCESS 확인, 실제 전환 여부는 별도 결정 대기
- CLAUDE.md governance 2건 추가: "승인 범위 명시 원칙"(read-only 조사 승인이 문서기록/commit까지 자동 포함하지 않음), "단계별 Bookending 원칙"(작업 전/후 상태 한 줄 확인)

## 미해결 항목 (Phase 후순위)
- **[P0 — 다음 세션]** Instagram_Posts.execution_owner 필드 Airtable 추가
- **[P0 — 다음 세션]** APScheduler 조회 조건 수정: post_status=ready AND execution_owner 없음
- **[P0 — 다음 세션]** /api/v1/instagram/publish Endpoint 구현 (modules/sns/instagram_publish_api.py)
- **[P0 — 다음 세션]** DRY_RUN 검증 (PUBLISH_API_DRY_RUN=true → false 전환)
- **[P0 — 다음 세션]** 테스트용 Record 1건 생성 후 실제 게시 Runtime Proof
- 그룹 610113703703488: div[role='feed'] 미탐지 — 가입 승인 대기 중 (코드 문제 아님)
- LOST_DRY_RUN=false 전환 대기 — 실운영 전 Airtable 필드 확인 후 적용
- 워터마크 제외 로직 — **260616 부분 구현** (_IMAGE_BLOCK_KEYWORDS + Supplier_Blocklist 등록), passes_image_filter 이미지 픽셀 분석 미구현
- data/processed_comment_ids.json untracked 유지 (정상 — gitignore 대상)
- 백업 필요 시점 도달 (마지막 백업: backup_(12)_260602_2207)
- ~~**[P1 — 다음 세션]** 도매꾹(domeggook) 크롤러 추가~~ → **완료**(260619 세션2~8, D001/D002 Active 실운영 중, dome_crawl/dome_export APScheduler 잡 정상 — 이 목록 자체가 오래 미정리된 상태였음)
- **[P1 — 다음 세션]** heartbeat_monitor.py WakeToRun=True 변경 후 실제 Modern Standby 구간에서 로그가 이어지는지 실증 검증 대기 (유일하게 남은 절전 관련 미검증 항목)
- ~~**[P1 — 다음 세션]** watchdog.ps1 자체의 절전/1차다운 근본 메커니즘 여전히 UNKNOWN~~ → **260711 구조적 해소**: watchdog.ps1을 Task Scheduler 기반에서 NSSM Windows 서비스로 전환, 크래시 재시작+재부팅 실증 PASS(ERR-057/058, PENDING-A 종결) — Task Scheduler 고유 결함(WakeToRun 등) 자체가 더 이상 해당 없음
- ~~**[P1]** ERR-047 핵심 증상(재부팅 후 SNS_Watchdog_AutoStart 무재실행) 자체는 여전히 미해결(OPEN)~~ → **260711 해소**(위와 동일 사유, 구조 자체 교체)
- **[P2]** ERR-051/FP-038 Task Scheduler launch-only 실패 근본원인 미확정 (watchdog.ps1은 더 이상 Task Scheduler 아니므로 영향 범위 축소, 다른 Task 대상 잔존 여부만 저위험으로 남음)
- ~~**[P2]** PENDING-A(NSSM 전환) 최종 결정 — 사용자 승인 필요~~ → **260711 완전 종결**(ERR-057/058 참조)
- ~~**[P2 — 신규]** n8n(PID 10248 등) watchdog.ps1이 계속 재시작 시도·실패하며 알림만 반복 발생~~ → **260715 근본원인 확인**(ERR-065/FP-049/INC-037): LocalSystem 전환 후 npx 대화형 설치 프롬프트에서 좀비 프로세스 발생 가설(미확정), 성공 0건·실패 5,298건+ 누적. **Fix 미적용** — 회장 방침: 안정화 우선, n8n은 나중에 진행+설계(WF-01~05) 재검토 예정
- ~~**[P0-1 → ERR-066, OPEN]** `dm_receiver.send_telegram()` IGSID·원문 무마스킹~~ → **260715 RESOLVED**(패키지 A1): `_mask_igsid()`/`_telegram_preview()` 재사용 적용 + DM 수신 로그 원문 완전 제거, Runtime Proof로 마스킹 확인, pytest 30 passed
- ~~**[FP-047, OPEN, 재확인 260715]** 댓글 Airtable 기록(`_record_comment()`) 실패 시 예외를 삼키고 무조건 캐시에 처리완료로 남겨 재시도 없이 영구 유실~~ → **260715~716 코드 구현 완료**(커밋 `00466a3`): `comment_event_store.py` fencing claim + retry_queue 위임으로 근본 수정. `COMMENT_EVENT_STORE_MODE=disabled`(기본값)로 커밋 — enforce 전환 전 필수 항목이던 원문 평문 저장/Airtable preflight는 **260716~17 A+B로 완료**(아래 항목).
- ~~**[enforce 전환 전 필수 A+B, OPEN]** 댓글 원문 평문 저장(ERR-066과 같은 클래스), Airtable 필드 존재 startup preflight 미구현~~ → **260716~17 코드 구현 완료**: A(커밋 `ab3c25d`, PII 마스킹+retry payload 암호화), B(커밋 `d456102`, `verify_field_exists()` startup preflight). **`COMMENT_EVENT_STORE_MODE`/`COMMENT_POLL_ALLOWLIST_MODE` 운영 모드 전환(enforce/allowlist)은 여전히 미실행 — 별도 승인 대상으로 남음.**
- **[ERR-069/FP-050/INC-038, 코드 구현 완료·운영 미전환]** "최근 게시물 N개" 폴링 한도로 캠페인 댓글이 시스템 진입 자체를 못 하던 결함(실사용자 테스트로 발견) — Package 1(Phase A, 커밋 `eb98741`)로 근본 수정. `COMMENT_POLL_ALLOWLIST_MODE=legacy`(기본값)로 커밋 — **이 결함을 만든 "최근 N개" 방식이 여전히 운영 중**이라, allowlist 모드 전환 전까지는 동일 누락이 재발할 수 있음을 인지할 것. **Phase B(allowlist 전환·6개 media 순차 baseline) 자체는 아직 착수 안 함 — 별도 세션·별도 승인 대상.**
- ~~**[신규, 미커밋]** `modules/comment/comment_auto_reply.py`의 가격 키워드 확대(스팸/부정 제외 전부 응답 대상, 260715 회장 지시) + 쿨다운 0h·일일예산 사실상 무제한~~ → **260716 커밋 완료**(`210f72b`, 스팸/부정 필터 강화와 함께 커밋됨).
- **[ERR-064/FP-048/INC-036, OPEN — 부분 완화]** 앱 테스터 미등록 실계정과의 DM 왕복 시 손님 답장 웹훅 미도착(Standard Access 의심, 미확정) — Meta App Review 4개 권한 신청 260716 재확인 기준 "검토 진행 중"(최대 20일 소요, 여전히 미결론). **ManyChat 병행 전략 확정 + kbeautiquewholesale 1개 계정 실운영 Canary 성공**(Advanced Access라 이 문제 자체가 없음) — 완전한 대체는 아니지만 리스크 완화 경로 확보됨. Meta 심사 결과는 **다음 세션 시작 시에도 계속 확인 필요**.
- ~~**[ERR-063]** `test_dm_rules.py` hang, 원인 UNKNOWN~~ → **260715 RESOLVED**: 실제 Gemini API 호출(`generate_reply()`)을 mock하지 않은 테스트 설계 누락 확인, 7.48초 재현 실증. 테스트에 mock 추가하는 실제 수정은 미착수(기록만)
- ~~**[ERR-071/FP-052, OPEN]** 신규~~ → **260716 RESOLVED**: `comment_safety_guard.COOLDOWN_HOURS` 모듈 상수가 실제 `.env` 값에 고정되던 테스트 격리 버그, 커밋 `e70f733`로 해결.
- **[신규, 260717]** DM_RELAY_COMMERCE_RFC 설계 변경(불변조건 #7 폐기→웜 핸드오프) — **파일 본문 미반영, 다음 세션 최우선 작업**. 불변조건 #1과의 충돌 가능성 재검토 필요.
- **[신규, 260717]** ManyChat kbeautiquewholesale `View Details` 링크 — 아직 `ubk.com` 플레이스홀더, Shopify 결제 연동 완료 후 회장 직접 교체 예정(코드/승인 불필요, 순수 운영 작업).

## 절대 금지
- 250723 삭제/dead 판정
- 폴더 merge/전체 복사
- Evidence 없는 완료 선언
- 코드 수정 (승인 전)
- git add/commit 선행
- PowerShell Set-Content -Encoding UTF8 로 JSON 파일 저장 (BOM 삽입됨 — [System.IO.File]::WriteAllText + UTF8Encoding(false) 사용)

## [260528_Virtual_AutoReply_Proof] — 2026-05-28 13:27 KST
- Infra: Flask :5000 PID 14256 + ngrok :4040 PID 8956 LISTENING 확인
- Webhook: 로컬 POST 200 OK 확인
- Parser: 단가 얼마예요? detect_price_inquiry=True 확인
- AutoReply: DEFAULT_BASE_PRICE=50000 적용, handle_price_inquiry 완료
- Airtable: LI-2B0A72F7 생성, recXgM9FlDo9EEikr qualified/auto_replied
- IG 발송 실패: TEST_SENDER_004 가상 ID 정상 예상 결과
- 백업: backup_(7)_260528_1338 완료

## [260528_Real_DM_AutoReply_Proof] — 2026-05-28 20:14 KST
- 실계정 IGSID: 1792783944739953
- IG DM 발송 완료: 20:14:37 msg_id 확인 (recKh3tm6R5foxjjv)
- Lead 상태: qualified / auto_replied
- Telegram 알림: 성공 (1회 ConnectionReset 후 복구)

## [260528_Duplicate_Bug_Fix] — 2026-05-28 21:42 KST
- 버그1: _rule.reason AttributeError → getattr(_rule, "reason", "unknown") 수정
- 버그2: 중복 발송 → _has_recent_auto_replied() 추가 (CREATED_TIME() 기준 3분 window)
- 검증: 21:42:15 duplicate skip recvpUz9Q6YW4EsPv ✅
- 검증: 21:50:03 duplicate skip recKeIWfh5YtBLhzo ✅
- 수정 파일: modules/dm/dm_auto_reply.py ✅ 72e0e1a 커밋 완료

## [260529_Crawler_Normalization] — 2026-05-29 KST
- ERR-027: accounts.json `[]` → crawl_urls skip → account1 등록으로 해소 (7ce335e)
- ERR-028: Airtable caption 필드 없음 → 422 → UI에서 Long text 필드 추가로 해소
- 검증: 19:43:40 `계정 완료 | account=account1 | 3개` ✅
- 검증: 20:13:41 `계정 완료 | account=account1 | 3개` ✅

## [260601~260602_Clone_Mode_Proof] — 2026-06-02 01:08 KST
- Phase 1: replace_contacts() 매핑 추가 (c8000ee)
- Phase 2: generate_caption_clone() 추가 (3ed3b45)
- Phase 3: facebook_crawler clone 경로 연결 (b059740)
- Phase 4: keyword filter 확장 + BRAND_ALLOWLIST (25c3f13)
- Phase 5: comment auto-reply 안전장치 COMMENT_AUTO_REPLY_ENABLED=false (a64b0ff)
- Phase 6: expand_see_more() 추가 + Runtime Proof (deec24c)
- Runtime Proof: recsmA4WIlrur1wHO — original_text / converted_text / caption / media_type=image 전부 저장 확인 ✅
- 백업: C:\backup_(11)_260602_0108_SNS_24AutoProject_260511.zip

## [260602_섹션19_Instagram_Upload_Runtime_Proof] — 2026-06-02 16:20 KST
- 업로드 체인 분석: bot_uploader→insta_uploader dead stub 확인, 실제 업로더=launcher/main.py:159
- 환경변수 이슈: 시스템 AIRTABLE_API_KEY 플레이스홀더 → latin-1 UnicodeEncodeError → User scope 삭제 해소
- find_dotenv() 탐색 실패 원인 확인: temp 경로 실행 시 발생 — 절대경로 load_dotenv 사용으로 우회
- ERR-037 해소: caption Facebook UI 잔여물(작성자명·경과시간··) → clean_fb_metadata() 추가 (349fedf)
- Airtable ready 레코드 2건 caption 일괄 정정 완료
- **Graph API 업로드 성공 증거:**
  - 대상: recFyw7OUaZ666JDJ
  - 이미지: 960×1707 ratio=0.56 → imgbb center-crop → https://i.ibb.co/dwnMVq7Z/2547998023eb.jpg
  - /media id: 17889472404540095
  - /media_publish id (ig_media_id): **18101360630320704** ✅
  - Airtable post_status: ready → uploading → **posted** ✅

## [260602_섹션19_Clone_Mode_그룹URL_다중화] — 2026-06-02 13:40 KST
- crawl_urls 1개 → 4개 그룹 확장 (3dbe72a)
  - 1676627532598134 (K-beauty 필리핀 중고 그룹)
  - 610113703703488 (feed 셀렉터 실패 — 가입 승인 대기)
  - 345179878828208 (기존 그룹, Airtable 저장 확인 ✅)
  - 755455243345993 (신규 그룹)
- accounts.json BOM 제거 (c6a30d1) — PowerShell Set-Content UTF8 BOM 삽입 버그 수정
- facebook_crawler.py load_dotenv(override=True) 추가 (f5d59f2) — 모듈 직접 실행 시 .env 로드 보장
- Airtable 저장 성공 재확인: 그룹 345179878828208 → [AIRTABLE] 저장 완료 ✅
- pytest 104 passed / 1 xfailed / 2 xpassed ✅
- deep-translator 1.11.4 pip install 완료
- 백업 필요 시점 도달 (다음 세션 초반 백업 권장)

## [260612_운영정비] — 2026-06-12 00:26 KST
- Supplier_Blocklist 실차단 적용 (11fc204) — DRY_RUN 로그 제거, 매칭 시 continue로 실제 skip
- LOST 72h 타임아웃 구현 (0e5133b) — followup3_sent + 72h 경과 → LOST 자동 전환, DRY_RUN 모드
  - 실운영 전환 조건: .env LOST_DRY_RUN=false 설정
- Lead_Interactions 필드 추가: lost_reason(Single line) / lost_at(Date) / disqualified(Checkbox)
- filter_rules.json + generate_filter_rules.py (3840a6a) — Crawl_Training_Set 기반 분석 전용, 운영 연동 금지
- FB그룹 1676627532598134 제거 (c71f2c7) — Crawl_Targets 레코드 삭제 + accounts.json crawl_urls 제거
  - 사유: 인도 트래픽 비율 높음, K-beauty 타겟 부적합
  - crawl_urls 5개 → 5개 유지 (610113703703488 Hold 포함)
- Instagram_Posts.caption 필드 재추가 — API로 multilineText 추가 (fldcxTzLzYCzD9aYe), 422 오류 해소
  - 원인: 260529 UI 추가 후 어느 시점 삭제됨
- ig_media_id 17863634121631171 클리어 (rectwruMD3uua54sv) — engagement_tracker 30분 간격 반복 오류 해소
- launcher/main.py 기동 확인 (00:26 KST) — Flask :5000 / APScheduler 8잡 / RetryQueue 정상
  - AdsPower 미실행으로 FB 크롤링 WinError 10061 (AdsPower 기동 후 자동 복구)
- upload_rate 6.2% — caption 필드 복구로 다음 크롤링부터 ready 레코드 누적 회복 예상
- 최신 커밋: 0688849 / GitHub push 완료

## [260616_운영정비_2차] — 2026-06-16 23:00 KST
- M&Y GLOBAL 워터마크 공급자 차단:
  - Supplier_Blocklist 등록: author_name=Mooncher Kim / page_name=M&Y GLOBAL / reason_code=BLOCK_WATERMARK_SUPPLIER (recEDhkour93vZR74)
  - content_filter._IMAGE_BLOCK_KEYWORDS에 `r'm&y\s*global'` 추가 (a126754)
- `facebook_crawler.py`에 `clean_fb_metadata()` 호출 추가 (0688849):
  - raw_text 추출 직후 L202에서 clean_fb_metadata(raw_text) 호출
  - 작성자명·경과시간·구분점(·) 제거 후 필터링 → 오탐 방지
  - import L14에 clean_fb_metadata 추가
- `modules/sns/image_hosting.py` 신규 생성 (BOM없음, 54줄):
  - upload_to_imgbb(source_url) — imgbb API 래퍼
  - MIME 검증 / 32MB 제한 / SHA256 content_hash / HEAD 공개 URL 검증
  - 향후 launcher/main.py _preprocess_image() 대체 후보
- Blocklist 로드 완료: 5건 (M&Y GLOBAL 추가 후 확인)
- Regine Kim 포스트 A-F3-260616-001 업로드 성공 → posted 확인 ✅
- 런처 재기동: 23:00 KST (clean_fb_metadata 적용 버전)

## [260616_버그수정] — 2026-06-16 02:07 KST
- post_status 옵션 소실 (ready/uploading 없음) → Airtable Meta API PATCH 422 → typecast:True 더미 레코드 방식으로 강제 복구
  - 복구 후 옵션 목록: ['draft', 'scheduled', 'posted', 'failed', 'ready', 'uploading'] ✅
- uploading 고착 28건 일괄 마킹:
  - 원인①: FB CDN 동일 이미지를 다른 노드(fhan15-2, fdad3-8, fhan5-6)로 서빙 → URL 해시 달라 중복 28건 저장
  - 원인②: Graph API 업로드 실패 후 retry_count UNKNOWN_FIELD_NAME 예외 → uploading 고착
  - 조치: 28건 전체 post_status=failed PATCH 완료 (200 OK)
- retry_count/last_error_msg 필드 제거 (463c350):
  - launcher/main.py 성공/실패 경로 양쪽에서 두 필드 참조 제거
  - 실패 에러 내용은 logger.error로 직접 출력으로 대체
- image_url_hash 개선 (25c6779):
  - Before: `hashlib.sha256(image_url.encode())` — CDN 노드 다르면 다른 해시
  - After: `re.search(r"/(\d+_\d+(?:_\d+)*)[_.]", image_url)` → FB 미디어 ID 추출 후 해시
  - 검증: 3개 CDN URL → 동일 미디어 ID → 동일 해시 ✅
- import re 추가 (366c617): facebook_crawler.py 상단 `import re` 누락 수정
- Instagram 업로드 성공 증거:
  - 대상: recw3EHD8d9uiP2FX
  - /media_publish id (ig_media_id): **18122871268709171** ✅
  - Airtable post_status: ready → uploading → **posted** ✅
- 최신 커밋: 366c617 / GitHub push 완료
## [260617] Airtable Account DB 구축 완료

### 변경사항
- Account_Registry 필드 추가: identity_id / category / automation_enabled / pilot_wave / identity_status / adspower_profile_id
- 유효 계정 33개 확정 (중복/빈행 정리 완료)
- Platform_Accounts 테이블 신규 생성 (tblkdk5dEagfQvUMp)
- Instagram 19개 + Facebook 12개 = 31개 입력
- Instagram_Posts 라우팅 필드 추가: target_identity_id / target_platform_account_id / publish_status / run_id / scheduled_at
- Account_Registry <-> Platform_Accounts Linked Record 연결 (fldcRdC6XdGnMILqI)
- Pilot 3개 Active: IDN-000036(nguyenknv15) / IDN-000038(nhm880808) / IDN-000016(kang88jungmin)

### Airtable 현재 상태
- Base ID: apphJNTHWNoFcVb1D
- Account_Registry: 33개 (Active 3 / Ready 30)
- Platform_Accounts: 31개

### 다음 단계
- n8n 워크플로우 설계 (별도 세션)
- Pilot 3개 Runtime 포스팅 검증
- 3 -> 10 -> 33개 확장


## [260617] ImgBB 연동 + 데이터 정합성 복구 세션

### 완료 작업
1. Dashboard 복구 — Flask :5000 / Streamlit :8501 / watchdog 정상 기동
2. Instagram 업로드 실패 원인 확정 — Facebook CDN URL -> Instagram Graph API error_subcode 2207052
3. imgbb 연동 (Phase 1~4)
   - original_image_url 필드 추가 (fldEpMV0uFiWR7OmB)
   - IMGBB_API_KEY .env 추가
   - modules/sns/image_hosting.py 신규 생성
   - tools/backfill_failed_images.py 신규 생성 (DRY_RUN=true 기본값)
4. Backfill 1건 End-to-End 실증 — rec2v96YaBLQJvLyl: failed->ready->posted (ig_media_id: 18071004683495931)
5. 데이터 정합성 복구
   - ig_media_id 있는 failed 78건 Graph API 검증
   - VERIFIED_POSTED 3건 -> posted 복구
   - INVALID 75건 -> ig_media_id 클리어
6. 버그 수정 — launcher/main.py: unverified ig_media_id -> posted 강제전환 제거 (commit e33cf37)
7. Phase 4 — facebook_crawler.py save_to_airtable()에 imgbb 업로드 연동 (commit af85d3a)

### 현재 Airtable 상태
- failed: 145건 / posted: 14건 / ready: 0건
- 성공률: 6.2% -> 8.2% 개선

### Git 커밋 (260617 세션)
- e33cf37: fix: prevent unverified ig_media_id from forcing posted status
- 3b3fedf: feat: add ImgBB image hosting adapter
- 6ab2ff0: feat: add guarded failed-image backfill utility
- af85d3a: feat: integrate ImgBB upload in save_to_airtable (Phase4)

### 미완료
- Runtime Proof: 신규 크롤링 1건 ImgBB 성공 로그 확인 (진행 중)
- failed 145건 backfill (Phase 3 보류)
- push 미실행 (별도 승인 필요)
- 안정화 후 API 키 재발급 필요 (AIRTABLE/INSTA/GEMINI/TELEGRAM/SLACK/IMGBB)

## [260617_n8n설계_publish_single분리] — 2026-06-17 KST

### publish_single() 분리 (9d65cb4)
- launcher/main.py 게시 로직을 publish_single() 독립 함수로 분리
- _job_insta_upload(): uploading 마킹 후 publish_single() 1줄 위임
- n8n Endpoint와 APScheduler 공통 호출 가능 구조 확보
- Token/ig_user_id 호출자 주입, 함수 내 저장소 참조 없음, 로그 access_token 출력 금지
- Runtime Proof: NOT_EXECUTED (260617 기준 ready 레코드 0건)

### last_error_msg L191 잔존 참조 제거 (20bef95)
- launcher/main.py L191 image_url 없음 조기 실패 경로에서 last_error_msg 제거
- ERR-041 완전 해소

### n8n Architecture 설계 확정 (DESIGN_COMPLETE)
- WF-01: Posting Scheduler — Airtable ready 레코드 폴링 → /api/v1/instagram/publish 호출
- WF-02: Real-time DM Webhook — Meta Webhook → Python dm_receiver 처리
- WF-03: Credential Health Check — 계정 토큰 주기적 검증
- WF-04: Failure/Recovery Watchdog — failed 레코드 재시도 조율
- WF-05: Runtime Alert — 오류/비정상 감지 → Slack 알림
- Credential 구조 Option B 확정: Python Graph API Token 소유 (.env CRED_{ref}_TOKEN), n8n Token 비보유
- Canonical Status: post_status 단일 (publish_status 신규 필드 미사용)

### P0 Backlog (다음 세션)
1. Instagram_Posts.execution_owner 필드 Airtable 추가
2. APScheduler _job_insta_upload() 조회 조건 수정
3. modules/sns/instagram_publish_api.py — /api/v1/instagram/publish Blueprint 구현
4. dm_receiver.py Blueprint 등록
5. PUBLISH_API_DRY_RUN=true 검증 → false 전환
6. 테스트용 Record 1건 생성 → 실제 게시 Runtime Proof

## [260619_Airtable_crawl_urls_전환] — 2026-06-19 KST

### 완료 작업
1. FB_MAX_POSTS=20 .env 설정 완료
2. Crawl_Targets 스키마 확장: platform(singleSelect)/max_posts(number)/account_ref(singleLineText)/last_run_at(dateTime)/last_result(singleLineText) 필드 추가 (Airtable Metadata API)
3. account_manager.py _load_crawl_urls_from_airtable() + _shadow_compare() 추가
4. CRAWL_TARGET_SOURCE Feature Flag 구현: accounts_json(기본) / shadow(비교 로그) / airtable(URL 교체)
5. Shadow 모드 검증: accounts.json=5건 / Airtable=4건 / 누락 그룹(610113703703488 Hold) 정상 감지
6. CRAWL_TARGET_SOURCE=airtable 전환 — Airtable 4건 URL 기반 크롤링 Runtime Proof 완료
   - groups/1827528710833477 → 1건 수집 (720×1280, imgbb 중복 skip 정상)
7. accounts.json → 계정/세션 정보 전용 유지 / crawl_urls → Airtable Crawl_Targets 단일 소스

### Git
- 커밋: 9cc4ee9 (feat: CRAWL_TARGET_SOURCE Feature Flag — Airtable crawl_urls 동적 로드 [260619])
- push: origin/master 완료

### 다음 세션 예정
- 도매꾹(domeggook) 크롤러 추가 — Crawl_Targets platform=domeggook 지원

## [260619_도매꾹크롤러] — 2026-06-19 KST (세션2)

### 완료 작업
1. 도매꾹 Open API 개통 확인 (ver=4.1, aid=DOMEGGOOK_API_KEY, om=json)
2. modules/crawlers/ 패키지 신설
   - base_connector.py — BaseCrawlConnector ABC + ConnectorError
   - domeggook_api_connector.py — DomeggookApiConnector (health_check/fetch/normalize)
   - quality_gate.py — READY/ERROR/FILTERED 판정 (fixture 5/5 PASS)
3. Crawl_Targets keyword 필드 추가 (fldNhkqfOJvkCZZnp)
4. D001 레코드 Hold 등록 (recg8JU3eqL9BkMgf) — category_code 제외 (singleSelect 선택지 미등록)
5. commit 2112739 push 완료

### Known Facts
- DomeggookApiConnector.fetch(kw=화장품, max_posts=10) = 10건 정규화 성공
- NormalizedItem Contract v1.0 확정
- Crawl_Targets category_code 선택지: A/B/C/D (BEAUTY 추가 시 Airtable UI에서 직접)
- API 키 파라미터: aid= (key= 아님), mode=getItemList, ver=4.1

### P0 Backlog (다음 세션)
1. Dispatcher 연결 — APScheduler에 domeggook job 추가
2. platform=domeggook 레코드 조회 → fetch() → Gate → Source_Items 저장
3. D001 Hold → Active 전환 전 Runtime Proof 필수
4. Source_Items Airtable 테이블 설계 및 생성

### 절대 금지 (다음 세션 전)
- D001 Active 전환 금지 (Runtime Proof 전)
- 전체 2,743건 수집 금지
- FB/Instagram 코드 수정 금지

## [260619_세션3_Source_Items] — 2026-06-19 KST

### 완료 작업
1. adultOnly 파싱 버그 수정 (str->bool, f6bef6a)
2. Source_Items 테이블 생성 (tblMWJaInVHS7YfY6, 17개 필드)
3. STAGING WRITE TEST 4/4 PASS
   - 1차: INSERT=10 / 2차: SKIP=10 / 3차: UPDATE=1 / 4차: SKIP=10(복구확인)
4. D001 Hold 유지 확인
5. 절차 위반 기록: STAGING WRITE TEST 전 BOM/diff 5개 조건 Claude Code 자체 진행

### Known Facts
- Source_Items 10건 저장 (화장품 키워드, READY)
- pipeline_status=NEW, quality_status=READY 정상
- FILTERED/ERROR 항목 pipeline_status 비움 확인
- D001 recoNRhWSKTiwNeuv Hold 유지
- tools/ 임시 스크립트 untracked (commit 대상 아님)

### P0 Backlog (다음 세션)
1. _job_dome_crawl() 구현 — launcher/main.py APScheduler 등록
2. Dispatcher read-only 재확인 후 DRY_RUN
3. Scheduler 수동 1회 실행
4. D001 Hold 상태 Runtime Proof 후 Active 전환 검토
5. C003 platform=daisomall 수정 (Dispatcher 확대 전 필수)

### 절대 금지 (다음 세션 전)
- D001 Active 전환 금지
- Instagram_Posts 저장 금지
- 전체 2,743건 수집 금지
- FB/Instagram 코드 수정 금지
- Dispatcher 미승인 연결 금지

## [260619_세션4_Dispatcher] — 2026-06-19 KST

### 완료 작업
1. _job_dome_crawl() 구현 + APScheduler 등록 (d1ca290)
2. DRY_RUN: D001 Hold → Active 타겟 없음 스킵 확인
3. D001 Active 전환 → fetch=10 ready=10 Runtime Proof
4. Source_Items Upsert 정상 (중복 없음)
5. max_posts 상한 min(value, 10) 강제 적용
6. D001 Hold 복구 확인

### Known Facts
- dome_crawl job: interval 60분, next_run offset 80초
- D001 Hold 상태 — 실운영 전 별도 Active 전환 승인 필요
- Source_Items 11건 (STAGING + Runtime Proof 누적)
- C003 platform=daisomall 수정 미완료 — 다음 세션

### P0 Backlog (다음 세션)
1. C003 platform=daisomall 수정
2. D001 실운영 Active 전환 승인 후 24시간 모니터링
3. Source_Items → Instagram_Posts Export 파이프라인 설계
4. 건강식품 등 카테고리 확장 (D002 추가)

## [260619_세션5_실운영전환] — 2026-06-19 KST

### 완료 작업
1. C003 platform=daisomall 수정 완료
2. D001 Active 전환
3. launcher 재시작 → dome_crawl job 등록 확인
4. 16:47:28 자동 실행 → fetch=10 ready=10 Upsert 성공
5. 다음 실행 17:47:28 (60분 interval) 확인

### Known Facts
- dome_crawl: 60분 interval 실운영 중
- D001 Active (recoNRhWSKTiwNeuv)
- C003 platform=daisomall (Hold 유지)
- Source_Items 누적 중 (11건+)
- watchdog.ps1 백그라운드 유지

### P0 Backlog (다음 세션)
1. Source_Items → Instagram_Posts Export 파이프라인 설계
2. 건강식품 D002 추가
3. 24시간 후 Source_Items 누적 건수 확인

## [260619_세션6_ExportPipeline] — 2026-06-19 KST

### 완료 작업
1. Source_Items 필드 4개 추가 (export_retry_count/last_error/next_retry_at/started_at)
2. Instagram_Posts source_item_id 필드 추가
3. source_exporter.py 구현 + Runtime Proof (d3b6003)
   - DRY_RUN 3건 확인
   - Export 1건 성공 (domeggook:55808288)
   - 중복 재실행 exported=0 확인
4. _job_dome_export() + APScheduler 10분 interval 등록 (4bf6e74)
   - Runtime Proof exported=2 확인

### Known Facts
- dome_crawl: 60분 interval 실운영 중
- dome_export: 10분 interval 실운영 중
- D001 Active
- Source_Items → Instagram_Posts 파이프라인 완성
- STALE_QUEUED 30분 복구 로직 포함
- retry/backoff: 10분/60분/300분

### P0 Backlog (다음 세션)
1. 건강식품 D002 추가
2. 24시간 후 Source_Items/Instagram_Posts 누적 확인
3. launcher 재시작 (watchdog 통해 dome_export job 자동 등록 확인)
## [260619_세션7_실운영확인] — 2026-06-19 KST

### 완료 작업
1. launcher 재시작 → dome_crawl + dome_export 자동 등록 확인
2. D002 건강식품 Hold 등록 (recuRdoKY0KDiV7Ci)
3. 24시간 누적 확인:
   - Source_Items 21건 (EXPORTED=4 / NEW=17)
   - Instagram_Posts 도매꾹 출처 3건
   - dome_crawl 60분 / dome_export 10분 자동 실행 확인

### Known Facts
- dome_crawl: 60분 interval 실운영 중 (D001 Active)
- dome_export: 10분 interval 실운영 중
- D002 Hold (건강식품) — 다음 세션 Active 전환 검토
- Source_Items 누적 중 (10건/회)

### P0 Backlog (다음 세션)
1. D002 건강식품 Active 전환 → Runtime Proof
2. source_item_id 기준 export_to_instagram_posts target_id 확장
3. Instagram_Posts 도매꾹 출처 게시물 품질 확인

## [260622_API_Usage_Logging] — 2026-06-22 KST

### 완료 작업
1. Airtable Team 플랜 업그레이드 완료
2. Lily Yoon Supplier_Blocklist 등록 (recTMGb5XHgT8qjKJ)
   - author_name: Lily Yoon / reason_code: WATERMARK_TAG_OVERLAY
   - 근거: Crawl_Training_Set 3건 decision=BLOCK / has_watermark=True 확인
3. Instagram_Posts 160번 레코드 rejected 처리
4. modules/infra/ 패키지 신설
   - airtable_usage_logger.py — API 호출 카운트 / logs/airtable_usage.jsonl 날짜별 누적 / get_monthly_count() / 100,000회 초과 Telegram 경고
5. log_api_call() 12개 포인트 연결
   - airtable_bridge.py: fetch_ready_one(GET) / update_record(PATCH)
   - facebook_crawler.py: Supplier_Blocklist(GET) / Instagram_Posts(GET·POST)
   - launcher/main.py: Crawl_Targets(GET) / Source_Items(GET·PATCH·POST) / Instagram_Posts(GET·PATCH×3)

### Known Facts
- Airtable Usage 월 누적: 3회 (2026-06 기준, 테스트 포함)
- logs/airtable_usage.jsonl 정상 생성 확인
- content_filter.py: Airtable 직접 호출 없음 (연결 대상 아님)

### P0 Backlog (다음 세션)
1. Instagram_Posts 도매꾹 출처 게시물 품질 육안 확인
2. 카테고리 추가 검토 (D003 등)
3. 48시간 안정성 모니터링

## [260619_세션8_D002확장] — 2026-06-19 KST

### 완료 작업
1. D002 건강식품 Active 전환
2. dome_crawl D001+D002 동시 fetch=10+10 Runtime Proof
3. _job_dome_export() target_id=None / batch_size=5 확장 (7fdd9d1)
4. exported=3 (D001+D002 혼합) Gemini caption 3건 성공

### Known Facts
- dome_crawl: D001(화장품)+D002(건강식품) Active 실운영
- dome_export: target_id=None 전체 대상 / batch_size=5
- Source_Items 누적 중
- Instagram_Posts 도매꾹 출처 증가 중

### P0 Backlog (다음 세션)
1. Instagram_Posts 도매꾹 출처 게시물 품질 육안 확인
2. 카테고리 추가 검토 (D003 등)
3. 48시간 안정성 모니터링

## [260623_FB_Crawler_HUNG_해소] — 2026-06-23 14:17 KST

### Root Cause 4개 해소

| 커밋 | 분류 | 내용 |
|---|---|---|
| e648ce3 | feat | Stage Log (JOB_START/ADSPOWER/DRIVER/PAGE_GET/CRAWL/CLEANUP) + timeout hardening |
| f9b9483 | fix | SSL handshake timeout: socket.setdefaulttimeout + urllib3 adapter (효과 없음 → 다음 커밋으로 대체) |
| 1082d11 | fix | daemon thread + join(timeout=12): Windows SSL hang 포함 wall-clock 강제 종료 |
| 0878c68 | fix | **threading.Lock → RLock** — log_api_call()→get_monthly_count() 중첩 획득 deadlock 해소 (핵심 원인) |
| 56b09d1 | fix | RemoteConnection.set_timeout() 제거 — _client_config AttributeError (_job_fb_crawl 크롤링 실패) |

### Stage Log 전구간 확인 (Scheduler 자동 실행 14:17 KST)
```
JOB_START  elapsed=0.0s
Blocklist  6건 로드 완료
ADSPOWER   elapsed=1.3~1.4s
DRIVER     elapsed=2.5~4.0s  (WebDriver 연결 완료)
PAGE_GET   elapsed=16~24s
CRAWL      posts=2~3
CLEANUP    elapsed=25~32s
AdsPower Stop API 완료
→ 다음 URL 반복 (4개 URL 전체)
```

### Repository Interface (260622~260623)
- modules/infra/repository_interface.py — ABC (fetch_one/fetch_all/update/insert/delete)
- modules/infra/airtable_repository.py — AirtableRepository 구현체 (offset 페이지네이션, log_api_call 내장)
- 기존 airtable_bridge.py 수정 금지 (호환성 유지)
- **연결 0% — 기존 코드 수정 없음, Phase 2 대기**

### Known Facts
- airtable_usage_logger._lock: RLock으로 교체 완료 (재진입 안전)
- _job_fb_crawl 스케줄러 자동 실행: 14:17:51 KST (interval 30분)
- 다음 정기 실행: 16:47 KST
- scheduler_err.log에 STAGE 로그 기록됨 (app.log 동일 핸들러)
- fb_crawl 완료: {'account1': 1} — 1건 처리 (중복 이미지 skip 정상)
- pytesseract 없음 경고: 비치명적, 통과 처리

### P0 Backlog (다음 세션)
1. Instagram_Posts 도매꾹 출처 게시물 품질 육안 확인
2. 카테고리 추가 검토 (D003 등)
3. 48시간 FB Crawler 안정성 모니터링
4. Repository Interface Phase 2 연결 계획 수립

## [260623_Repository_Interface_1차_연결] — 2026-06-23 KST

### 완료 작업

#### Phase 1 — Interface 설계 (758d29d)
- `modules/infra/repository_interface.py` 전면 교체
  - Enum: SourceItemStatus / InstagramPostStatus
  - TypedDict 6개: SupplierBlockEntry / SourceItemRef / SourceItem / InstagramPost / CrawlTarget / PostPublishResult
  - 예외 4개: RepositoryError / Unavailable / NotFound / Validation
  - ABC 메서드 10개: list_blocked_suppliers / exists_post_by_image_url / save_instagram_post / fetch_active_crawl_targets / find_source_item_by_hash / save_source_item / update_source_item_status / fetch_pending_posts / claim_post_for_upload / mark_post_result
- `modules/infra/airtable_repository.py` 전면 교체
  - 10개 메서드 Airtable HTTP 구현체
  - fields 언패킹 → TypedDict 변환
  - _raise() → RepositoryError 계층 변환
  - claim_post_for_upload: WARNING non-atomic, single-worker only
  - fetch_active_crawl_targets: filterByFormula `{status}='Active'` 단독 (platform 제한 제거)

#### Phase 2 — 직접 호출 교체 (c52e00b)
| 파일 | 교체 내용 |
|------|----------|
| `airtable_bridge.py` | fetch_ready_one / update_record dead code 제거 / import requests 제거 |
| `launcher/main.py` | _job_dome_crawl: Crawl_Targets GET → repo.fetch_active_crawl_targets() |
| `launcher/main.py` | _job_dome_crawl: Source_Items upsert → find_source_item_by_hash / save_source_item / update_source_item_status |
| `launcher/main.py` | _job_insta_upload: fetch_pending_posts / claim_post_for_upload / mark_post_result 연결 |
| `launcher/main.py` | publish_single: table.update 3개 제거, 순수 반환값 함수로 전환 |
| `facebook_crawler.py` | Instagram_Posts 중복체크 직접호출 → repo.exists_post_by_image_url() |

### Known Facts
- import 검증: AirtableRepository 10개 추상 메서드 전부 구현 확인 (python -c 검증)
- airtable_bridge.py: get_table() 유지 (Function Signature Lock) / fetch_ready_one, update_record 제거
- launcher/main.py: _req, BASE_ID, API_KEY 잔재 _job_dome_crawl 내부 전부 제거
- facebook_crawler.py: _api_key, _base_id, image_url_hash 계산 로직 Repository 내부로 이동
- 잔존 직접 호출: dm/, crm/, comment/, crawlers/source_exporter.py 등 16개 파일 — 다음 세션

### P0 Backlog (다음 세션)
1. DM 모듈 (dm_auto_reply / dm_followup_scheduler / dm_receiver) Repository 연결
2. CRM 모듈 (lead_scorer / lead_closer / order_detector / daily_report) Repository 연결
3. Comment 모듈 (comment_auto_reply / comment_poller) Repository 연결
4. source_exporter.py Repository 연결 (호출 11개 — 최대 규모)

## [260624_DM_CRM_Comment_Repository_연결] — 2026-06-24 KST

### 완료 작업

#### Interface 확장 (repository_interface.py)
- Enum 추가: LeadBridgeStatus (dm_received / auto_replied / followup1~3_sent / lost / closed / converted)
- TypedDict 추가: LeadInteraction (id / igsid / bridge_status / lead_status / lead_grade / relay_scheduled_at) / LeadInteractionCreate (igsid / source / interaction_type / occurred_at)
- 추상 메서드 12개 추가 (#11~#22): get_base_price / has_recent_auto_reply / create_lead_interaction / is_repeat_inquiry / fetch_leads_due / fetch_today_lead_stats / update_lead_replied / update_lead_score / update_followup_status / mark_lead_lost / mark_lead_closed / mark_lead_converted

#### AirtableRepository 구현 (airtable_repository.py)
- 12개 메서드 Airtable HTTP 구현 + _patch_lead_interaction() private helper
- fetch_today_lead_stats: lead_grade 필드 반환 추가

#### 직접 호출 교체 (10개 파일)
| 파일 | 교체 내용 | 직접 호출 |
|------|----------|----------|
| dm_auto_reply.py | _at_headers/_at_patch 제거 → has_recent_auto_reply / get_base_price / update_lead_replied | 3→0 |
| dm_receiver.py | _at_post/_gen_code 제거 → create_lead_interaction | 1→0 |
| dm_followup_scheduler.py | _at_get_due/lost/_at_patch 제거 → fetch_leads_due / update_followup_status / mark_lead_lost | 3→0 |
| comment_auto_reply.py | _record_comment 직접 POST → create_lead_interaction | 1→0 |
| lead_scorer.py | 직접 GET/PATCH → is_repeat_inquiry / update_lead_score | 2→0 |
| lead_closer.py | 직접 PATCH 2건 → mark_lead_closed | 2→0 |
| order_detector.py | 직접 PATCH 2건 → mark_lead_converted | 2→0 |
| daily_report.py | 직접 GET → fetch_today_lead_stats | 1→0 |
| repository_interface.py | LeadInteraction lead_grade 필드 추가 | — |
| airtable_repository.py | fetch_today_lead_stats lead_grade 반환 추가 | — |

### Known Facts
- DM/CRM/Comment 영역 Airtable 직접 호출 0건 검증 완료 (Grep 확인)
- "followup_error" 비표준 상태: LeadBridgeStatus 외부 → _patch_lead_interaction() private 직접 사용
- inquiry_message / comment_id / media_id: LeadInteractionCreate 미포함 데이터 갭 (허용)
- lead_grade (hot/warm/cold): LeadInteraction TypedDict 추가 후 fetch_today_lead_stats 반환에 포함
- BOM 체크 10개 파일 전부 OK

### 잔존 직접 호출 (다음 세션 대상)
| 파일 | 라인 | 테이블 |
|------|------|--------|
| modules/common/account_manager.py | L114 | Crawl_Targets GET |
| modules/common/airtable_autorun_engine.py | L19 | BASE_URL 상수 |
| modules/crawlers/source_exporter.py | L9 | BASE_URL 상수 (다수 호출) |
| modules/ingest/domeggook_ingest.py | L33 | TRAINING_TABLE POST |
| modules/sns/facebook_crawler.py | L44 | Supplier_Blocklist GET |

### P0 Backlog (다음 세션)
1. account_manager / airtable_autorun_engine / source_exporter / domeggook_ingest / facebook_crawler Repository 연결

## [260624_직접호출_완전교체] — 2026-06-24 KST

### 완료 작업

#### 잔존 4파일 Repository 교체 (df9df6b)
| 파일 | 변경 내용 |
|------|-----------|
| `account_manager.py` | `_load_crawl_urls_from_airtable()` — requests 제거 → `repo.fetch_active_crawl_targets()` + platform 필터 list comprehension |
| `facebook_crawler.py` | `load_supplier_blocklist()` — requests+threading+socket 제거 → `repo.list_blocked_suppliers()` / `socket` top-level import 제거 |
| `source_exporter.py` | 직접 호출 11건 전체 → Repository 교체. `BASE_URL/_headers()/_base()` 제거. 신규 메서드 4개(fetch_source_items_for_export / recover_stale_queued / claim_source_item_for_export / update_source_item_retry) 추가 |
| `domeggook_ingest.py` | Training 직접 호출 → `TrainingRepository.upsert_training_record()` |
| `training_repository.py` | 신규 생성 — Product_Training_Set 전용 (GET 중복확인 → PATCH/POST upsert) |
| `repository_interface.py` | `SourceItemStatus.QUEUED` 추가 / `SourceItem` 필드 확장 / 추상 메서드 4개 추가 (#23~#26) |
| `airtable_repository.py` | 메서드 23~26 구현 (서버사이드 filterByFormula 적용) |

#### save_to_airtable NameError 수정 (4502e65)
- `facebook_crawler.py` `save_to_airtable()` — `_req/_url/_hdrs/image_url_hash` 미정의 변수 NameError 수정
- `_req.post()` + `log_api_call()` → `repo.save_instagram_post(payload)` 교체
- `hashlib.sha256` 인라인 계산 추가
- `import logging` 인라인 3개 → `logger` 통일

#### airtable_bridge dead import 제거 (e0bcff6)
- `airtable_bridge.py` — `log_api_call` import 제거 (호출 없는 dead import)

#### inquiry_message 데이터 갭 해소 (36cbf05)
- `LeadInteractionCreate` — `inquiry_message: str` 필드 추가
- `create_lead_interaction()` — `fields["inquiry_message"]` Airtable 저장 추가
- `dm_receiver.py` — `record_interaction()` 호출 시 `inquiry_message=message_text` 전달
- `comment_auto_reply.py` — `_record_comment()` 호출 시 `inquiry_message=text` 전달
- 효과: dashboard.py 메시지 표시 / kpi_collector price/neg 집계 실데이터 기반 동작

### Infrastructure 외부 직접 호출 최종 검증
- `Select-String api.airtable.com` grep 결과 운영 코드 내 잔존:
  - `airtable_autorun_engine.py` 1건 — **dead 파일 확정** (import 없음, 250723 복사 산물)
  - `airtable_repository.py` / `training_repository.py` — infra 계층 허용
- **실질적 직접 호출 0건 확정**

### Known Facts
- `airtable_autorun_engine.py`: 250723 복사 파일, 어디서도 import 없음, dead 판정 (삭제 불필요)
- `domeggook_ingest.py` 중복 반환값 변경: duplicate → upsert 내부 처리 (PATCH), 카운터 집계 방식 변경
- `SourceItemStatus.QUEUED` 추가: source_exporter 내부 상태 전용

### P0 Backlog (다음 세션)
1. ~~Failure Injection Test~~ ✅ PASS (260624)
2. ~~Runtime Proof 5회 연속 정상~~ ✅ PASS (260624 19:50~21:50)

## [260624_검증완료] — 2026-06-24 KST

### Failure Injection Test
- 스크립트: `tools/_test_failure_injection.py`
- 주입 방식: `get_driver()` 몽키패치 → `page_load_timeout=3s` 강제 오버라이드
- 결과:
  - **finally cleanup PASS** — `[STAGE:CLEANUP]` 정상 실행 / `[AdsPower] Stop API 완료` 확인
  - **AdsPower Pre/Post=False** — Stop API 정상 호출 후 Inactive 확인
  - TimeoutException 미발생 — CDP-attach 모드(debuggerAddress)에서 `page_load_timeout` 미작동 (Facebook 초기 DOM 3초 내 complete 도달)
  - finally 경로 자체는 정상 보장 확인
- STAGE Log 전구간:
  ```
  JOB_START → ADSPOWER → DRIVER(timeout 3s 적용) → PAGE_GET(15.4s) → CRAWL(posts=2) → CLEANUP → AdsPower Stop API 완료
  ```

### Runtime Proof 5회 연속 정상 (19:50~21:50 KST)
- DM/댓글 수신 정상
- inquiry_message Airtable 저장 확인
- Repository Interface 전 계층 정상 동작

### Repository Interface 전체 작업 완료 요약
| 단계 | 커밋 | 내용 |
|------|------|------|
| DM/CRM/Comment 연결 | 18aa3a7 | 10개 파일 직접 호출 → Repository |
| 잔존 4파일 교체 | df9df6b | account_manager / facebook_crawler / source_exporter / domeggook_ingest |
| NameError 수정 | 4502e65 | facebook_crawler save_to_airtable |
| dead import 제거 | e0bcff6 | airtable_bridge log_api_call |
| inquiry_message 갭 | 36cbf05 | LeadInteractionCreate + dm/comment caller |
| docs 업데이트 | 90c971d | CURRENT_RUNTIME_CONTEXT |

### Known Facts
- Infrastructure 외부 직접 호출 실질적 0건 (airtable_autorun_engine.py dead 파일 제외)
- CDP-attach 모드 page_load_timeout 제한: debuggerAddress 연결 시 timeout 미작동 — 알려진 Selenium 제약
- TrainingRepository: Product_Training_Set 전용 분리 클래스 (RepositoryInterface 미상속)

### P0 Backlog (다음 세션)
1. Instagram_Posts 도매꾹 출처 게시물 품질 육안 확인
2. D003 카테고리 추가 검토
3. 48시간 안정성 모니터링

---

## [260629] 워터마크/필터 수정 + Caption 교체

_업데이트: 260629 21:34 KST_

### 변경 내용

| 항목 | Before | After | 커밋 |
|------|--------|-------|------|
| COSLIFE·Lily 차단 | ImageFilter OCR (pytesseract 미설치로 무력화) | CAPTION_BLOCKLIST 텍스트 매칭 | d79a3b3 |
| FB UI 잔여물 제거 | 경과시간·댓글달기만 제거 | 원본보기·번역평가·좋아요·공유하기·저장 추가(_ui_pat) | 998215e |
| Caption 생성 | generate_caption_clone() — 텍스트 원본 보존 | generate_caption() — Gemini 재생성 | 998215e |
| 해시태그 필터 | 국가명 제한 없음 | Korea-related tags only (Myanmar·Vietnam 등 제외 명시) | 998215e |
| DOME_EXPORT_ENABLED | true (260619 활성화 완료) | 유지 | — |

### CAPTION_BLOCKLIST (content_filter.py)
`python
CAPTION_BLOCKLIST = ["coslife", "lily"]
`
- passes_keyword_filter() 선두에서 번역 캡션 체크 → 매칭 시 즉시 False 반환
- pytesseract 미설치 상태에서 텍스트 레벨 대체 차단 (ERR-044)

### 48시간 모니터링
- 시작: 2026-06-29 21:34 KST
- 종료: 2026-07-01 21:34 KST
- 확인 항목: [CaptionBlocklist] 차단 감지 로그 / lily 오탐 여부 / Gemini caption 품질

### P0 Backlog (갱신)
1. lily 오탐 모니터링 → 오탐 발생 시 "lily cosmetics"로 구체화
2. pytesseract 설치 여부 검토 (ERR-044 근본 해소)
3. Instagram_Posts 도매꾹 품질 육안 확인
4. D003 카테고리 추가 검토

## [260703~260705] DI Canary #2/#3 + Supplier_Blocklist 회귀 수정

### 260703 — Supplier_Blocklist 필드 매핑 회귀 수정 (ERR-046/FP-034/INC-024)
- repository_interface.py / airtable_repository.py / facebook_crawler.py 3파일 supplier_name→author_name+page_name 매핑 수정
- Gate 6 ISOLATED INTEGRATION PROOF 통과 + 운영 Supplier_Blocklist 5건 대상 Runtime Proof 6/6 매칭 성공
- pytest 100 passed, pre-existing 4 failed는 stash 비교로 무관 확인

### 260704 — DI Canary #2 (airtable_integrity.py)
- 신규 메서드 fetch_posted_missing_media_id() 추가 (repository_interface.py + airtable_repository.py)
- airtable_integrity.py get_table() 직접호출 → AirtableRepository 치환
- 타겟 3건 PASSED, 전체 100 passed·4 failed(pre-existing)·3 xfailed
- 커밋: 코드 f6194ac / 문서 57b5c00

### 260705 — DI Canary #3 (kpi_collector.py)
- 신규 메서드 2개 추가: fetch_all_instagram_posts() / fetch_all_lead_interactions(since_utc)
- kpi_collector.py _fetch_leads()/_fetch_posts() get_table() 직접호출 2곳 → AirtableRepository 치환
- 신규 테스트 4건 추가 (tests/test_smoke_metrics.py)
- 타겟 17/17 PASSED, 전체 104 passed·4 failed(pre-existing, test_dm_close.py)·3 xfailed
- 신규 HOLD: airtable_repository.py 전체 GET 메서드 offset 페이지네이션 미구현
- 커밋: 코드 f21e4b8 / 문서 a24d318

## [260710] heartbeat_monitor 절전 대응 + Governance 강화

### 완료 작업
1. heartbeat_monitor.py 신규 (b2aa30d) — watchdog.ps1과 독립된 heartbeat 정지 감지, Task Scheduler 5분 주기(`SNS_HeartbeatMonitor_Independent`)
2. ERR-052/FP-039/INC-029 (fe37ed4) — 250723 참조 활성 Task 2건(`SNS_AUTO_PRODUCTION`/`SNS_Auto_Run`) 발견, `Disable-ScheduledTask`로 즉시 비활성화
3. ERR-047/050 INC-028 Modern Standby 상관관계 조사 (fdd1333) — 1차/2차 다운 메커니즘이 서로 다를 수 있음을 최초 제기
4. ERR-049 증거 파일 정식 편입 + 스크래치 파일 gitignore 정리 (e8583ba)
5. ERR-053/FP-040 (d49ab61) — heartbeat_monitor.py 예약 작업이 `WakeToRun=False`로 Modern Standby 중 71회(약 5시간47분) 미실행 근본원인 확정
6. CLAUDE.md 승인 범위 명시 원칙 (3ab2e49) — read-only 조사 승인이 문서기록/commit까지 자동 포함하지 않음 (ERR-053 절차위반을 계기로 등록)
7. INC-028 Note 3 (422f9bd) — 1차 다운(20:09:40) 실제 원인 확정: Modern Standby 아님, 실제 OS shutdown(`StartMenuExperienceHost.exe`, 20:09:52 개시). Update/로그오프 배제, 사람의 조작 Hypothesis(확정 아님)
8. `docs/PENDING_INVESTIGATIONS.md` 신규 (b89e213) — PENDING-A(NSSM 전환 검토): AdsPower Local API가 Session 0(S4U)에서도 정상 응답함을 진단 Task로 실증 SUCCESS 확인
9. CLAUDE.md 단계별 Bookending 원칙 (e09fae5) — 작업 전/후 상태를 한 줄로 확인하는 습관 등록
10. `SNS_HeartbeatMonitor_Independent` Task `WakeToRun=True`로 변경 적용 — 실제 절전 구간 재현 검증은 다음 세션 대기

### Known Facts
- Flask(:5000)/Streamlit(:8501)/ngrok(:4040) 3개 포트 LISTENING 확인(260710 세션 중 재확인)
- `SNS_HeartbeatMonitor_Independent` 최근 상태: `WakeToRun=True`, 나머지 Settings 필드 변경 없음
- AdsPower Local API(`http://local.adspower.net:50325`)는 Session 0/S4U 비대화형 컨텍스트에서도 정상 응답(raw 실증 완료) — `facebook_crawler.py` 자체는 subprocess/GUI 의존 없음, 순수 HTTP 클라이언트

### P0/P1 Backlog (다음 세션)
1. WakeToRun=True 적용 후 실제 Modern Standby 구간 1~2회 확보해 heartbeat_monitor.log 기록 대조 검증
2. watchdog.ps1 자체의 1차다운 근본 메커니즘(여전히 UNKNOWN) 별도 조사
3. ERR-047 핵심 증상(재부팅 후 SNS_Watchdog_AutoStart 무재실행) 자체 해결책 검토
4. PENDING-A(NSSM/서비스 전환) 최종 결정 — 사용자 승인 필요
5. ⚠️ 260706~260709 커밋(ERR-048/050/051, INC-023/025/026/028, quality gate 재설계 등)은 이번 갱신에 미포함 — 필요 시 별도 backfill

### 관련 문서
- ERR-052/053, FP-039/040, INC-028(Note1~3)/029, PENDING-A — 전체 raw 근거는 각 문서 참조(중복 서술 최소화)

---

## [260711] NSSM 전환 완료 + ngrok LocalSystem 결함 발견·해소

### 완료 작업
1. 전날 노트북 종료로 자동화 전체 중단 → 재부팅 후 세션 재개, `SNS_Watchdog_AutoStart`(당시 아직 미비활성) 자동 재기동으로 1차 복구 확인
2. AdsPower 미기동으로 FB 크롤링 전량 실패(WinError 10061) → 사용자 직접 재기동, 정상화 확인
3. `.claude/settings.json` 신규 — PowerShell 도구 읽기 전용 명령 20개 자동 허용(권한 팝업 감소), git commit/push·프로세스 제어는 의도적으로 제외
4. **ERR-057** — NSSM 서비스(`SNS_Watchdog`)와 구 Task(`SNS_Watchdog_AutoStart`)가 watchdog.ps1을 동시 이중 실행 중이던 것 발견(PENDING-A 전환의 Phase 3 누락) → 관리자 권한으로 `Disable-ScheduledTask` + 중복 프로세스 `Stop-Process` 정리
5. **크래시 재시작 실증 PASS** — NSSM 관리 watchdog.ps1 강제 종료 → `AppRestartDelay` 경과 후 자동 재기동, 수동 개입 없이 전체 복구 확인
6. **재부팅 실증 PASS** — 실제 재부팅 후 watchdog.log 시작 배너 1번만 기록(구 Task 재발 없음) → **PENDING-A(NSSM 서비스 전환) 완전 종결**
7. **ERR-058** — 재부팅 실증 중 ngrok 실행 실패 신규 발견: (1) Microsoft Store(MSIX) 설치라 LocalSystem(비대화형) 컨텍스트에서 Execution Alias 실행 불가 (2) authtoken이 admin 사용자 프로필 전용이라 LocalSystem이 인증정보 미발견 — 오늘 아침엔 구 Task(admin 계정)가 우연히 가려온 잠복 결함. `watchdog.ps1` 포터블 exe 경로 지정 + authtoken을 LocalSystem 프로필에 복사로 해소, Runtime Proof 완료(`public_url` 정상 응답)
8. FP-042(전환 중간상태 방치 패턴)/FP-043(서비스 계정 전환 시 의존 도구 전수점검 필요) 신규 등록

### Known Facts
- `SNS_Watchdog` NSSM 서비스: `LocalSystem` 계정, `AppExit Default=Restart`, `AppRestartDelay=60000ms`
- `SNS_Watchdog_AutoStart` Task: `Disabled` 유지(삭제 아님, 증거 보존), 재부팅 실증으로 재발 없음 확인
- ngrok: `C:\ngrok\ngrok-v3-stable-windows-amd64\ngrok.exe`(포터블, 실사용) vs `WindowsApps\ngrok.exe`(MSIX 심볼릭 링크, LocalSystem에서 사용 불가 — 더 이상 참조 안 함)
- ngrok authtoken 이중 보관: `C:\Users\admin\AppData\Local\ngrok\ngrok.yml`(admin) + `C:\Windows\System32\config\systemprofile\AppData\Local\ngrok\ngrok.yml`(LocalSystem, 260711 신규 복사)
- AdsPower Global: 260711 재부팅 시 Windows 시작 시 자동 기동 확인(12:10:33~40) — 오늘 아침 첫 재부팅 때만 예외적으로 꺼져있었음(원인 미상)
- FB 크롤링: 재부팅 이후에도 정상 수집 지속 확인(12:34:07 1건 등)

### P1/P2 Backlog (다음 세션)
1. heartbeat_monitor.py 실제 Modern Standby 구간에서 로그가 이어지는지 실증 검증(유일하게 남은 절전 관련 미검증 항목, watchdog.ps1과 별개)
2. n8n(PID 10248 등) watchdog.ps1의 반복 재시작 시도·알림 잡음 — 우선순위 낮음으로 보류
3. ⚠️ 260706~260709 구간 여전히 별도 미반영(과거 Backlog #5 그대로 승계)

### 관련 문서
- ERR-057/058, FP-042/043, INC-030/031, PENDING-A(완전 종결) — 전체 raw 근거는 각 문서 참조

---

## [260713~260715] Gate C~G DM/댓글 안전장치 시리즈 + n8n/P0-1/FP-047/ERR-063 재조사

⚠️ 260706~260709 구간은 이번 갱신에도 여전히 미반영(과거 Backlog #5 그대로 승계, 필요 시 별도 backfill).

### 완료 작업

1. **Gate C — 가격 자동응답 안전차단**(ERR-061/FP-046/INC-034): `docs/design/DM_RELAY_COMMERCE_RFC.md` 설계검토 중 `get_base_price()`가 문의 상품을 특정하지 않고 최신 등록가를 그대로 자동발송하는 구조적 결함 발견. `PRICE_AUTO_REPLY_ENABLED`(기본 `false`) 도입, 비활성 시 상품확인 요청 템플릿으로 대체. Codex 4라운드 교차검증으로 발송실패 시 `bridge_status` 오갱신 방지, Telegram PII 마스킹(`_mask_igsid`/`_telegram_preview`, 단 신규 함수에만 적용), `(sender, 문의문)` 키 원자적 중복방지 동반 수정. 커밋 `c1c90b2`(260713) → 260714 10:18 launcher 재시작 + 10:24:41 Canary로 **가격 자동발송 차단 PASS 확정**. 안내문 실발송·신규 마스킹 E2E는 PARTIAL(미확인).
2. **Gate E-A/E-B — Graph API 버전 중앙화**: `modules/common/meta_graph.py` 신규(v19.0→v25.0 URL 중앙화), DM/댓글 4파일 8곳 적용. 라이브 Canary 4경로 중 3경로(dm_auto_reply/dm_followup_scheduler/comment_poller) PASS.
3. **ERR-062/FP-047/INC-035 — 댓글 리드 Airtable 기록 실패**(RESOLVED, 이번 2건): `Lead_Interactions.conversation_channel`에 `instagram_comment` 선택지 없어 댓글 리드 2건 기록 실패 + 재시도 없이 캐시에 완료 처리되어 유실. Airtable 선택지 추가로 이번 유형 해소, 저장 Canary PASS. **단 예외를 삼키고 무조건 캐시하는 근본 패턴(FP-047) 자체는 미해결로 계속 OPEN.**
4. **Gate G — 댓글 자동응답 Private Reply 전환**(ERR-064/FP-048/INC-036): 공개 답글 대신 비공개 Private Reply로 전면 전환. `modules/comment/comment_safety_guard.py` 신설(캠페인 게시물 allowlist/24h 쿨다운/일일예산/circuit breaker/fail-closed/REPLY_LOCK 동시성). Codex 4라운드 리뷰로 엔드포인트 계약(`POST /{page-id}/messages`, `recipient.comment_id`) 확정. 실계정(tgbtgbnate) 라이브 테스트로 댓글→Private Reply 수신까지 회장 육안 확인.
5. **Gate G 라이브 테스트 중 신규 발견(OPEN)**: tgbtgbnate(앱 테스터 미등록)의 Private Reply 답장이 45분+ 웹훅 미도착. 웹훅 구독(`messages`/`messaging_postbacks`)·토큰 스코프 전부 정상 확인됐으나, Meta 앱 대시보드에서 테스트 계정(채솔)만 테스터 등록·tgbtgbnate 미등록임을 확인 — Standard Access(App Review 미통과) 상태에서 앱 역할 없는 일반 사용자와의 메시징(인바운드 웹훅)이 제한될 수 있다는 가설과 정황 일치, 단 실제 Access Level은 미확인(CONFIRMED 아님).
6. **Meta App Review 제출**: 260715 00:35, `instagram_manage_comments`/`instagram_content_publish`/`instagram_manage_messages`/`instagram_basic` 4개 권한 Advanced Access 신청 제출(검토 중, 대본 `docs/design/META_APP_REVIEW_SCRIPT_260714.md`). **ManyChat**(이미 Meta 공식 Business Partner로 Advanced Access 보유, Pro $29~/월) 우회 전환도 검토 후보로 부상 — App Review 대기 vs ManyChat 전환 최종 방향 미결정.
7. **260715 재조사(전부 read-only, 회장 지시로 기록만 — 코드/프로세스 변경 없음):**
   - **ERR-065/FP-049/INC-037(n8n)**: watchdog.log 전체(260517~260715) n8n 재시작 실패 5,298건/성공 8건, 마지막 성공 260624 23:56:09 — **260711 NSSM/LocalSystem 전환 이후 성공 0건**. `logs/n8n.log`가 npx 대화형 설치 프롬프트("Ok to proceed? (y)")에서 멈춰 있고, 그 원인으로 보이는 좀비 프로세스(cmd.exe 16948→node.exe 21620, 260714 22:25 생성)가 10시간+ 생존 확인. 전역 npm 경로(admin 프로필 전용)와 LocalSystem 실행 계정 불일치가 원인으로 의심(ERR-058과 동일 클래스, 미확정).
   - **P0-1 → ERR-066 승격**: `dm_receiver.py:54-71`/`:147`이 여전히 IGSID 전체·원문 200자를 무마스킹 전송 확인. Gate C 때 만든 마스킹 유틸(`dm_auto_reply._mask_igsid()`/`_telegram_preview()`/`_PII_PATTERNS`)이 이미 있어 재사용만 하면 됨. 부수로 `dm_receiver.py:143` 로그도 원문 무마스킹 노출 확인(문서에 없던 추가 지점).
   - **FP-047 재확인**: Gate G 이후 줄 번호만 이동(`comment_poller.py:116`/`:123-125`, `comment_auto_reply.py:146-157`), 로직(예외를 삼키는 `_record_comment()` + 무조건 캐시) 그대로 — 부정 댓글·일반/가격 댓글 두 경로 모두 동일하게 취약함을 추가 확인.
   - **ERR-063 원인 확정(RESOLVED)**: `test_send_failure_does_not_mark_replied_or_schedule_followup`만 유일하게 `PRICE_AUTO_REPLY_ENABLED=True`+`get_base_price` non-None이라 `dm_auto_reply.py:289`의 실제 Gemini `generate_reply()` 호출까지 도달하는데 이게 mock되어 있지 않음 확인. `.venv` python으로 직접 재실행 → Gemini 200 OK, 7.48초 만에 PASSED — 무한 hang이 아니라 실제 API 상태(quota/rate-limit)에 좌우되는 테스트임을 실증. 260714 최초 발견 당시 Gemini 무료 쿼터 소진 상태였다는 기록과 대조하면 429 재시도 지연(`_RETRY_DELAYS=[20,40,60]`, 누적 최대 120초+)이 25초 격리 타임아웃을 넘겨 "hang"으로 보였던 것으로 설명됨.

### Known Facts
- `.env`: `COMMENT_AUTO_REPLY_ENABLED=false`, `PRICE_AUTO_REPLY_ENABLED=false` 둘 다 안전 상태 확인(260715).
- `configs/comment_campaign_posts.json`: `media_ids=["18116772601675773"]`(Gate G 라이브 테스트 값 유지, 커밋 완료) — `.env` 플래그 false라 즉시 실행 위험 없음.
- Gate C~G 전체 origin 동기화 완료(커밋 4f3f38e까지 push), 260715 문서 커밋 2건(`a0d5207`, `f511447`)도 push 완료.
- Gemini API 쿼터 상태는 시점에 따라 변동(260714 소진 확인 → 260715 재실행 시 200 OK 정상) — 매 세션 재확인 필요, 고정 사실 아님.

### P0/P1 Backlog (다음 세션)
1. **[최우선]** Meta App Review 결과 확인 + ManyChat 전환 여부 최종 결정(ERR-064/FP-048/INC-036) — 실제 손님 대상 자동화 핵심 전제에 직접 영향
2. FP-047(댓글 Airtable 기록 실패 시 유실) 코드 수정 — 재시도 큐 적용 또는 실패 ID 캐시 제외
3. ERR-066(P0-1, Telegram PII 노출) 코드 수정 — 기존 마스킹 유틸 재사용, 신규 개발 불필요
4. ERR-063 테스트에 `ai_reply_generator.generate_reply` mock 추가(회귀 아님, 테스트 안정성 개선)
5. n8n(ERR-065) 좀비 프로세스 정리 + watchdog.ps1 n8n 감시 블록 처리 방향 결정 — 단 회장 방침(안정화 우선)에 따라 n8n 재설계와 함께 후순위
6. ⚠️ 260706~260709 구간 여전히 별도 미반영 — 과거 Backlog 그대로 승계

### 관련 문서
- ERR-061~066, FP-046~049, INC-034~037, `docs/design/DM_RELAY_COMMERCE_RFC.md`, `docs/design/META_APP_REVIEW_SCRIPT_260714.md` — 전체 raw 근거는 각 문서 참조

---

## [260715~260716] FP-047 구현 + shadow 실계정 라이브 테스트 + Package 1(Phase A) 캠페인 allowlist 폴링

### 완료 작업

1. **FP-047(댓글 이벤트 idempotency) 실제 구현**(커밋 `00466a3`) — GPT/Codex 12라운드 교차검토(설계 8라운드 + 구현 후 코드리뷰 4라운드). 신규 `comment_event_store.py`(fencing token 원자적 claim, stale lease 자동 회수 내장), `comment_retry_dead_monitor.py`(retry_queue dead 태스크 Slack 알림). 단일 진입점 `process_comment_event()` — `COMMENT_EVENT_STORE_MODE`(disabled/shadow/enforce) 킬스위치, `CommentProcessResult` 구조화 반환값. Airtable `Lead_Interactions.source_event_id` 필드 신규 추가. 신규 테스트 65개, `COMMENT_EVENT_STORE_MODE=disabled`(기본값)로 커밋 — 운영 동작 무변화.

2. **shadow 모드 실계정 라이브 테스트(260715)** — `.env`를 `COMMENT_EVENT_STORE_MODE=shadow` + `COMMENT_AUTO_REPLY_ENABLED=true`로 전환(관리자 권한 서비스 재시작 반복 경유). 실제 테스트 계정(hsy00718g/jiho2987/petit__phau_thuat/kbeautymcn/reviewasiamarket 등)이 캠페인 게시물에 댓글 → **실제 Private Reply DM 수신까지 회장 육안 스크린샷 확인**(E2E PASS, 복수 계정·복수 라운드).
   - 이 과정에서 회장이 직접 내린 비즈니스 정책 변경 3건: (1) 가격 키워드(`단가`/`가격`/`price` 등)로 좁혀서 걸러내지 않고 스팸/부정 댓글 외 전부 Private Reply 대상으로 확대("재고있나요"/"연락주세요" 등 키워드 목록에 없던 실제 구매의사 표현을 놓치던 jiho2987 사례로 발견) (2) 사용자별 재응답 쿨다운 24h→0h (3) 일일 발송 예산 30→100000(사실상 무제한, circuit breaker는 버그 방지용으로 유지).
   - **이 정책 변경(`comment_auto_reply.py` 일부 + `tests/test_comment_auto_reply.py`)은 `.env`에는 반영·라이브 테스트까지 마쳤으나, 코드 자체는 아직 미커밋** — Package 1 커밋(`eb98741`)에서 관련 무관 변경으로 의도적으로 제외했고, 워킹트리에 그대로 남아있음. 다음 세션에서 별도 커밋 여부 결정 필요.

3. **ERR-069/FP-050/INC-038 발견** — 라이브 테스트 중 회장이 30초 간격으로 서로 다른 상품 게시물 2곳에 댓글을 남겼는데 1곳만 응답이 옴을 보고. 조사 결과 `comment_poller.py`가 `COMMENT_POLL_MEDIA_COUNT=5`(기본값) "최근 게시물 5개"만 폴링 중이었고, 캠페인 게시물(총 6개 등록)이 계정의 잦은 게시 빈도로 그중 3개가 감시 범위 밖에 밀려나 있었음. 밀려난 게시물의 댓글은 `db/comment_events.db`에 기록 자체가 없어(웹훅도 이 계정에서 안정적으로 안 들어와 보완 안 됨) 이벤트가 시스템에 아예 진입 못 한 것으로 raw 확인 — 실제 잠재고객 문의 1건("MOV 어떻게되나요")이 완전히 유실됨.

4. **Package 1(Phase A) 구현**(커밋 `eb98741`, push 완료) — GPT 전략자문 1라운드("최근 N개" 폐기, 캠페인 목록 직접 폴링으로 전환 확정, ManyChat 등 상용 서비스 사례 근거 제시) + Codex 코드검수 9라운드(설계가 아니라 구현 완료 후 실제 코드 재현 기반 리뷰, 라운드마다 실제 버그 발견).
   - 신규 `modules/comment/comment_campaign_config.py` — 캠페인 allowlist 공용 loader(`comment_safety_guard`/`comment_poll_targets` 공유, 스키마 검증/중복제거/공백 정규화, 파일 없음도 fail-closed).
   - 신규 `modules/comment/comment_poll_targets.py` — media별 `PENDING_BASELINE→ACTIVE→PAUSED` 상태머신(`comment_events.db` 별도 테이블), `campaign_config_hash`/`baseline_config_hash`로 설정 드리프트 감지, `COMMENT_POLL_ALLOWLIST_MODE`(기본 legacy) 킬스위치.
   - 신규 `tools/comment_campaign_baseline_cli.py` — media당 1개씩 수동 cutover(`--dry-run` → `--apply --cutover-at --expected-config-hash`(필수) → `--verify`(8개 계약) → `--activate --acknowledge-runtime-proof`(4가지 하드 조건: allowlist 모드+enforce 모드+운영자 확인 선언+설정 해시 일치)).
   - `comment_poller.py` — `_poll_legacy()`(기존 "최근 N개", 무변경)/`_poll_allowlist()`(신규, 전체 페이지네이션)로 분리.
   - `comment_auto_reply.py` — `process_comment_event()` 최상단에 `_blocked_by_allowlist_gating()` 게이트 신설(event-store 모드·mode 분기보다 먼저, event_store 행 생성 전 검사).
   - **9라운드 중 재현·수정된 핵심 버그(전부 실제 코드 재현으로 확인 후 수정, 상세는 ERR-069/`porting_logs/MERGE_JOURNAL.md` 참조):** PENDING media 새 댓글이 SHADOW_SEEN 태그로 영구 고착돼 나중에 ACTIVE 전환 후에도 처리 못 하는 버그(가장 심각 — 응답 영구 유실 시나리오), legacy 모드가 실수로 전체 페이지네이션을 써서 배포만으로 과거 댓글 대량발송 위험 재현, disabled 모드가 게이트 우회, PENDING 보호가 allowlist 플래그에만 종속돼 baseline 준비 작업(Phase B) 도중 무방비, JSON에서 방금 제거된 ACTIVE media가 DB 동기화 전까지 통과되는 경쟁 구간, `--activate` "경고만"이 위험함(allowlist+shadow+ACTIVE 조합이 다음 폴링 주기부터 실발송으로 이어짐 재현) → 하드 블록으로 변경, `--confirm-runtime-proof`가 증명이 아니라 자기선언임을 인정해 `--acknowledge-runtime-proof`로 개명 + CLI가 명시적으로 `.env` 로드하도록 수정.
   - 신규 테스트 87개, 전체 회귀 **424 total / 416 passed / 5 failed(무관 기존 `test_dm_close.py` 4건 + flaky 후보 `test_review_grid_ui.py` 1건, 반복 실행 중 재현 여부가 갈려 환경 타이밍 의존으로 추정되나 원인조사 전이라 공식 UNCLASSIFIED 유지) / 3 xfailed**.
   - 커밋 스테이징을 hunk 단위로 정밀 분리(`comment_auto_reply.py`의 게이트 부분만 스테이징, 가격 키워드 확대 부분은 워킹트리에 남기고 제외) — Codex가 최종 `git diff --cached --stat`/`--check` 재검수 후 승인.
   - 의무기록 5종(`ERROR_DATABASE.md` ERR-069 / `FAILURE_PATTERN.md` FP-050 / `INCIDENT_TIMELINE.md` INC-038 / `VALIDATION_STATUS.md` / `porting_logs/MERGE_JOURNAL.md`) 작성, `.env.example`에 신규 킬스위치 3종(`COMMENT_POLL_ALLOWLIST_MODE`/`COMMENT_POLL_MAX_PAGES`/`COMMENT_POLL_FAILURE_ALERT_THRESHOLD`) 등록 — 전부 이번 커밋에 포함.

5. **커밋+push 완료** — `eb98741`(Package 1 Phase A) push 시 그 이전 로컬 전용 커밋 2개(`00466a3` FP-047, `07e6521` ERR-066 PII 마스킹 — 둘 다 이 세션 내 이미 승인·커밋됐던 것)도 함께 origin에 반영됨(fast-forward, 선택적 push 불가능한 git 특성).

### Known Facts
- `COMMENT_EVENT_STORE_MODE=shadow`(FP-047), `COMMENT_POLL_ALLOWLIST_MODE=legacy`(Package 1), `COMMENT_AUTO_REPLY_ENABLED=true`, `COMMENT_REPLY_COOLDOWN_HOURS=0`, `COMMENT_REPLY_DAILY_BUDGET=100000` — 260716 기준 실제 `.env` 상태(라이브 테스트 이후 유지 중).
- `configs/comment_campaign_posts.json`: media_ids 6개로 확장된 상태(이전 세션 회장 직접 편집분, Package 1과 무관하게 이미 반영됨, 미커밋 상태로 워킹트리에 남음).
- `comment_poll_targets`/`comment_campaign_config`/baseline CLI는 전부 코드만 존재 — 실제 `--apply`/`--activate` 한 번도 미실행, `COMMENT_POLL_ALLOWLIST_MODE=allowlist`/`COMMENT_EVENT_STORE_MODE=enforce` 전환도 미실행.
- shadow 모드 라이브 테스트로 인해 `db/comment_events.db`에 실계정 댓글 다수가 `SHADOW_SEEN` 태그로 이미 존재 — 향후 baseline `--apply` 실행 시 이 행들을 "확정완료 아님"으로 분류해 정상 처리하도록 이미 코드 반영됨(P0-4).

### P0 Backlog (다음 세션)
1. **[최우선]** Meta App Review 결과 확인 + ManyChat 전환 여부 최종 결정(ERR-064/FP-048/INC-036) — 이전 세션부터 이어지는 미결 사안, 여전히 미확인
2. 가격 키워드 확대 정책 변경(`comment_auto_reply.py`)의 별도 커밋 여부 결정
3. Package 1 Phase B 착수 여부 결정 — allowlist 모드 전환 → 6개 media 순차 baseline(`--dry-run`/`--apply`/`--verify`) → enforce 전제조건(원문 평문 저장/Airtable preflight) 해소 → 자동 Runtime Proof 시스템 → 1개 media Canary → 전체 활성화, 각 단계 별도 승인
4. FP-047 enforce 진입 전제조건(원문 평문 저장, Airtable 필드 preflight) 착수 여부
5. ⚠️ 260706~260709 구간 여전히 별도 미반영 — 과거 Backlog 그대로 승계

### 관련 문서
- ERR-067~069, FP-047/050, INC-035/038, `docs/design/FP047_COMMENT_EVENT_IDEMPOTENCY_260715.md`, `porting_logs/MERGE_JOURNAL.md`(상세 구현 로그·9라운드 버그 목록) — 전체 raw 근거는 각 문서 참조

---
