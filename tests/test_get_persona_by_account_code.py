"""tests/test_get_persona_by_account_code.py — 260730 10.5-5단계(Persona 연결)
Repository 역조회 계약 검증. Persona_Profile.account_code_ref는 Linked Record
타입이라 Account_Registry의 Persona_Profile 링크 필드를 통해 역조회한다.
0건/링크없음/inactive=None, 링크 2건 이상=RepositoryValidationError(임의 첫
레코드 선택 금지), 네트워크/HTTP 오류=구분된 예외. 실제 네트워크 호출 없이
requests.get만 mock."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from modules.infra.airtable_repository import AirtableRepository
from modules.infra.repository_interface import (
    RepositoryUnavailableError,
    RepositoryValidationError,
)


def _account_resp(persona_ids: list[str] | None) -> MagicMock:
    r = MagicMock()
    r.raise_for_status.return_value = None
    fields = {"account_code": "IDN-000041"}
    if persona_ids is not None:
        fields["Persona_Profile"] = persona_ids
    r.json.return_value = {"records": [{"id": "recAcct", "fields": fields}]}
    return r


def _account_resp_zero() -> MagicMock:
    r = MagicMock()
    r.raise_for_status.return_value = None
    r.json.return_value = {"records": []}
    return r


def _persona_resp(fields: dict) -> MagicMock:
    r = MagicMock()
    r.raise_for_status.return_value = None
    r.json.return_value = {"id": "recPersona", "fields": fields}
    return r


class TestGetPersonaByAccountCode:
    def test_account_not_found_returns_none(self):
        with patch("modules.infra.airtable_repository.requests.get", return_value=_account_resp_zero()):
            result = AirtableRepository().get_persona_by_account_code("IDN-999999")
        assert result is None

    def test_no_linked_persona_returns_none(self):
        with patch("modules.infra.airtable_repository.requests.get", return_value=_account_resp([])):
            result = AirtableRepository().get_persona_by_account_code("IDN-000041")
        assert result is None

    def test_missing_persona_field_returns_none(self):
        """Account_Registry 레코드에 Persona_Profile 필드 자체가 없는 경우(공란)."""
        with patch("modules.infra.airtable_repository.requests.get", return_value=_account_resp(None)):
            result = AirtableRepository().get_persona_by_account_code("IDN-000041")
        assert result is None

    def test_two_linked_personas_raises_validation_error_not_first_record(self):
        with patch("modules.infra.airtable_repository.requests.get", return_value=_account_resp(["recP1", "recP2"])):
            with pytest.raises(RepositoryValidationError):
                AirtableRepository().get_persona_by_account_code("IDN-000041")

    def test_single_linked_inactive_persona_returns_none(self):
        account_resp = _account_resp(["recP1"])
        persona_resp = _persona_resp({
            "persona_code": "PER-001", "tone_style": "친근함",
            "greeting_template": "", "followup_template": "", "active": False,
        })
        with patch(
            "modules.infra.airtable_repository.requests.get",
            side_effect=[account_resp, persona_resp],
        ):
            result = AirtableRepository().get_persona_by_account_code("IDN-000041")
        assert result is None

    def test_single_linked_active_persona_returns_fields(self):
        account_resp = _account_resp(["recP1"])
        persona_resp = _persona_resp({
            "persona_code": "PER-001",
            "tone_style": "친근하고 캐주얼한 말투",
            "greeting_template": "안녕하세요 :)",
            "followup_template": "혹시 더 궁금하신 점 있으실까요?",
            "active": True,
        })
        with patch(
            "modules.infra.airtable_repository.requests.get",
            side_effect=[account_resp, persona_resp],
        ) as mock_get:
            result = AirtableRepository().get_persona_by_account_code("IDN-000041")
        assert result == {
            "persona_code": "PER-001",
            "tone_style": "친근하고 캐주얼한 말투",
            "greeting_template": "안녕하세요 :)",
            "followup_template": "혹시 더 궁금하신 점 있으실까요?",
        }
        # 두 번째 호출이 Persona_Profile/recP1 단건 GET인지 확인
        second_call_url = mock_get.call_args_list[1].args[0]
        assert second_call_url.endswith("Persona_Profile/recP1")

    def test_empty_account_code_returns_none_without_http_call(self):
        with patch("modules.infra.airtable_repository.requests.get") as mock_get:
            result = AirtableRepository().get_persona_by_account_code("")
        assert result is None
        mock_get.assert_not_called()

    def test_none_account_code_returns_none_without_http_call(self):
        with patch("modules.infra.airtable_repository.requests.get") as mock_get:
            result = AirtableRepository().get_persona_by_account_code(None)
        assert result is None
        mock_get.assert_not_called()

    def test_network_error_on_account_lookup_raises_unavailable(self):
        with patch(
            "modules.infra.airtable_repository.requests.get",
            side_effect=requests.ConnectionError("timeout"),
        ):
            with pytest.raises(RepositoryUnavailableError):
                AirtableRepository().get_persona_by_account_code("IDN-000041")

    def test_network_error_on_persona_lookup_raises_unavailable(self):
        account_resp = _account_resp(["recP1"])
        with patch(
            "modules.infra.airtable_repository.requests.get",
            side_effect=[account_resp, requests.ConnectionError("timeout")],
        ):
            with pytest.raises(RepositoryUnavailableError):
                AirtableRepository().get_persona_by_account_code("IDN-000041")
