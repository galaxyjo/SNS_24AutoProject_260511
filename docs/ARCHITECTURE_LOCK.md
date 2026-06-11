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

## INSTAGRAM UPLOAD ARCHITECTURE LOCK (260602 확정)
```
업로드 실제 진입점: launcher/main.py:159 _job_insta_upload()
  (bot_uploader.py → insta_uploader.py 체인은 dead stub — 실제 API 호출 없음)

업로드 파이프라인 (고정):
Airtable Instagram_Posts (post_status=ready)
  → _preprocess_image()          # 비율 보정(4:5~1.91:1) + imgbb 영구 URL 변환
  → table.update(uploading)      # 원자적 잠금
  → POST /media                  # 미디어 컨테이너 생성 → creation_id
  → POST /media_publish          # 게시 → ig_media_id
  → table.update(posted, ig_media_id)

환경변수 (필수):
  INSTA_ACCESS_TOKEN, INSTA_IG_USER_ID, IMGBB_API_KEY (전처리용)

Runtime Proof (2026-06-02):
  recFyw7OUaZ666JDJ → ig_media_id=18101360630320704 → posted ✅
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

## FINAL PRINCIPLE
```
Conversation ≠ System Reality
Text ≠ File
말로 완료 ≠ 실제 완료
```
