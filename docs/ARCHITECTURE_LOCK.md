# ARCHITECTURE_LOCK.md
> Generated: 2026-05-16 | Status: ACTIVE | Version: v1.1
> 선언일: 2026-05-16

---

## SOURCE OF TRUTH 선언
```
SOURCE OF TRUTH  → 260511 (운영 실행본, 절대 기준)
LEGACY ARCHIVE   → 250723 (발굴 전용, 실행 금지)
MASTER CONTRACT  → MASTERTREE_CONTRACT.md
```

---

## CORE ARCHITECTURE
```
Python Core Engine (260511)
        ↓
Airtable State DB (State 관리 전용 / credentials 저장 금지)
        ↓
n8n Orchestration (webhook 수신 / flow 연결)
        ↓
AdsPower + Selenium Runtime
        ↓
Instagram / Facebook Execution
        ↓
DM Relay / CRM
        ↓
Analytics + Dashboard
```

---

## FREEZE 규칙
```
- 신규 기능 추가 금지 (Phase 1 완료 전)
- 운영 버그 수정만 허용
- 260511 구조 변경 금지 (adapter 경유 필수)
- 250723 실행 절대 금지
```

---

## ABSOLUTE LOCKS

### LOCK #1 | Source of Truth 고정
```
260511 = 유일한 실행 기준
250723 = 정적 분석만 허용
```

### LOCK #2 | Airtable 역할
```
Airtable = State DB Only
credentials 저장 금지
runtime 실행 로직 금지
```

### LOCK #3 | Role Separation
```
crawler  = execute only
adapter  = config only
bridge   = write only
```

### LOCK #4 | Runtime-first
```
문서보다 Runtime 우선
텍스트보다 Filesystem 우선
```

### LOCK #5 | Filesystem Verification
```
완료 선언 전 반드시:
Get-ChildItem 확인
git commit 확인
```

### LOCK #6 | Single Source of Truth
```
MasterTree 기준 유지
동일 기능 파일 2개 이상 금지
```

---

## PORTING 규칙
```
- 파일 직접 복사 금지
- adapters/legacy_bridge 경유 필수
- One Module → One Test → One Commit → One Deploy
- Behavior Compatibility 검증 필수
  (같은 입력 → 같은 출력 → 같은 side effect)
```

---

## FORBIDDEN 목록 (13개)
```
1.  두 저장소 동시 수정          → Drift 발생
2.  import 경로 임시 수정 반복   → Runtime 꼬임
3.  sys.path 남발                → 구조 붕괴
4.  .fixed.py 누적 유지          → 중복 폭증
5.  테스트 없는 리팩토링          → 운영붕괴
6.  파일 직접 복사 merge          → Runtime Conflict
7.  Multi-module 동시 이식        → 검증 불가
8.  run_engine 먼저 이식          → 의존성 충돌
9.  evidence 없는 완료 선언       → 환각 반복
10. rollback 없는 merge           → 복구 불가
11. partial success 완료 처리     → Ghost Bug
12. production_verified 남발      → 신뢰도 붕괴
13. "거의 됐다" "될 것 같다" 판단 → 추정 기반 운영
```

---

## CLONE MODE ARCHITECTURE LOCK (260602 확정)
```
원칙:
1. Gemini rewrite 호출 절대 금지 (generate_caption() clone 경로 사용 금지)
2. original_text 보존 필수 — post.text 직후 캡처, 가공 전 저장
3. converted_text = replace_contacts(raw_text) 결과
4. caption = generate_caption_clone(converted_text) 결과 (포맷 정리만)
5. expand_see_more() 호출 필수 — raw_text 읽기 직전
6. Runtime Proof 1건 확보 전 기능 확장 금지
7. COMMENT_AUTO_REPLY_ENABLED=false 기본 유지

저장 파이프라인 (고정):
Facebook post
  → expand_see_more()         # 더보기 클릭
  → raw_text = post.text      # 원문 캡처
  → detect_and_translate()    # 필터용 번역 (저장 미사용)
  → passes_keyword_filter()   # 필터 통과 체크
  → replace_contacts(raw_text) → converted_text
  → save_to_airtable(converted_text, original_text=raw_text)
      → generate_caption_clone(converted_text) → caption, hashtags
          └→ clean_fb_metadata()       # FB UI 잔여물(작성자명·경과시간··) 제거 (ERR-037)
          └→ replace_contacts()        # 연락처 치환
      → Airtable POST: original_text / converted_text / caption / hashtag / media_type=image

Runtime Proof (2026-06-02):
  recsmA4WIlrur1wHO — original_text / converted_text / caption / media_type=image ✅
```

## INSTAGRAM UPLOAD ARCHITECTURE LOCK (260617 갱신)
```
업로드 진입점:
  - APScheduler: launcher/main.py _job_insta_upload() → publish_single() 위임 (9d65cb4)
  - n8n Endpoint: /api/v1/instagram/publish → publish_single() 위임 (P0, 미구현)
  (bot_uploader.py → insta_uploader.py 체인은 dead stub — 실제 API 호출 없음)

업로드 파이프라인 (고정):
Airtable Instagram_Posts (post_status=ready)
  → table.update(uploading)      # 원자적 잠금 (_job_insta_upload)
  → publish_single(rid, image_url, caption, token, ig_user_id)
      → _preprocess_image()          # 비율 보정(4:5~1.91:1) + imgbb 영구 URL 변환
      → POST /media                  # 미디어 컨테이너 생성 → creation_id
      → POST /media_publish          # 게시 → ig_media_id
      → table.update(posted, ig_media_id)

환경변수 (필수):
  INSTA_ACCESS_TOKEN, INSTA_IG_USER_ID, IMGBB_API_KEY (전처리용)

Runtime Proof (2026-06-02):
  recFyw7OUaZ666JDJ → ig_media_id=18101360630320704 → posted ✅
publish_single() Runtime Proof: NOT_EXECUTED (260617 기준 ready 레코드 0건)
```

## RUNTIME VERIFIED (2026-05-28)
```
- 실거래 DM AutoReply E2E 성공: IGSID 1792783944739953 → IG DM 발송 완료
- 중복 발송 방지: _has_recent_auto_replied() CREATED_TIME() 3분 window 적용
- duplicate skip 로그 검증: 21:42:15 / 21:50:03 정상 차단 확인
- 수정 파일: modules/dm/dm_auto_reply.py ✅ 72e0e1a 커밋 완료
```

## LEAD STATE MACHINE LOCK (260612 확정)
```
Lead_Interactions bridge_status 상태 전이:

new → qualified → auto_replied
                 → followup1_sent → followup2_sent → followup3_sent
                                                    → LOST (72h 타임아웃, DRY_RUN 모드)
             → disqualified (Supplier_Blocklist 차단)

LOST 전환 조건:
  followup3_sent 상태 + relay_scheduled_at 기준 72h 경과
  .env LOST_DRY_RUN=false 설정 필요 (현재 DRY_RUN 모드)

Airtable Lead_Interactions 필드 (260612 추가):
  lost_reason   — Single line text
  lost_at       — Date
  disqualified  — Checkbox
```

## SUPPLIER_BLOCKLIST ARCHITECTURE LOCK (260612 확정)
```
- Supplier_Blocklist Airtable 테이블 기반 차단 (DRY_RUN 제거 완료)
- FB 크롤러 실행 시 Blocklist 로드 → author 매칭 → continue(skip)
- 현재 등록: 4건
- 차단 로그: [Blocklist] 통과 | author='...' / [FB Crawler] POST N 필터 제외
```

## FILTER_RULES ARCHITECTURE LOCK (260612 확정)
```
- configs/filter_rules.json: 분석 전용, 운영 연동 금지
- generate_filter_rules.py: Crawl_Training_Set 기반 생성 스크립트, 자동 실행 금지
- 운영 필터: modules/sns/content_filter.py passes_keyword_filter() 사용
```

## IMAGE HOSTING MODULE (260616 추가)
```
- modules/sns/image_hosting.py: imgbb 업로드 유틸 (upload_to_imgbb)
- 용도: FB CDN 만료 URL → imgbb 영구 URL 변환 (Instagram 업로드 전처리)
- 현재: launcher/main.py _preprocess_image()에서 직접 imgbb 호출 중
- 향후: image_hosting.upload_to_imgbb()로 대체 예정
- BOM 없음 확인 (UTF-8 without BOM)
```

## CRAWL_TARGET_SOURCE FEATURE FLAG (260619 확정)
```
crawl_urls 소스 제어 Feature Flag (.env CRAWL_TARGET_SOURCE):
  accounts_json (기본): configs/accounts.json crawl_urls 사용
  shadow         : accounts.json 사용 + Airtable 비교 로그 출력 (검증용)
  airtable       : Airtable Crawl_Targets에서 Active facebook URL 동적 로드

현재 운영: CRAWL_TARGET_SOURCE=airtable (Airtable 단일 소스)
구현 파일: modules/common/account_manager.py
  - _load_crawl_urls_from_airtable(): Airtable Crawl_Targets 조회
  - _shadow_compare(): accounts.json vs Airtable URL 집합 비교
  - _get_all(): Feature Flag 분기 처리
커밋: 9cc4ee9
```

## Crawl_Targets 스키마 (260619 확장)
```
기존 필드: target_id / target_name / category_code / target_url / status / priority / notes
신규 추가:
  platform      (singleSelect: facebook / domeggook)
  max_posts     (number)
  account_ref   (singleLineText)
  last_run_at   (dateTime, Asia/Bangkok)
  last_result   (singleLineText)
```

## FINAL PRINCIPLE
```
Conversation ≠ System Reality
Text ≠ File
말로 완료 ≠ 실제 완료
```

## [260617] Airtable 구조 변경 확정

### 신규 테이블
- Platform_Accounts (tblkdk5dEagfQvUMp)
  - platform_account_id / identity_id / platform / username / profile_url
  - platform_status / platform_automation_enabled / adspower_profile_id
  - last_login_success_at / last_post_success_at / notes

### Account_Registry 신규 필드
- identity_id (PK 형식: IDN-000001)
- category (A_BEAUTY / B_MED / C_TRAVEL / UNCATEGORIZED)
- automation_enabled (checkbox)
- pilot_wave (3 / 10 / 30)
- identity_status (Ready / Active / Review / Blocked)
- adspower_profile_id
- linked_platform_accounts (Linked Record -> Platform_Accounts)

### Instagram_Posts 신규 필드
- target_identity_id
- target_platform_account_id
- publish_status (Ready / Processing / Posted / Failed)
- run_id
- scheduled_at

### 고유키 확정
- identity_id: IDN-000001
- platform_account_id: PLT-IG-000001 / PLT-FB-000001
- content_id: CNT-000001
- run_id: RUN-000001

### 절대 변경 금지
- 기존 테이블 삭제/이름변경 금지
- 비밀번호 Airtable 원문 저장 금지
- Base 분리는 100개 확장 후 병목 확인 후 검토


---
## [260617] 이미지 호스팅 계층 추가 (확정)

### 구조
FB 크롤링 -> FB CDN URL 추출 -> imgbb 업로드 -> 공개 URL -> Airtable image_url 저장 -> Instagram 업로드

### 확정 모듈
- modules/sns/image_hosting.py: upload_to_imgbb(source_url) -> {success, public_url, content_hash}
- Airtable 필드: image_url(imgbb), original_image_url(FB CDN 원본 보존)

### 금지
- FB CDN URL을 Instagram Graph API에 직접 전달 금지
- imgbb 검증 전 post_status=ready 설정 금지
- caption 없는 레코드 ready 전환 금지

---
## [260617] n8n Architecture 설계 확정 (DESIGN_COMPLETE)

### n8n Workflow 목록
- WF-01: Posting Scheduler — Airtable ready 레코드 폴링 → /api/v1/instagram/publish 호출
- WF-02: Real-time DM Webhook — Meta Webhook → Python dm_receiver 처리
- WF-03: Credential Health Check — 계정 토큰 주기적 검증
- WF-04: Failure/Recovery Watchdog — failed 레코드 재시도 조율
- WF-05: Runtime Alert — 오류/비정상 감지 → Slack 알림

### Credential 구조 (Option B 확정)
- Python이 Instagram Graph API Token 소유
- n8n은 Token 비보유 — /api/v1/instagram/publish Endpoint 경유만 허용
- Token 저장: .env CRED_{credential_ref}_TOKEN 형식
- Airtable credential 원문 저장 절대 금지

### publish_single() 분리 (9d65cb4 확정)
- launcher/main.py: publish_single(rid, image_url, caption, access_token, ig_user_id)
- _job_insta_upload(): uploading 마킹 후 publish_single() 위임
- /api/v1/instagram/publish (P0 미구현): 인증 → 재검증 → publish_single() 위임
- Token/ig_user_id 호출자 주입, 로그에 access_token 출력 금지

### Canonical Status (확정)
- post_status 단일 필드 사용 (ready → uploading → posted / failed)
- publish_status 신규 필드: 미사용 (향후 다계정 라우팅 시 검토)

### P0 Backlog (미구현)
- Instagram_Posts.execution_owner 필드 Airtable 추가
- APScheduler 조회 조건: post_status=ready AND (execution_owner='' OR 없음)
- modules/sns/instagram_publish_api.py — Flask Blueprint
- dm_receiver.py Blueprint 등록
- Runtime Proof: 테스트용 Record 1건 실제 게시
---

## [260624] Repository Interface 전면 교체 완료

_확정일: 2026-06-24_

### 선언
Infrastructure 외부 직접 호출 실질적 **0건** 달성.
모든 Airtable 접근은 AirtableRepository (RepositoryInterface 구현체) 경유로 통일.

### 확정된 메서드 (25개)
| 카테고리 | 메서드 |
|----------|--------|
| 차단 공급업체 | list_blocked_suppliers |
| 소스 피드 | list_crawl_urls, list_source_feeds, get_source_feed, upsert_source_feed |
| 소스 아이템 | list_pending_source_items, get_source_item, upsert_source_item, mark_source_item_exported |
| Instagram 게시물 | list_instagram_posts, get_instagram_post, upsert_instagram_post, mark_post_uploading, mark_post_uploaded, mark_post_failed |
| Lead/DM | create_lead_interaction, list_due_followups, mark_followup_sent, list_pending_comments, mark_comment_replied |
| 공통 | exists_post_by_image_url |
| Instagram 게시물 (KPI/집계) | fetch_posted_missing_media_id, fetch_all_instagram_posts, fetch_all_lead_interactions |

### 교체 완료 파일 (커밋 체인 18aa3a7 → df9df6b)
- dm/auto_responder.py, followup_scheduler.py, dm_receiver.py
- crm/lead_scorer.py, order_detector.py
- comment/comment_poller.py, comment_auto_reply.py
- modules/common/account_manager.py
- modules/sns/facebook_crawler.py, source_exporter.py
- modules/dome/domeggook_ingest.py
- modules/metrics/airtable_integrity.py (DI Canary #2, 커밋 f6194ac)
- modules/metrics/kpi_collector.py (DI Canary #3, 커밋 f21e4b8)

### 예외 (아키텍처 허용)
- irtable_autorun_engine.py — dead 파일, 실행 경로 없음, 교체 불필요
- TrainingRepository — Product_Training_Set 전용 분리 클래스 (RepositoryInterface 미상속 허용)

### Failure Injection Test (260624 PASS)
- AdsPower Stop finally 경로 정상 실행 확인
- Runtime Proof 5회 연속 (19:50~21:50 KST) 정상
