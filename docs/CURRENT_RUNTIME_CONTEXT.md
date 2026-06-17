# CURRENT_RUNTIME_CONTEXT.md
_마지막 업데이트: 260617_0000_

## 현재 단계
**260616 운영정비 완료** — 버그수정 5건 / M&Y GLOBAL 차단 등록 / content_filter 패턴 추가 / clean_fb_metadata 크롤러 적용 / image_hosting.py 신규 모듈 추가

## 최종 확인 커밋
0688849 (fix: clean_fb_metadata 호출 추가 — FB UI 잔여물 제거 [260616])

## Source of Truth
- Runtime: C:\SNS_24AutoProject_260511
- Archive: C:\SNS_24AutoProject_250723 (삭제/dead 판정 금지)

## 마지막 확인 커밋 체인
- 463c350 (fix: retry_count/last_error_msg 필드 제거 + Graph API 실패 로깅 보강 [260616])
- 25c6779 (fix: image_url_hash FB CDN 중복 감지 개선 — URL 전체 대신 미디어ID 추출 [260616])
- 366c617 (fix: facebook_crawler import re 누락 추가 [260616])
- a126754 (fix: IMAGE_BLOCK_KEYWORDS에 M&Y GLOBAL 워터마크 패턴 추가 [260616])
- 0688849 (fix: clean_fb_metadata 호출 추가 — FB UI 잔여물 제거 [260616])

## Runtime 상태 (260529 20:15 기준 — 세션 간 기동 미확인)
| 구간 | 상태 | 근거 |
|---|---|---|
| Flask (dm_receiver) | ⚠️ UNKNOWN | 세션 외 확인 필요 |
| launcher/main.py | ⚠️ UNKNOWN | 세션 외 확인 필요 |
| ngrok | ⚠️ UNKNOWN | 세션 외 확인 필요 |
| Streamlit | ⚠️ UNKNOWN | 세션 외 확인 필요 |
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

## 미해결 항목 (Phase 후순위)
- 그룹 610113703703488: div[role='feed'] 미탐지 — 가입 승인 대기 중 (코드 문제 아님)
- LOST_DRY_RUN=false 전환 대기 — 실운영 전 Airtable 필드 확인 후 적용
- 워터마크 제외 로직 — **260616 부분 구현** (_IMAGE_BLOCK_KEYWORDS + Supplier_Blocklist 등록), passes_image_filter 이미지 픽셀 분석 미구현
- data/processed_comment_ids.json untracked 유지 (정상 — gitignore 대상)
- 백업 필요 시점 도달 (마지막 백업: backup_(12)_260602_2207)

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
