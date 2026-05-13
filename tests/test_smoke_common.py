"""
tests/test_smoke_common.py — 공통 유틸리티 smoke tests

외부 서비스(Airtable, Instagram, Selenium) 없이 실행 가능.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import modules.common.retry_queue as rq_mod
import modules.common.health_monitor as hm_mod


# ── logger ────────────────────────────────────────────────────────────────────

def test_get_logger_returns_logger():
    from modules.common.logger import get_logger
    logger = get_logger("test.smoke")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test.smoke"


def test_get_logger_same_instance():
    from modules.common.logger import get_logger
    assert get_logger("mod_a") is get_logger("mod_a")


# ── retry_queue ───────────────────────────────────────────────────────────────

def test_retry_queue_enqueue(tmp_path, monkeypatch):
    monkeypatch.setattr(rq_mod, "_DB_PATH", tmp_path / "rq.db")
    from modules.common.retry_queue import RetryQueue
    rq = RetryQueue()
    tid = rq.enqueue("upload", {"record_id": "rec123"})
    assert isinstance(tid, int) and tid >= 1


def test_retry_queue_stats_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(rq_mod, "_DB_PATH", tmp_path / "rq2.db")
    from modules.common.retry_queue import RetryQueue
    rq = RetryQueue()
    rq.enqueue("upload", {"a": 1})
    rq.enqueue("upload", {"b": 2})
    stats = rq.stats()
    assert stats.get("pending", 0) == 2


def test_retry_queue_handler_success(tmp_path, monkeypatch):
    monkeypatch.setattr(rq_mod, "_DB_PATH", tmp_path / "rq3.db")
    from modules.common.retry_queue import RetryQueue
    rq = RetryQueue()
    called = []
    rq.register("task_x", lambda payload: called.append(payload["v"]))
    rq.enqueue("task_x", {"v": 42})
    rq._process_due()
    assert called == [42]
    assert rq.stats().get("done", 0) == 1


def test_retry_queue_handler_failure_marks_dead(tmp_path, monkeypatch):
    monkeypatch.setattr(rq_mod, "_DB_PATH", tmp_path / "rq4.db")
    from modules.common.retry_queue import RetryQueue
    rq = RetryQueue()
    rq.register("bad_task", lambda p: (_ for _ in ()).throw(RuntimeError("fail")))
    rq.enqueue("bad_task", {}, max_attempts=1)
    rq._process_due()
    assert rq.stats().get("dead", 0) == 1


# ── account_manager ───────────────────────────────────────────────────────────

def test_account_selenium_proxy_options_disabled():
    from modules.common.account_manager import Account
    acct = Account(
        name="test", active=True, adspower_user_id="x",
        ig_user_id="1", ig_access_token="tok",
        fb_page_id="2", airtable_base_id="app",
        proxy={"enabled": False, "host": "proxy.example.com", "port": 8080},
    )
    assert acct.selenium_proxy_options() == {}


def test_account_selenium_proxy_options_enabled():
    from modules.common.account_manager import Account
    acct = Account(
        name="test", active=True, adspower_user_id="x",
        ig_user_id="1", ig_access_token="tok",
        fb_page_id="2", airtable_base_id="app",
        proxy={"enabled": True, "scheme": "http", "host": "p.example.com", "port": 3128},
    )
    opts = acct.selenium_proxy_options()
    assert opts["proxy_server"] == "http://p.example.com:3128"


def test_account_as_env_keys():
    from modules.common.account_manager import Account
    acct = Account(
        name="a", active=True, adspower_user_id="u",
        ig_user_id="ig1", ig_access_token="tok",
        fb_page_id="fb1", airtable_base_id="appXXX",
    )
    env = acct.as_env()
    assert "INSTA_ACCESS_TOKEN" in env
    assert "AIRTABLE_BASE_ID" in env
    assert env["INSTA_IG_USER_ID"] == "ig1"


# ── health_monitor._check_errors ─────────────────────────────────────────────

def test_check_errors_no_file(monkeypatch, tmp_path):
    monkeypatch.setattr(hm_mod, "_ERROR_LOG", tmp_path / "nonexistent.log")
    result = hm_mod._check_errors()
    assert result == {"last_1h": 0, "recent": []}


def test_check_errors_counts_recent(monkeypatch, tmp_path):
    log_file = tmp_path / "error.log"
    now = datetime.now()
    recent = (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    old    = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    log_file.write_text(
        f"{old} [ERROR] old error\n"
        f"{recent} [ERROR] recent error\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(hm_mod, "_ERROR_LOG", log_file)
    result = hm_mod._check_errors(window_minutes=60)
    assert result["last_1h"] == 1
    assert "recent error" in result["recent"][0]
