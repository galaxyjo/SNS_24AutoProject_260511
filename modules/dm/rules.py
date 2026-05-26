"""modules/dm/rules.py — DM 메시지 rule-based 필터

250723 modules/dm/rules.py 설계 기반. 구조 동일, 한국어 운영 환경 반영.
banned/allowed 단어 정책으로 DM을 사전 분류한다.
AI 응답(ai_reply_generator) 앞단에서 호출된다.
"""

from modules.common.logger import get_logger

logger = get_logger(__name__)


class RuleResult:
    def __init__(self, passed: bool, reason: str = ""):
        self.passed = passed
        self.reason = reason

    def __bool__(self):
        return self.passed


def get_default_policy() -> dict:
    return {
        "banned": {
            "spam", "scam", "fraud",
            "스팸", "사기", "불법", "홍보", "광고", "도박",
        },
        "allowed": {
            "help", "support", "contact",
            "문의", "구매", "가격", "단가", "배송", "주문",
        },
    }


def evaluate(text: str, policy: dict | None = None) -> RuleResult:
    """텍스트를 정책에 따라 평가한다.

    우선순위: allowed 먼저 통과 → banned 차단 → 기본 통과.
    """
    if policy is None:
        policy = get_default_policy()

    text_lower = (text or "").strip().lower()

    for word in policy.get("allowed", []):
        if word in text_lower:
            logger.debug(f"[Rules] allowed | word={word}")
            return RuleResult(True, reason=f"allowed: {word}")

    for word in policy.get("banned", []):
        if word in text_lower:
            logger.debug(f"[Rules] banned | word={word}")
            return RuleResult(False, reason=f"banned: {word}")

    return RuleResult(True, reason="no_match")
