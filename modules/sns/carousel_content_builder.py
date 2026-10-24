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


# 261023 STEP 4-AM — 노트 손그림 캐러셀. with_image_scenes=True일 때만 slide마다 영어 장면 묘사를
# 같은 Gemini 호출에서 함께 받는다(추가 호출 없음). 기존 호출은 이 스키마를 쓰지 않는다.
_IMAGE_SCENE_MAX_WORDS = 45
# 장면 묘사에 들어가면 이미지 모델이 글자·로고를 그려 넣기 쉬운 단어(260723 샘플 실측: 노트북 로고,
# 카페 간판). 금지 지시도 단어를 불러오므로 "no text"처럼 부정형으로 쓰는 것도 막는다.
_IMAGE_SCENE_FORBIDDEN_RE = re.compile(
    r"\b(logos?|brand(?:s|ed|ing)?|texts?|letters?|words?|writing|written|signs?|signage|labels?|"
    r"captions?|screens?|monitors?|laptops?|computers?|phones?|smartphones?|tablets?|posters?|"
    r"banners?|newspapers?|documents?|notes?|notepads?|notebooks?|papers?|books?|speech\s+bubbles?|"
    r"talking)\b|\d",
    re.IGNORECASE,
)
_SHORT_SCENE_RESPONSE_SCHEMA = {
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
                    "image_scene": {"type": "string"},
                },
                "required": ["index", "role", "text", "image_scene"],
            },
        },
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["slides", "caption", "hashtags"],
}
_IMAGE_SCENE_RULE = (
    "5. For EVERY slide also write image_scene: one plain English sentence (max 40 words) describing a "
    "simple drawing that shows exactly what that slide's text says — who or what is in it and what is "
    "happening. Use only ideas from that slide's text. Prefer a scene that shows how the information "
    "works (something going in, being handled and coming out, or an old way next to a new way) over a "
    "generic person at a desk. Use generic people and everyday objects only. "
    "Never mention company, product or brand names, numbers, or any screen, laptop, phone, computer, "
    "document, poster, sign, note, notepad, notebook, paper, book or speech bubble, show conversations "
    "as people facing each other and gesturing (never 'talking'), and do not write words such as text, "
    "letters, logo or label at all "
    "(not even to say 'no text').\n"
)


@dataclass(frozen=True)
class Slide:
    index: int
    role: str
    text: str
    image_scene: str = ""


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
# 261023 STEP 4-AV — 비마지막 장 행동 요청 판정. 문장이 '~세요/~십시오'로 끝날 때만 본다('?'로 끝나는
# 질문형 훅 '하고 계세요?'와 문장 중간·인용 속 '~하세요'는 제외).
_NON_LAST_IMPERATIVE_RE = re.compile(r"(세요|십시오)[.!]*$")


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


def _move_cta_only_caption_lines(lines: "list[str]") -> "list[str]":
    """261023 STEP 4-BA — 캡션은 슬라이드와 달리 줄을 통째로 옮겨도 빈 블록이 생기지 않는다.
    마지막 줄이 아닌 곳에 순수 CTA만으로 된 줄이 있고 마지막 줄에 CTA가 없으면, 그 줄을 맨 끝으로
    옮긴다(여러 줄이면 마지막 것 1개만). 운영 실패 caption_line_cta=[0, 0, 1, 0] 대응."""
    if len(lines) < 2 or _count_cta_sentences(lines[-1]) > 0:
        return lines

    def cta_only(line: str) -> bool:
        sentences = _sentences(line)
        return bool(sentences) and all(_is_pure_cta_sentence(s) for s in sentences)

    cta_lines = [line for line in lines[:-1] if cta_only(line)]
    if not cta_lines:
        return lines
    return [line for line in lines[:-1] if not cta_only(line)] + [lines[-1], cta_lines[-1]]


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
    fixed = _move_cta_only_caption_lines(_move_pure_ctas(lines))
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
    # 261023 STEP 4-AV — CTA 키워드 없는 행동 요청('자동화하세요', '바꿔보세요')도 마지막 장에만 허용한다.
    for slide in ordered[:-1]:
        if any(_NON_LAST_IMPERATIVE_RE.search(s) for s in _sentences(slide.get("text", ""))):
            return "IMPERATIVE_NOT_LAST_SLIDE"

    return _validate_caption_and_hashtags(payload)


def _validate_image_scenes(payload: dict) -> "str | None":
    """261023 STEP 4-AM — 장별 image_scene 계약. 하나라도 비었거나 길거나 금지어가 있으면 실패."""
    for slide in payload.get("slides") or []:
        scene = slide.get("image_scene")
        if not isinstance(scene, str) or not scene.strip():
            return "IMAGE_SCENE_EMPTY"
        if len(scene.split()) > _IMAGE_SCENE_MAX_WORDS:
            return "IMAGE_SCENE_TOO_LONG"
        if _IMAGE_SCENE_FORBIDDEN_RE.search(scene):
            return "IMAGE_SCENE_FORBIDDEN_WORD"
    return None


# 261023 STEP 4-AQ — Canary 1회차에서 Gemini가 image_scene에 금지어를 써 패키지가 글 단계에서 멈췄다
# (어떤 단어인지 로그가 없어 UNKNOWN). 걸린 단어·장 번호만 로그로 남기고, 그 장면만 1회 다시 받는다.
_IMAGE_SCENE_FORBIDDEN_WORDS_TEXT = (
    "logo, brand, text, letter, word, writing, written, sign, signage, label, caption, screen, monitor, "
    "laptop, computer, phone, smartphone, tablet, poster, banner, newspaper, document, note, notepad, "
    "notebook, paper, book, speech bubble, talking, and any digit"
)
_SCENE_REPAIR_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"index": {"type": "integer"}, "image_scene": {"type": "string"}},
                "required": ["index", "image_scene"],
            },
        },
    },
    "required": ["scenes"],
}


def _forbidden_scene_hits(payload: dict) -> "list[tuple[int, str]]":
    """(장 번호, 걸린 단어) 목록 — 로그·재요청 대상 판정용. 장면 문장 전체는 반환하지 않는다."""
    hits = []
    for slide in payload.get("slides") or []:
        scene = slide.get("image_scene")
        if isinstance(scene, str):
            hits += [(slide.get("index"), m.group(0).lower()) for m in _IMAGE_SCENE_FORBIDDEN_RE.finditer(scene)]
    return hits


def _repair_forbidden_scenes(payload: dict, hits: "list[tuple[int, str]]", *, client, throttle_fn, model
                             ) -> "dict | None":
    """금지어가 걸린 장의 image_scene만 Gemini 1회로 다시 받는다(글은 그대로). 호출·파싱 실패나
    요청하지 않은 장 번호가 오면 None — 재요청은 이 1회뿐이다."""
    targets = sorted({index for index, _word in hits})
    slides = sorted((dict(s) for s in payload.get("slides") or []), key=lambda s: s.get("index", -1))
    lines = "\n".join(
        f"- Slide {s['index']} text: {s.get('text', '')}\n  Previous image_scene: {s.get('image_scene', '')}"
        for s in slides if s.get("index") in targets
    )
    prompt = (
        "Rewrite the image_scene for each slide below. Each image_scene is one plain English sentence "
        f"(max 40 words) describing a simple drawing that shows exactly what that slide's text says, using "
        "generic people and everyday objects only. Never mention company, product or brand names.\n"
        f"These words are FORBIDDEN in image_scene (do not use them in any form, not even negatively): "
        f"{_IMAGE_SCENE_FORBIDDEN_WORDS_TEXT}.\n\n{lines}\n\n"
        "Return only the slides listed above, in the exact JSON schema provided."
    )
    config = genai_types.GenerateContentConfig(
        response_mime_type="application/json", response_json_schema=_SCENE_REPAIR_RESPONSE_SCHEMA,
    )
    try:
        throttle_fn()
        response = client.models.generate_content(model=model, contents=prompt, config=config)
        scenes = {item["index"]: item["image_scene"] for item in json.loads(response.text)["scenes"]}
    except Exception as exc:
        logger.warning(f"[CarouselContent] image_scene 재요청 실패 | error_type={type(exc).__name__}")
        return None
    if sorted(scenes) != targets:
        logger.warning(f"[CarouselContent] image_scene 재요청 장 번호 불일치 | requested={targets}")
        return None
    for slide in slides:
        if slide.get("index") in scenes:
            slide["image_scene"] = scenes[slide["index"]]
    return {**payload, "slides": slides}


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


# 261023 STEP 4-BB — 문제 제기형 일반 조언 대신 정보 전달 우선: ① 구체적 새 사실/변화 → ② 핵심 기능·차이
# (입력·처리·결과) → ③ 실제 사용법·조건 + 마지막 CTA. 장수·글자수·CTA 위치·명령형 계약은 그대로다.
_SHORT_NEWS_SLIDE = (
    "   Slide 1 (news value): one line, at most 40 Korean characters, containing at least one real "
    "product, feature or change named in the source plus why it matters to the reader. Not a bare "
    "question and not a generic pain line; vary the form from post to post.\n"
)
_SHORT_SLIDE_PLANS = {
    2: (_SHORT_NEWS_SLIDE +
        "   Slide 2 (how to use + CTA): the core feature in one line, then how a Korean business owner, "
        "marketer or office worker can use it (tool or feature, what to enter, order, expected result, a "
        "limit stated in the source), at most 30 words, ending with exactly one call to action.\n"),
    3: (_SHORT_NEWS_SLIDE +
        "   Slide 2 (key facts): 2-3 verified features, differences or limits from the source, written as "
        "what goes in, what is handled and where the result ends up — short phrases joined by '·', at most "
        "30 words. No vague benefits such as 업무 효율 향상 or 시간 절약.\n"
        "   Slide 3 (practical use + CTA): one concrete way to use it now — tool or feature, what to enter, "
        "order, expected result, and a limit stated in the source — at most 30 words, ending with exactly "
        "one call to action.\n"),
    4: (_SHORT_NEWS_SLIDE +
        "   Slide 2 (key facts): 2-3 verified features, differences or limits from the source, short "
        "phrases joined by '·', at most 30 words.\n"
        "   Slide 3 (how it works or compared): the steps or the old-vs-new difference written as noun "
        "phrases (e.g. 입력 → 처리 → 결과), at most 30 words. No request or call to action here.\n"
        "   Slide 4 (practical use + CTA): who should use it and the one condition to check first, ending "
        "with exactly one call to action. Use a 4th slide only when the source has enough real detail.\n"),
}
_SHORT_COPY_STYLE = (
    "Role: you are an AI technology editor who follows the US AI industry every day and writes dense, "
    "practical card-news for Korean business owners, marketers and office workers. Your job is not "
    "motivational advice but facts the reader did not know: a verified new fact or change, the real "
    "feature, how to use it, and the conditions that apply. Every slide must add different useful "
    "information, and the post must contain at least one thing worth saving to look up later (a usable "
    "prompt, setup order, feature limit, old-vs-new difference or input → process → result example). "
    "Write fast, concrete, natural Korean and explain any technical term in a few words. Product names, "
    "features, prices, dates and numbers may appear only if they are in the source; never invent menus, "
    "buttons or steps. If the source is thin, narrow the scope to what it supports instead of padding. "
    "No clichéd productivity advice, unsupported time-saving claims, repeated ad phrases or buzzwords "
    "such as 혁신, 효율성 증대, 극대화, 획기적. Do not connect every topic to repetitive-work automation. "
    "Requests or imperative lines may appear only on the last slide; write steps on other slides as noun "
    "phrases. Detailed verified steps that do not fit the slides go in the caption.\n"
)


def _short_content_type_line(source_published_at: str) -> str:
    """뉴스 원천(Sourcebook 14.x 피드, 게시 시각 있음)과 일반 Sourcebook 교육 자료를 구분해 알린다 —
    오래된 기능을 새 소식처럼 쓰지 않게 하는 것이 목적이다."""
    if source_published_at:
        return (f"Content type: NEWS (source published {source_published_at}). Lead with what changed and "
                "why it matters now.\n\n")
    return ("Content type: GUIDE (evergreen reference, not breaking news). Do not call it new, just "
            "released or the latest; lead with the most useful concrete fact instead.\n\n")


def _build_short_prompt(core_message: str, title: str, slot_role: str, template_type: str,
                        slide_count: int, source_published_at: str = "") -> str:
    return (
        f"You are writing a {slide_count}-slide Instagram carousel (card-news) for Korean small-business "
        "owners and office workers who want to use AI tools, using ONLY the source content below.\n\n"
        f"Source title: {title}\n"
        f"Source content (the ONLY allowed source of facts/numbers/claims): {core_message}\n\n"
        + _short_content_type_line(source_published_at) +
        f"Slot role: {slot_role}. Sentence template: {template_type}.\n\n"
        "Rules:\n"
        "1. Do NOT invent any fact, statistic, name, or claim not present in the source content above. "
        "Paraphrase — do not copy sentences verbatim.\n"
        f"2. Produce exactly {slide_count} slides. Only the last slide may contain a call to action. "
        "The call to action is ONE separate final sentence that must contain one of these Korean words: "
        "저장, 공유, 팔로우, 댓글 — make it carry the action message too (e.g. '이 사용 순서를 저장해 두고 필요할 때 "
        "꺼내 보세요.'). No other sentence anywhere may use those words or '확인해 보세요'.\n"
        + _SHORT_SLIDE_PLANS[slide_count] +
        "3. A strong hook is fine, but no false claims, guarantees, false urgency, or unsupported "
        "performance numbers. No long paragraphs.\n"
        + _SHORT_COPY_STYLE +
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
    with_image_scenes: bool = False,
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
    if with_image_scenes and slide_count not in SHORT_SLIDE_COUNTS:
        return CarouselResult(success=False, error_code="IMAGE_SCENE_UNSUPPORTED")
    # 261023 STEP 4-AY(Codex BLOCKER) — note 경로는 페르소나 전용 client만 쓴다. 없으면 공유
    # GEMINI_API_KEY(_get_client)로 넘어가지 않고 Gemini 호출 전에 실패한다(CLAUDE.md 규칙 9).
    if with_image_scenes and client is None:
        return CarouselResult(success=False, error_code="NOTE_CLIENT_MISSING")
    if slot_role not in VALID_SLOT_ROLES:
        return CarouselResult(success=False, error_code="SLOT_ROLE_UNKNOWN")
    if template_type not in TEMPLATE_TYPES:
        return CarouselResult(success=False, error_code="TEMPLATE_TYPE_UNKNOWN")
    if not topic.core_message or not topic.core_message.strip():
        return CarouselResult(success=False, error_code="INSUFFICIENT_SOURCE_EVIDENCE")

    config = genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=_SHORT_SCENE_RESPONSE_SCHEMA if with_image_scenes else _CAROUSEL_RESPONSE_SCHEMA,
    )
    short = slide_count in SHORT_SLIDE_COUNTS
    prompt = (
        _build_short_prompt(topic.core_message, topic.title, slot_role, template_type, slide_count,
                            getattr(topic, "source_published_at", "") or "")
        if short else _build_prompt(topic.core_message, topic.title, slot_role, template_type)
    )
    if with_image_scenes:
        prompt = prompt.replace("Return the result in the exact JSON schema provided.",
                                _IMAGE_SCENE_RULE + "Return the result in the exact JSON schema provided.")
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
    if not contract_error and with_image_scenes:
        contract_error = _validate_image_scenes(payload)
        if contract_error == "IMAGE_SCENE_FORBIDDEN_WORD":
            hits = _forbidden_scene_hits(payload)
            logger.warning(f"[CarouselContent] image_scene 금지어 — 장면만 1회 재요청 | hits={hits}")
            repaired = _repair_forbidden_scenes(
                payload, hits, client=client, throttle_fn=active_throttle, model=active_model,
            )
            if repaired is None:
                contract_error = "IMAGE_SCENE_REPAIR_FAILED"
            else:
                payload = repaired
                contract_error = _validate_image_scenes(payload)
                if contract_error == "IMAGE_SCENE_FORBIDDEN_WORD":
                    logger.warning(f"[CarouselContent] 재요청 후에도 금지어 | hits={_forbidden_scene_hits(payload)}")
    if contract_error:
        if short:
            logger.warning(f"[CarouselContent] 계약 실패 | {contract_error} | {_cta_location_summary(payload)}")
        return CarouselResult(success=False, error_code=contract_error)

    slides = tuple(
        Slide(index=s["index"], role=s.get("role", ""), text=s["text"],
              image_scene=s["image_scene"].strip() if with_image_scenes else "")
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
