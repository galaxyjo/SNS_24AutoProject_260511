"""261108 — Producer 생성 실패 알림: (날짜, 계정, 오류코드)당 1회, 계정별로 독립."""
import launcher.main as m


def test_first_alert_per_account_and_code_only(monkeypatch):
    monkeypatch.setattr(m, "_PRODUCER_FAIL_ALERTED", set())
    assert m._producer_fail_alert_first("IDN-000024", "CAROUSEL_TEXT_FAILED:GENERATION_FAILED") is True
    assert m._producer_fail_alert_first("IDN-000024", "CAROUSEL_TEXT_FAILED:GENERATION_FAILED") is False
    assert m._producer_fail_alert_first("IDN-000030", "CAROUSEL_TEXT_FAILED:GENERATION_FAILED") is True
    assert m._producer_fail_alert_first("IDN-000024", "IMAGE_GENERATION_FAILED") is True


def test_new_day_alerts_again(monkeypatch):
    from datetime import datetime
    monkeypatch.setattr(m, "_PRODUCER_FAIL_ALERTED", set())
    monkeypatch.setattr(m, "_ict_now", lambda: datetime(2026, 11, 8, 9, 0))
    assert m._producer_fail_alert_first("IDN-000024", "X") is True
    monkeypatch.setattr(m, "_ict_now", lambda: datetime(2026, 11, 9, 9, 0))
    assert m._producer_fail_alert_first("IDN-000024", "X") is True
