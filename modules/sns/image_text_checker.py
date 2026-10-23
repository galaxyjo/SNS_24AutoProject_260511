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

import json
import time
from dataclasses import dataclass

from google.genai import types as genai_types

from modules.common.logger import get_logger
from modules.sns.caption_generator import _MAX_ATTEMPTS, _classify_retry, _next_retry_delay, _throttle

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

    try:
        items = json.loads(response.text)["images"]
        checks = tuple(
            ImageCheck(index=item["index"], has_text=item["has_text"], has_logo=item["has_logo"])
            for item in sorted(items, key=lambda item: item["index"])
        )
    except (ValueError, AttributeError, TypeError, KeyError):
        return ImageCheckResult(success=False, error_code="CHECK_PARSE_FAILED")

    if ([c.index for c in checks] != list(range(1, len(images) + 1))
            or any(not isinstance(c.has_text, bool) or not isinstance(c.has_logo, bool) for c in checks)):
        return ImageCheckResult(success=False, error_code="CHECK_RESULT_INVALID")

    logger.info("[ImageTextCheck] 판독 완료 | "
                + " ".join(f"{c.index}:text={c.has_text},logo={c.has_logo}" for c in checks))
    return ImageCheckResult(success=True, checks=checks)
