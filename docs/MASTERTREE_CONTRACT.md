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
Lead_Interactions ← DM/CRM 상태
Account_Registry  ← 계정 + AdsPower 매핑
```

---

## RUNTIME STATUS (2026-05-28)
```
modules/dm/dm_auto_reply.py  M  — 중복 발송 방지 + AttributeError 수정 (미커밋)
실거래 DM AutoReply E2E PASS — IGSID 1792783944739953
duplicate skip 검증 PASS      — 21:42:15 / 21:50:03
```

## MASTER PRINCIPLE
```
MasterTree   > Conversation
Runtime      > Text
Evidence     > Assumption
260511       > 250723
```
