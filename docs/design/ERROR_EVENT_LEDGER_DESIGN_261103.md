# 오류 이벤트 원장(Error Event Ledger) 설계 — 261103

작성: Claude Code (설계만, 코드·설정 변경 없음). 상태: 승인 대기.

## 1. 문제
AdsPower 한도 때문인지, Meta 차단(190/459 등)인지, 이미지 호스트 문제인지를 **한 곳에서 정확히 구분해 볼 수 없다.**
- 게시 실패 사유는 Airtable에 쓰지 못한다(ERR-075: `Instagram_Posts`에 error_code 필드가 없어 쓰면 PATCH 전체가 422로 거부) → 로그에만 남고, 로그는 회전·분산돼 있다.
- Meta 오류 본문(code/subcode)은 `_extract_meta_error_detail`이 **문자열로만** 만들고(`launcher/main.py:334`) 코드별 분류·알림·계정별 집계가 없다.
- 오류 종류별로 기록 위치가 제각각이다(AdsPower=`db/adspower_open_daily.json`, Gemini=error.log 429 줄, Meta=게시 실패 로그, ImgBB=Meta 9004로만 드러남).

## 2. 증거(오늘 실측)
- AdsPower: `{"count":5,"blocked_until":"2026-11-03 22:31:16"}` + `fb_crawl 스킵 — AdsPower Open 한도 초과` 로그 → 구분 가능.
- Meta 9004/2207052: `meta_error=(message=Only photo or video..., code=9004, subcode=2207052)` 로그 → 구분 가능하나 집계 없음.
- Gemini 025: 429 `project_number:130069634177` — 진단에 수동 호출이 필요했음.
- Meta 190/459: 코드에 분기·기록·알림이 **없음**(`main.py`에 190/459 분기 검색 결과 없음).

## 3. 선택지 (Build / Reuse / Buy)
- **Reuse:** `_extract_meta_error_detail`(파싱), `modules/common/*` SQLite 저장 패턴(`retry_queue`, `publish_ledger`, `producer_lock`), `services/slack_notifier`, 기존 `handle_errors`.
- **Build(작게):** `modules/common/error_events.py`(분류기 + SQLite 기록 + 1일 1회 알림 중복 억제). 외부도구 불필요(Sentry 등은 현재 규모에 과함, DEFER).
- **금지:** Airtable `Instagram_Posts`에 오류 필드를 쓰지 않는다(ERR-075 재발 방지).

## 4. 설계
**저장:** `db/error_events.db`(SQLite, gitignore 대상). 테이블 `events(ts, source, account, error_class, severity, http, code, subcode, stage, record_id, detail_head)`; `detail_head`는 `safe_text`(공백 정리 → 퍼센트 디코딩 → URL 쿼리 제거 → `redact_sensitive` → 접두 토큰 마스킹 → 앞 200자). `stage`는 기록 지점(`poller_publish`, `slot_publish_<kind>`)이며, 자동 대응을 뜻하는 `action` 열은 2단계(소프트 보류)에서 추가한다(Codex 리뷰: 설계-구현 불일치 정리).
**지연 상한:** 이벤트 기록과 알림 중복 확인은 한 연결·한 트랜잭션(SQLite 대기 최대 3초 1회), Slack 발송은 DB를 닫은 뒤 별도 데몬 스레드 — 게시 실패 처리 경로의 최대 지연은 DB 대기 3초.
**분류(`classify_meta_error(http, code, subcode)`):**

| error_class | 조건 | 심각도 | 자동 대응(1단계) |
|---|---|---|---|
| META_AUTH | code 190·102, 또는 subcode 458·459·460·463·467(보통 `code=190` 아래 subcode) | P1 | 기록 + Slack 1일 1회/계정 |
| META_PERMISSION | code 10, 200~299 | P1 | 기록 + Slack |
| META_RATE_LIMIT | code 4, 17, 32, 613, 80002 | P2 | 기록 |
| META_MEDIA_FETCH | 9004/2207052 | P2 | 기록(이미지 호스트 문제 추적) |
| META_POLICY_BLOCK | code 368 등 | P1 | 기록 + Slack |
| META_TRANSIENT | 1, 2, 5xx, 타임아웃 | P3 | 기록 |
| META_UNCLASSIFIED | 그 외 | P2 | 기록(분류표 보강 대상) |
다른 출처(2단계): `ADSPOWER_OPEN_LIMIT`, `ADSPOWER_DOWN`, `GEMINI_QUOTA_429`, `GEMINI_AUTH`, `IMGBB_FETCH`, `AIRTABLE_HTTP` — 기록 지점만 추가.

**1단계 범위(이번 승인 대상):** Meta 게시 경로만. `launcher/main.py`의 `publish_single` 실패 지점(Phase A 컨테이너 생성 실패, Phase B 모호 실패, 확정 실패)과 두 게시 잡의 실패 처리에서 `record_error_event(...)` 호출. 게시 흐름·재시도·상태 변경은 바꾸지 않는다(기록과 알림만, 실패해도 게시 흐름을 막지 않는 try/except 격리).
**조회:** `python -m modules.common.error_events --since 24h --by account,class` CLI + 일일 요약 알림(INFO).
**2단계(별도 승인):** META_AUTH 발생 계정의 "소프트 보류"(SQLite 보류 목록, 폴러가 조회) — Airtable `automation_enabled`를 코드가 쓰지 않는다.
**3단계(별도 승인):** AdsPower·Gemini·ImgBB 출처 연결, 일일 INFO 요약, 상태 대시보드 탭.

## 5. 가장 작은 테스트
단위: 분류표 전 항목(경계값 포함), 기록 실패가 호출자에 예외를 전파하지 않음, 알림 1일 1회 중복 억제, 마스킹, 동시 기록(SQLite WAL). 회귀: 게시 관련 기존 테스트(`test_publish_*`) 전체. Runtime: 의도된 가짜 Meta 오류 1건을 단위 수준에서만 재현(운영 계정에 오류를 일으키지 않는다).

## 6. 원복
`git revert` 한 번 + 재시작. DB 파일은 삭제해도 게시에 영향 없음(부가 기록).

## 7. 리스크
- 기록 호출이 게시 경로에 들어가므로 예외 격리와 지연 방지(로컬 SQLite, 타임아웃 짧게)가 필수.
- 분류표의 일부 코드는 Meta 문서 기준이라 실제 운영 데이터로 보강이 필요(UNCLASSIFIED 집계로 확인).
- Instagram 직접 확인 같은 Runtime 증거는 첫 실제 오류가 나야 얻는다.

## 8. 회장 결정
1. 1단계(Meta 게시 경로 기록 + 알림만)로 시작해도 되는가. 2단계 소프트 보류는 별도 승인.
2. 알림 채널은 현재 Slack으로 시작(텔레그램 구축은 HOLD 유지).

## 9. GPT 검토 요청문(필요 시)
```
검토 요청: docs/design/ERROR_EVENT_LEDGER_DESIGN_261103.md. (1) Meta 오류 분류표(190/102/459/463/467=AUTH 등)가 Graph API 공식 오류 코드와 일치하는가, 누락된 코드가 있는가 (2) 기록을 게시 경로에 넣을 때 예외 격리·지연 방지 설계가 충분한가 (3) 1단계(기록+알림)와 2단계(소프트 보류) 분리가 적절한가
```
