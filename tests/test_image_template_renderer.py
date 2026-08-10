"""Track B-8 — image_template_renderer.py 단위 테스트.

실제 이미지 렌더링을 실행한다(Pillow, 외부 API 호출 없음). Vault/Airtable/
게시 어디에도 쓰지 않는다.
"""

import io

import pytest
from PIL import Image

from modules.sns.image_template_renderer import CANVAS_SIZE, CardContent, render_card


def _decode(png_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png_bytes))


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
