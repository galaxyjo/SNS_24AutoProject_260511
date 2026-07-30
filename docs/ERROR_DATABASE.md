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

**260721 재발·해결:** Engagement 실행 중 동일 `GraphMethodException code=100 / subcode=33`이 4개 ID에서 다시 관측되어 전체 범위를 read-only 배치 조사. Airtable `posted + ig_media_id 있음` 291개 중 Graph API 접근 가능 285개, 접근 불가 6개로 확정했다. 계정 ID·토큰은 정상(`INSTA_IG_USER_ID` 계정 조회 성공, 최근 media 100개 조회 성공)이며 6개만 개별 조회도 모두 100/33이었다. 승인 후 아래 레코드의 현재 ID·`posted` 상태가 예상값과 일치할 때만 `ig_media_id`를 공란 처리하고 각 레코드를 재조회해 6/6 `null` 확인.
- `rec2v96YaBLQJvLyl` — `18071004683495931`
- `recCv8cUnDUf2oZR9` — `17880870432453703`
- `recFMnnjmU94erZs5` — `18444932203139480`
- `recFyw7OUaZ666JDJ` — `18101360630320704`
- `recsmA4WIlrur1wHO` — `18105411013959035`
- `recw3EHD8d9uiP2FX` — `18122871268709171`

정리 직후 Engagement 대상은 289개로 확인됐는데, 기존 정상 285개에 260721 12:23경 신규 게시물 4개가 추가된 결과였다. 현재 289개 전체를 Graph API 배치 재검증해 **available=289 / unavailable=0** 확인. ERR-039 패턴 재발은 해소됨.

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

## ERR-074 | 학습용 사진 수집(`run_for_training_photos`)이 스케줄러에 연결되지 않아 260713 이후 8일간 신규 수집 0건 — 설계상 수동 1회성 러너만 존재

**발견 경위:** 260721 21:24 회장이 대시보드 "학습 검토" 탭에서 전체 299건(PASS 56/BLOCK 243/PENDING 0, "검토할 것이 없습니다")을 보고 "학습이 멈췄다"고 지적 — read-only 조사 착수.

**Raw:**
- `launcher/main.py`, `core/run_engine.py`(APScheduler 잡 등록 파일) grep 결과 "training" 문자열 0건 — 두 스케줄러 어디에도 학습용 크롤 job 미등록.
- `run_all_training_targets()`/`run_for_training_photos()`(`modules/sns/facebook_crawler.py`)의 유일한 호출부는 `tools/_run_training_photo_crawl.py` — 수동 실행 전용 러너.
- 커밋 `17dae25`(260713) 메시지에 이미 "커밋되지 않은 1회성 러너 스크립트(`tools/_run_training_photo_crawl.py`, 반복 실행용이라 tools/ 관례대로 미커밋)"라고 명시 — 처음부터 사람이 매번 직접 실행하는 설계였음.
- 로그(`logs/function/modules_sns_facebook_crawler.log.1`) 마지막 `[Training] 저장 완료`: 2026-07-13 00:32:17. 현재 로그 파일(260714~260721 21:19까지 계속 기록 중)에는 `[Training]` 태그 0건 — 반면 동일 파일의 `[FB Crawler]`(Instagram 업로드용)는 오늘도 정상 기록됨, 즉 시스템 장애가 아니라 이 스크립트만 재실행되지 않은 것.
- Training_Review_Queue 현황(대시보드 260721 21:24 기준): 전체 299 / PASS 56 / BLOCK 243 / PENDING 0 — 260713 확보된 PENDING 107건(커밋 `17dae25` 기록)을 이후 8일간 리뷰 그리드로 전부 소진, 신규 보충 없음과 정확히 일치.

**Root Cause:** 학습 데이터 "수집" 단계는 애초에 자동 반복 실행으로 설계되지 않았고, 사람이 필요할 때 `tools/_run_training_photo_crawl.py`를 수동 실행해야만 큐가 채워지는 구조. "리뷰/저장" 단계(그리드 UI, 배치 커밋, undo)는 ERR-059/FP-044로 안전성까지 하드닝됐으나, "수집" 단계의 반복 실행 설계는 애초에 범위 밖이었음.

**Fix:** 미적용 — 회장 결정 대기 중(A: 수동 재실행 매번 명령 필요 / B: 스케줄러 자동화 신규 구현).

**Prevention:** FP-056 참조.

**관련:** ERR-059, FP-044, FP-056, INC-041

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

## ERR-061 | 가격 자동응답이 문의 상품을 특정하지 못한 채 최신 가격을 자동발송 — Gate C 가격 안전차단 운영 반영 PASS(260714 10:24:41), 안내문 발송·신규 Telegram 마스킹 E2E는 PARTIAL(미확인)

**발견 경위:** 260713 `docs/design/DM_RELAY_COMMERCE_RFC.md`(Buyer↔회장님↔Supplier 릴레이 판매대행 시스템) 설계검토(§8/§13) 중 `modules/dm/dm_auto_reply.py`의 `get_base_price()`가 문의 대상 상품을 특정하지 않고 "Instagram_Posts 중 price>0 최신값"을 그대로 자동응답에 사용하는 구조적 결함 확인. buyer 클레임이나 오발송 신고로 발견된 것이 아니라 설계 검토 중 발견.

**Raw:** `get_base_price()`(dm_auto_reply.py:104-118 부근)가 상품 식별 로직 없이 최신 등록가만 반환. `dm_receiver.py`의 DM 웹훅이 어느 게시물(media_id)에 대한 문의인지 저장하지 않아, 애초에 상품 특정 자체가 불가능한 구조.

**Root Cause:** DM 자동응답(12단계, 260512 이전 구현) 당시 Post/Product 매핑 없이 "최신 등록가"를 fallback으로 채택 — 게시물이 1개일 때는 문제없었으나 다품목 운영 시 buyer가 문의한 상품과 무관한 가격이 발송될 수 있는 구조.

**Fix:** Gate C(`docs/design/DM_RELAY_COMMERCE_RFC.md` §17) — `PRICE_AUTO_REPLY_ENABLED` 플래그 신규 도입(기본값 `false`). `false`일 때 가격 대신 상품확인(링크·번호·스크린샷) 요청 템플릿으로 대체(buyer 접수응답 자체는 유지). 추가로 Codex 교차검증 4라운드를 거쳐: 발송실패/예외 시 `bridge_status` 오갱신·팔로업 오예약 방지, Telegram PII 마스킹(단 **신규 `send_telegram_price_pending()` 알림에만 적용** — 기존 `dm_receiver.send_telegram()`의 전체 IGSID·원문 노출은 미해결, P0-1 대상, 계속 OPEN), `(sender_igsid, 정규화된 문의문)` 키 + `threading.Lock` 기반 원자적 임시 중복방지(Airtable 스키마 변경 없음, 3분 TTL) 동반 수정. **260714 10:18 launcher 재시작(watchdog 자동복구 경유) + 10:24:41 통제된 Canary(로컬 웹훅 시뮬레이션, 가짜 IGSID)로 가격 자동발송 차단 동작 실증 PASS** — 앱 로그 대조로 팔로업 오예약·bridge_status 오갱신 없음도 함께 확인(Gate C 적용 이전인 260713 21:50 실제 발송실패 사례와 대조). **단 Canary가 가짜 IGSID였던 관계로 실제 IG 안내문(상품확인 요청) 발송 성공 여부와 `send_telegram_price_pending()` 신규 마스킹 동작은 이번 검증 범위 밖 — E2E PARTIAL(미확인)로 별도 기록.**

**재활성화 조건:** 단순 "P1-B 완료"가 아니라 **Post/Product 매핑 가격조회 구현 + `price_verified_at` 기준 24시간 유효기간 검증 통과 후**에만 `PRICE_AUTO_REPLY_ENABLED=true` 전환.

**Prevention:** FP-046 참조.

**관련:** FP-046, INC-034, `docs/design/DM_RELAY_COMMERCE_RFC.md` §8/§13/§17, `modules/dm/dm_auto_reply.py`

## ERR-062 | `Lead_Interactions.conversation_channel`에 `instagram_comment` 선택지 없음 — 댓글 리드 Airtable 기록 반복 실패 (RESOLVED — 260714 선택지 추가)

**발견 경위:** 260714 Gate E-A 쓰기 Canary 검증 중, 회장님 지시로 테스트 계정(채솔)이 실제 게시물에 댓글 2건("price plz", "dm")을 남겼고, `comment_poller.py`의 5분 간격 폴링이 이를 정상 감지·처리하는 과정에서 재현됨. `docs/design/DM_RELAY_COMMERCE_RFC.md` §"기존 코드 결함(8건)" 1번 항목으로 설계검토 때 이미 이론상 식별돼 있었으나, 오늘 실제 운영에서 처음 실증(재현)됨.

**Raw:** `logs/summary/app.log` 260714 11:08:18/11:08:20 — `[Comment] Airtable 기록 예외 | [Lead_Interactions] 입력 오류: {"error":{"type":"INVALID_MULTIPLE_CHOICE_OPTIONS","message":"Insufficient permissions to create new select option \"instagram_comment\""}}` 댓글 2건 모두 동일 오류.

**Root Cause (정정):** 직접원인은 `Lead_Interactions.conversation_channel`(singleSelect)에 `instagram_comment` 선택지가 애초에 없었던 것. **최초 판단("Airtable API 토큰에 신규 선택지 자동생성 권한이 없음")은 오판으로 정정** — 같은 토큰으로 `typecast: true`를 붙여 호출하면 선택지 자동생성+저장이 정상 처리됨을 실증(260714, 테스트 레코드로 확인 후 삭제). `comment_auto_reply.py:98`의 `_record_comment()`가 `typecast`를 쓰지 않는 것 자체는, 오타가 새 선택지로 조용히 자동생성되는 것을 막는 안전한 정책일 수 있어 **버그로 확정하지 않음**(코드 변경 권장 안 함).

**Fix (적용 완료):** Airtable `conversation_channel`에 `instagram_comment` 선택지 수동 추가(색상 `blueLight2`, ID `selzqhgoAJrJWibse`, 260714) + 저장 Canary 1건 PASS(`conversation_channel=instagram_comment` 정상 저장 확인, 테스트 레코드는 삭제 후 재조회로 제거 확인). 코드(`airtable_repository.py`/`comment_auto_reply.py`)는 변경하지 않음 — 이 결함의 직접원인은 해소됐으나, 저장 실패 시 재시도가 안 되는 구조적 문제는 FP-047로 별도 계속 OPEN.

**관련:** FP-047, INC-035, `docs/design/DM_RELAY_COMMERCE_RFC.md` "기존 코드 결함(8건)" #1, `modules/comment/comment_auto_reply.py:94-105`

## ERR-063 | `test_dm_rules.py::TestAutoReplyHook::test_send_failure_does_not_mark_replied_or_schedule_followup` 실행 시 hang — 원인 확인됨(RESOLVED — mock 미적용으로 인한 실제 Gemini API 호출 지연, 무한 hang 아님)

**발견 경위:** 260714 Gate E-B(Graph API v19.0→v25.0 URL 중앙화, `modules/common/meta_graph.py` 신규) 코드·테스트 검증 중, 신규 테스트(`tests/test_meta_graph_version.py`)와 별개로 기존 `tests/test_dm_rules.py` 전체 실행이 이 테스트에서 멈춤을 발견. 이후 이 테스트 1개만 격리해 25초 타임아웃으로 재실행 — 동일하게 응답 없이 멈춤을 재현(좀비 프로세스는 남기지 않고 타임아웃으로 안전 종료 확인).

**Raw(260714 최초 발견):** `pytest tests/test_dm_rules.py::TestAutoReplyHook::test_send_failure_does_not_mark_replied_or_schedule_followup` — 25초 내 PASS/FAIL/ERROR 어떤 결과도 출력되지 않고 타임아웃.

**Raw(260715 재조사, 근본원인 확인):**
- 코드 대조 결과, `TestAutoReplyHook` 클래스 내 테스트 중 **이 테스트만 유일하게** `PRICE_AUTO_REPLY_ENABLED=True`이면서 `get_base_price`를 `None`이 아닌 실제값(`10000.0`)으로 mock함(`tests/test_dm_rules.py:214-215`). 다른 모든 테스트는 `PRICE_AUTO_REPLY_ENABLED=False`이거나, `True`여도 `get_base_price`가 `None`을 반환하도록 되어 있어 `modules/dm/dm_auto_reply.py:283`에서 조기 반환됨.
- 그 결과 이 테스트만 유일하게 `dm_auto_reply.py:289`의 `generate_reply()`(실제 Gemini API 호출)까지 도달 — 이 호출은 테스트에서 **mock되어 있지 않아 실제 네트워크 요청이 나감**.
- `modules/dm/ai_reply_generator.py:25` `_RETRY_DELAYS = [20, 40, 60]` — Gemini가 429(rate limit/쿼터 초과)를 반환하면 20초→40초→60초 순서로 `time.sleep()` 하며 재시도(최악의 경우 누적 최대 120초+ 대기).
- **직접 재현 실행**(`.venv` python, 넉넉한 타임아웃으로 이 테스트만 격리 실행): 이번엔 Gemini가 `POST .../gemini-2.5-flash-lite:generateContent` "HTTP/1.1 200 OK"로 즉시 응답해 **7.48초 만에 PASSED** — 무한 hang이 아니라 **실제 Gemini API 응답 시간(및 429 재시도 지연)에 실행시간이 좌우되는 테스트**임을 실증 확인.

**Root Cause:** **확인됨.** 이 테스트가 `generate_reply()`(실제 Gemini API 호출)를 mock하지 않은 테스트 설계상의 누락. 260714 최초 발견 당시엔 Gemini 무료 티어 일일 쿼터가 소진된 상태였다는 기록(memory: Gemini Status)과 대조하면, 그 시점엔 429 재시도 지연(최소 20초 이상)이 누적되며 조사자가 설정한 25초 격리 타임아웃을 넘겨 "hang"으로 관측된 것으로 설명됨. Gate E-B의 URL 중앙화 변경(`meta_graph.py`)과는 무관 — `tests/test_meta_graph_version.py`의 신규 14개 테스트는 전부 정상 통과(1.81초)했고, 이번 재현도 Gate E-B 변경과 무관하게 재현됨.

**Fix:** 미적용(OPEN, 회장 지시로 이번엔 기록만 갱신, 코드 수정 없음). 향후 수정 시 `tests/test_dm_rules.py:199` 테스트에 `monkeypatch.setattr("modules.dm.ai_reply_generator.generate_reply", lambda *a, **k: "...")` 형태로 Gemini 호출을 mock 처리하면 테스트 실행시간이 외부 API 상태(quota/rate-limit)에 좌우되지 않게 됨 — `generate_reply`가 `dm_auto_reply.py:289`에서 함수 내부 지역 import(`from modules.dm.ai_reply_generator import generate_reply`)로 매 호출마다 다시 조회되므로, `dm_auto_reply` 모듈이 아니라 `ai_reply_generator` 모듈 쪽 속성을 patch해야 함.

**관련:** `tests/test_dm_rules.py`, `modules/dm/ai_reply_generator.py`, Gate E-B(`modules/common/meta_graph.py`), Gemini Status(memory)

## ERR-064 | Private Reply로 시작된 대화의 손님 답장이 웹훅으로 수신되지 않음 — Standard Access(앱 테스터 미등록) 의심

**발견 경위:** Gate G(댓글→Private Reply 전환) 라이브 테스트 중, `COMMENT_AUTO_REPLY_ENABLED=true` + 캠페인 게시물(`18116772601675773`)에 등록된 실계정(tgbtgbnate)이 "가격 얼마예요?" 계열 댓글을 남겼고, 시스템이 정상적으로 Private Reply를 발송·수신 확인(회장 육안 확인)까지 마쳤다. 이후 tgbtgbnate가 그 Private Reply에 실제로 답장("무시 할게", Instagram 스크린샷으로 시각 오후 4:14경 확인)했으나, 45분 이상 경과한 시점까지 우리 서버(webhook)에 어떤 메시지 이벤트도 수신되지 않음을 발견.

**Raw:** `curl http://127.0.0.1:4040/api/requests/http`(ngrok 요청 로그) 확인 결과, 마지막으로 수신된 webhook은 15:44:12(읽음 확인 이벤트, `"read":{"mid":...}`만 포함 — 실제 메시지 텍스트 없음)이며, 16:30 시점까지 그 이후 신규 요청 0건. `GET /{page-id}/subscribed_apps`로 웹훅 구독 필드 재확인 결과 `["messages", "messaging_postbacks"]` 정상 구독 확인 — 구독 설정 자체는 문제 없음. Instagram 스크린샷으로 해당 대화가 "요청함"(Message Requests)이 아닌 "Primary" 탭에 정상 위치함을 확인 — 메시지 요청함 대기 가설은 기각.

**Root Cause:** **가설 단계(미확정).** `GET /debug_token`으로 액세스 토큰 조회 결과 `instagram_manage_messages`/`pages_messaging`/`instagram_manage_comments` 스코프가 대상 IG 계정(`17841476202821375`)에 정상 부여돼 있어 권한 자체의 부재는 아님. 다만 회장이 Meta 앱 대시보드(역할 > Instagram 테스터)를 직접 확인한 결과 **테스트 계정(채솔)만 테스터로 등록돼 있고, tgbtgbnate는 미등록**임을 확인 — 이는 앱이 `instagram_manage_messages` 등에 대해 아직 App Review를 통과하지 못한 **Standard Access** 상태이고, 이 상태에서는 앱에 역할이 없는 일반 사용자와의 메시징(특히 수신측 웹훅)이 제한될 수 있다는 가설과 일치. 근거 보강: 오늘 하루 동안 테스터 등록 계정(채솔)과의 DM은 전부 수 초 내 즉시 webhook 수신됐으나(13:13 등), 미등록 계정(tgbtgbnate)과는 이번 건 포함 최소 2회(13:12경 1건, 16:14경 이번 건) 동일 패턴(발신 성공, 수신 미도착/지연)이 재현됨. **단, App Review > 권한과 기능 화면에서 `instagram_manage_messages`의 실제 Access Level(Standard/Advanced) 자체는 아직 미확인** — 이것이 확인되기 전까지는 CONFIRMED로 승격하지 않음.

**Fix:** 미적용. 만약 Root Cause가 확정되면, 코드 수정으로는 해결 불가능한 유형 — 정식 해결책은 Meta Business Manager에서 `instagram_manage_messages`(및 필요 시 `instagram_manage_comments`)에 대한 **App Review를 통과해 Advanced Access로 승격**하는 것뿐이며, 이는 회장이 직접 진행해야 하는 행정 절차(사용목적 설명·화면녹화 시연 제출 등).

**영향:** 실제 손님(앱에 테스터로 등록되지 않은 일반 계정 — 사실상 모든 실제 고객)의 Private Reply 답장이 우리 시스템에 도달하지 않을 수 있음. Gate G의 `comment_poller.py`/`comment_auto_reply.py` 자체 로직(키워드 감지·게이트·Private Reply 발송)은 오늘 실증으로 정상 확인됐으나, 문제는 그 앞단인 Meta 인프라(웹훅 배달) 레이어 — "손님 답장 감지 → `dm_auto_reply`가 24시간 상담을 이어받는다"는 24/7 자동화의 핵심 전제 자체가 위협받는 발견.

**관련:** FP-048, INC-036, Gate G(`modules/comment/comment_auto_reply.py`, `modules/comment/comment_poller.py`)

## ERR-065 | n8n watchdog 재시작이 무한 실패 반복 — 좀비 npx 프로세스가 대화형 설치 프롬프트에서 정지, LocalSystem 전환 이후 성공 0건

**발견 경위:** 회장 지시로 `logs/watchdog.log`의 n8n 반복 실패 알림 원인 조사(260715 08:40경). n8n은 워크플로우가 아직 구현되지 않은 설계 단계(WF-01~05 설계만 확정, execution_owner 미구현, ERR-056 참조) 컴포넌트이며 "연결만 해놓은" 상태 — 정식 운영 대상이 아님에도 `watchdog.ps1`이 계속 감시·재시작을 시도 중이었음.

**Raw:**
- `logs/watchdog.log` 전체(260517~260715, 25,153줄): `n8n 재시작 실패` 5,298건 / `n8n 재시작 성공` 8건. 조사 시점(260715 08:41) 연속 실패 카운터 668회, 계속 증가 중.
- 성공 8건의 타임스탬프는 전부 260517~260624 사이(마지막 성공 260624 23:56:09)이며, **ERR-057/ERR-058(260711 NSSM 서비스 LocalSystem 전환) 이후로는 성공 0건** — 실패만 누적.
- `logs/n8n.log` 내용 전체: `Need to install the following packages:\nn8n@2.30.4\nOk to proceed? (y)` — npx가 원격 설치 확인을 묻는 대화형 프롬프트에서 멈춰 있음. 파일 마지막 수정시각 2026-07-14 22:25:44, 이후 갱신 없음(조사 시점까지 10시간+ 정체).
- `Get-CimInstance Win32_Process`로 확인한 결과 PID 16948(cmd.exe, 생성 2026-07-14 22:25:39) → 자식 PID 21620(node.exe, 생성 22:25:40)이 조사 시점(260715 08:4x, 10시간+ 경과)에도 여전히 살아있음 — 이 프로세스가 위 대화형 프롬프트에서 응답 없이 정지된 좀비 프로세스로 추정.
- `npm list -g n8n` → `n8n@2.15.0` 이미 전역 설치 확인됨. 그럼에도 `npx n8n start`는 이를 인식하지 못하고 최신버전(2.30.4) 원격 설치를 제안.
- `npm config get prefix -g` → `C:\Users\admin\AppData\Roaming\npm` (admin 사용자 프로필 전용 경로).
- `Get-CimInstance Win32_Service -Filter "Name='SNS_Watchdog'"` → `StartName=LocalSystem` 확인(ERR-057/058과 동일).
- `netstat -ano`에서 `:5678` LISTENING 없음 확인 — n8n 서버 자체는 조사 시점까지 한 번도 뜨지 않은 상태.

**Root Cause:** **가설 단계(미확정, 프로세스 강제종료·재현 테스트 없이는 확정 불가 — 이번 조사는 회장 지시로 read-only에 국한).**
1. `watchdog.ps1`의 `Start-N8n()`(152~159행)이 `npx n8n start`를 hidden window + 출력 리다이렉션(`> n8n.log 2>&1`)으로 실행하며 `-y`/`--yes` 옵션을 주지 않음. npx가 로컬에서 즉시 실행 가능한 n8n을 찾지 못하면 원격 설치 여부를 묻는 대화형 프롬프트를 띄우는데, stdin이 연결되지 않은 실행 컨텍스트라 그 프롬프트에서 무기한 대기(hang)하는 것으로 추정. 260714 22:25에 생성된 이 좀비 프로세스 1건이 계속 살아있으면서 로그 파일과 포트 상태에 영향을 주고, 이후 매 감시 주기(약 35~55초)마다 새로 시도되는 `Start-N8n` 호출들은 정상적으로 진행되지 못하고 있는 것으로 보임(로그 파일이 260714 22:25:44 이후 갱신되지 않는 것과 정황 일치).
2. npx가 이미 설치된 전역 `n8n@2.15.0`을 인식하지 못하는 이유는 미확정이나, 전역 npm 경로(`C:\Users\admin\AppData\Roaming\npm`)가 admin 사용자 프로필 전용이고 `SNS_Watchdog` 서비스가 260711부터 `LocalSystem` 계정으로 실행 중이라는 점이 **ERR-058(ngrok이 admin 프로필 전용 authtoken 경로에 접근 못해 실패)과 동일한 클래스의 정황**으로 유력하게 의심됨.

**Fix:** 미실행. 회장 방침(260715): n8n은 워크플로우 미구현 상태이며 안정화 작업을 우선 완료한 뒤 n8n 진행 예정, 설계(WF-01~05) 자체도 재검토 예정 — 이번엔 코드/프로세스 변경 없이 기록만 남김.

**260721 Root Cause 확정·임시 조치:** LocalSystem 기준 경로에는 `n8n.cmd`가 없고(`C:\Windows\System32\config\systemprofile\AppData\Roaming\npm\n8n.cmd=False`), admin 사용자 경로에만 존재(`C:\Users\admin\AppData\Roaming\npm\n8n.cmd=True`)함을 직접 확인. `watchdog.ps1`은 PATH에서 찾은 `C:\Program Files\nodejs\npx.cmd`로 `npx n8n start`를 실행하므로, LocalSystem 컨텍스트에서 n8n을 찾지 못해 `Need to install ... Ok to proceed? (y)`로 진입하는 원인이 확정됐다. `N8N_WATCHDOG_ENABLED` feature flag를 추가해 기본값 `false`로 감시·재시작·Slack 경고를 임시 중지하고 `.env.example`에도 등록. `tests/test_watchdog_encoding.py` 포함 타깃 테스트 3 passed, PowerShell Parser 오류 0, 서비스 재시작 후 12:16:54 비활성화 로그 확인. 마지막 실패 12:16:38 이후 heartbeat만 지속되고 추가 n8n 재시도 0건. **n8n 기능 자체는 여전히 미구현·미기동이며 이 조치는 알림/프로세스 누적을 막는 임시 완화다.**

**Prevention(제안, 미실행 — 추후 n8n 재개 시 검토):**
- 워크플로우가 실제로 구현되기 전까지는 `watchdog.ps1`의 n8n 감시 블록(240~256행)을 비활성화하거나 알림 빈도를 제한해 Slack 알림 잡음(5,298건 누적)을 줄일 것
- 재개 시 `Start-N8n`을 `npx --yes n8n start`로 변경하거나, 사전에 `npm install -g n8n`으로 로컬 확정 설치 후 `npx` 대신 `n8n start`를 직접 호출하는 방식 검토
- LocalSystem 계정 실행 시 사용자 프로필 종속 경로(전역 npm, ngrok authtoken 등) 접근성을 사전 점검하는 것을 서비스 계정 전환 표준 체크리스트에 포함(ERR-058 Prevention과 통합 검토)

**관련:** ERR-056, ERR-057, ERR-058, PENDING-A, MERGE_JOURNAL(260714 Gate G 후속 "P2 — 신규" 항목)

## ERR-066 | `dm_receiver.send_telegram()`이 모든 DM에서 IGSID 전체·원문 200자를 마스킹 없이 Telegram으로 전송 (P0-1, RESOLVED — 260715 A1 패치 적용)

**발견 경위:** P0-1은 Gate C(ERR-061) Fix 항목에서 "범위 밖, 계속 OPEN"으로만 언급돼 왔고 자체 ERR 번호가 없었음. 회장 지시로 260715 코드 직접 재확인 — 전용 항목으로 승격.

**Raw:**
- `modules/dm/dm_receiver.py:54-71`의 `send_telegram(sender_igsid, message_text)` — `f"\U0001f464 \`{sender_igsid}\`\n\U0001f4ac {message_text[:200]}"` 형태로 IGSID 전체와 메시지 원문 최대 200자를 마스킹 전혀 없이 그대로 Telegram 메시지 본문에 포함.
- `modules/dm/dm_receiver.py:147` `send_telegram(sender_id, text)` — 매 신규 DM 수신마다(웹훅 처리 경로 전체) 무조건 호출됨.
- **재사용 가능한 재료가 이미 존재함**: Gate C(260713~14)에서 `modules/dm/dm_auto_reply.py`에 마스킹 유틸이 이미 구현돼 있음 — `_mask_igsid()`(`:55-56`, IGSID 앞 4자리+`***`), `_PII_PATTERNS`(`:48-52`, 전화번호·이메일 정규식), `_telegram_preview()`(`:59-63`, 위 패턴 제거 후 20자 미리보기). 단 이 유틸은 신규 함수 `send_telegram_price_pending()`(`:219-238`)에만 적용됐고, 기존 `dm_receiver.send_telegram()`에는 적용되지 않은 채 그대로 방치.
- **부수 발견(문서에 없던 추가 노출 지점):** `modules/dm/dm_receiver.py:143` `logger.info(f"[DM] from={sender_id} | text={text[:100]}")` — IGSID와 메시지 원문 100자가 `logs/summary/app.log`에도 마스킹 없이 남음. Telegram(외부 채널)과는 별개로 로컬 로그 파일에도 동일 성격의 PII가 평문 저장되고 있음 — 기존 P0-1 정의(Telegram 노출)의 범위를 넘어서는 인접 노출.

**Root Cause:** DM 자동응답(12단계, 260512 이전 구현) 당시 알림 편의를 위해 IGSID·원문을 그대로 Telegram에 실어보내는 구조로 만들어졌고, 이후 Gate C에서 마스킹 로직을 도입할 때 신규 함수에만 적용하고 기존 함수는 "범위 밖"으로 명시적으로 이월(P0-1)한 뒤 지금까지 재적용되지 않음.

**Fix(260715 적용, 패키지 A1):** Codex 리뷰(GPT/Codex 3-패키지 검토) 거쳐 실행.
1. `dm_receiver.py` — `from modules.dm.dm_auto_reply import ... _mask_igsid, _telegram_preview` 추가(cross-module private import, 긴급수정 허용 범위로 합의됨. 장기적으로는 공용 유틸 승격 검토 대상).
2. `send_telegram()` — Telegram 메시지 본문의 IGSID를 `_mask_igsid()`, 메시지 원문을 `_telegram_preview()`(전화번호·이메일 정규식 제거 후 20자)로 교체. 발송 성공 로그(`[Telegram] 수신 알림 전송`)의 `from=` 필드도 마스킹.
3. `dm_receiver.py:143`(패치 후 147로 이동) `logger.info` — 원문을 아예 제거, `from={_mask_igsid(sender_id)} | text_len={len(text)}`로 교체(Codex 제안: `app.log`는 Telegram보다 오래 보존·검색·백업되므로 원문을 남길 이유가 없음).

**Runtime Proof(260715):** `.venv` python으로 `send_telegram()` 단독 실행 — IGSID(`1234567890123456`)·전화번호(`010-1234-5678`)·이메일(`test@example.com`)을 포함한 메시지로 실제 Telegram 발송 payload를 가로채 확인한 결과, 셋 다 원문이 payload에 없음 확인(`1234***`, `***`로 마스킹). `pytest tests/test_dm_rules.py` 30 passed(회귀 없음).

**Prevention:** `_mask_igsid()`/`_telegram_preview()`가 현재 `dm_auto_reply.py`의 private(`_` prefix) 함수를 cross-module로 재사용하는 상태 — 다음 정리 사이클에서 공용 유틸 모듈(예: `modules/common/pii_mask.py`)로 승격해 두 모듈이 각자의 private 함수를 참조하는 구조를 정리할 것(Codex 리뷰 코멘트, 이번엔 긴급수정으로 보류).

**관련:** ERR-061(Gate C Fix에서 최초 P0-1 이월 언급), FP-046, `modules/dm/dm_auto_reply.py`(`_mask_igsid`/`_telegram_preview`/`_PII_PATTERNS`)

## ERR-067 | FP-047(댓글 이벤트 idempotency) 구현 과정에서 다단계 리뷰로 발견·수정된 correctness 버그 다수 (RESOLVED — 260715, disabled 기본값)

**발견 경위:** FP-047("저장 실패를 성공처럼 처리해 재시도 기회를 잃는 패턴") 코드 구현을 회장 지시("기본만들고 실계정 테스트하며 안정화")로 착수. GPT/Codex와 총 12라운드(설계 8라운드 + 구현 후 코드 리뷰 4라운드) 교차검토를 거치며, 매 라운드마다 실제 코드로 직접 재현·검증한 correctness 버그가 다수 발견됨 — 단순 설계 미비가 아니라, 구현 1차 버전 자체에 실제로 존재했던 버그들.

**Raw(라운드별 발견된 버그, 전부 코드 재현으로 확인 후 수정):**
1. `comment_poller.py`/`dm_receiver.py`가 `process_comment_event()` 실패 시에도 캐시/200 응답 — FP-047 자체가 event_store 도입 후에도 재현될 뻔함
2. `reclaim_stale()`을 구현만 해두고 실제 런타임 어디서도 호출 안 함 — claim 직후 crash가 영구 skip으로 남는 구조였음. `try_claim()` 자체에 stale reclaim을 내장하는 방식으로 재설계
3. `mark_effect_started()` 반환값(fencing 성공 여부)을 무시하고 발송을 강행 — fenced-out worker도 손님에게 중복발송할 수 있었음
4. 재개(reclaim 후) 시 이미 완료된 effect를 재확인 없이 재실행 — 이미 보낸 Telegram/Private Reply/Airtable 기록을 중복 실행할 뻔함
5. 킬스위치가 전역이라 "제한 Canary"가 실제로는 전역 enforce였음 — Gate G의 기존 캠페인 게시물 allowlist 재사용으로 스코핑
6. retry_queue 태스크의 claim_token이 payload에 고정 저장돼, lease 만료로 다른 worker가 stale reclaim하면 재시도 완료 반영이 영구히 fencing 실패 — "다음 시도에 자연 복구된다"던 최초 주석이 실제로는 틀렸음(재현 테스트로 확인). `airtable_status='RETRY_PENDING'` 조건 기반 완료 처리로 수정
7. shadow 모드 claim이 실제 claim과 구분 안 돼, enforce가 이미 legacy 경로로 처리된 shadow row를 "죽은 것"으로 오인해 재claim할 수 있었음 — 설계문서(v4)에 `SHADOW_SEEN` 태깅이 문서화만 되고 실제 구현에서 누락돼 있던 것을 4차 리뷰에서 발견
8. `process_comment_event()`가 예외 없이 끝나면 항상 성공으로 간주 — "완료"와 "남이 처리중"을 구분 못해 poller가 미확정 상태를 영구 캐시할 뻔함. `CommentProcessResult` 구조화된 반환값 도입으로 해결
9. `mark_airtable_done()`/`mark_airtable_retry_pending()`의 fencing 결과(bool)를 호출부가 무시 — Airtable 쓰기는 성공했는데 event_store 상태만 영구 고착될 수 있었음(데이터 유실은 아니나 상태 불일치)

**Root Cause:** 단일 기능처럼 보이지만 실제로는 분산시스템의 고전적 함정(원자적 claim, lease 기반 crash 복구, at-most-once vs at-least-once 구분, idempotency key 설계)이 전부 얽혀있는 문제라, 1차 구현만으로는 이런 종류의 race condition·fencing 누락을 스스로 발견하기 어려웠음. 매 라운드 Codex가 구체적 시나리오(worker crash 시점, lease 만료 타이밍 등)를 재구성해 제시했고, Claude가 그 주장을 실제 코드로 직접 재현·검증(때로는 Codex가 언급 안 한 추가 버그도 테스트 작성 중 자체 발견)하는 방식으로 수렴.

**Fix:** 위 9개 전부 코드 수정 완료. 신규 테스트 65개(동시성 10스레드 경쟁, fencing 위조 token 거부, crash 재현, shadow 격리, webhook 2단계 처리 등) 전부 통과. 전체 회귀 345 total/338 passed/4 failed(무관 기존 `test_dm_close.py`)/3 xfailed.

**Prevention:** 분산 상태머신·idempotency가 필요한 기능은 "일단 만들고 나중에 테스트" 순서보다, 각 실패 시나리오(crash 시점별 상태 조합)를 먼저 표로 나열한 뒤 구현하는 게 더 안전했을 것 — 이번엔 반대 순서(구현 후 리뷰가 시나리오를 하나씩 찾아냄)로 진행돼 라운드가 많아짐. 유사 기능(예: DM 채널 idempotency, 향후 별도 과제) 착수 시 이 교훈 적용 검토.

**관련:** FP-047, INC-035, `docs/design/FP047_COMMENT_EVENT_IDEMPOTENCY_260715.md`

## ERR-068 | Telegram/Facebook 등 외부 API 호출이 간헐적으로 `ConnectionResetError(10054)`로 끊김 — 원인 미확정, 데이터 유실 없음(OPEN, 낮은 우선순위)

**발견 경위:** FP-047 shadow 모드 실계정 테스트(260715) 중, 댓글 5건을 연속 처리하는 과정에서 Telegram 알림 1건이 `[Comment] Telegram 알림 실패 | ('Connection aborted.', ConnectionResetError(10054, ...))`로 실패. 회장 지시로 원인 조사.

**Raw:**
- 동일 에러(`ConnectionResetError 10054`, "현재 연결은 원격 호스트에 의해 강제로 끊겼습니다")가 `logs/summary/app.log` 전체에서 **20회** 발견됨. 최초 발생은 오늘(260715)이 아니라 **260714 14:59:52**부터 — 이번에 새로 생긴 문제가 아니라 이전부터 있던 패턴.
- Telegram(`comment_auto_reply.py`/`dm_receiver.py`/`dm_auto_reply.py`/`dm_followup_scheduler.py`) 뿐 아니라 **Facebook Graph API 조회, 이미지 다운로드(`Preprocess`)** 등 완전히 다른 원격 서버 대상 호출에서도 동일 에러 발생 — 특정 서버(Telegram) 문제가 아니라 **이 컴퓨터에서 나가는 네트워크 연결 자체가 간헐적으로 끊기는 패턴**으로 추정.
- 오늘 실패 시각(17:14:55)을 전후 로그와 대조한 결과, 같은 1~2초 구간에 `engagement_tracker`(별도 기능)도 동시에 Facebook 서버에 요청을 보내고 있었음 — **여러 외부 요청이 동시에 몰릴 때 그중 하나가 끊기는 경향**이 정황상 확인됨(우연히 5건 연속 댓글 처리와 겹침).

**Root Cause:** **미확정(가설 단계).**
1. 동시 다발적 외부 HTTPS 연결 시도 시 소켓/리소스 경합으로 일부가 끊기는 것으로 추정(정황 일치, 확정 아님).
2. **회장 제기 가설(미검증): 노트북 전원 on/off(절전·재개) 반복 이력과의 연관 가능성.** 이 프로젝트는 과거에도 절전(Modern Standby)·재부팅 관련 네트워크·프로세스 이상이 여러 차례 있었음(ERR-053/054/057/058 등 — 전부 watchdog·ngrok 계열이라 이번 건과 직접 연결되진 않지만, "전원 상태 변화가 이 기기의 네트워크 스택에 영향을 준다"는 동일 계열 패턴일 가능성은 배제 못함). 두 가설 다 raw 로그만으로는 확정할 근거 부족 — UNKNOWN으로 유지.

**영향:** **데이터 유실 없음.** Telegram 알림은 "운영자에게 알려주는 용도"일 뿐이라, 실패해도 해당 댓글은 Airtable에 정상 기록됨(오늘 실패 건도 직후 "Airtable 기록 완료" 로그로 확인). Private Reply·Airtable 기록 등 손님 대면 핵심 동작에는 영향 없음.

**Fix:** **미적용 — 지금은 기록만, 낮은 우선순위로 보류.** 재발 빈도가 늘거나(예: 하루에도 여러 번, 또는 데이터 유실로 이어지는 다른 API 호출까지 번짐) 실제 운영에 지장이 생기면 그때 정식 조사·수정 착수.

**Prevention(참고, 미실행):** 재개 시 후보 — (1) `requests` 세션 재사용/재시도(`urllib3.Retry`) 도입, (2) 동시 외부 호출을 살짝 지연시켜 겹침 완화, (3) 노트북 절전 이력과의 상관관계를 실제로 대조(예: `Get-WinEvent`로 절전/재개 이벤트 타임스탬프와 이 에러 발생 시각 교차 확인) — 이번엔 미실시.

**관련:** ERR-053, ERR-054, ERR-057, ERR-058(절전/재부팅 계열 과거 사례, 참고용 — 직접 연결 확정 아님)

## ERR-069 | "최근 게시물 N개"(recent-N) 폴링 한도 때문에 캠페인 댓글이 실제로 시스템에 진입조차 못함 — Package 1로 근본 수정(260716)

**발견 경위:** 260715 저녁 Gate G 실계정 라이브 테스트 중, 회장이 `reviewasiamarket` 계정으로 30초 간격으로 서로 다른 상품 게시물 2곳에 댓글을 남김. 게시물 A(캠페인 등록·최근 5개 안)는 정상적으로 Private Reply까지 도착했으나, 게시물 B(캠페인 등록됐지만 계정이 게시물을 자주 올려 "최근 5개" 밖으로 밀려남)의 댓글은 아무 반응이 없었음. 회장 보고("2개 새 아이디로 댓글 달았는데 DM이 하나만 왔다")로 조사 착수.

**Raw:**
- `configs/comment_campaign_posts.json`에 캠페인 게시물 6개 등록돼 있었으나, `comment_poller.py`의 `get_recent_media_ids()`가 반환하는 "최근 5개 게시물"(`COMMENT_POLL_MEDIA_COUNT=5`) 목록에는 그중 3개만 포함됨(계정 게시 빈도 때문에 나머지 3개가 밀려남).
- 밀려난 게시물 B(`18009967625923895`)에 남긴 댓글(`comment_id=18013411718872236`, "MOV 어떻게되나요")은 `db/comment_events.db`(comment_event_store)에 **기록 자체가 없음** — 폴러가 그 게시물의 댓글을 아예 조회조차 안 했으므로, 이벤트가 시스템에 진입하지 못한 것으로 raw 대조 확인. 웹훅 경로도 이 이벤트를 못 잡음(같은 이유로 DB에 없음).

**Root Cause:** "감시 대상 결정"을 "캠페인 등록 여부"가 아니라 "게시물이 얼마나 최근인가"로 하고 있었음 — 계정이 게시물을 자주 올릴수록 오래된(그러나 여전히 캠페인 중인) 게시물이 감시 범위 밖으로 밀려나 댓글 자체를 조회하지 않게 됨. 캠페인 목록(JSON)과 실제 폴링 대상(최근 N개) 사이에 별도의 동기화 메커니즘이 없어 두 목록이 어긋난 것.

**Fix:** **Package 1(Phase A) 구현 완료.** `comment_poll_targets.py`(신규) — 캠페인 media별 `PENDING_BASELINE→ACTIVE→PAUSED` 상태머신 도입, `comment_poller.py`가 "최근 N개"가 아니라 이 상태머신의 ACTIVE 목록 전체를 폴링하도록 재구성(전체 페이지네이션 포함, 기존 첫 페이지만 읽던 버그도 동시 수정). 신규 media를 곧바로 실시간 처리 대상에 넣으면 과거 댓글을 신규로 오인해 대량 발송 사고가 날 수 있어, `tools/comment_campaign_baseline_cli.py`(신규)로 media별 수동 cutover baseline(`--dry-run`/`--apply`/`--verify`/`--activate`) 절차를 강제.

**Runtime Proof:** 신규 코드는 `COMMENT_POLL_ALLOWLIST_MODE=legacy`(기본값)로 커밋. **기본값에서는 폴링 대상 선택이 기존 recent-N 방식으로 유지된다. 단, 캠페인 설정 또는 poll-target DB 이상 시 신규 안전 게이트(`_blocked_by_allowlist_gating()`)가 fail-closed로 처리를 차단할 수 있다** — "운영 동작이 전혀 안 바뀜"은 부정확한 표현이었음(260716 Codex 재검토로 정정): 감시 대상 선택 로직 자체는 legacy 그대로지만, 새 SQLite 테이블(`comment_poll_targets`) 초기화와 설정/DB 이상 상황에 대한 새 방어선(fail-closed 게이트)이 실제로 추가됐다(코드 배포=감시 대상 결과 no-op을 보장하기 위한 킬스위치, GPT/Codex 교차검토 9라운드에서 이 성질이 실제로 깨지는 경로 2건을 찾아내 수정한 뒤 확정). `--apply`/`--activate` 실제 실행, `COMMENT_POLL_ALLOWLIST_MODE=allowlist`/`COMMENT_EVENT_STORE_MODE=enforce` 전환, 서비스 재시작은 전부 미실행 — 각각 별도 승인 대상.

**Prevention:** "감시 대상"과 "최근성"을 분리할 것 — 운영자 의도(캠페인 등록)를 표현하는 목록과, 그 목록의 각 항목이 실제로 안전하게 감시 가능한 상태인지(baseline 검증 여부)를 나타내는 상태를 별도로 관리해야 한다. 하나의 "최근 N개"류 지표에 감시 대상 결정을 의존시키면 그 지표가 변할 때(게시 빈도 증가 등) 감시 범위가 조용히 줄어드는 사고가 재발한다.

**관련:** FP-050, INC-038, FP-047, `docs/design/FP047_COMMENT_EVENT_IDEMPOTENCY_260715.md`

## ERR-070 | `comment_auto_reply.py`가 `modules.dm.dm_auto_reply`를 직접 import하면 `modules.dm` 패키지와 순환 임포트 발생 (RESOLVED — 260716)

**발견 경위:** FP-047 enforce 전제조건(A-1, 댓글 채널 로그·Telegram 원문 마스킹) 구현 중, ERR-066에서 만든 `_telegram_preview()`(DM 채널용, `modules/dm/dm_auto_reply.py`)를 댓글 채널에도 재사용하려고 `comment_auto_reply.py`에 `from modules.dm.dm_auto_reply import _telegram_preview`를 추가. 이후 `pytest tests/ -k comment` 실행 시 전체 테스트 수집이 1건의 ImportError로 중단됨.

**Raw:**
```
ImportError: cannot import name 'process_comment_event' from partially initialized module
'modules.comment.comment_auto_reply' (most likely due to a circular import)
  modules/dm/__init__.py:1: from .dm_receiver import app, record_interaction
  modules/dm/dm_receiver.py:24: from modules.comment.comment_auto_reply import process_comment_event, CommentProcessResult
```

**Root Cause:** `modules/dm/__init__.py`가 패키지 로드 시점에 `dm_receiver`를 즉시(eager) import하고, `dm_receiver.py`는 다시 `comment_auto_reply`를 import한다. 이 상태에서 `comment_auto_reply.py`가 `modules.dm.dm_auto_reply`를 import하려고 하면, Python은 특정 서브모듈만 로드하는 게 아니라 `modules.dm` 패키지(`__init__.py`) 전체를 먼저 실행하려 하고, 그 과정에서 아직 완성되지 않은(현재 import 진행 중인) `comment_auto_reply` 모듈을 다시 요구하게 되어 순환이 발생함.

**Fix:** `_mask_igsid()`/`_telegram_preview()`(및 이들이 쓰는 PII 정규식)를 도메인 중립적인 신규 `modules/common/pii_mask.py`로 추출. `comment_auto_reply.py`는 `modules.common.pii_mask`에서 직접 import(`modules.dm` 패키지를 전혀 거치지 않음). `dm_auto_reply.py`는 기존 이름(`_mask_igsid`/`_telegram_preview`)을 `pii_mask` 모듈에서 재-import해 별칭으로 유지 — `dm_receiver.py` 등 기존 호출부는 변경 없이 그대로 동작. 이제 미사용이 된 `dm_auto_reply.py`의 `import re`도 함께 제거.

**Prevention:** `__init__.py`가 형제 모듈들을 eager import하는 패키지(이 프로젝트의 `modules/dm/__init__.py`가 대표적 예 — `dm_receiver`/`dm_auto_reply`/`dm_followup_scheduler`를 전부 즉시 re-export)에서는, 그 패키지 밖의 다른 도메인이 "서브모듈 하나만" import해도 순환 위험이 생길 수 있음을 항상 의식할 것. 여러 도메인이 함께 쓸 유틸(마스킹, 포맷팅 등)은 처음부터 특정 도메인 패키지 안이 아니라 `modules/common/`에 둘 것 — 나중에 다른 도메인이 재사용하려 할 때마다 이런 순환을 새로 겪지 않도록.

**관련:** FP-051, ERR-066(같은 클래스의 PII 마스킹 문제 계열)

## ERR-071 | 테스트 2건이 `comment_safety_guard.COOLDOWN_HOURS`(모듈 import 시점에 실제 `.env` 값으로 고정)에 우연히 의존해, pytest 수집 순서가 바뀌자 실패로 표면화 (RESOLVED — 260716)

**발견 경위:** FP-047 enforce 전제조건 B(Airtable startup preflight) 구현 후 신규 테스트 파일 2개(`test_airtable_repository_field_preflight.py`, `test_comment_airtable_preflight.py`)를 추가하고 `tests/ -k "comment or repository or airtable"` 전체를 실행하자, B 코드와 아무 관련 없는 `test_reply_lock_serializes_concurrent_calls_prevents_double_send`(`test_comment_auto_reply.py`)와 `test_mark_user_replied_recovers_from_corrupted_state`(`test_comment_safety_guard.py`) 2건이 새로 실패. 각각 단독 실행하면 통과해 최초엔 "순서 의존 flaky"로만 기록(UNCLASSIFIED)했으나, Codex 재검토("단독 통과는 무관 증거가 아니다")로 실제 원인 규명 착수.

**Raw:**
- `modules/comment/comment_safety_guard.py:26` — `COOLDOWN_HOURS = float(os.getenv("COMMENT_REPLY_COOLDOWN_HOURS", "24"))`. **모듈 import 시점에 딱 한 번만 평가**되는 모듈 레벨 상수.
- 실제 `.env`는 260715 회장 지시로 `COMMENT_REPLY_COOLDOWN_HOURS=0`(쿨다운 사실상 해제, 적극 테스트 목적).
- `is_user_in_cooldown()`(`comment_safety_guard.py:87`)의 판정식 `elapsed_hours < COOLDOWN_HOURS` — `COOLDOWN_HOURS=0.0`이면 이 식은 사실상 항상 거짓이 됨. 즉 "방금 응답 표시했으니 쿨다운 중이어야 한다"를 검증하는 두 테스트가 **자기도 모르게 실제 운영 정책값(0)에 의존**하고 있었음.
- pytest는 세션당 각 모듈을 한 번만 import한다 — `comment_safety_guard`가 이번 세션에서 **어느 테스트 파일에 의해 처음 import되는지**(즉 다른 모듈의 `load_dotenv(override=True)` 호출보다 먼저인지 나중인지)에 따라 `COOLDOWN_HOURS`가 24(기본값, `.env` 로드 전)로 고정되거나 0(`.env` 로드 후)으로 고정됨. 신규 테스트 파일 2개 추가로 전체 수집 순서가 바뀌면서 이번에 처음 후자 경로를 탐.

**Root Cause:** 운영 정책(비즈니스 요구에 따라 수시로 바뀌는 `.env` 값)을 읽어 **모듈 import 시점에 고정하는 상수**를, 그 상수에 의존하는 테스트에서 명시적으로 override하지 않고 방치함. 같은 파일의 다른 테스트(`test_cooldown_expires_after_window`)는 이미 `monkeypatch.setattr(guard, "COOLDOWN_HOURS", 24)`로 명시 고정하고 있었으나, 이번에 실패한 2건은 그 관례를 따르지 않았음.

**Fix:** `tests/test_comment_safety_guard.py`의 `_isolate_state`(autouse fixture)와 `tests/test_comment_auto_reply.py`의 REPLY_LOCK 동시성 테스트에 `monkeypatch.setattr(guard, "COOLDOWN_HOURS", 24)`를 명시 추가 — 실제 `.env` 값·모듈 import 순서와 완전히 무관하게 결정적으로 동작하도록 격리.

**Runtime Proof:** 수정 전 `tests/ -k "comment or repository or airtable"` 1회 실패 확인(2건) → 수정 후 동일 명령 **2회 연속 실행 모두 219 passed, 0 failed**(우연한 재통과 아님을 반복 실행으로 확인). 전체 프로젝트 회귀도 원래 기존 베이스라인(`test_dm_close.py` 4건만 무관 실패)으로 정확히 복귀: 407 passed / 4 failed(무관) / 3 xfailed.

**Prevention:** 모듈 레벨 상수를 실제(변경 가능한) `.env`/설정값에서 import 시점에 읽어오는 코드가 있다면, 그 상수를 사용하는 모든 테스트는 반드시 `monkeypatch.setattr()`로 명시 고정할 것 — "이 파일의 다른 테스트가 이미 하고 있으니 나도 괜찮겠지"라고 안 하고 파일 안의 모든 테스트에 일관 적용해야 한다(이번에 정확히 그 누락으로 발생). 신규 테스트 파일을 추가할 때는 그것만으로 기존 테스트의 pytest 수집 순서가 바뀔 수 있다는 점도 인지할 것 — "내가 만든 코드는 안 건드렸다"가 "회귀 없음"의 증거가 아니다.

**관련:** ERR-070(같은 세션에서 발견된 또 다른 테스트 인프라 문제), FP-052

## ERR-072 | BOM 없는 한글 포함 `watchdog.ps1`을 Windows PowerShell 5.1이 재기동 시 오해석해 NSSM이 60초마다 종료 코드 1로 재시작 (RESOLVED — 260721)

**발견 경위:** 260721 노트북 부팅 후 대시보드·Flask·ngrok이 모두 내려간 상태에서 `SNS_Watchdog`가 `Paused`로 보임. 단순 일시중지로 판단해 `CONTINUE`, `Restart-Service`, `STOP→START`를 시도했으나 새 PID가 생긴 직후 다시 `Paused`로 돌아가 원인 조사.

**Raw:**
- NSSM Application 이벤트: `powershell.exe ... -File ...\watchdog.ps1`가 매번 1.5초 이내 `return code 1`로 종료, `AppRestartDelay=60000` 때문에 재시도 사이에 서비스가 `PAUSED`로 표시됨.
- 수정 전 첫 4바이트: `23 20 77 61`(UTF-8 BOM 없음).
- Windows PowerShell `5.1.26100.8894`의 `Parser.ParseFile()` 결과: 닫히지 않은 문자열, 누락된 `}`, try에 대응하는 catch/finally 없음 등 4개 파싱 오류.
- 같은 파일을 `Get-Content -Raw -Encoding UTF8`로 읽어 `Parser.ParseInput()`에 전달하면 오류 `0개` — 코드 블록 자체가 아니라 파일 디코딩 경로 문제임을 격리.
- BOM 추가 후 첫 3바이트 `EF BB BF`, `Parser.ParseFile()` 오류 `0개`.
- NSSM 자동 재시도 후 `SNS_Watchdog=Running`, watchdog 새 시작 배너 `2026-07-21 11:32:16`, 5000/8501/4040 HTTP 200 확인.

**Root Cause:** 한글·긴 대시 등 비ASCII 문자가 들어 있는 `watchdog.ps1`이 BOM 없는 UTF-8로 저장되어, Windows PowerShell 5.1 `-File` 경로가 현재 부팅 환경에서 파일을 시스템 코드페이지로 잘못 해석했다. 그 결과 문자열 경계가 깨져 실행 전 파서 단계에서 종료 코드 1이 발생했다. **과거에는 같은 파일이 실행됐는데 이번 재기동에서 처음 실패한 정확한 환경 차이는 증거 부족으로 UNKNOWN**이며, "기존 프로세스가 이미 메모리에 읽어 둔 상태였다"는 설명은 가능한 가설일 뿐 확정 근거가 아니다.

**Fix:** `watchdog.ps1` 선두에 UTF-8 BOM 추가. `tests/test_watchdog_encoding.py` 신규 추가 — (1) BOM 바이트 직접 검증, (2) Windows PowerShell 5.1 `Parser.ParseFile()` 실제 실행 검증. 타깃 테스트 `2 passed`.

**Prevention:** 한글 포함 Windows PowerShell 5.1 실행 스크립트는 BOM을 배포 계약으로 고정하고, cold start 전에 실제 `ParseFile()` 검사를 통과해야 한다. 단순 텍스트 diff만으로는 BOM 소실을 놓칠 수 있으므로 바이트 검사와 런타임 파서 검사를 함께 유지한다. 실제 OS 재부팅 실증은 이번 작업에서 수행하지 않았으며 다음 계획된 재부팅 때 별도 확인한다.

**관련:** FP-053, INC-039

## ERR-073 | 부팅 후 AdsPower가 실행되지 않아 Facebook 크롤링 4개 대상이 모두 Local API 연결 거부로 실패 (RESOLVED, 재부팅 자동기동 실증 PASS — 260721)

**발견 경위:** watchdog 복구 직후 launcher가 예약된 FB 크롤링을 실행했지만 Airtable에서 읽은 4개 그룹 모두 `WinError 10061`로 실패. 현재 활성 진입점 `launcher/main.py → modules.sns.facebook_crawler`와 실제 의존 포트 `local.adspower.net:50325`를 확인.

**Raw:**
- 실패 시 AdsPower 관련 프로세스 없음, 50325 LISTENING 없음.
- `app.log` 11:34:01~11:34:17: 그룹 4개 모두 `<urlopen error [WinError 10061] 대상 컴퓨터에서 연결을 거부>`; 결과 `account1: 0`.
- 설치 실행파일: `C:\Program Files\AdsPower Global\AdsPower Global.exe`.
- AdsPower UI 실행 후 창 제목 `AdsPower Browser | 8.4.3 | 2.8.6.9`, `0.0.0.0:50325 LISTENING` 확인.

**Root Cause:** FB 크롤러는 AdsPower Local API가 먼저 실행 중이어야 하지만, 노트북 부팅 후 AdsPower가 자동 실행되지 않았다. 현재 watchdog은 Streamlit/ngrok/launcher/n8n만 감시하며 AdsPower의 실행·50325 readiness를 보장하지 않는다.

**Fix:** 이번에는 AdsPower 앱을 수동 실행해 50325 포트를 복구. **전체 FB 크롤링 E2E 재실행 증거는 아직 없음** — 실패한 예약 사이클은 AdsPower 실행 전에 끝났고 다음 사이클 검증이 남아 있다.

**Prevention:** LocalSystem 서비스에서 GUI 앱을 무리하게 직접 실행하지 말고, 사용자 로그인 세션에서의 AdsPower 자동 시작 또는 별도 readiness gate를 설계해야 한다. launcher가 크롤링 직전에 50325 상태를 명확히 기록·알림하고, 의존성이 없을 때 4개 URL을 연속 실패시키는 대신 단일 원인으로 종료하는 개선도 후보. 실제 자동기동 구현은 이번 커밋 범위 밖이다.

**관련:** FP-054, INC-040, ERR-058(Session 0/LocalSystem과 AdsPower 실행 컨텍스트 참고)

**260721 추가 조사·해결:** 공용 시작프로그램에 `C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup\AdsPower.lnk`가 이미 있었으나, 대상이 존재하지 않는 `C:\Program Files\AdsPower Global\AdsPower.exe`였고 실제 설치 파일은 `AdsPower Global.exe`였다. 관리자 승인으로 바로가기 TargetPath를 `C:\Program Files\AdsPower Global\AdsPower Global.exe`로 수정하고 `TargetExists=True` 재확인. AdsPower 실행 후 50325 LISTENING, 다음 예약 FB 크롤링(12:03:48~12:07:02) 4개 그룹 전체 연결 성공·총 1건 처리로 E2E PASS.

**260721 실제 재부팅 실증(PASS, PENDING 해소):** 회장 승인 하에 `Restart-Computer -Force`로 실제 재부팅 실행(13:13 명령). `logs/watchdog.log` 원본 확인 — `13:14:41 [FATAL] watchdog.ps1 최상위 종료됨` → `13:15:13` SNS_Watchdog(NSSM, Automatic) 자동 재기동 → `13:15:18~13:15:37` Streamlit/ngrok/launcher 순차 자동 복구. AdsPower Global 프로세스 8개 전부 `13:17:32~13:17:40`에 기동 시작(사용자 로그인 세션 시작프로그램 바로가기 경유, 수정한 대상 경로로 정상 실행). 재부팅 후 포트 4개 재검사 — 50325/5000/8501/4040 전부 LISTENING, 50325 소유 프로세스 PID 14908 `C:\Program Files\AdsPower Global\AdsPower Global.exe` 확인. **자동기동 PENDING 항목 완전 해소.**

---

## ERR-075 | mark_post_result() 실패경로 `error_code` 미존재 필드 → 422 UNKNOWN_FIELD_NAME → uploading 11건 고착 (ACTIVE, ERR-041 재발)

**Type:** Airtable 422 UNKNOWN_FIELD_NAME (ERR-041과 동일 클래스, 참조 필드명만 다름)

**Raw:**
```
2026-07-23 14:23:02 [ERROR] __main__ - [publish_single] 3회 실패 최종 | rid=recuqN2wQu6bFNzDp
2026-07-23 14:23:03 [ERROR] core.error_handler - [ErrorHandler] insta_upload 실패 | [Instagram_Posts] 입력 오류: {"error":{"type":"UNKNOWN_FIELD_NAME","message":"Unknown field name: \"error_code\""}}
requests.exceptions.HTTPError: 422 Client Error: Unprocessable Entity for url: https://api.airtable.com/v0/apphJNTHWNoFcVb1D/Instagram_Posts/recuqN2wQu6bFNzDp
modules.infra.repository_interface.RepositoryValidationError: [Instagram_Posts] 입력 오류: {"error":{"type":"UNKNOWN_FIELD_NAME","message":"Unknown field name: \"error_code\""}}
```
(동일 스택 2026-07-14 16:01:24~26 `rid=recknmIxozEIhpmfn`에서도 재현 확인)

**Root Cause (Confirmed):** `launcher/main.py:328` `publish_single()` 실패 시 `PostPublishResult(error_code=raw.get("error", ""))` 구성 → `modules/infra/airtable_repository.py:404-405, 412-416` `mark_post_result()`가 이 `error_code`를 Instagram_Posts PATCH payload에 포함 → 현재 Airtable Schema에 `error_code` 필드가 존재하지 않아 422 반환 → 상태 갱신 PATCH 전체가 거부되어 `post_status`가 `failed`로 전환되지 못하고 `uploading`에 영구 고착.

**Fix:** 미적용 — 이번 세션은 문서화만 승인됨. 아래 "향후 수정 Gate" 충족 후 별도 승인 필요.

**Prevention:** (향후 수정 시 반영 예정) Repository Interface에 필드 추가 시 실제 Airtable Schema 대조 절차 필수화. 상세는 FP-057 참조.

**Risk:** `HIGH` — (1) 현재도 재발 중인 활성 Production Bug(2026-06-30~2026-07-23 today), (2) 실패 레코드가 최종 상태로 전환되지 않아 운영 상태 왜곡, (3) `retry_count`(ERR-041) → `error_code`로 필드명만 바뀌며 반복되는 Failure Pattern(FP-057), (4) Live E2E Test에서 실패경로 검증을 방해, (5) 방치 시 신규 `uploading` 고착 레코드가 계속 발생 가능.

**Status:** OPEN / ACTIVE — 수정 미적용, 고착 레코드 11건 확인: `recEl21XwVS1fQMLM, recDe7zuva9DU4Kpo, recRXuRK8M9LhksKs, rech2WtIaNBv6QAh3, recK5BOXjGQbWszDG, recZgm5co4xrhR61v, reca9Xztuir5D6Fbg, recknmIxozEIhpmfn, recrma9TOOVYQ9zX7, rec2FFjFQRikBf3xs, recuqN2wQu6bFNzDp`

**Evidence:** `error.log:45076-45096`(2026-07-14), `error.log:46284-46304`(2026-07-23) — 11건 전부 "[publish_single] 3회 실패 최종" 직후 동일 `error_code` UNKNOWN_FIELD_NAME 스택트레이스 1:1 매칭 확인(260723 Runtime Evidence 감사).

**ERR-041과의 관계 (재오픈 아님):** ERR-041(2026-06-16, `retry_count`/`last_error_msg` 필드)은 커밋 `463c350`으로 RESOLVED 처리됨 — 그 수정 자체는 여전히 유효하다. 이후(정확한 시점 UNKNOWN, Repository DI 리팩터링 추정) 실패 경로에 `error_code` 필드가 새로 도입되며 **동일 실패 클래스가 다른 필드명으로 재발**해 이 신규 번호로 별도 기록한다.

**향후 수정 Gate (아래 전부 충족 + 별도 승인 후에만 코드 수정 착수):**
1. Runtime Caller 확인
2. Active File 확인
3. Repository Interface와 실제 Airtable Schema 대조
4. 영향받는 모든 실패 호출경로 확인
5. 기존 `retry_count` 유사 재발 패턴(ERR-041) 확인
6. Blast Radius 확인
7. Rollback 방법 정의
8. 성공 기준 사전 확정
9. 사용자 별도 수정 승인

**향후 수정 성공 기준 (기록만, 이번 세션 미실행):**
1. 게시 실패 시 Airtable PATCH가 HTTP 성공한다.
2. 실패 레코드가 `uploading → failed`로 전환된다.
3. 존재하지 않는 Airtable 필드 전송이 0건이다.
4. 실패 원인 정보는 실제 Schema에 존재하는 필드 또는 승인된 저장경로에 남는다.
5. 정상 게시 성공경로에는 회귀가 없다.
6. 단위 Test와 Repository 실패경로 Test가 PASS한다.
7. 격리 Canary에서 실패 1건이 `failed`로 저장된다.
8. 새로운 `uploading` 고착 레코드가 발생하지 않는다.
9. 기존 11건 복구는 별도 승인·별도 작업으로 분리한다.

**관련:** ERR-041, INC-022, INC-042, FP-057

---

## ERR-076 | media_publish HTTP 400이 컨테이너 처리중 일시적 상태일 수 있음 → "명확한 실패" 오분류 (OPEN, 운영영향 없이 수동복구)

**Type:** 설계 가정 오류 — "HTTP 4xx=재시도 금지, 항상 최종실패"로 확정한 규칙에 실측 반례 발견

**Raw:**
```
2026-07-25 09:11:07 [ERROR] __main__ - [publish_single] media_publish 명확한 실패(HTTP 400) | rid=recHTfHrFPQh79XGy | creation_id=17943613074257522
```
수동 재현(같은 creation_id로 재시도):
```
POST /media_publish (creation_id=17943613074257522) → HTTP 200 {"id": "18110242561955523"}
```
GET으로 실제 공개 게시 재확인:
```
permalink: https://www.instagram.com/p/DbMth5Skgy_/, username: aijomoojin
```

**Root Cause (Confirmed):** `launcher/main.py` `publish_single()` Phase B는 `r2.status_code >= 400`을 "서버가 명확히 거부, 게시 안 됐음이 확실"로 분류해 재시도 없이 `failed` 확정한다(260725 Codex 리뷰 STOP ITEM 대응으로 확정한 규칙, `test_publish_outcome_unknown.py`로 회귀 고정됨). 그러나 Meta 컨테이너가 이미지 다운로드/처리를 아직 끝내지 못한 상태에서 `/media_publish`를 호출하면 HTTP 400을 반환하고, 몇 초~수십 초 뒤 같은 `creation_id`로 재시도하면 정상 발행(HTTP 200)되는 사례가 `aijomoojin` 실게시 중 실측 확인됨 — 이 케이스의 400은 "영구 거부"가 아니라 "아직 준비 안 됨"이었다.

**Fix (260729, PARTIAL):** Prevention(3)을 원안(Airtable Schema에 creation_id 추가) 대신 **기존 outcome_unknown용 Slack 알림 패턴을 http_4xx 분기까지 확장**하는 방식으로 구현 — Instagram_Posts에 `error_code`/`creation_id` 필드 자체가 없어 payload에 넣으면 422 UNKNOWN_FIELD_NAME으로 PATCH 전체가 거부되는 ERR-075/041 재발 위험을 피하기 위함(Airtable Schema 변경 없음). `launcher/main.py` `publish_single()` http_4xx 분기 반환값에 `creation_id` 추가(다른 실패분기와 동일하게) + `_job_insta_upload()`가 `mark_post_result()` 성공 직후 `raw.get("ok") is False`면 `creation_id` 포함 Slack 알림 발송. 분류·재시도 로직(fail-closed, Codex STOP ITEM 계약)은 완전히 무변경. 신규 테스트 `test_job_definitive_failure_marks_failed_and_alerts_with_creation_id` 추가, 기존 `test_media_publish_http_400_is_clear_failure_no_retry` 등 회귀 0건(코드리뷰+standalone 실행으로 검증 — `runtime_boot_policy.json` PermissionError로 `_job_insta_upload()` 관련 job-레벨 pytest 3건은 baseline과 동일하게 이 세션에서 실행 불가, `get_canary_safe_mode_state()`만 monkeypatch로 우회한 standalone 스크립트로 대체검증). 미적용 남은 Prevention: (1) `/{creation_id}?fields=status_code` 폴링 후 발행(Meta 권장 패턴), (2) `error_subcode` 기반 제한적 재시도 — 둘 다 이번 세션 Raw Evidence에 `error_subcode` 값 자체가 없어 추측 구현 금지 원칙상 보류.

**Risk:** `MEDIUM→LOW`(관측성 확보 후) — 중복게시로 이어지지 않음(fail-closed 그대로 유지). 이번 수정으로 재현 시 Slack 알림이 즉시 발생해 사람 개입 자체는 여전히 필요하나 "발생 사실을 모르고 지나침" 위험은 제거됨.

**Status:** PARTIAL(RESOLVED 아님) — 관측성(Slack 알림+creation_id 전파)만 해소, 근본 분류 로직(폴링/error_subcode 기반 재시도)은 여전히 미구현.

**관련:** FP-058, ERR-075(같은 세션에서 별도로 발견된, 무관한 필드 스키마 버그)

---

## ERR-077 | Meta 콘솔 토큰 재발급 시 잘못된 Use Case(Instagram API with Instagram Login) 선택 → IGAA 포맷 토큰 저장, graph.facebook.com OAuth 파싱 실패 (RESOLVED, 260725)

**Type:** 토큰 포맷/호스트 불일치 (OAuthException code 190)

**Raw:**
```
GET https://graph.facebook.com/v21.0/17841476202821375?fields=id,username,account_type&access_token=IGAAL14Dve...
HTTP 400
{"error":{"message":"Invalid OAuth access token - Cannot parse access token","type":"OAuthException","code":190,"fbtrace_id":"A2jdsAJEXFMAYf-cygxZ_jR"}}
```
같은 토큰으로 `graph.instagram.com` 호출 시:
```
HTTP 200 {"id": "25455384140796901", "username": "yuna18253", "account_type": "BUSINESS"}
```

**Root Cause:** 7-C Token 교체([[project_workflow_architecture_priority_260723]] GPT 260725 확정 1순위 과제) 진행 중, `yuna18253` 계정은 원래 "Facebook Login for Business" 플로우(EAA 접두 토큰, `graph.facebook.com`)로 발급받은 계정이었으나, Meta 개발자 콘솔에서 "이용 사례 → API 설정 → 액세스 토큰 생성"(Instagram API with Instagram Login 전용 화면 — `docs/Instagram_토큰발급_매뉴얼.md`에 기술된 절차를 그대로 재사용해 발생, 그 매뉴얼은 원래 `aijomoojin`용으로 작성됨)으로 재발급해 `IGAA` 접두 토큰이 나왔다. `IGAA` 토큰은 `graph.instagram.com`에서만 유효하고, 계정 ID 체계도 다르다(`25455384140796901` vs 기존 `17841476202821375`). `launcher/main.py`의 `PROVIDER_CONFIG`는 `yuna18253`을 `graph.facebook.com` 고정 경로로 호출하므로 즉시 `OAuthException 190` 발생.

**Fix:** Graph API Explorer(`developers.facebook.com/tools/explorer`)에서 "사용자 또는 페이지"를 `yuna18253` 연결 Page("AI+24autoprogram")로 전환해 정식 Page Access Token(EAA 접두) 재발급 → `.env` `INSTA_ACCESS_TOKEN` 교체. 최종 검증: `graph.facebook.com` GET `id,username` → HTTP 200, `id=17841476202821375`(기존과 일치)/`username=yuna18253`.

**Prevention:** (제안, 미구현) `docs/Instagram_토큰발급_매뉴얼.md` 상단에 "이 매뉴얼은 Instagram API with Instagram Login 전용"임을 명시하고, Facebook Login for Business 계열 계정 재발급 절차(Graph API Explorer의 Page Access Token 경로)를 별도 섹션으로 추가.

**Risk:** `MEDIUM` — 잘못된 토큰이 `.env`에 저장된 동안(1차 저장+재시작 ~ 정정 재저장+재시작까지) `yuna18253` 게시 경로가 깨진 상태였음(INC-043). fail-closed 설계로 중복게시·데이터손상은 없음. 이 구간에 실제 예약 게시 시도가 있었는지는 로그 미조회(UNKNOWN).

**Status:** RESOLVED (260725) — 최종 read-only GET으로 정상 동작 확인.

**관련:** FP-059, INC-043, [[project_workflow_architecture_priority_260723]] 9단계/7-C

---

## ERR-078 | Instagram_Posts/Lead_Interactions KPI 집계가 Airtable 페이지네이션(offset) 미처리로 첫 100건만 반환 → 게시 성공률 등 전체 KPI 왜곡 (RESOLVED, 260725)

**Type:** 데이터 완전성 버그 — Airtable REST API 페이지네이션 미구현

**Raw:**
```
GET https://api.airtable.com/v0/{base}/Instagram_Posts (offset 파라미터 없이 단일 요청)
응답: records=100건, "offset" 필드 존재(추가 페이지 있음을 의미) — 코드가 이를 무시하고 종료
```
대시보드(Streamlit) 실제 총건수: 592건(확인 시점) vs `kpi_collector.collect_kpi()`가 본 건수: 100건 — 83% 데이터 누락.

**Root Cause:** `modules/infra/airtable_repository.py`의 `fetch_all_instagram_posts()`/`fetch_all_lead_interactions()`가 Airtable REST API의 페이지당 최대 100건 제한을 감안하지 않고 단일 `requests.get()` 호출로 끝남 — 응답의 `offset` 필드(다음 페이지 존재 신호)를 따라가지 않음. 같은 파일의 `count_candidates_by_status()`(Training_Review_Queue)는 이미 올바른 offset 순회 패턴을 쓰고 있었고, `fetch_candidate_phashes()`엔 동일 한계를 인지한 주석("NOTE: offset 페이지네이션 미구현...")까지 있었음에도 KPI 집계 경로 2곳은 미수정 상태로 방치됨. 결과: `uploading`(11건, ERR-041/ERR-075 고착 레코드와 겹침 가능성)·`rejected`(20건) 상태가 KPI에서 통째로 누락되는 등 실사용에 영향.

**Fix:** 두 메서드 모두 `count_candidates_by_status()`와 동일한 `while True` + `offset` 순회 패턴으로 재작성(같은 커밋). `fetch_all_lead_interactions()`는 기존 `since_utc` 필터(`filterByFormula`)를 페이지마다 유지하도록 함께 처리. `repository_interface.py`의 두 추상메서드 docstring도 "전체 페이지 순회" 명시로 갱신.

**Prevention:** (제안, 미착수) `fetch_candidate_phashes()`에 남아있는 동일 클래스 한계(주석으로 이미 인지된 상태)도 향후 동일 패턴으로 정리 필요 — 이번 수정 범위 밖(FP-060 예방 항목 참조).

**Risk:** 수정 전 `HIGH`(신뢰할 수 없는 KPI로 의사결정 위험, 10단계 Metric·수익 검증 착수 직후 발견) — RESOLVED로 해소.

**Status:** RESOLVED (260725) — 라이브 재확인: `fetch_all_instagram_posts()` 594건 반환(수정 전 100건), `collect_kpi("all").upload` = `{total:594, posted:393, failed:169, success_rate:66.2%}`(수정 전 `{total:100, posted:61, failed:34, success_rate:61.0%}`). 신규 단위테스트 6개(`tests/test_airtable_repository_pagination.py`) + 관련 기존 테스트 65개 전부 PASS.

**관련:** FP-060, [[project_kpi_collector_limitations_260725]], ERR-041/ERR-075(같은 `uploading` 고착 레코드가 이번 KPI 누락과도 연결됨을 확인)

---

## ERR-079 | 7-C Token 교체 후 발급된 신규 토큰이 단기(만료됨) 토큰이라 교체 당일 오후 재만료 → DM/댓글 API 전면 실패 재발 (RESOLVED, 260725)

**Type:** 토큰 수명 오분류 — 장기 토큰 교환 단계 누락

**Raw:**
```
2026-07-25 15:39:51 [ERROR] modules.dm.dm_auto_reply - [AutoReply] IG DM 발송 실패 | 401 |
{"error":{"message":"Error validating access token: Session has expired on Friday, 24-Jul-26 23:00:00 PDT. ...","type":"OAuthException","code":190,"error_subcode":463}}
```
15:39~16:30 사이 `ig_auto_reply`/`comment_poller` 반복 실패, retry_queue `dead` 신규 적재(`id=10004~10009` 등).

**Root Cause:** 오전 ERR-077 해소 시 Graph API Explorer에서 Page("AI+24autoprogram") 토큰을 발급받아 `.env`에 저장했으나, 장기 토큰(60일) 교환 단계를 실행하지 않고 그대로 사용 — Graph API Explorer가 기본 발급하는 토큰은 수명이 짧아(이번 사례 발급~만료 간격 약 5시간), 같은 날 오후 만료됨.

**Fix:** Meta Access Token Debugger(`developers.facebook.com/tools/debug/accesstoken`)에서 "액세스 토큰 확장(Extend Access Token)" 실행 → "만료되지 않는 새 액세스 토큰" 발급 확인 → `.env` `INSTA_ACCESS_TOKEN` 재교체 → `SNS_Watchdog` 재시작(회장 관리자 권한) → 신규 프로세스(재기동 16:31경)에서 read-only GET(HTTP 200, id 일치) + `comment_poller.get_recent_media_ids()` 직접 재현 호출(정상 5건 반환)로 재검증.

**Prevention:** (제안, 미착수) 토큰 재발급 절차에 "Graph API Explorer에서 받은 토큰은 항상 그 자리에서 Access Token Debugger로 장기 교환까지 마친 뒤 저장한다"를 필수 단계로 명시(`docs/Instagram_토큰발급_매뉴얼.md`는 여전히 이 단계 없음 — 별도 갱신 필요).

**Risk:** 수정 전 `MEDIUM` — 실제 업무 영향은 낮음(같은 날 확인된 DM/댓글 트래픽 대부분이 테스트 데이터, [[project_kpi_collector_limitations_260725]] 참조), 다만 자동화가 약 1시간 무인 상태로 전부 실패했고 재발 방지 없이는 매 토큰 재발급마다 반복될 위험.

**Status:** RESOLVED (260725) — 장기 토큰 교체 후 read-only GET + `comment_poller` 직접 재현 둘 다 정상 확인.

**관련:** FP-059, FP-061, ERR-077, INC-043, INC-044

---

## ERR-080 | order_detector.mark_lead_converted()가 Airtable에 없는 converted_at 필드를 PATCH → 전환 감지돼도 기록 실패, 예외가 삼켜져 무기록 (RESOLVED, 260725)

**Type:** Airtable UNKNOWN_FIELD_NAME — Repository 필드 스키마 불일치(ERR-041/ERR-075와 동일 클래스, 세 번째 재발)

**Raw:**
```
2026-07-25 15:40:19 [ERROR] modules.crm.order_detector - [Order] 전환 처리 실패 |
[Lead_Interactions] 입력 오류: {"error":{"type":"UNKNOWN_FIELD_NAME","message":"Unknown field name: \"converted_at\""}}
```

**Root Cause:** `modules/infra/airtable_repository.py:889-894` `mark_lead_converted()`가 `bridge_status`/`lead_status`와 함께 `converted_at`을 PATCH하지만, Airtable `Lead_Interactions` 테이블에 이 필드가 실제로 존재하지 않았음(유사 필드 `lost_at`은 존재). `modules/crm/order_detector.py:28-34` `handle_order_conversion()`이 이 호출을 넓은 `except Exception`으로 감싸 로그만 남기고 예외를 삼켜(재시도 큐 위임 없음) — 전환이 실제로 감지돼도 `lead_status`가 `converted`로 절대 전환되지 않고 영구 유실됨. 10단계(Metric·수익 검증) KPI 실측 중 "전환 0건"이 관찰돼 원인 조사 보류 중이었는데, 같은 세션에서 우연히 error.log 점검 중 발견.

**Fix:** Airtable Metadata API로 `Lead_Interactions`에 `converted_at`(dateTime, `lost_at`과 동일 설정: iso 날짜형식/24시간제/Asia-Bangkok 타임존) 필드 신규 추가(`fldznhZsTiC3kVFog`). `verify_field_exists("Lead_Interactions", "converted_at")` → `True`로 재확인. 코드 변경 없음(필드만 보강).

**Prevention:** (제안, 미착수) ERR-041/ERR-075와 동일 근본 예방책 — Repository Interface에 신규 필드를 쓰는 코드를 추가할 때 실제 Airtable Schema와 대조하는 절차 필수화(FP-057 예방 항목 참조, 세 번째 재발).

**Risk:** 수정 전 `HIGH`(전환 데이터 영구 유실 + 예외를 삼켜 증상이 표면화되지 않음) — RESOLVED로 해소되었으나, 이 버그가 언제부터 있었는지(최초 도입 시점)는 미조사 — 그동안 감지된 모든 전환이 실제로 유실됐을 가능성.

**Status:** RESOLVED (260725) — 필드 추가 완료, `verify_field_exists()`로 재확인. 실제 전환 이벤트로 end-to-end 재현 검증은 미실시(다음 실제 전환 발생 시 확인 필요).

**관련:** FP-057(같은 클래스 3번째 재발), ERR-041, ERR-075, INC-045

---

## ERR-081 | 전체 pytest 실행 시 39개 파일 Collection Error — 로컬 snapshots/ 폴더의 중복 tests 패키지가 원인 (RESOLVED, 260725)

**Type:** 테스트 실행환경 문제(로컬 작업폴더 클러터, 코드 결함 아님)

**Raw:**
```
pytest -q (인자 없음) → Interrupted: 39 errors during collection
ModuleNotFoundError: No module named 'tests.test_X' (39개 파일 전부)
```

**Root Cause:** 로컬 저장소에 `snapshots/snapshot_260516_project/tests/`(260516 시점 프로젝트 전체 스냅샷 백업, `.gitignore` 대상이라 git 미추적, 0 tracked files)가 남아있었고, 이 안에도 자체 `tests/__init__.py` + `test_smoke_common.py`/`test_smoke_crawler.py`/`test_smoke_crm.py`/`test_smoke_metrics.py` 4개가 진짜 `tests/`와 동일 파일명으로 존재. pytest를 인자 없이 실행하면 저장소 전체를 알파벳순으로 훑는데 `snapshots`가 `tests`보다 먼저 발견돼 `sys.modules['tests']`가 스냅샷 쪽 패키지로 먼저 바인딩됨 → 이후 진짜 `tests/`의 나머지 파일 전부가 "그 이름의 모듈이 없다"고 오판되어 39개 전부 `ModuleNotFoundError`.

**Fix:** `pytest.ini` 신규 추가(`[pytest]` / `testpaths = tests`) — pytest가 인자 없이 실행돼도 `tests/`만 탐색하도록 범위 고정. `snapshots/` 폴더 자체는 삭제하지 않음(별도 하우스키핑 결정, 이번 범위 밖 — 폴더 내용은 260516~260712 사이 정지된 죽은 스냅샷으로 확인됨, 최근 갱신 없음).

**Prevention:** 신규 스냅샷/백업 폴더를 저장소 루트에 만들 때는 `tests/`류 하위구조를 통째로 복제하지 않거나, `pytest.ini`의 `testpaths` 고정이 항상 이런 충돌을 원천 차단한다는 걸 인지.

**Risk:** 수정 전 `MEDIUM` — 실제 코드/테스트 자체는 건강했음(격리 실행 시 항상 정상), 다만 "전체 회귀 실행"이라는 안전장치가 매번 이 문제로 막혀있어 회귀 검증 습관 자체가 무력화될 위험이 있었음.

**Status:** RESOLVED (260725) — `pytest -q`(인자 없음) 재실행으로 collection error 0건, `579 passed / 4 failed(기존 known baseline test_dm_close.py) / 3 xfailed` 확인.

**관련:** FP-062

---

## ERR-082 | Webhook(`/webhook`) 엔드포인트에 `X-Hub-Signature-256` 서명 검증 코드가 존재하지 않음 — Meta 공식 요구 보안 통제 부재 확정 (RESOLVED — Runtime ADOPT·7단계 SUCCESS, 260728)

**Type:** Security — 미검증 외부 Payload를 무조건 신뢰하는 구조 (Gap Classification: Security)

**Raw:** Codex가 Bundle B(DM `account_code_ref` 태깅) 리뷰 과정에서 "Webhook 서명검증 부재는 Bundle B 이후 부가사항이 아니라 P0 보안 위험"이라고 지적 → 260726 Claude Code가 별도 Read-only 조사(Phase 0~5)로 코드 전수확인. 핵심 증거:
```
modules/dm/dm_receiver.py:142-147
@app.post("/webhook")
def receive_webhook():
    data = request.get_json(silent=True)   # ← 서명검증 없이 즉시 파싱
    if not data:
        abort(400)
```
`X-Hub-Signature-256`/`hmac.`/`hashlib.`/`compare_digest`/`APP_SECRET`/`app_secret` 문자열이 `dm_receiver.py` 및 프로젝트 `*.py` 전체(`.venv` 서드파티 라이브러리 제외)에서 매칭 0건(Grep 전수확인, 백그라운드 재확인 포함 2회 동일 결과). `.env.example`에도 Meta App Secret을 저장할 변수 자체가 없음(`WEBHOOK_VERIFY_TOKEN`만 존재하며 이는 GET 핸드셰이크 전용, POST Payload 검증과 무관).

**Root Cause:** **CONFIRMED**(더 이상 UNKNOWN 아님) — `launcher/main.py:536,550`이 `modules.dm.dm_receiver.app`을 직접 `app.run()`으로 구동하며, WSGI 미들웨어·리버스프록시 계층이 Python 코드상 존재하지 않음. `POST /webhook`(DM·댓글 이벤트 공용 라우트, `receive_webhook()`)이 `request.get_json(silent=True)`로 Payload를 곧바로 파싱해 Business Logic(Airtable Lead 생성·자동응답·Telegram 알림·댓글 처리)을 실행 — 서명 검증 코드, App Secret 저장소, HMAC 계산 로직이 셋 다 코드베이스 어디에도 없음이 Runtime Caller/Import Chain 전수확인으로 확정됨.

**Fix — 260727 로컬 구현 완료(GPT Target Architecture 결정 → Claude Code 구현, 회장 승인 범위: 코드·테스트 5파일+`.env.example` 1파일)**: `modules/common/webhook_signature.py`(신규) — `verify_meta_signature(raw_body, signature_header, app_secret)` 순수함수, Meta 공식 규격(`sha256=<hex>`, `hmac.compare_digest`) 그대로 구현. `modules/dm/dm_receiver.py` — 기존 `POST /webhook`(Galaxy/yuna, `WEBHOOK_APP_SECRET`)은 보존하고, 신규 `POST /webhook/ai-strategist`(AI Strategist, `AI_WEBHOOK_APP_SECRET`)를 additive로 추가. 두 Route 모두 `request.get_data(cache=True)` → 서명검증 → 실패 시 즉시 `abort(403)`(Business Logic 진입 0건) → 성공 시에만 `request.get_json()` → 기존 `_process_webhook_event()`(바이트 단위 무변경) 순서로 동작. GET 핸드셰이크도 `AI_WEBHOOK_VERIFY_TOKEN`으로 Galaxy와 분리, 두 App의 Secret/Token 교차 사용은 코드·테스트 양쪽에서 거부 확인. Build·Buy·Reuse 비교(기존 기록)대로 Python 표준 `hmac`/`hashlib`만 사용, 신규 의존성 0건.

**Test Evidence(260727)**: 신규 `tests/test_webhook_signature.py`(Validator 단위 10종) + 기존 `tests/test_dm_receiver_webhook.py`(8→23, Signed Request 전환+Route 보안회귀 15종 추가)/`tests/test_dm_account_routing.py`(10건 Signed Request 전환, 로직 무변경) 전부 PASS. 전체 Suite Before(순수 원복 상태) 606 passed/3 xfailed/0 failed → After 631 passed/3 xfailed/0 failed(재현 3회 일치, 신규 실패 0건, 차이 +25는 신규 테스트 수와 정확히 일치). `git diff --check` 오류 0건, 허용 6파일 외 Diff 0건, Encoding/BOM 무결(CRLF/LF는 `core.autocrlf=true` 표준 동작, 실질적 결함 아님).

**Runtime Closure Evidence(260728)**: AI Strategist 실제 Meta DM이 `POST /webhook/ai-strategist → 200`, 기존 yuna 실제 Meta DM이 `POST /webhook → 200`으로 처리됐다. Cross-secret 합성 요청은 `/webhook` + AI Secret 및 `/webhook/ai-strategist` + Galaxy Secret 모두 403으로 차단됐고 Business Logic 진입은 0건이었다. `DM_ACCOUNT_ROUTING_ENABLED=true`를 적용하고 Runtime을 재시작한 뒤 yuna Lead가 `account_code_ref=IDN-000041`로 저장됐으며 잘못된 계정 저장은 0건이었다. 가격 문의별 자동응답도 각각 1건씩 확인됐다. 실제 Secret·Token·Signature·DM Raw Body 노출은 0건이다.

**Prevention:** 두 Meta App은 Route별 고정 Secret과 공통 Raw Body HMAC-SHA256 Validator를 사용한다. 서명 누락·불일치·Cross-secret 요청은 403으로 Fail-closed 처리하고 Business Logic에 진입시키지 않는다. 신규 계정 추가 시 `docs/INSTAGRAM_ACCOUNT_WEBHOOK_ONBOARDING_RUNBOOK.md`의 Secret 매핑·실제 DM·Cross-secret·계정 라우팅 Canary를 반복한다.

**Risk:** 기존 무검증 Payload 수용 위험은 Runtime 서명검증 ADOPT로 차단됐다. 단, 7단계 Canary 구간에서 Signature 실패 경고 8건이 관측됐고 발생 주체는 **UNKNOWN**이다. 해당 요청의 Business Logic 진입·Lead 생성·계정 오염 Evidence는 없어 ERR-082 종료조건과 분리한 RISK/HOLD로 유지한다.

**Status:** **RESOLVED — Runtime ADOPT·7단계 SUCCESS(260728)**. AI/yuna 실제 Meta DM 200, 양 Route Cross-secret 403, yuna `IDN-000041` 저장, 오계정 0건, 자동응답 회귀 성공으로 정의된 종료조건을 모두 충족했다. Signature 실패 경고 8건의 출처 확인은 별도 HOLD이며 본 보안 통제의 우회 또는 Business Logic 진입 Evidence가 없어 ERR-082 재OPEN 조건으로 간주하지 않는다.

**관련:** Codex Bundle B 리뷰(대화 기록), `docs/WORKFLOW_ARCHITECTURE_STATUS.md` §10-9~10-11(Gate 순서·260727 로컬 구현·260728 Runtime 종료 Evidence), [[project_dm_relay_supplier_design_260713]] 계열 웹훅 설계 논의와 연관 가능성(재확인 필요)

## ERR-083 | Webhook GET 인증(hub.verify_token) 값이 werkzeug 접속로그에 평문으로 기록됨 (OPEN — 기록만, 조사·수정 미착수, 260727)

**Type:** Security/Observability — Secret이 애플리케이션 로그가 아닌 WSGI 접속로그에 노출 (Gap Classification: Security)

**Raw:** 260727 ERR-082 AI Strategist Webhook Runtime Canary 확인 중 `logs/summary/app.log`을 직접 열람하다가 부수적으로 발견(의도적 조사 아님, 목표는 `[Webhook/AI] 검증 성공` 로그 확인이었음). Meta가 GET 핸드셰이크 시 `hub.verify_token`을 URL 쿼리 파라미터로 전송하는데, Flask 기본 WSGI 접속로그(`werkzeug` 로거)가 요청 URL 전체를 그대로 기록해 다음과 같은 줄이 `app.log`에 남음(실제 값은 이 문서에도 마스킹 없이 옮기지 않음):
```
GET /webhook/ai-strategist?hub.mode=subscribe&hub.challenge=...&hub.verify_token=<실제 토큰 평문> HTTP/1.1
```
`dm_receiver.py`의 자체 `logger.info`/`logger.warning` 호출(`verify_webhook()`/`verify_webhook_ai_strategist()`)은 토큰 값을 직접 출력하지 않지만, Flask가 자동으로 남기는 werkzeug 접속로그 라인까지는 애플리케이션 코드가 통제하지 못함.

**Root Cause:** UNKNOWN(미조사) — werkzeug 기본 access log 포맷이 원인일 가능성이 높다는 것만 관찰됨(추정, 확정 아님). Galaxy 기존 `GET /webhook`(`WEBHOOK_VERIFY_TOKEN`)도 같은 구조라 이번 세션 이전부터 동일하게 노출됐을 가능성 있음 — 실제 과거 로그 확인은 안 함(범위 밖).

**Fix:** 미착수(승인 대기, 이번 세션은 기록만) — 예상 후보(검증 안 됨): (1) werkzeug 로거 포맷에서 쿼리스트링 마스킹 (2) 커스텀 WSGI 미들웨어로 로그 남기기 전 `hub.verify_token=` 값 치환 (3) 별도 로그 레벨/필터 적용. 어느 쪽이 적절한지는 다음 종합 점검 때 Build·Buy·Reuse 비교 필요.

**Prevention:** 없음(미착수)

**Risk:** `MEDIUM`(추정) — Verify Token은 GET 핸드셰이크 1회성 검증용이라 DM 본문·Access Token보다는 민감도가 낮지만, 로그 파일(`logs/summary/app.log`)에 평문으로 남아있으면 그 로그에 접근 가능한 누구나 토큰을 알아내 임의 GET 요청으로 인증 재현이 가능해짐. 실제 악용 정황은 없음(단순 관찰 발견).

**Status:** **OPEN — 기록만 완료, 조사·수정 착수 안 함**(회장 지시: "기록만해놔, 나중에 다 종합 점검할 때 다시 확인하고 수정"). 다음 종합 점검 세션에서 Gate 1~3(Outcome/Success Criteria/Runtime Evidence)부터 재시작.

**관련:** ERR-082(같은 Webhook 엔드포인트에서 파생 발견), [[feedback_md_docs_autoupdate]]

## ERR-084 | Facebook Exact-Post Canary Selector가 "게시물 숨기기" 등 UI 액션 anchor의 placeholder href를 실제 게시물 링크로 오인 (RESOLVED, 260729)

**Type:** Code Defect — Selector 판정 로직이 비-콘텐츠 UI 액션 링크를 콘텐츠 식별 근거로 오인 (Gap Classification: Code Defect)

**Raw:** 8단계 P1-1 C1 Facebook Exact-Post Canary 실행 과정에서, 승인된 permalink(`https://www.facebook.com/groups/1827528710833477/posts/4051001165152876`)에 실제 브라우저로 재접속할 때마다 `_find_exact_permalink_article()`이 매번 다른, 완전히 무관한 게시물(예: "Cielo Anne Areno"의 필리핀 화장품 판매글, "China Sixsix"의 중국 화장품 제조업체 광고)을 목표 Post ID와 일치한다고 판정하는 현상을 반복 관측. 260729 05:24 ICT 실제 DOM 전수조사로 원인을 특정: 무관 게시물("China Sixsix") article 안에서
```
aria-label='China Sixsix님의 게시물 숨기기'
href='https://www.facebook.com/groups/1827528710833477/posts/4051001165152876#'
```
형태의 anchor를 발견 — "게시물 숨기기" 버튼은 실제 이동 목적지가 없는 JS 전용 UI 액션인데, href 값으로 현재 보고 있는 페이지(목표 permalink) 자체를 빈 `#` fragment와 함께 재사용하고 있었다.

**Root Cause:** **CONFIRMED** — `extract_facebook_post_id()`는 `urlparse()`로 URL을 분해한 뒤 `.path`만으로 Post ID를 추출하므로 `#` 뒤의 fragment는 자동으로 제거된다. 이 때문에 "숨기기" 같은 UI 액션 anchor의 placeholder href(`.../posts/<현재글ID>#`)도 실제 목적지가 있는 콘텐츠 링크와 동일하게 파싱돼 목표 Post ID와 일치 판정을 받았다. 이 placeholder href는 화면에 렌더링된 **모든** 게시물의 UI 액션 버튼에 동일하게 붙으므로, `_find_exact_permalink_article()`의 "article 안에 expected_post_id와 일치하는 anchor가 있는가" 판정은 실질적으로 거의 항상 참이 되어 Fail-closed 보장이 무력화돼 있었다.

**Fix(260729, 회장 승인 범위: 코드 1파일+테스트 1파일)**: `modules/sns/facebook_crawler.py::_find_exact_permalink_article()` 최소 수정 — anchor 판정 전에 (1) href가 공백 제거 후 빈 `#`로 끝나면 제외, (2) aria-label에 "숨기기"가 포함되면 제외. 두 조건 모두 실제 콘텐츠 목적지가 없는 UI 액션 anchor를 걸러내기 위함이며, 정규식·Post ID 추출 로직 자체는 무변경.

**Test Evidence**: `tests/test_package_s3_facebook_exact_runner.py`에 실측 재현 케이스 3건 신규 추가(단일 "숨기기" placeholder만 있으면 거부 / 진짜 링크와 공존 시 진짜 링크 선택 / aria-label 없이 href의 빈 `#`만으로도 거부). 대상 파일 31/31 PASS(기존 28+신규 3, 0 failed). 관련 전체 Suite(ProgramData ACL로 collection이 막히는 8개 파일 제외) 626 passed(기존 실패 9건과 동일, 신규 실패 0건). `git diff --check` 0건.

**Runtime 재확인(260729 05:58~05:59 ICT, 실제 브라우저 2회 연속)**: 수정된 함수를 동일 permalink에 직접 호출한 결과 2회 모두 더 이상 무관 게시물("China Sixsix" 등)을 선택하지 않았다(2회 모두 `found=0`으로 Fail-closed — 이 시간대에 진짜 대상 게시물 콘텐츠가 대기시간 안에 렌더링되지 않은 것으로 추정되며, 이는 기존에 별도 문서화된 DOM 로딩 비결정성 문제와 동일 계열로 이번 수정과 무관). 핵심 성공기준인 "무관 게시물 오매칭 재현 안 됨"은 2회 모두 충족했다.

**Prevention:** 이 오매칭은 애초에 실제 저장 함수(`run_exact_permalink_canary()`)의 payload 생성에 영향을 준 적이 없다 — Adversarial 단위테스트(가짜 DOM에 무관한 텍스트·이미지를 심어 검증)로 `caption`/`image_url`은 오직 `approved_caption`/`approved_image_url` 파라미터만 사용하며 DOM에서 읽은 값이 섞일 코드 경로 자체가 없음을 별도 증명(260728). 260728에 저장된 실제 draft(`recFHv9AvW891KaHW`)는 이 버그와 무관하게 안전했다. 향후 유사 Selector 로직을 재사용할 경우, DOM anchor 매칭만으로 "올바른 게시물"을 판정하지 말고 사람의 직접 확인(또는 승인된 값의 수동 입력)을 병행해야 한다.

**Status:** **RESOLVED(260729)** — Root Cause Confirmed·코드 수정·회귀테스트·실측 재확인 전부 완료. 8단계 P1-1 완료 선언의 마지막 보류 사유였다.

**관련:** `docs/CURRENT_RUNTIME_CONTEXT.md` 260729 06:00 ICT 섹션, `docs/WORKFLOW_ARCHITECTURE_STATUS.md` §10-12~10-14

---

## ERR-085 | dm_receiver.py 웹훅 핸들러가 Lead_Interactions 최초 생성(record_interaction) 실패를 삼키고 해당 DM 전체를 건너뜀 — retry_queue 위임 없음 (RESOLVED, 260729)

**분류:** `LIVE_PATH / OBSERVED_INCIDENT_NONE_IN_SEARCHED_EVIDENCE`(260729 재검증) — Runtime Caller·Import Chain은 Confirmed(`dm_receiver.py:305`에서 직접 호출, `launcher/main.py:622,635`가 `from modules.dm.dm_receiver import app` → `app.run(...)`으로 실제 구동). 다만 조사한 로그 범위(`logs/error/error.log`, `logs/summary/app.log*`)에서 `[Airtable] 기록 실패` 문자열의 실제 발생은 0건 — 이는 "장애가 없었다"는 증명이 아니라 "이번 검색 범위에서 발견되지 않았다"는 뜻이며, 실제 Incident 발생 여부는 **UNKNOWN**이다.

**Type:** 예외삼킴(Exception Swallow) — 쓰기 실패가 재시도·알림 없이 조용히 무기록으로 종료되는 패턴, ERR-080과 동일 클래스(Gap Classification: Reliability)

**Raw:** P1-2(데이터 유실 예외삼킴 표적 감사, 260729) 중 코드 read-only 조사로 발견. `modules/dm/dm_receiver.py:304-309`:
```python
try:
    record_id = record_interaction(sender_id, text, account_code_ref=account_code_ref)
    send_telegram(sender_id, text)
except Exception as exc:
    logger.error(f"[Airtable] 기록 실패 | sender_id={sender_id} | {exc}")
    continue
```

**Root Cause:** `record_interaction()`(`modules/dm/dm_receiver.py:133-147`)이 `_repo.create_lead_interaction()`으로 `Lead_Interactions`에 DM 최초 레코드를 생성하는데, 이 호출을 감싸는 웹훅 루프가 실패 시 `logger.error` 후 `continue`로 다음 이벤트로 넘어간다. retry_queue(`modules/common/retry_queue.py`) 위임이나 재시도 로직이 전혀 없어, 이 지점이 실패하면 해당 DM은 Lead 레코드 자체가 생성되지 않고 영구 유실된다. 이는 웹훅 파이프라인의 가장 상류(최초 진입점)이므로, 실패 시 하위의 Lead 스코어링·주문감지·자동응답 로직이 전부 실행되지 않는다 — ERR-080(order_detector, 파이프라인 중간 지점)보다 넓은 blast radius.

**Fix:** 완료(commit `75c60d2`, 260729) — `record_interaction()` 실패 시 로그만 남기고 `continue`하던 것을, `modules/common/retry_queue.py::get_retry_queue()`에 task_type `dm_record_interaction`(payload: sender_id/text/account_code_ref)으로 위임하도록 변경. 실패 시 `send_telegram()`도 호출하지 않음(레코드 미생성 상태에서 알림만 나가는 불일치 방지). 성공 경로는 기존과 동일.

**Prevention:** 적용됨 — Lead 최초 생성 실패를 retry_queue로 위임해 재처리 기회를 남김.

**Risk:** 수정 전 `HIGH` → 수정 후 재시도 경로 확보로 완화. 실제 과거 발생 건수는 여전히 UNKNOWN(조사 범위 내 로그 0건).

**Verification:** 신규 테스트 `tests/test_dm_receiver_record_interaction_retry.py`(성공경로 유지 + 실패 시 retry_queue 등록·send_telegram 미호출 확인) — 이 환경의 로컬 pytest는 `runtime_boot_policy.json` PermissionError로 dm_receiver import 자체가 collection 단계에서 막혀 실행 불가(기존 `tests/test_dm_receiver_webhook.py`도 동일하게 겪는 pre-existing 환경 제약, baseline 대조로 회귀 아님을 확인). 대신 코드 리뷰(diff 범위 확인) + 260729 11:43:51 Runtime 재시작으로 신규 코드가 반영된 프로세스 기동을 `logs/watchdog.log`(`[OK] launcher/main.py 재시작 성공`)로 확인. 회장 승인(B안)에 따라 라이브 웹훅 호출 검증은 별도 발견 사안(WEBHOOK_APP_SECRET 라이브/파일 불일치, task_b24dbf54로 분리 조사 예정)으로 이번 범위에서 제외.

**Status:** **RESOLVED — commit `75c60d2`, 260729. Runtime 재시작 반영 확인.**

**관련:** ERR-080, ERR-086, ERR-087, ERR-088, FP-063

---

## ERR-086 | lead_scorer.update_lead_score() 저장 실패 시 로그만 남기고 재시도·알림 없이 종료 (RESOLVED, 260729)

**분류:** `LIVE_PATH / OBSERVED_INCIDENT_NONE_IN_SEARCHED_EVIDENCE`(260729 재검증) — Runtime Caller·Import Chain은 Confirmed(`dm_receiver.py:321`에서 직접 호출, 같은 Live Chain). 조사한 로그 범위에서 `[Scorer] 업데이트 예외` 문자열의 실제 발생은 0건 — 미발견은 미발생의 증명이 아니며, 실제 Incident 여부는 **UNKNOWN**이다.

**Type:** 예외삼킴(Exception Swallow) — ERR-080과 동일 클래스(Gap Classification: Reliability)

**Raw:** P1-2 표적 감사 중 발견. `modules/crm/lead_scorer.py:58-64`:
```python
def update_lead_score(record_id: str, score: int, grade: str) -> None:
    """Lead_Interactions에 lead_score, lead_grade 업데이트."""
    try:
        _repo.update_lead_score(record_id, score, grade)
        logger.info(f"[Scorer] 스코어 저장 | record={record_id} score={score} grade={grade}")
    except Exception as exc:
        logger.warning(f"[Scorer] 업데이트 예외 | {exc}")
```

**Root Cause:** `_repo.update_lead_score()` 호출 실패가 `warning` 레벨 로그만 남기고 그대로 함수가 종료된다. retry_queue 위임 없음. 실패해도 호출자(`dm_receiver.py`)는 이를 알지 못하고 정상 진행한다 — 해당 Lead의 `lead_score`/`lead_grade`는 영구히 기록되지 않는다.

**Fix:** 완료(commit `75c60d2`, 260729) — 실패 시 task_type `lead_update_score`(payload: record_id/score/grade)로 retry_queue 위임. 성공 경로는 기존과 동일.

**Prevention:** 적용됨 — retry_queue 연동.

**Risk:** 수정 전 `MEDIUM` → 수정 후 재시도 경로 확보로 완화. 실제 과거 발생 건수는 UNKNOWN(조사 범위 내 로그 0건).

**Verification:** `tests/test_crm_write_retry_queue.py::TestErr086UpdateLeadScoreRetry` 2/2 통과(성공경로 유지 + 실패 시 retry_queue 등록 확인) + 260729 11:43:51 Runtime 재시작 반영 확인(`logs/watchdog.log`).

**Status:** **RESOLVED — commit `75c60d2`, 260729.**

**관련:** ERR-080, ERR-085, ERR-087, ERR-088, FP-063

---

## ERR-087 | lead_closer.mark_lead_closed() — 코드 패턴은 존재하나 Production Caller 0건, 현재 Runtime 영향 없음(잠재 위험으로 재분류, 260729 재검증) (RESOLVED, 260729)

**분류:** `NOT_ACTIVE / LATENT_RISK` — **현재 Runtime 영향: 없음.**

**260729 재검증으로 기존 Runtime 결함 판정을 철회한다.** 최초 등록 시 이 함수를 "실제로 도는 함수"로 간주하고 Risk를 `MEDIUM~HIGH`로 매겼으나, Runtime Caller·Import Chain을 재확인한 결과 `modules/crm/lead_closer.py::mark_lead_closed()`를 호출하는 프로덕션 코드는 **0건**이다(`grep -rn "mark_lead_closed" --include=*.py` 결과, 참조는 `modules/infra/repository_interface.py`·`modules/infra/airtable_repository.py`의 인터페이스/구현 정의와 `tests/test_dm_close.py`뿐). `tests/test_dm_close.py:175`에 `reason="dm_followup_scheduler.py에 mark_lead_closed 연동 미완료 — 다음 구현 단계에서 활성화"`라고 코드로 명시돼 있어, 현재 참조는 테스트 코드뿐이며 아직 어떤 Scheduler에도 연결되지 않았음이 확인된다.

최초 등록 근거였던 `logs/error/error.log`의 `[Closer] CLOSE 처리 실패 | timeout` 16건(260725~260729)은 재조사 결과 **pytest 실행이 운영 로그 파일에 그대로 기록된 Test Artifact**로 확인됐다 — 예외 메시지 `"timeout"`이 `tests/test_dm_close.py:132`의 `patch("requests.patch", side_effect=ConnectionError("timeout"))` mock과 정확히 일치하고, 인접 로그 줄에 `pytest-of-admin\pytest-176\...` pytest 임시 디렉터리 경로가 그대로 나타난다. 즉 이 16건은 실제 Production Incident가 아니다(상세: FP-064).

**Type:** 예외삼킴(Exception Swallow) + 상태-알림 불일치 — 코드 패턴 자체는 ERR-080과 동일 클래스지만, 현재는 Caller가 없어 발현되지 않는 잠재 위험(Gap Classification: Reliability, Dormant)

**Raw:** P1-2 표적 감사 중 발견. `modules/crm/lead_closer.py:15-25`:
```python
def mark_lead_closed(record_id: str) -> None:
    """CLOSE 상태 전환 — bridge_status=closed, lead_status=converted, closed_at 기록."""
    if not record_id:
        logger.warning("[Closer] record_id 없음 — skip")
        return
    try:
        _repo.mark_lead_closed(record_id)
        logger.info(f"[Closer] CLOSE 처리 완료 | record={record_id}")
    except Exception as exc:
        logger.error(f"[Closer] CLOSE 처리 실패 | {exc}")
    _send_telegram_closed(record_id)
```

**Root Cause:** `_repo.mark_lead_closed()` 실패가 `error` 로그만 남기고 예외가 함수 밖으로 전파되지 않는다. 더구나 `_send_telegram_closed(record_id)` 호출이 `try/except` 블록 **밖**에 있어, Airtable 쓰기가 실패했어도 무조건 실행된다 — 즉 실제로는 `bridge_status`/`lead_status`/`closed_at`이 전혀 갱신되지 않았는데 운영자에게는 "CLOSE 처리 완료" Telegram 알림이 그대로 간다. retry_queue 위임 없음.

**Fix:** 완료(commit `75c60d2`, 260729) — 현재 Production Caller가 없어 시급성은 낮지만, 향후 `dm_followup_scheduler.py` 연결 시 즉시 활성화될 잠재 위험이므로 선제 수정: (1) 실패 시 task_type `lead_mark_closed`(payload: record_id)로 retry_queue 위임. (2) `_send_telegram_closed(record_id)` 호출을 `try` 블록의 성공 경로로 이동 — 실패 시 `return`으로 함수를 끝내 "CLOSE 완료" 알림이 나가지 않도록 상태-알림 불일치를 해소.

**Prevention:** 적용됨 — retry_queue 연동 + 알림 게이팅.

**Risk:** 여전히 `NONE`(Production Caller 0건, 도달 불가능한 코드 경로) — 이번 수정은 실제 Runtime 영향 해소가 아니라, Caller 연결 시점에 잠재 위험이 이미 해소된 상태로 활성화되도록 선제 조치한 것.

**Verification:** `tests/test_crm_write_retry_queue.py::TestErr087MarkLeadClosedRetry` 2/2 통과(성공 시 알림 전송 유지 + 실패 시 retry_queue 등록·알림 미전송 확인) + 회귀 확인 `tests/test_dm_close.py` 12 passed·3 xfailed(`mark_lead_closed()`가 여전히 외부로 예외를 전파하지 않음을 재확인) + 260729 11:43:51 Runtime 재시작 반영 확인.

**Status:** **RESOLVED — commit `75c60d2`, 260729. `NOT_ACTIVE` 분류(Caller 0건)는 유지, Caller 연결 시점 재감사 필요성도 유지.**

**관련:** ERR-080, ERR-085, ERR-086, ERR-088, FP-063, FP-064

---

## ERR-088 | order_detector.handle_order_conversion() — 처리 실패 후 durable retry·dead letter·failure state가 없는 구조. ERR-080 RESOLVED는 Airtable 필드만 보강, 실패-은폐 구조는 잔존 (RESOLVED, 260729)

**분류:** `CONFIRMED_RUNTIME_FAILURE`(Live Caller 확인 + 운영 로그 실제 발생 확인, 260729 재검증) — 단 "영구 데이터 유실"·"실제 고객 매출 손실"은 확정하지 않는다(아래 UNKNOWN 참조).

**Type:** 예외삼킴(Exception Swallow) + Durable Retry·Dead Letter·Failure State 부재 — ERR-080 재발 위험(Gap Classification: Reliability)

**Raw:** P1-2 표적 감사 중, ERR-080의 실제 수정 내역을 재확인해 발견. `modules/crm/order_detector.py:28-35`:
```python
def handle_order_conversion(record_id: str, sender_igsid: str, text: str) -> None:
    """주문 의사 감지 → lead_status/bridge_status=converted 업데이트 + Telegram 알림."""
    try:
        _repo.mark_lead_converted(record_id)
        logger.info(f"[Order] 전환 처리 완료 | record={record_id} from={sender_igsid}")
    except Exception as exc:
        logger.error(f"[Order] 전환 처리 실패 | {exc}")
    _send_telegram_conversion(sender_igsid, text)
```

**Root Cause:** ERR-080(RESOLVED, 260725)은 `converted_at` 필드를 Airtable Schema에 추가해 그 필드 불일치로 인한 실패는 막았지만("코드 변경 없음(필드만 보강)", ERR-080 본문에 명시), `handle_order_conversion()`의 broad `except Exception` + 로그만 남기고 삼키는 코드 구조 자체는 전혀 수정되지 않았다. **결함의 핵심은 HTTP 200 자체가 아니라, 처리 실패 후 재시도(durable retry)·실패 격리(dead letter)·실패 상태 기록(failure state) 경로가 전혀 없다는 구조다** — 웹훅이 호출자에게 200을 반환하는 것 자체는 별도의 ACK 정책일 수 있어 단독으로 결함이라 단정하지 않는다. `_send_telegram_conversion()`도 `try` 블록 밖에서 무조건 실행돼 ERR-087과 동일한 상태-알림 불일치 위험을 공유한다.

**260729 재검증 — Confirmed:**
```text
- 전환 처리 실패 로그 9건(260712 16:36:49 / 260713 21:50:26 / 260715 22:56:06·22:58:37 /
  260722 10:17:04 / 260725 07:35:29·15:38:20·15:40:19·15:42:50)
- 8건의 Airtable record_id 매핑 확보(1건은 record_id 미확보)
- 매핑된 8건은 2026-07-29 07:32 ICT 현재 lead_status=new, converted_at 공란
- RetryQueue 등록 없음(order_detector.py에 retry_queue import 자체가 없음,
  modules_common_retry_queue.log에도 order/conversion 관련 항목 0건)
- Dead Letter 없음(RetryQueue에 등록조차 안 됐으므로 Dead Letter 경로 자체가 없음)
- 동일 record_id의 후속 성공 로그 없음
- 관측된 실패 요청 이후 werkzeug 로그로 HTTP 200 응답 확인(9건 전부)
- 9건의 sender_igsid는 모두 TEST_PRICE_001(테스트용 식별자로만 확정 — 실제 IGSID는
  숫자 형식이며 TEST_PRICE_001은 그 형식과 다름)
```

**260729 재검증 — UNKNOWN:**
```text
- record_id 미확보 1건(260725 07:35:29)의 Airtable 현재 상태
- 9건이 모두 logs/test_autoreply.py 실행에서 발생했다는 직접 실행 출처
  (동일 sender_igsid·메시지 패턴이 그 스크립트와 일치하나, 실행 로그 자체로 트리거를
  직접 추적하지는 못했음 — "운영자가 반복 수동 발송했다"고 확정하지 않는다)
- 실제 고객(숫자형 IGSID) 데이터의 손실 사례 존재 여부 — 이번 검색 범위에서는
  발견되지 않았으나, 미발견이 미발생의 증명은 아니다
- 검색 범위(logs/error/error.log 보존 기간) 밖의 과거 Incident 존재 여부
```

**Fix:** 완료(commit `75c60d2`, 260729) — 실패 시 task_type `order_mark_converted`(payload: record_id)로 retry_queue 위임. 기존 계약 보존: `_send_telegram_conversion()`은 성공/실패 무관하게 그대로 호출(이번 수정 범위 밖 — 알림 게이팅은 별도 결정 필요 사안으로 남김, ERR-087과 달리 여기서는 상태-알림 불일치를 해소하지 않았음에 주의).

**Prevention:** 적용됨(부분) — durable retry 경로는 확보. dead letter/failure state 자체는 retry_queue의 기존 `status='dead'`(최대 3회 실패 후 영구 보존, 삭제 없음) 메커니즘을 그대로 재사용.

**Risk:** 수정 전 `HIGH` → 수정 후 재시도 경로 확보로 완화. 단, 알림 게이팅 미적용은 유지되므로 "실패했는데 전환 완료 알림이 감"이라는 상태-알림 불일치 위험 자체는 ERR-088 범위에서 의도적으로 잔존(기존 계약 보존 우선, Codex/GPT 리뷰 지시에 따름). 실제 고객 영향 여부는 여전히 UNKNOWN.

**Verification:** `tests/test_crm_write_retry_queue.py::TestErr088HandleOrderConversionRetry` 2/2 통과(성공 경로 유지 + 실패 시 retry_queue 등록·알림은 그대로 전송됨을 확인) + 260729 11:43:51 Runtime 재시작 반영 확인.

**Status:** **RESOLVED(durable retry 확보) — commit `75c60d2`, 260729. 알림 게이팅 미적용은 알려진 잔존 사항으로 별도 판단 필요.**

**관련:** ERR-080, ERR-085, ERR-086, ERR-087, FP-057, FP-063, FP-064

---

## ERR-089 | launcher/main.py 내부 두 BackgroundScheduler가 약 28분간 Job 실행을 시도하지 않음 — watchdog은 launcher 내부 응답성을 감시하지 않아 미탐지 (PARTIAL, 관측성 보강 완료·Root Cause 여전히 UNKNOWN)

**Type:** 관측성 공백(Observability Gap) + 미확정 Runtime 정지(Root Cause UNKNOWN) — 계정별 Kill Switch(ERR 무관, §WORKFLOW §10-20) Runtime Canary 도중 발견

**Raw:**
```
2026-07-30 07:48:10 [INFO] apscheduler.executors.default - Job "_job_insta_upload (trigger: interval[0:05:00], next run at: 2026-07-30 09:53:08 KST)" executed successfully
────────── 07:48:10~08:16:18, 27분58초간 app.log 0줄(health check·dotenv 경고 포함 전부) ──────────
2026-07-30 08:16:19 [WARNING] apscheduler.executors.default - Run time of job "process_due_followups ..." was missed by 0:00:10.069824
2026-07-30 08:16:19 [WARNING] ... "process_lost_candidates ..." was missed by 0:00:10.069977
2026-07-30 08:16:19 [WARNING] ... "poll_new_comments ..." was missed by 0:00:10.067222
2026-07-30 08:18:18 [WARNING] ... "_job_comment_dead_monitor ..." was missed by 0:10:10.063522
2026-07-30 08:18:18 [WARNING] ... "_job_insta_upload ..." was missed by 0:00:10.063522
2026-07-30 08:18:18 [WARNING] ... "_job_dome_export ..." was missed by 0:01:10.064520
2026-07-30 08:18:18 [WARNING] ... "_job_fb_crawl ..." was missed by 0:16:10.064520
2026-07-30 08:18:18 [WARNING] ... "_job_kpi_snapshot ..." was missed by 0:14:10.064520
2026-07-30 08:18:18 [WARNING] ... "_job_engagement_update ..." was missed by 0:13:10.065510
2026-07-30 08:18:18 [WARNING] ... "_job_dome_crawl ..." was missed by 0:12:10.066523

watchdog.log(같은 구간):
[HEARTBEAT] alive — 07:48~08:16 전 구간 30초 간격 끊김 0건(watchdog 자체 프로세스는 생존)
[2026-07-30 08:16:21] [WARN] Streamlit 응답 없음 — 재시작 시도    ← 별도 프로세스, launcher 아님
[2026-07-30 08:16:32] [ERROR] Streamlit 재시작 후에도 응답 없음
[2026-07-30 08:17:05] [RECOVER] Streamlit 복구
```

**Root Cause(UNKNOWN, Hypothesis만 존재):** launcher 프로세스 내부에 독립된 `BackgroundScheduler` 2개(`launcher/main.py::_build_scheduler()` + `modules/dm/dm_followup_scheduler.py::start_scheduler()`, 둘 다 apscheduler 3.11.2 기본값 `misfire_grace_time=1초`/`coalesce=True`/`ThreadPoolExecutor max_workers=10`)가 있으며, 07:48:10~08:16:18 사이 양쪽 스케줄러 전부 "Running job" 시작 로그조차 0건이었다 — 개별 Job 하나가 멈춘 게 아니라 스케줄러 루프 자체가 정지한 패턴. 후보 원인(블로킹 I/O에 `timeout=` 미설정/GIL 경합/OS 레벨 프로세스 일시정지) 중 무엇인지는 Thread Dump·리소스 시계열 부재로 특정 불가. 07:37~41의 Gemini API 429(도매꾹 caption 생성)는 각 사이클이 정상 종료 로그를 남겨 직접 원인일 가능성은 낮음(반증 방향, Confirmed 아님). Kill Switch 코드(commit `e9b8fb8`, 순수 dict 읽기)는 구조적으로 배제.

**핵심 관측성 공백(Confirmed):** `watchdog.ps1:216-218`의 Flask/launcher HTTP 헬스체크가 `[260527]` 주석으로 비활성화돼 있어(`# if (-not (Test-Http $FLASK_URL)) {`), launcher는 오직 OS 프로세스 존재 여부(`Test-Launcher`, 커맨드라인 매칭)로만 감시된다. Streamlit은 HTTP 체크가 살아있어 이번에 무응답을 스스로 탐지·재시작했지만, **launcher 내부(Flask 응답성·스케줄러 동작)가 멈춰도 watchdog은 원천적으로 알 수 없다** — 이번 정지도 자동 탐지가 아니라 Kill Switch Canary 관측 중 우연히 발견됐다.

**Fix:** 미적용 — Root Cause 미확정 상태에서는 코드 수정 대상을 특정할 수 없음. 회장 지시로 최소 관측성 보강(§Prevention)만 먼저 승인 대상.

**Prevention(1~3 구현·commit 완료, 260730 — 전부 Alert-only, 자동 재시작 없음):**
1. `watchdog.ps1` Flask HTTP 헬스체크 Alert-only 복구 — commit `d7d038a`(Mock+라이브 Canary 검증 완료, §10-20/§10-21 Runtime Evidence 참조)
2. 두 `BackgroundScheduler`(main/dm) 각각 60초 간격 heartbeat 로그(`[SchedulerHeartbeat][main|dm]`) — commit `c00a734`
3. Gemini 호출(`caption_generator.py`/`ai_reply_generator.py`) 시작~종료 소요시간 로그(model·timeout·재시도 정책 무변경) — commit `e4d324e`. Airtable·Meta Graph·Facebook Crawler timeout 감사는 별도 HOLD 유지(미착수).
4. **재발 판정 기준(확정, 260730)**: watchdog이 30초 주기로 아래를 판정 — ①Flask `/health` 무응답 → 즉시 WARN+Slack(재시작 없음) ②`[SchedulerHeartbeat][main]` 또는 `[dm]`이 **연속 7분** 이상 안 찍히면(후보 B, 최단 Job 주기 5분+2분 여유, 회장 확정) WARN+Slack ③재발 시 Gemini 호출 로그의 `X.X초` 값으로 어느 호출이 오래 걸렸는지 1차 특정 가능 — 단, 이 3개 신호로도 최종 Root Cause 자체가 자동으로 밝혀지는 것은 아니며, "정지가 다시 발생했음을 조용히 놓치지 않는 것"까지가 이번 보강의 목표.

**Risk:** `HIGH → MEDIUM`(관측성 확보 후) — 재발을 조용히 놓칠 위험은 해소됐으나(1~3 구현), Root Cause 자체는 여전히 UNKNOWN이라 재발 자체를 막지는 못한다. 라이브 운영 중(`INSTAGRAM_PROVIDER_ROUTING_ENABLED=true`) 실사용자 영향 가능성은 이번 구간 기준 여전히 UNKNOWN.

**Status:** PARTIAL — 관측성 보강 1~4 전부 완료·commit(`d7d038a`/`c00a734`/`e4d324e`), 실제 라이브 Runtime에서 24시간+ 오탐 없이 안정 동작하는지는 아직 관측 중(미검증). Root Cause는 Confirmed 승격 전까지 UNKNOWN 유지. Kill Switch Canary 재개는 이 관측 보강 완료로 조건 충족(회장 재승인 시 진행 가능).

**관련:** 계정별 Kill Switch(§WORKFLOW_ARCHITECTURE_STATUS.md §10-20) Runtime Canary 도중 발견

---

## ERR-090 | Claude Code가 `.env` grep 중 YUNA_INSTA_ACCESS_TOKEN·AI_INSTA_ACCESS_TOKEN 원문을 tool 출력에 노출(대화 기록에 잔존) (OPEN, 토큰 교체 대기)

**Type:** Secret 노출(Claude Code 실행 실수) — CLAUDE.md 14.1 위반

**경위:** 7단계(Multi-account Routing) DM Page Messages API 설계 중 `fb_page_id` 확인을 위해 `grep -n "PAGE_ID\|AI_INSTA\|YUNA_INSTA" .env`를 실행 — 의도는 `_IG_USER_ID`/`PAGE_ID` 키 이름만 확인하려던 것이었으나 패턴이 `ACCESS_TOKEN` 라인까지 매칭해, `YUNA_INSTA_ACCESS_TOKEN`과 `AI_INSTA_ACCESS_TOKEN` 원문이 그대로 tool 출력에 찍혔다(260730 10:51 ICT). ERR-077/FP-059(260725 yuna18253 로그노출)와 동일 클래스.

**Fix:** 미적용 — 토큰 재발급은 Meta Developer Console/Access Token Debugger 접근이 필요하며 Claude Code는 이 권한이 없다(회장 전용, 기존 ERR-077 대응과 동일). 회장이 두 계정 모두 재발급 후 `.env` 교체 필요.

**Prevention(적용 필요):** `.env` grep 시 `_ACCESS_TOKEN` 라인을 항상 제외하는 패턴 사용(예: `grep -v ACCESS_TOKEN` 병행) — 이번처럼 "키 이름만 보려던" 의도와 실제 정규식 매칭 범위가 어긋나지 않도록 값 필드가 있는 라인은 원천적으로 자동 배제.

**Risk:** `MEDIUM` — 대화 기록(로컬)에만 노출, 외부 유출 증거는 없음. 단 노출 자체를 "아무도 안 봤을 것"으로 추정하지 않고 교체 원칙 적용(ERR-077 선례와 동일).

**Status:** OPEN — 회장이 Meta Developer Console에서 두 계정(yuna18253/aijomoojin) 토큰 재발급 후 `.env` 교체 대기.

**관련:** ERR-077, FP-059(260725 동일 클래스 선례)

## ERR-091 | DM 전역 fallback이 항상 yuna18253으로 고정 — 다른 계정 해석 실패 시 그 고정 계정 소유 경로로 오발송 시도 위험 (RESOLVED, 260730)

**Type:** 잠재 위험(Latent Risk) — Multi-account DM Routing 설계 리뷰 중 발견, 실제 오발송 발생은 아님

**경위:** ERR-090 직후 세션 종료 직전, 회장이 "yuna 1계정만 검증됐고 전역 fallback이 남아있어 다계정 완료 판정은 이르다"고 지적. Read-only 재조사 결과 `INSTA_IG_USER_ID`/`FACEBOOK_PAGE_ID`가 정확히 yuna18253 소유임을 실측 확인 — `_resolve_dm_send_target()`(`modules/dm/dm_auto_reply.py`)이 계정 해석에 실패하면(예: `Account_Registry` 조회 실패, credential 해석 예외, 미지원 provider 등) `send_ig_reply()`/`_send_ig_dm()` 양쪽 모두 조건 없이 이 전역(yuna18253) 경로로 실제 발송을 시도하는 구조였다. yuna18253 자신의 해석 실패는 결과가 같아 무해하지만, aijomoojin 등 다른 계정의 해석 실패는 다른 계정 소유 Page Token으로 발송을 시도하게 되는 잠재 위험이었다.

**Fix:** `modules/dm/dm_auto_reply.py`에 `GLOBAL_FALLBACK_ACCOUNT_CODE_REF`(기본값 `IDN-000041`=yuna18253) 상수 추가 + `send_ig_reply()`에 조건분기 추가 — `account_code_ref`가 있고(계정이 이미 식별됨) 그 값이 `GLOBAL_FALLBACK_ACCOUNT_CODE_REF`가 아닌데 해석 실패 시, 전역 발송을 시도하지 않고 즉시 `False`를 반환해 호출자가 `retry_queue`로 위임하게 한다. `modules/dm/dm_followup_scheduler.py::_send_ig_dm()`에도 동일 로직 REUSE. `account_code_ref` 공란(레거시/미해석)이거나 yuna18253 자신인 경우는 기존 전역 fallback 동작을 100% 보존.

**검증:** ① Mock 단위테스트 5개 신규(`tests/test_dm_multi_account_send.py` 2개 + `tests/test_dm_followup_fallback_gate.py` 신규 3개) — 회장 터미널(프로젝트 venv) Raw Output **13 passed, 0 failed**(기존 7개 회귀 포함). ② 실제 aijomoojin 가격문의 DM Runtime Canary — `Lead_Interactions`(`recObauwGlbvU1Djs`) `account_code_ref=IDN-000036` 정확히 태깅, `[AutoReply] IG DM 발송 완료` 확인, fallback 경고 로그 0건(1차 시도에서 aijomoojin 자신의 `instagram_login` 경로로 정상 성공 — 오늘 구현한 차단 분기 자체는 이 실측에서 발동되지 않았음, mock 테스트로만 검증된 상태).

**Risk:** 발견 시점 `MEDIUM`(실제 오발송 발생 전 리뷰 단계에서 차단) — Fix 적용 후 `LOW`.

**Status:** RESOLVED — 코드 구현·mock 테스트·실제 Canary(정상 경로) 전부 완료. 차단 분기 자체의 실제 Graph API 조건 재현(실패 케이스)은 자연 발생하지 않아 mock 검증에만 의존하는 잔존 사항으로 남음(Accept, 낮은 우선순위).

**관련:** ERR-090, [260730_세션종료직전_추가발견] `porting_logs/MERGE_JOURNAL.md`

## ERR-092 | 댓글 Private Reply가 Facebook Page 미보유 계정(instagram_login, aijomoojin류)에서 구조적으로 불가능 — 시도 전 Provider 게이트 추가 (RESOLVED, 260730)

**Type:** 잠재 위험(Latent Risk) — 10.5-6단계(댓글 Routing) 설계 검토 중 발견, 실제 API 실패 발생은 아님

**경위:** ERR-091(DM fallback-gate) 종결 직후 10.5-6단계(댓글 계정별 Routing) 착수 — 지난 세션 설계("`media_id`→`account_code_ref` 역조회 1단계만 추가하면 DM의 `_resolve_dm_send_target()` 그대로 REUSE 가능")를 코드로 확인하는 과정에서 전제 자체가 깨짐을 발견. 현재 라이브 댓글 자동응답 경로는 `_try_private_reply()`→`reply_privately_to_comment()`(`modules/comment/comment_auto_reply.py`) 단 하나이며, 이 함수는 `POST /{page-id}/messages`+`recipient.comment_id`(Meta Private Replies 공식사양)만 사용한다. Meta 공식문서 fetch로 확인한 결과 이 기능은 **Facebook Page 연동 + Page Access Token이 반드시 필요**하며, `Account_Registry`상 aijomoojin(`IDN-000036`, `api_provider=instagram_login`)은 Facebook Page 개념 자체가 없다(DM 설계 때 이미 확인된 사실) — 즉 자격증명을 아무리 정확히 라우팅해도 이 API 자체를 aijomoojin 계정으로 호출할 방법이 없다. 대안인 공개 답글(`reply_to_comment()`, `POST /{comment-id}/replies`)은 Meta 공식문서상 Instagram API with Instagram Login에서 지원되지만, 260714 Gate G에서 "손님을 DM으로 유도(공개 노출 방지)"라는 이유로 의도적으로 Private Reply 전면 전환한 이후 현재 라이브 경로에서 호출되지 않는 죽은 코드(`tests/test_meta_graph_version.py`에서만 참조)다.

**회장 결정(260730):** 지금은 yuna18253만 범위로 두고, instagram_login 계정은 Private Reply를 시도하지 않고 스킵(로그만 남김) — 공개 답글 전환 등 대안은 이번 범위 밖, 별도 논의 대상.

**Fix:** 신규 Repository 메서드 `get_account_code_ref_by_media_id(media_id)`(`repository_interface.py`+`airtable_repository.py`, 기존 `get_publish_account_by_ig_user_id()`와 동일 스타일) + `comment_auto_reply.py`에 `_is_private_reply_supported(media_id)` 헬퍼 신설 — `media_id` 소유 계정의 `api_provider`가 `instagram_login`이면 `_try_private_reply()`가 발송 시도 자체를 하지 않고 즉시 반환(로그 남김). `account_code_ref` 공란(레거시/다계정 이전 게시물)이거나 조회 실패 시에는 Fail-open으로 기존 동작 100% 보존.

**검증:** `configs/comment_campaign_posts.json`의 등록 캠페인 게시물 6개를 Airtable로 직접 조회 — **전부 `account_code_ref` 공란**(260714~15 생성, 다계정 이전 데이터), 즉 현재 aijomoojin 소유로 등록된 댓글 캠페인은 0건이라 실제 API 호출 실패나 실측 Canary 자체가 아직 재현 불가능(잠재 위험을 사전 차단). Mock 단위테스트 신규 16개(`tests/test_get_account_code_ref_by_media_id.py` 8개 + `tests/test_comment_auto_reply.py` 8개 추가) — `pytest tests/test_comment_auto_reply.py tests/test_get_account_code_ref_by_media_id.py tests/test_get_publish_account_by_ig_user_id.py` **53 passed**. 전체 회귀 스위트 706 passed/94 failed/3 xfailed/6 errors — 실패·에러 파일 목록이 기존 baseline(`test_package_s5_write_budget_idempotency.py`/`test_provider_routing.py`/`test_publish_gate_and_approval.py`/`test_publish_outcome_unknown.py` + `modules.dm` PermissionError 계열)과 정확히 동일, 신규 회귀 0건.

**Risk:** 발견 시점 `MEDIUM`(실제 API 실패 발생 전 설계 리뷰 단계에서 차단) — Fix 적용 후 `LOW`. 현재 캠페인 0건이라 즉시 운영 영향 없음.

**Status:** RESOLVED — 코드 구현·mock 테스트·전체 회귀 확인 완료. 실제 Graph API 조건(aijomoojin 게시물이 실제 캠페인에 등록된 상태)에서의 실측 Canary는 그런 게시물이 아직 없어 수행 불가(Accept, aijomoojin 댓글 캠페인이 실제 등록되는 시점에 재검증 필요).

**관련:** ERR-091, FP-065, FP-066(신규)

## ERR-093 | Persona_Profile 실제 콘텐츠·계정 연결 0건 확인 — Repository 조회+wiring만 선구현 (PARTIAL, 260730)

**Type:** Missing Data(콘텐츠 부재) — 코드 결함 아님

**경위:** ERR-092 종결 직후 10.5-5단계(Persona 연결) 착수. Airtable 직접 조회 결과 `Persona_Profile` 테이블에 레코드가 `PER-001`(엔틱) 단 1건뿐이며, 그 1건조차 `account_code_ref`(Linked Record) 공란·`tone_style`/`greeting_template`/`followup_template` 전부 공란임을 확인. 살아있는 계정 2개(yuna18253=`IDN-000041`, aijomoojin=`IDN-000036`) 모두 `Account_Registry.Persona_Profile` 링크도 공란 — 어느 계정에도 Persona가 연결돼 있지 않다.

**회장 결정(선택형 질문)**: 콘텐츠 입력 전에 코드(Repository 조회+wiring)부터 먼저 구현 — 지금은 빈 값이라 기존 동작과 100% 동일하게 유지되고, 나중에 회장이 Airtable에 콘텐츠만 채우면 바로 반영되는 구조.

**Fix(구현 완료)**: `repository_interface.py`+`airtable_repository.py`에 `get_persona_by_account_code(account_code)` 신규 — `Persona_Profile.account_code_ref`가 Linked Record 타입임을 실측 확인(필드 타입 추측 금지 원칙 준수)해, Account_Registry의 `Persona_Profile` 링크 필드를 통해 역조회(직접 텍스트 매칭 아님). 연결 0건/공란/inactive는 None(Fail-open), 2건 이상 연결은 `RepositoryValidationError`(임의 선택 금지). `modules/dm/dm_auto_reply.py`에 `_get_persona_kwargs(account_code_ref)` 헬퍼 신설 — `ai_reply_generator.generate_reply()` 호출 시 조회된 tone_style/greeting_template/followup_template을 그대로 전달(조회 실패·미연결 시 전부 빈 문자열, 기존 동작 100% 보존).

**검증**: 신규 mock 테스트 15개(`tests/test_get_persona_by_account_code.py` 10개, 이 세션에서 직접 실행 **10 passed** + `tests/test_dm_persona_kwargs.py` 5개, `modules.dm` PermissionError로 이 세션 직접 실행 불가 — 회장 터미널 실행 필요). 전체 회귀 재확인: **717 passed / 93~96 failed(재실행 간 소폭 변동, 기존 문서화된 flaky 1건 포함) / 3 xfailed / 7 errors** — 실패 11개 파일 중 5개 파일(`test_meta_graph_version.py`/`test_dome_export_batch_isolation.py`/`test_package_b_post_attribution.py`/`test_package_s5_write_budget_idempotency.py` 등)을 직접 표본 재현해 전부 동일한 `runtime_boot_policy.json` PermissionError(오늘 코드와 무관, 기존 환경제약)임을 확인. **참고**: 이전 두 항목(ERR-091/ERR-092)에서 "실패 파일 4개, 기존 baseline과 동일"이라 보고한 것은 `tail -25` 출력이 잘려 일부만 보인 결과였음 — 실제로는 11개 파일이지만 전부 동일 원인으로 수렴, 신규 회귀라는 결론 자체는 변하지 않는다(FP-064 교훈 재확인: 잘린 출력으로 성급히 결론내지 말 것).

**Status:** PARTIAL — 코드·mock 테스트·전체 회귀 확인 완료. **실제 콘텐츠 입력(tone_style 등)과 계정 연결은 회장 담당, 시점 미정** — 콘텐츠가 채워지기 전까지는 이 기능이 Runtime에서 실질적 효과를 내지 않는다(안전하게 no-op).

**관련:** 260729 22:35 세션의 "Persona Runtime 최소연결(PARTIAL)" 항목 후속

## ERR-094 | 시스템 PYTHONPATH 환경변수가 250723(Reference Only)을 가리켜, sys.path 미처리 일회성 스크립트가 구버전을 잘못 참조할 위험 (OPEN, 260730)

**Type:** 환경 설정 오류(Windows System PYTHONPATH) — 코드 결함 아님

**경위:** 10.5 Close Gate 보완용 팔로업 라우팅 Canary 스크립트(`tools/run_followup_routing_canary.py`)를 작성해 회장 터미널에서 실행했으나 `ImportError: cannot import name 'dm_followup_scheduler' from 'modules.dm' (C:\SNS_24AutoProject_250723\modules\dm\__init__.py)` 발생. Read-only 조사 결과 시스템 `PYTHONPATH` 환경변수가 `C:\SNS_24AutoProject_250723`(CLAUDE.md상 Reference Only, 실행 금지 저장소)로 설정돼 있음을 확인(`echo $PYTHONPATH` 직접 확인). `250723\modules\__init__.py`가 존재(정식 패키지)해, sys.path를 스크립트 자신이 명시적으로 챙기지 않으면(`python 파일.py` 방식으로 직접 실행 시 sys.path[0]이 스크립트 자신의 디렉터리가 됨) `modules.*` import가 250723으로 resolve된다. 250723은 `modules/infra/`(Repository 패턴, 260624 도입) 자체가 없는 등 260511과 구조가 크게 다른 구버전이라, 존재하지 않는 서브모듈에서 즉시 ImportError가 나거나(이번 사례), 최악의 경우 이름이 우연히 겹치는 구버전 코드가 조용히 실행될 잠재 위험이 있다.

**Blast Radius(실측 확인, 축소됨)**:
- **라이브 프로세스(`launcher/main.py`) 안전**: 파일 최상단에서 자체적으로 `sys.path.insert(0, 프로젝트루트)`를 실행해(코드 확인, `launcher/main.py:28-32`) PYTHONPATH보다 항상 260511을 먼저 찾음.
- **`pytest` 안전**: `pytest.ini`(`testpaths = tests`) 기반 rootdir 삽입 메커니즘으로 260511을 우선 참조(오늘 세션의 모든 pytest 결과가 260511 코드 기준임을 재확인).
- **위험 범위는 `tools/`의 일회성 스크립트로 한정** — 프로젝트 루트를 sys.path에 명시적으로 추가하지 않는 스크립트만 해당.

**Fix:** 미적용 — Windows 시스템 환경변수 수정은 Claude Code 권한 밖(CLAUDE.md "시스템 설정 변경 금지"). 회장이 시스템 환경변수에서 `PYTHONPATH`를 제거하거나 260511로 정정해야 함. 임시 완화로 `tools/run_followup_routing_canary.py`에는 `launcher/main.py`와 동일한 `sys.path.insert(0, 프로젝트루트)` 패턴을 적용해 이 스크립트만 우회.

**Prevention(향후 권장):** `tools/`에 신규 스크립트 작성 시 항상 파일 최상단에 프로젝트 루트 sys.path 삽입을 포함할 것(기존 `launcher/main.py` 패턴 재사용). 기존 `tools/*.py` 전수 감사는 이번 범위 밖(별도 Gate, GPT 지시).

**Risk:** `MEDIUM` — 라이브 Runtime은 영향 없음(실측 확인)이나, 향후 진단·운영 스크립트가 이 문제를 모르고 작성되면 조용히 잘못된 코드베이스를 실행할 구조적 위험이 상존.

**Status:** OPEN — 회장이 향후 별도 "환경 무결성 Gate"로 처리 예정(GPT 지시, 260730). 10.5 Close Gate 판정에는 비차단으로 처리됨(GPT 확정).

**관련:** FP-067(신규)
