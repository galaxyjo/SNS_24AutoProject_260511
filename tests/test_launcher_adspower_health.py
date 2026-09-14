"""260913 — launcher/main.py::_job_adspower_health 검증.

배경: 2026-09-11 02:33 ~ 09-12 16:34 KST 38시간 동안 AdsPower Local API 가
죽어 크롤링(78회 전체실패)·친구요청이 함께 멈췄으나 그 사실을 알리는 경보가
없었다. 이 잡은 그 침묵을 제거한다.

이 테스트는 실제 AdsPower·Slack·네트워크를 전혀 호출하지 않는다(Mock 전용).
Runtime 상태변경 없음 — 상태파일도 tmp_path 로 격리한다.

검증 목표:
  1. Flag 가 false 면 아무것도 하지 않는다
  2. 정상이면 알리지 않는다
  3. 임계 미달 실패는 알리지 않는다
  4. 임계 도달 시 DOWN 경보를 정확히 1건 보낸다
  5. 계속 다운인 동안 재발송하지 않는다(알림 폭탄 방지)
  6. 복구 시 복구 경보를 정확히 1건 보낸다
  7. DOWN 경보를 보낸 적 없으면 복구 경보도 보내지 않는다
  8. 상태는 파일에 남아 재시작을 넘어 중복 경보를 막는다
  9. 감시자가 감시 대상을 죽이지 않는다(예외 비전파)
"""

import json
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def slack_guard(monkeypatch):
    """이 파일의 모든 테스트에서 실제 Slack Webhook 호출을 차단한다.

    260914 테스트 격리 결함: 데코레이터(handle_errors) 경유 호출이 launcher.main 의
    _slack → services.slack_notifier.send_alert → requests.post 까지 도달해
    .env 의 실제 SLACK_WEBHOOK_URL 로 가짜 'disk full' 경보를 보냈다.

    - send_alert 를 기록용 Mock 으로 바꾼다 → 알림 호출 횟수·내용은 여기서 검증한다.
    - 그 아래 HTTP 경계(requests.post)는 호출을 기록만 한다. slack_notifier._post 가
      모든 예외를 삼키므로 raise 로는 실패가 드러나지 않는다 — 대신 teardown 에서
      호출 0건을 단언한다(실제 네트워크 요청 0건 증명).
    """
    import services.slack_notifier as sn

    guard = SimpleNamespace(sent=[], http_calls=[])
    monkeypatch.setattr(
        sn, "send_alert",
        lambda title, body="", level="warning": guard.sent.append(
            {"title": title, "body": body, "level": level}
        ) or True,
    )
    monkeypatch.setattr(
        sn.requests, "post",
        lambda *a, **k: guard.http_calls.append((a, k)),
    )
    yield guard
    assert guard.http_calls == [], "테스트가 실제 Slack Webhook HTTP 요청을 시도했다"


@pytest.fixture
def m(monkeypatch, tmp_path):
    """launcher.main 을 Flag ON + 상태파일 격리 상태로 돌려준다."""
    monkeypatch.setenv("ADSPOWER_HEALTH_ALERT_ENABLED", "true")
    from launcher import main as _m
    monkeypatch.setattr(
        _m, "_ADSPOWER_HEALTH_STATE_PATH", tmp_path / "adspower_health_state.json"
    )
    monkeypatch.setattr(_m, "_ADSPOWER_HEALTH_FAIL_THRESHOLD", 3)
    return _m


@pytest.fixture
def alerts(monkeypatch, m):
    """Slack 발송을 가로채 (title, body, level) 로 모은다."""
    sent = []
    monkeypatch.setattr(
        m, "_adspower_health_notify",
        lambda title, body, level: sent.append((title, body, level)),
    )
    return sent


def _patch_ping(monkeypatch, m, ok, reason=""):
    monkeypatch.setattr(m, "_adspower_ping", lambda *a, **k: (ok, reason))


def _run(m):
    m._job_adspower_health.__wrapped__()


def _state(m):
    return json.loads(m._ADSPOWER_HEALTH_STATE_PATH.read_text(encoding="utf-8"))


# ── 1. Flag OFF ───────────────────────────────────────────────────────────────
def test_flag_off_does_nothing(monkeypatch, m, alerts):
    monkeypatch.setenv("ADSPOWER_HEALTH_ALERT_ENABLED", "false")
    pinged = []
    monkeypatch.setattr(m, "_adspower_ping", lambda *a, **k: pinged.append(1) or (True, ""))
    _run(m)
    assert pinged == []
    assert alerts == []
    assert not m._ADSPOWER_HEALTH_STATE_PATH.exists()


# ── 2. 정상이면 조용하다 ──────────────────────────────────────────────────────
def test_healthy_sends_nothing(monkeypatch, m, alerts):
    _patch_ping(monkeypatch, m, True)
    _run(m)
    assert alerts == []
    assert _state(m)["healthy"] is True
    assert _state(m)["consecutive_failures"] == 0


# ── 3. 임계 미달 실패는 알리지 않는다 ─────────────────────────────────────────
def test_below_threshold_sends_nothing(monkeypatch, m, alerts):
    _patch_ping(monkeypatch, m, False, "URLError: refused")
    _run(m)
    _run(m)
    assert alerts == []
    assert _state(m)["consecutive_failures"] == 2
    assert _state(m)["down_alerted"] is False


# ── 4. 임계 도달 시 DOWN 경보 1건 ─────────────────────────────────────────────
def test_threshold_sends_exactly_one_down_alert(monkeypatch, m, alerts):
    _patch_ping(monkeypatch, m, False, "URLError: refused")
    for _ in range(3):
        _run(m)
    assert len(alerts) == 1
    title, body, level = alerts[0]
    assert "다운" in title
    assert level == "error"
    assert "refused" in body
    assert _state(m)["down_alerted"] is True


# ── 5. 계속 다운이어도 재발송하지 않는다 (알림 폭탄 방지) ─────────────────────
def test_still_down_does_not_repeat(monkeypatch, m, alerts):
    _patch_ping(monkeypatch, m, False, "URLError: refused")
    for _ in range(12):          # 10분 간격이면 2시간치
        _run(m)
    assert len(alerts) == 1
    assert _state(m)["consecutive_failures"] == 12


# ── 6. 복구 시 복구 경보 1건 ──────────────────────────────────────────────────
def test_recovery_sends_exactly_one_alert(monkeypatch, m, alerts):
    _patch_ping(monkeypatch, m, False, "URLError: refused")
    for _ in range(3):
        _run(m)
    assert len(alerts) == 1

    _patch_ping(monkeypatch, m, True)
    _run(m)
    _run(m)                      # 두 번째 정상 확인에는 아무것도 안 보낸다
    assert len(alerts) == 2
    title, body, level = alerts[1]
    assert "복구" in title
    assert level == "success"
    assert "지속 시간" in body
    assert _state(m)["down_alerted"] is False


# ── 7. DOWN 경보가 없었으면 복구 경보도 없다 ─────────────────────────────────
def test_recovery_without_down_alert_is_silent(monkeypatch, m, alerts):
    _patch_ping(monkeypatch, m, False, "URLError: refused")
    _run(m)                      # 1회 실패(임계 미달)
    _patch_ping(monkeypatch, m, True)
    _run(m)
    assert alerts == []


# ── 8. 상태는 재시작을 넘어 보존된다 ─────────────────────────────────────────
def test_state_survives_restart_no_duplicate_alert(monkeypatch, m, alerts):
    """launcher 재시작으로 모듈 전역이 초기화돼도 파일 상태로 중복 경보를 막는다."""
    m._ADSPOWER_HEALTH_STATE_PATH.write_text(
        json.dumps({
            "healthy": False,
            "consecutive_failures": 50,
            "down_alerted": True,
            "down_since": "2026-09-11 02:33:59",
        }),
        encoding="utf-8",
    )
    _patch_ping(monkeypatch, m, False, "URLError: refused")
    _run(m)
    assert alerts == []          # 이미 알린 다운이므로 재발송 없음
    assert _state(m)["consecutive_failures"] == 51


def test_down_since_preserved_across_runs(monkeypatch, m, alerts):
    _patch_ping(monkeypatch, m, False, "URLError: refused")
    _run(m)
    first = _state(m)["down_since"]
    for _ in range(4):
        _run(m)
    assert _state(m)["down_since"] == first


# ── 9. 감시자가 감시 대상을 죽이지 않는다 ────────────────────────────────────
def test_ping_never_raises(monkeypatch, m):
    """네트워크 예외는 (False, 사유) 로 흡수한다."""
    def _boom(*a, **k):
        raise OSError("WinError 10061")
    monkeypatch.setattr("urllib.request.urlopen", _boom)
    ok, reason = m._adspower_ping()
    assert ok is False
    assert "10061" in reason


def test_non_zero_code_is_failure(monkeypatch, m):
    """HTTP 200 이어도 code != 0 이면 정상이 아니다."""
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"code": -1, "msg": "not logged in"}'
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    ok, reason = m._adspower_ping()
    assert ok is False
    assert "비정상 응답" in reason


def test_state_write_failure_does_not_break_job(monkeypatch, m, alerts, slack_guard):
    """상태파일을 못 써도 경보는 나가고 잡은 죽지 않는다."""
    monkeypatch.setattr(
        m, "_adspower_health_state_read",
        lambda: {"consecutive_failures": 2, "down_alerted": False, "down_since": "x"},
    )
    def _boom(_state):
        raise OSError("disk full")
    monkeypatch.setattr(m, "_adspower_health_state_write", _boom)
    _patch_ping(monkeypatch, m, False, "URLError: refused")
    with pytest.raises(OSError):
        _run(m)                              # __wrapped__ 는 예외를 그대로 낸다
    assert len(alerts) == 1                  # 경보는 이미 나갔다
    assert m._job_adspower_health() is None  # 데코레이터 경유는 삼켜야 한다
    # 데코레이터(handle_errors)의 notify_fn=_slack 경로 — 이 경로가 실제 Slack 으로
    # 가짜 경보를 보냈던 곳이다. 이제는 send_alert Mock 에만 닿아야 한다.
    expected = 1 if m._slack is not None else 0
    error_path = [c for c in slack_guard.sent if "disk full" in c["body"]]
    assert len(error_path) == expected
    if expected:
        assert error_path[0]["level"] == "error"
        assert "[adspower_health]" in error_path[0]["body"]


# ── 10. _build_scheduler() 등록 파라미터 ─────────────────────────────────────

class TestSchedulerRegistration:
    def test_flag_off_registers_no_health_job(self, monkeypatch):
        monkeypatch.delenv("ADSPOWER_HEALTH_ALERT_ENABLED", raising=False)
        from launcher import main as launcher_main

        sched = launcher_main._build_scheduler()
        assert "adspower_health" not in {j.id for j in sched.get_jobs()}

    def test_flag_on_registers_one_health_job(self, monkeypatch):
        monkeypatch.setenv("ADSPOWER_HEALTH_ALERT_ENABLED", "true")
        from launcher import main as launcher_main

        sched = launcher_main._build_scheduler()
        jobs = [j for j in sched.get_jobs() if j.id == "adspower_health"]
        assert len(jobs) == 1
        assert jobs[0].max_instances == 1
        assert jobs[0].coalesce is True

    def test_canary_safe_mode_registers_nothing(self, monkeypatch):
        monkeypatch.setenv("ADSPOWER_HEALTH_ALERT_ENABLED", "true")
        from launcher import main as launcher_main

        sched = launcher_main._build_scheduler(canary_safe_mode=True)
        assert sched.get_jobs() == []

    def test_health_job_does_not_disturb_existing_jobs(self, monkeypatch):
        """신규 잡 1개만 늘고 기존 잡 구성은 그대로여야 한다."""
        monkeypatch.delenv("ADSPOWER_HEALTH_ALERT_ENABLED", raising=False)
        from launcher import main as launcher_main

        before = {j.id for j in launcher_main._build_scheduler().get_jobs()}
        monkeypatch.setenv("ADSPOWER_HEALTH_ALERT_ENABLED", "true")
        after = {j.id for j in launcher_main._build_scheduler().get_jobs()}
        assert after - before == {"adspower_health"}
        assert before - after == set()
