"""tests/test_dm_event_dedup.py — 261029 STEP 2 DM 영속 중복 방지(comment_event_store 재사용).

source=instagram_dm:{account_code}, source_event_id=Meta mid. DM_EVENT_DEDUP_ENABLED 기본 false.
전부 mock/임시 SQLite — 실제 Airtable·Meta·운영 db 접근 없음, 운영 성공 증거 아님.
"""

import hashlib
import hmac
import json
import logging
import threading
from datetime import datetime, timezone

import pytest

import modules.dm.dm_auto_reply as dm_auto_reply
import modules.dm.dm_receiver as dm_receiver
from modules.comment import comment_event_store as ces

SECRET = "test-dedup-secret"
RECIPIENT_051 = "17841404481418678"
RECIPIENT_041 = "17841476202821375"


def _fail_with(status):
    """send_ig_reply mock: 지정한 HTTP 상태로 실패(False)를 흉내 낸다. 0=요청을 보내지 않음."""
    def _send(*a, **k):
        dm_auto_reply._SEND_TLS.status = status
        return False
    return _send


@pytest.fixture(autouse=True)
def _no_real_slack(monkeypatch):
    """테스트가 실제 Slack Webhook으로 나가지 않도록 .env에서 불러온 URL을 비운다(알림 자동 생략)."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")   # Telegram 대체 알림도 실제로 나가지 않게 한다


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(ces, "_DB_PATH", tmp_path / "events_test.db")
    monkeypatch.setattr(ces, "_conn", None)
    dm_auto_reply._TEMPLATE_EN_DEDUP.clear()
    dm_auto_reply._TEMPLATE_EN_HOLD.clear()   # UNKNOWN hold가 테스트 간에 새지 않게 초기화
    dm_auto_reply._ALERT_LAST.clear()
    dm_auto_reply._AWAITING_PRODUCT_DEDUP.clear()
    yield


@pytest.fixture
def client(monkeypatch):
    dm_receiver.app.config["TESTING"] = True
    monkeypatch.setattr(dm_receiver, "WEBHOOK_APP_SECRET", SECRET)
    return dm_receiver.app.test_client()


def _post(client, recipient, mid="mid-1", text="Hello", sender="buyer1", with_mid=True):
    message = {"text": text}
    if with_mid:
        message["mid"] = mid
    payload = {"object": "instagram", "entry": [{"messaging": [
        {"sender": {"id": sender}, "recipient": {"id": recipient}, "message": message}]}]}
    body = json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/webhook", data=body, content_type="application/json",
                       headers={"X-Hub-Signature-256": sig})


class _Spies:
    def __init__(self, monkeypatch, enabled):
        self.saved, self.alerts, self.handled = [], [], []
        monkeypatch.setattr(dm_receiver, "DM_EVENT_DEDUP_ENABLED", enabled)
        monkeypatch.setattr(dm_receiver, "DM_ACCOUNT_ROUTING_ENABLED", True)
        mapping = {RECIPIENT_051: "IDN-000051", RECIPIENT_041: "IDN-000041"}
        monkeypatch.setattr(
            dm_receiver._repo, "get_publish_account_by_ig_user_id",
            lambda ig: {"account_code": mapping[ig], "api_provider": "x", "ig_user_id": ig,
                        "credential_key": "x"} if ig in mapping else None)
        monkeypatch.setattr(dm_receiver, "record_interaction",
                            lambda *a, **k: self.saved.append((a, k)) or "rec1")
        monkeypatch.setattr(dm_receiver, "send_telegram", lambda *a, **k: self.alerts.append(a))
        monkeypatch.setattr(dm_receiver, "is_repeat_inquiry", lambda *a, **k: False)
        monkeypatch.setattr(dm_receiver, "detect_order", lambda *a, **k: False)
        monkeypatch.setattr(dm_receiver, "update_lead_score", lambda *a, **k: None)
        monkeypatch.setattr(dm_receiver, "handle_price_inquiry",
                            lambda *a, **k: self.handled.append((a, k)))


# ── 플래그 OFF: 기존 동작 불변 ─────────────────────────────────────────────────

def test_flag_off_does_not_touch_store_and_logs_mid_presence_only(client, monkeypatch, caplog):
    spies = _Spies(monkeypatch, enabled=False)
    monkeypatch.setattr(ces, "try_claim", lambda *a, **k: (_ for _ in ()).throw(AssertionError("store 호출 금지")))
    with caplog.at_level(logging.INFO):
        _post(client, RECIPIENT_051, mid="secret-mid-value")
        _post(client, RECIPIENT_051, mid="secret-mid-value")   # 같은 mid도 플래그 OFF면 둘 다 처리
    assert len(spies.saved) == 2 and len(spies.handled) == 2
    assert "mid_present=True" in caplog.text
    assert "secret-mid-value" not in caplog.text, "mid 값은 로그에 남기지 않는다"
    assert all("dm_event" not in k for _, k in spies.handled)


def test_flag_off_logs_mid_absent(client, monkeypatch, caplog):
    _Spies(monkeypatch, enabled=False)
    with caplog.at_level(logging.INFO):
        _post(client, RECIPIENT_051, with_mid=False)
    assert "mid_present=False" in caplog.text


# ── 플래그 ON: mid 있을 때만 차단 ──────────────────────────────────────────────

def test_same_account_same_mid_is_processed_once(client, monkeypatch):
    spies = _Spies(monkeypatch, enabled=True)
    _post(client, RECIPIENT_051, mid="m1")
    _post(client, RECIPIENT_051, mid="m1")   # Meta 재전송
    assert len(spies.saved) == 1 and len(spies.alerts) == 1 and len(spies.handled) == 1
    assert spies.handled[0][1]["dm_event"][0] == "instagram_dm:IDN-000051"


def test_different_account_same_mid_is_independent(client, monkeypatch):
    spies = _Spies(monkeypatch, enabled=True)
    _post(client, RECIPIENT_051, mid="shared")
    _post(client, RECIPIENT_041, mid="shared")
    assert len(spies.saved) == 2 and len(spies.handled) == 2


def test_dedup_survives_restart_new_connection(client, monkeypatch):
    spies = _Spies(monkeypatch, enabled=True)
    _post(client, RECIPIENT_051, mid="persist")
    monkeypatch.setattr(ces, "_conn", None)   # 프로세스 재시작 시뮬레이션: 새 연결, 같은 DB 파일
    _post(client, RECIPIENT_051, mid="persist")
    assert len(spies.saved) == 1 and len(spies.handled) == 1


def test_concurrent_claims_only_one_wins():
    results, lock = [], threading.Lock()

    def worker():
        out = dm_receiver._claim_dm_event("IDN-000051", "race-mid")
        with lock:
            results.append(out)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    winners = [r for r in results if r[0] is not None]
    duplicates = [r for r in results if r[2] is True]
    assert len(winners) == 1 and len(duplicates) == 7


def test_missing_mid_holds_reply_but_keeps_save_and_alert(client, monkeypatch, caplog):
    spies = _Spies(monkeypatch, enabled=True)
    with caplog.at_level(logging.WARNING):
        _post(client, RECIPIENT_051, with_mid=False)
    assert len(spies.saved) == 1 and len(spies.alerts) == 1
    assert spies.handled == []
    assert "DM_MID_MISSING_REPLY_HOLD" in caplog.text


def test_store_error_holds_reply_but_keeps_save_and_alert(client, monkeypatch, caplog):
    spies = _Spies(monkeypatch, enabled=True)
    monkeypatch.setattr(ces, "try_claim", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db locked")))
    with caplog.at_level(logging.ERROR):
        _post(client, RECIPIENT_051, mid="m-err")
    assert len(spies.saved) == 1 and len(spies.alerts) == 1
    assert spies.handled == []
    assert "DM_EVENT_STORE_ERROR" in caplog.text


def test_event_marked_completed_after_record_so_stale_reclaim_cannot_reprocess(client, monkeypatch):
    _Spies(monkeypatch, enabled=True)
    _post(client, RECIPIENT_051, mid="done-1")
    row = ces.get_status("instagram_dm:IDN-000051", "done-1")
    assert row["status"] == "COMPLETED" and row["airtable_status"] == "DONE"


# ── 처리기(handle_price_inquiry) 레벨: 발송 상태 기록 ──────────────────────────

class _Repo:
    def __init__(self):
        self.obs = []

    def has_recent_auto_reply(self, *a, **k):
        return False

    def get_publish_account(self, code):
        return {"reply_mode": "template_en"} if code == "IDN-000051" else None

    def get_persona_by_account_code(self, *a, **k):
        return None

    def record_reply_observability(self, *a, **k):
        self.obs.append(k)


def _handler(monkeypatch, send, mid="h-mid"):
    dm_auto_reply._repo = _Repo()
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", send)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)
    token = ces.try_claim("instagram_dm:IDN-000051", mid, "dm_webhook")
    dm_auto_reply.handle_price_inquiry(
        "rec", "buyer1", "Hello", datetime.now(timezone.utc),
        account_code_ref="IDN-000051", dm_event=("instagram_dm:IDN-000051", mid, token))
    return ces.get_status("instagram_dm:IDN-000051", mid)


def test_successful_send_marks_reply_done(monkeypatch):
    sent = []
    row = _handler(monkeypatch, lambda *a, **k: sent.append(1) or True)
    assert len(sent) == 1 and row["private_reply_status"] == "DONE"


def test_send_exception_marks_unknown_and_manual_review(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("timeout")

    dm_auto_reply._repo = _Repo()
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", boom)
    token = ces.try_claim("instagram_dm:IDN-000051", "h-exc", "dm_webhook")
    with pytest.raises(RuntimeError):
        dm_auto_reply.handle_price_inquiry(
            "rec", "buyer1", "Hello", datetime.now(timezone.utc),
            account_code_ref="IDN-000051", dm_event=("instagram_dm:IDN-000051", "h-exc", token))
    row = ces.get_status("instagram_dm:IDN-000051", "h-exc")
    assert row["private_reply_status"] == "UNKNOWN" and row["manual_review_required"] == 1


@pytest.mark.parametrize("state", ["STARTED", "UNKNOWN", "DONE"])
def test_previous_reply_state_blocks_automatic_resend(monkeypatch, state):
    ces.try_claim("instagram_dm:IDN-000051", "prev", "dm_webhook")
    ces._c().execute("UPDATE comment_events SET private_reply_status=? WHERE source_event_id='prev'", (state,))
    ces._c().commit()
    # 재claim을 가정해 새 토큰으로 처리기를 호출
    ces._c().execute("UPDATE comment_events SET claim_token='tok2' WHERE source_event_id='prev'")
    ces._c().commit()
    sent = []
    dm_auto_reply._repo = _Repo()
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: sent.append(1) or True)
    dm_auto_reply.handle_price_inquiry(
        "rec", "buyer1", "Hello", datetime.now(timezone.utc),
        account_code_ref="IDN-000051", dm_event=("instagram_dm:IDN-000051", "prev", "tok2"))
    assert sent == []
    # 슬롯이 해제되어 정당한 이후 요청이 막히지 않는다
    assert ("IDN-000051", "buyer1") not in dm_auto_reply._TEMPLATE_EN_DEDUP


def test_fenced_out_claim_holds_reply(monkeypatch):
    ces.try_claim("instagram_dm:IDN-000051", "fenced", "dm_webhook")
    sent = []
    dm_auto_reply._repo = _Repo()
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: sent.append(1) or True)
    dm_auto_reply.handle_price_inquiry(
        "rec", "buyer1", "Hello", datetime.now(timezone.utc),
        account_code_ref="IDN-000051", dm_event=("instagram_dm:IDN-000051", "fenced", "wrong-token"))
    assert sent == []


# ── retry 경계 (261029 retry 경계 보완) ─────────────────────────────────────────

class _FakeRQ:
    def __init__(self):
        self.tasks = []

    def register(self, *a, **k):
        pass

    def start(self):
        pass

    def enqueue(self, task_type, payload, **k):
        self.tasks.append((task_type, payload))
        return len(self.tasks)


def _first_attempt_fails_and_queues(monkeypatch, mid="r-mid"):
    from modules.common import retry_queue as retry_queue_mod
    rq = _FakeRQ()
    monkeypatch.setattr(retry_queue_mod, "get_retry_queue", lambda: rq)
    dm_auto_reply._repo = _Repo()
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", _fail_with(400))
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)
    token = ces.try_claim("instagram_dm:IDN-000051", mid, "dm_webhook")
    dm_auto_reply.handle_price_inquiry(
        "rec", "buyer1", "Hello", datetime.now(timezone.utc),
        account_code_ref="IDN-000051", dm_event=("instagram_dm:IDN-000051", mid, token))
    return rq, mid


def test_retry_payload_carries_event_identity(monkeypatch):
    rq, mid = _first_attempt_fails_and_queues(monkeypatch)
    payload = rq.tasks[0][1]
    assert payload["dm_event"][:2] == ["instagram_dm:IDN-000051", mid] and len(payload["dm_event"]) == 3


def test_retry_success_marks_done_and_second_run_does_not_resend(monkeypatch):
    rq, mid = _first_attempt_fails_and_queues(monkeypatch)
    sent = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: sent.append(1) or True)
    dm_auto_reply._retry_send_ig_reply(rq.tasks[0][1])
    assert sent == [1]
    assert ces.get_status("instagram_dm:IDN-000051", mid)["private_reply_status"] == "DONE"
    dm_auto_reply._retry_send_ig_reply(rq.tasks[0][1])   # 큐가 같은 작업을 다시 실행해도
    assert sent == [1]


def test_retry_exception_marks_unknown_and_next_attempt_sends_nothing(monkeypatch):
    rq, mid = _first_attempt_fails_and_queues(monkeypatch)
    calls = []

    def ambiguous(*a, **k):
        calls.append(1)
        raise RuntimeError("timeout after possible delivery")

    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", ambiguous)
    with pytest.raises(RuntimeError):
        dm_auto_reply._retry_send_ig_reply(rq.tasks[0][1])
    row = ces.get_status("instagram_dm:IDN-000051", mid)
    assert row["private_reply_status"] == "UNKNOWN" and row["manual_review_required"] == 1
    dm_auto_reply._retry_send_ig_reply(rq.tasks[0][1])   # 큐의 다음 시도
    assert calls == [1], "UNKNOWN 이후 자동 재발송 금지"


def test_retry_definite_failure_stays_retryable(monkeypatch):
    rq, mid = _first_attempt_fails_and_queues(monkeypatch)
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", _fail_with(400))
    with pytest.raises(RuntimeError):
        dm_auto_reply._retry_send_ig_reply(rq.tasks[0][1])
    assert ces.get_status("instagram_dm:IDN-000051", mid)["private_reply_status"] == "STARTED"


def test_retry_payload_without_event_keeps_legacy_behavior(monkeypatch):
    sent = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: sent.append(1) or True)
    dm_auto_reply._retry_send_ig_reply({"sender_igsid": "b", "message": "m", "account_code_ref": "IDN-000051"})
    dm_auto_reply._retry_send_ig_reply({"sender_igsid": "b", "message": "m", "account_code_ref": "IDN-000051"})
    assert sent == [1, 1]   # 옛 payload는 기존 동작(상태 확인 없음)


def test_retry_event_store_error_fails_closed_without_sending(monkeypatch):
    sent = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: sent.append(1) or True)
    monkeypatch.setattr(ces, "get_status", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db locked")))
    with pytest.raises(RuntimeError):
        dm_auto_reply._retry_send_ig_reply({"sender_igsid": "b", "message": "m",
                                            "account_code_ref": "IDN-000051",
                                            "dm_event": ["instagram_dm:IDN-000051", "x", "t"]})
    assert sent == []


def test_flag_off_first_failure_enqueues_payload_without_event(monkeypatch):
    from modules.common import retry_queue as retry_queue_mod
    rq = _FakeRQ()
    monkeypatch.setattr(retry_queue_mod, "get_retry_queue", lambda: rq)
    dm_auto_reply._repo = _Repo()
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: False)
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)
    dm_auto_reply.handle_price_inquiry("rec", "buyer1", "Hello", datetime.now(timezone.utc),
                                       account_code_ref="IDN-000051")
    assert "dm_event" not in rq.tasks[0][1]


# ── Codex 독립 검수 반영: retry fencing · 완료 표시 fencing ──────────────────────

def test_retry_with_missing_event_row_sends_nothing(monkeypatch):
    sent = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: sent.append(1) or True)
    dm_auto_reply._retry_send_ig_reply({"sender_igsid": "b", "message": "m", "account_code_ref": "IDN-000051",
                                        "dm_event": ["instagram_dm:IDN-000051", "no-such-mid", "tok"]})
    assert sent == []


def test_retry_with_stale_claim_token_sends_nothing(monkeypatch):
    rq, mid = _first_attempt_fails_and_queues(monkeypatch, mid="stale-mid")
    ces._c().execute("UPDATE comment_events SET claim_token='newer-owner' WHERE source_event_id=?", (mid,))
    ces._c().commit()
    sent = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: sent.append(1) or True)
    dm_auto_reply._retry_send_ig_reply(rq.tasks[0][1])   # 옛 token을 가진 payload
    assert sent == []
    assert ces.get_status("instagram_dm:IDN-000051", mid)["private_reply_status"] == "STARTED"  # 갱신도 안 됨


def test_fenced_completion_stops_telegram_and_reply(client, monkeypatch):
    spies = _Spies(monkeypatch, enabled=True)
    monkeypatch.setattr(ces, "mark_airtable_done", lambda *a, **k: False)   # claim 상실 시뮬레이션
    _post(client, RECIPIENT_051, mid="fence-1")
    assert len(spies.saved) == 1
    assert spies.alerts == [] and spies.handled == []


def test_completion_store_error_keeps_alert_but_holds_reply(client, monkeypatch):
    spies = _Spies(monkeypatch, enabled=True)
    monkeypatch.setattr(ces, "mark_airtable_done", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("locked")))
    _post(client, RECIPIENT_051, mid="err-1")
    assert len(spies.alerts) == 1 and spies.handled == []


# ── UNKNOWN 수동 확인 Slack 알림 (기존 services/slack_notifier 재사용) ───────────────

@pytest.fixture
def slack(monkeypatch):
    import services.slack_notifier as sn
    sent = []
    monkeypatch.setattr(sn, "send_alert", lambda title, body="", level="warning": sent.append(title + " " + body) or True)
    return sent


def test_unknown_after_send_exception_notifies_slack_without_pii(monkeypatch, slack):
    dm_auto_reply._repo = _Repo()
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("timeout")))
    token = ces.try_claim("instagram_dm:IDN-000051", "abcdef123456", "dm_webhook")
    with pytest.raises(RuntimeError):
        dm_auto_reply.handle_price_inquiry(
            "rec", "buyer-secret-id", "Hello", datetime.now(timezone.utc),
            account_code_ref="IDN-000051", dm_event=("instagram_dm:IDN-000051", "abcdef123456", token))
    assert len(slack) == 1
    assert "UNKNOWN" in slack[0] and "abcdef***" in slack[0]
    assert "abcdef123456" not in slack[0] and "buyer-secret-id" not in slack[0]


def test_retry_exception_notifies_slack_once_and_next_attempt_is_silent(monkeypatch, slack):
    rq, mid = _first_attempt_fails_and_queues(monkeypatch, mid="zzzzzz999")
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("t")))
    with pytest.raises(RuntimeError):
        dm_auto_reply._retry_send_ig_reply(rq.tasks[0][1])
    dm_auto_reply._retry_send_ig_reply(rq.tasks[0][1])   # 다음 시도는 UNKNOWN 홀드로 조용히 종료
    assert len(slack) == 1


def test_reply_state_hold_notifies_for_started_but_not_for_done(monkeypatch, slack):
    for state, expected in (("STARTED", 1), ("DONE", 0)):
        slack.clear()
        mid = f"hold-{state}"
        ces.try_claim("instagram_dm:IDN-000051", mid, "dm_webhook")
        ces._c().execute("UPDATE comment_events SET private_reply_status=?, claim_token='tk' WHERE source_event_id=?", (state, mid))
        ces._c().commit()
        dm_auto_reply._repo = _Repo()
        monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: True)
        dm_auto_reply._TEMPLATE_EN_DEDUP.clear()
        dm_auto_reply.handle_price_inquiry(
            "rec", f"b-{state}", "Hello", datetime.now(timezone.utc),
            account_code_ref="IDN-000051", dm_event=("instagram_dm:IDN-000051", mid, "tk"))
        assert len(slack) == expected, state


def test_slack_failure_does_not_break_hold_path(monkeypatch):
    import services.slack_notifier as sn
    monkeypatch.setattr(sn, "send_alert", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("slack down")))
    dm_auto_reply._notify_dm_manual_review("instagram_dm:IDN-000051", "mid", "reason")   # 예외 전파 없음


# ── HTTP 실패 분류: 확정 미발송(0·4xx)만 재시도 허용, 5xx·불명은 UNKNOWN (Codex 재검수 반영) ──────────

@pytest.mark.parametrize("status,definite", [(0, True), (400, True), (403, True), (429, True),
                                              (500, False), (502, False), (503, False), (None, False)])
def test_failure_classifier(status, definite):
    dm_auto_reply._SEND_TLS.status = status
    assert dm_auto_reply._last_send_failure_is_definite() is definite


def test_send_ig_reply_records_http_status_and_no_request_marker(monkeypatch):
    class Resp:
        ok = False
        status_code = 503
        text = "unavailable"

    dm_auto_reply._repo = _Repo()
    monkeypatch.setattr(dm_auto_reply, "_resolve_dm_send_target", lambda ref: {"url": "u", "token": "t"})
    monkeypatch.setattr(dm_auto_reply.requests, "post", lambda *a, **k: Resp())
    assert dm_auto_reply.send_ig_reply("b", "m", "IDN-000051") is False
    assert dm_auto_reply._SEND_TLS.status == 503
    monkeypatch.setattr(dm_auto_reply, "_resolve_dm_send_target", lambda ref: None)
    assert dm_auto_reply.send_ig_reply("b", "m", "IDN-000051") is False   # 대상 해석 실패 — 요청 없음
    assert dm_auto_reply._SEND_TLS.status == 0


def _first_attempt(monkeypatch, status, mid):
    from modules.common import retry_queue as retry_queue_mod
    rq = _FakeRQ()
    monkeypatch.setattr(retry_queue_mod, "get_retry_queue", lambda: rq)
    dm_auto_reply._repo = _Repo()
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", _fail_with(status))
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)
    token = ces.try_claim("instagram_dm:IDN-000051", mid, "dm_webhook")
    dm_auto_reply.handle_price_inquiry(
        "rec", "buyer1", "Hello", datetime.now(timezone.utc),
        account_code_ref="IDN-000051", dm_event=("instagram_dm:IDN-000051", mid, token))
    return rq


def test_first_attempt_5xx_marks_unknown_without_enqueueing_retry(monkeypatch):
    sent_alerts = []
    import services.slack_notifier as sn
    monkeypatch.setattr(sn, "send_alert", lambda title, body="", level="warning": sent_alerts.append(title + " " + body) or True)
    rq = _first_attempt(monkeypatch, 503, "f-503")
    row = ces.get_status("instagram_dm:IDN-000051", "f-503")
    assert rq.tasks == []
    assert row["private_reply_status"] == "UNKNOWN" and row["manual_review_required"] == 1
    assert len(sent_alerts) == 1


def test_first_attempt_4xx_enqueues_retry_and_stays_started(monkeypatch):
    rq = _first_attempt(monkeypatch, 400, "f-400")
    assert len(rq.tasks) == 1
    assert ces.get_status("instagram_dm:IDN-000051", "f-400")["private_reply_status"] == "STARTED"


def test_retry_5xx_marks_unknown_notifies_and_does_not_raise_or_resend(monkeypatch):
    rq = _first_attempt(monkeypatch, 400, "r-503")
    alerts, calls = [], []
    import services.slack_notifier as sn
    monkeypatch.setattr(sn, "send_alert", lambda title, body="", level="warning": alerts.append(title + " " + body) or True)

    def server_error(*a, **k):
        calls.append(1)
        dm_auto_reply._SEND_TLS.status = 503
        return False

    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", server_error)
    dm_auto_reply._retry_send_ig_reply(rq.tasks[0][1])        # 예외 없이 종료(큐가 다시 돌리지 않음)
    assert ces.get_status("instagram_dm:IDN-000051", "r-503")["private_reply_status"] == "UNKNOWN"
    assert len(alerts) == 1
    dm_auto_reply._retry_send_ig_reply(rq.tasks[0][1])        # 이후 시도도 발송 없음
    assert calls == [1]


def test_flag_off_5xx_keeps_legacy_retry_enqueue(monkeypatch):
    """dm_event 없는 경로(플래그 OFF)는 실패 종류와 무관하게 기존대로 retry를 등록한다."""
    from modules.common import retry_queue as retry_queue_mod
    rq = _FakeRQ()
    monkeypatch.setattr(retry_queue_mod, "get_retry_queue", lambda: rq)
    dm_auto_reply._repo = _Repo()
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", _fail_with(503))
    monkeypatch.setattr(dm_auto_reply, "send_telegram_price_pending", lambda *a, **k: None)
    dm_auto_reply.handle_price_inquiry("rec", "buyer1", "Hello", datetime.now(timezone.utc),
                                       account_code_ref="IDN-000051")
    assert len(rq.tasks) == 1 and "dm_event" not in rq.tasks[0][1]


# ── 모호한 실패 후 cooldown 슬롯 유지 / 확정 미발송에서만 해제 (Codex 의견 반영) ─────────────────

def _slot_key(sender="buyer1"):
    return ("IDN-000051", sender)


def test_ambiguous_5xx_keeps_cooldown_slot_and_blocks_next_message(monkeypatch):
    dm_auto_reply._TEMPLATE_EN_DEDUP.clear()
    _first_attempt(monkeypatch, 503, "slot-503")
    assert _slot_key() in dm_auto_reply._TEMPLATE_EN_DEDUP, "모호한 실패 후 슬롯이 풀리면 중복 응답 위험"
    sent = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: sent.append(1) or True)
    token2 = ces.try_claim("instagram_dm:IDN-000051", "slot-503-next", "dm_webhook")
    dm_auto_reply.handle_price_inquiry(
        "rec2", "buyer1", "Another message", datetime.now(timezone.utc),
        account_code_ref="IDN-000051", dm_event=("instagram_dm:IDN-000051", "slot-503-next", token2))
    assert sent == []


def test_definite_4xx_releases_cooldown_slot(monkeypatch):
    dm_auto_reply._TEMPLATE_EN_DEDUP.clear()
    _first_attempt(monkeypatch, 400, "slot-400")
    assert _slot_key() not in dm_auto_reply._TEMPLATE_EN_DEDUP


def test_send_exception_with_event_keeps_slot_but_without_event_releases(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("timeout")

    for with_event in (True, False):
        dm_auto_reply._TEMPLATE_EN_DEDUP.clear()
        dm_auto_reply._TEMPLATE_EN_HOLD.clear()   # 앞 반복의 UNKNOWN hold가 다음 반복을 막지 않게 한다
        dm_auto_reply._repo = _Repo()
        monkeypatch.setattr(dm_auto_reply, "send_ig_reply", boom)
        mid = f"exc-{with_event}"
        kwargs = {}
        if with_event:
            token = ces.try_claim("instagram_dm:IDN-000051", mid, "dm_webhook")
            kwargs["dm_event"] = ("instagram_dm:IDN-000051", mid, token)
        with pytest.raises(RuntimeError):
            dm_auto_reply.handle_price_inquiry("rec", "buyer1", "Hello", datetime.now(timezone.utc),
                                               account_code_ref="IDN-000051", **kwargs)
        assert (_slot_key() in dm_auto_reply._TEMPLATE_EN_DEDUP) is with_event
