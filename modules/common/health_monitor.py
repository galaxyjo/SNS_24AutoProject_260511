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

import json
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
_BOOT_STATE_PATH = _ROOT / "db" / "launcher_boot_state.json"

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


# ── 260811 ERR-109 대응: Runtime 진입점 코드 신선도 확인 ──────────────────────
# 배경: launcher/main.py는 프로세스 시작 시점에 메모리에 고정된다 — 그 안의
# publish_single() 같은 최상위 함수는 이후 파일을 아무리 고쳐도 프로세스를
# 재시작하기 전까지 옛 코드로 계속 동작한다. 260810 Phase A.5 수정을 09:01
# 커밋했지만 프로세스가 05:56부터 떠 있었고 20:02까지 재시작이 없어, 그 사이
# 17:00 자동 슬롯이 옛(버그 있는) publish_single()로 다시 실패했다 — 이걸
# "실제로 반영됐는지" 확인할 방법이 없어서 그날 낮에는 아무도 몰랐다.
# (주의) 함수 내부에서 지역 import되는 다른 모듈(예: content_package_builder,
# caption_generator)은 이 프로세스 생애주기 중 "그 모듈이 처음 import되는
# 시점"의 디스크 상태를 따른다 — launcher/main.py 자체의 최상위 코드와는
# 신선도가 다를 수 있다(같은 프로세스 안에서도 모듈별로 엇갈릴 수 있음, 알려진
# 한계). 이 체크는 launcher/main.py 자기 자신의 신선도만 보장한다.


def record_boot_commit() -> None:
    """launcher/main.py의 main() 시작 시 1회 호출 — 그 시점의 git HEAD 커밋을
    db/launcher_boot_state.json에 기록한다. git 명령 실패(예: git 미설치 환경)
    시에도 조용히 넘어간다(Fail-open) — 이 기록 실패가 실제 서비스 기동을
    막으면 안 된다."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_ROOT, stderr=subprocess.DEVNULL, text=True, timeout=5,
        ).strip()
    except Exception:
        commit = ""
    try:
        _BOOT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _BOOT_STATE_PATH.write_text(
            json.dumps({
                "commit": commit,
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }),
            encoding="utf-8",
        )
    except Exception:
        pass


def _check_code_freshness() -> dict:
    if not _BOOT_STATE_PATH.exists():
        return {"status": "unknown", "boot_commit": None, "head_commit": None, "started_at": None}
    try:
        boot_state = json.loads(_BOOT_STATE_PATH.read_text(encoding="utf-8"))
        boot_commit = boot_state.get("commit") or ""
        head_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_ROOT, stderr=subprocess.DEVNULL, text=True, timeout=5,
        ).strip()
        if not boot_commit or not head_commit:
            return {
                "status": "unknown", "boot_commit": boot_commit or None,
                "head_commit": head_commit or None, "started_at": boot_state.get("started_at"),
            }
        status = "fresh" if boot_commit == head_commit else "stale"
        return {
            "status": status, "boot_commit": boot_commit, "head_commit": head_commit,
            "started_at": boot_state.get("started_at"),
        }
    except Exception:
        return {"status": "unknown", "boot_commit": None, "head_commit": None, "started_at": None}


def get_code_freshness_status() -> dict[str, Any]:
    """launcher/main.py 프로세스가 기동 당시 커밋 그대로인지("fresh"), 그 이후
    새 커밋이 생겼는지("stale") 반환한다. get_watchdog_status()와 별개 축이다
    — watchdog은 "프로세스가 살아있는가", 이건 "그 프로세스가 최신 코드를
    실행 중인가". "stale"이면 재시작이 필요하다는 뜻(주의: launcher/main.py
    자기 자신 기준, 위 모듈 설명 참조)."""
    return _check_code_freshness()


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
    freshness = get_code_freshness_status()
    fresh_icon = "✓" if freshness["status"] == "fresh" else ("!" if freshness["status"] == "stale" else "?")
    print(f"  [{fresh_icon}] {'code_freshness':<20} {freshness['status']}"
          f"{' — 재시작 필요' if freshness['status'] == 'stale' else ''}")
    if freshness["status"] == "stale":
        print(f"      boot={freshness['boot_commit'][:8] if freshness['boot_commit'] else '?'}"
              f" head={freshness['head_commit'][:8] if freshness['head_commit'] else '?'}"
              f" started_at={freshness['started_at']}")
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
