# modules/comment/comment_poll_targets.py
# 댓글 감시 대상(media_id) 상태머신 — FP-047 Package 1 Phase A (260715)
#
# 목적: "캠페인 게시물 목록(JSON)"과 "실제로 실시간 처리를 흘려도 되는 상태"를 분리한다.
#   - configs/comment_campaign_posts.json = 운영자 의도(이 게시물은 캠페인이다)
#   - comment_poll_targets.state          = baseline/cutover 검증까지 끝난 실제 활성 상태
# 두 계층을 분리하는 이유: JSON에 media를 추가한 순간 곧바로 실시간 처리를 흘리면,
# 그 게시물에 이미 달려있던 과거 댓글들이 전부 "신규"로 오인되어 실제 고객에게
# 대량 DM이 나가는 사고가 난다(260715 Codex 5차 리뷰). 반드시 baseline CLI가
# media별로 안전을 확인(--verify)하고 --activate해야만 ACTIVE로 전이한다.
#
# 상태:
#   PENDING_BASELINE — JSON엔 있지만 아직 baseline 검증 전(또는 재검증 필요). 실시간
#                       처리 대상에서 제외.
#   ACTIVE           — baseline 검증 완료 + CLI로 명시적 activate됨. 실시간 처리 대상.
#   PAUSED           — JSON에서 제거됨(캠페인 종료 등). 실시간 처리 대상에서 제외.
#                       재등록되면 PENDING_BASELINE으로 돌아가 재검증을 강제한다 —
#                       중단 기간 동안의 댓글을 놓쳤을 수 있어 안전하게 다시 확인한다.
#   INVALID          — 자동 전이 대상에서 제외(수동 CLI 개입 필요). 이번 Phase A
#                       범위에서는 코드에서 이 상태로 자동 전이시키지 않는다(예약만).
#
# state 컬럼은 sync_from_campaign_json()과 baseline CLI(apply_baseline/verify_baseline/
# activate)만 변경한다 — 수동 DB 편집 금지(260715 Codex 5차 리뷰 명시 요구사항).

import hashlib
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from modules.common.logger import get_logger
from modules.comment.comment_campaign_config import CampaignConfigError, load_campaign_media_ids

logger = get_logger(__name__)

_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "comment_events.db"
_LOCK = threading.Lock()

VALID_STATES = ("PENDING_BASELINE", "ACTIVE", "PAUSED", "INVALID")


def is_allowlist_gating_enabled() -> bool:
    """260715 Codex 6차 리뷰 P0-1/P0-2 — Phase A 코드가 배포(재시작)돼도 이 플래그가
    기본값(legacy)인 한 실시간 처리 경로·poller 감시 대상이 전혀 바뀌지 않는다.
    comment_poll_targets가 완전히 준비(baseline+activate)되기 전에 이 코드가 우연히
    배포돼도 댓글 감시가 통째로 멈추거나(poller) 검증 안 된 media가 webhook으로
    실제 발송되는(entry point) 사고를 막는 단일 kill switch.
    이 플래그를 'allowlist'로 바꾸는 것 자체가 상태변경이라 별도 승인 대상."""
    raw = os.getenv("COMMENT_POLL_ALLOWLIST_MODE", "legacy").strip().lower()
    if raw not in ("legacy", "allowlist"):
        logger.warning(f"[PollTargets] COMMENT_POLL_ALLOWLIST_MODE 값이 유효하지 않음(legacy로 폴백) | value={raw!r}")
        return False
    return raw == "allowlist"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS comment_poll_targets (
            media_id                TEXT PRIMARY KEY,
            state                   TEXT NOT NULL DEFAULT 'PENDING_BASELINE',
            cutover_at              TEXT,
            baseline_comment_count  INTEGER,
            baseline_source_hash    TEXT,
            baseline_applied_at     TEXT,
            baseline_verified_at    TEXT,
            campaign_config_hash    TEXT,
            baseline_config_hash    TEXT,
            last_success_at         TEXT,
            consecutive_failures    INTEGER NOT NULL DEFAULT 0,
            last_alerted_at         TEXT,
            updated_at              TEXT NOT NULL
        )
    """)
    conn.commit()


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


_conn: sqlite3.Connection | None = None


def _c() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _get_conn()
    return _conn


# ── JSON ↔ DB 동기화 ─────────────────────────────────────────────────────────

def sync_from_campaign_json() -> bool:
    """캠페인 JSON을 읽어 poll_targets 상태를 동기화한다. 폴링 주기마다 호출.
    반환값: True=동기화 정상 수행. False=JSON 손상으로 이번 주기 스킵(fail-closed,
    테이블은 손대지 않음 — 손상된 상태를 근거로 기존 ACTIVE를 잘못 PAUSED시키지 않기
    위함. 대신 poller가 이번 주기 전체를 건너뛰어야 한다)."""
    try:
        media_ids = load_campaign_media_ids()
    except CampaignConfigError as exc:
        logger.error(f"[PollTargets] 캠페인 설정 손상/소실 — 동기화 생략(fail-closed) | {exc}")
        return False

    campaign_set = set(media_ids)
    # 260715 Codex 6차 리뷰 P0-3: 캠페인 JSON 전체 내용의 해시 — media 하나의
    # 존재 여부와 무관하게 목록 자체가 apply~verify 사이에 바뀌었는지 감지하는 용도.
    config_hash = hashlib.sha256(",".join(sorted(media_ids)).encode("utf-8")).hexdigest()
    now = _now_iso()
    with _LOCK:
        rows = _c().execute("SELECT media_id, state FROM comment_poll_targets").fetchall()
        existing = {r["media_id"]: r["state"] for r in rows}

        for mid in campaign_set - existing.keys():
            _c().execute(
                "INSERT INTO comment_poll_targets (media_id, state, campaign_config_hash, updated_at) VALUES (?, 'PENDING_BASELINE', ?, ?)",
                (mid, config_hash, now),
            )
            logger.info(f"[PollTargets] 신규 캠페인 media 등록(PENDING_BASELINE) | media={mid}")

        for mid in existing.keys() - campaign_set:
            if existing[mid] not in ("PAUSED", "INVALID"):
                _c().execute(
                    "UPDATE comment_poll_targets SET state='PAUSED', updated_at=? WHERE media_id=?",
                    (now, mid),
                )
                logger.warning(f"[PollTargets] 캠페인 목록에서 제거됨 — PAUSED 처리 | media={mid} (이전 상태={existing[mid]})")

        for mid in campaign_set & existing.keys():
            if existing[mid] == "PAUSED":
                _c().execute(
                    """UPDATE comment_poll_targets
                       SET state='PENDING_BASELINE', cutover_at=NULL, baseline_comment_count=NULL,
                           baseline_source_hash=NULL, baseline_applied_at=NULL, baseline_verified_at=NULL,
                           baseline_config_hash=NULL, campaign_config_hash=?, updated_at=?
                       WHERE media_id=?""",
                    (config_hash, now, mid),
                )
                logger.warning(f"[PollTargets] 재등록됨 — baseline 초기화 후 재검증 필요(PENDING_BASELINE) | media={mid}")
            else:
                _c().execute(
                    "UPDATE comment_poll_targets SET campaign_config_hash=?, updated_at=? WHERE media_id=?",
                    (config_hash, now, mid),
                )

        _c().commit()
    return True


# ── 조회 ─────────────────────────────────────────────────────────────────────

def get_active_media_ids() -> list[str]:
    with _LOCK:
        rows = _c().execute("SELECT media_id FROM comment_poll_targets WHERE state='ACTIVE'").fetchall()
    return [r["media_id"] for r in rows]


def get_target(media_id: str) -> dict | None:
    with _LOCK:
        row = _c().execute(
            "SELECT * FROM comment_poll_targets WHERE media_id=?", (media_id,)
        ).fetchone()
    return dict(row) if row else None


# ── 폴링 성공/실패 집계 ────────────────────────────────────────────────────────

def record_poll_success(media_id: str) -> None:
    """260715 Codex 6차 리뷰 P1: last_alerted_at도 함께 리셋해야 한다 — 안 그러면
    최초 실패 스트릭에서 한 번 알림이 나간 뒤, 복구→재실패하는 새로운 스트릭에서는
    last_alerted_at이 계속 남아있어 영원히 재알림이 안 가는 버그가 생긴다."""
    now = _now_iso()
    with _LOCK:
        _c().execute(
            "UPDATE comment_poll_targets SET last_success_at=?, consecutive_failures=0, last_alerted_at=NULL, updated_at=? WHERE media_id=?",
            (now, now, media_id),
        )
        _c().commit()


def record_poll_failure(media_id: str) -> int:
    """실패 시 consecutive_failures 증가, 증가 후 값을 반환(호출부가 알림 임계치 판단)."""
    now = _now_iso()
    with _LOCK:
        _c().execute(
            "UPDATE comment_poll_targets SET consecutive_failures=consecutive_failures+1, updated_at=? WHERE media_id=?",
            (now, media_id),
        )
        _c().commit()
        row = _c().execute(
            "SELECT consecutive_failures FROM comment_poll_targets WHERE media_id=?", (media_id,)
        ).fetchone()
    return row["consecutive_failures"] if row else 0


def mark_alerted(media_id: str) -> None:
    with _LOCK:
        _c().execute(
            "UPDATE comment_poll_targets SET last_alerted_at=? WHERE media_id=?",
            (_now_iso(), media_id),
        )
        _c().commit()


# ── baseline CLI 전용(tools/comment_campaign_baseline_cli.py만 호출) ──────────

def apply_baseline(media_id: str, cutover_at_iso: str, comment_count: int, source_hash: str) -> bool:
    """--apply 단계: baseline 메타데이터 기록. state는 PENDING_BASELINE 그대로 유지
    (verify/activate를 거치지 않고는 절대 ACTIVE가 될 수 없음).
    media_id가 poll_targets에 없으면(sync 전 CLI를 먼저 돌린 경우 등) False.

    260715 Codex 6차 리뷰 P1: 이 호출 자체와 그 앞의 event_store.suppress_pre_cutover()
    반복 호출들은 하나의 DB 트랜잭션으로 묶여있지 않다(각자 자체 commit) — "all-or-
    nothing"이 아니라 "resumable/idempotent"가 정확한 설명이다. CLI가 중간에
    죽어도 suppress_pre_cutover()는 INSERT OR IGNORE라 재실행 시 이미 처리된 comment_id는
    조용히 스킵되고 나머지만 이어서 처리되므로, --apply를 그냥 다시 실행하면 항상
    일관된 최종 상태로 수렴한다(단일 트랜잭션은 아니지만 안전)."""
    now = _now_iso()
    with _LOCK:
        row = _c().execute(
            "SELECT campaign_config_hash FROM comment_poll_targets WHERE media_id=? AND state='PENDING_BASELINE'",
            (media_id,),
        ).fetchone()
        if not row:
            return False
        cur = _c().execute(
            """UPDATE comment_poll_targets
               SET cutover_at=?, baseline_comment_count=?, baseline_source_hash=?,
                   baseline_applied_at=?, baseline_verified_at=NULL, baseline_config_hash=?, updated_at=?
               WHERE media_id=? AND state='PENDING_BASELINE'""",
            (cutover_at_iso, comment_count, source_hash, now, row["campaign_config_hash"], now, media_id),
        )
        _c().commit()
        return cur.rowcount == 1


def verify_baseline(media_id: str) -> bool:
    """--verify 단계: 호출부(CLI)가 8개 계약 항목(campaign_config_hash 드리프트 포함)을
    모두 확인한 뒤에만 호출해야 한다 — 이 함수 자체는 "검증 통과했다"는 사실만
    기록한다(재검증 로직은 CLI에 있음).
    baseline_applied_at이 없으면(apply를 안 거쳤으면) False."""
    now = _now_iso()
    with _LOCK:
        cur = _c().execute(
            """UPDATE comment_poll_targets SET baseline_verified_at=?, updated_at=?
               WHERE media_id=? AND state='PENDING_BASELINE' AND baseline_applied_at IS NOT NULL""",
            (now, now, media_id),
        )
        _c().commit()
        return cur.rowcount == 1


def activate(media_id: str) -> bool:
    """--activate: baseline_verified_at이 기록돼 있어야만 ACTIVE로 전이.
    이게 이 상태머신에서 ACTIVE를 만드는 유일한 경로다.

    260716 Codex 7차 리뷰 P1: verify가 통과한 뒤 activate를 부르기 전 사이에
    캠페인 JSON이 바뀌었을 수 있다(verify_baseline()은 그 순간의 스냅샷만 확인) —
    activate 시점에 campaign_config_hash를 다시 대조해, 그 사이 드리프트가 있으면
    거부한다(재-verify 필요)."""
    now = _now_iso()
    with _LOCK:
        row = _c().execute(
            "SELECT state, baseline_verified_at, campaign_config_hash, baseline_config_hash FROM comment_poll_targets WHERE media_id=?",
            (media_id,),
        ).fetchone()
        if not row or row["state"] != "PENDING_BASELINE" or not row["baseline_verified_at"]:
            return False
        if row["campaign_config_hash"] != row["baseline_config_hash"]:
            logger.error(f"[PollTargets] activate 거부: verify 이후 캠페인 설정이 바뀜(재-verify 필요) | media={media_id}")
            return False
        _c().execute(
            "UPDATE comment_poll_targets SET state='ACTIVE', updated_at=? WHERE media_id=?",
            (now, media_id),
        )
        _c().commit()
    return True
