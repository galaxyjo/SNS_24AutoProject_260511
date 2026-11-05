"""261105 Gemini 진단 1단계 — 필드 추출·분류·원장 기록·알림·마스킹·비전파. 네트워크·운영 DB 없음(tmp DB)."""

import logging
import sqlite3

import pytest
from google.genai import errors as genai_errors

import modules.common.gemini_failure_diag as diag
import modules.sns.carousel_content_builder as builder
from modules.sns.source_selector import SourceTopic

_SECRET = "AIzaSyFAKEFAKEFAKEFAKEFAKEFAKE12345"


def _err(code, limit="0", location="asia-east1"):
    details = [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{
            "quotaMetric": "generativelanguage.googleapis.com/generate_content_requests",
            "quotaId": "GenerateContentRequestsPerMinutePerProjectPerRegion",
            "quotaDimensions": {"location": location, "model": "m"}, "quotaValue": limit}]},
        {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "metadata": {"consumer": "projects/123"}},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "5s"},
    ]
    return genai_errors.APIError(code, {"error": {"code": code, "message": "boom " + _SECRET, "details": details}})


def _rows(db):
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute("SELECT source, account, error_class, severity, http, detail_head FROM events").fetchall()
    finally:
        conn.close()


def test_extract_and_classify_quota_zero_vs_rate():
    f = diag.extract_fields(_err(429, "0"))
    assert f["quota_location"] == "asia-east1" and f["quota_limit_value"] == "0" and f["consumer"] == "projects/123"
    assert f["retry_delay"] == "5s" and diag.classify(f) == diag.GEMINI_QUOTA_ZERO
    assert diag.classify(diag.extract_fields(_err(429, "10"))) == diag.GEMINI_RATE
    assert diag.classify({"http_code": 403}) == diag.GEMINI_AUTH
    assert diag.classify({"http_code": 503}) == diag.GEMINI_TRANSIENT
    assert diag.classify({"http_code": 400}) is None and diag.classify({"http_code": None}) is None


def test_zero_value_variants_and_other_quota_items():
    """Codex 261106: '0.0' 도 한도 0, 요청 한도가 아닌 항목의 0 은 일반 rate."""
    assert diag.classify(diag.extract_fields(_err(429, "0.0"))) == diag.GEMINI_QUOTA_ZERO
    f = diag.extract_fields(_err(429, "0"))
    f["quota_id"], f["quota_metric"] = "TokensPerDay", "generativelanguage.googleapis.com/tokens"
    assert diag.classify(f) == diag.GEMINI_RATE
    assert diag.classify({"http_code": 429, "quota_limit_value": "abc", "quota_id": "RequestsPerMinute"}) == diag.GEMINI_RATE


def test_403_reason_is_extracted():
    exc = genai_errors.APIError(403, {"error": {"code": 403, "details": [
        {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "CONSUMER_SUSPENDED", "metadata": {}}]}})
    f = diag.extract_fields(exc)
    assert f["reason"] == "CONSUMER_SUSPENDED" and diag.classify(f) == diag.GEMINI_AUTH


def test_missing_fields_do_not_crash():
    f = diag.extract_fields(RuntimeError("x"))
    assert f["http_code"] is None and diag.classify(f) is None
    assert diag.extract_fields(genai_errors.APIError(429, {"error": {"code": 429}}))["quota_limit_value"] == ""


def test_final_failure_recorded_once_alerted_once_per_day(tmp_path):
    db, sent = tmp_path / "e.db", []
    for _ in range(2):
        res = diag.record_gemini_failure(_err(429, "0"), account="PER-018", model="m", attempt=4, final=True,
                                         notify=sent.append, db_path=db, notify_async=False)
        assert res == diag.GEMINI_QUOTA_ZERO
    rows = _rows(db)
    assert len(rows) == 2 and rows[0][:5] == ("gemini", "PER-018", "GEMINI_QUOTA_ZERO", "P1", 429)
    assert len(sent) == 1 and "asia-east1" in sent[0] and _SECRET not in sent[0]
    assert "asia-east1" in rows[0][5] and _SECRET not in rows[0][5]


def test_non_final_attempt_logs_but_does_not_write(tmp_path, caplog):
    db = tmp_path / "e.db"
    diag.logger.propagate = True
    with caplog.at_level(logging.DEBUG, logger=diag.logger.name):
        diag.record_gemini_failure(_err(429, "0"), account="PER-018", attempt=1, final=False, db_path=db)
    msg = [r.getMessage() for r in caplog.records if "[GeminiDiag]" in r.getMessage()][0]
    assert "quota_location=asia-east1" in msg and "quota_limit_value=0" in msg and "acct=PER-018" in msg
    assert _SECRET not in msg and not db.exists()


def test_rate_limit_is_recorded_without_alert(tmp_path):
    sent = []
    diag.record_gemini_failure(_err(429, "10"), account="PER-025", notify=sent.append, db_path=tmp_path / "e.db",
                               notify_async=False)
    assert sent == [] and _rows(tmp_path / "e.db")[0][2:4] == ("GEMINI_RATE", "P3")


def test_failures_never_propagate(tmp_path):
    bad_db = tmp_path  # 디렉터리를 DB 경로로 → sqlite 오류
    assert diag.record_gemini_failure(_err(429, "0"), account="A", db_path=bad_db) is None

    def boom(_msg):
        raise RuntimeError("slack down")
    assert diag.record_gemini_failure(_err(403), account="A", notify=boom, db_path=tmp_path / "ok.db",
                                      notify_async=False) == diag.GEMINI_AUTH


class _Models:
    def __init__(self, excs):
        self.excs, self.calls = list(excs), 0

    def generate_content(self, model, contents, config):
        self.calls += 1
        raise self.excs.pop(0)


class _Client:
    def __init__(self, m):
        self.models = m


def _topic():
    return SourceTopic(topic_id="3.1", title="T", status="VERIFIED FACT", source_url="https://example.com/s",
                       core_message="이 도구는 하루 3건 자동 게시를 지원한다.", prohibited_expression="")


@pytest.mark.parametrize("account,expect_calls", [("PER-018", 1), ("", 0)])
def test_builder_hook_only_with_account_and_retry_unchanged(monkeypatch, account, expect_calls):
    calls = []
    monkeypatch.setattr(builder, "record_gemini_failure_default", lambda exc, **kw: calls.append(kw))
    monkeypatch.setattr(builder, "_throttle", lambda: None)
    monkeypatch.setattr(builder.time, "sleep", lambda s: None)
    n = builder._MAX_ATTEMPTS
    models = _Models([_err(429, "0")] * n)
    monkeypatch.setattr(builder, "_get_client", lambda: _Client(models))
    result = builder.generate_carousel_content(_topic(), "REACH", "HOOK_IMPACT", diag_account=account)
    assert result.error_code == "GENERATION_FAILED" and models.calls == n          # 재시도·반환 불변
    assert len(calls) == expect_calls * n
    if calls:
        assert [c["final"] for c in calls] == [False] * (n - 1) + [True] and calls[0]["account"] == "PER-018"
