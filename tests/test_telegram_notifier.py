"""261106 Telegram 알림 — ok=true 일 때만 성공, 토큰 비노출, 미설정 시 None. 네트워크 없음(requests.post 대체)."""

import services.telegram_notifier as tg


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def _env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:SECRETTOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")


def test_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert tg.get_notify_fn() is None and tg.send_message("x") is False


def test_success_only_when_ok_true(monkeypatch):
    _env(monkeypatch)
    sent = {}
    monkeypatch.setattr(tg.requests, "post", lambda url, json, timeout: sent.update(url=url, json=json) or _Resp(200, {"ok": True}))
    assert tg.get_notify_fn()("hello") is True
    assert sent["json"] == {"chat_id": "42", "text": "hello"} and sent["url"].endswith("/sendMessage")


def test_failure_variants_return_false(monkeypatch, caplog):
    _env(monkeypatch)
    for resp in (_Resp(200, {"ok": False}), _Resp(200, None), _Resp(401, {"ok": False})):
        monkeypatch.setattr(tg.requests, "post", lambda url, json, timeout, r=resp: r)
        assert tg.send_message("x") is False

    def boom(url, json, timeout):
        raise RuntimeError("https://api.telegram.org/bot123:SECRETTOKEN/sendMessage failed")
    monkeypatch.setattr(tg.requests, "post", boom)
    tg.logger.propagate = True
    with caplog.at_level("DEBUG", logger=tg.logger.name):
        assert tg.send_message("x") is False
    assert "SECRETTOKEN" not in caplog.text
