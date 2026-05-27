# MERGE_JOURNAL

> 생성일: 2026-05-16 20:34
> 목적: 250723 참조 저장소 → 260511 Active 저장소 수동 이식 작업 기록

---

## [260526] 하노이 세션 — Airtable 스키마 정리 + Persona_Profile 구축

| 항목 | 내용 |
|------|------|
| 작업일 | 2026-05-26 |
| 위치 | 하노이 도착 후 첫 세션 |
| 작업 1 | 孤兒 필드 4개 삭제 — `caption copy`, `post_url copy`, `error_message` (Instagram_Posts) / `source_url (URL)` (Source_Feeds). grep 전수조사 코드 참조 0건 확인 → Airtable UI 직접 삭제. `docs/schema_governance.md` 삭제 확정 기록 추가. |
| 작업 2 | Account_Registry ACC-001 검증 — `ig_user_id: 17841476202821375` / `fb_page_id: 868456346356581` / `account_email: nhm880808@gmail.com` 3개 필드 PASS. `tools/check_account_registry.py` 작성. |
| 작업 3 | Persona_Profile 테이블 신규 생성 (Metadata API) — table_id: tblbxtUH1K88aomOP, 12개 필드, Account_Registry 링크 연결. `tools/create_persona_profile_table.py` 작성. |
| 작업 4 | Persona_Profile PER-001 레코드 생성 — record_id: reck5gPdhpWqgmdKP, persona_name: 엔틱, persona_role: seller, mbti_type: INTJ. |
| 작업 5 | 백업 완료 — `C:\backup_(3)_260526 1350_SNS_24AutoProject_260511.zip` |
| 커밋 목록 | `b8033dd` schema orphan cleanup / `eb22910` add Persona_Profile table / `d6b7eb4` orphan fields deleted / `2953ddf` PER-001 record / `fe756ac` progress all complete |

---

## [260517-2] launcher/main.py 안정화 수정 3건 (PHASE2 검증)

| 항목 | 내용 |
|------|------|
| 작업일 | 2026-05-17 |
| 대상 파일 | `launcher/main.py` |
| 수정 1 | OAuthException 190/104 감지 시 `_slack` 직접 호출 + `raise` (ERR-017) |
| 수정 2 | `post_status='uploading'` 원자적 잠금 + `max_instances=1` (ERR-018) |
| 수정 3 | `ig_media_id` 존재 시 재업로드 차단 — `posted` 복원 후 `continue` (ERR-019) |
| 근거 | PHASE2_CHECKLIST #3/#4/#5 검증 중 GAP 발견 후 즉시 수정 |
| 커밋 | 이번 커밋 포함 |

---

## [260517] imgbb 영구 URL 방식 도입

| 항목 | 내용 |
|------|------|
| 작업일 | 2026-05-17 |
| 대상 파일 | `modules/sns/instagram_uploader.py` |
| 변경 내용 | Facebook CDN URL → imgbb API 재업로드 → 영구 URL 방식으로 전환 |
| 근거 | ERR-013 (aspect ratio / CDN 만료) 반복 해결 불가 → FP-015 등록 |
| 결과 | `ig_media_id=18116524126780958` 실제 업로드 성공 / INC-010 |
| 환경변수 추가 | `IMGBB_API_KEY=702c210583c10ddbeb435751b1b2e5fa` (.env) |
| 커밋 | `0456adb` fix: preprocess image via imgbb upload |

---

---
## [260527] watchdog 재기동 + Runtime Infra Recovery

### 장애 원인
- Flask/launcher/ngrok 2026-05-18 이후 중단 (9일간 미기동)
- watchdog.ps1 미실행 상태

### 재기동 시각
- 2026-05-27 14:57

### 복구 결과
- Flask ✅ / launcher ✅ / ngrok ✅ / Streamlit ✅
- overall=ok 확인 (scheduler_err.log 15:00)
- _job_fb_crawl / _job_insta_upload / _job_kpi_snapshot 정상 실행

### DEFAULT_BASE_PRICE
- .env 설정값: 50000 ✅
- Runtime 실제 반영: UNKNOWN (실제 DM price inquiry 미수신)

### 신규 파일
- docs/CURRENT_RUNTIME_CONTEXT.md 생성 ✅
- CLAUDE.md append 완료 ✅

### 현재 상태
Runtime Infra Recovery Complete / Business Flow Verification Pending
