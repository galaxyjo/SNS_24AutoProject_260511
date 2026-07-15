"""tests/test_dm_receiver_webhook.py — P0(260715 Codex 3차 리뷰) 검증:
댓글 이벤트가 durable하게 접수되지 않았으면 200으로 뭉개지 않고 5xx를 반환해
Meta가 재전송하도록 유도해야 한다."""

import pytest

import modules.dm.dm_receiver as dm_receiver
from modules.comment.comment_auto_reply import CommentProcessResult


@pytest.fixture
def client():
    dm_receiver.app.config["TESTING"] = True
    return dm_receiver.app.test_client()


def _comment_payload(comment_id="c1", text="가격문의"):
    return {
        "object": "instagram",
        "entry": [{
            "changes": [{
                "field": "comments",
                "value": {
                    "id": comment_id,
                    "text": text,
                    "from": {"username": "buyer1", "id": "u1"},
                    "media": {"id": "media1"},
                },
            }],
        }],
    }


class TestDurableAcceptResponseCode:
    def test_accepted_returns_200(self, client, monkeypatch):
        monkeypatch.setattr(
            dm_receiver, "process_comment_event",
            lambda *a, **k: CommentProcessResult.ACCEPTED,
        )
        resp = client.post("/webhook", json=_comment_payload())
        assert resp.status_code == 200

    def test_in_progress_returns_5xx(self, client, monkeypatch):
        """P0(260715 Codex 4차 리뷰) — IN_PROGRESS는 활성 worker만 보유하고 durable
        백업이 없으므로 200으로 뭉개면 Meta 재전송이라는 복구 경로가 사라진다."""
        monkeypatch.setattr(
            dm_receiver, "process_comment_event",
            lambda *a, **k: CommentProcessResult.IN_PROGRESS,
        )
        resp = client.post("/webhook", json=_comment_payload())
        assert resp.status_code >= 500

    def test_retry_owned_returns_200(self, client, monkeypatch):
        """retry_queue.db가 payload를 durable 보유 중이면 Meta 재전송 불필요."""
        monkeypatch.setattr(
            dm_receiver, "process_comment_event",
            lambda *a, **k: CommentProcessResult.RETRY_OWNED,
        )
        resp = client.post("/webhook", json=_comment_payload())
        assert resp.status_code == 200

    def test_exception_returns_5xx(self, client, monkeypatch):
        def _boom(*a, **k):
            raise ConnectionError("event store db locked")
        monkeypatch.setattr(dm_receiver, "process_comment_event", _boom)

        resp = client.post("/webhook", json=_comment_payload())
        assert resp.status_code >= 500

    def test_rejected_not_ready_returns_5xx(self, client, monkeypatch):
        monkeypatch.setattr(
            dm_receiver, "process_comment_event",
            lambda *a, **k: CommentProcessResult.REJECTED_NOT_READY,
        )
        resp = client.post("/webhook", json=_comment_payload())
        assert resp.status_code >= 500

    def test_mixed_batch_one_failure_causes_5xx_for_whole_request(self, client, monkeypatch):
        """같은 웹훅 요청에 댓글 2건, 하나는 성공 하나는 durable-accept 실패 —
        전체를 5xx로 응답해야 실패한 쪽이 Meta 재전송으로 복구될 기회가 생긴다."""
        calls = []

        def _fake(cid, *a, **k):
            calls.append(cid)
            if cid == "c-bad":
                raise ConnectionError("boom")
            return CommentProcessResult.ACCEPTED

        monkeypatch.setattr(dm_receiver, "process_comment_event", _fake)

        payload = {
            "object": "instagram",
            "entry": [{
                "changes": [
                    {"field": "comments", "value": {
                        "id": "c-good", "text": "hi",
                        "from": {"username": "b1", "id": "u1"},
                        "media": {"id": "media1"},
                    }},
                    {"field": "comments", "value": {
                        "id": "c-bad", "text": "hi2",
                        "from": {"username": "b2", "id": "u2"},
                        "media": {"id": "media1"},
                    }},
                ],
            }],
        }
        resp = client.post("/webhook", json=payload)
        assert resp.status_code >= 500
        assert set(calls) == {"c-good", "c-bad"}, "실패와 무관하게 같은 배치의 다른 댓글도 처리는 시도돼야 함"


class TestTwoPhaseProcessing:
    """P0(260715 Codex 4차 리뷰) — 댓글 durable-accept 실패 시 같은 요청에 섞인 DM은
    아예 손대지 않아야 한다. 안 그러면 503으로 인한 Meta 재전송이 DM 쪽에 새로운
    중복(재기록·재알림)을 만들 수 있다."""

    def test_dm_not_processed_when_comment_durable_accept_fails(self, client, monkeypatch):
        monkeypatch.setattr(
            dm_receiver, "process_comment_event",
            lambda *a, **k: (_ for _ in ()).throw(ConnectionError("boom")),
        )
        dm_calls = []
        monkeypatch.setattr(dm_receiver, "record_interaction", lambda *a, **k: dm_calls.append(a) or "rec1")
        monkeypatch.setattr(dm_receiver, "send_telegram", lambda *a, **k: None)

        payload = {
            "object": "instagram",
            "entry": [{
                "changes": [{"field": "comments", "value": {
                    "id": "c1", "text": "hi",
                    "from": {"username": "b1", "id": "u1"},
                    "media": {"id": "media1"},
                }}],
                "messaging": [{
                    "sender": {"id": "sender1"},
                    "message": {"text": "가격 문의"},
                }],
            }],
        }
        resp = client.post("/webhook", json=payload)
        assert resp.status_code >= 500
        assert dm_calls == [], "댓글 durable-accept 실패 시 같은 요청의 DM은 처리되면 안 됨(재전송 시 중복 방지)"

    def test_dm_processed_when_comments_all_succeed(self, client, monkeypatch):
        monkeypatch.setattr(
            dm_receiver, "process_comment_event",
            lambda *a, **k: CommentProcessResult.ACCEPTED,
        )
        dm_calls = []
        monkeypatch.setattr(dm_receiver, "record_interaction", lambda *a, **k: dm_calls.append(a) or "rec1")
        monkeypatch.setattr(dm_receiver, "send_telegram", lambda *a, **k: None)
        monkeypatch.setattr(dm_receiver, "is_repeat_inquiry", lambda *a, **k: False)
        monkeypatch.setattr(dm_receiver, "detect_order", lambda *a, **k: False)
        monkeypatch.setattr(dm_receiver, "detect_price_inquiry", lambda *a, **k: False)

        payload = {
            "object": "instagram",
            "entry": [{
                "changes": [{"field": "comments", "value": {
                    "id": "c1", "text": "hi",
                    "from": {"username": "b1", "id": "u1"},
                    "media": {"id": "media1"},
                }}],
                "messaging": [{
                    "sender": {"id": "sender1"},
                    "message": {"text": "안녕하세요"},
                }],
            }],
        }
        resp = client.post("/webhook", json=payload)
        assert resp.status_code == 200
        assert len(dm_calls) == 1, "댓글이 전부 성공하면 DM도 정상 처리돼야 함"
