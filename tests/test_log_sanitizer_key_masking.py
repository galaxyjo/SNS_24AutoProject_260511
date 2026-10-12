"""261012 2단계 — 단독 `key=`(ImgBB 등)·access_token 마스킹과 예외 로그 출력 마스킹.
모든 값은 가짜. Live API 요청 0건(requests.get mock).
"""

import logging

import requests

from modules.common.log_sanitizer import redact_sensitive
import modules.comment.comment_poller as poller

FAKE_KEY = "fakeimgbbkey0123456789"
FAKE_TOKEN = "EAAfaketoken0123456789"


def test_bare_query_key_is_masked():
    text = (
        "HTTPSConnectionPool(host='api.imgbb.com', port=443): Max retries exceeded with url: "
        f"/1/upload?key={FAKE_KEY} (Caused by ConnectTimeoutError(...))"
    )
    out = redact_sensitive(text)
    assert FAKE_KEY not in out
    assert "key=[REDACTED]" in out
    assert "api.imgbb.com" in out and "ConnectTimeoutError" in out


def test_key_among_other_params_and_encoded():
    out = redact_sensitive(f"/1/upload?expiration=600&key={FAKE_KEY}&name=a")
    assert FAKE_KEY not in out and "expiration=600" in out and "name=a" in out
    out2 = redact_sensitive(f"url=%2F1%2Fupload%3Fkey%3D{FAKE_KEY}%26x%3D1")
    assert FAKE_KEY not in out2


def test_access_token_still_masked():
    out = redact_sensitive(f"/v25.0/123/media?fields=id&access_token={FAKE_TOKEN}&limit=5")
    assert FAKE_TOKEN not in out and "fields=id" in out and "limit=5" in out


def test_plain_text_and_suffixed_identifiers_preserved():
    text = "content_id=3-3-261010 | idempotency_key=abc123 | monkey=1 | rid=recX | code=9004"
    assert redact_sensitive(text) == text


def test_comment_poller_exception_log_is_masked(monkeypatch, caplog):
    def _raise(*a, **k):
        raise requests.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='graph.facebook.com', port=443): Max retries exceeded with url: "
            f"/v25.0/1784/media?fields=id%2Ctimestamp&limit=10&access_token={FAKE_TOKEN}"
        )

    monkeypatch.setattr(poller.requests, "get", _raise)
    with caplog.at_level(logging.ERROR, logger=poller.logger.name):
        assert poller.get_recent_media_ids() == []
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "media 조회 예외" in logged
    assert FAKE_TOKEN not in logged
    assert "access_token=[REDACTED]" in logged


def test_imgbb_upload_error_string_masked_as_logged_by_producer():
    # launcher/main.py Producer는 upload.get("error")를 redact_sensitive(str(...))로 감싸 기록한다.
    err = f"imgbb 업로드 실패: HTTPSConnectionPool(host='api.imgbb.com', port=443): url: /1/upload?key={FAKE_KEY} (Caused by X)"
    out = redact_sensitive(str(err))
    assert FAKE_KEY not in out and "imgbb 업로드 실패" in out
