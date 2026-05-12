"""
retry_queue.py — SQLite 기반 영속 재시도 큐

사용법:
    from modules.common.retry_queue import RetryQueue

    rq = RetryQueue()
    rq.register("insta_upload", my_upload_fn)   # 핸들러 등록
    rq.start()                                   # 백그라운드 워커 시작

    rq.enqueue("insta_upload", {"record_id": "xxx", "image_url": "..."})

핸들러 시그니처:
    def my_handler(payload: dict) -> None:
        ...  # 실패 시 예외를 raise — 큐가 재시도 스케줄링

재시도 백오프 (기본): 10s → 60s → 300s
최대 3회 실패 후 status='dead' 로 보관 (삭제하지 않음).
"""

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict

from modules.common.logger import get_logger

logger = get_logger(__name__)

_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "retry_queue.db"
_BACKOFF  = [10, 60, 300]   # 재시도 대기(초): 1차, 2차, 3차
_POLL_SEC = 10               # 큐 폴링 주기(초)


# ── DB 초기화 ─────────────────────────────────────────────────────────────────

def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS retry_tasks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type    TEXT    NOT NULL,
            payload      TEXT    NOT NULL,
            attempts     INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            next_retry   TEXT    NOT NULL,
            status       TEXT    NOT NULL DEFAULT 'pending',
            last_error   TEXT,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rq_status ON retry_tasks(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rq_next   ON retry_tasks(next_retry)")
    conn.commit()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


# ── RetryQueue ────────────────────────────────────────────────────────────────

class RetryQueue:
    def __init__(self):
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._conn      = _get_conn()
        self._lock      = threading.Lock()
        self._handlers: Dict[str, Callable] = {}
        self._running   = False
        self._thread: threading.Thread | None = None

    def register(self, task_type: str, handler: Callable) -> None:
        """task_type 에 대한 핸들러 함수를 등록한다."""
        self._handlers[task_type] = handler
        logger.debug(f"[RetryQueue] 핸들러 등록: {task_type}")

    def enqueue(self, task_type: str, payload: dict, max_attempts: int = 3) -> int:
        """태스크를 큐에 추가하고 task id를 반환한다."""
        with self._lock:
            cur = self._conn.execute(
                """INSERT INTO retry_tasks (task_type, payload, max_attempts, next_retry)
                   VALUES (?, ?, ?, datetime('now'))""",
                (task_type, json.dumps(payload, ensure_ascii=False), max_attempts),
            )
            self._conn.commit()
            tid = cur.lastrowid
        logger.info(f"[RetryQueue] 큐 추가 | type={task_type} | id={tid}")
        return tid

    def start(self) -> None:
        """백그라운드 워커 스레드를 시작한다."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True, name="RetryQueueWorker")
        self._thread.start()
        logger.info("[RetryQueue] 워커 시작")

    def stop(self) -> None:
        self._running = False
        logger.info("[RetryQueue] 워커 중지 요청")

    # ── 내부 워커 ─────────────────────────────────────────────────────────────

    def _worker(self) -> None:
        while self._running:
            try:
                self._process_due()
            except Exception as exc:
                logger.error(f"[RetryQueue] 워커 오류: {exc}")
            time.sleep(_POLL_SEC)

    def _process_due(self) -> None:
        """next_retry 시각이 된 pending 태스크를 처리한다."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM retry_tasks
                   WHERE status = 'pending'
                     AND next_retry <= datetime('now')
                   ORDER BY next_retry
                   LIMIT 10"""
            ).fetchall()

        for row in rows:
            self._execute(dict(row))

    def _execute(self, task: dict) -> None:
        tid       = task["id"]
        task_type = task["task_type"]
        payload   = json.loads(task["payload"])
        attempts  = task["attempts"] + 1
        max_att   = task["max_attempts"]

        handler = self._handlers.get(task_type)
        if not handler:
            logger.warning(f"[RetryQueue] 핸들러 없음 | type={task_type} | id={tid}")
            self._update(tid, attempts, "dead", f"no handler for {task_type}")
            return

        try:
            handler(payload)
            self._update(tid, attempts, "done", None)
            logger.info(f"[RetryQueue] 성공 | type={task_type} | id={tid} | attempt={attempts}")

        except Exception as exc:
            err = str(exc)
            logger.warning(f"[RetryQueue] 실패 | type={task_type} | id={tid} | attempt={attempts} | {err}")

            if attempts >= max_att:
                self._update(tid, attempts, "dead", err)
                logger.error(f"[RetryQueue] 최대 재시도 초과 → dead | type={task_type} | id={tid}")
            else:
                delay = _BACKOFF[min(attempts - 1, len(_BACKOFF) - 1)]
                next_retry = (datetime.utcnow() + timedelta(seconds=delay)).strftime("%Y-%m-%d %H:%M:%S")
                with self._lock:
                    self._conn.execute(
                        "UPDATE retry_tasks SET attempts=?, next_retry=?, last_error=? WHERE id=?",
                        (attempts, next_retry, err, tid),
                    )
                    self._conn.commit()
                logger.info(f"[RetryQueue] {delay}초 후 재시도 예약 | id={tid}")

    def _update(self, tid: int, attempts: int, status: str, error: str | None) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE retry_tasks SET attempts=?, status=?, last_error=? WHERE id=?",
                (attempts, status, error, tid),
            )
            self._conn.commit()

    # ── 상태 조회 ─────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """pending / done / dead 건수 반환."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM retry_tasks GROUP BY status"
            ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}


# ── 싱글턴 ───────────────────────────────────────────────────────────────────
_instance: RetryQueue | None = None

def get_retry_queue() -> RetryQueue:
    """프로세스 내 싱글턴 RetryQueue 반환."""
    global _instance
    if _instance is None:
        _instance = RetryQueue()
    return _instance
