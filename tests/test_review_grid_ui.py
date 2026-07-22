"""tests/test_review_grid_ui.py — modules/infra/review_grid_ui.py 그리드 UI 상태 테스트.

Streamlit AppTest로 render_review_grid()를 가짜 5건 후보 + 가짜 repo에 대해 구동한다.
실제 Airtable 접속 없음 (FakeRepo만 사용) — Codex 2/2B단계 요구사항:
클릭/재클릭, 전체 선택/전체 해제, 확정 전 저장 호출 0회, 확정 버튼 1개,
새 배치마다 전체선택·개별선택 상태 초기화.
"""

from streamlit.testing.v1 import AppTest


class FakeRepo:
    """실제 Airtable 대신 쓰는 인메모리 가짜 repo. 저장 호출 횟수/내용을 그대로 기록한다.

    candidates에 리스트의 리스트를 넘기면 배치 전환(2번째 fetch부터 다음 배치 반환)을
    시뮬레이션할 수 있다. 단일 리스트를 넘기면 매번 같은 배치를 반환한다.

    fail_on_save_for/mismatch_for로 committer 연결(3B) 실패 경로도 시뮬레이션한다 —
    review_batch_committer가 get_review_status로 재검증하므로 기본은 저장값과 일치시킨다.
    """

    def __init__(self, candidates, fail_on_save_for=(), mismatch_for=(), get_error_for=None):
        if candidates and isinstance(candidates[0], list):
            self._batches = list(candidates)
        else:
            self._batches = [list(candidates)]
        self.save_calls: list[tuple[str, str]] = []
        self.fetch_calls = 0
        self.statuses: dict[str, str] = {}
        self.fail_on_save_for = set(fail_on_save_for)
        self.mismatch_for = set(mismatch_for)
        # get_error_for: {record_id: Exception 인스턴스} — GET 자체가 예외를 던지는 경우
        # (verification_errors 유발, mismatch_for와 달리 "값이 다름"이 아니라 "확인 실패").
        self.get_error_for = dict(get_error_for or {})

    def fetch_pending_candidates(self, limit=50):
        idx = min(self.fetch_calls, len(self._batches) - 1)
        batch = self._batches[idx]
        self.fetch_calls += 1
        return batch[:limit]

    def save_review_decision(self, record_id, decision, note=""):
        self.save_calls.append((record_id, decision))
        if record_id in self.fail_on_save_for:
            raise RuntimeError(f"simulated save failure for {record_id}")
        self.statuses[record_id] = decision

    def get_review_status(self, record_id):
        if record_id in self.get_error_for:
            raise self.get_error_for[record_id]
        if record_id in self.mismatch_for:
            return "STALE"
        return self.statuses.get(record_id)


def _make_candidates(n=5):
    return [{"record_id": f"rec_{i}", "image_url": f"http://fake/{i}.jpg"} for i in range(n)]


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
    """undo_store를 주입해서 구동 — 매번 새 AppTest 인스턴스라 세션이 완전히 새로 시작된다
    (브라우저 새로고침과 동일한 조건)."""
    at = AppTest.from_function(_app_with_store, kwargs={"repo": repo, "undo_store": undo_store})
    at.run()
    return at


def _item_checkboxes(at):
    return [c for c in at.checkbox if c.label == "버림"]


class TestInitialRender:
    def test_five_fake_candidates_render_five_unchecked_boxes(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        assert not at.exception
        boxes = _item_checkboxes(at)
        assert len(boxes) == 5
        assert all(b.value is False for b in boxes)

    def test_no_save_call_on_initial_render(self):
        repo = FakeRepo(_make_candidates(5))
        _run(repo)
        assert repo.save_calls == []


class TestClickAndReclick:
    def test_click_checks_the_box(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_chk_rec_0").check().run()
        assert at.checkbox(key="grid_chk_rec_0").value is True

    def test_reclick_returns_to_unchecked(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_chk_rec_0").check().run()
        at.checkbox(key="grid_chk_rec_0").uncheck().run()
        assert at.checkbox(key="grid_chk_rec_0").value is False

    def test_click_reclick_causes_no_save_call(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_chk_rec_1").check().run()
        at.checkbox(key="grid_chk_rec_1").uncheck().run()
        at.checkbox(key="grid_chk_rec_2").check().run()
        assert repo.save_calls == []

    def test_other_boxes_unaffected_by_single_click(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_chk_rec_0").check().run()
        others = [c for c in _item_checkboxes(at) if c.key != "grid_chk_rec_0"]
        assert all(c.value is False for c in others)


class TestSelectAllDeselectAll:
    def test_master_check_selects_all_five(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_master_select").check().run()
        boxes = _item_checkboxes(at)
        assert all(b.value is True for b in boxes)
        assert repo.save_calls == []

    def test_master_uncheck_deselects_all_five(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_master_select").check().run()
        at.checkbox(key="grid_master_select").uncheck().run()
        boxes = _item_checkboxes(at)
        assert all(b.value is False for b in boxes)
        assert repo.save_calls == []

    def test_select_all_then_individual_uncheck_keeps_rest_checked(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_master_select").check().run()
        at.checkbox(key="grid_chk_rec_2").uncheck().run()
        boxes = {c.key: c.value for c in _item_checkboxes(at)}
        assert boxes["grid_chk_rec_2"] is False
        assert boxes["grid_chk_rec_0"] is True
        assert boxes["grid_chk_rec_4"] is True


class TestNoSaveBeforeConfirm:
    def test_multiple_toggles_zero_save_calls_until_confirm(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_chk_rec_0").check().run()
        at.checkbox(key="grid_chk_rec_1").check().run()
        at.checkbox(key="grid_master_select").check().run()
        at.checkbox(key="grid_master_select").uncheck().run()
        at.checkbox(key="grid_chk_rec_3").check().run()
        at.checkbox(key="grid_chk_rec_3").uncheck().run()
        assert repo.save_calls == []
        assert repo.fetch_calls == 1  # 배치는 최초 1회만 조회, 토글 중 재조회 없음


class TestConfirmSubmit:
    def test_confirm_saves_exactly_five_with_correct_decisions(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_chk_rec_0").check().run()
        at.checkbox(key="grid_chk_rec_2").check().run()
        at.button(key="grid_submit").click().run()

        assert len(repo.save_calls) == 5
        decisions = dict(repo.save_calls)
        assert decisions["rec_0"] == "BLOCK"
        assert decisions["rec_1"] == "PASS"
        assert decisions["rec_2"] == "BLOCK"
        assert decisions["rec_3"] == "PASS"
        assert decisions["rec_4"] == "PASS"

    def test_confirm_with_nothing_selected_saves_all_pass(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.button(key="grid_submit").click().run()
        assert len(repo.save_calls) == 5
        assert all(dec == "PASS" for _, dec in repo.save_calls)

    def test_confirm_with_select_all_saves_all_block(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_master_select").check().run()
        at.button(key="grid_submit").click().run()
        assert len(repo.save_calls) == 5
        assert all(dec == "BLOCK" for _, dec in repo.save_calls)

    def test_no_exception_raised_during_full_flow(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_master_select").check().run()
        at.checkbox(key="grid_chk_rec_0").uncheck().run()
        at.button(key="grid_submit").click().run()
        assert not at.exception


class TestSaveFailureKeepsBatchAndSelection:
    """3B: committed=False(저장 실패/GET 불일치)면 배치와 선택 상태를 그대로 유지해야 한다."""

    def test_save_failure_keeps_batch_loaded(self):
        repo = FakeRepo(_make_candidates(5), fail_on_save_for=["rec_2"])
        at = _run(repo)
        at.checkbox(key="grid_chk_rec_0").check().run()
        at.button(key="grid_submit").click().run()

        assert not at.exception
        # 배치가 그대로 남아있어야 함 -> 그리드 체크박스가 여전히 5개 렌더링됨
        boxes = _item_checkboxes(at)
        assert len(boxes) == 5

    def test_save_failure_keeps_selection_checked(self):
        repo = FakeRepo(_make_candidates(5), fail_on_save_for=["rec_2"])
        at = _run(repo)
        at.checkbox(key="grid_chk_rec_0").check().run()
        at.button(key="grid_submit").click().run()

        assert at.checkbox(key="grid_chk_rec_0").value is True  # 선택 상태 유지

    def test_save_failure_shows_error_message(self):
        repo = FakeRepo(_make_candidates(5), fail_on_save_for=["rec_2"])
        at = _run(repo)
        at.button(key="grid_submit").click().run()
        assert len(at.error) > 0

    def test_save_failure_stops_before_later_records(self):
        """build_review_payloads는 batch 순서를 지키므로 rec_2에서 멈추면 rec_3/rec_4는 저장 시도조차 안 한다."""
        repo = FakeRepo(_make_candidates(5), fail_on_save_for=["rec_2"])
        at = _run(repo)
        at.button(key="grid_submit").click().run()
        saved_ids = [rid for rid, _ in repo.save_calls]
        assert "rec_3" not in saved_ids
        assert "rec_4" not in saved_ids

    def test_get_mismatch_keeps_batch_and_selection(self):
        repo = FakeRepo(_make_candidates(5), mismatch_for=["rec_3"])
        at = _run(repo)
        at.checkbox(key="grid_chk_rec_1").check().run()
        at.button(key="grid_submit").click().run()

        assert not at.exception
        assert len(at.error) > 0
        boxes = _item_checkboxes(at)
        assert len(boxes) == 5  # 배치 그대로
        assert at.checkbox(key="grid_chk_rec_1").value is True  # 선택 그대로

    def test_success_after_failure_condition_removed(self):
        """실패 조건이 없으면(정상 케이스) 그대로 커밋되고 배치가 비워진다 — 대조군."""
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.button(key="grid_submit").click().run()
        assert not at.exception
        assert len(at.error) == 0
        assert len(repo.save_calls) == 5


class _HttpLikeError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class TestUncertainSaveDoesNotPermanentlyFail:
    """260722 Codex 리뷰 2차 반영: 저장 후 확인(GET) 자체가 실패한 경우(verification_errors만
    있고 failed_id/mismatched_ids는 없는 경우)는 "확정 실패"가 아니므로 mark_failed를
    호출하면 안 된다 — undo_store에 'prepared' 상태로 남겨서 다음 접속 시 기존 복구
    로직(get_latest_prepared -> verify_only)이 자동으로 재확인하게 해야 한다.

    (test_stuck_prepared_batch_that_actually_succeeded_recovers_to_committed 등은 이미
    'prepared'로 시작하는 배치의 복구를 검증하지만, 여기서는 _submit_grid_batch() 자신의
    최초 제출이 verification_errors만 내는 상황에서 mark_failed가 호출되지 않는지를 검증한다.)"""

    def test_verification_error_only_leaves_batch_prepared_not_failed(self, tmp_path):
        from modules.infra.undo_state_store import UndoStateStore

        db_path = str(tmp_path / "undo_state.db")
        store = UndoStateStore(db_path)
        repo = FakeRepo(
            _make_candidates(5),
            get_error_for={"rec_3": _HttpLikeError("forbidden", status_code=403)},
        )
        at = _run_with_store(repo, store)
        at.button(key="grid_submit").click().run()

        assert not at.exception
        assert len(at.error) > 0  # 확인 실패 안내는 여전히 표시됨
        # 확정 실패(failed)로 넘어가지 않고 prepared 그대로 — 다음 접속 시 자동 재확인 대상.
        prepared = store.get_latest_prepared()
        assert prepared is not None
        assert prepared["batch_id"] is not None
        assert store.get_latest_undoable() is None  # committed도 아님(당연히)

    def test_confirmed_mismatch_still_marks_failed(self, tmp_path):
        """대조군 — 진짜 값 불일치(mismatched_ids)는 여전히 확정 실패로 mark_failed 호출."""
        from modules.infra.undo_state_store import UndoStateStore

        db_path = str(tmp_path / "undo_state.db")
        store = UndoStateStore(db_path)
        repo = FakeRepo(_make_candidates(5), mismatch_for=["rec_3"])
        at = _run_with_store(repo, store)
        at.button(key="grid_submit").click().run()

        assert not at.exception
        assert store.get_latest_prepared() is None  # failed로 확정 전환됨(더 이상 prepared 아님)

    def test_confirmed_save_failure_still_marks_failed(self, tmp_path):
        """대조군 — 저장 자체가 확정 실패(failed_id)면 여전히 mark_failed 호출."""
        from modules.infra.undo_state_store import UndoStateStore

        db_path = str(tmp_path / "undo_state.db")
        store = UndoStateStore(db_path)
        repo = FakeRepo(_make_candidates(5), fail_on_save_for=["rec_2"])
        at = _run_with_store(repo, store)
        at.button(key="grid_submit").click().run()

        assert not at.exception
        assert store.get_latest_prepared() is None  # failed로 확정 전환됨


class TestVerificationErrorBlocksConfirmButton:
    """260712 사고 이후: verification_errors 발생 시 확정 버튼을 잠그고, 재클릭으로 인한
    재-PATCH를 막는다. 새 배치를 받으면 잠금이 풀린다."""

    def test_verification_error_disables_confirm_button(self):
        # 잠금 플래그는 클릭을 처리하는 바로 그 pass 안에서 세팅되므로, 버튼 자체가
        # disabled=True로 "다시 그려지는" 건 그 다음 rerun부터다 — 그래서 run()을 한 번 더 호출한다.
        repo = FakeRepo(_make_candidates(5), get_error_for={"rec_3": _HttpLikeError("forbidden", status_code=403)})
        at = _run(repo)
        at.button(key="grid_submit").click().run()
        at.run()

        assert not at.exception
        assert at.button(key="grid_submit").proto.disabled is True

    def test_verification_error_shows_immediate_error_with_lock_instruction(self):
        """클릭 직후(같은 pass)에는 오류 메시지에 '다시 누르지 마세요' 안내가 들어있어야 한다."""
        repo = FakeRepo(_make_candidates(5), get_error_for={"rec_3": _HttpLikeError("forbidden", status_code=403)})
        at = _run(repo)
        at.button(key="grid_submit").click().run()

        assert any("다시 누르지 마세요" in e.value for e in at.error)

    def test_verification_error_shows_persistent_warning_after_rerun(self):
        """그 다음 rerun부터는(에러는 사라지고) 잠금 경고 배너가 계속 남아있어야 한다."""
        repo = FakeRepo(_make_candidates(5), get_error_for={"rec_3": _HttpLikeError("forbidden", status_code=403)})
        at = _run(repo)
        at.button(key="grid_submit").click().run()
        at.run()

        assert len(at.warning) > 0

    def test_plain_mismatch_without_get_exception_does_not_disable_button(self):
        """진짜 값 불일치(verification_errors 아님)는 버튼을 잠그지 않는다 — 대조군."""
        repo = FakeRepo(_make_candidates(5), mismatch_for=["rec_3"])
        at = _run(repo)
        at.button(key="grid_submit").click().run()

        assert at.button(key="grid_submit").proto.disabled is False

    def test_new_batch_resets_confirm_button_lock(self):
        batch1 = _make_candidates(5)
        batch2 = [{"record_id": f"rec2_{i}", "image_url": "x"} for i in range(5)]
        repo = FakeRepo([batch1, batch2], get_error_for={"rec_3": _HttpLikeError("forbidden", status_code=403)})
        at = _run(repo)
        at.button(key="grid_submit").click().run()
        at.run()
        assert at.button(key="grid_submit").proto.disabled is True

        # 실행취소로 배치를 비우고 다음 배치를 새로 받으면 잠금이 풀려야 한다.
        # (이 시나리오에서는 아직 committed=False라 undo_ids가 없으므로, 배치를 직접 새로고침한다)
        at.session_state["grid_batch"] = None
        at.run()
        assert at.button(key="grid_submit").proto.disabled is False


class TestSingleConfirmButtonOnly:
    def test_exactly_one_confirm_button_exists(self):
        """2B단계: 상단 중복 확정 버튼 제거 — grid_submit 하나만 남아야 한다."""
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        assert len(at.button) == 1
        assert at.button[0].key == "grid_submit"

    def test_no_top_block_button_key_exists(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        keys = [b.key for b in at.button]
        assert "grid_block_top_btn" not in keys

    def test_block_count_badge_still_shown_as_text_not_button(self):
        """카운트 배지는 남되(정보용), 클릭 가능한 버튼이면 안 된다."""
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        assert "BLOCK 선택" in at.markdown[0].value
        assert not any("BLOCK 선택" in (b.label or "") for b in at.button)


class TestPayloadPreview:
    """자동 payload 미리보기: 버튼 추가 없이 체크 상태가 바뀔 때마다 자동 표시, Airtable 호출 없음."""

    def test_preview_shown_automatically_no_extra_button(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        assert len(at.dataframe) == 1
        assert len(at.button) == 1  # grid_submit 하나만 — 미리보기용 버튼 추가 안 함
        assert repo.save_calls == []

    def test_preview_contains_all_batch_ids_default_pass(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        df = at.dataframe[0].value
        records = df.to_dict("records")
        assert len(records) == 5
        assert {r["record_id"] for r in records} == {f"rec_{i}" for i in range(5)}
        assert all(r["review_status"] == "PASS" for r in records)

    def test_preview_updates_when_checkbox_toggled(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_chk_rec_1").check().run()
        df = at.dataframe[0].value
        by_id = {r["record_id"]: r["review_status"] for r in df.to_dict("records")}
        assert by_id["rec_1"] == "BLOCK"
        assert by_id["rec_0"] == "PASS"
        assert repo.save_calls == []  # 미리보기 자체는 저장을 호출하지 않음

    def test_preview_updates_on_select_all(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_master_select").check().run()
        df = at.dataframe[0].value
        assert all(r == "BLOCK" for r in df["review_status"])
        assert repo.save_calls == []

    def test_preview_caption_shows_counts(self):
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_chk_rec_0").check().run()
        at.checkbox(key="grid_chk_rec_2").check().run()
        captions = [c.value for c in at.caption]
        assert any("2 BLOCK" in c and "3 PASS" in c for c in captions)


class TestBatchTransitionResetsSelection:
    """1번째 배치에서 전체선택 체크한 채로 제출해도 2번째 배치엔 그 상태가 남으면 안 된다.

    note: 전환 후 상태는 at.checkbox/.value가 아니라 at.session_state.filtered_state로 읽는다.
    _submit_grid_batch가 처리된 record_id의 grid_chk_* 키를 명시적으로 pop하는데,
    AppTest 내부적으로 이미 pop된 위젯 키를 다시 세번째 run() 이후 조회하면
    (at.checkbox 재조회, 같은 세션에서 두번째 제출 등) AppTest 자체의 스테일 위젯 참조
    버그로 KeyError가 나는 게 확인됨 — 프로덕션 코드(at.exception은 매번 비어있음)가 아니라
    테스트 하네스 쪽 한계이므로, 그 경로를 피해 session_state를 직접 읽는다.
    """

    def test_master_select_resets_false_on_new_batch(self):
        batch1 = _make_candidates(5)
        batch2 = [{"record_id": f"rec2_{i}", "image_url": f"http://fake2/{i}.jpg"} for i in range(5)]
        repo = FakeRepo([batch1, batch2])
        at = _run(repo)

        at.checkbox(key="grid_master_select").check().run()
        assert at.checkbox(key="grid_master_select").value is True

        at.button(key="grid_submit").click().run()  # batch1 제출 -> grid_batch=None -> batch2 재조회

        assert not at.exception
        assert at.session_state.filtered_state["grid_master_select"] is False

    def test_individual_checks_reset_on_new_batch(self):
        batch1 = _make_candidates(5)
        batch2 = [{"record_id": f"rec2_{i}", "image_url": f"http://fake2/{i}.jpg"} for i in range(5)]
        repo = FakeRepo([batch1, batch2])
        at = _run(repo)

        at.checkbox(key="grid_master_select").check().run()
        at.button(key="grid_submit").click().run()

        assert not at.exception
        state = at.session_state.filtered_state
        old_batch_keys = [k for k in state if k.startswith("grid_chk_rec_")]
        new_batch_keys = [k for k in state if k.startswith("grid_chk_rec2_")]
        assert old_batch_keys == []  # batch1 체크 상태는 완전히 정리됨
        assert len(new_batch_keys) == 5
        assert all(state[k] is False for k in new_batch_keys)

    def test_new_batch_would_submit_all_pass(self):
        """batch2는 전부 미체크 상태로 초기화되므로, 이 상태 그대로 확정하면 전부 PASS다.

        (같은 AppTest 세션에서 두 번째 제출을 실제로 누르면 하네스 버그가 나서,
        여기서는 build_review_payloads로 이 상태가 실제 어떤 payload를 만드는지 직접 확인한다 —
        이 함수는 1단계에서 이미 그 자체로 9개 테스트를 통과한 순수 함수다.)
        """
        from modules.infra.review_batch import build_review_payloads

        batch1 = _make_candidates(5)
        batch2_ids = [f"rec2_{i}" for i in range(5)]
        batch2 = [{"record_id": rid, "image_url": "x"} for rid in batch2_ids]
        repo = FakeRepo([batch1, batch2])
        at = _run(repo)

        at.checkbox(key="grid_master_select").check().run()
        at.button(key="grid_submit").click().run()

        state = at.session_state.filtered_state
        checked = [k[len("grid_chk_"):] for k in state if k.startswith("grid_chk_rec2_") and state[k]]
        payloads = build_review_payloads(batch2_ids, checked)
        assert all(p["review_status"] == "PASS" for p in payloads)


class TestDurableUndoAcrossRefresh:
    """260712 INC 재발 방지: undo_store를 주입하면, 브라우저 새로고침(=완전히 새 세션)
    후에도 '직전 배치 실행취소' 버튼이 SQLite에서 복원돼야 한다."""

    def test_undo_button_absent_without_store_after_refresh(self):
        """대조군: undo_store 없이는(기존 동작) 새로고침 후 버튼이 사라진다."""
        repo = FakeRepo(_make_candidates(5))
        at = _run(repo)
        at.checkbox(key="grid_chk_rec_0").check().run()
        at.button(key="grid_submit").click().run()
        assert "grid_undo_btn" in [b.key for b in at.button]  # 같은 세션엔 정상적으로 있음

        # "새로고침" 시뮬레이션 — 완전히 새로운 AppTest 세션(session_state 전부 리셋)
        repo2 = FakeRepo(_make_candidates(5))
        at2 = _run(repo2)
        keys = [b.key for b in at2.button]
        assert "grid_undo_btn" not in keys  # 저장소가 없으니 복원 불가 — 기존의 알려진 결함

    def test_undo_button_restored_after_refresh_with_store(self, tmp_path):
        from modules.infra.undo_state_store import UndoStateStore

        db_path = str(tmp_path / "undo_state.db")
        store1 = UndoStateStore(db_path)
        repo = FakeRepo(_make_candidates(5))
        at = _run_with_store(repo, store1)
        at.checkbox(key="grid_chk_rec_0").check().run()
        at.button(key="grid_submit").click().run()

        assert store1.get_latest_undoable() is not None  # 저장소에 기록됐는지 확인

        # "새로고침" 시뮬레이션 — 완전히 새 AppTest 세션 + 새 UndoStateStore 인스턴스(같은 DB 파일)
        store2 = UndoStateStore(db_path)
        repo2 = FakeRepo(_make_candidates(5))
        at2 = _run_with_store(repo2, store2)

        keys = [b.key for b in at2.button]
        assert "grid_undo_btn" in keys

    def test_undo_click_after_refresh_actually_reverts_and_cancels_store_entry(self, tmp_path):
        from modules.infra.undo_state_store import UndoStateStore

        db_path = str(tmp_path / "undo_state.db")
        store1 = UndoStateStore(db_path)
        repo = FakeRepo(_make_candidates(5))
        at = _run_with_store(repo, store1)
        at.checkbox(key="grid_chk_rec_0").check().run()
        at.button(key="grid_submit").click().run()
        assert repo.statuses["rec_0"] == "BLOCK"

        # 새로고침 후 새 세션에서 실행취소 클릭 — repo는 REAL(같은 데이터를 들고 있는) 것과
        # 동일해야 실제로 되돌려지므로, 같은 repo 인스턴스를 재사용한다(같은 Airtable을 의미).
        store2 = UndoStateStore(db_path)
        at2 = _run_with_store(repo, store2)
        at2.button(key="grid_undo_btn").click().run()

        assert repo.statuses["rec_0"] == "PENDING"
        assert store2.get_latest_undoable() is None  # 취소 완료로 기록되어 더 이상 undoable 아님

    def test_no_persisted_batch_means_no_undo_button(self, tmp_path):
        from modules.infra.undo_state_store import UndoStateStore

        store = UndoStateStore(str(tmp_path / "undo_state.db"))
        repo = FakeRepo(_make_candidates(5))
        at = _run_with_store(repo, store)
        keys = [b.key for b in at.button]
        assert "grid_undo_btn" not in keys

    def test_second_real_batch_supersedes_first_in_undo_store(self, tmp_path):
        """Codex 지적 재확인: 두 번째 배치를 실제로 커밋하면 첫 번째는 더 이상 undoable이면 안 된다.

        (같은 AppTest 세션에서 두 번째 제출을 실제로 누르면 이미 알려진 AppTest 하네스
        스테일 위젯 버그가 나므로, 각 배치를 별도 AppTest 세션으로 나눠서 진행 — 새로고침 후
        다음 배치를 처리하는 실제 시나리오와도 더 가깝다.)
        """
        from modules.infra.undo_state_store import UndoStateStore

        db_path = str(tmp_path / "undo_state.db")

        batch1 = _make_candidates(5)
        store1 = UndoStateStore(db_path)
        repo1 = FakeRepo(batch1)
        at1 = _run_with_store(repo1, store1)
        at1.button(key="grid_submit").click().run()  # batch1 커밋

        first_undoable = store1.get_latest_undoable()
        assert first_undoable is not None
        assert {p["record_id"] for p in first_undoable["payload"]} == {c["record_id"] for c in batch1}

        batch2 = [{"record_id": f"rec2_{i}", "image_url": "x"} for i in range(5)]
        store2 = UndoStateStore(db_path)  # 새 세션 + 같은 DB 파일
        repo2 = FakeRepo(batch2)
        at2 = _run_with_store(repo2, store2)
        at2.button(key="grid_submit").click().run()  # batch2 커밋

        second_undoable = store2.get_latest_undoable()
        assert second_undoable is not None
        assert {p["record_id"] for p in second_undoable["payload"]} == {c["record_id"] for c in batch2}
        # batch1 record_id는 더 이상 undoable payload에 없어야 함
        assert not ({c["record_id"] for c in batch1} & {p["record_id"] for p in second_undoable["payload"]})

    def test_prepare_batch_failure_blocks_airtable_patch(self):
        """SQLite 쓰기(prepare_batch) 실패 시 Airtable PATCH를 아예 시작하면 안 된다."""

        class FailingUndoStore:
            def prepare_batch(self, batch_id, payload):
                raise RuntimeError("simulated sqlite write failure")

            def get_latest_undoable(self):
                return None

            def get_latest_prepared(self):
                return None

            def mark_committed(self, batch_id):
                pass

            def mark_failed(self, batch_id, error_message=""):
                pass

            def mark_cancelled(self, batch_id):
                pass

        repo = FakeRepo(_make_candidates(5))
        at = _run_with_store(repo, FailingUndoStore())
        at.button(key="grid_submit").click().run()

        assert repo.save_calls == []  # PATCH 자체가 시도되지 않았어야 함
        assert len(at.error) > 0


class TestPreparedBatchRecovery:
    """mark_committed/mark_failed가 실행되지 못해 'prepared'에 멈춘 배치를
    다음 접속 시 GET-only로 재확인해서 committed/failed로 전환하는지 확인."""

    def test_stuck_prepared_batch_that_actually_succeeded_recovers_to_committed(self, tmp_path):
        from modules.infra.undo_state_store import UndoStateStore

        db_path = str(tmp_path / "undo_state.db")
        store = UndoStateStore(db_path)
        payload = [
            {"record_id": "rec_0", "review_status": "BLOCK"},
            {"record_id": "rec_1", "review_status": "PASS"},
        ]
        store.prepare_batch("stuck1", payload)  # mark_committed가 호출 안 된 채로 멈춘 상황 시뮬레이션

        # 실제로는 Airtable 저장이 성공했던 상황 — FakeRepo에 그 결과를 미리 반영해둔다.
        repo = FakeRepo(_make_candidates(5))
        repo.statuses["rec_0"] = "BLOCK"
        repo.statuses["rec_1"] = "PASS"

        at = _run_with_store(repo, store)

        assert not at.exception
        assert len(at.success) > 0  # "복구 완료" 메시지
        assert store.get_latest_undoable() is not None  # committed로 전환됨
        assert "grid_undo_btn" in [b.key for b in at.button]  # 실행취소 버튼도 정상 복원

    def test_stuck_prepared_batch_that_actually_failed_recovers_to_failed(self, tmp_path):
        from modules.infra.undo_state_store import UndoStateStore

        db_path = str(tmp_path / "undo_state.db")
        store = UndoStateStore(db_path)
        payload = [{"record_id": "rec_0", "review_status": "BLOCK"}]
        store.prepare_batch("stuck1", payload)

        # 실제로는 저장이 반영 안 된 상황(여전히 PENDING 등 다른 값)
        repo = FakeRepo(_make_candidates(5))
        repo.statuses["rec_0"] = "PENDING"

        at = _run_with_store(repo, store)

        assert not at.exception
        assert len(at.error) > 0  # "복구 결과 — 실패" 메시지
        assert store.get_latest_prepared() is None  # failed로 전환됨(더 이상 prepared 아님)
        assert store.get_latest_undoable() is None  # committed도 아님
        assert "grid_undo_btn" not in [b.key for b in at.button]
        # 화면 잠금 — 실패로 확정된 뒤에도 새 배치/확정 버튼을 보여주면 안 된다.
        assert "grid_submit" not in [b.key for b in at.button]
        assert len(at.checkbox) == 0

    def test_verification_errors_only_keeps_prepared_and_locks_screen(self, tmp_path):
        """GET 자체가 실패(값 불일치 확정 아님)면 failed로 넘기지 않고 prepared를 유지해야
        한다 — 일시적 네트워크 오류일 수 있으므로. 화면도 잠가서 새 배치 진행을 막는다."""
        from modules.infra.undo_state_store import UndoStateStore

        db_path = str(tmp_path / "undo_state.db")
        store = UndoStateStore(db_path)
        payload = [{"record_id": "rec_0", "review_status": "BLOCK"}]
        store.prepare_batch("stuck1", payload)

        # 403은 재시도 대상이 아니라서(즉시 verification_error로 분류) 실제 대기 없이
        # 테스트가 빠르게 끝난다 — 5xx/429였어도 결과는 동일(prepared 유지)하지만, 그건
        # review_batch_committer의 재시도 정책 자체를 테스트하는 게 아니라 여기서는
        # "값 불일치가 아니면 prepared를 유지한다"는 이 파일의 관심사만 확인하면 된다.
        repo = FakeRepo(
            _make_candidates(5),
            get_error_for={"rec_0": _HttpLikeError("forbidden", status_code=403)},
        )
        at = _run_with_store(repo, store)

        assert not at.exception
        assert len(at.warning) > 0  # error가 아니라 warning(일시적일 수 있음, 확정 아님)
        assert store.get_latest_prepared() is not None  # 여전히 prepared — failed로 넘어가지 않음
        assert store.get_latest_prepared()["batch_id"] == "stuck1"
        assert store.get_latest_undoable() is None
        # 화면 잠금 — 여전히 불확실하니 새 배치/확정 버튼을 보여주면 안 된다.
        assert "grid_submit" not in [b.key for b in at.button]
        assert len(at.checkbox) == 0


class TestMarkCommittedFailedExceptionsDoNotCrash:
    """mark_committed/mark_failed가 예외를 던져도 화면이 죽으면 안 되고,
    Airtable 쪽 결과(성공/실패 여부)는 그대로 유지돼야 한다."""

    def test_mark_committed_exception_does_not_crash_and_batch_still_clears(self):
        class FlakyUndoStore:
            def prepare_batch(self, batch_id, payload):
                pass

            def get_latest_undoable(self):
                return None

            def get_latest_prepared(self):
                return None

            def mark_committed(self, batch_id):
                raise RuntimeError("simulated sqlite failure on commit")

            def mark_failed(self, batch_id, error_message=""):
                pass

            def mark_cancelled(self, batch_id):
                pass

        repo = FakeRepo(_make_candidates(5))
        at = _run_with_store(repo, FlakyUndoStore())
        at.button(key="grid_submit").click().run()

        assert not at.exception  # 화면이 죽지 않아야 함
        assert len(repo.save_calls) == 5  # Airtable 저장은 정상적으로 끝까지 진행됨
        assert len(at.warning) > 0  # 경고로 안내

    def test_mark_failed_exception_does_not_crash(self):
        class FlakyUndoStore:
            def prepare_batch(self, batch_id, payload):
                pass

            def get_latest_undoable(self):
                return None

            def get_latest_prepared(self):
                return None

            def mark_committed(self, batch_id):
                pass

            def mark_failed(self, batch_id, error_message=""):
                raise RuntimeError("simulated sqlite failure on fail-record")

            def mark_cancelled(self, batch_id):
                pass

        repo = FakeRepo(_make_candidates(5), fail_on_save_for=["rec_2"])
        at = _run_with_store(repo, FlakyUndoStore())
        at.button(key="grid_submit").click().run()

        assert not at.exception
        assert len(at.warning) > 0
        assert len(at.error) > 0  # 원래의 저장 실패 안내도 그대로 표시됨


class TestMarkCancelledFailureKeepsUndoInfo:
    """mark_cancelled()가 실패하면(하지만 실제 되돌리기는 Airtable에 반영됨),
    실행취소 정보를 지우면 안 된다 — 성공 후에만 정보 제거."""

    def test_mark_cancelled_failure_does_not_clear_undo_ids(self, tmp_path):
        from modules.infra.undo_state_store import UndoStateStore

        class FlakyOnCancelStore(UndoStateStore):
            def mark_cancelled(self, batch_id):
                raise RuntimeError("simulated sqlite failure on cancel")

        db_path = str(tmp_path / "undo_state.db")
        store = FlakyOnCancelStore(db_path)
        repo = FakeRepo(_make_candidates(5))

        at = _run_with_store(repo, store)
        at.checkbox(key="grid_chk_rec_0").check().run()
        at.button(key="grid_submit").click().run()
        assert repo.statuses["rec_0"] == "BLOCK"

        at.button(key="grid_undo_btn").click().run()

        assert not at.exception
        assert repo.statuses["rec_0"] == "PENDING"  # 실제 되돌리기는 성공
        assert len(at.error) > 0  # 기록 갱신 실패는 알림
        assert at.session_state.filtered_state["grid_undo_ids"] == ["rec_0", "rec_1", "rec_2", "rec_3", "rec_4"]
        assert "grid_undo_btn" in [b.key for b in at.button]  # 정보가 지워지지 않아 버튼도 그대로
