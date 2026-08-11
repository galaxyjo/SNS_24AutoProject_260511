"""tests/test_review_grid_ui_re_review.py — 260806 "재검수" 기능 전용 테스트.

review_grid_ui.py에 상단 "리뷰 모드" 선택(PENDING/PASS/BLOCK)을 추가해, 이미 PASS/BLOCK
처리된 후보를 다시 불러와 판정을 바꿀 수 있게 한 기능만 검증한다. 기존 PENDING 기본
경로(tests/test_review_grid_ui.py, 51 tests)는 이 변경으로 전혀 바뀌지 않는다 — 기본
모드가 여전히 PENDING이고 FakeRepo가 fetch_candidates_by_status를 노출하지 않아도
PENDING 모드에서는 그 메서드를 호출하지 않는다(호출 경로 자체가 분기되어 있음).

여기서 확인하는 것:
  1. 기본 모드는 PENDING — fetch_candidates_by_status는 호출되지 않는다.
  2. 모드를 PASS/BLOCK으로 바꾸면 fetch_candidates_by_status(status, limit=50)를 호출한다.
  3. 재검수 모드에서는 체크박스 초기값이 후보의 현재 review_status를 반영한다
     (BLOCK인 후보는 이미 체크됨 — 그대로 두면 BLOCK 유지, 해제하면 PASS로 바뀜).
  4. 재검수 배치 제출 시 실제로 review_status가 다시 저장된다.
  5. 재검수 배치를 실행취소하면 PENDING이 아니라 원래 상태(PASS 또는 BLOCK)로 되돌아간다
     — undo_batch_with_verification(revert_to=...)가 정확히 배선됐는지가 핵심.
  6. 모드를 바꾸면 이전 모드의 배치를 버리고 새로 조회한다.
"""

from streamlit.testing.v1 import AppTest


class ReReviewFakeRepo:
    """PENDING 조회 + 상태별(PASS/BLOCK) 조회를 모두 지원하는 가짜 repo."""

    def __init__(self, pending=None, by_status=None):
        self._pending = list(pending or [])
        self._by_status = {k: list(v) for k, v in (by_status or {}).items()}
        self.pending_fetch_calls = 0
        self.status_fetch_calls: list[str] = []
        self.save_calls: list[tuple[str, str]] = []
        self.statuses: dict[str, str] = {}
        for status, items in self._by_status.items():
            for c in items:
                self.statuses[c["record_id"]] = status

    def fetch_pending_candidates(self, limit=50):
        self.pending_fetch_calls += 1
        return self._pending[:limit]

    def fetch_candidates_by_status(self, status, limit=50):
        self.status_fetch_calls.append(status)
        return self._by_status.get(status, [])[:limit]

    def save_review_decision(self, record_id, decision, note=""):
        self.save_calls.append((record_id, decision))
        self.statuses[record_id] = decision

    def get_review_status(self, record_id):
        return self.statuses.get(record_id)


def _make_candidates_with_status(n, status, prefix="p"):
    return [
        {"record_id": f"{prefix}_{i}", "image_url": f"http://fake/{prefix}_{i}.jpg", "review_status": status}
        for i in range(n)
    ]


def _app(repo):
    from modules.infra.review_grid_ui import render_review_grid
    render_review_grid(repo)


def _run(repo) -> AppTest:
    at = AppTest.from_function(_app, kwargs={"repo": repo})
    at.run()
    return at


def _app_with_store(repo, undo_store):
    from modules.infra.review_grid_ui import render_review_grid
    render_review_grid(repo, undo_store=undo_store)


def _run_with_store(repo, undo_store) -> AppTest:
    at = AppTest.from_function(_app_with_store, kwargs={"repo": repo, "undo_store": undo_store})
    at.run()
    return at


def _item_checkboxes(at):
    return [c for c in at.checkbox if c.label == "버림"]


class TestDefaultModeIsPendingUnchanged:
    def test_default_mode_fetches_pending_not_by_status(self):
        repo = ReReviewFakeRepo(pending=_make_candidates_with_status(3, "PENDING", prefix="rec"))
        at = _run(repo)
        assert not at.exception
        assert repo.pending_fetch_calls == 1
        assert repo.status_fetch_calls == []

    def test_default_mode_selectbox_value_is_pending(self):
        repo = ReReviewFakeRepo(pending=_make_candidates_with_status(3, "PENDING", prefix="rec"))
        at = _run(repo)
        assert at.selectbox(key="grid_review_mode").value == "PENDING"


class TestSwitchingModeFetchesByStatus:
    def test_switch_to_pass_calls_fetch_candidates_by_status(self):
        repo = ReReviewFakeRepo(
            pending=[],
            by_status={"PASS": _make_candidates_with_status(4, "PASS")},
        )
        at = _run(repo)
        at.selectbox(key="grid_review_mode").select("PASS").run()

        assert not at.exception
        assert repo.status_fetch_calls == ["PASS"]
        boxes = _item_checkboxes(at)
        assert len(boxes) == 4

    def test_switch_to_block_calls_fetch_candidates_by_status(self):
        repo = ReReviewFakeRepo(
            pending=[],
            by_status={"BLOCK": _make_candidates_with_status(2, "BLOCK", prefix="b")},
        )
        at = _run(repo)
        at.selectbox(key="grid_review_mode").select("BLOCK").run()

        assert not at.exception
        assert repo.status_fetch_calls == ["BLOCK"]

    def test_switching_mode_resets_batch_and_refetches(self):
        repo = ReReviewFakeRepo(
            pending=_make_candidates_with_status(3, "PENDING", prefix="rec"),
            by_status={"PASS": _make_candidates_with_status(2, "PASS")},
        )
        at = _run(repo)
        assert repo.pending_fetch_calls == 1
        at.selectbox(key="grid_review_mode").select("PASS").run()
        assert repo.status_fetch_calls == ["PASS"]
        # PENDING 배치가 그대로 재사용되지 않고 PASS 배치로 완전히 교체됐는지 그리드 건수로 확인.
        boxes = _item_checkboxes(at)
        assert len(boxes) == 2


class TestReReviewCheckboxDefaults:
    def test_pass_mode_candidates_default_unchecked(self):
        """PASS 재검수 모드 — 현재 PASS인 후보는 체크 해제(=PASS 유지)로 시작해야 한다."""
        repo = ReReviewFakeRepo(pending=[], by_status={"PASS": _make_candidates_with_status(3, "PASS")})
        at = _run(repo)
        at.selectbox(key="grid_review_mode").select("PASS").run()

        boxes = _item_checkboxes(at)
        assert len(boxes) == 3
        assert all(b.value is False for b in boxes)

    def test_block_mode_candidates_default_checked(self):
        """BLOCK 재검수 모드 — 현재 BLOCK인 후보는 처음부터 체크(=BLOCK 유지)로 시작해야 한다."""
        repo = ReReviewFakeRepo(pending=[], by_status={"BLOCK": _make_candidates_with_status(3, "BLOCK", prefix="b")})
        at = _run(repo)
        at.selectbox(key="grid_review_mode").select("BLOCK").run()

        boxes = _item_checkboxes(at)
        assert len(boxes) == 3
        assert all(b.value is True for b in boxes)

    def test_unchecking_a_block_candidate_previews_pass(self):
        repo = ReReviewFakeRepo(pending=[], by_status={"BLOCK": _make_candidates_with_status(3, "BLOCK", prefix="b")})
        at = _run(repo)
        at.selectbox(key="grid_review_mode").select("BLOCK").run()
        at.checkbox(key="grid_chk_b_0").uncheck().run()

        df = at.dataframe[0].value
        by_id = {r["record_id"]: r["review_status"] for r in df.to_dict("records")}
        assert by_id["b_0"] == "PASS"
        assert by_id["b_1"] == "BLOCK"


class TestReReviewSubmitWritesDecision:
    def test_pass_mode_submit_keeps_unchecked_as_pass_and_checked_as_block(self):
        repo = ReReviewFakeRepo(pending=[], by_status={"PASS": _make_candidates_with_status(3, "PASS")})
        at = _run(repo)
        at.selectbox(key="grid_review_mode").select("PASS").run()
        at.checkbox(key="grid_chk_p_1").check().run()  # p_1만 BLOCK으로 재판정
        at.button(key="grid_submit").click().run()

        assert not at.exception
        decisions = dict(repo.save_calls)
        assert decisions["p_0"] == "PASS"
        assert decisions["p_1"] == "BLOCK"
        assert decisions["p_2"] == "PASS"
        assert repo.statuses["p_1"] == "BLOCK"

    def test_block_mode_submit_can_flip_back_to_pass(self):
        repo = ReReviewFakeRepo(pending=[], by_status={"BLOCK": _make_candidates_with_status(2, "BLOCK", prefix="b")})
        at = _run(repo)
        at.selectbox(key="grid_review_mode").select("BLOCK").run()
        at.checkbox(key="grid_chk_b_0").uncheck().run()  # b_0을 PASS로 재판정, b_1은 BLOCK 유지
        at.button(key="grid_submit").click().run()

        assert not at.exception
        decisions = dict(repo.save_calls)
        assert decisions["b_0"] == "PASS"
        assert decisions["b_1"] == "BLOCK"


class TestReReviewUndoRevertsToOriginalStatusNotPending:
    """260806 핵심 요구사항 — 재검수 배치를 실행취소하면 PENDING이 아니라 원래 상태로 돌아가야 한다."""

    def test_undo_after_pass_mode_batch_reverts_to_pass(self, tmp_path):
        from modules.infra.undo_state_store import UndoStateStore

        store = UndoStateStore(str(tmp_path / "undo_state.db"))
        repo = ReReviewFakeRepo(pending=[], by_status={"PASS": _make_candidates_with_status(2, "PASS")})
        at = _run_with_store(repo, store)
        at.selectbox(key="grid_review_mode").select("PASS").run()
        at.checkbox(key="grid_chk_p_0").check().run()  # p_0 -> BLOCK
        at.button(key="grid_submit").click().run()
        assert repo.statuses["p_0"] == "BLOCK"

        at.button(key="grid_undo_btn").click().run()

        assert not at.exception
        assert repo.statuses["p_0"] == "PASS"  # PENDING이 아니라 원래 PASS로 복원
        assert repo.statuses["p_1"] == "PASS"

    def test_undo_after_block_mode_batch_reverts_to_block(self, tmp_path):
        from modules.infra.undo_state_store import UndoStateStore

        store = UndoStateStore(str(tmp_path / "undo_state.db"))
        repo = ReReviewFakeRepo(pending=[], by_status={"BLOCK": _make_candidates_with_status(2, "BLOCK", prefix="b")})
        at = _run_with_store(repo, store)
        at.selectbox(key="grid_review_mode").select("BLOCK").run()
        at.checkbox(key="grid_chk_b_0").uncheck().run()  # b_0 -> PASS
        at.button(key="grid_submit").click().run()
        assert repo.statuses["b_0"] == "PASS"

        at.button(key="grid_undo_btn").click().run()

        assert not at.exception
        assert repo.statuses["b_0"] == "BLOCK"  # PENDING이 아니라 원래 BLOCK으로 복원

    def test_normal_pending_undo_still_reverts_to_pending(self, tmp_path):
        """대조군 — 기존 PENDING 워크플로우의 실행취소는 그대로 PENDING으로 복원돼야 한다(회귀 없음)."""
        from modules.infra.undo_state_store import UndoStateStore

        store = UndoStateStore(str(tmp_path / "undo_state.db"))
        repo = ReReviewFakeRepo(pending=_make_candidates_with_status(2, "PENDING", prefix="rec"))
        at = _run_with_store(repo, store)
        at.checkbox(key="grid_chk_rec_0").check().run()
        at.button(key="grid_submit").click().run()
        assert repo.statuses["rec_0"] == "BLOCK"

        at.button(key="grid_undo_btn").click().run()

        assert not at.exception
        assert repo.statuses["rec_0"] == "PENDING"

    def test_undo_button_label_mentions_revert_target_in_re_review_mode(self, tmp_path):
        from modules.infra.undo_state_store import UndoStateStore

        store = UndoStateStore(str(tmp_path / "undo_state.db"))
        repo = ReReviewFakeRepo(pending=[], by_status={"PASS": _make_candidates_with_status(1, "PASS")})
        at = _run_with_store(repo, store)
        at.selectbox(key="grid_review_mode").select("PASS").run()
        at.button(key="grid_submit").click().run()

        undo_buttons = [b for b in at.button if b.key == "grid_undo_btn"]
        assert len(undo_buttons) == 1
        assert "PASS" in undo_buttons[0].label

    def test_undo_after_refresh_new_session_reverts_to_pass_not_pending(self, tmp_path):
        """260806 Codex P2 지적 — 기존 undo 테스트는 제출 직후 같은 AppTest 세션에서
        취소해 grid_undo_revert_to(session_state)만으로도 통과한다. 실제 새로고침은
        session_state가 전부 사라지고 undo_store(SQLite)의 payload["revert_to"]만
        남는 경로라, 이 테스트는 그 경로를 별도로 검증한다(test_review_grid_ui.py의
        test_undo_click_after_refresh_actually_reverts_and_cancels_store_entry와 동일 패턴)."""
        from modules.infra.undo_state_store import UndoStateStore

        db_path = str(tmp_path / "undo_state.db")
        store1 = UndoStateStore(db_path)
        repo = ReReviewFakeRepo(pending=[], by_status={"PASS": _make_candidates_with_status(2, "PASS")})
        at = _run_with_store(repo, store1)
        at.selectbox(key="grid_review_mode").select("PASS").run()
        at.checkbox(key="grid_chk_p_0").check().run()  # p_0 -> BLOCK
        at.button(key="grid_submit").click().run()
        assert repo.statuses["p_0"] == "BLOCK"

        # "새로고침" 시뮬레이션 — 완전히 새 AppTest 세션 + 새 UndoStateStore 인스턴스(같은 DB 파일).
        # repo는 같은 인스턴스를 재사용(같은 Airtable을 의미) — session_state는 전부 리셋된다.
        store2 = UndoStateStore(db_path)
        at2 = _run_with_store(repo, store2)
        assert not at2.exception
        at2.button(key="grid_undo_btn").click().run()

        assert not at2.exception
        assert repo.statuses["p_0"] == "PASS"  # PENDING이 아니라 새로고침 전 원래 상태(PASS)로 복원
        assert repo.statuses["p_1"] == "PASS"
        assert store2.get_latest_undoable() is None  # 취소 완료로 기록되어 더 이상 undoable 아님

    def test_undo_after_refresh_new_session_reverts_to_block_not_pending(self, tmp_path):
        """위 테스트의 BLOCK 대응 버전 — revert_to='BLOCK'도 새 세션에서 SQLite payload로만
        정확히 복원되는지 확인한다."""
        from modules.infra.undo_state_store import UndoStateStore

        db_path = str(tmp_path / "undo_state.db")
        store1 = UndoStateStore(db_path)
        repo = ReReviewFakeRepo(pending=[], by_status={"BLOCK": _make_candidates_with_status(2, "BLOCK", prefix="b")})
        at = _run_with_store(repo, store1)
        at.selectbox(key="grid_review_mode").select("BLOCK").run()
        at.checkbox(key="grid_chk_b_0").uncheck().run()  # b_0 -> PASS
        at.button(key="grid_submit").click().run()
        assert repo.statuses["b_0"] == "PASS"

        store2 = UndoStateStore(db_path)
        at2 = _run_with_store(repo, store2)
        assert not at2.exception
        at2.button(key="grid_undo_btn").click().run()

        assert not at2.exception
        assert repo.statuses["b_0"] == "BLOCK"  # PENDING이 아니라 원래 BLOCK으로 복원
        assert store2.get_latest_undoable() is None


class TestRevertToValidation:
    """260806 Codex P1 지적 — revert_to/status는 undo_store(SQLite)에서 복원되거나
    외부에서 직접 호출될 수 있어, 저장소 경계에서 PENDING/PASS/BLOCK 외 값을 거부해야 한다."""

    def test_undo_batch_with_verification_rejects_invalid_revert_to(self):
        from modules.infra.review_batch_committer import undo_batch_with_verification

        repo = ReReviewFakeRepo(pending=_make_candidates_with_status(1, "PENDING"))
        result = undo_batch_with_verification(repo, ["rec_0"], revert_to="DROP TABLE")

        assert result.committed is False
        assert result.failed_id  # UI의 "if result.failed_id:" 분기로 사용자에게 노출되어야 함
        assert repo.save_calls == []  # 검증 실패 시 저장 자체가 시작되지 않아야 함

    def test_fetch_candidates_by_status_rejects_invalid_status(self):
        from modules.infra.repository_interface import RepositoryValidationError
        from modules.infra.airtable_repository import AirtableRepository

        repo = AirtableRepository()
        try:
            repo.fetch_candidates_by_status("DROP TABLE")
            assert False, "RepositoryValidationError가 발생해야 한다"
        except RepositoryValidationError:
            pass
