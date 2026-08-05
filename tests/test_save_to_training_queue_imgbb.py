"""tests/test_save_to_training_queue_imgbb.py — 260805
save_to_training_queue()가 저장 전 imgbb 재호스팅을 시도하고, 실패 시 원본 URL로
폴백 저장하는지 검증한다. Facebook CDN 원본 URL이 수일 내 서명 만료(403)되어
리뷰가 늦어지면 화면이 깨진 이미지로 채워지던 문제(Runtime 확인, 260805)의 수정 대상.
"""

from unittest.mock import MagicMock

from modules.sns import facebook_crawler


class _Repo:
    def __init__(self, duplicate=False):
        self.duplicate = duplicate
        self.inserted = []

    def exists_candidate_by_hash(self, image_hash):
        return self.duplicate

    def insert_training_candidate(self, candidate):
        self.inserted.append(candidate)
        return "rec_fake"


def test_rehost_success_stores_public_url(monkeypatch):
    repo = _Repo()
    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository",
        lambda: repo,
    )
    monkeypatch.setattr(
        facebook_crawler,
        "upload_to_imgbb",
        MagicMock(return_value={"success": True, "public_url": "https://i.ibb.co/fake.jpg"}),
    )

    ok = facebook_crawler.save_to_training_queue(
        "https://scontent.fbcdn.net/v/123_456_789_n.jpg",
        "https://www.facebook.com/groups/1/posts/2",
        "caption text",
        "target-1",
    )

    assert ok is True
    assert len(repo.inserted) == 1
    assert repo.inserted[0]["image_url"] == "https://i.ibb.co/fake.jpg"


def test_rehost_failure_falls_back_to_original_url(monkeypatch):
    repo = _Repo()
    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository",
        lambda: repo,
    )
    monkeypatch.setattr(
        facebook_crawler,
        "upload_to_imgbb",
        MagicMock(return_value={"success": False, "error": "다운로드 실패"}),
    )

    original = "https://scontent.fbcdn.net/v/123_456_789_n.jpg"
    ok = facebook_crawler.save_to_training_queue(
        original, "https://www.facebook.com/groups/1/posts/2", "caption text", "target-1",
    )

    assert ok is True
    assert len(repo.inserted) == 1
    assert repo.inserted[0]["image_url"] == original


def test_rehost_exception_falls_back_to_original_url(monkeypatch):
    repo = _Repo()
    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository",
        lambda: repo,
    )
    monkeypatch.setattr(
        facebook_crawler,
        "upload_to_imgbb",
        MagicMock(side_effect=RuntimeError("network down")),
    )

    original = "https://scontent.fbcdn.net/v/123_456_789_n.jpg"
    ok = facebook_crawler.save_to_training_queue(
        original, "https://www.facebook.com/groups/1/posts/2", "caption text", "target-1",
    )

    assert ok is True
    assert repo.inserted[0]["image_url"] == original


def test_duplicate_skips_imgbb_and_insert(monkeypatch):
    repo = _Repo(duplicate=True)
    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository",
        lambda: repo,
    )
    imgbb = MagicMock(side_effect=AssertionError("중복인데 imgbb 호출됨"))
    monkeypatch.setattr(facebook_crawler, "upload_to_imgbb", imgbb)

    ok = facebook_crawler.save_to_training_queue(
        "https://scontent.fbcdn.net/v/123_456_789_n.jpg",
        "https://www.facebook.com/groups/1/posts/2",
        "caption text",
        "target-1",
    )

    assert ok is False
    assert repo.inserted == []
    imgbb.assert_not_called()


def test_empty_url_skips_everything(monkeypatch):
    imgbb = MagicMock(side_effect=AssertionError("빈 URL인데 imgbb 호출됨"))
    monkeypatch.setattr(facebook_crawler, "upload_to_imgbb", imgbb)

    ok = facebook_crawler.save_to_training_queue(
        "", "https://www.facebook.com/groups/1/posts/2", "caption text", "target-1",
    )

    assert ok is False
    imgbb.assert_not_called()
