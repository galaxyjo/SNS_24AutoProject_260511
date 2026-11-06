"""tests/test_text_ai_failure_diag.py — 261107 텍스트 AI(GPT→Claude) 최종 실패 진단 Target Test.

실제 API·운영 원장·Telegram 없음 — 임시 DB와 가짜 notify만 쓴다.
"""

import json
import sqlite3
from types import SimpleNamespace

import anthropic
import httpx
import openai
import pytest

import modules.sns.carousel_content_builder as builder
from modules.common import error_events as ev
from modules.common import gemini_failure_diag as diag
from modules.sns.caption_generator import TextAIError, TextAIFallbackClient
from modules.sns.source_selector import SourceTopic

from tests.test_carousel_content_builder import _valid_payload

_REQ = httpx.Request("POST", "https://example.invalid")


def _openai_credit_error():
    return openai.RateLimitError("m", response=httpx.Response(429, request=_REQ),
                                 body={"message": "You have no credits remaining. sk-proj-SECRETKEY123", "type": "x"})


def _anthropic_credit_error():
    return anthropic.BadRequestError(
        "m", response=httpx.Response(400, request=_REQ),
        body={"type": "error", "error": {"type": "invalid_request_error",
                                         "message": "Your credit balance is too low. sk-ant-SECRETKEY999"}})


def _attempt(provider="gpt", status=None, code="", etype="Exception", finish="", tin=None, tout=None):
    return {"provider": provider, "model": "m", "status": status, "code": code, "etype": etype,
            "finish": finish, "tin": tin, "tout": tout, "ms": 12}


def _rows(db):
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute("select source,account,error_class,severity,http,stage,detail_head from events").fetchall()
    finally:
        conn.close()


class _FakeOpenAI:
    def __init__(self, exc=None, content=None):
        outer = self
        self.exc, self.content = exc, content

        class _C:
            def create(self, **kw):
                if outer.exc:
                    raise outer.exc
                return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop",
                                                                message=SimpleNamespace(content=outer.content))],
                                       usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))

        self.chat = SimpleNamespace(completions=_C())


class _FakeAnthropic:
    def __init__(self, exc=None):
        outer = self
        self.exc = exc

        class _M:
            def create(self, **kw):
                raise outer.exc

        self.messages = _M()


def _client(o, a):
    return TextAIFallbackClient(openai_key="o", anthropic_key="a", account="IDN-T",
                                openai_factory=lambda k: o, anthropic_factory=lambda k: a)


class TestClassification:
    @pytest.mark.parametrize("attempts,expected", [
        ([_attempt(status=429, code="credit_exhausted"), _attempt("claude", 400, "credit_exhausted")], diag.TEXT_AI_CREDIT),
        ([_attempt(status=429, code="insufficient_quota")], diag.TEXT_AI_CREDIT),
        ([_attempt(status=401, code="invalid_api_key"), _attempt("claude", 500)], diag.TEXT_AI_AUTH),
        ([_attempt(finish="length", code="text_ai_gpt_incomplete"), _attempt("claude", 503)], diag.TEXT_AI_EMPTY),
        ([_attempt(etype="ValueError", code="invalid_json"), _attempt("claude", etype="ValueError")], diag.TEXT_AI_SCHEMA),
        ([_attempt(status=429, code="rate_limit_exceeded"), _attempt("claude", 429)], diag.TEXT_AI_RATE),
        ([_attempt(etype="APITimeoutError"), _attempt("claude", etype="APIConnectionError")], diag.TEXT_AI_TIMEOUT),
        ([_attempt(status=503), _attempt("claude", 500)], diag.TEXT_AI_TRANSIENT),
        ([_attempt(etype="KeyError")], diag.TEXT_AI_UNKNOWN),
        ([], diag.TEXT_AI_UNKNOWN),
    ])
    def test_classes(self, tmp_path, attempts, expected):
        got = diag.record_gemini_failure(TextAIError("X", providers=attempts), account="PER-T", db_path=tmp_path / "e.db",
                                         notify_async=False)
        assert got == expected


class TestLedgerAndAlerts:
    def test_one_row_per_final_failure_with_fields(self, tmp_path):
        db = tmp_path / "e.db"
        exc = TextAIError("TEXT_AI_ALL_PROVIDERS_FAILED", providers=[
            _attempt(status=429, code="credit_exhausted", tin=1830, tout=0),
            _attempt("claude", 400, "credit_exhausted")])
        diag.record_gemini_failure(exc, account="PER-018", db_path=db, notify_async=False)
        rows = _rows(db)
        assert len(rows) == 1
        source, account, klass, severity, http, stage, detail = rows[0]
        assert (source, account, klass, severity, http, stage) == (
            "text_ai", "PER-018", "TEXT_AI_CREDIT", "P1", 429, "carousel_generate")
        assert "gpt:" in detail and "claude:" in detail and "tok=1830/0" in detail and "ms=12" in detail

    def test_non_final_logs_only(self, tmp_path):
        db = tmp_path / "e.db"
        diag.record_gemini_failure(TextAIError("X", providers=[_attempt(status=503)]), account="PER-T", final=False,
                                   db_path=db, notify_async=False)
        assert not db.exists() or _rows(db) == []

    def test_alert_once_per_day_per_account_for_credit_and_auth_only(self, tmp_path):
        db, sent = tmp_path / "e.db", []
        exc = TextAIError("X", providers=[_attempt(status=429, code="credit_exhausted")])
        for _ in range(3):
            diag.record_gemini_failure(exc, account="PER-018", db_path=db, notify=lambda m: sent.append(m) or True,
                                       notify_async=False)
        diag.record_gemini_failure(exc, account="PER-019", db_path=db, notify=lambda m: sent.append(m) or True,
                                   notify_async=False)
        diag.record_gemini_failure(TextAIError("X", providers=[_attempt(status=503)]), account="PER-020", db_path=db,
                                   notify=lambda m: sent.append(m) or True, notify_async=False)
        assert len(sent) == 2                      # 018 1회 + 019 1회, 일시 오류(503)는 알리지 않음
        assert len(_rows(db)) == 5                  # 실패 1건당 원장 1행(경보 중복 제한과 별개)

    def test_failed_delivery_releases_daily_claim(self, tmp_path):
        db, calls = tmp_path / "e.db", []
        exc = TextAIError("X", providers=[_attempt(status=401, code="invalid_api_key")])
        diag.record_gemini_failure(exc, account="PER-1", db_path=db, notify=lambda m: calls.append(m) or False,
                                   notify_async=False)
        diag.record_gemini_failure(exc, account="PER-1", db_path=db, notify=lambda m: calls.append(m) or True,
                                   notify_async=False)
        assert len(calls) == 2

    def test_diag_failure_never_raises(self, tmp_path):
        bad_db = tmp_path                                       # 디렉터리 → sqlite 연결 실패
        exc = TextAIError("X", providers=[_attempt(status=429, code="credit_exhausted")])
        assert diag.record_gemini_failure(exc, account="PER-1", db_path=bad_db, notify_async=False) is None

    def test_no_secrets_stored(self, tmp_path):
        db = tmp_path / "e.db"
        o = _FakeOpenAI(exc=_openai_credit_error())
        a = _FakeAnthropic(exc=_anthropic_credit_error())
        with pytest.raises(TextAIError) as ei:
            _client(o, a).models.generate_content(model="m", contents="hi", config=None)
        diag.record_gemini_failure(ei.value, account="PER-1", db_path=db, notify_async=False)
        blob = json.dumps(_rows(db)) + json.dumps(ei.value.providers)
        assert "SECRETKEY" not in blob and "sk-proj" not in blob and "sk-ant" not in blob


class TestWrapperMetadata:
    def test_providers_carry_codes_and_stay_non_retryable(self):
        o, a = _FakeOpenAI(exc=_openai_credit_error()), _FakeAnthropic(exc=_anthropic_credit_error())
        with pytest.raises(TextAIError) as ei:
            _client(o, a).models.generate_content(model="m", contents="hi", config=None)
        gpt, claude = ei.value.providers
        assert (gpt["provider"], gpt["status"], gpt["code"]) == ("gpt", 429, "credit_exhausted")
        assert (claude["provider"], claude["status"], claude["code"]) == ("claude", 400, "credit_exhausted")
        assert str(ei.value) == "TEXT_AI_ALL_PROVIDERS_FAILED" and "429" not in str(ei.value)

    def test_invalid_json_and_length_are_distinguishable(self):
        o = _FakeOpenAI(content="not json")
        a = _FakeAnthropic(exc=anthropic.APITimeoutError(request=_REQ))
        cfg = SimpleNamespace(response_mime_type="application/json", response_json_schema={"type": "object"})
        with pytest.raises(TextAIError) as ei:
            _client(o, a).models.generate_content(model="m", contents="hi", config=cfg)
        gpt, claude = ei.value.providers
        assert gpt["code"] == "invalid_json" and gpt["etype"] == "ValueError" and gpt["tin"] == 10 and gpt["tout"] == 5
        assert claude["etype"] == "APITimeoutError"


class TestEndToEndCarouselRecording:
    def _topic(self):
        return SourceTopic(topic_id="3.1", title="Example Source", status="VERIFIED FACT",
                           source_url="https://example.com/source-1",
                           core_message="이 도구는 하루 3건 자동 게시를 지원한다. 무료 등급은 검색 기능이 제한된다.",
                           prohibited_expression="")

    def _isolate(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ev, "_DB_PATH", tmp_path / "e.db")
        monkeypatch.setattr(diag, "_default_notify", lambda: None)
        return tmp_path / "e.db"

    def test_both_fail_records_exactly_one_row_and_blocks(self, monkeypatch, tmp_path):
        db = self._isolate(monkeypatch, tmp_path)
        o, a = _FakeOpenAI(exc=_openai_credit_error()), _FakeAnthropic(exc=_anthropic_credit_error())
        r = builder.generate_carousel_content(self._topic(), "REACH", "HOOK_IMPACT", client=_client(o, a),
                                              throttle_fn=lambda: None, diag_account="PER-018")
        assert r.success is False and r.error_code == "GENERATION_FAILED"
        rows = _rows(db)
        assert len(rows) == 1 and rows[0][0] == "text_ai" and rows[0][2] == "TEXT_AI_CREDIT" and rows[0][1] == "PER-018"

    def test_gpt_success_records_nothing(self, monkeypatch, tmp_path):
        db = self._isolate(monkeypatch, tmp_path)
        monkeypatch.setattr(builder, "check_caption_safety", lambda text, **kw: ("SAFE", "STOP"))
        o = _FakeOpenAI(content=json.dumps(_valid_payload()))
        r = builder.generate_carousel_content(self._topic(), "REACH", "HOOK_IMPACT", client=_client(o, _FakeAnthropic()),
                                              throttle_fn=lambda: None, diag_account="PER-018")
        assert r.success is True
        assert (not db.exists()) or _rows(db) == []

    def test_gpt_failure_claude_success_records_nothing(self, monkeypatch, tmp_path):
        db = self._isolate(monkeypatch, tmp_path)
        monkeypatch.setattr(builder, "check_caption_safety", lambda text, **kw: ("SAFE", "STOP"))
        o = _FakeOpenAI(exc=_openai_credit_error())
        a = _FakeAnthropic()
        a.messages = SimpleNamespace(create=lambda **kw: SimpleNamespace(
            content=[SimpleNamespace(text=json.dumps(_valid_payload()))],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1), stop_reason="end_turn"))
        r = builder.generate_carousel_content(self._topic(), "REACH", "HOOK_IMPACT", client=_client(o, a),
                                              throttle_fn=lambda: None, diag_account="PER-018")
        assert r.success is True
        assert (not db.exists()) or _rows(db) == []

    def test_gemini_classification_unchanged(self):
        class _G(Exception):
            code = 429
            details = {"error": {"details": [{"@type": "x.QuotaFailure", "violations": [
                {"quotaMetric": "generate_content_requests", "quotaValue": "0",
                 "quotaDimensions": {"location": "asia-east1"}}]}]}}
        f = diag.extract_fields(_G())
        assert diag.classify(f) == diag.GEMINI_QUOTA_ZERO
        assert diag.classify({"http_code": 503}) == diag.GEMINI_TRANSIENT
        assert diag.classify({"http_code": 401}) == diag.GEMINI_AUTH


class TestWorkersAiProvider:
    def test_workers_ai_neurons_exhausted_recorded_as_credit(self, tmp_path):
        db = tmp_path / "e.db"
        exc = TextAIError("TEXT_AI_ALL_PROVIDERS_FAILED", providers=[
            _attempt(provider="workers_ai", status=429, code="credit_exhausted", tin=1700, tout=0),
            _attempt("claude", None, "TEXT_AI_NO_CLAUDE_KEY", etype="TextAIError")])
        got = diag.record_gemini_failure(exc, account="PER-018", db_path=db, notify_async=False)
        assert got == diag.TEXT_AI_CREDIT
        rows = _rows(db)
        assert len(rows) == 1 and "workers_ai:" in rows[0][6] and rows[0][3] == "P1"
