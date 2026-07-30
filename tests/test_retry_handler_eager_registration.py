"""tests/test_retry_handler_eager_registration.py — 10.6-5A(ERR-097 계열, 260730).

comment_airtable_record 외 6개 retry_queue 핸들러(ig_auto_reply/ig_followup/
dm_record_interaction/order_mark_converted/lead_update_score/lead_mark_closed)가
launcher 시작 시 eager 등록 가능한 register_retry_handlers(rq)를 노출하는지,
그리고 실제 핸들러 함수가 올바른 Repository 메서드를 호출하는지 검증한다.

modules.crm.* 3개는 modules.dm에 의존하지 않아 이 세션에서 직접 실행 가능하다.
modules.dm.* 3개는 modules/dm/__init__.py의 canary_safe_mode 체크로 이 세션에서
직접 실행이 막혀 있는 기존 환경제약(ERR-089 계열) — 회장 터미널에서 실행한다.
"""

import pytest


class _FakeRQ:
    def __init__(self):
        self.registered: dict = {}

    def register(self, task_type, handler):
        self.registered[task_type] = handler


# ── modules.crm (이 세션에서 직접 실행 가능) ──────────────────────────────────

def test_order_detector_registers_order_mark_converted(monkeypatch):
    from modules.crm import order_detector

    calls = []
    monkeypatch.setattr(order_detector._repo, "mark_lead_converted", lambda rid: calls.append(rid))

    rq = _FakeRQ()
    order_detector.register_retry_handlers(rq)

    assert "order_mark_converted" in rq.registered
    rq.registered["order_mark_converted"]({"record_id": "recABC"})
    assert calls == ["recABC"]


def test_lead_scorer_registers_lead_update_score(monkeypatch):
    from modules.crm import lead_scorer

    calls = []
    monkeypatch.setattr(lead_scorer._repo, "update_lead_score", lambda rid, s, g: calls.append((rid, s, g)))

    rq = _FakeRQ()
    lead_scorer.register_retry_handlers(rq)

    assert "lead_update_score" in rq.registered
    rq.registered["lead_update_score"]({"record_id": "recABC", "score": 5, "grade": "cold"})
    assert calls == [("recABC", 5, "cold")]


def test_lead_closer_registers_lead_mark_closed(monkeypatch):
    from modules.crm import lead_closer

    calls = []
    monkeypatch.setattr(lead_closer._repo, "mark_lead_closed", lambda rid: calls.append(rid))

    rq = _FakeRQ()
    lead_closer.register_retry_handlers(rq)

    assert "lead_mark_closed" in rq.registered
    rq.registered["lead_mark_closed"]({"record_id": "recABC"})
    assert calls == ["recABC"]


# ── modules.dm (회장 터미널 실행 — 이 세션은 modules.dm import 자체가 막혀있음) ──

def test_dm_auto_reply_registers_ig_auto_reply(monkeypatch):
    import modules.dm.dm_auto_reply as dm_auto_reply

    calls = []
    monkeypatch.setattr(dm_auto_reply, "send_ig_reply", lambda *a, **k: calls.append(a) or True)

    rq = _FakeRQ()
    dm_auto_reply.register_retry_handlers(rq)

    assert "ig_auto_reply" in rq.registered
    rq.registered["ig_auto_reply"]({"sender_igsid": "ig1", "message": "hi", "account_code_ref": "IDN-000036"})
    assert calls == [("ig1", "hi", "IDN-000036")]


def test_dm_followup_scheduler_registers_ig_followup(monkeypatch):
    import modules.dm.dm_followup_scheduler as dm_followup_scheduler

    calls = []
    monkeypatch.setattr(dm_followup_scheduler, "_send_ig_dm", lambda *a, **k: calls.append(a) or True)

    rq = _FakeRQ()
    dm_followup_scheduler.register_retry_handlers(rq)

    assert "ig_followup" in rq.registered
    rq.registered["ig_followup"]({"igsid": "ig1", "text": "hi", "account_code_ref": "IDN-000036"})
    assert calls == [("ig1", "hi", "IDN-000036")]


def test_dm_receiver_registers_dm_record_interaction(monkeypatch):
    import modules.dm.dm_receiver as dm_receiver

    calls = []
    monkeypatch.setattr(dm_receiver, "record_interaction", lambda *a, **k: calls.append((a, k)))

    rq = _FakeRQ()
    dm_receiver.register_retry_handlers(rq)

    assert "dm_record_interaction" in rq.registered
    rq.registered["dm_record_interaction"]({"sender_id": "ig1", "text": "hi", "account_code_ref": "IDN-000036"})
    assert calls == [(("ig1", "hi"), {"account_code_ref": "IDN-000036"})]
