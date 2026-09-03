"""STEP 3-C (260901) — Outbound_Actions 한도카운트 + Account_Registry 한도 + Prospect_Queue
repo 메서드 검증. 실제 네트워크 없이 requests mock."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from modules.infra.airtable_repository import AirtableRepository


def _resp(payload):
    r = MagicMock()
    r.raise_for_status.return_value = None
    r.json.return_value = payload
    return r


def test_count_outbound_actions_today_counts_only_today():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = {"records": [
        {"fields": {"occurred_at": f"{today}T01:00:00Z"}},
        {"fields": {"occurred_at": f"{today}T05:00:00Z"}},
        {"fields": {"occurred_at": "2020-01-01T00:00:00Z"}},
        {"fields": {"occurred_at": ""}},
    ]}
    with patch("modules.infra.airtable_repository.requests.get", return_value=_resp(payload)) as mg, \
         patch("modules.infra.airtable_repository.log_api_call"):
        repo = AirtableRepository()
        n = repo.count_outbound_actions_today("IDN-000041", "follow")
    assert n == 2
    f = mg.call_args.kwargs["params"]["filterByFormula"]
    assert "IDN-000041" in f and "follow" in f


def test_list_outbound_actions_since_filters_by_prefix():
    payload = {"records": [
        {"id": "r1", "fields": {"occurred_at": "2026-09-01T01:00:00Z", "result": "success",
                                "relationship_status": "requested", "target_identifier": "1"}},
        {"id": "r2", "fields": {"occurred_at": "2026-09-01T05:00:00Z", "result": "failed",
                                "relationship_status": "", "target_identifier": "2"}},
        {"id": "r3", "fields": {"occurred_at": "2026-08-31T23:00:00Z", "result": "success",
                                "relationship_status": "requested", "target_identifier": "3"}},
    ]}
    with patch("modules.infra.airtable_repository.requests.get", return_value=_resp(payload)), \
         patch("modules.infra.airtable_repository.log_api_call"):
        repo = AirtableRepository()
        rows = repo.list_outbound_actions_since("IDN-000041", "friend_request", "2026-09-01")
    assert [r["target_identifier"] for r in rows] == ["1", "2"]
    assert rows[0]["relationship_status"] == "requested"


def test_count_outbound_actions_today_requested_only():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = {"records": [
        {"fields": {"occurred_at": f"{today}T01:00:00Z", "result": "success",
                    "relationship_status": "requested"}},
        {"fields": {"occurred_at": f"{today}T02:00:00Z", "result": "failed",
                    "relationship_status": ""}},
        {"fields": {"occurred_at": f"{today}T03:00:00Z", "result": "success",
                    "relationship_status": "requested"}},
    ]}
    with patch("modules.infra.airtable_repository.requests.get", return_value=_resp(payload)), \
         patch("modules.infra.airtable_repository.log_api_call"):
        repo = AirtableRepository()
        assert repo.count_outbound_actions_today("IDN-000041", "friend_request") == 3
        assert repo.count_outbound_actions_today(
            "IDN-000041", "friend_request", requested_only=True) == 2


def test_get_account_outbound_limits_missing_fields_zero():
    with patch("modules.infra.airtable_repository.requests.get",
               return_value=_resp({"records": [{"fields": {}}]})), \
         patch("modules.infra.airtable_repository.log_api_call"):
        repo = AirtableRepository()
        lim = repo.get_account_outbound_limits("IDN-000041")
    assert lim == {"follow": 0, "friend": 0, "comment": 0}


def test_get_account_outbound_limits_reads_values():
    payload = {"records": [{"fields": {
        "daily_follow_limit": 20, "daily_friend_limit": 10, "daily_comment_limit": 5}}]}
    with patch("modules.infra.airtable_repository.requests.get", return_value=_resp(payload)), \
         patch("modules.infra.airtable_repository.log_api_call"):
        repo = AirtableRepository()
        lim = repo.get_account_outbound_limits("IDN-000041")
    assert lim == {"follow": 20, "friend": 10, "comment": 5}


def test_get_account_outbound_limits_ambiguous_returns_zero():
    with patch("modules.infra.airtable_repository.requests.get",
               return_value=_resp({"records": [{"fields": {"daily_follow_limit": 9}},
                                               {"fields": {"daily_follow_limit": 9}}]})), \
         patch("modules.infra.airtable_repository.log_api_call"):
        repo = AirtableRepository()
        assert repo.get_account_outbound_limits("IDN-000041")["follow"] == 0


def test_find_prospect_by_target():
    with patch("modules.infra.airtable_repository.requests.get",
               return_value=_resp({"records": [{"id": "recPQ1"}]})), \
         patch("modules.infra.airtable_repository.log_api_call"):
        repo = AirtableRepository()
        assert repo.find_prospect_by_target("100064", "follow") == "recPQ1"

    with patch("modules.infra.airtable_repository.requests.get",
               return_value=_resp({"records": []})), \
         patch("modules.infra.airtable_repository.log_api_call"):
        repo = AirtableRepository()
        assert repo.find_prospect_by_target("100064", "follow") is None


def test_create_prospect_posts_expected_fields():
    with patch("modules.infra.airtable_repository.requests.post",
               return_value=_resp({"id": "recNEW"})) as mp, \
         patch("modules.infra.airtable_repository.log_api_call"):
        repo = AirtableRepository()
        rid = repo.create_prospect({
            "source_group_code_ref": "PG-016",
            "target_url": "https://www.facebook.com/anna",
            "target_identifier": "anna",
            "action_type": "friend_request",
            "status": "needs_review",
            "score": 48,
        })
    assert rid == "recNEW"
    sent = mp.call_args.kwargs["json"]["fields"]
    assert sent["prospect_code"].startswith("PQ-")
    assert sent["action_type"] == "friend_request"
    assert sent["status"] == "needs_review"
    assert sent["score"] == 48
    assert sent["collected_at"].endswith("Z")


def test_update_prospect_patches():
    with patch("modules.infra.airtable_repository.requests.patch",
               return_value=_resp({"id": "recPQ1"})) as mp, \
         patch("modules.infra.airtable_repository.log_api_call"):
        repo = AirtableRepository()
        repo.update_prospect("recPQ1", {"status": "actioned", "outbound_action_ref": "OA-1234"})
    assert mp.call_args.kwargs["json"]["fields"]["status"] == "actioned"
