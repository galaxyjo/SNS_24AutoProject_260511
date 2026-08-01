"""tests/test_airtable_repository_due_scheduled.py — 260801 Step6B
fetch_due_scheduled_post() 검증. 실제 네트워크 호출 없이 requests.get만 mock."""

from unittest.mock import MagicMock, patch

from modules.infra.airtable_repository import AirtableRepository


def test_empty_account_code_ref_returns_none_without_call():
    repo = AirtableRepository()
    with patch("modules.infra.airtable_repository.requests.get") as mock_get:
        assert repo.fetch_due_scheduled_post("", "2026-08-01T08:00:00+09:00") is None
        mock_get.assert_not_called()


def test_due_record_found_maps_fields():
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "records": [{
            "id": "recDue1",
            "fields": {
                "account_code_ref": "IDN-000036", "post_status": "ready",
                "caption": "c", "image_url": "https://example.com/x.png",
            },
        }]
    }
    with patch("modules.infra.airtable_repository.requests.get", return_value=resp) as mock_get, \
         patch("modules.infra.airtable_repository.log_api_call"):
        repo = AirtableRepository()
        result = repo.fetch_due_scheduled_post("IDN-000036", "2026-08-01T08:00:00+09:00")

    assert result is not None
    assert result["post_id"] == "recDue1"
    assert result["account_code_ref"] == "IDN-000036"

    # formula에 계정 한정 + 시간조건이 실제로 포함되는지 확인(필수증명 1·2 근거)
    called_formula = mock_get.call_args.kwargs["params"]["filterByFormula"]
    assert "IDN-000036" in called_formula
    assert "scheduled_upload_at" in called_formula
    assert "canary_run_id" in called_formula
    assert mock_get.call_args.kwargs["params"]["maxRecords"] == 1


def test_no_due_record_returns_none():
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"records": []}
    with patch("modules.infra.airtable_repository.requests.get", return_value=resp), \
         patch("modules.infra.airtable_repository.log_api_call"):
        repo = AirtableRepository()
        assert repo.fetch_due_scheduled_post("IDN-000036", "2026-08-01T08:00:00+09:00") is None
