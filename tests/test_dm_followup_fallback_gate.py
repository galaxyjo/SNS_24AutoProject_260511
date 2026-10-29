"""tests/test_dm_followup_fallback_gate.py — 260730 DM Routing Close Gate.

dm_followup_scheduler.py::_send_ig_dm()이 dm_auto_reply.py::send_ig_reply()와
동일한 fallback 차단 정책을 따르는지 검증한다(REUSE 계약 확인). 실제 네트워크
호출 없이 전부 monkeypatch.

modules.dm.dm_followup_scheduler를 정상 경로로 import하면 modules/dm/__init__.py가
dm_receiver.py를 통해 runtime_boot_policy.json을 확인하려다 이 환경에서
PermissionError를 던진다(기존에 반복 문서화된 환경제약, 이 파일과 무관) —
이 파일은 그 제약이 없는 환경(CI/회장 터미널)에서 실행하기 위해 작성한다.
"""

import pytest

import modules.dm.dm_auto_reply as dm_auto_reply
import modules.dm.dm_followup_scheduler as dm_followup_scheduler


class _FakeRepo:
    def __init__(self, accounts: dict):
        self._accounts = accounts

    def get_publish_account(self, account_code_ref):
        return self._accounts.get(account_code_ref)


@pytest.fixture(autouse=True)
def _restore_repo():
    original = dm_auto_reply._repo
    yield
    dm_auto_reply._repo = original


def test_send_ig_dm_skips_fallback_for_other_account_when_unresolved(monkeypatch):
    """account_code_ref가 aijomoojin 등 전역 fallback 소유자(yuna18253)가 아닌데
    해석에 실패하면, 전역 fallback으로 실제 발송을 시도하지 않고 즉시 False를
    반환해야 한다(호출자가 retry_queue로 위임)."""
    dm_auto_reply._repo = _FakeRepo({})  # 조회 실패 → target=None

    called = {"post": False}

    def _fake_post(*a, **k):
        called["post"] = True
        raise AssertionError("전역 fallback으로 실제 발송을 시도하면 안 된다")

    monkeypatch.setattr(dm_followup_scheduler.requests, "post", _fake_post)

    sent = dm_followup_scheduler._send_ig_dm("sender1", "hello", account_code_ref="IDN-000036")

    assert sent is False
    assert called["post"] is False


def test_send_ig_dm_still_falls_back_when_unresolved_account_is_the_fallback_owner(monkeypatch):
    """account_code_ref가 전역 fallback 소유 계정(yuna18253) 자신이면, 해석에
    실패해도 결과가 동일하므로 기존 전역 fallback을 그대로 유지해야 한다(회귀 방지)."""
    dm_auto_reply._repo = _FakeRepo({})
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "868456346356581")
    monkeypatch.setattr(dm_followup_scheduler, "_get_page_token", lambda: "global-fallback-token")

    captured = {}

    class _FakeResp:
        ok = True

        def json(self):
            return {"message_id": "mid_yuna"}

    def _fake_post(url, headers=None, data=None, timeout=None):
        captured["called"] = True
        return _FakeResp()

    monkeypatch.setattr(dm_followup_scheduler.requests, "post", _fake_post)

    sent = dm_followup_scheduler._send_ig_dm(
        "sender1", "hello",
        account_code_ref=dm_auto_reply.GLOBAL_FALLBACK_ACCOUNT_CODE_REF,
    )

    assert sent is True
    assert captured.get("called") is True


def test_send_ig_dm_blocks_when_account_code_ref_empty(monkeypatch):
    """261029 STEP 1 — account_code_ref가 공란(미식별)이면 전역(yuna) 경로로 발송하지 않고 False."""
    dm_auto_reply._repo = _FakeRepo({})
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "111222333")
    monkeypatch.setattr(dm_followup_scheduler, "_get_page_token", lambda: "global-fallback-token")

    called = {"post": 0}

    def _fake_post(*a, **k):
        called["post"] += 1
        raise AssertionError("공란 참조로 실제 발송을 시도하면 안 된다")

    monkeypatch.setattr(dm_followup_scheduler.requests, "post", _fake_post)

    sent = dm_followup_scheduler._send_ig_dm("sender1", "hello", account_code_ref="")

    assert sent is False
    assert called["post"] == 0


def _due_record(record_id, account_code_ref):
    return {"id": record_id, "igsid": "sender1", "bridge_status": "auto_replied",
            "account_code_ref": account_code_ref}


class _FakeFollowupRepo:
    def __init__(self, records):
        self._records = records
        self.patches = []
        self.status_updates = []

    def fetch_leads_due(self, statuses, before_iso, limit=20):
        return self._records

    def _patch_lead_interaction(self, record_id, fields):
        self.patches.append((record_id, fields))

    def update_followup_status(self, *a, **k):
        self.status_updates.append((a, k))


def test_process_due_followups_marks_error_and_sends_nothing_when_account_unresolved(monkeypatch):
    """공란 참조 레코드는 _send_ig_dm·retry_queue 모두 호출하지 않고 followup_error로 표시한다."""
    repo = _FakeFollowupRepo([_due_record("recBlank", "")])
    monkeypatch.setattr(dm_followup_scheduler, "_repo", repo)
    sends = []
    monkeypatch.setattr(dm_followup_scheduler, "_send_ig_dm", lambda *a, **k: sends.append(a) or True)

    dm_followup_scheduler.process_due_followups()

    assert sends == []
    assert repo.patches == [("recBlank", {
        "bridge_status": "followup_error",
        "last_error_msg": "ACCOUNT_UNRESOLVED_FOLLOWUP_SKIPPED",
    })]
    assert repo.status_updates == []


def test_process_due_followups_still_sends_for_global_fallback_account(monkeypatch):
    """IDN-000041 레코드는 기존대로 발송되고 다음 단계로 전진한다(회귀 방지)."""
    repo = _FakeFollowupRepo([_due_record("rec041", "IDN-000041")])
    monkeypatch.setattr(dm_followup_scheduler, "_repo", repo)
    sends = []
    monkeypatch.setattr(dm_followup_scheduler, "_send_ig_dm", lambda *a, **k: sends.append(a) or True)
    monkeypatch.setattr(dm_followup_scheduler, "_send_telegram_followup", lambda *a, **k: None)

    dm_followup_scheduler.process_due_followups()

    assert len(sends) == 1 and sends[0][2] == "IDN-000041"
    assert repo.patches == []
    assert len(repo.status_updates) == 1
