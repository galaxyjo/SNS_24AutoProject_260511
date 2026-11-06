"""tests/test_text_ai_fallback.py — 261106 텍스트 생성 GPT(1순위)→Claude(2순위) 자동전환 Target Test.

실제 OpenAI/Anthropic/Gemini 호출 없음 — 전부 Fake. 운영 로그·네트워크를 건드리지 않는다.
"""

import json
from types import SimpleNamespace

import pytest

import modules.sns.carousel_content_builder as builder
import modules.sns.caption_generator as cg
from modules.common import credential_resolver as cr
from modules.sns.caption_generator import TextAIError, TextAIFallbackClient
from modules.sns.source_selector import SourceTopic

from tests.test_carousel_content_builder import _valid_payload


class _ApiError(Exception):
    def __init__(self, status_code, msg="boom"):
        super().__init__(msg)
        self.status_code = status_code


def _chat(content, finish="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content))])


class _FakeOpenAI:
    def __init__(self, content=None, exc=None, finish="stop", moderation=None, moderation_exc=None):
        self.calls = 0
        self.mod_calls = 0
        self.last_kwargs = None
        outer = self

        class _Completions:
            def create(self, **kw):
                outer.calls += 1
                outer.last_kwargs = kw
                if exc:
                    raise exc
                return _chat(content, finish)

        class _Moderations:
            def create(self, **kw):
                outer.mod_calls += 1
                if moderation_exc:
                    raise moderation_exc
                flagged, cats = moderation or (False, {})
                return SimpleNamespace(results=[SimpleNamespace(
                    flagged=flagged, categories=SimpleNamespace(model_dump=lambda: cats))])

        self.chat = SimpleNamespace(completions=_Completions())
        self.moderations = _Moderations()


class _FakeAnthropic:
    def __init__(self, text=None, exc=None):
        self.calls = 0
        outer = self

        class _Messages:
            def create(self, **kw):
                outer.calls += 1
                if exc:
                    raise exc
                return SimpleNamespace(content=[SimpleNamespace(text=text)])

        self.messages = _Messages()


class _FakeGemini:
    def __init__(self):
        self.calls = []
        outer = self

        class _Models:
            def generate_content(self, model, contents, config):
                outer.calls.append(contents)
                return SimpleNamespace(text="GEMINI")

        self.models = _Models()
        self.extra = "extra-attr"


def _client(openai=None, anthropic=None, gemini=None, anthropic_key="a-key"):
    return TextAIFallbackClient(
        openai_key="o-key", anthropic_key=anthropic_key, gemini_client=gemini, account="IDN-TEST",
        openai_factory=lambda key: openai, anthropic_factory=lambda key: anthropic,
    )


def _json_config():
    return SimpleNamespace(response_mime_type="application/json", response_json_schema={"type": "object"})


GOOD = json.dumps({"k": 1})


class TestGenerateFallback:
    def test_gpt_success_uses_gpt_only(self):
        o, a = _FakeOpenAI(content=GOOD), _FakeAnthropic(text=GOOD)
        r = _client(o, a).models.generate_content(model="m", contents="hi", config=_json_config())
        assert json.loads(r.text) == {"k": 1}
        assert o.calls == 1 and a.calls == 0  # GPT 성공 → Claude 호출 0건
        assert o.last_kwargs["response_format"] == {"type": "json_object"}
        assert "JSON" in o.last_kwargs["messages"][0]["content"]

    @pytest.mark.parametrize("exc", [_ApiError(429), _ApiError(401), _ApiError(503), TimeoutError()])
    def test_gpt_failure_switches_to_claude(self, exc):
        o, a = _FakeOpenAI(exc=exc), _FakeAnthropic(text="```json\n" + GOOD + "\n```")
        c = _client(o, a)
        r = c.models.generate_content(model="m", contents="hi", config=_json_config())
        assert json.loads(r.text) == {"k": 1}
        assert o.calls == 1 and a.calls == 1
        assert c.last_provider == "claude"

    def test_gpt_invalid_json_switches_to_claude(self):
        o, a = _FakeOpenAI(content="not json"), _FakeAnthropic(text=GOOD)
        r = _client(o, a).models.generate_content(model="m", contents="hi", config=_json_config())
        assert json.loads(r.text) == {"k": 1} and a.calls == 1

    def test_gpt_incomplete_finish_reason_switches_to_claude(self):
        o, a = _FakeOpenAI(content=GOOD, finish="length"), _FakeAnthropic(text=GOOD)
        _client(o, a).models.generate_content(model="m", contents="hi", config=_json_config())
        assert a.calls == 1

    def test_both_fail_raises_and_is_not_retryable(self):
        o, a = _FakeOpenAI(exc=_ApiError(429)), _FakeAnthropic(exc=_ApiError(500))
        with pytest.raises(TextAIError) as ei:
            _client(o, a).models.generate_content(model="m", contents="hi", config=_json_config())
        retryable, _ = cg._classify_retry(ei.value)
        assert retryable is False  # 기존 실패 경로로 곧바로 Fail-closed

    def test_no_claude_key_fails_closed_after_gpt_failure(self):
        o = _FakeOpenAI(exc=_ApiError(429))
        with pytest.raises(TextAIError):
            _client(o, None, anthropic_key="").models.generate_content(model="m", contents="hi", config=None)

    def test_plain_text_when_no_json_config(self):
        o = _FakeOpenAI(content="hello")
        r = _client(o, None).models.generate_content(model="m", contents="hi", config=None)
        assert r.text == "hello" and "response_format" not in o.last_kwargs

    def test_non_string_contents_delegate_to_gemini(self):
        g, o = _FakeGemini(), _FakeOpenAI(content=GOOD)
        c = _client(o, None, gemini=g)
        r = c.models.generate_content(model="m", contents=["image-part", "text"], config=None)
        assert r.text == "GEMINI" and o.calls == 0 and g.calls == [["image-part", "text"]]
        assert c.extra == "extra-attr"  # 그 밖의 속성은 Gemini로 위임


class TestSafety:
    def test_moderation_safe(self):
        o = _FakeOpenAI(moderation=(False, {}))
        assert _client(o, None).check_text_safety("ok") == ("SAFE", "MODERATION_OK")

    def test_moderation_flagged_blocks(self):
        o = _FakeOpenAI(moderation=(True, {"hate": False, "violence": True}))
        status, reason = _client(o, None).check_text_safety("bad")
        assert status == "UNSAFE" and reason == "MODERATION:violence"

    def test_gpt_failure_uses_claude_classification(self):
        o, a = _FakeOpenAI(moderation_exc=_ApiError(429)), _FakeAnthropic(text="SAFE")
        assert _client(o, a).check_text_safety("ok")[0] == "SAFE" and a.calls == 1

    def test_claude_unsafe_blocks_and_unparseable_blocks(self):
        o = _FakeOpenAI(moderation_exc=_ApiError(500))
        assert _client(o, _FakeAnthropic(text="UNSAFE")).check_text_safety("x")[0] == "UNSAFE"
        assert _client(o, _FakeAnthropic(text="maybe")).check_text_safety("x")[0] == "PERMANENT"

    def test_both_fail_blocks(self):
        o, a = _FakeOpenAI(moderation_exc=_ApiError(500)), _FakeAnthropic(exc=_ApiError(500))
        assert _client(o, a).check_text_safety("x")[0] == "RETRY_EXHAUSTED"

    def test_check_caption_safety_routes_to_wrapper_not_gemini(self):
        g = _FakeGemini()
        c = _client(_FakeOpenAI(moderation=(False, {})), None, gemini=g)
        assert cg.check_caption_safety("caption", client=c, throttle_fn=lambda: None) == ("SAFE", "MODERATION_OK")
        assert g.calls == []


class TestEndToEndCarousel:
    """기존 8장 캐러셀 계약·안전 검사·중복 방지는 그대로 적용된다."""

    def _topic(self):
        return SourceTopic(topic_id="3.1", title="Example Source", status="VERIFIED FACT",
                           source_url="https://example.com/source-1",
                           core_message="이 도구는 하루 3건 자동 게시를 지원한다. 무료 등급은 검색 기능이 제한된다.",
                           prohibited_expression="")

    def test_gpt_success_produces_content_and_zero_claude_calls(self):
        o, a = _FakeOpenAI(content=json.dumps(_valid_payload()), moderation=(False, {})), _FakeAnthropic(text="x")
        r = builder.generate_carousel_content(self._topic(), "REACH", "HOOK_IMPACT",
                                              client=_client(o, a), throttle_fn=lambda: None)
        assert r.success is True and a.calls == 0

    def test_gpt_failure_claude_success_produces_content(self):
        o = _FakeOpenAI(exc=_ApiError(429), moderation_exc=_ApiError(429))
        a = _FakeAnthropic(text=json.dumps(_valid_payload()))
        # 본 생성은 Claude, Safety는 Claude 분류 응답이 JSON이 아니므로 SAFE 판정을 위해 시퀀스 응답을 쓴다.
        seq = iter([json.dumps(_valid_payload()), "SAFE"])
        a.messages.create = lambda **kw: SimpleNamespace(content=[SimpleNamespace(text=next(seq))])
        r = builder.generate_carousel_content(self._topic(), "REACH", "HOOK_IMPACT",
                                              client=_client(o, a), throttle_fn=lambda: None)
        assert r.success is True

    def test_both_fail_blocks_publishing(self):
        o, a = _FakeOpenAI(exc=_ApiError(429)), _FakeAnthropic(exc=_ApiError(429))
        r = builder.generate_carousel_content(self._topic(), "REACH", "HOOK_IMPACT",
                                              client=_client(o, a), throttle_fn=lambda: None)
        assert r.success is False and r.error_code == "GENERATION_FAILED"

    def test_duplicate_fingerprint_still_blocked(self):
        o = _FakeOpenAI(content=json.dumps(_valid_payload()), moderation=(False, {}))
        first = builder.generate_carousel_content(self._topic(), "REACH", "HOOK_IMPACT",
                                                  client=_client(o, None), throttle_fn=lambda: None)
        again = builder.generate_carousel_content(
            self._topic(), "REACH", "HOOK_IMPACT", client=_client(o, None), throttle_fn=lambda: None,
            existing_fingerprints={first.content.content_fingerprint})
        assert again.success is False and again.error_code == "DUPLICATE_FINGERPRINT"


class TestResolver:
    def test_no_openai_key_means_not_enabled(self, monkeypatch):
        monkeypatch.delenv("IDN_000099_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("TEXT_AI_FALLBACK_DISABLED", raising=False)
        assert cr.resolve_text_ai_credentials("IDN_000099") is None

    def test_keys_resolved(self, monkeypatch):
        monkeypatch.setenv("IDN_000099_OPENAI_API_KEY", "o")
        monkeypatch.setenv("IDN_000099_ANTHROPIC_API_KEY", "a")
        monkeypatch.delenv("TEXT_AI_FALLBACK_DISABLED", raising=False)
        c = cr.resolve_text_ai_credentials("IDN_000099")
        assert (c.openai_key, c.anthropic_key) == ("o", "a")

    def test_kill_switch_and_bad_key(self, monkeypatch):
        monkeypatch.setenv("IDN_000099_OPENAI_API_KEY", "o")
        monkeypatch.setenv("TEXT_AI_FALLBACK_DISABLED", "true")
        assert cr.resolve_text_ai_credentials("IDN_000099") is None
        monkeypatch.delenv("TEXT_AI_FALLBACK_DISABLED")
        assert cr.resolve_text_ai_credentials("bad key") is None
        assert cr.resolve_text_ai_credentials("") is None


# ── 261107 Cloudflare Workers AI 모드 ─────────────────────────────────────────
import io as _io

import httpx
import openai

from PIL import Image as _Image

import modules.sns.image_text_checker as _itc

_CF_BASE = "https://api.cloudflare.com/client/v4/accounts/ACC/ai/v1"


def _cf_client(o, a=None, gemini=None):
    return TextAIFallbackClient(openai_key="cf-token", anthropic_key="a-key" if a else "", gemini_client=gemini,
                                account="IDN-CF", base_url=_CF_BASE,
                                openai_factory=lambda key: o, anthropic_factory=lambda key: a)


class _CfOpenAI:
    """chat.completions.create 호출을 기록하는 가짜 OpenAI 호환 client."""

    def __init__(self, content=None, exc=None, finish="stop"):
        self.calls = []
        outer = self

        class _C:
            def create(self, **kw):
                outer.calls.append(kw)
                if exc:
                    raise exc
                return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish,
                                                                message=SimpleNamespace(content=content))],
                                       usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3))

        self.chat = SimpleNamespace(completions=_C())


def _png(size, color="white"):
    buf = _io.BytesIO()
    _Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


class TestCloudflareMode:
    def test_defaults_and_label(self):
        c = _cf_client(_CfOpenAI())
        assert c.provider_name == "workers_ai" and c.vision_enabled is True
        assert c.gpt_model == "@cf/meta/llama-4-scout-17b-16e-instruct"
        assert c.safety_model == "@cf/meta/llama-guard-3-8b"
        assert _client(_FakeOpenAI(), None).vision_enabled is False   # OpenAI 모드는 기존대로 Gemini 위임

    def test_base_url_and_token_reach_openai_sdk(self, monkeypatch):
        seen = {}

        class _SDK:
            def __init__(self, **kw):
                seen.update(kw)
                self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **k: SimpleNamespace(
                    choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content='{"k":1}'))],
                    usage=None)))

        monkeypatch.setattr(openai, "OpenAI", _SDK)
        c = TextAIFallbackClient(openai_key="cf-token", account="IDN-CF", base_url=_CF_BASE)
        c.models.generate_content(model="m", contents="hi", config=None)
        assert seen == {"api_key": "cf-token", "base_url": _CF_BASE}

    def test_text_generation_uses_scout_and_labels_provider(self):
        o = _CfOpenAI(content=GOOD)
        c = _cf_client(o)
        r = c.models.generate_content(model="gemini-x", contents="hi", config=_json_config())
        assert json.loads(r.text) == {"k": 1} and c.last_provider == "workers_ai"
        assert o.calls[0]["model"] == "@cf/meta/llama-4-scout-17b-16e-instruct"

    def test_text_failure_attempt_is_labelled_workers_ai(self):
        o, a = _CfOpenAI(exc=_ApiError(429)), _FakeAnthropic(exc=_ApiError(500))
        with pytest.raises(TextAIError) as ei:
            _cf_client(o, a).models.generate_content(model="m", contents="hi", config=None)
        assert [p["provider"] for p in ei.value.providers] == ["workers_ai", "claude"]


class TestCloudflareSafetyGuard:
    @pytest.mark.parametrize("answer,expected", [
        ("\n\nsafe", ("SAFE", "GUARD_OK")),
        ("\n\nunsafe\nS1", ("UNSAFE", "GUARD:s1")),
        ("maybe", ("PERMANENT", "GUARD_UNPARSEABLE")),
    ])
    def test_guard_parsing(self, answer, expected):
        o = _CfOpenAI(content=answer)
        assert _cf_client(o).check_text_safety("caption") == expected
        assert o.calls[0]["model"] == "@cf/meta/llama-guard-3-8b"

    def test_guard_failure_uses_claude_then_blocks(self):
        o = _CfOpenAI(exc=_ApiError(429))
        a = _FakeAnthropic(text="SAFE")
        assert _cf_client(o, a).check_text_safety("x")[0] == "SAFE" and a.calls == 1
        assert _cf_client(o, _FakeAnthropic(exc=_ApiError(500))).check_text_safety("x")[0] == "RETRY_EXHAUSTED"
        assert _cf_client(o, None).check_text_safety("x")[0] == "RETRY_EXHAUSTED"

    def test_check_caption_safety_routes_to_guard(self):
        g = _FakeGemini()
        c = _cf_client(_CfOpenAI(content="safe"), None, gemini=g)
        assert cg.check_caption_safety("caption", client=c, throttle_fn=lambda: None) == ("SAFE", "GUARD_OK")
        assert g.calls == []


class TestCloudflareVision:
    def test_generate_vision_payload(self):
        o = _CfOpenAI(content='{"images":[]}')
        c = _cf_client(o)
        c.generate_vision("check", [b"\x89PNGaa", b"\x89PNGbb"], _json_config())
        kw = o.calls[0]
        parts = kw["messages"][0]["content"]
        assert kw["max_tokens"] == 400 and kw["response_format"] == {"type": "json_object"}
        assert parts[0]["type"] == "text" and [p["type"] for p in parts[1:]] == ["image_url", "image_url"]
        assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")

    def test_generate_vision_failure_raises_with_metadata(self):
        with pytest.raises(TextAIError) as ei:
            _cf_client(_CfOpenAI(exc=_ApiError(429))).generate_vision("p", [b"x"], None)
        assert ei.value.providers[0]["provider"] == "workers_ai" and ei.value.providers[0]["status"] == 429

    def test_generate_vision_disabled_in_openai_mode(self):
        with pytest.raises(TextAIError):
            _client(_FakeOpenAI(), None).generate_vision("p", [b"x"], None)

    def test_downscale_shrinks_large_and_keeps_small(self):
        big = _itc._downscale_png(_png((1024, 1024)))
        assert max(_Image.open(_io.BytesIO(big)).size) == 512
        small = _png((300, 200))
        assert _itc._downscale_png(small) == small
        tall = _itc._downscale_png(_png((1080, 1350)))
        w, h = _Image.open(_io.BytesIO(tall)).size
        assert max(w, h) == 512 and abs(w / h - 1080 / 1350) < 0.02       # 비율 유지

    def test_checker_sends_512px_images_and_parses(self):
        body = json.dumps({"images": [{"index": i, "has_text": i == 2, "has_logo": False} for i in (1, 2, 3)]})
        o = _CfOpenAI(content=body)
        res = _itc.check_images_for_text_and_logo([_png((1024, 1024))] * 3, client=_cf_client(o))
        assert res.success and [c.has_text for c in res.checks] == [False, True, False]
        sent = o.calls[0]["messages"][0]["content"][1:]
        import base64 as _b64
        dims = [_Image.open(_io.BytesIO(_b64.b64decode(p["image_url"]["url"].split(",", 1)[1]))).size for p in sent]
        assert all(max(d) == 512 for d in dims)

    def test_checker_result_count_mismatch_fails_closed(self):
        body = json.dumps({"images": [{"index": 1, "has_text": False, "has_logo": False}]})
        res = _itc.check_images_for_text_and_logo([_png((600, 600))] * 3, client=_cf_client(_CfOpenAI(content=body)))
        assert (res.success, res.error_code) == (False, "CHECK_RESULT_INVALID")

    def test_checker_call_failure_and_bad_json_fail_closed(self):
        res = _itc.check_images_for_text_and_logo([_png((600, 600))], client=_cf_client(_CfOpenAI(exc=_ApiError(500))))
        assert (res.success, res.error_code) == (False, "CHECK_CALL_FAILED")
        res = _itc.check_images_for_text_and_logo([_png((600, 600))], client=_cf_client(_CfOpenAI(content="nope")))
        assert (res.success, res.error_code) == (False, "CHECK_CALL_FAILED")

    def test_openai_mode_client_still_delegates_vision_to_gemini(self, monkeypatch):
        called = {}

        class _Models:
            def generate_content(self, model, contents, config):
                called["n"] = len(contents)
                return SimpleNamespace(text=json.dumps({"images": [{"index": 1, "has_text": False, "has_logo": False}]}))

        g = SimpleNamespace(models=_Models())
        res = _itc.check_images_for_text_and_logo([_png((600, 600))], client=_client(_FakeOpenAI(), None, gemini=g))
        assert res.success and called["n"] == 2   # 프롬프트 + 이미지 1장 — Gemini 경로 그대로


class TestCloudflareResolver:
    def test_cloudflare_mode_resolves_global_creds(self, monkeypatch):
        monkeypatch.delenv("TEXT_AI_FALLBACK_DISABLED", raising=False)
        monkeypatch.setenv("IDN_000099_TEXT_AI_PROVIDER", "cloudflare")
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc123")
        monkeypatch.delenv("IDN_000099_OPENAI_API_KEY", raising=False)
        c = cr.resolve_text_ai_credentials("IDN_000099")
        assert c.openai_key == "tok" and c.base_url == "https://api.cloudflare.com/client/v4/accounts/acc123/ai/v1"

    def test_cloudflare_mode_without_creds_is_none(self, monkeypatch):
        monkeypatch.delenv("TEXT_AI_FALLBACK_DISABLED", raising=False)
        monkeypatch.setenv("IDN_000099_TEXT_AI_PROVIDER", "cloudflare")
        monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
        assert cr.resolve_text_ai_credentials("IDN_000099") is None

    def test_kill_switch_and_openai_mode_unchanged(self, monkeypatch):
        monkeypatch.setenv("IDN_000099_TEXT_AI_PROVIDER", "cloudflare")
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
        monkeypatch.setenv("TEXT_AI_FALLBACK_DISABLED", "true")
        assert cr.resolve_text_ai_credentials("IDN_000099") is None
        monkeypatch.delenv("TEXT_AI_FALLBACK_DISABLED")
        monkeypatch.delenv("IDN_000099_TEXT_AI_PROVIDER")
        monkeypatch.setenv("IDN_000099_OPENAI_API_KEY", "o")
        c = cr.resolve_text_ai_credentials("IDN_000099")
        assert c.openai_key == "o" and c.base_url == ""      # 기존 OpenAI 방식은 base_url 없음


class TestCloudflareFailureClassification:
    def test_daily_neurons_exhausted_maps_to_credit(self):
        body = {"errors": [{"code": 4006, "message": "you have used up your daily free allocation of 10,000 neurons"}]}
        exc = openai.RateLimitError("m", response=httpx.Response(
            429, request=httpx.Request("POST", "https://x")), body=body)
        assert cg._provider_error_code(exc) == "credit_exhausted"
