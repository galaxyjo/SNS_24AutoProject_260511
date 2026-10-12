"""261012 P2 — generate_image()가 requests Timeout/ConnectionError일 때만
10초→60초 대기 후 최대 2회 재시도한다. HTTP 응답 실패·그 외 예외는 기존처럼 즉시 Fail-closed.
HTTP·sleep 전부 mock(실제 Cloudflare 호출 0건).
"""

import base64

import pytest
import requests

import modules.sns.image_provider_cloudflare as provider


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(provider, "_DB_PATH", tmp_path / "image_gen_quota_test.db")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "fake-token")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "fake-account")


class _Resp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


_OK = _Resp(200, {"success": True, "result": {"image": base64.b64encode(b"png").decode()}})


def _run(monkeypatch, side_effects):
    calls, sleeps = [], []
    seq = iter(side_effects)

    def _post(*a, **k):
        calls.append(1)
        item = next(seq)
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr(provider.requests, "post", _post)
    monkeypatch.setattr(provider.time, "sleep", lambda s: sleeps.append(s))
    return provider.generate_image("prompt"), calls, sleeps


@pytest.mark.parametrize("exc", [
    requests.exceptions.ReadTimeout("read timeout"),
    requests.exceptions.ConnectTimeout("connect timeout"),
    requests.exceptions.ConnectionError("conn reset"),
])
def test_timeout_then_recover(monkeypatch, exc):
    result, calls, sleeps = _run(monkeypatch, [exc, _OK])
    assert result.success is True
    assert len(calls) == 2 and sleeps == [10]


def test_timeout_exhausted_fails_closed(monkeypatch):
    e = requests.exceptions.ReadTimeout("read timeout")
    result, calls, sleeps = _run(monkeypatch, [e, e, e])
    assert result.success is False and result.error_code == "REQUEST_FAILED"
    assert len(calls) == 3 and sleeps == [10, 60]
    assert provider.quota_available() is True  # 실패는 상한 카운트 미증가


@pytest.mark.parametrize("status", [400, 500, 503])
def test_http_error_response_no_retry(monkeypatch, status):
    result, calls, sleeps = _run(monkeypatch, [_Resp(status, text="err")])
    assert result.success is False and result.error_code == f"HTTP_{status}"
    assert len(calls) == 1 and sleeps == []


def test_other_exception_no_retry(monkeypatch):
    result, calls, sleeps = _run(monkeypatch, [RuntimeError("boom")])
    assert result.error_code == "REQUEST_FAILED"
    assert len(calls) == 1 and sleeps == []


def test_first_attempt_success_single_request(monkeypatch):
    result, calls, sleeps = _run(monkeypatch, [_OK])
    assert result.success is True
    assert len(calls) == 1 and sleeps == []
