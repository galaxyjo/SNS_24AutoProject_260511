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
**Status:** 🔴 OPEN — 미해결, watchdog.ps1 현재도 미기동 상태 (launcher/main.py는 2026-07-05 20:10:28 별도/불명 경로로 기동 중, watchdog 감시 없음)
**Evidence:** `schtasks /Query /TN "SNS_Watchdog_AutoStart" /V` 출력 / `logs/watchdog.log` tail(마지막 2026-07-01 23:36:55) / `Get-WinEvent -Id 12` 9건(06-29 20:12 이후) / `powercfg /a`(빠른 시작 "현재 시스템 정책에서 사용하지 않도록 설정" 확인 — cold boot 확정) / `Get-Process python` (PID 14740/5524, StartTime 2026-07-05 20:10:28~29) / `Get-CimInstance Win32_Process -Filter "Name='powershell.exe'"` (watchdog.ps1 실행 중인 프로세스 없음, 2026-07-05 20:2x 시점)
**관련:** ERR-045, FP-033, INC-023, INC-025

**[2026-07-08 추가 Note]:** 별도 세션에서 Start-ScheduledTask(수동 트리거)로는 Task 실행 자체가 확인됨(ERR-050 참조). 단, 이는 BootTrigger/LogonTrigger 자동 발동 여부를 검증한 것이 아니므로 본 항목의 근본원인(9회 재부팅 무재실행)은 여전히 UNKNOWN. ERR-047 Status는 변경 없음.

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
**Status:** 🟡 MITIGATED (근본원인 미해결, OPEN 유지)
**Evidence:** watchdog_wrapper.log(PID=29076 START 기록) / watchdog_wrapper_stdout.log(HEARTBEAT 5회+) / Win32_Process 조회 3회(direct 임시 Task 소멸 확인, 22908 단독 재확인 2회) / Task XML Format-List(wrapper 경로 확정)
**다음 세션 승계 (미실행):** (a) 실제 재부팅으로 BootTrigger/LogonTrigger 자동 발동 여부 검증(ERR-047 원인 규명), (b) 실제 재부팅으로 wrapper 경로 생존 여부 검증(ERR-050 완화 확인), (c) 조건 4개 분리 A/B 테스트(stdout/stderr redirect → -NoProfile → WorkingDirectory → 절대경로), (d) 사망 시점 LastTaskResult 종료코드 재조회, (e) PowerShell/Task Scheduler Operational 이벤트 로그 확인
**관련:** ERR-047, FP-017, ERR-021, INC-023
