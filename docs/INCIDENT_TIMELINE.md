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
