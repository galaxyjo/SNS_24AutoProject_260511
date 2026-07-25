"""260725 — modules/common/credential_resolver.py 단위 테스트.

Account_Registry.credential_key → .env 자격증명 조회 유틸.
비밀값 원문이 예외 메시지에 노출되지 않는지도 함께 확인한다.
"""

import pytest

from modules.common.credential_resolver import (
    CredentialResolutionError,
    resolve_credential,
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
