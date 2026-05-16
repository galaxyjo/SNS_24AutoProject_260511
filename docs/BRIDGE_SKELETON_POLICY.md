# BRIDGE_SKELETON_POLICY.md

# 260516 Runtime Governance Policy

# adapters/legacy_bridge/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. OBJECTIVE
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

본 문서는
250723 → 260511 Runtime Migration 과정에서
legacy runtime module을 안전하게 이식하기 위한
Bridge Skeleton 정책을 정의한다.

목적:

* Runtime Drift 방지
* Ghost Import 방지
* Duplicate Runtime 방지
* Contract-first Migration 강제
* 운영 안정성 유지

기준일:
260516

MASTER REPO:
C:\SNS_24AutoProject_260511

LEGACY SOURCE:
C:\SNS_24AutoProject_250723

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. DIRECTORY STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

adapters/
└── legacy_bridge/
├── bridge_base.py
├── error_handler_bridge.py
├── task_router_bridge.py
├── run_engine_bridge.py
└── contracts/

규칙:

* legacy module 직접 import 금지
* bridge layer 통해서만 연결
* legacy runtime access 단일화

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. MIGRATION PRIORITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

우선순위:

1️⃣ error_handler
2️⃣ task_router
3️⃣ run_engine

원칙:

* 가장 작은 coupling부터 이식
* runtime 영향도 낮은 순서 우선
* state validation 가능한 모듈 우선

금지:

* run_engine 먼저 이식 금지
* multi-module 동시 이식 금지

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. BRIDGE BASE CONTRACT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

bridge_base.py는
모든 bridge module의 Behavior Contract 기준이다.

필수 항목:

* module_name
* source_path
* target_runtime
* validate()
* execute()
* rollback()

필수 규칙:

① validate() 성공 전 execute() 금지
② execute() 실패 시 rollback() 필수
③ runtime path logging 필수
④ import source logging 필수
⑤ DB write target logging 필수

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. CONTRACT-FIRST POLICY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

모든 이식은
반드시 Contract → Validation → Execute 순서만 허용한다.

순서:

1️⃣ Contract 정의
2️⃣ Runtime Validation
3️⃣ Import Validation
4️⃣ Test Execution
5️⃣ Commit
6️⃣ Production Attach

금지:

* 코드 먼저 수정
* 실행 후 검증
* 운영 중 직접 patch

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
6. FILE COPY POLICY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ 절대 금지:

* legacy file 직접 복사
* copy-paste migration
* .fixed.py 누적 생성
* duplicate runtime 생성

허용:

* bridge wrapping
* adapter pattern
* contract migration
* isolated runtime attach

원칙:
"기능 복사"가 아니라
"Behavior Migration" 수행.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
7. ONE MODULE ONE COMMIT ONE TEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

강제 규칙:

1 Module
→ 1 Commit
→ 1 Test
→ 1 Validation

금지:

* 다중 모듈 동시 수정
* 테스트 없는 commit
* runtime 미검증 commit

Commit 기준:

* rollback 가능 상태 유지
* 이전 runtime 즉시 복구 가능 상태 유지

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
8. RUNTIME VALIDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

모든 bridge module은
다음 항목 검증 필수:

* 실제 import path
* 실제 DB target
* 실제 runtime PID
* 실제 config source
* 실제 env source
* 실제 write target

원칙:
추정 금지.
실제 runtime evidence 기반만 허용.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
9. DUPLICATE RUNTIME POLICY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

동일 기능 runtime이
2개 이상 존재할 경우:

상태:
⚠️ Runtime Conflict

조치:

* Source of Truth 지정
* legacy reference 분리
* bridge attach 적용
* duplicate isolate 수행

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
10. FINAL PRINCIPLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

현재 단계는:
"Feature Expansion" 단계가 아니다.

현재 단계:
Pre-Production Runtime Governance

최우선 목표:

* Runtime Stability
* Operational Traceability
* Import Determinism
* Recovery Capability

절대 원칙:
"실행되는 현실(Runtime Reality)을 먼저 통제한다."
