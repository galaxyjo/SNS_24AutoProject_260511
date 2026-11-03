"""AirtableRepository 재사용 보충용 조회 메서드(261103) — requests 를 가짜로 바꿔 formula·페이지 순회·검증만 확인한다."""

import pytest

from modules.infra import airtable_repository as ar
from modules.infra.repository_interface import RepositoryValidationError


class _Resp:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


@pytest.fixture
def repo(monkeypatch):
    monkeypatch.setattr(ar, "log_api_call", lambda *a, **k: None)
    r = ar.AirtableRepository()
    r.calls = []
    return r


def _install(monkeypatch, repo, pages):
    pages = list(pages)

    def fake_get(url, headers=None, params=None, timeout=None):
        repo.calls.append(params)
        return _Resp(pages.pop(0))

    monkeypatch.setattr(ar.requests, "get", fake_get)


def test_count_ready_posts_by_account_paginates_and_uses_poller_filter(repo, monkeypatch):
    _install(monkeypatch, repo, [
        {"records": [{"id": "1", "fields": {"account_code_ref": "IDN-000007"}},
                     {"id": "2", "fields": {"account_code_ref": "IDN-000007"}}], "offset": "o1"},
        {"records": [{"id": "3", "fields": {"account_code_ref": "IDN-000014"}}]},
    ])
    assert repo.count_ready_posts_by_account() == {"IDN-000007": 2, "IDN-000014": 1}
    formula = repo.calls[0]["filterByFormula"]
    assert "{post_status}='ready'" in formula and "{canary_run_id}=BLANK()" in formula
    assert "{data_classification}='production'" in formula
    assert repo.calls[1]["offset"] == "o1"


def test_fetch_reuse_source_posts_skips_rows_without_caption(repo, monkeypatch):
    _install(monkeypatch, repo, [{"records": [
        {"id": "a", "fields": {"caption": "hi", "image_url": "u", "image_url_hash": "h", "ig_media_id": "m"}},
        {"id": "b", "fields": {"caption": "  ", "image_url": "u2"}},
    ]}])
    out = repo.fetch_reuse_source_posts("IDN-000041")
    assert [p["post_id"] for p in out] == ["a"] and out[0]["ig_media_id"] == "m" and out[0]["hashtag"] == ""
    assert "{account_code_ref}='IDN-000041'" in repo.calls[0]["filterByFormula"]


def test_fetch_image_hashes_for_account(repo, monkeypatch):
    _install(monkeypatch, repo, [{"records": [
        {"id": "a", "fields": {"image_url_hash": "h1"}}, {"id": "b", "fields": {}}]}])
    assert repo.fetch_image_hashes_for_account("IDN-000007") == {"h1"}


def test_count_recent_failed_posts_by_run_prefix(repo, monkeypatch):
    _install(monkeypatch, repo, [{"records": [{"id": "a", "fields": {}}, {"id": "b", "fields": {}}]}])
    assert repo.count_recent_failed_posts_by_run_prefix("R041-AUTO", 24) == 2
    f = repo.calls[0]["filterByFormula"]
    assert "{post_status}='failed'" in f and "LEFT({run_id},9)='R041-AUTO'" in f and "-24,'hours'" in f


def test_prefix_rejects_overlong_value(repo):
    with pytest.raises(RepositoryValidationError):
        repo.count_recent_failed_posts_by_run_prefix("a" * 41, 24)


@pytest.mark.parametrize("bad", ["", "x' OR 1=1", "IDN 000007"])
def test_prefix_and_codes_reject_formula_injection(repo, bad):
    with pytest.raises(RepositoryValidationError):
        repo.count_recent_failed_posts_by_run_prefix(bad, 24)
    with pytest.raises(RepositoryValidationError):
        repo.fetch_image_hashes_for_account(bad)
    with pytest.raises(RepositoryValidationError):
        repo.fetch_reuse_source_posts(bad)


@pytest.mark.parametrize("hours", [0, 169, True, "24", None])
def test_hours_must_be_bounded_int(repo, hours):
    with pytest.raises(RepositoryValidationError):
        repo.count_recent_failed_posts_by_run_prefix("R041-AUTO", hours)
