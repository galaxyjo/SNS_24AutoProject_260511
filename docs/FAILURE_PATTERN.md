# FAILURE_PATTERN.md
> Generated: 2026-05-16 | Status: ACTIVE | Version: v1.1
> Scope: SNS_24AutoProject / 260511 SOURCE OF TRUTH

---

## CORE PRINCIPLE

```
텍스트(Text) ≠ 실제 상태(Runtime Reality)
대화 기록은 증거가 아니다.
실제 파일 + Runtime + DB + Git 상태만 증거로 인정한다.
```

---

## FP-001 | Fake Completion Declaration
**설명:** 파일/기능이 실제 없는데 "완료" 선언됨
**근본 원인:** GPT/Claude 텍스트 출력 = 실제 파일 생성으로 오인
**증상:** 나중에 파일 없음 / import 실패 / 문서 참조 실패
**예방:**
```powershell
# 완료 선언 전 반드시 실행
Get-ChildItem -Path "경로" -Filter "파일명"
git log --oneline -3
```

---

## FP-002 | Runtime Drift
**설명:** 문서 구조 ≠ 실제 Runtime 구조
**근본 원인:** 리팩토링 후 검증 누락 / import path 변경
**증상:** ModuleNotFoundError / stale runtime / old module import
**예방:** Runtime verification 필수 / absolute path 사용

---

## FP-003 | Ghost Success
**설명:** 실제 실패인데 성공처럼 보이는 현상
**근본 원인:** Exception swallow / print만 성공 / Runtime 실패 hidden
**증상:** PASS 로그 존재 + 실제 동작 실패
**예방:** Real execution verification / log evidence / output validation

---

## FP-004 | Multi-Repo Divergence
**설명:** 250723 / 260511 repo 간 상태 불일치
**근본 원인:** 문서 sync 없음 / 파일 복사 기반 운영
**증상:** 서로 다른 main.py / import mismatch / duplicate modules
**예방:** Single Source of Truth(260511) 유지 / MasterTree 계약 준수

---

## FP-005 | Hallucinated Artifact
**설명:** AI가 존재하지 않는 artifact를 존재한다고 판단
**근본 원인:** Context assumption / prior text trust / filesystem 미검증
**증상:** "완료" 기록 존재 + 실제 파일 없음
**예방:** Evidence-based only 원칙 / Get-ChildItem 필수

---

## FP-006 | sys.path 오염
**설명:** sys.path.insert 남발로 runtime import 경로 불확정
**근본 원인:** 임시 패치 누적
**증상:** 어느 파일이 실행되는지 모름 / 버전 혼재
**예방:** absolute path 고정 / sys.path 임시패치 금지

---

## FP-007 | .fixed.py 누적
**설명:** 수정본 파일(.fixed.py)이 누적되어 어느 게 실행되는지 불명확
**근본 원인:** 원본 보존 없는 patch 방식
**증상:** duplicate runtime / ghost bug
**예방:** .fixed.py 생성 금지 / git branch로 관리

---

## FP-008 | UI State Assumption
**설명:** Instagram UI 상태 검증 없이 다음 단계 진행
**근본 원인:** nav/create 버튼 존재 미확인
**증상:** Create button not found / nav wait timeout
**예방:** 각 UI 단계 state validation 필수

---

## FP-009 | DB Schema Mismatch
**설명:** 코드와 실제 DB schema 불일치
**근본 원인:** schema 변경 후 migration 미적용
**증상:** no column named post_id / OperationalError
**예방:** schema_governance.md 기준 / migration forbidden rule 준수

---

## FP-010 | Duplicate Module Execution
**설명:** 동일 기능 모듈이 2개 이상 동시 실행
**근본 원인:** legacy + new 병존
**증상:** 수정했는데 적용 안 됨 / 다른 파일이 실행됨
**예방:** Feature Matrix 기준 / Source of Truth 1개만 실행

---

## FP-011 | Token/Session Expiry Silent Fail
**설명:** token/session 만료인데 오류 없이 빈 결과 반환
**근본 원인:** Exception 미처리 / silent fail
**증상:** 빈 결과 / 응답 없음 / timeout
**예방:** token lifecycle 명시적 관리 / expiry 사전 체크

---

## FP-012 | Partial Success Illusion
**설명:** 일부 단계만 성공했는데 전체 성공으로 판단
**근본 원인:** E2E 검증 없이 단계별 PASS 확인
**증상:** 로그 성공 + 실제 업로드/DM 미발송
**예방:** E2E flow 전체 검증 / production_verified 기준 엄격 적용

---

## FP-013 | Evidence-less PASS 선언
**설명:** 실제 검증 없이 VALIDATION_STATUS PASS 처리
**근본 원인:** 대화 기록만 보고 판단
**증상:** Phase 진입 후 미완성 발견
**예방:** PASS 선언 전 체크리스트 전항목 실제 확인 필수

---

## FP-014 | Launcher Silent Stop
**설명:** `main.py`가 조용히 종료됐는데 아무도 모름
**근본 원인:** watchdog / 프로세스 모니터링 없음
**증상:** 크롤링/업로드 중단 / DB 신규 기록 없음 / `crawl_stats.db` 타임스탬프 정지
**예방:** 프로세스 생존 확인 자동화 / watchdog.ps1 상시 실행 / 주기적 포트 확인

---

## FP-016 | Inner Except Swallows Exception — Decorator Alert Lost
**설명:** 함수 내부 `except`가 예외를 캐치·처리하면 `@handle_errors(notify_fn=...)` 데코레이터에 예외가 전달되지 않아 알림 누락
**근본 원인:** 레코드별 재시도 루프 안의 `except Exception` 이 예외를 소비 → 함수 정상 종료처럼 보임
**증상:** Airtable failed 마킹은 되나 Slack/Telegram 알림 없음 — 운영자가 token 만료를 인지 못함
**해결:** token 오류 등 치명적 예외는 내부에서 `notify_fn` 직접 호출 후 `raise`로 재전파
**예방:** `@handle_errors` 의존 알림은 예외가 함수 밖으로 나와야 함 — 내부 except 범위 설계 시 치명/일반 오류 분리
**관련:** ERR-017 / 2026-05-17 수정 확인

---

## FP-015 | CDN URL Expiry Silent Upload Fail
**설명:** Facebook CDN 이미지 URL을 그대로 Instagram API에 전달 시 업로드 실패
**근본 원인:** Facebook CDN URL은 일정 시간 후 만료됨 — Instagram Graph API가 접근 불가
**증상:** 업로드 요청 성공처럼 보이나 media_id 미생성 / 또는 aspect ratio 오류로 위장
**해결:** imgbb API로 이미지를 재업로드 → 영구 URL 획득 후 Instagram API 전달
**예방:** 크롤 시점에 imgbb 업로드 완료 후 영구 URL만 Airtable에 저장
**관련:** ERR-013 / INC-010 / 2026-05-17 해결 확인

---

## FP-017 | Watchdog 감시 대상과 진입점 내부 기동이 충돌하는 패턴
**설명:** watchdog이 독립 서비스(A)를 기동하는데, 진입점(B)도 내부에서 동일 서비스(A)를 포함하는 구조 → A 중복 실행
**근본 원인:** 서비스 책임 경계 미정의. watchdog이 "Flask는 내가 감시한다" + launcher도 "Flask는 내가 실행한다" → 충돌
**증상:** 동일 포트 이중 바인딩 / APScheduler 이중 등록 / 동일 잡 N회 실행 / 로그에 동일 패턴 시간 간격
**해결:** watchdog은 진입점(launcher)만 감시. 내부 서비스 기동은 진입점에 위임.
**예방:** watchdog 기동 대상 정의 시 "이 서비스가 다른 프로세스 내부에도 포함되는가" 반드시 확인. 포함되면 watchdog 직접 감시 제거.
**관련:** ERR-021 / 2026-05-27 해결 확인

**재발 사례 (2026-07-08):** ERR-050 완화 작업 중 PID 22908(direct, 새벽 수동 복구)과 PID 29076/30888(wrapper, Task Scheduler 트리거)이 동시 생존 확인 → 세션 승인 하에 wrapper 계열 정리. 동일 패턴이 watchdog 자체의 이중 감시 형태로 재발함을 확인.

---

## FP-018 | PowerShell chcp 65001 미설정 — 한글 깨짐
**설명:** PowerShell 기본 코드페이지(CP949)에서 Python 스크립트 한글 출력 시 깨진 문자 표시
**근본 원인:** Windows PowerShell 기본 인코딩 ≠ Python UTF-8 stdout
**증상:** 로그·출력에 `???` 또는 알 수 없는 문자 출력 / 오류 메시지 판독 불가
**예방:**
```powershell
# Python 스크립트 실행 전 항상 먼저 실행
chcp 65001
```
**관련:** ERR-022 / 2026-05-28 확인

---

## FP-020 | Runtime Proof 없이 commit 누적
**설명:** 코드 패치를 여러 단계 commit 했으나 실제 Airtable 저장 1건도 확인하지 않은 상태
**근본 원인:** py_compile + git diff 통과 = 동작 확인으로 오인. 실제 FB 피드 → 저장까지 E2E 미검증
**증상:** commit 6개 쌓인 후 Runtime에서 0개 처리 / 피드 언어 불일치 / .env 미로드 등 뒤늦게 발견
**예방:** 기능 commit 전 반드시 one-shot crawler 단발 실행 → Airtable record 1건 직접 확인
**관련:** 260601 Clone Mode 진단 세션

---

## FP-021 | Facebook 더보기(See more) 미클릭으로 원문 누락
**설명:** Selenium이 `post.text`를 읽을 때 `더 보기` 클릭 전 truncated 텍스트만 수집
**근본 원인:** Facebook은 긴 게시글을 `더 보기` 뒤에 숨김. Selenium `post.text`는 보이는 텍스트만 반환
**증상:** `text_len: 63` (실제 전문 581자) → 키워드 미매칭 → 필터 제외
**해결:** `expand_see_more(post, driver)` 추가 — post.text 읽기 전 클릭 시도, 실패 시 silent skip
**예방:** Clone Mode에서 원문 보존이 목적이므로 더보기 클릭은 필수 보정
**관련:** deec24c / 260601 Runtime Proof

---

## FP-022 | 베트남어/중국어 게시글을 필터 버그로 오인
**설명:** `detect_and_translate()`가 베트남어 텍스트에 `""` 반환 → 필터 제외 → 버그 의심
**근본 원인:** `_has_excluded_language()` 설계대로 베트남어/중국어 차단. 버그 아님
**증상:** `POST N 필터 제외` 로그 + `필터_text: (빈값)` → 오인 가능
**예방:** 필터 제외 시 원문을 진단해 언어 확인 후 판정. 베트남어/중국어는 설계 차단
**관련:** 260601 진단 — `raw_after: Khánh Sun ... NMN 36000 – Hỗ trợ ...` 확인

---

## FP-023 | clean_contact_info() 선처리 후 replace_contacts() 치환 실패
**설명:** `run()` 에서 `clean_contact_info(text)` 가 연락처를 먼저 제거하면, 이후 `replace_contacts()` 가 치환할 패턴 없음
**근본 원인:** Phase 3 패치로 `clean_contact_info()` 를 clone 경로에서 제거, `replace_contacts(raw_text)` 로 교체. 두 함수의 역할 혼동 시 재발 가능
**예방:** clone 경로에서 `clean_contact_info()` 재투입 금지. `replace_contacts()` 만 사용
**관련:** b059740 Phase 3 패치

---

## FP-024 | data/processed_comment_ids.json commit 혼입
**설명:** `git add .` 사용 시 `data/processed_comment_ids.json` 이 commit에 혼입됨
**근본 원인:** comment_poller 캐시 파일이 `data/` 에 생성됨. `.gitignore` 미등록 상태
**증상:** commit에 런타임 캐시 파일 포함 → 다음 pull 시 comment 중복 처리 위험
**예방:** `git add .` 절대 금지. 파일명 지정 add만 허용. `data/` 폴더 gitignore 확인
**관련:** 현재 `data/processed_comment_ids.json` untracked 유지 중

---

## FP-019 | watchdog 미기동 시 Flask 수동 실행 패턴
**설명:** watchdog.ps1이 실행되지 않은 상태에서 세션 시작 시 Flask(:5000), ngrok, launcher 모두 미기동 상태일 수 있음
**근본 원인:** watchdog.ps1은 자동 시작 등록 없이 수동 실행 — 재부팅·세션 종료 후 미기동
**증상:** curl :5000 연결 거부 / webhook 수신 불가 / ngrok URL 없음
**체크:**
```powershell
# 세션 시작 시 포트 확인
netstat -ano | findstr ":5000"
netstat -ano | findstr ":4040"
```
**복구 순서:**
1. `.\watchdog.ps1` 기동 (별도 터미널)
2. 또는 `python launcher/main.py` 직접 실행
3. ngrok 별도 기동 필요 시: watchdog에 포함됨 확인
**관련:** ERR-024 / 2026-05-28 확인

---

## FP-020 | Airtable 미존재 필드 기반 IS_AFTER 필터 무력화
**설명:** `IS_AFTER({replied_at}, ...)` 같이 Airtable에 실제 존재하지 않는 필드를 filterByFormula에 사용하면 항상 빈 결과 반환
**근본 원인:** Airtable 테이블에 해당 컬럼이 없어도 API 오류 없이 빈 records[] 반환 → 가드 로직이 항상 False 판정
**증상:** 중복 방지 로직이 존재하는데 실제로는 무력화 — 중복 발송 계속 발생
**해결:** 미존재 필드 의존 금지 — Airtable 내장 필드(`CREATED_TIME()`) 사용
**예방:** filterByFormula에 커스텀 필드 사용 시 해당 필드 존재 여부 사전 확인 필수
**관련:** ERR-026 / 2026-05-28 해결 확인

---

## FP-021 | 명시적 kwargs가 기본값 변경을 무력화
**설명:** 함수 기본값을 변경해도 호출부에서 명시적으로 값을 전달하면 기본값 변경이 무의미
**근본 원인:** `def f(x=3)` 으로 변경했으나 `f(x=10)` 호출부가 남아있음 — 실제 동작은 10
**증상:** 기본값 변경 후 재검증 시 이전과 동일한 동작 — 수정 미적용처럼 보임
**해결:** 기본값 변경 시 호출부도 함께 확인/수정
**예방:** 기본값 변경 후 반드시 `grep` 으로 호출부 전수 확인
**관련:** 2026-05-28 minutes=10→3 수정 과정에서 발견

---

## FP-022 | accounts.json 빈 배열 → account_manager default 폴백 → crawl_urls 고정 빈 리스트
**설명:** `configs/accounts.json`이 `[]`이면 account_manager가 `.env` 단일 계정으로 폴백하는데, 이 default 계정은 `crawl_urls=[]`로 하드코딩되어 있음 → FB_GROUP_URL을 `.env`에 추가해도 크롤러가 읽지 않음
**근본 원인:** account_manager의 default 계정 생성 로직이 `crawl_urls=[]` 고정값 사용 — `.env` `FB_GROUP_URL` 참조 없음
**증상:** `[WARNING] crawl_urls 없음 — skip | account=default` 반복 — .env 변경해도 해소 안 됨
**해결:** `configs/accounts.json`에 계정 1개 이상 등록 (name / adspower_user_id / crawl_urls 포함)
**예방:**
```json
[{ "name": "account1", "adspower_user_id": "...", "crawl_urls": ["https://..."], ... }]
```
크롤러 기동 후 `crawl_urls 없음 — skip` 로그 유무로 즉시 확인
**관련:** ERR-027 / 2026-05-29 해결 확인

---

## REQUIRED VALIDATION CHECKLIST
모든 완료 선언 전:
- [ ] File Exists (Get-ChildItem)
- [ ] Git Commit Verified (git log)
- [ ] Runtime Verified
- [ ] DB Verified
- [ ] Log Evidence Exists
- [ ] Actual Output Checked

---

## OPERATION STANDARD
```
신뢰 순서:
1. Filesystem
2. Runtime
3. Git
4. DB
5. Logs

대화는 참고자료일 뿐이다.
```

## FP-026 | load_dotenv() 경로 미지정 + 시스템 환경변수 플레이스홀더 → .env 무시
**설명:** `load_dotenv()` (경로 인자 없음)는 `find_dotenv()`로 호출 스크립트 위치에서 상위로 탐색. 스크립트가 `%TEMP%` 등 프로젝트 외부 경로에서 실행되면 `.env`를 찾지 못하고 시스템 환경변수 우선 적용
**근본 원인:** 1) `find_dotenv()` 탐색 기준 = 호출 스크립트 파일 위치 (CWD 아님) 2) User/Machine 수준 환경변수에 한국어 플레이스홀더 잔존 시 non-ASCII 값이 덮어씌워짐
**증상:** `AIRTABLE_API_KEY` len=10 / non-ASCII / latin-1 UnicodeEncodeError → Airtable API 헤더 인코딩 실패 → 모든 Airtable 연동 차단
**해결:**
```python
from dotenv import load_dotenv
load_dotenv(dotenv_path=r'C:\SNS_24AutoProject_260511\.env', override=True)
```
시스템 환경변수 플레이스홀더 제거: `[System.Environment]::SetEnvironmentVariable("KEY", $null, "User")`
**예방:** 모든 단발 실행 스크립트에서 절대경로 `dotenv_path` 지정 필수. 시스템 환경변수에 플레이스홀더 절대 설정 금지
**관련:** ERR-036 / INC-018 / 2026-06-02 해결 확인

---

## FP-025 | PowerShell Set-Content -Encoding UTF8 → BOM 삽입 → JSON 파싱 실패
**설명:** PowerShell 5.1의 `Set-Content -Encoding UTF8`은 파일 앞에 UTF-8 BOM(EF BB BF)을 삽입함. Python `json.load()`는 일반 UTF-8로 읽으므로 BOM 감지 시 `Unexpected UTF-8 BOM` 파싱 에러 발생
**근본 원인:** PowerShell 5.1 기본 UTF8 인코딩 구현이 BOM 포함. Python `open(encoding='utf-8')`은 BOM 미처리
**증상:** `[AccountManager] accounts.json 파싱 실패 | Unexpected UTF-8 BOM (decode using utf-8-sig)` → 계정 설정 없음 → crawl_urls skip
**해결:** `[System.IO.File]::WriteAllText(path, content, [System.Text.UTF8Encoding]::new($false))` 사용
**예방:**
```powershell
# JSON/설정 파일 저장 시 반드시 BOM-free 방식 사용
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText("경로", $content, $utf8NoBom)
# Set-Content -Encoding UTF8 절대 금지 (JSON/환경설정 파일에)
```
**관련:** ERR-035 / c6a30d1 / 2026-06-02 수정 확인

---
## FP-027 (260603)
- 증상: watchdog 미실행 → Flask dead
- 원인: LocalMachine ExecutionPolicy=Restricted → .ps1 실행 차단
- 에러코드: 0xC000013A (작업스케줄러 LastTaskResult)
- 해결: Set-ExecutionPolicy RemoteSigned -Scope LocalMachine -Force
- 재발방지: watchdog.ps1 상단 자가치유 블록 삽입 (커밋 2695d87)

---

## FP-028 | Airtable 필드 UI 추가 후 재소멸 — 코드 의존 필드 선언 누락
**설명:** Airtable 테이블에 필드를 UI에서 추가했으나 이후 세션에서 해당 필드가 없는 상태로 재발. 코드에서 신규 필드를 사용하면서도 해당 필드를 Airtable Schema에 공식 선언하지 않으면 재발 가능.
**근본 원인:** Airtable UI 수동 추가는 코드/문서와 연동되지 않음. MASTERTREE_CONTRACT의 데이터 계약 미갱신 시 팀(또는 AI)이 해당 필드 존재를 모르고 삭제하거나 base를 새로 구성할 때 누락.
**증상:** `422 UNKNOWN_FIELD_NAME: "caption"` 반복 — save_to_airtable()은 caption 저장 시도, 테이블에는 없음
**해결:** Airtable Metadata API로 프로그래매틱 필드 추가 (재현 가능 / 문서화 가능)
```python
requests.post(f'.../tables/{table_id}/fields', json={'name': 'caption', 'type': 'multilineText'})
```
**예방:** 신규 Airtable 필드 사용 시 MASTERTREE_CONTRACT.md 데이터 계약 테이블 즉시 업데이트. UI 수동 추가보다 API 추가 우선 (재현 가능).
**관련:** ERR-028(260529 해소 → 260612 재발) / ERR-039 / INC-020

---

## FP-029 | FB CDN 동일 이미지 다중 URL — URL 해시 기반 중복 감지 무력화
**설명:** Facebook은 동일한 이미지를 여러 CDN 노드로 서빙한다 (`scontent.fhan15-2`, `fdad3-8`, `fhan5-6` 등). URL 전체를 해시 키로 사용하면 노드가 달라질 때마다 다른 해시가 생성되어 동일 이미지를 신규 레코드로 저장한다. 크롤링이 반복될수록 같은 이미지의 중복 레코드가 기하급수적으로 누적된다.
**근본 원인:** `hashlib.sha256(image_url.encode())` — CDN URL의 도메인 부분이 가변적. FB CDN URL 구조: `https://scontent.{node}/v/{path}/{media_id_composite}.jpg?{query_params}` — 미디어 ID만 고정.
**증상:** 같은 이미지(Regine Kim 포스트)가 28건 중복 저장. uploading 고착 + upload_rate 하락.
**해결:** FB 미디어 ID 추출 정규식으로 CDN 노드 무관한 고유 키 생성:
```python
_m = re.search(r"/(\d+_\d+(?:_\d+)*)[_.]", image_url)
_key = _m.group(1) if _m else image_url
image_url_hash = hashlib.sha256(_key.encode("utf-8")).hexdigest()
```
**예방:** 외부 CDN URL을 해시 키로 직접 사용 금지. URL 내부의 콘텐츠 고유 ID를 추출하여 해시 생성. CDN 도메인·쿼리파라미터는 가변 요소로 취급.
**관련:** ERR-042, ERR-041, ERR-040

---

## FP-030 | FB raw_text 메타데이터 오염 — clean_fb_metadata 미호출로 필터 오탐
**설명:** Selenium `post.text`는 Facebook UI가 렌더링한 전체 텍스트를 반환한다. 여기에는 작성자명(첫 줄), 경과시간("2시간 전"), 구분점(·) 등 UI 잔여물이 포함된다. 이 오염된 텍스트를 `detect_and_translate()` → `passes_keyword_filter()`에 통과시키면 작성자명이나 UI 문자열이 키워드 규칙에 의도치 않게 매칭(또는 미매칭)될 수 있다.
**근본 원인:** `facebook_crawler.py`에서 `raw_text = post.text` 후 `clean_fb_metadata()` 호출 없이 바로 `detect_and_translate(raw_text)` 진행. `clean_fb_metadata()`는 `caption_generator.py` 내부에서만 호출되어 caption용으로만 정제됨.
**증상:** `Ct Cossmetic YU` 텍스트가 `passes_keyword_filter=False` 반환 (정상 차단이지만 원인이 작성자명인지 본문인지 불명확). 필터 동작 의도와 실제 매칭 경로 불일치.
**해결:** `facebook_crawler.py` L202에 `raw_text = clean_fb_metadata(raw_text)` 추가 (0688849) — raw_text 추출 직후, `_author_raw` 추출 및 필터링 이전에 적용.
**예방:** `post.text` 사용 시 항상 `clean_fb_metadata()` 선처리 후 필터 적용. caption과 raw_text 모두 동일한 정제 파이프라인 통과 원칙.
**관련:** ERR-037(caption 오염 → 260602 해소), 0688849


---
## [260617] FB CDN URL -> Instagram API 거부 패턴

### 패턴
- Facebook CDN URL(fbcdn.net)을 Instagram Graph API image_url로 직접 전달
- Meta 서버가 fbcdn.net 다운로드 실패 -> error_subcode 2207052

### 근본 원인
- facebook_crawler.py가 FB CDN URL을 Airtable image_url에 그대로 저장
- Instagram Graph API는 공개 접근 가능한 URL만 허용

### 해결
- imgbb 중간 호스팅 계층 추가
- FB CDN -> 로컬 다운로드 -> imgbb 업로드 -> 공개 URL -> Airtable 저장

### 관련 파일
- modules/sns/image_hosting.py
- modules/sns/facebook_crawler.py (save_to_airtable)
- tools/backfill_failed_images.py
---

## FP-031 | FB Crawler HUNG — RLock deadlock (AdsPower Stop finally 미실행)
**발생일:** 2026-06-24
**증상:** facebook_crawler.run() 호출 후 프로세스가 무한 대기 상태로 진입. AdsPower Stop API가 finally 블록에서 호출되지 않아 브라우저 세션 누적. 스케줄러 잡이 hang 상태 지속.
**근본 원인:** get_driver() 내부 RLock 획득 후 예외 발생 시 lock 해제 누락 → deadlock. finally 블록 도달 불가.
**해결:** finally 경로 보장 + AdsPower Stop API 호출 위치 재배치. Failure Injection Test로 finally 정상 실행 확인 (260624 PASS).
**예방:** driver 획득·해제는 반드시 try/finally 쌍으로 구성. RLock 사용 시 with 문 또는 명시적 release 보장.
**관련:** ERR-044, 커밋 체인 260624

---

## FP-032 | pytesseract 미설치 — ImageFilter OCR 무력화로 워터마크 브랜드 통과
**발생일:** 2026-06-29
**증상:** passes_image_filter() 내 pytesseract.image_to_string() 호출 시 ModuleNotFoundError 발생. except 블록이 True 반환 → 모든 이미지 필터 통과. COSLIFE·Lily 워터마크 이미지가 차단되지 않음.
**근본 원인:** pytesseract 미설치 상태에서 예외를 통과 처리(fail-open)로 설계. ImageFilter가 사실상 무력화.
**해결:** CAPTION_BLOCKLIST = ["coslife", "lily"] 추가 → passes_keyword_filter() 에서 번역 캡션 텍스트 기준 선행 차단 적용 (d79a3b3). OCR 없이 텍스트 레벨에서 대체 차단.
**예방:** OCR 의존 필터는 fail-open 금지. 미설치 시 경고 + 텍스트 대체 필터 명시 적용 필수. pytesseract 설치 여부 startup 시 점검 권장.
**관련:** ERR-044, 커밋 d79a3b3

---

## FP-033 | 24/7 상시 구동 시스템에 OS reboot/sleep 대응 부재
**발생일:** 2026-07-01
**증상:** Windows 자체 재부팅(10:02) 이후 watchdog.ps1 미재기동으로 launcher/main.py, Flask, Streamlit, ngrok 전체가 최대 약 13시간(10:02~23:35) 무감시 상태로 방치. 중간에 크롤러 간헐 재개 구간(12:47~17:57 추정) 있었으나 이후 재중단, 수동 확인 전까지 알림 없음.
**근본 원인:** watchdog.ps1은 "별도 터미널 수동 실행" 전제로 설계, OS 재부팅/로그온 시 자동 기동 등록 없음. watchdog 자체가 죽으면 Slack 알림 포함 어떤 자동 복구/알림 경로도 없는 구조적 단일 장애점(SPOF).
**해결:** 2026-07-01 23:35 수동으로 run_scheduler.ps1 + watchdog.ps1 재기동.
**예방:** watchdog.ps1을 Task Scheduler "시스템 시작 시" 트리거로 등록. Modern Standby/절전 비활성화 검토.
**관련:** ERR-045, INC-023

---

## FP-034 | DI 리팩터링이 정상 동작 코드를 결함 있는 추상화로 교체한 회귀
**발생일:** 2026-06-24 (df9df6b 커밋 기준 회귀 발생, 결함 자체는 2026-06-23 758d29d에서 최초 도입)
**증상:** `facebook_crawler.py`의 supplier blocklist 매칭이 무증상으로 무력화됨. 차단 대상 author의 게시물이 있어도 `[Blocklist] 통과` 로그만 남아 정상 게시물과 구분 불가.
**근본 원인:** `758d29d`(Repository Interface 최초 도입)에서 `SupplierBlockEntry`/`list_blocked_suppliers()`가 잘못된 필드명(`supplier_name`)으로 작성됨. `df9df6b`(잔존 직접 호출 Repository 교체)에서 `facebook_crawler.py`가 기존에 정상 동작하던 직접 Airtable 호출(`fields.get('author_name','')`)을 이 결함 있는 Repository 경유 코드로 교체하며 정상 기능이 회귀됨. DI 리팩터링이 "직접 호출 제거" 목표는 달성했으나 교체 대상 추상화 자체의 필드 매핑 정합성은 검증되지 않음.
**해결:** ✅ 완료 (2026-07-03) — ERR-046 필드명 수정(`supplier_name`→`author_name`, `page_name` 매핑 추가) 적용. 격리 테스트 테이블 기반 ISOLATED INTEGRATION PROOF(Gate 6) 및 운영 Supplier_Blocklist 대상 Runtime Proof(6/6 매칭) 완료.
**예방:** 직접 호출을 Repository로 교체하는 모든 커밋에 대해 교체 전/후 동일 입력→동일 출력 회귀 테스트 1건 이상 필수화. 특히 blocklist/권한 체크 등 "실패 시 무증상 통과"되기 쉬운 필터링 로직은 우선순위 높게 검증. (미적용 잔여: DI 리팩터링 커밋 대상 회귀 테스트 의무화 체계 자체는 아직 미구축 — 향후 트랙)
**관련:** ERR-046, INC-024

---

## FP-035 | "등록 완료" 문서화가 실제 재기동 보장을 의미하지 않음 — Task Scheduler 자동 기동 검증 부재
**발생일:** 2026-06-29(등록) ~ 2026-07-05(무재실행 9회 발견)
**증상:** FP-033의 재발 방지책으로 `SNS_Watchdog_AutoStart` 스케줄 작업을 등록(260529)하고 CURRENT_RUNTIME_CONTEXT.md에 "✅ 등록 완료"로 기록했으나, 실제로는 등록 직후 1회만 실행되고 이후 9회의 실제 재부팅(cold boot, Fast Startup 비활성 확인)에도 단 한 번도 재실행되지 않음. watchdog.log는 07-01 23:36:55 이후 4일간 공백.
**근본 원인:** "작업이 존재/Enabled 상태"와 "트리거 발동 시 실제 실행됨"을 구분하지 않고 등록 완료 = 문제 해결로 판단. `Logon Mode: Interactive only` 등 실행 조건이 재부팅 후 실제 발동을 막을 가능성을 검증하지 않음 (Runtime Proof 없이 문서만 갱신 — CLAUDE.md "Evidence 없는 완료 선언 금지" 원칙 위반 사례).
**해결:** 미해결 — 사용자 승인 대기 중 (문서화만 우선 완료).
**예방:** 자동 기동/재시작 안전장치를 "등록 완료"로 종결하지 말 것. 등록 후 실제 재부팅 1회 이상 발생시켜 `Last Run Time` 갱신 여부로 Runtime Proof 필수. 이후에도 주기적(예: 주 1회) `schtasks /Query` 점검을 상시 점검 항목에 추가 검토.
**관련:** ERR-047, FP-033, INC-023, INC-025

---

## FP-036 | 중복 기동 방지 장치 부재 상태에서 수동 Start-Process 반복 실행 — 프로세스 생존 여부 미확인 후 추가 기동
**발생일:** 2026-07-06
**증상:** 세션 중 `launcher/main.py`를 여러 차례 `Start-Process`로 기동하면서, 매번 기존 인스턴스가 이미 살아있는지(`:5000` 바인딩 여부, 기존 python.exe 프로세스 존재 여부)를 사전 확인하지 않고 추가 기동을 반복 — 결과적으로 5세대(10프로세스) 동시 실행 상태에 도달(ERR-048). watchdog.ps1 미기동(ERR-047)으로 인해 "정상 상태 = 프로세스 1개"라는 기준선 자체가 흔들린 상태에서 수동 개입이 누적된 것이 근본 원인.
**근본 원인:** launcher/main.py에 중복 기동을 막는 자체 가드(PID 파일, 포트 선점 체크 등)가 없어, 운영자/에이전트가 "이미 떠 있는지"를 매번 외부에서 수동으로 검증해야만 안전한 구조. 이 검증을 매 기동 전에 강제하는 절차가 없었음.
**해결:** 8개 중복 프로세스 정리 후 단일 인스턴스로 재기동 완료(ERR-048 Fix 참조).
**예방:** launcher/main.py 기동 스크립트(또는 이를 감싸는 절차)에 "기동 전 `:5000` 바인딩 및 동일 커맨드라인 프로세스 존재 여부 체크 → 이미 있으면 기동 중단" 가드를 표준 절차화. watchdog.ps1이 정상 동작한다면 수동 기동 자체가 예외적 상황으로 한정되므로 ERR-047 해결이 최우선.
**관련:** ERR-048, ERR-047, INC-026, INC-025

---

## FP-037 | Dry-run 검증 필드/언어가 실제 runtime 입력과 불일치 — caption 기준 검증을 title 기준 runtime proof로 오판
**발생일:** 2026-07-06
**증상:** `quality_gate.py` relevance filter canary 검증 시 Instagram_Posts의 영문 번역 `caption` 필드 20건으로 dry-run 20/20 MATCH를 확인하고 이를 runtime proof로 오판. 그러나 실제 `run_gate()`가 검사하는 필드는 Domeggook API 원본 `title`이며, 이는 한국어다. 영어-only 키워드(`COSMETIC_KEYWORDS`/`HEALTH_KEYWORDS`)가 한국어 title에 매칭되지 않아, 화장품/건강식품 포함 정상 상품까지 전량 `FILTERED` — D001/D002 `fetch=10 ready=0`.
**근본 원인:** dry-run 검증에 사용한 필드(`caption`, 영문)와 실제 runtime이 검사하는 필드(`title`, 한국어)가 서로 다름. 검증 완료 = 배포 안전이라는 가정이, "무엇을 검증했는가"가 "실제 무엇이 실행되는가"와 일치하는지 확인 없이 성립됨.
**증상 재현 조건:** dry-run 대상 데이터의 필드명/언어가 실제 프로덕션 코드 경로의 입력 필드명/언어와 다를 때.
**해결:** `git checkout HEAD -- modules\crawlers\quality_gate.py` 로 원본 4규칙(adult_only/title/unit_price/image_url) rollback. launcher/main.py PID 지정 재시작으로 런타임 반영 확인.
**예방:** dry-run 검증 시 반드시 (1) 실제 runtime 코드가 참조하는 정확한 필드명, (2) 그 필드의 실제 언어/포맷, (3) 실제 raw 샘플 데이터를 사용해야 함. 캡션·요약·번역 등 가공 필드로 검증한 결과는 원본 필드 검증을 대체할 수 없음.
**관련:** ERR-049, INC-027(예정)

---

## FP-038 | Task Scheduler `LastTaskResult=0`이 실제 실행 성공을 보장하지 않음 — launch-only 상태에서도 성공 코드 반환
**발생일:** 2026-07-07(최초 관측, ERR-051) / 2026-07-09(100% 재현, RunLevel 후보 배제 확정)
**증상:** 진단용 Task(`SNS_WatchdogAB_TestB`)를 `Start-ScheduledTask`로 트리거 시 `Get-ScheduledTaskInfo`의 `LastTaskResult`가 항상 `0`(성공)을 반환하지만, 실제로는 (1) 마커 파일이 갱신되지 않고, (2) Task Scheduler Operational 로그에 `100/200/201/102`(프로세스 생성~완료) 이벤트가 전혀 기록되지 않으며, (3) Task 전체 `State`가 `Queued`에서 고착되어 `Ready`로 복귀하지 않는 launch-only 실패가 발생. 260709 재조사에서 RunLevel=Limited로 변경 후 6회 트리거 전부(100%) 이 패턴으로 재현됨.
**근본 원인:** UNKNOWN(ERR-051 참조) — 다만 `LastTaskResult` 필드 자체가 "Task Scheduler가 인스턴스를 launched로 기록했는가"만 반영하고 "Action이 실제로 프로세스를 생성해 완료됐는가"는 반영하지 않는 것으로 보임. 즉 이 필드는 실행 성공의 신뢰 가능한 지표가 아님.
**증상 재현 조건:** 아직 특정 조건 미확정(ERR-051 조사 진행 중) — 최소 한 차례는 관리자 권한 `Set-ScheduledTask`로 Task 정의를 갱신한 직후 100% 재현됨(인과관계 미확정, 상관관계만 관측).
**해결:** 미해결 — ERR-051 근본원인 조사 진행 중.
**예방:** watchdog/운영 Task의 정상 실행 여부를 `LastTaskResult`만으로 판정하지 말 것. (1) `129/100/200/201/102` 이벤트 시퀀스 존재, (2) Task `State`가 `Queued`에 고착되지 않고 `Ready`로 복귀, (3) Action이 실제로 남기는 부산물(로그 파일, 마커 파일 등) 갱신 여부, 3가지를 실행 성공 판정의 필요조건으로 병행 확인해야 함.
**관련:** ERR-051, ERR-050

---

## FP-039 | 저장소 이전(porting) 시 코드 파일만 옮기고, 그 코드를 실행하던 외부 자동화 설정(Task Scheduler 등록 등)은 별도 자산이라 함께 옮겨지지 않는다
**발생일:** 등록 추정 2025-11-20~2026-01-13(Task 등록 시점) / 발견 2026-07-10(ERR-052)
**증상:** 250723(Reference Only, 실행 금지 원칙 적용 저장소)의 코드가 260511로 이식(porting)된 이후에도, 250723 경로를 직접 가리키는 Windows Task Scheduler 등록(`SNS_AUTO_PRODUCTION`, `SNS_Auto_Run`) 2건이 활성 상태로 8개월 가까이 방치됨. 파일시스템상 코드는 260511로 옮겨졌지만, 그 코드를 자동 실행하던 트리거(Task Scheduler)는 파일시스템과 완전히 별개의 저장소(Windows 시스템 DB, Task Scheduler 서비스가 관리)이기 때문에 파일 이동과 함께 자동으로 갱신되거나 제거되지 않음.
**근본 원인:** "저장소 이전(porting)"이라는 개념이 통상 파일시스템 단위(코드/설정 파일 복사·수정)로만 인식되고, 그 코드를 구동하던 외부 자동화 설정(Task Scheduler, Windows 서비스, cron 유사 도구, 시작프로그램 등)은 별도의 독립된 저장소라는 점이 작업 체크리스트에 반영되지 않음. 코드 검색(grep) 도구는 Windows 시스템 DB(Task Scheduler 등록 내역)를 대상으로 하지 않기 때문에, 파일시스템 기준 점검만으로는 이런 잔존 등록을 발견할 수 없는 구조적 한계가 있음.
**증상 재현 조건:** 저장소를 폐기(deprecate)하거나 다른 위치로 완전히 전환할 때, 그 저장소의 코드를 실행하던 외부 자동화 설정을 별도로 전수 점검하지 않을 경우 언제든 재발 가능.
**해결:** ERR-052 참조 — 발견된 2건은 `Disable-ScheduledTask`로 즉시 비활성화(삭제 아님).
**예방:** 저장소 폐기/전환 체크리스트에 다음 항목 필수화 — "이 경로(예: `C:\SNS_24AutoProject_250723`)를 참조하는 Scheduled Task 전수 검색": `Get-ScheduledTask` 전체를 순회하며 Actions 문자열(`Execute`+`Arguments`)에 구경로 문자열이 포함되는지 매칭. Task Scheduler 외 다른 자동화 경로(시작프로그램, 다른 스케줄러 등)는 이번 점검 대상에 포함되지 않았음 — INC-029 재발 방지 항목 참조.
**관련:** ERR-052