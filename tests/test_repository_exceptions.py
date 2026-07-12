"""tests/test_repository_exceptions.py — airtable_repository.py 예외 속성 전달 테스트.

260712 사고 이후: review_batch_committer가 429/5xx/타임아웃만 재시도하고 403/404는
즉시 처리하려면 예외에서 status_code/retry_after_seconds/original_error_type을
읽을 수 있어야 한다. 실제 네트워크 호출 없이 requests 호출부만 mock으로 검증한다.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from modules.infra.airtable_repository import AirtableRepository, _raise
from modules.infra.repository_interface import (
    RepositoryError,
    RepositoryNotFoundError,
    RepositoryUnavailableError,
    RepositoryValidationError,
)


def _http_error(status_code: int, retry_after: str | None = None) -> requests.HTTPError:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = f"error body {status_code}"
    resp.headers = {"Retry-After": retry_after} if retry_after else {}
    exc = requests.HTTPError(f"HTTP {status_code}")
    exc.response = resp
    return exc


class TestRaiseStatusCodePropagation:
    def test_429_raises_repository_error_with_status_code_and_retry_after(self):
        with pytest.raises(RepositoryError) as exc_info:
            _raise(_http_error(429, retry_after="7.5"), "Training_Review_Queue")
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after_seconds == 7.5

    def test_429_without_retry_after_header_has_none(self):
        with pytest.raises(RepositoryError) as exc_info:
            _raise(_http_error(429), "Training_Review_Queue")
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after_seconds is None

    def test_429_with_non_numeric_retry_after_is_none_not_crash(self):
        with pytest.raises(RepositoryError) as exc_info:
            _raise(_http_error(429, retry_after="not-a-number"), "Training_Review_Queue")
        assert exc_info.value.retry_after_seconds is None

    def test_403_raises_unavailable_with_status_code(self):
        with pytest.raises(RepositoryUnavailableError) as exc_info:
            _raise(_http_error(403), "Training_Review_Queue")
        assert exc_info.value.status_code == 403

    def test_401_raises_unavailable_with_status_code(self):
        with pytest.raises(RepositoryUnavailableError) as exc_info:
            _raise(_http_error(401), "Training_Review_Queue")
        assert exc_info.value.status_code == 401

    def test_404_raises_not_found_with_status_code(self):
        with pytest.raises(RepositoryNotFoundError) as exc_info:
            _raise(_http_error(404), "Training_Review_Queue")
        assert exc_info.value.status_code == 404

    def test_422_raises_validation_error_with_status_code(self):
        with pytest.raises(RepositoryValidationError) as exc_info:
            _raise(_http_error(422), "Training_Review_Queue")
        assert exc_info.value.status_code == 422

    def test_500_raises_generic_repository_error_with_status_code(self):
        with pytest.raises(RepositoryError) as exc_info:
            _raise(_http_error(500), "Training_Review_Queue")
        assert exc_info.value.status_code == 500

    def test_503_raises_generic_repository_error_with_status_code(self):
        with pytest.raises(RepositoryError) as exc_info:
            _raise(_http_error(503), "Training_Review_Queue")
        assert exc_info.value.status_code == 503


class TestGetReviewStatusOriginalErrorType:
    def test_timeout_preserves_original_error_type(self):
        repo = AirtableRepository()
        with patch("requests.get", side_effect=requests.exceptions.Timeout("timed out")):
            with pytest.raises(RepositoryUnavailableError) as exc_info:
                repo.get_review_status("rec_test")
        assert exc_info.value.original_error_type == "Timeout"

    def test_connection_error_preserves_original_error_type(self):
        repo = AirtableRepository()
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("refused")):
            with pytest.raises(RepositoryUnavailableError) as exc_info:
                repo.get_review_status("rec_test")
        assert exc_info.value.original_error_type == "ConnectionError"

    def test_404_still_returns_none_not_raise(self):
        """기존 동작 회귀 확인 — 404는 예외가 아니라 None."""
        repo = AirtableRepository()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)
        with patch("requests.get", return_value=mock_resp):
            assert repo.get_review_status("rec_missing") is None

    def test_429_from_real_get_call_has_status_code(self):
        """실제 get_review_status 경로에서도 429가 status_code=429로 올라오는지 확인."""
        repo = AirtableRepository()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "2"}
        mock_resp.text = "rate limited"
        mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(RepositoryError) as exc_info:
                repo.get_review_status("rec_test")
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after_seconds == 2.0
