"""9-10-3-G Defect F — launcher/main.py::_job_insta_upload()에서 mark_post_result()
실패가 (1) 나머지 후보 게시물 처리를 막지 않는지, (2) IG 게시 성공/실패 여부에 따라
로그·Slack 알림이 올바르게 구분되는지 검증한다. publish_single() 자체는 이미 검증된
SAFE 경로이므로 이 테스트에서는 monkeypatch로 대체한다.

Runtime 상태변경(Airtable Write, 실제 네트워크 호출, Slack 전송) 없이 Mock으로만 검증한다.
"""

import pytest


class _FakeRepo:
    def __init__(self, posts, mark_fail_on=None):
        self._posts = posts
        self._mark_fail_on = mark_fail_on or set()
        self.mark_calls = []
        self.claimed = []

    def fetch_pending_posts(self, limit=50):
        return self._posts

    def get_publish_account(self, code):
        return {"api_provider": "facebook_login", "ig_user_id": "ig-123", "credential_key": "YUNA"}

    def claim_post_for_upload(self, post_id):
        self.claimed.append(post_id)
        return True

    def mark_post_result(self, post_id, result):
        if post_id in self._mark_fail_on:
            raise RuntimeError(f"mark_post_result 실패(시뮬레이션): {post_id}")
        self.mark_calls.append((post_id, dict(result)))


class _FakeCredential:
    ig_user_id = "ig-123"
    access_token = "token-abc"


def _post(post_id, account_code_ref="IDN-000041"):
    return {
        "post_id": post_id,
        "image_url": "https://img.example/x.jpg",
        "caption": "caption",
        "hashtag": "#tag",
        "account_code_ref": account_code_ref,
        "data_classification": "production",
        "canary_run_id": "",
        "post_status": "ready",
    }


def _setup(monkeypatch, posts, mark_fail_on, publish_results):
    from launcher import main as launcher_main

    monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
    repo = _FakeRepo(posts, mark_fail_on=mark_fail_on)
    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository", lambda: repo
    )
    monkeypatch.setattr(
        "modules.common.canary_classification.validate_publication_candidate",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "modules.common.credential_resolver.resolve_credential",
        lambda key: _FakeCredential(),
    )

    def _fake_publish_single(post_id, *a, **k):
        return publish_results[post_id]

    monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)

    sent_alerts = []
    monkeypatch.setattr(launcher_main, "_slack", lambda msg: sent_alerts.append(msg))

    return launcher_main, repo, sent_alerts


class TestInstaUploadBatchIsolation:
    def test_mark_post_result_success_records_normally(self, monkeypatch):
        launcher_main, repo, alerts = _setup(
            monkeypatch,
            posts=[_post("rid1")],
            mark_fail_on=set(),
            publish_results={"rid1": {"ok": True, "ig_media_id": "media1"}},
        )

        launcher_main._job_insta_upload.__wrapped__()

        assert repo.mark_calls == [("rid1", {"status": "posted", "platform_post_id": "media1", "error_code": ""})]
        assert alerts == []

    def test_ig_success_but_mark_failure_isolates_and_alerts(self, monkeypatch):
        launcher_main, repo, alerts = _setup(
            monkeypatch,
            posts=[_post("rid-mark-fail"), _post("rid-ok")],
            mark_fail_on={"rid-mark-fail"},
            publish_results={
                "rid-mark-fail": {"ok": True, "ig_media_id": "media-fail"},
                "rid-ok": {"ok": True, "ig_media_id": "media-ok"},
            },
        )

        launcher_main._job_insta_upload.__wrapped__()

        # 두 번째 게시물은 첫 번째의 mark_post_result 실패와 무관하게 정상 기록돼야 한다.
        assert ("rid-ok", {"status": "posted", "platform_post_id": "media-ok", "error_code": ""}) in repo.mark_calls
        assert len(repo.mark_calls) == 1
        # IG 게시는 성공했는데 상태기록만 실패한 가장 위험한 케이스이므로 Slack 알림이 가야 한다.
        assert len(alerts) == 1
        assert "IG 게시 성공" in alerts[0]
        assert "rid-mark-fail" in alerts[0]

    def test_ig_failure_and_mark_failure_isolates_without_extra_alert(self, monkeypatch):
        launcher_main, repo, alerts = _setup(
            monkeypatch,
            posts=[_post("rid-both-fail"), _post("rid-ok")],
            mark_fail_on={"rid-both-fail"},
            publish_results={
                "rid-both-fail": {"ok": False, "error": "network error"},
                "rid-ok": {"ok": True, "ig_media_id": "media-ok"},
            },
        )

        launcher_main._job_insta_upload.__wrapped__()

        assert len(repo.mark_calls) == 1
        assert repo.mark_calls[0][0] == "rid-ok"
        # 게시 자체도 실패했던 경우는 IG-성공-전용 긴급 Slack 알림을 보내지 않는다
        # (publish_single 실패 자체의 알림 계약은 이번 수정 범위 밖).
        assert alerts == []
