"""Track B-4 — image_provider_cloudflare.py 단위 테스트.

실제 Cloudflare API 호출 없음(requests.post mock) — 별도 승인 전 실호출 금지 원칙 준수.
"""

import base64
import sqlite3

import pytest

import modules.sns.image_provider_cloudflare as provider


@pytest.fixture(autouse=True)
def _isolated_quota_db(tmp_path, monkeypatch):
    """모든 테스트에서 실제 db/image_gen_quota.db 대신 임시 DB 사용."""
    monkeypatch.setattr(provider, "_DB_PATH", tmp_path / "image_gen_quota_test.db")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "fake-token")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "fake-account")


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


def _fake_success_response(image_bytes=b"fake-png-bytes"):
    return _FakeResponse(
        status_code=200,
        json_data={"success": True, "result": {"image": base64.b64encode(image_bytes).decode()}},
    )


def test_quota_available_true_when_no_generations_yet():
    assert provider.quota_available() is True


def test_generate_image_success_records_generation(monkeypatch):
    monkeypatch.setattr(
        provider.requests, "post", lambda *a, **k: _fake_success_response(b"abc123")
    )

    result = provider.generate_image("a conceptual illustration", negative_prompt="text, logo")

    assert result.success is True
    assert result.image_bytes == b"abc123"
    assert result.provider == provider.PROVIDER_NAME
    assert result.model == provider.MODEL_NAME
    assert result.generation_timestamp  # 비어있지 않음


def test_generate_image_blocks_after_daily_cap_reached(monkeypatch):
    monkeypatch.setattr(provider.requests, "post", lambda *a, **k: _fake_success_response())

    for _ in range(provider.DAILY_IMAGE_CAP):
        r = provider.generate_image("prompt")
        assert r.success is True

    blocked = provider.generate_image("prompt")
    assert blocked.success is False
    assert blocked.error_code == "DAILY_IMAGE_CAP_EXCEEDED"
    assert provider.quota_available() is False


def test_generate_image_fails_closed_when_credentials_missing(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.setattr(provider.requests, "post", lambda *a, **k: _fake_success_response())

    result = provider.generate_image("prompt")

    assert result.success is False
    assert result.error_code == "CREDENTIALS_MISSING"


def test_generate_image_fails_closed_on_empty_prompt(monkeypatch):
    monkeypatch.setattr(provider.requests, "post", lambda *a, **k: _fake_success_response())

    result = provider.generate_image("")

    assert result.success is False
    assert result.error_code == "EMPTY_PROMPT"


def test_generate_image_fails_closed_on_non_200_http_status(monkeypatch):
    monkeypatch.setattr(
        provider.requests, "post",
        lambda *a, **k: _FakeResponse(status_code=429, text="rate limited"),
    )

    result = provider.generate_image("prompt")

    assert result.success is False
    assert result.error_code == "HTTP_429"


def test_generate_image_fails_closed_on_api_success_false(monkeypatch):
    monkeypatch.setattr(
        provider.requests, "post",
        lambda *a, **k: _FakeResponse(status_code=200, json_data={"success": False, "errors": ["bad prompt"]}),
    )

    result = provider.generate_image("prompt")

    assert result.success is False
    assert result.error_code == "API_ERROR"


def test_generate_image_fails_closed_on_request_exception(monkeypatch):
    def _raise(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(provider.requests, "post", _raise)

    result = provider.generate_image("prompt")

    assert result.success is False
    assert result.error_code == "REQUEST_FAILED"


def test_generate_image_fails_closed_on_missing_image_field(monkeypatch):
    monkeypatch.setattr(
        provider.requests, "post",
        lambda *a, **k: _FakeResponse(status_code=200, json_data={"success": True, "result": {}}),
    )

    result = provider.generate_image("prompt")

    assert result.success is False
    assert result.error_code == "NO_IMAGE_IN_RESPONSE"


def test_generate_image_never_sends_negative_prompt_in_payload(monkeypatch):
    """260807 — Cloudflare가 `/negative_prompt`를 스키마 위반(HTTP 400)으로 거부함을
    Runtime Evidence로 확인. FLUX.1-schnell이 지원하지 않는 이 필드는 인자로 받아도
    실제 요청 payload에는 절대 포함되면 안 된다."""
    captured = {}

    def _spy(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        return _fake_success_response()

    monkeypatch.setattr(provider.requests, "post", _spy)

    result = provider.generate_image("a conceptual illustration", negative_prompt="text, logo")

    assert result.success is True
    assert "negative_prompt" not in captured["payload"]


def test_credential_check_happens_before_any_request(monkeypatch):
    calls = {"post": 0}

    def _spy(*a, **k):
        calls["post"] += 1
        return _fake_success_response()

    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.setattr(provider.requests, "post", _spy)

    provider.generate_image("prompt")

    assert calls["post"] == 0  # credential 없으면 API 호출 자체를 안 함
