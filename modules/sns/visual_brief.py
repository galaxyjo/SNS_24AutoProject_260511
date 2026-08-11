"""visual_brief.py — Track B-4 Visual Brief / Image Prompt Builder.

Source Topic(title/core_message) + Caption 맥락을 이미지 생성 Provider용 Prompt로 변환한다.
Provider 호출은 하지 않는다(Track B-4A Architecture 3~4단계, Provider Adapter는 분리).

핵심 제약(GPT 저작권 정책, 260731 확정 + 260731 Canary #1 실측 수정):
  - core_message에 없는 내용은 Prompt에 넣지 않는다(Fail-closed: core_message 공란이면 None).
  - **negative_prompt는 안전장치로 신뢰하지 않는다** — Cloudflare Workers AI의
    FLUX.1-schnell 모델은 negative_prompt 파라미터를 지원하지 않음(공식 문서 확인,
    260731). Canary #1 실측에서 "no logo/no text" negative_prompt를 보냈음에도
    Netflix 로고와 일본어 텍스트가 그대로 생성되어 확인됨(ERR 후보). 따라서 텍스트·
    로고·브랜드 회피 지시는 반드시 positive prompt_text 안에 명시적으로 넣는다.
  - Topic의 실제 회사·브랜드명(title)은 이미지 컨셉의 근거는 되지만, prompt 안에서
    "그 브랜드를 문자 그대로 시각화하지 말 것"을 항상 명시한다(브랜드명이 프롬프트에
    등장하면 모델이 실제 로고를 강하게 연상해 그려내는 경향 실측 확인).
"""

from dataclasses import dataclass, field

PROMPT_VERSION = "v2"
DEFAULT_ASPECT_RATIO = "1:1"

_BASE_FORBIDDEN_ELEMENTS = (
    "text",
    "logo",
    "watermark",
    "real photograph of a specific named person",
    "brand names",
    "invented statistics or numbers",
)


@dataclass(frozen=True)
class VisualBrief:
    topic_id: str
    title: str
    core_message: str
    tone_style: str = ""
    forbidden_elements: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class ImagePrompt:
    prompt_text: str
    negative_prompt: str
    aspect_ratio: str
    prompt_version: str


def build_visual_brief(
    topic_id: str,
    core_message: str,
    title: str = "",
    prohibited_expression: str = "",
    tone_style: str = "",
) -> VisualBrief:
    forbidden = list(_BASE_FORBIDDEN_ELEMENTS)
    if title:
        forbidden.append(f"{title} logo or branding")
    if prohibited_expression:
        forbidden.append(prohibited_expression)
    return VisualBrief(
        topic_id=topic_id,
        title=title or "",
        core_message=core_message or "",
        tone_style=tone_style,
        forbidden_elements=tuple(forbidden),
    )


def build_image_prompt(brief: VisualBrief) -> "ImagePrompt | None":
    """Visual Brief -> Image Prompt. core_message 공란이면 None(Fail-closed, 근거 없는 생성 금지).

    안전 지시는 negative_prompt가 아니라 prompt_text 본문에 명시한다(v2, 위 모듈 docstring 참조).
    """
    if not brief.core_message or not brief.core_message.strip():
        return None

    tone_clause = f", {brief.tone_style} mood" if brief.tone_style else ""
    brand_clause = (
        f" Do NOT depict {brief.title}'s actual logo, brand colors, or any recognizable "
        f"company branding — represent the underlying idea with a completely generic, "
        f"unbranded scene instead."
        if brief.title else ""
    )

    prompt_text = (
        "A striking, curiosity-provoking symbolic editorial illustration for an AI/tech "
        "business audience, representing the following idea: "
        f"\"{brief.core_message.strip()}\"{tone_clause}. "
        "Dramatic lighting, vivid color contrast, layered depth, highly detailed, "
        "premium and futuristic in feel."
        f"{brand_clause} "
        "Absolutely no text, letters, or writing in any language anywhere in the image. "
        "No logos, no watermarks, no real or recognizable human faces, no invented "
        "statistics or numbers. Abstract and symbolic only — do not depict any real "
        "company's literal branding."
    )
    negative_prompt = ", ".join(brief.forbidden_elements)

    return ImagePrompt(
        prompt_text=prompt_text,
        negative_prompt=negative_prompt,
        aspect_ratio=DEFAULT_ASPECT_RATIO,
        prompt_version=PROMPT_VERSION,
    )


def build_background_only_prompt(brief: VisualBrief) -> "ImagePrompt | None":
    """260811 Visual Type Wiring — `render_hero_card()`용 배경 이미지 Prompt.

    `build_image_prompt()`와 별개 함수다(기존 함수·기존 호출부 무수정) — 이
    배경은 최종 이미지가 아니라 Pillow가 그 위에 실제 텍스트를 덧그리는
    바탕이므로, "no text" 지시를 지키지 못했을 때의 위험이 다르다(Pillow
    텍스트가 항상 실제로 그려지므로 최종 결과의 글자 자체는 항상 정확 —
    `render_hero_card()`가 헤드라인 구간에 불투명 밴드를 추가로 덮어 배경의
    잔여 텍스트 유령을 가린다, 260811 실측 확인). 그래도 1차 방어선으로 이
    함수도 동일하게 "no text" 지시를 명시한다.
    """
    if not brief.core_message or not brief.core_message.strip():
        return None

    tone_clause = f", {brief.tone_style} mood" if brief.tone_style else ""
    brand_clause = (
        f" Do NOT depict {brief.title}'s actual logo, brand colors, or any recognizable "
        f"company branding — represent the underlying idea with a completely generic, "
        f"unbranded scene instead."
        if brief.title else ""
    )

    prompt_text = (
        "A modern high-tech isometric 3D business banner background, deep navy "
        "blue and neon cyan aesthetic, symbolic imagery representing the "
        "following idea: "
        f"\"{brief.core_message.strip()}\"{tone_clause}. "
        "Dramatic lighting, layered depth, premium and futuristic in feel, "
        "glowing circuit-board pattern accents."
        f"{brand_clause} "
        "Absolutely no text, letters, or writing in any language anywhere in the "
        "image. No logos, no watermarks, no real or recognizable human faces, no "
        "invented statistics or numbers. Abstract and symbolic only."
    )
    negative_prompt = ", ".join(brief.forbidden_elements)

    return ImagePrompt(
        prompt_text=prompt_text,
        negative_prompt=negative_prompt,
        aspect_ratio=DEFAULT_ASPECT_RATIO,
        prompt_version=PROMPT_VERSION,
    )
