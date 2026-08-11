"""image_template_renderer.py — Track B-8 정보형 이미지 템플릿 렌더러.

260808 설계 승인분(Read-only 설계 → Pillow REUSE 확정)의 실제 구현. Pillow는
기존 requirements.txt(`Pillow>=10.0.0`)에 이미 있는 내부 자산이라 신규
의존성이 없다.

기존 3개 템플릿(WORKFLOW/BEFORE_AFTER/SOURCE_CARD, render_card())은 Cloudflare
Flux를 전혀 쓰지 않는다 — 배경은 템플릿별 고정 그라데이션이라 텍스트
오생성·화질편차 위험이 구조적으로 없다(negative_prompt 미신뢰 문제,
260731/260807과 무관해짐).

260811 회장 승인 — 신규 4번째 템플릿(HeroCardContent/render_hero_card())은
Cloudflare Flux로 생성한 AI 배경 이미지(텍스트 없이) 위에 Pillow로 실제
한글 텍스트를 얹는 하이브리드 방식이다. AI 모델(Flux-schnell)은 한글 등
비라틴 문자를 정확히 그리지 못하는 것으로 실측 확인됐다("괵긕 린겐
극시팥릳시" 등 의미 없는 글자 — 260811 Read-only 테스트) — 그래서 AI에는
텍스트를 요청하지 않고 순수 배경·그래픽만 생성하게 하고, 실제 읽히는
텍스트는 전부 Pillow(Pretendard 폰트)로 정확하게 그린다. AI 배경 생성
자체는 이 함수의 책임이 아니다 — 호출자가 `image_provider_cloudflare.
generate_image()`로 만든 PNG bytes를 `ai_background`로 전달한다(관심사
분리, 기존 provider 모듈 REUSE).

공통 규격: 1080x1350(4:5). 폰트는 Pretendard Regular(본문)+ExtraBold(제목),
SIL OFL 1.1 — assets/fonts/pretendard/LICENSE 동봉.

Source에 없는 내용을 채워 넣지 않는다(Fail-closed) — 필수 필드가 비어있으면
ValueError.
"""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CANVAS_SIZE = (1080, 1350)
BRAND_HANDLE = "@aijomoojin"
TEMPLATE_TYPES = ("WORKFLOW", "BEFORE_AFTER", "SOURCE_CARD")
HERO_ICON_KINDS = ("target", "search", "gear", "graph", "check")

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


# ── 260811 신규 — AI 배경 + Pillow 텍스트 하이브리드 템플릿 ──────────────────

_HERO_MARGIN = 60
_HERO_FULL_W = CANVAS_SIZE[0] - 2 * _HERO_MARGIN
_HERO_LEFT_W = 580
_HERO_CYAN = (103, 232, 249)
_HERO_WHITE = (255, 255, 255)
_HERO_DIM = (190, 210, 235)
_HERO_FOOTER_DIM = (180, 200, 230)


@dataclass(frozen=True)
class HeroBlock:
    icon: str  # HERO_ICON_KINDS 중 하나("check" 제외 — 그건 태그라인 박스 전용)
    title: str
    desc: str


@dataclass(frozen=True)
class HeroCardContent:
    headline: str
    subheadline: str
    blocks: tuple  # HeroBlock 정확히 4개
    tagline: str
    source_label: str
    ai_background: bytes  # image_provider_cloudflare.generate_image()가 만든 PNG/JPEG bytes(텍스트 없는 배경)
    brand: str = BRAND_HANDLE


def _hero_fit_font_one_line(draw, text: str, path: Path, max_w: int, start_size: int, min_size: int = 28):
    """텍스트가 max_w 안에 줄바꿈 없이 한 줄로 들어가는 가장 큰 폰트 크기를
    찾는다(260811 회장 지시 — 헤드라인 등은 줄바꿈되면 안 됨)."""
    size = start_size
    while size > min_size:
        font = ImageFont.truetype(str(path), size)
        if draw.textlength(text, font=font) <= max_w:
            return font
        size -= 2
    return ImageFont.truetype(str(path), min_size)


def _hero_draw_icon(draw, kind: str, cx: float, cy: float, r: float) -> None:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=_HERO_CYAN, width=3)
    if kind == "target":
        for rad in (r * 0.65, r * 0.3):
            draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=_HERO_CYAN, width=3)
        draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=_HERO_CYAN)
    elif kind == "search":
        gr = r * 0.42
        gx, gy = cx - r * 0.18, cy - r * 0.18
        draw.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], outline=_HERO_CYAN, width=4)
        draw.line([(gx + gr * 0.7, gy + gr * 0.7), (cx + r * 0.45, cy + r * 0.45)], fill=_HERO_CYAN, width=5)
    elif kind == "gear":
        import math
        for i in range(8):
            ang = math.radians(i * 45)
            tx = cx + math.cos(ang) * r * 0.62
            ty = cy + math.sin(ang) * r * 0.62
            draw.ellipse([tx - 6, ty - 6, tx + 6, ty + 6], fill=_HERO_CYAN)
        draw.ellipse([cx - r * 0.35, cy - r * 0.35, cx + r * 0.35, cy + r * 0.35], outline=_HERO_CYAN, width=4)
    elif kind == "graph":
        bw = r * 0.28
        heights = [r * 0.5, r * 0.8, r * 1.1]
        base_y = cy + r * 0.5
        for i, h in enumerate(heights):
            bx = cx - r * 0.55 + i * (bw + 8)
            draw.rectangle([bx, base_y - h, bx + bw, base_y], fill=_HERO_CYAN)
    elif kind == "check":
        # 260811 회장 지시 — 이전 로켓 아이콘이 "A"처럼 보인다는 지적으로
        # 명확한 체크마크로 교체.
        draw.line([(cx - r * 0.45, cy), (cx - r * 0.1, cy + r * 0.4)], fill=_HERO_CYAN, width=6)
        draw.line([(cx - r * 0.1, cy + r * 0.4), (cx + r * 0.5, cy - r * 0.4)], fill=_HERO_CYAN, width=6)
    else:
        raise ValueError(f"알 수 없는 icon kind: {kind}")


def render_hero_card(content: HeroCardContent) -> bytes:
    """HeroCardContent -> PNG bytes(1080x1350). ai_background 위에 헤드라인·
    서브헤드라인·블록 4개·태그라인·출처를 Pillow로 그린다(전부 실제 텍스트,
    AI가 그리지 않음 — 위 모듈 docstring 참조). 필수 필드 공란·blocks 개수
    불일치·ai_background 공란은 ValueError(Fail-closed, 빈 카드로 채우지 않음)."""
    if not content.headline.strip() or not content.subheadline.strip():
        raise ValueError("headline/subheadline은 비어있을 수 없습니다")
    if not content.tagline.strip() or not content.source_label.strip():
        raise ValueError("tagline/source_label은 비어있을 수 없습니다")
    if len(content.blocks) != 4:
        raise ValueError("blocks는 정확히 4개여야 합니다")
    for b in content.blocks:
        if not b.title.strip() or not b.desc.strip():
            raise ValueError("각 block의 title/desc는 비어있을 수 없습니다")
        if b.icon not in ("target", "search", "gear", "graph"):
            raise ValueError(f"block icon은 target/search/gear/graph 중 하나여야 합니다: {b.icon!r}")
    if not content.ai_background:
        raise ValueError("ai_background는 비어있을 수 없습니다")

    bg = Image.open(BytesIO(content.ai_background)).convert("RGBA")
    scale = CANVAS_SIZE[0] / bg.width
    new_h = int(bg.height * scale)
    bg = bg.resize((CANVAS_SIZE[0], new_h))
    canvas = Image.new("RGBA", CANVAS_SIZE, (5, 8, 25, 255))
    canvas.paste(bg, (0, (CANVAS_SIZE[1] - new_h) // 2))

    # 260811 ERR-109 계열 재현 대응 — AI 배경이 "no text" 지시를 무시하고 글자 비슷한
    # 형상을 그려 넣는 경우가 실측 확인됐다(Flux는 negative_prompt 미지원, positive
    # prompt 지시도 항상 지키지 않음 — visual_brief.py 기존 주석과 동일 근본원인).
    # 헤드라인/서브헤드라인이 배경 위에 바로 얹히면 그 잔상과 겹쳐 보일 수 있어,
    # 실제 텍스트 높이를 계산해 그 구간만 거의 불투명한 별도 밴드로 덮는다 —
    # 왼쪽 전체 그라데이션(4블록/태그라인 가독성용)과는 별개, 헤드라인 구간에서만
    # 추가로 덧씌운다.
    measure_draw = ImageDraw.Draw(canvas)
    title_font = _hero_fit_font_one_line(measure_draw, content.headline, _FONT_EXTRABOLD, _HERO_FULL_W, 88)
    sub_font = _hero_fit_font_one_line(measure_draw, content.subheadline, _FONT_REGULAR, _HERO_FULL_W, 44)
    headline_top = 240 - 40
    headline_bottom = 240 + title_font.size + 25 + sub_font.size + 60

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    # 왼쪽 텍스트 영역 가독성 확보용 다크 오버레이(좌측이 진하고 우측으로 갈수록 옅어짐).
    for x in range(620):
        alpha = int(190 * (1 - x / 620)) if x < 500 else int(190 * 0.2)
        odraw.line([(x, 0), (x, CANVAS_SIZE[1])], fill=(5, 8, 25, min(alpha + 40, 235)))
    # 헤드라인·서브헤드라인 구간은 전체 폭에 걸쳐 거의 불투명하게 추가로 덮는다.
    odraw.rectangle([0, headline_top, CANVAS_SIZE[0], headline_bottom], fill=(5, 8, 25, 255))
    canvas = Image.alpha_composite(canvas, overlay)
    draw = ImageDraw.Draw(canvas)

    block_title_font = _load_font(_FONT_EXTRABOLD, 34)
    block_desc_font = _load_font(_FONT_REGULAR, 26)
    footer_font = _load_font(_FONT_REGULAR, 22)

    y = 240
    draw.text((_HERO_MARGIN, y), content.headline, font=title_font, fill=_HERO_WHITE)
    y += title_font.size + 25
    draw.text((_HERO_MARGIN, y), content.subheadline, font=sub_font, fill=_HERO_CYAN)
    y += sub_font.size + 30
    draw.line([(_HERO_MARGIN, y), (_HERO_MARGIN + _HERO_LEFT_W, y)], fill=_HERO_CYAN, width=3)
    y += 45

    for block in content.blocks:
        icon_r = 30
        icon_cx = _HERO_MARGIN + icon_r
        icon_cy = y + icon_r
        _hero_draw_icon(draw, block.icon, icon_cx, icon_cy, icon_r)
        text_x = _HERO_MARGIN + icon_r * 2 + 24
        title_w = draw.textlength(block.title + ": ", font=block_title_font)
        draw.text((text_x, y + icon_r - 20), block.title + ":", font=block_title_font, fill=_HERO_WHITE)
        draw.text((text_x + title_w, y + icon_r - 16), block.desc, font=block_desc_font, fill=_HERO_DIM)
        y += 90

    y += 30
    tag_font = _hero_fit_font_one_line(draw, content.tagline, _FONT_EXTRABOLD, _HERO_LEFT_W - 110, 38)
    box_h = 100
    draw.rounded_rectangle([_HERO_MARGIN, y, _HERO_MARGIN + _HERO_LEFT_W, y + box_h], radius=20, outline=_HERO_CYAN, width=3)
    icon_cx, icon_cy = _HERO_MARGIN + 55, y + box_h // 2
    _hero_draw_icon(draw, "check", icon_cx, icon_cy, 26)
    draw.text((_HERO_MARGIN + 100, y + box_h // 2 - tag_font.size // 2), content.tagline, font=tag_font, fill=_HERO_CYAN)

    footer_y = CANVAS_SIZE[1] - 90
    draw.text((_HERO_MARGIN, footer_y), f"출처: {content.source_label}", font=footer_font, fill=_HERO_FOOTER_DIM)
    draw.text((_HERO_MARGIN, footer_y + 32), content.brand, font=footer_font, fill=_HERO_FOOTER_DIM)

    buf = BytesIO()
    canvas.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
