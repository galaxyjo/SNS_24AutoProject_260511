"""
ai_reply_generator.py — Gemini 기반 문맥 인식 DM 자동응답 생성

고정 템플릿 대신 고객 메시지를 분석해 개인화된 응답을 생성한다.
Gemini 실패 시 기존 템플릿으로 자동 폴백.

사용법:
    from modules.dm.ai_reply_generator import generate_reply

    reply = generate_reply(
        user_message="도매 단가 알고 싶어요. 100개 주문하면 얼마예요?",
        base_price=50000,
        margin_rate=0.10,
    )
"""

import os
import time

from modules.common.logger import get_logger

logger = get_logger(__name__)

_CALL_INTERVAL = 4.0
_RETRY_DELAYS  = [20, 40, 60]
_last_call_ts  = 0.0
_client        = None

_FALLBACK_TEMPLATE = (
    "안녕하세요! 문의 감사합니다 😊\n"
    "단가 기준가는 {price:,.0f}원입니다.\n"
    "수량·조건에 따라 협의 가능하오니 편하게 말씀해주세요!"
)

_SYSTEM_PROMPT = """당신은 한국 도매 쇼핑몰의 친절한 고객 응대 담당자입니다.
고객의 Instagram DM 문의에 자연스럽고 친절하게 답변하세요.

규칙:
- 한국어로만 답변
- 2~4문장 이내로 간결하게
- 이모지 1~2개 포함
- 가격 정보는 반드시 포함 (기준가 {price:,.0f}원, 마진 {margin_pct}% 포함)
- 수량·조건 협의 가능함을 언급
- 고객 메시지의 구체적인 내용(수량, 품목 등)에 맞게 개인화
- 고압적이거나 판매 강요 금지"""


def _throttle() -> None:
    global _last_call_ts
    wait = _CALL_INTERVAL - (time.time() - _last_call_ts)
    if wait > 0:
        time.sleep(wait)
    _last_call_ts = time.time()


def generate_reply(
    user_message: str,
    base_price: float,
    margin_rate: float = 0.10,
    tone_style: str = "",
    greeting_template: str = "",
    followup_template: str = "",
) -> str:
    """Gemini로 개인화된 DM 응답 생성. 실패 시 템플릿 폴백.

    tone_style/greeting_template/followup_template은 Persona_Profile 연결 전까지
    항상 빈 문자열로 호출되며, 그 경우 기존 프롬프트와 100% 동일하게 동작한다.
    """
    reply_price = round(base_price * (1 + margin_rate))

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        logger.warning("[AIReply] GEMINI_API_KEY 없음 — 템플릿 폴백")
        return _FALLBACK_TEMPLATE.format(price=reply_price)

    system = _SYSTEM_PROMPT.format(
        price=reply_price,
        margin_pct=int(margin_rate * 100),
    )
    if tone_style:
        system += f"\n\n말투: {tone_style}"
    if greeting_template:
        system += f"\n인사말 참고: {greeting_template}"
    if followup_template:
        system += f"\n팔로업 참고: {followup_template}"
    prompt = f"{system}\n\n고객 메시지:\n{user_message[:500]}\n\n응답:"

    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=api_key)

    for attempt, delay in enumerate([0] + _RETRY_DELAYS, start=1):
        if delay:
            logger.info(f"[AIReply] 429 재시도 {attempt} | {delay}초 대기")
            time.sleep(delay)
        try:
            _throttle()
            resp = _client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt,
            )
            reply = resp.text.strip()
            if reply:
                logger.info(f"[AIReply] 생성 완료 | length={len(reply)}")
                return reply
        except Exception as exc:
            err = str(exc)
            if "429" in err and attempt <= len(_RETRY_DELAYS):
                continue
            logger.warning(f"[AIReply] 생성 실패 — 템플릿 폴백 | {exc}")
            break

    return _FALLBACK_TEMPLATE.format(price=reply_price)
