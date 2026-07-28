"""tests/test_dm_receiver_webhook.py — P0(260715 Codex 3차 리뷰) 검증:
댓글 이벤트가 durable하게 접수되지 않았으면 200으로 뭉개지 않고 5xx를 반환해
Meta가 재전송하도록 유도해야 한다.

ERR-082(260727): Signature 검증 삽입 이후, 이 파일의 모든 POST 요청은 Route 전용
App Secret으로 서명된 Signed Request여야 한다(_signed_post 헬퍼). 이 파일은 또한
webhook_signature.py의 Route 레벨 보안 회귀(Fail-closed/Route별 Secret 분리/
Business Logic 무단진입 0건) 테스트를 담당한다(tests/test_dm_account_routing.py는
계정 Routing 행위 자체에 집중, 보안 매트릭스는 여기로 통일)."""

import hashlib
import hmac
import json

import pytest

import modules.dm.dm_receiver as dm_receiver
from modules.comment.comment_auto_reply import CommentProcessResult

GALAXY_SECRET = "test-galaxy-secret"
AI_SECRET = "test-ai-secret"
GALAXY_TOKEN = "test-galaxy-token"
AI_TOKEN = "test-ai-token"


@pytest.fixture
def client(monkeypatch):
    dm_receiver.app.config["TESTING"] = True
    monkeypatch.setattr(dm_receiver, "WEBHOOK_APP_SECRET", GALAXY_SECRET)
    monkeypatch.setattr(dm_receiver, "AI_WEBHOOK_APP_SECRET", AI_SECRET)
    monkeypatch.setattr(dm_receiver, "VERIFY_TOKEN", GALAXY_TOKEN)
    monkeypatch.setattr(dm_receiver, "AI_WEBHOOK_VERIFY_TOKEN", AI_TOKEN)
    return dm_receiver.app.test_client()


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _signed_post(client, path, payload, secret=GALAXY_SECRET, raw_body=None):
    """유효한 Route 전용 서명을 붙여 POST한다. raw_body가 주어지면 payload 대신 그 원본
    bytes로 서명·전송한다(변조/비-JSON 케이스 테스트용)."""
    body = raw_body if raw_body is not None else json.dumps(payload).encode("utf-8")
    headers = {}
    if secret is not None:
        headers["X-Hub-Signature-256"] = _sign(body, secret)
    return client.post(path, data=body, content_type="application/json", headers=headers)


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
        resp = _signed_post(client, "/webhook", _comment_payload())
        assert resp.status_code == 200

    def test_in_progress_returns_5xx(self, client, monkeypatch):
        """P0(260715 Codex 4차 리뷰) — IN_PROGRESS는 활성 worker만 보유하고 durable
        백업이 없으므로 200으로 뭉개면 Meta 재전송이라는 복구 경로가 사라진다."""
        monkeypatch.setattr(
            dm_receiver, "process_comment_event",
            lambda *a, **k: CommentProcessResult.IN_PROGRESS,
        )
        resp = _signed_post(client, "/webhook", _comment_payload())
        assert resp.status_code >= 500

    def test_retry_owned_returns_200(self, client, monkeypatch):
        """retry_queue.db가 payload를 durable 보유 중이면 Meta 재전송 불필요."""
        monkeypatch.setattr(
            dm_receiver, "process_comment_event",
            lambda *a, **k: CommentProcessResult.RETRY_OWNED,
        )
        resp = _signed_post(client, "/webhook", _comment_payload())
        assert resp.status_code == 200

    def test_exception_returns_5xx(self, client, monkeypatch):
        def _boom(*a, **k):
            raise ConnectionError("event store db locked")
        monkeypatch.setattr(dm_receiver, "process_comment_event", _boom)

        resp = _signed_post(client, "/webhook", _comment_payload())
        assert resp.status_code >= 500

    def test_rejected_not_ready_returns_5xx(self, client, monkeypatch):
        monkeypatch.setattr(
            dm_receiver, "process_comment_event",
            lambda *a, **k: CommentProcessResult.REJECTED_NOT_READY,
        )
        resp = _signed_post(client, "/webhook", _comment_payload())
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
        resp = _signed_post(client, "/webhook", payload)
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
        resp = _signed_post(client, "/webhook", payload)
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
        resp = _signed_post(client, "/webhook", payload)
        assert resp.status_code == 200
        assert len(dm_calls) == 1, "댓글이 전부 성공하면 DM도 정상 처리돼야 함"


# ── ERR-082(260727) Signature 보안 회귀 ──────────────────────────────────────

def _no_business_logic_stubs(monkeypatch):
    calls = {"record": [], "telegram": [], "comment": []}
    monkeypatch.setattr(dm_receiver, "record_interaction", lambda *a, **k: calls["record"].append(a) or "rec1")
    monkeypatch.setattr(dm_receiver, "send_telegram", lambda *a, **k: calls["telegram"].append(a))
    monkeypatch.setattr(dm_receiver, "process_comment_event", lambda *a, **k: calls["comment"].append(a) or CommentProcessResult.ACCEPTED)
    return calls


class TestSignatureFailClosedGalaxyRoute:
    """POST /webhook(Galaxy/yuna) — 서명 오류 매트릭스, 전부 403 + Business Logic 0회."""

    def test_no_signature_header_rejected(self, client, monkeypatch):
        calls = _no_business_logic_stubs(monkeypatch)
        resp = _signed_post(client, "/webhook", _comment_payload(), secret=None)
        assert resp.status_code == 403
        assert calls == {"record": [], "telegram": [], "comment": []}

    def test_wrong_secret_rejected(self, client, monkeypatch):
        calls = _no_business_logic_stubs(monkeypatch)
        resp = _signed_post(client, "/webhook", _comment_payload(), secret=AI_SECRET)
        assert resp.status_code == 403, "AI Secret으로 서명한 요청은 Galaxy Route에서 거부돼야 함(교차수용 금지)"
        assert calls == {"record": [], "telegram": [], "comment": []}

    def test_bad_prefix_rejected(self, client, monkeypatch):
        calls = _no_business_logic_stubs(monkeypatch)
        body = json.dumps(_comment_payload()).encode("utf-8")
        bad_sig = "sha1=" + hmac.new(GALAXY_SECRET.encode(), body, hashlib.sha256).hexdigest()
        resp = client.post("/webhook", data=body, content_type="application/json",
                            headers={"X-Hub-Signature-256": bad_sig})
        assert resp.status_code == 403
        assert calls == {"record": [], "telegram": [], "comment": []}

    def test_bad_digest_length_rejected(self, client, monkeypatch):
        calls = _no_business_logic_stubs(monkeypatch)
        body = json.dumps(_comment_payload()).encode("utf-8")
        resp = client.post("/webhook", data=body, content_type="application/json",
                            headers={"X-Hub-Signature-256": "sha256=abcd1234"})
        assert resp.status_code == 403
        assert calls == {"record": [], "telegram": [], "comment": []}

    def test_tampered_payload_rejected(self, client, monkeypatch):
        calls = _no_business_logic_stubs(monkeypatch)
        body = json.dumps(_comment_payload()).encode("utf-8")
        valid_sig = _sign(body, GALAXY_SECRET)
        tampered_body = body + b" "
        resp = client.post("/webhook", data=tampered_body, content_type="application/json",
                            headers={"X-Hub-Signature-256": valid_sig})
        assert resp.status_code == 403
        assert calls == {"record": [], "telegram": [], "comment": []}

    def test_route_secret_unset_rejects_only_this_route(self, client, monkeypatch):
        """Galaxy Secret이 미설정(빈 문자열)이어도 Flask App 자체는 살아있고, 이
        Route만 403을 반환해야 한다(Startup Crash 없음, 다른 Route에 영향 없음)."""
        monkeypatch.setattr(dm_receiver, "WEBHOOK_APP_SECRET", "")
        calls = _no_business_logic_stubs(monkeypatch)
        resp = _signed_post(client, "/webhook", _comment_payload(), secret=GALAXY_SECRET)
        assert resp.status_code == 403
        assert calls == {"record": [], "telegram": [], "comment": []}

    def test_valid_signature_with_invalid_json_returns_400(self, client):
        raw = b"not-json-at-all"
        resp = _signed_post(client, "/webhook", payload=None, secret=GALAXY_SECRET, raw_body=raw)
        assert resp.status_code == 400


class TestSignatureFailClosedAiRoute:
    """POST /webhook/ai-strategist — Galaxy와 완전히 분리된 자기 Secret만 수용."""

    def test_own_secret_accepted(self, client, monkeypatch):
        monkeypatch.setattr(
            dm_receiver, "process_comment_event",
            lambda *a, **k: CommentProcessResult.ACCEPTED,
        )
        resp = _signed_post(client, "/webhook/ai-strategist", _comment_payload(), secret=AI_SECRET)
        assert resp.status_code == 200

    def test_galaxy_secret_rejected_on_ai_route(self, client, monkeypatch):
        calls = _no_business_logic_stubs(monkeypatch)
        resp = _signed_post(client, "/webhook/ai-strategist", _comment_payload(), secret=GALAXY_SECRET)
        assert resp.status_code == 403, "Galaxy Secret으로 서명한 요청은 AI Route에서 거부돼야 함"
        assert calls == {"record": [], "telegram": [], "comment": []}

    def test_no_signature_rejected(self, client, monkeypatch):
        calls = _no_business_logic_stubs(monkeypatch)
        resp = _signed_post(client, "/webhook/ai-strategist", _comment_payload(), secret=None)
        assert resp.status_code == 403
        assert calls == {"record": [], "telegram": [], "comment": []}


class TestGetVerifyTokenIsolation:
    """GET /webhook, GET /webhook/ai-strategist — Verify Token 교차 사용 거부."""

    def test_galaxy_token_on_galaxy_route_succeeds(self, client):
        resp = client.get("/webhook", query_string={
            "hub.mode": "subscribe", "hub.verify_token": GALAXY_TOKEN, "hub.challenge": "ch1",
        })
        assert resp.status_code == 200
        assert resp.get_data(as_text=True) == "ch1"

    def test_ai_token_on_ai_route_succeeds(self, client):
        resp = client.get("/webhook/ai-strategist", query_string={
            "hub.mode": "subscribe", "hub.verify_token": AI_TOKEN, "hub.challenge": "ch2",
        })
        assert resp.status_code == 200
        assert resp.get_data(as_text=True) == "ch2"

    def test_galaxy_token_on_ai_route_rejected(self, client):
        resp = client.get("/webhook/ai-strategist", query_string={
            "hub.mode": "subscribe", "hub.verify_token": GALAXY_TOKEN, "hub.challenge": "ch3",
        })
        assert resp.status_code == 403

    def test_ai_token_on_galaxy_route_rejected(self, client):
        resp = client.get("/webhook", query_string={
            "hub.mode": "subscribe", "hub.verify_token": AI_TOKEN, "hub.challenge": "ch4",
        })
        assert resp.status_code == 403

    def test_missing_token_rejected(self, client):
        resp = client.get("/webhook", query_string={"hub.mode": "subscribe", "hub.challenge": "ch5"})
        assert resp.status_code == 403
