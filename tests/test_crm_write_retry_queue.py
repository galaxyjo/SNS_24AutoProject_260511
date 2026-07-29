"""9-11 ERR-086~088 수정 검증 — CRM 쓰기 실패가 (1) 조용히 유실되지 않고 retry_queue에
위임되는지, (2) 성공 경로는 회귀 없이 그대로인지 확인한다.

ERR-085(modules.dm.dm_receiver)는 별도 파일(test_dm_receiver_record_interaction_retry.py)
로 분리했다 — dm_receiver 모듈은 import 시점에 canary_safe_mode의
runtime_boot_policy.json을 확인하는데, 이 로컬 pytest 실행 계정에는 그 파일 읽기 권한이
없어(PermissionError, 기존 tests/test_dm_receiver_webhook.py도 동일하게 collection
자체가 실패하는 pre-existing 환경 제약) 이 파일에 함께 두면 ERR-086~088 테스트까지
전부 collection이 막힌다.

Runtime 상태변경(Airtable Write, 실제 네트워크 호출) 없이 Mock으로만 검증한다.
"""


class _FakeRetryQueue:
    def __init__(self):
        self.registered: dict[str, callable] = {}
        self.enqueued: list[tuple[str, dict]] = []
        self.started = False

    def register(self, task_type, handler):
        self.registered[task_type] = handler

    def start(self):
        self.started = True

    def enqueue(self, task_type, payload, max_attempts=3):
        self.enqueued.append((task_type, payload))
        return 1


# ── ERR-086: lead_scorer.update_lead_score() ────────────────────────────────

class TestErr086UpdateLeadScoreRetry:
    def test_success_path_unaffected(self, monkeypatch):
        from modules.crm import lead_scorer

        monkeypatch.setattr(lead_scorer._repo, "update_lead_score", lambda *a, **k: None)
        lead_scorer.update_lead_score("rec1", 25, "hot")  # 예외 없이 통과하면 성공

    def test_failure_registers_retry_queue(self, monkeypatch):
        from modules.crm import lead_scorer

        fake_rq = _FakeRetryQueue()
        monkeypatch.setattr("modules.common.retry_queue.get_retry_queue", lambda: fake_rq)

        def _boom(*a, **k):
            raise RuntimeError("boom")

        monkeypatch.setattr(lead_scorer._repo, "update_lead_score", _boom)
        lead_scorer.update_lead_score("rec1", 25, "hot")

        assert "lead_update_score" in fake_rq.registered
        assert fake_rq.enqueued == [("lead_update_score", {"record_id": "rec1", "score": 25, "grade": "hot"})]


# ── ERR-087: lead_closer.mark_lead_closed() ─────────────────────────────────

class TestErr087MarkLeadClosedRetry:
    def test_success_path_sends_telegram(self, monkeypatch):
        from modules.crm import lead_closer

        monkeypatch.setattr(lead_closer._repo, "mark_lead_closed", lambda *a, **k: None)
        alerts = []
        monkeypatch.setattr(lead_closer, "_send_telegram_closed", lambda rid: alerts.append(rid))

        lead_closer.mark_lead_closed("rec1")

        assert alerts == ["rec1"]

    def test_failure_registers_retry_queue_and_skips_success_notification(self, monkeypatch):
        from modules.crm import lead_closer

        fake_rq = _FakeRetryQueue()
        monkeypatch.setattr("modules.common.retry_queue.get_retry_queue", lambda: fake_rq)

        def _boom(*a, **k):
            raise RuntimeError("boom")

        monkeypatch.setattr(lead_closer._repo, "mark_lead_closed", _boom)
        alerts = []
        monkeypatch.setattr(lead_closer, "_send_telegram_closed", lambda rid: alerts.append(rid))

        lead_closer.mark_lead_closed("rec1")

        assert "lead_mark_closed" in fake_rq.registered
        assert fake_rq.enqueued == [("lead_mark_closed", {"record_id": "rec1"})]
        # 상태 갱신이 실패했는데 "CLOSE 완료" 알림이 나가면 안 된다(상태-알림 불일치 방지).
        assert alerts == []


# ── ERR-088: order_detector.handle_order_conversion() ───────────────────────

class TestErr088HandleOrderConversionRetry:
    def test_success_path_still_sends_telegram(self, monkeypatch):
        from modules.crm import order_detector

        monkeypatch.setattr(order_detector._repo, "mark_lead_converted", lambda *a, **k: None)
        alerts = []
        monkeypatch.setattr(order_detector, "_send_telegram_conversion", lambda sid, text: alerts.append(sid))

        order_detector.handle_order_conversion("rec1", "sender1", "주문할게요")

        assert alerts == ["sender1"]

    def test_failure_registers_retry_queue_but_still_notifies(self, monkeypatch):
        from modules.crm import order_detector

        fake_rq = _FakeRetryQueue()
        monkeypatch.setattr("modules.common.retry_queue.get_retry_queue", lambda: fake_rq)

        def _boom(*a, **k):
            raise RuntimeError("boom")

        monkeypatch.setattr(order_detector._repo, "mark_lead_converted", _boom)
        alerts = []
        monkeypatch.setattr(order_detector, "_send_telegram_conversion", lambda sid, text: alerts.append(sid))

        order_detector.handle_order_conversion("rec1", "sender1", "주문할게요")

        assert "order_mark_converted" in fake_rq.registered
        assert fake_rq.enqueued == [("order_mark_converted", {"record_id": "rec1"})]
        # 기존 동작 유지: 전환 기록 실패해도 Telegram 알림은 그대로 감(이번 수정 범위 밖,
        # 기존 계약 보존 확인용).
        assert alerts == ["sender1"]
