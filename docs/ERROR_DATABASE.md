# ERROR_DATABASE.md
> Generated: 2026-05-16 | Status: ACTIVE | Version: v1.1
> Scope: SNS_24AutoProject

---

## ERR-001 | Import Drift
**Type:** ModuleNotFoundError
**Raw:** `ModuleNotFoundError: No module named 'modules.xxx'`
**Root Cause:** Wrong runtime path / sys.path 오염
**Fix:** absolute path 고정 / sys.path.insert 제거
**Prevention:** FP-006 준수 / absolute import only

---

## ERR-002 | DB Schema Mismatch
**Type:** OperationalError
**Raw:** `no column named post_id`
**Root Cause:** schema 변경 후 migration 미적용
**Fix:** ALTER TABLE / init_db 재실행
**Prevention:** schema_governance.md 기준 / migration forbidden rule

---

## ERR-003 | Instagram UI Failure
**Type:** TimeoutException / NoSuchElementException
**Raw:** `Create button not found` / `nav wait timeout`
**Root Cause:** UI state 미검증 / popup state mismatch
**Fix:** state validation 먼저 / sequential load 적용
**Prevention:** FP-008 준수 / nav existence check 필수

---

## ERR-004 | OAuthException 190
**Type:** Token Error
**Raw:** `OAuthException: Error validating access token: Session has expired`
**Root Cause:** token invalid / session 만료
**Fix:** 신규 token 발급
**Prevention:** token lifecycle 관리 / expiry 사전 체크

---

## ERR-005 | Hallucinated Artifact
**Type:** Reference Error
**Raw:** 파일 없음 / import 실패 (선언만 존재)
**Root Cause:** AI 텍스트 출력 = 실제 파일 생성 오인
**Fix:** filesystem verification / 실제 파일 생성
**Prevention:** Evidence-based operation / Get-ChildItem 필수

---

## ERR-006 | AdsPower Attach Failure
**Type:** ConnectionError / CDP Error
**Raw:** `Failed to connect to AdsPower profile`
**Root Cause:** profile 미실행 / debug port 미개방
**Fix:** AdsPower profile Open 후 재시도
**Prevention:** attach 전 profile status 확인 필수

---

## ERR-007 | Selenium Stale Element
**Type:** StaleElementReferenceException
**Raw:** `stale element reference: element is not attached to the page document`
**Root Cause:** DOM 변경 후 element 재참조
**Fix:** element 재탐색 / explicit wait 추가
**Prevention:** find_element 재호출 구조 / retry wrapper

---

## ERR-008 | Airtable Rate Limit
**Type:** HTTPError 429
**Raw:** `429 Too Many Requests`
**Root Cause:** API 호출 과다
**Fix:** retry with backoff
**Prevention:** rate limit 관리 / 호출 간격 조절

---

## ERR-009 | Duplicate Scheduler Trigger
**Type:** Logic Error
**Raw:** 동일 작업 중복 실행
**Root Cause:** scheduler lock 없음
**Fix:** lock 파일 / DB status 체크
**Prevention:** scheduler duplicate 0 유지 정책

---

## ERR-010 | Retry Queue Dead
**Type:** Operational Error
**Raw:** retry_queue에 dead task 누적
**Root Cause:** max_retry 초과 / fallback 없음
**Fix:** dead task 수동 확인 / 원인 제거 후 재시작
**Prevention:** retry queue dead 0 유지 모니터링

---

## ERR-011 | .fixed.py Runtime Conflict
**Type:** Import Conflict
**Raw:** 수정했는데 적용 안 됨
**Root Cause:** .fixed.py와 원본 동시 존재
**Fix:** .fixed.py 제거 / 원본만 유지
**Prevention:** FP-007 준수 / .fixed.py 생성 금지

---

## ERR-012 | Partial E2E Success Illusion
**Type:** Validation Error
**Raw:** 단계별 PASS + 실제 E2E 미완성
**Root Cause:** E2E 전체 검증 없이 단계별 완료 선언
**Fix:** E2E flow 전체 재검증
**Prevention:** FP-012 준수 / production_verified 기준 엄격 적용

---

## ERR-013 | Instagram Aspect Ratio Rejection
**Type:** Graph API Error 36003
**Raw:** `The aspect ratio is not supported`
**Root Cause:** FB 수집 이미지 비율이 Instagram 허용 범위(4:5 ~ 1.91:1) 벗어남
**Fix:** Pillow center-crop 전처리 + imgbb 영구 URL 업로드 방식 적용 (`_preprocess_image()` in instagram_uploader.py)
**Prevention:** `save_to_airtable()` 단계 비율 사전 검증
**Status:** ✅ RESOLVED (2026-05-17)
**Evidence:** `ig_media_id=18116524126780958` 실제 업로드 성공 확인 / INC-010

---

## ERR-014 | Media ID Expiry
**Type:** Graph API Error 9007 / 22070
**Raw:** `Media ID is not available`
**Root Cause:** 미디어 컨테이너 생성 후 publish 시간 초과
**Fix:** Step1→Step2 즉시 연결 / 대기 최소화
**Prevention:** 10초 이내 publish 호출

---

## ERR-015 | False Runtime Targeting
**Type:** Dead Code Debugging
**Raw:** 수정했는데 반영 안 됨
**Root Cause:** `instagram_uploader.py` 수정했으나 실제 runtime은 `main.py`
**Fix:** 실제 entry point 확인 후 수정
**Prevention:** 수정 전 import chain 추적 필수

---

## ERR-016 | Launcher Not Running
**Type:** Operational Error
**Raw:** 2일간 크롤링/업로드 미동작
**Root Cause:** `main.py` 프로세스 미실행
**Fix:** `python launcher/main.py` 재실행
**Prevention:** 프로세스 상태 모니터링 / 자동 재시작 watchdog

---

## ERR-017 | Token Expiry Silent Fail (No Slack)
**Type:** OAuthException 190 / Silent Alert Gap
**Raw:** `OAuthException 190: Invalid OAuth access token`
**Root Cause:** `_job_insta_upload` 내부 `except`가 예외를 삼켜 `@handle_errors(notify_fn=_slack)` 미도달
**Fix:** API 응답 `error.code in (190, 104)` 감지 시 `_slack` 직접 호출 후 `raise` (`launcher/main.py`)
**Status:** ✅ RESOLVED (2026-05-17)
**Evidence:** bad token 테스트 → OAuthException 190 감지 + Slack mock 호출 1회 + Airtable failed 마킹 확인 (PHASE2 #3)

---

## ERR-018 | Multi-Account Upload Race Condition (Structural)
**Type:** Concurrency / Logic Gap
**Raw:** 다계정 병렬 실행 시 동일 ready 레코드 중복 픽업 → 중복 게시 가능
**Root Cause:** ① `_job_insta_upload`에 record-level 잠금 없음 ② APScheduler `max_instances` 미설정으로 잡 중복 실행 가능
**Fix:** ① 레코드 처리 전 `post_status='uploading'` 원자적 마킹 추가 ② `max_instances=1` 설정 (`launcher/main.py`)
**Status:** ✅ RESOLVED (2026-05-17) — 1계정 운영 중 사전 수정
**Evidence:** 코드 구조 분석 / PHASE2 #4 검증

---

## ERR-019 | Posted Record Re-upload on Status Reset
**Type:** Logic Gap / Duplicate Upload
**Raw:** `post_status='posted'` 레코드를 `ready`로 수동 변경 시 재업로드 발생
**Root Cause:** `_job_insta_upload`이 `ready` 상태만 확인하고 `ig_media_id` 존재 여부 미검사
**Fix:** `uploading` 잠금 전 `ig_media_id` 존재 시 `posted` 복원 후 `continue` (`launcher/main.py`)
**Status:** ✅ RESOLVED (2026-05-17)
**Evidence:** recy3sNhxbsGelFgy ready 변경 → 330s 후 ig_media_id 유지된 채 posted 복원 확인 (PHASE2 #5)

---

## ERR-021 | Watchdog Dual Process — Flask :5000 중복 바인딩 + APScheduler 이중 실행
**Type:** Architecture Gap / Duplicate Process
**Raw:** watchdog 기동 시 `dm_receiver`(:5000)와 `launcher\main.py`(:5000)가 동시 LISTEN → APScheduler `process_due_followups` / `poll_new_comments` 매 5분 2회 실행 (27초 간격)
**Root Cause:** `watchdog.ps1`이 `Start-Flask`(dm_receiver 독립 기동)와 `Start-Launcher` 두 개를 각각 기동. `launcher\main.py` 내부(line 300)에서도 `app.run(:5000)` 실행 → :5000 이중 바인딩. dm_receiver 독립 프로세스가 `start_scheduler()` 호출 → APScheduler 중복 인스턴스 생성.
**Fix:** `watchdog.ps1`에서 `Start-Flask` 함수(line 97~103)와 Flask 감시 블록(line 140~156) 주석 처리. launcher\main.py가 Flask를 직접 관리하도록 위임.
**Status:** ✅ RESOLVED (2026-05-27)
**Evidence:** app.log 22:00:34 / 22:05:34 `process_due_followups` 1회/5분 확인. :5000 단일 LISTEN (PID 23272) 확인. PSParser 문법 검증 PASS.

---

## ERR-022 | PowerShell 한글 인코딩 깨짐 (chcp 65001 미설정)
**Type:** Encoding Error
**Raw:** 한글 출력이 `???` 또는 깨진 문자로 표시됨
**Root Cause:** PowerShell 기본 코드페이지(CP949/EUC-KR)에서 UTF-8 스트림 출력 시 인코딩 불일치
**Fix:** `chcp 65001` 실행 후 스크립트 재시작 / 또는 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`
**Prevention:** FP-018 준수 — PowerShell 터미널에서 한글 포함 Python 스크립트 실행 전 chcp 65001 필수
**Date:** 2026-05-28

---

## ERR-023 | pyngrok ModuleNotFoundError
**Type:** ModuleNotFoundError
**Raw:** `ModuleNotFoundError: No module named 'pyngrok'`
**Root Cause:** venv에 pyngrok 미설치 상태에서 launcher/main.py 실행
**Fix:** `.venv\Scripts\pip install pyngrok`
**Prevention:** requirements.txt 확인 후 venv activate → pip install -r requirements.txt 선행 실행
**Date:** 2026-05-28

---

## ERR-024 | watchdog 미기동 → Flask :5000 미리스닝
**Type:** Operational Error
**Raw:** `curl http://localhost:5000` 연결 거부 / webhook 수신 불가
**Root Cause:** watchdog.ps1 미실행 상태에서 launcher/main.py도 미기동 → Flask 프로세스 없음
**Fix:** `python launcher/main.py` 직접 실행 또는 `.\watchdog.ps1` 재기동
**Prevention:** FP-019 준수 — 세션 시작 시 Flask :5000 LISTENING 여부 확인 필수
**Date:** 2026-05-28

---

## ERR-025 | _rule.reason AttributeError on Falsy Rule Object
**Type:** AttributeError
**Raw:** `AttributeError: 'NoneType' object has no attribute 'reason'` (또는 False/falsy 객체)
**Root Cause:** `if not _rule:` 분기 내부에서 `_rule.reason` 직접 접근 — _rule이 falsy면 속성 없음
**Fix:** `reason = getattr(_rule, "reason", "unknown")` fallback 적용
**Prevention:** falsy 판정 후 해당 객체 속성 접근 금지 — getattr + default 패턴 사용
**Status:** ✅ RESOLVED (2026-05-28)
**File:** modules/dm/dm_auto_reply.py

---

## ERR-026 | IS_AFTER Airtable Filter Bypassed — replied_at 필드 미존재
**Type:** Logic Gap / Silent Filter Bypass
**Raw:** 중복 발송 차단 가드가 존재하나 실제로 차단 안 됨
**Root Cause:** `IS_AFTER({replied_at}, cutoff)` filterByFormula 사용 — Airtable Lead_Interactions 테이블에 `replied_at` 커스텀 필드 없음 → API가 오류 없이 빈 records 반환 → 가드 항상 False
**Fix:** `IS_AFTER(CREATED_TIME(), cutoff)` 로 교체 — Airtable 내장 시스템 필드 사용
**Prevention:** filterByFormula에 커스텀 필드 사용 시 해당 필드 Airtable 존재 여부 사전 검증 필수
**Status:** ✅ RESOLVED (2026-05-28)
**File:** modules/dm/dm_auto_reply.py — _has_recent_auto_replied()

---

## ERR-020 | Watchdog Slack Silent (env var not loaded)
**Type:** Configuration Gap
**Raw:** watchdog 재시작 알림이 Slack에 미전달 — `Send-SlackAlert` 내 `$webhookUrl` 항상 null
**Root Cause:** `watchdog.ps1`이 `$env:SLACK_WEBHOOK_URL` 읽음. 그런데 해당 값은 `.env`에만 존재하고 시스템 환경변수에 미등록 → `if (-not $webhookUrl) { return }` 로 즉시 반환
**Fix:** watchdog.ps1 시작부에 `.env` 파싱 블록 추가 — `Get-Content .env | Where { $_ -match '^SLACK_WEBHOOK_URL\s*=' }` → `$env:SLACK_WEBHOOK_URL` 세팅
**Prevention:** PowerShell 스크립트에서 `.env` 값 사용 시 별도 로드 블록 필수
**Status:** ✅ RESOLVED (2026-05-17)
**Evidence:** watchdog.ps1 상단 .env 로드 블록 추가 확인

---

## ERR-027 | accounts.json 빈 배열 → crawl_urls 없음 → FB Crawler skip
**Type:** Configuration Gap
**Raw:** `[WARNING] [FB Crawler] crawl_urls 없음 — skip | account=default`
**Root Cause:** `configs/accounts.json`이 `[]` 빈 배열 → account_manager가 `.env` 단일 계정으로 폴백 → default 계정은 `crawl_urls=[]` 하드코딩 → 크롤러 전량 skip
**Fix:** `configs/accounts.json`에 account1 + crawl_urls 등록 (`https://www.facebook.com/groups/3393946167372584`)
**Prevention:** FP-022 준수 — accounts.json 배포 후 크롤러 로그에서 skip 여부 반드시 확인
**Status:** ✅ RESOLVED (2026-05-29)
**Evidence:** 19:43 / 20:13 크롤러 2회 연속 `계정 완료 | account=account1 | 3개` 확인

---

## ERR-029 | one-liner 실행 시 .env 미로드 → Airtable API_KEY 없음
**Type:** Configuration Gap
**Raw:** `[AIRTABLE] API_KEY 또는 BASE_ID 미설정`
**Root Cause:** `python -c "..."` one-liner 실행 시 `load_dotenv()` 미호출 → 환경변수 없음
**Fix:** one-liner 앞에 `from dotenv import load_dotenv; load_dotenv(override=True);` 추가
**Prevention:** 단발 실행 one-liner에는 항상 load_dotenv() 선행 호출 필수
**Status:** ✅ RESOLVED (2026-06-02)
**Evidence:** load_dotenv 추가 후 `[AIRTABLE] 저장 완료` 확인

---

## ERR-030 | raw_text 보존 위치 오류 — clean_contact_info 선처리로 원문 손실
**Type:** Logic Error
**Raw:** `original_text = text` 시점이 clean_contact_info() 통과 후 → 원문 아님
**Root Cause:** 기존 run()에서 `text = clean_contact_info(text)` 후 `save_to_airtable(text)` 호출 → save_to_airtable 내부의 `original_text = text` 는 이미 가공된 값
**Fix:** Phase 3 패치 — `raw_text = post.text` 직후 캡처, `clean_contact_info()` clone 경로 제거
**Prevention:** original_text는 반드시 post.text 직후 값. 어떤 가공도 전에 캡처
**Status:** ✅ RESOLVED (2026-06-01, b059740)

---

## ERR-037 | Clone Mode caption에 Facebook UI 잔여물 포함
**Type:** Data Contamination
**Raw:** caption 필드에 `우다현\n43분\n·\n[NEW ARRIVAL]...` 형태로 작성자명·경과시간·구분점이 그대로 포함됨
**Root Cause:** `generate_caption_clone()`이 `replace_contacts()`만 호출하고 Facebook UI 메타데이터(작성자명, 경과시간, ·) 제거 없이 원문을 그대로 캡션으로 사용
**Fix:** `content_filter.py`에 `clean_fb_metadata()` 추가 (경과시간 패턴 감지 → 해당 줄 및 직전 이름 줄 소급 제거), `generate_caption_clone()`에서 `replace_contacts()` 전에 호출
**Prevention:** clone 경로에서 원문 보존은 본문 내용만 대상. UI 잔여물(작성자/시간/구분점) 제거는 별도 전처리 단계로 분리
**Status:** ✅ RESOLVED (2026-06-02)

---

## ERR-031 | generate_caption() Gemini rewrite로 원문 손실
**Type:** Design Error
**Raw:** caption이 원문 요약/번역본 → 상품명/가격/조건 소실
**Root Cause:** 기존 `generate_caption(text)` 는 Gemini API 호출로 `Summarize in 2-3 sentences` 지시 → 원문 정보 손실
**Fix:** `generate_caption_clone(text)` 신규 추가 — Gemini 호출 없이 포맷 정리만
**Prevention:** Clone Mode에서 Gemini rewrite 호출 절대 금지
**Status:** ✅ RESOLVED (2026-06-01, 3ed3b45)

---

## ERR-032 | Facebook 더보기 미클릭 → 텍스트 63자 truncated → 키워드 미매칭
**Type:** Data Capture Gap
**Raw:** `text_len: 63` → `passes: False` → 필터 제외 (실제 전문 581자)
**Root Cause:** Selenium `post.text`는 현재 DOM에 렌더된 텍스트만 반환. Facebook 더보기 클릭 전 truncated 상태
**Fix:** `expand_see_more(post, driver)` 추가 — post.text 읽기 직전 클릭
**Prevention:** Clone Mode에서 더보기 클릭은 원문 보존 필수 보정
**Status:** ✅ RESOLVED (2026-06-01, deec24c)

---

## ERR-033 | 베트남어 게시글 → detect_and_translate() 빈값 → 필터 제외 (정상 동작)
**Type:** Expected Behavior (버그 아님)
**Raw:** `filter_text: (빈값)` / `POST N 필터 제외` — 베트남어 게시글
**Root Cause:** `_has_excluded_language()` 가 베트남어 특수문자 감지 → `""` 반환 → 정상 차단
**Fix:** 없음 — 설계대로 동작
**Prevention:** 필터 제외 시 원문 텍스트 언어 확인 후 판정. 베트남어/중국어는 정상 차단
**Status:** ✅ CONFIRMED (2026-06-01, 설계 정상)

---

## ERR-034 | comment_poller 미실행 → 댓글 알림 미발송
**Type:** Operational Gap
**Raw:** IG 댓글 수신 후 Telegram 알림 없음
**Root Cause:** `poll_new_comments()`는 `core/run_engine.py` 스케줄러에 등록됨. launcher 미실행 시 polling loop 없음
**Fix:** launcher 기동으로 즉시 활성화
**Prevention:** launcher 실행 상태 주기적 확인. watchdog.ps1 SNS_Watchdog_AutoStart 등록 확인
**Status:** ⏸ PENDING (launcher 기동 시 자동 해소)

---

## ERR-028 | Airtable caption 필드 없음 → 422 UNKNOWN_FIELD_NAME
**Type:** Airtable Schema Mismatch
**Raw:** `422 Client Error: Unprocessable Entity — UNKNOWN_FIELD_NAME: "caption"`
**Root Cause:** `facebook_crawler.py` `save_to_airtable()`이 `"caption"` 필드로 저장 시도 — Airtable `Instagram_Posts` 테이블에 해당 필드 미존재
**Fix (1차):** Airtable UI에서 `Instagram_Posts` 테이블에 `caption` (Long text / multilineText) 필드 수동 추가
**Fix (2차, 260612):** Airtable Metadata API로 프로그래매틱 추가 → field_id: fldcxTzLzYCzD9aYe
**Prevention:** UI 수동 추가 대신 API 추가 사용 (재현 가능). MASTERTREE_CONTRACT 데이터 계약 즉시 갱신. FP-028 참조.
**Status:** ✅ RESOLVED (재발 260611 → 재해소 260612)
**Evidence (2차):** Meta API 200 OK, `{'type': 'multilineText', 'id': 'fldcxTzLzYCzD9aYe', 'name': 'caption'}` 확인

## ERR-035 | PowerShell Set-Content UTF8 BOM → account_manager JSON 파싱 실패
**Type:** JSON Parse Error / Encoding Bug
**Raw:** `[AccountManager] accounts.json 파싱 실패 | Unexpected UTF-8 BOM (decode using utf-8-sig)`
**Root Cause:** `Set-Content -Encoding UTF8` 이 BOM(EF BB BF) 포함 파일 생성 → Python `json.load()` BOM 거부
**Fix:** `[System.IO.File]::WriteAllText(path, content, [System.Text.UTF8Encoding]::new($false))`
**Prevention:** FP-025 준수 — JSON/설정 파일은 반드시 BOM-free UTF-8 저장
**Status:** ✅ RESOLVED (2026-06-02, c6a30d1)
**Evidence:** BOM 제거 후 `[AccountManager] accounts.json 로드 | 1개 계정` 확인

---

## ERR-036 | facebook_crawler.py 모듈 load_dotenv 미호출 → Airtable API_KEY 미설정
**Type:** Configuration Gap / Module-level
**Raw:** `[AIRTABLE] API_KEY 또는 BASE_ID 미설정`
**Root Cause:** `modules/sns/facebook_crawler.py` 상단에 `load_dotenv()` 미호출 → 모듈 직접 import 실행 시 `.env` 미로드 → `os.getenv("AIRTABLE_API_KEY")` 빈 값 반환
**Fix:** 모듈 상단에 `from dotenv import load_dotenv; load_dotenv(override=True)` 추가
**Prevention:** 독립 실행 가능성 있는 모듈은 상단에 load_dotenv 필수. ERR-029(one-liner 수준)와 별개로 모듈 자체가 보장해야 함
**Status:** ✅ RESOLVED (2026-06-02, f5d59f2)
**Evidence:** 수정 후 `[AIRTABLE] 저장 완료` 확인 (그룹 345179878828208)

---
## ERR-038 (260603)
- 코드: 0xC000013A (3221225786)
- 발생: 작업스케줄러 SNS_Watchdog_AutoStart LastTaskResult
- 의미: 프로세스 강제종료 / ExecutionPolicy 차단
- 해결: Set-ExecutionPolicy RemoteSigned -Scope LocalMachine -Force

---

## ERR-039 | engagement_tracker 무효 ig_media_id 반복 조회
**Type:** Graph API Warning / Data Integrity
**Raw:** `[Engagement] Graph API 오류 | 17863634121631171 | Unsupported get request. Object with ID '17863634121631171' does not exist, cannot be loaded due to missing permissions`
**Root Cause:** `Instagram_Posts` 레코드 `rectwruMD3uua54sv`의 `ig_media_id` 필드에 유효하지 않은 media ID 잔존 → `engagement_tracker.py`가 `post_status=posted AND ig_media_id!=''` 필터로 30분마다 조회 → Graph API 반복 실패
**Fix:** 해당 레코드 `ig_media_id` 필드를 공백으로 PATCH → engagement_tracker 조회 대상에서 자동 제외
**Prevention:** 업로드 실패로 media_id 획득에 실패했거나 게시물이 삭제된 경우 ig_media_id 즉시 클리어. `post_status=posted`인데 ig_media_id가 비어있는 경우 → 재업로드 또는 레코드 정리.
**Status:** ✅ RESOLVED (2026-06-12)
**Evidence:** PATCH 200 OK / 다음 실행부터 해당 레코드 engagement_tracker 조회 제외
**관련:** INC-021

---

## ERR-040 | post_status Single Select 옵션 소실
**Type:** Airtable 422 INVALID_MULTIPLE_CHOICE_OPTIONS
**Raw:** `422 Client Error: INVALID_MULTIPLE_CHOICE_OPTIONS: Insufficient permissions to create new select option "ready"`
**Root Cause:** Instagram_Posts 테이블 post_status 필드에서 `ready` / `uploading` 옵션이 소실됨. 260612 caption 필드 재추가 작업 시 연관 변경으로 추정. Airtable UI에서 Single Select 필드를 재생성하면 기존 옵션이 초기화됨.
**Fix:** Airtable Meta API PATCH 시도 → 422 실패 → Records API `typecast:True`로 더미 레코드 생성 → 옵션 강제 등록 → 더미 레코드 삭제
**Prevention:** post_status 필드 수정 시 기존 옵션 목록 확인 필수. API 수정 후 즉시 옵션 목록 재확인.
**Status:** ✅ RESOLVED (2026-06-16)
**Evidence:** `['draft','scheduled','posted','failed','ready','uploading']` Meta API 응답 확인
**관련:** ERR-041

---

## ERR-041 | retry_count / last_error_msg UNKNOWN_FIELD_NAME
**Type:** Airtable 422 UNKNOWN_FIELD_NAME
**Raw:** `422 Client Error: UNKNOWN_FIELD_NAME: "retry_count"` — launcher/main.py 업로드 실패 경로
**Root Cause:** Instagram_Posts 테이블에 `retry_count` / `last_error_msg` 필드 미존재. 코드에서 해당 필드에 write를 시도하여 422 발생. 예외는 `@handle_errors(reraise=False)`에 의해 삼켜져서 "executed successfully" 로그만 남고 실제 상태는 `uploading` 고착.
**Fix:** launcher/main.py 성공 경로(L224) + 실패 경로(L237) 양쪽에서 `retry_count` / `last_error_msg` 참조 제거. 실패 에러 내용은 `logger.error`로 직접 출력.
**Prevention:** Airtable 필드 write 전 Meta API로 필드 존재 확인. 코드에 존재하지 않는 Airtable 필드명 사용 금지.
**Status:** ✅ RESOLVED (2026-06-16) — 커밋 463c350
**Evidence:** 이후 업로드 성공 → post_status=posted 정상 마킹 확인 (recw3EHD8d9uiP2FX)
**관련:** ERR-040, FP-029

---

## ERR-042 | FB CDN 동일 이미지 다중 URL → image_url_hash 중복 미탐지
**Type:** Data Quality / Airtable 중복 레코드
**Raw:** uploading 고착 28건 전부 Regine Kim 포스트 동일 이미지 — CDN 노드만 다름 (`scontent.fhan15-2`, `fdad3-8`, `fhan5-6`)
**Root Cause:** `image_url_hash = hashlib.sha256(image_url.encode())` — URL 전체를 해시 → CDN 노드가 다르면 다른 해시 → 동일 이미지도 신규로 저장. 같은 이미지가 28건 중복 저장됨.
**Fix:** `re.search(r"/(\d+_\d+(?:_\d+)*)[_.]", image_url)`로 FB 미디어 ID 추출 → 미디어 ID 기준 해시. 추출 실패 시 원본 URL 폴백.
**Prevention:** CDN URL 해시 금지. 미디어 고유 ID 기반 중복 감지 원칙. FB CDN URL 파싱 로직은 FP-029 참조.
**Status:** ✅ RESOLVED (2026-06-16) — 커밋 25c6779
**Evidence:** 3개 CDN URL → 동일 미디어 ID(709844463_2805495464410633) → 동일 해시 ✅
**관련:** FP-029, ERR-041

---

## ERR-043 | import re 누락
**Type:** NameError
**Raw:** `[FB Crawler] 크롤링 실패 | name 're' is not defined` — 그룹 1827528710833477
**Root Cause:** `facebook_crawler.py`에 `re.search()` 호출(L138) 추가 시 `import re` 추가 누락. ERR-042 수정 커밋(25c6779)에서 import 라인 미포함.
**Fix:** `facebook_crawler.py` 상단 `import re` 추가.
**Prevention:** `re`, `os`, `sys` 등 표준 라이브러리 사용 시 파일 상단 import 확인 필수. 코드 수정 후 즉시 `python -c "import facebook_crawler"` 또는 lint 검증.
**Status:** ✅ RESOLVED (2026-06-16) — 커밋 366c617
**Evidence:** 이후 크롤링 NameError 미발생 확인
**관련:** ERR-042

Cannot overwrite variable Error because it is read-only or constant.

---

## ERR-044 | pytesseract 미설치 — ImageFilter OCR 무력화
**Type:** ModuleNotFoundError (silent fallback)
**Raw:** `[ImageFilter] OCR 실패 — 통과 처리 | No module named 'pytesseract'`
**Root Cause:** `pytesseract` 패키지 미설치. `passes_image_filter()` 예외 처리에서 OCR 실패 시 `True` 반환 → 모든 이미지 통과. `_IMAGE_BLOCK_KEYWORDS`의 coslife 등 패턴이 실질적으로 작동하지 않음.
**Fix:** `CAPTION_BLOCKLIST`를 `content_filter.py`에 추가, `passes_keyword_filter()` 에서 번역된 텍스트 기준 차단 적용 (coslife, lily). OCR 없이 caption 텍스트 레벨에서 선행 차단.
**Prevention:** ImageFilter가 pytesseract 의존이면 설치 확인 필수. 혹은 OCR 실패 시 경고 + 대체 텍스트 필터 명시적 적용.
**Status:** ✅ MITIGATED (2026-06-29) — 커밋 예정 | pytesseract 미설치 자체는 미해결
**Evidence:** scheduler_err.log L33394 `No module named 'pytesseract'` 2026-06-28 05:29:14 반복 확인

---

## ERR-045 | Windows 재부팅 후 watchdog.ps1 미재기동 → 장시간 파이프라인 중단
**Type:** Infrastructure / OS-level (not application code)
**Raw:** `scheduler_err.log` 10:01:25 이후 라인 없음 (crash traceback 없음). Windows System 이벤트로그: `2026-07-01 10:02:48 [Event 109] Kernel API — Power Action Shutdown Off` (시스템 자체 재부팅)
**Root Cause:** 10:02경 Windows가 자체 재부팅(Kernel API 트리거, Windows Update 추정 — 미확정) 실행. watchdog.ps1은 부팅 시 자동 기동 메커니즘(시작 프로그램/예약 작업) 없어 재부팅 후 재기동되지 않음. 이후 launcher/main.py도 감시 주체 없이 방치되다 17:57 이후 프로세스 소멸(정확한 원인 UNKNOWN — watchdog 부재로 crash 로그 없음). 23:32 확인 시점 python/streamlit/ngrok/watchdog 프로세스 전무.
**Fix:** 수동으로 run_scheduler.ps1 실행 → watchdog.ps1 백그라운드 기동 (2026-07-01 23:35). Flask/Streamlit/ngrok/python 정상 기동, facebook_crawler 23:38 정상 재개 확인.
**Prevention:** watchdog.ps1을 Windows Task Scheduler("시스템 시작 시"/"로그온 시" 트리거)에 등록해 재부팅 후 자동 재기동 보장 필요. Modern Standby 비활성화 병행 검토.
**Status:** 🟡 MITIGATED (수동 복구 완료) — 재발 방지책(자동 기동 등록) 미적용, 재발 가능
**Evidence:** Get-WinEvent(Kernel-Power) / scheduler_err.log(3506줄, 마지막 10:01:25) / watchdog.log(마지막 00:39:28) / core_log_initializer.log(00:39:24 이후 재초기화 없음) / Get-Process(23:32 python·streamlit·ngrok 0개)

---

## ERR-046 | Supplier_Blocklist author 매칭 무력화 — supplier_name/author_name 필드명 불일치
**Type:** Data mapping bug (Repository Interface 필드명 오류)
**Raw:** `is_blocked_supplier('Lily Yoon', bl)` → `None` (실시간 재현 확인, 2026-07-02). Airtable에는 `Lily Yoon`이 `author_name='Lily Yoon'`으로 등록되어 있음에도 매칭 실패.
**Root Cause:** `modules/infra/airtable_repository.py:105`의 `list_blocked_suppliers()`가 `f.get("supplier_name", "")`로 Airtable raw field를 읽으나, 실제 `Supplier_Blocklist` 테이블의 필드명은 `author_name` — `supplier_name` 키 자체가 존재하지 않아 항상 빈 문자열 반환. `modules/infra/repository_interface.py:42-44`의 `SupplierBlockEntry` TypedDict도 `supplier_name`만 정의하고 `page_name` 필드는 계약에 아예 없음. `modules/sns/facebook_crawler.py:41-42`의 `load_supplier_blocklist()`가 이 빈 값을 그대로 `author_name: ''`으로 재구성하고 `page_name`도 하드코딩 `''`으로 채움 → `is_blocked_supplier()`의 `if item['author_name'] and ...` 조건이 항상 False → 등록된 어떤 공급자도 실제로 차단되지 않음.
**Fix:** ✅ 적용 완료 (2026-07-03) — `airtable_repository.py:104-108`의 `f.get("supplier_name", "")` → `f.get("author_name", "")` / `f.get("page_name", "")` 매핑으로 수정, `repository_interface.py:42-45`의 `SupplierBlockEntry`에 `page_name` 필드 추가, `facebook_crawler.py:39-46`의 `load_supplier_blocklist()` 하드코딩 `page_name: ''` 제거 후 실제 값 매핑.
**Prevention:** Repository 패턴 도입 시 raw Airtable 필드명과 DTO 필드명이 다르면 통합 테스트(실제 매칭 성공 케이스 1건) 없이는 회귀를 잡을 수 없음. 필드 매핑 변경 시 최소 1건 실제 매칭 검증 필수화 권장.
**Status:** ✅ RESOLVED (2026-07-03) — 3파일 수정 적용 + Gate 6 ISOLATED INTEGRATION PROOF(격리 테스트 테이블 `Supplier_Blocklist_Test`, 실제 HTTP 왕복) 사전 통과 + 운영 `Supplier_Blocklist` 대상 Runtime Proof 6/6 전건 매칭 성공 확인
**Evidence:** (수정 전) 라이브 테스트 `is_blocked_supplier()` 6/6 전건 `None` 반환 (Lily Yoon, Mooncher Kim, M&Y GLOBAL, Cosmetics Station, Athena Magnayon, COSLIFE 전부, 2026-07-02) / `git show 758d29d`(`supplier_name=f.get("supplier_name","")` 최초 도입, 2026-06-23) / `git show df9df6b`(facebook_crawler.py가 직접 호출 `fields.get('author_name','')`에서 Repository 경유 `e.get('supplier_name','')`로 교체, 2026-06-24) / Airtable `Supplier_Blocklist` 실제 필드 5건 raw 확인. (수정 후, 2026-07-03) `tools/_gate6_integration_proof.py` 실행 — 격리 테스트 테이블에 실 레코드 POST→GET(mock 없음), BUGGY 매핑 재현(None) 후 FIXED 매핑 정상 매칭 확인 / 운영 `Supplier_Blocklist` 5건 대상 `is_blocked_supplier()` 재실행 — Lily Yoon·Mooncher Kim·M&Y GLOBAL·Cosmetics Station·Athena Magnayon·COSLIFE 6/6 전건 매칭 성공 / pytest 100 passed·4 failed(pre-existing, stash 비교로 무관 확인)·3 xfailed — 회귀 없음

---

## ERR-047 | SNS_Watchdog_AutoStart 스케줄 작업 — 06-29 등록 이후 9회 재부팅에도 무재실행, watchdog.ps1 4일+ 감시 공백
**Type:** Infrastructure / Task Scheduler 미작동 (not application code)
**Raw:** `schtasks /Query /TN "SNS_Watchdog_AutoStart" /V` → `Last Run Time: 2026-06-29 20:12:06`, `Last Result: -1073741510` (0xC000013A, CTRL+C성 강제종료), `Next Run Time: N/A`. `logs/watchdog.log` 마지막 항목 `2026-07-01 23:36:55` 이후 4일간 무기록. `Get-WinEvent Kernel-General Event 12`(실제 cold boot, Fast Startup 시스템 정책상 비활성 확인) 기준 2026-06-29 20:12 이후 **9회 재부팅** 확인(07-01 11:01 / 07-03 20:47·20:49·21:06 / 07-04 09:53·22:43 / 07-05 15:35·16:15·19:57)했으나 스케줄 작업 Last Run Time은 06-29 그대로 — 단 한 번도 재실행되지 않음.
**Root Cause:** `SNS_Watchdog_AutoStart` 작업은 `Schedule Type: At system start up` + `Logon Mode: Interactive only` (Run As User: admin, 인터랙티브 토큰 필요)로 등록됨. CURRENT_RUNTIME_CONTEXT.md에는 "260529 관리자 권한으로 등록 완료"로 기록되어 있으나, 실제로는 최초 1회(06-29 20:12, 등록 직후 최초 부팅 트리거) 실행된 이후 이어진 9회의 재부팅+admin 인터랙티브 로그온 상황에서도 재실행되지 않음 — 등록된 자동 기동 안전장치가 실질적으로 작동하지 않는 상태. 정확한 미작동 사유(트리거 조건 결락, 계정 토큰 만료, 정책 변경 등) 미확정 — UNKNOWN. watchdog.log 자체는 07-01 23:35:58 수동 재시작 후 23:36:55까지만 기록되고 중단 — INC-023 복구 작업(23:35~23:39) 도중 watchdog.ps1 루프 자체가 별도로 조기 종료된 것으로 추정되나 원인 미확정.
**Fix:** 미적용 (문서화만 우선 진행, 사용자 승인 대기 중).
**Prevention:** (1) Task Scheduler 조건 재확인 — "Run whether user is logged on or not"(S4U/비밀번호 저장)로 변경해 인터랙티브 로그온 의존성 제거 검토. (2) watchdog.ps1 자체에 self-heal 불가하므로, 상위 감시 계층(예: 별도 Scheduled Task가 30분 간격으로 watchdog.ps1 프로세스 생존 여부 점검 후 재기동) 이중화 검토. (3) Task Scheduler 히스토리(`Microsoft-Windows-TaskScheduler/Operational` Event Log)로 실제 트리거 시도 여부(시도했으나 실패 vs 아예 미시도) 구분 확인 필요 — 현재 미실시.
**Status:** 🟢 구조적 해소(Moot) — 260711 Note 6 참조. "왜 옛 Task가 재부팅 후 무재실행했는지"의 근본원인 자체는 영원히 UNKNOWN으로 남으나, 그 메커니즘(Task Scheduler 기반 watchdog) 자체를 폐기했으므로 증상 재발 가능성이 구조적으로 사라짐.
**Evidence:** `schtasks /Query /TN "SNS_Watchdog_AutoStart" /V` 출력 / `logs/watchdog.log` tail(마지막 2026-07-01 23:36:55) / `Get-WinEvent -Id 12` 9건(06-29 20:12 이후) / `powercfg /a`(빠른 시작 "현재 시스템 정책에서 사용하지 않도록 설정" 확인 — cold boot 확정) / `Get-Process python` (PID 14740/5524, StartTime 2026-07-05 20:10:28~29) / `Get-CimInstance Win32_Process -Filter "Name='powershell.exe'"` (watchdog.ps1 실행 중인 프로세스 없음, 2026-07-05 20:2x 시점)
**관련:** ERR-045, FP-033, INC-023, INC-025, INC-028

**[2026-07-08 추가 Note]:** 별도 세션에서 Start-ScheduledTask(수동 트리거)로는 Task 실행 자체가 확인됨(ERR-050 참조). 단, 이는 BootTrigger/LogonTrigger 자동 발동 여부를 검증한 것이 아니므로 본 항목의 근본원인(9회 재부팅 무재실행)은 여전히 UNKNOWN. ERR-047 Status는 변경 없음.

**[2026-07-08 추가 Note 2 — 재부팅 실증, 별도 세션]:** 실제 Windows 재부팅(20:29 KST) 1회 실증 결과, 기존 본문의 "9회 재부팅 무재실행" 증상과 달리 **이번에는 Task Action이 재부팅 후 실행됨** — 단, 이는 Note 1 시점 이후 Task Action이 watchdog_task_wrapper.ps1 경유로 변경된 상태에서의 결과이며, 기존 9회 재부팅 시점의 Action(direct 실행)과 조건이 다름. 따라서 "무재실행 문제 해결"로 판단 불가 — 별개 조건에서의 신규 관찰로 취급.

- Confirmed:
  - 재부팅 후 Task Action 실행 확인 (LastRunTime 2026-07-08 18:54:25 → 20:32:05 갱신)
  - wrapper(watchdog_task_wrapper.ps1) PID 2656 기동 확인 (20:32:17 WRAPPER START)
  - watchdog loop 약 4분 24초 정상 동작 (20:32:17~20:36:41 HEARTBEAT; Streamlit/ngrok/launcher 재시작 성공, n8n 자체복구 포함)
  - WRAPPER END 로그 없음 / stderr 빈 파일 / silent death
  - LastTaskResult=3221225786 (0xC000013A) 재부팅 전후 동일
- **Task Action 호출은 확인됨. 실제 발동 트리거(Boot/Logon)는 Operational Event Log 확인 전까지 UNKNOWN.**
- UNKNOWN:
  - 실제 발동한 트리거가 BootTrigger인지 LogonTrigger인지 — `Microsoft-Windows-TaskScheduler/Operational` Event Log 확인 전까지 미확정 (양쪽 모두 Enabled=True, Delay=PT1M로 동시 등록되어 있어 LastRunTime만으로 구분 불가)
  - 4~5분 후 종료 주체 — Task Scheduler 세션/토큰 정리, PowerShell Host 종료, wrapper 내부 미포착 예외 중 어느 것인지 미확정 (전부 Hypothesis, 확정 아님)
  - 0xC000013A가 이번 신규 종료와 인과관계가 있는지, 단순 이전 값 잔존인지 미확정
- Status 변경 없음 — ERR-047 여전히 OPEN. 단, 증상 프로파일이 "무재실행"에서 "재실행은 되나 4~5분 내 silent death"로 갱신되었음을 다음 세션에 명시적으로 승계.
- **Evidence:** `logs/watchdog_wrapper.log`(raw, 17행 `[2026-07-08 20:32:17] WRAPPER START`/18행 `PID=2656`, 이후 WRAPPER END 미기록) / `logs/watchdog_wrapper_stderr.log`(0 bytes, 빈 파일 확인) / `logs/watchdog.log`(1746~1764행, `20:32:18 watchdog 시작` ~ `20:36:41 HEARTBEAT` 이후 무기록, 파일 tail과 일치) / `schtasks /Query /TN "SNS_Watchdog_AutoStart" /V`(Last Run Time 2026-07-08 20:32:05, Last Result -1073741510 = 0xC000013A 재확인)
- 관련: ERR-050 (wrapper 자연사망 최초 증거 — 상세 근거는 ERR-050 항목 참조)

**[2026-07-10 추가 Note 4 — 절전모드(Modern Standby) 상관관계 조사]:**

`powercfg /a` 확인 결과, 이 시스템은 S1/S2/S3 전통적 대기 모드가 전부 비활성화되어 있음(S1/S2: 펌웨어 미지원, S3: 펌웨어 미지원 + Device Guard가 추가로 비활성화, 하이브리드 절전: S3 불가 + 하이퍼바이저 미지원) — 실질적으로 **Modern Standby(S0 저전원 유휴)만 사용 가능**한 구성. Fast Startup도 "현재 시스템 정책에서 사용하지 않도록 설정됨" — 기존 ERR-045에서 cold boot 확정에 썼던 근거와 일치.

2026-07-09 19:00~2026-07-10 현재 System 로그의 Kernel-Power Id 506(Modern Standby 진입)/507(해제) 이벤트 raw 전체(11개 구간):
```
21:40:28 → 21:44:19
21:47:18 → 21:50:46
22:04:55 → 22:13:58
23:52:41 → 23:56:05
00:54:30 → 04:11:29   (약 3시간17분)
04:30:54 → 04:32:26
05:04:30 → 05:19:25
05:59:30 → 06:14:47
06:14:47 → 06:14:53
06:42:27 → 06:42:28
06:45:29 → 06:48:31
```

INC-028의 2차 다운(heartbeat_monitor.py가 탐지한 watchdog 마지막 heartbeat `2026-07-10 03:04:09`)은 `00:54:30~04:11:29` Modern Standby 구간 한가운데에 위치 — **상관관계가 강함**(인과관계 확정 아님).

반면 INC-028의 1차 다운(watchdog 마지막 heartbeat `2026-07-09 20:09:40`)은 가장 가까운 절전 구간(21:40:28)과도 1시간30분 이상 차이가 나 — 이번 조사로는 절전모드로 설명되지 않음.

**결론(잠정):** ERR-047/ERR-050/ERR-051/INC-028을 단일 근본원인으로 묶어온 전제 자체를 재검토할 필요가 있을 수 있음 — 최소 2개의 서로 다른 메커니즘(절전모드 관련 vs 미상)이 섞여 있을 가능성.

**UNKNOWN으로 남기는 항목:**
- INC-028 1차 다운(20:09:40)의 실제 원인 — 절전모드로 설명되지 않는다는 것 외에는 미상이었으나, 아래 Note 5(및 INC-028 Note 3)에서 해소됨(실제 OS shutdown 확인)
- Modern Standby가 왜 watchdog을 죽이는지의 메커니즘 — Windows가 절전 중 백그라운드 프로세스/Task Scheduler 트리거를 지연·억제하는 것은 일반적으로 알려진 동작이나, 이 컴퓨터에서 실제로 그렇게 작동했다는 직접 증거(프로세스 자체가 kill됐는지 vs 타이머만 지연됐는지 구분)는 아직 없음
- `powercfg /sleepstudy` 리포트는 관리자 권한 필요로 미생성 — 향후 관리자 권한 세션에서 재시도 가능

**Evidence:** `powercfg /a` / `Get-WinEvent -LogName System`(Kernel-Power Id 506/507, 2026-07-09 19:00~) / heartbeat_monitor.py의 `logs/heartbeat_monitor.log` 기록(last_heartbeat=2026-07-10 03:04:09) / INC-028 문서(1차 다운 20:09:40)

**관련:** ERR-050, ERR-051, INC-028

**[2026-07-10 추가 Note 5 — INC-028 1차 다운(20:09:40) 실제 원인 확정: 실제 OS Shutdown, Modern Standby 아님]:**

Note 4의 "UNKNOWN으로 남기는 항목" 중 "INC-028 1차 다운(20:09:40)의 실제 원인"을 재조사하여 확정함. 상세 이벤트 체인·Confirmed/Hypothesis/UNKNOWN 전체 구분은 INC-028 Note 3에 기록(중복 서술 생략) — 요약: `20:09:52` `StartMenuExperienceHost.exe`가 admin 세션 명의로 시스템 종료를 개시, `20:10:53` OS 종료 확정까지 정상적인 종료 시퀀스가 이어짐. Modern Standby 아님 — 직전 절전 해제(19:39:00, Id=507)부터 다음 절전 진입(21:40:28, Id=506)까지 약 2시간1분 동안 Modern Standby 이벤트가 전혀 없었고(`Get-WinEvent` Id=506,507 raw 확인), 1차 다운 전체 구간(20:09:40 마지막 heartbeat ~ 20:10:53 OS 종료 확정)이 이 공백 한가운데 위치함. Windows Update 강제 재부팅 아님, 명시적 사용자 로그오프/잠금 이벤트도 아님 — 전부 raw 로그로 배제 확인.

시작 메뉴를 통한 사람의 직접 종료 조작일 가능성이 가장 유력하나(Hypothesis, 확정 아님), `20:10:03` 재시도 실패 기록과 `20:10:28` 실제 종료 재개 사이 25초 갭의 메커니즘은 여전히 UNKNOWN.

이 발견으로 Note 4의 "결론(잠정) — 최소 2개의 서로 다른 메커니즘(절전모드 관련 vs 미상)이 섞여 있을 가능성"이 확정됨: 2차 다운(Modern Standby 상관관계 강함, ERR-053에서 heartbeat_monitor 쪽 메커니즘 확정) / 1차 다운(실제 OS shutdown, 사람의 조작 가능성) — 서로 다른 별개 사건으로 분리 확정.

**관련(추가 5):** INC-028(Note 3 — 원본 근거)

**[2026-07-11 추가 Note 6 — NSSM 서비스 전환으로 구조적 해소, PENDING-A 종결]:**

`docs/PENDING_INVESTIGATIONS.md` PENDING-A(260710 결론남) 후속으로, watchdog.ps1의 실행 주체를 Task Scheduler(`SNS_Watchdog_AutoStart`, 이 항목이 다루는 대상 자체)에서 NSSM Windows 서비스(`SNS_Watchdog`)로 완전히 교체(ERR-057). 크래시 재시작 실증(강제 종료 → 60초 내 자동 재기동) PASS + 실제 재부팅 실증(watchdog.log 시작 배너 1번만 기록, 구 Task 재발 없음) PASS 확인 — 상세는 ERR-057/058, `docs/PENDING_INVESTIGATIONS.md` PENDING-A 참조.

이로써 본 항목이 추적해온 "다음 세션 승계 (a) 재부팅 시 BootTrigger/LogonTrigger 자동 발동 검증"은 **더 이상 유효한 질문이 아님** — 그 트리거 메커니즘 자체가 폐기됐기 때문. Note 1~5에서 남겨둔 UNKNOWN 항목들(direct silent death 원인, 트리거 종류 미확정 등)도 마찬가지로 대상 메커니즘이 사라져 규명 실익이 없어짐 — **조사 종결(Moot), 미해결로 방치된 것이 아니라 재발방지 목적 자체는 대체 수단으로 달성됨**을 명시.

`SNS_Watchdog_AutoStart` Task 자체는 삭제하지 않고 `Disabled` 상태로 증거 보존 유지 중(260710/711 governance 원칙에 따름).

**관련(추가 6):** ERR-057, ERR-058, PENDING-A

---

## ERR-048 | launcher/main.py 중복 기동 — 세션 중 Start-Process 반복 실행으로 5세대(10프로세스) 동시 기동, 종료 후 유령 LISTENING PID 잔존
**Type:** Operational / 수동 프로세스 관리 실수 (not application code)
**Raw:** 세션 중 `Start-Process .venv\Scripts\python.exe launcher\main.py` 를 여러 차례 반복 실행. `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` 로 확인한 결과, 서로 다른 시각에 시작된 `.venv` launcher 프로세스 4개 + 시스템 Python310(AdsPower/Selenium 연동 추정) 짝 프로세스 4개, 총 8개가 동시 생존(시작 시각: 16:46:43/44, 16:51:04/04, 16:55:41/42, 16:55:57/58) — 여기에 전날(2026-07-05 23:38:57)부터 떠있던 PID 20448/5284 쌍까지 포함하면 5세대 launcher가 동시에 각자의 APScheduler(`_job_fb_crawl` 30분, `_job_insta_upload` 5분, `process_due_followups`/`process_lost_candidates`/`poll_new_comments` 5분 등)를 병행 실행 중이었음. `Stop-Process -Force`로 8개는 정상 종료됐으나 PID 20448/5284는 동일 사용자(admin) 소유임에도 `Access is denied`로 종료 실패(메모리 사용량 각 1MB/5.7MB로 극소, 실제 launcher 본체로 보기 어려움 — 권한 승격 컨텍스트에서 기동된 것으로 추정). 이후 신규 인스턴스 1개(PID 33148/6140)만 재기동했음에도 `netstat -ano | findstr ":5000"` 에 정상 PID(6140) 외에 `Get-Process`/`Get-CimInstance` 어디에도 나타나지 않는 유령 PID 32944 가 동시에 `:5000` LISTENING 상태로 잡힘(반복 확인 시에도 동일 PID 재현).
**Root Cause:** (1) 다중 기동: watchdog.ps1 미기동 상태(ERR-047/INC-025 지속) + 수동 Start-Process 반복 실행이 결합되어, 기존 인스턴스 생존 여부를 사전 확인하지 않고 새 인스턴스를 추가 기동 — 포트 바인딩 충돌 검사나 PID lock 파일 등 중복 실행 방지 장치가 launcher/main.py에 전혀 없음. (2) 유령 PID 32944: 정확한 원인 UNKNOWN — 커널 소켓 테이블에 남은 stale LISTENING 엔트리(정상 종료되지 않은 과거 Flask 프로세스의 잔존 소켓 핸들 추정) 또는 WMI/프로세스 열거 API가 포착하지 못하는 별도 보호 컨텍스트의 실프로세스일 가능성 — 재부팅 없이는 판별 불가.
**Fix:** 8개 중복 프로세스 `Stop-Process -Force`로 정리 후 단일 인스턴스(PID 33148/6140) 재기동 완료, 앱 로그(`logs/summary/app.log` 17:11:05~18) 상 스케줄러 잡 1세트만 등록되고 Flask 정상 바인딩 확인. PID 20448/5284, 32944는 비관리자 세션에서 종료 불가 — 미해결 상태로 남음.
**Prevention:** (1) launcher/main.py 시작 시 PID 파일 또는 포트 선점 체크로 중복 기동 자체를 차단하는 가드 추가 검토. (2) watchdog.ps1 정상화(ERR-047)가 최우선 선행 조건 — watchdog가 살아있었다면 애초에 수동 반복 기동 필요성 자체가 낮았을 것. (3) 관리자 권한 세션에서 PID 20448/5284/32944 재확인 및 필요 시 재부팅으로 커널 소켓 테이블 초기화 검토.
**Status:** 🟡 부분 해결 — 신규 단일 인스턴스는 정상 동작 확인, 잔존 유령 프로세스(20448/5284/32944)는 비관리자 권한으로 종료 불가하여 미해결
**Evidence:** `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` 4회 스냅샷(중복 발견 시점 / 정리 후 / 재기동 후 / 재확인) / `Get-Process -Id <pid> | Select StartTime` 대조표 / `netstat -ano | findstr ":5000"` 3회(정리 전/정리 직후 비어있음/재기동 후 32944 재출현) / `logs/summary/app.log` 17:11:05~18 정상 단일 기동 로그 / `Invoke-CimMethod GetOwner` (20448/5284 소유자 admin 확인, Stop-Process 여전히 Access denied)
**관련:** ERR-047, FP-035, INC-025, FP-036, INC-026

---

## ERR-049 | quality_gate.py relevance filter canary — 영어-only 키워드가 한국어 title에 전량 미매칭, Domeggook 크롤 100% 차단
**Type:** Logic Error / Language Mismatch / Uncommitted canary edit loaded into active runtime
**Raw:** launcher/main.py 재시작 후 첫 `_job_dome_crawl` 실행 로그: `[dome_crawl] D001 fetch=10 ready=0`, `[dome_crawl] D002 fetch=10 ready=0` (2026-07-06 13:02:18) — 직전까지 8회 연속 `fetch=10 ready=10`였던 것과 대비되는 100% 필터링.
**Root Cause:** `quality_gate.py`에 5번째 규칙(`relevance`, `_is_irrelevant_category`)을 canary 편집으로 추가하면서, dry-run 검증은 Instagram_Posts의 영문 번역 `caption` 필드 20건 기준으로 20/20 MATCH를 확인했으나, 실제 runtime에서 `run_gate()`가 검사하는 필드는 Domeggook API 원본 `title`이며 이는 한국어("이켈 포맨 프리미엄 콜라겐 기초세트... 남성화장품 로션 스킨" 등)였다. `COSMETIC_KEYWORDS`/`HEALTH_KEYWORDS`가 전부 영어 단어("cream", "serum", "organic" 등)로 작성되어 한국어 title에 매칭 불가 → `_is_irrelevant_category()`가 화장품/건강식품 포함 전 상품을 `True`(FILTERED)로 반환.
**Fix:** `git checkout HEAD -- modules\crawlers\quality_gate.py` 로 원본 4규칙(adult_only/title/unit_price/image_url)으로 rollback. launcher/main.py PID 지정 재시작(Stop-Process -Id 지정 + 재기동)으로 런타임 반영 확인.
**Prevention:** dry-run 검증은 반드시 실제 runtime이 검사하는 필드(이 경우 `title`, 언어=한국어)로 수행해야 함. 캡션(번역/가공 필드) 기준 검증은 원본 필드 언어와 다를 경우 무의미. 관련성 필터 재설계 시 한국어+영어 이중언어 키워드 세트 필수.
**Status:** ✅ ROLLED BACK (2026-07-06) — 재설계 미착수, quality_gate.py는 원본 4규칙 상태
**Evidence:** dome_crawl 로그(8회 fetch=10/ready=10 정상 → 1회 fetch=10/ready=0 이상) / `_test_relevance_function.py` 오프라인 테스트 — 한국어 title 5건 전부 `irrelevant=True` 오분류 확인 / Gate 9~11에서 rollback 후 `quality_gate.py` 원본 4규칙 및 HEAD diff clean 확인
**관련:** FP-037 / INC-027 예정. INC-026은 launcher 5세대 중복 기동 사고로 별도 분리.

---

## ERR-050 | SNS_Watchdog_AutoStart 수동 트리거 시 direct 실행 60초 내 silent death, wrapper 경유는 생존
**Type:** Task Scheduler Process Survival (조건부, not application code)
**Raw:** Start-ScheduledTask로 수동 트리거 시 — direct 실행(watchdog.ps1 직접): 시작 배너+HEARTBEAT 1회 기록(12:49:56~59) 후 60초 이내 프로세스 소멸 확인(LastTaskResult=267009 RUNNING 표시했으나 실제 프로세스 부재, PID 기준 실물 확인으로 발견). wrapper 경유(watchdog_task_wrapper.ps1): 동일 방식 트리거 시 2분+ 지속 HEARTBEAT 확인(10:16:57~10:19:03, 5회+), 사망 없음.
**Root Cause:** 현상(Phenomenon): Confirmed — direct 실행은 Task Scheduler 트리거 후 60초 내 사망, wrapper 경유는 생존(재현 완료). 원인(Mechanism): Hypothesis, 미확정 — 이중 감시 충돌은 주 원인 가능성 낮아짐(동일하게 PID 22908과 병존한 상태에서도 direct만 사망, wrapper는 생존). 유력 후보(우선순위순, 미분리검증): (1) stdout/stderr redirect 차이 (2) -NoProfile 차이 (3) WorkingDirectory 고정 방식 (4) PowerShell 절대경로 차이.
**Fix (임시):** Task Action을 watchdog_task_wrapper.ps1 경유로 전환(2026-07-08 완료) — 운영 안전 확보용 임시 조치, 근본 수정 아님.
**Prevention:** LastTaskResult 단독으로 프로세스 생존 판정 금지 확인됨(RUNNING 표시 중 실제 사망 사례 확보) — 판정은 반드시 PID 기준 실물 확인. 조건 분리 A/B 테스트(stdout/stderr redirect부터) 필요, 다음 세션 승계.
**Status:** 🟢 구조적 해소(Moot) — 260711 Note 5 참조. wrapper(watchdog_task_wrapper.ps1) 경유 방식 자체를 폐기했으므로 근본원인 규명 실익 없음.
**Evidence:** watchdog_wrapper.log(PID=29076 START 기록) / watchdog_wrapper_stdout.log(HEARTBEAT 5회+) / Win32_Process 조회 3회(direct 임시 Task 소멸 확인, 22908 단독 재확인 2회) / Task XML Format-List(wrapper 경로 확정)
**다음 세션 승계 (미실행):** (a) 실제 재부팅으로 BootTrigger/LogonTrigger 자동 발동 여부 검증(ERR-047 원인 규명), (b) 실제 재부팅으로 wrapper 경로 생존 여부 검증(ERR-050 완화 확인), (c) 조건 4개 분리 A/B 테스트(stdout/stderr redirect → -NoProfile → WorkingDirectory → 절대경로), (d) 사망 시점 LastTaskResult 종료코드 재조회, (e) PowerShell/Task Scheduler Operational 이벤트 로그 확인
**관련:** ERR-047, FP-017, ERR-021, INC-023, INC-028

**[2026-07-08 추가 Note 2]:** wrapper 인스턴스(PID 29076/자식 30888) 실제 생존 시간 재확인 — 최초 기록(10:16:57~10:19:03, "2분+")보다 훨씬 길게 10:16:55~12:02까지 약 1시간 46분간 정상 생존(watchdog.log heartbeat 연속 확인). 12:03:12 WRAPPER END — ExitCode=-1은 자연사가 아니라, 별도 세션(Claude Desktop)에서 PID 22908(새벽 수동 복구본, direct 실행)과 29076/30888(wrapper 경유)가 동시에 감시 중인 이중 watchdog 상태를 발견하고 사용자 승인 하에 Stop-Process -Id 30888/29076 -Force로 의도적 종료한 결과 — FP-017(watchdog 이중 감시 충돌 패턴)의 재발 사례. wrapper 자체의 자연 사망 사례는 이번엔 관찰되지 않음(오히려 안정성 증거 강화). 단, "다음 세션 승계" 항목 (a)(b) 재부팅 트리거 검증은 여전히 미실시 — Status 🟡 MITIGATED/OPEN 유지.

**[2026-07-09 추가 Note 3 — 재부팅 실증, wrapper 자연사망 최초 관측]:** 2026-07-08 20:32:17 재부팅 트리거 케이스에서 wrapper(PID 2656)가 WRAPPER END 로그 없이 약 4분 24초(20:32:17~20:36:41) 만에 종료됨(silent death). Note 2의 "1h46m 생존"과 성격이 다름 — Note 2의 종료는 사용자의 의도적 Stop-Process(이중 watchdog 정리)였고 자연 수명이 아니었던 반면, 이번 4분 24초 종료는 사용자 개입 없이 재부팅 트리거 이후 자연 발생한 것으로, 관찰된 최초의 순수 wrapper 자연사망 사례. 두 사례는 트리거 방식(수동 Start-ScheduledTask vs 실제 재부팅)과 종료 원인(의도적 vs 자연)이 모두 달라 직접 비교·연장 해석 불가.
- 상세 raw 로그 근거(watchdog_wrapper.log/watchdog_wrapper_stderr.log/watchdog.log/schtasks 출력): ERR-047 Note 2 참조(동일 실증, 중복 서술 생략)
- 사망 근본원인 여전히 UNKNOWN — 본 항목 Root Cause의 Hypothesis (1)~(4) 중 이번 재부팅 케이스로 검증된 것 없음. Task Scheduler 세션정리/PowerShell Host 종료/wrapper 내부 미포착 예외 모두 미확정.
- "다음 세션 승계 (b) 재부팅 시 wrapper 생존 여부 검증"은 이번 실증으로 수행되었으나 결과는 "생존"이 아닌 "약 4분 24초 후 자연사망" — 완화(MITIGATED) 판정의 근거였던 wrapper 안정성 가정이 재부팅 조건에서는 뒷받침되지 않음.
- Status 변경 없음 — 🟡 MITIGATED(근본원인 미해결, OPEN 유지).

**[2026-07-10 추가 Note 4 — 절전모드(Modern Standby) 상관관계 조사, ERR-047 Note 4와 연계]:**

watchdog 관련 반복 사망 현상의 공통 원인 후보로 이 시스템의 절전 구성(Modern Standby만 사용 가능, S1/S2/S3 전부 비활성화, Fast Startup 비활성화)과 2026-07-09 19:00~2026-07-10 Modern Standby 진입/해제(Id 506/507) 이력을 조사함 — 전체 raw 이벤트 목록·상세 근거는 ERR-047 Note 4 참조(중복 서술 생략). INC-028의 2차 다운(watchdog 마지막 heartbeat 2026-07-10 03:04:09)이 00:54:30~04:11:29 Modern Standby 구간 한가운데에 위치해 상관관계가 강함(인과관계 확정 아님)으로 확인됐으나, 본 항목(ERR-050)이 다루는 07-08 20:32~20:36 wrapper silent death 사례는 이번 조사 대상 시간대(07-09 19:00 이후) 밖이라 직접 검증되지 않음 — 동일 메커니즘 여부는 UNKNOWN.
Status 변경 없음 — 🟡 MITIGATED(근본원인 미해결, OPEN 유지).
**관련:** ERR-047(Note 4 — 절전모드 상관관계 원본 근거)

**[2026-07-11 추가 Note 5 — NSSM 전환으로 구조적 해소]:**

ERR-047 Note 6와 동일 사유·동일 조치(watchdog.ps1을 NSSM Windows 서비스로 전환, ERR-057/058)로 본 항목도 종결. `watchdog_task_wrapper.ps1` 경유 방식 자체를 더 이상 사용하지 않으므로, Root Cause에서 남겨둔 Hypothesis(1)~(4)(stdout/stderr redirect 차이 등)와 "다음 세션 승계" 항목 (c)(d)(e)는 대상이 사라져 조사 실익 없음 — Moot 처리. wrapper 자연사망(Note 3) 자체는 역사적 기록으로 유지, 재조사 계획 없음.

**관련(추가 5):** ERR-047(Note 6), ERR-057, ERR-058, PENDING-A

---

## ERR-051 | Task Scheduler 진단 Task(A/B/D) 12:51~13:17 구간 한정 launch-only 무반응 — 8개 후보변수 배제, 근본원인 UNKNOWN, 13:22 이후 재발 0건

**Type:** Infrastructure / Task Scheduler 간헐적 실행 실패 (not application code)

**Raw:** ERR-047/ERR-050 재부팅 실증 후속 A/B 테스트(진단용 Task A/B/D, 운영 Task `SNS_Watchdog_AutoStart`와 완전 별개, 등록 위치·이름 모두 분리). 마커 파일 생성(`Out-File`)만 하는 최소 스크립트를 Action으로 등록 후 `Start-ScheduledTask`로 반복 트리거 — 12:51:15/12:53:24/12:55:27(Task A, PowerShell direct), 13:09:48(Task B), 13:17:53(Task D, cmd.exe)까지 총 5회 전부 동일 패턴으로 실패: `LastTaskResult=0`(성공) 기록되나 이벤트 로그는 매번 `325`(queued)+`110`(launched)에서 멈추고 `129/100/200/201/102`(프로세스 생성~완료) 계열 이벤트 전무, 마커 파일 미생성, WMI 폴링(0.2초 간격 10초간) PID 0건. 13:22:01 이후(같은 Task B, 설정 무변경)로는 16:56 현재까지 전부(7/7+) 정상 성공 — 전체 이벤트 시퀀스 정상, 마커 파일 정상 생성.

**Root Cause:** 현상(Phenomenon): Confirmed — 12:51~13:17(약 26분) 구간에 한정해 Task Scheduler Action이 "launched" 기록 이후 프로세스 생성 단계에서 관측 불가 상태로 소실, 13:22 이후 자연 소멸(재현 0건). 원인(Mechanism): UNKNOWN — 아래 8개 후보 순차 배제(Confirmed 기각):
(1) MultipleInstancesPolicy(IgnoreNew→Parallel 변경해도 동일 실패)
(2) UseUnifiedSchedulingEngine(Task B=True, 운영 Task=True로 이미 일치 — 변수 아님)
(3) 실행 엔진 종류(PowerShell 스크립트→cmd.exe로 교체해도 동일 실패)
(4) RunLevel(Highest 그대로 유지된 채 재시도했는데 성공 — Highest 단독으로는 원인 아님. Limited로의 실제 변경은 `Set-ScheduledTaskPrincipal` cmdlet 부재로 미검증 상태로 남음)
(5) 세션 불일치(도구 실행 세션·admin 대화형 세션 모두 SessionId=1로 동일 확인)
(6) 프로세스 생성 감사 정책(`auditpol` "No Auditing" — 4688 자체가 없어 판별 불가일 뿐 원인 성립 근거도 아님)
(7) Windows Defender/CodeIntegrity/SmartAppControl(3개 소스 모두 12:51~13:17 구간 차단·탐지 이벤트 0건, SmartAppControl=Off)
(8) Task Scheduler 부하/큐 지연(동일 구간 시스템 예약 작업 4건은 전부 정상 완료) 및 절전(Modern Standby) 복귀·DeviceAssociationService 3502 반복 에러(12:46~13:19, 61초 간격, 실패 구간을 시간상 포괄) — 단 16:15~16:39 성공 구간에도 동일 밀도로 계속 발생해 기각

13:17:53~13:22:01(전환 4분 창) System/Application 로그 정밀 조회 결과 3502 반복 외 다른 신호 없음 — 전환 원인 직접 증거 없음.

**Fix:** 미적용 — 별도 조치 없이 13:22 이후 자연 소멸, 재현 불가 상태로 조사 종료.

**Prevention:** (1) watchdog Task Action 호출 후 프로세스 생성 여부를 자체적으로 이중 확인하는 감시 계층 필요성 재확인(ERR-050 Prevention과 동일 맥락 강화). (2) `LastTaskResult=0`만으로 실행 성공을 판정하지 않고, `129/100/200/201/102` 이벤트 시퀀스 존재 여부를 실행 성공의 필요조건으로 삼는 모니터링 검토.

**Status:** 🔴 260709 재현됨(5/5, 100%) — 근본원인 여전히 UNKNOWN, RunLevel 후보는 배제 확정

**260709 후속 조사 — RunLevel=Limited 실증 + 100% 재현:**

Task B(`SNS_WatchdogAB_TestB`)의 RunLevel을 (4)번 후보 미검증 상태였던 Highest→Limited로 관리자 권한 `Set-ScheduledTask -Principal`로 변경(22:26:55) 후 `Start-ScheduledTask`로 22:28:01 및 22:29:28~22:30:21 사이 총 6회 트리거.

- 6/6 전부 동일 launch-only 패턴 재현: `LastTaskResult=0`(성공) 기록되나 이벤트 로그는 매번 `110`(launched)+`325`(queued, **Warning**)에서 멈추고 `100/200/201/102` 전무
- 마커 파일(`_ab_test_marker.txt`) 6회 전부 미갱신 — 트리거 전후 mtime 동일(2026-07-09 16:56:12.7566, 이전 세션 마지막 정상 실행 그대로)
- **신규 발견**: Task 전체 `State` 속성이 트리거 직후부터 최소 30초 이상(5초 간격 6회 연속 폴링) `"Queued"`로 고착, `Ready`로 복귀하지 않음 — 이전(260707) 조사에서는 미관측 항목
- `Settings.MultipleInstances = Parallel` 확인 — 인스턴스 제한 정책이 큐잉 원인이 아님을 재확인
- 트리거 완료 후 시점 기준 `powershell.exe` 프로세스 0개 — 실제 프로세스 미생성 재확인

**후보 변수 갱신:**
(4) RunLevel — **배제 확정.** Limited로 실제 변경 후에도 동일 실패 100% 재현되어 RunLevel(Highest든 Limited든)이 원인이 아님을 확증. 이전 항목의 "미검증 상태로 남음" 해소.

**해석:** 이번 재현은 지난 12:51~13:17 구간(26분 한정, 이후 자연 소멸)과 달리 시간 구간에 무관하게 즉시·지속적으로 재현됨 — 트리거 조건이 이전과 달라졌을 가능성(RunLevel 변경 자체가 트리거? 혹은 관리자 권한으로 `Set-ScheduledTask`가 Task 정의를 갱신한 시점(22:26:55, 이벤트 Id 140)이 Task Scheduler 내부 상태를 손상시켰을 가능성) — 직접 근거는 아직 없음, 추가 조사 필요.

**Prevention 갱신:** `State` 속성이 `Queued`에 고착되는지 여부를 launch-only 실패의 조기 감지 지표로 추가 검토(기존 `129/100/200/201/102` 이벤트 시퀀스 부재 판정과 병행).

**Evidence:** `Get-WinEvent Microsoft-Windows-TaskScheduler/Operational`(Task 이름 필터 및 시스템 전역 조회 다회) / `Get-ScheduledTaskInfo`·`Get-ScheduledTask...Settings`·`...Principal` 다회 / WMI `Get-CimInstance Win32_Process` 폴링(0.2초×50회) / `auditpol /get /subcategory:{0CCE922B-69AE-11D9-BED3-505054503030}` / `Get-WinEvent` Windows Defender/Operational, CodeIntegrity/Operational, `MSFT_MpComputerStatus.SmartAppControlState` / `Get-WinEvent` System log(12:45~16:40, Id 507/172/566/3502/36871) / Security log(4624) / 마커 파일(`_ab_test_marker.txt`) raw 생성 확인 12회+

**관련:** ERR-047, ERR-050, FP-017, INC-028

**진단용 Task 보존:** `SNS_WatchdogAB_TestA`/`TestB`/`TestD`는 증거 보전을 위해 삭제하지 않고 유지 중 — 운영 Task와 완전 별개. **2026-07-10 `Disable-ScheduledTask`로 비활성화 완료**(삭제 아님, State=Disabled), 완전 삭제 여부는 여전히 별도 승인 필요.

**[2026-07-10 추가 Note — 트리거 0개 상태에서 TestB 자연 성공 관측 + 진단 Task 3종 Disable 처리]:**

세션 시작 점검 중 `_ab_test_marker.txt` 파일 mtime이 이전 세션 마지막 기록(2026-07-09 16:56:12, 정상 성공 기준선)보다 최신인 **2026-07-10 00:44:37**로 갱신되어 있음을 발견, 재조사함.

**Confirmed (raw):**
- `Get-ScheduledTaskInfo -TaskName "SNS_WatchdogAB_TestB"` → `LastRunTime: 2026-07-10 00:44:33`, `LastTaskResult: 0`
- 마커 파일 내용: `ENTERED: 2026-07-10T00:44:37.2077689+07:00 PID=24764 SessionId=1` — **이번엔 정상 완주(마커 실제 갱신)**, 직전 6/6 launch-only 실패(627번째 줄)와 다른 결과
- `(Get-ScheduledTask -TaskName "SNS_WatchdogAB_TestB").Triggers` → **빈 배열(트리거 0개)**. TestA는 트리거 1개(1회성 `StartBoundary`, 이미 경과), TestD는 0개 — TestB의 00:44:33 실행은 자동 트리거로는 설명 불가, `Start-ScheduledTask`(수동/on-demand) 호출로 추정되나 **누가/무엇이 호출했는지는 UNKNOWN**(이번 세션에서 Claude Code가 트리거한 적 없음)

**해석 (Hypothesis, 확정 아님):** 00:44:33은 2026-07-09 20:10:53 확정된 실제 OS shutdown(INC-028 Note 3) 이후 시스템이 재부팅되어 있던 시간대와 겹침. `SessionId=1`이 재부팅 후 첫 세션일 가능성을 시사하나, 이것만으로 재부팅 자체가 트리거 원인이라 확정할 근거는 없음.

**조치 (2026-07-10):** 예측 불가능한(비결정적) 재현 패턴을 고려해 추가 재현 실험보다 증거 보전 우선 판단 — TestA/TestB/TestD 3개 전부 `Disable-ScheduledTask`로 비활성화(삭제 아님). 최초 시도는 비관리자 권한 세션에서 `Access is denied`로 실패, 관리자 권한(UAC) 재시도로 성공 확인:
```
SNS_WatchdogAB_TestA : DISABLE OK
SNS_WatchdogAB_TestB : DISABLE OK
SNS_WatchdogAB_TestD : DISABLE OK
```
재조회 결과 3개 전부 `State: Ready → Disabled` 확인. 이 조치 과정에서 사용한 스크래치 파일(`_disable_abtest_wrapper_260710.ps1`, `_disable_abtest_result_260710.txt`)도 동일한 원칙으로 처리 — **삭제하지 않고 보존**, `.gitignore`에 추가해 추적 대상에서만 제외(Task를 삭제 대신 Disable한 것과 동일하게, 파일도 삭제 대신 추적제외만 적용).

**남은 UNKNOWN:** (1) TestB의 00:44:33 실행을 누가/무엇이 트리거했는지, (2) 애초에 12:51~13:17(260707)/22:26~22:30(260709) 두 차례 관측된 launch-only 실패의 근본 메커니즘 — 여전히 미해결. 이번 발견은 근본원인을 해소한 것이 아니라, "이 현상이 100% 재현되는 결정론적 실패가 아니라 예측 불가능하게 성공/실패가 뒤섞이는 패턴"이라는 사실만 추가함.

**관련:** FP-038(갱신)

---

## ERR-052 | 250723(Reference Only) 참조전용 저장소를 가리키는 활성 Scheduled Task 2개 발견 — SNS_AUTO_PRODUCTION / SNS_Auto_Run

**Type:** Infrastructure / Governance — 저장소 경계 규칙(250723 실행 금지) 위반 정황 (not application code)

**발견 경위:** heartbeat_monitor.py의 Task Scheduler launch-only 실패(`SNS_HeartbeatMonitor_Independent`, 등록 직후 일시적 재현)를 조사하던 중, "지금 이 순간 Task Scheduler 전반이 정상인지" 기존 정상 Task로 교차검증할 목적으로 `SNS_Auto_Run`을 골라 `Start-ScheduledTask`로 수동 트리거했다가, 그 Action이 `C:\SNS_24AutoProject_250723\tools\run_production.py`를 가리키고 있음을 우연히 발견함 — 250723을 노린 의도된 감사가 아니었음을 명시한다.

**Raw — Task 2건:**
- `SNS_AUTO_PRODUCTION`: StartBoundary 2025-11-20T09:00:00, DailyTrigger(DaysInterval=1), Action=`python.exe C:\SNS_24AutoProject_250723\tools\run_production.py`, 발견 시점 State=Ready, LastRunTime=2026-07-09 09:37:51(자연 발동, 예정 09:00 대비 37분 지연), LastTaskResult=1
- `SNS_Auto_Run`: StartBoundary 2026-01-13T09:00:00, DailyTrigger(DaysInterval=1), Action=`python C:\SNS_24AutoProject_250723\tools\run_production.py`, 발견 시점 State=Ready, LastRunTime=2026-07-10 04:52:58(본 세션 수동 트리거 기록), LastTaskResult=1
- 두 Task 모두 Execute 절대경로 없음(`python`/`python.exe`만), WorkingDirectory 미지정

**Root Cause:** 250723→260511 이전(porting) 작업 시 코드 파일은 옮겼으나, 해당 코드를 자동 실행하던 Task Scheduler 등록은 정리되지 않고 250723 경로를 그대로 가리킨 채 방치됨(구조적 원인 상세는 FP-039 참조).

**정적 분석 결과 (raw 근거 — "추정", stderr 실측 아님, 250723 재실행 금지 원칙상 재실행 미실시):**
- 1차 실패점 추정: `Get-Command python`/`python.exe` → `Source: C:\Python314\python.exe`(프로젝트 venv 아닌 시스템 전역 Python 3.14.6), 해당 인터프리터 `pip list` 조회 결과 `dotenv`/`requests` 매칭 0건 — `run_production.py` 최상단 `from dotenv import load_dotenv`에서 `ModuleNotFoundError` 발생 가능성
- 2차 실패점 추정(1차를 넘겼다면): `modules\log_trace.py` 부재(`Test-Path`=False), 대신 `modules\log_trace_fixed.py` 존재 확인(개명됨) — `from modules.log_trace import init_log_db` 실패 가능성
- 3차 실패점 추정(2차도 넘겼다면): `modules\account_runner.py` 저장소 전체 재귀 검색 결과 0건(완전 부재) — `from modules.account_runner import run_all_accounts` 실패 가능성

**250723 자체 로그/DB 최종 수정 시각 (raw, "프로덕션 쓰기까지 도달한 흔적 낮음"의 근거로만 인용):**
`db\trace_log.db` 2026-05-11 14:52:05(가장 최근) / `db\instagram.db` 2026-02-04 / `db\session.db` 2026-02-09 / `*.log` 전체 최신 2025-11-22 — 두 Task가 등록 이후 매일 발동해온 것으로 추정되는 기간 대비, 의미 있는 산출물 갱신 흔적이 극히 낮음.

**공유 프로덕션 자원 확인 (raw):**
250723 `.env`: `AIRTABLE_BASE_ID=apphJNTHWNoFcVb1D` / 260511 `.env`: `AIRTABLE_BASE_ID=apphJNTHWNoFcVb1D` — **동일 Base ID.** 250723과 260511이 같은 프로덕션 Airtable Base를 공유하는 상태이며, 위 3중 import 실패가 우연히 해소되는 시점부터 260511과 동시에 같은 Base에 쓰기가 발생할 수 있는 잠재 위험이 실재했음.

**조치 (2026-07-10):**
```
Disable-ScheduledTask -TaskName "SNS_AUTO_PRODUCTION"
Disable-ScheduledTask -TaskName "SNS_Auto_Run"
Get-ScheduledTask -TaskName "SNS_AUTO_PRODUCTION","SNS_Auto_Run" | Select-Object TaskName, State
```
결과(raw): `SNS_AUTO_PRODUCTION State=Disabled` / `SNS_Auto_Run State=Disabled` — **삭제 아님, 증거 보존 목적으로 비활성화만 수행.**

**Status:** 🟡 MITIGATED — Disable로 즉시 위험(자동 발동에 의한 잠재적 동시 쓰기) 차단 완료. 근본 정리(Task 완전 삭제 여부, 250723 저장소 자체의 처리 방향)는 미완료.

**반드시 UNKNOWN으로 남기는 항목:**
- 약 8개월(2025-11-20~2026-07-10, 추정) 동안 단 한 번이라도 위 3중 import 실패 지점을 넘겨 실제 프로덕션 쓰기(Airtable/Instagram)에 도달한 적이 있는지 — 정적 추론상 가능성은 낮아 보이나 stderr 실측이 없어 확정 불가
- 애초에 이 두 Task가 250723 절대경로를 가리키도록 등록된 경위(누가/언제/왜, 의도적 이중화였는지 실수였는지) — UNKNOWN

**Evidence:** `Get-ScheduledTask`/`Get-ScheduledTaskInfo`/Triggers/Actions Format-List 다회(양쪽 Task) / `Get-Command python`,`python.exe` / `C:\Python314\python.exe -m pip list` / `Test-Path`+`Get-ChildItem -Recurse`(log_trace/account_runner) / `Get-ChildItem *.log,*.db -Recurse`(250723 전체) / 260511·250723 양쪽 `.env` AIRTABLE_BASE_ID 대조 / `Disable-ScheduledTask` 실행 후 재조회

**관련:** FP-039, INC-029

---

## ERR-053 | heartbeat_monitor.py 예약 작업(SNS_HeartbeatMonitor_Independent) — Modern Standby 구간에서 71회(약 5시간47분) 미실행, WakeToRun=False가 근본 원인으로 확정

**Type:** Infrastructure / Task Scheduler 설정 (not application code)

**발견 경위:** 세션 시작 점검 중 `logs/heartbeat_monitor.log` 마지막 기록이 `2026-07-10 06:11:29`에서 멈춰있고 이후 신규 기록이 전혀 없음을 발견. 최초에는 "heartbeat_monitor.py 프로세스가 죽었다"로 판단했으나, 이는 스크립트 실제 경로(`tools/heartbeat_monitor.py`, 프로젝트 루트 아님)를 잘못 가정한 조사에 근거한 성급한 결론이었음 — README.md 확인 후 5분 주기 Task Scheduler 트리거 기반 스크립트(상시 프로세스 아님)임을 파악하고 재조사함.

**Raw:**
- `Get-ScheduledTaskInfo -TaskName "SNS_HeartbeatMonitor_Independent"` → `LastRunTime: 2026-07-10 06:11:28`, `LastTaskResult: 0`, `NextRunTime: 2026-07-10 12:11:27`, **`NumberOfMissedRuns: 71`**
- `Get-ScheduledTask ... | Select-Object Settings` → `WakeToRun: False`, `DisallowStartIfOnBatteries: True`, `StartWhenAvailable: True`
- `Get-WinEvent Microsoft-Windows-Kernel-Power`(직전 8시간): 04:11~08:25 구간 15~40분 간격 Modern Standby 진입/탈출 반복, 이후 08:25:16 진입 → 11:16:28 Power Button 탈출까지 **약 2시간51분 연속 절전** — 이 구간 전체에서 트리거 재발동 기록 없음
- 06:11:28(마지막 정상 실행) ~ 확인 시점(11:56) 경과 약 5시간45분 ÷ 5분 주기 ≈ 69회로, `NumberOfMissedRuns=71`과 근사 일치(오차는 StartBoundary 오프셋 기인 추정)
- 비교 대상 `SNS_Watchdog_AutoStart`: `NumberOfMissedRuns: 0`, `NextRunTime:` 없음 — 이 Task는 로그온/부팅 시 1회성 트리거로 상시 프로세스(watchdog.ps1)를 기동하는 구조라 반복 트리거 자체가 없음. 그래서 절전에서 깨면 이미 떠 있던 프로세스가 자연히 재개되어 `watchdog.log`에 06:16:18부터 HEARTBEAT가 스스로 재개된 것으로 확인됨 — heartbeat_monitor.py 구조와의 핵심 차이.

**Root Cause:** **확정.** `SNS_HeartbeatMonitor_Independent`는 5분 간격 반복 트리거 Task이며 `WakeToRun=False`로 등록되어 있어, 시스템이 Modern Standby 상태인 동안 Windows Task Scheduler가 트리거를 발동시키지 못하고 조용히 건너뜀(에러/경고 없이 `NumberOfMissedRuns`로만 집계). watchdog.ps1(로그온 1회 트리거 + 상시 루프 프로세스)과 heartbeat_monitor.py(반복 트리거 + 매회 신규 프로세스 기동)는 절전 복원력이 근본적으로 다른 구조이며, "watchdog이 죽어도 별도로 감시한다"는 heartbeat_monitor.py의 설계 목적 자체가 watchdog을 못 잡아내는 것과 동일한 원인(Modern Standby)에 의해 함께 무력화될 수 있는 구조적 결함으로 확인됨.

**Fix:** 미적용 — 사용자 승인 대기 중. 후보: (1) 해당 Task `WakeToRun=True`로 변경(배터리 소모 트레이드오프 있음), (2) heartbeat_monitor.py를 watchdog.ps1처럼 상시 루프 프로세스로 재설계, (3) Modern Standby 자체를 이 머신에서 비활성화(전원 정책 변경, 별도 트랙 — 영향 범위 큼).

**Prevention:** 반복 트리거 기반 Task Scheduler 작업 등록 시 `WakeToRun` 값을 점검 체크리스트에 명시적으로 포함할 것. `NumberOfMissedRuns`를 상시 감시 지표에 추가하는 방안 검토(현재 어떤 감시 계층도 이 필드를 참조하지 않음 — 이번 조사에서 최초로 참조됨).

**Evidence:** `Get-ScheduledTaskInfo`/`Get-ScheduledTask...Settings`(양쪽 Task) Format-List / `Get-WinEvent Microsoft-Windows-Kernel-Power`(8시간) / `Get-Content watchdog.log`(grep 06:0·06:1·재시작·restart·kill) / `Get-Content heartbeat_monitor.log`(tail) / `tools/heartbeat_monitor.py`, `README.md`, `watchdog.ps1` 소스 확인 / `Get-CimInstance Win32_Process`(부모-자식 PID 대조)

**관련:** ERR-047, ERR-050, ERR-051, ERR-052, INC-028, FP-040

---

## ERR-054 | SNS_Watchdog_AutoStart 예약 작업도 WakeToRun=False로 등록되어 있었음(FP-040과 동일 클래스 취약점) — 관리자 권한으로 WakeToRun=True 적용, XML/taskinfo diff로 부작용 없음 실증

**Type:** Infrastructure / Task Scheduler 설정 (not application code)

**발견 경위:** ERR-053/FP-040(heartbeat_monitor.py Modern Standby 미실행) 조사 종료 후, PENDING-A(NSSM 전환 검토) 관련 작업 중 `SNS_Watchdog_AutoStart` Task 설정을 재확인하다 이 Task 역시 `WakeToRun: False`로 등록되어 있음을 확인.

**Raw (변경 전):**
- `Get-ScheduledTask ... Settings` → `WakeToRun: False`, `RestartCount: 3`, `RestartInterval: PT1M`, `DisallowStartIfOnBatteries: True`
- Action: `powershell.exe -ExecutionPolicy Bypass -File watchdog_task_wrapper.ps1`
- Trigger: `Delay: PT1M` 반복 패턴 2건(로그온/부팅 계열 추정)

**1차 시도(비관리자 권한) 실패:** `Set-ScheduledTask` → `Access is denied` (HRESULT `0x80070005`). 변경 후 State/taskinfo 재확인 결과 변경 전과 완전 동일 — 부수효과 없이 순수 실패로 확인.

**2차 시도(관리자 권한) 성공:**
- `Export-ScheduledTask`로 before.xml/after.xml 스냅샷 확보(`snapshots/watchdog_wakeup_260710/`)
- `Set-ScheduledTask -Settings`로 `WakeToRun=True` 적용
- XML diff(`Compare-Object`): 변경 라인 단 1개(`<WakeToRun>true</WakeToRun>` 추가) — 다른 필드 변경/리셋 없음
- taskinfo diff: `LastRunTime`/`LastTaskResult`(2147943467) 변경 전후 완전 동일 — 예약 인스턴스 영향 없음
- 최종 확인: `State: Ready` 유지, `WakeToRun: True` 반영 확인

**Root Cause:** N/A — 버그가 아니라 설정 누락(FP-040과 동일 원인 클래스: Task 등록 시 `WakeToRun` 기본값(False)을 점검하지 않음).

**Fix:** 적용 완료 — `WakeToRun: True`로 변경(관리자 권한). 단, 이 Task는 로그온/부팅 1회성 트리거 + 상시 루프 프로세스 구조라 FP-040 본문이 규정한 "반복 트리거+Modern Standby" 재현조건과 완전히 같지는 않음 — 예방 차원 적용이며, 실제 Modern Standby 구간에서의 효과 검증은 대상 외.

**Prevention:** FP-040 예방안("WakeToRun 점검 체크리스트화")을 heartbeat_monitor뿐 아니라 이 프로젝트의 모든 Task Scheduler 등록 Task에 전수 적용.

**Evidence:** `snapshots/watchdog_wakeup_260710/{before,after}.xml`, `taskinfo_{before,after}.txt` (gitignore 대상, 로컬 보존, git 미추적)

**관련:** FP-040, ERR-053

---

## ERR-055 | backup(14) zip 크기 이상(9.14MB, backup(13) 172MB 대비 급감) — 프로세스 점유로 일부 파일 압축 누락 추정, 전체 정지 후 backup(15) 재생성(174,715KB)으로 정상 확인

**Type:** Operational / 백업 무결성

**발견 경위:** backup(14)(260710_2332) 생성 시 db 4개 파일은 SQLite Online Backup API로 무중단 안전복사 성공 + 오류 0건으로 정상 판정했으나, 사용자가 Windows 탐색기에서 backup(13)(172MB) 대비 파일 크기(9.14MB)를 비교하다 이상 발견.

**Raw:**
- backup(14) 생성 시점, launcher 중복 프로세스(30636/31416) + dashboard(4996/33476) + n8n(10248)이 db/log 파일을 점유 중이었음
- 최초 순수 `Compress-Archive` 시도는 `db\retry_queue.db`, `logs\n8n.log`에서 각각 "being used by another process"로 실패(zip 미생성)
- SQLite Online Backup API(db 4개) + `FileShare.ReadWrite` 강제 오픈(나머지 전체) 스테이징 방식으로 우회해 9.14MB zip 생성 — 이때 검증은 "파일 개수(2278개)"만 했고 직전 백업 대비 크기 비교를 하지 않아 이상 징후를 놓침
- 정확히 어떤 파일이 최종 누락됐는지는 raw 로그로 재확인 안 됨 — "n8n.log 등 잠금 실패로 누락"은 추정이며 확정 아님

**Root Cause:** 미확정(UNKNOWN). 조치(전체 프로세스 정지) 후 backup(15)가 174,715KB로 backup(13)과 동일 정상범위로 복귀한 것은 "프로세스 점유가 원인이었을 가능성이 높다"는 상관관계 증거일 뿐, 인과관계 확정은 아님.

**Fix:** launcher(2개)+dashboard(2개)+n8n(1개, 관리자권한 필요) 전부 정지 → backup(15)(174,715KB) 재생성 + sha256 해시 생성 완료.

**Prevention:** 백업 검증 절차에 "직전 백업 대비 크기 비교(예: ±20% 초과 시 경고)"를 파일개수 확인과 함께 표준 항목화. 프로세스 가동 중 백업 시 SQLite 외 일반 로그 파일도 잠금 충돌 가능성 있음을 사전 고지.

**Evidence:** `Get-Item SizeMB` 대조(13=172MB/14=9.14MB/15=174,715KB), zip 엔트리 수(2278개), 최초 `Compress-Archive` 실패 로그 2건

**관련:** 없음(신규, 이번 세션 ERR-054/WakeToRun 건과는 시간상 인접하나 논리적으로 무관)

**Note:** backup(14).zip은 삭제하지 않고 보존(증거 가치, 삭제 여부는 이번 범위 밖 별도 판단).

---

## ERR-056 | n8n(PID 10248, :5678)이 설계단계(DESIGN_COMPLETE, execution_owner 미구현)임에도 승인 없이 LISTENING 상태로 가동 중 발견 — 가동 원인 UNKNOWN, 우선순위 낮음으로 추가조사 보류

**발견 경위:** backup 작업 중 포트 점검(netstat) 과정에서 `:5678`(n8n 기본포트) LISTENING 발견. MASTERTREE_CONTRACT.md 기준 n8n은 WF-01~05 설계만 확정, execution_owner 미구현 — 실행 승인 이력 없는 컴포넌트.

**Raw:** netstat PID 10248 `:5678` LISTENING / CommandLine 조회 시 권한제한으로 빈 값 / 비관리자 세션 Stop-Process 2회 시도 모두 Access denied

**Root Cause:** UNKNOWN — 시작 주체/시점 미상.

**Fix:** 이번 세션 재기동 목록에서 의도적 제외, 관리자 권한으로 최종 정지 완료.

**Prevention:** 미정 — 사용자 판단상 우선순위 낮음, 현황만 기록. 단 "우선순위 낮음"은 재발방지 조치를 미루는 것이지 기록 생략 사유는 아님(Evidence Rule 우선 적용).

**관련:** ERR-052

## ERR-057 | NSSM 서비스(SNS_Watchdog)와 구 Task Scheduler(SNS_Watchdog_AutoStart)가 watchdog.ps1을 동시에 이중 실행 — PENDING-A 전환의 Phase 3(구 Task 비활성화) 누락

**발견 경위:** 260711 재부팅 후 세션에서 `logs/watchdog.log`에 `===== watchdog 시작 =====` 배너가 09:07:02와 09:07:58 두 번(56초 간격) 기록된 것을 발견. n8n 재시작 실패 알림이 짧은 간격으로 반복 발생하는 것을 계기로 원인 조사 시작.

**Raw:**
- `nssm --version` → 설치 확인(`C:\ProgramData\chocolatey\bin\nssm.exe`, 2.24-101)
- `Get-Service SNS_Watchdog` → `Status=Running, StartType=Automatic`
- `Get-CimInstance Win32_Service -Filter "Name='SNS_Watchdog'"` → `PathName=C:\ProgramData\chocolatey\lib\NSSM\tools\nssm.exe`, `ProcessId=6024`
- `Get-CimInstance Win32_Process -Filter "Name='powershell.exe'"` → PID 13008(부모=6024, 생성 09:07:01, NSSM 경유) / PID 27664(부모=2244, 생성 09:07:55) → PID 28548(부모=27664, 생성 09:07:57) — 후자 체인이 구버전 watchdog.ps1
- `Get-ScheduledTask -TaskName "SNS_Watchdog_AutoStart"` → `State=Running`(당시), `Get-ScheduledTaskInfo` → `LastRunTime=2026-07-11 09:07:57`
- 소유자 확인(`GetOwner`): 27664/28548 모두 `admin`(동일 사용자) — 단 높은 무결성 수준으로 등록되어 있어 일반 권한 세션에서 `Disable-ScheduledTask`/`Stop-Process` 모두 `Access is denied`로 실패, 관리자 PowerShell에서만 실행 가능했음(raw 재현)

**Root Cause:** `docs/PENDING_INVESTIGATIONS.md` PENDING-A(watchdog.ps1의 NSSM 전환 검토, 260710 결론남)에 따라 NSSM 서비스(`SNS_Watchdog`)가 이미 설치되어 `Automatic` 시작으로 등록되어 있었음(정확한 설치 시점·주체는 세션 기록에 없어 UNKNOWN). 그러나 기존 `SNS_Watchdog_AutoStart` Scheduled Task를 비활성화하는 후속 조치(전환의 "Phase 3")가 수행되지 않아, 재부팅마다 두 자동시작 메커니즘이 동일 스크립트(watchdog.ps1)를 병행 기동하는 상태로 방치되어 있었음. 두 인스턴스가 각자 Flask/Streamlit/ngrok/n8n 상태를 점검·재시작 시도하며 경쟁 — 이번 세션 시작 시점(09:07~09:10)의 watchdog.log에서 Streamlit/ngrok 재시작 로그와 n8n 실패 알림이 중복 기록된 것이 그 결과.

**Fix:**
1. 사용자가 관리자 PowerShell에서 `Disable-ScheduledTask -TaskName "SNS_Watchdog_AutoStart"` 실행 → `schtasks /Query /TN "SNS_Watchdog_AutoStart" /V` 재조회로 `Scheduled Task State: Disabled` 확인(raw). (`Get-ScheduledTask`의 `State` 컬럼은 "이미 떠 있는 인스턴스가 실행 중"이면 Disable 후에도 `Running`으로 표시될 수 있다는 점을 확인 — Enabled/Disabled 여부는 `schtasks /V`의 `Scheduled Task State` 필드로만 확정 가능, `Get-ScheduledTask.State`와 혼동 주의)
2. 구버전이 이미 띄워놓은 PID 27664/28548은 Disable만으로는 종료되지 않아, 사용자가 관리자 PowerShell에서 `Stop-Process -Id 27664 -Force` / `Stop-Process -Id 28548 -Force` 실행
3. 재조회 결과: `Get-Process -Id 27664,28548` → 결과 없음(종료 확인) / 남은 `powershell.exe`는 NSSM 경유 PID 13008뿐(정상) / `Get-Service SNS_Watchdog` → `Running/Automatic` 유지 / Flask(:5000)·Streamlit(:8501)·ngrok(:4040) 전부 LISTENING 유지(이번 정리 작업으로 인한 서비스 영향 없음 확인)

**Prevention:** FP-042 참조 — 전환(migration) 작업은 신규 설치와 구 메커니즘 제거를 한 세션 내에서 짝지어 완료하거나, 부득이 나눌 경우 `CURRENT_RUNTIME_CONTEXT.md`에 "구 메커니즘 아직 미비활성" 같은 중간상태를 명시적으로 남길 것.

**관련:** PENDING-A, ERR-053, ERR-054, FP-040, FP-017, FP-042

## ERR-058 | NSSM 서비스 실행계정(LocalSystem) 전환의 부작용 — ngrok이 (1) Microsoft Store(MSIX) 앱이라 접근 불가 + (2) authtoken 설정이 admin 사용자 프로필 전용이라 이중으로 실패

**발견 경위:** ERR-057(구 Task 비활성화) 조치 후 재부팅 실증(260711 12:08)에서 dual-watchdog 문제는 해소됐으나, `logs/watchdog.log`에 `[FATAL] Start-Ngrok 실패: This command cannot be run due to the error: The file cannot be accessed by the system.`가 반복 발생, `:4040` 미LISTENING 확인.

**Raw:**
- `where ngrok` → `C:\Users\admin\AppData\Local\Microsoft\WindowsApps\ngrok.exe`(심볼릭 링크) → 실제 대상 `C:\Program Files\WindowsApps\ngrok.ngrok_3.39.1.0_x64__1g87z0zv29zzc\ngrok.exe`(Microsoft Store/MSIX 패키지 보호 폴더)
- `Get-CimInstance Win32_Service -Filter "Name='SNS_Watchdog'"` → `StartName=LocalSystem` / `nssm get SNS_Watchdog ObjectName` → `LocalSystem`
- 대체 경로 확인: `C:\ngrok\ngrok-v3-stable-windows-amd64\ngrok.exe`(포터블 exe, MSIX 아님) 존재 및 `ngrok version` → `3.35.0` 정상 응답
- 1차 수정(watchdog.ps1 `Start-Ngrok`을 포터블 exe 경로로 변경) 후에도 여전히 실패 — 단 `[FATAL]` 예외 없이 `Get-Process -Name ngrok` 결과만 없는 형태로 증상 변화
- `ngrok config check` → `Valid configuration file at C:\Users\admin\AppData\Local/ngrok/ngrok.yml`(admin 사용자 프로필 전용) / `C:\Windows\System32\config\systemprofile\AppData\Local\ngrok` 경로는 애초에 존재하지 않음(LocalSystem 프로필에 authtoken 없음) 확인

**Root Cause:** 두 가지 원인이 겹쳐 있었음.
1. ngrok이 Microsoft Store(MSIX) 패키지로 설치되어 있어, Execution Alias(`WindowsApps\ngrok.exe`)를 통한 실행은 대화형 사용자 세션의 패키지 활성화 인프라를 필요로 함 — `LocalSystem` 계정(비대화형, Session 0)에서는 이 활성화가 실패하며 "The file cannot be accessed by the system" 오류로 나타남. 오늘 아침(ERR-057 조치 전)엔 구 Task(admin 계정, 대화형 컨텍스트)가 우연히 ngrok을 성공시켜 왔기 때문에 이 결함이 가려져 있었음 — ERR-057에서 구 Task를 비활성화하고 NSSM(LocalSystem) 단독 운영으로 전환하면서 비로소 드러난 잠복 결함.
2. 1차 수정(포터블 exe 경로 지정)만으로는 불충분 — ngrok의 authtoken 설정(`ngrok.yml`)이 `LocalSystem`이 아닌 `admin` 사용자 프로필 하위에만 존재해, `LocalSystem` 컨텍스트에서 실행된 ngrok은 인증 정보를 찾지 못해 커스텀 도메인(`--url=danuta-overdramatic-whirly.ngrok-free.dev`) 터널을 열지 못함.

**Fix:**
1. `watchdog.ps1`의 `Start-Ngrok` 함수가 PATH 탐색(`"ngrok"`)이 아닌 명시적 포터블 경로(`C:\ngrok\ngrok-v3-stable-windows-amd64\ngrok.exe`, `$NGROK_EXE` 변수로 도입)를 사용하도록 수정
2. 사용자가 관리자 PowerShell에서 `C:\Users\admin\AppData\Local\ngrok\ngrok.yml`을 `C:\Windows\System32\config\systemprofile\AppData\Local\ngrok\ngrok.yml`로 복사(`New-Item -ItemType Directory -Force` + `Copy-Item -Force`) — 이 경로는 일반 권한은 물론 비-SYSTEM 컨텍스트의 관리자 PowerShell에서도 조회(`Test-Path`)조차 거부되는 보호 폴더라, 실제 성공 여부는 사용자가 붙여넣은 명령 실행 결과(에러 없음)로만 간접 확인 가능했음
3. 사용자가 관리자 PowerShell에서 `Restart-Service -Name "SNS_Watchdog" -Force` 실행 → watchdog.log 재확인 결과 12:33:45/12:34:48 재시도는 여전히 실패했으나 12:35:48 `[OK] ngrok 재시작 성공` + `[RECOVER] Ngrok 복구` 확인, `:4040` LISTENING(PID 23924), `http://localhost:4040/api/tunnels` 조회로 `public_url=https://danuta-overdramatic-whirly.ngrok-free.dev` 정상 응답 확인 — **최종 PASS**

**Prevention:** FP-043 신규 등록 참조 — 서비스 실행 계정을 변경(예: 대화형 사용자 → LocalSystem)할 때는 그 계정이 의존하는 모든 외부 도구의 (a) 설치 형태(일반 exe vs Store/MSIX 패키지)와 (b) 인증정보 저장 위치(사용자 프로필 vs 시스템 전역)를 함께 점검해야 함 — 스크립트 경로만 바꾸는 것으로는 불충분.

**관련:** ERR-057, FP-042, FP-043, PENDING-A

---

## ERR-059 | 학습 리뷰 그리드 실제 50건 저장 시 GET 재검증이 전부 "값 불일치"로 오탐 — 저장은 성공했으나 확인 로직이 예외를 은폐

**발견 경위:** 260712 세션 — 학습 리뷰 그리드(Training_Review_Queue PASS/BLOCK, `modules/infra/review_grid_ui.py`) 실제 운영 50건 배치에서 사용자가 확정 버튼(44 BLOCK/6 PASS)을 클릭했으나 화면에 "저장 후 확인(GET)이 일치하지 않습니다" 오류와 함께 50개 record_id 전부가 나열됨. 사용자는 "실행이 잘 됐다는 내용이 안 나온다"고 보고.

**Raw:**
- `commit_batch_with_verification()`(당시 버전)이 PATCH 50건 + 확인용 GET 50건을 연달아 호출
- 직접 재조회 결과(`get_review_status()` 47/50건 확인): 42건 BLOCK, 5건 PASS로 **정확히 저장돼 있었음** — 즉 저장(PATCH) 자체는 성공, 확인(GET) 단계만 실패로 잘못 표시됨
- 최초 가설(속도 제한)은 사용자/Codex 재조사에서 기각됨 — 실제 PATCH는 약 82초 동안 1.4~1.6초 간격(초당 5회인 Airtable 공식 제한보다 훨씬 낮음)으로 진행된 로그 확인
- 근본원인 확정: `_safe_get_status()`가 GET에서 발생하는 모든 예외(429/403/타임아웃/기타)를 구분 없이 `None`으로 변환 → `None != 기대값`이 되어 실제로는 저장 성공인 건까지 "값 불일치"로 잘못 보고

**Root Cause:** GET 재검증 단계에서 "저장이 안 된 것"과 "확인 자체가 실패한 것"을 구분하지 않고 예외를 전부 은폐한 설계 결함. 429/403/타임아웃 등 서로 다른 성격의 오류가 전부 동일하게 처리됨.

**Fix (`modules/infra/review_batch_committer.py`, `modules/infra/repository_interface.py`, `modules/infra/airtable_repository.py`, `modules/infra/review_grid_ui.py`):**
1. `VerificationError`(record_id/status_code/error_type/message) 신설, `CommitResult`/`UndoResult`에 `verification_errors`를 `mismatched_ids`와 분리해서 추가
2. `RepositoryError`에 `status_code`/`retry_after_seconds`/`original_error_type` 속성 추가, `_raise()`가 HTTP 상태·`Retry-After` 헤더를 그대로 전달, `get_review_status()`의 네트워크 예외도 원래 타입명 보존
3. 429는 `Retry-After` 기반, 5xx·타임아웃은 지수 백오프(최대 3회)로 재시도, 403·404·기타는 즉시 오류 처리(재시도 없음)
4. `actual is None`(실제 `get_review_status()`의 404 계약)을 `mismatched_ids`가 아니라 `status_code=404, error_type="NotFound"`인 `verification_errors`로 분리(1차 수정에서 누락됐던 부분, Codex 재검토로 확인 후 `_verify_one()` 공통 헬퍼로 3개 함수 통합하며 수정)
5. `verify_only(repo, expected)` 신규 — PATCH 없이 GET만으로 기존 저장 결과를 재검증
6. UI: `verification_errors` 발생 시 확정 버튼을 `disabled=True`로 잠그고 "확정 버튼을 다시 누르지 마세요" 안내, 새 배치를 받으면 자동 해제

**해당 50건 배치의 최종 처리 — 조건부 종결:**
- 원본 선택(체크 상태)은 브라우저 세션에만 있었는데, 오류 이후 해당 탭이 새로고침되어 session_state가 초기화됨 — 원본 44 BLOCK/6 PASS 선택 기록 자체가 유실됨
- Airtable 현재값으로 "기대값"을 역산해서 재검증하면 자기 자신과 비교하는 무의미한 검증이 되므로(Codex 지적), 그 배치에 대한 완전한 재검증은 구조적으로 더 이상 불가능
- 확보 가능한 최선의 증거로 종결: 47/50건 직접 재조회 결과 42 BLOCK + 5 PASS로 정확히 저장 확인, 나머지 3건은 UNKNOWN(화면 캡처 전사 과정의 오타로 추정되나 미확정), PENDING 건수가 그 배치 처리 전후로 50건 이상 감소해 지금 20건까지 줄어든 것과 정황상 일치
- 회장님 결정(260712): 이 50건 건은 위 증거로 **조건부 종결**, 신규 20건 배치부터는 수정된 파이프라인으로 처음부터 정식 절차 진행

**Prevention:** FP-044 신규 참조 — 검증(재확인) 로직에서 예외를 뭉뚱그려 처리하면 "확인 실패"와 "데이터 실패"를 구분할 수 없게 되고, 실제로는 성공한 작업이 실패로 오탐될 수 있다.

**관련:** FP-044, INC-032, docs/VALIDATION_EVIDENCE_training_review_3B_260712.md

## ERR-060 | NSSM 서비스(SNS_Watchdog) 자체가 예기치 않게 종료 + 등록된 nssm.exe 실행파일이 디스크에서 사라짐 — 서비스 등록 완전 재생성으로 해소, 원인 UNKNOWN

**발견 경위:** 260712 세션 재개 중 상태 재확인(`Get-Service SNS_Watchdog`) 결과 `Stopped` 확인 — watchdog.log는 계속 heartbeat를 남기고 있어 모순 발견, 조사 진행.

**Raw:**
- `Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Service Control Manager'; Id=7034}` → `2026-07-11 23:08:47 — The SNS_Watchdog service terminated unexpectedly. It has done this 1 time(s).`
- 이후 `Get-Service SNS_Watchdog` → `Stopped`, `Start-Service` 시도 → `Cannot open SNS_Watchdog service` (일반 권한) / `Cannot start service` (관리자 권한에서도 실패)
- `sc.exe failure SNS_Watchdog ...` (복구 옵션 설정 시도) → `[SC] ChangeServiceConfig2 FAILED 2: The system cannot find the file specified.`
- `where nssm` → `C:\ProgramData\chocolatey\bin\nssm.exe`(shim)는 존재하나 실행 시 `Cannot find file at '..\lib\NSSM\tools\nssm.exe' ... 이것은 보통 파일이 없어졌거나 이동되었음을 나타냅니다` 오류
- `C:\ProgramData\chocolatey\lib\nssm\` 폴더 확인 결과 `nssm.nupkg`/`.nuspec`/`.txt` 메타데이터만 존재, 실제 실행파일이 들어있어야 할 `tools\` 하위 폴더 자체가 없음
- `nssm get SNS_Watchdog Application` (파일 복구 후 재시도) → `Error querying service "SNS_Watchdog"! QueryServiceConfig(): ...` — 서비스 레지스트리 등록 자체가 손상되어, 실행파일을 복구해도 조회조차 불가능한 상태로 확인
- 원인 조사(read-only): `git log`/프로젝트 파일 mtime — 크래시 시각(23:08) 전후 30분 구간에 커밋·파일 변경 없음 / `chocolatey.log` — 그날 choco 실행은 새벽 01:01:28(`choco install nssm -y`, User-Agent에 `claude` 포함 — 이전 Claude 세션이 최초 설치한 기록으로 확인) 단 1건뿐, 23:00대 실행 없음 / `Get-MpThreatDetection`, Defender Operational 로그 — 실제 탐지·격리 이벤트 없음(23:08:21에 정기 상태보고 1151 이벤트가 있으나 22:08:21에도 동일 패턴 존재해 매시간 정기 보고로 판단, 크래시와 인과관계 낮음)

**Root Cause:** ~~UNKNOWN~~ → **260713 Note에서 확정**(아래 참조). 최초 작성 시점 기준: `nssm.exe` 실행파일이 정확히 언제/왜 디스크에서 사라졌는지(우발적 삭제, 디스크 정리 도구, 백신 격리, chocolatey 자체 결함 등) 확정할 근거를 찾지 못함 — git/chocolatey.log/Defender 탐지 로그 어디에도 크래시 시각과 인과관계가 있는 흔적이 없음. 파일 소실 시점과 서비스 크래시(23:08:47) 시점의 선후 관계도 직접 증명되지 않음(둘이 근접했다는 정황뿐).

**Fix:**
1. 고아 상태로 남아있던 이전 watchdog.ps1 인스턴스(PID 23828/27220/1924 — 서로 다른 재시작 시점에 생성된 것으로 추정되는 3세대)를 순차 확인 후 `Stop-Process -Force`로 전부 정리(일부는 일반 권한, 일부는 관리자 권한 필요)
2. `choco install nssm -y --force`로 실행파일 재설치 확인(`nssm version` 정상 응답) — 그러나 서비스 자체는 여전히 시작 불가(등록 손상은 별도 문제였음)
3. `nssm remove SNS_Watchdog confirm` → `nssm install SNS_Watchdog "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" "-ExecutionPolicy Bypass -File C:\SNS_24AutoProject_260511\watchdog.ps1"`로 서비스 완전 재생성, `AppDirectory`/`Start=SERVICE_AUTO_START`/`AppExit Default=Restart`/`AppRestartDelay=60000` 재설정
4. `sc.exe failure SNS_Watchdog reset= 86400 actions= restart/60000/restart/60000/restart/60000`로 **서비스 본체가 죽는 경우에도** Windows SCM이 자동 재시작하도록 신규 보강(기존엔 NSSM의 `AppExit`만 있어 자식 프로세스 크래시만 커버, 서비스 자체 크래시는 무방비였음 — 이번 사고의 직접 원인)
5. 검증: `Get-Service` → `Running/Automatic`, `nssm get ...` 전체 조회 정상, `sc.exe qfailure` → `SUCCESS`(복구 옵션 3건 확인), `watchdog.log` 새 시작 배너 확인, Flask(:5000)/Streamlit(:8501)/ngrok(:4040) 동일 PID로 무중단 유지 확인 — **PASS**

**Prevention:** FP-045 신규 참조 — `Get-Service`의 상태값과 실제 프로세스 생존 여부가 어긋날 수 있다는 것, 그리고 자식 프로세스 크래시 복구(NSSM `AppExit`)와 서비스 본체 크래시 복구(`sc.exe failure`)는 서로 다른 계층이라 둘 다 설정해야 한다는 것.

**관련:** ERR-057, ERR-058, FP-042, FP-043, FP-045, INC-033, PENDING-A

**[2026-07-13 00:09 추가 Note — 근본원인 확정: 백신(AhnLab Safe Transaction) PUP 오탐·치료로 인한 파일 삭제]**

사용자가 **AhnLab Safe Transaction**(백신/거래보호 프로그램, 이전 조사에서 Windows Defender만 확인하고 놓쳤던 별도 제품)의 실시간 탐지 팝업을 직접 화면에서 확인·제보: 진단명 `Unwanted/Win.NSSM.C242...`(파일 경로 `C:\ProgramData\chocolatey\lib\nssm\tools\nssm.exe`), 상태 "치료 가능"으로 표시된 탐지 이력이 존재함 — NSSM이 서비스 래퍼 도구 특성상 PUP(잠재적 유해 프로그램) 휴리스틱에 걸리는 것으로 확인. 사용자가 과거 이 탐지에서 "치료하기"를 클릭한 이력이 있었던 것으로 추정되며, 이것이 `nssm.exe` 파일이 디스크에서 사라진 진짜 원인.

**Raw:** AhnLab Safe Transaction "환경 설정 > 보안 > 검사 대상 설정"에 `유해 가능 프로그램` 항목이 체크되어 있었음(스크린샷 확인) — 이 카테고리 검사가 nssm.exe를 지속 재탐지·재격리하는 구조. 재복구 직후(260712 세션)에도 동일 탐지 팝업이 재차 발생해 실시간으로 재현 확인.

**Fix(추가):** 사용자가 AhnLab Safe Transaction 설정에서 `유해 가능 프로그램` 검사 체크 해제 → 이후 탐지 팝업(치료 대상)을 "닫기"로 처리(치료/삭제 아님) → nssm.exe 파일·서비스 상태 재확인 결과 정상 유지 확인(00:08:25 기준 `Get-Service Running`, `watchdog.log` heartbeat 지속). 이 프로그램 자체에 파일 단위 예외처리(화이트리스트) 기능은 없어(보안/기타 탭 확인), 카테고리 단위 차단 해제가 유일한 옵션이었음.

**Prevention(추가):** 이 시스템에 nssm.exe 외 다른 서비스 래퍼/관리 도구를 설치할 경우 동일한 PUP 오탐 위험이 있음을 인지 — 설치 직후 AhnLab Safe Transaction 탐지 팝업이 뜨는지 확인하는 것을 표준 점검 항목에 추가.

**관련(추가):** ERR-058(같은 세션에서 확인된 유사 계열 이슈는 아니지만 참고), FP-045

## ERR-061 | 가격 자동응답이 문의 상품을 특정하지 못한 채 최신 가격을 자동발송 — Gate C(`PRICE_AUTO_REPLY_ENABLED`) 코드 구현·테스트 완료(커밋 `c1c90b2` 완료·운영 미배포)

**발견 경위:** 260713 `docs/design/DM_RELAY_COMMERCE_RFC.md`(Buyer↔회장님↔Supplier 릴레이 판매대행 시스템) 설계검토(§8/§13) 중 `modules/dm/dm_auto_reply.py`의 `get_base_price()`가 문의 대상 상품을 특정하지 않고 "Instagram_Posts 중 price>0 최신값"을 그대로 자동응답에 사용하는 구조적 결함 확인. buyer 클레임이나 오발송 신고로 발견된 것이 아니라 설계 검토 중 발견.

**Raw:** `get_base_price()`(dm_auto_reply.py:104-118 부근)가 상품 식별 로직 없이 최신 등록가만 반환. `dm_receiver.py`의 DM 웹훅이 어느 게시물(media_id)에 대한 문의인지 저장하지 않아, 애초에 상품 특정 자체가 불가능한 구조.

**Root Cause:** DM 자동응답(12단계, 260512 이전 구현) 당시 Post/Product 매핑 없이 "최신 등록가"를 fallback으로 채택 — 게시물이 1개일 때는 문제없었으나 다품목 운영 시 buyer가 문의한 상품과 무관한 가격이 발송될 수 있는 구조.

**Fix:** Gate C(`docs/design/DM_RELAY_COMMERCE_RFC.md` §17) — `PRICE_AUTO_REPLY_ENABLED` 플래그 신규 도입(기본값 `false`). `false`일 때 가격 대신 상품확인(링크·번호·스크린샷) 요청 템플릿으로 대체(buyer 접수응답 자체는 유지). 추가로 Codex 교차검증 4라운드를 거쳐: 발송실패/예외 시 `bridge_status` 오갱신·팔로업 오예약 방지, Telegram PII 마스킹(단 **신규 `send_telegram_price_pending()` 알림에만 적용** — 기존 `dm_receiver.send_telegram()`의 전체 IGSID·원문 노출은 미해결, P0-1 대상), `(sender_igsid, 정규화된 문의문)` 키 + `threading.Lock` 기반 원자적 임시 중복방지(Airtable 스키마 변경 없음, 3분 TTL) 동반 수정. **현재 코드 구현·테스트 완료 상태이며 git commit·프로세스 재시작·Canary 검증 전 — 운영상 실제 차단은 재시작+Canary 검증 후 확정.**

**재활성화 조건:** 단순 "P1-B 완료"가 아니라 **Post/Product 매핑 가격조회 구현 + `price_verified_at` 기준 24시간 유효기간 검증 통과 후**에만 `PRICE_AUTO_REPLY_ENABLED=true` 전환.

**Prevention:** FP-046 참조.

**관련:** FP-046, INC-034, `docs/design/DM_RELAY_COMMERCE_RFC.md` §8/§13/§17, `modules/dm/dm_auto_reply.py`
