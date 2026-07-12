"""
modules/infra/review_grid_ui.py
Tab 8 "학습 리뷰" 그리드 일괄 처리 화면 렌더링.
dashboard.py의 인라인 블록에서 추출 — repo를 인자로 주입받아
테스트 시 가짜 repo로 교체 가능하게(실제 Airtable 접속 없이 AppTest 검증).

저장/실행취소는 review_batch_committer의 안전 실패 오케스트레이터를 통해서만 수행한다 —
committed=False(저장 중 실패, 또는 저장 후 GET 재검증 불일치)면 배치와 선택 상태를 그대로
유지하고 다음 배치로 넘어가지 않는다. committed=True일 때만 배치를 비우고 다음 배치를 연다.

undo_store(선택)를 주입하면 "직전 배치 실행취소" 상태를 SQLite에 영구 저장한다 — 없으면
기존처럼 st.session_state에만 남아 새로고침 시 사라진다(260712 INC 재발 방지, undo_store가
없을 때는 이전 동작과 완전히 동일하게 유지).
"""
from __future__ import annotations

import uuid

import streamlit as st

from modules.infra.review_batch import build_review_payloads
from modules.infra.review_batch_committer import (
    commit_batch_with_verification,
    undo_batch_with_verification,
    verify_only,
)


def render_review_grid(repo, undo_store=None) -> None:
    """그리드 일괄 리뷰 — 체크 = 버릴(BLOCK), 나머지는 전부 자동 PASS."""
    if "grid_batch" not in st.session_state:
        st.session_state.grid_batch = None

    # ── 복구: mark_committed/mark_failed가 어떤 이유로든 실행되지 못해 'prepared'에
    # 멈춘 배치가 있으면(Airtable 저장은 이미 끝났을 수도, 실패했을 수도 있는 불확실한 상태),
    # PATCH 없이 GET-only로 실제 결과를 확인해서 committed/failed로 전환한다.
    #
    # 복구가 committed로 완전히 끝나지 않는 한(진짜 실패로 확정됐거나, 확인 자체가 안 돼서
    # 여전히 불확실하거나) 아래로 내려가지 않고 여기서 화면을 잠근다 — 새 배치 조회도,
    # 확정 버튼도 보여주지 않는다.
    if undo_store is not None:
        _prepared = undo_store.get_latest_prepared()
        if _prepared is not None:
            st.warning("⚠️ 이전 저장 상태가 불확실합니다 — 복구를 확인하는 중입니다.")
            _expected = {p["record_id"]: p["review_status"] for p in _prepared["payload"]}
            _verify = verify_only(repo, _expected)

            if _verify.verified:
                try:
                    undo_store.mark_committed(_prepared["batch_id"])
                except Exception as e:
                    st.error(f"복구 중 기록 갱신 실패 — {e}\n다음 접속 시 다시 시도합니다.")
                    return
                st.success(
                    "✅ 복구 완료 — 이전 저장은 실제로 성공했습니다. "
                    "실행취소가 다시 가능합니다."
                )
                # committed로 완전히 해소됐으므로 여기서만 계속 진행(return 안 함).
            elif _verify.mismatched_ids:
                # GET이 성공적으로 응답했는데 값 자체가 실제로 다름 — 진짜 실패로 확정.
                try:
                    undo_store.mark_failed(
                        _prepared["batch_id"],
                        f"값 불일치 확인됨: {', '.join(_verify.mismatched_ids)}",
                    )
                except Exception as e:
                    st.error(f"복구 중 기록 갱신 실패 — {e}")
                st.error(
                    f"❌ 복구 결과 — 이전 저장이 실제로 실패한 것으로 확인됐습니다 "
                    f"(값 불일치 {len(_verify.mismatched_ids)}건: {', '.join(_verify.mismatched_ids)}). "
                    f"운영자가 원본 데이터를 직접 확인·조치해야 합니다. "
                    f"이 문제가 해결되기 전까지 새 배치 작업을 진행할 수 없습니다."
                )
                return
            else:
                # GET 자체가 실패(verification_errors만 있음) — 값이 틀렸다고 확정할 근거가
                # 없다(일시적 네트워크 오류일 수 있음). 상태를 건드리지 않고 prepared 그대로
                # 유지해서 다음 접속 때 다시 재시도하게 한다.
                st.warning(
                    f"⏳ 확인(GET) 자체가 실패했습니다({len(_verify.verification_errors)}건) — "
                    f"일시적인 오류일 수 있어 상태를 그대로 유지합니다. 다음 접속 시 다시 확인합니다."
                )
                return

    # 새로고침 등으로 세션이 비었을 때, 영구 저장소에 아직 남아있는 "직전 배치 실행취소"를 복원.
    if undo_store is not None and not st.session_state.get("grid_undo_ids"):
        _persisted = undo_store.get_latest_undoable()
        if _persisted:
            st.session_state["grid_undo_ids"] = [p["record_id"] for p in _persisted["payload"]]
            st.session_state["grid_undo_batch_id"] = _persisted["batch_id"]

    if not st.session_state.grid_batch:
        try:
            st.session_state.grid_batch = repo.fetch_pending_candidates(limit=50)
            # 새 배치를 받을 때마다 전체선택/개별선택 상태를 초기화 —
            # 이전 배치의 선택 상태가 화면에 남아 실제 선택 집합과 어긋나는 사고 방지.
            st.session_state["grid_master_select"] = False
            st.session_state["grid_verification_blocked"] = False
            for c in st.session_state.grid_batch:
                st.session_state[f"grid_chk_{c['record_id']}"] = False
        except Exception as e:
            st.error(f"후보 조회 실패: {e}")
            st.session_state.grid_batch = []

    # ── 방금 처리한 배치 실행취소 (시간 제한 없음 — 다음 배치 제출 전까지 유지) ─────
    _undo_ids = st.session_state.get("grid_undo_ids") or []
    if _undo_ids:
        if st.button(f"\U000021a9️ 방금 배치 실행취소 ({len(_undo_ids)}건)", key="grid_undo_btn"):
            with st.spinner("되돌리는 중..."):
                result = undo_batch_with_verification(repo, _undo_ids)
            if not result.committed:
                if result.failed_id:
                    st.error(
                        f"되돌리기 실패 — {result.failed_id}: {result.failed_error}\n"
                        f"다시 시도해주세요."
                    )
                else:
                    if result.mismatched_ids:
                        st.error(
                            f"되돌린 뒤 확인(GET) 결과 값이 실제로 다릅니다 — "
                            f"{', '.join(result.mismatched_ids)}\n다시 시도해주세요."
                        )
                    if result.verification_errors:
                        st.error(
                            f"되돌린 뒤 확인(GET) 자체가 실패했습니다(값 불일치 아님) — "
                            f"{len(result.verification_errors)}건: " + ", ".join(
                                f"{e.record_id}(HTTP {e.status_code or '?'} {e.error_type})"
                                for e in result.verification_errors
                            ) + "\n저장은 이미 완료됐을 수 있습니다. 확인 후 다시 시도해주세요."
                        )
            else:
                if undo_store is not None:
                    _bid = st.session_state.get("grid_undo_batch_id")
                    if _bid:
                        try:
                            undo_store.mark_cancelled(_bid)
                        except Exception as e:
                            # 실제 되돌리기(PATCH+GET)는 성공했다 — 다만 이 사실을 영구
                            # 기록하는 데 실패했으므로, 세션의 실행취소 정보를 지우지 않고
                            # 그대로 둔다(mark_cancelled 성공 후에만 정보 제거).
                            st.error(
                                f"실행취소는 Airtable에 반영됐지만 기록 갱신에 실패했습니다 — {e}\n"
                                f"다음 접속 시 이 배치가 다시 실행취소 가능한 상태로 보일 수 있습니다."
                            )
                            return
                st.session_state["grid_undo_ids"] = []
                st.session_state["grid_undo_batch_id"] = None
                st.session_state.grid_batch = None
                st.rerun()
        st.divider()

    batch = st.session_state.grid_batch

    if not batch:
        st.success("\U0001f389 리뷰할 후보가 없습니다 — 전부 처리했거나 아직 수집된 게 없습니다.")
        return

    # 체크 = 버릴(불합격) 사진, 기본값은 전부 PASS.

    def _submit_grid_batch() -> bool:
        """성공적으로 커밋됐으면 True(배치 비움), 실패면 False(배치·선택 상태 유지)."""
        batch_ids = [c["record_id"] for c in batch]
        block_ids = [rid for rid in batch_ids if st.session_state.get(f"grid_chk_{rid}", False)]
        payload = build_review_payloads(batch_ids, block_ids)

        # PATCH를 시작하기 전에 먼저 영구 저장 — 이 기록이 실패하면 Airtable 쓰기 자체를
        # 시작하지 않는다(SQLite 쓰기 실패 시 Airtable PATCH 시작 금지).
        _bid = None
        if undo_store is not None:
            _bid = str(uuid.uuid4())
            try:
                undo_store.prepare_batch(_bid, payload)
            except Exception as e:
                st.error(f"실행취소 기록 준비 실패 — 저장을 시작하지 않았습니다: {e}")
                return False

        with st.spinner("일괄 처리 중..."):
            result = commit_batch_with_verification(repo, batch_ids, block_ids)

        if not result.committed:
            if undo_store is not None and _bid is not None:
                try:
                    undo_store.mark_failed(_bid, result.failed_error or "GET 재검증 실패")
                except Exception as e:
                    st.warning(
                        f"실행취소 기록(실패 상태) 갱신 실패 — {e}\n"
                        f"다음 접속 시 자동으로 재확인됩니다."
                    )
            if result.failed_id:
                st.error(
                    f"저장 실패 — {result.failed_id}: {result.failed_error}\n"
                    f"배치와 선택 상태를 그대로 유지합니다. 다시 시도해주세요."
                )
            else:
                if result.mismatched_ids:
                    st.error(
                        f"저장 후 확인(GET) 결과 값이 실제로 다릅니다 — "
                        f"{', '.join(result.mismatched_ids)}\n"
                        f"배치와 선택 상태를 그대로 유지합니다. 다시 시도해주세요."
                    )
                if result.verification_errors:
                    st.session_state["grid_verification_blocked"] = True
                    st.error(
                        f"저장 후 확인(GET) 자체가 실패했습니다(값 불일치 아님) — "
                        f"{len(result.verification_errors)}건: " + ", ".join(
                            f"{e.record_id}(HTTP {e.status_code or '?'} {e.error_type})"
                            for e in result.verification_errors
                        ) + "\n저장은 이미 완료됐을 수 있습니다. "
                        "확정 버튼을 다시 누르지 마세요 — 재확인 후 별도로 안내해드리겠습니다."
                    )
            return False

        for rid in batch_ids:
            st.session_state.pop(f"grid_chk_{rid}", None)
        st.session_state["grid_undo_ids"] = batch_ids
        st.session_state.grid_batch = None

        _bookkeeping_ok = True
        if undo_store is not None and _bid is not None:
            try:
                undo_store.mark_committed(_bid)
                st.session_state["grid_undo_batch_id"] = _bid
            except Exception as e:
                # Airtable 저장 자체는 이미 성공했다(위에서 배치는 이미 비웠다) — 여기서
                # 실패해도 그 사실은 바뀌지 않는다. SQLite 기록만 'prepared'에 멈추고,
                # 다음 접속 시 복구 로직이 GET-only로 재확인해서 committed/failed로 전환한다
                # (render_review_grid 상단 참조). 이 경고를 화면에 실제로 보여주기 위해
                # False를 반환해서 호출부의 자동 rerun을 이번만 건너뛴다.
                _bookkeeping_ok = False
                st.warning(
                    f"저장은 성공했지만 실행취소 기록 갱신에 실패했습니다 — {e}\n"
                    f"다음 접속 시 자동으로 재확인됩니다."
                )
        return _bookkeeping_ok

    selected_ids = {
        c["record_id"] for c in batch
        if st.session_state.get(f"grid_chk_{c['record_id']}", False)
    }
    n_block = len(selected_ids)
    n_pass = len(batch) - n_block

    def _on_master_toggle():
        _val = st.session_state.get("grid_master_select", False)
        for c in st.session_state.grid_batch:
            st.session_state[f"grid_chk_{c['record_id']}"] = _val

    sel_col, cnt_col = st.columns([1, 2])
    with sel_col:
        st.checkbox("전체 선택", key="grid_master_select", on_change=_on_master_toggle)
    with cnt_col:
        st.markdown(
            f'<div style="background:#1a56db;color:#fff;font-weight:700;'
            f'padding:6px 16px;border-radius:6px;font-size:1em;'
            f'display:inline-block;">'
            f'\U0001f5d1️ BLOCK 선택 {n_block}</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    n_cols = 5
    grid_cols = st.columns(n_cols)
    for i, cand in enumerate(batch):
        rid = cand["record_id"]
        with grid_cols[i % n_cols]:
            img_url = cand.get("image_url", "")
            st.markdown(
                f'<div style="width:100%;aspect-ratio:1/1;overflow:hidden;'
                f'border-radius:6px;background:#222;">'
                f'<img src="{img_url}" style="width:100%;height:100%;'
                f'object-fit:cover;display:block;" /></div>',
                unsafe_allow_html=True,
            )
            st.checkbox("버림", key=f"grid_chk_{rid}", label_visibility="collapsed")

    st.divider()

    # 읽기 전용 payload 미리보기 — Airtable 호출 없음, 체크 상태가 바뀔 때마다(=매 rerun) 자동 갱신.
    # 확정 버튼은 추가하지 않는다 — 하단 확정 버튼 하나만 유지 요구사항 유지.
    st.caption(f"\U0001f4cb 저장 시 전송될 payload 미리보기 ({n_block} BLOCK / {n_pass} PASS · 총 {len(batch)}건)")
    _preview_batch_ids = [c["record_id"] for c in batch]
    _preview_block_ids = [rid for rid in _preview_batch_ids if st.session_state.get(f"grid_chk_{rid}", False)]
    _preview_payloads = build_review_payloads(_preview_batch_ids, _preview_block_ids)
    st.dataframe(_preview_payloads, width="stretch", hide_index=True)

    st.divider()

    _verification_blocked = st.session_state.get("grid_verification_blocked", False)
    if _verification_blocked:
        st.warning(
            "⚠️ 직전 저장의 확인(GET)이 실패해서 확정 버튼을 잠갔습니다 — "
            "저장 자체는 이미 됐을 수 있습니다. 재확인 후 다시 안내해드리겠습니다."
        )

    if st.button(
        f"\U0001f5d1️ {n_block}개 BLOCK 처리 · 나머지 {n_pass}개 PASS",
        type="primary", use_container_width=True, key="grid_submit",
        disabled=_verification_blocked,
    ):
        if _submit_grid_batch():
            st.rerun()
