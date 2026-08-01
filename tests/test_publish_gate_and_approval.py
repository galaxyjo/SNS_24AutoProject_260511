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
    monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")

    from launcher import main as launcher_main

    calls = {"publish_single": 0, "mark_post_result": []}

    class _FakeRepo:
        def fetch_pending_posts(self, limit=50):
            return [{
                "post_id": "rec1", "image_url": "http://img", "caption": "blocked text",
                "hashtag": "", "account_code_ref": "IDN-000041",
            }]

        def get_publish_account(self, account_code):
            return {
                "account_code": account_code,
                "api_provider": "facebook_login",
                "ig_user_id": "fake-iguser",
                "credential_key": "YUNA",
                "automation_enabled": True,
            }

        def claim_post_for_upload(self, post_id):
            raise AssertionError("차단된 게시물은 claim까지 가면 안 됨")

        def mark_post_result(self, post_id, result):
            calls["mark_post_result"].append((post_id, dict(result)))

    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository", lambda: _FakeRepo()
    )
    # 기존 REUSE 패턴(test_insta_upload_batch_isolation.py) — 이 테스트 목적과 무관한
    # 선행 Canary 분류 검증만 격리, assert는 약화하지 않음.
    monkeypatch.setattr(
        "modules.common.canary_classification.validate_publication_candidate",
        lambda *a, **k: None,
    )

    def _fake_publish_single(*a, **k):
        calls["publish_single"] += 1
        return {"ok": True, "ig_media_id": "should-not-be-called"}

    monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)
    monkeypatch.setattr(
        launcher_main, "resolve_publish_gate",
        lambda caption, account_code_ref, **k: (False, "DOMAIN_CONTENT_REJECTED"),
    )

    with caplog.at_level(logging.INFO):
        launcher_main._job_insta_upload()

    assert calls["publish_single"] == 0
    assert len(calls["mark_post_result"]) == 1
    rid, result = calls["mark_post_result"][0]
    assert rid == "rec1"
    assert result["status"] == "rejected"
    assert result["error_code"] == "DOMAIN_CONTENT_REJECTED"
    assert "[Approval] ready 레코드 처리 시작 | rid=rec1" in caplog.text
    assert "[PublishGate] DOMAIN_CONTENT_REJECTED | rid=rec1" in caplog.text


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
                "automation_enabled": True,
            }

        def claim_post_for_upload(self, post_id):
            calls["claim"] += 1
            return True

        def mark_post_result(self, post_id, result):
            pass

    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository", lambda: _FakeRepo()
    )
    monkeypatch.setattr(
        "modules.common.canary_classification.validate_publication_candidate",
        lambda *a, **k: None,
    )

    def _fake_publish_single(*a, **k):
        calls["publish_single"] += 1
        return {"ok": True, "ig_media_id": "media1"}

    monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)
    # resolve_publish_gate를 차단으로 세팅해도, 게이트가 꺼져있으면 호출 자체가 안 되어야 함
    monkeypatch.setattr(
        launcher_main, "resolve_publish_gate",
        lambda caption, account_code_ref, **k: (False, "DOMAIN_CONTENT_REJECTED"),
    )

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
                "automation_enabled": True,
            }

        def claim_post_for_upload(self, post_id):
            return True

        def mark_post_result(self, post_id, result):
            pass

    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository", lambda: _FakeRepo()
    )
    monkeypatch.setattr(
        "modules.common.canary_classification.validate_publication_candidate",
        lambda *a, **k: None,
    )

    def _fake_publish_single(*a, **k):
        calls["publish_single"] += 1
        return {"ok": True, "ig_media_id": "media3"}

    monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)
    monkeypatch.setattr(
        launcher_main, "resolve_publish_gate",
        lambda caption, account_code_ref, **k: (True, "PUBLISH_ALLOWED"),
    )

    launcher_main._job_insta_upload()

    assert calls["publish_single"] == 1


def test_text_gate_blank_account_code_ref_rejected_by_main_py_identity_gate(monkeypatch, caplog):
    """Identity 판정은 main.py 소유 — 공란 account_code_ref는 resolve_publish_gate() 호출 전에
    main.py 자체에서 차단해야 한다(Track B-1E, 260731. Router에 Identity 중복 구현 금지 증거)."""
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "true")
    monkeypatch.setenv("INSTA_ACCESS_TOKEN", "fake-token")
    monkeypatch.setenv("INSTA_IG_USER_ID", "fake-iguser")

    from launcher import main as launcher_main

    calls = {"publish_single": 0, "mark_post_result": [], "resolve_publish_gate": 0}

    class _FakeRepo:
        def fetch_pending_posts(self, limit=50):
            return [{
                "post_id": "rec4", "image_url": "http://img", "caption": "아무 캡션",
                "hashtag": "",  # account_code_ref 없음(공란)
            }]

        def claim_post_for_upload(self, post_id):
            raise AssertionError("차단된 게시물은 claim까지 가면 안 됨")

        def mark_post_result(self, post_id, result):
            calls["mark_post_result"].append((post_id, dict(result)))

    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository", lambda: _FakeRepo()
    )
    monkeypatch.setattr(
        "modules.common.canary_classification.validate_publication_candidate",
        lambda *a, **k: None,
    )

    def _fake_publish_single(*a, **k):
        calls["publish_single"] += 1
        return {"ok": True, "ig_media_id": "should-not-be-called"}

    def _spy_resolve_publish_gate(caption, account_code_ref):
        calls["resolve_publish_gate"] += 1
        return (False, "DOMAIN_CONTENT_REJECTED")

    monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)
    monkeypatch.setattr(launcher_main, "resolve_publish_gate", _spy_resolve_publish_gate)

    with caplog.at_level(logging.INFO):
        launcher_main._job_insta_upload()

    # Router는 호출조차 되지 않아야 함 — Identity 중복 제거 증거
    assert calls["resolve_publish_gate"] == 0
    assert calls["publish_single"] == 0
    assert len(calls["mark_post_result"]) == 1
    rid, result = calls["mark_post_result"][0]
    assert rid == "rec4"
    assert result["status"] == "rejected"
    assert result["error_code"] == "IDENTITY_REJECTED"
    assert "[PublishGate] IDENTITY_REJECTED | rid=rec4" in caplog.text


def test_text_gate_unregistered_account_code_ref_rejected_by_identity_before_router(monkeypatch, caplog):
    """비공란이지만 Account_Registry 조회 실패(미등록) 계정 — Router 호출 전 Identity Gate에서
    IDENTITY_REJECTED로 차단해야 한다(Track B-1G, 260731)."""
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "true")
    monkeypatch.setenv("INSTA_ACCESS_TOKEN", "fake-token")
    monkeypatch.setenv("INSTA_IG_USER_ID", "fake-iguser")
    monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")

    from launcher import main as launcher_main

    calls = {"publish_single": 0, "mark_post_result": [], "resolve_publish_gate": 0}

    class _FakeRepo:
        def fetch_pending_posts(self, limit=50):
            return [{
                "post_id": "rec5", "image_url": "http://img", "caption": "아무 캡션",
                "hashtag": "", "account_code_ref": "IDN-999999",
            }]

        def get_publish_account(self, account_code):
            return None  # 미등록 — Account_Registry 조회 실패 시뮬레이션

        def claim_post_for_upload(self, post_id):
            raise AssertionError("차단된 게시물은 claim까지 가면 안 됨")

        def mark_post_result(self, post_id, result):
            calls["mark_post_result"].append((post_id, dict(result)))

    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository", lambda: _FakeRepo()
    )
    monkeypatch.setattr(
        "modules.common.canary_classification.validate_publication_candidate",
        lambda *a, **k: None,
    )

    def _fake_publish_single(*a, **k):
        calls["publish_single"] += 1
        return {"ok": True, "ig_media_id": "should-not-be-called"}

    def _spy_resolve_publish_gate(caption, account_code_ref):
        calls["resolve_publish_gate"] += 1
        return (False, "DOMAIN_CONTENT_REJECTED")

    monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)
    monkeypatch.setattr(launcher_main, "resolve_publish_gate", _spy_resolve_publish_gate)

    with caplog.at_level(logging.INFO):
        launcher_main._job_insta_upload()

    assert calls["resolve_publish_gate"] == 0
    assert calls["publish_single"] == 0
    assert len(calls["mark_post_result"]) == 1
    rid, result = calls["mark_post_result"][0]
    assert rid == "rec5"
    assert result["status"] == "rejected"
    assert result["error_code"] == "IDENTITY_REJECTED"
    assert "[PublishGate] IDENTITY_REJECTED | rid=rec5" in caplog.text


def test_text_gate_registered_account_not_in_domain_policy_returns_unknown_domain(monkeypatch):
    """등록됐지만(Identity 통과) ACCOUNT_DOMAIN_POLICY Allowlist에 없는 계정 — Router까지
    도달해 UNKNOWN_DOMAIN으로 차단해야 한다(Track B-1G, 260731. 실제 resolve_publish_gate 사용,
    monkeypatch로 대체하지 않음)."""
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "true")
    monkeypatch.setenv("INSTA_ACCESS_TOKEN", "fake-token")
    monkeypatch.setenv("INSTA_IG_USER_ID", "fake-iguser")
    monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")

    from launcher import main as launcher_main

    calls = {"publish_single": 0, "mark_post_result": []}

    class _FakeRepo:
        def fetch_pending_posts(self, limit=50):
            return [{
                "post_id": "rec6", "image_url": "http://img", "caption": "아무 캡션",
                "hashtag": "", "account_code_ref": "IDN-000099",
            }]

        def get_publish_account(self, account_code):
            return {
                "account_code": account_code,
                "api_provider": "facebook_login",
                "ig_user_id": "fake-iguser",
                "credential_key": "YUNA",
                "automation_enabled": True,
            }

        def claim_post_for_upload(self, post_id):
            raise AssertionError("차단된 게시물은 claim까지 가면 안 됨")

        def mark_post_result(self, post_id, result):
            calls["mark_post_result"].append((post_id, dict(result)))

    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository", lambda: _FakeRepo()
    )
    monkeypatch.setattr(
        "modules.common.canary_classification.validate_publication_candidate",
        lambda *a, **k: None,
    )

    def _fake_publish_single(*a, **k):
        calls["publish_single"] += 1
        return {"ok": True, "ig_media_id": "should-not-be-called"}

    monkeypatch.setattr(launcher_main, "publish_single", _fake_publish_single)
    # resolve_publish_gate는 실제 함수 그대로 사용 — IDN-000099는 ACCOUNT_DOMAIN_POLICY에 없음

    launcher_main._job_insta_upload()

    assert calls["publish_single"] == 0
    assert len(calls["mark_post_result"]) == 1
    rid, result = calls["mark_post_result"][0]
    assert rid == "rec6"
    assert result["status"] == "rejected"
    assert result["error_code"] == "UNKNOWN_DOMAIN"


# ── 4. resolve_publish_gate() — Account Domain Routing 단위 매트릭스 (Track B-1D/1E, 260731) ──

def test_gate_product_account_normal_caption_allowed():
    from modules.sns.content_filter import resolve_publish_gate

    allowed, code = resolve_publish_gate("Isntree 도매 재고있음 세럼", "IDN-000041")
    assert allowed is True
    assert code == "PUBLISH_ALLOWED"


def test_gate_product_account_non_wholesale_caption_rejected():
    from modules.sns.content_filter import resolve_publish_gate

    allowed, code = resolve_publish_gate("오늘 날씨가 좋네요", "IDN-000041")
    assert allowed is False
    assert code == "DOMAIN_CONTENT_REJECTED"


def test_gate_ai_content_account_without_v0_kwargs_fails_closed():
    """260801 AI_CONTENT Gate v0 — 무조건 DOMAIN_GATE_NOT_READY이던 이전 동작은
    폐기됐다(GPT 검수 승인, Gate v0 구현). source_url/persona_code 없이 호출하면
    (이전 2-인자 호출 방식) 여전히 Fail-closed로 차단되지만 사유가 달라진다 —
    자세한 5개 조건별 테스트는 tests/test_ai_content_gate_v0.py 참조."""
    from modules.sns.content_filter import resolve_publish_gate

    allowed, code = resolve_publish_gate("아무 정상적인 컨설팅 콘텐츠 캡션", "IDN-000036")
    assert allowed is False
    assert code in ("AI_CONTENT_PERSONA_MISMATCH", "AI_CONTENT_NO_SOURCE")


def test_gate_unknown_account_code_rejected():
    from modules.sns.content_filter import resolve_publish_gate

    allowed, code = resolve_publish_gate("아무 캡션", "IDN-999999")
    assert allowed is False
    assert code == "UNKNOWN_DOMAIN"


def test_gate_router_does_not_duplicate_identity_check():
    """Router는 Identity를 판정하지 않는다 — 공란 account_code_ref는 Domain Routing
    미스(UNKNOWN_DOMAIN)로 수렴할 뿐, IDENTITY_REJECTED를 자체 생성하지 않는다.
    (실제 공란 계정 차단은 main.py 소유 — 위 test_text_gate_blank_account_code_ref_*
    통합테스트 참조, Track B-1E 260731 Identity 중복 제거 증거)"""
    from modules.sns.content_filter import resolve_publish_gate

    allowed, code = resolve_publish_gate("아무 캡션", "")
    assert allowed is False
    assert code == "UNKNOWN_DOMAIN"


def test_gate_blocklist_rejects_regardless_of_account():
    from modules.sns.content_filter import resolve_publish_gate

    allowed_a, code_a = resolve_publish_gate("coslife 신상 재입고", "IDN-000041")
    allowed_b, code_b = resolve_publish_gate("coslife 신상 재입고", "IDN-000036")
    assert (allowed_a, code_a) == (False, "GLOBAL_SAFETY_REJECTED")
    assert (allowed_b, code_b) == (False, "GLOBAL_SAFETY_REJECTED")


def test_gate_router_exception_fails_closed(monkeypatch):
    import modules.sns.content_filter as content_filter

    def _boom(text):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(content_filter, "passes_keyword_filter", _boom)

    allowed, code = content_filter.resolve_publish_gate("정상 캡션", "IDN-000041")
    assert allowed is False
    assert code == "PUBLISH_GATE_INTERNAL_ERROR"
