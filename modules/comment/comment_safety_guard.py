# modules/comment/comment_safety_guard.py
# 댓글 Private Reply 안전장치 — 캠페인 게시물 한정 + 사용자별 쿨다운 + 일일 예산 + circuit breaker
# 목적: 탐지 회피가 아니라 공식 API 요청빈도를 스스로 제한해 정상 트래픽 패턴을 유지하는 것

import json as _json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"

_CAMPAIGN_CONFIG_PATH = _CONFIG_DIR / "comment_campaign_posts.json"
_COOLDOWN_STATE_PATH = _DATA_DIR / "comment_reply_cooldown.json"
_BUDGET_STATE_PATH = _DATA_DIR / "comment_reply_budget.json"

# 댓글 웹훅(Flask 요청 스레드)과 comment_poller(APScheduler 스레드)가 같은 프로세스 안에서
# 동시에 게이트 체크+소비를 할 수 있어(TOCTOU) 호출부가 이 락으로 전체 시퀀스를 감싸야 한다.
# Gate C의 threading.Lock 기반 원자적 중복방지와 동일 패턴(SQLite 도입 없이 인프로세스 락으로 해결).
REPLY_LOCK = threading.Lock()

COOLDOWN_HOURS = float(os.getenv("COMMENT_REPLY_COOLDOWN_HOURS", "24"))
DAILY_BUDGET = int(os.getenv("COMMENT_REPLY_DAILY_BUDGET", "30"))
CIRCUIT_FAILURE_THRESHOLD = int(os.getenv("COMMENT_REPLY_CIRCUIT_THRESHOLD", "3"))
CIRCUIT_COOLDOWN_MINUTES = float(os.getenv("COMMENT_REPLY_CIRCUIT_COOLDOWN_MINUTES", "30"))


class _StateCorrupted(Exception):
    """상태 파일이 존재하는데 파싱이 안 됨 — fail-closed(발송 차단) 강제 대상."""


def _load_json(path: Path) -> dict:
    """파일이 없으면 빈 dict(정상, 첫 실행). 파일이 있는데 손상됐으면 예외를 던져 호출부가 fail-closed 처리하게 한다."""
    if not path.exists():
        return {}
    try:
        return _json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise _StateCorrupted(f"{path} 파싱 실패: {exc}") from exc


def _save_json(path: Path, data: dict) -> None:
    """임시 파일에 쓴 뒤 원자적으로 교체(os.replace) — 크래시/동시쓰기 중간 상태로 인한 파일 손상을 줄인다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(_json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


# ── 캠페인 게시물 allowlist ──────────────────────────────────────────

def is_campaign_post(media_id: str) -> bool:
    """configs/comment_campaign_posts.json에 등록된 media_id만 자동응답 대상.
    파일 없음(첫 실행)은 전부 차단(안전기본값). 파일이 손상됐어도 fail-closed(전부 차단)."""
    if not media_id:
        return False
    try:
        data = _load_json(_CAMPAIGN_CONFIG_PATH)
    except _StateCorrupted:
        return False
    return media_id in set(data.get("media_ids", []))


# ── 사용자별 쿨다운 ───────────────────────────────────────────────────

def is_user_in_cooldown(username: str) -> bool:
    if not username:
        return False
    try:
        state = _load_json(_COOLDOWN_STATE_PATH)
    except _StateCorrupted:
        return True  # fail-closed: 상태를 못 믿으면 쿨다운 중인 것으로 간주해 발송 차단
    last_iso = state.get(username)
    if not last_iso:
        return False
    try:
        last = datetime.fromisoformat(last_iso)
    except ValueError:
        return True  # fail-closed
    elapsed_hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
    return elapsed_hours < COOLDOWN_HOURS


def mark_user_replied(username: str) -> None:
    if not username:
        return
    try:
        state = _load_json(_COOLDOWN_STATE_PATH)
    except _StateCorrupted:
        state = {}
    state[username] = datetime.now(timezone.utc).isoformat()
    _save_json(_COOLDOWN_STATE_PATH, state)


# ── 일일 예산 ─────────────────────────────────────────────────────────

def consume_daily_budget() -> bool:
    """오늘(UTC) 예산이 남아있으면 1건 소비하고 True. 날짜가 바뀌면 이전 카운트는 자동 초기화(집계용이 아니라 속도제한용이므로 이력 보존 불필요).
    상태 파일이 손상되면 fail-closed(예산 소진으로 간주, 발송 차단)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        state = _load_json(_BUDGET_STATE_PATH)
    except _StateCorrupted:
        return False
    count = state.get(today, 0)
    if count >= DAILY_BUDGET:
        return False
    _save_json(_BUDGET_STATE_PATH, {today: count + 1})
    return True


# ── Circuit Breaker (프로세스 인메모리 — 재시작 시 초기화됨) ─────────────

_circuit_failure_count = 0
_circuit_open_until = 0.0


def circuit_is_open() -> bool:
    return time.time() < _circuit_open_until


def record_circuit_success() -> None:
    global _circuit_failure_count
    _circuit_failure_count = 0


def record_circuit_failure() -> None:
    global _circuit_failure_count, _circuit_open_until
    _circuit_failure_count += 1
    if _circuit_failure_count >= CIRCUIT_FAILURE_THRESHOLD:
        _circuit_open_until = time.time() + CIRCUIT_COOLDOWN_MINUTES * 60
