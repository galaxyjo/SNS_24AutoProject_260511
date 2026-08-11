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

**[2026-07-10 추가 Note — 비결정적 성공/실패 패턴 확인 + 진단 Task Disable]:**
`SNS_WatchdogAB_TestB`가 트리거가 0개로 등록된 상태에서 2026-07-10 00:44:33에 `Start-ScheduledTask`(추정, 호출 주체 UNKNOWN) 방식으로 실행되어 이번엔 정상 완주(마커 갱신 확인) — 직전(260709) 6/6 launch-only 실패와 상반된 결과. 즉 이 패턴은 100% 결정론적 실패가 아니라 **성공/실패가 비결정적으로 관측되는 패턴**임이 추가로 확인됨(예방 항목이나 근본원인 판정을 바꾸지는 않음). 증거 보전 목적으로 유지해온 진단 Task 3종(TestA/TestB/TestD)은 추가 재현 실험보다 안정성 우선 판단하에 2026-07-10 `Disable-ScheduledTask`로 비활성화 완료(삭제 아님). 조치에 사용한 스크래치 파일 2개도 삭제 대신 `.gitignore` 추가로 추적제외만 적용(삭제 금지 원칙 유지).
**관련(추가):** ERR-051(Note — 상세 raw 근거)

---

## FP-039 | 저장소 이전(porting) 시 코드 파일만 옮기고, 그 코드를 실행하던 외부 자동화 설정(Task Scheduler 등록 등)은 별도 자산이라 함께 옮겨지지 않는다
**발생일:** 등록 추정 2025-11-20~2026-01-13(Task 등록 시점) / 발견 2026-07-10(ERR-052)
**증상:** 250723(Reference Only, 실행 금지 원칙 적용 저장소)의 코드가 260511로 이식(porting)된 이후에도, 250723 경로를 직접 가리키는 Windows Task Scheduler 등록(`SNS_AUTO_PRODUCTION`, `SNS_Auto_Run`) 2건이 활성 상태로 8개월 가까이 방치됨. 파일시스템상 코드는 260511로 옮겨졌지만, 그 코드를 자동 실행하던 트리거(Task Scheduler)는 파일시스템과 완전히 별개의 저장소(Windows 시스템 DB, Task Scheduler 서비스가 관리)이기 때문에 파일 이동과 함께 자동으로 갱신되거나 제거되지 않음.
**근본 원인:** "저장소 이전(porting)"이라는 개념이 통상 파일시스템 단위(코드/설정 파일 복사·수정)로만 인식되고, 그 코드를 구동하던 외부 자동화 설정(Task Scheduler, Windows 서비스, cron 유사 도구, 시작프로그램 등)은 별도의 독립된 저장소라는 점이 작업 체크리스트에 반영되지 않음. 코드 검색(grep) 도구는 Windows 시스템 DB(Task Scheduler 등록 내역)를 대상으로 하지 않기 때문에, 파일시스템 기준 점검만으로는 이런 잔존 등록을 발견할 수 없는 구조적 한계가 있음.
**증상 재현 조건:** 저장소를 폐기(deprecate)하거나 다른 위치로 완전히 전환할 때, 그 저장소의 코드를 실행하던 외부 자동화 설정을 별도로 전수 점검하지 않을 경우 언제든 재발 가능.
**해결:** ERR-052 참조 — 발견된 2건은 `Disable-ScheduledTask`로 즉시 비활성화(삭제 아님).
**예방:** 저장소 폐기/전환 체크리스트에 다음 항목 필수화 — "이 경로(예: `C:\SNS_24AutoProject_250723`)를 참조하는 Scheduled Task 전수 검색": `Get-ScheduledTask` 전체를 순회하며 Actions 문자열(`Execute`+`Arguments`)에 구경로 문자열이 포함되는지 매칭. Task Scheduler 외 다른 자동화 경로(시작프로그램, 다른 스케줄러 등)는 이번 점검 대상에 포함되지 않았음 — INC-029 재발 방지 항목 참조.
**관련:** ERR-052

---

## FP-040 | 반복(Repeating) 트리거 기반 Task Scheduler 작업은 WakeToRun 미설정 시 Modern Standby 중 실패 로그 없이 조용히 스킵된다
**발생일:** 상시(등록 시점부터 잠재), 확인 2026-07-10(ERR-053)
**증상:** `SNS_HeartbeatMonitor_Independent`(5분 주기)가 약 5시간45분 동안 71회 미실행. `LastTaskResult=0`(직전 성공)만 남아있고 에러/경고 이벤트가 전혀 발생하지 않아 겉보기엔 "정상 등록된 Task"로 보임 — `NumberOfMissedRuns` 필드를 직접 조회하지 않으면 절대 드러나지 않는다.
**근본 원인:** Windows Task Scheduler는 Modern Standby(또는 일반 절전) 상태에서 `WakeToRun=False`인 반복 트리거의 예정 시각이 지나가면, 시스템이 깨어날 때까지 그 발동을 재시도하지 않고 그냥 건너뛴다(catch-up 없음). 이 동작은 에러로 취급되지 않으므로 Task 자체의 `State`/`LastTaskResult`에는 아무 이상 신호가 남지 않는다.
**증상 재현 조건:** (1) 반복(간격) 트리거 Task, (2) `WakeToRun=False`(기본값), (3) 시스템이 Modern Standby로 자주/장시간 전환되는 환경 — 이 3가지가 겹치면 항상 재현 가능.
**해결:** 미해결 — ERR-053 Fix 후보 참조, 사용자 승인 대기.
**예방:** (1) "watchdog을 감시하는 감시자"처럼 가용성이 핵심인 반복 Task는 등록 시 `WakeToRun=True` 여부를 필수 점검 항목화. (2) 상시 루프 프로세스(watchdog.ps1 방식)와 반복 트리거 프로세스(heartbeat_monitor.py 방식)는 절전 복원력이 다르다는 점을 설계 단계에서 인지 — 가용성이 중요한 감시 스크립트는 후자보다 전자 방식을 우선 검토. (3) `NumberOfMissedRuns`를 정기 점검 체크리스트(`get_watchdog_status()` 등)에 포함시키는 방안 검토.
**관련:** ERR-053, ERR-047, INC-028

**[2026-07-10 추가 Note — watchdog Task(`SNS_Watchdog_AutoStart`)에도 동일 클래스 취약점 확인 + WakeToRun=True 적용]:**
ERR-053/FP-040이 지적한 `WakeToRun=False` 취약점이 heartbeat_monitor.py Task뿐 아니라 `SNS_Watchdog_AutoStart`(watchdog.ps1 기동용)에도 동일하게 등록되어 있었음을 확인(ERR-054). 단 이 Task는 반복(Repeating) 트리거가 아니라 로그온/부팅 1회성 트리거 + 상시 루프 프로세스 구조라, 본 패턴이 규정한 재현조건(반복 트리거+Modern Standby)과 완전히 동일하지는 않음 — 그럼에도 예방 차원에서 관리자 권한으로 `WakeToRun=True` 적용, XML/taskinfo diff로 다른 필드 변경 없음과 예약 인스턴스 영향 없음을 실증 확인(`snapshots/watchdog_wakeup_260710/`). 실제 Modern Standby 재현 구간에서의 효과 검증은 heartbeat_monitor.py와 마찬가지로 미완료.
**관련(추가):** ERR-054

---

## FP-041 | 동일 스크립트를 실행하는 python.exe가 여러 PID로 보여도 자동으로 "중복 실행"은 아님 — 부모-자식 체인 확인 없이 종료하면 정상 프로세스를 불필요하게 죽일 위험

**발생일:** 260706(ERR-048/FP-036, 실제 중복 사례) / 260711(이번, 실제로는 정상 부모-자식 구조였던 사례)
**증상:** `.venv` python이 시스템 python을 자식으로 재실행하는 구조상, 동일 스크립트(launcher/main.py, dashboard.py) 실행 python.exe가 4개까지 보일 수 있음 — PID만 보면 FP-036(실제 중복)과 구분 안 됨.
**근본원인:** venv 재실행 구조 자체는 정상 동작 — "문제"는 식별 절차 부재.
**해결:** StartTime 근접 + ParentProcessId 체인 + 포트 소유(netstat) 3가지 대조로 논리적 서비스 개수 확인 후 판정.
**예방:** python.exe 다중 PID 발견 시 즉시 종료 금지, 위 3단계 확인 절차 표준화.
**관련:** FP-036, ERR-048

---

## FP-042 | 구성요소 전환(migration) 작업의 중간 상태(신규 메커니즘 설치 완료 + 구 메커니즘 미제거)가 세션 경계를 넘어 방치되면, 두 메커니즘이 동일 스크립트/서비스를 중복 실행한다

**발생일:** 260711(ERR-057, NSSM/Task Scheduler 이중 watchdog) — 유사 패턴 260527(ERR-021/FP-017, Flask 이중 바인딩)
**증상:** watchdog.ps1을 실행하는 메커니즘이 NSSM 서비스(`SNS_Watchdog`)와 Task Scheduler(`SNS_Watchdog_AutoStart`) 두 개로 동시에 존재, 재부팅마다 두 인스턴스가 병행 기동됨. watchdog.log에 시작 배너가 중복 기록되고 Streamlit/ngrok 재시작·n8n 실패 알림이 두 배로 남아, 실제로 조사해야 할 문제(예: n8n 반복 실패)를 진단할 때 잡음이 됨.
**근본원인:** 전환 작업이 "신규 설치"와 "구 제거"라는 두 단계로 나뉘어 있을 때, 앞 단계만 완료된 중간 상태에서 세션이 종료되면 그 상태가 다음 세션 핸드오프 메모에 정확히 반영되지 않을 수 있다. 이번 건은 핸드오프 메모에 "NSSM Phase 2→3 경계, 아직 시작 안 함"이라 적혀 있었으나 실제로는 NSSM 서비스가 이미 `Running` 상태였음 — 문서(기억)와 실제 시스템 상태가 어긋난 STALE STATE 사례.
**해결:** 세션 시작 시 문서 요약만 신뢰하지 않고, 실제 서비스/Task 상태를 raw로 재확인(`Get-Service`, `Get-ScheduledTask`, 프로세스 부모-자식 체인)한 뒤에 "다음 단계"를 판단.
**예방:** (1) 전환 작업은 가능하면 설치+구 제거를 한 세션 내 원자적으로 묶어 처리. (2) 부득이 나눠야 한다면 `CURRENT_RUNTIME_CONTEXT.md`에 "신규 메커니즘 설치 완료, 구 메커니즘 아직 활성 — 다음 세션에서 반드시 제거 확인" 처럼 중간상태를 명시적으로 경고. (3) High-Risk(Scheduler/Watchdog) 재개 작업은 항상 재조사(read-only raw 확인)로 시작하고 메모를 그대로 신뢰하지 않는다 — CLAUDE.md STALE STATE CHECK 원칙의 구체 사례.
**관련:** ERR-057, FP-017, FP-035, PENDING-A

---

## FP-043 | 서비스 실행 계정을 바꾸면(대화형 사용자 → LocalSystem 등), 그 계정에 의존하던 외부 도구의 "설치 형태"와 "인증정보 저장 위치"가 함께 깨질 수 있다

**발생일:** 260711(ERR-058, NSSM 전환 후 ngrok 이중 실패)
**증상:** watchdog.ps1 코드 자체는 그대로인데, 실행 주체를 admin 계정(Task Scheduler)에서 LocalSystem(NSSM 서비스)으로 바꾸자 ngrok만 실패하기 시작함 — 원인이 한 번에 드러나지 않고 두 겹으로 숨어있었음: (1) Microsoft Store(MSIX)로 설치된 도구는 비대화형/SYSTEM 컨텍스트에서 Execution Alias 실행 자체가 막힘, (2) 포터블 실행파일로 우회해도 그 도구의 인증정보(authtoken 등)가 기존 계정의 사용자 프로필 하위에만 저장되어 있으면 새 계정은 여전히 그걸 못 찾음.
**근본원인:** "스크립트가 도는 계정"이 바뀌면, 그 스크립트가 호출하는 모든 외부 프로그램 각각에 대해 "이 계정에서도 이 프로그램이 인식되고, 이 계정의 프로필에서도 필요한 설정/인증정보에 접근 가능한가"를 개별적으로 다시 검증해야 한다 — 코드(경로 문자열)만 맞으면 된다고 가정하면 이런 부작용이 재부팅 실증 등 실제 운영 조건에서만 드러난다.
**해결:** watchdog.ps1이 호출하는 다른 외부 도구(현재는 python.exe/streamlit.exe만 있고 둘 다 프로젝트 폴더 내 `.venv`라 안전 — ngrok만 유일하게 외부 설치+사용자 프로필 의존 조합이었음)도 동일 기준으로 점검 완료.
**예방:** (1) 서비스 실행 계정을 바꾸는 작업은 그 계정이 호출하는 외부 프로그램 목록을 먼저 나열하고, 각각에 대해 설치 형태(일반 exe vs Store/MSIX)와 설정 저장 위치(사용자 프로필 vs 시스템 전역/환경변수)를 표로 점검한 뒤 진행. (2) 가능하면 외부 도구는 사용자 프로필 의존적인 Store 버전보다 포터블/시스템 전역 설정 도구를 우선 채택 — 실행 계정이 바뀌어도 흔들리지 않음. (3) 계정 전환 후에는 반드시 실제 재부팅(또는 서비스 재시작) 실증으로 전체 체인을 재확인 — 크래시 재시작 실증만으로는 이런 "설정 접근 불가" 류 결함이 드러나지 않을 수 있음(코드는 실행되지만 도구 내부에서 조용히 실패).
**관련:** ERR-058, ERR-057, FP-042

---

## FP-044 | 저장 성공 여부를 재확인(GET)하는 로직에서 확인 자체의 예외를 전부 뭉뚱그려 처리하면, 실제로 성공한 작업이 실패로 오탐될 수 있다

**발생일:** 260712(ERR-059, 학습 리뷰 그리드 실제 50건 배치 GET 재검증 오탐)
**증상:** PATCH(저장)는 전부 성공했는데, 그 직후 확인용 GET 단계의 예외(429/403/타임아웃 등)를 모두 `None`으로 변환해 "값이 다름"으로 처리 → 실제로는 100% 성공한 배치가 화면에 "실패, 다시 시도해주세요"로 표시됨. 사용자가 이 안내를 그대로 믿고 확정 버튼을 다시 눌렀다면 이미 정상 저장된 50건을 불필요하게 재-PATCH할 뻔했음.
**근본원인:** "저장이 실제로 잘못됨(값 불일치)"과 "확인 자체를 못 함(예외)"은 서로 다른 문제인데, 코드가 확인 단계의 모든 예외를 하나의 결과(`None`, 곧 불일치로 처리)로 뭉뚱그려서 구분이 사라짐. 예외의 종류(429/403/404/5xx/타임아웃)에 따라 실제 대응(재시도 가능/불가능, 재-PATCH 필요/불필요)이 전혀 다른데 그 정보도 함께 사라짐.
**해결:** 확인 단계의 결과를 세 가지로 명확히 분리 — (1) 값이 실제로 다름(mismatched_ids), (2) 확인 자체가 실패함(verification_errors, 원래 상태코드·오류종류 보존), (3) 정상 일치. 재시도는 429(Retry-After 기반)·5xx·타임아웃에만 제한적으로 적용하고, 403·404·기타는 즉시 오류로 보고(재시도 없음). 사용자에게도 "저장은 이미 됐을 수 있다"는 것과 "확정 버튼을 다시 누르지 마라"를 구분해서 안내.
**예방:** (1) "저장 후 재확인" 패턴을 만들 때는 확인 단계 자체의 예외를 절대 값 불일치와 같은 결과로 합치지 않는다. (2) 재시도 가능 여부는 예외의 실제 성격(상태코드/타입)으로 판단하고, 상태코드가 없는 예외는 기본적으로 재시도하지 않는(안전 측) 쪽을 택한다. (3) 재확인 실패가 곧 "재실행해도 된다"는 뜻이 아니므로, UI에서 재시도 버튼을 그대로 활성 상태로 두지 말고 잠그거나 명확히 경고한다. (4) "속도 제한"처럼 그럴듯한 원인을 실제 로그(요청 간격 등) 대조 없이 단정하지 않는다 — 이번 건도 최초 가설(속도 제한)이 틀렸고, 예외 은폐가 진짜 원인이었음.
**관련:** ERR-059, INC-032

---

## FP-045 | "자식 프로세스 크래시 복구"와 "서비스 본체 크래시 복구"는 서로 다른 계층 — 하나만 설정하면 다른 하나는 무방비

**발생일:** 260711 23:08:47 크래시(발견은 260712), ERR-060

**증상:** NSSM 서비스에 `AppExit Default=Restart`(자식 프로세스, 즉 watchdog.ps1이 죽으면 재시작)만 설정해뒀는데, 정작 NSSM 서비스 본체(`nssm.exe` 서비스 호스트 프로세스)가 죽어버리자 아무도 복구하지 않았음. `Get-Service`가 계속 `Stopped`를 보고했지만, 그 이전에 이미 떠있던 자식(watchdog.ps1)은 고아 상태로 계속 살아있어서 겉보기엔(로그·포트 기준) 정상처럼 보였음 — 실제로는 무감독 상태.

**근본원인:** Windows 서비스 하나에 복구 메커니즘이 두 계층으로 나뉘어 있음: (1) NSSM 자체의 `AppExit`/`AppRestartDelay` — NSSM이 감시하는 **자식 애플리케이션**이 죽었을 때만 작동, (2) Windows SCM의 `sc.exe failure`(서비스 복구 탭) — **서비스 프로세스 자신**이 죽었을 때 작동. 이번 사고는 (2)를 설정하지 않아, NSSM 본체가 죽는 순간 전체 복구 체계가 무력화됐음.

**해결:** ERR-060 Fix 참조 — 서비스 재생성 후 `sc.exe failure`로 (2) 계층 신규 추가.

**예방:** NSSM(또는 유사한 서비스 래퍼)으로 무언가를 상시 실행시킬 때는 반드시 두 계층을 모두 설정할 것 — `AppExit`(자식 복구) + `sc.exe failure`(서비스 본체 복구). 하나만 있으면 "왜 복구가 안 되지"를 나중에야 알게 된다. 또한 `Get-Service`의 상태값(`Running`/`Stopped`)은 "서비스가 관리하는 자식이 실제로 살아있는지"를 보장하지 않는다 — 자식이 고아로 남아 계속 살아있으면 서비스는 `Stopped`인데 기능은 정상으로 보이는 혼란스러운 중간 상태가 가능하다.

**[2026-07-13 추가 Note]:** 서비스 본체가 애초에 왜 죽었는지의 트리거가 확정됨(ERR-060 Note 참조) — 백신(AhnLab Safe Transaction)이 `nssm.exe`를 PUP(잠재적 유해 프로그램)로 오탐, 사용자가 치료 처리하며 파일 삭제. 이 패턴(두 계층 복구 분리 필요)의 일반성은 트리거 종류와 무관하게 그대로 유효.

**관련:** ERR-060, ERR-057, ERR-058, FP-042, FP-043

## FP-046 | 자동응답 fallback이 "가장 최근 값"일 때, 대상이 여러 개면 잘못된 대상에 매칭될 위험

**발생일:** DM 자동응답(12단계) 구현 시점(260512 이전, 정확한 시작일 미상)부터 잠재, 발견 260713(ERR-061)

**증상:** `get_base_price()`가 문의 상품 식별 없이 최신 등록가를 그대로 반환·발송 — buyer가 어떤 상품을 물었는지와 무관하게 응답이 나감.

**근본원인:** "최신값 = 관련값"이라는 암묵적 가정이, 대상(상품)이 1개에서 여러 개(다품목)로 늘어나는 순간 깨짐. 이 가정이 깨진 걸 알아챌 방법(상품 매핑 검증)이 애초에 없었음.

**해결(코드 구현):** ERR-061 Fix 참조 — Gate C 코드 구현·테스트 완료. **260714 10:18 재시작 + 10:24:41 Canary로 운영 적용·가격 자동발송 차단 PASS 확정.** 실제 안내문 발송·신규 Telegram 마스킹 E2E는 PARTIAL(미확인) — 기존 `dm_receiver.send_telegram()` PII 노출(P0-1)은 별개로 계속 OPEN.

**예방:** 다중 대상이 가능한 도메인에서 "최신값" fallback을 쓸 때는 반드시 대상 식별(매핑) 완료 여부를 게이트로 걸 것 — 식별이 안 되면 fallback 자체를 비활성화(Gate C 패턴을 향후 유사 사례에도 재사용).

**관련:** ERR-061, INC-034

## FP-047 | 저장 실패를 성공처럼 처리해 재시도 기회를 잃는 패턴

**발생일:** `comment_poller.py`/`comment_auto_reply.py` 구현 시점부터 잠재, 발견·실증 260714(ERR-062)

**증상:** Airtable 기록이 실패해도 댓글 처리 자체는 "완료"로 캐시되어, 같은 댓글이 다시는 재시도되지 않음 — 실패가 조용히 영구 유실로 이어짐.

**근본원인:** `comment_poller.py:113` `new_ids.add(cid)`가 `handle_comment()` 호출(116행) *이전에* 실행되고, `_record_comment()`(`comment_auto_reply.py:94-105`)는 Airtable 예외를 자체 try/except로 삼켜 로그(WARNING)만 남기고 반환(재발생 없음) — 따라서 `handle_comment()`는 항상 정상 종료로 보이고, `poll_new_comments()`의 120-122행이 무조건 `_save_cache(processed | new_ids)`를 실행해 실패한 comment_id까지 영구 처리완료로 기록. 예외를 삼킨 함수와, 그 함수의 성공 여부를 확인하지 않고 무조건 캐시하는 호출부가 각각 별도로는 문제없어 보이지만 조합되면 재시도 경로 자체가 없어짐.

**해결(코드 구현):** 미적용(OPEN, 계속). ERR-062의 이번 사례(Airtable 선택지 누락)는 260714 선택지 추가로 직접원인이 해소됐지만, **이 패턴 자체(예외를 삼키는 함수 + 무조건 캐시하는 호출부의 조합)는 그대로 남아있음** — Airtable 장애, 스키마 변경, 네트워크 오류 등 다른 어떤 이유로든 `_record_comment()`가 다시 실패하면 똑같이 영구 유실된다. 재시도 큐(`modules/common/retry_queue.py`, DM 자동응답 발송실패에는 이미 사용 중) 패턴을 Airtable 기록 실패에도 적용하거나, 최소한 실패한 comment_id는 `processed` 캐시에서 제외하는 방안 필요 — 코드 변경 미착수.

**재확인(260715):** 회장 지시로 Gate G(Private Reply 전환) 이후 코드를 재확인 — 패턴은 그대로 남아있음, 코드 수정 없음(기록만 갱신). 줄 번호만 Gate G 추가 코드(`_try_private_reply` 등)로 밀려 현재는 `comment_poller.py:116`(`new_ids.add`)/`:123-125`(무조건 `_save_cache`), `comment_auto_reply.py:146-157`(`_record_comment`)로 이동 — 로직 자체는 원문과 동일. `handle_comment()`가 부정 댓글(`:236`) 경로와 일반/가격 댓글(`:246`) 경로 양쪽에서 각각 `_record_comment()`를 호출하는 구조도 확인, 두 경로 모두 동일하게 취약.

**해결(코드 구현, 260715 — `IMPLEMENTED — NOT DEPLOYED`. disabled 기본값, enforce Runtime Proof 전까지 이 FP 자체는 OPEN 유지):** GPT/Codex 총 12라운드 교차검토(설계 8라운드 + 구현 후 코드 리뷰 4라운드) 거쳐 구현·sign-off 완료. 설계 근거: `docs/design/FP047_COMMENT_EVENT_IDEMPOTENCY_260715.md`(v4). 핵심 구조:
- 신규 `modules/comment/comment_event_store.py` — 웹훅+폴러 공동 원자적 claim(fencing token 포함), stale lease 자동 회수(`try_claim()` 자체 내장, 별도 스윕 잡 불필요)
- 단일 진입점 `process_comment_event()`(`comment_auto_reply.py`) — `comment_poller.py`/`dm_receiver.py` 둘 다 이걸 통해서만 처리, `COMMENT_EVENT_STORE_MODE`(disabled/shadow/enforce) 킬스위치
- Airtable `source_event_id` 필드 신규 추가(API로, `tools/add_lead_interactions_source_event_field.py`) + 3-way 조회(FOUND/NOT_FOUND/LOOKUP_FAILED)로 재시도 시 중복 생성 방지
- Airtable 기록 실패는 기존 `retry_queue.py`로 위임(신규 `comment_airtable_record` 태스크), enqueue 자체 실패는 fail-closed
- `CommentProcessResult`(ACCEPTED/DUPLICATE_COMPLETED/RETRY_OWNED/IN_PROGRESS/LEGACY/REJECTED_NOT_READY) 반환값으로 poller 캐시 여부·webhook 200/503 여부를 정확히 구분
- 신규 테스트 65개(동시성/fencing/crash복구/shadow격리/webhook 2단계처리 등) 전부 통과, 전체 회귀 345 total/338 passed/4 failed(무관 기존 실패)/3 xfailed
- **`COMMENT_EVENT_STORE_MODE=disabled`(기본값)로 커밋 — 기존 운영 동작 전혀 안 바뀜. shadow/enforce 전환 및 실계정 Runtime Proof는 별도 승인 대상.**
- **enforce 진입 전 반드시 해결 필요(OPEN 잔여):** 댓글 원문 평문 저장(Telegram/로그/retry payload, ERR-066과 같은 클래스), Airtable 필드 존재 여부 startup preflight 미구현.

**예방:** 예외를 삼키는 함수(`try/except`로 로그만 남기고 반환)를 호출하는 쪽에서는, 그 반환값만으로 성공 여부를 판단하지 말고 명시적 성공/실패 신호(bool 반환 또는 예외 재발생)를 받아 그에 따라 캐시·재시도 여부를 결정할 것.

**관련:** ERR-062, ERR-067, INC-035, `docs/design/FP047_COMMENT_EVENT_IDEMPOTENCY_260715.md`

## FP-048 | 앱 테스터 미등록 실계정과의 DM 왕복이 불안정한 패턴 (Standard Access 의심)

**발생일:** 260714, 최소 2회 관측 — 13:12경 tgbtgbnate DM 1건 미도착(당시엔 원인 미조사), 16:14경 tgbtgbnate의 Private Reply 답장("무시 할게") 미도착(45분+ 경과, ERR-064로 조사)

**증상:** Meta 앱에 Instagram 테스터로 등록된 계정(채솔)과는 DM webhook이 항상 수 초 내 즉시 정상 수신되나, 앱에 아무 역할도 없는 일반 계정(tgbtgbnate)과는 **발신(Private Reply/DM)은 항상 성공**하는데 **수신(손님 답장의 webhook)만 지연되거나 도착하지 않는** 비대칭 패턴이 반복됨.

**근본원인(가설, 미확정):** Meta 앱이 `instagram_manage_messages` 등 메시징 권한에 대해 아직 App Review를 통과하지 못한 **Standard Access** 상태일 가능성 — 이 상태에서는 앱에 역할(테스터/개발자/관리자)이 있는 계정과는 완전한 기능이 보장되지만, 역할이 없는 일반 사용자와는 기능이 제한(특히 인바운드 웹훅)될 수 있음. `debug_token`으로 액세스 토큰의 스코프 자체는 정상 부여 확인됨(권한 부재는 아님) — 다만 App Review의 실제 Access Level(Standard/Advanced)은 아직 미확인이라 CONFIRMED 아님.

**해결:** 미적용(OPEN). 가설이 확정되면 코드로 해결 불가능 — Meta App Review를 통한 Advanced Access 승격이 유일한 정식 경로(회장이 직접 진행하는 행정 절차).

**예방:** 신규 실계정으로 라이브 Canary를 진행할 때 "발신 성공"만으로 "왕복 정상"이라 판단하지 말 것 — 반드시 상대방의 답장이 실제로 webhook에 도착하는 것까지 확인. 테스터로 미리 등록되지 않은 계정으로 검증할 경우 이 패턴이 재현될 수 있음을 전제하고, 가능하면 검증 전 해당 계정을 앱 테스터로 등록해두거나, 등록이 어려우면 이 제약을 감안해 결과를 해석할 것.

**관련:** ERR-064, INC-036, Gate G

## FP-049 | 설계 미완료 컴포넌트를 watchdog 상시감시에 조기 포함시키면 재시작 실패 알림이 무한 반복되며 잡음이 누적된다

**발생일:** 최소 260517부터 잠재(watchdog.log 최초 n8n 실패 기록), 실질적 근본원인 조사는 260715(ERR-065)

**증상:** 아직 실사용(워크플로우 구현) 전인 컴포넌트(n8n)를 `watchdog.ps1`이 다른 필수 프로세스(Flask/Streamlit/ngrok/launcher)와 동일하게 상시 HTTP 헬스체크·자동 재시작 대상으로 포함시켜 둔 결과, 그 컴포넌트가 정상 기동될 수 없는 상태(설치·설정 미완료 등)에서도 감시가 계속되어 실패 알림이 무한 반복 누적됨(n8n 케이스: 260711 이후 성공 0건, 실패 5천 건+).

**근본원인:** "이 프로세스가 아직 운영 대상이 아니다/설계 단계다"라는 정보가 `watchdog.ps1`의 감시 목록 자체에는 반영되지 않고, 그 프로세스 실행 여부와만 결합됨 — 감시 대상 등록과 "실제 운영 승인 여부"가 분리되어 있어, 설계만 끝난 컴포넌트도 일단 스크립트에 등록되면 무조건 감시·재시작 시도 대상이 됨.

**해결:** 260721 임시 완화 적용. LocalSystem에는 `n8n.cmd`가 없고 admin 사용자 경로에만 있으며, watchdog이 `npx n8n start`를 호출해 대화형 설치 질문에서 멈추는 실제 원인을 확인했다. `N8N_WATCHDOG_ENABLED` feature flag를 추가하고 기본값을 `false`로 두어 미완성 n8n의 감시·재시작·경고만 중지했다. 서비스 재시작 후 비활성화 로그가 1회 기록됐고 마지막 실패(12:16:38) 뒤 추가 재시도는 없었다. n8n 기능 자체는 아직 미구현·미기동이다.

**예방:** 신규 컴포넌트를 watchdog 감시 대상에 추가하는 시점을, "코드/설계 완료 시점"이 아니라 "실제 운영 승인 시점"으로 맞출 것. 부득이 미리 등록해야 한다면(예: 향후 실행 경로 테스트 목적) 실패 시 알림을 매번 보내지 않도록 별도 저빈도 채널로 분리하거나, `docs/PENDING_INVESTIGATIONS.md`류 문서에 "이 컴포넌트는 아직 감시 대상이지만 운영 미승인" 상태를 명시해 향후 조사자가 알림 잡음과 실제 장애를 혼동하지 않도록 할 것.

**관련:** ERR-065, ERR-056, PENDING-A

## FP-050 | 감시 대상 결정을 "최근 게시물 N개"처럼 최근성 기준으로 삼으면, 게시 빈도가 높은 계정에서 캠페인 대상이 감시 범위 밖으로 밀려나 통째로 누락된다

**발생일:** 260715 저녁 실계정 라이브 테스트 중 발견(회장이 다른 상품 게시물 2곳에 댓글, 1곳만 반응). ERR-069로 상세 조사.

**증상:** `comment_poller.py`가 `COMMENT_POLL_MEDIA_COUNT`(기본 5)개의 "최근 게시물"만 폴링 대상으로 삼고 있었는데, 캠페인 게시물 등록(`configs/comment_campaign_posts.json`)과 "최근 N개" 목록이 서로 별개의 기준이라 계정이 게시물을 자주 올릴수록 캠페인 게시물이 조용히 감시 범위 밖으로 밀려남. 밀려난 게시물의 댓글은 폴러가 아예 조회를 안 하므로 이벤트 자체가 시스템에 진입 못 함(웹훅도 이 계정에서는 안정적으로 안 들어와 보완이 안 됨).

**근본원인:** "무엇을 감시할지"를 운영자의 명시적 의도(캠페인 목록)가 아니라 파생적·변동 가능한 지표("최근성")로 결정하고 있었음 — 두 목록이 일치한다는 암묵적 가정에 의존했으나 이를 강제하는 동기화 메커니즘이 없었음.

**해결:** Package 1(Phase A)로 근본 수정 — 감시 대상 결정을 "최근 N개"에서 캠페인 목록 기반 상태머신(`comment_poll_targets.py`, PENDING_BASELINE/ACTIVE/PAUSED)으로 교체. 자세한 구현은 ERR-069 참고. `COMMENT_POLL_ALLOWLIST_MODE=legacy`(기본값)로 커밋 — **기본값에서는 폴링 대상 선택이 기존 recent-N 방식으로 유지된다. 단, 캠페인 설정 또는 poll-target DB 이상 시 신규 안전 게이트(`_blocked_by_allowlist_gating()`)가 fail-closed로 처리를 차단할 수 있다** — "운영 동작이 전혀 안 바뀜"이 아니라 "감시 대상 선택 로직은 그대로이나, 설정/DB 이상 상황에 대한 새 방어선이 추가됐다"는 것이 정확한 표현(260716 Codex 재검토 반영, 최초 기록의 과장 정정).

**예방:** "감시/처리 대상 목록"을 정의할 때, 그 목록이 다른 변동 가능한 파생 지표(최근성, 개수 제한, 정렬 순서 등)에 암묵적으로 의존하고 있지 않은지 확인할 것. 운영자 의도를 담은 목록과 그 목록의 실행 범위를 결정하는 지표가 다른 소스라면, 반드시 명시적 동기화·검증 로직으로 둘을 묶어야 한다(이번엔 두 목록이 몇 달째 조용히 어긋나 있었는데도 발견되지 않았음 — 실사용자 테스트가 아니었다면 계속 몰랐을 것).

**관련:** ERR-069, INC-038, FP-047

## FP-051 | 다른 도메인 패키지 안의 유틸 함수를 재사용하려고 직접 import하면, 그 패키지의 `__init__.py`가 eager import하는 형제 모듈과 순환 임포트가 발생할 수 있다

**발생일:** 260716, FP-047 enforce 전제조건(A-1, 댓글 채널 PII 마스킹 재사용) 구현 중 발견.

**증상:** `comment_auto_reply.py`가 `modules.dm.dm_auto_reply`의 `_telegram_preview()`를 재사용하려고 `from modules.dm.dm_auto_reply import _telegram_preview`를 추가하자, `modules.dm.__init__`이 eager import하는 `dm_receiver.py`가 이미 `comment_auto_reply`를 import하고 있어 순환 발생(ERR-070 상세).

**근본원인:** 패키지 경계를 넘어 유틸을 재사용할 때 "서브모듈 하나만 import한다"고 생각하기 쉽지만, Python은 상위 패키지의 `__init__.py`를 먼저 완전히 실행한다. 이 프로젝트의 `modules/dm/__init__.py`처럼 `__init__.py`가 이미 여러 형제 모듈(`dm_receiver`/`dm_auto_reply`/`dm_followup_scheduler`)을 eager re-export하고 있으면, 그 결합도가 겉으로 드러나지 않아 재사용 시점에야 순환이 드러난다.

**해결:** 공용 유틸은 특정 도메인 패키지가 아니라 처음부터 `modules/common/`에 둘 것 — 이번엔 `modules/common/pii_mask.py`(신규)로 추출해 해소, 기존 호출부(`dm_auto_reply.py` 등)는 별칭 재-import로 하위호환 유지.

**예방:** 도메인 A의 모듈이 도메인 B 패키지 내부 함수를 재사용하고 싶어지면, import를 추가하기 전에 "이게 정말 도메인 B 전용인가, 실은 공용 유틸인가"부터 판단할 것. 공용이면 `modules/common/`으로 먼저 옮기고 양쪽이 거기서 import하게 할 것. 특히 대상 패키지의 `__init__.py`가 형제 모듈들을 eager import하는 구조인지 먼저 확인할 것(이 프로젝트에 흔한 패턴이라 순환 위험이 특히 높음).

**관련:** ERR-070

## FP-052 | 운영 `.env` 값을 import 시점에 읽어 고정하는 모듈 레벨 상수에 의존하는 테스트는, 그 상수를 명시적으로 override하지 않으면 실제 정책값이 바뀌거나 pytest 수집 순서가 바뀔 때 조용히 깨진다

**발생일:** 260716, FP-047 enforce 전제조건 B 구현 후 신규 테스트 파일 추가로 pytest 전체 수집 순서가 바뀌며 발견.

**증상:** `comment_safety_guard.COOLDOWN_HOURS`가 `float(os.getenv("COMMENT_REPLY_COOLDOWN_HOURS", "24"))`로 모듈 import 시점에 한 번만 고정되는데, 실제 `.env`가 260715 이후 `0`(회장의 적극 테스트 지시)이라, 이 모듈이 `.env` 로드 이후 처음 import되는 세션에서는 쿨다운 판정식이 항상 거짓이 됨. 이를 명시적으로 override하지 않은 테스트 2건이 신규 테스트 파일 추가로 바뀐 수집 순서 때문에 그동안 잠자고 있다가 이번에 처음 표면화됨(ERR-071 상세).

**근본원인:** 모듈 레벨 상수를 "변경 가능한 운영 설정값"에서 가져오면서도, 그 상수에 의존하는 테스트가 자신이 "실제 운영값이 아니라 통제된 테스트값"으로 돌고 있다고 암묵적으로 가정함 — 같은 파일 안에 이미 명시적으로 override하는 테스트(`test_cooldown_expires_after_window`)가 있었는데도 관례가 파일 전체에 일관 적용되지 않았음.

**해결:** 해당 상수를 사용하는 테스트/fixture 전부에 `monkeypatch.setattr(module, "CONST", 고정값)`을 명시 추가. ERR-071 참고.

**예방:** (1) 모듈 레벨 상수가 `os.getenv(...)`로 채워진다면, 그 상수를 쓰는 테스트는 파일 안의 일부가 아니라 **전부** 명시적으로 override할 것(autouse fixture에 넣는 게 가장 안전). (2) 신규 테스트 파일을 추가하는 작업(오늘의 B단계처럼)이 "내 코드와 무관한 다른 테스트를 깨뜨릴 수 있다"는 점을 인지할 것 — pytest는 세션당 모듈을 한 번만 import하므로, 무엇이 무엇보다 먼저 import되는지는 파일 추가만으로도 바뀔 수 있다. (3) 단독 실행 시 통과한다고 "전체 스위트와 무관"이라고 성급히 결론짓지 말 것 — 그 자체가 import/실행 순서 의존성의 증거이지, 무관함의 증거가 아니다.

**관련:** ERR-071

## FP-053 | BOM 없는 비ASCII PowerShell 스크립트는 텍스트 diff가 정상이어도 Windows PowerShell 5.1 cold start에서 파싱 자체가 깨질 수 있다

**발생일:** 260721 노트북 부팅 후 NSSM `SNS_Watchdog` 자동복구 실패 조사에서 발견.

**증상:** 한글이 포함된 `watchdog.ps1`의 괄호·따옴표 구조는 UTF-8로 읽으면 정상인데, Windows PowerShell 5.1이 BOM 없는 파일을 시스템 코드페이지로 읽으면서 닫히지 않은 문자열과 누락된 블록 오류를 만들었다. NSSM은 자식 종료 코드 1을 감지해 60초마다 재시도했으나, 실행 전 파서 단계에서 계속 죽어 서비스 화면에는 재시도 대기 상태인 `Paused`만 보였다.

**근본원인:** 소스 내용뿐 아니라 파일 인코딩 메타데이터(BOM)가 Windows PowerShell 5.1 실행 계약의 일부인데, 기존 테스트·검증은 텍스트 내용과 장기 실행 상태만 확인하고 cold-start 파일 디코딩을 검사하지 않았다.

**해결:** `watchdog.ps1`에 UTF-8 BOM 추가. `tests/test_watchdog_encoding.py`가 BOM 바이트와 실제 Windows PowerShell `Parser.ParseFile()`을 모두 검증하도록 추가.

**예방:** 비ASCII PowerShell 스크립트는 (1) BOM 바이트 검사, (2) 대상 PowerShell 버전의 실제 파서 검사, (3) 계획된 재부팅/cold-start 검증을 서로 다른 계층으로 유지한다. 이미 떠 있는 프로세스의 장시간 정상 동작만으로 디스크의 현재 파일이 다음 부팅에도 실행된다고 판단하지 않는다.

**관련:** ERR-072, INC-039

## FP-054 | 사용자 세션 GUI 의존성을 24/7 파이프라인의 선행조건으로 두고 자동기동·readiness를 보장하지 않으면 재부팅 후 예약 잡 전체가 실패한다

**발생일:** 260721 watchdog 복구 후 첫 FB 크롤링에서 발견.

**증상:** launcher와 스케줄러는 정상 기동했지만 AdsPower Local API(50325)가 없어 4개 Facebook 대상이 같은 `WinError 10061`로 연속 실패했다. 핵심 프로세스가 살아 있다는 사실과 실제 업무 의존성이 준비됐다는 사실이 분리되어 있었다.

**근본원인:** AdsPower는 사용자 로그인 세션의 GUI 앱인데 watchdog은 LocalSystem 서비스로 실행된다. 공용 시작프로그램 바로가기는 있었지만 존재하지 않는 `AdsPower.exe`를 가리켰고, 실제 설치 파일은 `AdsPower Global.exe`였다. 이 오래된 실행파일명 때문에 로그인 후 자동 시작이 실패했다. 크롤링 전 readiness gate는 여전히 없다.

**해결:** 공용 시작프로그램 `AdsPower.lnk`의 대상을 실제 `AdsPower Global.exe`로 수정하고 `TargetExists=True`를 재확인했다. 50325 LISTENING 복구 후 다음 예약 FB 크롤링에서 4개 그룹 연결 성공·총 1건 처리로 E2E PASS. **260721 실제 재부팅 실증 완료:** `Restart-Computer -Force` 실행 후 SNS_Watchdog 자동 재기동(13:15:13)→Streamlit/ngrok/launcher 자동 복구(13:15:18~37)→AdsPower Global 자동 실행(13:17:32~40), 재부팅 후 50325/5000/8501/4040 전부 LISTENING 재확인. PENDING 해소.

**예방:** 사용자 세션이 필요한 GUI 의존성은 LocalSystem 서비스에서 직접 띄우는 방식으로 섣불리 해결하지 않는다. 로그인 세션 자동 시작, 별도 태스크, 또는 명시적 운영 절차 중 하나를 결정하고, 크롤러는 fan-out 전에 50325를 한 번 검사해 공통 선행조건 실패로 보고해야 한다.

**관련:** ERR-073, INC-040, ERR-058

## FP-055 | 삭제·권한소실된 외부 리소스 ID를 로컬 제어판에 계속 보관하면 예약 작업마다 같은 API 오류가 반복된다

**발생일:** 260611 최초(ERR-039/INC-021), 260721 6개 ID로 재발.

**증상:** Airtable에 `posted + ig_media_id 있음`으로 남은 Instagram media ID가 Graph API에서는 `code=100 / subcode=33`으로 더 이상 접근되지 않아 Engagement 수집 때마다 경고가 반복됐다. 계정·토큰은 정상이어도 일부 오래된 ID만 무효가 될 수 있다.

**근본원인:** 외부 리소스의 삭제·권한소실 상태와 Airtable의 `ig_media_id` 상태가 자동 동기화되지 않는다. 조회 실패를 기록만 하고 무효 ID를 조회 대상에서 격리하지 않아 같은 실패가 다음 주기에도 재현된다.

**해결:** 전체 291개를 배치 검증해 접근 불가 6개를 특정하고, 승인 후 레코드·현재 ID·`posted` 상태가 모두 일치할 때만 `ig_media_id`를 공란 처리했다. 처리 후 6/6 `null`, 신규 게시물 4개를 포함한 현재 대상 289/289가 Graph API 접근 가능함을 재검증했다.

**예방:** Engagement 수집기가 연속 `100/33`을 받은 ID를 별도 상태로 격리하거나 승인 가능한 정리 목록으로 올리게 한다. 계정/토큰 전체 이상과 개별 media 소실을 구분하기 위해 계정 조회와 최근 media 조회를 먼저 통과시킨 뒤 개별 ID를 판정한다.

**관련:** ERR-039, INC-021

---

## FP-056 | "수집→검토" 2단계 파이프라인에서 검토 단계만 자동/안전화하고 수집 단계를 수동 트리거로 남기면, 검토 큐가 바닥나도 알림 없이 조용히 멈춘다

**발생일:** 260713 최초 구축(수동 러너로 설계), 260721 8일간 수집 0건으로 발현.

**증상:** 리뷰 그리드는 PENDING 0건이 되면 "검토할 것이 없습니다"라는 정상적인 완료 메시지를 보여줄 뿐, "수집이 며칠째 안 되고 있다"는 경고를 하지 않는다. 큐가 정상적으로 다 처리된 상태와 상류 수집이 멈춘 상태가 화면상 구분되지 않는다.

**근본원인:** 파이프라인의 한쪽 절반(리뷰/저장/undo)만 여러 차례 리뷰를 거쳐 자동화·하드닝됐고, 다른 절반(수집)은 "필요할 때 사람이 돌리는 도구"로 남겨진 채 그 사실이 대시보드나 알림 어디에도 드러나지 않았다.

**예방:** 수집→검토처럼 앞단이 뒷단을 채우는 구조의 파이프라인은 (1) 앞단이 자동인지 수동인지를 대시보드에 명시하거나, (2) 마지막 수집 시각 기준 경과일이 임계치를 넘으면 별도 알림을 내보내는 가드를 둔다. "PENDING 0건"을 무조건 좋은 신호로 표시하지 않는다.

**관련:** ERR-074, ERR-059, FP-044

---

## FP-057 | 실패경로가 Airtable Schema에 없는 필드를 참조하는 패턴이 필드명을 바꿔가며 반복 재발한다

**설명:** 게시/작업 실패 시 상태를 기록하려는 코드가 Airtable에 실제로 존재하지 않는 필드를 PATCH payload에 포함시켜, 그 상태-기록 PATCH 자체가 422 UNKNOWN_FIELD_NAME으로 거부되고 대상 레코드가 중간 상태(`uploading` 등)에 영구 고착되는 패턴.

**근본 원인:** 실패 경로 코드(예외 처리·상태전환 로직)를 작성·수정할 때 Repository Interface에 새 필드를 추가하면서 실제 Airtable Schema와 대조하는 절차가 없음. 최초 발생(ERR-041, 2026-06-16, `retry_count`/`last_error_msg`)이 커밋 `463c350`으로 수정됐으나, 이후 별도 리팩터링(추정: Repository DI 전환)에서 동일 실패 경로에 새 필드(`error_code`)가 다시 도입되며 동일 클래스가 재발(ERR-075).

**증상:** 게시/작업 실패 시 `422 Client Error: Unprocessable Entity` + `UNKNOWN_FIELD_NAME` 메시지가 error.log에 기록되고, 해당 레코드의 상태값이 `failed` 등 최종 상태로 전환되지 않은 채 중간 상태에 남는다.

**예방:** (1) Repository Interface에 새 필드를 추가할 때마다 실제 Airtable Schema(get_table_schema 등)와 대조하는 절차를 필수화한다. (2) 실패 경로 자체의 오류(상태 기록 실패)를 별도로 감지·알림해 "실패의 실패"가 조용히 묻히지 않게 한다. (3) 동일 클래스 재발 이력(ERR-041 → ERR-075)이 있으므로 향후 수정 시 회귀 테스트에 이 필드 존재 여부 확인을 포함한다.

**관련:** ERR-041, ERR-075, INC-022, INC-042, FP-009

---

## FP-058 | 외부 API의 "명확해 보이는" 4xx가 실제로는 일시적 상태일 수 있음 — 상태코드만으로 최종성 단정 금지

**설명:** 외부 API(Meta Graph API 등)가 4xx를 반환해도, 그게 항상 "영구적 거부"를 의미하지 않는다. 비동기로 처리되는 리소스(예: 업로드된 미디어 컨테이너가 아직 처리 중)에 너무 이른 타이밍에 요청하면, 서버가 "아직 준비 안 됨"을 클라이언트 오류(4xx)로 표현하는 경우가 있다.

**근본 원인:** API 설계 문서(Meta Graph API 공식 문서 포함)가 "컨테이너 상태를 폴링한 뒤 발행하라"는 권장 패턴을 제시하지만, 이걸 따르지 않고 컨테이너 생성 직후 곧바로 발행을 시도하면 처리 미완료 상태에서 400을 받을 수 있다. 이 프로젝트는 260725 Codex 리뷰에서 "HTTP 4xx=명확한 실패, 재시도 금지"라는 안전 규칙을 확정했는데(중복게시 방지가 목적), 그 규칙 자체가 "4xx는 항상 최종적"이라는 암묵적 가정 위에 서 있었다.

**증상:** `/media_publish`(또는 유사한 2단계 발행 API)를 컨테이너 생성 직후 호출하면 HTTP 400, 몇 초~수십 초 뒤 같은 리소스 ID로 재시도하면 HTTP 200으로 정상 처리됨(ERR-076).

**예방:** (1) 외부 API 재시도 정책을 설계할 때 "상태코드만으로 최종성 단정 금지"를 기본 원칙으로 삼는다. (2) 가능하면 공식 문서의 "polling/status 확인 후 다음 단계 진행" 패턴을 따른다. (3) 4xx를 최종실패로 분류해 기록하더라도, 재시도에 필요한 컨텍스트(예: `creation_id`)는 사람이 수동으로라도 복구할 수 있게 최종 저장소(Airtable 등)에 남긴다 — 로그에만 남기면 복구 난이도가 불필요하게 올라간다.

**관련:** ERR-076

---

## FP-059 | 계정마다 Meta Auth 플로우(Facebook Login for Business vs Instagram API with Instagram Login)가 다르면, 토큰 재발급 화면을 잘못 고르는 것만으로 토큰 포맷·호스트·계정ID 체계가 통째로 바뀐다

**설명:** Meta는 Instagram Graph API 접근에 최소 두 가지 플로우를 제공한다 — (A) Facebook Login for Business: FB 페이지를 경유, `EAA` 접두 토큰, `graph.facebook.com`, 계정ID는 FB 연결 기준. (B) Instagram API with Instagram Login: Instagram 계정 직접 로그인, `IGAA` 접두 토큰, `graph.instagram.com` 전용, 계정ID 체계도 별도. 같은 Instagram 계정이라도 어느 화면에서 토큰을 발급받았는지에 따라 완전히 다른 토큰·ID·호스트가 나오며, 기존 코드가 특정 플로우에 고정 배선돼 있으면 다른 플로우로 재발급 시 즉시 호환 오류가 난다.

**증상:** 재발급된 토큰으로 기존 호출 경로(`graph.facebook.com`)를 그대로 두면 `OAuthException code 190 "Cannot parse access token"` 발생(ERR-077). 토큰 자체는 유효하지만(다른 호스트에서는 200), 계정ID까지 다르게 나와 필드 조회도 어긋난다.

**예방:** (1) 계정별로 "어느 플로우로 발급됐는지"를 `Account_Registry` 등 SSOT에 명시 필드로 남긴다(이 프로젝트는 260724에 `api_provider`/`credential_key`로 이미 도입 — 재발급 매뉴얼에도 계정별 플로우를 함께 기록해야 함). (2) 토큰 재발급용 매뉴얼(`docs/Instagram_토큰발급_매뉴얼.md`)이 특정 플로우 전용임을 문서 제목/상단에 명시한다. (3) 토큰 교체 후 반드시 실제 호출 경로(호스트)로 read-only GET 검증하고, 계정ID가 기존 값과 일치하는지까지 대조한다(포맷만 맞고 ID가 다른 경우를 놓치지 않기 위해).

**관련:** ERR-077

---

## FP-062 | 저장소 루트에 남은 옛 스냅샷/백업 폴더가 pytest 등 "전체 탐색" 도구와 충돌할 수 있다 — .gitignore로 git 추적만 막는 것으로는 로컬 도구 충돌까지 막지 못한다

**설명:** `.gitignore`는 git 추적(커밋/푸시)만 막을 뿐, 로컬 디스크에 실제로 존재하는 파일까지 숨기지는 않는다. pytest·`grep -r`·기타 "현재 디렉터리 전체를 도는" 도구들은 `.gitignore`를 인식하지 않으므로, gitignore된 백업/스냅샷 폴더 안에 원본과 동일한 이름의 파일(특히 Python 패키지 `__init__.py` + 동일 모듈명)이 있으면 실제 충돌이 발생할 수 있다.

**증상:** 특정 파일을 명시적으로 지정해 실행하면 정상, 아무 인자 없이 "전체 실행"하면 알 수 없는 이유로 다수 파일이 한꺼번에 실패(ERR-081).

**예방:** (1) 테스트 도구는 `testpaths`/`--rootdir` 등으로 탐색 범위를 명시적으로 고정한다(이번에 `pytest.ini`로 적용). (2) 저장소 루트에 백업/스냅샷을 둘 때는 가능하면 저장소 트리 밖(예: `C:\backup_*`처럼 이미 이 프로젝트가 쓰는 방식)에 두는 걸 우선한다 — 루트 안에 두려면 원본과 같은 하위구조(특히 `tests/`)를 통째로 복제하지 않는다.

**관련:** ERR-081, INC-043

---

## FP-060 | Airtable REST API는 페이지당 최대 100건만 반환한다 — 응답의 offset을 따라가지 않으면 "전체 조회"가 조용히 일부만 반환한다

**설명:** Airtable REST API는 명시적으로 pageSize(기본/최대 100)만큼만 레코드를 반환하고, 더 있으면 응답 바디에 `offset` 필드를 함께 준다. 호출부가 이 `offset`을 다음 요청의 파라미터로 넘기지 않으면, 에러 없이 "성공"으로 응답하면서도 첫 페이지만 반환한다 — 개수가 100 이하인 동안은 증상이 전혀 안 보이다가, 100을 넘는 순간부터 조용히 데이터가 누락되기 시작한다.

**증상:** "전체 레코드 반환"을 의도한 메서드가 레코드 수가 100을 넘는 테이블에서 항상 정확히 100건(또는 요청한 pageSize)만 반환. 집계 지표(개수, 비율)가 실제와 크게 달라질 수 있음(ERR-078: 594건 중 100건만 봐서 84% 데이터 누락, 성공률 61.0%→66.2%로 정정).

**예방:** (1) "전체 조회" 성격의 메서드를 새로 만들 때는 반드시 `offset` 순회 루프를 기본으로 넣는다 — 이 코드베이스엔 이미 올바른 예시(`count_candidates_by_status()`)가 있었으니 새 코드 작성 전 기존 패턴부터 찾아본다. (2) 100건 근처의 소규모 데이터로만 검증하면 이 버그가 절대 드러나지 않는다 — 실제 규모(수백 건 이상)로 최소 1회는 다른 출처(대시보드 등)와 실측 대조한다(이번엔 대시보드 표시 건수와의 불일치로 발견됨). (3) 같은 파일 내 유사 메서드(`fetch_candidate_phashes()`)에 이미 "미구현" 주석이 남아있었다는 것 자체가, 한 곳에서 발견한 패턴 결함을 전체 파일에 걸쳐 훑어봐야 한다는 신호였음 — 이번엔 그 스윕까지는 범위 밖으로 미룸.

**관련:** ERR-078

---

## FP-061 | Meta Graph API Explorer가 기본 발급하는 토큰은 단기(수 시간 내 만료) — "발급 성공 = 장기 사용 가능"이 아니다

**설명:** Graph API Explorer의 "Generate Access Token" 버튼으로 받는 토큰은 기본적으로 짧은 수명(이번 사례 실측 약 5시간)을 가진다. 발급 직후 read-only GET으로 정상 응답을 받아도, 그건 "지금 유효하다"는 확인일 뿐 "앞으로도 유효하다"는 보장이 아니다 — 장기(60일 또는 무기한) 토큰으로 쓰려면 별도로 Access Token Debugger의 "액세스 토큰 확장(Extend Access Token)" 또는 `fb_exchange_token` API 호출을 반드시 거쳐야 한다.

**증상:** 토큰 교체 직후엔 정상 동작하다가, 발급 후 수 시간~하루 이내에 전체 API 호출이 갑자기 `OAuthException code 190 "Session has expired"`로 일괄 실패하기 시작(ERR-079).

**예방:** (1) 토큰을 새로 발급받을 때마다 "발급 → 즉시 검증"만으로 끝내지 않고 "발급 → 장기 교환 → 그 결과로 검증"까지를 한 세트로 취급한다. (2) Access Token Debugger로 "만료일" 필드를 직접 확인해 무기한/장기인지 재확인한다(이번 사례에서 처음 발급받은 토큰의 디버거 출력에 "만료일: 약 1시간 이내"라고 명시돼 있었음에도 이 단계를 건너뛰고 바로 저장했던 게 재발 원인). (3) 재발급 절차 문서(`docs/Instagram_토큰발급_매뉴얼.md`)에 장기 교환을 필수 단계로 명시한다.

**관련:** ERR-079

---

## FP-063 | 쓰기 실패 상태전환 함수가 broad except로 예외를 삼키고 retry_queue 위임 없이 로그만 남기는 패턴이 CRM 모듈 전반에 반복된다

**설명:** Lead/주문 상태를 Airtable에 기록하는 함수(최초 Lead 생성, 스코어 갱신, CLOSE 처리, 주문 전환 처리)가 공통적으로 `try: _repo.쓰기함수() / except Exception: logger만` 구조를 갖는다. `retry_queue`(`modules/common/retry_queue.py`) 인프라가 이미 존재하고 다른 경로(`dm_followup_scheduler.py`/`comment_*`/`kpi_collector.py`/`health_monitor.py`)에는 이미 연동돼 있음에도, CRM 쓰기 경로 중 현재 Live인 3곳(`dm_receiver.py::record_interaction()` 호출부, `lead_scorer.py::update_lead_score()`, `order_detector.py::handle_order_conversion()`)은 전혀 연동되지 않았다. `order_detector.py`는 한 걸음 더 나아가, 상태 갱신 실패 여부와 무관하게 Telegram "완료" 알림을 `try` 블록 밖에서 무조건 발송해 상태-알림 불일치까지 발생한다. `lead_closer.py::mark_lead_closed()`는 동일한 코드 패턴을 갖지만 260729 재검증 결과 Production Caller가 0건(NOT_ACTIVE/LATENT_RISK, ERR-087)으로 확인돼, 현재는 이 패턴의 활성 사례가 아니라 향후 Scheduler 연결 시 활성화될 잠재 사례로 분류한다.

**근본 원인:** ERR-080(order_detector) 최초 발견 시 Airtable 필드 스키마 불일치라는 "증상"만 고치고, 그 증상을 감싸고 있던 예외삼킴 코드 구조 자체는 동일 클래스로 재사용 가능한 패턴임에도 다른 파일로 전파 여부를 스윕하지 않았다. CRM 모듈(`modules/crm/`, `modules/dm/dm_receiver.py`)을 작성할 때 "쓰기 실패 시 로그만 남기고 파이프라인은 계속 진행"이라는 방어적 스타일이 반복 채택됐으나, 이게 fail-open이 적절한 지점(예: 계정 태깅처럼 부가 정보)과 fail-closed·durable-retry가 필요한 지점(Lead 원본 데이터 생성, 상태 전환)을 구분하지 않고 동일하게 적용됐다.

**증상:** Airtable 쓰기가 어떤 이유로든 실패해도 error.log에 한 줄 남을 뿐 파이프라인은 "정상 진행"한 것처럼 계속되고(호출자에게 HTTP 200이 그대로 반환됨), durable retry·dead letter·failure state 경로가 없어 실패가 방치된다. ERR-088(order_detector)에서 이 구조가 Live 상태로 Confirmed됐다 — 260729 재검증에서 실제 실패 로그 9건과 Airtable 미반영 상태(조회 시점 기준)까지 실측 확인했으나, 그 9건 전부가 테스트용 식별자였으므로 실제 고객 데이터 손실 여부는 별도로 UNKNOWN이다. ERR-085/086은 Live Caller Chain은 Confirmed이나 조사 범위 내 실제 발생 로그는 0건, ERR-087은 Production Caller 자체가 없어 현재는 발현되지 않는다.

**예방:** (1) Lead 최초 생성처럼 "실패=이벤트 자체 소멸"인 지점부터 우선순위를 두어 `retry_queue` 연동을 순차 적용한다(이미 다른 모듈에 검증된 인프라를 재사용 — BUILD보다 REUSE). (2) 상태 갱신과 알림 발송을 같은 `try` 블록으로 묶어, 실패 시 알림도 함께 억제하거나 "실패" 알림으로 전환한다. (3) 새로운 쓰기 함수를 CRM 모듈에 추가할 때 이 패턴(broad except + log-only)을 기본값으로 복붙하지 않도록, 리뷰 체크리스트에 "이 실패는 fail-open이 맞는가, retry_queue가 필요한가"를 명시적으로 묻는 항목을 추가한다. (4) 코드 패턴만으로 Risk를 매기지 말고, 이번처럼 Runtime Caller·Import Chain·실제 로그까지 재검증해야 활성/잠재 사례를 구분할 수 있다는 점을 감사 절차에 포함한다.

**관련:** ERR-080, ERR-085, ERR-086, ERR-087, ERR-088, FP-057, FP-064

**260729 후속(commit `75c60d2`):** 이 패턴의 4개 구체 사례(ERR-085~088)를 모두 retry_queue 연동으로 수정 완료(RESOLVED). 단, 예방책 (2)(상태-알림 게이팅)는 ERR-087에만 적용했고 ERR-088(order_detector)은 회장/GPT 지시로 기존 계약 보존을 우선해 알림 게이팅을 의도적으로 적용하지 않았다 — 이 패턴 자체(broad except + 무조건 알림)의 재발 방지책 (3)(리뷰 체크리스트 항목화)은 아직 미착수.

---

## FP-064 | 테스트 실행이 운영 error.log·app.log에 그대로 기록되어 Test Artifact와 Production Incident를 로그만으로 구분하기 어렵다

**설명:** pytest 테스트 실행 중 발생시킨 mock 예외(예: `ConnectionError("timeout")`)가 실제 운영 로그 파일(`logs/error/error.log`, `logs/summary/app.log`)에 그대로 기록된다. 로거가 테스트 환경과 운영 환경을 구분하지 않고 동일한 파일 핸들러를 사용하기 때문이며, 인접 로그 줄에 `pytest-of-admin\pytest-176\...` 같은 pytest 임시 디렉터리 경로가 함께 남는 경우에만 Test Artifact임을 구분할 수 있다(그 흔적이 없으면 구분이 불가능하다).

**근본 원인:** `modules/common/logger.py`(중앙 로거)가 테스트 실행 시에도 동일한 파일 핸들러를 그대로 사용하도록 설정돼 있어, 테스트 스위트가 실제로 파일에 쓰기 작업을 수행한다. 테스트/운영 로그 분리나 실행 출처 표시(예: `PYTEST_CURRENT_TEST` 환경변수 감지 후 태깅) 장치가 없다.

**증상:** 운영 로그에서 특정 에러 문자열이 반복 발견되면 실제 Production Incident로 오판하기 쉽다 — 이번 ERR-087 최초 등록(260729)이 실제 사례로, `[Closer] CLOSE 처리 실패 | timeout` 16건을 실제 Runtime 결함으로 판단했으나 재검증 결과 pytest 실행의 부산물(Test Artifact)로 확인돼 False Positive였음이 드러났다.

**예방:** (1) 테스트 실행 시 운영 로그 파일과 분리된 별도 로그 대상을 쓰도록 로거를 환경 감지형으로 개선한다(예: `PYTEST_CURRENT_TEST` 존재 시 다른 핸들러 사용). (2) 최소한 과도기적으로는, 로그 메시지에 실행 출처(pytest vs 실제 프로세스)를 태깅한다. (3) 운영 로그 기반 장애 감사 시, 에러 문자열만으로 결론 내리지 말고 인접 로그의 pytest 경로 흔적·Caller/Import Chain 재확인을 거치는 절차를 감사 표준에 포함한다.

**관련:** ERR-087, FP-063

## FP-065 | 여러 계정을 지원해야 하는 경로에서 "전역 fallback"이 사실은 특정 계정 1개로 고정돼 있으면, 다른 계정의 실패가 그 고정 계정 소유 자원으로 잘못 흘러갈 위험이 있다

**설명:** 계정 식별/자격증명 해석이 실패했을 때 안전하게 "기존 전역 설정"으로 fallback하는 패턴은 계정이 1개였던 시절에는 무해하지만, 다계정으로 확장된 뒤에도 그 전역 설정(env 변수 등)이 여전히 특정 계정 1개(A)만 가리키고 있으면, 계정 A가 아닌 다른 계정(B)의 해석 실패가 "안전한 fallback"이 아니라 "A 소유 자원으로 B의 요청을 잘못 시도"하는 상황으로 바뀐다.

**근본 원인:** fallback 설계 당시(단일계정 시절) "전역 설정=기본값"이라는 가정이, 다계정 확장 이후에도 코드에 명시적으로 재검토되지 않고 그대로 남아있었다. "해석 실패 시 fallback"이라는 안전장치 자체는 맞지만, fallback 목적지가 실제로 "누구 것인지"를 구분하는 조건이 없었다.

**증상:** 260730 DM Routing Close Gate 조사 중 발견 — `modules/dm/dm_auto_reply.py::_resolve_dm_send_target()`이 실패하면 `send_ig_reply()`/`_send_ig_dm()`이 조건 없이 전역 `FACEBOOK_PAGE_ID`/`INSTA_ACCESS_TOKEN`(실측 결과 yuna18253 고정)으로 발송을 시도 — aijomoojin 등 다른 계정의 해석 실패가 yuna18253 소유 Page Token 시도로 이어질 잠재 위험이었다(실제 오발송 발생 전에 리뷰로 차단, ERR-091).

**예방:** 다계정 구조에서 "전역 fallback"을 유지하려면, fallback 목적지가 실제로 어느 계정 소유인지 상수/설정으로 명시하고, 계정이 이미 식별된 상태(예: `account_code_ref` 보유)에서 해석만 실패했다면 그 계정이 fallback 소유자 자신인 경우에만 fallback을 허용하고, 그 외에는 fallback을 생략하고 명확한 실패로 처리(retry_queue 등)한다. 계정 자체가 식별 안 된(레거시) 경우만 기존처럼 전역 fallback을 유지한다.

**관련:** ERR-091, FP-046(다른 대상이 여러 개일 때 "최신값" fallback이 잘못 매칭되는 동일 계열의 상위 패턴)

## FP-066 | 계정마다 지원 가능한 외부 API 기능(Product)이 다를 수 있다 — 자격증명 라우팅만으로는 API 자체가 지원 안 되는 계정을 구할 수 없다

**설명:** 다계정 확장 설계 시 "계정별로 올바른 자격증명/엔드포인트로 라우팅하면 그 계정에서도 동일 기능이 동작할 것"이라는 암묵적 가정이 있었다. 하지만 Meta 같은 플랫폼은 계정이 어떤 인증 흐름(Facebook Login for Business vs Instagram API with Instagram Login 등)으로 연결됐는지에 따라 애초에 특정 기능(API Product) 자체를 제공하지 않는 경우가 있다 — 이 경우 라우팅을 아무리 정확히 해도 그 계정으로는 해당 기능을 쓸 방법이 없다.

**근본 원인:** DM 라우팅(ERR-091)에서 검증된 "계정별 credential 분기" 패턴을 다른 기능(댓글 Private Reply)에도 그대로 REUSE 가능할 것이라 가정했으나, 검증 없이 재사용 범위를 확대하면 그 기능이 대상 계정 유형에서 API 차원에서 지원되는지를 놓칠 수 있다.

**증상:** 260730 10.5-6단계 설계 중 발견 — 댓글 Private Reply(`recipient.comment_id`, `POST /{page-id}/messages`)는 Meta 공식문서상 Facebook Page 연동이 필수인데, aijomoojin(`instagram_login`)은 Facebook Page 자체가 없어 아무리 자격증명을 정확히 골라도 이 API를 호출할 방법이 없다(ERR-092).

**예방:** 기존 기능을 다른 계정 유형으로 확장하기 전에, 그 기능이 사용하는 정확한 API Product/엔드포인트가 대상 계정의 인증 유형에서도 공식적으로 지원되는지 먼저 확인한다(공식문서 확인 우선, 라우팅 코드부터 짜지 않는다). 지원되지 않는 계정 유형은 "다르게 라우팅"이 아니라 "그 기능 자체를 스킵(fail-closed, 로그만 남김)"으로 처리하고, 대안(예: 공개 답글로 전환)은 별도 사업적 결정으로 분리한다.

**관련:** ERR-091, ERR-092

## FP-067 | Active/Reference 저장소가 공존하는 환경에서, sys.path를 스크립트가 직접 챙기지 않으면 시스템 PYTHONPATH가 조용히 구버전(Reference) 코드로 우회시킬 수 있다

**설명:** Active Runtime(260511)과 Reference Only(250723) 두 저장소가 같은 머신에 공존하는 상태에서, 시스템 `PYTHONPATH` 환경변수가 Reference 저장소를 가리키고 있으면, `python 파일.py` 형태로 직접 실행되는 스크립트(sys.path[0]이 스크립트 자신의 디렉터리가 되어 프로젝트 루트가 자동으로 포함되지 않는 경우)는 `import modules.xxx` 시 Active 저장소가 아니라 Reference 저장소를 잘못 찾을 수 있다.

**근본 원인:** 정식 패키지(`__init__.py` 보유)로 한 번 resolve된 최상위 모듈(`modules`)은 이후 그 서브모듈 검색을 해당 디렉터리 안으로 한정한다(namespace package가 아닌 한 다른 sys.path 항목으로 넘어가지 않음) — 따라서 최상위 `modules` 패키지가 어느 저장소에서 먼저 발견되느냐가 그 프로세스 전체의 import 결과를 결정한다. 진입점 스크립트(`launcher/main.py`)나 테스트 러너(`pytest`)는 이를 피하기 위한 자체 sys.path 처리를 갖고 있지만, 새로 작성하는 일회성 스크립트는 이 처리가 없으면 취약하다.

**증상:** 260730 ERR-094 — `tools/run_followup_routing_canary.py`를 sys.path 처리 없이 작성해 직접 실행했더니 `modules.dm`이 250723(Reference, 서브모듈 구조가 다름)에서 resolve돼 `ImportError`가 발생. 만약 우연히 같은 이름의 서브모듈이 양쪽에 존재했다면 에러 없이 조용히 구버전 코드가 실행됐을 것.

**예방:** Active/Reference 저장소가 공존하는 프로젝트에서 신규 진입점·진단 스크립트를 작성할 때는 항상 파일 최상단에 `sys.path.insert(0, 프로젝트_루트)`를 포함한다(이미 확립된 `launcher/main.py` 패턴 재사용). 근본적으로는 시스템 `PYTHONPATH`가 Reference 저장소를 가리키지 않도록 정정하는 것이 맞다(환경 설정 문제, 코드로 매번 우회하는 것은 임시방편).

**관련:** ERR-094

---

## FP-068 | 좁게 스코프된 Track(Canary/Soak Test) 도중 발견한 "관련 위험"을 고치려다 Track 자체의 Scope 밖 구조개선으로 번질 수 있다

**설명:** 좁게 정의된 작업(예: 단일계정 Publishing Soak Canary) 도중 실행 전 안전점검을 하다가 그 작업과 인접한(그러나 그 작업의 성공에 필수는 아닌) 위험을 발견하면, "이왕이면 안전하게 미리 고치자"는 판단으로 공용/Closed-Gate 코드를 건드리기 쉽다. 5요소 Decision Memo와 회장의 "진행해" 승인을 받았더라도, 그 승인이 "이 문제를 고쳐도 되는가"에 대한 것이었을 뿐 "이게 지금 이 Track의 Scope 안인가"까지 확인된 것은 아닐 수 있다.

**근본 원인:** 상태변경 승인 절차(5요소/Decision Memo)가 "무엇을 고치는가/왜/어떻게 원복하는가"는 강제하지만, "이게 지금 이 Track의 공식 Scope 안에 있는가"를 별도 항목으로 강제하지 않으면, 발견된 위험이 실제로 그 Track의 필수 블로커인지 아니면 그냥 "관련되어 보이는 다른 개선"인지가 승인 절차 안에서 흐려진다.

**증상:** 260730 ERR-095 — 10.6-3(aijomoojin Publishing Soak Canary) 실행 전 점검 중 "실게시 테스트 데이터가 운영 KPI에 섞인다"는 위험을 발견 → 5요소 제출 후 승인받아 공용 `kpi_collector.py`를 수정했으나, 이 수정 자체가 Publishing Soak의 필수 블로커였다는 증거 없이 Track B(콘텐츠/KPI 구조개선)급 변경으로 Scope가 확장됨 — 회장 판정 후 전량 원상복귀.

**예방:** 좁게 스코프된 Track 도중 인접 위험을 발견하면, "지금 고칠지"를 묻기 전에 먼저 "이게 이 Track의 성공에 필수인가, 아니면 별도 Track/HOLD로 분리해야 하는가"를 명시적으로 구분해 보고하고, 필수가 아니면 발견만 기록한 뒤 진행 중인 Track을 계속한다 — "이왕이면"은 승인 사유가 아니다.

**관련:** ERR-095

---

## FP-069 | 공용 함수의 시그니처를 바꾸는 커밋은, 그 함수를 호출/mock하는 모든 테스트 파일을 전수 확인하지 않으면 회귀 스위트를 조용히 무력화할 수 있다

**설명:** 여러 파일에서 호출되는 공용 함수(`send_ig_reply()` 등)의 파라미터를 늘리는 변경은, 그 함수를 사용하는 프로덕션 호출부는 컴파일/런타임 에러로 바로 드러나지만, **그 함수를 가짜(mock)로 대체해 우회하는 테스트**는 실제로 실행되기 전까지 조용히 남아있다가 실행 시점에야 `TypeError`로 드러난다. 그마저 그 테스트 파일이 한동안 실행되지 않으면(다른 세션/작업에 밀려) 회귀 안전망이 무력화된 상태로 몇 시간~며칠 방치될 수 있다.

**근본 원인:** 시그니처 변경 커밋 시점에 "이 함수를 호출하는 Production 코드"만 확인하고, "이 함수를 mock하는 테스트 코드"까지는 전수 확인하지 않으면, 테스트가 실제로는 이미 깨진 채로 다음 실행 전까지 "통과 상태"처럼 방치된다(마지막으로 확인됐던 결과가 최신인 것처럼 오인됨).

**증상:** 260730 ERR-096 — 커밋 `ae2bec2`(`send_ig_reply()`에 `account_code_ref` 3번째 인자 추가)가 `test_dm_rules.py`의 mock 3개를 놓쳐, 이후 몇 시간 동안 이 3개 테스트가 계속 실패 상태였으나 그 사이 아무도 이 특정 파일을 실행하지 않아 발견되지 않음. 별개의 신규 기능(10.6-4B) 작업 후 전체 스위트를 돌리다가 우연히 발견됨.

**예방:** 여러 곳에서 mock되는 공용 함수의 시그니처를 바꿀 때는 `grep -rn "함수이름"` 으로 프로덕션 호출부뿐 아니라 **테스트의 monkeypatch/mock 정의**까지 전수 나열한 뒤, 해당 시그니처를 사용하는 모든 테스트 파일을 그 커밋 안에서 함께 갱신하고 전체 스위트를 실행해 Baseline과 대조한다.

**관련:** ERR-096

---

## FP-070 | Feature Flag로 오래 꺼져 있던 코드 분기는, 그 분기 안에 있는 안전장치(중복방지 등)까지 함께 검증된 적이 없을 수 있다

**설명:** `if/else`의 한쪽 분기가 Feature Flag(`PRICE_AUTO_REPLY_ENABLED` 등)로 오랫동안 비활성 상태였다면, 그 분기 안의 로직뿐 아니라 **그 분기가 의존하는 주변 안전장치(중복방지·Rate Limit·잠금 등)도 실제 트래픽으로 검증된 적이 없다**는 뜻이다. 반대쪽(활성) 분기에만 중복방지가 있고 비활성 분기에는 없어도, 지금까지는 아무 문제가 없었던 것처럼 보인다 — 그 분기가 한 번도 실행되지 않았기 때문이다.

**근본 원인:** Gate C(`PRICE_AUTO_REPLY_ENABLED=false`, 260713) 도입 당시 "가격 숫자 자동발송을 막는다"는 목적에 집중해 `false` 분기(상품확인 템플릿)에만 즉시-선점 중복방지를 추가했고, 나중에 `true`가 될 `persona`/AI 분기는 "그때 가서" 검증하면 된다고 암묵적으로 남겨뒀다. Flag가 실제로 계정별로 켜지는 시점(10.6-4D)이 되어서야 그 분기가 처음 실제 트래픽을 받았고, 없던 안전장치가 그제서야 드러났다.

**증상:** 260730 ERR-097 — `reply_mode=persona`를 처음 실제로 켠 순간, `generate_reply()` 처리 시간(수십 초) 동안 도착한 후속 문의가 전부 중복 발송됨. 코드 자체는 몇 달 전부터 존재했지만 실제로 실행된 것은 오늘이 처음.

**예방:** Feature Flag로 꺼진 분기를 처음 켤 때는 "그 분기의 핵심 로직"만이 아니라 "그 분기 진입 시점의 중복방지·잠금·Rate Limit이 반대쪽 분기와 동등한 수준인지"를 별도로 점검 항목에 넣는다 — 반대쪽 분기에 이미 있는 안전장치를 그대로 재사용/대칭 구현했는지 확인한다.

**관련:** ERR-097

---

## FP-071 | 하나의 안전 패턴을 한 곳에만 적용하고 "동일 패턴을 쓰는 나머지"로 확대 적용하지 않으면, 코드 주석에 위험이 적혀 있어도 방치될 수 있다

**설명:** 여러 곳에서 반복되는 구조적 위험(예: retry_queue 핸들러 지연등록)을 발견해 그중 **하나만** 표준 해결 패턴으로 고치고 나면, 그 수정의 주석/문서에 "다른 곳도 같은 위험이 있다"고 명시적으로 적어놓아도, 실제로 나머지에 그 패턴을 적용하는 작업은 별도 티켓·후속 조치 없이는 누락되기 쉽다. 코드에 위험이 "기록"돼 있는 것과 "해소"돼 있는 것은 다르다.

**근본 원인:** 안전 패턴 적용 작업이 "지금 당장 문제가 된 사례 1건 해결"로 스코프가 좁혀지면, 같은 커밋/세션 안에서 "이 패턴을 쓰는 다른 코드가 더 있는가"를 `grep`으로 전수 확인하는 단계가 생략되기 쉽다.

**증상:** 260730 ERR-098 — `comment_auto_reply.py::register_retry_handlers()`의 주석이 `ig_auto_reply`/`ig_followup`도 같은 위험이 있다고 명시적으로 적어뒀지만(FP-047 당시), 실제 조치는 `comment_airtable_record` 하나에만 적용되고 나머지 5개(위 2개 포함)는 그대로 방치돼 몇 달 뒤 실제 데이터 유실(30건 dead)로 이어짐.

**예방:** 구조적 위험을 발견해 표준 패턴으로 고칠 때는, 그 즉시 `grep -rn`으로 동일 패턴(예: 특정 함수 호출 시그니처, 특정 구조)을 쓰는 다른 위치를 전수 나열하고, 전부 같은 커밋/세션 안에서 함께 고치거나(가능하면), 못 고치면 최소한 각각을 ERR/FP로 개별 등록해 추적 가능하게 만든다 — 주석에 "여기도 위험함"이라고 적는 것만으로는 예방이 아니다.

**관련:** ERR-098, FP-047

---

## FP-072 | 다계정 확장 중 "발행 직전 공용 Gate"처럼 계정 무관하게 실행되는 코드가, 새 계정의 콘텐츠 도메인을 고려하지 않고 기존 계정 전용 규칙을 계속 강제할 수 있다

**설명:** 단일 계정(yuna18253, 화장품 도매) 시절에 만들어진 발행 직전 텍스트 검수 로직이, 계정이 늘어난 뒤에도 "이 텍스트가 도매 키워드를 포함하는가"라는 원래 계정 전용 기준을 모든 계정에 그대로 적용했다. 새 계정(aijomoojin, AI 콘텐츠)의 캡션은 애초에 그 기준과 무관한 도메인이라, 규칙을 통과할 방법이 구조적으로 없었다.

**근본 원인:** 공용 Gate/Filter를 설계할 때 "지금 유일한 계정"을 암묵적 전제로 두면, 그 전제가 코드에 명시되지 않은 채(계정별 분기 없음) 굳어진다. 이후 다른 도메인의 계정이 추가돼도 Gate 자체는 계정을 구분하지 않으므로 잘못된 계정 감지 없이 그대로 작동(오류 없이 조용히 항상 차단 또는 항상 허용).

**증상:** 260731 — `passes_keyword_filter()`가 `launcher/main.py`의 발행 게이트에서 계정 인자 없이 전역 호출됨(ERR-099). 같은 클래스의 이전 사례: 260730 ERR-091 — DM 전역 fallback이 항상 yuna18253(최초 유일 계정)으로 고정되어, 다른 계정 해석 실패 시 그 계정 소유 경로로 잘못 시도될 위험.

**예방:** 신규 계정을 추가하는 모든 단계에서, 공용/전역으로 동작하는 기존 Gate·Filter·Fallback·Routing 로직을 `grep`으로 먼저 나열하고, 각각이 "특정 계정을 암묵적으로 전제하고 있지 않은가"를 명시적으로 검토한다. Identity(계정 식별)와 Domain(계정별 콘텐츠·정책) 책임을 분리해 설계하면, 새 계정 추가 시 Domain 매핑만 추가하고 공용 로직은 건드리지 않을 수 있다.

**관련:** ERR-099, ERR-091, FP-065

---

## FP-073 | 외부 산출물 생성 뒤 실행되는 로컬 운영정책 파일 Gate가 읽기 권한 하나로 실패하면, Queue 저장 전 부분상태가 남는다

**설명:** 캡션·이미지·외부 이미지 호스팅처럼 비용과 외부 상태를 만드는 단계가 먼저 끝난 뒤, Airtable 저장 경로에서 별도 운영정책 파일을 읽는 구조다. 이 파일 접근이 거부되면 게시 Queue만 생성되지 않아 "산출물은 존재하지만 제어 레코드는 없음" 상태가 된다.

**증상:** 260803 6F #1/3 — Gemini·이미지·Vault·ImgBB 성공 후 `runtime_boot_policy.json` PermissionError로 Airtable POST 전 종료(ERR-101).

**예방:** 라이브 Canary 전에 실제 실행 사용자로 모든 pre-write Gate를 read-only 검증하고, 외부 상태변경보다 뒤에 있는 로컬 권한 의존성을 명시한다. 실패 후에는 산출물·호스팅 URL·Record 존재 여부를 먼저 확인하고 원 실행을 반복하지 않는다.

**관련:** ERR-101, INC-046

**해소(260803):** 운영 ACL을 넓히지 않고 기존 SYSTEM Runtime을 유지했다. 공통 정책 읽기의 `OSError/PermissionError`를 typed fail-closed 오류로 변환하고, 수동 Canary의 P0/P1을 Gemini·Vault·ImgBB·Airtable보다 앞으로 이동했다. Commit `b98afa1` Push 및 Active Python 3.10 Mock 검증 완료.

**Closed Gate 재확인(260804):** 6F 3/3(전체) 완료까지 이 패턴 재발 0건.

---

## FP-074 | AI 안전성 검사 함수가 Provider 장애와 콘텐츠 거부를 같은 False/blocked 결과로 접으면, transient 장애가 영구 거부 상태가 된다

**설명:** Safety API의 정상 유해성 판정과 503/timeout/transport failure를 동일한 `SAFETY_CHECK_ERROR` 또는 boolean 실패로 반환하고, 상위 호출자가 모두 `AI_CONTENT_SAFETY_BLOCKED`로 저장하면 상태 의미가 손실된다.

**증상:** 260803 6F #1/3 — Gemini HTTP 503 high demand가 `AI_CONTENT_SAFETY_BLOCKED`로 기록되고 Airtable Record가 `rejected` 처리됨(ERR-102). 동일 콘텐츠는 승인된 재시도에서 Safety HTTP 200 후 정상 게시됐다.

**예방:** `unsafe_content`와 `safety_check_transient_error`를 별도 typed result/error code로 유지한다. transient error는 게시하지 않는 Fail-closed를 유지하되 영구 `rejected`와 구분하고, 자동/수동 재시도 정책과 시도 상한을 명시한다.

**관련:** ERR-102, INC-046

**해소(260803):** structured Safety 신호와 Provider/transport 오류를 typed status로 분리하고, transient 오류는 같은 실행 안에서 최초 포함 최대 4회로 제한했다. `UNSAFE→rejected`, `RETRY_EXHAUSTED/PERMANENT→failed`, 모든 차단·오류에서 claim/Meta 0회 계약을 Commit `09f03c0`으로 Production 적용했다. 6F #2/3에서 503×3 후 4번째 Safety 성공으로 재발 방지 계약을 Runtime 확인했다.

**Closed Gate 재확인(260804):** 6F #3/3 최초 시도의 Gemini 503 4/4 소진이 `RETRY_EXHAUSTED→failed`로 정확히 분류됐다(오분류 재발 0건) — 6F 전체 3/3 SUCCESS로 종결.

---

## FP-075 | 24시간 무단 운영을 전제한 Scheduler가 머신 Sleep 구간 동안 통째로 멈추고, misfire_grace_time을 넘긴 Cron 슬롯은 그날 안에 재실행되지 않는다

**설명:** APScheduler(및 그 안의 모든 Job)는 호스트 프로세스가 살아있는 동안만 동작한다 — Windows가 Sleep에 들어가면 프로세스 자체가 멈추고, Wake 후 다음 tick에서야 "몇 개 slot이 얼마나 늦었는지"를 한꺼번에 인식한다. `misfire_grace_time=60`초(260804, Catch-up 방지 설계)보다 길게 놓친 Cron Job은 그 날짜의 실행을 그냥 건너뛰고 다음 예정 시각(대개 익일)으로 재등록된다 — 이는 설계된 Fail-closed(무한 재시도 금지)가 정상 동작한 것이지 버그가 아니지만, "24시간 무단 동작"(CLAUDE.md §0.1)이라는 최상위 전제와 이 머신의 실제 전원 상태가 충돌하고 있다는 사실 자체를 드러낸다.

**증상:** 260805 08:50:55~09:07:04 Windows Sleep(Kernel-Power Event 506/507) 동안 `app.log`의 heartbeat·`_job_insta_upload`·`_job_fb_crawl`·DM followup·`_job_aijomoojin_content_producer` 등 **모든** 등록 Job이 동시에 끊겼다(ERR-103). 09:00 ICT aijomoojin Producer 슬롯만 골라서 실패한 것이 아니라, 그 시각에 도는 모든 Job이 동일하게 대상이었다 — 우연히 Producer가 가장 눈에 띄었을 뿐이다.

**예방:** (1) 이 머신의 전원설정(`powercfg`) Sleep/Idle timeout이 실제로 어떻게 설정돼 있는지 Read-only 확인 — 자동 Sleep이 켜져 있다면 그 자체가 "24시간 무단 동작" 전제의 근본 결함이다. (2) 향후 유사 Cron 슬롯(aijomoojin 3슬롯 등) 설계 시 misfire 발생을 Slack/Health로 관측 가능하게(현재는 로그에만 남고 별도 Alert 없음, 확인 필요) 만드는 것을 검토— 지금은 로그를 직접 찾아야만 미실행 여부를 알 수 있다.

**관련:** ERR-103, INC-047

---

## FP-076 | "안전 필드 추출 결과가 전부 None"을 곧바로 "추출 코드 결함"으로 해석하면 안 된다 — Provider가 애초에 그 필드를 안 줬을 수 있다

**설명:** 예외/응답에서 특정 필드(예: quota 상세)를 안전하게(getattr/dict.get, 예외 없이) 추출하는 코드를 작성할 때, 실제 Runtime에서 결과가 전부 `None`으로 나오면 두 가지 서로 다른 원인이 있을 수 있다 — (1) 추출 로직 자체의 버그, (2) Provider가 이번 응답에 그 필드를 애초에 포함하지 않음. 이 둘을 구분하지 않고 (1)로 단정하면, 존재하지도 않는 버그를 찾아 헤매거나 반대로 실제 Provider 제약을 "우리 코드 문제"로 오판해 근본원인 조사가 엉뚱한 곳으로 샌다.

**증상:** 260805 ERR-104 — `_extract_gemini_quota_fields()`를 합성 테스트(quota 구조 있는 값 3종 + 없는 경우 + APIError 아닌 경우) 4개로 먼저 검증해 로직 자체가 정상임을 증명한 뒤 실제 Gemini 호출을 했더니, `status_code`만 채워지고 `quota_id`/`quota_metric`/`limit`/`retry_delay`는 전부 `None`이었다. 합성 테스트가 먼저 있었기 때문에 "추출 로직은 정상, 실제 Provider 응답에 그 구조가 없다"로 명확히 구분할 수 있었다 — 합성 테스트가 없었다면 코드를 의심하며 재작업했을 상황이다.

**예방:** Provider 응답에서 특정 구조를 추출하는 코드를 추가할 때는, 실제 호출 전에 반드시 "필드가 존재하는 합성 케이스"와 "필드가 없는 합성 케이스"를 둘 다 단위 테스트로 고정해둔다. 그러면 실제 Runtime에서 전부 None이 나와도 "코드는 이미 두 케이스 다 검증됨 → 이번엔 Provider가 안 준 것"이라고 근거를 갖고 판정할 수 있다.

---

## FP-077 | 파이프라인 수정은 그 시점 이후 수집분에만 적용되고, 그 이전에 이미 저장된 데이터는 FIFO 큐 맨 앞에서 영구히 사람의 판단을 막을 수 있다

**설명:** 데이터 파이프라인의 결함(예: 외부 CDN URL을 재호스팅 없이 그대로 저장)을 코드로 고쳐도, 그 수정은 이후 신규로 들어오는 데이터에만 적용된다. 이미 저장된 구(舊) 데이터는 그대로 남아있고, 그 큐가 "오래된 순"으로 소비되는 구조라면 문제 있는 옛 데이터가 항상 맨 앞을 차지해 이후 정상 데이터의 소비 자체를 막을 수 있다.

**증상:** 260806 — `save_to_training_queue()`의 imgbb 재호스팅 수정(260805, 커밋 `cba1cc2`)은 이미 정상 배포돼 있었으나, 그 이전(260730)에 수집된 55건이 Facebook CDN 서명 만료로 전부 이미지 소실 상태로 남아 리뷰 그리드(`fetch_pending_candidates`, `collected_at` 오름차순) 맨 앞을 계속 차지 — 사람이 판단할 수 없는 항목이 큐를 막아 신규 정상 데이터의 리뷰 진행을 사실상 정지시켰다.

**예방:** (1) 외부 리소스(hotlink URL 등)의 유효기간이 있는 필드를 다루는 파이프라인을 수정할 때는, 코드 수정과 별개로 "그 수정 이전에 이미 저장된 데이터"의 backfill 필요 여부를 항상 점검한다. (2) FIFO(오래된 순) 소비 큐는 "판단 불가 상태"(예: 이미지 소실)를 자동 감지해 별도 격리하거나 건너뛸 수 있는 안전장치를 두는 것을 검토한다 — 그렇지 않으면 하나의 죽은 항목이 전체 큐를 조용히 막을 수 있다.

**관련:** ERR-106, INC-048, FP-055(같은 계열 — 외부 리소스 삭제·만료 상태와 로컬 저장 상태가 동기화되지 않는 문제)

**관련:** ERR-104

## FP-078 | 발행성 API 호출을 "생성 성공 직후 상태 확인 없이" 바로 이어 부르면, 대상이 아직 처리 중일 때 애매한 실패가 발생할 수 있다

**설명:** 비동기로 처리되는 리소스(예: Meta Graph API의 미디어 컨테이너)를 생성한 뒤, 그 리소스가 완전히 처리 완료됐는지 확인하지 않고 곧바로 그 리소스를 사용하는 다음 단계(발행 등)를 호출하면, 리소스가 아직 처리 중일 때 그 호출이 거부될 수 있다. 이런 거부는 "명확한 영구 실패"가 아니라 "타이밍 문제"인 경우가 있어, 응답 코드만 보고 실패로 단정하면 실제로는 성공 가능했던 시도를 놓치게 된다.

**증상:** 260808 — `publish_single()`이 컨테이너 생성(`/media`) 성공 직후 상태 확인 없이 발행(`/media_publish`)을 호출, 하루 동안 2건(16:00 정규 슬롯, 18:04 수동 테스트)이 HTTP 400 결과불명으로 종료. 두 건 모두 이후 Read-only 조회에서 컨테이너가 `FINISHED` 상태로 확인됐고, 그중 1건은 재시도로 즉시 성공 — "생성 직후 발행 시도"와 "처리 미완료 상태에서의 거부" 간 상관관계를 시사.

**예방:** (1) 비동기 처리 리소스를 만든 뒤 그 리소스를 사용하는 다음 API 호출 전에는, 가능하면 "처리 완료" 상태를 확인(폴링 또는 대기)하는 절차를 넣는 것을 검토한다. (2) 그런 폴링이 없는 상태에서 발행류 API가 400/5xx로 실패하면, 코드 결함을 의심하기 전에 "생성 직후라 아직 처리 중이었을 가능성"부터 Read-only로 확인한다(대상 리소스의 상태 조회 API가 있다면 그것부터). (3) 이런 API의 실패 응답은 상태코드만이 아니라 본문(에러 상세)도 함께 로그에 남겨야 다음번엔 추정 없이 바로 원인을 알 수 있다. (4, 260810 추가) 폴링을 고정 횟수×고정 timeout으로 설계하면 개별 호출이 느릴 때 전체 대기가 곱연산으로 폭증해 다른 작업(스케줄러 등)을 막을 수 있다 — `time.monotonic()` 기반 전체 deadline을 두고, 개별 호출의 timeout도 그 남은 예산 이내로 제한해야 한다(Codex 리뷰로 발견, ERR-107 260810 후속 참조).

**예방 적용 완료(260810):** ERR-107 — `publish_single()`에 Phase A/B 사이 `status_code=FINISHED` 대기(30초 deadline 폴링) 추가, Codex 리뷰로 위 (4)까지 반영. Target Test 통과, Commit(`98e7a6c`/`38ac9fc`) Push 완료. 같은 날 신규 컨테이너 기준 end-to-end 실게시(`ig_media_id=18102250937459027`)로 production_verified 확인 완료.

**관련:** ERR-107, INC-049, 260801 6D 선례(같은 계열 — "HTTP 400=확정 거부"라는 가정이 두 번째로 틀렸음이 재확인됨)

## FP-079 | 비동기 리소스의 상태조회 API가 "처리완료"를 반환해도, 오래 방치된 리소스는 실제 사용(발행 등) 시점에 이미 무효화됐을 수 있다

**설명:** FP-078은 "생성 직후 상태확인 없이 바로 사용"하는 문제였다. 이번은 그 반대 극단 — 생성 후 오랜 시간(수십 시간)이 지난 뒤 상태조회를 하면 API가 여전히 "처리완료"(예: `status_code=FINISHED`)라고 응답하지만, 그 응답이 "지금 실제로 사용 가능하다"를 보장하지 않을 수 있다. 상태조회 API와 실제 사용 API가 서로 다른 내부 유효기간/캐시 정책을 가질 수 있기 때문으로 추정된다(공식 확정 아님).

**증상:** 260810 — Meta 미디어 컨테이너(`creation_id=17945860479257522`, 생성 후 약 42시간 경과)를 GET `status_code`로 조회하면 `FINISHED`(HTTP 200)를 반환했으나, 곧이어 `media_publish`를 호출하면 `code=24, error_subcode=2207006 "media file not found"`로 거부됨. 상세는 ERR-108 참조.

**예방:** (1) 비동기 리소스를 "생성 직후"가 아니라 "한참 지난 뒤" 재사용하려 할 때는, 상태조회가 성공(FINISHED 등)해도 실제 사용 API가 별도로 실패할 수 있음을 전제하고, 실패 시 재시도보다 새로 생성하는 경로를 우선 검토한다(단, 이미 1회 발행 시도가 있었던 리소스는 중복 위험 때문에 함부로 재생성하지 않는다 — 회장 승인 등 안전장치 하에 진행). (2) 리소스의 "생성 후 경과 시간"을 재사용 판단의 한 요소로 명시적으로 고려한다(공식 만료 문서가 있다면 그 기준을, 없다면 관측된 사례를 근거로 보수적 임계값을 잠정 채택).

**관련:** ERR-108, ERR-107, FP-078

---

## FP-080 | "코드를 커밋했다"와 "실행 중인 프로세스가 그 코드를 실제로 실행하고 있다"는 서로 다른 사실이다 — 재시작 전까지 실 프로세스는 구코드를 계속 실행한다

**설명:** Python(및 대부분의 인터프리터 언어)은 이미 `import`돼 실행 중인 모듈의 최상위 코드를 프로세스 메모리에 캐시한다. 파일을 수정하고 `git commit`까지 완료해도, 이미 떠 있는 프로세스는 재시작되기 전까지 그 변경을 전혀 인식하지 못한다. "코드 수정 완료" 보고와 "Runtime에 실제 반영됨" 보고를 같은 것으로 취급하면, 이미 해결됐다고 믿는 버그가 실제 운영에서는 여전히 살아있는 상태로 계속 재발할 수 있다.

**증상:** 260810 — ERR-107(Phase A.5 상태확인 누락) 수정 코드가 그날 커밋됐고, 별도 스크립트로 실행해 "production_verified"로 보고됐다. 그러나 실제 Live 스케줄러 프로세스(`launcher/main.py`)는 그날 05:56:43부터 20:02:54까지 재시작되지 않아, 하루 종일 수정 전 구코드로 계속 동작 — 17:00:33에 동일한 HTTP 400 OUTCOME_UNKNOWN이 4번째로 재현됨. 상세는 ERR-109 참조.

**예방:** (1) "코드 수정 완료"와 "Runtime 반영 확인"을 분리된 별도 사실로 취급하고, 실제 반영 검증은 반드시 대상 Live 프로세스 자체의 재시작 여부(기동 시각, PID 변경)를 확인한 뒤에 한다 — 별도 스크립트/단독 실행 검증을 Live 프로세스 검증으로 치환하지 않는다(CLAUDE.md 12.3 "기존 증거 재사용" 원칙과 직결). (2) 프로세스가 기동 당시의 커밋과 현재 코드베이스 HEAD가 다른("stale") 상태를 스스로 관측할 수 있게 만든다(ERR-109 `health_monitor.get_code_freshness_status()` 참조) — 단, 이 관측은 최상위 코드에만 적용되고 지연 import되는 하위 모듈까지는 커버하지 않는 명시적 한계가 있다.

**관련:** ERR-109, ERR-107

---

## FP-081 | AI 이미지 생성 모델에게 준 "글자 넣지 마" 지시는 신뢰할 수 없다 — 텍스트가 실제로 그려질 자리 전체를 구조적으로 가려야 한다

**설명:** Diffusion 기반 이미지 생성 모델(FLUX.1-schnell 등)은 프롬프트로 "텍스트 없이"라고 지시해도, 학습 데이터의 강한 사전편향(문서·화면·배너·간판류 이미지는 대개 텍스트를 포함) 때문에 그 지시를 확률적으로 어긴다. `negative_prompt` 파라미터를 지원하지 않는 Provider(Cloudflare Workers AI/FLUX.1-schnell, 260731 확인)에서는 이 위험이 더 크다. 프롬프트 문구를 아무리 다듬어도 "발생 확률을 낮출 뿐" 완전히 없애지는 못한다 — 실제 텍스트가 반드시 정확해야 하는 용도(예: 정보형 카드 이미지)에서는 프롬프트만으로 방어하면 안 되고, 최종 합성 단계에서 텍스트가 그려지는 영역 자체를 구조적으로 가리는 별도 레이어가 필요하다.

**증상:** 260811 — `render_hero_card()`(AI배경+Pillow텍스트 하이브리드)에서 헤드라인 전용 오버레이만 있을 때는 블록 영역에서, 오버레이를 왼쪽 컬럼 전체로 넓힌 뒤에도(프롬프트 강화 전) 상단·하단 여백에서 유령글자가 계속 재현됨 — 어디에 텍스트가 나타날지 예측할 수 없었다. 상세는 ERR-110 참조.

**예방:** (1) AI가 생성한 이미지 위에 실제 텍스트를 별도로 그려 넣는 설계(AI배경+Pillow텍스트 하이브리드 등)에서는, 프롬프트 레벨 방어(no-text 지시, 문서/화면/패널 연상 표현 회피)를 1차 완화책으로만 쓰고, 실제 텍스트가 그려지는 영역 전체를 충분히 불투명한 레이어로 덮는 것을 최종 방어선으로 설계한다 — 특정 요소(예: 헤드라인)만 부분적으로 가리면 다른 요소(블록·태그라인 등) 영역에서 동일 문제가 재현될 수 있다. (2) "이번엔 안 나왔다"를 근거로 완전히 해결됐다고 선언하지 않는다 — 확률적 문제이므로 최소 2회 이상 서로 다른 입력으로 재검증한다(ERR-110에서 2개 topic으로 검증한 방식).

**관련:** ERR-110
