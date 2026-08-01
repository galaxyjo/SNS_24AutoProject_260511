"""tests/test_ai_content_gate_v0.py — 260801 AI_CONTENT Gate v0 최소 테스트.
실제 Gemini 호출 없이 mock으로 검증한다. PRODUCT 도메인 기존 동작 불변도 확인."""

from unittest.mock import MagicMock, patch

from modules.sns.content_filter import resolve_publish_gate, passes_ai_content_gate_v0
from modules.sns import caption_generator


def _mock_gemini_response(finish_reason_name="STOP"):
    candidate = MagicMock()
    reason = MagicMock()
    reason.name = finish_reason_name
    candidate.finish_reason = reason
    resp = MagicMock()
    resp.candidates = [candidate]
    return resp


class TestCheckCaptionSafety:
    def test_empty_caption_blocked(self):
        assert caption_generator.check_caption_safety("") == (False, "EMPTY_CAPTION")

    def test_stop_finish_reason_is_safe(self):
        with patch.object(caption_generator, "_get_client", return_value=MagicMock(
            models=MagicMock(generate_content=MagicMock(return_value=_mock_gemini_response("STOP")))
        )), patch.object(caption_generator, "_throttle"):
            safe, reason = caption_generator.check_caption_safety("hello world")
        assert safe is True
        assert reason == "STOP"

    def test_safety_finish_reason_is_blocked(self):
        with patch.object(caption_generator, "_get_client", return_value=MagicMock(
            models=MagicMock(generate_content=MagicMock(return_value=_mock_gemini_response("SAFETY")))
        )), patch.object(caption_generator, "_throttle"):
            safe, reason = caption_generator.check_caption_safety("some text")
        assert safe is False
        assert reason == "SAFETY"

    def test_api_exception_blocks(self):
        with patch.object(caption_generator, "_get_client", side_effect=RuntimeError("boom")):
            safe, reason = caption_generator.check_caption_safety("text")
        assert safe is False
        assert reason.startswith("SAFETY_CHECK_ERROR")


class TestAiContentGateV0:
    def _patch_safe(self):
        return patch("modules.sns.caption_generator.check_caption_safety", return_value=(True, "STOP"))

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
        with patch("modules.sns.caption_generator.check_caption_safety", return_value=(False, "SAFETY")):
            allowed, code = passes_ai_content_gate_v0(
                "caption", "IDN-000036", "https://jobs.netflix.com/culture", "PER-002"
            )
        assert allowed is False
        assert code == "AI_CONTENT_SAFETY_BLOCKED:SAFETY"

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
        with patch("modules.sns.caption_generator.check_caption_safety", return_value=(True, "STOP")):
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
