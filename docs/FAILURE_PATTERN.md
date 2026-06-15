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
