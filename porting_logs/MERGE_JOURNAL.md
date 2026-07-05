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

