"""tests/test_dm_close.py — modules/crm/lead_closer.py TDD 초안 (구현 전 작성)

lead_closer.py 미구현 상태에서는 pytest.importorskip 으로 전체 파일 자동 skip.
구현 완료 후 자동 활성화.
TestCloseFollowupIntegration 은 dm_followup_scheduler.py 연동 완료 전까지 xfail.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

# ── 모듈 가드 ─────────────────────────────────────────────────────────────────
# lead_closer.py 미존재 시 전체 파일 skip — 구현 완료 후 자동 활성화
lead_closer = pytest.importorskip(
    "modules.crm.lead_closer",
    reason="modules/crm/lead_closer.py not yet implemented",
)
mark_lead_closed = lead_closer.mark_lead_closed


# ── 공통 헬퍼 ─────────────────────────────────────────────────────────────────

def _resp(ok: bool = True, status: int = 200) -> MagicMock:
    m = MagicMock()
    m.ok = ok
    m.status_code = status
    m.text = "ok" if ok else "Unprocessable Entity"
    return m


def _extract_all_fields(mock_patch_obj) -> list[dict]:
    """mock requests.patch 호출 목록에서 전송된 fields dict 전부 추출.
    현재 프로덕션 계약(json=)을 우선 확인하고, data=(bytes) 호출도 호환 유지한다."""
    result = []
    for c in mock_patch_obj.call_args_list:
        json_kw = c.kwargs.get("json")
        if isinstance(json_kw, dict):
            result.append(json_kw.get("fields", {}))
            continue
        raw = c.kwargs.get("data")
        if raw is None and len(c.args) > 1:
            raw = c.args[1]
        if isinstance(raw, bytes):
            result.append(json.loads(raw.decode()).get("fields", {}))
    return result


# ── TestCloseTransition ───────────────────────────────────────────────────────

class TestCloseTransition:
    """mark_lead_closed() PATCH payload 정확성 검증."""

    @pytest.fixture(autouse=True)
    def _mock_telegram(self):
        """이 클래스는 PATCH 계약 검증이 목적 — Telegram 실네트워크 호출 방지."""
        with patch("requests.post", return_value=_resp()):
            yield

    def test_close_patches_bridge_status_closed(self, monkeypatch):
        monkeypatch.setenv("AIRTABLE_BASE_ID", "base_test")
        monkeypatch.setenv("AIRTABLE_API_KEY", "key_test")
        with patch("requests.patch", return_value=_resp()) as mp:
            mark_lead_closed("rec_001")
        fields_list = _extract_all_fields(mp)
        assert any(f.get("bridge_status") == "closed" for f in fields_list)

    def test_close_patches_lead_status_converted(self, monkeypatch):
        monkeypatch.setenv("AIRTABLE_BASE_ID", "base_test")
        monkeypatch.setenv("AIRTABLE_API_KEY", "key_test")
        with patch("requests.patch", return_value=_resp()) as mp:
            mark_lead_closed("rec_001")
        fields_list = _extract_all_fields(mp)
        assert any(f.get("lead_status") == "converted" for f in fields_list)

    def test_close_records_closed_at(self, monkeypatch):
        monkeypatch.setenv("AIRTABLE_BASE_ID", "base_test")
        monkeypatch.setenv("AIRTABLE_API_KEY", "key_test")
        with patch("requests.patch", return_value=_resp()) as mp:
            mark_lead_closed("rec_001")
        fields_list = _extract_all_fields(mp)
        assert any("closed_at" in f for f in fields_list), \
            "closed_at 가 어느 PATCH payload 에도 없음"

    def test_close_closed_at_is_utc_iso(self, monkeypatch):
        monkeypatch.setenv("AIRTABLE_BASE_ID", "base_test")
        monkeypatch.setenv("AIRTABLE_API_KEY", "key_test")
        with patch("requests.patch", return_value=_resp()) as mp:
            mark_lead_closed("rec_001")
        fields_list = _extract_all_fields(mp)
        closed_at_values = [f["closed_at"] for f in fields_list if "closed_at" in f]
        assert closed_at_values, "closed_at 값이 payload 에 없음"
        val = closed_at_values[0]
        assert "T" in val and ("Z" in val or "+00:00" in val), \
            f"UTC ISO8601 포맷 아님: {val}"

    def test_close_patch_url_contains_record_id(self, monkeypatch):
        monkeypatch.setenv("AIRTABLE_BASE_ID", "base_test")
        monkeypatch.setenv("AIRTABLE_API_KEY", "key_test")
        with patch("requests.patch", return_value=_resp()) as mp:
            mark_lead_closed("rec_target_xyz")
        urls = [c.args[0] for c in mp.call_args_list if c.args]
        assert any("rec_target_xyz" in url for url in urls), \
            "PATCH URL 에 record_id 미포함"


# ── TestCloseEdgeCases ────────────────────────────────────────────────────────

class TestCloseEdgeCases:
    """방어 로직 / 오류 처리 검증."""

    def test_close_none_record_id_safe(self, monkeypatch):
        monkeypatch.setenv("AIRTABLE_BASE_ID", "base_test")
        monkeypatch.setenv("AIRTABLE_API_KEY", "key_test")
        with patch("requests.patch", return_value=_resp()):
            mark_lead_closed(None)  # 예외 없이 조기 반환 확인

    def test_close_empty_record_id_safe(self, monkeypatch):
        monkeypatch.setenv("AIRTABLE_BASE_ID", "base_test")
        monkeypatch.setenv("AIRTABLE_API_KEY", "key_test")
        with patch("requests.patch", return_value=_resp()):
            mark_lead_closed("")  # 예외 없이 조기 반환 확인

    def test_close_patch_failure_does_not_raise(self, monkeypatch):
        monkeypatch.setenv("AIRTABLE_BASE_ID", "base_test")
        monkeypatch.setenv("AIRTABLE_API_KEY", "key_test")
        with patch("requests.patch", return_value=_resp(ok=False, status=422)):
            mark_lead_closed("rec_001")  # 422 응답에도 예외 미전파

    def test_close_network_exception_does_not_raise(self, monkeypatch):
        monkeypatch.setenv("AIRTABLE_BASE_ID", "base_test")
        monkeypatch.setenv("AIRTABLE_API_KEY", "key_test")
        with patch("requests.patch", side_effect=ConnectionError("timeout")):
            mark_lead_closed("rec_001")  # 네트워크 오류에도 예외 미전파

    def test_close_idempotent_on_double_call(self, monkeypatch):
        """동일 record 에 두 번 호출해도 무해하게 완료 (무한 재시도 없음)."""
        monkeypatch.setenv("AIRTABLE_BASE_ID", "base_test")
        monkeypatch.setenv("AIRTABLE_API_KEY", "key_test")
        with patch("requests.patch", return_value=_resp()) as mp:
            mark_lead_closed("rec_001")
            mark_lead_closed("rec_001")
        # 2호출 × 최대 2 PATCH씩 = 4 이내여야 함 (재시도 루프 없음)
        assert mp.call_count <= 4


# ── TestCloseTelegramAlert ────────────────────────────────────────────────────

class TestCloseTelegramAlert:
    """Telegram 알림 발송 조건 검증."""

    def test_close_telegram_sent_when_token_set(self, monkeypatch):
        monkeypatch.setenv("AIRTABLE_BASE_ID", "base_test")
        monkeypatch.setenv("AIRTABLE_API_KEY", "key_test")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok_test")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat_test")
        with patch("requests.patch", return_value=_resp()):
            with patch("requests.post", return_value=_resp()) as tg:
                mark_lead_closed("rec_001")
        assert tg.called, "TELEGRAM_BOT_TOKEN 존재하는데 Telegram POST 미호출"

    def test_close_telegram_skipped_when_no_token(self, monkeypatch):
        monkeypatch.setenv("AIRTABLE_BASE_ID", "base_test")
        monkeypatch.setenv("AIRTABLE_API_KEY", "key_test")
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        with patch("requests.patch", return_value=_resp()):
            with patch("requests.post", return_value=_resp()) as tg:
                mark_lead_closed("rec_001")
        assert not tg.called, "TELEGRAM_BOT_TOKEN 없는데 Telegram POST 호출됨"


# ── TestCloseFollowupIntegration ──────────────────────────────────────────────

@pytest.mark.xfail(
    reason="dm_followup_scheduler.py에 mark_lead_closed 연동 미완료 — 다음 구현 단계에서 활성화",
    strict=False,
)
class TestCloseFollowupIntegration:
    """followup_scheduler 와 CLOSE 연동 검증.

    dm_followup_scheduler.py 수정 완료 후 xfail → pass 로 전환 예상.
    strict=False: xpass 허용 (구현 완료 시 자동 통과).
    """

    def test_followup3_completion_invokes_close(self, monkeypatch):
        """process_due_followups() 가 followup2→followup3 전환 완료 시 mark_lead_closed 호출."""
        from modules.dm import dm_followup_scheduler

        closed_records = []
        monkeypatch.setattr(
            "modules.crm.lead_closer.mark_lead_closed",
            lambda rid: closed_records.append(rid),
        )
        monkeypatch.setattr(
            dm_followup_scheduler,
            "_at_get_due_records",
            lambda: [{
                "id": "rec_followup3",
                "fields": {
                    "bridge_status":       "followup2_sent",
                    "inquiry_user_handle": "ig_user_test",
                    "relay_scheduled_at":  "2000-01-01T00:00:00.000Z",
                },
            }],
        )
        monkeypatch.setattr(dm_followup_scheduler, "_send_ig_dm", lambda igsid, text: True)
        monkeypatch.setattr(dm_followup_scheduler, "_at_patch", lambda *a, **k: None)
        monkeypatch.setattr(dm_followup_scheduler, "_send_telegram_followup", lambda *a: None)

        dm_followup_scheduler.process_due_followups()

        assert "rec_followup3" in closed_records, \
            "followup3_sent 완료 후 mark_lead_closed 미호출"

    def test_followup3_dm_failure_does_not_invoke_close(self, monkeypatch):
        """followup3 DM 발송 실패 시 mark_lead_closed 미호출."""
        from modules.dm import dm_followup_scheduler

        closed_records = []
        monkeypatch.setattr(
            "modules.crm.lead_closer.mark_lead_closed",
            lambda rid: closed_records.append(rid),
        )
        monkeypatch.setattr(
            dm_followup_scheduler,
            "_at_get_due_records",
            lambda: [{
                "id": "rec_followup3_fail",
                "fields": {
                    "bridge_status":       "followup2_sent",
                    "inquiry_user_handle": "ig_user_test",
                    "relay_scheduled_at":  "2000-01-01T00:00:00.000Z",
                },
            }],
        )
        monkeypatch.setattr(dm_followup_scheduler, "_send_ig_dm", lambda igsid, text: False)
        monkeypatch.setattr(dm_followup_scheduler, "_at_patch", lambda *a, **k: None)
        monkeypatch.setattr(dm_followup_scheduler, "_send_telegram_followup", lambda *a: None)

        dm_followup_scheduler.process_due_followups()

        assert "rec_followup3_fail" not in closed_records, \
            "DM 발송 실패인데 mark_lead_closed 호출됨"

    def test_followup3_close_does_not_update_relay_scheduled_at(self, monkeypatch):
        """followup3_sent 완료 후 relay_scheduled_at 갱신 없음 — 스케줄 체인 종료 확인."""
        from modules.dm import dm_followup_scheduler

        patched_fields: dict = {}
        monkeypatch.setattr(
            "modules.crm.lead_closer.mark_lead_closed",
            lambda rid: None,
        )
        monkeypatch.setattr(
            dm_followup_scheduler,
            "_at_get_due_records",
            lambda: [{
                "id": "rec_chain_end",
                "fields": {
                    "bridge_status":       "followup2_sent",
                    "inquiry_user_handle": "ig_user_test",
                    "relay_scheduled_at":  "2000-01-01T00:00:00.000Z",
                },
            }],
        )
        monkeypatch.setattr(dm_followup_scheduler, "_send_ig_dm", lambda igsid, text: True)
        monkeypatch.setattr(
            dm_followup_scheduler,
            "_at_patch",
            lambda rid, fields: patched_fields.update(fields),
        )
        monkeypatch.setattr(dm_followup_scheduler, "_send_telegram_followup", lambda *a: None)

        dm_followup_scheduler.process_due_followups()

        assert "relay_scheduled_at" not in patched_fields, \
            "followup3_sent 후 relay_scheduled_at 갱신됨 — 스케줄 체인 미종료"
