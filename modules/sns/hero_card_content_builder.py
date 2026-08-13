"""modules/sns/hero_card_content_builder.py — 260811 Visual Type Wiring.

`image_template_renderer.render_hero_card()`가 요구하는 짧은 텍스트(헤드라인·
서브헤드라인·4블록·태그라인)를 `topic.core_message`로부터 구조화 생성한다.

`caption_generator.generate_hook_caption()`은 한 글자도 건드리지 않는다 — 실제
캡션(라이브 게시물)에서 확인한 바, 그 함수의 9필드(HOW_POINT1/2·CORE_POINT 등)는
완전한 문장(20~35자)이라 히어로카드 블록(한 줄, 6~14자)에 그대로 쓸 수 없다
(260811 시뮬레이션으로 실측 확인, 상세는 세션 기록 참조). 대신 이미지 전용으로
별도 구조화 호출 1회를 한다 — `carousel_content_builder.py`가 이미 쓰는 검증된
패턴(Gemini structured JSON + Fail-closed 계약 검증 + 과장/수치조작 탐지)을
그대로 REUSE한다.

Fail-closed: 계약(길이·blocks 개수)을 어기거나, core_message에 없는 숫자·최상급
주장이 섞이거나, Safety 검사가 UNSAFE면 콘텐츠를 반환하지 않는다.
"""

import hashlib
import json
import time
from dataclasses import dataclass

from google.genai import types as genai_types

from modules.sns.caption_generator import (
    _MAX_ATTEMPTS,
    _classify_retry,
    _get_client,
    _next_retry_delay,
    _throttle,
    check_caption_safety,
)
from modules.sns.carousel_content_builder import _detect_possible_fabrication, _normalize_text

# 260814 ERR-113 — 실제 6회 라이브 호출 실측 결과 3/6이 SUBHEADLINE_INVALID/
# BLOCK_DESC_INVALID로 거부됐다(전부 원래 상한을 1~5자 초과, 조작·안전 문제
# 아님) — Gemini가 프롬프트에 명시한 글자수를 항상 정확히 지키지는 않는다는
# 실측 근거로 상한을 실측 분포에 여유를 둔 값으로 조정한다. `render_hero_card()`
# 의 블록 줄(`_hero_fit_block_line`)도 같은 날 폰트 축소 안전장치를 추가해,
# 이 상한을 다소 넉넉히 잡아도 시각적으로 깨지지 않는다.
_HEADLINE_MAX_CHARS = 18
_SUBHEADLINE_MAX_CHARS = 42
_BLOCK_TITLE_MAX_CHARS = 8
_BLOCK_DESC_MAX_CHARS = 20
_TAGLINE_MAX_CHARS = 26
_BLOCK_COUNT = 4

_HERO_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "subheadline": {"type": "string"},
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "desc": {"type": "string"},
                },
                "required": ["title", "desc"],
            },
        },
        "tagline": {"type": "string"},
    },
    "required": ["headline", "subheadline", "blocks", "tagline"],
}


@dataclass(frozen=True)
class HeroBlockText:
    title: str
    desc: str


@dataclass(frozen=True)
class HeroCardTextContent:
    headline: str
    subheadline: str
    blocks: "tuple[HeroBlockText, ...]"
    tagline: str
    content_fingerprint: str


@dataclass(frozen=True)
class HeroCardTextResult:
    success: bool
    content: "HeroCardTextContent | None" = None
    error_code: str = ""


def compute_hero_card_fingerprint(source_section_id: str, normalized_text: str) -> str:
    """`source_section_id + 정규화된 생성문` 조합의 결정적 해시(sha256) —
    carousel_content_builder.compute_content_fingerprint()와 동일한 목적,
    슬롯 역할/템플릿 타입이 없는 이 콘텐츠 형태에 맞춰 basis만 축소."""
    basis = f"{source_section_id}|{normalized_text}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _validate_contract(payload: dict) -> "str | None":
    """계약 위반 시 error_code를 반환한다(문제 없으면 None). 길이 상한은
    render_hero_card()의 한 줄 표시(폰트 축소로 크래시는 안 나지만, 너무 길면
    가독성이 떨어짐)를 위한 품질 기준이다 — carousel의 HOOK_MAX_CHARS와
    동일한 성격(하드 크래시 방지가 아니라 디자인 계약)."""
    headline = payload.get("headline", "")
    if not headline or len(headline) > _HEADLINE_MAX_CHARS:
        return "HEADLINE_INVALID"

    subheadline = payload.get("subheadline", "")
    if not subheadline or len(subheadline) > _SUBHEADLINE_MAX_CHARS:
        return "SUBHEADLINE_INVALID"

    blocks = payload.get("blocks")
    if not isinstance(blocks, list) or len(blocks) != _BLOCK_COUNT:
        return "BLOCK_COUNT_INVALID"
    for block in blocks:
        title = block.get("title", "")
        desc = block.get("desc", "")
        if not title or len(title) > _BLOCK_TITLE_MAX_CHARS:
            return "BLOCK_TITLE_INVALID"
        if not desc or len(desc) > _BLOCK_DESC_MAX_CHARS:
            return "BLOCK_DESC_INVALID"

    tagline = payload.get("tagline", "")
    if not tagline or len(tagline) > _TAGLINE_MAX_CHARS:
        return "TAGLINE_INVALID"

    return None


def _build_prompt(core_message: str, title: str) -> str:
    return (
        "You are writing very short label text for an Instagram info-card image "
        "(NOT the post caption), for a Korean AI-startup founder audience, using "
        "ONLY the source content below.\n\n"
        f"Source title: {title}\n"
        f"Source content (the ONLY allowed source of facts/claims): {core_message}\n\n"
        "Produce, in Korean:\n"
        f"- headline: at most {_HEADLINE_MAX_CHARS} Korean characters, noun-phrase style.\n"
        f"- subheadline: at most {_SUBHEADLINE_MAX_CHARS} Korean characters, one sentence.\n"
        f"- exactly {_BLOCK_COUNT} blocks, each with a short 'title' (at most "
        f"{_BLOCK_TITLE_MAX_CHARS} Korean characters, a label — not a full sentence) "
        f"and a short 'desc' (at most {_BLOCK_DESC_MAX_CHARS} Korean characters). "
        "The 4 blocks should break the source content's idea into 4 steps or "
        "angles, not unrelated topics.\n"
        f"- tagline: at most {_TAGLINE_MAX_CHARS} Korean characters, a punchy closing line.\n\n"
        "Rules:\n"
        "1. Do NOT invent any fact, statistic, name, or claim not present in the "
        "source content above.\n"
        "2. Keep every field within its character limit — these are short image "
        "labels, not sentences copied from the source.\n"
        "3. No exaggeration or unsupported performance numbers.\n"
        "Return the result in the exact JSON schema provided."
    )


def generate_hero_card_content(
    topic, *, client=None, throttle_fn=None, model=None,
    existing_fingerprints: "set | None" = None,
) -> HeroCardTextResult:
    """Sourcebook `topic`(source_selector.SourceTopic 또는 동일 필드를 가진
    객체)의 `core_message`로 히어로카드 전용 짧은 텍스트를 생성한다. Google
    Search/URL Context Tool을 쓰지 않는다(core_message는 이미 Sourcebook에
    있는 값 — 이 함수 자신은 인터넷에 접근하지 않는다)."""
    if not topic.core_message or not topic.core_message.strip():
        return HeroCardTextResult(success=False, error_code="INSUFFICIENT_SOURCE_EVIDENCE")

    config = genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=_HERO_RESPONSE_SCHEMA,
    )
    prompt = _build_prompt(topic.core_message, topic.title)
    active_throttle = throttle_fn or _throttle
    active_model = model or "gemini-2.5-flash-lite"

    response = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            active_throttle()
            active_client = client or _get_client()
            response = active_client.models.generate_content(
                model=active_model, contents=prompt, config=config,
            )
            break
        except Exception as exc:
            retryable, _category = _classify_retry(exc)
            if retryable and attempt < _MAX_ATTEMPTS:
                time.sleep(_next_retry_delay(attempt - 1, exc))
                continue
            return HeroCardTextResult(success=False, error_code="GENERATION_FAILED")
    if response is None:
        return HeroCardTextResult(success=False, error_code="GENERATION_FAILED")

    try:
        payload = json.loads(response.text)
    except (ValueError, AttributeError, TypeError):
        return HeroCardTextResult(success=False, error_code="RESPONSE_PARSE_FAILED")

    contract_error = _validate_contract(payload)
    if contract_error:
        return HeroCardTextResult(success=False, error_code=contract_error)

    blocks = tuple(HeroBlockText(title=b["title"], desc=b["desc"]) for b in payload["blocks"])
    headline = payload["headline"]
    subheadline = payload["subheadline"]
    tagline = payload["tagline"]
    combined_text = (
        headline + " " + subheadline + " "
        + " ".join(f"{b.title} {b.desc}" for b in blocks) + " " + tagline
    )

    if _detect_possible_fabrication(combined_text, topic.core_message):
        return HeroCardTextResult(success=False, error_code="POSSIBLE_FABRICATION")

    safety_status, safety_reason = check_caption_safety(
        combined_text, client=client, throttle_fn=throttle_fn, model=model,
    )
    if safety_status != "SAFE":
        return HeroCardTextResult(success=False, error_code=f"SAFETY_BLOCKED:{safety_reason}")

    normalized = _normalize_text(combined_text)
    fingerprint = compute_hero_card_fingerprint(topic.topic_id, normalized)
    if existing_fingerprints and fingerprint in existing_fingerprints:
        return HeroCardTextResult(success=False, error_code="DUPLICATE_FINGERPRINT")

    content = HeroCardTextContent(
        headline=headline,
        subheadline=subheadline,
        blocks=blocks,
        tagline=tagline,
        content_fingerprint=fingerprint,
    )
    return HeroCardTextResult(success=True, content=content)
