"""Token log-redaction regression tests.

ERR/SEC: Graph API 예외 문자열에 access_token이 평문으로 로그에 남는 문제
(logs/summary/app.log 외 6개 파일, 593건 노출 확인 — 260723 감사) 재발 방지.

FAKE_SECRET_TOKEN만 사용 — 실제 운영 토큰은 이 테스트에서 절대 사용하지 않는다.
"""

import logging

from modules.common.log_sanitizer import redact_sensitive

FAKE = "FAKE_SECRET_TOKEN"


# ── 1. sanitizer 단위 테스트 ──────────────────────────────────────────────

def test_redacts_plain_query_token():
    out = redact_sensitive(f"access_token={FAKE}")
    assert FAKE not in out
    assert "[REDACTED]" in out


def test_redacts_url_encoded_token():
    out = redact_sensitive(f"access_token%3D{FAKE}%26foo%3Dbar")
    assert FAKE not in out
    assert "foo%3Dbar" in out


def test_redacts_case_insensitive_keys():
    for key in ("access_token", "ACCESS_TOKEN", "Access_Token", "token", "TOKEN",
                "api_key", "API_KEY", "apikey", "APIKEY"):
        out = redact_sensitive(f"{key}={FAKE}")
        assert FAKE not in out, f"leaked for key={key}"


def test_redacts_token_deep_inside_long_url():
    text = (
        "400 Client Error: Bad Request for url: "
        "https://graph.facebook.com/v21.0/17841476202821375/media_publish"
        f"?creation_id=17895531663540095&access_token={FAKE}"
    )
    out = redact_sensitive(text)
    assert FAKE not in out
    assert "creation_id=17895531663540095" in out
    assert "graph.facebook.com" in out


def test_redacts_only_token_param_among_many():
    text = f"fields=like_count,comments_count&access_token={FAKE}&other=value"
    out = redact_sensitive(text)
    assert FAKE not in out
    assert "fields=like_count,comments_count" in out
    assert "other=value" in out


def test_no_token_present_unchanged():
    text = "HTTPSConnectionPool(host='api.airtable.com', port=443): Read timed out. (read timeout=30)"
    assert redact_sensitive(text) == text


def test_redacts_httperror_style_message():
    text = (
        "400 Client Error: Bad Request for url: "
        f"https://graph.facebook.com/v21.0/x/media_publish?creation_id=1&access_token={FAKE}"
    )
    out = redact_sensitive(text)
    assert FAKE not in out
    assert "400 Client Error" in out


def test_redacts_connectionerror_style_message():
    text = (
        "HTTPSConnectionPool(host='graph.facebook.com', port=443): Max retries exceeded with url: "
        f"/v21.0/x/media?access_token={FAKE} (Caused by NewConnectionError('failed'))"
    )
    out = redact_sensitive(text)
    assert FAKE not in out
    assert "Max retries exceeded" in out


def test_redacts_timeout_style_message():
    text = (
        "HTTPSConnectionPool(host='graph.facebook.com', port=443): Read timed out. "
        f"(read timeout=30) url=/v21.0/x/media_publish?creation_id=1&access_token={FAKE}"
    )
    out = redact_sensitive(text)
    assert FAKE not in out
    assert "Read timed out" in out


def test_redacts_authorization_header_style():
    out = redact_sensitive(f"Authorization: Bearer {FAKE}")
    assert FAKE not in out
    assert out == "Authorization: Bearer [REDACTED]"


def test_empty_and_none_inputs_are_noop():
    assert redact_sensitive("") == ""
    assert redact_sensitive(None) is None


# ── 2. launcher/main.py publish_single 회귀 테스트 (Step 1) ──────────────

def test_publish_single_logs_no_token_on_connection_error(monkeypatch, caplog):
    import requests as real_requests
    from launcher import main as launcher_main

    def _boom(*args, **kwargs):
        raise real_requests.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='graph.facebook.com', port=443): "
            f"Max retries exceeded with url: /v21.0/x/media?access_token={FAKE}"
        )

    monkeypatch.setattr(real_requests, "post", _boom)
    monkeypatch.setattr(launcher_main, "_preprocess_image", lambda url: url)

    with caplog.at_level(logging.WARNING):
        result = launcher_main.publish_single("rid1", "http://img", "caption", FAKE, "iguser")

    assert result["ok"] is False
    assert FAKE not in caplog.text
    assert "[REDACTED]" in caplog.text
    assert "3회 실패 최종" in caplog.text  # 기존 3회 재시도 동작 회귀 없음


def test_publish_single_success_path_unaffected(monkeypatch):
    """정상 게시 흐름의 함수 signature/반환 계약이 바뀌지 않았는지 확인."""
    import requests as real_requests
    from launcher import main as launcher_main

    class _OkResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "creation123"}

    calls = []

    def _fake_post(url, params=None, timeout=None):
        calls.append(url)
        return _OkResp()

    monkeypatch.setattr(real_requests, "post", _fake_post)
    monkeypatch.setattr(launcher_main, "_preprocess_image", lambda url: url)

    result = launcher_main.publish_single("rid2", "http://img", "caption", FAKE, "iguser")

    assert result == {"ok": True, "ig_media_id": "creation123"}
    assert len(calls) == 2  # media 생성 + media_publish 2회 호출 그대로


# ── 3. engagement_tracker.py _fetch_metrics 회귀 테스트 (Step 2) ─────────

def test_fetch_metrics_logs_no_token_on_connection_error(monkeypatch, caplog):
    import requests as real_requests
    from modules.interaction_engine import engagement_tracker

    def _boom(*args, **kwargs):
        raise real_requests.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='graph.facebook.com', port=443): "
            f"Max retries exceeded with url: /v21.0/media123?access_token={FAKE}"
        )

    monkeypatch.setattr(engagement_tracker.requests, "get", _boom)

    with caplog.at_level(logging.WARNING):
        result = engagement_tracker._fetch_metrics("media123", FAKE)

    assert result is None
    assert FAKE not in caplog.text
    assert "[REDACTED]" in caplog.text
    assert "조회 실패" in caplog.text


def test_fetch_metrics_success_path_unaffected(monkeypatch):
    """정상 metric 수집 계약(반환값)이 바뀌지 않았는지 확인."""
    from modules.interaction_engine import engagement_tracker

    class _OkResp:
        def json(self):
            return {"like_count": 10, "comments_count": 3}

    monkeypatch.setattr(
        engagement_tracker.requests, "get",
        lambda *a, **k: _OkResp(),
    )

    result = engagement_tracker._fetch_metrics("media123", FAKE)
    assert result == {"like_count": 10, "comments_count": 3}
