"""tests/test_dm_retry_concurrency.py — 261029 DM retry 동시 실행 fencing(원자적 SENDING 선점).

임시 SQLite만 사용한다(운영 db·Airtable·Slack·Meta 접속 없음). 외부 발송은 mock이며,
전부 운영 성공 증거가 아니다. 동시성은 threading.Barrier와 별도 프로세스(subprocess)로 확인한다.
"""

import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

import modules.dm.dm_auto_reply as dm_auto_reply
from modules.comment import comment_event_store as ces

SOURCE = "instagram_dm:IDN-000051"
REPO_ROOT = str(Path(__file__).resolve().parents[1])


@pytest.fixture(autouse=True)
def _no_real_slack(monkeypatch):
    """테스트가 실제 Slack Webhook으로 나가지 않도록 .env에서 불러온 URL을 비운다(알림 자동 생략)."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")   # Telegram 대체 알림도 실제로 나가지 않게 한다


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(ces, "_DB_PATH", tmp_path / "events_test.db")
    monkeypatch.setattr(ces, "_conn", None)
    dm_auto_reply._TEMPLATE_EN_HOLD.clear()
    dm_auto_reply._ALERT_LAST.clear()
    yield


@pytest.fixture
def slack(monkeypatch):
    import services.slack_notifier as sn
    sent = []
    monkeypatch.setattr(sn, "send_alert", lambda title, body="", level="warning": sent.append(title + " " + body) or True)
    return sent


def _event(mid, state="STARTED"):
    token = ces.try_claim(SOURCE, mid, "dm_webhook")
    ces._c().execute("UPDATE comment_events SET private_reply_status=? WHERE source_event_id=?", (state, mid))
    ces._c().commit()
    return token


def _payload(mid, token):
    return {"sender_igsid": "buyer", "message": "m", "account_code_ref": "IDN-000051",
            "dm_event": [SOURCE, mid, token]}


def _status(mid):
    return ces.get_status(SOURCE, mid)["private_reply_status"]


# ── 저장소 함수 단위 ────────────────────────────────────────────────────────────

def test_try_begin_effect_wins_only_from_allowed_states_with_matching_token():
    token = _event("m1", "STARTED")
    assert ces.try_begin_effect(SOURCE, "m1", "wrong", "private_reply", ("STARTED",)) is False
    assert ces.try_begin_effect(SOURCE, "m1", token, "private_reply", ("DONE",)) is False
    assert ces.try_begin_effect(SOURCE, "m1", token, "private_reply", ("STARTED", "NOT_APPLICABLE")) is True
    assert _status("m1") == "SENDING"
    assert ces.try_begin_effect(SOURCE, "m1", token, "private_reply", ("STARTED", "NOT_APPLICABLE")) is False


def test_finish_effect_failed_only_reverts_sending_with_matching_token():
    token = _event("m2", "SENDING")
    assert ces.finish_effect_failed(SOURCE, "m2", "wrong", "private_reply") is False
    assert _status("m2") == "SENDING"
    assert ces.finish_effect_failed(SOURCE, "m2", token, "private_reply") is True
    assert _status("m2") == "STARTED"
    assert ces.finish_effect_failed(SOURCE, "m2", token, "private_reply") is False   # STARTED는 대상 아님


def test_new_functions_do_not_touch_comment_source_rows():
    ces.try_claim("instagram_comment", "c1", "webhook")
    token = ces.try_claim(SOURCE, "m3", "dm_webhook")
    assert ces.try_begin_effect(SOURCE, "m3", token, "private_reply", ("NOT_APPLICABLE",)) is True
    assert ces.get_status("instagram_comment", "c1")["private_reply_status"] == "NOT_APPLICABLE"


# ── 핸들러 동시성 (Barrier) ─────────────────────────────────────────────────────

@pytest.mark.parametrize("round_no", range(30))
def test_concurrent_retry_executions_send_at_most_once(monkeypatch, round_no):
    mid = f"race-{round_no}"
    token = _event(mid, "STARTED")
    payload = _payload(mid, token)
    n = 8
    barrier = threading.Barrier(n)
    sent, lock, errors = [], threading.Lock(), []

    def slow_send(*a, **k):
        time.sleep(0.05)
        with lock:
            sent.append(1)
        return True

    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", slow_send)

    def worker():
        try:
            barrier.wait(timeout=10)
            dm_auto_reply._retry_send_ig_reply(payload)
        except Exception as exc:   # 어느 스레드도 예외 없이 끝나야 한다
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert errors == []
    assert len(sent) == 1, f"동시 {n}개 실행에서 외부 발송 {len(sent)}회"
    assert _status(mid) == "DONE"


def test_concurrent_executions_with_ambiguous_exception_send_at_most_once(monkeypatch, slack):
    mid = "race-exc"
    token = _event(mid, "STARTED")
    payload = _payload(mid, token)
    n = 8
    barrier = threading.Barrier(n)
    calls, lock = [], threading.Lock()

    def boom(*a, **k):
        time.sleep(0.05)
        with lock:
            calls.append(1)
        raise RuntimeError("timeout after possible delivery")

    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", boom)

    def worker():
        barrier.wait(timeout=10)
        try:
            dm_auto_reply._retry_send_ig_reply(payload)
        except RuntimeError:
            pass

    threads = [threading.Thread(target=worker) for _ in range(n)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(calls) == 1
    assert _status(mid) == "UNKNOWN"


# ── 상태 전이 보존 ──────────────────────────────────────────────────────────────

def test_definite_failure_returns_to_started_and_is_retryable(monkeypatch):
    token = _event("seq-1", "STARTED")
    payload = _payload("seq-1", token)
    results = iter([False, True])
    sent = []

    def flaky(*a, **k):
        sent.append(1)
        ok = next(results)
        dm_auto_reply._SEND_TLS.status = 200 if ok else 400   # 첫 시도는 확정 실패(4xx)
        return ok

    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", flaky)
    with pytest.raises(RuntimeError):
        dm_auto_reply._retry_send_ig_reply(payload)
    assert _status("seq-1") == "STARTED"            # SENDING에 갇히지 않고 재시도 가능
    dm_auto_reply._retry_send_ig_reply(payload)
    assert _status("seq-1") == "DONE" and len(sent) == 2
    dm_auto_reply._retry_send_ig_reply(payload)     # 순차 반복 — 추가 발송 없음
    assert len(sent) == 2


def test_leftover_sending_state_holds_and_notifies(monkeypatch, slack):
    token = _event("stuck", "SENDING")
    sent = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: sent.append(1) or True)
    dm_auto_reply._retry_send_ig_reply(_payload("stuck", token))
    assert sent == [] and _status("stuck") == "SENDING"
    assert len(slack) == 1 and "SENDING" in slack[0]


def test_stale_token_is_rejected_before_any_state_change(monkeypatch):
    _event("tok", "STARTED")
    sent = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: sent.append(1) or True)
    dm_auto_reply._retry_send_ig_reply(_payload("tok", "stale-token"))
    assert sent == [] and _status("tok") == "STARTED"


# ── 별도 프로세스 동시성 (선택, 같은 임시 DB 파일 공유) ────────────────────────────

def test_two_processes_race_for_same_event_only_one_wins(tmp_path):
    db_path = tmp_path / "multiproc.db"
    ces._DB_PATH = db_path
    ces._conn = None
    token = ces.try_claim(SOURCE, "mp-1", "dm_webhook")
    start_at = time.time() + 2.5
    code = textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, r"{REPO_ROOT}")
        from pathlib import Path
        from modules.comment import comment_event_store as ces
        ces._DB_PATH = Path(r"{db_path}")
        ces._conn = None
        ces._c()                              # 연결·스키마를 시작 시각 전에 준비
        while time.time() < {start_at}:
            time.sleep(0.001)
        won = ces.try_begin_effect("{SOURCE}", "mp-1", "{token}", "private_reply", ("NOT_APPLICABLE", "STARTED"))
        print("WON" if won else "LOST")
    """)
    procs = [subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
             for _ in range(4)]
    outs = [p.communicate(timeout=60) for p in procs]
    results = [o[0].strip() for o in outs]
    assert all(p.returncode == 0 for p in procs), [o[1] for o in outs]
    assert results.count("WON") == 1 and results.count("LOST") == 3, results
