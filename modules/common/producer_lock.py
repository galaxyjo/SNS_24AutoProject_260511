"""modules/common/producer_lock.py — 260804 Track B 6G Producer 공용 Lock.

Scheduler Job(`_job_aijomoojin_content_producer`)과 수동 진입점
(`tools/run_aijomoojin_producer_manual.py` — 그 Job을 그대로 호출만 하므로
동일 Lock을 코드 구조상 자동 공유)이 동일 Lock을 공유해 동시 실행을 막는다
(회장 승인 조건 8-9). gitignore되는 구 `tools/_canary_260801_queue_aijomoojin_post_6f.py`
에 Lock을 붙이는 방식은 일반 Commit·clone에 배포되지 않는다는 이유로 폐기됐다
(260804 Codex 2차 리뷰) — 그 스크립트는 원상복구된 상태로 이 Lock 계약과 무관하다.

계약(회장 확정, 최소 구현):
  - owner-token 기반 — acquire()가 발급한 token으로만 release() 가능(다른 프로세스가
    실수로 남의 Lock을 풀지 못함).
  - 자동 만료 없음 — Lease/Heartbeat/TTL 전부 의도적으로 만들지 않는다. Crash로 Lock이
    풀리지 않으면 사람이 force_release()를 직접 실행해 수동 해제해야 한다.
  - 신규 Queue 아님 — 단일 행(row) 1개짜리 Mutex일 뿐, 재시도 순서·우선순위·복수
    대기자 개념이 없다. acquire() 실패 시 호출자는 즉시 스킵해야 한다(대기 없음).

REUSE 원칙: SQLite PRIMARY KEY + INSERT + IntegrityError로 원자적 선점하는 패턴은
modules/common/canary_execution_guard.py·publish_ledger.py가 이미 쓰는 것과 동일
Idiom이다 — 다만 그 두 모듈은 각각 Canary Safe Mode·Publish Dedup 전용이라 이번
목적(Producer 단일 실행 보장)에 직접 재사용할 수 없어, 같은 Idiom만 가져와 훨씬
작은 전용 모듈로 새로 만든다. publish_ledger.py(Step6B, ISOLATED_UNAPPROVED)와는
무관하다 — 재도입 아님, 별개의 훨씬 좁은 목적의 신규 유틸리티.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "producer_lock.db"
_LOCK_NAME = "aijomoojin_content_producer"

_SCHEMA = """
    CREATE TABLE IF NOT EXISTS producer_lock (
        lock_name    TEXT PRIMARY KEY,
        owner_token  TEXT NOT NULL,
        acquired_at  TEXT NOT NULL
    )
"""


def _connect(db_path: "Path | None" = None) -> sqlite3.Connection:
    path = db_path or _DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5)
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def new_owner_token() -> str:
    return uuid.uuid4().hex


def acquire(owner_token: str, *, db_path: "Path | None" = None) -> bool:
    """Lock을 원자적으로 선점한다. 이미 다른 owner가 보유 중이면 False(대기·재시도
    없음 — 호출자가 즉시 스킵해야 한다). 자동 만료가 없으므로, 이미 이 Lock이
    걸려 있다는 건 "다른 실행이 아직 끝나지 않았거나 비정상 종료로 안 풀렸다"는
    뜻이며 둘 다 사람 확인이 우선이다."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        try:
            conn.execute(
                "INSERT INTO producer_lock (lock_name, owner_token, acquired_at) VALUES (?, ?, ?)",
                (_LOCK_NAME, owner_token, now),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return False
    return True


def release(owner_token: str, *, db_path: "Path | None" = None) -> bool:
    """owner_token이 실제 보유자와 일치할 때만 해제한다(다른 프로세스의 Lock을
    실수로 풀지 못하게). 일치하지 않거나 애초에 안 걸려 있으면 False."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM producer_lock WHERE lock_name = ? AND owner_token = ?",
            (_LOCK_NAME, owner_token),
        )
        conn.commit()
        return cursor.rowcount == 1


def get_holder(*, db_path: "Path | None" = None) -> "dict | None":
    """진짜 Read-only — 현재 Lock을 누가 갖고 있는지 확인(사람이 수동 해제 판단할
    때 사용). 260804 Codex 4차 리뷰 지적 — 이전엔 `_connect()`를 거쳐 디렉터리·
    DB 파일·테이블을 없으면 만들어버렸다(mkdir + CREATE TABLE + commit) — "Read-only
    점검 도구"라는 이름과 달리 실제로는 쓰기 동작이었다. 이제 DB 파일이 없으면
    아무것도 만들지 않고 즉시 None을 반환하고, 있을 때는 SQLite `mode=ro` URI로
    열어 물리적으로 쓰기가 불가능한 연결로만 조회한다."""
    path = db_path or _DB_PATH
    if not path.exists():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    try:
        row = conn.execute(
            "SELECT owner_token, acquired_at FROM producer_lock WHERE lock_name = ?",
            (_LOCK_NAME,),
        ).fetchone()
    except sqlite3.OperationalError:
        # 파일은 있으나 테이블이 아직 없는 극단적 경우 — Lock 없음과 동일 취급.
        return None
    finally:
        conn.close()
    return {"owner_token": row[0], "acquired_at": row[1]} if row else None


def force_release(*, db_path: "Path | None" = None) -> bool:
    """사람이 수동으로 강제 해제할 때만 사용한다(owner_token 불문). 코드 경로
    (Producer Job/수동 스크립트)는 이 함수를 호출하지 않는다 — 운영자가 직접
    실행해야 하는 사람 개입 전용 함수(Lease/Heartbeat 자동 해제 대체 아님)."""
    with _connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM producer_lock WHERE lock_name = ?", (_LOCK_NAME,))
        conn.commit()
        return cursor.rowcount == 1
