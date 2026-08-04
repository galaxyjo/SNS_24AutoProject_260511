"""tests/test_ai_content_gate_v0.py — 260801 AI_CONTENT Gate v0 최소 테스트.
실제 Gemini 호출 없이 mock으로 검증한다. PRODUCT 도메인 기존 동작 불변도 확인."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from modules.sns.content_filter import resolve_publish_gate, passes_ai_content_gate_v0
from modules.sns import caption_generator


class _SafetyResponse:
    def __init__(self, *, candidates=None, prompt_feedback=None, text="SAFE", text_error=None):
        self.candidates = candidates or []
        self.prompt_feedback = prompt_feedback
        self._text = text
        self._text_error = text_error
        self.text_accesses = 0

    @property
    def text(self):
        self.text_accesses += 1
        if self._text_error:
            raise self._text_error
        return self._text


def _safety_response(
    finish_reason=genai_types.FinishReason.STOP, text="SAFE", text_error=None
):
    return _SafetyResponse(
        candidates=[genai_types.Candidate(finish_reason=finish_reason)],
        text=text,
        text_error=text_error,
    )


class _SequenceModels:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0

    def generate_content(self, model, contents):
        self.calls += 1
        outcome = self._outcomes[self.calls - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _patch_safety_client(monkeypatch, outcomes):
    models = _SequenceModels(outcomes)
    monkeypatch.setattr(
        caption_generator, "_get_client", lambda: MagicMock(models=models)
    )
    monkeypatch.setattr(caption_generator, "_throttle", lambda: None)
    monkeypatch.setattr(caption_generator.time, "sleep", lambda _seconds: None)
    return models


def _server_error(code=503):
    return genai_errors.ServerError(
        code, {"error": {"code": code, "message": "transient", "status": "UNAVAILABLE"}}
    )


def _client_error(code):
    return genai_errors.ClientError(
        code, {"error": {"code": code, "message": "permanent", "status": "INVALID_ARGUMENT"}}
    )


def _forbidden_get_client():
    raise AssertionError("전역 caption_generator._get_client()가 호출되면 안 됨")


def _forbidden_throttle():
    raise AssertionError("전역 caption_generator._throttle()이 호출되면 안 됨")


class TestCheckCaptionSafety:
    def test_empty_caption_blocked(self):
        assert caption_generator.check_caption_safety("") == ("PERMANENT", "EMPTY_CAPTION")

    def test_stop_finish_reason_with_normal_text_is_safe(self, monkeypatch):
        models = _patch_safety_client(monkeypatch, [_safety_response(text="SAFE")])
        assert caption_generator.check_caption_safety("hello world") == ("SAFE", "STOP")
        assert models.calls == 1

    def test_actual_safety_finish_reason_is_unsafe(self, monkeypatch):
        response = _safety_response(genai_types.FinishReason.SAFETY, text_error=AssertionError())
        models = _patch_safety_client(monkeypatch, [response])
        assert caption_generator.check_caption_safety("some text") == ("UNSAFE", "SAFETY")
        assert models.calls == 1
        assert response.text_accesses == 0

    def test_no_candidate_with_actual_block_reason_is_unsafe_without_text(self, monkeypatch):
        response = _SafetyResponse(
            candidates=[],
            prompt_feedback=genai_types.GenerateContentResponsePromptFeedback(
                block_reason=genai_types.BlockedReason.SAFETY
            ),
            text_error=AssertionError("text must not be read"),
        )
        models = _patch_safety_client(monkeypatch, [response])
        assert caption_generator.check_caption_safety("text") == ("UNSAFE", "SAFETY")
        assert models.calls == 1
        assert response.text_accesses == 0

    def test_no_candidate_without_block_reason_is_permanent_without_text(self, monkeypatch):
        response = _SafetyResponse(
            candidates=[], text_error=AssertionError("text must not be read")
        )
        models = _patch_safety_client(monkeypatch, [response])
        assert caption_generator.check_caption_safety("text") == (
            "PERMANENT", "NO_CANDIDATE_WITHOUT_BLOCK_REASON"
        )
        assert models.calls == 1
        assert response.text_accesses == 0

    def test_unspecified_block_reason_is_not_treated_as_unsafe(self, monkeypatch):
        response = _SafetyResponse(
            candidates=[],
            prompt_feedback=genai_types.GenerateContentResponsePromptFeedback(
                block_reason=genai_types.BlockedReason.BLOCKED_REASON_UNSPECIFIED
            ),
            text_error=AssertionError("text must not be read"),
        )
        _patch_safety_client(monkeypatch, [response])
        assert caption_generator.check_caption_safety("text") == (
            "PERMANENT", "NO_CANDIDATE_WITHOUT_BLOCK_REASON"
        )
        assert response.text_accesses == 0

    def test_stop_with_exact_safety_text_is_unsafe(self, monkeypatch):
        _patch_safety_client(monkeypatch, [_safety_response(text="  SAFETY  ")])
        assert caption_generator.check_caption_safety("text") == ("UNSAFE", "SAFETY_TEXT")

    def test_safety_text_substring_is_not_blocked(self, monkeypatch):
        _patch_safety_client(monkeypatch, [_safety_response(text="SAFETY CHECK COMPLETE")])
        assert caption_generator.check_caption_safety("text") == ("SAFE", "STOP")

    def test_503_then_success_is_exactly_two_attempts(self, monkeypatch):
        models = _patch_safety_client(monkeypatch, [_server_error(), _safety_response()])
        assert caption_generator.check_caption_safety("text") == ("SAFE", "STOP")
        assert models.calls == 2

    def test_503_exhausts_at_exactly_four_attempts(self, monkeypatch):
        models = _patch_safety_client(monkeypatch, [_server_error()] * 4)
        assert caption_generator.check_caption_safety("text") == (
            "RETRY_EXHAUSTED", "provider_http_503"
        )
        assert models.calls == caption_generator._MAX_ATTEMPTS == 4

    @pytest.mark.parametrize(
        "error",
        [httpx.ReadTimeout("timeout"), httpx.ConnectError("connect")],
    )
    def test_transport_errors_are_bounded(self, monkeypatch, error):
        models = _patch_safety_client(monkeypatch, [error] * 4)
        status, reason = caption_generator.check_caption_safety("text")
        assert status == "RETRY_EXHAUSTED"
        assert reason.startswith("transport_")
        assert models.calls == 4

    @pytest.mark.parametrize("code", [400, 401, 403])
    def test_permanent_http_errors_make_one_attempt(self, monkeypatch, code):
        models = _patch_safety_client(monkeypatch, [_client_error(code)])
        assert caption_generator.check_caption_safety("text") == (
            "PERMANENT", f"permanent_http_{code}"
        )
        assert models.calls == 1

    def test_injected_client_bypasses_global_get_client(self, monkeypatch):
        """260805 Codex 리뷰(P1) — client 주입 시 전역 _get_client()가 0회
        호출되는지 직접 증명한다(이전 라운드는 인자가 전달됐다는 것만 확인했지,
        전역 Client가 실제로 미호출인지는 검증하지 않았다)."""
        monkeypatch.setattr(caption_generator, "_get_client", _forbidden_get_client)
        monkeypatch.setattr(caption_generator, "_throttle", lambda: None)
        models = _SequenceModels([_safety_response(text="SAFE")])
        injected_client = MagicMock(models=models)

        status, reason = caption_generator.check_caption_safety("hello", client=injected_client)

        assert (status, reason) == ("SAFE", "STOP")
        assert models.calls == 1

    def test_injected_throttle_bypasses_global_throttle(self, monkeypatch):
        """260805 Codex 리뷰(P1) — throttle_fn 주입 시 전역 _throttle()이 0회
        호출되는지 직접 증명한다."""
        monkeypatch.setattr(caption_generator, "_throttle", _forbidden_throttle)
        models = _SequenceModels([_safety_response(text="SAFE")])
        monkeypatch.setattr(caption_generator, "_get_client", lambda: MagicMock(models=models))
        injected_calls = []

        status, reason = caption_generator.check_caption_safety(
            "hello", throttle_fn=lambda: injected_calls.append(1)
        )

        assert (status, reason) == ("SAFE", "STOP")
        assert injected_calls == [1]
        assert models.calls == 1


class TestAiContentGateV0:
    def _patch_safe(self):
        return patch("modules.sns.caption_generator.check_caption_safety", return_value=("SAFE", "STOP"))

    def test_all_conditions_pass(self):
        with self._patch_safe():
            allowed, code = passes_ai_content_gate_v0(
                "caption text", "IDN-000036", "https://jobs.netflix.com/culture", "PER-002"
            )
        assert allowed is True
        assert code == "PUBLISH_ALLOWED"

    def test_wrong_account_blocked(self):
        allowed, code = passes_ai_content_gate_v0("c", "IDN-999999", "https://x", "PER-002")
        assert allowed is False
        assert code == "AI_CONTENT_ACCOUNT_MISMATCH"

    def test_wrong_persona_blocked(self):
        allowed, code = passes_ai_content_gate_v0("c", "IDN-000036", "https://x", "PER-999")
        assert allowed is False
        assert code == "AI_CONTENT_PERSONA_MISMATCH"

    def test_empty_caption_blocked(self):
        allowed, code = passes_ai_content_gate_v0("", "IDN-000036", "https://x", "PER-002")
        assert allowed is False
        assert code == "AI_CONTENT_EMPTY_CAPTION"

    def test_missing_source_blocked(self):
        allowed, code = passes_ai_content_gate_v0("c", "IDN-000036", "", "PER-002")
        assert allowed is False
        assert code == "AI_CONTENT_NO_SOURCE"

    def test_gemini_safety_blocked(self):
        with patch("modules.sns.caption_generator.check_caption_safety", return_value=("UNSAFE", "SAFETY")):
            allowed, code = passes_ai_content_gate_v0(
                "caption", "IDN-000036", "https://jobs.netflix.com/culture", "PER-002"
            )
        assert allowed is False
        assert code == "AI_CONTENT_SAFETY_BLOCKED:SAFETY"

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("RETRY_EXHAUSTED", "AI_CONTENT_SAFETY_RETRY_EXHAUSTED:provider_http_503"),
            ("PERMANENT", "AI_CONTENT_SAFETY_CHECK_FAILED:permanent_http_400"),
        ],
    )
    def test_operational_safety_failures_are_not_content_blocks(self, status, expected):
        reason = "provider_http_503" if status == "RETRY_EXHAUSTED" else "permanent_http_400"
        with patch(
            "modules.sns.caption_generator.check_caption_safety",
            return_value=(status, reason),
        ):
            allowed, code = passes_ai_content_gate_v0(
                "caption", "IDN-000036", "https://jobs.netflix.com/culture", "PER-002"
            )
        assert allowed is False
        assert code == expected

    def test_english_caption_blocked_when_korean_required(self):
        """260801 6E — 실측 오사고(영어 게시) 재발방지. required_language="ko"인데
        caption이 영어면 Gemini Safety 호출 전에 차단돼야 한다."""
        allowed, code = passes_ai_content_gate_v0(
            "This is an English caption about our product line today",
            "IDN-000036", "https://jobs.netflix.com/culture", "PER-002",
            required_language="ko",
        )
        assert allowed is False
        assert code == "AI_CONTENT_LANGUAGE_MISMATCH"

    def test_korean_caption_passes_when_korean_required(self):
        with self._patch_safe():
            allowed, code = passes_ai_content_gate_v0(
                "오늘 하루도 힘내세요 여러분 좋은 하루 보내시길 바랍니다",
                "IDN-000036", "https://jobs.netflix.com/culture", "PER-002",
                required_language="ko",
            )
        assert allowed is True
        assert code == "PUBLISH_ALLOWED"

    def test_required_language_blank_skips_check(self):
        """required_language 미전달(기존 호출부/PRODUCT 등)은 언어검사를 건너뛴다 — 하위호환."""
        with self._patch_safe():
            allowed, code = passes_ai_content_gate_v0(
                "English caption text here", "IDN-000036",
                "https://jobs.netflix.com/culture", "PER-002",
            )
        assert allowed is True
        assert code == "PUBLISH_ALLOWED"

    def test_safety_client_and_throttle_forwarded_to_check_caption_safety(self):
        """260805 Codex 리뷰(P0) — 게시 직전 Gate도 safety_client/safety_throttle을
        받으면 check_caption_safety()에 그대로 전달해야 한다(Research 단계만
        격리하고 여기서 다시 전역 Key를 쓰면 격리가 무의미해진다)."""
        captured = {}

        def _spy_check_caption_safety(caption, *, client=None, throttle_fn=None):
            captured["client"] = client
            captured["throttle_fn"] = throttle_fn
            return "SAFE", "STOP"

        sentinel_client = object()
        sentinel_throttle = lambda: None  # noqa: E731

        with patch(
            "modules.sns.caption_generator.check_caption_safety", _spy_check_caption_safety
        ):
            allowed, code = passes_ai_content_gate_v0(
                "caption", "IDN-000036", "https://jobs.netflix.com/culture", "PER-002",
                safety_client=sentinel_client, safety_throttle=sentinel_throttle,
            )

        assert allowed is True
        assert code == "PUBLISH_ALLOWED"
        assert captured["client"] is sentinel_client
        assert captured["throttle_fn"] is sentinel_throttle

    def test_no_safety_override_keeps_default_none(self):
        """safety_client/safety_throttle 미전달(기존 호출부)은 check_caption_safety()에
        None/None이 그대로 전달돼 전역 Client/Throttle을 쓰게 된다 — 하위호환."""
        captured = {}

        def _spy_check_caption_safety(caption, *, client=None, throttle_fn=None):
            captured["client"] = client
            captured["throttle_fn"] = throttle_fn
            return "SAFE", "STOP"

        with patch(
            "modules.sns.caption_generator.check_caption_safety", _spy_check_caption_safety
        ):
            allowed, code = passes_ai_content_gate_v0(
                "caption", "IDN-000036", "https://jobs.netflix.com/culture", "PER-002",
            )

        assert allowed is True
        assert captured["client"] is None
        assert captured["throttle_fn"] is None


class TestResolvePublishGateBackwardCompat:
    def test_product_domain_unaffected_by_new_kwargs(self):
        """PRODUCT 도메인(yuna18253)은 새 kwargs 없이도 기존 그대로 동작해야 한다."""
        allowed, code = resolve_publish_gate("wholesale k-beauty skincare export", "IDN-000041")
        assert allowed is True
        assert code == "PUBLISH_ALLOWED"

    def test_product_domain_reject_unchanged(self):
        allowed, code = resolve_publish_gate("random unrelated text", "IDN-000041")
        assert allowed is False
        assert code == "DOMAIN_CONTENT_REJECTED"

    def test_ai_content_domain_no_longer_hardblocked(self):
        with patch("modules.sns.caption_generator.check_caption_safety", return_value=("SAFE", "STOP")):
            allowed, code = resolve_publish_gate(
                "caption", "IDN-000036",
                source_url="https://jobs.netflix.com/culture", persona_code="PER-002",
            )
        assert allowed is True
        assert code == "PUBLISH_ALLOWED"

    def test_ai_content_domain_without_new_kwargs_fails_closed(self):
        """기존 2-인자 호출(kwargs 생략)은 source_url/persona_code가 빈 값이라
        Fail-closed로 차단된다 — DOMAIN_GATE_NOT_READY 하드블록은 제거됐지만
        무조건 통과는 아니라는 것을 함께 확인(구체적 사유는 검사 순서에 따라
        AI_CONTENT_PERSONA_MISMATCH 또는 AI_CONTENT_NO_SOURCE)."""
        allowed, code = resolve_publish_gate("caption", "IDN-000036")
        assert allowed is False
        assert code in ("AI_CONTENT_PERSONA_MISMATCH", "AI_CONTENT_NO_SOURCE")

    def test_unknown_domain_unaffected(self):
        allowed, code = resolve_publish_gate("c", "IDN-999999")
        assert allowed is False
        assert code == "UNKNOWN_DOMAIN"

    def test_required_language_kwarg_passthrough_blocks_english(self):
        allowed, code = resolve_publish_gate(
            "English only caption text here today",
            "IDN-000036",
            source_url="https://jobs.netflix.com/culture",
            persona_code="PER-002",
            required_language="ko",
        )
        assert allowed is False
        assert code == "AI_CONTENT_LANGUAGE_MISMATCH"

    def test_safety_client_and_throttle_passthrough_to_ai_content_gate(self):
        """260805 Codex 리뷰(P0) — resolve_publish_gate()의 safety_client/
        safety_throttle이 passes_ai_content_gate_v0()를 거쳐 check_caption_safety()
        까지 그대로 전달되는지 전체 체인으로 확인한다(launcher/main.py 게시
        직전 호출부와 동일 경로)."""
        captured = {}

        def _spy_check_caption_safety(caption, *, client=None, throttle_fn=None):
            captured["client"] = client
            captured["throttle_fn"] = throttle_fn
            return "SAFE", "STOP"

        sentinel_client = object()
        sentinel_throttle = lambda: None  # noqa: E731

        with patch(
            "modules.sns.caption_generator.check_caption_safety", _spy_check_caption_safety
        ):
            allowed, code = resolve_publish_gate(
                "caption", "IDN-000036",
                source_url="https://jobs.netflix.com/culture", persona_code="PER-002",
                safety_client=sentinel_client, safety_throttle=sentinel_throttle,
            )

        assert allowed is True
        assert code == "PUBLISH_ALLOWED"
        assert captured["client"] is sentinel_client
        assert captured["throttle_fn"] is sentinel_throttle
