"""tests/test_review_batch.py — modules/infra/review_batch.py 단위 테스트"""

from modules.infra.review_batch import build_review_payloads


class TestBuildReviewPayloads:
    def test_zero_selected_all_pass(self):
        """0개 선택 — 전부 PASS."""
        batch_ids = ["r1", "r2", "r3"]
        result = build_review_payloads(batch_ids, block_ids=[])
        assert result == [
            {"record_id": "r1", "review_status": "PASS"},
            {"record_id": "r2", "review_status": "PASS"},
            {"record_id": "r3", "review_status": "PASS"},
        ]

    def test_two_selected_rest_pass(self):
        """2개 선택 — 선택된 2개만 BLOCK, 나머지는 PASS."""
        batch_ids = ["r1", "r2", "r3", "r4"]
        result = build_review_payloads(batch_ids, block_ids=["r2", "r4"])
        assert result == [
            {"record_id": "r1", "review_status": "PASS"},
            {"record_id": "r2", "review_status": "BLOCK"},
            {"record_id": "r3", "review_status": "PASS"},
            {"record_id": "r4", "review_status": "BLOCK"},
        ]

    def test_select_all_all_block(self):
        """전체 선택 — 배치 전원 BLOCK."""
        batch_ids = ["r1", "r2", "r3"]
        result = build_review_payloads(batch_ids, block_ids=batch_ids)
        assert all(p["review_status"] == "BLOCK" for p in result)
        assert len(result) == 3

    def test_select_then_cancel_all_pass(self):
        """선택 후 취소 — 최종 block_ids가 비면 전부 PASS (상태 잔존 없음)."""
        batch_ids = ["r1", "r2", "r3"]
        selected_then_cancelled: set[str] = {"r1", "r2"}
        selected_then_cancelled.clear()  # 취소 동작 시뮬레이션
        result = build_review_payloads(batch_ids, block_ids=selected_then_cancelled)
        assert all(p["review_status"] == "PASS" for p in result)

    def test_output_covers_every_batch_id_exactly_once(self):
        batch_ids = ["r1", "r2", "r3", "r4", "r5"]
        result = build_review_payloads(batch_ids, block_ids=["r3"])
        assert [p["record_id"] for p in result] == batch_ids
        assert len(result) == len(batch_ids)

    def test_preserves_batch_order(self):
        batch_ids = ["r5", "r1", "r3"]
        result = build_review_payloads(batch_ids, block_ids=["r1"])
        assert [p["record_id"] for p in result] == ["r5", "r1", "r3"]

    def test_block_id_outside_batch_is_ignored(self):
        """배치 범위 밖 record_id가 block_ids에 섞여 있어도 무시한다."""
        batch_ids = ["r1", "r2"]
        result = build_review_payloads(batch_ids, block_ids=["r1", "stale_from_other_batch"])
        assert result == [
            {"record_id": "r1", "review_status": "BLOCK"},
            {"record_id": "r2", "review_status": "PASS"},
        ]

    def test_empty_batch_returns_empty(self):
        assert build_review_payloads([], block_ids=["r1"]) == []

    def test_duplicate_block_ids_no_effect(self):
        batch_ids = ["r1", "r2"]
        result = build_review_payloads(batch_ids, block_ids=["r1", "r1", "r1"])
        assert result == [
            {"record_id": "r1", "review_status": "BLOCK"},
            {"record_id": "r2", "review_status": "PASS"},
        ]
