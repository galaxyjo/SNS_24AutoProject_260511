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

**해결:** 공용 시작프로그램 `AdsPower.lnk`의 대상을 실제 `AdsPower Global.exe`로 수정하고 `TargetExists=True`를 재확인했다. 50325 LISTENING 복구 후 다음 예약 FB 크롤링에서 4개 그룹 연결 성공·총 1건 처리로 E2E PASS. 다음 실제 로그인/재부팅 자동실행은 아직 미검증(PENDING).

**예방:** 사용자 세션이 필요한 GUI 의존성은 LocalSystem 서비스에서 직접 띄우는 방식으로 섣불리 해결하지 않는다. 로그인 세션 자동 시작, 별도 태스크, 또는 명시적 운영 절차 중 하나를 결정하고, 크롤러는 fan-out 전에 50325를 한 번 검사해 공통 선행조건 실패로 보고해야 한다.

**관련:** ERR-073, INC-040, ERR-058

## FP-055 | 삭제·권한소실된 외부 리소스 ID를 로컬 제어판에 계속 보관하면 예약 작업마다 같은 API 오류가 반복된다

**발생일:** 260611 최초(ERR-039/INC-021), 260721 6개 ID로 재발.

**증상:** Airtable에 `posted + ig_media_id 있음`으로 남은 Instagram media ID가 Graph API에서는 `code=100 / subcode=33`으로 더 이상 접근되지 않아 Engagement 수집 때마다 경고가 반복됐다. 계정·토큰은 정상이어도 일부 오래된 ID만 무효가 될 수 있다.

**근본원인:** 외부 리소스의 삭제·권한소실 상태와 Airtable의 `ig_media_id` 상태가 자동 동기화되지 않는다. 조회 실패를 기록만 하고 무효 ID를 조회 대상에서 격리하지 않아 같은 실패가 다음 주기에도 재현된다.

**해결:** 전체 291개를 배치 검증해 접근 불가 6개를 특정하고, 승인 후 레코드·현재 ID·`posted` 상태가 모두 일치할 때만 `ig_media_id`를 공란 처리했다. 처리 후 6/6 `null`, 신규 게시물 4개를 포함한 현재 대상 289/289가 Graph API 접근 가능함을 재검증했다.

**예방:** Engagement 수집기가 연속 `100/33`을 받은 ID를 별도 상태로 격리하거나 승인 가능한 정리 목록으로 올리게 한다. 계정/토큰 전체 이상과 개별 media 소실을 구분하기 위해 계정 조회와 최근 media 조회를 먼저 통과시킨 뒤 개별 ID를 판정한다.

**관련:** ERR-039, INC-021
