# MASTERTREE_CONTRACT.md
> Generated: 2026-05-16 | Status: ACTIVE | Version: v1.1
> Scope: SNS_24AutoProject_260511

---

## MASTERTREE 정의
```
MasterTree는 프로젝트의 유일한 구조 기준이다.
260511이 MasterTree의 Source of Truth.
```

---

## 확정 디렉토리 구조
```
SNS_24AutoProject_260511/
├── core/                      ← 엔진 (run_engine, task_router, error_handler)
├── modules/
│   ├── crawling/              ✅ 구현됨
│   ├── upload/                ✅ 구현됨 (stub → 실구현 필요)
│   ├── dm/                    ✅ 구현됨 (부분)
│   ├── crm/                   ✅ 구현됨
│   ├── interaction_engine/    ← 이식 예정
│   ├── metrics/               ← 이식 예정
│   ├── trade/                 ← 보류
│   └── avatar/                ← 보류
├── adapters/
│   └── legacy_bridge/         ✅ skeleton 완성
│       ├── bridge_base.py
│       ├── contracts/
│       └── README.md
├── services/
│   ├── gpt_connector/         ← 이식 예정
│   ├── smtp/                  ← 이식 예정
│   └── slack/                 ← 이식 예정
├── db/
│   ├── retry_queue.db         ✅
│   ├── kpi_snapshots.db       ✅
│   └── crawl_stats.db         ✅
├── docs/                      ✅ governance 문서
├── audit/                     ✅ schema dump + airtable export
├── porting_logs/              ✅ MERGE_JOURNAL.md
├── snapshots/                 ✅ (gitignore)
├── tests/
├── logs/
└── tools/
```

---

## HASH POLICY
```
핵심 파일 SHA256 기록 필수:
- sha256_integrity_mastertree.py
- verify_integrity_and_identify_unnecessary.py

기준 파일: hash_extract_fixed_columns_20250721_final.csv
(⚠️ .csv.csv 이중 확장자 — 실제 파일명 재확인 필요)
```

---

## MASTERTREE RULES

### RULE #1 | Unknown File = Quarantine
알 수 없는 파일 → 즉시 격리, 운영 제외

### RULE #2 | Duplicate File = Review Required
동일 기능 파일 2개 이상 → 즉시 검토, 1개만 유지

### RULE #3 | .fixed.py 자동 신뢰 금지
.fixed.py는 임시 파일. 운영 기준 파일 아님.

### RULE #4 | Hash Mismatch = Manual Verify
hash 불일치 → 자동 통과 금지 / 수동 확인 후 판단

### RULE #5 | Contract-first Porting
250723 → 260511 이식 시 MasterTree 구조 기준으로만

---

## RESTORE POLICY
복구 전 필수:
```
1. dry-run 실행
2. hash verify
3. backup snapshot 생성
4. rollback 경로 확인
```

---

## AIRTABLE STATE DB 구조
```
Source_Feeds      ← FB 크롤링 원본
Instagram_Posts   ← 업로드 상태 관리
Lead_Interactions ← DM/CRM 상태 (lost_reason / lost_at / disqualified 추가 — 260612)
Account_Registry  ← 계정 + AdsPower 매핑
Crawl_Targets     ← 크롤링 대상 URL 관리 (FB_GROUP_POOL_V1 = 5개 활성)
Supplier_Blocklist ← 차단 공급사 목록 (실차단 적용 중)
```

---

## AIRTABLE Instagram_Posts 데이터 계약 (260602 확정)

| 필드명 | 타입 | 역할 | 기본값 |
|--------|------|------|--------|
| `image_url` | url | Facebook CDN 이미지 URL | 필수 |
| `image_url_hash` | singleLineText | 중복 체크용 SHA256 | 자동 생성 |
| `source_url` | url | Facebook 그룹 URL | 필수 |
| `post_status` | singleSelect | ready → uploading → posted / failed | ready |
| `caption` | multilineText | generate_caption_clone() 결과 | 원문 기반 |
| `hashtag` | multilineText | 원문 #태그 추출본 | 없으면 빈값 |
| `original_text` | multilineText | post.text 직후 원문 (가공 전) | 필수 |
| `converted_text` | multilineText | replace_contacts() 결과 | 필수 |
| `media_type` | singleLineText | 미디어 타입 | image (기본) |

```
media_type 확장 계획:
- image: 현재 구현 (260602 Runtime Proof 완료)
- carousel: Phase 후속 (별도 기획 필요)
- video: Phase 후속 (별도 기획 필요)
```

### 주의: 존재하지 않는 필드 (코드 참조 금지)
- `retry_count` — 삭제됨 (463c350, 260616)
- `last_error_msg` — 삭제됨 (463c350, 260616)

### modules/sns 신규 모듈 (260616)
- `modules/sns/image_hosting.py` — imgbb 업로드 유틸 (upload_to_imgbb)

## RUNTIME STATUS (2026-06-12 세션 완료)
```
260612: 운영정비 완료
- Supplier_Blocklist 실차단 적용 (11fc204)
- LOST 72h 타임아웃 DRY_RUN 구현 (0e5133b)
- Lead_Interactions: lost_reason / lost_at / disqualified 필드 추가
- FB그룹 1676627532598134 제거 (c71f2c7) — crawl_urls 5개 운영
- Instagram_Posts.caption 필드 재추가 (API, fldcxTzLzYCzD9aYe)
- ig_media_id 17863634121631171 클리어 (rectwruMD3uua54sv)
최신 commit: 0b9291c
백업: backup_(12)_260602_2207 (백업 필요 시점 도달)
```
```
260616: 버그수정 5건 + 운영정비
- ERR-040~043 수정: post_status 옵션 복구 / retry_count 제거 / CDN 중복 개선 / import re 추가
- M&Y GLOBAL Supplier_Blocklist 등록
- _IMAGE_BLOCK_KEYWORDS m&y\s*global 추가 (a126754)
- facebook_crawler.py clean_fb_metadata() 호출 추가 (0688849)
- image_hosting.py 신규 추가
- upload_rate: 5.1% → 5.7% 반등
최신 commit: 0688849
```
```
260603: ExecutionPolicy 차단 해결 + watchdog 자가치유 블록 추가
Flask/APScheduler/ngrok/watchdog 전부 정상 가동 확인
최종 commit: 2695d87
작업스케줄러 권한: RunLevel=Highest / UserId=admin ✅
```
```
Clone Mode Runtime Proof PASS — recsmA4WIlrur1wHO (260602_0108) ✅
Instagram 업로드 Runtime Proof PASS — recFyw7OUaZ666JDJ / ig_media_id=18101360630320704 (260602_1620) ✅
pytest 104 passed ✅
백업: backup_(12)_260602_2207
```

## MASTER PRINCIPLE
```
MasterTree   > Conversation
Runtime      > Text
Evidence     > Assumption
260511       > 250723
```

## [260617] AIRTABLE STATE DB 구조 갱신

### 현재 Base 구조
Base: Airtable_Import_Ready_Control_Tower_v3
Base ID: apphJNTHWNoFcVb1D
Workspace: 24auto_vr01_260410_0347pm

### 테이블 목록 (총 9개)
기존 유지:
- Account_Registry     아바타 본체 33개 (Active 3 / Ready 30)
- Source_Feeds         크롤링 원본
- Instagram_Posts      게시 대기열 (라우팅 필드 추가됨)
- Lead_Interactions    DM/리드
- Persona_Profile      아바타 성격/말투
- Crawl_Training_Set   필터 학습 67 records
- Crawl_Targets        크롤링 대상
- Supplier_Blocklist   공급자 차단

신규 추가:
- Platform_Accounts    SNS별 계정 31개 (IG 19 + FB 12)

### Multi-Account Routing 구조
Instagram_Posts.target_identity_id
-> Account_Registry.identity_id
-> Platform_Accounts.identity_id
-> Platform_Accounts.adspower_profile_id
-> AdsPower 실행
-> Instagram 게시
-> publish_status 반환

### Pilot 운영 현황
- Active 3개: IDN-000036 / IDN-000038 / IDN-000016
- 다음 단계: n8n 워크플로우 연결 후 Runtime 검증
- Rollout: 3 -> 10 -> 33개


---
## [260617] 신규 모듈 등록

| 파일 | 역할 | 상태 |
|------|------|------|
| modules/sns/image_hosting.py | imgbb 업로드 어댑터 | ACTIVE |
| tools/backfill_failed_images.py | failed 레코드 imgbb 복구 | ACTIVE (DRY_RUN 기본) |

### Airtable 스키마 변경
- Instagram_Posts.original_image_url 필드 추가 (fldEpMV0uFiWR7OmB, url 타입)