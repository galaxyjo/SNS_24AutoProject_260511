"""
health_monitor.py — 시스템 상태 수집기

사용법:
    from modules.common.health_monitor import get_health

    snapshot = get_health()
    # {
    #   "timestamp": "2026-05-13 10:00:00",
    #   "services": {"flask": "ok", "streamlit": "ok", "ngrok": "ok", "launcher": "ok"},
    #   "retry_queue": {"pending": 0, "done": 12, "dead": 1},
    #   "errors": {"last_1h": 3, "recent": ["...", ...]},
    #   "overall": "ok"   # "ok" | "degraded" | "down"
    # }
"""

import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from modules.common.logger import get_logger

logger = get_logger(__name__)

# ── 경로 ──────────────────────────────────────────────────────────────────────
_ROOT        = Path(__file__).resolve().parents[2]
_ERROR_LOG   = _ROOT / "logs" / "error" / "error.log"
_RQ_DB       = _ROOT / "db" / "retry_queue.db"
_WATCHDOG_LOG = _ROOT / "logs" / "watchdog.log"

# ── 엔드포인트 ────────────────────────────────────────────────────────────────
_FLASK_URL      = "http://localhost:5000/health"
_STREAMLIT_URL  = "http://localhost:8501"
_HTTP_TIMEOUT   = 4
_WATCHDOG_STALE_SEC = 90  # 마지막 로그 이후 이 시간(초)을 넘으면 비정상 판정


# ── 개별 체크 함수 ────────────────────────────────────────────────────────────

def _check_http(url: str) -> str:
    try:
        r = requests.get(url, timeout=_HTTP_TIMEOUT)
        return "ok" if r.status_code < 500 else "error"
    except Exception:
        return "down"


def _check_process(keyword: str) -> str:
    """WMI 없이 tasklist 출력으로 프로세스 커맨드라인 검색."""
    try:
        out = subprocess.check_output(
            ["tasklist", "/FO", "CSV", "/NH"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        if keyword == "ngrok":
            return "ok" if "ngrok" in out.lower() else "down"

        # python 프로세스 커맨드라인 확인 (PowerShell Get-WmiObject, wmic 대체)
        ps_out = subprocess.check_output(
            [
                "powershell", "-NoProfile", "-Command",
                "Get-WmiObject Win32_Process -Filter \"Name='python.exe'\" | Select-Object -ExpandProperty CommandLine",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        return "ok" if keyword in ps_out else "down"
    except Exception:
        return "unknown"


def _check_retry_queue() -> dict:
    if not _RQ_DB.exists():
        return {}
    try:
        conn = sqlite3.connect(_RQ_DB)
        rows = conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM retry_tasks GROUP BY status"
        ).fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def _check_errors(window_minutes: int = 60, tail: int = 5) -> dict:
    if not _ERROR_LOG.exists():
        return {"last_1h": 0, "recent": []}
    try:
        lines = _ERROR_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        recent_errors = []
        count_1h = 0
        for line in reversed(lines):
            # 로그 포맷: "2026-05-13 10:00:00 [ERROR] ..."
            try:
                ts = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
                if ts >= cutoff:
                    count_1h += 1
                    if len(recent_errors) < tail:
                        recent_errors.append(line)
            except ValueError:
                continue
        return {"last_1h": count_1h, "recent": list(reversed(recent_errors))}
    except Exception:
        return {"last_1h": 0, "recent": []}


def _check_watchdog() -> dict:
    """logs/watchdog.log 마지막 줄 타임스탬프로 watchdog.ps1 생존 여부를 판정한다."""
    if not _WATCHDOG_LOG.exists():
        return {"status": "unknown", "last_heartbeat": None, "elapsed_sec": None}
    try:
        lines = _WATCHDOG_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        if not lines:
            return {"status": "unknown", "last_heartbeat": None, "elapsed_sec": None}
        # 로그 포맷: "[2026-07-09 17:16:32] [HEARTBEAT] alive"
        ts = datetime.strptime(lines[-1][1:20], "%Y-%m-%d %H:%M:%S")
        elapsed = (datetime.now() - ts).total_seconds()
        status = "ok" if elapsed <= _WATCHDOG_STALE_SEC else "down"
        return {
            "status": status,
            "last_heartbeat": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_sec": int(elapsed),
        }
    except Exception:
        return {"status": "unknown", "last_heartbeat": None, "elapsed_sec": None}


# ── 통합 헬스 스냅샷 ──────────────────────────────────────────────────────────

def get_health() -> dict[str, Any]:
    """전체 시스템 헬스 스냅샷을 반환한다."""
    services = {
        "flask":           _check_http(_FLASK_URL),
        "streamlit":       _check_http(_STREAMLIT_URL),
        "ngrok":           _check_process("ngrok"),
        "launcher":        _check_process("launcher\\main"),
    }

    retry_stats = _check_retry_queue()
    error_stats = _check_errors()

    # FB 크롤링 URL 마지막 체크 결과 (check_all() 잡이 주기적으로 갱신)
    try:
        from modules.common.crawl_url_checker import get_last_results
        crawl_url_stats = get_last_results()
    except Exception:
        crawl_url_stats = {}

    # overall 상태 결정
    down_count = sum(1 for v in services.values() if v == "down")
    url_problem = any(v != "ok" for v in crawl_url_stats.values())
    if down_count == 0 and not url_problem:
        overall = "ok"
    elif down_count <= 1:
        overall = "degraded"
    else:
        overall = "down"

    snapshot = {
        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "services":    services,
        "retry_queue": retry_stats,
        "errors":      error_stats,
        "crawl_urls":  crawl_url_stats,
        "overall":     overall,
    }

    logger.debug(f"[HealthMonitor] overall={overall} | services={services}")
    return snapshot


def get_watchdog_status() -> dict[str, Any]:
    """watchdog.ps1 생존 상태 스냅샷을 반환한다 (get_health()의 4개 서비스 카드와 별개)."""
    return _check_watchdog()


def print_health() -> None:
    """콘솔에 헬스 상태를 보기 좋게 출력한다."""
    s = get_health()
    print(f"\n{'='*50}")
    print(f"  시스템 상태 ({s['timestamp']})  overall: {s['overall'].upper()}")
    print(f"{'='*50}")
    for name, status in s["services"].items():
        icon = "✓" if status == "ok" else ("!" if status == "degraded" else "✗")
        print(f"  [{icon}] {name:<20} {status}")
    rq = s["retry_queue"]
    if rq:
        print(f"\n  retry_queue  pending={rq.get('pending',0)}  done={rq.get('done',0)}  dead={rq.get('dead',0)}")
    err = s["errors"]
    print(f"  errors(1h)   {err.get('last_1h', 0)}건")
    if err.get("recent"):
        print("  --- 최근 에러 ---")
        for line in err["recent"]:
            print(f"  {line}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    print_health()
