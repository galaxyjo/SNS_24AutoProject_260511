"""tests/test_image_hosting_local_upload.py — 260801 Step6B 로컬PNG→공개URL
브릿지 함수 검증. 실제 imgbb 네트워크 호출 없이 requests만 mock한다."""

from unittest.mock import MagicMock, patch

import pytest

from modules.sns import image_hosting


@pytest.fixture
def fake_png(tmp_path):
    p = tmp_path / "sample.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\nfakepngbytes")
    return p


def test_missing_file_returns_error(tmp_path):
    result = image_hosting.upload_local_file_to_imgbb(tmp_path / "does_not_exist.png", api_key="k")
    assert result["success"] is False
    assert "파일 없음" in result["error"]


def test_missing_api_key_returns_error(fake_png, monkeypatch):
    monkeypatch.delenv("IMGBB_API_KEY", raising=False)
    result = image_hosting.upload_local_file_to_imgbb(fake_png, api_key=None)
    assert result["success"] is False
    assert "IMGBB_API_KEY" in result["error"]


def test_success_returns_public_url(fake_png):
    post_resp = MagicMock()
    post_resp.raise_for_status.return_value = None
    post_resp.json.return_value = {"success": True, "data": {"url": "https://i.ibb.co/fake/sample.png"}}
    head_resp = MagicMock()
    head_resp.status_code = 200

    with patch("modules.sns.image_hosting.requests.post", return_value=post_resp), \
         patch("modules.sns.image_hosting.requests.head", return_value=head_resp):
        result = image_hosting.upload_local_file_to_imgbb(fake_png, api_key="k")

    assert result["success"] is True
    assert result["public_url"] == "https://i.ibb.co/fake/sample.png"
    assert len(result["content_hash"]) == 64  # sha256 hex


def test_imgbb_upload_failure_returns_error(fake_png):
    post_resp = MagicMock()
    post_resp.raise_for_status.return_value = None
    post_resp.json.return_value = {"success": False, "error": {"message": "bad key"}}

    with patch("modules.sns.image_hosting.requests.post", return_value=post_resp):
        result = image_hosting.upload_local_file_to_imgbb(fake_png, api_key="k")

    assert result["success"] is False
    assert "imgbb 응답 실패" in result["error"]


def test_public_url_verification_failure_returns_error(fake_png):
    post_resp = MagicMock()
    post_resp.raise_for_status.return_value = None
    post_resp.json.return_value = {"success": True, "data": {"url": "https://i.ibb.co/fake/sample.png"}}
    head_resp = MagicMock()
    head_resp.status_code = 404

    with patch("modules.sns.image_hosting.requests.post", return_value=post_resp), \
         patch("modules.sns.image_hosting.requests.head", return_value=head_resp):
        result = image_hosting.upload_local_file_to_imgbb(fake_png, api_key="k")

    assert result["success"] is False
    assert "공개 URL 접근 실패" in result["error"]


def test_empty_file_returns_error(tmp_path):
    p = tmp_path / "empty.png"
    p.write_bytes(b"")
    result = image_hosting.upload_local_file_to_imgbb(p, api_key="k")
    assert result["success"] is False
    assert "빈 이미지" in result["error"]
