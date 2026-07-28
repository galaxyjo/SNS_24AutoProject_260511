"""Step 6 MVP — 발행직전 텍스트 Quality Gate + 승인(Draft/Approved) 단계.

외부 게시·Airtable Write 없이 전부 Mock으로 검증한다.
"""

import logging

from modules.infra.repository_interface import InstagramPostStatus, PostPublishResult


# ── 1. InstagramPostStatus enum 확장 확인 ─────────────────────────────────

def test_status_enum_has_draft_and_rejected():
    assert InstagramPostStatus.DRAFT.value == "draft"
    assert InstagramPostStatus.REJECTED.value == "rejected"
    # 기존 값 회귀 없음
    assert InstagramPostStatus.READY.value == "ready"
    assert InstagramPostStatus.UPLOADING.value == "uploading"
    assert InstagramPostStatus.POSTED.value == "posted"
    assert InstagramPostStatus.FAILED.value == "failed"


# ── 2. save_instagram_post() 승인단계 기본값 분기 ─────────────────────────

def test_save_instagram_post_defaults_to_ready_when_approval_disabled(monkeypatch):
    monkeypatch.delenv("REQUIRE_APPROVAL_BEFORE_PUBLISH", raising=False)
    from modules.infra.airtable_repository import AirtableRepository

    captured = {}

    class _OkResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "rec123"}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json["fields"]
        return _OkResp()

    monkeypatch.setattr("modules.infra.airtable_repository.requests.post", _fake_post)
    monkeypatch.setattr(
        "modules.infra.airtable_repository.log_api_call", lambda *a, **k: None
    )

    repo = AirtableRepository()
    monkeypatch.setattr(
        repo,
        "validate_instagram_post_context",
        lambda *a, **k: {"account_code": "IDN-000041"},
    )
    repo.save_instagram_post({
        "image_url": "http://img",
        "account_code_ref": "IDN-000041",
        "data_classification": "production",
    })

    assert captured["payload"]["post_status"] == "ready"


def test_save_instagram_post_defaults_to_draft_when_approval_enabled(monkeypatch):
    monkeypatch.setenv("REQUIRE_APPROVAL_BEFORE_PUBLISH", "true")
    from modules.infra.airtable_repository import AirtableRepository

    captured = {}

    class _OkResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "rec456"}

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json["fields"]
        return _OkResp()

    monkeypatch.setattr("modules.infra.airtable_repository.requests.post", _fake_post)
    monkeypatch.setattr(
        "modules.infra.airtable_repository.log_api_call", lambda *a, **k: None
    )

    repo = AirtableRepository()
    monkeypatch.setattr(
        repo,
        "validate_instagram_post_context",
        lambda *a, **k: {"account_code": "IDN-000041"},
    )
    repo.save_instagram_post({
        "image_url": "http://img",
        "account_code_ref": "IDN-000041",
        "data_classification": "production",
    })

    assert captured["payload"]["post_status"] == "draft"


def test_fetch_pending_posts_still_filters_ready_only():
    """draft 레코드는 fetch_pending_posts()가 조회하지 않음을 필터식 자체로 확인 (5단계 Exit Criteria)."""
    import inspect
    from modules.infra.airtable_repository import AirtableRepository

    src = inspect.getsource(AirtableRepository.fetch_pending_posts)
    assert "InstagramPostStatus.READY.value" in src
    assert "draft" not in src.lower()


# ── 3. launcher/main.py 발행직전 텍스트 Gate + ready 처리시작 로그 ─────────

def test_text_gate_blocks_and_marks_rejected_when_enabled(monkeypatch, caplog):
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "true")
    monkeypatch.setenv("INSTA_ACCESS_TOKEN", "fake-token")
    monkeypatch.setenv("INSTA_IG_USER_ID", "fake-iguser")

    from launcher import main as launcher_main

    calls = {"publish_single": 0, "mark_post_result": []}

    class _FakeRepo:
        def fetch_pending_posts(self, limit=50):
            return [{"post_id": "rec1", "image_url": "http://img", "caption": "blocked text", "hashtag": ""}]

        def claim_post_for_upload(self, post_id):
            raise AssertionError("차단된 게시물은 claim까지 가면 안 됨")

        def mark_post_result(self, post_id, result):
            calls["mark_post_result"].append((post_id, dict(result)))

    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository", lambda: _FakeRepo()
    )

    def _fake_publish_single(*a, **k):
        calls["publish_single"] += 1
        return {"ok": True, "ig_media_id": "should-not-be-called"}

    monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)
    monkeypatch.setattr(launcher_main, "passes_keyword_filter", lambda text: False)

    with caplog.at_level(logging.INFO):
        launcher_main._job_insta_upload()

    assert calls["publish_single"] == 0
    assert len(calls["mark_post_result"]) == 1
    rid, result = calls["mark_post_result"][0]
    assert rid == "rec1"
    assert result["status"] == "rejected"
    assert "[Approval] ready 레코드 처리 시작 | rid=rec1" in caplog.text
    assert "[PublishGate] 텍스트 차단 | rid=rec1" in caplog.text


def test_text_gate_disabled_by_default_preserves_existing_behavior(monkeypatch):
    """PUBLISH_TEXT_GATE_ENABLED 미설정(기본 false) — 기존 동작(게이트 없이 바로 publish) 회귀 없음."""
    monkeypatch.delenv("PUBLISH_TEXT_GATE_ENABLED", raising=False)
    monkeypatch.setenv("INSTA_ACCESS_TOKEN", "fake-token")
    monkeypatch.setenv("INSTA_IG_USER_ID", "fake-iguser")
    monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
    monkeypatch.setenv("YUNA_INSTA_IG_USER_ID", "fake-iguser")
    monkeypatch.setenv("YUNA_INSTA_ACCESS_TOKEN", "fake-token")

    from launcher import main as launcher_main

    calls = {"publish_single": 0, "claim": 0}

    class _FakeRepo:
        def fetch_pending_posts(self, limit=50):
            return [{
                "post_id": "rec2", "image_url": "http://img", "caption": "any text",
                "hashtag": "", "account_code_ref": "IDN-000041",
            }]

        def get_publish_account(self, account_code):
            return {
                "account_code": account_code,
                "api_provider": "facebook_login",
                "ig_user_id": "fake-iguser",
                "credential_key": "YUNA",
            }

        def claim_post_for_upload(self, post_id):
            calls["claim"] += 1
            return True

        def mark_post_result(self, post_id, result):
            pass

    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository", lambda: _FakeRepo()
    )

    def _fake_publish_single(*a, **k):
        calls["publish_single"] += 1
        return {"ok": True, "ig_media_id": "media1"}

    monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)
    # passes_keyword_filter를 False로 세팅해도, 게이트가 꺼져있으면 호출 자체가 안 되어야 함
    monkeypatch.setattr(launcher_main, "passes_keyword_filter", lambda text: False)

    launcher_main._job_insta_upload()

    assert calls["claim"] == 1
    assert calls["publish_single"] == 1


def test_text_gate_passes_through_when_filter_returns_true(monkeypatch):
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "true")
    monkeypatch.setenv("INSTA_ACCESS_TOKEN", "fake-token")
    monkeypatch.setenv("INSTA_IG_USER_ID", "fake-iguser")
    monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
    monkeypatch.setenv("YUNA_INSTA_IG_USER_ID", "fake-iguser")
    monkeypatch.setenv("YUNA_INSTA_ACCESS_TOKEN", "fake-token")

    from launcher import main as launcher_main

    calls = {"publish_single": 0}

    class _FakeRepo:
        def fetch_pending_posts(self, limit=50):
            return [{
                "post_id": "rec3", "image_url": "http://img", "caption": "good text",
                "hashtag": "", "account_code_ref": "IDN-000041",
            }]

        def get_publish_account(self, account_code):
            return {
                "account_code": account_code,
                "api_provider": "facebook_login",
                "ig_user_id": "fake-iguser",
                "credential_key": "YUNA",
            }

        def claim_post_for_upload(self, post_id):
            return True

        def mark_post_result(self, post_id, result):
            pass

    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository", lambda: _FakeRepo()
    )

    def _fake_publish_single(*a, **k):
        calls["publish_single"] += 1
        return {"ok": True, "ig_media_id": "media3"}

    monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)
    monkeypatch.setattr(launcher_main, "passes_keyword_filter", lambda text: True)

    launcher_main._job_insta_upload()

    assert calls["publish_single"] == 1
