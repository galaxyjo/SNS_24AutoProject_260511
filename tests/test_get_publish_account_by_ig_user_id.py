"""tests/test_get_publish_account_by_ig_user_id.py — Bundle B(260726) Repository
역조회 계약 검증. Codex 요구사항: 0건=None, 2건 이상=RepositoryValidationError(임의
첫 레코드 선택 금지), 형식오류=HTTP 호출 없이 None, 네트워크/HTTP 오류=구분된 예외.
실제 네트워크 호출 없이 requests.get만 mock."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from modules.infra.airtable_repository import AirtableRepository
from modules.infra.repository_interface import (
    RepositoryUnavailableError,
    RepositoryValidationError,
)


def _resp(records: list[dict]) -> MagicMock:
    r = MagicMock()
    r.raise_for_status.return_value = None
    r.json.return_value = {"records": records}
    return r


class TestGetPublishAccountByIgUserId:
    def test_single_match_returns_publish_account(self):
        records = [{
            "id": "recX",
            "fields": {
                "account_code": "IDN-000041",
                "api_provider": "facebook_login",
                "ig_user_id": "17841476202821375",
                "credential_key": "YUNA",
            },
        }]
        with patch("modules.infra.airtable_repository.requests.get", return_value=_resp(records)) as mock_get:
            result = AirtableRepository().get_publish_account_by_ig_user_id("17841476202821375")
        assert result == {
            "account_code": "IDN-000041",
            "api_provider": "facebook_login",
            "ig_user_id": "17841476202821375",
            "credential_key": "YUNA",
        }
        params = mock_get.call_args.kwargs["params"]
        assert params["filterByFormula"] == "{ig_user_id}='17841476202821375'"
        assert params["maxRecords"] == 2

    def test_singleselect_api_provider_dict_form_unwrapped(self):
        records = [{"id": "recX", "fields": {
            "account_code": "IDN-000036",
            "api_provider": {"id": "sel1", "name": "instagram_login"},
            "ig_user_id": "17841467725643424",
            "credential_key": "AI",
        }}]
        with patch("modules.infra.airtable_repository.requests.get", return_value=_resp(records)):
            result = AirtableRepository().get_publish_account_by_ig_user_id("17841467725643424")
        assert result["api_provider"] == "instagram_login"

    def test_zero_matches_returns_none(self):
        with patch("modules.infra.airtable_repository.requests.get", return_value=_resp([])):
            result = AirtableRepository().get_publish_account_by_ig_user_id("99999999999999999")
        assert result is None

    def test_two_matches_raises_validation_error_not_first_record(self):
        records = [
            {"id": "recA", "fields": {"account_code": "IDN-A", "ig_user_id": "111"}},
            {"id": "recB", "fields": {"account_code": "IDN-B", "ig_user_id": "111"}},
        ]
        with patch("modules.infra.airtable_repository.requests.get", return_value=_resp(records)):
            with pytest.raises(RepositoryValidationError):
                AirtableRepository().get_publish_account_by_ig_user_id("111")

    def test_empty_ig_user_id_returns_none_without_http_call(self):
        with patch("modules.infra.airtable_repository.requests.get") as mock_get:
            result = AirtableRepository().get_publish_account_by_ig_user_id("")
        assert result is None
        mock_get.assert_not_called()

    def test_non_numeric_ig_user_id_returns_none_without_http_call(self):
        with patch("modules.infra.airtable_repository.requests.get") as mock_get:
            result = AirtableRepository().get_publish_account_by_ig_user_id("abc123")
        assert result is None
        mock_get.assert_not_called()

    def test_none_ig_user_id_returns_none_without_http_call(self):
        with patch("modules.infra.airtable_repository.requests.get") as mock_get:
            result = AirtableRepository().get_publish_account_by_ig_user_id(None)
        assert result is None
        mock_get.assert_not_called()

    def test_network_error_raises_unavailable_not_none(self):
        with patch(
            "modules.infra.airtable_repository.requests.get",
            side_effect=requests.ConnectionError("timeout"),
        ):
            with pytest.raises(RepositoryUnavailableError):
                AirtableRepository().get_publish_account_by_ig_user_id("17841476202821375")

    def test_http_error_propagates(self):
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "server error"
        resp.headers = {}
        exc = requests.HTTPError("500")
        exc.response = resp
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = exc
        with patch("modules.infra.airtable_repository.requests.get", return_value=mock_resp):
            with pytest.raises(Exception):
                AirtableRepository().get_publish_account_by_ig_user_id("17841476202821375")
