"""261012 — uploading 고착 회수(_record_publish_pending + _job_publish_reconcile).

안전 계약:
  - posted 는 게시 성공 응답에서 그 rid 에 직접 연결된 ig_media_id 가 있을 때만 쓴다.
  - creation_id 만 있는 PUBLISHED 는 시각·캡션 후보를 진단용으로만 남기고 쓰지 않는다.
  - Airtable 현재 상태가 uploading 이 아니거나 계정이 다르면 덮어쓰지 않는다.
Graph·Airtable·Slack 실호출 0건(mock), 재게시(publish_single·POST) 0건, 실제 db/ 접근 0건.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_REAL_LEDGER = Path(__file__).resolve().parents[1] / "db" / "publish_outcome_pending.json"
ACCT = "IDN-000036"
CAP = "오늘의 창업 팁 #startup"


@pytest.fixture(autouse=True)
def _real_db_guard():
    """실제 db/publish_outcome_pending.json 이 테스트로 생기거나 바뀌면 실패시킨다."""
    before = _REAL_LEDGER.read_bytes() if _REAL_LEDGER.exists() else None
    yield
    after = _REAL_LEDGER.read_bytes() if _REAL_LEDGER.exists() else None
    assert after == before, "테스트가 실제 db/publish_outcome_pending.json 에 접근했다"


@pytest.fixture
def m(monkeypatch, tmp_path):
    from launcher import main as _m
    # launcher.main 이 이 fixture 에서 처음 import 되면 conftest 격리보다 늦으므로 직접 격리한다.
    monkeypatch.setattr(_m, "_PUBLISH_PENDING_PATH", tmp_path / "publish_outcome_pending.json")
    assert _m._PUBLISH_PENDING_PATH.resolve() != _REAL_LEDGER.resolve()
    sent = []
    monkeypatch.setattr(_m, "_slack", lambda msg: sent.append(msg))
    monkeypatch.setattr(_m, "publish_single", lambda *a, **k: pytest.fail("재게시 호출 금지"))
    monkeypatch.setattr(_m, "_fetch_post_state", lambda rid: ("uploading", ACCT))
    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: pytest.fail("POST 호출 금지"))
    from modules.common import credential_resolver
    monkeypatch.setattr(credential_resolver, "resolve_credential",
                        lambda key: type("C", (), {"access_token": "fake", "ig_user_id": "IG1"})())
    _m._test_sent = sent
    return _m


class _Repo:
    def __init__(self):
        self.marks = []

    def mark_post_result(self, rid, result):
        self.marks.append((rid, result["status"], result["platform_post_id"]))


@pytest.fixture
def repo(monkeypatch):
    r = _Repo()
    monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: r)
    return r


class _Resp:
    def __init__(self, status, js):
        self.status_code, self._js = status, js

    def json(self):
        return self._js


def _graph(monkeypatch, container=None, media=None, raise_exc=None):
    calls = []

    def _get(url, params=None, timeout=None, headers=None):
        calls.append(url)
        if raise_exc:
            raise raise_exc
        if url.endswith("/media"):
            return media
        return container

    import requests
    monkeypatch.setattr(requests, "get", _get)
    return calls


def _seed(m, rid="rec1", kind="outcome_unknown", age_min=40, **kw):
    m._record_publish_pending(rid, kind, creation_id=kw.get("creation_id", "C1"),
                              ig_media_id=kw.get("ig_media_id", ""), credential_key="AI",
                              api_host="graph.facebook.com", caption=kw.get("caption", CAP),
                              account_code_ref=ACCT)
    data = m._load_publish_pending()
    at = datetime.now() - timedelta(minutes=age_min)
    data[rid]["at"] = at.strftime(m._RECONCILE_TS_FMT)
    m._save_publish_pending(data)
    return at


def _ig_ts(local_dt, delta_sec=0):
    return (local_dt.astimezone(timezone.utc) + timedelta(seconds=delta_sec)).strftime("%Y-%m-%dT%H:%M:%S+0000")


# ── 직접 연결된 media_id 만 posted ──

def test_posted_unrecorded_with_direct_media_id_marks_posted(m, repo, monkeypatch):
    _seed(m, kind="posted_unrecorded", ig_media_id="M9")
    calls = _graph(monkeypatch)
    m._job_publish_reconcile()
    assert repo.marks == [("rec1", "posted", "M9")]
    assert calls == [] and m._load_publish_pending() == {}


def test_published_single_candidate_is_diagnostic_only(m, repo, monkeypatch):
    at = _seed(m)
    _graph(monkeypatch, container=_Resp(200, {"status_code": "PUBLISHED"}),
           media=_Resp(200, {"data": [{"id": "M1", "timestamp": _ig_ts(at, -3), "caption": CAP}]}))
    m._job_publish_reconcile()
    m._job_publish_reconcile()
    assert repo.marks == []
    assert len(m._test_sent) == 1 and "M1" in m._test_sent[0]
    assert "rec1" in m._load_publish_pending()


def test_published_mismatch_candidates_hold(m, repo, monkeypatch):
    at = _seed(m)
    _graph(monkeypatch, container=_Resp(200, {"status_code": "PUBLISHED"}),
           media=_Resp(200, {"data": [{"id": "M1", "timestamp": _ig_ts(at, -3), "caption": "다른 글"}]}))
    m._job_publish_reconcile()
    assert repo.marks == [] and "none" in m._test_sent[0]


# ── 미게시 확인 ──

def test_expired_marks_failed(m, repo, monkeypatch):
    _seed(m)
    _graph(monkeypatch, container=_Resp(200, {"status_code": "EXPIRED"}))
    m._job_publish_reconcile()
    assert repo.marks == [("rec1", "failed", "")]


def test_failed_unrecorded_marks_failed_without_graph(m, repo, monkeypatch):
    _seed(m, kind="failed_unrecorded")
    calls = _graph(monkeypatch)
    m._job_publish_reconcile()
    assert repo.marks == [("rec1", "failed", "")] and calls == []


# ── 상태 충돌 방지 ──

@pytest.mark.parametrize("state", [("posted", ACCT), ("failed", ACCT), ("ready", ACCT), ("uploading", "IDN-000041")])
def test_state_conflict_is_not_overwritten(m, repo, monkeypatch, state):
    _seed(m, kind="posted_unrecorded", ig_media_id="M9")
    monkeypatch.setattr(m, "_fetch_post_state", lambda rid: state)
    m._job_publish_reconcile()
    m._job_publish_reconcile()
    assert repo.marks == []
    assert len(m._test_sent) == 1 and "state_conflict" in m._test_sent[0]
    assert "rec1" in m._load_publish_pending()


def test_state_lookup_failure_holds(m, repo, monkeypatch):
    _seed(m)
    _graph(monkeypatch, container=_Resp(200, {"status_code": "EXPIRED"}))
    monkeypatch.setattr(m, "_fetch_post_state", lambda rid: None)
    m._job_publish_reconcile()
    assert repo.marks == [] and "state_lookup_failed" in m._test_sent[0]


# ── 진행 중·조회 실패·반복 ──

def test_recent_entry_is_not_touched(m, repo, monkeypatch):
    _seed(m, age_min=5)
    calls = _graph(monkeypatch, container=_Resp(200, {"status_code": "EXPIRED"}))
    m._job_publish_reconcile()
    assert repo.marks == [] and calls == []


@pytest.mark.parametrize("container,exc", [
    (_Resp(500, {}), None),
    (None, RuntimeError("network down")),
    (_Resp(200, {"status_code": "IN_PROGRESS"}), None),
    (_Resp(200, {"status_code": "FINISHED"}), None),
])
def test_unknown_or_lookup_failure_holds_with_single_alert(m, repo, monkeypatch, container, exc):
    _seed(m)
    _graph(monkeypatch, container=container, raise_exc=exc)
    m._job_publish_reconcile()
    m._job_publish_reconcile()
    assert repo.marks == [] and len(m._test_sent) == 1


def test_repeat_run_does_not_double_write(m, repo, monkeypatch):
    _seed(m)
    _graph(monkeypatch, container=_Resp(200, {"status_code": "EXPIRED"}))
    m._job_publish_reconcile()
    m._job_publish_reconcile()
    assert repo.marks == [("rec1", "failed", "")]


def test_airtable_failure_keeps_entry_for_retry(m, monkeypatch):
    class _Bad:
        def mark_post_result(self, rid, result):
            raise RuntimeError("airtable down")
    monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: _Bad())
    _seed(m)
    _graph(monkeypatch, container=_Resp(200, {"status_code": "EXPIRED"}))
    m._job_publish_reconcile()
    assert "rec1" in m._load_publish_pending()


def test_empty_ledger_is_noop(m, repo, monkeypatch):
    calls = _graph(monkeypatch)
    m._job_publish_reconcile()
    assert repo.marks == [] and calls == []


def test_ledger_stores_hash_and_account_not_caption_text(m):
    _seed(m)
    e = m._load_publish_pending()["rec1"]
    assert "caption" not in e and len(e["caption_sha"]) == 64 and e["account_code_ref"] == ACCT
    assert "창업" not in m._PUBLISH_PENDING_PATH.read_text(encoding="utf-8")


def test_reconcile_job_registered(m):
    import inspect
    src = inspect.getsource(m._build_scheduler)
    assert "_job_publish_reconcile" in src and 'id="publish_reconcile"' in src
