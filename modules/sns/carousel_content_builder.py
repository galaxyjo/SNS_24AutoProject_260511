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

from modules.sns.caption_generator import (
    _MAX_ATTEMPTS,
    _classify_retry,
    _get_client,
    _next_retry_delay,
    _throttle,
    check_caption_safety,
)

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


def generate_carousel_content(
    topic, slot_role: str, template_type: str,
    *, client=None, throttle_fn=None, model=None,
    existing_fingerprints: "set | None" = None,
) -> CarouselResult:
    """Sourcebook `topic`(source_selector.SourceTopic 또는 동일 필드를 가진
    객체) + 슬롯 역할 + 문장 템플릿으로 8-Slide 카드뉴스 구조화 콘텐츠 1건을
    생성한다. Google Search/URL Context Tool을 전혀 쓰지 않는다(topic.
    core_message는 이미 Sourcebook에 있는 값 — 이 함수 자신은 인터넷에
    접근하지 않는다)."""
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
    prompt = _build_prompt(topic.core_message, topic.title, slot_role, template_type)
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

    contract_error = _validate_contract(payload)
    if contract_error:
        return CarouselResult(success=False, error_code=contract_error)

    slides = tuple(
        Slide(index=s["index"], role=s.get("role", ""), text=s["text"])
        for s in sorted(payload["slides"], key=lambda s: s["index"])
    )
    caption = payload["caption"]
    hashtags = tuple(payload["hashtags"])
    combined_text = " ".join(s.text for s in slides) + " " + caption

    if _detect_possible_fabrication(combined_text, topic.core_message):
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
