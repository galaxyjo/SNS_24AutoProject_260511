"""Track B-4 — visual_brief.py 단위 테스트. Provider 호출 없음(순수 함수)."""

from modules.sns.visual_brief import (
    DEFAULT_ASPECT_RATIO,
    PROMPT_VERSION,
    build_background_only_prompt,
    build_image_prompt,
    build_visual_brief,
)


def test_build_visual_brief_includes_base_forbidden_elements():
    brief = build_visual_brief("3.1", "core message")
    assert "logo" in brief.forbidden_elements
    assert "text" in brief.forbidden_elements
    assert "invented statistics or numbers" in brief.forbidden_elements


def test_build_visual_brief_appends_prohibited_expression():
    brief = build_visual_brief("3.1", "core message", prohibited_expression="레디 피플")
    assert "레디 피플" in brief.forbidden_elements


def test_build_image_prompt_returns_none_when_core_message_empty():
    brief = build_visual_brief("3.1", "")
    assert build_image_prompt(brief) is None


def test_build_image_prompt_contains_core_message_and_metadata():
    brief = build_visual_brief("3.1", "Netflix trusts people over process", tone_style="confident")
    prompt = build_image_prompt(brief)

    assert prompt is not None
    assert "Netflix trusts people over process" in prompt.prompt_text
    assert "confident" in prompt.prompt_text
    assert prompt.aspect_ratio == DEFAULT_ASPECT_RATIO
    assert prompt.prompt_version == PROMPT_VERSION


def test_build_image_prompt_negative_prompt_includes_forbidden_elements():
    brief = build_visual_brief("3.1", "core message", prohibited_expression="레디 피플")
    prompt = build_image_prompt(brief)

    assert "logo" in prompt.negative_prompt
    assert "레디 피플" in prompt.negative_prompt


def test_build_image_prompt_never_adds_facts_beyond_core_message():
    brief = build_visual_brief("3.1", "only this fact is allowed")
    prompt = build_image_prompt(brief)

    assert "only this fact is allowed" in prompt.prompt_text
    # 프롬프트 템플릿 자체가 다른 사실을 주입하지 않는지(허용된 문구 집합 밖의 숫자·고유명사 없음)
    assert "%" not in prompt.prompt_text


# ── Canary #1 실측(260731) 회귀 방지: negative_prompt 미지원 Provider에서도 안전 ──

def test_build_image_prompt_no_text_instruction_covers_any_language():
    brief = build_visual_brief("3.1", "core message")
    prompt = build_image_prompt(brief)
    assert "any language" in prompt.prompt_text


def test_build_visual_brief_with_title_adds_brand_avoidance_to_forbidden_elements():
    brief = build_visual_brief("3.1", "core message", title="Netflix Culture Memo")
    assert any("Netflix Culture Memo" in item for item in brief.forbidden_elements)


def test_build_image_prompt_instructs_avoiding_actual_brand_logo_in_positive_prompt():
    """negative_prompt는 이 Provider(FLUX.1-schnell/Cloudflare)에서 무시되므로(260731 실측
    확인), 브랜드 회피 지시는 반드시 prompt_text 본문에 있어야 한다."""
    brief = build_visual_brief("3.1", "Netflix trusts people over process", title="Netflix Culture Memo")
    prompt = build_image_prompt(brief)

    assert "Do NOT depict Netflix Culture Memo's actual logo" in prompt.prompt_text


def test_build_image_prompt_without_title_has_no_brand_clause():
    brief = build_visual_brief("3.1", "core message")
    prompt = build_image_prompt(brief)
    assert "Do NOT depict" not in prompt.prompt_text


# ── 260811 Visual Type Wiring — build_background_only_prompt() ────────────

def test_build_background_only_prompt_returns_none_when_core_message_empty():
    brief = build_visual_brief("3.1", "")
    assert build_background_only_prompt(brief) is None


def test_build_background_only_prompt_contains_core_message_and_metadata():
    brief = build_visual_brief("3.1", "Sequoia's business plan structure", tone_style="confident")
    prompt = build_background_only_prompt(brief)

    assert prompt is not None
    assert "Sequoia's business plan structure" in prompt.prompt_text
    assert "confident" in prompt.prompt_text
    assert prompt.aspect_ratio == DEFAULT_ASPECT_RATIO
    assert prompt.prompt_version == PROMPT_VERSION


def test_build_background_only_prompt_no_text_instruction_covers_any_language():
    brief = build_visual_brief("3.1", "core message")
    prompt = build_background_only_prompt(brief)
    assert "any language" in prompt.prompt_text


def test_build_background_only_prompt_instructs_avoiding_actual_brand_logo():
    brief = build_visual_brief("3.1", "core message", title="Sequoia Capital Resources")
    prompt = build_background_only_prompt(brief)
    assert "Do NOT depict Sequoia Capital Resources's actual logo" in prompt.prompt_text


def test_build_background_only_prompt_negative_prompt_includes_forbidden_elements():
    brief = build_visual_brief("3.1", "core message", prohibited_expression="레디 피플")
    prompt = build_background_only_prompt(brief)
    assert "logo" in prompt.negative_prompt
    assert "레디 피플" in prompt.negative_prompt


def test_build_background_only_prompt_is_distinct_function_from_build_image_prompt():
    """기존 build_image_prompt()는 이 함수 추가로 전혀 수정되지 않는다(회귀 방지)."""
    brief = build_visual_brief("3.1", "core message")
    original = build_image_prompt(brief)
    background = build_background_only_prompt(brief)
    assert original.prompt_text != background.prompt_text
