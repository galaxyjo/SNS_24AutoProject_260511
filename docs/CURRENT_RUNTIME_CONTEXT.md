# CURRENT_RUNTIME_CONTEXT.md
_마지막 업데이트: 260602_1620_

## 현재 단계
**섹션19 Instagram 업로드 Runtime Proof 완료** — Graph API 2-step 업로드 / imgbb 전처리 / Airtable posted 마킹 / caption clean_fb_metadata 적용

## 최종 확인 커밋
349fedf (fix: Clone Mode caption Facebook UI 잔여물 제거 (ERR-037) [260602])

## Source of Truth
- Runtime: C:\SNS_24AutoProject_260511
- Archive: C:\SNS_24AutoProject_250723 (삭제/dead 판정 금지)

## 마지막 확인 커밋 체인
- 3dbe72a (feat: crawl_urls 4개 그룹으로 확장 [260602])
- c6a30d1 (fix: accounts.json BOM 제거 + newline 정리 [260602])
- f5d59f2 (fix: facebook_crawler load_dotenv 누락 추가 [260602])
- 349fedf (fix: Clone Mode caption Facebook UI 잔여물 제거 ERR-037 [260602])

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
- Airtable caption 필드 없음 → 422 UNKNOWN_FIELD_NAME → **260529 해소 완료** (UI에서 필드 추가)
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

## 미해결 항목 (Phase 후순위)
- 그룹 610113703703488: div[role='feed'] 미탐지 — 가입 승인 대기 중 (코드 문제 아님)
- 워터마크 제외 로직 미구현
- data/processed_comment_ids.json untracked 유지 (정상 — gitignore 대상)
- 백업 필요 시점 도달 (마지막 백업: backup_(11)_260602_0108)

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