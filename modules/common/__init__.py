# modules/common/__init__.py
# ✅ manualfixed: circular import 방지를 위해 내용 제거

# 내부 모듈은 각 사용처(test, main 등)에서 직접 import 하도록 구성
# 예: from modules.common import base_types → 권장 ❌
#     import modules.common.base_types as base_types → 권장 ✅
