"""tests/test_comment_campaign_config.py — 캠페인 allowlist 공용 loader 검증
(260715 Package 1 Phase A)."""

import json

import pytest

from modules.comment.comment_campaign_config import CampaignConfigError, load_campaign_media_ids


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_missing_file_raises(tmp_path):
    """260715 Codex 6차 리뷰 P1 — 파일 소실을 "의도적으로 캠페인 0개"와 구분해야
    sync_from_campaign_json()이 기존 ACTIVE를 전부 PAUSED시키는 사고를 막을 수 있다."""
    with pytest.raises(CampaignConfigError):
        load_campaign_media_ids(tmp_path / "missing.json")


def test_explicit_empty_media_ids_is_valid(tmp_path):
    """파일이 실제로 존재하고 {"media_ids": []}면(의도적 빈 캠페인) 에러가 아니다."""
    path = tmp_path / "campaign.json"
    _write(path, {"media_ids": []})
    assert load_campaign_media_ids(path) == []


def test_whitespace_in_media_id_normalized(tmp_path):
    path = tmp_path / "campaign.json"
    _write(path, {"media_ids": [" 123 ", "456"]})
    assert load_campaign_media_ids(path) == ["123", "456"]


def test_valid_file_returns_media_ids(tmp_path):
    path = tmp_path / "campaign.json"
    _write(path, {"media_ids": ["a", "b", "c"]})
    assert load_campaign_media_ids(path) == ["a", "b", "c"]


def test_duplicates_removed_order_preserved(tmp_path):
    path = tmp_path / "campaign.json"
    _write(path, {"media_ids": ["a", "b", "a", "c", "b"]})
    assert load_campaign_media_ids(path) == ["a", "b", "c"]


def test_corrupted_json_raises(tmp_path):
    path = tmp_path / "campaign.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(CampaignConfigError):
        load_campaign_media_ids(path)


def test_missing_media_ids_key_raises(tmp_path):
    path = tmp_path / "campaign.json"
    _write(path, {"other_key": []})
    with pytest.raises(CampaignConfigError):
        load_campaign_media_ids(path)


def test_media_ids_not_a_list_raises(tmp_path):
    path = tmp_path / "campaign.json"
    _write(path, {"media_ids": "not-a-list"})
    with pytest.raises(CampaignConfigError):
        load_campaign_media_ids(path)


def test_empty_string_media_id_raises(tmp_path):
    path = tmp_path / "campaign.json"
    _write(path, {"media_ids": ["a", "", "c"]})
    with pytest.raises(CampaignConfigError):
        load_campaign_media_ids(path)


def test_non_string_media_id_raises(tmp_path):
    path = tmp_path / "campaign.json"
    _write(path, {"media_ids": ["a", 123, "c"]})
    with pytest.raises(CampaignConfigError):
        load_campaign_media_ids(path)


def test_default_path_used_when_no_argument(monkeypatch, tmp_path):
    """path 인자 없이 호출하면 모듈의 _CONFIG_PATH(운영 기본 파일)를 사용해야 한다."""
    import modules.comment.comment_campaign_config as cfg

    path = tmp_path / "campaign.json"
    _write(path, {"media_ids": ["x"]})
    monkeypatch.setattr(cfg, "_CONFIG_PATH", path)
    assert load_campaign_media_ids() == ["x"]
