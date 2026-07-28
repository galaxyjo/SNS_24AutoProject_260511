"""Safety Package S5 — Controlled Canary Write Budget와 영구 재실행 방지.

외부 Write를 직접 수행하지 않는다. Runner는 각 외부 요청 직전에
``authorize_write()``를 호출해야 하며, 허용 횟수는 요청 성공 여부와 무관하게
먼저 영구 기록된다. 따라서 실패 후 자동 재시도도 예산을 우회할 수 없다.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from modules.common.canary_safe_mode import (
    CanarySafeModeError,
    get_canary_safe_mode_state,
)


class CanaryExecutionError(RuntimeError):
    """Canary 실행·예산·Idempotency 계약 위반."""


class CanaryRoute(str, Enum):
    FACEBOOK = "facebook"
    DOME = "dome"


class CanaryWriteOperation(str, Enum):
    INSTAGRAM_POST_CREATE = "instagram_post_create"
    SOURCE_ITEM_CREATE = "source_item_create"
    SOURCE_ITEM_PATCH = "source_item_patch"
    OTHER_AIRTABLE_CREATE = "other_airtable_create"
    OTHER_AIRTABLE_UPDATE = "other_airtable_update"
    AIRTABLE_DELETE = "airtable_delete"
    IMGBB_UPLOAD = "imgbb_upload"
    INSTAGRAM_PUBLISH = "instagram_publish"
    DM_OR_COMMENT = "dm_or_comment"


_ALL_ZERO = {operation: 0 for operation in CanaryWriteOperation}


@dataclass(frozen=True)
class CanaryWriteBudget:
    route: CanaryRoute
    limits: dict[CanaryWriteOperation, int]
    exact_source_record_id: str = ""

    @classmethod
    def for_facebook(cls) -> "CanaryWriteBudget":
        limits = dict(_ALL_ZERO)
        limits[CanaryWriteOperation.INSTAGRAM_POST_CREATE] = 1
        return cls(route=CanaryRoute.FACEBOOK, limits=limits)

    @classmethod
    def for_dome(cls, exact_source_record_id: str) -> "CanaryWriteBudget":
        record_id = (exact_source_record_id or "").strip()
        if not record_id:
            raise CanaryExecutionError("Dome exact_source_record_id 필수")
        limits = dict(_ALL_ZERO)
        limits[CanaryWriteOperation.SOURCE_ITEM_PATCH] = 2
        limits[CanaryWriteOperation.INSTAGRAM_POST_CREATE] = 1
        return cls(
            route=CanaryRoute.DOME,
            limits=limits,
            exact_source_record_id=record_id,
        )


class CanaryExecutionGuard:
    """SQLite에 Run ID와 선소진 Write 횟수를 기록하는 fail-closed Guard."""

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS canary_runs (
            canary_run_id TEXT PRIMARY KEY,
            route TEXT NOT NULL,
            exact_source_identifier TEXT NOT NULL,
            exact_source_record_id TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            write_counts_json TEXT NOT NULL,
            terminal_code TEXT NOT NULL DEFAULT ''
        )
    """

    def __init__(
        self,
        canary_run_id: str,
        exact_source_identifier: str,
        budget: CanaryWriteBudget,
        *,
        db_path: str | Path | None = None,
    ):
        self.canary_run_id = (canary_run_id or "").strip()
        self.exact_source_identifier = (exact_source_identifier or "").strip()
        self.budget = budget
        self.db_path = Path(db_path) if db_path else (
            Path(__file__).resolve().parents[2] / "db" / "canary_runs.db"
        )
        self._begun = False
        if not self.canary_run_id:
            raise CanaryExecutionError("canary_run_id 필수")
        if not self.exact_source_identifier:
            raise CanaryExecutionError("exact_source_identifier 필수")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _validate_live_context(self):
        try:
            state = get_canary_safe_mode_state()
        except CanarySafeModeError as exc:
            raise CanaryExecutionError(str(exc)) from exc
        if not state.enabled:
            raise CanaryExecutionError("Canary Safe Mode 활성 필요")
        if state.run_id != self.canary_run_id:
            raise CanaryExecutionError(
                "canary_run_id가 승인된 Safe Mode Context와 불일치"
            )
        return state

    def begin(self) -> None:
        """Run ID를 원자적으로 선점한다. 기존 상태와 무관하게 재사용은 금지한다."""

        state = self._validate_live_context()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        counts = {
            operation.value: 0
            for operation in CanaryWriteOperation
        }
        started_at = datetime.now(timezone.utc).isoformat()
        expires_at = state.expires_at.isoformat() if state.expires_at else ""

        with self._connect() as connection:
            connection.execute(self._SCHEMA)
            try:
                connection.execute(
                    """
                    INSERT INTO canary_runs (
                        canary_run_id, route, exact_source_identifier,
                        exact_source_record_id, status, started_at, expires_at,
                        write_counts_json, terminal_code
                    ) VALUES (?, ?, ?, ?, 'RUNNING', ?, ?, ?, '')
                    """,
                    (
                        self.canary_run_id,
                        self.budget.route.value,
                        self.exact_source_identifier,
                        self.budget.exact_source_record_id,
                        started_at,
                        expires_at,
                        json.dumps(counts, sort_keys=True),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise CanaryExecutionError(
                    "canary_run_id 재사용 금지"
                ) from exc
        self._begun = True

    def authorize_write(
        self,
        operation: CanaryWriteOperation,
        *,
        record_id: str = "",
    ) -> int:
        """외부 요청 전에 예산 1회를 영구 선소진하고 새 누적값을 반환한다."""

        self._validate_live_context()
        if not isinstance(operation, CanaryWriteOperation):
            raise CanaryExecutionError("알 수 없는 Write operation")
        if not self._begun:
            raise CanaryExecutionError("현재 프로세스 begin() 전 Write 금지")

        if operation == CanaryWriteOperation.SOURCE_ITEM_PATCH:
            expected = self.budget.exact_source_record_id
            if not expected or (record_id or "").strip() != expected:
                raise CanaryExecutionError(
                    "승인된 Source Item 외 PATCH 금지"
                )

        if not self.db_path.exists():
            raise CanaryExecutionError("begin() 전 Write 금지")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                row = connection.execute(
                    """
                    SELECT route, exact_source_identifier, exact_source_record_id,
                           status, write_counts_json
                      FROM canary_runs
                     WHERE canary_run_id = ?
                    """,
                    (self.canary_run_id,),
                ).fetchone()
            except sqlite3.OperationalError as exc:
                raise CanaryExecutionError("begin() 전 Write 금지") from exc
            if row is None:
                raise CanaryExecutionError("begin() 전 Write 금지")
            if row["status"] != "RUNNING":
                raise CanaryExecutionError("종료된 Canary Run의 Write 금지")
            if row["route"] != self.budget.route.value:
                raise CanaryExecutionError("저장된 Canary Route 불일치")
            if row["exact_source_identifier"] != self.exact_source_identifier:
                raise CanaryExecutionError("저장된 exact_source_identifier 불일치")
            if row["exact_source_record_id"] != self.budget.exact_source_record_id:
                raise CanaryExecutionError("저장된 exact_source_record_id 불일치")

            counts = json.loads(row["write_counts_json"])
            key = operation.value
            next_count = int(counts.get(key, 0)) + 1
            limit = int(self.budget.limits.get(operation, 0))
            if next_count > limit:
                raise CanaryExecutionError(
                    f"Write Budget 초과: {key} {next_count}>{limit}"
                )
            counts[key] = next_count
            connection.execute(
                """
                UPDATE canary_runs
                   SET write_counts_json = ?
                 WHERE canary_run_id = ?
                """,
                (json.dumps(counts, sort_keys=True), self.canary_run_id),
            )
            return next_count

    def complete(self) -> None:
        self._mark_terminal("COMPLETED", "SUCCESS")

    def fail(self, terminal_code: str) -> None:
        code = (terminal_code or "FAILED").strip()[:128]
        self._mark_terminal("FAILED", code)

    def _mark_terminal(self, status: str, terminal_code: str) -> None:
        self._validate_live_context()
        if not self._begun:
            raise CanaryExecutionError(
                "현재 프로세스에서 begin()을 완료하지 않은 종료 금지"
            )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE canary_runs
                   SET status = ?, terminal_code = ?
                 WHERE canary_run_id = ? AND status = 'RUNNING'
                """,
                (status, terminal_code, self.canary_run_id),
            )
            if cursor.rowcount != 1:
                raise CanaryExecutionError(
                    "존재하지 않거나 이미 종료된 Canary Run"
                )

    def read_evidence(self) -> dict | None:
        """감사용 Read-only Snapshot. DB가 없으면 생성하지 않고 None을 반환한다."""

        if not self.db_path.exists():
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM canary_runs WHERE canary_run_id = ?",
                (self.canary_run_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["write_counts"] = json.loads(result.pop("write_counts_json"))
        return result
