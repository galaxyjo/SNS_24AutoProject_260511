"""tests/test_create_lead_interaction_account_code_ref.py — Bundle B(260726):
LeadInteractionCreate.account_code_ref는 선택 필드이며, 값이 있을 때만 Airtable
payload에 포함돼야 한다(기존 source_event_id와 동일 패턴). 댓글 Caller가 이 필드를
안 넘기는 기존 호출 방식도 무변화로 계속 동작해야 한다."""

from unittest.mock import MagicMock, patch

from modules.infra.airtable_repository import AirtableRepository
from modules.infra.repository_interface import LeadInteractionCreate


def _resp() -> MagicMock:
    r = MagicMock()
    r.raise_for_status.return_value = None
    r.json.return_value = {"id": "recNEW"}
    return r


def _sent_fields(mock_post) -> dict:
    """requests.post(..., json={"fields": {...}}, ...) 호출에서 fields dict를 그대로 꺼낸다."""
    return mock_post.call_args.kwargs["json"]["fields"]


class TestCreateLeadInteractionAccountCodeRef:
    def test_account_code_ref_included_when_present(self):
        data = LeadInteractionCreate(
            igsid="sender1", source="instagram_dm", interaction_type="dm_received",
            occurred_at="2026-07-26T00:00:00Z", inquiry_message="hi",
            account_code_ref="IDN-000041",
        )
        with patch("modules.infra.airtable_repository.requests.post", return_value=_resp()) as mock_post:
            AirtableRepository().create_lead_interaction(data)
        fields = _sent_fields(mock_post)
        assert fields["account_code_ref"] == "IDN-000041"

    def test_account_code_ref_omitted_when_absent(self):
        """DM 경로에서 account_code_ref="" 로 넘어오거나(Bundle B fail-open) 아예 키가
        없을 때, Airtable payload에 이 필드 자체가 안 실려야 한다."""
        data = LeadInteractionCreate(
            igsid="sender1", source="instagram_dm", interaction_type="dm_received",
            occurred_at="2026-07-26T00:00:00Z", inquiry_message="hi",
        )
        with patch("modules.infra.airtable_repository.requests.post", return_value=_resp()) as mock_post:
            AirtableRepository().create_lead_interaction(data)
        fields = _sent_fields(mock_post)
        assert "account_code_ref" not in fields

    def test_account_code_ref_empty_string_omitted(self):
        data = LeadInteractionCreate(
            igsid="sender1", source="instagram_dm", interaction_type="dm_received",
            occurred_at="2026-07-26T00:00:00Z", inquiry_message="hi",
            account_code_ref="",
        )
        with patch("modules.infra.airtable_repository.requests.post", return_value=_resp()) as mock_post:
            AirtableRepository().create_lead_interaction(data)
        fields = _sent_fields(mock_post)
        assert "account_code_ref" not in fields

    def test_comment_path_payload_unchanged(self):
        """댓글 Caller(source=instagram_comment)는 account_code_ref를 아예 안 넘기므로
        Bundle B 적용 후에도 기존 payload 구조가 그대로 유지돼야 한다."""
        data = LeadInteractionCreate(
            igsid="commenter1", source="instagram_comment", interaction_type="comment_received",
            occurred_at="2026-07-26T00:00:00Z", inquiry_message="가격문의",
            source_event_id="c123",
        )
        with patch("modules.infra.airtable_repository.requests.post", return_value=_resp()) as mock_post:
            AirtableRepository().create_lead_interaction(data)
        fields = _sent_fields(mock_post)
        assert "account_code_ref" not in fields
        assert fields["source_event_id"] == "c123"
        assert fields["conversation_channel"] == "instagram_comment"
