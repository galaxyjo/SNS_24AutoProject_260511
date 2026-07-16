"""tests/test_airtable_repository_field_preflight.py — 260716 FP-047/Package1 enforce
전제조건 B: AirtableRepository.verify_field_exists() Metadata API 조회.
실제 네트워크 호출 없이 requests.get만 mock으로 검증한다."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from modules.infra.airtable_repository import AirtableRepository
from modules.infra.repository_interface import RepositoryUnavailableError


def _meta_response(tables: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"tables": tables}
    return resp


class TestVerifyFieldExists:
    def test_field_present_returns_true(self):
        tables = [{"name": "Lead_Interactions", "fields": [{"name": "source_event_id"}, {"name": "lead_status"}]}]
        with patch("modules.infra.airtable_repository.requests.get", return_value=_meta_response(tables)):
            assert AirtableRepository().verify_field_exists("Lead_Interactions", "source_event_id") is True

    def test_field_missing_returns_false(self):
        tables = [{"name": "Lead_Interactions", "fields": [{"name": "lead_status"}]}]
        with patch("modules.infra.airtable_repository.requests.get", return_value=_meta_response(tables)):
            assert AirtableRepository().verify_field_exists("Lead_Interactions", "source_event_id") is False

    def test_table_missing_returns_false(self):
        """테이블 자체가 목록에 없으면 필드도 당연히 없는 것으로 취급 — 별도 예외 아님."""
        tables = [{"name": "Instagram_Posts", "fields": [{"name": "caption"}]}]
        with patch("modules.infra.airtable_repository.requests.get", return_value=_meta_response(tables)):
            assert AirtableRepository().verify_field_exists("Lead_Interactions", "source_event_id") is False

    def test_network_failure_propagates_not_swallowed(self):
        """조회 자체의 실패(네트워크/타임아웃)는 False와 구분돼야 한다 — 호출부가
        "필드 없음 확인됨"과 "확인 자체를 못 함"을 다르게 처리해야 하므로."""
        with patch(
            "modules.infra.airtable_repository.requests.get",
            side_effect=requests.ConnectionError("network down"),
        ):
            with pytest.raises(RepositoryUnavailableError):
                AirtableRepository().verify_field_exists("Lead_Interactions", "source_event_id")

    def test_http_error_propagates(self):
        resp = MagicMock()
        resp.status_code = 403
        resp.text = "forbidden"
        resp.headers = {}
        exc = requests.HTTPError("403")
        exc.response = resp
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = exc
        with patch("modules.infra.airtable_repository.requests.get", return_value=mock_resp):
            with pytest.raises(Exception):
                AirtableRepository().verify_field_exists("Lead_Interactions", "source_event_id")
