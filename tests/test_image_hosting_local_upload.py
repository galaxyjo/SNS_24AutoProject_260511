"""tests/test_image_hosting_local_upload.py — 260801 Step6B 로컬PNG→공개URL
브릿지 함수 검증. 실제 imgbb 네트워크 호출 없이 requests만 mock한다."""

from unittest.mock import MagicMock, patch

import pytest
import requests

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


# ── 260923 P1-2 Sprint1 — HEAD 검증 False Negative 차단 ──────────────────────
def _post_ok():
    r = MagicMock()
    r.raise_for_status.return_value = None
    r.json.return_value = {"success": True, "data": {"url": "https://i.ibb.co/fake/sample.png"}}
    return r


def test_head_timeout_then_success_returns_url_with_single_post(fake_png):
    """일시 Timeout 2회 뒤 200이면 최종 성공하고, 업로드 POST는 1회만 호출한다."""
    ok = MagicMock(); ok.status_code = 200
    post = MagicMock(return_value=_post_ok())
    head = MagicMock(side_effect=[requests.exceptions.ReadTimeout("t1"),
                                  requests.exceptions.ReadTimeout("t2"), ok])
    with patch("modules.sns.image_hosting.requests.post", post),          patch("modules.sns.image_hosting.requests.head", head),          patch("modules.sns.image_hosting.time.sleep") as slept:
        result = image_hosting.upload_local_file_to_imgbb(fake_png, api_key="k")
    assert result["success"] is True
    assert result["public_url"] == "https://i.ibb.co/fake/sample.png"
    assert post.call_count == 1
    assert head.call_count == 3
    assert slept.call_count == 2


def test_head_all_attempts_fail_is_fail_closed_with_single_post(fake_png):
    """3회 전부 실패하면 기존과 동일하게 실패를 반환하고 POST는 1회뿐이다."""
    post = MagicMock(return_value=_post_ok())
    head = MagicMock(side_effect=requests.exceptions.ReadTimeout("boom"))
    with patch("modules.sns.image_hosting.requests.post", post),          patch("modules.sns.image_hosting.requests.head", head),          patch("modules.sns.image_hosting.time.sleep"):
        result = image_hosting.upload_local_file_to_imgbb(fake_png, api_key="k")
    assert result["success"] is False
    assert "URL 검증 실패" in result["error"]
    assert post.call_count == 1
    assert head.call_count == image_hosting.HEAD_MAX_ATTEMPTS == 3


def test_post_failure_does_not_call_head(fake_png):
    """업로드 POST가 실패하면 HEAD 검증은 한 번도 호출되지 않는다."""
    bad = MagicMock()
    bad.raise_for_status.return_value = None
    bad.json.return_value = {"success": False, "error": {"message": "bad key"}}
    post = MagicMock(return_value=bad)
    head = MagicMock()
    with patch("modules.sns.image_hosting.requests.post", post),          patch("modules.sns.image_hosting.requests.head", head):
        result = image_hosting.upload_local_file_to_imgbb(fake_png, api_key="k")
    assert result["success"] is False
    assert post.call_count == 1
    assert head.call_count == 0


def test_head_404_is_definitive_no_retry(fake_png):
    """4xx는 일시 오류가 아니므로 재시도하지 않고 즉시 실패로 확정한다."""
    nf = MagicMock(); nf.status_code = 404
    post = MagicMock(return_value=_post_ok())
    head = MagicMock(return_value=nf)
    with patch("modules.sns.image_hosting.requests.post", post),          patch("modules.sns.image_hosting.requests.head", head):
        result = image_hosting.upload_local_file_to_imgbb(fake_png, api_key="k")
    assert result["success"] is False
    assert "공개 URL 접근 실패: 404" in result["error"]
    assert post.call_count == 1
    assert head.call_count == 1


@pytest.mark.parametrize("status", [408, 429])
def test_head_retryable_status_then_success(fake_png, status):
    """408·429는 일시 오류로 보고 재시도하며, 이후 200이면 최종 성공한다(POST 1회)."""
    busy = MagicMock(); busy.status_code = status
    ok = MagicMock(); ok.status_code = 200
    post = MagicMock(return_value=_post_ok())
    head = MagicMock(side_effect=[busy, ok])
    with patch("modules.sns.image_hosting.requests.post", post),          patch("modules.sns.image_hosting.requests.head", head),          patch("modules.sns.image_hosting.time.sleep") as slept:
        result = image_hosting.upload_local_file_to_imgbb(fake_png, api_key="k")
    assert result["success"] is True
    assert result["public_url"] == "https://i.ibb.co/fake/sample.png"
    assert post.call_count == 1
    assert head.call_count == 2
    assert slept.call_count == 1


@pytest.mark.parametrize("status", [400, 403, 404])
def test_head_non_retryable_4xx_fails_immediately(fake_png, status):
    """408·429를 제외한 4xx는 재시도 없이 즉시 실패로 확정한다(POST 1회)."""
    bad = MagicMock(); bad.status_code = status
    post = MagicMock(return_value=_post_ok())
    head = MagicMock(return_value=bad)
    with patch("modules.sns.image_hosting.requests.post", post),          patch("modules.sns.image_hosting.requests.head", head):
        result = image_hosting.upload_local_file_to_imgbb(fake_png, api_key="k")
    assert result["success"] is False
    assert f"공개 URL 접근 실패: {status}" in result["error"]
    assert post.call_count == 1
    assert head.call_count == 1


def test_head_5xx_is_retried_then_fail_closed(fake_png):
    """5xx는 재시도 대상이며 3회 소진 시 Fail-closed한다(POST 1회)."""
    err = MagicMock(); err.status_code = 503
    post = MagicMock(return_value=_post_ok())
    head = MagicMock(return_value=err)
    with patch("modules.sns.image_hosting.requests.post", post),          patch("modules.sns.image_hosting.requests.head", head),          patch("modules.sns.image_hosting.time.sleep"):
        result = image_hosting.upload_local_file_to_imgbb(fake_png, api_key="k")
    assert result["success"] is False
    assert "공개 URL 접근 실패: 503" in result["error"]
    assert post.call_count == 1
    assert head.call_count == 3
