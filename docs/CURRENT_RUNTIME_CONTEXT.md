# CURRENT_RUNTIME_CONTEXT.md
_마지막 업데이트: 260624_직접호출_완전교체_inquiry_message_갭_해소_

## 현재 단계
**260624 Infrastructure 외부 직접 호출 실질적 0건 확정** — 잔존 4파일(account_manager / facebook_crawler / source_exporter / domeggook_ingest) Repository 교체 완료 / TrainingRepository 신규 생성 / save_to_airtable NameError 수정 / inquiry_message 데이터 갭 해소 / airtable_autorun_engine.py dead 파일 확인(import 없음)

## 최종 확인 커밋
36cbf05 (fix: inquiry_message 데이터 갭 해소 [260624])

## Source of Truth
- Runtime: C:\SNS_24AutoProject_260511
- Archive: C:\SNS_24AutoProject_250723 (삭제/dead 판정 금지)

## 마지막 확인 커밋 체인
- 9cc4ee9 (feat: CRAWL_TARGET_SOURCE Feature Flag — Airtable crawl_urls 동적 로드 [260619])
- 9d65cb4 (refactor: publish_single() 분리 — APScheduler/n8n 공용 게시 함수 [260617])
- 20bef95 (fix: last_error_msg L191 잔존 참조 제거 [260616])
- 463c350 (fix: retry_count/last_error_msg 필드 제거 + Graph API 실패 로깅 보강 [260616])
- 25c6779 (fix: image_url_hash FB CDN 중복 감지 개선 — URL 전체 대신 미디어ID 추출 [260616])
- 366c617 (fix: facebook_crawler import re 누락 추가 [260616])
- a126754 (fix: IMAGE_BLOCK_KEYWORDS에 M&Y GLOBAL 워터마크 패턴 추가 [260616])
- 0688849 (fix: clean_fb_metadata 호출 추가 — FB UI 잔여물 제거 [260616])

## Runtime 상태 (260622 기준)
| 구간 | 상태 | 근거 |
|---|---|---|
| Flask (dm_receiver) | ✅ LIVE | :5000 확인 |
| launcher/main.py | ✅ LIVE | watchdog.ps1 기동 중 |
| ngrok | ✅ LIVE | :4040 확인 |
| Streamlit | ✅ LIVE | :8501 확인 |
| n8n | ⚠️ 미설정 | 정상 — 아직 구성 안 함 |

## Dual Scheduler 해소 (260527)
| 항목 | Before | After |
|---|---|---|
| process_due_followups 실행 횟수/5분 | 2회 (27초 간격) | 1회 |
| :5000 바인딩 수 | 2 (watchdog Start-Flask + launcher) | 1 (launcher만) |
| watchdog.ps1 Start-Flask | ACTIVE | 주석 처리 완료 |
| 근거 | app.log 22:00:34 / 22:05:34 단일 실행 2사이클 확인 | ERR-021 / FP-017 / INC-011 |

## E2E AutoReply 증거
| 증거 | 상태 | 내용 |
|---|---|---|
| 화면 증거 | ✅ CONFIRMED | "단가 기준가는 11,000원" (5/12) |
| 로그 증거 | ❌ LOST | overwrite 구조로 소멸 |
| 코드 경로 | ✅ CONFIRMED | get_base_price() → Airtable → 응답 정상 |

## 250723 스캔 결과
- 전체 스캔 완료
- 이식 대상 없음 확정
- pytest: 613 passed / 17 failed / 6 errors — Green Build 아님
- 역할: Archive / Evidence 참고용만

## Known Fact
- DEFAULT_BASE_PRICE=50000 .env 설정 확인
- dual scheduler 중복 발송 → **260527 해소 완료** (watchdog.ps1 Start-Flask 주석 처리)
- webhook_stderr.log overwrite 구조 확인됨
- Windows venv shim: .venv\Scripts\python.exe(268KB) → Python310\python.exe(103KB) 자식 프로세스 — 2 PID 정상 (1 논리 인스턴스)
- 중복 발송 버그 → **260528 해소 완료** (_has_recent_auto_replied() CREATED_TIME() 기준 3분 window)
- _rule.reason AttributeError → **260528 해소 완료** (getattr fallback)
- SNS_Watchdog_AutoStart 작업 스케줄러 등록 → ✅ **등록 완료** (260529 관리자 권한으로 등록)
- accounts.json 빈 배열 → crawl_urls skip → **260529 해소 완료** (account1 + crawl_url 등록)
- Airtable caption 필드 없음 → 422 UNKNOWN_FIELD_NAME → **260529 해소** → **260612 재발 → 재해소** (API로 multilineText 필드 추가, field_id=fldcxTzLzYCzD9aYe)
- FB 크롤러 2회 연속 정상 완료 → **260529 19:43 / 20:13 확인**
- crawl_urls 4개 그룹 확장 → **260602 완료** (3dbe72a)
- accounts.json BOM 제거 → **260602 완료** (c6a30d1) — PowerShell Set-Content UTF8 금지
- facebook_crawler.py load_dotenv 추가 → **260602 완료** (f5d59f2)
- pytest 104 passed / 1 xfailed / 2 xpassed 확인 (260602)
- deep-translator 1.11.4 설치 완료 (260602)
- 시스템 환경변수 AIRTABLE_API_KEY 플레이스홀더(`pat여기에전체토큰`) → **260602 제거 완료** (User scope + 세션 제거)
- bot_uploader.py → insta_uploader.py 체인: **dead stub 확인** — 실제 Graph API 호출 없음, launcher/main.py가 실제 업로더
- caption clean_fb_metadata() → **260602 완료** (349fedf) — 작성자명·경과시간·구분점(·) 제거
- Airtable ready 레코드 caption 오염 일괄 정정 → **260602 완료** (2건: recKLX1OsOvfRu5k1, recsmA4WIlrur1wHO)
- Instagram 업로드 Runtime Proof → **260602 완료** — recFyw7OUaZ666JDJ / ig_media_id=18101360630320704 / post_status=posted ✅
- 백업 완료: C:\backup_(12)_260602_2207_SNS_24AutoProject_260511.zip
- 최종 commit: 2695d87
- Supplier_Blocklist 실제 차단 적용 → **260611 완료** (11fc204) — DRY_RUN 제거, continue 적용
- LOST 72h 타임아웃 구현 → **260611 완료** (0e5133b) — DRY_RUN 모드, 실운영은 LOST_DRY_RUN=false 설정 후 활성화
- Lead_Interactions lost_reason / lost_at / disqualified 필드 추가 → **260611 완료** (Airtable UI)
- filter_rules.json + generate_filter_rules.py 추가 → **260611 완료** (3840a6a) — 운영 연동 금지, 분석용 전용
- FB그룹 1676627532598134 제거 → **260612 완료** (c71f2c7) — 인도 비율 높음, accounts.json + Crawl_Targets 동시 삭제
- ig_media_id 17863634121631171 클리어 → **260612 완료** — rectwruMD3uua54sv, engagement_tracker 반복 오류 해소
- crawl_urls 현재 5개 운영 중 (FB_GROUP_POOL_V1): 610113703703488(Hold) / 345179878828208 / 755455243345993 / 3289570041331131 / 1827528710833477
- upload_rate 6.2% → caption 필드 복구로 다음 크롤링부터 회복 예상 (260612)
- post_status ready/uploading 옵션 소실 → **260616 해소** (typecast 더미 레코드 방식으로 강제 복구)
- uploading 고착 28건 (Regine Kim 포스트 동일 이미지) → **260616 failed 일괄 마킹** (200 OK 전부)
- retry_count/last_error_msg UNKNOWN_FIELD_NAME → **260616 해소** (463c350 — 두 필드 코드에서 제거)
- image_url_hash URL 전체 해시 → CDN 노드 달라 중복 미탐지 → **260616 해소** (25c6779 — FB 미디어 ID 추출로 변경)
- import re 누락 → [FB Crawler] 크롤링 실패 | name 're' is not defined → **260616 해소** (366c617)
- Instagram 업로드 성공 → **260616 02:07 KST 확인** | recw3EHD8d9uiP2FX | post_id=18122871268709171 ✅
- M&Y GLOBAL / Mooncher Kim Supplier_Blocklist 등록 → **260616 완료** | recEDhkour93vZR74 | reason_code=BLOCK_WATERMARK_SUPPLIER
- _IMAGE_BLOCK_KEYWORDS에 `r'm&y\s*global'` 추가 → **260616 완료** (a126754)
- `clean_fb_metadata()` facebook_crawler.py L202 호출 추가 → **260616 완료** (0688849) — raw_text 추출 직후 작성자명·경과시간 제거
- `modules/sns/image_hosting.py` 신규 추가 → **260616 완료** — imgbb 업로드 유틸 (다운로드→MIME검증→SHA256→업로드→URL검증)
- `publish_single()` 분리 → **260617 완료** (9d65cb4) — launcher/main.py 게시 로직 독립 함수화, APScheduler + n8n Endpoint 공용 호출 가능
- `last_error_msg` L191 잔존 참조 제거 → **260616/17 완료** (20bef95)
- n8n Architecture 설계 → **260617 확정** (DESIGN_COMPLETE) — WF-01 Posting Scheduler / WF-02 DM Webhook / WF-03 Credential Health / WF-04 Failure Recovery / WF-05 Runtime Alert
- Credential 구조 Option B 확정 — Python이 Graph API Token 소유 (.env CRED_{ref}_TOKEN), n8n Token 비보유
- Canonical Status: post_status 단일 사용 (publish_status 미사용)
- `execution_owner` 필드 — **미구현 (P0 Backlog)**
- FB_MAX_POSTS=20 .env 설정 완료 (260619)
- Crawl_Targets 스키마 확장: platform/max_posts/account_ref/last_run_at/last_result 필드 추가 (260619)
- account_manager.py _load_crawl_urls_from_airtable() + _shadow_compare() 추가 (260619) — 9cc4ee9
- CRAWL_TARGET_SOURCE Feature Flag 구현 (260619): accounts_json(기본)/shadow(비교 로그)/airtable(URL 교체)
- Shadow 모드 검증 완료 (260619): accounts.json=5건 vs Airtable=4건, 누락 그룹 610113703703488 감지
- CRAWL_TARGET_SOURCE=airtable 전환 → Airtable 4건 URL 기반 크롤링 Runtime Proof 완료 (260619)
- accounts.json: 계정/세션 정보 전용 유지 / crawl_urls: Airtable Crawl_Targets 단일 소스 (260619)

## 미해결 항목 (Phase 후순위)
- **[P0 — 다음 세션]** Instagram_Posts.execution_owner 필드 Airtable 추가
- **[P0 — 다음 세션]** APScheduler 조회 조건 수정: post_status=ready AND execution_owner 없음
- **[P0 — 다음 세션]** /api/v1/instagram/publish Endpoint 구현 (modules/sns/instagram_publish_api.py)
- **[P0 — 다음 세션]** DRY_RUN 검증 (PUBLISH_API_DRY_RUN=true → false 전환)
- **[P0 — 다음 세션]** 테스트용 Record 1건 생성 후 실제 게시 Runtime Proof
- 그룹 610113703703488: div[role='feed'] 미탐지 — 가입 승인 대기 중 (코드 문제 아님)
- LOST_DRY_RUN=false 전환 대기 — 실운영 전 Airtable 필드 확인 후 적용
- 워터마크 제외 로직 — **260616 부분 구현** (_IMAGE_BLOCK_KEYWORDS + Supplier_Blocklist 등록), passes_image_filter 이미지 픽셀 분석 미구현
- data/processed_comment_ids.json untracked 유지 (정상 — gitignore 대상)
- 백업 필요 시점 도달 (마지막 백업: backup_(12)_260602_2207)
- **[P1 — 다음 세션]** 도매꾹(domeggook) 크롤러 추가 — Crawl_Targets platform=domeggook 지원

## 절대 금지
- 250723 삭제/dead 판정
- 폴더 merge/전체 복사
- Evidence 없는 완료 선언
- 코드 수정 (승인 전)
- git add/commit 선행
- PowerShell Set-Content -Encoding UTF8 로 JSON 파일 저장 (BOM 삽입됨 — [System.IO.File]::WriteAllText + UTF8Encoding(false) 사용)

## [260528_Virtual_AutoReply_Proof] — 2026-05-28 13:27 KST
- Infra: Flask :5000 PID 14256 + ngrok :4040 PID 8956 LISTENING 확인
- Webhook: 로컬 POST 200 OK 확인
- Parser: 단가 얼마예요? detect_price_inquiry=True 확인
- AutoReply: DEFAULT_BASE_PRICE=50000 적용, handle_price_inquiry 완료
- Airtable: LI-2B0A72F7 생성, recXgM9FlDo9EEikr qualified/auto_replied
- IG 발송 실패: TEST_SENDER_004 가상 ID 정상 예상 결과
- 백업: backup_(7)_260528_1338 완료

## [260528_Real_DM_AutoReply_Proof] — 2026-05-28 20:14 KST
- 실계정 IGSID: 1792783944739953
- IG DM 발송 완료: 20:14:37 msg_id 확인 (recKh3tm6R5foxjjv)
- Lead 상태: qualified / auto_replied
- Telegram 알림: 성공 (1회 ConnectionReset 후 복구)

## [260528_Duplicate_Bug_Fix] — 2026-05-28 21:42 KST
- 버그1: _rule.reason AttributeError → getattr(_rule, "reason", "unknown") 수정
- 버그2: 중복 발송 → _has_recent_auto_replied() 추가 (CREATED_TIME() 기준 3분 window)
- 검증: 21:42:15 duplicate skip recvpUz9Q6YW4EsPv ✅
- 검증: 21:50:03 duplicate skip recKeIWfh5YtBLhzo ✅
- 수정 파일: modules/dm/dm_auto_reply.py ✅ 72e0e1a 커밋 완료

## [260529_Crawler_Normalization] — 2026-05-29 KST
- ERR-027: accounts.json `[]` → crawl_urls skip → account1 등록으로 해소 (7ce335e)
- ERR-028: Airtable caption 필드 없음 → 422 → UI에서 Long text 필드 추가로 해소
- 검증: 19:43:40 `계정 완료 | account=account1 | 3개` ✅
- 검증: 20:13:41 `계정 완료 | account=account1 | 3개` ✅

## [260601~260602_Clone_Mode_Proof] — 2026-06-02 01:08 KST
- Phase 1: replace_contacts() 매핑 추가 (c8000ee)
- Phase 2: generate_caption_clone() 추가 (3ed3b45)
- Phase 3: facebook_crawler clone 경로 연결 (b059740)
- Phase 4: keyword filter 확장 + BRAND_ALLOWLIST (25c3f13)
- Phase 5: comment auto-reply 안전장치 COMMENT_AUTO_REPLY_ENABLED=false (a64b0ff)
- Phase 6: expand_see_more() 추가 + Runtime Proof (deec24c)
- Runtime Proof: recsmA4WIlrur1wHO — original_text / converted_text / caption / media_type=image 전부 저장 확인 ✅
- 백업: C:\backup_(11)_260602_0108_SNS_24AutoProject_260511.zip

## [260602_섹션19_Instagram_Upload_Runtime_Proof] — 2026-06-02 16:20 KST
- 업로드 체인 분석: bot_uploader→insta_uploader dead stub 확인, 실제 업로더=launcher/main.py:159
- 환경변수 이슈: 시스템 AIRTABLE_API_KEY 플레이스홀더 → latin-1 UnicodeEncodeError → User scope 삭제 해소
- find_dotenv() 탐색 실패 원인 확인: temp 경로 실행 시 발생 — 절대경로 load_dotenv 사용으로 우회
- ERR-037 해소: caption Facebook UI 잔여물(작성자명·경과시간··) → clean_fb_metadata() 추가 (349fedf)
- Airtable ready 레코드 2건 caption 일괄 정정 완료
- **Graph API 업로드 성공 증거:**
  - 대상: recFyw7OUaZ666JDJ
  - 이미지: 960×1707 ratio=0.56 → imgbb center-crop → https://i.ibb.co/dwnMVq7Z/2547998023eb.jpg
  - /media id: 17889472404540095
  - /media_publish id (ig_media_id): **18101360630320704** ✅
  - Airtable post_status: ready → uploading → **posted** ✅

## [260602_섹션19_Clone_Mode_그룹URL_다중화] — 2026-06-02 13:40 KST
- crawl_urls 1개 → 4개 그룹 확장 (3dbe72a)
  - 1676627532598134 (K-beauty 필리핀 중고 그룹)
  - 610113703703488 (feed 셀렉터 실패 — 가입 승인 대기)
  - 345179878828208 (기존 그룹, Airtable 저장 확인 ✅)
  - 755455243345993 (신규 그룹)
- accounts.json BOM 제거 (c6a30d1) — PowerShell Set-Content UTF8 BOM 삽입 버그 수정
- facebook_crawler.py load_dotenv(override=True) 추가 (f5d59f2) — 모듈 직접 실행 시 .env 로드 보장
- Airtable 저장 성공 재확인: 그룹 345179878828208 → [AIRTABLE] 저장 완료 ✅
- pytest 104 passed / 1 xfailed / 2 xpassed ✅
- deep-translator 1.11.4 pip install 완료
- 백업 필요 시점 도달 (다음 세션 초반 백업 권장)

## [260612_운영정비] — 2026-06-12 00:26 KST
- Supplier_Blocklist 실차단 적용 (11fc204) — DRY_RUN 로그 제거, 매칭 시 continue로 실제 skip
- LOST 72h 타임아웃 구현 (0e5133b) — followup3_sent + 72h 경과 → LOST 자동 전환, DRY_RUN 모드
  - 실운영 전환 조건: .env LOST_DRY_RUN=false 설정
- Lead_Interactions 필드 추가: lost_reason(Single line) / lost_at(Date) / disqualified(Checkbox)
- filter_rules.json + generate_filter_rules.py (3840a6a) — Crawl_Training_Set 기반 분석 전용, 운영 연동 금지
- FB그룹 1676627532598134 제거 (c71f2c7) — Crawl_Targets 레코드 삭제 + accounts.json crawl_urls 제거
  - 사유: 인도 트래픽 비율 높음, K-beauty 타겟 부적합
  - crawl_urls 5개 → 5개 유지 (610113703703488 Hold 포함)
- Instagram_Posts.caption 필드 재추가 — API로 multilineText 추가 (fldcxTzLzYCzD9aYe), 422 오류 해소
  - 원인: 260529 UI 추가 후 어느 시점 삭제됨
- ig_media_id 17863634121631171 클리어 (rectwruMD3uua54sv) — engagement_tracker 30분 간격 반복 오류 해소
- launcher/main.py 기동 확인 (00:26 KST) — Flask :5000 / APScheduler 8잡 / RetryQueue 정상
  - AdsPower 미실행으로 FB 크롤링 WinError 10061 (AdsPower 기동 후 자동 복구)
- upload_rate 6.2% — caption 필드 복구로 다음 크롤링부터 ready 레코드 누적 회복 예상
- 최신 커밋: 0688849 / GitHub push 완료

## [260616_운영정비_2차] — 2026-06-16 23:00 KST
- M&Y GLOBAL 워터마크 공급자 차단:
  - Supplier_Blocklist 등록: author_name=Mooncher Kim / page_name=M&Y GLOBAL / reason_code=BLOCK_WATERMARK_SUPPLIER (recEDhkour93vZR74)
  - content_filter._IMAGE_BLOCK_KEYWORDS에 `r'm&y\s*global'` 추가 (a126754)
- `facebook_crawler.py`에 `clean_fb_metadata()` 호출 추가 (0688849):
  - raw_text 추출 직후 L202에서 clean_fb_metadata(raw_text) 호출
  - 작성자명·경과시간·구분점(·) 제거 후 필터링 → 오탐 방지
  - import L14에 clean_fb_metadata 추가
- `modules/sns/image_hosting.py` 신규 생성 (BOM없음, 54줄):
  - upload_to_imgbb(source_url) — imgbb API 래퍼
  - MIME 검증 / 32MB 제한 / SHA256 content_hash / HEAD 공개 URL 검증
  - 향후 launcher/main.py _preprocess_image() 대체 후보
- Blocklist 로드 완료: 5건 (M&Y GLOBAL 추가 후 확인)
- Regine Kim 포스트 A-F3-260616-001 업로드 성공 → posted 확인 ✅
- 런처 재기동: 23:00 KST (clean_fb_metadata 적용 버전)

## [260616_버그수정] — 2026-06-16 02:07 KST
- post_status 옵션 소실 (ready/uploading 없음) → Airtable Meta API PATCH 422 → typecast:True 더미 레코드 방식으로 강제 복구
  - 복구 후 옵션 목록: ['draft', 'scheduled', 'posted', 'failed', 'ready', 'uploading'] ✅
- uploading 고착 28건 일괄 마킹:
  - 원인①: FB CDN 동일 이미지를 다른 노드(fhan15-2, fdad3-8, fhan5-6)로 서빙 → URL 해시 달라 중복 28건 저장
  - 원인②: Graph API 업로드 실패 후 retry_count UNKNOWN_FIELD_NAME 예외 → uploading 고착
  - 조치: 28건 전체 post_status=failed PATCH 완료 (200 OK)
- retry_count/last_error_msg 필드 제거 (463c350):
  - launcher/main.py 성공/실패 경로 양쪽에서 두 필드 참조 제거
  - 실패 에러 내용은 logger.error로 직접 출력으로 대체
- image_url_hash 개선 (25c6779):
  - Before: `hashlib.sha256(image_url.encode())` — CDN 노드 다르면 다른 해시
  - After: `re.search(r"/(\d+_\d+(?:_\d+)*)[_.]", image_url)` → FB 미디어 ID 추출 후 해시
  - 검증: 3개 CDN URL → 동일 미디어 ID → 동일 해시 ✅
- import re 추가 (366c617): facebook_crawler.py 상단 `import re` 누락 수정
- Instagram 업로드 성공 증거:
  - 대상: recw3EHD8d9uiP2FX
  - /media_publish id (ig_media_id): **18122871268709171** ✅
  - Airtable post_status: ready → uploading → **posted** ✅
- 최신 커밋: 366c617 / GitHub push 완료
## [260617] Airtable Account DB 구축 완료

### 변경사항
- Account_Registry 필드 추가: identity_id / category / automation_enabled / pilot_wave / identity_status / adspower_profile_id
- 유효 계정 33개 확정 (중복/빈행 정리 완료)
- Platform_Accounts 테이블 신규 생성 (tblkdk5dEagfQvUMp)
- Instagram 19개 + Facebook 12개 = 31개 입력
- Instagram_Posts 라우팅 필드 추가: target_identity_id / target_platform_account_id / publish_status / run_id / scheduled_at
- Account_Registry <-> Platform_Accounts Linked Record 연결 (fldcRdC6XdGnMILqI)
- Pilot 3개 Active: IDN-000036(nguyenknv15) / IDN-000038(nhm880808) / IDN-000016(kang88jungmin)

### Airtable 현재 상태
- Base ID: apphJNTHWNoFcVb1D
- Account_Registry: 33개 (Active 3 / Ready 30)
- Platform_Accounts: 31개

### 다음 단계
- n8n 워크플로우 설계 (별도 세션)
- Pilot 3개 Runtime 포스팅 검증
- 3 -> 10 -> 33개 확장


## [260617] ImgBB 연동 + 데이터 정합성 복구 세션

### 완료 작업
1. Dashboard 복구 — Flask :5000 / Streamlit :8501 / watchdog 정상 기동
2. Instagram 업로드 실패 원인 확정 — Facebook CDN URL -> Instagram Graph API error_subcode 2207052
3. imgbb 연동 (Phase 1~4)
   - original_image_url 필드 추가 (fldEpMV0uFiWR7OmB)
   - IMGBB_API_KEY .env 추가
   - modules/sns/image_hosting.py 신규 생성
   - tools/backfill_failed_images.py 신규 생성 (DRY_RUN=true 기본값)
4. Backfill 1건 End-to-End 실증 — rec2v96YaBLQJvLyl: failed->ready->posted (ig_media_id: 18071004683495931)
5. 데이터 정합성 복구
   - ig_media_id 있는 failed 78건 Graph API 검증
   - VERIFIED_POSTED 3건 -> posted 복구
   - INVALID 75건 -> ig_media_id 클리어
6. 버그 수정 — launcher/main.py: unverified ig_media_id -> posted 강제전환 제거 (commit e33cf37)
7. Phase 4 — facebook_crawler.py save_to_airtable()에 imgbb 업로드 연동 (commit af85d3a)

### 현재 Airtable 상태
- failed: 145건 / posted: 14건 / ready: 0건
- 성공률: 6.2% -> 8.2% 개선

### Git 커밋 (260617 세션)
- e33cf37: fix: prevent unverified ig_media_id from forcing posted status
- 3b3fedf: feat: add ImgBB image hosting adapter
- 6ab2ff0: feat: add guarded failed-image backfill utility
- af85d3a: feat: integrate ImgBB upload in save_to_airtable (Phase4)

### 미완료
- Runtime Proof: 신규 크롤링 1건 ImgBB 성공 로그 확인 (진행 중)
- failed 145건 backfill (Phase 3 보류)
- push 미실행 (별도 승인 필요)
- 안정화 후 API 키 재발급 필요 (AIRTABLE/INSTA/GEMINI/TELEGRAM/SLACK/IMGBB)

## [260617_n8n설계_publish_single분리] — 2026-06-17 KST

### publish_single() 분리 (9d65cb4)
- launcher/main.py 게시 로직을 publish_single() 독립 함수로 분리
- _job_insta_upload(): uploading 마킹 후 publish_single() 1줄 위임
- n8n Endpoint와 APScheduler 공통 호출 가능 구조 확보
- Token/ig_user_id 호출자 주입, 함수 내 저장소 참조 없음, 로그 access_token 출력 금지
- Runtime Proof: NOT_EXECUTED (260617 기준 ready 레코드 0건)

### last_error_msg L191 잔존 참조 제거 (20bef95)
- launcher/main.py L191 image_url 없음 조기 실패 경로에서 last_error_msg 제거
- ERR-041 완전 해소

### n8n Architecture 설계 확정 (DESIGN_COMPLETE)
- WF-01: Posting Scheduler — Airtable ready 레코드 폴링 → /api/v1/instagram/publish 호출
- WF-02: Real-time DM Webhook — Meta Webhook → Python dm_receiver 처리
- WF-03: Credential Health Check — 계정 토큰 주기적 검증
- WF-04: Failure/Recovery Watchdog — failed 레코드 재시도 조율
- WF-05: Runtime Alert — 오류/비정상 감지 → Slack 알림
- Credential 구조 Option B 확정: Python Graph API Token 소유 (.env CRED_{ref}_TOKEN), n8n Token 비보유
- Canonical Status: post_status 단일 (publish_status 신규 필드 미사용)

### P0 Backlog (다음 세션)
1. Instagram_Posts.execution_owner 필드 Airtable 추가
2. APScheduler _job_insta_upload() 조회 조건 수정
3. modules/sns/instagram_publish_api.py — /api/v1/instagram/publish Blueprint 구현
4. dm_receiver.py Blueprint 등록
5. PUBLISH_API_DRY_RUN=true 검증 → false 전환
6. 테스트용 Record 1건 생성 → 실제 게시 Runtime Proof

## [260619_Airtable_crawl_urls_전환] — 2026-06-19 KST

### 완료 작업
1. FB_MAX_POSTS=20 .env 설정 완료
2. Crawl_Targets 스키마 확장: platform(singleSelect)/max_posts(number)/account_ref(singleLineText)/last_run_at(dateTime)/last_result(singleLineText) 필드 추가 (Airtable Metadata API)
3. account_manager.py _load_crawl_urls_from_airtable() + _shadow_compare() 추가
4. CRAWL_TARGET_SOURCE Feature Flag 구현: accounts_json(기본) / shadow(비교 로그) / airtable(URL 교체)
5. Shadow 모드 검증: accounts.json=5건 / Airtable=4건 / 누락 그룹(610113703703488 Hold) 정상 감지
6. CRAWL_TARGET_SOURCE=airtable 전환 — Airtable 4건 URL 기반 크롤링 Runtime Proof 완료
   - groups/1827528710833477 → 1건 수집 (720×1280, imgbb 중복 skip 정상)
7. accounts.json → 계정/세션 정보 전용 유지 / crawl_urls → Airtable Crawl_Targets 단일 소스

### Git
- 커밋: 9cc4ee9 (feat: CRAWL_TARGET_SOURCE Feature Flag — Airtable crawl_urls 동적 로드 [260619])
- push: origin/master 완료

### 다음 세션 예정
- 도매꾹(domeggook) 크롤러 추가 — Crawl_Targets platform=domeggook 지원

## [260619_도매꾹크롤러] — 2026-06-19 KST (세션2)

### 완료 작업
1. 도매꾹 Open API 개통 확인 (ver=4.1, aid=DOMEGGOOK_API_KEY, om=json)
2. modules/crawlers/ 패키지 신설
   - base_connector.py — BaseCrawlConnector ABC + ConnectorError
   - domeggook_api_connector.py — DomeggookApiConnector (health_check/fetch/normalize)
   - quality_gate.py — READY/ERROR/FILTERED 판정 (fixture 5/5 PASS)
3. Crawl_Targets keyword 필드 추가 (fldNhkqfOJvkCZZnp)
4. D001 레코드 Hold 등록 (recg8JU3eqL9BkMgf) — category_code 제외 (singleSelect 선택지 미등록)
5. commit 2112739 push 완료

### Known Facts
- DomeggookApiConnector.fetch(kw=화장품, max_posts=10) = 10건 정규화 성공
- NormalizedItem Contract v1.0 확정
- Crawl_Targets category_code 선택지: A/B/C/D (BEAUTY 추가 시 Airtable UI에서 직접)
- API 키 파라미터: aid= (key= 아님), mode=getItemList, ver=4.1

### P0 Backlog (다음 세션)
1. Dispatcher 연결 — APScheduler에 domeggook job 추가
2. platform=domeggook 레코드 조회 → fetch() → Gate → Source_Items 저장
3. D001 Hold → Active 전환 전 Runtime Proof 필수
4. Source_Items Airtable 테이블 설계 및 생성

### 절대 금지 (다음 세션 전)
- D001 Active 전환 금지 (Runtime Proof 전)
- 전체 2,743건 수집 금지
- FB/Instagram 코드 수정 금지

## [260619_세션3_Source_Items] — 2026-06-19 KST

### 완료 작업
1. adultOnly 파싱 버그 수정 (str->bool, f6bef6a)
2. Source_Items 테이블 생성 (tblMWJaInVHS7YfY6, 17개 필드)
3. STAGING WRITE TEST 4/4 PASS
   - 1차: INSERT=10 / 2차: SKIP=10 / 3차: UPDATE=1 / 4차: SKIP=10(복구확인)
4. D001 Hold 유지 확인
5. 절차 위반 기록: STAGING WRITE TEST 전 BOM/diff 5개 조건 Claude Code 자체 진행

### Known Facts
- Source_Items 10건 저장 (화장품 키워드, READY)
- pipeline_status=NEW, quality_status=READY 정상
- FILTERED/ERROR 항목 pipeline_status 비움 확인
- D001 recoNRhWSKTiwNeuv Hold 유지
- tools/ 임시 스크립트 untracked (commit 대상 아님)

### P0 Backlog (다음 세션)
1. _job_dome_crawl() 구현 — launcher/main.py APScheduler 등록
2. Dispatcher read-only 재확인 후 DRY_RUN
3. Scheduler 수동 1회 실행
4. D001 Hold 상태 Runtime Proof 후 Active 전환 검토
5. C003 platform=daisomall 수정 (Dispatcher 확대 전 필수)

### 절대 금지 (다음 세션 전)
- D001 Active 전환 금지
- Instagram_Posts 저장 금지
- 전체 2,743건 수집 금지
- FB/Instagram 코드 수정 금지
- Dispatcher 미승인 연결 금지

## [260619_세션4_Dispatcher] — 2026-06-19 KST

### 완료 작업
1. _job_dome_crawl() 구현 + APScheduler 등록 (d1ca290)
2. DRY_RUN: D001 Hold → Active 타겟 없음 스킵 확인
3. D001 Active 전환 → fetch=10 ready=10 Runtime Proof
4. Source_Items Upsert 정상 (중복 없음)
5. max_posts 상한 min(value, 10) 강제 적용
6. D001 Hold 복구 확인

### Known Facts
- dome_crawl job: interval 60분, next_run offset 80초
- D001 Hold 상태 — 실운영 전 별도 Active 전환 승인 필요
- Source_Items 11건 (STAGING + Runtime Proof 누적)
- C003 platform=daisomall 수정 미완료 — 다음 세션

### P0 Backlog (다음 세션)
1. C003 platform=daisomall 수정
2. D001 실운영 Active 전환 승인 후 24시간 모니터링
3. Source_Items → Instagram_Posts Export 파이프라인 설계
4. 건강식품 등 카테고리 확장 (D002 추가)

## [260619_세션5_실운영전환] — 2026-06-19 KST

### 완료 작업
1. C003 platform=daisomall 수정 완료
2. D001 Active 전환
3. launcher 재시작 → dome_crawl job 등록 확인
4. 16:47:28 자동 실행 → fetch=10 ready=10 Upsert 성공
5. 다음 실행 17:47:28 (60분 interval) 확인

### Known Facts
- dome_crawl: 60분 interval 실운영 중
- D001 Active (recoNRhWSKTiwNeuv)
- C003 platform=daisomall (Hold 유지)
- Source_Items 누적 중 (11건+)
- watchdog.ps1 백그라운드 유지

### P0 Backlog (다음 세션)
1. Source_Items → Instagram_Posts Export 파이프라인 설계
2. 건강식품 D002 추가
3. 24시간 후 Source_Items 누적 건수 확인

## [260619_세션6_ExportPipeline] — 2026-06-19 KST

### 완료 작업
1. Source_Items 필드 4개 추가 (export_retry_count/last_error/next_retry_at/started_at)
2. Instagram_Posts source_item_id 필드 추가
3. source_exporter.py 구현 + Runtime Proof (d3b6003)
   - DRY_RUN 3건 확인
   - Export 1건 성공 (domeggook:55808288)
   - 중복 재실행 exported=0 확인
4. _job_dome_export() + APScheduler 10분 interval 등록 (4bf6e74)
   - Runtime Proof exported=2 확인

### Known Facts
- dome_crawl: 60분 interval 실운영 중
- dome_export: 10분 interval 실운영 중
- D001 Active
- Source_Items → Instagram_Posts 파이프라인 완성
- STALE_QUEUED 30분 복구 로직 포함
- retry/backoff: 10분/60분/300분

### P0 Backlog (다음 세션)
1. 건강식품 D002 추가
2. 24시간 후 Source_Items/Instagram_Posts 누적 확인
3. launcher 재시작 (watchdog 통해 dome_export job 자동 등록 확인)
## [260619_세션7_실운영확인] — 2026-06-19 KST

### 완료 작업
1. launcher 재시작 → dome_crawl + dome_export 자동 등록 확인
2. D002 건강식품 Hold 등록 (recuRdoKY0KDiV7Ci)
3. 24시간 누적 확인:
   - Source_Items 21건 (EXPORTED=4 / NEW=17)
   - Instagram_Posts 도매꾹 출처 3건
   - dome_crawl 60분 / dome_export 10분 자동 실행 확인

### Known Facts
- dome_crawl: 60분 interval 실운영 중 (D001 Active)
- dome_export: 10분 interval 실운영 중
- D002 Hold (건강식품) — 다음 세션 Active 전환 검토
- Source_Items 누적 중 (10건/회)

### P0 Backlog (다음 세션)
1. D002 건강식품 Active 전환 → Runtime Proof
2. source_item_id 기준 export_to_instagram_posts target_id 확장
3. Instagram_Posts 도매꾹 출처 게시물 품질 확인

## [260622_API_Usage_Logging] — 2026-06-22 KST

### 완료 작업
1. Airtable Team 플랜 업그레이드 완료
2. Lily Yoon Supplier_Blocklist 등록 (recTMGb5XHgT8qjKJ)
   - author_name: Lily Yoon / reason_code: WATERMARK_TAG_OVERLAY
   - 근거: Crawl_Training_Set 3건 decision=BLOCK / has_watermark=True 확인
3. Instagram_Posts 160번 레코드 rejected 처리
4. modules/infra/ 패키지 신설
   - airtable_usage_logger.py — API 호출 카운트 / logs/airtable_usage.jsonl 날짜별 누적 / get_monthly_count() / 100,000회 초과 Telegram 경고
5. log_api_call() 12개 포인트 연결
   - airtable_bridge.py: fetch_ready_one(GET) / update_record(PATCH)
   - facebook_crawler.py: Supplier_Blocklist(GET) / Instagram_Posts(GET·POST)
   - launcher/main.py: Crawl_Targets(GET) / Source_Items(GET·PATCH·POST) / Instagram_Posts(GET·PATCH×3)

### Known Facts
- Airtable Usage 월 누적: 3회 (2026-06 기준, 테스트 포함)
- logs/airtable_usage.jsonl 정상 생성 확인
- content_filter.py: Airtable 직접 호출 없음 (연결 대상 아님)

### P0 Backlog (다음 세션)
1. Instagram_Posts 도매꾹 출처 게시물 품질 육안 확인
2. 카테고리 추가 검토 (D003 등)
3. 48시간 안정성 모니터링

## [260619_세션8_D002확장] — 2026-06-19 KST

### 완료 작업
1. D002 건강식품 Active 전환
2. dome_crawl D001+D002 동시 fetch=10+10 Runtime Proof
3. _job_dome_export() target_id=None / batch_size=5 확장 (7fdd9d1)
4. exported=3 (D001+D002 혼합) Gemini caption 3건 성공

### Known Facts
- dome_crawl: D001(화장품)+D002(건강식품) Active 실운영
- dome_export: target_id=None 전체 대상 / batch_size=5
- Source_Items 누적 중
- Instagram_Posts 도매꾹 출처 증가 중

### P0 Backlog (다음 세션)
1. Instagram_Posts 도매꾹 출처 게시물 품질 육안 확인
2. 카테고리 추가 검토 (D003 등)
3. 48시간 안정성 모니터링

## [260623_FB_Crawler_HUNG_해소] — 2026-06-23 14:17 KST

### Root Cause 4개 해소

| 커밋 | 분류 | 내용 |
|---|---|---|
| e648ce3 | feat | Stage Log (JOB_START/ADSPOWER/DRIVER/PAGE_GET/CRAWL/CLEANUP) + timeout hardening |
| f9b9483 | fix | SSL handshake timeout: socket.setdefaulttimeout + urllib3 adapter (효과 없음 → 다음 커밋으로 대체) |
| 1082d11 | fix | daemon thread + join(timeout=12): Windows SSL hang 포함 wall-clock 강제 종료 |
| 0878c68 | fix | **threading.Lock → RLock** — log_api_call()→get_monthly_count() 중첩 획득 deadlock 해소 (핵심 원인) |
| 56b09d1 | fix | RemoteConnection.set_timeout() 제거 — _client_config AttributeError (_job_fb_crawl 크롤링 실패) |

### Stage Log 전구간 확인 (Scheduler 자동 실행 14:17 KST)
```
JOB_START  elapsed=0.0s
Blocklist  6건 로드 완료
ADSPOWER   elapsed=1.3~1.4s
DRIVER     elapsed=2.5~4.0s  (WebDriver 연결 완료)
PAGE_GET   elapsed=16~24s
CRAWL      posts=2~3
CLEANUP    elapsed=25~32s
AdsPower Stop API 완료
→ 다음 URL 반복 (4개 URL 전체)
```

### Repository Interface (260622~260623)
- modules/infra/repository_interface.py — ABC (fetch_one/fetch_all/update/insert/delete)
- modules/infra/airtable_repository.py — AirtableRepository 구현체 (offset 페이지네이션, log_api_call 내장)
- 기존 airtable_bridge.py 수정 금지 (호환성 유지)
- **연결 0% — 기존 코드 수정 없음, Phase 2 대기**

### Known Facts
- airtable_usage_logger._lock: RLock으로 교체 완료 (재진입 안전)
- _job_fb_crawl 스케줄러 자동 실행: 14:17:51 KST (interval 30분)
- 다음 정기 실행: 16:47 KST
- scheduler_err.log에 STAGE 로그 기록됨 (app.log 동일 핸들러)
- fb_crawl 완료: {'account1': 1} — 1건 처리 (중복 이미지 skip 정상)
- pytesseract 없음 경고: 비치명적, 통과 처리

### P0 Backlog (다음 세션)
1. Instagram_Posts 도매꾹 출처 게시물 품질 육안 확인
2. 카테고리 추가 검토 (D003 등)
3. 48시간 FB Crawler 안정성 모니터링
4. Repository Interface Phase 2 연결 계획 수립

## [260623_Repository_Interface_1차_연결] — 2026-06-23 KST

### 완료 작업

#### Phase 1 — Interface 설계 (758d29d)
- `modules/infra/repository_interface.py` 전면 교체
  - Enum: SourceItemStatus / InstagramPostStatus
  - TypedDict 6개: SupplierBlockEntry / SourceItemRef / SourceItem / InstagramPost / CrawlTarget / PostPublishResult
  - 예외 4개: RepositoryError / Unavailable / NotFound / Validation
  - ABC 메서드 10개: list_blocked_suppliers / exists_post_by_image_url / save_instagram_post / fetch_active_crawl_targets / find_source_item_by_hash / save_source_item / update_source_item_status / fetch_pending_posts / claim_post_for_upload / mark_post_result
- `modules/infra/airtable_repository.py` 전면 교체
  - 10개 메서드 Airtable HTTP 구현체
  - fields 언패킹 → TypedDict 변환
  - _raise() → RepositoryError 계층 변환
  - claim_post_for_upload: WARNING non-atomic, single-worker only
  - fetch_active_crawl_targets: filterByFormula `{status}='Active'` 단독 (platform 제한 제거)

#### Phase 2 — 직접 호출 교체 (c52e00b)
| 파일 | 교체 내용 |
|------|----------|
| `airtable_bridge.py` | fetch_ready_one / update_record dead code 제거 / import requests 제거 |
| `launcher/main.py` | _job_dome_crawl: Crawl_Targets GET → repo.fetch_active_crawl_targets() |
| `launcher/main.py` | _job_dome_crawl: Source_Items upsert → find_source_item_by_hash / save_source_item / update_source_item_status |
| `launcher/main.py` | _job_insta_upload: fetch_pending_posts / claim_post_for_upload / mark_post_result 연결 |
| `launcher/main.py` | publish_single: table.update 3개 제거, 순수 반환값 함수로 전환 |
| `facebook_crawler.py` | Instagram_Posts 중복체크 직접호출 → repo.exists_post_by_image_url() |

### Known Facts
- import 검증: AirtableRepository 10개 추상 메서드 전부 구현 확인 (python -c 검증)
- airtable_bridge.py: get_table() 유지 (Function Signature Lock) / fetch_ready_one, update_record 제거
- launcher/main.py: _req, BASE_ID, API_KEY 잔재 _job_dome_crawl 내부 전부 제거
- facebook_crawler.py: _api_key, _base_id, image_url_hash 계산 로직 Repository 내부로 이동
- 잔존 직접 호출: dm/, crm/, comment/, crawlers/source_exporter.py 등 16개 파일 — 다음 세션

### P0 Backlog (다음 세션)
1. DM 모듈 (dm_auto_reply / dm_followup_scheduler / dm_receiver) Repository 연결
2. CRM 모듈 (lead_scorer / lead_closer / order_detector / daily_report) Repository 연결
3. Comment 모듈 (comment_auto_reply / comment_poller) Repository 연결
4. source_exporter.py Repository 연결 (호출 11개 — 최대 규모)

## [260624_DM_CRM_Comment_Repository_연결] — 2026-06-24 KST

### 완료 작업

#### Interface 확장 (repository_interface.py)
- Enum 추가: LeadBridgeStatus (dm_received / auto_replied / followup1~3_sent / lost / closed / converted)
- TypedDict 추가: LeadInteraction (id / igsid / bridge_status / lead_status / lead_grade / relay_scheduled_at) / LeadInteractionCreate (igsid / source / interaction_type / occurred_at)
- 추상 메서드 12개 추가 (#11~#22): get_base_price / has_recent_auto_reply / create_lead_interaction / is_repeat_inquiry / fetch_leads_due / fetch_today_lead_stats / update_lead_replied / update_lead_score / update_followup_status / mark_lead_lost / mark_lead_closed / mark_lead_converted

#### AirtableRepository 구현 (airtable_repository.py)
- 12개 메서드 Airtable HTTP 구현 + _patch_lead_interaction() private helper
- fetch_today_lead_stats: lead_grade 필드 반환 추가

#### 직접 호출 교체 (10개 파일)
| 파일 | 교체 내용 | 직접 호출 |
|------|----------|----------|
| dm_auto_reply.py | _at_headers/_at_patch 제거 → has_recent_auto_reply / get_base_price / update_lead_replied | 3→0 |
| dm_receiver.py | _at_post/_gen_code 제거 → create_lead_interaction | 1→0 |
| dm_followup_scheduler.py | _at_get_due/lost/_at_patch 제거 → fetch_leads_due / update_followup_status / mark_lead_lost | 3→0 |
| comment_auto_reply.py | _record_comment 직접 POST → create_lead_interaction | 1→0 |
| lead_scorer.py | 직접 GET/PATCH → is_repeat_inquiry / update_lead_score | 2→0 |
| lead_closer.py | 직접 PATCH 2건 → mark_lead_closed | 2→0 |
| order_detector.py | 직접 PATCH 2건 → mark_lead_converted | 2→0 |
| daily_report.py | 직접 GET → fetch_today_lead_stats | 1→0 |
| repository_interface.py | LeadInteraction lead_grade 필드 추가 | — |
| airtable_repository.py | fetch_today_lead_stats lead_grade 반환 추가 | — |

### Known Facts
- DM/CRM/Comment 영역 Airtable 직접 호출 0건 검증 완료 (Grep 확인)
- "followup_error" 비표준 상태: LeadBridgeStatus 외부 → _patch_lead_interaction() private 직접 사용
- inquiry_message / comment_id / media_id: LeadInteractionCreate 미포함 데이터 갭 (허용)
- lead_grade (hot/warm/cold): LeadInteraction TypedDict 추가 후 fetch_today_lead_stats 반환에 포함
- BOM 체크 10개 파일 전부 OK

### 잔존 직접 호출 (다음 세션 대상)
| 파일 | 라인 | 테이블 |
|------|------|--------|
| modules/common/account_manager.py | L114 | Crawl_Targets GET |
| modules/common/airtable_autorun_engine.py | L19 | BASE_URL 상수 |
| modules/crawlers/source_exporter.py | L9 | BASE_URL 상수 (다수 호출) |
| modules/ingest/domeggook_ingest.py | L33 | TRAINING_TABLE POST |
| modules/sns/facebook_crawler.py | L44 | Supplier_Blocklist GET |

### P0 Backlog (다음 세션)
1. account_manager / airtable_autorun_engine / source_exporter / domeggook_ingest / facebook_crawler Repository 연결

## [260624_직접호출_완전교체] — 2026-06-24 KST

### 완료 작업

#### 잔존 4파일 Repository 교체 (df9df6b)
| 파일 | 변경 내용 |
|------|-----------|
| `account_manager.py` | `_load_crawl_urls_from_airtable()` — requests 제거 → `repo.fetch_active_crawl_targets()` + platform 필터 list comprehension |
| `facebook_crawler.py` | `load_supplier_blocklist()` — requests+threading+socket 제거 → `repo.list_blocked_suppliers()` / `socket` top-level import 제거 |
| `source_exporter.py` | 직접 호출 11건 전체 → Repository 교체. `BASE_URL/_headers()/_base()` 제거. 신규 메서드 4개(fetch_source_items_for_export / recover_stale_queued / claim_source_item_for_export / update_source_item_retry) 추가 |
| `domeggook_ingest.py` | Training 직접 호출 → `TrainingRepository.upsert_training_record()` |
| `training_repository.py` | 신규 생성 — Product_Training_Set 전용 (GET 중복확인 → PATCH/POST upsert) |
| `repository_interface.py` | `SourceItemStatus.QUEUED` 추가 / `SourceItem` 필드 확장 / 추상 메서드 4개 추가 (#23~#26) |
| `airtable_repository.py` | 메서드 23~26 구현 (서버사이드 filterByFormula 적용) |

#### save_to_airtable NameError 수정 (4502e65)
- `facebook_crawler.py` `save_to_airtable()` — `_req/_url/_hdrs/image_url_hash` 미정의 변수 NameError 수정
- `_req.post()` + `log_api_call()` → `repo.save_instagram_post(payload)` 교체
- `hashlib.sha256` 인라인 계산 추가
- `import logging` 인라인 3개 → `logger` 통일

#### airtable_bridge dead import 제거 (e0bcff6)
- `airtable_bridge.py` — `log_api_call` import 제거 (호출 없는 dead import)

#### inquiry_message 데이터 갭 해소 (36cbf05)
- `LeadInteractionCreate` — `inquiry_message: str` 필드 추가
- `create_lead_interaction()` — `fields["inquiry_message"]` Airtable 저장 추가
- `dm_receiver.py` — `record_interaction()` 호출 시 `inquiry_message=message_text` 전달
- `comment_auto_reply.py` — `_record_comment()` 호출 시 `inquiry_message=text` 전달
- 효과: dashboard.py 메시지 표시 / kpi_collector price/neg 집계 실데이터 기반 동작

### Infrastructure 외부 직접 호출 최종 검증
- `Select-String api.airtable.com` grep 결과 운영 코드 내 잔존:
  - `airtable_autorun_engine.py` 1건 — **dead 파일 확정** (import 없음, 250723 복사 산물)
  - `airtable_repository.py` / `training_repository.py` — infra 계층 허용
- **실질적 직접 호출 0건 확정**

### Known Facts
- `airtable_autorun_engine.py`: 250723 복사 파일, 어디서도 import 없음, dead 판정 (삭제 불필요)
- `domeggook_ingest.py` 중복 반환값 변경: duplicate → upsert 내부 처리 (PATCH), 카운터 집계 방식 변경
- `SourceItemStatus.QUEUED` 추가: source_exporter 내부 상태 전용

### P0 Backlog (다음 세션)
1. **Failure Injection Test 1회** — 의도적 오류 주입 후 복구 흐름 검증
2. **Runtime Proof 3회 연속 정상 확인** — DM/댓글 수신 + inquiry_message 저장 검증
