"""9-11 ERR-085 수정 검증 — dm_receiver 웹훅 핸들러가 record_interaction() 실패를
retry_queue에 위임하는지 확인한다(기존 test_dm_receiver_webhook.py와 동일한
client/_signed_post 패턴 재사용).

주의: 이 파일은 modules.dm.dm_receiver를 import하며, 그 모듈은 import 시점에
canary_safe_mode의 runtime_boot_policy.json 접근을 시도한다 — 이 로컬 pytest 실행
계정에 그 파일 읽기 권한이 없으면(PermissionError) collection 자체가 실패한다.
이는 기존 tests/test_dm_receiver_webhook.py도 동일하게 겪는 pre-existing 환경
제약이며, 이번 수정으로 발생한 회귀가 아니다(baseline 대조로 확인됨).

Runtime 상태변경(Airtable Write, 실제 네트워크 호출) 없이 Mock으로만 검증한다.
"""

import hashlib
import hmac
import json

import pytest

import modules.dm.dm_receiver as dm_receiver

GALAXY_SECRET = "test-galaxy-secret"


@pytest.fixture
def client(monkeypatch):
    dm_receiver.app.config["TESTING"] = True
    monkeypatch.setattr(dm_receiver, "WEBHOOK_APP_SECRET", GALAXY_SECRET)
    monkeypatch.setattr(dm_receiver, "AI_WEBHOOK_APP_SECRET", "test-ai-secret")
    monkeypatch.setattr(dm_receiver, "VERIFY_TOKEN", "test-galaxy-token")
    monkeypatch.setattr(dm_receiver, "AI_WEBHOOK_VERIFY_TOKEN", "test-ai-token")
    return dm_receiver.app.test_client()


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _signed_post(client, path, payload, secret=GALAXY_SECRET):
    body = json.dumps(payload).encode("utf-8")
    headers = {"X-Hub-Signature-256": _sign(body, secret)}
    return client.post(path, data=body, content_type="application/json", headers=headers)


def _dm_payload(sender_id="sender1", text="가격 문의"):
    return {
        "object": "instagram",
        "entry": [{
            "messaging": [{"sender": {"id": sender_id}, "message": {"text": text}}],
        }],
    }


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


class TestErr085RecordInteractionRetry:
    def test_success_path_unaffected(self, client, monkeypatch):
        dm_calls = []
        monkeypatch.setattr(dm_receiver, "record_interaction", lambda *a, **k: dm_calls.append(a) or "rec1")
        monkeypatch.setattr(dm_receiver, "send_telegram", lambda *a, **k: None)
        monkeypatch.setattr(dm_receiver, "is_repeat_inquiry", lambda *a, **k: False)
        monkeypatch.setattr(dm_receiver, "detect_order", lambda *a, **k: False)
        monkeypatch.setattr(dm_receiver, "detect_price_inquiry", lambda *a, **k: False)

        resp = _signed_post(client, "/webhook", _dm_payload())

        assert resp.status_code == 200
        assert len(dm_calls) == 1

    def test_failure_registers_retry_queue_instead_of_silent_loss(self, client, monkeypatch):
        fake_rq = _FakeRetryQueue()
        monkeypatch.setattr("modules.common.retry_queue.get_retry_queue", lambda: fake_rq)

        def _boom(*a, **k):
            raise RuntimeError("Airtable 기록 실패(시뮬레이션)")

        monkeypatch.setattr(dm_receiver, "record_interaction", _boom)
        telegram_calls = []
        monkeypatch.setattr(dm_receiver, "send_telegram", lambda *a, **k: telegram_calls.append(a))

        resp = _signed_post(client, "/webhook", _dm_payload(sender_id="sender-fail", text="문의"))

        assert resp.status_code == 200
        assert "dm_record_interaction" in fake_rq.registered
        assert len(fake_rq.enqueued) == 1
        task_type, payload = fake_rq.enqueued[0]
        assert task_type == "dm_record_interaction"
        assert payload["sender_id"] == "sender-fail"
        # record_interaction 실패 시 send_telegram(기존 성공 알림)은 호출되면 안 된다
        # (아직 레코드가 생성 안 됐는데 알림만 나가는 상태·알림 불일치 방지).
        assert telegram_calls == []
