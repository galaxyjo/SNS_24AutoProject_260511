"""image_template_renderer.py — Track B-8 정보형 이미지 템플릿 렌더러.

260808 설계 승인분(Read-only 설계 → Pillow REUSE 확정)의 실제 구현. Pillow는
기존 requirements.txt(`Pillow>=10.0.0`)에 이미 있는 내부 자산이라 신규
의존성이 없다. Cloudflare Flux(AI 이미지 생성)는 이 경로에서 전혀 쓰지 않는다
— 배경은 템플릿별 고정 그라데이션이라 텍스트 오생성·화질편차 위험이
구조적으로 없다(negative_prompt 미신뢰 문제, 260731/260807과 무관해짐).

3개 템플릿(회장 승인): WORKFLOW / BEFORE_AFTER / SOURCE_CARD.
공통 규격: 1080x1350(4:5) / 제목 상단 / 보조문장 1개 / 핵심 도식 1개(템플릿별) /
하단 출처 표기 / Brand. 폰트는 Pretendard Regular(본문)+ExtraBold(제목),
SIL OFL 1.1 — assets/fonts/pretendard/LICENSE 동봉.

Source에 없는 내용을 채워 넣지 않는다(Fail-closed) — hook/core_message/
source_label 중 하나라도 비어있으면 ValueError.
"""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CANVAS_SIZE = (1080, 1350)
BRAND_HANDLE = "@aijomoojin"
TEMPLATE_TYPES = ("WORKFLOW", "BEFORE_AFTER", "SOURCE_CARD")

_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "pretendard"
_FONT_REGULAR = _FONT_DIR / "Pretendard-Regular.otf"
_FONT_EXTRABOLD = _FONT_DIR / "Pretendard-ExtraBold.otf"

# 결정론적 고정 팔레트 — 계정마다/콘텐츠마다 바뀌지 않는다(재현 가능성 우선).
_PALETTES = {
    "WORKFLOW":     {"top": (30, 58, 138),  "bottom": (59, 130, 246), "text": (255, 255, 255), "accent": (191, 219, 254)},
    "BEFORE_AFTER": {"top": (194, 65, 12),  "bottom": (13, 148, 136), "text": (255, 255, 255), "accent": (255, 237, 213)},
    "SOURCE_CARD":  {"top": (17, 24, 39),   "bottom": (55, 65, 81),   "text": (255, 255, 255), "accent": (156, 163, 175)},
}

_MARGIN = 80


@dataclass(frozen=True)
class CardContent:
    template_type: str
    hook: str
    core_message: str
    source_label: str
    steps: tuple = ()  # WORKFLOW: 정확히 3개 / BEFORE_AFTER: 정확히 2개(before, after) / SOURCE_CARD: 미사용
    brand: str = BRAND_HANDLE


def _load_font(path: Path, size: int) -> "ImageFont.FreeTypeFont":
    return ImageFont.truetype(str(path), size)


def _vertical_gradient(size: "tuple[int, int]", top: "tuple[int,int,int]", bottom: "tuple[int,int,int]") -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        ratio = y / max(h - 1, 1)
        rgb = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        draw.line([(0, y), (w, y)], fill=rgb)
    return img


def _wrap_text(draw: "ImageDraw.ImageDraw", text: str, font: "ImageFont.FreeTypeFont", max_width: int) -> "list[str]":
    """한글은 공백 기준 word-wrap이 신뢰할 수 없어(공백 없는 긴 절이 흔함)
    글자 단위로 폭을 재며 줄바꿈한다."""
    lines: list[str] = []
    current = ""
    for ch in text:
        candidate = current + ch
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = ch
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _draw_wrapped(draw, text, font, x, y, max_width, fill, line_height) -> int:
    for line in _wrap_text(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def render_card(content: CardContent) -> bytes:
    """CardContent -> PNG bytes(1080x1350). Source에 없는 내용을 만들지 않는다
    — hook/core_message/source_label 중 하나라도 비어있으면 ValueError(Fail-closed,
    빈 카드나 추정 문구로 채우지 않는다)."""
    if content.template_type not in TEMPLATE_TYPES:
        raise ValueError(f"알 수 없는 template_type: {content.template_type}")
    if not content.hook.strip() or not content.core_message.strip() or not content.source_label.strip():
        raise ValueError("hook/core_message/source_label은 비어있을 수 없습니다")
    if content.template_type == "WORKFLOW" and len(content.steps) != 3:
        raise ValueError("WORKFLOW 템플릿은 steps가 정확히 3개여야 합니다")
    if content.template_type == "BEFORE_AFTER" and len(content.steps) != 2:
        raise ValueError("BEFORE_AFTER 템플릿은 steps가 정확히 2개(before, after)여야 합니다")

    palette = _PALETTES[content.template_type]
    img = _vertical_gradient(CANVAS_SIZE, palette["top"], palette["bottom"])
    draw = ImageDraw.Draw(img)

    title_font = _load_font(_FONT_EXTRABOLD, 64)
    body_font = _load_font(_FONT_REGULAR, 40)
    footer_font = _load_font(_FONT_REGULAR, 26)

    content_width = CANVAS_SIZE[0] - 2 * _MARGIN
    y = 130
    y = _draw_wrapped(draw, content.hook, title_font, _MARGIN, y, content_width, palette["text"], 78)
    y += 36
    y = _draw_wrapped(draw, content.core_message, body_font, _MARGIN, y, content_width, palette["text"], 52)
    y += 50

    if content.template_type == "WORKFLOW":
        step_font = _load_font(_FONT_EXTRABOLD, 32)
        arrow_font = _load_font(_FONT_EXTRABOLD, 40)
        step_w = content_width // 3
        box_h = 160
        for i, step in enumerate(content.steps):
            x = _MARGIN + i * step_w
            box_w = step_w - (30 if i < 2 else 0)
            draw.rounded_rectangle([x, y, x + box_w, y + box_h], radius=20, outline=palette["accent"], width=3)
            _draw_wrapped(draw, step, step_font, x + 24, y + 24, box_w - 48, palette["accent"], 40)
            if i < 2:
                draw.text((x + box_w + 2, y + box_h // 2 - 20), "→", font=arrow_font, fill=palette["accent"])
        y += box_h + 40

    elif content.template_type == "BEFORE_AFTER":
        label_font = _load_font(_FONT_EXTRABOLD, 32)
        col_gap = 40
        col_w = (content_width - col_gap) // 2
        box_h = 240
        for i, (label, value) in enumerate(zip(("BEFORE", "AFTER"), content.steps)):
            x = _MARGIN + i * (col_w + col_gap)
            draw.rounded_rectangle([x, y, x + col_w, y + box_h], radius=20, outline=palette["accent"], width=3)
            draw.text((x + 24, y + 20), label, font=label_font, fill=palette["accent"])
            _draw_wrapped(draw, value, body_font, x + 24, y + 74, col_w - 48, palette["text"], 48)
        y += box_h + 40

    # SOURCE_CARD: 별도 도식 없음 — core_message 인용 텍스트 자체가 핵심 도식 역할.

    footer_y = CANVAS_SIZE[1] - 130
    draw.line([(_MARGIN, footer_y - 20), (CANVAS_SIZE[0] - _MARGIN, footer_y - 20)], fill=palette["accent"], width=2)
    draw.text((_MARGIN, footer_y), f"출처: {content.source_label}", font=footer_font, fill=palette["accent"])
    draw.text((_MARGIN, footer_y + 40), content.brand, font=footer_font, fill=palette["accent"])

    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
