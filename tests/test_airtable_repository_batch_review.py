"""tests/test_airtable_repository_batch_review.py — 260722 배치 API 속도개선.

AirtableRepository.batch_save_review_decisions()/batch_get_review_status()의 실제
PATCH/GET payload·파라미터·예외 변환을 requests.patch/get mock으로 검증한다(실제 네트워크
호출 없음). 260722 10:31 Codex 리뷰 4번 지적("FakeBatchRepo만으로는 실제 어댑터의
payload/formula/예외 변환이 검증되지 않는다") 반영.

패턴은 기존 tests/test_airtable_repository_field_preflight.py와 동일 — 실제 요청 대신
patch("modules.infra.airtable_repository.requests.get/patch", ...)만 사용한다.
"""

import re
from unittest.mock import MagicMock, patch

import pytest
import requests

from modules.infra.airtable_repository import AirtableRepository
from modules.infra.repository_interface import (
    RepositoryUnavailableError,
    RepositoryValidationError,
)


def _ok_response(json_body=None) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = json_body or {}
    return resp


def _http_error_response(status_code: int, retry_after: str | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = f"error {status_code}"
    resp.headers = {"Retry-After": retry_after} if retry_after else {}
    exc = requests.HTTPError(f"{status_code}")
    exc.response = resp
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = exc
    return mock_resp


class TestBatchSaveReviewDecisionsPayload:
    def test_patch_url_has_no_record_id_suffix(self):
        with patch("modules.infra.airtable_repository.requests.patch", return_value=_ok_response()) as mp:
            AirtableRepository().batch_save_review_decisions([
                {"record_id": "rec1", "decision": "BLOCK", "other_note": ""},
            ])
        url = mp.call_args.args[0]
        assert url.endswith("/Training_Review_Queue")
        assert "rec1" not in url  # 배치 엔드포인트는 URL에 개별 record_id를 넣지 않는다

    def test_records_array_shape_for_two_updates(self):
        with patch("modules.infra.airtable_repository.requests.patch", return_value=_ok_response()) as mp:
            AirtableRepository().batch_save_review_decisions([
                {"record_id": "rec1", "decision": "BLOCK", "other_note": "n1"},
                {"record_id": "rec2", "decision": "PASS", "other_note": ""},
            ])
        body = mp.call_args.kwargs["json"]
        assert set(body.keys()) == {"records"}
        assert len(body["records"]) == 2
        rec1 = next(r for r in body["records"] if r["id"] == "rec1")
        rec2 = next(r for r in body["records"] if r["id"] == "rec2")
        assert rec1["fields"]["review_status"] == "BLOCK"
        assert rec1["fields"]["other_note"] == "n1"
        assert rec2["fields"]["review_status"] == "PASS"
        assert rec2["fields"]["other_note"] == ""

    def test_reviewed_at_is_utc_iso_z_format(self):
        with patch("modules.infra.airtable_repository.requests.patch", return_value=_ok_response()) as mp:
            AirtableRepository().batch_save_review_decisions([
                {"record_id": "rec1", "decision": "BLOCK"},
            ])
        reviewed_at = mp.call_args.kwargs["json"]["records"][0]["fields"]["reviewed_at"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", reviewed_at)

    def test_empty_updates_makes_no_request(self):
        with patch("modules.infra.airtable_repository.requests.patch") as mp:
            AirtableRepository().batch_save_review_decisions([])
        mp.assert_not_called()

    def test_more_than_10_updates_raises_before_any_request(self):
        updates = [{"record_id": f"rec{i}", "decision": "PASS"} for i in range(11)]
        with patch("modules.infra.airtable_repository.requests.patch") as mp:
            with pytest.raises(RepositoryValidationError):
                AirtableRepository().batch_save_review_decisions(updates)
        mp.assert_not_called()

    def test_exactly_10_updates_is_allowed(self):
        updates = [{"record_id": f"rec{i}", "decision": "PASS"} for i in range(10)]
        with patch("modules.infra.airtable_repository.requests.patch", return_value=_ok_response()) as mp:
            AirtableRepository().batch_save_review_decisions(updates)
        assert mp.call_count == 1
        assert len(mp.call_args.kwargs["json"]["records"]) == 10


class TestBatchSaveReviewDecisionsErrorMapping:
    def test_429_preserves_status_code_and_retry_after(self):
        with patch(
            "modules.infra.airtable_repository.requests.patch",
            return_value=_http_error_response(429, retry_after="5"),
        ):
            with pytest.raises(Exception) as exc_info:
                AirtableRepository().batch_save_review_decisions([{"record_id": "rec1", "decision": "BLOCK"}])
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after_seconds == 5.0

    def test_422_maps_to_repository_validation_error(self):
        with patch(
            "modules.infra.airtable_repository.requests.patch",
            return_value=_http_error_response(422),
        ):
            with pytest.raises(RepositoryValidationError) as exc_info:
                AirtableRepository().batch_save_review_decisions([{"record_id": "rec1", "decision": "BLOCK"}])
        assert exc_info.value.status_code == 422

    def test_403_maps_to_repository_unavailable_error(self):
        with patch(
            "modules.infra.airtable_repository.requests.patch",
            return_value=_http_error_response(403),
        ):
            with pytest.raises(RepositoryUnavailableError) as exc_info:
                AirtableRepository().batch_save_review_decisions([{"record_id": "rec1", "decision": "BLOCK"}])
        assert exc_info.value.status_code == 403

    def test_5xx_preserves_status_code(self):
        with patch(
            "modules.infra.airtable_repository.requests.patch",
            return_value=_http_error_response(503),
        ):
            with pytest.raises(Exception) as exc_info:
                AirtableRepository().batch_save_review_decisions([{"record_id": "rec1", "decision": "BLOCK"}])
        assert exc_info.value.status_code == 503

    def test_connection_error_preserves_original_error_type_for_retry_classification(self):
        with patch(
            "modules.infra.airtable_repository.requests.patch",
            side_effect=requests.ConnectionError("reset"),
        ):
            with pytest.raises(RepositoryUnavailableError) as exc_info:
                AirtableRepository().batch_save_review_decisions([{"record_id": "rec1", "decision": "BLOCK"}])
        assert exc_info.value.original_error_type == "ConnectionError"
        assert exc_info.value.status_code is None  # 상태코드 없음 — review_batch_committer가 Timeout류로 재시도 판별

    def test_timeout_preserves_original_error_type(self):
        with patch(
            "modules.infra.airtable_repository.requests.patch",
            side_effect=requests.Timeout("timed out"),
        ):
            with pytest.raises(RepositoryUnavailableError) as exc_info:
                AirtableRepository().batch_save_review_decisions([{"record_id": "rec1", "decision": "BLOCK"}])
        assert exc_info.value.original_error_type == "Timeout"


class TestBatchGetReviewStatusPayload:
    def test_get_url_has_no_record_id_suffix(self):
        with patch(
            "modules.infra.airtable_repository.requests.get",
            return_value=_ok_response({"records": []}),
        ) as mg:
            AirtableRepository().batch_get_review_status(["rec1"])
        url = mg.call_args.args[0]
        assert url.endswith("/Training_Review_Queue")
        assert "rec1" not in url  # record_id는 URL이 아니라 filterByFormula 파라미터로 전달됨

    def test_filter_formula_ors_all_record_ids(self):
        with patch(
            "modules.infra.airtable_repository.requests.get",
            return_value=_ok_response({"records": []}),
        ) as mg:
            AirtableRepository().batch_get_review_status(["rec1", "rec2", "rec3"])
        params = mg.call_args.kwargs["params"]
        formula = params["filterByFormula"]
        assert formula.startswith("OR(") and formula.endswith(")")
        for rid in ("rec1", "rec2", "rec3"):
            assert f"RECORD_ID()='{rid}'" in formula

    def test_page_size_and_fields_params(self):
        with patch(
            "modules.infra.airtable_repository.requests.get",
            return_value=_ok_response({"records": []}),
        ) as mg:
            AirtableRepository().batch_get_review_status(["rec1"])
        params = mg.call_args.kwargs["params"]
        assert params["pageSize"] == 10
        assert params["fields[0]"] == "review_status"

    def test_response_mapping_returns_status_per_id(self):
        response = {"records": [
            {"id": "rec1", "fields": {"review_status": "BLOCK"}},
            {"id": "rec2", "fields": {"review_status": "PASS"}},
        ]}
        with patch("modules.infra.airtable_repository.requests.get", return_value=_ok_response(response)):
            result = AirtableRepository().batch_get_review_status(["rec1", "rec2"])
        assert result == {"rec1": "BLOCK", "rec2": "PASS"}

    def test_missing_id_is_absent_from_returned_dict_not_present_as_none(self):
        """요청한 2개 중 1개만 응답에 있으면, 반환 dict에는 그 1개만 키로 존재해야 한다
        (누락된 쪽은 아예 없음 — 단건 get_review_status의 404 계약과 동일한 의미)."""
        response = {"records": [{"id": "rec1", "fields": {"review_status": "BLOCK"}}]}
        with patch("modules.infra.airtable_repository.requests.get", return_value=_ok_response(response)):
            result = AirtableRepository().batch_get_review_status(["rec1", "rec2"])
        assert result == {"rec1": "BLOCK"}
        assert "rec2" not in result

    def test_present_record_with_empty_fields_maps_to_none(self):
        """Airtable은 비어있는(선택 안 된) 필드를 응답에서 아예 생략한다 — review_status가
        없으면 None으로 매핑돼야 한다(review_batch_committer가 이를 NotFound와 동일하게
        VerificationError로 분류하는 전제)."""
        response = {"records": [{"id": "rec1", "fields": {}}]}
        with patch("modules.infra.airtable_repository.requests.get", return_value=_ok_response(response)):
            result = AirtableRepository().batch_get_review_status(["rec1"])
        assert result == {"rec1": None}

    def test_empty_ids_makes_no_request_returns_empty_dict(self):
        with patch("modules.infra.airtable_repository.requests.get") as mg:
            result = AirtableRepository().batch_get_review_status([])
        assert result == {}
        mg.assert_not_called()

    def test_more_than_10_ids_raises_before_any_request(self):
        ids = [f"rec{i}" for i in range(11)]
        with patch("modules.infra.airtable_repository.requests.get") as mg:
            with pytest.raises(RepositoryValidationError):
                AirtableRepository().batch_get_review_status(ids)
        mg.assert_not_called()


class TestBatchGetReviewStatusErrorMapping:
    def test_429_preserves_status_code_and_retry_after(self):
        with patch(
            "modules.infra.airtable_repository.requests.get",
            return_value=_http_error_response(429, retry_after="3"),
        ):
            with pytest.raises(Exception) as exc_info:
                AirtableRepository().batch_get_review_status(["rec1"])
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after_seconds == 3.0

    def test_403_maps_to_repository_unavailable_error(self):
        with patch(
            "modules.infra.airtable_repository.requests.get",
            return_value=_http_error_response(403),
        ):
            with pytest.raises(RepositoryUnavailableError) as exc_info:
                AirtableRepository().batch_get_review_status(["rec1"])
        assert exc_info.value.status_code == 403

    def test_timeout_preserves_original_error_type(self):
        with patch(
            "modules.infra.airtable_repository.requests.get",
            side_effect=requests.Timeout("timed out"),
        ):
            with pytest.raises(RepositoryUnavailableError) as exc_info:
                AirtableRepository().batch_get_review_status(["rec1"])
        assert exc_info.value.original_error_type == "Timeout"

    def test_connection_error_preserves_original_error_type(self):
        with patch(
            "modules.infra.airtable_repository.requests.get",
            side_effect=requests.ConnectionError("reset"),
        ):
            with pytest.raises(RepositoryUnavailableError) as exc_info:
                AirtableRepository().batch_get_review_status(["rec1"])
        assert exc_info.value.original_error_type == "ConnectionError"
