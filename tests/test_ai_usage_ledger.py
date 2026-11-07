"""tests/test_ai_usage_ledger.py — 261107 AI 호출 장부 1단계 Target Test.

실제 AI 호출·네트워크 없음(전부 Fake). 운영 DB(`db/error_events.db`)는 건드리지 않는다 — 모든 테스트는 임시 DB 경로로 격리한다.
"""

import sqlite3
from types import SimpleNamespace

import pytest

import modules.common.ai_usage_ledger as ledger
from modules.sns.caption_generator import TextAIError, TextAIFallbackClient

from tests.test_text_ai_fallback import GOOD, _ApiError, _client, _FakeAnthropic, _FakeOpenAI, _json_config


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    db = tmp_path / "ledger.db"
    monkeypatch.setattr(ledger, "_DB_PATH", db)
    monkeypatch.delenv("AI_USAGE_LEDGER_ENABLED", raising=False)
    return db


def _on(monkeypatch):
    monkeypatch.setenv("AI_USAGE_LEDGER_ENABLED", "true")


def _rows(db):
    if not db.exists():
        return []
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(
            "SELECT account, provider, model, stage, outcome, status, tin, tout FROM ai_calls ORDER BY id").fetchall()
    finally:
        conn.close()


class _GeminiModels:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc, self.calls = resp, exc, []

    def generate_content(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.exc:
            raise self.exc
        return self.resp


class _FakeGenai:
    def __init__(self, resp=None, exc=None):
        self.models = _GeminiModels(resp, exc)
        self.extra = "extra-attr"


# ── 1~3. 기록 함수 ───────────────────────────────────────────────────────────────
class TestRecord:
    def test_stores_only_allowed_fields_and_strips_token_like_text(self, monkeypatch, _isolated_db):
        _on(monkeypatch)
        ledger.record_ai_call(account="IDN-000025", provider="gemini", model="gemini-3.5-flash-lite sk-ABCDEFGHIJKLMNOP",
                              stage="carousel", outcome="ok", status=200, tin=10, tout=20, ms=5)
        cols = [r[1] for r in sqlite3.connect(str(_isolated_db)).execute("PRAGMA table_info(ai_calls)")]
        assert cols == ["id", "ts", "account", "provider", "model", "stage", "outcome", "status", "tin", "tout", "ms"]
        row = _rows(_isolated_db)[0]
        assert row[:5] == ("IDN-000025", "gemini", "gemini-3.5-flash-lite", "carousel", "ok")
        assert "sk-" not in str(row)

    def test_flag_off_writes_nothing_and_creates_no_file(self, _isolated_db):
        ledger.record_ai_call(account="A", provider="gemini", outcome="ok")
        assert not _isolated_db.exists()

    def test_db_failure_never_raises(self, monkeypatch, tmp_path):
        _on(monkeypatch)
        blocker = tmp_path / "afile"
        blocker.write_text("x")
        monkeypatch.setattr(ledger, "_DB_PATH", blocker / "sub" / "x.db")   # 부모가 파일 → 연결 불가
        ledger.record_ai_call(account="A", provider="gemini", outcome="ok")   # 예외 없이 통과해야 한다

    def test_non_int_values_become_null(self, monkeypatch, _isolated_db):
        _on(monkeypatch)
        ledger.record_ai_call(account="A", provider="gemini", outcome="weird", status="429", tin=True, tout=None, ms=1.5)
        assert _rows(_isolated_db)[0][4:] == ("fail", None, None, None)


# ── 4. TextAIFallbackClient ──────────────────────────────────────────────────────
class TestFallbackClientLedger:
    def test_gpt_success_one_ok_row(self, monkeypatch, _isolated_db):
        _on(monkeypatch)
        r = _client(_FakeOpenAI(content=GOOD), _FakeAnthropic(text=GOOD)).models.generate_content(
            model="m", contents="hi", config=_json_config())
        assert r.text == GOOD
        rows = _rows(_isolated_db)
        assert [(x[1], x[4]) for x in rows] == [("gpt", "ok")] and rows[0][0] == "IDN-TEST"

    def test_gpt_fail_then_claude_ok_two_rows(self, monkeypatch, _isolated_db):
        _on(monkeypatch)
        r = _client(_FakeOpenAI(exc=_ApiError(429)), _FakeAnthropic(text=GOOD)).models.generate_content(
            model="m", contents="hi", config=_json_config())
        assert r.text == GOOD
        rows = _rows(_isolated_db)
        assert [(x[1], x[4]) for x in rows] == [("gpt", "fail"), ("claude", "ok")]
        assert rows[0][5] == 429

    def test_both_fail_two_fail_rows_and_error_unchanged(self, monkeypatch, _isolated_db):
        _on(monkeypatch)
        c = _client(_FakeOpenAI(exc=_ApiError(429)), _FakeAnthropic(exc=_ApiError(500)))
        with pytest.raises(TextAIError) as ei:
            c.models.generate_content(model="m", contents="hi", config=_json_config())
        assert str(ei.value).startswith("TEXT_AI_ALL_PROVIDERS_FAILED") or "ALL_PROVIDERS_FAILED" in repr(ei.value)
        assert [(x[1], x[4]) for x in _rows(_isolated_db)] == [("gpt", "fail"), ("claude", "fail")]

    def test_flag_off_same_result_and_no_rows(self, _isolated_db):
        r = _client(_FakeOpenAI(exc=_ApiError(429)), _FakeAnthropic(text=GOOD)).models.generate_content(
            model="m", contents="hi", config=_json_config())
        assert r.text == GOOD
        assert not _isolated_db.exists()

    def test_ledger_exception_does_not_change_result(self, monkeypatch):
        _on(monkeypatch)

        def _boom(**kw):
            raise RuntimeError("ledger down")
        monkeypatch.setattr(ledger, "record_ai_call", _boom)
        r = _client(_FakeOpenAI(content=GOOD), _FakeAnthropic(text=GOOD)).models.generate_content(
            model="m", contents="hi", config=_json_config())
        assert r.text == GOOD


# ── 5. UsageRecordingClient ──────────────────────────────────────────────────────
class TestRecordingClient:
    def test_passthrough_return_args_and_tokens(self, monkeypatch, _isolated_db):
        _on(monkeypatch)
        resp = SimpleNamespace(text="T", usage_metadata=SimpleNamespace(prompt_token_count=11, candidates_token_count=22))
        inner = _FakeGenai(resp=resp)
        c = ledger.UsageRecordingClient(inner, "IDN-000025")
        out = c.models.generate_content(model="gemini-3.5-flash-lite", contents="p", config="cfg")
        assert out is resp
        assert inner.models.calls == [((), {"model": "gemini-3.5-flash-lite", "contents": "p", "config": "cfg"})]
        row = _rows(_isolated_db)[0]
        assert row == ("IDN-000025", "gemini", "gemini-3.5-flash-lite", "", "ok", None, 11, 22)

    def test_exception_propagates_unchanged_and_records_fail(self, monkeypatch, _isolated_db):
        _on(monkeypatch)
        exc = _ApiError(429)
        exc.code = 429
        c = ledger.UsageRecordingClient(_FakeGenai(exc=exc), "IDN-000023")
        with pytest.raises(_ApiError) as ei:
            c.models.generate_content(model="m", contents="p")
        assert ei.value is exc
        row = _rows(_isolated_db)[0]
        assert row[4] == "fail" and row[5] == 429

    def test_missing_usage_metadata_is_null(self, monkeypatch, _isolated_db):
        _on(monkeypatch)
        c = ledger.UsageRecordingClient(_FakeGenai(resp=SimpleNamespace(text="T")), "A")
        c.models.generate_content(model="m", contents="p")
        assert _rows(_isolated_db)[0][6:] == (None, None)

    def test_attribute_delegation_and_not_text_ai_client(self):
        c = ledger.UsageRecordingClient(_FakeGenai(), "A")
        assert c.extra == "extra-attr"
        assert not isinstance(c, TextAIFallbackClient)   # caption_generator·image_text_checker의 isinstance 분기 불변
        with pytest.raises(AttributeError):
            c._nope

    def test_ledger_exception_does_not_change_result(self, monkeypatch):
        _on(monkeypatch)
        monkeypatch.setattr(ledger, "record_ai_call", lambda **kw: (_ for _ in ()).throw(RuntimeError("down")))
        resp = SimpleNamespace(text="T")
        # record_ai_call 자체가 예외를 삼키는 구조이므로, 호출부 래퍼는 예외를 그대로 내보내지 않는지 확인한다.
        c = ledger.UsageRecordingClient(_FakeGenai(resp=resp), "A")
        try:
            assert c.models.generate_content(model="m", contents="p") is resp
        except RuntimeError:
            pytest.fail("기록 실패가 호출 결과를 바꿨다")


# ── 6. wrap_gemini_client / launcher._wrap_text_ai_client ─────────────────────────
class TestWrap:
    def test_flag_off_returns_same_object(self):
        inner = _FakeGenai()
        assert ledger.wrap_gemini_client(inner, "A") is inner
        assert ledger.wrap_gemini_client(None, "A") is None

    def test_flag_on_wraps(self, monkeypatch):
        _on(monkeypatch)
        inner = _FakeGenai()
        w = ledger.wrap_gemini_client(inner, "A")
        assert isinstance(w, ledger.UsageRecordingClient) and w._inner is inner

    def test_launcher_off_identity_and_on_wrapper(self, monkeypatch):
        import launcher.main as lm
        monkeypatch.delenv("TEXT_AI_FALLBACK_DISABLED", raising=False)
        for k in ("IDN_000099_TEXT_AI_PROVIDER", "IDN_000099_OPENAI_API_KEY"):
            monkeypatch.delenv(k, raising=False)
        acct = SimpleNamespace(account_code="IDN-000099", credential_key="IDN_000099")
        inner = _FakeGenai()
        assert lm._wrap_text_ai_client(acct, inner) is inner          # OFF → 기존 동작과 동일 객체
        _on(monkeypatch)
        w = lm._wrap_text_ai_client(acct, inner)                      # ON, 대체 자격증명 없음 → 기록 래퍼
        assert isinstance(w, ledger.UsageRecordingClient)

    def test_launcher_on_with_cloudflare_keeps_fallback_client(self, monkeypatch):
        import launcher.main as lm
        _on(monkeypatch)
        monkeypatch.delenv("TEXT_AI_FALLBACK_DISABLED", raising=False)
        monkeypatch.setenv("IDN_000099_TEXT_AI_PROVIDER", "cloudflare")
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
        acct = SimpleNamespace(account_code="IDN-000099", credential_key="IDN_000099")
        w = lm._wrap_text_ai_client(acct, _FakeGenai())
        assert isinstance(w, TextAIFallbackClient)
        assert isinstance(w._gemini, ledger.UsageRecordingClient)     # 위임용 Gemini도 기록됨


# ── 7. 조회 CLI ──────────────────────────────────────────────────────────────────
class TestSummarize:
    def test_summarize_groups(self, monkeypatch, _isolated_db, capsys):
        _on(monkeypatch)
        for outcome in ("ok", "ok", "fail"):
            ledger.record_ai_call(account="A", provider="gemini", outcome=outcome, tin=1, tout=2)
        rows = ledger.summarize(24, ("account", "outcome"))
        assert {(r[0], r[1]): r[2] for r in rows} == {("A", "ok"): 2, ("A", "fail"): 1}
        assert ledger.main(["--since", "24h"]) == 0
        assert "A | gemini | ok | 2건" in capsys.readouterr().out
        assert ledger.main(["--by", "bogus"]) == 2
