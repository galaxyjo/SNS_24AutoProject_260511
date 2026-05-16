# adapters/legacy_bridge/

250723 → 260511 Runtime Migration Bridge Layer.

정책 전문: `docs/BRIDGE_SKELETON_POLICY.md`

---

## 구조

```
adapters/legacy_bridge/
├── bridge_base.py          — LegacyBridge 추상 기반 클래스 (모든 bridge의 계약)
├── error_handler_bridge.py — (예정) error_handler 이식 bridge
├── task_router_bridge.py   — (예정) task_router 이식 bridge
├── run_engine_bridge.py    — (예정) run_engine 이식 bridge
└── contracts/              — 모듈별 계약 문서 저장
```

---

## 사용법

```python
from adapters.legacy_bridge import LegacyBridge, BridgeContext

class MyBridge(LegacyBridge):
    def validate(self) -> bool:
        # import path / DB target / runtime PID 검증
        self._validated = True
        return True

    def execute(self) -> bool:
        # 실제 이식 실행
        return True

    def rollback(self) -> bool:
        # 이전 상태 복구
        return True

ctx = BridgeContext(
    module_name="my_module",
    source_path="C:/SNS_24AutoProject_250723/...",
    target_runtime="C:/SNS_24AutoProject_260511/...",
)
bridge = MyBridge(ctx)
bridge.run()  # validate() → execute() → rollback() on failure
```

---

## 핵심 규칙

- `validate()` 통과 전 `execute()` 호출 금지
- `execute()` 실패 시 `rollback()` 자동 실행
- legacy module 직접 import 금지 — bridge layer 경유 필수
- 1 Module → 1 Commit → 1 Test (정책 §7)
- `contracts/` 폴더에 모듈별 계약 문서 저장 후 이식 시작
