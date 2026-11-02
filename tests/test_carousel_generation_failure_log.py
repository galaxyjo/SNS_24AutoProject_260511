"""261102 ERR-192 — 캐러셀 Gemini 호출 예외가 로그에 남는지 검증(반환 계약은 그대로).
실제 Gemini·네트워크 없음 — 전부 Fake.
"""

import logging

import pytest
from google.genai import errors as genai_errors

import modules.sns.carousel_content_builder as builder
from modules.sns.source_selector import SourceTopic

_SECRET = "AIzaSyFAKEFAKEFAKEFAKEFAKEFAKE12345"


class _Models:
    def __init__(self, excs):
        self.excs = list(excs)
        self.calls = 0

    def generate_content(self, model, contents, config):
        self.calls += 1
        raise self.excs.pop(0)


class _Client:
    def __init__(self, models):
        self.models = models


def _topic():
    return SourceTopic(topic_id="3.1", title="T", status="VERIFIED FACT", source_url="https://example.com/s",
                       core_message="이 도구는 하루 3건 자동 게시를 지원한다.", prohibited_expression="")


@pytest.fixture
def run(monkeypatch):
    sleeps = []
    monkeypatch.setattr(builder, "_throttle", lambda: None)
    monkeypatch.setattr(builder.time, "sleep", lambda s: sleeps.append(s))

    def _run(excs, caplog):
        models = _Models(excs)
        monkeypatch.setattr(builder, "_get_client", lambda: _Client(models))
        builder.logger.propagate = True
        with caplog.at_level(logging.DEBUG, logger=builder.logger.name):
            result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")
        return result, models, sleeps

    return _run


def _api_error(code):
    return genai_errors.APIError(code, {"error": {"code": code, "message": "boom " + _SECRET, "status": "X"}})


def _records(caplog):
    return [r for r in caplog.records if "Gemini 호출 예외" in r.getMessage()]


def test_non_retryable_error_is_logged_once_as_error(run, caplog):
    result, models, _ = run([_api_error(400)], caplog)
    assert result.success is False and result.error_code == "GENERATION_FAILED"   # 반환 계약 불변
    recs = _records(caplog)
    assert len(recs) == 1 and recs[0].levelno == logging.ERROR
    msg = recs[0].getMessage()
    assert "attempt=1/" in msg and "http_code=400" in msg and "retryable=False" in msg and "will_retry=False" in msg
    assert "permanent_http_400" in msg and "APIError" in msg


def test_retryable_error_logs_every_attempt_then_final_error(run, caplog):
    attempts = builder._MAX_ATTEMPTS
    result, models, sleeps = run([_api_error(503)] * attempts, caplog)
    assert result.error_code == "GENERATION_FAILED" and models.calls == attempts and len(sleeps) == attempts - 1
    recs = _records(caplog)
    assert len(recs) == attempts
    assert [r.levelno for r in recs] == [logging.WARNING] * (attempts - 1) + [logging.ERROR]
    assert "will_retry=True" in recs[0].getMessage() and "provider_http_503" in recs[0].getMessage()
    assert f"attempt={attempts}/{attempts}" in recs[-1].getMessage() and "will_retry=False" in recs[-1].getMessage()


def test_secret_like_text_is_masked_and_message_truncated(run, caplog):
    long_exc = RuntimeError(("x" * 500) + _SECRET)
    result, _, _ = run([long_exc], caplog)
    msg = _records(caplog)[0].getMessage()
    assert _SECRET not in msg and "message=" in msg and len(msg.split("message=")[1]) <= 200
    result, _, _ = run([RuntimeError("key=" + _SECRET + " fail")], caplog)
    assert _SECRET not in _records(caplog)[-1].getMessage()


@pytest.mark.parametrize("raw", [
    "request failed api_key=ZZSECRETVALUE99 end",
    "bad access_token=ZZSECRETVALUE99&x=1",
    "Authorization: Bearer ZZSECRETVALUE99",
    "authorization=ZZSECRETVALUE99",
    "https://x/y?token=ZZSECRETVALUE99",
])
def test_common_sanitizer_formats_are_masked(run, caplog, raw):
    run([RuntimeError(raw)], caplog)
    msg = _records(caplog)[0].getMessage()
    assert "ZZSECRETVALUE99" not in msg and "message=" in msg


def test_producer_failure_log_states_max_attempts_not_actual():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "launcher" / "main.py").read_text(encoding="utf-8")
    assert "max_attempts={_PRODUCER_MAX_ATTEMPTS}" in src and "attempts<=" not in src


def test_retryable_then_success_path_unchanged(monkeypatch, caplog):
    """일시 오류 1회 뒤 성공하면 결과가 정상(success)이고 경고 로그만 1건."""
    import json

    class _Resp:
        def __init__(self, p):
            self.text = json.dumps(p)

    from tests.test_carousel_content_builder import _valid_payload

    class _M:
        def __init__(self):
            self.calls = 0

        def generate_content(self, model, contents, config):
            self.calls += 1
            if self.calls == 1:
                raise _api_error(429)
            return _Resp(_valid_payload())

    m = _M()
    monkeypatch.setattr(builder, "_get_client", lambda: _Client(m))
    monkeypatch.setattr(builder, "_throttle", lambda: None)
    monkeypatch.setattr(builder, "check_caption_safety", lambda text, **kw: ("SAFE", "STOP"))
    monkeypatch.setattr(builder.time, "sleep", lambda s: None)
    builder.logger.propagate = True
    with caplog.at_level(logging.DEBUG, logger=builder.logger.name):
        result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT")
    assert result.success is True and m.calls == 2
    recs = _records(caplog)
    assert len(recs) == 1 and recs[0].levelno == logging.WARNING and "http_code=429" in recs[0].getMessage()
