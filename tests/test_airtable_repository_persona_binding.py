"""tests/test_airtable_repository_persona_binding.py — 260801 Step4 T1 Account Binding Gate.

AirtableRepository.get_active_persona_by_account_code_v2()의 Pagination·Exact Record ID
비교·Repository 책임경계(PER-002 비하드코딩)를 검증한다. 실제 네트워크 호출 없이
requests.get만 mock으로 검증한다. 기존 get_persona_by_account_code()와 그 Caller는
이 테스트 파일의 대상이 아니다(무수정 확인은 별도 git diff Evidence로 다룸).
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from modules.infra.airtable_repository import AirtableRepository
from modules.infra.repository_interface import (
    RepositoryUnavailableError,
    RepositoryValidationError,
)

ACC_OK = {"records": [{"id": "recREALACCOUNT01"}]}


def _mock_get(account_resp, persona_pages):
    """persona_pages: list of response bodies returned in order for Persona_Profile calls."""
    pages = iter(persona_pages)

    def _get(url, headers=None, params=None, timeout=None):
        m = MagicMock()
        m.status_code = 200
        m.raise_for_status.return_value = None
        if "Account_Registry" in url:
            m.json.return_value = account_resp
        else:
            m.json.return_value = next(pages)
        return m

    return _get


def _persona(record_id, account_ids, active=True, persona_code="PER-002", language=None):
    fields = {"account_code_ref": account_ids, "active": active, "persona_code": persona_code}
    if language is not None:
        fields["language"] = language
    return {"id": record_id, "fields": fields}


class TestPagination:
    def test_first_page_exact_match(self):
        page1 = {"records": [_persona("recP1", ["recREALACCOUNT01"])]}
        with patch("modules.infra.airtable_repository.requests.get", side_effect=_mock_get(ACC_OK, [page1])):
            result = AirtableRepository().get_active_persona_by_account_code_v2("IDN-000036")
        assert result is not None
        assert result["persona_code"] == "PER-002"

    def test_language_field_returned(self):
        """260801 6E — Persona_Profile.language를 PersonaProfile에 실어 반환해야
        Adapter가 언어 Gate를 적용할 수 있다."""
        page1 = {"records": [_persona("recP1", ["recREALACCOUNT01"], language="ko")]}
        with patch("modules.infra.airtable_repository.requests.get", side_effect=_mock_get(ACC_OK, [page1])):
            result = AirtableRepository().get_active_persona_by_account_code_v2("IDN-000036")
        assert result is not None
        assert result["language"] == "ko"

    def test_language_field_absent_defaults_empty(self):
        page1 = {"records": [_persona("recP1", ["recREALACCOUNT01"])]}
        with patch("modules.infra.airtable_repository.requests.get", side_effect=_mock_get(ACC_OK, [page1])):
            result = AirtableRepository().get_active_persona_by_account_code_v2("IDN-000036")
        assert result is not None
        assert result.get("language", "") == ""

    def test_match_found_after_first_page_offset(self):
        page1 = {"records": [_persona(f"recFiller{i}", ["recUNRELATED"]) for i in range(100)], "offset": "off1"}
        page2 = {"records": [_persona("recP2", ["recREALACCOUNT01"])]}
        with patch("modules.infra.airtable_repository.requests.get", side_effect=_mock_get(ACC_OK, [page1, page2])):
            result = AirtableRepository().get_active_persona_by_account_code_v2("IDN-000036")
        assert result is not None
        assert result["persona_code"] == "PER-002"

    def test_duplicate_exact_match_across_pages_raises(self):
        page1 = {"records": [_persona("recDup1", ["recREALACCOUNT01"])], "offset": "off1"}
        page2 = {"records": [_persona("recDup2", ["recREALACCOUNT01"])]}
        with patch("modules.infra.airtable_repository.requests.get", side_effect=_mock_get(ACC_OK, [page1, page2])):
            with pytest.raises(RepositoryValidationError):
                AirtableRepository().get_active_persona_by_account_code_v2("IDN-000036")


class TestExactMatchBoundary:
    def test_partial_match_persona_excluded(self):
        page1 = {"records": [_persona("recDecoy", ["recOTHER_NOT_MATCH"])]}
        with patch("modules.infra.airtable_repository.requests.get", side_effect=_mock_get(ACC_OK, [page1])):
            result = AirtableRepository().get_active_persona_by_account_code_v2("IDN-000036")
        assert result is None

    def test_zero_candidates_returns_none(self):
        page1 = {"records": []}
        with patch("modules.infra.airtable_repository.requests.get", side_effect=_mock_get(ACC_OK, [page1])):
            result = AirtableRepository().get_active_persona_by_account_code_v2("IDN-000036")
        assert result is None

    def test_inactive_persona_excluded(self):
        page1 = {"records": [_persona("recInactive", ["recREALACCOUNT01"], active=False)]}
        with patch("modules.infra.airtable_repository.requests.get", side_effect=_mock_get(ACC_OK, [page1])):
            result = AirtableRepository().get_active_persona_by_account_code_v2("IDN-000036")
        assert result is None

    def test_malformed_account_code_ref_type_excluded_not_crash(self):
        page1 = {"records": [{"id": "recBad", "fields": {"account_code_ref": "recREALACCOUNT01", "active": True, "persona_code": "PER-002"}}]}
        with patch("modules.infra.airtable_repository.requests.get", side_effect=_mock_get(ACC_OK, [page1])):
            result = AirtableRepository().get_active_persona_by_account_code_v2("IDN-000036")
        assert result is None


class TestFailureAndResponsibility:
    def test_airtable_api_failure_propagates(self):
        def _get_fail(url, headers=None, params=None, timeout=None):
            if "Account_Registry" in url:
                m = MagicMock()
                m.status_code = 200
                m.raise_for_status.return_value = None
                m.json.return_value = ACC_OK
                return m
            raise requests.RequestException("boom")

        with patch("modules.infra.airtable_repository.requests.get", side_effect=_get_fail):
            with pytest.raises(RepositoryUnavailableError):
                AirtableRepository().get_active_persona_by_account_code_v2("IDN-000036")

    def test_repository_does_not_hardcode_per_002(self):
        """Repository는 persona_code 값과 무관하게 exact+active 단일매치면 반환해야 한다
        (PER-002 여부 검증은 Adapter 책임 — Repository가 하드코딩하면 이 테스트가 실패한다)."""
        page1 = {"records": [_persona("recOtherPersona", ["recREALACCOUNT01"], persona_code="PER-999")]}
        with patch("modules.infra.airtable_repository.requests.get", side_effect=_mock_get(ACC_OK, [page1])):
            result = AirtableRepository().get_active_persona_by_account_code_v2("IDN-000036")
        assert result is not None
        assert result["persona_code"] == "PER-999"
