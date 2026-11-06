"""modules/sns/image_text_checker.py — 261023 STEP 4-AM 생성 이미지 글자·로고 판독.

Cloudflare Flux는 "글자·로고 금지" 지시를 지키지 않는다(261023 노트 손그림 샘플 실측:
6장 중 노트북 사과 로고 1장, "Cafe" 간판 1장, 재생성 후에도 형광펜 글자·작은 서명).
Tesseract(content_filter._ocr_image_state)는 같은 샘플에서 서명 "AML"을 놓치고 글자가
없는 그림에서 "QQ"를 찾았다(오탐) — 그래서 이 판독은 페르소나 전용 Gemini의 이미지
입력으로 한다(261023 4-AN/4-AO 판독 테스트: 서명 글자 탐지, Apple·Starbucks 로고 탐지,
글자·로고 없는 그림 2장 정상 판정).

Fail-closed: client가 없거나(공유 GEMINI_API_KEY로 대체하지 않는다), 호출·파싱이 실패하거나,
결과 장 수·순서가 입력과 다르면 success=False. 판독이 애매하면 has_text/has_logo=True로
답하라고 지시한다. 로그에는 장 번호와 True/False만 남기고 모델이 읽은 글자는 남기지 않는다.
"""

import io
import json
import time
from dataclasses import dataclass

from google.genai import types as genai_types

from modules.common.logger import get_logger
from modules.sns.caption_generator import (
    _MAX_ATTEMPTS, _classify_retry, _next_retry_delay, _throttle, TextAIFallbackClient,
)

logger = get_logger(__name__)

_CHECK_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "images": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "has_text": {"type": "boolean"},
                    "has_logo": {"type": "boolean"},
                },
                "required": ["index", "has_text", "has_logo"],
            },
        },
    },
    "required": ["images"],
}

_CHECK_PROMPT = (
    "You are a strict quality inspector for social media illustrations. For each image in order "
    "(index 1..N), report whether ANY text is visible: letters, words, numbers, signatures, initials, "
    "scribbles that look like writing, labels on objects — even tiny ones in corners or on props. "
    "Also report whether any real company logo or brand mark is visible (e.g. a fruit logo on a laptop). "
    "When unsure, answer true."
)


@dataclass(frozen=True)
class ImageCheck:
    index: int
    has_text: bool
    has_logo: bool

    @property
    def passed(self) -> bool:
        return not self.has_text and not self.has_logo


@dataclass(frozen=True)
class ImageCheckResult:
    success: bool
    checks: "tuple[ImageCheck, ...]" = ()
    error_code: str = ""


def check_images_for_text_and_logo(
    images: "list[bytes]", *, client=None, throttle_fn=None, model=None,
) -> ImageCheckResult:
    """PNG bytes 목록을 Gemini 1회 호출로 판독한다. checks는 입력 순서(index 1..N)와 같다."""
    if not images or any(not data for data in images):
        return ImageCheckResult(success=False, error_code="CHECK_INPUT_EMPTY")
    if client is None:
        return ImageCheckResult(success=False, error_code="CHECK_CLIENT_MISSING")

    if isinstance(client, TextAIFallbackClient) and client.vision_enabled:
        return _check_with_text_ai(images, client)

    contents = [_CHECK_PROMPT] + [
        genai_types.Part.from_bytes(data=data, mime_type="image/png") for data in images
    ]
    config = genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=_CHECK_RESPONSE_SCHEMA,
    )
    active_throttle = throttle_fn or _throttle
    active_model = model or "gemini-2.5-flash-lite"

    response = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            active_throttle()
            response = client.models.generate_content(model=active_model, contents=contents, config=config)
            break
        except Exception as exc:
            retryable, _category = _classify_retry(exc)
            if retryable and attempt < _MAX_ATTEMPTS:
                time.sleep(_next_retry_delay(attempt - 1, exc))
                continue
            logger.warning(f"[ImageTextCheck] 판독 호출 실패 | error_type={type(exc).__name__}")
            return ImageCheckResult(success=False, error_code="CHECK_CALL_FAILED")
    if response is None:
        return ImageCheckResult(success=False, error_code="CHECK_CALL_FAILED")

    return _parse_check_response(response.text, len(images))


def _parse_check_response(response_text: str, image_count: int) -> ImageCheckResult:
    """판독 응답(JSON 문자열)을 검증해 ImageCheckResult로 만든다. Gemini·Workers AI 경로가 같은 검증을 쓴다."""
    try:
        items = json.loads(response_text)["images"]
        checks = tuple(
            ImageCheck(index=item["index"], has_text=item["has_text"], has_logo=item["has_logo"])
            for item in sorted(items, key=lambda item: item["index"])
        )
    except (ValueError, AttributeError, TypeError, KeyError):
        return ImageCheckResult(success=False, error_code="CHECK_PARSE_FAILED")

    if ([c.index for c in checks] != list(range(1, image_count + 1))
            or any(not isinstance(c.has_text, bool) or not isinstance(c.has_logo, bool) for c in checks)):
        return ImageCheckResult(success=False, error_code="CHECK_RESULT_INVALID")

    logger.info("[ImageTextCheck] 판독 완료 | "
                + " ".join(f"{c.index}:text={c.has_text},logo={c.has_logo}" for c in checks))
    return ImageCheckResult(success=True, checks=checks)


# 261107 — Workers AI는 입력 이미지 토큰이 neurons를 좌우한다(3장 호출: 768px 4,561토큰 → 512px 2,386토큰, 결과 동일).
# 운영 판독 이미지(Flux 1024px)를 긴 변 512px로 줄여 보내 하루 무료 한도(10,000 neurons) 안에 들어오게 한다.
_VISION_MAX_SIDE_PX = 512


def _downscale_png(data: bytes, max_side: int = _VISION_MAX_SIDE_PX) -> bytes:
    """긴 변이 max_side를 넘으면 비율 유지로 줄인 PNG bytes를 돌려준다(이미 작으면 그대로). 실패하면 예외."""
    from PIL import Image
    with Image.open(io.BytesIO(data)) as im:
        if max(im.size) <= max_side:
            return data
        small = im.convert("RGB")
        small.thumbnail((max_side, max_side), Image.LANCZOS)
        out = io.BytesIO()
        small.save(out, "PNG")
        return out.getvalue()


def _check_with_text_ai(images: "list[bytes]", client: TextAIFallbackClient) -> ImageCheckResult:
    """Workers AI(OpenAI 호환)로 판독한다. 축소·호출·파싱 실패와 결과 불일치는 모두 Fail-closed."""
    config = genai_types.GenerateContentConfig(
        response_mime_type="application/json", response_json_schema=_CHECK_RESPONSE_SCHEMA,
    )
    try:
        small = [_downscale_png(data) for data in images]
        response = client.generate_vision(_CHECK_PROMPT, small, config)
    except Exception as exc:
        logger.warning(f"[ImageTextCheck] 판독 호출 실패(Workers AI) | error_type={type(exc).__name__}")
        return ImageCheckResult(success=False, error_code="CHECK_CALL_FAILED")
    return _parse_check_response(response.text, len(images))
