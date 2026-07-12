# MERGE_JOURNAL

> 생성일: 2026-05-16 20:34
> 목적: 250723 참조 저장소 → 260511 Active 저장소 수동 이식 작업 기록

---

## [260619_Airtable_crawl_urls_전환] CRAWL_TARGET_SOURCE Feature Flag + Airtable 단일 소스 전환

| 항목 | 내용 |
|------|------|
| 작업일 | 2026-06-19 |
| 커밋 | 9cc4ee9 |
| 변경 1 | `.env` — FB_MAX_POSTS=20 추가 |
| 변경 2 | Airtable `Crawl_Targets` — platform/max_posts/account_ref/last_run_at/last_result 필드 5개 추가 (Metadata API) |
| 변경 3 | `modules/common/account_manager.py` — `_load_crawl_urls_from_airtable()` 추가: Airtable Crawl_Targets에서 Active+facebook URL 조회 |
| 변경 4 | `modules/common/account_manager.py` — `_shadow_compare()` 추가: accounts.json vs Airtable URL 집합 비교 로그 |
| 변경 5 | `modules/common/account_manager.py` — `_get_all()` CRAWL_TARGET_SOURCE 분기: accounts_json/shadow/airtable 3단계 |
| 변경 6 | `.env` — CRAWL_TARGET_SOURCE=shadow → CRAWL_TARGET_SOURCE=airtable 최종 전환 |
| Shadow 검증 | accounts.json=5건 / Airtable=4건 / 누락 그룹 610113703703488(Hold) 정상 감지 |
| Runtime Proof | Airtable 4건 URL 기반 크롤링 — groups/1827528710833477 → 1건 수집 (720×1280) 확인 ✅ |
| 상태 | accounts.json: 계정/세션 정보 전용 / crawl_urls: Airtable Crawl_Targets 단일 소스 |
| push | 완료 (9cc4ee9 → origin/master) |
| 다음 세션 | 도매꾹(domeggook) 크롤러 추가 — Crawl_Targets platform=domeggook 지원 |

---

## [260617_n8n설계+publish_single분리] publish_single() 분리 / n8n WF 설계 확정

| 항목 | 내용 |
|------|------|
| 작업일 | 2026-06-17 |
| 커밋 | 9d65cb4 / 20bef95 |
| 변경 1 | `launcher/main.py` — `publish_single()` 분리 (9d65cb4): 게시 로직 독립 함수화, APScheduler + n8n Endpoint 공용 호출 가능, Token 호출자 주입 구조 |
| 변경 2 | `launcher/main.py` L191 — `last_error_msg` 잔존 참조 제거 (20bef95), ERR-041 완전 해소 |
| n8n 설계 | WF-01~WF-05 Architecture 확정 (DESIGN_COMPLETE) |
| Credential 구조 | Option B 확정: Python이 Graph API Token 소유, n8n Token 비보유, .env CRED_{ref}_TOKEN 형식 |
| Canonical Status | post_status 단일 사용 (publish_status 미사용) |
| P0 Backlog | execution_owner 필드 미구현 / instagram_publish_api.py 미구현 |
| Runtime Proof | NOT_EXECUTED (ready 레코드 0건) |
| push | 완료 (9d65cb4 → origin/master) |

---

## [260616_운영정비] M&Y GLOBAL 차단 / content_filter 개선 / clean_fb_metadata 크롤러 적용

| 항목 | 내용 |
|------|------|
| 작업일 | 2026-06-16 |
| 목표 | 워터마크 공급자 차단, FB raw_text 오염 제거, imgbb 업로드 유틸 신규 추가 |
| 변경 1 | Airtable `Supplier_Blocklist` — M&Y GLOBAL / Mooncher Kim 등록 (recEDhkour93vZR74, BLOCK_WATERMARK_SUPPLIER) |
| 변경 2 | `modules/sns/content_filter.py` — `_IMAGE_BLOCK_KEYWORDS`에 `r'm&y\s*global'` 추가 (a126754) |
| 변경 3 | `modules/sns/facebook_crawler.py` — `clean_fb_metadata()` import + L202 호출 추가 (0688849) |
| 변경 4 | `modules/sns/image_hosting.py` — imgbb 업로드 유틸 신규 생성 (BOM없음) |
| 선행 수정 (260616 1차) | ERR-040~043 4건 수정: post_status 옵션 복구 / retry_count 제거 (463c350) / CDN 중복 개선 (25c6779) / import re 추가 (366c617) |
| 업로드 증거 | A-F3-260616-001 (recklCtzkFd0TR2v4) posted ✅ |
| Blocklist 건수 | 5건 (M&Y GLOBAL 추가 후) |
| 최종 커밋 | 0688849 |
| push | 완료 (0688849 → origin/master) |

---

## [260611~260612_운영정비] Supplier_Blocklist 실차단 / LOST 구현 / 그룹 정리 / caption 재추가

| 항목 | 내용 |
|------|------|
| 작업일 | 2026-06-11 ~ 2026-06-12 |
| 목표 | 크롤링 품질 개선, Lead 상태머신 완성, 운영 오류 2건 해소 |
| 변경 1 | `modules/dm/dm_auto_reply.py` 또는 blocklist 모듈 — Supplier_Blocklist DRY_RUN 제거, continue 적용 (11fc204) |
| 변경 2 | `modules/dm/dm_followup_scheduler.py` — LOST 72h 타임아웃 구현, DRY_RUN 모드 (0e5133b) |
| 변경 3 | Airtable Lead_Interactions — lost_reason(Single line) / lost_at(Date) / disqualified(Checkbox) 필드 추가 |
| 변경 4 | `tools/generate_filter_rules.py` + `configs/filter_rules.json` — Crawl_Training_Set 기반 분석용 (3840a6a), 운영 연동 금지 |
| 변경 5 | `configs/accounts.json` — crawl_urls에서 FB그룹 1676627532598134 제거, 5개 유지 (c71f2c7) |
| 변경 6 | Airtable `Crawl_Targets` — rec20hOhqyCukfYPs (A001/FB_KB뷰티도매) 레코드 삭제 |
| 변경 7 | Airtable `Instagram_Posts.caption` 필드 재추가 — API로 multilineText 생성 (field_id: fldcxTzLzYCzD9aYe) |
| 변경 8 | Airtable `Instagram_Posts` rectwruMD3uua54sv — ig_media_id 17863634121631171 클리어 |
| 운영 오류 | ERR-028 재발(caption 422) → 재해소 / ERR-039 신규(ig_media_id invalid) → 해소 |
| 문서 | CURRENT_RUNTIME_CONTEXT.md 업데이트 (0b9291c) |
| 최종 커밋 | 0b9291c |
| crawl_urls | 5개 운영: 610113703703488(Hold) / 345179878828208 / 755455243345993 / 3289570041331131 / 1827528710833477 |

---

## [260602_섹션19] Clone Mode 그룹URL 다중화 + BOM 수정 + load_dotenv 추가

| 항목 | 내용 |
|------|------|
| 작업일 | 2026-06-02 |
| 목표 | crawl_urls 다중화, 환경 설정 버그 2건 수정 |
| 변경 1 | `configs/accounts.json` — crawl_urls 1개 → 4개 그룹 (1676627532598134 / 610113703703488 / 345179878828208 / 755455243345993) (3dbe72a) |
| 변경 2 | `configs/accounts.json` — PowerShell Set-Content UTF8 BOM 삽입 버그 수정. [System.IO.File]::WriteAllText + UTF8Encoding(false) 사용 (c6a30d1) |
| 변경 3 | `modules/sns/facebook_crawler.py` — 모듈 상단 `from dotenv import load_dotenv; load_dotenv(override=True)` 추가 (f5d59f2) |
| 검증 | Airtable 저장 성공 — 그룹 345179878828208 기준 `[AIRTABLE] 저장 완료` 확인 ✅ |
| pytest | 104 passed / 1 xfailed / 2 xpassed ✅ |
| 그룹 610113703703488 | div[role='feed'] 미탐지 — 가입 승인 대기 중, 코드 문제 아님 |
| 신규 ERR | ERR-035 (BOM 삽입) / ERR-036 (load_dotenv 모듈 누락) |
| 신규 FP | FP-025 (PowerShell UTF8 BOM) |
| 최종 커밋 | f5d59f2 |
| 백업 필요 | 다음 세션 초반 백업 권장 |

---
## [260601~260602] Clone Mode 전체 파이프라인 구축 + Runtime Proof

| 항목 | 내용 |
|------|------|
| 작업일 | 2026-06-01 ~ 2026-06-02 |
| 목표 | Facebook 원문 보존 Clone Mode 저장 파이프라인 구축 및 Runtime Proof 확보 |
| Phase 1 | `modules/sns/content_filter.py` — `replace_contacts()` 추가, 판매자 연락처 → 내 연락처 매핑 치환 (c8000ee) |
| Phase 2 | `modules/sns/caption_generator.py` — `generate_caption_clone()` 추가, Gemini rewrite 없이 원문 포맷 정리만 (3ed3b45) |
| Phase 3 | `modules/sns/facebook_crawler.py` — `run()` clone 경로 연결, `raw_text` 보존 + `replace_contacts()` → `converted_text`, `save_to_airtable()` payload 확장 (b059740) |
| Phase 4 | `modules/sns/content_filter.py` — keyword filter 확장 7개 + `BRAND_ALLOWLIST=["snuggle"]` (25c3f13) |
| Phase 5 | `modules/comment/comment_auto_reply.py` — `COMMENT_AUTO_REPLY_ENABLED=false` 안전장치, IG 공개 답글만 차단, Telegram+Airtable 유지 (a64b0ff) |
| Phase 6 | `modules/sns/facebook_crawler.py` — `expand_see_more()` 추가, post.text 읽기 전 더보기 클릭 (deec24c) |
| Runtime Proof | recsmA4WIlrur1wHO — original_text / converted_text / caption / media_type=image 저장 확인 ✅ |
| 백업 | C:\backup_(11)_260602_0108_SNS_24AutoProject_260511.zip |
| 주요 진단 | 베트남어 게시글 정상 차단 확인 / FB 더보기 클릭 110→581자 확장 확인 / GoogleTranslator 정상 동작 확인 |

---

## [260527_2000~2200] watchdog.ps1 Start-Flask 주석 처리 — :5000 중복 바인딩 + Dual Scheduler 해소

| 항목 | 내용 |
|------|------|
| 작업일 | 2026-05-27 |
| 대상 파일 | `watchdog.ps1` |
| 문제 | watchdog `Start-Flask`가 dm_receiver(:5000) 독립 기동 + launcher\main.py도 내부에서 `:5000` LISTEN → 이중 바인딩. dm_receiver 독립 APScheduler + launcher 내부 APScheduler → `process_due_followups` / `poll_new_comments` 매 5분 2회 실행(27초 간격) |
| 원인 분석 | launcher\main.py line 286~287 `start_scheduler()` 호출로 dm_receiver APScheduler가 launcher 내부에서 이미 기동됨. watchdog이 dm_receiver를 별도 프로세스로 추가 기동하면 중복 인스턴스 발생 |
| 수정 | `watchdog.ps1` `Start-Flask` 함수(line 97~103) + Flask 감시 블록(line 140~156) 주석 처리(#). 삭제 없음. launcher\main.py에 Flask 관리 위임. |
| 검증 | PSParser 문법 PASS. app.log 22:00:34 / 22:05:34 `process_due_followups` 1회/5분 2사이클 연속 확인. :5000 단일 LISTEN (PID 23272) 확인. |
| 근거 문서 | ERR-021 / FP-017 / INC-011 / VALIDATION_STATUS watchdog_flask_dual_fixed_260527 PASS |
| 커밋 | d3f9428 (이전) + 이번 세션 체크리스트 커밋 |

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

---
## [260527_1533~1940] 250723 전체 스캔 + E2E 로그 갭 확정

### 작업 내용
- 250723 전체 폴더 스캔 완료 (modules/dm, sns, common, crm, tools, dashboard, scripts, tests)
- 이식 대상 없음 확정 — 260511이 전부 더 완성됨
- 250723 pytest 마지막 결과: 613 passed / 17 failed / 6 errors — Green Build 아님
- E2E AutoReply 화면 증거 확인: "단가 기준가는 11,000원" 응답 (5/12)
- 로그 갭 원인 확정: watchdog Start-Process -RedirectStandardError overwrite 구조로 이전 세션 로그 소멸
- watchdog 19:37 재기동 완료 — Flask/Streamlit/ngrok/launcher 전부 OK

### 확정 사항
- 250723 역할: Archive / Evidence 참고용만
- 260511 보호 유지
- Business Runtime commit: 로그 증거 소실로 화면 증거만 존재 — commit 보류 유지

---
## [260602_Instagram_Upload_Pipeline_Proof] — 2026-06-02 16:20 KST

| 항목 | 내용 |
|------|------|
| 작업일 | 2026-06-02 |
| 대상 파일 | `modules/sns/content_filter.py`, `modules/sns/caption_generator.py` |
| 수정 1 | `clean_fb_metadata()` 추가 — Facebook UI 잔여물(작성자명·경과시간·구분점) 제거 |
| 수정 2 | `generate_caption_clone()` 에서 `replace_contacts()` 전에 `clean_fb_metadata()` 선처리 |
| 환경변수 수정 | 시스템 AIRTABLE_API_KEY 플레이스홀더 User scope 삭제 + 세션 제거 |
| dead code 확인 | `bot_uploader→insta_uploader` 체인, `instagram_uploader.py`, `uploader_instagram.py`, `wf_instagram_scheduler.py` 전부 dead stub 확인 |
| Airtable 정정 | ready 레코드 caption 오염 2건 일괄 정정 (recKLX1OsOvfRu5k1, recsmA4WIlrur1wHO) |
| Instagram 업로드 증거 | recFyw7OUaZ666JDJ → ig_media_id=18101360630320704 → post_status=posted ✅ |
| git 상태 | 349fedf → 59b57ed (docs: Instagram 업로드 Runtime Proof 기록) ✅ |
| 백업 | C:\backup_(12)_260602_2207_SNS_24AutoProject_260511.zip |

### 미완
- n8n 미설정 상태 (정상)
- dual scheduler 중복 발송 원인 파악됨 — 수정 미적용

---
## [260528_Virtual_AutoReply_Proof] — 2026-05-28 13:27 KST
- Infra: Flask :5000 PID 14256 + ngrok :4040 PID 8956 LISTENING 확인
- Webhook: 로컬 POST 200 OK 확인
- Parser: 단가 얼마예요? detect_price_inquiry=True 확인
- AutoReply: DEFAULT_BASE_PRICE=50000 적용, handle_price_inquiry 완료
- Airtable: LI-2B0A72F7 생성, recXgM9FlDo9EEikr qualified/auto_replied
- IG 발송 실패: TEST_SENDER_004 가상 ID 정상 예상 결과
- 백업: backup_(7)_260528_1338 완료

---
## [260528_Real_DM_Proof + Duplicate_Bug_Fix] — 2026-05-28 20:14~22:00 KST

| 항목 | 내용 |
|------|------|
| 작업일 | 2026-05-28 |
| 대상 파일 | `modules/dm/dm_auto_reply.py` |
| 수정 1 | _rule.reason AttributeError 수정 — `getattr(_rule, "reason", "unknown")` |
| 수정 2 | 중복 발송 방지 — `_has_recent_auto_replied()` 추가, `CREATED_TIME()` 기준 3분 window, `bridge_status='auto_replied'` 조건 |
| 실거래 DM Proof | IGSID 1792783944739953 → IG DM 발송 완료 20:14:37 (recKh3tm6R5foxjjv) ✅ |
| duplicate skip 검증 | 21:42:15 recvpUz9Q6YW4EsPv ✅ / 21:50:03 recKeIWfh5YtBLhzo ✅ |
| git 상태 | M modules/dm/dm_auto_reply.py (미커밋 — 사용자 승인 후 commit 예정) |
| watchdog autostart | SNS_Watchdog_AutoStart 등록 시도 → 관리자 권한 필요 (미완료) |
| dual scheduler | 중복 없음 재확인 — process_due_followups 1회/5분 정상 |

## 세션20 (2026-06-03)
- 작업: ExecutionPolicy Restricted 차단 해결
- 조치: LocalMachine RemoteSigned 적용
- watchdog.ps1 자가치유 블록 삽입
- 커밋: 2695d87 (push 완료)
- 문서: FP-027 / INC-019 / ERR-038 등록
- 시스템: Flask/APScheduler/ngrok/watchdog 전부 정상

## 세션20 최종 (2026-06-03 1730)
- 작업스케줄러 RunLevel=Highest 확인 완료
- watchdog 자가치유 블록 권한 검증 완료
- 세션20 완전 종료

## [260617] MERGE_JOURNAL - Airtable Account DB 구축

### 작업 내역
날짜: 2026-06-17
세션: 260617_Airtable_Account_DB

변경 내용:
1. Account_Registry 필드 6개 추가
2. 43개 계정 입력 -> 정리 후 33개 확정
3. Platform_Accounts 테이블 신규 생성
4. Instagram 19 + Facebook 12 = 31개 입력
5. Instagram_Posts 라우팅 필드 5개 추가
6. Linked Record 연결 완료
7. Pilot 3개 Active 설정

### 삭제된 데이터
- 기존 샘플 행 3개 (ACC-001/002/003)
- 빈 행 4개
- 중복 이메일 행 2개 (IDN-000023, IDN-000035)

### 원본 보존
- 원본 Excel: 원본_Email 260609_520_260319_240725.xlsx
- 백업 Base: BACKUP_260615


---
## [260617] ImgBB 연동 + 데이터 정합성 복구

### 작업 요약
- Dashboard 복구 (Flask/Streamlit/watchdog)
- Instagram 업로드 실패 원인: FB CDN URL -> error_subcode 2207052
- image_hosting.py 신규 생성 (imgbb 업로드 모듈)
- backfill_failed_images.py 신규 생성 (하드가드 12개)
- Backfill 1건 E2E 실증 성공 (rec2v96YaBLQJvLyl -> posted)
- ig_media_id 오염 78건 Graph API 검증 -> VERIFIED 3건 복구 / INVALID 75건 클리어
- launcher/main.py 버그 수정: unverified ig_media_id -> posted 강제전환 제거
- facebook_crawler.py Phase4: save_to_airtable()에 imgbb 연동

### 커밋
- e33cf37: fix: prevent unverified ig_media_id from forcing posted status
- 3b3fedf: feat: add ImgBB image hosting adapter
- 6ab2ff0: feat: add guarded failed-image backfill utility
- af85d3a: feat: integrate ImgBB upload in save_to_airtable (Phase4)

### 상태
- failed=145 / posted=14 / ready=0 / 성공률 8.2%
- push 미실행

---

## [260619_도매꾹크롤러] 2026-06-19 KST (세션2)

| 항목 | 내용 |
|------|------|
| 커밋 | 2112739 |
| 변경 1 | modules/crawlers/__init__.py 신규 |
| 변경 2 | modules/crawlers/base_connector.py — BaseCrawlConnector ABC |
| 변경 3 | modules/crawlers/domeggook_api_connector.py — API v4.1 Connector (aid=key) |
| 변경 4 | modules/crawlers/quality_gate.py — Gate READY/ERROR/FILTERED |
| 변경 5 | Crawl_Targets keyword 필드 추가 (fldNhkqfOJvkCZZnp) |
| Runtime Proof | health_check=True / fetch 10건 / Gate 5/5 PASS |
| 상태 | D001 Hold 등록 (recg8JU3eqL9BkMgf) — category_code 제외 |
| push | 완료 (5c10eca → 2112739 origin/master) |
| 다음 세션 | Dispatcher 연결 + Source_Items 테이블 설계 + D001 Runtime Proof 후 Active |

---

## [260619_세션3_Source_Items] 2026-06-19 KST

| 항목 | 내용 |
|------|------|
| 커밋 | f6bef6a |
| 변경 | domeggook_api_connector.py adultOnly 파싱 버그 수정 |
| Source_Items | tblMWJaInVHS7YfY6 생성 / 17개 필드 |
| STAGING TEST | 4/4 PASS (INSERT/SKIP/UPDATE/복구) |
| 절차 위반 | BOM/diff 확인 전 자체 진행 — 결과 정상이나 기록 |
| D001 | Hold 유지 |
| 다음 세션 | Dispatcher _job_dome_crawl() 구현 |

---

## [260619_세션4_Dispatcher] 2026-06-19 KST

| 항목 | 내용 |
|------|------|
| 커밋 | d1ca290 |
| 변경 | launcher/main.py — _job_dome_crawl() + add_job |
| DRY_RUN | D001 Hold 스킵 확인 |
| Runtime Proof | fetch=10 ready=10 Source_Items Upsert 정상 |
| max_posts 상한 | min(value,10) 강제 |
| D001 | Hold 복구 완료 |
| 다음 세션 | C003 수정 + D001 실운영 전환 + Export 파이프라인 |

---

## [260619_세션5_실운영전환] 2026-06-19 KST

| 항목 | 내용 |
|------|------|
| C003 | platform=daisomall 수정 완료 |
| D001 | Active 전환 + Runtime Proof 완료 |
| dome_crawl | 60분 interval 실운영 등록 |
| fetch | 10건 ready=10 Upsert 성공 |
| 다음 세션 | Export 파이프라인 + D002 추가 |

---

## [260619_세션6_ExportPipeline] 2026-06-19 KST

| 항목 | 내용 |
|------|------|
| 커밋 | d3b6003 (source_exporter.py) / 4bf6e74 (dome_export job) |
| 필드 추가 | Source_Items 4개 + Instagram_Posts source_item_id |
| Runtime Proof | exported=2 / 중복=0 / Gemini caption 정상 |
| dome_export | 10분 interval 실운영 등록 |
| 다음 세션 | D002 건강식품 추가 + 24시간 모니터링 |
---

## [260619_세션7_실운영확인] 2026-06-19 KST

| 항목 | 내용 |
|------|------|
| launcher 재시작 | dome_crawl + dome_export 자동 등록 확인 |
| D002 | 건강식품 Hold 등록 완료 |
| Source_Items | 21건 누적 / EXPORTED=4 |
| Instagram_Posts | 도매꾹 출처 3건 |
| 다음 세션 | D002 Active 전환 + 품질 확인 |

---

## [260619_세션8_D002확장] 2026-06-19 KST

| 항목 | 내용 |
|------|------|
| 커밋 | 7fdd9d1 |
| D002 | 건강식품 Active 전환 + Runtime Proof |
| dome_export | target_id=None / batch_size=5 확장 |
| exported | 3건 (D001+D002 혼합) Gemini 성공 |
| 다음 세션 | 품질 확인 + 카테고리 확장 검토 |

---


---

## [260624_세션9_RepositoryInterface완료] 2026-06-24 KST

| 항목 | 내용 |
|------|------|
| 커밋 체인 | 18aa3a7 → df9df6b → 4502e65 → e0bcff6 → 36cbf05 → 90c971d → 04e4b31 |
| 목표 | Infrastructure 외부 직접 호출 완전 교체 — AirtableRepository 단일 경로 확립 |
| 교체 파일 | dm(3) + crm(2) + comment(2) + account_manager + facebook_crawler + source_exporter + domeggook_ingest |
| 확정 메서드 | 22개 (list_blocked_suppliers, list_crawl_urls, upsert_source_feed 등) |
| Failure Injection | AdsPower Stop finally 경로 정상 실행 확인 PASS |
| Runtime Proof | 5회 연속 (19:50~21:50 KST) 정상 — DM·댓글·inquiry_message Airtable 저장 확인 |
| 외부 직접 호출 | 실질적 0건 확정 (airtable_autorun_engine.py dead 파일 제외) |
| inquiry_message 갭 | LeadInteractionCreate 누락 → 36cbf05 해소 |
| 다음 세션 | 260629 필터/caption 수정 |
## [260629_세션_CaptionBlocklist추가] 2026-06-29 KST

| 항목 | 내용 |
|------|------|
| 변경 파일 | modules/sns/content_filter.py |
| 내용 | CAPTION_BLOCKLIST 추가 (coslife, lily) + passes_keyword_filter() 선행 차단 로직 |
| 근거 | pytesseract 미설치로 OCR ImageFilter 무력화 확인 (ERR-044) |
| 효과 | 번역된 caption 텍스트에 coslife/lily 포함 시 keyword filter 단계에서 즉시 차단 |
| 다음 세션 | lily 오탐 모니터링 + pytesseract 설치 여부 검토 |

## [260703_세션_ERR046_SupplierBlocklist_필드매핑수정] 2026-07-03 KST

| 항목 | 내용 |
|------|------|
| 관련 | ERR-046, FP-034, INC-024 (2026-06-24 df9df6b 도입, 2026-07-02 감사로 발견, 2026-07-03 종결) |
| 변경 파일 | `modules/infra/repository_interface.py` / `modules/infra/airtable_repository.py` / `modules/sns/facebook_crawler.py` |
| 내용 | `SupplierBlockEntry`에 `page_name` 필드 추가, `list_blocked_suppliers()` `f.get("supplier_name","")` → `f.get("author_name","")`/`f.get("page_name","")` 매핑 수정, `load_supplier_blocklist()` 하드코딩 `page_name: ''` 제거 |
| Gate 6 검증 | ISOLATED INTEGRATION PROOF — 격리 신규 테이블 `Supplier_Blocklist_Test`(tbll1UZHjGEYOcgya) 생성 → 실 레코드 POST/GET(mock 없음) → BUGGY 매핑 재현(무증상 통과 확인) → FIXED 매핑 정상 매칭 확인 → 테스트 레코드 삭제(테이블은 재검증용 유지) |
| Runtime Proof | 운영 `Supplier_Blocklist` 5건 대상 `is_blocked_supplier()` 재실행 — Lily Yoon/Mooncher Kim/M&Y GLOBAL/Cosmetics Station/Athena Magnayon/COSLIFE 6/6 전건 매칭 성공 |
| 회귀 검증 | pytest 100 passed / 4 failed(pre-existing, git stash 비교로 수정과 무관 확인) / 3 xfailed |
| 미실시 항목 | 2026-06-24~07-02 무방비 기간 중 실제 비차단 업로드 유출 여부(Instagram_Posts author_name 일치 조회) — 별도 확인 필요 |
| 절차 | Gate 3 Read-only 조사(2026-07-02) → 사용자 승인 후 코드 수정(2026-07-03) → 문서화 |
| 다음 세션 | Instagram_Posts 유출 여부 조회, DI 리팩터링 회귀 테스트 의무화 체계 수립 검토 |

## RUNTIME STATUS (2026-07-04 세션 완료) — DI Canary #2

260704: airtable_integrity.py DI 전환 (Canary #2, Canary #1 auto_liker.py 후속)
- DI 스코프 전수 스캔(260704 grep_result) 기준 재판정 완료
- 신규 메서드 fetch_posted_missing_media_id() 추가:
  - repository_interface.py: ABC 계약 선언 (fetch_posted_with_media_id 다음 위치)
  - airtable_repository.py: 구현 — filterByFormula AND({post_status}='posted', {ig_media_id}='')
  - 기존 fetch_posted_with_media_id(!='' 필터)와 반대 조건, 재사용 불가 확인 후 신규 작성
- airtable_integrity.py: get_table("Instagram_Posts").all(formula=...) 3줄 → AirtableRepository().fetch_posted_missing_media_id() 1줄 치환
- tests/test_smoke_metrics.py: airtable_bridge.get_table mock → AirtableRepository.fetch_posted_missing_media_id mock 갱신 (2개 테스트)
- Blast Radius: 운영 소비처 core/run_engine.py 1곳(6시간 간격 스케줄), 테스트 소비처 tests/test_smoke_metrics.py 1파일(3건) — 그 외 없음 확인
- Runtime Proof: 타겟 3건 PASSED / 전체 100 passed·4 failed(pre-existing)·3 xfailed(260703 baseline 일치)
- BOM 확인: airtable_integrity.py / test_smoke_metrics.py 2개 파일 BOM 없음 확인(repository_interface.py / airtable_repository.py는 BOM 미검증)
- 부수 확인: services/slack_notifier.send_alert 실존 확인 (이전 미확인 상태 해소)
최신 commit: f6194ac
push: 436bdf7..f6194ac master -> master

## RUNTIME STATUS (2026-07-05 세션 완료) — DI Canary #3

260705: kpi_collector.py DI 전환 (Canary #3, Canary #2 airtable_integrity.py 후속)
- 신규 메서드 2개 추가:
  - repository_interface.py: fetch_all_instagram_posts() / fetch_all_lead_interactions(since_utc) ABC 계약 선언
  - airtable_repository.py: 구현 — 무필터 전체 조회 (offset 페이지네이션 미구현, 기존 코드베이스 전체 공통 한계로 확인)
- 기존 유사 메서드 5개(fetch_pending_posts/fetch_posted_with_media_id/fetch_posted_missing_media_id/get_base_price/fetch_today_lead_stats) 재사용 불가 확인 후 신규 작성 — 상태 필터·필드 제한·limit 상한 중 하나 이상 불일치
- kpi_collector.py: _fetch_leads()/_fetch_posts() 내부 get_table() 직접호출 2곳 → AirtableRepository 메서드 호출로 치환, airtable_bridge import 제거
- tests/test_smoke_metrics.py: 신규 테스트 4건 추가 (test_fetch_leads_calls_repository_with_start / test_fetch_leads_returns_empty_list_on_exception / test_fetch_posts_calls_repository / test_fetch_posts_returns_empty_list_on_exception)
- Blast Radius: 운영 소비처 core/run_engine.py(1시간 interval) + launcher/main.py(1시간 interval, 이중 진입점 기존 구조) + dashboard.py(collect_kpi/load_snapshots 간접 소비) — 그 외 없음 확인
- Runtime Proof: 타겟 4건 PASSED (17/17 파일 전체) / 전체 104 passed·4 failed(pre-existing, test_dm_close.py)·3 xfailed(baseline 일치)
- BOM 확인: repository_interface.py / airtable_repository.py / kpi_collector.py / tests/test_smoke_metrics.py 4개 파일 전부 BOM 없음 확인
- 신규 HOLD: airtable_repository.py 전체 GET 메서드 offset 페이지네이션 미구현 (100건 초과 시 첫 페이지만 반환, 이번 신규 2개 포함 기존 코드베이스 전체 공통 한계)
최신 commit: (커밋 후 갱신)
push: (승인 후 진행)

## RUNTIME STATUS (2026-07-06 세션) — launcher/main.py 중복 기동 사고 정리 (ERR-048/FP-036/INC-026)

260706: 코드 변경 없음 — 운영 프로세스 정리 + 문서화만 진행
- 세션 중 `Start-Process launcher\main.py` 반복 실행으로 5세대(10프로세스) 동시 생존 발견 (시작 시각: 07-05 23:38:57 / 07-06 16:46:43 / 16:51:04 / 16:55:41 / 16:55:57)
- watchdog.ps1 미기동(INC-025 지속) 확인 후 자동 재시작 경합 없이 8개 프로세스 `Stop-Process -Force` 정리
- 단일 신규 인스턴스(PID 33148/6140) 재기동, app.log(17:11:05~18) 상 스케줄러 1세트만 정상 등록·Flask 정상 바인딩 확인
- 잔존 미해결: PID 20448/5284(전날 기동, 동일 사용자임에도 Access denied) + `:5000` 유령 LISTENING PID 32944(Get-Process/Get-CimInstance 어디에도 미포착, 재현 확인) — 관리자 권한 세션 또는 재부팅 필요
- ERROR_DATABASE.md ERR-048 / FAILURE_PATTERN.md FP-036 / INCIDENT_TIMELINE.md INC-026 / VALIDATION_STATUS.md launcher_duplicate_instance_cleanup_260706(🟡 PARTIAL) 등록
최신 commit: (커밋 후 갱신)
push: (승인 후 진행)


---
## [260706] quality_gate.py relevance filter canary — 언어 불일치 P0 및 rollback (사고 A)

### 요약
`quality_gate.py` Domeggook 관련성 필터 canary 편집 → dry-run 검증 오판 → 전량 차단 P0 → rollback 완료.

### 사고 경위
- dry-run 검증: Instagram_Posts 영문 `caption` 필드 20건 기준, 20/20 MATCH 확인
- 실제 runtime: `run_gate()`가 검사하는 필드는 Domeggook API 원본 `title`(한국어)
- `COSMETIC_KEYWORDS`/`HEALTH_KEYWORDS` 영어-only 키워드 → 한국어 title 매칭 불가
- 결과: launcher/main.py 재시작 후 첫 `_job_dome_crawl`에서 D001(화장품)/D002(건강식품) 모두 `fetch=10 ready=0` — Domeggook 크롤 100% 차단

### 조치
- `git checkout HEAD -- modules\crawlers\quality_gate.py` 로 원본 4규칙(adult_only/title/unit_price/image_url) rollback
- launcher/main.py PID 지정 재시작(Stop-Process -Id 지정 후 재기동)으로 런타임 반영 확인
- 재시작 과정에서 launcher 5세대 중복 기동 발생(별도 사고 B, ERR-048/FP-036/INC-026 참조)

### 문서화
- ERROR_DATABASE.md ERR-049 working tree 문서화 완료, commit 전
- FAILURE_PATTERN.md FP-037 working tree 문서화 완료, commit 전
- INCIDENT_TIMELINE.md INC-027 working tree 문서화 완료, commit 전
- VALIDATION_STATUS.md 상태 표 + 근거 표 working tree 반영 완료, commit 전

### 현재 상태
`modules\crawlers\quality_gate.py` 기준 원본 4규칙 상태로 복원 완료. Gate 9~11에서 해당 파일 HEAD diff clean 및 relevance rule 잔존 없음 확인. 관련성 필터 재설계는 미착수.

### 다음 작업
한국어+영어 이중언어 키워드 기준 relevance filter 재설계 — 실제 Domeggook title(한국어) 원본 샘플로 dry-run 재검증 후 canary 편집 진행 예정.

commit: 미실행 — 5개 문서 diff 확인 후 별도 승인 필요
push: 미실행 — commit 후 별도 승인 필요

---

## [260707] quality_gate.py relevance filter — 한국어+영어 이중언어 재설계

### 배경
260706 canary 실패(ERR-049/FP-037/INC-027) — `git checkout HEAD -- modules\crawlers\quality_gate.py`로 rollback 후 재설계 착수.

### 정책 확정
- category_code='Healthy' → 무조건 READY (title 검사 없음)
- category_code='BEAUTY' → COSMETIC_KEYWORDS/IRRELEVANT_HINTS(한국어+영어) 매칭, 미매칭 시 기본 FILTERED
- 미용기기(LED마스크/마사지기 등) → 우선 제외 (2026-07-07 14:09 ICT 기록, 세부기준 DEFER)

### Dry-run 검증
- 실제 Domeggook title(한국어) 30건 기준, 사용자 승인 라벨과 대체로 일치
- Edge case 1건(상품유형 키워드 없는 title) — 기본 FILTERED 정책상 known limitation으로 승인

### Canary 편집 및 Runtime Proof
- `modules\crawlers\quality_gate.py`에 5번째 규칙(`relevance`, `_is_irrelevant_category`) 추가
- launcher/main.py PID 지정 재시작 중 중복 기동 이슈 발생, 단일화 완료. 단, 별도 런타임 이슈로 분리.
- Runtime Proof: D001(BEAUTY) fetch=10 ready=2, D002(Healthy) fetch=10 ready=10 — 정책대로 정상 동작 확인

### DEFER
- 키워드 보강(팩/패치/시트/수분/진정/미백/주름/피부 등)
- UNKNOWN 3단계 상태 도입 검토 (READY/FILTERED만 저장하는 현 구조 제약)
- FILTERED 로그 별도 저장

### 문서화
- VALIDATION_STATUS.md `quality_gate_relevance_filter_redesign_260707` 🟡 PARTIAL 반영 완료(working tree)

### Commit 대상
이번 commit 후보는 `modules\crawlers\quality_gate.py`, `docs\VALIDATION_STATUS.md`, `porting_logs\MERGE_JOURNAL.md`. ERROR_DATABASE/FAILURE_PATTERN/INCIDENT_TIMELINE은 44cefec에서 이미 commit/push 완료되어 이번 commit 대상 아님. commit/push는 최종 diff 확인 후 별도 승인.
### 260708 watchdog wrapper 생존 재검증 및 이중 감시 정리
- ERR-050 재확인: wrapper 인스턴스 실제 생존 1h46m(기존 기록 "2분+"보다 상향 확정)
- 12:03:12 WRAPPER END는 자연사 아닌 의도적 정리(이중 watchdog, FP-017 재발) — 근본 원인 오판 방지
- INC-025 임시 완화(Mitigated)로 갱신, VALIDATION_STATUS에 watchdog_task_wrapper_260708 🟡 PARTIAL 등록
- 미해결 잔여(260708 시점): 재부팅 시 BootTrigger/LogonTrigger 자동 발동 검증(ERR-047), direct 실행 60초 사망 근본원인 → 260709 세션에서 실증 완료, 상세는 하단 [260709] 섹션 참조

---

## [260709] watchdog 재부팅 자동트리거 실증 — Task Action 발동 확인, wrapper 4분24초 자연사망

### 요약
BootTrigger/LogonTrigger 자동 발동 여부 검증 Runbook(9단계) 실행 완료. 결과: 실제 재부팅(2026-07-08 20:29 KST) 후 Task Action(wrapper 경유) 발동은 확인됨 — 단, wrapper(PID 2656)가 약 4분 24초(20:32:17~20:36:41) 만에 WRAPPER END 로그 없이 종료(silent death). 트리거 자체는 살아있으나 wrapper 자연사망 근본원인은 여전히 UNKNOWN.

### Evidence
- `logs/watchdog_wrapper.log`: WRAPPER START 20:32:17 PID=2656, WRAPPER END 미기록
- `logs/watchdog_wrapper_stderr.log`: 0 bytes
- `logs/watchdog.log`: 20:32:18~20:36:41 HEARTBEAT 이후 무기록
- `schtasks /Query /TN "SNS_Watchdog_AutoStart" /V`: Last Run Time 2026-07-08 20:32:05, Last Result -1073741510(0xC000013A)

### 문서 반영 (4건, 모두 working tree — commit 전)
- `docs/ERROR_DATABASE.md` — ERR-047에 Note 2, ERR-050에 Note 3 추가
- `docs/INCIDENT_TIMELINE.md` — INC-025에 재부팅 실증 Note 추가
- `docs/VALIDATION_STATUS.md` — `watchdog_task_wrapper_260708` 확인일 260708→260709 갱신, 상세설명 "미검증"→"실증 완료·부정적 결과"로 교체
- `porting_logs/MERGE_JOURNAL.md` — 본 항목 추가

### 근본원인 상태
- ERR-047(재부팅 무재실행 근본원인), ERR-050(wrapper 사망 메커니즘) 모두 UNKNOWN 유지 — 이번 세션에서 해결 선언 없음
- 실제 발동 트리거가 BootTrigger인지 LogonTrigger인지는 Operational Event Log 미확인으로 미확정

### 다음 세션 승계
- INC-022 번호 중복(line 235/279, 서로 다른 사건) — 이번 세션에서 다루지 않음, HOLD 유지, 별도 승인 시 처리
- `Microsoft-Windows-TaskScheduler/Operational` Event Log로 BootTrigger/LogonTrigger 실제 발동 주체 확인
- wrapper 4~5분 후 종료 주체 A/B 테스트(Task Scheduler 세션정리 / PowerShell Host 종료 / wrapper 내부 예외)

commit: 미실행 — 4개 문서(ERROR_DATABASE.md/INCIDENT_TIMELINE.md/VALIDATION_STATUS.md/MERGE_JOURNAL.md) working tree에만 반영, 별도 승인 필요
push: 미실행 — commit 후 별도 승인 필요

---

## [260709] Task Scheduler 진단 Task A/B/D — 12:51~13:17 간헐적 launch-only 실패 A/B 조사 (ERR-051)

### 요약
운영 Task와 완전 별개인 진단용 Task(`SNS_WatchdogAB_TestA`/`TestB`/`TestD`)로 Task Scheduler Action 실행 자체의 신뢰성을 검증. 12:51:15~13:17:53 구간(약 26분) 5회 시도 전부 "launched"만 기록되고 프로세스 생성 흔적 없이 무반응, 13:22:01 이후로는 동일 설정으로 7회+ 전부 정상 성공. 8개 후보 원인을 순차 격리 테스트로 배제했으나 근본원인은 특정하지 못함 — ERR-051로 등록.

### 격리 테스트 순서 및 결과 (전부 기각)
1. `MultipleInstancesPolicy` IgnoreNew→Parallel(Task B) — 동일 실패
2. `UseUnifiedSchedulingEngine` — Task B/운영 Task 모두 True로 이미 일치, 변수 아님
3. 실행 엔진(PowerShell→cmd.exe, Task D) — 동일 실패
4. `RunLevel` Highest 유지 상태에서 재시도 성공 — Highest 단독 원인 아님(Limited 실제 검증은 cmdlet 부재로 미실시)
5. 세션 불일치 — 도구 세션/admin 대화형 세션 모두 SessionId=1로 동일, 기각
6. 프로세스 생성 감사 정책 — `auditpol` "No Auditing", 4688 자체 부재로 판별 불가
7. Defender/CodeIntegrity/SmartAppControl — 3개 소스 모두 해당 구간 차단·탐지 이벤트 0건, SmartAppControl=Off
8. Task Scheduler 부하 및 절전(Modern Standby) 복귀/DeviceAssociationService 3502 반복 에러(12:46~13:19) — 시간상 실패구간을 포괄했으나 16:15~16:39 성공구간에도 동일 밀도로 발생해 최종 기각

### 전환 시점 조사
13:20~16:30 구간 시스템 전역 Task Scheduler 로그 확인 결과 실패 이벤트(103/202) 0건, 13:22:01부터 모든 태스크 정상 완료 — 전환 시점을 13:17:53~13:22:01(4분 창)로 좁혔으나 System/Application 로그에 3502 반복 외 다른 신호 없어 직접 원인 미확보.

### 문서화
- `docs/ERROR_DATABASE.md` — ERR-051 신규 등록(working tree, commit 전)
- `porting_logs/MERGE_JOURNAL.md` — 본 항목 추가

### 다음 세션 승계
- ERR-051 재발 시: `129/100/200/201/102` 이벤트 시퀀스 부재를 실행 실패 신호로 즉시 포착하는 모니터링 필요성 재확인
- RunLevel=Limited 실제 검증 미실시(cmdlet 정정 필요: `Set-ScheduledTask -Principal`)
- 진단용 Task A/B/D는 증거 보전을 위해 삭제하지 않고 보존 — 정리 여부 별도 승인 필요

commit: d07e80d 완료 (주: 본 섹션 하단의 "commit: 미실행" 표기는 커밋 반영 후 갱신 누락된 잔존 텍스트 — 260709 후속 세션에서 확인)
push: 미실행 — commit 후 별도 승인 필요

---

## [260709] ERR-051 후속 — RunLevel=Limited 실증 + 100% 재현 (Task B, 관리자 권한)

### 요약
ERR-051에서 "미검증 상태로 남음" 처리됐던 후보(4) RunLevel=Limited를 실제로 검증. Task B(`SNS_WatchdogAB_TestB`)를 관리자 권한 PowerShell(UAC 승인)에서 `New-ScheduledTaskPrincipal -RunLevel Limited` + `Set-ScheduledTask -Principal`로 변경 후(22:26:55) `Start-ScheduledTask`로 총 6회(22:28:01, 22:29:28~22:30:21 5연속) 트리거. 6/6 전부 동일 launch-only 패턴으로 재현되어 RunLevel 후보를 배제 확정. 아울러 Task 전체 `State`가 트리거 후 `Queued`에 30초+ 고착되는 신규 증상을 관측(이전 조사에서는 미확인 항목).

### 실행 절차
1. `Get-ScheduledTask ... Principal` / `State` 조회 — 최초 RunLevel=Highest, State=Ready 확인
2. 관리자 PowerShell 세션이 아니어서 `Set-ScheduledTask` 최초 시도 시 `Access is denied`(HRESULT 0x80070005) — 일반 권한 세션의 한계 확인
3. `Start-Process powershell -Verb RunAs`로 관리자 창 기동(UAC 사용자 승인) → 스크립트 파일 경유로 `Set-ScheduledTask -Principal` 실행 → 결과 파일에 `SUCCESS` 기록 확인
4. 변경 후 `Get-ScheduledTask ... Principal`로 RunLevel=Limited 반영 재확인
5. `Start-ScheduledTask` 1회 트리거 → `LastTaskResult=0`이나 마커 파일 mtime 미변경(16:56:12 그대로) 최초 이상 감지
6. 이벤트 로그(`Microsoft-Windows-TaskScheduler/Operational`) 조회 — `110`+`325`만 존재, `100/200/201/102` 부재 확인
7. 재현성 확보 위해 5회 추가 트리거(8초 간격 실행 + 5초 대기, 총 5세트) — 5/5 전부 동일 패턴(`LastTaskResult=0`, 마커 미갱신, 이벤트 `110`+`325`만)
8. `Settings.MultipleInstances` 확인 — `Parallel`(인스턴스 제한 아님, 후보 1번과 별개로 재확인)
9. Task `State` 5초 간격 6회 연속 폴링(30초) — 전부 `Queued`, `Ready` 미복귀 확인(신규 증상)
10. `tasklist`로 powershell.exe 프로세스 존재 확인 — 0개

### 근본원인 상태
- ERR-051 근본원인: 여전히 UNKNOWN — 이번 조사로 원인을 특정하지 못함
- 확정된 것: RunLevel(Highest/Limited 무관)은 원인이 아님, `LastTaskResult=0`은 실행 성공의 신뢰 가능한 지표가 아님(FP-038 신규 등록)
- 미확정: 22:26:55 `Set-ScheduledTask`(Task 정의 갱신) 자체가 이번 100% 재현의 트리거였는지 여부 — 상관관계만 관측, 인과관계 미확정

### 문서화
- `docs/ERROR_DATABASE.md` — ERR-051 Status 갱신(🟡 재현 불가 → 🔴 260709 재현됨) + 260709 후속 조사 섹션 추가
- `docs/FAILURE_PATTERN.md` — FP-038 신규 등록(`LastTaskResult=0` 허위 성공 신호 패턴)
- `porting_logs/MERGE_JOURNAL.md` — 본 항목 추가

### 다음 세션 승계
- ERR-051 근본원인 조사 계속 필요 — 이번 100% 재현이 재현 조건(Task 정의 갱신 직후?)을 좁힐 단서일 수 있음, 다음 세션에서 "Set-ScheduledTask 갱신 없이 순수 반복 트리거만" A/B 테스트로 인과관계 격리 권장
- Task `State=Queued` 고착 현상을 watchdog 자체 감시 로직에 조기 경보 지표로 추가할지 검토(FP-038 예방안 참조)
- 진단용 Task A/B/D는 계속 보존 — TestB는 현재 RunLevel=Limited 상태로 변경된 채 남아있음(운영 Task와 무관하므로 원복 불필요, 단 인지 필요)

commit: 미실행 — `docs/ERROR_DATABASE.md`/`docs/FAILURE_PATTERN.md`/`porting_logs/MERGE_JOURNAL.md` working tree에만 반영, 이번 커밋으로 함께 반영 예정
push: 미실행 — commit 후 별도 승인 필요

---

## [260709] INC-028 등록 — watchdog.log 감시 공백 3시간12분(20:09:40~23:22:14) + 파이프라인 전체 다운 및 재기동

### 요약
ERR-051 재현성 확인 작업 이후 운영 서비스 상태를 점검하는 과정에서, `logs/watchdog.log` 하트비트가 20:09:40에서 정지되어 있고 launcher/main.py(:5000)·Streamlit(:8501)·ngrok(:4040) 3개 서비스 프로세스가 전부 부재, 포트 3개 전부 미바인딩 상태임을 발견(22:56경 최초 포착, 23:01:54 종합 확인). 전수 프로세스 확인(잔존/좀비 0건)을 선행한 뒤 python/streamlit/ngrok을 순차 재기동하고, 관리자 권한(UAC 승인)으로 watchdog.ps1을 재기동해 23:22:14 HEARTBEAT 재개 확인. 4개 서비스 전부 정상화됐으나 공백의 근본 원인은 UNKNOWN으로 남음.

### 문서화
- `docs/INCIDENT_TIMELINE.md` — INC-028 신규 등록(발생/발견/요약/발견당시상태/재기동절차/근본원인 UNKNOWN 명시/해결/재발방지/n8n 노이즈 별도 기록)
- `docs/ERROR_DATABASE.md` — ERR-047/ERR-050/ERR-051 관련 라인에 INC-028 상호 참조 추가(3곳)
- `porting_logs/MERGE_JOURNAL.md` — 본 항목 추가

### 근본원인 상태
- INC-028 자체 원인: UNKNOWN — System 이벤트 로그(20:05~20:20) 매칭 0건은 원인 배제도 확정도 아님, 재부팅 여부·foreground 세션 종료 여부 모두 미확정으로 명시적 표기
- ERR-047/ERR-050/ERR-051과의 통합 조사 여부는 미결정 — 다음 세션 판단 필요

### 다음 세션 승계
- INC-028과 ERR-047/050/051의 인과관계·통합 조사 여부 판단
- watchdog 하트비트 정지에 대한 자동 감지/알림 계층이 실제로 이번 3시간+ 공백 동안 작동했는지(또는 왜 작동하지 않았는지) 검증 필요
- n8n WARN→ERROR→RECOVER 노이즈 패턴에 대한 별도 FP 등록 여부는 미결정(승인 대기)

commit: 미실행 — `docs/INCIDENT_TIMELINE.md`/`docs/ERROR_DATABASE.md`/`porting_logs/MERGE_JOURNAL.md` working tree에만 반영, 별도 승인 필요
push: 미실행 — commit 후 별도 승인 필요

---

## [260710] heartbeat_monitor 절전 대응 + Governance 강화 + TestA/B/D 정리

### 요약
watchdog 감시 공백(ERR-047/050/051 계열) 후속 조사가 이전 세션(260709_2200)에서 시작해 자정을 넘겨 이번 세션(260710_1144)으로 이어짐. ERR-051 RunLevel=Limited 실증(100% 재현)과 INC-028 등록(watchdog 감시공백 3시간12분)을 시작으로, watchdog을 감시하기 위해 신규 추가한 heartbeat_monitor.py 자신도 Task Scheduler `WakeToRun=False`로 인해 Modern Standby 중 71회(5시간47분) 미실행됐음을 확인(ERR-053/FP-040). INC-028의 1차 다운(20:09:40) 원인을 실제 OS shutdown으로 확정(Note 3), 250723 참조 활성 Task 2건을 발견해 비활성화(ERR-052/FP-039/INC-029), watchdog/heartbeat_monitor의 NSSM 서비스 전환 검토를 위해 AdsPower Local API의 Session 0(S4U) 응답성을 신규 문서 `docs/PENDING_INVESTIGATIONS.md`(PENDING-A)로 실증(SUCCESS), `CURRENT_RUNTIME_CONTEXT.md` 260710 갱신, 증거보전용 진단 Task 3종(TestA/B/D) Disable 처리까지 완료. 세션 중 절차 위반(read-only 조사 승인 범위를 넘어 문서기록/commit까지 자동 실행)이 1건 발생해 CLAUDE.md에 "승인 범위 명시 원칙"과 "단계별 Bookending 원칙" 2개 governance 규칙을 신규 등록.

### 커밋 목록
**이전 세션(260709_2200)에서 시작, 자정 넘겨 이번 세션(260710_1144)로 이어짐:**
1. `144bd47` — ERR-051 후속: RunLevel=Limited 실증 100% 재현, FP-038 등록
2. `70a771f` — INC-028 등록: watchdog 감시공백 3시간12분 + 파이프라인 다운/재기동
3. `fe37ed4` — ERR-052/FP-039/INC-029: 250723 참조 활성 Task 2건 발견 및 비활성화
4. `b2aa30d` — heartbeat_monitor.py 신규: watchdog.ps1과 독립된 heartbeat 정지 감지
5. `b1b3933` — README에 heartbeat_monitor.py 실행법/의존성 기록
6. `fdd1333` — ERR-047/050 INC-028: 절전모드 상관관계 조사, 1차/2차 다운 메커니즘 분리
7. `e8583ba` — ERR-049 증거 파일 정식 편입 + 스크래치 파일 gitignore 정리

**이번 세션(260710_1144)에서 진행:**
8. `d49ab61` — ERR-053/FP-040: heartbeat_monitor.py WakeToRun=False 근본원인 확정
9. `3ab2e49` — CLAUDE.md 승인 범위 명시 원칙 추가
10. `422f9bd` — INC-028 1차 다운(20:09:40) 원인 확정: 실제 OS shutdown
11. `b89e213` — PENDING_INVESTIGATIONS.md 신규: PENDING-A AdsPower Session 0 실증 SUCCESS
12. `e09fae5` — CLAUDE.md 단계별 Bookending 원칙 추가
13. `7472cf4` — CURRENT_RUNTIME_CONTEXT.md 260710 갱신
14. `729dc88` — TestA/B/D Disable 처리 + ERR-051/FP-038 문서반영 + 스크래치파일 gitignore

### 근본원인 상태
- ERR-051: Task Scheduler launch-only 실패는 100% 결정론적이 아니라 비결정적 패턴(TestB가 트리거 0개 상태에서 00:44:33 자연 성공)으로 재확인 — 근본원인 여전히 UNKNOWN
- ERR-053/FP-040: heartbeat_monitor.py의 절전 취약성 메커니즘은 확정(WakeToRun=False). WakeToRun=True로 변경 적용했으나 실제 절전 구간 재현 검증은 다음 세션 대기(PENDING)
- INC-028 1차 다운(20:09:40): 실제 OS shutdown으로 확정. 단 "누가/무엇이 종료를 트리거했는지"는 여전히 Hypothesis(사람의 조작 가능성, 확정 아님)
- watchdog.ps1 자체의 근본 메커니즘(ERR-047 핵심 증상: 재부팅 후 무재실행)은 여전히 UNKNOWN — 이번 구간에서 해소되지 않음

### 문서화
- `docs/ERROR_DATABASE.md` — ERR-052, ERR-053 신규 등록 + ERR-047 Note 5(1차 다운 원인 확정) + ERR-051 Note(TestA/B/D 비결정적 성공 + Disable 처리)
- `docs/FAILURE_PATTERN.md` — FP-039, FP-040 신규 등록 + FP-038 Note(비결정적 launch 패턴)
- `docs/INCIDENT_TIMELINE.md` — INC-029 신규 등록 + INC-028 Note 2/3
- `docs/PENDING_INVESTIGATIONS.md` — 신규 생성, PENDING-A 등록(결론남)
- `docs/CURRENT_RUNTIME_CONTEXT.md` — 260710 갱신(260706~260709 구간은 미반영 명시)
- `docs/VALIDATION_STATUS.md` — inc028_1st_shutdown_root_cause_confirmed / heartbeat_wake_to_run_applied(PARTIAL) / pending_a_session0_adspower_verified / testabd_diagnostic_tasks_disabled 4건 추가(별도 승인 대기)
- `CLAUDE.md` — 승인 범위 명시 원칙, 단계별 Bookending 원칙 2개 신규 등록

### 다음 세션 승계
- heartbeat_monitor.py `WakeToRun=True` 적용 후 실제 Modern Standby 구간 1~2회로 실증 검증 필요
- watchdog.ps1 자체의 재부팅 후 무재실행(ERR-047 핵심 증상) 및 1차다운 메커니즘 여전히 UNKNOWN — 별도 조사 필요
- PENDING-A(NSSM/서비스 전환) 최종 결정 — 사용자 승인 필요
- 260706~260709 구간(ERR-048/050/051, INC-023/025/026/028, quality gate 재설계 등)은 CURRENT_RUNTIME_CONTEXT.md에 아직 backfill 안 됨 — 별도 작업 권장(이번 세션에서 의도적으로 범위 제외)
- `SNS_WatchdogAB_TestA/TestB/TestD`는 Disable(State=Disabled) 상태로 유지 — 완전 삭제 여부는 미결정

commit: 위 14개 전부 이미 각각 개별 커밋됨(`144bd47`~`729dc88`) — 본 MERGE_JOURNAL 항목 자체는 이번에 별도 커밋 필요
push: 미실행 — commit 후 별도 승인 필요

---

## [260710_1850] SNS_Watchdog_AutoStart WakeToRun 적용 + ERR-054/FP-040 Note/VALIDATION_STATUS 문서화

### 요약
PENDING-A 조사 과정에서 `SNS_Watchdog_AutoStart` Task도 `WakeToRun: False`(FP-040과 동일 클래스 취약점)로 등록되어 있음을 발견. 관리자 권한 PowerShell로 `WakeToRun=True` 변경 적용, before/after XML·taskinfo diff로 다른 필드 변경 없음과 예약 인스턴스 영향 없음을 raw로 실증 확인 후 ERR-054 신규 등록.

### 실행 절차
1. 비관리자 권한 세션에서 `Set-ScheduledTask` 1차 시도 → `Access is denied`(0x80070005) 확인, 변경 미반영 재확인
2. 사용자가 관리자 권한 PowerShell에서 직접 3~7단계 재실행
3. `Export-ScheduledTask`(before/after) + `Compare-Object` XML diff → `WakeToRun` 라인 1개 외 변경 없음 확인
4. `Get-ScheduledTaskInfo`(before/after) diff → `LastRunTime`/`LastTaskResult` 완전 동일 확인
5. 최종 `State: Ready` 유지, `WakeToRun: True` 반영 확인

### 문서화
- `docs/ERROR_DATABASE.md` — ERR-054 신규 등록
- `docs/FAILURE_PATTERN.md` — FP-040 Note 추가(watchdog Task도 동일 클래스 취약점 확인)
- `docs/VALIDATION_STATUS.md` — `watchdog_wakeup_applied_260710` 신규 행 추가(PASS, 설정 적용+무결성 확인 범위로 한정 표기)

### 다음 세션 승계
- `SNS_Watchdog_AutoStart`의 `WakeToRun=True` 적용 후 실제 Modern Standby 재현 구간에서의 효과는 검증되지 않음(애초에 반복 트리거 구조가 아니라 검증 대상 여부 자체가 불명확 — 다음 세션에서 검증 필요성 판단 권장)
- PENDING-A(NSSM 서비스 전환) 최종 결정 — 여전히 사용자 승인 대기 중

commit: `1966891` (ERR-054/FP-040 Note/VALIDATION_STATUS 3개 파일)
push: 미실행 — commit 후 별도 승인 필요

### 후반부 추가 작업 (260711 새벽)

**1) backup(14) 부분 이상 → backup(15) 재생성**
backup(14)(260710_2332, 9.14MB)이 backup(13)(172MB) 대비 비정상적으로 작음을 사용자가 파일탐색기 비교로 발견. 생성 당시 launcher(중복 2개)/dashboard(2개)/n8n(1개)이 db/log 파일을 점유한 상태로 압축을 시도했던 것이 원인으로 추정(확정 아님, ERR-055 참조). 전체 프로세스 정지(n8n은 관리자 권한 필요) 후 backup(15)(174,715KB) 재생성, backup(13)과 동일 정상범위 확인 + sha256 해시 생성 완료. backup(14).zip은 삭제하지 않고 보존.

**2) n8n(PID 10248) 미승인 가동 발견 (ERR-056 등록)**
MASTERTREE_CONTRACT.md 기준 설계만 완료(DESIGN_COMPLETE)·execution_owner 미구현 상태인 n8n이 `:5678`에서 LISTENING 중임을 backup 작업 중 발견. 가동 원인 UNKNOWN, 사용자 확인 결과 우선순위 낮음("급하지 않고 진행 중이던 작업 없음")으로 추가조사는 보류하되, ERR-052와 동일 유형(승인 안 된 컴포넌트 활성 상태 발견)이라 기록은 생략하지 않고 ERR-056으로 등록. 이번 세션에서는 재기동 목록에서 의도적으로 제외, 관리자 권한으로 최종 정지 완료.

**3) launcher/dashboard 4개 프로세스 — 중복 아님, 부모-자식 정상 구조로 재확인 (FP-041 등록)**
프로세스 재기동 후 python.exe 4개(38192→16548, 36064→39148)가 발견돼 최초엔 ERR-048/FP-036류 중복으로 의심했으나, StartTime(00:18:20~21 거의 동시)·ParentProcessId 체인·포트 소유(:5000/:8501 각각 단일) 대조 결과 `.venv` python이 시스템 python을 자식으로 재실행하는 정상 구조로 확인, 진짜 중복 아님으로 정정. 이번 대화 내에서도 동일한 "중복→정정" 왕복이 발생해 시간 낭비가 재현된 점을 근거로 FP-041(동일 스크립트 다중 PID 오판 방지)로 신규 등록.

commit: `9c9cf6a` (ERR-055/ERR-056/FP-041/VALIDATION_STATUS 반영)
push: 미실행 — commit 후 별도 승인 필요

## [260711_오전] 재부팅 후 자동화 재개 + NSSM/Task 이중 watchdog 발견·해소

### 배경
전날 노트북 종료로 자동화 전체 중단, 260711 재기동 세션. Session Start Rule 확인 결과 `SNS_Watchdog_AutoStart` Task가 재부팅 시 실제로 자동 발동해 Flask/Streamlit/ngrok/launcher를 복구한 것을 확인(ERR-047이 지적하던 "재부팅 후 무재실행" 증상이 이번엔 재현되지 않음 — 단 1회 관측, 근본 해소 확정 아님). AdsPower가 꺼져 있어 FB 크롤링이 전량 실패했으나 사용자가 직접 재기동, `local.adspower.net:50325` 연결 정상화 확인.

### 1) 원격 예약 작업으로 FB 크롤링 정상화 검증
`fb-crawl-check-260711-1142`(scheduled-tasks MCP) 1회성 작업 등록 — 이 과정에서 이 시스템의 실제 OS 타임존이 UTC+7이고 로그의 "KST" 표기는 라벨일 뿐임을 발견, fireAt을 최초 요청(KST+09:00 가정)에서 실제 시스템 로컬 기준으로 정정.

### 2) `.claude/settings.json` 권한 자동화 (fewer-permission-prompts 스킬)
세션 transcript 31개 스캔 → PowerShell 도구 호출이 압도적 다수(1212회)임을 확인, 읽기 전용 cmdlet(Get-Content/Get-Process/Get-ScheduledTask 등) 20개 패턴을 프로젝트 공용 `.claude/settings.json`에 신규 추가. `git add/commit/push`, 프로세스 제어(`Stop-Process`/`Start-Process` 등), 인터프리터(`python`/`powershell` 자체)는 의도적으로 제외 — 사용자가 "상태 변경 행동은 항상 먼저 물어볼 것"을 명시적으로 재확인.

### 3) ERR-057 | NSSM 서비스 ↔ 구 Task Scheduler 이중 watchdog 발견 및 해소
watchdog.log에 시작 배너가 09:07:02/09:07:58 두 번 기록된 것을 단서로 조사 — PENDING-A(260710 결론남) 전환에서 NSSM 서비스(`SNS_Watchdog`) 설치까지는 이미 완료돼 있었으나, 구 Task(`SNS_Watchdog_AutoStart`) 비활성화(Phase 3)가 누락된 채 방치되어 재부팅마다 두 메커니즘이 watchdog.ps1을 동시 실행 중이었음을 프로세스 부모-자식 체인으로 확인. 사용자가 관리자 PowerShell에서 `Disable-ScheduledTask` + `Stop-Process -Force`(PID 27664/28548) 실행 → 재조회로 완전 정리 확인, NSSM 서비스 단독 운영 전환. Flask/Streamlit/ngrok 포트는 작업 전 구간 영향 없이 유지.

이전 세션 핸드오프 메모("NSSM Phase 2→3 경계, 아직 시작 안 함")가 실제 시스템 상태(이미 절반 진행됨)와 어긋나 있었던 STALE STATE 사례로, FP-042(신규)로 별도 등록.

### 문서화
- `docs/ERROR_DATABASE.md` — ERR-057 신규 등록
- `docs/FAILURE_PATTERN.md` — FP-042 신규 등록
- `docs/INCIDENT_TIMELINE.md` — INC-030 신규 등록
- `docs/VALIDATION_STATUS.md` — `nssm_dual_watchdog_resolved_260711` 신규 행 추가(PASS)

### 다음 세션 승계
- n8n(PID 10248 등)은 여전히 의도적 정지 상태 유지 — watchdog.ps1이 계속 재시작을 시도하며 알림을 발생시키는 구조는 그대로 남아 있음(이번 세션에서 코드 수정 안 함, 필요 시 watchdog.ps1의 n8n 체크 제외 여부 별도 검토)
- Claude Desktop "원격 제어 연결 끊김" 이슈는 저장소 문서에 근거 없음 — 사용자에게 현재도 재현되는지 확인 필요(이번 세션에서는 다루지 않음)
- ERR-047(재부팅 후 무재실행) 근본 해소는 이번 1회 관측만으로 확정 불가, 계속 관찰 필요

commit: `7765011` (ERR-057/FP-042/INC-030/VALIDATION_STATUS/MERGE_JOURNAL)
push: 완료 (`ef0aca3..7765011`, 사용자 승인 후 실행)

### 후속 작업 — 항목 1/2 순차 진행 (260711 오전, 계속)

**항목 1) Claude Desktop "원격 제어 연결 끊김"** — 사용자 확인 결과 현재 재현 안 됨("지금정상"), 별도 조치 없이 종결.

**항목 2) NSSM 크래시 재시작 실증 (PENDING-A 잔여 트랙)**
관리자 권한으로 NSSM 관리 watchdog.ps1(PID 13008)을 `Stop-Process -Force`로 강제 종료(11:54:58) → NSSM이 `AppRestartDelay=60000ms` 설정대로 자동 재기동(`watchdog.log` 새 시작 배너 11:56:35, 약 97초 후) → 재기동된 watchdog.ps1이 자체 헬스체크로 Streamlit까지 정상화(PID 18048→31652) → Flask(`/health` HTTP 200)/Streamlit/ngrok/NSSM 서비스 전부 수동 개입 없이 정상 복구 확인 — PASS. 새 ERR/FP/INC 등록 없음(이상 없는 정상 검증 결과이므로 `docs/PENDING_INVESTIGATIONS.md` PENDING-A에 Note 추가 + `docs/VALIDATION_STATUS.md`에 `nssm_crash_restart_verified_260711` 행 추가로 기록).

**잔여:** 재부팅 실증(실제 OS reboot 후 NSSM 서비스 단독 정상 기동 확인)은 아직 미실시 — 사용자 편한 시점에 별도 진행.

### 문서화
- `docs/PENDING_INVESTIGATIONS.md` — PENDING-A에 260711 Note 추가(크래시 재시작 실증 결과)
- `docs/VALIDATION_STATUS.md` — `nssm_crash_restart_verified_260711` 신규 행 추가(PASS)

### 다음 세션 승계
- NSSM 재부팅 실증만 남음(Phase 2→3 나머지 트랙)
- n8n(PID 10248 등) 반복 실패 알림은 여전히 그대로(watchdog.log 기준 11:55:27 시점 "연속 183회 실패" 누적 중) — 의도적 정지 상태 유지, 코드 수정 안 함

commit: `62cea04`
push: 완료 (`7765011..62cea04`)

### 재부팅 실증 준비 (260711 12:00) — 다음 세션 시작 시 확인 필수

**Baseline (재부팅 직전, 12:00:37):**
- NSSM 서비스 `SNS_Watchdog`: Running / StartMode=Auto
- 구 예약작업 `SNS_Watchdog_AutoStart`: `Scheduled Task State: Disabled` 확인됨(ERR-057에서 처리)
- 크래시 재시작 실증은 같은 세션에서 이미 PASS 확인(위 항목 참조)

**다음 세션(재부팅 후)에서 확인할 것:**
1. `Get-Service SNS_Watchdog` → `Running` 이어야 함(수동 개입 없이 자동 기동)
2. `logs/watchdog.log` tail — `===== watchdog 시작 =====` 배너가 **1번만** 찍혀야 정상(2번 찍히면 구 Task가 다시 살아난 것 — 이 경우 `schtasks /Query /TN "SNS_Watchdog_AutoStart" /V`로 재확인)
3. Flask(:5000 `/health`)/Streamlit(:8501)/ngrok(:4040) 정상 LISTENING 여부
4. 확인 결과를 PENDING-A(`docs/PENDING_INVESTIGATIONS.md`)에 최종 Note로 추가 — PASS 시 PENDING-A 완전 종결, 실패 시 새 ERR 등록

commit: `4ff0b21`
push: 완료 (`62cea04..4ff0b21`)

### 재부팅 실증 결과 + ngrok 신규 결함 발견·해결 (260711 12:09~12:35)

**1) 재부팅 실증 — PASS, PENDING-A 완전 종결**
사용자가 12:09 재부팅 완료. 확인 결과: `Get-Service SNS_Watchdog` → `Running/Automatic` 자동 기동 / `watchdog.log` 시작 배너 **1번만**(12:08:11, 오늘 첫 재부팅 09:07:02+09:07:58 2번과 대비) — 구 Task 비활성화가 재부팅을 넘어 유지됨을 실증.

**2) 신규 발견: ngrok 실행 실패 (ERR-058)**
재부팅 실증 확인 중 `:4040` 미LISTENING, watchdog.log에 `Start-Ngrok 실패: The file cannot be accessed by the system` 반복 확인. 조사 결과 2중 원인: (1) ngrok이 Microsoft Store(MSIX) 설치라 LocalSystem(비대화형) 컨텍스트에서 Execution Alias 실행 자체가 막힘, (2) 포터블 exe로 우회해도 authtoken(`ngrok.yml`)이 admin 사용자 프로필 전용이라 LocalSystem이 인증 정보를 못 찾음 — 오늘 아침엔 구 Task(admin 계정, 대화형)가 우연히 살려왔던 것이라 ERR-057 조치 전까지 드러나지 않았던 잠복 결함.

**Fix:**
- `watchdog.ps1` — `Start-Ngrok`이 PATH 탐색 대신 명시적 포터블 경로(`$NGROK_EXE = "C:\ngrok\ngrok-v3-stable-windows-amd64\ngrok.exe"`) 사용하도록 수정
- 사용자가 관리자 PowerShell에서 `ngrok.yml`을 `C:\Windows\System32\config\systemprofile\AppData\Local\ngrok\`(LocalSystem 프로필)로 복사
- `Restart-Service -Name "SNS_Watchdog" -Force` → 12:35:48 `[RECOVER] Ngrok 복구` 확인, `/api/tunnels`로 `public_url` 정상 응답, Flask/Streamlit/ngrok 전체 정상 확인

### 문서화
- `docs/ERROR_DATABASE.md` — ERR-058 신규 등록
- `docs/FAILURE_PATTERN.md` — FP-043 신규 등록(서비스 계정 전환 시 의존 도구 전수점검 필요)
- `docs/INCIDENT_TIMELINE.md` — INC-031 신규 등록(웹훅 수신 불가 추정 구간)
- `docs/PENDING_INVESTIGATIONS.md` — PENDING-A 최종 Note, 완전 종결
- `docs/VALIDATION_STATUS.md` — `nssm_reboot_proof_260711` / `ngrok_localsystem_fix_260711` 신규 행 추가(모두 PASS)

### 다음 세션 승계
- PENDING-A(NSSM 전환) 전체 트랙 완전 종결 — 더 이상 승계 항목 없음
- n8n(PID 10248 등) 반복 실패 알림은 여전히 그대로 — 의도적 정지 상태 유지, 코드 수정 안 함
- Claude Desktop "원격 제어 연결 끊김"은 사용자 확인 결과 재현 안 됨으로 종결(이전 기록 참조)

commit: `fe50fec`
push: 미실행 — 세션 종료 시 일괄 push 예정([[feedback_push_cadence]] 방식 적용)

### CURRENT_RUNTIME_CONTEXT.md 반영 (260711, 세션 마무리)

`docs/CURRENT_RUNTIME_CONTEXT.md`(맨 위 요약 문서)가 260710 상태에서 멈춰있어 오늘 세션(ERR-057/058, PENDING-A 종결 등) 미반영 상태였음 — 최종 확인 커밋을 `fe50fec`로 갱신, "현재 단계"를 NSSM 전환 완료로 업데이트, "미해결 항목"에서 PENDING-A/watchdog.ps1 절전 관련 3개 항목을 완료 처리(취소선 + 사유), heartbeat_monitor.py 절전 실증만 유일하게 남은 항목으로 유지, 파일 끝에 `[260711]` 섹션 신규 추가.

commit: `e5d3034`
push: 미실행 — 세션 종료 시 일괄 push

### 외부 감사 테이블 재평가 반영 (260711)

사용자가 제공한 외부 감사 테이블(ERR-047/050/051/INC-028 계열 다수 항목, PENDING-A 완료 이전 시점 기준)을 오늘 작업 결과와 대조해 재평가. `docs/PENDING_INVESTIGATIONS.md`에 **PENDING-B** 신규 등록(재평가 표 + 갱신된 우선순위 4개), `docs/ERROR_DATABASE.md`의 ERR-047(Note 6)/ERR-050(Note 5)에 "NSSM 전환으로 구조적 해소(Moot)" 정리 추가 — Status를 🔴 OPEN/🟡 MITIGATED에서 🟢 구조적 해소(Moot)로 변경. ERR-051 등 오늘 조치와 무관한 항목은 그대로 유지.

commit: 미실행 — 이 기록과 함께 커밋 예정
push: 미실행 — 세션 종료 시 일괄 push

---

### 학습 리뷰 그리드 — 안전 저장 파이프라인 + 영구 실행취소 + dashboard 실연결 (260712)

`Training_Review_Queue` PASS/BLOCK 리뷰 그리드(tab8 "학습 검토")를 처음부터 끝까지 Codex 다단계 검토를 거치며 완성. 각 단계마다 별도 승인("N단계 진행하자")을 받아 진행([[feedback_plan_approval_vs_execution_gate]] 원칙의 실제 적용 사례).

**신규 파일:**
- `modules/infra/review_batch.py` — `build_review_payloads()` 순수 함수(batch_ids/block_ids → PASS/BLOCK payload)
- `modules/infra/review_batch_committer.py` — `commit_batch_with_verification()`/`undo_batch_with_verification()`/`verify_only()`. 저장 실패 시 즉시 중단, 저장 후 GET 재검증, 진짜 값 불일치(`mismatched_ids`)와 확인 자체 실패(`verification_errors`, 상태코드·오류종류 보존)를 분리, 429/5xx/타임아웃만 제한적 재시도(403/404 등은 즉시 처리)
- `modules/infra/review_grid_ui.py` — dashboard.py tab8 그리드 UI를 분리(테스트 가능하게). 저장 전 payload 미리보기 자동 표시, verification_errors 시 확정 버튼 잠금, 새 배치마다 선택 상태 초기화
- `modules/infra/undo_state_store.py` — "직전 배치 실행취소" 상태를 SQLite(`db/review_undo_state.db`)에 영구 저장. prepared→committed/failed→cancelled/superseded 상태 전이, PATCH 전에 먼저 기록(SQLite 쓰기 실패 시 PATCH 시작 안 함), mark_committed/mark_failed 실패해도 화면이 안 죽고 다음 접속 시 GET-only로 자동 복구
- 테스트 5개 파일(`tests/test_review_batch*.py`, `test_undo_state_store.py`, `test_repository_exceptions.py`) — 전부 FakeRepo/임시 SQLite만 사용, 실제 Airtable 접속 없이 검증

**수정 파일:**
- `modules/infra/repository_interface.py` — `get_review_status()` 추상 메서드 추가, `RepositoryError`에 `status_code`/`retry_after_seconds`/`original_error_type` 속성 추가
- `modules/infra/airtable_repository.py` — `get_review_status()` 구현(404는 예외 아닌 None), `_raise()`가 HTTP 상태·Retry-After 헤더 전달
- `dashboard.py` — tab8이 `render_review_grid(_repo, undo_store=UndoStateStore(...))`로 연결(db 폴더 존재 확인 후)

**사고 및 정정 (ERR-059/FP-044/INC-032):**
실제 운영 50건 배치 확정 시 저장은 100% 성공했으나 GET 재검증 단계가 모든 예외를 "값 불일치"로 오탐 표시 — 원인은 예외 은폐(`_safe_get_status`가 429/403/타임아웃 구분 없이 전부 None 처리). 최초 제기된 "속도 제한" 가설은 실제 PATCH 간격 로그(82초/50건, 1.4~1.6초 간격)로 기각. 근본 수정 후 Codex 재검토에서 (1) 실제 404 계약(None 반환)을 mismatched_ids로 잘못 분류, (2) GET 자체 실패도 즉시 failed 확정, (3) 복구 미해결 시에도 새 작업 진행 가능 등 3차례 추가 결함 발견·수정. 해당 50건 배치는 원본 선택 기록이 브라우저 새로고침으로 유실돼 완전 재검증 불가 — 확보 가능한 최선의 증거(47/50건 직접 재조회 확인)로 **조건부 종결**.

**실제 운영 검증:** 신규 20건 배치를 수정된 파이프라인으로 실제 처리 — PATCH 20회 + GET 재검증, `PENDING 20→0 / PASS 39→40 / BLOCK 133→152` 정확히 일치, SQLite에 `committed` 상태로 payload 전체(19 BLOCK/1 PASS) 정확히 기록, 새로고침 후 실행취소 버튼 정상 복원까지 확인 — **PASS**.

**부수 발견:** 오래 떠 있던 Streamlit 프로세스(NSSM, 2026-07-11 12:30 기동)가 구버전 `review_grid_ui.py`를 메모리에 캐시하고 있어 `undo_store` 연결 직후 `TypeError` 발생 — 관리자 권한으로 프로세스 재시작(watchdog 자동 복구, PID 22856→32636) 후 해소. 이후 화면에 나타난 "선택 건수 미갱신처럼 보이는" 현상은 AppTest 재현으로 코드 정상 확인 — 실제로는 서버 응답 시차였음(새로고침으로 해소).

**함께 커밋되는 이전 세션 미커밋분 (이번 세션 승인 후 함께 정리):**
- `.env.example`/`.gitignore`/`requirements.txt` — Naver 커넥터 관련 env 자리표시자, imagehash 의존성, training_snapshots gitignore (이전 세션 Phase 0 승인분)
- `modules/sns/facebook_crawler.py` — `save_to_training_queue`/`run_for_training_photos` 등 학습용 FB 그룹 크롤러 함수 (이전 세션에 실제 192건 수집까지 검증 완료된 승인분)
- `modules/infra/repository_interface.py`/`airtable_repository.py`의 Phase 0 스캐폴딩(`TrainingCandidate`, `insert_training_candidate` 등) — 오늘 수정분과 같은 파일에 섞여 있어 분리 불가, 이전 세션에 이미 승인된 내용
- `modules/crawlers/naver_search_connector.py` — robots.txt 위반(AI 학습/RAG 명시적 금지)으로 폐기 결정된 코드. 삭제하지 않고 그대로 커밋(참고용, 실행 금지) — 삭제 여부는 별도 결정 사항

**문서화:** `docs/ERROR_DATABASE.md`(ERR-059) / `docs/FAILURE_PATTERN.md`(FP-044) / `docs/INCIDENT_TIMELINE.md`(INC-032) / `docs/VALIDATION_STATUS.md`(2행) / `docs/VALIDATION_EVIDENCE_training_review_3B_260712.md`(신규, 3B 실제 Airtable 실증 원문 증거) 전부 260712 세션 중 작성.

commit: `9307403`
push: 완료 (당시 "commit: 미실행" 표기가 실제 커밋·push 후 갱신 안 된 채 남아있었음 — 아래 260712 후속 세션에서 뒤늦게 정정)

---

### NSSM 서비스(SNS_Watchdog) 본체 크래시 + 실행파일 소실 → 완전 재생성 (260712, 학습 리뷰 세션 이후)

**발견 경위:** 학습 리뷰/크롤링 세션 종료 후 watchdog 상태 재확인 중 `Get-Service SNS_Watchdog`가 `Stopped`인데 `watchdog.log`는 계속 heartbeat를 남기는 모순 발견.

**원인 조사:** `Get-WinEvent`(Service Control Manager)로 `2026-07-11 23:08:47`에 서비스 본체가 예기치 않게 종료(Event 7034)된 것 확인. 조사 결과 등록된 `nssm.exe` 실행파일 자체가 `C:\ProgramData\chocolatey\lib\NSSM\tools\`에서 사라져있었고, 파일을 재설치(`choco install nssm -y --force`)해도 서비스 레지스트리 등록 자체가 손상돼(`nssm get` 조회조차 실패) 시작이 안 되는 상태였음. git 커밋·프로젝트 파일 변경·chocolatey.log·Windows Defender 탐지 로그를 전부 대조했으나 크래시 시각과 인과관계가 있는 흔적을 찾지 못함 — **원인 UNKNOWN으로 확정 기록**(추정하지 않음).

**해소:** 고아 상태로 남아있던 이전 watchdog.ps1 인스턴스 3세대(PID 23828/27220/1924) 정리 → `nssm remove`+`nssm install`로 서비스 완전 재생성(기존과 동일한 Application/AppParameters/AppExit/AppRestartDelay 설정 복원, `AppDirectory` 명시 추가) → `sc.exe failure`로 **서비스 본체 자체**의 크래시 복구 옵션 신규 추가(기존엔 NSSM `AppExit`가 자식 프로세스 크래시만 커버, 서비스 본체 크래시엔 무방비였던 것이 이번 사고의 직접 원인, FP-045). 검증: `Get-Service` Running/Automatic, `sc.exe qfailure` SUCCESS, watchdog.log 새 시작 배너, Flask/Streamlit/ngrok 동일 PID로 무중단 유지 — PASS.

**문서화:** `docs/ERROR_DATABASE.md`(ERR-060) / `docs/FAILURE_PATTERN.md`(FP-045) / `docs/INCIDENT_TIMELINE.md`(INC-033, 약 24시간 무감독 구간) / `docs/VALIDATION_STATUS.md`(1행)

**다음 세션 승계:** 없음 — 이번 건은 완결. 단, "왜 nssm.exe가 사라졌는지"는 영구 UNKNOWN으로 남으므로 향후 유사 증상(서비스 Stopped인데 자식은 살아있음) 재발 시 이 기록(ERR-060/FP-045) 우선 참조.

commit: 미실행 — 이 기록과 함께 커밋 예정
push: 미실행 — 세션 종료 시 일괄 push([[feedback_push_cadence]] 방식 적용)

---
