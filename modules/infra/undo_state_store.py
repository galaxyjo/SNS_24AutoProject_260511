"""
modules/infra/undo_state_store.py
학습 리뷰 그리드 "직전 배치 실행취소" 상태를 SQLite에 영구 저장.

기존엔 st.session_state에만 있어서 브라우저 새로고침으로 Streamlit 세션이 초기화되면
실행취소 대상(어떤 record_id들을 되돌릴 수 있는지) 자체가 사라졌음(260712 INC 재발 방지).
Airtable/Streamlit import 없음 — 순수 SQLite 래퍼.

상태 전이: prepared(PATCH 시작 전 기록) -> committed(저장+GET검증 성공, =실행취소 가능)
                                        -> failed(저장 또는 검증 실패)
           committed -> cancelled(실행취소 성공+GET검증 완료)
           committed -> superseded(더 새 배치가 prepare되면서 대체됨)

get_latest_undoable()은 "가장 최근에 생성된 배치가 지금 committed 상태일 때만" 반환한다 —
그 배치가 취소/대체/실패됐으면 그보다 오래된 배치를 대신 반환하지 않고 그냥 None을 반환한다
(직전 배치 단 하나만 실행취소 가능해야 한다는 요구사항).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone


class UndoStateStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_undo_batches (
                    batch_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    committed_at TEXT,
                    cancelled_at TEXT,
                    failed_at TEXT,
                    error_message TEXT
                )
                """
            )
            conn.commit()

    def prepare_batch(self, batch_id: str, payload: list[dict]) -> None:
        """Airtable PATCH를 시작하기 전에 반드시 먼저 호출 — 이 호출이 예외를 던지면
        (SQLite 쓰기 실패) 호출자는 PATCH를 절대 시작하면 안 된다.

        기존에 committed 상태였던 배치가 있으면 superseded로 전환한다 — "직전 배치
        하나만" 실행취소 가능해야 하므로, 새 배치가 준비되는 순간 이전 배치는 더 이상
        되돌리기 대상이 아니게 된다."""
        with closing(self._connect()) as conn:
            conn.execute("UPDATE review_undo_batches SET status = 'superseded' WHERE status = 'committed'")
            conn.execute(
                "INSERT OR REPLACE INTO review_undo_batches "
                "(batch_id, payload, status, created_at, committed_at, cancelled_at, failed_at, error_message) "
                "VALUES (?, ?, 'prepared', ?, NULL, NULL, NULL, NULL)",
                (batch_id, json.dumps(payload), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def mark_committed(self, batch_id: str) -> None:
        """저장(PATCH)과 GET 재검증이 전부 성공한 뒤 호출 — 이제부터 실행취소 가능."""
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE review_undo_batches SET status = 'committed', committed_at = ? WHERE batch_id = ?",
                (datetime.now(timezone.utc).isoformat(), batch_id),
            )
            conn.commit()

    def mark_failed(self, batch_id: str, error_message: str = "") -> None:
        """저장 또는 검증이 실패한 경우 호출 — 실행취소 대상 아님, 기록만 보존."""
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE review_undo_batches SET status = 'failed', failed_at = ?, error_message = ? "
                "WHERE batch_id = ?",
                (datetime.now(timezone.utc).isoformat(), error_message, batch_id),
            )
            conn.commit()

    def mark_cancelled(self, batch_id: str) -> None:
        """실행취소(undo) 성공 + GET 검증까지 끝난 뒤 호출."""
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE review_undo_batches SET status = 'cancelled', cancelled_at = ? WHERE batch_id = ?",
                (datetime.now(timezone.utc).isoformat(), batch_id),
            )
            conn.commit()

    def get_latest_undoable(self) -> dict | None:
        """가장 최근에 생성된 배치가 지금 'committed' 상태일 때만 반환한다.
        그 배치가 취소/대체/실패 상태면 더 오래된 배치로 대체 반환하지 않고 None."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT batch_id, payload, status, created_at FROM review_undo_batches "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        batch_id, payload_json, status, created_at = row
        if status != "committed":
            return None
        return {
            "batch_id": batch_id,
            "payload": json.loads(payload_json),
            "created_at": created_at,
        }

    def get_latest_prepared(self) -> dict | None:
        """가장 최근 배치가 지금 'prepared'(=결과 불확실, mark_committed/mark_failed가
        어떤 이유로든 아직 실행 안 됨)면 반환, 아니면 None. 새로고침 직후 이 상태가
        보이면 GET-only로 실제 결과를 재확인해서 committed/failed로 전환해야 한다."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT batch_id, payload, status, created_at FROM review_undo_batches "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        batch_id, payload_json, status, created_at = row
        if status != "prepared":
            return None
        return {
            "batch_id": batch_id,
            "payload": json.loads(payload_json),
            "created_at": created_at,
        }
