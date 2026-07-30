"""tests/test_get_account_code_ref_by_media_id.py — 260730 10.5-6단계(댓글 Routing)
Repository 역조회 계약 검증. 0건/공란=""(레거시 취급), 2건 이상=RepositoryValidationError
(임의 첫 레코드 선택 금지), 네트워크/HTTP 오류=구분된 예외. 실제 네트워크 호출 없이
requests.get만 mock."""

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


class TestGetAccountCodeRefByMediaId:
    def test_single_match_returns_account_code_ref(self):
        records = [{"id": "recX", "fields": {"ig_media_id": "999", "account_code_ref": "IDN-000036"}}]
        with patch("modules.infra.airtable_repository.requests.get", return_value=_resp(records)) as mock_get:
            result = AirtableRepository().get_account_code_ref_by_media_id("999")
        assert result == "IDN-000036"
        params = mock_get.call_args.kwargs["params"]
        assert params["filterByFormula"] == "{ig_media_id}='999'"
        assert params["maxRecords"] == 2

    def test_zero_matches_returns_empty_string(self):
        with patch("modules.infra.airtable_repository.requests.get", return_value=_resp([])):
            result = AirtableRepository().get_account_code_ref_by_media_id("unknown-media")
        assert result == ""

    def test_matched_record_with_blank_account_code_ref_returns_empty_string(self):
        """다계정 이전(레거시) 게시물 — 레코드는 있지만 account_code_ref가 비어있음."""
        records = [{"id": "recX", "fields": {"ig_media_id": "999"}}]
        with patch("modules.infra.airtable_repository.requests.get", return_value=_resp(records)):
            result = AirtableRepository().get_account_code_ref_by_media_id("999")
        assert result == ""

    def test_two_matches_raises_validation_error_not_first_record(self):
        records = [
            {"id": "recA", "fields": {"ig_media_id": "999", "account_code_ref": "IDN-A"}},
            {"id": "recB", "fields": {"ig_media_id": "999", "account_code_ref": "IDN-B"}},
        ]
        with patch("modules.infra.airtable_repository.requests.get", return_value=_resp(records)):
            with pytest.raises(RepositoryValidationError):
                AirtableRepository().get_account_code_ref_by_media_id("999")

    def test_empty_media_id_returns_empty_string_without_http_call(self):
        with patch("modules.infra.airtable_repository.requests.get") as mock_get:
            result = AirtableRepository().get_account_code_ref_by_media_id("")
        assert result == ""
        mock_get.assert_not_called()

    def test_none_media_id_returns_empty_string_without_http_call(self):
        with patch("modules.infra.airtable_repository.requests.get") as mock_get:
            result = AirtableRepository().get_account_code_ref_by_media_id(None)
        assert result == ""
        mock_get.assert_not_called()

    def test_network_error_raises_unavailable_not_empty_string(self):
        with patch(
            "modules.infra.airtable_repository.requests.get",
            side_effect=requests.ConnectionError("timeout"),
        ):
            with pytest.raises(RepositoryUnavailableError):
                AirtableRepository().get_account_code_ref_by_media_id("999")

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
                AirtableRepository().get_account_code_ref_by_media_id("999")
