"""tests/test_aijomoojin_scheduled_publish_job.py — 260801 Step6B 완전자동
예약게시 오케스트레이터 통합 테스트. 실제 Airtable·Meta 호출 없이 Fake
Repository + Fake publish_single_fn으로 검증한다. 각 테스트는 tmp_path 격리
publish_ledger DB를 사용해 Runtime DB를 건드리지 않는다.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from modules.common import publish_ledger
from modules.common.aijomoojin_scheduled_publish_job import run_aijomoojin_scheduled_publish


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    """publish_ledger._DB_PATH를 tmp_path로 바꿔 이 파일의 모든 테스트가 격리된
    DB를 쓰게 한다(오케스트레이터 내부는 db_path 인자를 안 받으므로 모듈
    상수를 monkeypatch)."""
    monkeypatch.setattr(publish_ledger, "_DB_PATH", tmp_path / "ledger.db")


def _due_post(rid="rec1", account_code_ref="IDN-000036"):
    return {
        "post_id": rid, "image_url": "https://example.com/img.png", "caption": "c",
        "hashtag": "", "post_status": "ready", "ig_media_id": "",
        "account_code_ref": account_code_ref, "data_classification": "", "canary_run_id": "",
    }


def _fake_repo(due_post, persona_ok=True, claim_result=True, mark_result_raises=None):
    calls = {"fetch_due": 0, "persona_lookup": [], "claim": [], "mark_post_result": []}

    class _FakeRepo:
        def fetch_due_scheduled_post(self, account_code_ref, now_iso):
            calls["fetch_due"] += 1
            return due_post

        def get_active_persona_by_account_code_v2(self, account_code):
            calls["persona_lookup"].append(account_code)
            return {"persona_code": "PER-002"} if persona_ok else None

        def claim_post_for_upload(self, post_id):
            calls["claim"].append(post_id)
            return claim_result

        def mark_post_result(self, post_id, result):
            calls["mark_post_result"].append((post_id, dict(result)))
            if mark_result_raises:
                raise mark_result_raises

    return _FakeRepo(), calls


class TestFutureAndDueSelection:
    def test_no_due_record_returns_no_due_status(self):
        repo, calls = _fake_repo(due_post=None)
        publish_calls = []
        result = run_aijomoojin_scheduled_publish(repo, lambda *a: publish_calls.append(1) or {"ok": True})
        assert result["status"] == "no_due_record"
        assert publish_calls == []  # 필수증명 1: due가 없으면(미래 예약 포함) 게시 0회

    def test_due_record_selected_and_published(self):
        repo, calls = _fake_repo(due_post=_due_post())
        publish_calls = []

        def fake_publish(rid, image_url, caption, token, ig_user_id):
            publish_calls.append((rid, image_url, caption))
            return {"ok": True, "ig_media_id": "m1"}

        result = run_aijomoojin_scheduled_publish(repo, fake_publish)

        assert calls["fetch_due"] == 1  # 필수증명 2: due 1건만 선택(호출 1회)
        assert calls["claim"] == ["rec1"]
        assert publish_calls == [("rec1", "https://example.com/img.png", "c")]
        assert result["status"] == "published"
        assert result["ig_media_id"] == "m1"


class TestDedup:
    def test_duplicate_reserve_blocks_second_run_zero_publish(self):
        """필수증명 3: 동일 content_id+account_code+instagram 재실행 시
        publish_single이 다시 호출되지 않는다."""
        repo, calls = _fake_repo(due_post=_due_post())
        publish_calls = []

        def fake_publish(rid, image_url, caption, token, ig_user_id):
            publish_calls.append(1)
            return {"ok": True, "ig_media_id": "m1"}

        r1 = run_aijomoojin_scheduled_publish(repo, fake_publish)
        assert r1["status"] == "published"
        assert len(publish_calls) == 1

        r2 = run_aijomoojin_scheduled_publish(repo, fake_publish)
        assert r2["status"] == "duplicate_blocked"
        assert len(publish_calls) == 1  # 두 번째 실행에서 추가 게시 0회


class TestReceiptSeparation:
    def test_ig_success_airtable_failure_no_republish(self):
        """필수증명 4·5: Instagram 성공 ID가 Ledger에 먼저 저장되고, Airtable
        mark_post_result 실패 시 publish_single이 재호출되지 않는다."""
        repo, calls = _fake_repo(due_post=_due_post(), mark_result_raises=RuntimeError("airtable down"))
        publish_calls = []

        def fake_publish(rid, image_url, caption, token, ig_user_id):
            publish_calls.append(1)
            return {"ok": True, "ig_media_id": "m1"}

        result = run_aijomoojin_scheduled_publish(repo, fake_publish)

        assert result["status"] == "receipt_sync_pending"
        assert result["ig_media_id"] == "m1"
        assert len(publish_calls) == 1  # Airtable 실패해도 Instagram 재호출 0회

        ledger_state = publish_ledger.get_state(result["ledger_key"])
        assert ledger_state["state"] == "RECEIPT_SYNC_PENDING"
        assert ledger_state["instagram_post_id"] == "m1"  # ID 유실 안 됨

    def test_outcome_unknown_no_republish(self):
        repo, calls = _fake_repo(due_post=_due_post())
        publish_calls = []

        def fake_publish(rid, image_url, caption, token, ig_user_id):
            publish_calls.append(1)
            return {"ok": False, "outcome_unknown": True, "creation_id": "c1"}

        result = run_aijomoojin_scheduled_publish(repo, fake_publish)
        assert result["status"] == "outcome_unknown"
        assert len(publish_calls) == 1

    def test_definitive_failure_no_republish(self):
        repo, calls = _fake_repo(due_post=_due_post())
        publish_calls = []

        def fake_publish(rid, image_url, caption, token, ig_user_id):
            publish_calls.append(1)
            return {"ok": False, "error": "http_400"}

        result = run_aijomoojin_scheduled_publish(repo, fake_publish)
        assert result["status"] == "failed"
        assert len(publish_calls) == 1


class TestPersonaGate:
    def test_persona_missing_blocks_publish(self):
        repo, calls = _fake_repo(due_post=_due_post(), persona_ok=False)
        publish_calls = []
        result = run_aijomoojin_scheduled_publish(repo, lambda *a: publish_calls.append(1) or {"ok": True})
        assert result["status"] == "persona_gate_blocked"
        assert publish_calls == []
        assert calls["claim"] == []


class TestOtherAccountScopeDefensive:
    def test_defensive_block_if_repo_returns_other_account(self):
        """fetch_due_scheduled_post는 계정 한정으로 설계됐지만, Repository
        계약 위반(다른 계정 레코드 반환) 상황에서도 오케스트레이터가 방어적으로
        차단하는지 확인한다 — 필수증명 6과 직결."""
        repo, calls = _fake_repo(due_post=_due_post(rid="rec9", account_code_ref="IDN-000041"))
        publish_calls = []
        result = run_aijomoojin_scheduled_publish(repo, lambda *a: publish_calls.append(1) or {"ok": True})
        assert result["status"] == "unexpected_account_defensive_block"
        assert publish_calls == []
        assert calls["persona_lookup"] == []


class TestNoSecretsInResult:
    def test_result_dict_never_contains_token(self):
        """필수증명 8: 반환값·Ledger 어디에도 access_token 문자열이 없어야 한다."""
        repo, calls = _fake_repo(due_post=_due_post())

        def fake_publish(rid, image_url, caption, token, ig_user_id):
            assert token == ""  # 오케스트레이터는 credential을 스스로 만들지 않음(주입만)
            return {"ok": True, "ig_media_id": "m1"}

        result = run_aijomoojin_scheduled_publish(repo, fake_publish)
        assert "token" not in str(result).lower()
        ledger_state = publish_ledger.get_state(result["ledger_key"])
        assert "token" not in str(ledger_state).lower()
