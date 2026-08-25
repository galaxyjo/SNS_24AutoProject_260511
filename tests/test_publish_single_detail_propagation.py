"""260825 — GPT 승인 단일작업: publish_single() 실패 반환값에 이미 계산된 Meta
`detail`을 담아, 기존 raw.get("error") 소비 경로(Slack/Airtable)까지 끊김 없이
전달되게 한다. Correlation ID/Retry/Catch-up 등은 이번 범위 밖(추가 안 함).

Target Test 3개만 검증한다:
  1. Meta 실패 시 detail이 반환값에 포함되는가?
  2. 기존 error 값은 유지되는가?
  3. 기존 Slack/Airtable 소비 코드가 정상적으로 해당 값을 받을 수 있는가?
"""

from unittest.mock import patch

import requests

from launcher import main as launcher_main


class _Resp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err

    def json(self):
        return self._json_data


_MEDIA_OK = _Resp(200, {"id": "creation123"})
_STATUS_FINISHED = _Resp(200, {"status_code": "FINISHED"})
_META_ERROR_BODY = {
    "error": {"message": "Invalid parameter", "type": "OAuthException",
               "code": 100, "error_subcode": 2108006, "fbtrace_id": "AbCdEfGhIjK"},
}


def test_phase_a_failure_includes_detail_and_preserves_error():
    """1) Phase A(media 생성) 3회 실패 시 detail이 반환값에 담기고, 2) 기존 error(str(e))는 그대로 유지된다."""
    err_resp = _Resp(400, _META_ERROR_BODY)
    http_err = requests.HTTPError("400 Client Error")
    http_err.response = err_resp

    with patch("requests.post", side_effect=[http_err, http_err, http_err]):
        result = launcher_main.publish_single("r1", "http://img", "cap", "tok", "iguser")

    assert result["ok"] is False
    assert result["error"] == "400 Client Error"  # 기존 error 값 무변경(str(e) 그대로)
    assert "Invalid parameter" in result["detail"]
    assert "2108006" in result["detail"]


def test_phase_b_http_400_includes_detail_and_preserves_error():
    """Phase B(media_publish) HTTP 400도 동일 패턴 — outcome_unknown 값 자체는 그대로,
    detail만 추가로 담긴다(260801 6D 정책 — 재시도/캐치업 없음, 이번 수정과 무관하게 무변경)."""
    with patch("requests.post", side_effect=[_MEDIA_OK, _Resp(400, _META_ERROR_BODY)]), \
         patch("requests.get", return_value=_STATUS_FINISHED):
        result = launcher_main.publish_single("r2", "http://img", "cap", "tok", "iguser")

    assert result == {
        "ok": False, "error": "outcome_unknown", "outcome_unknown": True,
        "creation_id": "creation123", "detail": result["detail"],
    }
    assert "Invalid parameter" in result["detail"]


def test_success_path_has_no_detail_key_added():
    """성공 경로는 이번 변경으로 전혀 안 건드림 — detail 키 자체가 없어야 한다(회귀 방지)."""
    with patch("requests.post", side_effect=[_MEDIA_OK, _Resp(200, {"id": "mediaOK"})]), \
         patch("requests.get", return_value=_STATUS_FINISHED):
        result = launcher_main.publish_single("r3", "http://img", "cap", "tok", "iguser")

    assert result == {"ok": True, "ig_media_id": "mediaOK"}
    assert "detail" not in result


def test_existing_consumer_can_read_detail_via_get():
    """3) 기존 Slack/Airtable 소비 코드가 쓰는 raw.get(...) 방식 그대로 detail을 받을 수 있다
    (caller 코드 자체는 이번 범위에서 수정 안 함 — .get()이 새 키를 문제없이 읽는지만 확인)."""
    err_resp = _Resp(400, _META_ERROR_BODY)
    http_err = requests.HTTPError("400 Client Error")
    http_err.response = err_resp

    with patch("requests.post", side_effect=[http_err, http_err, http_err]):
        raw = launcher_main.publish_single("r4", "http://img", "cap", "tok", "iguser")

    # 기존 caller 계약(raw.get("error", "")) 무변경 확인 + 신규 raw.get("detail", "") 접근 가능 확인
    assert raw.get("error", "") == "400 Client Error"
    assert raw.get("detail", "") != ""
    assert raw.get("nonexistent_key", "default") == "default"  # .get() 계약 자체는 그대로
