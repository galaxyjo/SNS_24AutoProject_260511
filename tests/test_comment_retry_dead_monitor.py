"""tests/test_comment_retry_dead_monitor.py — dead task 감지/알림/event_store 동기화."""

import json
import sqlite3

import pytest

from modules.comment import comment_event_store as ces
from modules.comment import comment_retry_dead_monitor as mon


@pytest.fixture(autouse=True)
def _isolated_dbs(tmp_path, monkeypatch):
    events_db = tmp_path / "comment_events_test.db"
    retry_db = tmp_path / "retry_queue_test.db"
    monkeypatch.setattr(ces, "_DB_PATH", events_db)
    monkeypatch.setattr(ces, "_conn", None)
    monkeypatch.setattr(mon, "_RETRY_DB_PATH", retry_db)

    conn = sqlite3.connect(retry_db)
    conn.execute("""
        CREATE TABLE retry_tasks (
            id INTEGER PRIMARY KEY, task_type TEXT, payload TEXT,
            attempts INTEGER, max_attempts INTEGER, next_retry TEXT,
            status TEXT, last_error TEXT
        )
    """)
    conn.commit()
    conn.close()
    yield retry_db


def _insert_dead_task(db_path, task_id, task_type="comment_airtable_record"):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO retry_tasks (id, task_type, payload, attempts, max_attempts, next_retry, status, last_error) "
        "VALUES (?, ?, ?, 3, 3, datetime('now'), 'dead', 'boom')",
        (task_id, task_type, json.dumps({"comment_id": f"c{task_id}"})),
    )
    conn.commit()
    conn.close()


class TestDeadTaskDetection:
    def test_no_dead_tasks_returns_zero(self):
        assert mon.check_dead_comment_tasks() == 0

    def test_ignores_other_task_types(self, _isolated_dbs):
        _insert_dead_task(_isolated_dbs, 1, task_type="ig_auto_reply")
        assert mon._fetch_dead_tasks() == []

    def test_syncs_event_store_status_unconditionally(self, _isolated_dbs, monkeypatch):
        """Slack 미설정이라 알림은 실패해도, DEAD 반영 자체는 무조건 먼저 일어나야 한다."""
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        token = ces.try_claim("instagram_comment", "c1", "webhook")
        ces.mark_airtable_retry_pending("instagram_comment", "c1", token, 1)
        _insert_dead_task(_isolated_dbs, 1)

        mon.check_dead_comment_tasks()

        status = ces.get_status("instagram_comment", "c1")
        assert status["status"] == "DEAD"

    def test_alert_retried_on_next_run_if_slack_unset(self, _isolated_dbs, monkeypatch):
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        _insert_dead_task(_isolated_dbs, 1)

        n1 = mon.check_dead_comment_tasks()
        n2 = mon.check_dead_comment_tasks()
        assert n1 == 0 and n2 == 0, "Slack 미설정(전송 실패)이면 SENT로 기록되면 안 되고 계속 재시도 대상"

    def test_alert_sent_once_when_slack_succeeds(self, _isolated_dbs, monkeypatch):
        monkeypatch.setattr(
            "services.slack_notifier.send_alert",
            lambda title, body, level: True,
        )
        _insert_dead_task(_isolated_dbs, 1)

        n1 = mon.check_dead_comment_tasks()
        n2 = mon.check_dead_comment_tasks()
        assert n1 == 1, "1차 실행에서 알림 1건 발송돼야 함"
        assert n2 == 0, "이미 SENT된 건 재알림하면 안 됨"
