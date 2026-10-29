"""tests/test_dm_sla_alerts.py — 261029 STEP 2 DM 60초 SLA·장애 자동 알림 Target Test.

범위: burst guard(60초)·UNKNOWN 60분 hold, 발송 지연 SLA 측정/알림, 알림 단일 경로(Slack 실패 시
ERROR 로그+Telegram 대체), 저장소 장애 HOLD 알림, retry dead 감시(기동 이후만), 041 회귀.
전부 mock·임시 SQLite — 실제 Slack·Telegram·Meta·Airtable·운영 db 접속 없음, 운영 성공 증거 아님.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import modules.dm.dm_auto_reply as dm_auto_reply
import modules.dm.dm_receiver as dm_receiver
import modules.dm.dm_retry_dead_monitor as dead_monitor
from modules.comment import comment_event_store as ces

SOURCE = "instagram_dm:IDN-000051"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(ces, "_DB_PATH", tmp_path / "events_test.db")
    monkeypatch.setattr(ces, "_conn", None)
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    dm_auto_reply._TEMPLATE_EN_DEDUP.clear()
    dm_auto_reply._TEMPLATE_EN_HOLD.clear()
    dm_auto_reply._AWAITING_PRODUCT_DEDUP.clear()
    dm_auto_reply._ALERT_LAST.clear()
    yield


@pytest.fixture
def alerts(monkeypatch):
    """Slack send_alert 대체: (title, body, level) 기록, 항상 성공."""
    import services.slack_notifier as sn
    sent = []
    monkeypatch.setattr(sn, "send_alert", lambda title, body="", level="warning": sent.append((title, body, level)) or True)
    return sent


class _Repo:
    def has_recent_auto_reply(self, *a, **k):
        return False

    def get_publish_account(self, code):
        return {"reply_mode": "template_en"} if code == "IDN-000051" else {"reply_mode": ""}

    def get_persona_by_account_code(self, *a, **k):
        return None

    def record_reply_observability(self, *a, **k):
        pass


def _reply(monkeypatch, sender="buyer", text="Hello", account="IDN-000051", mid=None, received_ago=0.0, ok=True):
    dm_auto_reply._repo = _Repo()
    sent = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: sent.append(1) or ok)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)
    kwargs = {}
    if mid:
        token = ces.try_claim(f"instagram_dm:{account}", mid, "dm_webhook")
        kwargs["dm_event"] = (f"instagram_dm:{account}", mid, token)
    dm_auto_reply.handle_price_inquiry(
        "rec", sender, text, datetime.now(timezone.utc) - timedelta(seconds=received_ago),
        account_code_ref=account, **kwargs)
    return sent


# ── burst guard 60초 / UNKNOWN 60분 hold ────────────────────────────────────────

def test_burst_guard_is_seconds_not_minutes(monkeypatch):
    assert dm_auto_reply._TEMPLATE_EN_BURST_SECONDS == 60
    assert len(_reply(monkeypatch, text="first")) == 1
    assert _reply(monkeypatch, text="second right away") == []           # 1분 안 연속 메시지는 1회만
    dm_auto_reply._TEMPLATE_EN_DEDUP[("IDN-000051", "buyer")] -= timedelta(seconds=61)
    assert len(_reply(monkeypatch, text="third after 61s")) == 1           # 정상 신규 메시지는 60분 기다리지 않는다


def test_burst_is_per_account_and_sender(monkeypatch):
    assert len(_reply(monkeypatch, sender="a")) == 1
    assert len(_reply(monkeypatch, sender="b")) == 1


def test_unknown_hold_blocks_for_60_minutes_even_after_burst(monkeypatch):
    dm_auto_reply._hold_template_en_after_unknown("IDN-000051", "buyer")
    assert _reply(monkeypatch) == []
    dm_auto_reply._TEMPLATE_EN_HOLD[("IDN-000051", "buyer")] -= timedelta(minutes=59)
    assert _reply(monkeypatch) == []                                       # 59분: 아직 hold
    dm_auto_reply._TEMPLATE_EN_HOLD[("IDN-000051", "buyer")] -= timedelta(minutes=2)
    assert len(_reply(monkeypatch)) == 1                                   # 61분: 해제


def test_ambiguous_send_failure_sets_unknown_hold(monkeypatch, alerts):
    dm_auto_reply._SEND_TLS.status = None

    def server_error(*a, **k):
        dm_auto_reply._SEND_TLS.status = 503
        return False

    dm_auto_reply._repo = _Repo()
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", server_error)
    token = ces.try_claim(SOURCE, "m-unknown", "dm_webhook")
    dm_auto_reply.handle_price_inquiry("rec", "buyer", "Hello", datetime.now(timezone.utc),
                                       account_code_ref="IDN-000051", dm_event=(SOURCE, "m-unknown", token))
    assert ("IDN-000051", "buyer") in dm_auto_reply._TEMPLATE_EN_HOLD
    assert len(alerts) == 1 and "수동 확인 필요" in alerts[0][1]


# ── SLA 측정·알림 ──────────────────────────────────────────────────────────────

def test_sla_breach_alerts_once_without_pii(monkeypatch, alerts):
    _reply(monkeypatch, sender="buyer-secret-id", text="private message body", mid="abcdef123456", received_ago=75)
    sla = [a for a in alerts if "SLA 초과" in a[0]]
    assert len(sla) == 1
    title, body, _ = sla[0]
    assert "account=IDN-000051" in body and "abcdef***" in body and "수동 확인 불필요" in body
    for secret in ("buyer-secret-id", "private message body", "abcdef123456"):
        assert secret not in title + body


def test_within_sla_sends_no_alert(monkeypatch, alerts, caplog):
    with caplog.at_level(logging.INFO):
        _reply(monkeypatch, mid="fast-1", received_ago=10)
    assert alerts == []
    assert "[DM_SLA] latency_sec=" in caplog.text


def test_flag_off_path_logs_latency_but_never_alerts(monkeypatch, alerts, caplog):
    with caplog.at_level(logging.INFO):
        _reply(monkeypatch, received_ago=120)                              # dm_event 없음(플래그 OFF)
    assert alerts == []
    assert "[DM_SLA]" in caplog.text


def test_late_retry_success_triggers_sla_alert(monkeypatch, alerts):
    token = ces.try_claim(SOURCE, "late-1", "dm_webhook")
    ces._c().execute("UPDATE comment_events SET private_reply_status='STARTED' WHERE source_event_id='late-1'")
    ces._c().commit()
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: True)
    payload = {"sender_igsid": "b", "message": "m", "account_code_ref": "IDN-000051",
               "dm_event": [SOURCE, "late-1", token],
               "received_at": (datetime.now(timezone.utc) - timedelta(seconds=130)).isoformat()}
    dm_auto_reply._retry_send_ig_reply(payload)
    assert any("SLA 초과" in a[0] and "retry" in a[1] for a in alerts)


def test_first_failure_payload_carries_received_at(monkeypatch):
    from modules.common import retry_queue as retry_queue_mod
    queued = []

    class RQ:
        def register(self, *a, **k): pass
        def start(self): pass
        def enqueue(self, t, p, **k): queued.append(p); return 1

    monkeypatch.setattr(retry_queue_mod, "get_retry_queue", lambda: RQ())

    def client_error(*a, **k):
        dm_auto_reply._SEND_TLS.status = 400
        return False

    dm_auto_reply._repo = _Repo()
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", client_error)
    token = ces.try_claim(SOURCE, "rcv-1", "dm_webhook")
    dm_auto_reply.handle_price_inquiry("rec", "b", "Hello", datetime.now(timezone.utc),
                                       account_code_ref="IDN-000051", dm_event=(SOURCE, "rcv-1", token))
    assert "received_at" in queued[0] and datetime.fromisoformat(queued[0]["received_at"])


# ── 알림 단일 경로: Slack 실패 → ERROR 로그 + Telegram 대체 ───────────────────────

def test_slack_failure_logs_error_and_falls_back_to_telegram(monkeypatch, caplog):
    import services.slack_notifier as sn
    monkeypatch.setattr(sn, "send_alert", lambda *a, **k: False)
    sent = []
    monkeypatch.setattr(dm_auto_reply, "_telegram_alert", lambda text: sent.append(text) or True)
    with caplog.at_level(logging.ERROR):
        ok = dm_auto_reply._alert_dm("UNKNOWN 테스트", SOURCE, "abcdef123456", "detail")
    assert ok is True and len(sent) == 1
    assert "DM_ALERT_DELIVERY_FAILED" in caplog.text                       # error.log → 헬스 모니터에 노출되는 레벨
    assert any(r.levelno == logging.ERROR for r in caplog.records)
    assert "abcdef123456" not in sent[0]


def test_both_channels_failing_returns_false_and_still_logs_error(monkeypatch, caplog):
    import services.slack_notifier as sn
    monkeypatch.setattr(sn, "send_alert", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(dm_auto_reply, "_telegram_alert", lambda text: False)
    with caplog.at_level(logging.ERROR):
        assert dm_auto_reply._alert_dm("x", SOURCE, "m", "d") is False
    assert "DM_ALERT_DELIVERY_FAILED" in caplog.text


def test_telegram_fallback_uses_existing_env_and_does_not_leak_exceptions(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    posted = []

    class Resp:
        ok = True

    monkeypatch.setattr(dm_auto_reply.requests, "post", lambda url, **k: posted.append((url, k)) or Resp())
    assert dm_auto_reply._telegram_alert("hello") is True
    assert posted[0][0].endswith("/sendMessage") and posted[0][1]["json"]["chat_id"] == "chat"
    monkeypatch.setattr(dm_auto_reply.requests, "post", lambda *a, **k: (_ for _ in ()).throw(OSError("blocked")))
    assert dm_auto_reply._telegram_alert("hello") is False


def test_throttled_alerts_collapse_within_a_minute(monkeypatch, alerts):
    for _ in range(5):
        dm_auto_reply._alert_dm("저장소 장애 — 응답 HOLD", SOURCE, "m", "d", throttle=True)
    assert len(alerts) == 1
    dm_auto_reply._ALERT_LAST[("저장소 장애 — 응답 HOLD", "IDN-000051")] -= timedelta(seconds=61)
    dm_auto_reply._alert_dm("저장소 장애 — 응답 HOLD", SOURCE, "m", "d", throttle=True)
    assert len(alerts) == 2


# ── 저장소 장애 HOLD 알림 (receiver) ─────────────────────────────────────────────

def test_store_error_and_missing_mid_hold_send_alerts(monkeypatch):
    calls = []
    monkeypatch.setattr(dm_receiver, "_alert_dm", lambda *a, **k: calls.append((a, k)) or True)
    dm_event, hold, dup = dm_receiver._claim_dm_event("IDN-000051", "")
    assert (dm_event, hold, dup) == (None, True, False) and "mid 누락" in calls[0][0][0]
    monkeypatch.setattr(ces, "try_claim", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("locked")))
    dm_event, hold, dup = dm_receiver._claim_dm_event("IDN-000051", "m1")
    assert hold is True and "저장소 장애" in calls[1][0][0]
    assert calls[0][1].get("throttle") is True and calls[1][1].get("throttle") is True


# ── retry dead 감시 (기동 이후 dead만, 1회 알림) ─────────────────────────────────

def _make_retry_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE retry_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, task_type TEXT, payload TEXT,
                    attempts INTEGER DEFAULT 0, max_attempts INTEGER DEFAULT 3, next_retry TEXT,
                    status TEXT, last_error TEXT, created_at TEXT)""")
    for task_type, status, created_at, payload in rows:
        conn.execute("INSERT INTO retry_tasks (task_type, payload, status, created_at) VALUES (?,?,?,?)",
                     (task_type, json.dumps(payload), status, created_at))
    conn.commit()
    conn.close()


def test_dead_monitor_alerts_only_new_dm_dead_tasks_once(tmp_path, monkeypatch):
    db = tmp_path / "retry_test.db"
    old, new = "2026-10-01 00:00:00", "2026-10-29 12:00:00"
    _make_retry_db(db, [
        ("ig_auto_reply", "dead", old, {"account_code_ref": "IDN-000041"}),                                  # 기동 이전 dead — 무시
        ("ig_auto_reply", "dead", new, {"account_code_ref": "IDN-000051", "dm_event": [SOURCE, "dead-mid-1", "t"],
                                         "sender_igsid": "buyer-secret", "message": "secret text"}),         # 알림 대상
        ("dm_record_interaction", "dead", new, {"sender_id": "buyer-secret", "text": "secret text"}),         # 알림 대상(계정 미식별)
        ("lead_update_score", "dead", new, {}),                                                               # DM 응답 아님 — 제외
        ("ig_followup", "pending", new, {"account_code_ref": "IDN-000051"}),                                  # dead 아님
    ])
    monkeypatch.setattr(dead_monitor, "_RETRY_DB_PATH", db)
    sent = []
    monkeypatch.setattr(dead_monitor, "_alert_dm", lambda *a, **k: sent.append((a, k)) or True)

    assert dead_monitor.check_dead_dm_tasks(since="2026-10-15 00:00:00") == 2
    assert len(sent) == 2
    assert dead_monitor.check_dead_dm_tasks(since="2026-10-15 00:00:00") == 0   # 같은 dead는 다시 알리지 않음
    assert len(sent) == 2
    flat = json.dumps([[str(x) for x in a] for a, _ in sent], ensure_ascii=False)
    assert "buyer-secret" not in flat and "secret text" not in flat
    assert "UNRESOLVED" in flat and "IDN-000051" in flat


def test_dead_monitor_retries_alert_when_delivery_fails(tmp_path, monkeypatch):
    db = tmp_path / "retry_test.db"
    _make_retry_db(db, [("ig_followup", "dead", "2026-10-29 12:00:00", {"account_code_ref": "IDN-000051"})])
    monkeypatch.setattr(dead_monitor, "_RETRY_DB_PATH", db)
    results = iter([False, True])
    monkeypatch.setattr(dead_monitor, "_alert_dm", lambda *a, **k: next(results))
    assert dead_monitor.check_dead_dm_tasks(since="2026-10-01 00:00:00") == 0   # 전달 실패 → 다음 주기 재시도
    assert dead_monitor.check_dead_dm_tasks(since="2026-10-01 00:00:00") == 1
    assert dead_monitor.check_dead_dm_tasks(since="2026-10-01 00:00:00") == 0


def test_dead_monitor_default_cutoff_is_process_start_and_db_is_read_only(tmp_path, monkeypatch):
    db = tmp_path / "retry_test.db"
    _make_retry_db(db, [("ig_auto_reply", "dead", "2000-01-01 00:00:00", {})])
    monkeypatch.setattr(dead_monitor, "_RETRY_DB_PATH", db)
    monkeypatch.setattr(dead_monitor, "_alert_dm", lambda *a, **k: (_ for _ in ()).throw(AssertionError("과거 dead 알림 금지")))
    assert dead_monitor.check_dead_dm_tasks() == 0                              # 기본 cutoff = 모듈 로드 시각
    before = db.stat().st_mtime_ns
    dead_monitor.check_dead_dm_tasks()
    assert db.stat().st_mtime_ns == before                                     # 읽기 전용 조회


def test_dead_monitor_missing_db_is_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(dead_monitor, "_RETRY_DB_PATH", tmp_path / "nope.db")
    assert dead_monitor.check_dead_dm_tasks() == 0


# ── 041 회귀 ────────────────────────────────────────────────────────────────────

def test_041_price_inquiry_unchanged_and_never_uses_template_en_guards(monkeypatch, alerts):
    sent = []
    dm_auto_reply._repo = _Repo()
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda sid, msg, ref="": sent.append(msg) or True)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)
    for i in range(2):                                                          # 연속 가격 문의도 burst guard를 타지 않음
        dm_auto_reply._AWAITING_PRODUCT_DEDUP.clear()
        dm_auto_reply.handle_price_inquiry("rec", "kr-buyer", f"가격 문의드립니다 {i}", datetime.now(timezone.utc),
                                           account_code_ref="IDN-000041")
    assert sent == [dm_auto_reply.PRODUCT_CONFIRM_TEMPLATE] * 2
    assert dm_auto_reply._TEMPLATE_EN_DEDUP == {} and alerts == []
