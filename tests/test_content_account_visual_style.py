"""261028 STEP 4 — 전 계정 공통 콘텐츠·이미지 고도화 구조 확인.

- 캐러셀 기본 스타일은 전 계정 "note"(고도화 경로). 구형 "template"은 환경값으로 명시할 때만.
- Account_Registry.content_theme가 기존 계정 조회 경로로 읽혀 생성 프롬프트(글+이미지 장면)에 반영된다.
- Gemini 접두사는 신규 계정에서 표 수정 없이 규칙(`{credential_key}_GEMINI_API_KEY`)으로 해석된다.
- 일시 오류만 재시도하고 품질 Gate·Persona/Source 불일치·중복은 재시도하지 않는다.
"""
import launcher.main as lm
from modules.common import credential_resolver as cr
from modules.sns import carousel_content_builder as ccb


def test_every_registered_account_defaults_to_note_style():
    for code, acct in lm.CONTENT_ACCOUNTS.items():
        assert acct.carousel_style == "note", code


def test_env_value_takes_precedence_over_account_default(monkeypatch):
    acct = lm.CONTENT_ACCOUNTS["IDN-000024"]
    monkeypatch.setenv("IDN_000024_CAROUSEL_STYLE", "template")
    assert (lm._account_flag(acct, "CAROUSEL_STYLE", "") or acct.carousel_style) == "template"
    monkeypatch.delenv("IDN_000024_CAROUSEL_STYLE", raising=False)
    assert (lm._account_flag(acct, "CAROUSEL_STYLE", "") or acct.carousel_style) == "note"


def test_content_theme_enters_text_prompt_and_image_scene_rule_only_when_present():
    with_theme = ccb._build_persona_prompt_block("", "", "", "", "", content_theme="AI+뷰티")
    assert "Account main theme: AI+뷰티" in with_theme
    assert ccb._build_persona_prompt_block("", "", "", "", "") == ""   # 공란이면 기존 Prompt 불변


def test_content_persona_kwargs_reads_theme_from_existing_account_lookup():
    acct = lm.CONTENT_ACCOUNTS["IDN-000024"]
    persona = {"persona_code": "PER-023", "tone_style": "t", "language": "ko", "content_pillars": "beauty",
               "seo_keywords": "k", "conversion_cta": "c"}

    class _Repo:
        def get_active_persona_by_account_code_v2(self, code):
            return persona

        def get_publish_account(self, code):
            return {"content_theme": "AI+뷰티(AI.beautique)"}

    assert lm._content_persona_kwargs(_Repo(), acct)["content_theme"] == "AI+뷰티(AI.beautique)"

    class _RepoNoAccount(_Repo):
        def get_publish_account(self, code):
            raise RuntimeError("down")

    assert lm._content_persona_kwargs(_RepoNoAccount(), acct)["content_theme"] == ""   # 테마는 선택 입력 — 생성은 막지 않음


def test_gemini_prefix_uses_exception_table_then_convention_then_fail_closed(monkeypatch):
    assert cr.gemini_env_prefix("AI") == "AIJOMOOJIN"                       # 예외 이름 표 우선
    monkeypatch.setenv("IDN_000999_GEMINI_API_KEY", "x")
    assert cr.gemini_env_prefix("IDN_000999") == "IDN_000999"               # 신규 계정: 규칙으로 해석(표 수정 불필요)
    monkeypatch.delenv("IDN_000998_GEMINI_API_KEY", raising=False)
    assert cr.gemini_env_prefix("IDN_000998") is None                       # 키가 없으면 Fail-closed(공유 Key 대체 없음)


def test_only_transient_codes_are_retried():
    transient = lm._PRODUCER_TRANSIENT_ERROR_CODES
    assert {"IMAGE_GENERATION_FAILED", "CAPTION_GENERATION_FAILED"} <= transient
    for code in ("SOURCE_PERSONA_MISMATCH", "NO_SELECTABLE_TOPIC", "DUPLICATE_CAPTION_TEXT",
                 "IMAGE_TEXT_CHECK_FAILED", "NOTE_CLIENT_MISSING", "VAULT_SCAN_ERROR"):
        assert code not in transient
    assert lm._PRODUCER_MAX_ATTEMPTS == 3


def test_carousel_is_default_on_for_common_accounts_and_off_for_legacy_aijomoojin(monkeypatch):
    common = lm.CONTENT_ACCOUNTS["IDN-000024"]
    legacy = lm.CONTENT_ACCOUNTS["IDN-000036"]
    monkeypatch.delenv("IDN_000024_CAROUSEL_ENABLED", raising=False)
    monkeypatch.delenv("AIJOMOOJIN_CAROUSEL_ENABLED", raising=False)
    assert lm._carousel_enabled(common) is True            # 신규 공통 계정은 고도화(캐러셀)가 기본
    assert lm._carousel_enabled(legacy) is False           # 기존 aijomoojin은 환경값이 true일 때만(변경 없음)
    monkeypatch.setenv("IDN_000024_CAROUSEL_ENABLED", "false")
    assert lm._carousel_enabled(common) is False           # 명시적으로 끄면 존중


# ── 261028 마무리: 영구 이미지 공급자 오류(NSFW 정책 차단 HTTP 400 등)는 재시도 대상에서 제외 ──
import pytest
from types import SimpleNamespace

from modules.sns import content_package_builder as cpb


@pytest.mark.parametrize("provider_error,expected", [
    ("HTTP_400", "IMAGE_PROVIDER_REJECTED"),            # Cloudflare NSFW 정책 차단
    ("HTTP_403", "IMAGE_PROVIDER_REJECTED"),
    ("DAILY_IMAGE_CAP_EXCEEDED", "IMAGE_PROVIDER_REJECTED"),
    ("CREDENTIALS_MISSING", "IMAGE_PROVIDER_REJECTED"),
    ("HTTP_429", "IMAGE_GENERATION_FAILED"),            # 일시(속도 제한)
    ("HTTP_503", "IMAGE_GENERATION_FAILED"),
    ("REQUEST_FAILED", "IMAGE_GENERATION_FAILED"),
    ("NO_IMAGE_IN_RESPONSE", "IMAGE_GENERATION_FAILED"),
])
def test_image_provider_failures_split_into_permanent_and_transient(provider_error, expected):
    assert cpb._image_failure_code(provider_error) == expected


def test_nsfw_http_400_is_not_retried_but_network_failure_is(monkeypatch):
    carousel = SimpleNamespace(slides=[SimpleNamespace(image_scene="a scene", text="t")])
    topic = SimpleNamespace(title="x")
    monkeypatch.setattr(cpb, "generate_image", lambda prompt: SimpleNamespace(success=False, error_code="HTTP_400"))
    images, code = cpb._build_note_carousel_images(topic, carousel)
    assert images is None and code == "IMAGE_PROVIDER_REJECTED"
    assert code not in lm._PRODUCER_TRANSIENT_ERROR_CODES

    monkeypatch.setattr(cpb, "generate_image", lambda prompt: SimpleNamespace(success=False, error_code="REQUEST_FAILED"))
    images, code = cpb._build_note_carousel_images(topic, carousel)
    assert images is None and code == "IMAGE_GENERATION_FAILED"
    assert code in lm._PRODUCER_TRANSIENT_ERROR_CODES


def test_scene_prompt_keeps_theme_to_wording_and_scenes_to_slide_meaning(monkeypatch):
    """261028 028 실측 3회: 계정 주제를 장면에 허용하면 요리 장면이 반복됐다. 주제가 있어도 장면은 장 글 의미로만 그린다."""
    import json as _json
    from modules.sns import carousel_content_builder as ccb2
    from modules.sns.source_selector import SourceTopic

    captured = {}

    class _Models:
        def generate_content(self, model, contents, config):
            captured["prompt"] = contents
            raise RuntimeError("stop after capturing the prompt")

    client = SimpleNamespace(models=_Models())
    monkeypatch.setattr(ccb2, "_throttle", lambda: None)
    topic = SourceTopic(topic_id="3.1", title="Example", status="VERIFIED FACT", source_url="https://example.com/s",
                        core_message="이 도구는 하루 3건 자동 게시를 지원한다.", prohibited_expression="")
    ccb2.generate_carousel_content(topic, "REACH", "HOOK_IMPACT", client=client, slide_count=3,
                                   with_image_scenes=True, content_theme="AI+여행+음식")
    prompt = str(captured["prompt"])
    assert "Account main theme: AI+여행+음식" in prompt                      # 문구에는 반영
    assert "do not set any scene in the world of the account theme" in prompt  # 장면에는 반영 금지

    captured.clear()
    ccb2.generate_carousel_content(topic, "REACH", "HOOK_IMPACT", client=client, slide_count=3, with_image_scenes=True)
    assert "account theme" not in str(captured["prompt"])                    # 테마가 없으면 프롬프트 불변
