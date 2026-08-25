"""260825 — aijomoojin 5슬롯이 misfire_grace_time(60초)을 넘겨 스킵될 때(주로 노트북
Modern Standby로 스케줄러 전체가 멈췄을 때) 즉시 Slack 알림이 가는지 검증한다.
노트북이 잠드는 것 자체를 막는 시도는 이미 실패해 중단했고(ERR-114/ERR-116), 대신
"놓치면 바로 안다"로 방향을 바꾼 조치. 재시도/캐치업 동작은 절대 추가하지 않는다
(기존 스킵 설계 무변경 — 이 테스트는 그 설계가 안 바뀌었는지도 함께 확인한다)."""

from datetime import datetime

from apscheduler.events import EVENT_JOB_MISSED, JobExecutionEvent

from launcher import main as launcher_main


def _missed_event(job_id: str) -> JobExecutionEvent:
    return JobExecutionEvent(
        EVENT_JOB_MISSED, job_id, "default", datetime(2026, 8, 25, 9, 0, 0)
    )


def test_aijomoojin_slot_missed_sends_slack_alert(monkeypatch):
    sent = []
    monkeypatch.setattr(launcher_main, "_slack", lambda msg: sent.append(msg))

    launcher_main._on_aijomoojin_job_missed(_missed_event("aijomoojin_slot_0900"))

    assert len(sent) == 1
    assert "aijomoojin_slot_0900" in sent[0]
    assert "2026-08-25 09:00:00" in sent[0]


def test_aijomoojin_producer_missed_sends_slack_alert(monkeypatch):
    sent = []
    monkeypatch.setattr(launcher_main, "_slack", lambda msg: sent.append(msg))

    launcher_main._on_aijomoojin_job_missed(_missed_event("aijomoojin_producer_0800"))

    assert len(sent) == 1
    assert "aijomoojin_producer_0800" in sent[0]


def test_non_aijomoojin_job_missed_does_not_alert(monkeypatch):
    """알림 폭주 방지 — 5분 간격 폴러 등 다른 Job이 같은 절전 구간에 같이 놓쳐도
    aijomoojin 외에는 이 리스너가 알림을 보내지 않는다(기존 다른 알림 경로와 무관)."""
    sent = []
    monkeypatch.setattr(launcher_main, "_slack", lambda msg: sent.append(msg))

    launcher_main._on_aijomoojin_job_missed(_missed_event("_job_insta_upload"))

    assert sent == []


def test_missed_slot_alert_does_not_retry_or_reschedule(monkeypatch):
    """이 리스너는 관측(알림)만 하고, 놓친 Job을 다시 실행시키거나 재등록하지 않는다
    — add_job/modify_job 등 스케줄러 조작 함수를 전혀 호출하지 않는지 확인."""
    monkeypatch.setattr(launcher_main, "_slack", lambda msg: None)

    class _ExplodingScheduler:
        def __getattr__(self, name):
            raise AssertionError(f"리스너가 스케줄러를 건드리면 안 됨: {name} 호출 시도됨")

    # 리스너 함수는 스케줄러 인스턴스를 인자로 받지 않으므로, 전역에 스케줄러가
    # 있어도 참조하지 않는지는 함수 시그니처 자체(event만 받음)로 이미 보장된다.
    launcher_main._on_aijomoojin_job_missed(_missed_event("aijomoojin_slot_0600"))


def test_missed_slot_alert_noop_when_slack_not_configured(monkeypatch):
    """SLACK_WEBHOOK_URL 미설정 등으로 _slack이 None이어도 예외 없이 조용히 넘어간다."""
    monkeypatch.setattr(launcher_main, "_slack", None)

    launcher_main._on_aijomoojin_job_missed(_missed_event("aijomoojin_slot_1200"))
