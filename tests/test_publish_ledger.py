"""tests/test_publish_ledger.py — 260801 Step6B Publish Ledger 영속 테스트.

실제 db/publish_ledger.db가 아니라 매 테스트마다 tmp_path의 격리된 SQLite
파일을 사용한다(Runtime DB 오염 0건)."""

import pytest

from modules.common import publish_ledger


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_publish_ledger.db"


class TestMakeUniquePublishKey:
    def test_normalizes_case_and_whitespace(self):
        k1 = publish_ledger.make_unique_publish_key(" ABC ", " IDN-000036 ", "Instagram")
        k2 = publish_ledger.make_unique_publish_key("abc", "idn-000036", "instagram")
        assert k1 == k2 == "abc|idn-000036|instagram"

    def test_missing_parts_raise(self):
        with pytest.raises(publish_ledger.PublishLedgerError):
            publish_ledger.make_unique_publish_key("", "IDN-000036", "instagram")


class TestReserveAndTransition:
    def test_reserve_then_publishing_then_published(self, db_path):
        key = publish_ledger.reserve("rec1", "IDN-000036", "instagram", db_path=db_path)
        assert publish_ledger.get_state(key, db_path=db_path)["state"] == "RESERVED"

        publish_ledger.transition(key, "PUBLISHING", db_path=db_path)
        assert publish_ledger.get_state(key, db_path=db_path)["state"] == "PUBLISHING"

        publish_ledger.transition(key, "PUBLISHED", instagram_post_id="m123", db_path=db_path)
        state = publish_ledger.get_state(key, db_path=db_path)
        assert state["state"] == "PUBLISHED"
        assert state["instagram_post_id"] == "m123"

    def test_duplicate_reserve_raises(self, db_path):
        publish_ledger.reserve("rec1", "IDN-000036", "instagram", db_path=db_path)
        with pytest.raises(publish_ledger.PublishLedgerError):
            publish_ledger.reserve("rec1", "IDN-000036", "instagram", db_path=db_path)

    def test_transition_without_reserve_raises(self, db_path):
        with pytest.raises(publish_ledger.PublishLedgerError):
            publish_ledger.transition("never-reserved-key", "PUBLISHING", db_path=db_path)

    def test_disallowed_transition_raises(self, db_path):
        key = publish_ledger.reserve("rec2", "IDN-000036", "instagram", db_path=db_path)
        # RESERVED -> PUBLISHED는 허용되지 않은 전이(PUBLISHING을 건너뜀)
        with pytest.raises(publish_ledger.PublishLedgerError):
            publish_ledger.transition(key, "PUBLISHED", db_path=db_path)

    def test_ig_success_then_airtable_failure_preserves_id_via_receipt_sync_pending(self, db_path):
        """필수증명 4·5 핵심: Instagram 성공 ID가 Ledger에 먼저 저장되고,
        이후 Airtable 실패를 흉내낸 RECEIPT_SYNC_PENDING 전이에서도 그
        instagram_post_id가 유지되는지 확인한다."""
        key = publish_ledger.reserve("rec3", "IDN-000036", "instagram", db_path=db_path)
        publish_ledger.transition(key, "PUBLISHING", db_path=db_path)
        publish_ledger.transition(key, "PUBLISHED", instagram_post_id="m999", db_path=db_path)
        state_after_ig_success = publish_ledger.get_state(key, db_path=db_path)
        assert state_after_ig_success["instagram_post_id"] == "m999"

        publish_ledger.transition(key, "RECEIPT_SYNC_PENDING", last_error_code="airtable_down", db_path=db_path)
        state_after_airtable_fail = publish_ledger.get_state(key, db_path=db_path)
        assert state_after_airtable_fail["state"] == "RECEIPT_SYNC_PENDING"
        assert state_after_airtable_fail["instagram_post_id"] == "m999"  # ID 유실되지 않음

    def test_failed_to_dlq(self, db_path):
        key = publish_ledger.reserve("rec4", "IDN-000036", "instagram", db_path=db_path)
        publish_ledger.transition(key, "PUBLISHING", db_path=db_path)
        publish_ledger.transition(key, "FAILED", last_error_code="http_500", db_path=db_path)
        publish_ledger.transition(key, "DLQ", db_path=db_path)
        assert publish_ledger.get_state(key, db_path=db_path)["state"] == "DLQ"

    def test_get_state_missing_key_returns_none(self, db_path):
        assert publish_ledger.get_state("no-such-key", db_path=db_path) is None
