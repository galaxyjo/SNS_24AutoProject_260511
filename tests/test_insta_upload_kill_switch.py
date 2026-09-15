"""260915 — launcher/main.py::_job_insta_upload Kill Switch 계약 복구 검증.

결함: automation_enabled=false 분기가 _identity_reject() 를 호출해,
PUBLISH_TEXT_GATE_ENABLED=true 에서 ready 게시물을 post_status=rejected 로 영구 변경했다
(9/15 09:04 운영 2건). Kill Switch OFF 는 "보류"이고, Identity 실패만 "거절"이다.

실제 Airtable·실제 게시·실제 자격증명·Slack 없음 — 전부 Mock.
claim_post_for_upload 는 호출을 기록하고 False 를 반환해 publish 직전에서 멈춘다
(= 해당 레코드가 Kill Switch·Gate 를 통과해 게시 경로에 들어갔다는 증거).
"""

import logging
from types import SimpleNamespace

import pytest

READY = {
    "post_id": "rec1",
    "image_url": "http://img",
    "caption": "Korean serum wholesale restock",
    "hashtag": "",
    "account_code_ref": "IDN-000041",
}


@pytest.fixture
def launcher(monkeypatch):
    monkeypatch.delenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", raising=False)
    monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
    monkeypatch.setenv("INSTA_ACCESS_TOKEN", "fake-token")
    monkeypatch.setenv("INSTA_IG_USER_ID", "fake-iguser")
    from launcher import main as m
    return m


def _setup(monkeypatch, m, *, automation_enabled=True, account_missing=False,
           account_code_ref="IDN-000041"):
    calls = SimpleNamespace(claim=[], mark=[], publish=0)
    record = dict(READY, account_code_ref=account_code_ref)

    class Repo:
        def fetch_pending_posts(self, limit=50):
            return [dict(record)]

        def get_publish_account(self, code):
            if account_missing:
                return None
            return {
                "account_code": code,
                "api_provider": "facebook_login",
                "ig_user_id": "fake-iguser",
                "credential_key": "YUNA",
                "automation_enabled": automation_enabled,
            }

        def claim_post_for_upload(self, post_id):
            calls.claim.append(post_id)
            return False                                   # 게시 직전에서 멈춤

        def mark_post_result(self, post_id, result):
            calls.mark.append((post_id, dict(result)))

    monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: Repo())
    monkeypatch.setattr(
        "modules.common.canary_classification.validate_publication_candidate",
        lambda *a, **k: None,
    )

    def _publish(*a, **k):
        calls.publish += 1
        return {"ok": True, "ig_media_id": "must-not-publish"}

    monkeypatch.setattr(m, "publish_single", _publish)
    monkeypatch.setattr(m, "resolve_publish_gate", lambda caption, code, **k: (True, "PUBLISH_ALLOWED"))
    # _job_insta_upload 가 함수 안에서 import 하므로 원본 모듈 속성을 교체한다.
    monkeypatch.setattr(
        "modules.common.credential_resolver.resolve_credential",
        lambda key: SimpleNamespace(ig_user_id="fake-iguser", access_token="fake-token"),
    )
    return calls


# ── 1. Kill Switch OFF = 보류: 상태 변화 0, claim 0, 게시 0 (Gate ON/OFF 모두) ──
@pytest.mark.parametrize("gate", ["true", "false"])
def test_kill_switch_off_holds_ready_without_status_change(monkeypatch, launcher, caplog, gate):
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", gate)
    calls = _setup(monkeypatch, launcher, automation_enabled=False)
    with caplog.at_level(logging.INFO):
        launcher._job_insta_upload()
    assert calls.mark == []                               # rejected 기록 금지
    assert calls.claim == []
    assert calls.publish == 0
    assert "계정별 Kill Switch OFF — 처리 보류 | rid=rec1" in caplog.text
    assert "IDENTITY_REJECTED" not in caplog.text


# ── 2. Kill Switch ON = 같은 레코드가 게시 경로(claim)까지 진행 ────────────────
@pytest.mark.parametrize("gate", ["true", "false"])
def test_kill_switch_on_record_proceeds_to_publish_path(monkeypatch, launcher, caplog, gate):
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", gate)
    calls = _setup(monkeypatch, launcher, automation_enabled=True)
    with caplog.at_level(logging.INFO):
        launcher._job_insta_upload()
    assert calls.claim == ["rec1"]
    assert calls.mark == []
    assert "Kill Switch OFF" not in caplog.text


# ── 3. OFF → ON 전환: OFF 동안 보류된 ready 가 ON 이후 게시 후보로 복귀 ────────
def test_off_then_on_same_ready_record_returns_to_candidates(monkeypatch, launcher, caplog):
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "true")
    off = _setup(monkeypatch, launcher, automation_enabled=False)
    launcher._job_insta_upload()
    assert off.mark == [] and off.claim == []

    on = _setup(monkeypatch, launcher, automation_enabled=True)
    launcher._job_insta_upload()
    assert on.claim == ["rec1"]
    assert on.mark == []


# ── 4. 실제 Identity 실패는 기존대로 rejected 유지 ─────────────────────────────
def test_identity_failure_empty_account_code_still_rejected(monkeypatch, launcher, caplog):
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "true")
    calls = _setup(monkeypatch, launcher, account_code_ref="")
    with caplog.at_level(logging.INFO):
        launcher._job_insta_upload()
    assert len(calls.mark) == 1
    rid, result = calls.mark[0]
    assert rid == "rec1"
    assert result["status"] == "rejected"
    assert result["error_code"] == "IDENTITY_REJECTED"
    assert calls.claim == [] and calls.publish == 0


def test_identity_failure_account_not_found_still_rejected(monkeypatch, launcher, caplog):
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "true")
    calls = _setup(monkeypatch, launcher, account_missing=True)
    with caplog.at_level(logging.INFO):
        launcher._job_insta_upload()
    assert len(calls.mark) == 1
    assert calls.mark[0][1]["status"] == "rejected"
    assert calls.mark[0][1]["error_code"] == "IDENTITY_REJECTED"
    assert calls.claim == [] and calls.publish == 0
