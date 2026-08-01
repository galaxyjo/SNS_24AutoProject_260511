"""260725 — publish_single() `/media_publish` timeout 중복게시 방지(STOP ITEM) 테스트.

Codex 리뷰 확정 규칙:
  - creation_id 확보 이후 어떤 예외가 나도 새 /media 컨테이너를 만들지 않는다.
  - ConnectTimeout만 같은 creation_id로 제한적 재시도, 나머지 모호한 실패는 즉시 outcome_unknown.
  - HTTP 4xx=명확한 failed(재시도 없음) / 5xx·파싱실패·id누락=outcome_unknown(재시도 없음).
  - Job은 outcome_unknown을 받으면 mark_post_result()를 호출하지 않고 uploading 상태로 격리 + 즉시 알림.
외부 게시·Airtable Write 없이 전부 Mock으로 검증한다.
"""

from unittest.mock import patch

import pytest
import requests

from launcher import main as launcher_main


class _Resp:
    def __init__(self, status_code=200, json_data=None, json_error=False):
        self.status_code = status_code
        self._json_data = json_data
        self._json_error = json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err

    def json(self):
        if self._json_error:
            raise ValueError("bad json")
        return self._json_data


_MEDIA_OK = _Resp(200, {"id": "creation123"})


# ── 1~7. publish_single() Phase A/B 분류 ──────────────────────────────────

class TestPublishSinglePhaseHandling:
    def test_media_creation_read_timeout_then_retry_success(self):
        """/media ReadTimeout 후 재시도 성공 — /media만 추가 호출, /media_publish는 컨테이너 확보 후 1회."""
        with patch(
            "requests.post",
            side_effect=[
                requests.exceptions.ReadTimeout("t"),
                _MEDIA_OK,
                _Resp(200, {"id": "media456"}),
            ],
        ) as mock_post:
            result = launcher_main.publish_single("r1", "http://img", "cap", "tok", "iguser")

        assert result == {"ok": True, "ig_media_id": "media456"}
        assert mock_post.call_count == 3
        assert "/media_publish" in mock_post.call_args_list[2].args[0]

    def test_media_publish_read_timeout_stops_immediately_no_new_container(self):
        with patch(
            "requests.post",
            side_effect=[_MEDIA_OK, requests.exceptions.ReadTimeout("t")],
        ) as mock_post:
            result = launcher_main.publish_single("r2", "http://img", "cap", "tok", "iguser")

        assert result == {"ok": False, "error": "outcome_unknown", "outcome_unknown": True, "creation_id": "creation123"}
        assert mock_post.call_count == 2  # /media 1회 + /media_publish 1회, 재시도 없음

    def test_media_publish_connection_error_stops_immediately_no_new_container(self):
        with patch(
            "requests.post",
            side_effect=[_MEDIA_OK, requests.exceptions.ConnectionError("reset")],
        ) as mock_post:
            result = launcher_main.publish_single("r3", "http://img", "cap", "tok", "iguser")

        assert result["outcome_unknown"] is True
        assert result["creation_id"] == "creation123"
        assert mock_post.call_count == 2

    def test_media_publish_connect_timeout_retries_with_same_creation_id(self):
        """ConnectTimeout 2회 후 3번째 성공 — /media 추가 호출 없이 같은 creation_id 재사용."""
        with patch(
            "requests.post",
            side_effect=[
                _MEDIA_OK,
                requests.exceptions.ConnectTimeout("t1"),
                requests.exceptions.ConnectTimeout("t2"),
                _Resp(200, {"id": "media789"}),
            ],
        ) as mock_post:
            result = launcher_main.publish_single("r4", "http://img", "cap", "tok", "iguser")

        assert result == {"ok": True, "ig_media_id": "media789"}
        assert mock_post.call_count == 4  # /media 1회 + /media_publish 3회(같은 creation_id)
        for call in mock_post.call_args_list[1:]:
            assert call.kwargs["params"]["creation_id"] == "creation123"

    def test_media_publish_connect_timeout_exhausted_returns_outcome_unknown(self):
        with patch(
            "requests.post",
            side_effect=[
                _MEDIA_OK,
                requests.exceptions.ConnectTimeout("t1"),
                requests.exceptions.ConnectTimeout("t2"),
                requests.exceptions.ConnectTimeout("t3"),
            ],
        ) as mock_post:
            result = launcher_main.publish_single("r5", "http://img", "cap", "tok", "iguser")

        assert result["outcome_unknown"] is True
        assert mock_post.call_count == 4  # /media 1회 + ConnectTimeout 3회, 새 /media 없음

    def test_media_publish_http_400_is_outcome_unknown_no_retry(self):
        """260801 6D — HTTP 400을 더 이상 '명확한 실패'로 간주하지 않는다(실측
        사고 2건: 400 응답 직후 서버측에서 실제로는 게시가 성공한 사례 확인,
        aijomoojin Canary media_id 17900221041544868/18021773060855830).
        5xx와 동일하게 outcome_unknown으로 격리해 재시도를 막는다."""
        with patch("requests.post", side_effect=[_MEDIA_OK, _Resp(400)]) as mock_post:
            result = launcher_main.publish_single("r6", "http://img", "cap", "tok", "iguser")

        assert result["ok"] is False
        assert result["outcome_unknown"] is True
        assert mock_post.call_count == 2

    def test_media_publish_http_500_is_outcome_unknown_no_retry(self):
        with patch("requests.post", side_effect=[_MEDIA_OK, _Resp(500)]) as mock_post:
            result = launcher_main.publish_single("r7", "http://img", "cap", "tok", "iguser")

        assert result["outcome_unknown"] is True
        assert mock_post.call_count == 2  # 5xx는 재시도 없이 즉시 중단

    def test_media_publish_200_with_json_parse_failure_is_outcome_unknown(self):
        with patch(
            "requests.post",
            side_effect=[_MEDIA_OK, _Resp(200, json_error=True)],
        ) as mock_post:
            result = launcher_main.publish_single("r8", "http://img", "cap", "tok", "iguser")

        assert result["outcome_unknown"] is True
        assert mock_post.call_count == 2

    def test_media_publish_200_without_id_is_outcome_unknown(self):
        with patch(
            "requests.post",
            side_effect=[_MEDIA_OK, _Resp(200, {})],
        ) as mock_post:
            result = launcher_main.publish_single("r9", "http://img", "cap", "tok", "iguser")

        assert result["outcome_unknown"] is True
        assert mock_post.call_count == 2

    @pytest.mark.parametrize("empty_id", ["", None])
    def test_media_publish_200_with_empty_id_value_is_outcome_unknown(self, empty_id):
        """id 키는 존재하지만 값이 비어있는 경우(260725 Codex 재검수 지적) — 성공으로 오인하면 안 됨."""
        with patch(
            "requests.post",
            side_effect=[_MEDIA_OK, _Resp(200, {"id": empty_id})],
        ) as mock_post:
            result = launcher_main.publish_single("r9b", "http://img", "cap", "tok", "iguser")

        assert result["outcome_unknown"] is True

    def test_normal_success_unchanged(self):
        with patch("requests.post", side_effect=[_MEDIA_OK, _Resp(200, {"id": "mediaOK"})]):
            result = launcher_main.publish_single("r10", "http://img", "cap", "tok", "iguser")

        assert result == {"ok": True, "ig_media_id": "mediaOK"}

    def test_facebook_login_default_host_unchanged(self):
        """api_host 인자를 안 주는 기존 호출부는 여전히 graph.facebook.com을 씀(회귀 없음)."""
        with patch("requests.post", side_effect=[_MEDIA_OK, _Resp(200, {"id": "mediaFB"})]) as mock_post:
            result = launcher_main.publish_single("r11", "http://img", "cap", "tok", "iguser")

        assert result == {"ok": True, "ig_media_id": "mediaFB"}
        assert all("graph.facebook.com" in c.args[0] for c in mock_post.call_args_list)


# ── 8. Job 레벨 — outcome_unknown 격리 ─────────────────────────────────────

def test_job_isolates_outcome_unknown_without_marking_or_retrying(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
    monkeypatch.setenv("YUNA_INSTA_IG_USER_ID", "yuna-ig-user")
    monkeypatch.setenv("YUNA_INSTA_ACCESS_TOKEN", "yuna-token")

    calls = {"claim": [], "mark_post_result": [], "slack": []}

    class _FakeRepo:
        def fetch_pending_posts(self, limit=50):
            return [{"post_id": "recU", "image_url": "http://img", "caption": "c", "hashtag": "", "account_code_ref": "IDN-000041"}]

        def get_publish_account(self, account_code):
            return {
                "account_code": account_code,
                "api_provider": "facebook_login",
                "ig_user_id": "yuna-ig-user",
                "credential_key": "YUNA",
            }

        def claim_post_for_upload(self, post_id):
            calls["claim"].append(post_id)
            return True

        def mark_post_result(self, post_id, result):
            calls["mark_post_result"].append((post_id, dict(result)))

    monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: _FakeRepo())

    publish_calls = []

    def _fake_publish_single(rid, image_url, caption, access_token, ig_user_id, api_host="graph.facebook.com"):
        publish_calls.append(rid)
        return {"ok": False, "error": "outcome_unknown", "outcome_unknown": True, "creation_id": "creationX"}

    monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)
    monkeypatch.setattr(launcher_main, "_slack", lambda msg: calls["slack"].append(msg))

    launcher_main._job_insta_upload()

    assert calls["claim"] == ["recU"]           # claim은 됨(uploading 마킹)
    assert publish_calls == ["recU"]             # publish_single은 1회만 호출(추가 재시도 없음)
    assert calls["mark_post_result"] == []       # mark_post_result 0회 — uploading 그대로 격리
    assert len(calls["slack"]) == 1              # 즉시 알림 1회
    assert "recU" in calls["slack"][0]
    assert "creationX" in calls["slack"][0]


def test_job_mixed_batch_outcome_unknown_does_not_block_next_record(monkeypatch):
    """260725 Codex 재검수 지적 — 첫 레코드가 outcome_unknown이어도 배치의 다음 레코드는 정상 처리돼야 함."""
    monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
    monkeypatch.setenv("YUNA_INSTA_IG_USER_ID", "yuna-ig-user")
    monkeypatch.setenv("YUNA_INSTA_ACCESS_TOKEN", "yuna-token")

    calls = {"claim": [], "mark_post_result": [], "slack": []}

    class _FakeRepo:
        def fetch_pending_posts(self, limit=50):
            return [
                {"post_id": "recFirst", "image_url": "http://img", "caption": "c", "hashtag": "", "account_code_ref": "IDN-000041"},
                {"post_id": "recSecond", "image_url": "http://img", "caption": "c", "hashtag": "", "account_code_ref": "IDN-000041"},
            ]

        def get_publish_account(self, account_code):
            return {
                "account_code": account_code,
                "api_provider": "facebook_login",
                "ig_user_id": "yuna-ig-user",
                "credential_key": "YUNA",
            }

        def claim_post_for_upload(self, post_id):
            calls["claim"].append(post_id)
            return True

        def mark_post_result(self, post_id, result):
            calls["mark_post_result"].append((post_id, dict(result)))

    monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: _FakeRepo())

    publish_calls = []

    def _fake_publish_single(rid, image_url, caption, access_token, ig_user_id, api_host="graph.facebook.com"):
        publish_calls.append(rid)
        if rid == "recFirst":
            return {"ok": False, "error": "outcome_unknown", "outcome_unknown": True, "creation_id": "creationFirst"}
        return {"ok": True, "ig_media_id": "media-second"}

    monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)
    monkeypatch.setattr(launcher_main, "_slack", lambda msg: calls["slack"].append(msg))

    launcher_main._job_insta_upload()

    assert calls["claim"] == ["recFirst", "recSecond"]
    assert publish_calls == ["recFirst", "recSecond"]
    assert calls["mark_post_result"] == [
        ("recSecond", {"status": "posted", "platform_post_id": "media-second", "error_code": ""}),
    ]
    assert len(calls["slack"]) == 1
    assert "recFirst" in calls["slack"][0]


def test_job_definitive_failure_marks_failed_and_alerts_with_creation_id(monkeypatch):
    """ERR-076 — HTTP 4xx '명확한 실패'도 mark_post_result는 그대로 호출하되(회귀 유지),
    creation_id를 담은 Slack 알림이 함께 발생해야 한다(기존엔 outcome_unknown만 알림)."""
    monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
    monkeypatch.setenv("YUNA_INSTA_IG_USER_ID", "yuna-ig-user")
    monkeypatch.setenv("YUNA_INSTA_ACCESS_TOKEN", "yuna-token")

    calls = {"claim": [], "mark_post_result": [], "slack": []}

    class _FakeRepo:
        def fetch_pending_posts(self, limit=50):
            return [{"post_id": "recFail", "image_url": "http://img", "caption": "c", "hashtag": "", "account_code_ref": "IDN-000041"}]

        def get_publish_account(self, account_code):
            return {
                "account_code": account_code,
                "api_provider": "facebook_login",
                "ig_user_id": "yuna-ig-user",
                "credential_key": "YUNA",
            }

        def claim_post_for_upload(self, post_id):
            calls["claim"].append(post_id)
            return True

        def mark_post_result(self, post_id, result):
            calls["mark_post_result"].append((post_id, dict(result)))

    monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: _FakeRepo())

    def _fake_publish_single(rid, image_url, caption, access_token, ig_user_id, api_host="graph.facebook.com"):
        return {"ok": False, "error": "http_400", "creation_id": "creationFail"}

    monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)
    monkeypatch.setattr(launcher_main, "_slack", lambda msg: calls["slack"].append(msg))

    launcher_main._job_insta_upload()

    assert calls["mark_post_result"] == [
        ("recFail", {"status": "failed", "platform_post_id": "", "error_code": "http_400"}),
    ]
    assert len(calls["slack"]) == 1
    assert "recFail" in calls["slack"][0]
    assert "creationFail" in calls["slack"][0]
