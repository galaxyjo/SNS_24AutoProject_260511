"""Track B-8 — image_template_renderer.py 단위 테스트.

실제 이미지 렌더링을 실행한다(Pillow, 외부 API 호출 없음). Vault/Airtable/
게시 어디에도 쓰지 않는다.
"""

import io

import pytest
from PIL import Image

from modules.sns.image_template_renderer import (
    CANVAS_SIZE,
    CardContent,
    HeroBlock,
    HeroCardContent,
    render_card,
    render_hero_card,
)


def _decode(png_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png_bytes))


def _fake_ai_background() -> bytes:
    """render_hero_card() 테스트용 최소 유효 PNG bytes(실제 Cloudflare 호출
    없음) — 순수 단색 이미지면 충분하다, 실제 배경 품질은 이 함수 책임이
    아니다(image_provider_cloudflare.generate_image()의 책임)."""
    img = Image.new("RGB", (1024, 1024), (10, 10, 40))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _hero_content(**overrides) -> HeroCardContent:
    defaults = dict(
        headline="스타트업 성장 프레임워크",
        subheadline="검증된 자료로 사업을 검증하고, 만들고, 키운다",
        blocks=(
            HeroBlock("target", "아이디어 발굴", "검증된 기회를 찾는다"),
            HeroBlock("search", "고객 검증", "진짜 시장 문제를 확인한다"),
            HeroBlock("gear", "제품 개발", "시행착오 없이 MVP를 만든다"),
            HeroBlock("graph", "확장과 성장", "체계적으로 사업을 키운다"),
        ),
        tagline="시행착오 없이, 체계적인 사업 성장.",
        source_label="The Startup Owner's Manual (Steve Blank)",
        ai_background=_fake_ai_background(),
    )
    defaults.update(overrides)
    return HeroCardContent(**defaults)


def test_render_workflow_card_produces_correct_canvas_size():
    content = CardContent(
        template_type="WORKFLOW",
        hook="매번 반복되는 그 업무, 아직도 손으로 하시나요?",
        core_message="반복되는 업무 하나를 자동화 흐름으로 바꾸면 시스템이 대신 처리한다.",
        source_label="Zapier 공식 블로그",
        steps=("트리거", "처리", "기록"),
    )

    png_bytes = render_card(content)
    img = _decode(png_bytes)

    assert img.size == CANVAS_SIZE
    assert img.format == "PNG"


def test_render_before_after_card_produces_correct_canvas_size():
    content = CardContent(
        template_type="BEFORE_AFTER",
        hook="수작업 대신 자동화로",
        core_message="반복 업무를 자동화 흐름으로 바꾸면 결과가 달라진다.",
        source_label="Zapier 공식 블로그",
        steps=("사람이 매번 손으로 처리", "시스템이 대신 처리"),
    )

    png_bytes = render_card(content)
    img = _decode(png_bytes)

    assert img.size == CANVAS_SIZE


def test_render_source_card_without_steps():
    content = CardContent(
        template_type="SOURCE_CARD",
        hook="유명 VC는 어떤 기준으로 사업계획서를 볼까요?",
        core_message="유명 VC가 실제 투자 검토에 사용하는 사업계획 구조를 공개자료로 배울 수 있다.",
        source_label="Sequoia Capital 공식 자료",
    )

    png_bytes = render_card(content)
    img = _decode(png_bytes)

    assert img.size == CANVAS_SIZE


def test_render_card_fails_closed_on_missing_hook():
    content = CardContent(
        template_type="SOURCE_CARD",
        hook="",
        core_message="core message",
        source_label="source",
    )

    with pytest.raises(ValueError):
        render_card(content)


def test_render_card_fails_closed_on_missing_core_message():
    content = CardContent(
        template_type="SOURCE_CARD",
        hook="hook",
        core_message="   ",
        source_label="source",
    )

    with pytest.raises(ValueError):
        render_card(content)


def test_render_card_fails_closed_on_missing_source_label():
    content = CardContent(
        template_type="SOURCE_CARD",
        hook="hook",
        core_message="core message",
        source_label="",
    )

    with pytest.raises(ValueError):
        render_card(content)


def test_render_card_fails_closed_on_unknown_template_type():
    content = CardContent(
        template_type="NOT_A_REAL_TEMPLATE",
        hook="hook",
        core_message="core message",
        source_label="source",
    )

    with pytest.raises(ValueError):
        render_card(content)


def test_workflow_requires_exactly_three_steps():
    content = CardContent(
        template_type="WORKFLOW",
        hook="hook",
        core_message="core message",
        source_label="source",
        steps=("only one step",),
    )

    with pytest.raises(ValueError):
        render_card(content)


def test_before_after_requires_exactly_two_steps():
    content = CardContent(
        template_type="BEFORE_AFTER",
        hook="hook",
        core_message="core message",
        source_label="source",
        steps=("only before",),
    )

    with pytest.raises(ValueError):
        render_card(content)


def test_long_korean_text_wraps_without_crashing():
    """공백 없는 긴 한글 문장도 캔버스를 벗어나지 않고(예외 없이) 렌더링돼야 한다."""
    long_hook = "매번똑같이반복되는업무를직접손으로하나씩처리하느라소중한시간을계속뺏기는상황이라면"
    content = CardContent(
        template_type="SOURCE_CARD",
        hook=long_hook,
        core_message="반복되는 업무 하나를 자동화 흐름(트리거→처리→기록)으로 바꾸면 사람이 매번 손으로 하던 일을 시스템이 대신 처리하게 만들 수 있다.",
        source_label="Zapier 공식 블로그 — Business Process Automation Examples",
    )

    png_bytes = render_card(content)
    img = _decode(png_bytes)

    assert img.size == CANVAS_SIZE


def test_default_brand_is_aijomoojin_handle():
    content = CardContent(
        template_type="SOURCE_CARD",
        hook="hook",
        core_message="core message",
        source_label="source",
    )

    assert content.brand == "@aijomoojin"


# ── 260811 신규 — render_hero_card() (AI 배경 + Pillow 텍스트 하이브리드) ────


def test_render_hero_card_produces_correct_canvas_size():
    png_bytes = render_hero_card(_hero_content())
    img = _decode(png_bytes)

    assert img.size == CANVAS_SIZE
    assert img.format == "PNG"


def test_hero_card_default_brand_is_aijomoojin_handle():
    assert _hero_content().brand == "@aijomoojin"


@pytest.mark.parametrize("field", ["headline", "subheadline", "tagline", "source_label"])
def test_hero_card_fails_closed_on_missing_required_text_field(field):
    with pytest.raises(ValueError):
        render_hero_card(_hero_content(**{field: ""}))


def test_hero_card_fails_closed_on_missing_ai_background():
    with pytest.raises(ValueError):
        render_hero_card(_hero_content(ai_background=b""))


def test_hero_card_fails_closed_when_blocks_count_is_not_four():
    only_two = (
        HeroBlock("target", "아이디어 발굴", "검증된 기회를 찾는다"),
        HeroBlock("search", "고객 검증", "진짜 시장 문제를 확인한다"),
    )

    with pytest.raises(ValueError):
        render_hero_card(_hero_content(blocks=only_two))


def test_hero_card_fails_closed_on_empty_block_title_or_desc():
    blocks = (
        HeroBlock("target", "", "검증된 기회를 찾는다"),
        HeroBlock("search", "고객 검증", "진짜 시장 문제를 확인한다"),
        HeroBlock("gear", "제품 개발", "시행착오 없이 MVP를 만든다"),
        HeroBlock("graph", "확장과 성장", "체계적으로 사업을 키운다"),
    )

    with pytest.raises(ValueError):
        render_hero_card(_hero_content(blocks=blocks))


def test_hero_card_fails_closed_on_unknown_block_icon():
    blocks = (
        HeroBlock("rocket_ship", "아이디어 발굴", "검증된 기회를 찾는다"),
        HeroBlock("search", "고객 검증", "진짜 시장 문제를 확인한다"),
        HeroBlock("gear", "제품 개발", "시행착오 없이 MVP를 만든다"),
        HeroBlock("graph", "확장과 성장", "체계적으로 사업을 키운다"),
    )

    with pytest.raises(ValueError):
        render_hero_card(_hero_content(blocks=blocks))


def test_hero_card_long_headline_shrinks_to_fit_one_line_without_crashing():
    """260811 회장 지시 — 헤드라인은 줄바꿈되지 않고 한 줄에 들어가야 한다.
    아주 긴 헤드라인도 예외 없이 렌더링되고(폰트 크기를 줄여서 한 줄 유지),
    캔버스 크기를 벗어나지 않아야 한다."""
    long_headline = "매우 길고 긴 헤드라인 텍스트가 한 줄에 다 들어가야 하는 극단적인 경우의 테스트 문구입니다"

    png_bytes = render_hero_card(_hero_content(headline=long_headline))
    img = _decode(png_bytes)

    assert img.size == CANVAS_SIZE


def test_hero_card_long_block_text_shrinks_to_fit_without_crashing():
    """260814 ERR-113 — hero_card_content_builder의 문자수 상한을 실측 근거로
    완화한 만큼(예: block desc 14자→20자), 렌더러 쪽에도 구조적 안전장치가
    있어야 한다. 상한을 크게 넘는 block title/desc를 줘도 예외 없이
    렌더링되고 캔버스를 벗어나지 않아야 한다(_hero_fit_block_line)."""
    long_blocks = (
        HeroBlock("target", "아주 길고 긴 블록 제목입니다", "이것도 상한을 크게 초과하는 아주 긴 설명 문구입니다"),
        HeroBlock("search", "고객 검증", "진짜 시장 문제를 확인한다"),
        HeroBlock("gear", "제품 개발", "시행착오 없이 MVP를 만든다"),
        HeroBlock("graph", "확장과 성장", "체계적으로 사업을 키운다"),
    )

    png_bytes = render_hero_card(_hero_content(blocks=long_blocks))
    img = _decode(png_bytes)

    assert img.size == CANVAS_SIZE


def test_hero_card_accepts_ai_background_in_different_aspect_ratio():
    """image_provider_cloudflare가 만드는 실제 배경은 정사각형(1024x1024)에
    가깝다 — 4:5 캔버스와 비율이 달라도 예외 없이 리사이즈·크롭돼야 한다."""
    square_bg = Image.new("RGB", (768, 768), (20, 20, 60))
    buf = io.BytesIO()
    square_bg.save(buf, format="PNG")

    png_bytes = render_hero_card(_hero_content(ai_background=buf.getvalue()))
    img = _decode(png_bytes)

    assert img.size == CANVAS_SIZE
