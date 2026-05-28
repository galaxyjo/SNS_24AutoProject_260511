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

## RUNTIME VERIFIED (2026-05-28)
```
- 실거래 DM AutoReply E2E 성공: IGSID 1792783944739953 → IG DM 발송 완료
- 중복 발송 방지: _has_recent_auto_replied() CREATED_TIME() 3분 window 적용
- duplicate skip 로그 검증: 21:42:15 / 21:50:03 정상 차단 확인
- 수정 파일: modules/dm/dm_auto_reply.py (미커밋)
```

## FINAL PRINCIPLE
```
Conversation ≠ System Reality
Text ≠ File
말로 완료 ≠ 실제 완료
```
