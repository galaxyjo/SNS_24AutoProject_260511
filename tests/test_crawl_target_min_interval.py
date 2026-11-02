"""261103 — Crawl_Target별 최소 크롤 간격(CRAWL_TARGET_MIN_INTERVAL_HOURS, 기본 OFF) Target Test.

AdsPower Open(무료 20회/일)을 아끼려고 같은 (게시 계정, URL) 대상을 간격 안에서는 다시 크롤하지 않는다.
상태는 SQLite 행 단위 UPSERT(프로세스 간 동시 기록이 서로를 덮지 않는다). 실제 Airtable·Facebook·AdsPower 호출 없음.
상태 DB는 tmp로 바꾼다.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from modules.common import account_manager as am
from modules.sns import facebook_crawler as fc

ACCOUNTS = {
    "IDN-000041": {"account_code": "IDN-000041", "category": ""},
    "IDN-000048": {"account_code": "IDN-000048", "category": "A_BEAUTY"},
    "IDN-000007": {"account_code": "IDN-000007", "category": "A_BEAUTY"},
}


def _t(tid, code="IDN-000041", url=None):
    return {"target_url": url or f"https://www.facebook.com/groups/{tid}", "target_id": tid,
            "publish_account_code": code, "collection_purpose": "production", "max_posts": 20}


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(fc, "_CRAWL_LAST_RUN_PATH", tmp_path / "crawl_last_run.db")
    monkeypatch.delenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", raising=False)
    monkeypatch.setenv("CRAWL_RIGHTS_REQUIRED_ACCOUNTS", "")
    monkeypatch.setattr(fc, "_validate_publish_context",
                        lambda code, dc, cid="": dict(ACCOUNTS[code]))
    fc.logger.propagate = True


def _route(targets):
    return fc._route_crawl_targets(targets, 20, "production", "")


def _state(tmp_path):
    """상태 DB의 {route_key: last_run}. DB 파일이 없으면 None."""
    p = tmp_path / "crawl_last_run.db"
    if not p.exists():
        return None
    conn = sqlite3.connect(p)
    try:
        return dict(conn.execute("select route_key, last_run from crawl_last_run").fetchall())
    finally:
        conn.close()


def _seed(tmp_path, rows):
    conn = sqlite3.connect(tmp_path / "crawl_last_run.db")
    conn.execute("CREATE TABLE IF NOT EXISTS crawl_last_run (route_key TEXT PRIMARY KEY, last_run TEXT NOT NULL)")
    conn.executemany("INSERT OR REPLACE INTO crawl_last_run VALUES (?, ?)", rows)
    conn.commit()
    conn.close()


# ── 파싱 ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,expected", [(None, 0.0), ("", 0.0), ("abc", 0.0), ("0", 0.0), ("-3", 0.0),
                                          ("24", 24.0), ("0.5", 0.5)])
def test_interval_parsing(monkeypatch, raw, expected):
    if raw is not None:
        monkeypatch.setenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", raw)
    assert fc._min_interval_hours() == expected


# ── OFF(기본) = 기존 동작, 상태 DB도 만들지 않는다 ────────────────────────────────
def test_off_by_default_routes_everything_and_creates_no_state(tmp_path):
    targets = [_t("A1"), _t("A2", code="IDN-000048")]
    assert len(_route(targets)) == 2
    fc._mark_crawled("IDN-000041", targets[0]["target_url"])         # OFF에서는 기록 자체가 없다
    assert _state(tmp_path) is None
    assert len(_route(targets)) == 2
    assert _state(tmp_path) is None


# ── ON ──────────────────────────────────────────────────────────────────────
def test_recently_crawled_target_is_skipped_others_stay(monkeypatch, tmp_path):
    monkeypatch.setenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", "24")
    a, b = _t("A1", code="IDN-000048"), _t("A2", code="IDN-000007")
    fc._mark_crawled("IDN-000048", a["target_url"])
    routes = _route([a, b])
    assert [code for _, _, code in routes] == ["IDN-000007"]


def test_same_url_for_other_account_is_independent(monkeypatch):
    monkeypatch.setenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", "24")
    url = "https://www.facebook.com/groups/shared"
    fc._mark_crawled("IDN-000048", url)
    routes = _route([_t("X", code="IDN-000048", url=url), _t("Y", code="IDN-000007", url=url)])
    assert [code for _, _, code in routes] == ["IDN-000007"]


def test_target_returns_after_interval_passes(monkeypatch, tmp_path):
    monkeypatch.setenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", "24")
    t = _t("A1", code="IDN-000048")
    key = f"IDN-000048|{t['target_url']}"
    _seed(tmp_path, [(key, (datetime.now() - timedelta(hours=25)).isoformat(timespec="seconds"))])
    assert len(_route([t])) == 1
    _seed(tmp_path, [(key, (datetime.now() - timedelta(hours=23)).isoformat(timespec="seconds"))])
    assert _route([t]) == []


def test_corrupt_state_db_fails_open_and_logs_error(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", "24")
    (tmp_path / "crawl_last_run.db").write_bytes(b"this is not a sqlite database" * 50)
    with caplog.at_level(logging.ERROR):
        routes = _route([_t("A1")])
    assert len(routes) == 1 and "크롤 간격 상태 읽기 실패" in caplog.text


def test_mark_failure_is_a_warning_not_an_exception(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", "24")
    monkeypatch.setattr(fc, "_CRAWL_LAST_RUN_PATH", tmp_path / "file" / "x" / "state.db")
    (tmp_path / "file").write_text("i am a file, not a dir", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        fc._mark_crawled("IDN-000041", "https://www.facebook.com/groups/A1")
    assert "크롤 간격 기록 실패" in caplog.text


def test_interval_does_not_bypass_rights_gate(monkeypatch):
    """간격 제한은 다른 Fail-closed 규칙을 우회하지 못한다: 사용권 미확인 계정은 간격과 무관하게 건너뛴다."""
    monkeypatch.setenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", "24")
    monkeypatch.setenv("CRAWL_RIGHTS_REQUIRED_ACCOUNTS", "IDN-000048")
    assert _route([_t("A1", code="IDN-000048")]) == []


def test_upsert_updates_existing_row_without_duplicates(monkeypatch, tmp_path):
    monkeypatch.setenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", "24")
    url = "https://www.facebook.com/groups/U1"
    fc._mark_crawled("IDN-000048", url, now=datetime(2026, 11, 1, 9, 0, 0))
    fc._mark_crawled("IDN-000048", url, now=datetime(2026, 11, 2, 9, 0, 0))
    assert _state(tmp_path) == {f"IDN-000048|{url}": "2026-11-02T09:00:00"}


# ── 동시 기록(프로세스 간 직렬화는 SQLite가 보장, 행 단위 UPSERT라 서로 덮지 않음) ──────────────

def test_concurrent_marks_in_threads_lose_no_update(monkeypatch, tmp_path):
    import threading
    monkeypatch.setenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", "24")
    threads = [threading.Thread(target=fc._mark_crawled, args=("IDN-000048", f"https://www.facebook.com/groups/T{i}"))
               for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(_state(tmp_path)) == 8
    assert {p.name for p in tmp_path.iterdir()} == {"crawl_last_run.db"}   # lock·tmp 같은 잔재 파일이 없다


def test_concurrent_marks_across_processes_lose_no_update(monkeypatch, tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    script = (
        "import sys\n"
        f"sys.path.insert(0, r'{root}')\n"
        "from pathlib import Path\n"
        "from modules.sns import facebook_crawler as fc\n"
        "fc._CRAWL_LAST_RUN_PATH = Path(sys.argv[1])\n"
        "for i in range(10):\n"
        "    fc._mark_crawled('IDN-0000' + sys.argv[2], f'https://www.facebook.com/groups/P{sys.argv[2]}_{i}')\n"
    )
    env_ = {**os.environ, "CRAWL_TARGET_MIN_INTERVAL_HOURS": "24", "PYTHONPATH": ""}
    procs = [subprocess.Popen([sys.executable, "-c", script, str(tmp_path / "crawl_last_run.db"), f"{n:02d}"],
                              cwd=str(root), env=env_, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
             for n in range(3)]
    assert [p.wait(timeout=120) for p in procs] == [0, 0, 0]
    assert len(_state(tmp_path)) == 30                  # 3개 프로세스 × 10건, 유실 0
    assert {p.name for p in tmp_path.iterdir()} == {"crawl_last_run.db"}


def test_same_key_concurrent_upserts_do_not_error(monkeypatch, tmp_path):
    import threading
    monkeypatch.setenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", "24")
    url = "https://www.facebook.com/groups/SAME"
    threads = [threading.Thread(target=fc._mark_crawled, args=("IDN-000048", url)) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert list(_state(tmp_path)) == [f"IDN-000048|{url}"]


def test_writer_waits_for_a_held_write_lock_and_neither_update_is_lost(monkeypatch, tmp_path):
    """다른 프로세스(여기서는 별도 연결)가 쓰기 잠금을 잡고 멈춰 있어도, 기록은 기다렸다가 완료되고 기존 행을 덮지 않는다.
    (파일 잠금·stale 회수 없이 SQLite가 직렬화한다 — Codex 3차 지적의 '일시정지 소유자' 경계)"""
    import threading
    import time as _time
    monkeypatch.setenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", "24")
    fc._mark_crawled("IDN-000048", "https://www.facebook.com/groups/OLD")
    holder = sqlite3.connect(tmp_path / "crawl_last_run.db", isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")                                   # 쓰기 잠금을 쥔 채 멈춘 소유자
    done = []
    worker = threading.Thread(target=lambda: (fc._mark_crawled("IDN-000007", "https://www.facebook.com/groups/NEW"),
                                              done.append(1)))
    worker.start()
    _time.sleep(0.4)
    assert not done                                                     # 잠금이 풀릴 때까지 기다린다
    holder.execute("INSERT OR REPLACE INTO crawl_last_run VALUES ('IDN-000041|held-owner', '2026-11-03T00:00:00')")
    holder.execute("COMMIT")
    holder.close()
    worker.join(timeout=20)
    assert done == [1]
    keys = set(_state(tmp_path))
    assert keys == {"IDN-000048|https://www.facebook.com/groups/OLD",
                    "IDN-000007|https://www.facebook.com/groups/NEW", "IDN-000041|held-owner"}   # 세 기록 모두 보존


# ── run_all_accounts 통합 ────────────────────────────────────────────────────
def _acct(targets):
    return SimpleNamespace(name="account1", crawl_targets=targets, crawl_urls=[], adspower_user_id="x",
                           selenium_proxy_options=lambda: {})


def _run_all(monkeypatch, accounts, run_impl):
    monkeypatch.setattr(am, "get_active_accounts", lambda: accounts)
    monkeypatch.setattr(fc, "run", run_impl)
    return fc.run_all_accounts(target_publish_account_code_ref="IDN-000041", data_classification="production")


def test_success_marks_and_second_cycle_skips_open(monkeypatch, tmp_path):
    monkeypatch.setenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", "24")
    opened = []
    targets = [_t("A1", code="IDN-000048"), _t("A2", code="IDN-000007")]

    def _run(url, mp, user, proxy, **kw):
        opened.append(url)
        return []

    _run_all(monkeypatch, [_acct(targets)], _run)
    assert len(opened) == 2 and set(_state(tmp_path)) == {f"IDN-000048|{targets[0]['target_url']}",
                                                         f"IDN-000007|{targets[1]['target_url']}"}
    _run_all(monkeypatch, [_acct(targets)], _run)
    assert len(opened) == 2                                  # 같은 간격 안의 2회차에는 프로필을 열지 않는다


def test_failed_crawl_is_not_marked_so_it_can_retry(monkeypatch, tmp_path):
    monkeypatch.setenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", "24")
    targets = [_t("A1", code="IDN-000048"), _t("A2", code="IDN-000007")]

    def _run(url, mp, user, proxy, **kw):
        if url.endswith("A1"):
            raise RuntimeError("adspower browser/start failed")
        return []

    _run_all(monkeypatch, [_acct(targets)], _run)            # 일부 실패는 PARTIAL(예외 없음)
    assert list(_state(tmp_path)) == [f"IDN-000007|{targets[1]['target_url']}"]


def test_off_run_all_accounts_unchanged_and_no_state(monkeypatch, tmp_path):
    opened = []
    targets = [_t("A1", code="IDN-000048")]

    def _run(url, mp, user, proxy, **kw):
        opened.append(url)
        return []

    _run_all(monkeypatch, [_acct(targets)], _run)
    _run_all(monkeypatch, [_acct(targets)], _run)
    assert len(opened) == 2 and _state(tmp_path) is None     # OFF: 매 사이클 크롤, 상태 DB 없음


def test_legacy_crawl_urls_path_is_not_throttled(monkeypatch, tmp_path):
    monkeypatch.setenv("CRAWL_TARGET_MIN_INTERVAL_HOURS", "24")
    opened = []
    legacy = SimpleNamespace(name="account1", crawl_targets=[], crawl_urls=["https://www.facebook.com/groups/L1"],
                             adspower_user_id="x", selenium_proxy_options=lambda: {})

    def _run(url, mp, user, proxy, **kw):
        opened.append(url)
        return []

    _run_all(monkeypatch, [legacy], _run)
    _run_all(monkeypatch, [legacy], _run)
    assert len(opened) == 2 and _state(tmp_path) is None
