# INCIDENT_TIMELINE.md
> Generated: 2026-05-16 | Status: ACTIVE | Version: v1.1
> Scope: SNS_24AutoProject

---

## PURPOSE
프로젝트 전체 운영 중 발생한 주요 Incident 기록.
목적: 원인 추적 / 구조 Drift 추적 / 재발 방지

---

## INC-001 | Disk Loss / Environment Migration
**발생:** 2025-05
**요약:** 기존 개발 노트북 환경 손실. 신규 환경 복구 시작.
**영향:** 환경 초기화 / Runtime mismatch / package drift
**해결:** 신규 환경 구축 / PowerShell 기준 통합 / Python 3.10.11 고정
**재발 방지:** 환경 snapshot 정책 도입

---

## INC-002 | Duplicate Module Drift
**발생:** 2025-07
**요약:** 실행되는 account_runner.py와 수정한 파일이 서로 달랐음
**영향:** 수정이 반영 안 됨 / 디버깅 시간 낭비
**해결:** sys.path.insert 적용 / __pycache__ 제거 / absolute path 고정
**재발 방지:** FP-010 등록 / Source of Truth 1개 원칙

---

## INC-003 | Coverage Illusion
**발생:** 2025-08
**요약:** Coverage PASS인데 실제 Runtime 불안정
**영향:** 테스트 신뢰도 하락
**해결:** Runtime-first 기준 적용 / 실제 flow 검증 강화
**재발 방지:** FP-003 Ghost Success 등록

---

## INC-004 | Instagram Runtime Instability
**발생:** 2025-10
**요약:** Instagram Upload 단계 반복 실패
**근본 원인:** UI State mismatch / Selenium attach instability / popup state mismatch
**해결:** UI state validation 도입 / sequential load 적용 / nav existence check 추가
**재발 방지:** FP-008 UI State Assumption 등록

---

## INC-005 | sys.path 오염 누적
**발생:** 2025-11
**요약:** sys.path.insert 임시패치 누적으로 import 경로 불확정
**영향:** 어느 파일이 실행되는지 모르는 상태
**해결:** absolute path 전환 / sys.path 패치 제거
**재발 방지:** FP-006 등록 / ARCHITECTURE_LOCK sys.path 금지 추가

---

## INC-006 | DB Schema Mismatch
**발생:** 2025-12
**요약:** post_id 컬럼 없음 오류 / OperationalError 반복
**근본 원인:** schema 변경 후 migration 미적용
**해결:** ALTER TABLE / init_db sync
**재발 방지:** FP-009 등록 / schema_governance.md 작성

---

## INC-007 | Multi-Repo Structure Confusion
**발생:** 2026-05-11 ~ 2026-05-16
**요약:** 250723 / 260511 두 저장소 역할 미확정으로 동시 수정 발생
**영향:** Drift 폭발 위험 / import 혼재
**해결:** ARCHITECTURE_LOCK.md 선언 / 260511 = SOURCE OF TRUTH 확정
**재발 방지:** merge_policy.md / MASTERTREE_CONTRACT.md 작성

---

## INC-008 | Documentation Hallucination
**발생:** 2026-05-16
**요약:** 완료 선언된 문서 7개가 실제 filesystem에 존재하지 않음 발견
**영향:** 운영 혼선 / Phase 1 완료 조건 미충족
**근본 원인:** AI 텍스트 출력 = 실제 파일 생성으로 오인
**해결:** Evidence-based verification 의무화 / 실제 파일 생성 후 Get-ChildItem 확인
**재발 방지:** FP-001 / FP-005 / FP-013 등록 / 완료 선언 기준 고정

---

## INC-009 | Launcher 2일 중단
**발생:** 2026-05-15 ~ 2026-05-17
**요약:** `main.py` 미실행으로 크롤링/업로드 전면 중단. `crawl_stats.db` 마지막 기록 2026-05-15 15:24 확인으로 발견.
**영향:** FB 크롤링 / Instagram 업로드 / KPI 수집 / engagement 업데이트 전면 중단
**해결:** launcher 재기동 (`python launcher/main.py`) 후 크롤→Airtable 저장 확인
**재발 방지:** watchdog.ps1 상시 실행 / FP-014 등록

---

## INC-010 | Aspect Ratio E2E 업로드 첫 성공
**발생:** 2026-05-17
**요약:** ERR-013(Instagram 이미지 비율 오류) 해결 후 단일 계정 E2E 업로드 최초 성공 확인.
**원인:** Facebook 크롤 이미지 비율이 Instagram 허용 범위(4:5~1.91:1) 미충족
**해결:** Pillow center-crop 전처리 + imgbb 영구 URL 업로드 방식 적용 / `failed` 레코드 → `ready` 재시도 후 `posted` 전환 확인
**결과:** `ig_media_id=18116524126780958` 생성 / Single Account E2E PASS
**재발 방지:** PHASE2_CHECKLIST.md duplicate upload / retry consistency 항목 등록

---

## INC-011 | Watchdog :5000 중복 바인딩 + Dual Scheduler 해소
**발생:** 2026-05-27
**요약:** watchdog.ps1 재기동 시 Flask(:5000) 이중 바인딩 + `process_due_followups` 매 5분 2회 실행 발생. watchdog.ps1 `Start-Flask` 주석 처리로 해소.
**원인:** watchdog이 `dm_receiver`(Flask)를 독립 기동 + `launcher\main.py`도 기동 → launcher 내부에서도 `app.run(:5000)` 실행 → 이중 바인딩. dm_receiver 독립 APScheduler와 launcher APScheduler가 동시 실행 → 잡 중복.
**해결:** `watchdog.ps1` `Start-Flask` 함수(line 97~103) + Flask 감시 블록(line 140~156) 주석 처리. launcher\main.py에 Flask 관리 위임.
**결과:** :5000 단일 LISTEN 확인 / `process_due_followups` 1회/5분 2사이클 연속 확인
**재발 방지:** FP-017 등록 — watchdog 감시 대상 설계 시 진입점 내부 포함 여부 사전 확인 의무화

---

## INC-012 | 실거래 DM AutoReply 성공 + 중복 발송 버그 수정
**발생:** 2026-05-28
**요약:** 실계정(IGSID 1792783944739953) DM 수신 → AutoReply 발송 성공 확인 (20:14 KST). 동시에 동일 IGSID에 중복 발송(20:14, 21:29, 21:30) 문제 발견 → _has_recent_auto_replied() 추가로 해소.
**영향:** 실제 사용자에게 동일 DM 복수 발송 가능 — 운영 신뢰도 저하
**근본 원인:**
1. `_has_recent_auto_replied()` 미구현 → 동일 IGSID 중복 차단 없음
2. `IS_AFTER({replied_at}, ...)` 사용했으나 `replied_at` 필드 미존재 → 항상 빈 결과 → 가드 무력화
3. _rule.reason AttributeError — falsy _rule 객체에서 .reason 직접 접근
**해결:**
- `_has_recent_auto_replied()`: `CREATED_TIME()` 기준 3분 window, `bridge_status='auto_replied'` 조건
- `getattr(_rule, "reason", "unknown")` fallback 적용
**결과:** 21:42:15 / 21:50:03 duplicate skip 로그 확인 — 중복 차단 정상 동작
**재발 방지:** FP-020 / FP-021 등록 — Airtable 미존재 필드 의존 금지 / 호출부 명시값 확인 의무화

---

## INC-013 | FB Crawler Skip (accounts.json 빈 배열)
**발생:** 2026-05-29
**요약:** `accounts.json`이 빈 배열(`[]`)로 설정되어 crawl_urls 루프가 실행되지 않음. FB 크롤링 전면 skip.
**영향:** FB 콘텐츠 수집 중단
**해결:** `account1` + `crawl_url` 등록 (`7ce335e` 커밋)
**결과:** 19:43 / 20:13 `계정 완료 | account=account1 | 3개` 2회 연속 확인
**재발 방지:** accounts.json 최초 배포 시 빈 배열 여부 확인 의무화

---

## INC-014 | Airtable caption 422 UNKNOWN_FIELD_NAME
**발생:** 2026-05-29
**요약:** FB 크롤러가 Airtable `Source_Feeds` 테이블에 `caption` 필드 저장 시도 → 422 UNKNOWN_FIELD_NAME 오류 반복 발생.
**영향:** 크롤링 데이터 Airtable 저장 실패
**해결:** Airtable UI에서 `Source_Feeds` 테이블에 `caption` Long text 필드 직접 추가
**결과:** 422 오류 해소 / 크롤 데이터 정상 저장 확인
**재발 방지:** 신규 필드 사용 전 Airtable 스키마 선행 확인 의무화

---

## INC-015 | Watchdog 루프 중단 → Launcher 재시작으로 복구
**발생:** 2026-05-29
**요약:** watchdog 감시 루프가 중단되어 launcher 프로세스 감시 비활성화. Flask(:5000) / ngrok(:4040) DOWN 상태 지속.
**영향:** launcher 자동 재시작 불가 / 서비스 중단
**해결:** launcher 수동 재시작으로 복구
**결과:** 서비스 정상 복구
**재발 방지:** SNS_Watchdog_AutoStart 작업 스케줄러 등록 완료(260529) — 부팅 시 자동 시작

---

## INC-016 | Clone Mode 실패 → 진단 → Runtime Proof 성공
**발생:** 2026-06-01 ~ 2026-06-02
**요약:** Clone Mode 파이프라인 6단계 commit 후 Runtime Proof 0건 → 원인 진단 → 필터/더보기 보정 → 1건 확보
**타임라인:**
- 260601 Phase 1~3 commit 완료 (c8000ee, 3ed3b45, b059740)
- max_posts=3 단발 실행 → 0건 처리 (원인: 베트남어 피드 / 더보기 미클릭)
- 진단 1: `_diag_post_text.py` → POST 1 text_len 63, #SNUGGLE 감지
- 진단 2: `detect_and_translate()` 정상 동작 확인, `passes: True`
- 진단 3: `_diag_seemore.py` → 더보기 클릭 시 110→581자 확장 / 베트남어 확인
- Phase 4: keyword filter 확장 (25c3f13)
- Phase 5: comment auto-reply 안전장치 (a64b0ff)
- Phase 6: `expand_see_more()` 추가 (deec24c)
- 새 그룹 URL `1676627532598134` 로 max_posts=10 실행 → K-BEAUTY 키워드 매칭 → 저장 1건
- Airtable recsmA4WIlrur1wHO: original_text / converted_text / caption / media_type=image ✅
**영향:** Clone Mode Runtime Proof 6일 지연 (260529→260602)
**해결:** expand_see_more() + 그룹 URL 다중화로 해소
**재발 방지:** FP-020 (Runtime Proof 없는 commit 금지) / FP-021 (더보기 필수) 등록

---

## INC-017 | PowerShell BOM 삽입 → accounts.json 파싱 실패 → 크롤러 설정 미로드
**발생:** 2026-06-02
**요약:** `Set-Content -Encoding UTF8`로 `accounts.json` 저장 시 BOM 삽입 → `account_manager`가 JSON 파싱 실패 → 계정 설정 없음 → crawl_urls 미로드
**영향:** 세션 내 one-shot 크롤러 실행 시 accounts.json 미로드 (launcher 미기동 상태라 운영 크롤링 영향 없음)
**해결:** `[System.IO.File]::WriteAllText` + `UTF8Encoding(false)` 로 BOM-free 재저장 (c6a30d1)
**결과:** `accounts.json 로드 | 1개 계정` 정상 확인
**재발 방지:** FP-025 / ERR-035 등록 — JSON 설정 파일 Set-Content UTF8 금지 룰 확정

---

## INC-018 | 시스템 환경변수 플레이스홀더 + caption 오염 → Instagram 업로드 사전 차단
**발생:** 2026-06-02
**요약:** Instagram 업로드 테스트 준비 중 2개 독립 버그 발견 및 해소
**타임라인:**
- AIRTABLE_API_KEY User 환경변수에 `pat여기에전체토큰`(한국어 플레이스홀더, 10자) 잔존 확인
- `load_dotenv()` find_dotenv() 탐색 실패(temp 경로 실행) + 시스템 변수 우선 적용 → latin-1 UnicodeEncodeError
- 시스템 환경변수 User scope 삭제 + 세션 제거로 해소
- Airtable ready 레코드 caption 필드에 `우다현\n43분\n·` 형태 Facebook UI 잔여물 포함 확인 (ERR-037)
- `clean_fb_metadata()` 추가 + `generate_caption_clone()` 선처리 연결 (349fedf)
- 기존 dirty 레코드 2건 Airtable 직접 정정 완료
- Instagram 업로드 테스트 실행: recFyw7OUaZ666JDJ → ig_media_id=18101360630320704 → posted ✅
**영향:** 잠재적 latin-1 에러로 Airtable 연동 전체 차단 / 오염 caption 업로드 사전 방지
**해결:** 환경변수 정리 + ERR-037 코드 수정 + Airtable 레코드 정정
**재발 방지:** load_dotenv 절대경로 필수 / 시스템 환경변수 플레이스홀더 설정 금지 / clone 경로 원문 전처리 의무화

---

## LESSONS LEARNED
```
1. 텍스트는 증거가 아니다
2. Runtime만 신뢰
3. Git 없는 완료는 완료 아님
4. Evidence 없는 PASS 금지
5. AI 출력 = 실제 실행 아님
```
## INC-019 (2026-06-03)
- 시각: 11:34 부팅 후 watchdog 실행 실패
- 원인: ExecutionPolicy Restricted (0xC000013A)
- 조치: RemoteSigned 적용 → watchdog 수동기동 → Flask 복구 (15:29)
- 커밋: 2695d87

---

## INC-020 | Instagram_Posts caption 필드 재소멸 → 422 오류 반복 (2026-06-11~12)
**발생:** 2026-06-11 22:27 최초 확인, 22:57 / 23:27 반복
**요약:** FB 크롤러 `save_to_airtable()`이 `Instagram_Posts.caption` 저장 시도 → 422 UNKNOWN_FIELD_NAME 반복. 260529에 UI로 추가한 필드가 사라진 상태.
**영향:** `1827528710833477` 그룹 크롤 데이터 Airtable 저장 실패 반복. upload_rate 6.2% 저하 원인.
**근본 원인:** Airtable UI 수동 추가 필드는 추적 불가 — 언제 삭제됐는지 불명. ERR-028 재발.
**해결:** Airtable Metadata API로 프로그래매틱 추가 (`multilineText`, field_id: fldcxTzLzYCzD9aYe)
**결과:** 다음 크롤링부터 422 오류 없이 정상 저장 예상
**재발 방지:** FP-028 등록 — Airtable 필드는 API로 추가 + MASTERTREE_CONTRACT 데이터 계약 즉시 갱신

---

## INC-022 | post_status 옵션 소실 → retry_count 422 cascade → uploading 28건 고착 (2026-06-16)
**발생:** 2026-06-15 21:33 ~ 2026-06-16 02:07 (약 5시간)
**요약:** `Instagram_Posts.post_status` Single Select 필드의 `ready`/`uploading` 옵션이 소실된 상태에서 launcher 재기동. 크롤러가 `ready` 저장 시 422 발생해 데이터가 uploading 상태에 고착. 설상가상으로 업로드 실패 경로가 `retry_count` 필드(미존재)에 write를 시도해 또다른 422 발생 → uploading 상태에서 벗어나지 못하고 5분마다 루프.
**영향:** 약 28건 uploading 고착 / 업로드 0건 / upload_rate 5.1%까지 하락
**근본 원인 1:** post_status 옵션 소실 (260612 caption 재추가 작업 시 연관 변경 추정) → ERR-040
**근본 원인 2:** launcher/main.py 실패 경로에 `retry_count`/`last_error_msg` 미존재 필드 참조 → ERR-041
**근본 원인 3:** FB CDN 동일 이미지 다중 URL → URL 기반 해시로 중복 28건 저장 → ERR-042
**해결:**
1. Airtable typecast 더미 레코드 방식으로 `ready`/`uploading` 옵션 강제 복구
2. 28건 일괄 `post_status=failed` PATCH
3. launcher/main.py 성공/실패 경로에서 `retry_count`/`last_error_msg` 참조 제거 (463c350)
4. image_url_hash FB 미디어 ID 추출 방식으로 변경 (25c6779)
**결과:** 02:07 KST 업로드 성공 (post_id=18122871268709171) / upload_rate 5.7% 반등
**재발 방지:** ERR-040~043 등록 / FP-029 등록

---

## INC-021 | engagement_tracker ig_media_id 17863634121631171 반복 오류 (2026-06-11)
**발생:** 2026-06-11 00:03 ~ 23:25 (30분 간격 반복, 약 20회 이상)
**요약:** `engagement_tracker.py`가 `Instagram_Posts`에서 `post_status=posted, ig_media_id!=''` 조건으로 조회 → `rectwruMD3uua54sv` 레코드의 `ig_media_id=17863634121631171` Graph API 조회 → `Object does not exist or missing permissions` 반복 Warning.
**영향:** 로그 노이즈 / engagement_tracker 30분 간격 오류 누적
**근본 원인:** 존재하지 않거나 권한 없는 media_id가 Airtable에 남아 있음
**해결:** `rectwruMD3uua54sv` ig_media_id 필드 공백으로 PATCH → engagement_tracker 조회 대상에서 제외
**결과:** 다음 30분 간격 실행부터 해당 레코드 제외 → 오류 없음
**재발 방지:** ERR-039 등록 — 업로드 실패 레코드의 ig_media_id는 즉시 클리어

**260721 재발·해결:** 전체 Engagement 대상 291개를 검사해 Graph API 접근 불가 6개를 확정했다. 승인 후 해당 6개 Airtable 레코드의 `ig_media_id`만 조건부 공란 처리하고 6/6 `null`을 재확인했다. 조사 중 신규 게시물 4개가 추가되어 최종 대상은 289개가 되었으며, 289/289 전부 접근 가능했다. 고객 응대·게시물 업로드 영향은 없고 지표 수집 경고만 발생했다.


---
## [260617] Instagram 업로드 실패 148건 -> 정합성 복구

| 시간 | 이벤트 |
|------|--------|
| 260616 1440 | Dashboard 미작동 발견 |
| 260616 1500 | 전체 서비스 재기동 완료 |
| 260616 1530 | 업로드 성공률 6.2% 확인 |
| 260616 1600 | FB CDN URL 원인 확정 (error_subcode 2207052) |
| 260616 1700 | imgbb API 키 확보, Phase1 완료 |
| 260616 1730 | Backfill 1건 E2E 실증 성공 |
| 260616 1800 | ig_media_id 오염 78건 발견 |
| 260616 1900 | VERIFIED 3건 복구 / INVALID 75건 클리어 |
| 260616 2000 | launcher/main.py 버그 수정 commit |
| 260617 1200 | Phase4: facebook_crawler.py imgbb 연동 commit |
---

## INC-022 | 워터마크 브랜드(COSLIFE·Lily) 이미지 오업로드 위험 — OCR 필터 무력화 (2026-06-29)
**발생:** 2026-06-29 (scheduler_err.log L33394 기준 최초 확인: 2026-06-28 05:29)
**요약:** pytesseract 미설치로 passes_image_filter() OCR 필터가 실질적으로 무력화. _IMAGE_BLOCK_KEYWORDS에 coslife 패턴이 등록돼 있었으나 한 번도 실행되지 않음. COSLIFE·Lily 워터마크 이미지가 이미지 필터를 통과하는 구조적 위험 상태.
**영향:** 잠재적 타사 브랜드 워터마크 이미지 Instagram 업로드 위험. 실제 업로드 여부는 미확인 (keyword 필터에서 대부분 차단된 것으로 추정).
**근본 원인:** ImageFilter OCR fail-open 설계 + pytesseract 미설치 방치 (FP-032).
**조치:**
- CAPTION_BLOCKLIST = ["coslife", "lily"] 추가 (content_filter.py)
- passes_keyword_filter() 선두에서 번역 캡션 텍스트 기준 선행 차단 (d79a3b3)
- clean_fb_metadata() UI 잔여물 패턴 확장 (_ui_pat 추가, 998215e)
- generate_caption_clone → generate_caption 교체 (Gemini 재생성, 998215e)
**해결:** 2026-06-29 커밋 후 watchdog 재기동 완료. 48시간 모니터링 중 (종료: 2026-07-01 21:34).
**재발 방지:** FP-032 등록 / ERR-044 등록 / pytesseract 설치 검토 필요.

---

## INC-023 | Windows 재부팅 → watchdog 미재기동 → 전체 파이프라인 최대 13시간 중단 (2026-07-01)
**발생:** 2026-07-01 10:02 (Windows 재부팅) ~ 23:35 (수동 복구)
**요약:** Kernel-Power 이벤트(10:02:48, Reason: Kernel API)로 시스템 자체 재부팅. watchdog.ps1 부팅 후 미재기동으로 launcher/main.py(Flask+APScheduler+RetryQueue), Streamlit, ngrok 전체 감시 주체 없이 방치. 재부팅 직후 Modern Standby 반복(11:36~12:59). FB 크롤러 12:47경 일시 재개 흔적 있으나 17:57 이후 재중단, 23:32 확인 시점 python/streamlit/ngrok/watchdog 프로세스 전무.
**영향:** 최대 약 13.5시간 FB 크롤링/Instagram 업로드/DM 자동응답/팔로업/CRM 파이프라인 중단 가능성. Slack 알림 없음(watchdog 자체 미기동으로 발송 주체 부재). 실제 리드 유실 여부 미확인.
**근본 원인:** OS 재부팅(원인 미확정) + watchdog.ps1 자동 기동 메커니즘 부재 (FP-033).
**조치:**
- run_scheduler.ps1 실행 → ngrok, launcher/main.py, Streamlit 재기동 (23:35:14~23:35:36)
- watchdog.ps1 백그라운드 재기동
- facebook_crawler 정상 크롤 재개 확인 (23:38:58~23:39:04, 136 라인)
**해결:** 2026-07-01 23:39 전체 스택 정상 확인 완료.
**재발 방지:** watchdog.ps1 Task Scheduler 자동 기동 등록 필요 (미적용). Modern Standby 비활성화 검토 (미적용).

---

## INC-024 | Supplier_Blocklist 매칭 8일간 무력화 — DI 리팩터링 회귀 (2026-06-24~2026-07-03 종결)
**발생:** 2026-06-24 (df9df6b 커밋) ~ 2026-07-02 (금일 감사로 발견) ~ 2026-07-03 (수정 및 종결)
**요약:** Dependency Inversion/Repository Interface 리팩터링 과정에서 `facebook_crawler.py`의 공급자 차단(Supplier_Blocklist) 로직이 잘못된 Airtable 필드명(`supplier_name` vs 실제 `author_name`)을 사용하는 Repository 계층으로 교체되며 무증상 회귀 발생. `is_blocked_supplier()`가 항상 `None`을 반환해 등록된 5개 공급자(Mooncher Kim/M&Y GLOBAL, Lily Yoon, Cosmetics Station, Athena Magnayon/Cosmetics Station, COSLIFE) 중 어느 것도 실제로 차단되지 않음.
**영향:** Lily Yoon·COSLIFE는 별도 메커니즘(`CAPTION_BLOCKLIST` 키워드 필터, `ERR-044`/`FP-032` 대응으로 2026-06-29 도입)이 우연히 방어 중이나, Mooncher Kim(M&Y GLOBAL 워터마크)과 Athena Magnayon(Cosmetics Station, 비한국 공급자)은 8일간 무방비 상태. 실제로 이 기간 중 해당 공급자 게시물이 크롤링되어 Instagram에 업로드되었는지는 미확인(UNKNOWN).
**근본 원인:** FP-034 (DI 리팩터링이 정상 동작 코드를 결함 있는 추상화로 교체).
**조치 (2026-07-02, 조사):**
- (미적용) 코드 수정 없음 — Gate 3 Read-only 조사 규칙에 따름
- 라이브 테스트로 결함 재현 및 확정 완료 (`is_blocked_supplier()` 6/6 전건 `None`)
- git blame으로 정확한 회귀 시점 특정 완료 (758d29d 도입, df9df6b 소비 시작)
**조치 (2026-07-03, 종결):**
- 사용자 승인 후 3파일 수정 적용 — `repository_interface.py`(`SupplierBlockEntry`에 `page_name` 추가) / `airtable_repository.py`(`author_name`/`page_name` 매핑) / `facebook_crawler.py`(하드코딩 `page_name: ''` 제거)
- Gate 6 ISOLATED INTEGRATION PROOF — 격리 테스트 테이블 `Supplier_Blocklist_Test`에 실 레코드 POST/GET(mock 없음)으로 BUGGY 재현 및 FIXED 정상 매칭 사전 확인
- 운영 `Supplier_Blocklist` 대상 Runtime Proof — `is_blocked_supplier()` 6/6 전건(Lily Yoon/Mooncher Kim/M&Y GLOBAL/Cosmetics Station/Athena Magnayon/COSLIFE) 매칭 성공 확인
- pytest 회귀 없음 확인 (100 passed, pre-existing 4 failed는 stash 비교로 무관 확인)
**해결:** ✅ 완료 (2026-07-03) — 필드명 수정(`supplier_name`→`author_name`, `page_name` 매핑 추가) 적용 및 실증 완료
**재발 방지:** FP-034 등록/해결. DI 리팩터링 커밋에 대한 회귀 테스트 의무화 체계 자체는 미구축 — 향후 트랙. 실제 유출(비차단 업로드) 여부 확인을 위한 2026-06-24~07-02 사이 업로드된 Instagram_Posts 중 위 5개 공급자 author_name 일치 건 조회는 **미실시 — 별도 확인 필요**.

---

## INC-025 | watchdog.ps1 4일+ 감시 공백 — 스케줄 자동 기동 무재실행 (2026-07-01 23:36 ~ 진행 중, 2026-07-05 발견)
**발생:** 2026-07-01 23:36:55 (watchdog.log 마지막 기록) ~ 2026-07-05 20:2x (세션 점검으로 발견, 미해결)
**요약:** INC-023 복구(07-01 23:35 수동 재기동) 직후 watchdog.log가 23:36:55을 끝으로 기록이 끊김 — watchdog.ps1 감시 루프 자체가 재기동 직후 다시 조기 종료된 것으로 추정(원인 미확정). 이후 4일간(9회의 실제 재부팅 포함) `SNS_Watchdog_AutoStart` 스케줄 작업이 단 한 번도 재실행되지 않음(Last Run Time 06-29 20:12:06 고정, Last Result -1073741510/CTRL+C성 종료). 세션 점검 시점 watchdog.ps1 프로세스는 전무하나 launcher/main.py(python)는 2026-07-05 20:10:28에 별도/불명 경로로 기동 중 — 감시·자동재시작·Slack 알림 주체 없이 단독 운영 중인 상태로 확인.
**영향:** 최소 4일간 프로세스 크래시 시 자동 재시작 보장 없음. Slack 알림(watchdog 트리거 기반) 발송 불가 상태 지속. 이 기간 중 실제 다운타임 발생 여부는 별도 로그(scheduler_err.log 등) 대조 확인 필요 — 미실시.
**근본 원인:** ERR-047 / FP-035 (Task Scheduler "등록 완료"가 실제 재기동을 보장하지 않음, `Logon Mode: Interactive only` 등 미검증 실행 조건 가능성).
**조치 (2026-07-05, 발견 및 문서화):**
- `schtasks /Query /TN "SNS_Watchdog_AutoStart" /V` 로 Last Run Time 고정 확인
- `Get-WinEvent -Id 12`(Kernel-General)로 06-29 이후 실제 cold boot 9회 확인, `powercfg /a`로 Fast Startup 비활성 확인(hibernate-resume 오탐 배제)
- `Get-CimInstance Win32_Process`로 watchdog.ps1 미실행 확인
- ERROR_DATABASE.md ERR-047 / FAILURE_PATTERN.md FP-035 등록
- (미적용) watchdog.ps1 재시작 — 사용자 승인 대기, 문서화만 우선 진행하기로 결정

**조치 (2026-07-08, 추가):**
- Task Action을 watchdog_task_wrapper.ps1 경유로 전환(ERR-050 임시 Fix)
- wrapper 경유 인스턴스 1h46m 자연 생존 확인(10:16:55~12:02, watchdog.log heartbeat 연속) — direct 실행의 60초 조기사망과 대비
- 이중 watchdog(PID 22908 direct + 29076/30888 wrapper) 동시 감시 발견 → 사용자 승인 하 wrapper 계열 정리(FP-017 재발 패턴)
**해결:** 🟡 임시 완화 (Mitigated), 검증 불완전 — wrapper 우회로 direct 실행의 60초 조기사망 문제는 회피 확인됨. wrapper 경유 인스턴스(PID=29076)는 1h46m 정상 생존 후, 별도 발견된 이중 감시(FP-017 재발) 정리를 위해 의도적으로 종료됨(12:03:12, Stop-Process — 크래시 아님) — 자연 수명 검증은 아직 안 됨, 방해 없이 얼마나 오래 갈 수 있는지는 여전히 미확인. 근본원인(direct가 왜 죽는지) 및 재부팅 시 BootTrigger/LogonTrigger 자동 발동 여부 모두 OPEN (ERR-050 참조)
**재발 방지:** ERR-047/FP-035 Prevention 항목 참조 (Task Scheduler 조건 재검토, 상위 감시 계층 이중화, 정기 `schtasks /Query` 점검).

**[2026-07-09 추가 Note — 재부팅 실증]:** 2026-07-08 20:32 실제 재부팅 트리거 시 Task Action(wrapper 경유) 자체는 발동 확인됨 — 단, 이는 INC-025 원 증상("06-29 이후 9회 재부팅에도 무재실행")과 조건이 다름(당시 Action=direct 실행, 이번=Note 상 08-08 wrapper 경유 전환 이후). 트리거 발동 자체가 회복됐다는 의미는 아님 — 원인 규명 없이 조건이 바뀐 상태에서의 별개 관찰. wrapper(PID 2656)는 발동 후 약 4분 24초(20:32:17~20:36:41) 만에 WRAPPER END 로그 없이 종료(silent death) — INC-025가 기술한 "감시 공백" 문제가 형태를 바꿔 재현됨: 기존은 "재실행 자체가 안 됨", 이번은 "재실행은 되나 단명 후 재차 감시 공백 발생". 근본원인 여전히 UNKNOWN(상세 raw 로그 근거: ERR-047 Note 2 / ERR-050 Note 3 참조, 동일 실증 — watchdog_wrapper.log/watchdog_wrapper_stderr.log/watchdog.log/schtasks 출력 교차확인 완료). INC-025 해결 상태 변경 없음 — 🟡 임시 완화(Mitigated)/OPEN 유지, 완료 아님.

---

## INC-026 | launcher/main.py 5세대 동시 기동 (2026-07-06 16:46 ~ 17:11, 세션 중 발견 및 정리 완료)
**발생:** 2026-07-06 16:46:43 (1세대 기동) ~ 17:11:06 (정리 후 단일 인스턴스 재기동 완료)
**요약:** watchdog.ps1 미기동(INC-025 지속) 상태에서 세션 중 `launcher/main.py`를 수동으로 여러 차례 `Start-Process` 실행 — 기존 인스턴스 생존 여부를 매번 확인하지 않아 서로 다른 시각(16:46:43, 16:51:04, 16:55:41, 16:55:57)에 시작된 4세대 + 전날(07-05 23:38:57)부터 떠있던 1세대까지 총 5세대 launcher가 동시 생존, 각자 독립된 APScheduler로 `_job_fb_crawl`/`_job_insta_upload`/`process_due_followups` 등 동일 잡을 병행 실행 중이었음. 각 세대는 `.venv` launcher 프로세스 + 시스템 Python310(AdsPower/Selenium 연동 추정) 프로세스 짝으로 구성.
**영향:** 실제 중복 DM 발송/게시물 중복 업로드/AdsPower 세션 충돌 여부는 미확인 — app.log 상 명시적 크래시나 에러는 발견되지 않았으나, 5세대 병행 실행 자체가 잠재적 리소스 경합 및 정합성 위험 상태였음.
**근본 원인:** ERR-048 / FP-036 (launcher/main.py에 중복 기동 방지 가드 부재 + watchdog.ps1 미기동으로 인한 수동 개입 누적).
**조치 (2026-07-06):**
- `Get-CimInstance Win32_Process` / `Get-Process -StartTime` 대조로 5세대(10프로세스) 존재 및 각 시작 시각 확인
- `watchdog.ps1` 미실행 확인(자동 재시작 경합 없음 확인 후 정리 진행)
- 8개 프로세스 `Stop-Process -Force`로 정리 (전날 기동 PID 20448/5284 2개는 Access denied로 종료 실패, 잔존)
- `logs/summary/app.log` 확인 — 단일 신규 인스턴스(PID 33148/6140) 스케줄러 1세트만 정상 등록, Flask 정상 바인딩 확인
- `:5000` 재확인 중 프로세스 열거 도구에 나타나지 않는 유령 LISTENING PID 32944 발견 — 원인 미확정, ERR-048에 기록
- ERROR_DATABASE.md ERR-048 / FAILURE_PATTERN.md FP-036 등록
**해결:** 🟡 부분 해결 — 단일 신규 인스턴스는 정상 동작 확인, PID 20448/5284/32944는 비관리자 권한으로 종료/식별 불가하여 미해결 (관리자 권한 세션 또는 재부팅 필요)
**재발 방지:** ERR-048/FP-036 Prevention 항목 참조 (launcher 중복 기동 가드 추가, watchdog.ps1 정상화(ERR-047) 최우선).

---

## INC-027 | quality_gate.py relevance filter canary — 영어-only 키워드 오적용으로 Domeggook 크롤 100% 차단 및 rollback (2026-07-06)
**발생:** 2026-07-06 13:02 (재시작 후 첫 dome_crawl 사이클) ~ 같은 날 rollback 완료
**요약:** `quality_gate.py`에 관련성(relevance) 필터를 canary 편집으로 추가하는 과정에서, dry-run 검증을 Instagram_Posts의 영문 번역 `caption` 필드 20건 기준으로 수행해 20/20 MATCH를 확인했으나, 이를 실제 runtime proof로 오판. 실제 `run_gate()`가 검사하는 필드는 Domeggook API 원본 `title`이며 이는 한국어다. 영어-only 키워드가 한국어 title에 매칭되지 않아, launcher/main.py 재시작 직후 첫 `_job_dome_crawl` 실행에서 D001(화장품)/D002(건강식품) 모두 `fetch=10 ready=0` — 정상 화장품/건강식품 상품까지 전량 FILTERED되는 100% 크롤 차단 발생.
**영향:** Domeggook 크롤 파이프라인 1회 사이클(13:02~13:11 KST 구간, 다음 사이클 전) 전체 차단. 실제 게시물 게시 중단 여부는 이 사이클 한정, 이전 누적 ready 레코드(source_exporter 대상)는 영향 없음.
**근본 원인:** dry-run 검증 필드(`caption`, 영문)와 실제 runtime 입력 필드(`title`, 한국어)의 불일치. 검증 완료가 배포 안전을 보장한다는 가정이, "무엇을 검증했는가"와 "실제 무엇이 실행되는가"의 일치 여부 확인 없이 성립됨.
**조치:**
- `git checkout HEAD -- modules\crawlers\quality_gate.py` 로 원본 4규칙(adult_only/title/unit_price/image_url) rollback
- launcher/main.py PID 지정 재시작(Stop-Process -Id 지정 후 재기동)으로 런타임 반영 확인
- rollback 후 다음 dome_crawl 사이클에서 `fetch=10 ready=10` 복귀 자연 스케줄 대기로 검증 예정
**해결:** ✅ ROLLED BACK (2026-07-06) — quality_gate.py는 원본 4규칙 상태로 복원 완료. 관련성 필터 재설계는 미착수(한국어+영어 이중언어 키워드 기준 재설계 필요).
**재발 방지:** FP-037 참조 — dry-run 검증 시 실제 runtime 필드명/언어/raw 샘플 사용 필수.
**관련:** ERR-049, FP-037

---

## INC-028 | watchdog.log 감시 공백 3시간12분 + 파이프라인 전체 다운 (2026-07-09 20:09:40 ~ 23:22:14)

**발생:** 2026-07-09 20:09:40(watchdog.log 마지막 HEARTBEAT, 공백 시작 추정) ~ 2026-07-09 23:22:14(watchdog.ps1 재기동 로그 `===== watchdog 시작 =====`, 공백 종료) — 약 3시간 12분 34초
**발견:** 2026-07-09 22:56경(`Get-CimInstance Win32_Process` *watchdog* 필터 / `logs\watchdog.pid` 조회로 최초 이상 징후 포착) ~ 23:01:54(프로세스/포트/watchdog.log/Task 이벤트 종합 조회로 확정) — 세션 중 정기 상태 점검 과정에서 발견, 별도 알림/자동 감지 없음

**요약:** 세션 중 watchdog 운영 상태를 점검하던 중, `logs/watchdog.log`의 마지막 HEARTBEAT가 20:09:40에서 멈춰 있고 이후 약 3시간 12분간 신규 기록이 없음을 확인. 동시에 `launcher/main.py`(:5000)/Streamlit(:8501)/ngrok(:4040) 3개 핵심 서비스 프로세스가 전부 부재, 포트 3개 전부 미바인딩 상태였음. 발견 직후 재기동 절차(전수 프로세스 확인 → launcher → Streamlit → ngrok → watchdog.ps1 순차 기동)를 거쳐 23:22:14 watchdog.ps1 재시작, 4개 서비스 전부 정상화 확인.

**발견 당시 상태 (raw 근거):**
- `Get-CimInstance Win32_Process` 를 `python|pythonw|streamlit|ngrok|cmd.exe|pwsh` 등 조건으로 다회 조회한 결과 launcher/Streamlit/ngrok 프로세스 **0개** (매칭된 항목은 전부 무관 프로세스 — LG Software GSearch 인덱서, Chrome native host)
- `netstat -ano | findstr ":5000 :8501 :4040"` → 출력 없음. 전체 LISTENING 목록 재조회에서도 3개 포트 전부 부재 — **포트 3개 전부 미바인딩**
- `Get-ScheduledTaskInfo -TaskName "SNS_Watchdog_AutoStart"` → `LastRunTime: 2026-07-08 20:32:05`(발견 시점 기준 전날), `LastTaskResult: 3221225786`(0xC000013A) — **당일(07-09) 실행 이력 전무**
- `logs/watchdog.pid` 파일 자체 부재 (`Get-Content`가 null 반환, `Get-Process -Id $null` 바인딩 오류로 확인)
- `logs/watchdog.log` / `logs/watchdog_wrapper_stdout.log` 둘 다 마지막 라인이 `[2026-07-09 20:09:40] [HEARTBEAT] alive`에서 정지, 이후 신규 라인 없음(파일 mtime도 20:09:40 그대로)
- `Get-WinEvent -LogName System -MaxEvents 30 | Where TimeCreated 2026-07-09 20:05:00~20:20:00` → **매칭 이벤트 0건.** System 로그 자체에 해당 15분 구간 관련 신호가 없었다는 사실만 확인됨 — 재부팅 인과관계는 UNKNOWN(아래 근본 원인 참조), 배제도 확정도 아님.

**재기동 절차 및 결과 (raw 근거):**
- 재기동 전 전수 프로세스 확인: python/streamlit/ngrok/powershell 전체 스캔 결과 파이프라인 관련 잔존·좀비 프로세스 **0개** 확인 후 진행
- `Start-Process .venv\Scripts\python.exe launcher\main.py` → PID 30636(부모)/31416(자식) 생성, `netstat` 재확인 시 `:5000 LISTENING 31416` 일치 확인
- `Start-Process .venv\Scripts\streamlit.exe run dashboard.py --server.port 8501` → PID 체인 최종 33476, `:8501 LISTENING 33476` 일치 확인
- `Start-Process ngrok http --url=... 5000` → PID 19976, `:4040 LISTENING 19976` 일치 확인
- 각 서비스 기동 후 프로세스 트리 최말단 PID와 netstat LISTENING PID가 정확히 1:1 일치 — **중복 기동 없이 클린 기동 성공**(ERR-048류 유령·중복 프로세스 재발 없음 확인)
- `Start-Process powershell -Verb RunAs ... watchdog.ps1`(관리자 권한, UAC 승인) → `logs/watchdog.log`에 `[2026-07-09 23:22:14] ===== watchdog 시작 =====` 기록, 이후 HEARTBEAT 30초 간격으로 재개, 이후 재확인(23:26:16)까지 연속 정상 확인

**근본 원인:** **UNKNOWN.** 공백 발생 원인(재부팅 여부 / foreground 세션 종료 / 기타)을 특정할 직접 증거가 없음. System 이벤트 로그 20:05~20:20 조회에서 매칭 이벤트 0건인 것은 "이 구간에 System 로그상 기록된 재부팅·절전 이벤트가 없었다"는 사실만 보여줄 뿐, 재부팅이 원인임을 배제하는 근거도 다른 원인(foreground 세션 종료 등)을 확정하는 근거도 아니다 — 조회 범위(System 로그, 15분 창)와 실제 원인 사이의 인과관계는 미확인 상태로 남는다. ERR-047(스케줄 작업 무재실행)/ERR-050(wrapper silent death)/ERR-051(Task Scheduler launch-only 실패) 세 건 모두 유사하게 "watchdog 감시가 예고 없이 끊기는" 패턴을 다루고 있어 근본원인이 서로 연결되어 있을 가능성이 있으나, 이번 사고를 이들과 통합 조사할지 별도 트랙으로 둘지는 다음 세션에서 판단 필요.

**해결:** ✅ 서비스 복구 완료(2026-07-09 23:22:14, 재기동 후 4개 서비스 전부 LIVE 확인) — 단 **근본원인은 미해결.** 공백 재발 방지책 없이 서비스만 복구된 상태.

**재발 방지:** ERR-047/ERR-050/ERR-051 Prevention 항목과 동일 맥락 — (1) watchdog.log 하트비트 정지를 감지하는 상위 감시 계층 필요(현재는 세션 중 수동 점검으로만 발견됨, 자동 알림 없음 — CLAUDE.md `get_watchdog_status()` 90초 기준 판정 로직이 존재하나 이번 3시간+ 공백 동안 실제로 알림·감지가 이루어졌는지는 미확인, 별도 검증 필요). (2) 근본원인 규명 전까지는 재발 가능성을 상수로 간주하고 정기 점검 주기화 검토.

**별도 기록 (장애 아님, 노이즈):** watchdog.ps1 재기동 직후(23:22:20~23:23:11) n8n 관련 `[WARN] n8n 응답 없음` → `[ERROR] n8n 재시작 실패` → `[RECOVER] N8n 복구` 사이클이 30초 내 자동 발생·자동 해소됨. n8n은 CLAUDE.md 기준 "미설정, 정상" 상태이므로 실제 장애가 아니라 watchdog이 미구성 서비스를 체크하며 발생시키는 노이즈성 로그로 판단됨. 본 INC의 장애 범위에는 포함하지 않음 — 별도 FP·개선 항목 등록 여부는 승인 후 판단.

**관련:** ERR-047, ERR-050, ERR-051, INC-023, INC-025

**[2026-07-10 추가 Note — 절전모드(Modern Standby) 상관관계 조사]:**

본 INC의 재발(2차 다운, watchdog 마지막 heartbeat `2026-07-10 03:04:09` — heartbeat_monitor.py가 탐지, ERR-052 신규 Task 검증 과정에서 발견)와 이 시스템의 Modern Standby 이력을 대조함. 전체 raw 이벤트 목록·시스템 절전 구성 상세는 ERR-047 Note 4 참조(중복 서술 생략).

- **2차 다운(03:04:09):** `2026-07-10 00:54:30~04:11:29`(약 3시간17분) Modern Standby 구간 한가운데 위치 — **상관관계 강함**(인과관계 확정 아님)
- **1차 다운(본 INC의 원 사건, 20:09:40):** 가장 가까운 절전 구간(21:40:28)과도 1시간30분 이상 차이 — 이번 조사로는 절전모드로 설명되지 않음
- 즉 같은 "watchdog 감시 공백"으로 묶여온 1차/2차 다운이 서로 다른 메커니즘일 가능성이 있음 — ERR-047/050/051/본 INC를 단일 근본원인으로 묶어온 전제 재검토가 필요할 수 있음(잠정 결론, 확정 아님)

**UNKNOWN 유지:**
- 1차 다운(20:09:40)의 실제 원인 — 아래 Note 3에서 해소됨(실제 OS shutdown 확인, Modern Standby 아님)
- Modern Standby가 watchdog.ps1 자체를 실제로 어떻게 멈추는지의 메커니즘(프로세스 kill vs 타이머 지연 등 미구분) — 아래 Note 2는 heartbeat_monitor.py 쪽 메커니즘만 해소한 것이며, watchdog.ps1 자체의 메커니즘은 여전히 UNKNOWN
- `powercfg /sleepstudy`는 관리자 권한 필요로 미생성(향후 재시도 가능)

**관련(추가):** ERR-047(Note 4 — 원본 근거)

**[2026-07-10 추가 Note 2 — heartbeat_monitor.py 자체의 Modern Standby 취약성 메커니즘 확정, ERR-053]:**

Note 1에서 "Modern Standby가 watchdog을 실제로 어떻게 멈추는지의 메커니즘"을 UNKNOWN으로 남겼던 것 중, **heartbeat_monitor.py(watchdog을 감시하기 위해 추가된 별도 스크립트) 자신의 절전 취약성 메커니즘은 이번에 확정됨** (watchdog.ps1 자체의 메커니즘은 여전히 UNKNOWN, 구분 필요).

- `SNS_HeartbeatMonitor_Independent`(5분 주기 반복 트리거) `NumberOfMissedRuns=71`, `WakeToRun=False` 확인 — 06:11:28(마지막 정상 실행) 이후 약 5시간45분간 미실행, 이 구간은 04:11~11:16 사이의 Modern Standby 반복/연속 구간과 시간대가 겹침
- 대조군 `SNS_Watchdog_AutoStart`(로그온 1회 트리거 + 상시 프로세스)는 `NumberOfMissedRuns=0` — 반복 트리거가 아니라 절전 영향을 받지 않고, 실제로 06:16경 스스로 heartbeat 재개함(watchdog.log 확인)
- 즉 heartbeat_monitor.log가 06:11:29 이후 조용히 멈춘 것은 "프로세스 크래시"가 아니라 "애초에 Task Scheduler가 절전 중 트리거를 스킵해 프로세스가 생성되지 않았다"는 것으로 근본 원인이 확정됨(ERR-053/FP-040 참조)

**관련(추가 2):** ERR-053, FP-040

**[2026-07-10 추가 Note 3 — 1차 다운(20:09:40) 실제 원인 확정: Modern Standby 아님, 실제 OS Shutdown]:**

Note 1에서 "1차 다운(20:09:40)의 실제 원인"으로 UNKNOWN 남겼던 항목을 재조사함.

**Confirmed:**
1차 다운은 Modern Standby(절전)가 아니라 **실제 OS shutdown 이벤트**였음. 이벤트 체인(raw, 시간순):
- `20:09:40` `watchdog.log` 마지막 HEARTBEAT
- `20:09:52` System log, User32 Id=1074 — `StartMenuExperienceHost.exe`가 admin 세션 명의로 시스템 종료 개시 (`Reason Code: 0x0`, `기타(계획되지 않음)`, `Shutdown Type: 전원 끄기`)
- `20:10:03` User32 Id=1073 — "The attempt by user ... to restart/shutdown ... failed" (재시도 실패 기록)
- `20:10:28~20:10:53` — 서비스 순차 종료(explorer.exe/StSess.exe가 종료 지연, DHCP/WLAN/EventLog/TaskScheduler 서비스 순차 stop)
- `20:10:44` Kernel-Power Id=105(전원 소스 변경) / `20:10:51` Id=109(종료 전환 개시, `Reason: Kernel API`) / `20:10:53` Id=577(재부팅 준비)
- `20:10:53` Kernel-General Id=13 — "The operating system is shutting down"
- 마지막 heartbeat(20:09:40)와 종료 개시(20:09:52) 사이 12초 — 시간 정합 확인됨

**Confirmed(배제):**
- Modern Standby 아님 — 직전 절전 해제(19:39:00, Id=507)부터 다음 절전 진입(21:40:28, Id=506)까지 약 2시간1분 동안 Modern Standby 이벤트가 전혀 없었고(`Get-WinEvent` Id=506,507 raw 확인), 1차 다운 전체 구간(20:09:40 마지막 heartbeat ~ 20:10:53 OS 종료 확정)이 이 공백 한가운데 위치함
- Windows Update 강제 재부팅 아님 — `19:00~20:15` 구간 Update 관련 Provider/Message 매칭 이벤트 0건
- 명시적 사용자 로그오프/화면 잠금도 아님 — Security 로그 4647/4634/4801/4800(`20:08~20:11`) 매칭 이벤트 0건

**Hypothesis (확정 아님):**
시작 메뉴에서 사람이 직접 전원 버튼을 눌렀을 가능성이 가장 유력 — `Id=1074`가 `StartMenuExperienceHost.exe`(시작 메뉴 UI 프로세스 자체) 명의로 기록됐기 때문. 단, 다른 프로세스가 동일 종료 API를 자동 호출했을 가능성을 배제할 로그 증거는 없어 100% 확정은 아님.

**UNKNOWN (미해결):**
`20:10:03` "재시도 실패" 기록과 `20:10:28` 실제 종료 재개 사이 25초 갭의 정확한 메커니즘 — 어떤 프로세스/조건이 1차 종료 시도를 지연·차단했다가 25초 뒤 종료가 재개됐는지 불명. 재발 시 재조사 대상으로 남김.

**조사 방법(Evidence):** `Get-WinEvent` System/Security 로그 필터링 총 3회 라운드 — 1차(종료 체인 발견: User32/Kernel-Power/Kernel-General 이벤트, `watchdog.log` 타임스탬프 대조), 2차(Update 관련 Provider/Message 키워드 검색으로 배제, Security 4647/4634/4801/4800 조회로 로그오프/잠금 배제), 3차(Kernel-Power Id=506/507 전체 이력을 15:00~00:00 구간 시간순 정렬로 조회해 절전 공백 구간을 raw로 확정). `scheduler_err.log`/`Microsoft-Windows-TaskScheduler/Operational`도 같은 구간 조회했으나 이번 종료 체인과 직접 연관된 특이 항목은 확인되지 않음(대부분 종료 중 발생하는 일반 Task 실패 노이즈).

**ERR 신규 등록 판단:** 이번 발견은 별도 ERR-NNN으로 등록하지 않음. 근거 — (1) 근본 원인이 "코드 결함"이나 "잘못된 인프라 설정"이 아니라 (가장 유력한 가설상) 사람의 종료 조작 또는 최소한 애플리케이션 레벨에서 통제 불가능한 OS 종료 이벤트이며, ERR 포맷의 핵심 요소인 Fix/Prevention을 "종료 자체를 막는다"는 방향으로 적용할 수 없음. (2) 실질적으로 필요한 후속 조치("재부팅 이후 watchdog이 안정적으로 자동 복구되어야 한다")는 이미 ERR-047의 Root Cause/Prevention 범위에 포함되어 있어, 동일 Prevention 계획을 이원화하면 중복·분산만 초래함. 이번 조사 결과는 본 Note와 ERR-047 Note 5(교차 기록)로만 남긴다.

**관련(추가 3):** ERR-047

---

## INC-029 | 250723 참조 활성 Task 발견 및 긴급 비활성화 (2025-11-20 추정 ~ 2026-07-10)

**발생 추정:** 2025-11-20(SNS_AUTO_PRODUCTION 최초 등록, StartBoundary 기준) ~ 2026-07-10(오늘, 비활성화 완료) — 약 8개월
**발견:** 2026-07-10 새벽, `heartbeat_monitor.py`(신규 독립 감시 스크립트) 검증 작업 중 "기존 정상 Task로 Task Scheduler 전반 정상 여부 교차검증" 목적으로 `SNS_Auto_Run`을 트리거하다 우연히 발견 — 250723을 노린 의도된 조사가 아니었음을 명시한다.

**요약:** `SNS_AUTO_PRODUCTION`(2025-11-20 등록)과 `SNS_Auto_Run`(2026-01-13 등록) 두 Windows Scheduled Task가 매일 09:00 `C:\SNS_24AutoProject_250723\tools\run_production.py`(Reference Only, 실행 금지 원칙 적용 저장소의 코드)를 실행하도록 활성 상태로 남아 있었음. 250723과 260511은 동일 프로덕션 Airtable Base(`apphJNTHWNoFcVb1D`)를 공유하고 있어, 잠재적으로 동시 쓰기 위험이 있는 상태였음. 발견 즉시 두 Task를 `Disable-ScheduledTask`로 비활성화(삭제 아님, 증거 보존).

**실제 피해 여부:** UNKNOWN. 정적 분석(ERR-052 참조 — python 인터프리터에 dotenv 미설치, 모듈 파일 개명·부재로 인한 3중 import 실패 추정, 250723 자체 로그/DB 갱신 흔적이 6개월+ 전에 멈춤)상으로는 실제 프로덕션 쓰기까지 도달했을 가능성이 낮아 보이나, 이는 stderr 실측이 아닌 정적 추론일 뿐이며 8개월 전체 기간 중 단 한 번도 성공 실행이 없었다고 단정할 근거는 없음.

**해결:** 2026-07-10 `Disable-ScheduledTask -TaskName "SNS_AUTO_PRODUCTION"` / `"SNS_Auto_Run"` 실행, `Get-ScheduledTask` 재조회로 두 Task 모두 `State=Disabled` 확인(raw). 자동 발동에 의한 위험은 즉시 차단됐으나, Task 완전 삭제 여부·250723 저장소 자체 처리 방향은 별도 결정 필요.

**재발 방지:** 오늘 1차 전수 스캔(`Get-ScheduledTask` 전체 순회, Actions 문자열에 `"250723"` 매칭)을 완료해 이 2건 외 Task Scheduler상 추가 발견은 없음을 확인함. 단, Task Scheduler 이외의 다른 자동화 경로(Windows 시작프로그램, 별도 스케줄러/서비스, cron 유사 도구 등)는 이번 점검 대상에 포함되지 않았음 — **UNKNOWN, 별도 전수 재점검 필요.**

**관련:** ERR-052, FP-039

---

## INC-030 | NSSM 서비스와 구 Task Scheduler의 watchdog.ps1 이중 실행 — 발견 및 당일 정리 완료 (2026-07-11 09:07 ~ 11:5x)

**발생:** 2026-07-11 09:07경(재부팅 직후) ~ 발견 및 정리 완료(같은 세션 내, 오전 중)
**발견:** 세션 초반 상태 점검 중 watchdog.log에 `===== watchdog 시작 =====` 배너가 09:07:02/09:07:58 두 번 찍힌 것을 발견, 프로세스 부모-자식 체인 조사로 NSSM 서비스(`SNS_Watchdog`)와 구 Task(`SNS_Watchdog_AutoStart`)가 동시에 watchdog.ps1을 실행 중임을 확인(ERR-057).

**요약:** 이전 세션(260710)에서 PENDING-A(NSSM 전환 검토) 결론에 따라 NSSM 서비스가 설치·`Automatic` 등록까지 진행되어 있었으나, 구 Task 비활성화(Phase 3)가 누락된 채 세션이 종료됨. 260711 재부팅 시 두 메커니즘이 동시에 기동해 Flask/Streamlit/ngrok/n8n에 대해 각자 독립적으로 상태 점검·재시작을 시도.

**실제 피해 여부:** 완전한 서비스 중단은 없었음 — Flask(:5000)/Streamlit(:8501)/ngrok(:4040)는 전 구간 LISTENING 유지 확인. 관측된 영향은 (1) watchdog.log 시작 배너·재시작 로그 중복 기록, (2) n8n 재시작 실패 알림이 짧은 간격으로 반복 발생(단, n8n 자체는 ERR-056에 따라 원래도 의도적 정지 상태라 추가 실질 피해는 아님), (3) 두 watchdog 인스턴스가 동시에 프로세스를 재시작할 경우의 포트 바인딩 경합 등 잠재적 race condition 리스크(이번엔 실제 발현되지 않음, 리스크로만 기록).

**해결:** 사용자가 관리자 PowerShell에서 `Disable-ScheduledTask -TaskName "SNS_Watchdog_AutoStart"` 실행(`schtasks /V`로 `Scheduled Task State: Disabled` 확인) → 구버전이 이미 띄운 PID 27664/28548을 `Stop-Process -Force`로 종료 → 재조회로 두 PID 소멸, NSSM 서비스(PID 13008)만 단독 운영 중임을 확인. Flask/Streamlit/ngrok 포트 전부 영향 없이 정상 유지.

**재발 방지:** FP-042(신규) 등록 — 전환 작업의 중간 상태를 문서에 명시적으로 남기고, 세션 재개 시 raw 재확인을 우선하는 절차를 표준화.

**관련:** ERR-057, FP-042, PENDING-A, ERR-053, ERR-054

---

## INC-031 | ngrok 터널 다운으로 Instagram DM 웹훅 수신 불가 (2026-07-11 09:07경 ~ 12:35:48, 약 3시간반)

**발생:** 2026-07-11 09:07경(오늘 첫 재부팅, 이 시점부터 잠복 — 실제로는 그때도 구 Task가 우연히 살려서 정상이었음) ~ 실제 노출은 ERR-057 조치로 구 Task를 끈 이후(11:xx경)부터 ~ 12:35:48(해결)
**발견:** ERR-057 조치 후 재부팅 실증(12:08) 과정에서 watchdog.log에 ngrok 반복 재시작 실패 로그 확인.

**요약:** NSSM 서비스(LocalSystem 계정)가 watchdog.ps1의 유일한 실행 주체가 되면서, ngrok(Microsoft Store 설치 + admin 사용자 프로필 전용 authtoken)을 실행할 수 없게 됨(ERR-058). ngrok이 뜨지 못하면 `danuta-overdramatic-whirly.ngrok-free.dev`(Meta Webhook 콜백 URL로 등록된 고정 도메인)가 로컬 Flask(:5000)로 연결되지 않아, 이 구간 동안 Instagram DM/댓글 웹훅 수신이 실질적으로 불가능했을 것으로 추정.

**실제 피해 여부:** 이 구간에 실제 수신 시도가 있었는지는 확인 안 됨(Meta 측 재시도/실패 로그는 우리 쪽에서 조회 불가) — UNKNOWN. Flask 자체(:5000)는 로컬에서는 계속 정상(`/health` 200)이었으므로, 외부에서 ngrok 경유로 들어오는 요청만 영향받았을 것으로 추정.

**해결:** ERR-058 Fix 참조 — watchdog.ps1 ngrok 실행 경로를 포터블 exe로 변경 + authtoken 설정을 LocalSystem 프로필에 복사 → 12:35:48 `[RECOVER] Ngrok 복구` 확인, `public_url` 정상 응답 확인.

**재발 방지:** FP-043(신규) 참조 — 서비스 계정 전환 시 의존 도구 전수 점검을 표준 절차화.

**관련:** ERR-058, FP-043, ERR-057, FP-042

---

## INC-032 | 학습 리뷰 그리드 실제 50건 배치 저장이 "실패"로 오탐 표시됨 — 실제로는 성공, 원본 선택 기록 유실로 조건부 종결 (2026-07-12)

**발생:** 2026-07-12, 학습 리뷰 그리드(Training_Review_Queue) tab8에서 사용자가 실제 PENDING 50건에 대해 확정 버튼(44 BLOCK/6 PASS) 클릭.

**발견:** 화면에 "저장 후 확인(GET)이 일치하지 않습니다"와 함께 50개 record_id 전부가 나열되는 오류 표시. 사용자가 "선택했는데 왜 실행이 잘됐다는 내용이 안 나온다"고 보고.

**요약:** 저장(PATCH) 자체는 50건 전부 성공했으나, 직후 확인(GET) 단계의 코드가 예외를 전부 "값 불일치"로 잘못 처리해(ERR-059) 실패로 표시됨. 직접 재조회(47/50건)로 42 BLOCK/5 PASS 정확히 저장 확인. 최초 제기된 "속도 제한" 가설은 실제 PATCH 간격 로그(82초/50건, 초당 5회 제한보다 훨씬 낮음) 대조로 기각되고, 예외 은폐가 진짜 원인으로 확정됨(ERR-059/FP-044).

**실제 피해 여부:** 데이터 손상 없음 — 저장은 정확히 반영됨. 다만 화면의 잘못된 오류 안내로 사용자가 확정 버튼을 다시 눌러 불필요한 재-PATCH를 할 위험이 있었으나, 재클릭 금지 지시로 실제 재-PATCH는 발생하지 않음.

**추가 조사 시도 및 한계:** 원인 수정(ERR-059) 후 해당 50건을 PATCH 없이 GET만으로 재검증(`verify_only`)하려 했으나, 오류 발생 이후 해당 브라우저 탭이 새로고침되어 원본 44 BLOCK/6 PASS 선택 상태(session_state)가 유실됨을 확인. Airtable 현재값으로 "기대 payload"를 역산하면 자기 자신과 비교하는 무의미한 검증이 되므로, 이 배치에 대한 완전한 재검증은 구조적으로 더 이상 불가능하다고 판단.

**해결/종결:** 회장님 결정(260712) — 확보된 최선의 증거(47/50건 직접 재조회로 42 BLOCK+5 PASS 정확 확인, 3건 UNKNOWN, PENDING 건수 감소 추이 정황 일치)로 **조건부 종결**. 신규 20건 배치부터 수정된 파이프라인(ERR-059 Fix)으로 정식 절차 재개.

**재발 방지:** FP-044(신규) 참조 — 저장 후 재확인 로직에서 확인 자체의 예외와 값 불일치를 분리, 확정 버튼 오탐 시 잠금 처리 적용 완료.

**관련:** ERR-059, FP-044, docs/VALIDATION_EVIDENCE_training_review_3B_260712.md

---

## INC-033 | NSSM 서비스(SNS_Watchdog) 예기치 않은 종료로 약 24시간 무감독 상태(2026-07-11 23:08:47 ~ 2026-07-12 23:46:14)

**발생:** 2026-07-11 23:08:47(서비스 크래시, Event ID 7034) ~ 2026-07-12 23:46:14(서비스 완전 재생성 후 정상화 확인)
**발견:** 2026-07-12 세션 재개 중 `Get-Service SNS_Watchdog`가 `Stopped`인데 watchdog.log는 계속 heartbeat를 남기고 있는 모순을 발견하며 조사 시작.

**요약:** NSSM 서비스 본체가 예기치 않게 종료됐으나(ERR-060), 그 이전에 이미 떠있던 watchdog.ps1 자식 프로세스가 고아 상태로 계속 정상 작동해 Flask/Streamlit/ngrok을 무사히 유지 — 약 24시간 동안 겉보기엔 정상이었으나 실제로는 **아무 감독 없이 운 좋게 버틴 상태**였음. 이 구간에 watchdog.ps1이 단 한 번이라도 크래시했다면 아무도 복구하지 못했을 것.

**실제 피해 여부:** 이 구간 동안 실제 서비스 중단은 없었음(Flask/Streamlit/ngrok 전부 연속 LISTENING 확인) — 잠재적 무방비 상태였을 뿐, 실현된 장애는 아님.

**해결:** ERR-060 Fix 참조 — 고아 프로세스 정리, nssm.exe 재설치, 서비스 등록 완전 재생성, `sc.exe failure`로 서비스 본체 크래시 복구 옵션 신규 추가. `Get-Service` → `Running/Automatic`, `sc.exe qfailure` → `SUCCESS` 확인.

**재발 방지:** FP-045(신규) 참조 — 서비스 본체 크래시 복구(`sc.exe failure`)를 자식 프로세스 크래시 복구(NSSM `AppExit`)와 별도로 반드시 설정.

**[2026-07-13 추가]:** 트리거 원인 확정(ERR-060 Note) — 백신(AhnLab Safe Transaction)이 `nssm.exe`를 PUP로 오탐·치료(삭제). 사용자가 "유해 가능 프로그램" 검사 항목을 해제해 재발 차단 조치 완료, 재탐지 팝업 재현 후 "닫기"(치료 아님) 처리로 파일 보존 확인.

**관련:** ERR-060, FP-045, ERR-057, ERR-058, PENDING-A

## INC-034 | 가격 자동응답 오매칭 노출 구간 — 실제 피해 사례 확인 불가(UNKNOWN), Gate C 가격 안전차단 PASS로 260714 10:24:41 노출 종료 — 안내문 발송·Telegram 마스킹 E2E는 PARTIAL(미확인)

**발생(노출 시작 추정):** DM 자동응답(12단계) 구현 시점(260512 이전, 정확한 시작일 미상) ~ **260714 10:24:41 종료.** 260713 22:52 커밋 `c1c90b2`는 코드 완성 시점일 뿐이었고, 260714 10:18 launcher 재시작으로 운영 반영된 뒤, 10:24:41 통제된 Canary(로컬 웹훅 시뮬레이션)로 가격 자동발송 차단 동작이 실제로 확인된 시점을 보수적으로 노출 종료로 기록. 그 이전(260711/260712 기동, 커밋보다 이전 프로세스가 계속 DM에 응답 중이던 구간)은 구버전 코드 노출 구간으로 확정.

**발견:** 260713 세션 중 `docs/design/DM_RELAY_COMMERCE_RFC.md` 설계검토(§8/§13) 도중 구조적 결함으로 발견(ERR-061) — buyer 클레임이나 오발송 신고로 발견된 것이 아님.

**실제 피해 여부:** **UNKNOWN.** `dm_receiver.py`의 DM 웹훅이 media_id(어느 게시물 문의인지)를 저장하지 않아, 과거 실제 발송 건 중 몇 건이 "buyer 문의상품 ≠ 응답가격 대상 상품"이었는지 사후 대조가 불가능함. 확인된 buyer 클레임·환불요청 로그는 없음 — 다만 이는 "피해 없음"이 아니라 "확인할 방법이 없음"임을 명확히 함.

**해결:** Gate C(ERR-061) 코드 구현·테스트 완료, 커밋 `c1c90b2`(260713) → 260714 10:18 launcher 재시작(watchdog 자동복구 경유) → 10:24:41 통제된 Canary로 **가격 안전차단 PASS 확정**(로그 대조로 팔로업 오예약·bridge_status 오갱신 없음도 확인). **단 안내문(상품확인 요청) 실제 발송 성공 여부와 신규 `send_telegram_price_pending()` Telegram 마스킹은 가짜 IGSID·네트워크 오류로 이번 Canary 범위 밖 — E2E PARTIAL(미확인)로 분리 기록.** 기존 `dm_receiver.send_telegram()` PII 노출(P0-1)은 이번 Gate C 범위 밖이며 계속 OPEN. 근본해결(Post/Product 매핑 + `price_verified_at` 24시간 검증)은 P1-B 이후 별도 게이트.

**재발 방지:** FP-046 참조.

**관련:** ERR-061, FP-046

## INC-035 | 댓글 리드 2건 Airtable 미기록 — 과거 손실 범위 UNKNOWN (RESOLVED — 이번 2건, 과거 범위는 계속 UNKNOWN)

**발생:** 260714 11:08 테스트 계정(채솔)이 남긴 댓글 2건("price plz", "dm")이 `comment_poller.py` 폴링으로 정상 감지됐으나, `Lead_Interactions` Airtable 기록이 매번 실패(ERR-062)하고도 "처리 완료"로 캐시되어(FP-047) 재시도되지 않음 — 확인된 손실 2건.

**과거 손실 범위:** **UNKNOWN.** 이 결함은 `docs/design/DM_RELAY_COMMERCE_RFC.md` 설계검토 때 "기존 코드 결함(8건)" 1번으로 이미 이론상 식별돼 있었으나, 오늘 이전에 실제로 몇 건의 댓글 리드가 같은 이유로 기록되지 않고 유실됐는지는 `processed_comment_ids.json` 캐시에 성공/실패 구분이 없어 사후 추적 불가.

**영향:** 댓글 채널로 들어온 리드가 CRM(Lead_Interactions)에 기록되지 않아 후속 스코어링·팔로업·리포트에서 누락됨. DM 채널(Gate C 대상)과는 별개 경로.

**해결:** Airtable `conversation_channel`에 `instagram_comment` 선택지 추가(260714) + 저장 Canary PASS로 **이번 유형의 저장 실패는 해소**. 단 (1) 오늘 이전 과거 손실 범위는 여전히 UNKNOWN(추적 불가), (2) 저장 실패 시 재시도 없이 영구 유실되는 구조적 패턴(FP-047)은 계속 OPEN — 다른 원인으로 저장이 실패하면 동일한 유실이 재발할 수 있음.

**추가(260715):** FP-047 자체(구조적 패턴)에 대한 코드 구현이 완료됨(ERR-067 참조) — `COMMENT_EVENT_STORE_MODE=disabled`(기본값)로 커밋, 기존 운영 동작은 안 바뀜. shadow/enforce 전환·실계정 Runtime Proof는 별도 승인 대상이라 이 INC의 "재발 가능" 자체는 disabled 상태인 한 그대로 유효 — enforce 전환 후에야 실질적으로 해소됨.

**재발 방지:** FP-047 참조.

**관련:** ERR-062, ERR-067, FP-047, `docs/design/DM_RELAY_COMMERCE_RFC.md` "기존 코드 결함(8건)" #1, `docs/design/FP047_COMMENT_EVENT_IDEMPOTENCY_260715.md`

## INC-036 | 앱 테스터 미등록 실손님 계정의 Private Reply 답장이 웹훅 미도착 — 24/7 자동화 핵심 전제 위협 (OPEN)

**발생:** 260714 Gate G 라이브 Canary 중, 캠페인 게시물에 남긴 실계정(tgbtgbnate) 댓글에 대해 시스템이 Private Reply를 정상 발송(회장 육안으로 도착 확인)했으나, 손님의 실제 답장("무시 할게", 오후 4:14경 발송)이 45분 이상 경과한 시점까지 우리 서버(webhook)에 전혀 도달하지 않음.

**영향:** `dm_auto_reply`가 손님 답장을 감지해 24시간 상담을 자동으로 이어받는 흐름이, 앱 테스터로 등록되지 않은 일반 계정(≈ 사실상 모든 실제 손님)에 대해서는 실전에서 트리거되지 않을 위험이 있음을 시사. 테스트 계정(채솔, 앱 테스터 등록)과의 DM 왕복은 오늘 내내 정상 작동했으나, 미등록 일반 계정과는 이 문제가 최소 2회(13:12경, 16:14경) 재현됨 — 오늘 발견된 좁은 테스트 이슈가 아니라, 실 손님 대상 운영에 직접 영향을 미칠 수 있는 리스크로 격상해 기록.

**진행 상황:** Root Cause 가설(Meta 앱이 `instagram_manage_messages` 등에 대해 App Review 미통과 Standard Access 상태 — 앱 역할 없는 일반 사용자와의 메시징 제한) 수립. 회장이 Meta 앱 대시보드(역할 > Instagram 테스터)를 직접 확인해 **채솔만 테스터 등록, tgbtgbnate는 미등록**임을 확인 — 가설과 일치하는 정황 증거 확보. 단 App Review > 권한과 기능의 실제 Access Level(Standard/Advanced) 자체는 아직 미확인 상태라 **OPEN**(CONFIRMED 아님).

**해결:** 미해결. 가설이 확정될 경우 코드 수정으로는 해결 불가 — Meta Business Manager에서 App Review를 통해 Advanced Access를 승격받는 것이 유일한 정식 경로이며, 이는 회장이 직접 진행해야 하는 행정 절차.

**재발 방지:** FP-048 참조.

**관련:** ERR-064, FP-048, Gate G

## INC-037 | n8n watchdog 재시작 무한 실패로 Slack 알림 잡음 5,298건+ 누적, 좀비 프로세스 10시간+ 잔존 (OPEN, 우선순위 낮음)

**발생:** 최소 260517부터 간헐적으로 관측되던 n8n 재시작 실패가, 260711(ERR-057/058, NSSM 서비스 LocalSystem 전환) 이후로는 **성공 0건**으로 전환되어 이후 계속 실패만 반복 — 260715 08:41 조사 시점 기준 연속 실패 668회, 전체 로그 기간 누적 실패 5,298건. 원인이 되는 좀비 프로세스(cmd.exe PID 16948 → node.exe PID 21620)는 260714 22:25:39 생성된 뒤 조사 시점까지 10시간 이상 살아있는 상태로 확인.

**영향:** n8n은 워크플로우가 아직 구현되지 않은 설계 단계 컴포넌트(WF-01~05 설계만 확정)이며 실사용자 대상 서비스에는 관여하지 않음 — Flask/Streamlit/ngrok/launcher 등 실제 운영 프로세스에는 영향 없음(별도 확인됨). 다만 (1) 실패마다 Slack 알림이 발송되도록 되어 있어 알림 채널 잡음이 누적되고 있고, (2) 좀비 프로세스가 장시간 리소스(메모리/핸들)를 점유 중이며, (3) 로그 파일(`logs/n8n.log`, `logs/watchdog.log`)에 동일 패턴이 계속 쌓여 향후 다른 이슈 조사 시 노이즈로 혼동될 소지가 있음.

**진행 상황:** 260721 근본원인 확정(ERR-065) — LocalSystem 프로필에는 `n8n.cmd`가 없고 admin 사용자 프로필에만 존재했다. watchdog은 `C:\Program Files\nodejs\npx.cmd`를 통해 `npx n8n start`를 실행해 `Need to install ... Ok to proceed? (y)` 대화형 설치 질문에 진입했다.

**해결:** 260721 `N8N_WATCHDOG_ENABLED=false`를 기본값으로 추가해 n8n 감시·재시작·Slack 경고를 임시 중지했다. SNS_Watchdog 재시작 후 12:16:54 비활성화 로그 확인, 마지막 실패 12:16:38 이후 추가 재시도 0건. Flask/Streamlit/ngrok/launcher는 정상 자동복구됐다. **알림 잡음·반복 프로세스 문제는 완화됐지만 n8n 기능 자체는 여전히 미구현·미기동이다.**

**재발 방지:** FP-049 참조.

**관련:** ERR-065, FP-049, ERR-056, ERR-057, ERR-058, PENDING-A

## INC-038 | 실사용자(reviewasiamarket) 댓글이 폴링 한도로 시스템에 진입조차 못함 — 실제 응대 누락 확인 (OPEN → Package 1로 근본 수정 진행 중)

**발생:** 260715 저녁, 회장이 실계정(`reviewasiamarket`)으로 30초 간격을 두고 서로 다른 상품 게시물 2곳에 댓글을 남김("관심있는데 어떻게 사요?" / "MOV 어떻게되나요"). 첫 번째 댓글은 Private Reply가 정상 도착했으나, 두 번째 댓글에는 어떤 응답도 오지 않음.

**영향:** 실제 잠재고객(구매 문의로 추정되는 "MOV 어떻게되나요" — 최소주문수량 문의)이 응답을 전혀 받지 못한 채 방치됨. Airtable 기록도 없어 CRM 파이프라인에도 이 문의 자체가 남지 않음 — 자동화 시스템이 "놓친 문의가 있었다"는 사실조차 감지하지 못하는 상태였음(감지 실패가 알림으로 이어지지 않는 이중 실패).

**진행 상황:** raw 로그·Graph API 직접 대조로 원인 확정(ERR-069/FP-050) — 두 번째 댓글이 달린 게시물이 계정의 잦은 게시 빈도로 인해 폴러의 "최근 5개" 감시 범위 밖으로 밀려나 있었음. Package 1(Phase A) 구현으로 근본 수정 착수 — GPT/Codex 교차검토 9라운드를 거쳐 코드 sign-off 완료.

**해결:** **코드 수정 완료, 운영 미반영.** `COMMENT_POLL_ALLOWLIST_MODE=legacy`(기본값)로 커밋되어 이 인시던트를 만든 "최근 N개" 방식이 아직 그대로 운영 중 — 캠페인 게시물별 baseline(`--dry-run`/`--apply`/`--verify`/`--activate`) 완료 후 `allowlist`+`enforce` 모드로 명시 전환해야 실제로 이 인시던트 패턴이 재발하지 않게 됨(별도 승인 대상). 그때까지는 동일한 누락이 다시 발생할 수 있음을 인지할 것.

**재발 방지:** FP-050 참조.

**관련:** ERR-069, FP-050, FP-047

## INC-039 | 부팅 후 watchdog 파서 오류로 핵심 서비스 자동복구 실패 (2026-07-21 11:07경 ~ 11:32:16)

**발생:** 노트북 부팅 후 NSSM `SNS_Watchdog`는 Automatic으로 시작됐으나, BOM 없는 한글 포함 `watchdog.ps1`을 Windows PowerShell 5.1이 잘못 해석해 매번 1.5초 이내 종료 코드 1로 종료. NSSM이 60초 재시작 지연 중 `Paused`로 표시되며 반복 재시도.

**영향:** 부팅 후 약 25분간 Streamlit 8501, Flask 5000, ngrok 4040이 모두 닫혀 대시보드 접근·DM 웹훅 수신·스케줄 작업이 중단됨. 노트북이 실제로 꺼져 있던 260716~260721 구간은 시스템이 실행될 수 없는 사용자 의도 정지이므로 이 인시던트의 자동복구 실패 시간 계산에서 제외.

**해결:** `watchdog.ps1`에 UTF-8 BOM 추가. NSSM의 다음 자동 재시도에서 11:32:16 새 watchdog 시작 배너 확인, Streamlit/ngrok/launcher 순차 자동복구, 5000/8501/4040 HTTP 200 확인. `tests/test_watchdog_encoding.py` 2건 추가·통과.

**재발 방지:** FP-053 참조. 실제 OS 재부팅 실증은 이번 세션에서 수행하지 않았으며 다음 계획된 재부팅 때 확인 필요.

**관련:** ERR-072, FP-053

## INC-040 | watchdog 복구 후 첫 Facebook 크롤링이 AdsPower 미기동으로 4개 그룹 전부 실패 (2026-07-21 11:33:48 ~ 11:34:17)

**발생:** launcher 복구 직후 예약된 `_job_fb_crawl`이 실행됐으나 AdsPower Local API 50325가 열려 있지 않아 4개 대상 모두 `WinError 10061`로 실패, 결과 0건.

**영향:** 해당 사이클에서 신규 Facebook 콘텐츠 수집이 전혀 이루어지지 않음. 다른 핵심 서비스(대시보드/Flask/ngrok)는 정상 유지.

**해결:** 공용 시작프로그램 `AdsPower.lnk`가 존재하지 않는 `AdsPower.exe`를 가리키는 것을 확인해 실제 `AdsPower Global.exe`로 수정하고 `TargetExists=True`를 확인했다. AdsPower 50325 LISTENING 복구 후 다음 예약 크롤링(12:03:48~12:07:02)이 4개 그룹 모두 연결 성공·총 1건 처리로 E2E PASS. **260721 재부팅 실증 완료:** 회장 승인 후 실제 `Restart-Computer -Force` 실행, `watchdog.log` 원본으로 재부팅→SNS_Watchdog 자동 재기동(13:15:13)→Streamlit/ngrok/launcher 자동 복구(13:15:18~37)→AdsPower Global 자동 실행(13:17:32~40) 전 구간 확인, 재부팅 후 50325/5000/8501/4040 전부 LISTENING. PENDING 해소, 자동기동 자체 정상 작동 확인.

**재발 방지:** FP-054 참조. LocalSystem watchdog과 사용자 세션 GUI 앱의 실행 컨텍스트를 분리한 자동기동/readiness 설계가 필요.

**관련:** ERR-073, FP-054, ERR-058

## INC-041 | 학습용 Training_Review_Queue 신규 수집이 260713 이후 8일간 0건 — 리뷰 대기열이 조용히 고갈됨 (OPEN, 회장 결정 대기)

**발생:** 260713 00:32 마지막 수집(`run_for_training_photos`) 이후 260721까지 신규 후보 0건. 그 사이 리뷰 그리드로 PENDING 107건(260713 기준)을 포함해 누적된 물량을 전부 처리, 260721 기준 전체 299건(PASS 56/BLOCK 243/PENDING 0).

**영향:** 학습 데이터 축적이 8일간 정지. 대시보드 "학습 검토" 탭에는 "검토할 것이 없습니다"라는 정상 완료 메시지만 표시돼, 회장이 직접 인지하기 전까지 아무도 이 정지를 감지하지 못함.

**진행 상황:** 260721 read-only 조사로 근본원인 확정(ERR-074) — 수집 스크립트(`tools/_run_training_photo_crawl.py`)가 애초에 스케줄러 미연결·수동 실행 전용으로 설계됨.

**해결:** 미적용 — 회장이 A(수동 재실행, 매번 명령 필요)와 B(스케줄러 자동화 신규 구현, Codex 리뷰 포함 예상) 중 선택 예정.

**재발 방지:** FP-056 참조.

**관련:** ERR-074, FP-056

---

## INC-042 | mark_post_result() `error_code` 미존재 필드 재발 — uploading 11건 고착, ERR-041(retry_count)과 동일 클래스 (OPEN, 2026-06-30~진행중)

**발생:** 최초 확인 가능 시점 2026-06-30 22:44(`recEl21XwVS1fQMLM`) ~ 2026-07-23 14:23(`recuqN2wQu6bFNzDp`, 오늘)까지 간헐 재발, 현재도 활성.

**요약:** `launcher/main.py`의 `publish_single()`이 3회 재시도 실패 후 `mark_post_result()`로 상태를 `failed`로 전환하려 하나, payload에 포함된 `error_code` 필드가 Airtable Instagram_Posts Schema에 존재하지 않아 422 UNKNOWN_FIELD_NAME 반환 → 상태 전환 자체가 실패해 레코드가 `uploading`에 영구 고착.

**영향:** 확인된 고착 레코드 11건(`recEl21XwVS1fQMLM, recDe7zuva9DU4Kpo, recRXuRK8M9LhksKs, rech2WtIaNBv6QAh3, recK5BOXjGQbWszDG, recZgm5co4xrhR61v, reca9Xztuir5D6Fbg, recknmIxozEIhpmfn, recrma9TOOVYQ9zX7, rec2FFjFQRikBf3xs, recuqN2wQu6bFNzDp`). 운영 상태 왜곡(`uploading`으로 표시되나 실제로는 실패 확정) — 향후 자동 정합성 로직(예: n8n 게이트)이 이 상태값을 신뢰할 수 없게 됨.

**근본 원인:** `launcher/main.py:328` → `airtable_repository.py:404-416` `mark_post_result()`의 `error_code` 필드 write. 상세는 ERR-075 참조.

**진행 상황:** 260723 read-only 감사로 근본원인 Confirmed, HIGH Risk로 등록(ERR-075/FP-057). 코드 수정은 미실행 — 별도 승인 대상.

**해결:** 미적용 — ERR-075에 기록된 "향후 수정 Gate" 충족 후 별도 승인 받아 진행 예정.

**재발 방지:** FP-057 참조.

**관련:** ERR-075, ERR-041(2026-06-16 원본 사건, 필드명만 다른 동일 클래스), FP-057

---

## INC-044 | 7-C Token 교체 당일 오후 자동화 전면 중단 — 단기 토큰 만료로 DM/댓글 API 약 1시간 실패 (RESOLVED, 260725)

**발생:** 2026-07-25 15:39 ~ 16:31(약 52분간). ERR-079 참조.

**요약:** 오전 ERR-077 해소 과정에서 저장한 신규 토큰이 장기 교환 없이 사용돼 오후에 만료, `ig_auto_reply`/`comment_poller` 등 IG Graph API 호출 전면 실패.

**영향:** DM 자동응답·댓글 폴링이 약 1시간 동작 불능. 실제 손님 영향은 낮음으로 추정(같은 날 확인된 DM/댓글 트래픽 대부분이 테스트 데이터, [[project_kpi_collector_limitations_260725]] 참조) — 다만 이 시간대 실제 문의가 있었다면 응답을 못 받았을 가능성은 배제 못 함(로그상 실제 손님 문의 여부는 미확인).

**해결:** Access Token Debugger로 장기 토큰 재발급, `.env` 교체, 서비스 재시작(회장 관리자 권한), read-only 재검증 완료.

**재발 방지:** FP-061 참조.

**관련:** ERR-079, FP-061, ERR-077, INC-043

---

## INC-045 | 리드 전환 기록이 코드 결함으로 장기간 유실 (RESOLVED, 260725, 유실 시작 시점 미상)

**발생:** 발견 2026-07-25. 최초 도입 시점은 UNKNOWN — `mark_lead_converted()`/`converted_at` PATCH 로직 도입 시점부터 존재했을 것으로 추정되나 git blame 등 확인 안 함.

**요약:** 실제 주문/전환이 감지돼도(`order_detector.handle_order_conversion()` 호출 자체는 발생) Airtable 기록이 매번 실패해 `lead_status`가 `converted`로 남은 적이 한 번도 없었을 가능성. 10단계 KPI 실측에서 "전환 0건"으로 관찰된 현상의 실제 원인일 가능성이 높음(확정은 아님 — 실제 트래픽 자체도 희박했던 정황과 겹쳐 있어 두 요인이 혼재).

**영향:** 매출/전환 관련 KPI가 시스템 도입 이후 신뢰할 수 없는 상태였을 가능성. 금전적 손실 여부는 확인 불가(애초에 실제 손님 전환이 있었는지 자체가 불명 — [[project_kpi_collector_limitations_260725]] 참조).

**해결:** ERR-080 참조 — 필드 추가로 해소, 향후 발생하는 전환부터 정상 기록될 것으로 기대.

**재발 방지:** FP-057 참조.

**관련:** ERR-080, FP-057, [[project_kpi_collector_limitations_260725]]

---

## INC-043 | yuna18253 Instagram 게시 경로 일시 중단 — 잘못된 플로우로 재발급된 토큰 저장 구간 (RESOLVED, 260725)

**발생:** 260725, 7-C Token 교체(GPT 확정 1순위 과제) 진행 중. 최초 재발급 토큰(IGAA, ERR-077 원인) 저장 + `SNS_Watchdog` 재시작(1차) 이후부터, Graph API Explorer로 정식 EAA 토큰 재발급 + 재저장 + 재시작(2차) 완료 시점까지의 구간.

**요약:** `yuna18253` 계정의 `INSTA_ACCESS_TOKEN`이 `graph.facebook.com`과 호환되지 않는 포맷(`IGAA`)으로 교체된 채 서비스가 재시작되어, 이 구간 동안 해당 계정의 실제 게시 시도는 전부 `OAuthException 190`으로 실패했을 것(fail-closed, `failed` 상태로 안전 종료 — 코드 설계 의도대로 동작).

**영향:** 실제 예약 게시 시도가 이 구간에 있었는지는 미조회(UNKNOWN). 중복게시·데이터손상은 발생하지 않음(설계상 안전). 회장이 직접 발견(read-only GET 검증 요청)해 같은 세션 내 신속 정정.

**해결:** Graph API Explorer의 Page Access Token 경로로 재발급, `.env` 재교체, 서비스 재시작(회장 관리자 권한), read-only GET 재검증(HTTP 200, id/username 기존과 일치)으로 종결.

**재발 방지:** FP-059 참조.

**관련:** ERR-077, FP-059

---

## INC-046 | aijomoojin 6F Canary — #1·#2·#3 전부 게시 성공, ERR-101/102 해소 (RESOLVED, 3/3)

**발생:** 2026-08-03 15:18:09~15:55:08 ICT.

**요약:** 승인된 Canary 1회는 Gemini·이미지·ImgBB 성공 뒤 `runtime_boot_policy.json` PermissionError로 Airtable POST 전에 종료됐다. 사용자 `실행하라` 승인 후 Codex가 기존 산출물로 Airtable Record `recfFdfTkJoKk4biu`를 1회 생성했다. 첫 Scheduler tick에서 `AI_CONTENT_LANGUAGE_MISMATCH` 발생 — 원인은 UNKNOWN, 사용자 `수정승인` 후 동일 Record의 caption과 `ready` 상태를 복구했다. 다음 tick은 Gemini HTTP 503을 `AI_CONTENT_SAFETY_BLOCKED`로 오분류해 다시 `rejected` 처리했다. 사용자 `503 재시도 승인` 후 동일 Record만 `ready`로 복구했으며 기존 Scheduler의 15:51 tick이 15:51:56 Instagram `ig_media_id=17976679115901401`로 1회 게시했다.

**최종 Evidence:** Airtable 최종 GET에서 `recfFdfTkJoKk4biu=posted`, source URL·image URL·media ID 중 하나라도 일치하는 Record 총 1건. Canary 재실행 0회, 수동 Scheduler/Meta trigger 0회, 중복 Record·중복 media ID 0건, 추적 파일 변경 0건.

**영향:** #1/3은 최종 SUCCESS. 다만 자동 복구가 아닌 승인된 수동 Record 생성/상태 복구가 필요했고, ERR-101·ERR-102가 #2/3 차단 결함으로 남았다.

**후속 해결:** ERR-101은 Commit `b98afa1`, ERR-102는 Commit `09f03c0`으로 수정·Push·Production 적용했다. #2/3은 `content_id=3-5-260803-54c5b2e9`, Airtable `recDFi8IWZ8qXeEOz`, Instagram `18109337171018360`으로 기존 Scheduler가 1회 게시했고 중복 0건이다.

**#3/3 최초 시도 중단(20:19:52~20:21:28):** Source 3.6(NIST AI RMF 1.0)을 추가하고 Source Target Test 10/10 PASS 후 Canary를 정확히 1회 실행했다. Gemini Caption이 HTTP 503 4/4 소진 후 `CAPTION_GENERATION_FAILED`로 fail-closed 종료했다. 예정 `content_id=3-6-260803-54dbc154`; Vault·ImgBB·Airtable·Meta 부분상태 0건, ready/uploading 0건, 이미지 사용량 2/3. 재실행·수동복구는 하지 않았다.

**#3/3 완료(260804, 세션 인계 후):** 인계 시점 재확인 결과 Vault md/png·ImgBB `image_url`은 이미 정상 생성돼 있었고(`content_id=3-6-260804-54dbc154`, Airtable `rechmKYrCZx4e0RGt`, `post_status=failed`), `fetch_pending_posts()` 자동픽업 조건(계정·classification·canary_run_id)은 이미 전부 충족돼 있었다. 신규 Caption·이미지·Record 생성 없이 승인된 Airtable Write 1건(`post_status: failed→ready`)만 실행 — 약 5.5분 후 기존 APScheduler(`_job_insta_upload`)가 자동 픽업해 `posted` 전이, `ig_media_id=17895314160577781` 확보. 수동 Meta 게시 0건, 동일 media_id·image_url 각 1건씩만 존재(중복 0건).

**현재 해결 상태:** ERR-101/ERR-102는 RESOLVED. **6F 전체 3/3 SUCCESS로 종결**. 다음 단계는 6G(정식 운영 전환) — 회장 원칙 승인 완료, 실제 설계·구현은 별도 세션.

**관련:** ERR-101, ERR-102, FP-073, FP-074

---

## INC-047 | Track B 7A 배포 직후 첫 실사용 09:00 ICT aijomoojin Producer 슬롯이 머신 Sleep으로 완전 미실행 (MITIGATION APPLIED, 16:00 슬롯 재발 없음 확인)

**발생:** 2026-08-05 08:50:55~09:07:04 ICT(Windows Sleep 구간), 인지 시각 09:07:31(APScheduler misfire 로그) / 09:08 회장 확인 요청.

**요약:** 같은 날 08:29 `Restart-Service SNS_Watchdog`로 `AIJOMOOJIN_CONTENT_PRODUCER_ENABLED=true`를 Runtime에 반영(7A DEPLOYED)한 뒤, 첫 실사용 대상이던 09:00 ICT Producer 슬롯이 예상했던 Gemini 429가 아니라 머신이 08:50:55~09:07:04 사이 Sleep 상태였던 탓에 실행 자체가 발생하지 못했다. `misfire_grace_time=60`초를 초과해 익일(2026-08-06 09:00)로 재등록됐고, Producer뿐 아니라 그 시각 등록된 모든 Job(heartbeat/insta_upload/fb_crawl/DM followup 등)이 동일하게 정지했다.

**최종 Evidence:** `app.log` 08:56:03~09:07:26 전 Job 공통 로그 공백, `Get-WinEvent`(`Microsoft-Windows-Kernel-Power`) Sleep 진입 08:50:55(Event 506)·Wake 09:07:04(Event 507), APScheduler misfire 로그(09:07:31, `was missed by 0:07:31.405416`, next run 익일 재등록). Airtable pending/ready·Vault 파일·imgbb 업로드 등 부분상태 0건(실행이 시작조차 못 해 오염 없음).

**영향:** 오늘(2026-08-05) 하루 목표 3건 중 09:00 슬롯 1건 손실 확정(Catch-up 없음, 설계대로).

**후속 조치:** ERR-103(현상 기록) · FP-075(반복패턴 기록) 작성 완료. 근본원인을 공식 Microsoft 문서("Adaptive Hibernate / Standby Battery Budget", DC 전용 명시되어 있으나 이 머신은 AC 상시연결 상태에서도 발동한 것으로 확인된 문서-실동작 불일치)와 대조해 특정했다. 회장이 260805 10:18 ICT 관리자 PowerShell에서 `powercfg /hibernate off` 실행, `powercfg /a` Read-only 재확인으로 Hibernate 비활성화를 확인했다.

**16:00 슬롯 재검증 결과(260805 16:00~16:01 ICT):** `_job_aijomoojin_content_producer` 정각 실행(misfire 없음), 10:18 조치 이후 지금까지 `Get-WinEvent`(Kernel-Power 506/507/42) Sleep 이벤트 재발 0건 — 완화조치 유효성 1차 확인. 다만 해당 슬롯은 Gemini 429(aijomoojin 전용 quota 소진, 별개 Blocker)로 Fail-closed 종료돼 `ready` 생성에는 이르지 못함 — 오늘 3슬롯 중 실제 콘텐츠 생성 성공 0건.

**Status:** Sleep 재발 방지는 1회 관측 주기 기준 유효 확인, 완전 RESOLVED 판정은 추가 관측(내일 05·09·16 ICT) 이후로 보류.

**관련:** ERR-103, FP-075
