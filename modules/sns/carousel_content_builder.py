"""modules/sns/carousel_content_builder.py — 260805 Track B 7B-3 Sourcebook
Carousel Content Contract Canary.

이 모듈은 Canary로 존재한다 — 코드·Target Test는 있지만 `launcher/main.py`
Producer 실행 경로에는 연결하지 않는다(Runtime NOT APPLIED, 회장 별도 승인
후 연결). 기존 단일 caption 생성(`caption_generator.generate_hook_caption`)/
Content Package 저장(`content_package_builder.create_content_package`)은 이
파일이 단 1줄도 수정하지 않는다 — 완전히 별개의 새 함수 집합이다.

슬롯 역할 매핑(회장 승인, 260805 7B-2/7B-3 검수) — `launcher/main.py`에 이미
존재하는 Producer/Posting 슬롯 정수 튜플 `(5, 9, 16)`/`(6, 10, 17)`을 그대로
REUSE한다(새 시간판정 로직 아님, 이미 존재하는 두 튜플의 위치 대응):
    Producer 05:00 → Posting 06:00 → REACH
    Producer 09:00 → Posting 10:00 → ENGAGEMENT
    Producer 16:00 → Posting 17:00 → SAVE_SHARE

REUSE 원칙:
  - Gemini 예외 분류/재시도(`caption_generator._classify_retry`/`_next_retry_delay`/
    `_MAX_ATTEMPTS`) 그대로 재사용.
  - 안전성 확인은 신규 정책 엔진을 만들지 않고 기존 `caption_generator.
    check_caption_safety()`를 그대로 재사용한다.
  - Vault 조회는 `content_package_builder.py`를 import하지 않는다(순환참조
    방지, 그 파일도 이 파일을 모른다) — 이 파일 자체가 필요한 최소 frontmatter
    파싱만 독립적으로 갖는다(같은 파일 포맷을 읽기만 하므로 파싱 로직
    복제는 REUSE 범위 안의 불가피한 최소 중복으로 판단).

Fail-closed: 8-Slide/Caption/Hashtag 계약을 하나라도 못 지키거나, 생성된
텍스트에 원문(core_message)에 없는 숫자·통계가 섞여 있거나(최선노력 기계적
탐지 — 이름/사례 등 비수치 날조까지 완전히 잡아내지는 못한다, 프롬프트
차원의 grounding 지시가 1차 방어선), Safety 검사가 UNSAFE면 콘텐츠를
반환하지 않는다.
"""

import hashlib
import json
import re
import time
from dataclasses import dataclass, field

from google.genai import types as genai_types

from modules.common.logger import get_logger
from modules.sns.caption_generator import (
    _MAX_ATTEMPTS,
    _classify_retry,
    _get_client,
    _next_retry_delay,
    _throttle,
    check_caption_safety,
)

logger = get_logger(__name__)

# ── 슬롯 역할 매핑(REUSE — launcher/main.py의 기존 (5,9,16)/(6,10,17) 튜플과 위치 대응) ──
SLOT_ROLE_BY_PRODUCER_HOUR = {5: "REACH", 9: "ENGAGEMENT", 16: "SAVE_SHARE"}
SLOT_ROLE_BY_POSTING_HOUR = {6: "REACH", 10: "ENGAGEMENT", 17: "SAVE_SHARE"}
VALID_SLOT_ROLES = frozenset(SLOT_ROLE_BY_PRODUCER_HOUR.values())

# 260805 7B-4 — 슬롯 역할별 기본 템플릿(원 지시문의 역할 설명을 그대로 REUSE:
# REACH="훅형 정보요약"→HOOK_IMPACT, ENGAGEMENT="의견·질문·비교형"→COMPARE,
# SAVE_SHARE="리스트·체크리스트형"→LIST). 임의 발명이 아니라 이미 승인된
# 역할 설명 문구와 5개 템플릿 정의를 그대로 대응시킨 것이다.
DEFAULT_TEMPLATE_BY_SLOT_ROLE = {"REACH": "HOOK_IMPACT", "ENGAGEMENT": "COMPARE", "SAVE_SHARE": "LIST"}

TEMPLATE_TYPES = ("HOOK_IMPACT", "LIST", "CONTRARIAN", "COMPARE", "BEHIND_SCENE")

DESIGN_METADATA = {
    "canvas": "1080x1350",
    "ratio": "4:5",
    "background": "#0D1117",
    "primary_text": "#FFFFFF",
    "accent": "#38BDF8",
    "typography": "high-contrast sans-serif",
    "layout": "minimal",
}

_HOOK_MAX_CHARS = 15
_BODY_MAX_WORDS = 30
_CAPTION_MAX_CHARS = 400
_HASHTAG_MIN = 5
_HASHTAG_MAX = 8
_SLIDE_COUNT = 8
# 261023 STEP 4-AE — AIJOMOOJIN 2~4장 카드뉴스. 기본값은 기존 8장 그대로 두고, 호출자가
# slide_count로 2~4를 고를 때만 짧은 계약을 쓴다. 1장 텍스트는 표지 제목 한 줄이며,
# 히어로카드 headline 한 줄 상한(hero_card_content_builder._HEADLINE_MAX_CHARS=40)과 맞춘다.
SHORT_SLIDE_COUNTS = (2, 3, 4)
_COVER_TITLE_MAX_CHARS = 40

_CAROUSEL_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "slides": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "role": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["index", "role", "text"],
            },
        },
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["slides", "caption", "hashtags"],
}


@dataclass(frozen=True)
class Slide:
    index: int
    role: str
    text: str


@dataclass(frozen=True)
class CarouselContent:
    slot_role: str
    template_type: str
    source_section_id: str
    source_title: str
    source_url: str
    slides: "tuple[Slide, ...]"
    caption: str
    hashtags: "tuple[str, ...]"
    content_fingerprint: str
    design_metadata: dict = field(default_factory=lambda: dict(DESIGN_METADATA))


@dataclass(frozen=True)
class CarouselResult:
    success: bool
    content: "CarouselContent | None" = None
    error_code: str = ""


def slot_role_for_producer_hour(producer_hour: int) -> "str | None":
    """기존 `_producer_hour` 값(5/9/16)으로 슬롯 역할을 REUSE 매핑한다.
    등록되지 않은 값이면(임의 시간판정 금지) None(UNKNOWN)을 반환한다."""
    return SLOT_ROLE_BY_PRODUCER_HOUR.get(producer_hour)


def slot_role_for_posting_hour(posting_hour: int) -> "str | None":
    return SLOT_ROLE_BY_POSTING_HOUR.get(posting_hour)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def compute_content_fingerprint(
    source_section_id: str, slot_role: str, template_type: str, normalized_text: str,
) -> str:
    """`source_section_id + slot_role + template_type + 정규화된 생성문` 조합의
    결정적 해시(sha256)를 계산한다 — 새 DB 없이 기존 Vault frontmatter의 한
    필드로 저장·조회 가능한 값이다."""
    basis = f"{source_section_id}|{slot_role}|{template_type}|{normalized_text}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _extract_numeric_tokens(text: str) -> set:
    return set(re.findall(r"\d[\d,.]*%?", text))


# 260805 회장 지시(2차 검수 보완) — "과장·근거 없는 성과 수치 금지" 계약의
# 수치 외 축(단정적 최상급 주장)도 최선노력으로 잡는다. 신규 NLP 엔진이
# 아니라 고정 키워드 목록 매칭이다(범위 명시, 완전한 사실검증 아님).
_SUPERLATIVE_CLAIM_WORDS = ("최초", "유일", "업계 최고", "역대", "보장", "1위")


def _detect_possible_fabrication(generated_text: str, core_message: str) -> bool:
    """최선노력 기계적 grounding 확인 두 축 — (1) 생성문에만 있고 원문
    (core_message)에는 없는 숫자·통계 토큰, (2) 원문에 없는 단정적 최상급
    주장 키워드. 이름·사례 등 그 외 비수치·비최상급 날조는 이 검사로 잡지
    못한다(문서화된 한계, 신규 NLP 엔진을 만들지 않기 위한 의도적 최소
    구현)."""
    generated_numbers = _extract_numeric_tokens(generated_text)
    source_numbers = _extract_numeric_tokens(core_message)
    if generated_numbers and not generated_numbers.issubset(source_numbers):
        return True

    for word in _SUPERLATIVE_CLAIM_WORDS:
        if word in generated_text and word not in core_message:
            return True
    return False


_CTA_KEYWORDS = ("저장", "댓글", "공유", "팔로우", "구독", "확인하세요", "확인해보세요", "링크")


def _count_cta_sentences(text: str) -> int:
    """텍스트를 문장 단위로 나눠 CTA 키워드를 포함한 문장 수를 센다(최선노력
    키워드 매칭 — 의미 기반 CTA 탐지 아님, 범위 명시)."""
    sentences = re.split(r"[.!?\n]+", text)
    return sum(
        1 for s in sentences
        if s.strip() and any(keyword in s for keyword in _CTA_KEYWORDS)
    )


_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]*")
_IMPERATIVE_END_RE = re.compile(r"세요[.!?]*$")


def _sentences(text: str) -> "list[str]":
    return [s.strip() for s in _SENTENCE_RE.findall(text or "") if s.strip()]


def _is_pure_cta_sentence(sentence: str) -> bool:
    """CTA 키워드가 있고 '~세요'로 끝나는 독립 문장만 순수 CTA로 본다(혼합 문장은 아님)."""
    return _count_cta_sentences(sentence) == 1 and bool(_IMPERATIVE_END_RE.search(sentence.strip()))


def _move_pure_ctas(blocks: "list[str]") -> "list[str]":
    """마지막 블록을 뺀 블록에서 순수 CTA 문장만 떼어 내 마지막 블록 끝에 1개만 둔다.
    혼합 문장(키워드는 있지만 순수 CTA가 아님)은 건드리지 않는다 — 검증이 그대로 Fail-closed한다.
    떼어 내면 블록이 비는 경우도 건드리지 않는다."""
    if not blocks:
        return blocks
    moved = []
    out = []
    for block in blocks[:-1]:
        kept, taken = [], []
        for s in _sentences(block):
            (taken if _is_pure_cta_sentence(s) else kept).append(s)
        if taken and kept:
            out.append(" ".join(kept))
            moved.extend(taken)
        else:
            out.append(block)
    last_sentences = _sentences(blocks[-1])
    last_ctas = [s for s in last_sentences if _is_pure_cta_sentence(s)]
    keep_cta = last_ctas[-1] if last_ctas else (moved[-1] if moved else None)
    last_body = [s for s in last_sentences if not _is_pure_cta_sentence(s)]
    if keep_cta is None or (not moved and len(last_ctas) <= 1):
        out.append(blocks[-1])               # 바로잡을 것이 없으면 원문 그대로
    else:
        out.append(" ".join(last_body + [keep_cta]))
    return out


def _normalize_short_cta(payload: dict) -> dict:
    """261023 STEP 4-AI — 짧은 캐러셀(2~4장)의 순수 CTA 문장 위치만 바로잡는다(Gemini 재호출 없음).
    표지(1장)는 제목 한 줄이라 건드리지 않는다(CTA가 있으면 검증이 Fail-closed). 본문 장과 캡션 줄에서
    순수 CTA 문장을 떼어 마지막 장·마지막 줄 끝에 정확히 1개만 남긴다. 검증 규칙은 그대로이고,
    정규화 뒤 텍스트로 날조·Safety 검사를 한다."""
    slides = payload.get("slides")
    if not isinstance(slides, list) or len(slides) < 2:
        return payload
    ordered = sorted((dict(s) for s in slides), key=lambda s: s.get("index", -1))
    body_texts = _move_pure_ctas([s.get("text", "") for s in ordered[1:]])
    for slide, text in zip(ordered[1:], body_texts):
        slide["text"] = text
    caption = payload.get("caption", "")
    lines = [line for line in caption.splitlines() if line.strip()]
    fixed = _move_pure_ctas(lines)
    if lines and fixed != lines:
        caption = ("\n\n" if "\n\n" in caption else "\n").join(fixed)
    return {**payload, "slides": ordered, "caption": caption}


def _cta_location_summary(payload: dict) -> str:
    """실패 위치 로그용 — 본문 없이 장·줄별 CTA 문장 수만."""
    slides = sorted(payload.get("slides") or [], key=lambda s: s.get("index", -1))
    slide_counts = [_count_cta_sentences(s.get("text", "")) for s in slides]
    lines = [line for line in (payload.get("caption") or "").splitlines() if line.strip()]
    return f"slide_cta={slide_counts} caption_line_cta={[_count_cta_sentences(l) for l in lines]}"


def _validate_short_contract(payload: dict, slide_count: int) -> "str | None":
    """261023 STEP 4-AE — 2~4장 계약. 1장은 표지 제목 한 줄, 나머지 장은 짧은 본문,
    마지막 장에만 CTA 1개. 캡션·해시태그 계약은 8장과 같다."""
    slides = payload.get("slides")
    if not isinstance(slides, list) or len(slides) != slide_count:
        return "SLIDE_COUNT_INVALID"

    ordered = sorted(slides, key=lambda s: s.get("index", -1))
    if [s.get("index") for s in ordered] != list(range(1, slide_count + 1)):
        return "SLIDE_INDEX_INVALID"

    cover_title = ordered[0].get("text", "")
    if (not cover_title.strip() or "\n" in cover_title.strip()
            or len(cover_title.strip()) > _COVER_TITLE_MAX_CHARS):
        return "COVER_TITLE_INVALID"

    for slide in ordered[1:]:
        text = slide.get("text", "")
        if not text.strip():
            return "SLIDE_TEXT_EMPTY"
        if len(text.split()) > _BODY_MAX_WORDS:
            return "BODY_SLIDE_TOO_LONG"

    for slide in ordered[:-1]:
        if _count_cta_sentences(slide.get("text", "")) > 0:
            return "CTA_NOT_LAST_SLIDE"
    if _count_cta_sentences(ordered[-1].get("text", "")) != 1:
        return "LAST_SLIDE_CTA_COUNT_INVALID"

    return _validate_caption_and_hashtags(payload)


def _validate_caption_and_hashtags(payload: dict) -> "str | None":
    caption = payload.get("caption", "")
    if not caption or len(caption) > _CAPTION_MAX_CHARS:
        return "CAPTION_LENGTH_INVALID"

    hashtags = payload.get("hashtags")
    if not isinstance(hashtags, list) or not (_HASHTAG_MIN <= len(hashtags) <= _HASHTAG_MAX):
        return "HASHTAG_COUNT_INVALID"

    caption_lines = [line for line in caption.splitlines() if line.strip()]
    last_line = caption_lines[-1] if caption_lines else ""
    if _count_cta_sentences(last_line) != 1:
        return "CAPTION_CTA_COUNT_INVALID"
    other_lines_cta = sum(_count_cta_sentences(line) for line in caption_lines[:-1])
    if other_lines_cta > 0:
        return "CAPTION_CTA_NOT_LAST"
    return None


def _validate_contract(payload: dict) -> "str | None":
    """구조 계약 위반 시 error_code를 반환한다(문제 없으면 None)."""
    slides = payload.get("slides")
    if not isinstance(slides, list) or len(slides) != _SLIDE_COUNT:
        return "SLIDE_COUNT_INVALID"

    ordered = sorted(slides, key=lambda s: s.get("index", -1))
    if [s.get("index") for s in ordered] != list(range(1, _SLIDE_COUNT + 1)):
        return "SLIDE_INDEX_INVALID"

    hook_text = ordered[0].get("text", "")
    if len(hook_text) > _HOOK_MAX_CHARS:
        return "HOOK_TOO_LONG"

    for slide in ordered[2:6]:  # Slide 3~6 (0-based index 2~5)
        word_count = len(slide.get("text", "").split())
        if word_count > _BODY_MAX_WORDS:
            return "BODY_SLIDE_TOO_LONG"

    caption = payload.get("caption", "")
    if not caption or len(caption) > _CAPTION_MAX_CHARS:
        return "CAPTION_LENGTH_INVALID"

    hashtags = payload.get("hashtags")
    if not isinstance(hashtags, list) or not (_HASHTAG_MIN <= len(hashtags) <= _HASHTAG_MAX):
        return "HASHTAG_COUNT_INVALID"

    # 260805 회장 지시(2차 검수 보완) — "Slide 8: CTA 1개"·"Caption CTA는
    # 마지막에 1개만" 계약을 최선노력 키워드 매칭으로 기계 검증한다(의미
    # 기반 CTA 탐지가 아니므로 오탐 가능성은 있음, 범위 명시).
    slide_8_text = ordered[7].get("text", "")
    if _count_cta_sentences(slide_8_text) != 1:
        return "SLIDE_8_CTA_COUNT_INVALID"

    caption_lines = [line for line in caption.splitlines() if line.strip()]
    last_line = caption_lines[-1] if caption_lines else ""
    if _count_cta_sentences(last_line) != 1:
        return "CAPTION_CTA_COUNT_INVALID"
    other_lines_cta = sum(_count_cta_sentences(line) for line in caption_lines[:-1])
    if other_lines_cta > 0:
        return "CAPTION_CTA_NOT_LAST"

    return None


def _build_prompt(
    core_message: str, title: str, slot_role: str, template_type: str,
) -> str:
    return (
        "You are writing an 8-slide Instagram carousel (card-news) for a Korean "
        "AI-startup solo-entrepreneur audience, using ONLY the source content below.\n\n"
        f"Source title: {title}\n"
        f"Source content (the ONLY allowed source of facts/numbers/claims): "
        f"{core_message}\n\n"
        f"Slot role: {slot_role} "
        "(REACH=hook-style info summary, ENGAGEMENT=opinion/question/comparison, "
        "SAVE_SHARE=list/checklist).\n"
        f"Sentence template: {template_type}.\n\n"
        "Rules:\n"
        "1. Do NOT invent any fact, statistic, name, or claim not present in the "
        "source content above. Paraphrase and restructure meaning — do not copy "
        "sentences verbatim.\n"
        "2. Produce exactly 8 slides:\n"
        "   Slide 1: hook, at most 15 Korean characters.\n"
        "   Slide 2: problem or background.\n"
        "   Slide 3-6: exactly one core concept each, at most 30 words each.\n"
        "   Slide 7: summary or one immediately-actionable step.\n"
        "   Slide 8: exactly one call to action.\n"
        "3. No exaggeration, fear-mongering, or unsupported performance numbers.\n"
        "4. Also produce a Korean caption (<=400 chars, one sentence per line, "
        "blank line between paragraphs, first line a hook <=15 chars, exactly one "
        "CTA at the end matching the slot role) and 5-8 hashtags (array, separate "
        "from the caption body, using only terms present in the source content or "
        "generic allowed startup/AI terms — never claim a tag is 'mid-size/high "
        "performing').\n"
        "Return the result in the exact JSON schema provided."
    )


_SHORT_SLIDE_PLANS = {
    2: ("   Slide 1: cover title — one line, at most 40 Korean characters, the reader's problem or "
        "benefit (not a generic description).\n"
        "   Slide 2: how a Korean business owner or office worker can use it, ending with exactly "
        "one call to action.\n"),
    3: ("   Slide 1: cover title — one line, at most 40 Korean characters, the reader's problem or "
        "benefit (not a generic description).\n"
        "   Slide 2: the verified key facts or features, explained simply, at most 30 words.\n"
        "   Slide 3: how a Korean business owner or office worker can apply it, at most 30 words, "
        "ending with exactly one call to action.\n"),
    4: ("   Slide 1: cover title — one line, at most 40 Korean characters, the reader's problem or "
        "benefit (not a generic description).\n"
        "   Slide 2: the verified key facts or features, explained simply, at most 30 words.\n"
        "   Slide 3: how a Korean business owner or office worker can apply it, at most 30 words.\n"
        "   Slide 4: a short checklist or why it is worth saving, ending with exactly one call to "
        "action.\n"),
}


def _build_short_prompt(core_message: str, title: str, slot_role: str, template_type: str,
                        slide_count: int) -> str:
    return (
        f"You are writing a {slide_count}-slide Instagram carousel (card-news) for Korean small-business "
        "owners and office workers who want to use AI tools, using ONLY the source content below.\n\n"
        f"Source title: {title}\n"
        f"Source content (the ONLY allowed source of facts/numbers/claims): {core_message}\n\n"
        f"Slot role: {slot_role}. Sentence template: {template_type}.\n\n"
        "Rules:\n"
        "1. Do NOT invent any fact, statistic, name, or claim not present in the source content above. "
        "Paraphrase — do not copy sentences verbatim.\n"
        f"2. Produce exactly {slide_count} slides. Only the last slide may contain a call to action. "
        "The call to action is ONE separate final sentence that must contain one of these Korean words: "
        "저장, 공유, 팔로우, 댓글 (e.g. '필요할 때 다시 보도록 저장하세요.'). No other sentence anywhere may use "
        "those words or '확인해 보세요'.\n"
        + _SHORT_SLIDE_PLANS[slide_count] +
        "3. No exaggeration, fear-mongering, or unsupported performance numbers. No long paragraphs.\n"
        "4. Also produce a Korean caption (<=400 chars) with at least three lines separated by line breaks. "
        "Its first two lines explain the practical value for the reader instead of repeating the slides. "
        "The last line is exactly one CTA sentence containing 저장, 공유, 팔로우 or 댓글; no other caption line "
        "may contain those words. Then 5-8 "
        "relevant hashtags (array, separate from the caption body, Korean search terms related to this "
        "content are preferred).\n"
        "Return the result in the exact JSON schema provided."
    )


def generate_carousel_content(
    topic, slot_role: str, template_type: str,
    *, client=None, throttle_fn=None, model=None,
    existing_fingerprints: "set | None" = None,
    slide_count: int = _SLIDE_COUNT,
) -> CarouselResult:
    """Sourcebook `topic`(source_selector.SourceTopic 또는 동일 필드를 가진
    객체) + 슬롯 역할 + 문장 템플릿으로 8-Slide 카드뉴스 구조화 콘텐츠 1건을
    생성한다. Google Search/URL Context Tool을 전혀 쓰지 않는다(topic.
    core_message는 이미 Sourcebook에 있는 값 — 이 함수 자신은 인터넷에
    접근하지 않는다).

    261023 STEP 4-AE — slide_count: 기본 8(기존 계약 그대로). 2~4를 주면 짧은 계약
    (_validate_short_contract)과 짧은 프롬프트를 쓴다. 그 밖의 값은 Gemini 호출 없이 실패."""
    if slide_count != _SLIDE_COUNT and slide_count not in SHORT_SLIDE_COUNTS:
        return CarouselResult(success=False, error_code="SLIDE_COUNT_UNSUPPORTED")
    if slot_role not in VALID_SLOT_ROLES:
        return CarouselResult(success=False, error_code="SLOT_ROLE_UNKNOWN")
    if template_type not in TEMPLATE_TYPES:
        return CarouselResult(success=False, error_code="TEMPLATE_TYPE_UNKNOWN")
    if not topic.core_message or not topic.core_message.strip():
        return CarouselResult(success=False, error_code="INSUFFICIENT_SOURCE_EVIDENCE")

    config = genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=_CAROUSEL_RESPONSE_SCHEMA,
    )
    short = slide_count in SHORT_SLIDE_COUNTS
    prompt = (
        _build_short_prompt(topic.core_message, topic.title, slot_role, template_type, slide_count)
        if short else _build_prompt(topic.core_message, topic.title, slot_role, template_type)
    )
    active_throttle = throttle_fn or _throttle
    # 260805 7B-4 Live Canary에서 발견된 결함 수정 — model=None을 그대로 SDK에
    # 넘기면 요청 URL에 "{model}"이 문자 그대로 들어가 404가 난다(실제 Runtime
    # Evidence로 확인). `check_caption_safety()`와 동일한 fallback 패턴 적용.
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
            return CarouselResult(success=False, error_code="GENERATION_FAILED")
    if response is None:
        return CarouselResult(success=False, error_code="GENERATION_FAILED")

    try:
        payload = json.loads(response.text)
    except (ValueError, AttributeError, TypeError):
        return CarouselResult(success=False, error_code="RESPONSE_PARSE_FAILED")

    if short:
        payload = _normalize_short_cta(payload)
    contract_error = (
        _validate_short_contract(payload, slide_count) if short else _validate_contract(payload)
    )
    if contract_error:
        if short:
            logger.warning(f"[CarouselContent] 계약 실패 | {contract_error} | {_cta_location_summary(payload)}")
        return CarouselResult(success=False, error_code=contract_error)

    slides = tuple(
        Slide(index=s["index"], role=s.get("role", ""), text=s["text"])
        for s in sorted(payload["slides"], key=lambda s: s["index"])
    )
    caption = payload["caption"]
    hashtags = tuple(payload["hashtags"])
    combined_text = " ".join(s.text for s in slides) + " " + caption

    # 260817 ERR-115 — 위 _build_prompt() 호출도 core_message와 title을 함께
    # Gemini에게 근거로 주므로, 검증 대상도 동일하게 title을 포함해야 title에만
    # 있는 숫자(버전 등)를 날조로 오판정하지 않는다(hero_card_content_builder.py
    # 동일 수정과 짝).
    grounding_text = topic.core_message + " " + topic.title
    if _detect_possible_fabrication(combined_text, grounding_text):
        return CarouselResult(success=False, error_code="POSSIBLE_FABRICATION")

    safety_status, safety_reason = check_caption_safety(
        combined_text, client=client, throttle_fn=throttle_fn, model=model,
    )
    if safety_status != "SAFE":
        return CarouselResult(success=False, error_code=f"SAFETY_BLOCKED:{safety_reason}")

    normalized = _normalize_text(caption + " " + " ".join(s.text for s in slides))
    fingerprint = compute_content_fingerprint(
        topic.topic_id, slot_role, template_type, normalized,
    )
    if existing_fingerprints and fingerprint in existing_fingerprints:
        return CarouselResult(success=False, error_code="DUPLICATE_FINGERPRINT")

    content = CarouselContent(
        slot_role=slot_role,
        template_type=template_type,
        source_section_id=topic.topic_id,
        source_title=topic.title,
        source_url=topic.source_url,
        slides=slides,
        caption=caption,
        hashtags=hashtags,
        content_fingerprint=fingerprint,
    )
    return CarouselResult(success=True, content=content)


_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_FIELD_RE = re.compile(r"^(\w+):\s*(.*)$", re.MULTILINE)


def scan_existing_fingerprints(vault_root) -> set:
    """Vault content/*.md 중 status: complete이고 `content_fingerprint` 필드가
    있는 항목의 fingerprint 집합을 반환한다. 기존(이 Canary 이전) 항목은 이
    필드가 없어 자연히 제외된다 — 이 Canary가 실제 Runtime에 연결된 이후
    생성되는 항목부터 이 중복방지가 실제로 작동한다. 새 DB/Queue 없이 기존
    Vault 파일만 읽는다(REUSE)."""
    content_dir = vault_root / "content"
    fingerprints: set = set()
    if not content_dir.exists():
        return fingerprints
    for md_file in sorted(content_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        m = _FRONTMATTER_RE.match(text)
        if not m:
            continue
        for line_m in _FIELD_RE.finditer(m.group(1)):
            key, raw_value = line_m.group(1), line_m.group(2).strip()
            if key != "content_fingerprint":
                continue
            try:
                value = json.loads(raw_value)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(value, str) and value:
                fingerprints.add(value)
    return fingerprints
