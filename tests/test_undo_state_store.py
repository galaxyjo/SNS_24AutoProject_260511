"""tests/test_undo_state_store.py — modules/infra/undo_state_store.py 단위 테스트.

임시 SQLite 파일(pytest tmp_path)만 사용 — Airtable/Streamlit 없음.
260712 사고 재발 방지 + Codex 지적 반영:
- "직전 배치 단 하나만" 실행취소 가능해야 한다(취소해도 이전 배치가 다시 노출되면 안 됨)
- prepare_batch()를 PATCH 이전에 호출해서 앱이 도중에 죽어도 기록이 남아야 한다
- payload(BLOCK/PASS 기대값) 자체를 저장해야 한다(record_id만 저장하면 감사 증거 부족)
- prepared/committed/failed/cancelled/superseded 상태를 전부 보존해야 한다
"""

from modules.infra.undo_state_store import UndoStateStore


def _store(tmp_path):
    return UndoStateStore(str(tmp_path / "undo_state.db"))


PAYLOAD_1 = [{"record_id": "r1", "review_status": "BLOCK"}, {"record_id": "r2", "review_status": "PASS"}]
PAYLOAD_2 = [{"record_id": "r3", "review_status": "PASS"}]


class TestPrepareThenCommitFlow:
    def test_no_batches_returns_none(self, tmp_path):
        store = _store(tmp_path)
        assert store.get_latest_undoable() is None

    def test_prepared_but_not_committed_is_not_undoable(self, tmp_path):
        """prepare_batch만 하고 mark_committed를 안 하면(=PATCH 도중 실패/미완료) 아직 undoable 아님."""
        store = _store(tmp_path)
        store.prepare_batch("batch1", PAYLOAD_1)
        assert store.get_latest_undoable() is None

    def test_committed_batch_is_retrievable_with_full_payload(self, tmp_path):
        store = _store(tmp_path)
        store.prepare_batch("batch1", PAYLOAD_1)
        store.mark_committed("batch1")
        latest = store.get_latest_undoable()
        assert latest is not None
        assert latest["batch_id"] == "batch1"
        assert latest["payload"] == PAYLOAD_1  # record_id만이 아니라 BLOCK/PASS 기대값까지 보존

    def test_survives_new_store_instance_same_db_path(self, tmp_path):
        db_path = str(tmp_path / "undo_state.db")
        store1 = UndoStateStore(db_path)
        store1.prepare_batch("batch1", PAYLOAD_1)
        store1.mark_committed("batch1")

        store2 = UndoStateStore(db_path)  # 새로고침 이후를 흉내낸 새 인스턴스
        latest = store2.get_latest_undoable()
        assert latest is not None
        assert latest["batch_id"] == "batch1"
        assert latest["payload"] == PAYLOAD_1


class TestFailedBatchNotUndoable:
    def test_failed_batch_is_not_undoable(self, tmp_path):
        store = _store(tmp_path)
        store.prepare_batch("batch1", PAYLOAD_1)
        store.mark_failed("batch1", error_message="simulated save failure")
        assert store.get_latest_undoable() is None


class TestOnlyLatestBatchEverUndoable:
    """Codex 지적 핵심: 최신 배치를 취소해도 이전 배치가 다시 노출되면 안 된다."""

    def test_new_prepare_supersedes_previous_committed_batch(self, tmp_path):
        store = _store(tmp_path)
        store.prepare_batch("batch1", PAYLOAD_1)
        store.mark_committed("batch1")
        assert store.get_latest_undoable()["batch_id"] == "batch1"

        store.prepare_batch("batch2", PAYLOAD_2)  # 새 배치 준비 -> batch1은 superseded
        store.mark_committed("batch2")
        assert store.get_latest_undoable()["batch_id"] == "batch2"

    def test_cancelling_latest_batch_does_not_reveal_previous_one(self, tmp_path):
        store = _store(tmp_path)
        store.prepare_batch("batch1", PAYLOAD_1)
        store.mark_committed("batch1")
        store.prepare_batch("batch2", PAYLOAD_2)
        store.mark_committed("batch2")

        store.mark_cancelled("batch2")

        assert store.get_latest_undoable() is None  # batch1이 다시 나타나면 안 됨

    def test_superseded_batch_never_returned_even_if_newer_one_never_committed(self, tmp_path):
        """batch2가 prepare만 되고 committed되지 않아도(예: 앱이 도중에 죽음),
        superseded된 batch1이 되살아나서 잘못 반환되면 안 된다."""
        store = _store(tmp_path)
        store.prepare_batch("batch1", PAYLOAD_1)
        store.mark_committed("batch1")
        store.prepare_batch("batch2", PAYLOAD_2)  # batch1 -> superseded, batch2는 아직 prepared뿐

        assert store.get_latest_undoable() is None


class TestMarkCancelled:
    def test_cancel_unknown_batch_id_does_not_raise(self, tmp_path):
        store = _store(tmp_path)
        store.mark_cancelled("nonexistent")

    def test_cancel_then_prepare_recommit_same_batch_id_is_undoable_again(self, tmp_path):
        store = _store(tmp_path)
        store.prepare_batch("batch1", PAYLOAD_1)
        store.mark_committed("batch1")
        store.mark_cancelled("batch1")
        assert store.get_latest_undoable() is None

        store.prepare_batch("batch1", PAYLOAD_2)
        store.mark_committed("batch1")
        latest = store.get_latest_undoable()
        assert latest["batch_id"] == "batch1"
        assert latest["payload"] == PAYLOAD_2


class TestGetLatestPrepared:
    """mark_committed/mark_failed가 어떤 이유로든 실행되지 못해 'prepared'에 멈춘 배치를
    찾기 위한 조회 — 복구(recover) 로직의 입력."""

    def test_no_batches_returns_none(self, tmp_path):
        store = _store(tmp_path)
        assert store.get_latest_prepared() is None

    def test_prepared_only_is_returned(self, tmp_path):
        store = _store(tmp_path)
        store.prepare_batch("batch1", PAYLOAD_1)
        prepared = store.get_latest_prepared()
        assert prepared is not None
        assert prepared["batch_id"] == "batch1"
        assert prepared["payload"] == PAYLOAD_1

    def test_committed_batch_not_returned_as_prepared(self, tmp_path):
        store = _store(tmp_path)
        store.prepare_batch("batch1", PAYLOAD_1)
        store.mark_committed("batch1")
        assert store.get_latest_prepared() is None

    def test_failed_batch_not_returned_as_prepared(self, tmp_path):
        store = _store(tmp_path)
        store.prepare_batch("batch1", PAYLOAD_1)
        store.mark_failed("batch1", "some error")
        assert store.get_latest_prepared() is None

    def test_only_latest_batch_checked_even_if_older_one_is_prepared(self, tmp_path):
        """오래된 배치가 prepared로 멈춰 있어도, 그 이후 새 배치가 committed됐으면
        더 이상 '복구 필요' 상태가 아니어야 한다(최신 배치 기준으로만 판단)."""
        store = _store(tmp_path)
        store.prepare_batch("batch1", PAYLOAD_1)  # 이 배치는 committed도 failed도 안 됨(멈춤 시뮬레이션)
        store.prepare_batch("batch2", PAYLOAD_2)
        store.mark_committed("batch2")
        assert store.get_latest_prepared() is None
