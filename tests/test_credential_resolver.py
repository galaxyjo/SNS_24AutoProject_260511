"""260725 — modules/common/credential_resolver.py 단위 테스트.

Account_Registry.credential_key → .env 자격증명 조회 유틸.
비밀값 원문이 예외 메시지에 노출되지 않는지도 함께 확인한다.
"""

import pytest

from modules.common.credential_resolver import (
    CredentialResolutionError,
    resolve_credential,
    resolve_gemini_credential,
)


def test_resolve_credential_success(monkeypatch):
    monkeypatch.setenv("AI_INSTA_IG_USER_ID", "17841467725643424")
    monkeypatch.setenv("AI_INSTA_ACCESS_TOKEN", "IGAA-fake-token-value")

    cred = resolve_credential("AI")

    assert cred.ig_user_id == "17841467725643424"
    assert cred.access_token == "IGAA-fake-token-value"


@pytest.mark.parametrize(
    "bad_key",
    ["", "ai", "AI TEST", "../AI", "ai-token", "AI-TOKEN", "AI TOKEN", " AI"],
)
def test_resolve_credential_rejects_malformed_key(bad_key):
    with pytest.raises(CredentialResolutionError):
        resolve_credential(bad_key)


def test_resolve_credential_missing_env_raises(monkeypatch):
    monkeypatch.delenv("MISSING_INSTA_IG_USER_ID", raising=False)
    monkeypatch.delenv("MISSING_INSTA_ACCESS_TOKEN", raising=False)

    with pytest.raises(CredentialResolutionError):
        resolve_credential("MISSING")


def test_resolve_credential_partial_env_raises(monkeypatch):
    """ig_user_id는 있는데 access_token만 없는 경우도 차단(모호한 절반 성공 금지)."""
    monkeypatch.setenv("PARTIAL_INSTA_IG_USER_ID", "123")
    monkeypatch.delenv("PARTIAL_INSTA_ACCESS_TOKEN", raising=False)

    with pytest.raises(CredentialResolutionError):
        resolve_credential("PARTIAL")


def test_resolve_credential_error_message_never_contains_token(monkeypatch):
    monkeypatch.setenv("LEAK_INSTA_IG_USER_ID", "123")
    monkeypatch.setenv("LEAK_INSTA_ACCESS_TOKEN", "SUPER-SECRET-TOKEN-VALUE")

    # 형식 오류 케이스 — 애초에 .env를 조회하지 않으므로 토큰이 메시지에 나올 수 없음
    with pytest.raises(CredentialResolutionError) as exc_info:
        resolve_credential("leak")  # 소문자라 형식 오류
    assert "SUPER-SECRET-TOKEN-VALUE" not in str(exc_info.value)


def test_resolve_credential_uses_correct_env_naming_convention(monkeypatch):
    """실제 .env 네이밍({key}_INSTA_IG_USER_ID/{key}_INSTA_ACCESS_TOKEN)과 정확히 일치해야 함
    (Codex 2라운드 지적 — {key}_IG_USER_ID/{key}_ACCESS_TOKEN으로 구현하면 안 됨)."""
    monkeypatch.setenv("AI_INSTA_IG_USER_ID", "999")
    monkeypatch.setenv("AI_INSTA_ACCESS_TOKEN", "tok")
    # 잘못된 네이밍 변형은 설정 안 함 — 이게 존재해도 조회되면 안 되는 걸 증명
    monkeypatch.delenv("AI_IG_USER_ID", raising=False)
    monkeypatch.delenv("AI_ACCESS_TOKEN", raising=False)

    cred = resolve_credential("AI")
    assert cred.ig_user_id == "999"
    assert cred.access_token == "tok"


# ── 260805 Track B 7B-5 — resolve_gemini_credential() ─────────────────────

class TestResolveGeminiCredential:
    def test_known_credential_key_resolves_persona_specific_env_prefix(self, monkeypatch):
        """credential_key='AI'는 AIJOMOOJIN_GEMINI_API_KEY를 조회한다(Instagram
        쪽 AI_INSTA_*와 접두사가 다름 — 역사적으로 별도 명명됨, 리네이밍 없이
        매핑만 존재)."""
        monkeypatch.setenv("AIJOMOOJIN_GEMINI_API_KEY", "fake-persona-key-value")
        monkeypatch.setenv("AIJOMOOJIN_GEMINI_ACCOUNT_EMAIL", "nguyenknv15@gmail.com")

        cred = resolve_gemini_credential("AI")

        assert cred.api_key == "fake-persona-key-value"
        assert cred.account_email == "nguyenknv15@gmail.com"

    def test_does_not_read_shared_global_gemini_api_key(self, monkeypatch):
        """공유/전역 GEMINI_API_KEY가 설정돼 있어도 이 함수는 그 값을 절대
        반환하지 않는다(자동 fallback 금지)."""
        monkeypatch.setenv("GEMINI_API_KEY", "shared-corea-galaxy-key")
        monkeypatch.setenv("AIJOMOOJIN_GEMINI_API_KEY", "persona-only-key")

        cred = resolve_gemini_credential("AI")

        assert cred.api_key == "persona-only-key"
        assert cred.api_key != "shared-corea-galaxy-key"

    def test_unmapped_credential_key_raises_without_fallback(self, monkeypatch):
        """매핑표에 없는 credential_key는 공유 Key로 대체하지 않고 즉시
        Fail-closed한다."""
        monkeypatch.setenv("GEMINI_API_KEY", "shared-corea-galaxy-key")

        with pytest.raises(CredentialResolutionError):
            resolve_gemini_credential("UNKNOWN_PERSONA")

    def test_missing_env_value_raises_without_fallback(self, monkeypatch):
        monkeypatch.delenv("AIJOMOOJIN_GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "shared-corea-galaxy-key")

        with pytest.raises(CredentialResolutionError):
            resolve_gemini_credential("AI")

    def test_malformed_credential_key_rejected(self):
        with pytest.raises(CredentialResolutionError):
            resolve_gemini_credential("ai")

    def test_error_message_never_contains_api_key_value(self, monkeypatch):
        monkeypatch.delenv("AIJOMOOJIN_GEMINI_API_KEY", raising=False)

        with pytest.raises(CredentialResolutionError) as exc_info:
            resolve_gemini_credential("AI")

        assert "AIzaSy" not in str(exc_info.value)
        assert "AQ.Ab8" not in str(exc_info.value)
