"""
tools/heartbeat_monitor.py — watchdog.ps1과 완전히 독립된 heartbeat 정지 감지기

목적:
    watchdog.ps1(및 watchdog_task_wrapper.ps1)이 죽으면 그 자신도 감시를 멈추므로
    "감시 주체 자체가 죽었는지"를 알 방법이 없었던 문제(ERR-047/ERR-050/ERR-051/INC-028에서
    반복 재발)에 대응하기 위한 별도 감시 계층. watchdog.ps1의 프로세스/PID 파일/함수 어느
    것도 import하거나 의존하지 않고, logs/watchdog.log 파일 자체만 읽어 마지막 heartbeat로
    부터의 경과 시간만으로 판정한다.

실행:
    python tools/heartbeat_monitor.py

로컬 로그:
    logs/heartbeat_monitor.log       — 매 실행마다 판정 결과(정상/경보) 1줄 기록
    logs/heartbeat_monitor_state.txt — 마지막 Slack 알림 발송(시도) epoch 시각 (재알림 억제용)

참고: 이 파일은 작성만 된 상태이며, 아직 실행되거나 Task Scheduler에 등록되지 않았다.
      기존 SNS_Watchdog_AutoStart Task는 이 스크립트와 무관하며 변경되지 않는다.
"""

import sys
from datetime import datetime
from pathlib import Path

# Task Scheduler 등 독립 실행 환경에서 상대경로 탐색이 실패한 이력(ERR-029/ERR-036/FP-026)이
# 있어 프로젝트 루트를 절대경로로 고정한다.
_ROOT = Path(r"C:\SNS_24AutoProject_260511")

_LOCAL_LOG = _ROOT / "logs" / "heartbeat_monitor.log"


# ── 로컬 로그 (이 스크립트 자체가 죽어도 이 함수만은 최대한 살아남아야 함) ────────

def _local_log(level: str, msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}"
    try:
        _LOCAL_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOCAL_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # 로컬 로그 기록조차 실패하면 최후 수단으로 stderr에만 남긴다.
        try:
            print(line, file=sys.stderr)
        except Exception:
            pass


# ── 초기화 (dotenv / slack_notifier import) — 실패해도 스크립트는 죽지 않아야 함 ──

send_alert = None
try:
    sys.path.insert(0, str(_ROOT))

    from dotenv import load_dotenv
    load_dotenv(dotenv_path=r"C:\SNS_24AutoProject_260511\.env", override=True)

    from services.slack_notifier import send_alert  # noqa: F811 (위 None 초기값을 의도적으로 덮어씀)
except Exception as exc:
    _local_log("FATAL", f"초기화 실패(dotenv 로드 또는 services.slack_notifier import) — {exc}")
    send_alert = None


# ── 설정 ──────────────────────────────────────────────────────────────────────

_WATCHDOG_LOG = _ROOT / "logs" / "watchdog.log"
_STATE_FILE = _ROOT / "logs" / "heartbeat_monitor_state.txt"

# watchdog 정상 주기 30초의 6배. CLAUDE.md get_watchdog_status()의 90초 기준보다
# 여유 있게 잡아 일시적 지연/스케줄 지터로 인한 오탐을 줄인다. 필요시 조정 가능.
_STALE_THRESHOLD_SEC = 180

# 같은 "죽어있음" 상태에 대해 매 실행마다 반복 알림을 보내지 않기 위한 최소 재알림 간격.
# 필요시 조정 가능.
_REALERT_SUPPRESS_SEC = 1800  # 30분


# ── watchdog.log 마지막 heartbeat 시각 판정 ───────────────────────────────────

def _get_last_heartbeat() -> tuple[datetime | None, str]:
    """
    watchdog.log 마지막 줄의 타임스탬프를 파싱한다. 파싱 실패 시 파일 mtime으로 폴백한다.
    반환: (datetime 또는 None, 판정 방식 문자열)
    """
    if not _WATCHDOG_LOG.exists():
        return None, "file_missing"

    try:
        lines = _WATCHDOG_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        if lines:
            # 로그 포맷: "[2026-07-09 17:16:32] [HEARTBEAT] alive"
            try:
                ts = datetime.strptime(lines[-1][1:20], "%Y-%m-%d %H:%M:%S")
                return ts, "parsed_last_line"
            except Exception:
                pass
    except Exception:
        pass

    # 마지막 줄 파싱 실패(빈 파일/포맷 불일치 등) — mtime으로 폴백
    try:
        mtime = _WATCHDOG_LOG.stat().st_mtime
        return datetime.fromtimestamp(mtime), "mtime_fallback"
    except Exception:
        return None, "mtime_failed"


# ── 재알림 억제 상태 저장/조회 ─────────────────────────────────────────────────

def _load_last_alert_epoch() -> float:
    try:
        if _STATE_FILE.exists():
            return float(_STATE_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        pass
    return 0.0


def _save_last_alert_epoch(epoch: float) -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(str(epoch), encoding="utf-8")
    except Exception as exc:
        _local_log("ERROR", f"재알림 억제 상태 파일 저장 실패 — {exc}")


# ── 메인 판정 로직 ─────────────────────────────────────────────────────────────

def check_heartbeat() -> None:
    last_ts, method = _get_last_heartbeat()
    elapsed = None if last_ts is None else (datetime.now() - last_ts).total_seconds()
    is_down = (last_ts is None) or (elapsed > _STALE_THRESHOLD_SEC)

    if not is_down:
        _local_log(
            "OK",
            f"정상 — last_heartbeat={last_ts.strftime('%Y-%m-%d %H:%M:%S')} "
            f"elapsed={int(elapsed)}s (threshold={_STALE_THRESHOLD_SEC}s, method={method})",
        )
        return

    # ── 경보 상태 ──
    last_hb_str = "없음" if last_ts is None else last_ts.strftime("%Y-%m-%d %H:%M:%S")
    elapsed_str = "N/A" if elapsed is None else f"{int(elapsed)}s"

    now_epoch = datetime.now().timestamp()
    last_alert_epoch = _load_last_alert_epoch()
    since_last_alert = now_epoch - last_alert_epoch

    if since_last_alert < _REALERT_SUPPRESS_SEC:
        _local_log(
            "ALERT-SUPPRESSED",
            f"경보 상태 지속(재알림 억제 중) — last_heartbeat={last_hb_str} elapsed={elapsed_str} "
            f"마지막 알림 {int(since_last_alert)}s 전(억제 임계 {_REALERT_SUPPRESS_SEC}s)",
        )
        return

    if send_alert is None:
        # 초기화 단계에서 dotenv/slack_notifier import 자체가 실패한 경우 — 알림 시도 없이
        # 로컬 로그만 남긴다(Slack 발송 실패와 동일하게 취급, 재알림 억제 타임스탬프도 갱신).
        _save_last_alert_epoch(now_epoch)
        _local_log(
            "ALERT",
            f"경보 발송 불가(초기화 실패로 send_alert 사용 불가) — last_heartbeat={last_hb_str} "
            f"elapsed={elapsed_str} threshold={_STALE_THRESHOLD_SEC}s — 본 로컬 로그가 유일한 기록임",
        )
        return

    detail = (
        f"watchdog.log 마지막 heartbeat: {last_hb_str}\n"
        f"경과 시간: {elapsed_str} (임계치 {_STALE_THRESHOLD_SEC}초)\n"
        f"판정 방식: {method}\n"
        f"※ 본 알림은 watchdog.ps1과 독립된 heartbeat_monitor.py에서 발송됨 — "
        f"watchdog.ps1 자체가 죽어 있어도 이 알림은 별도로 동작함"
    )

    sent = False
    try:
        sent = send_alert(
            title="[Heartbeat Monitor] watchdog.log 정지 감지",
            body=detail,
            level="error",
        )
    except Exception as exc:
        _local_log("ERROR", f"send_alert() 호출 중 예외 발생 — {exc}")
        sent = False

    _save_last_alert_epoch(now_epoch)

    if sent:
        _local_log(
            "ALERT",
            f"경보 발송 성공 — elapsed={elapsed_str}, threshold={_STALE_THRESHOLD_SEC}s",
        )
    else:
        # send_alert() 반환값이 False(또는 예외)면 로컬 로그만이 유일한 기록이 되므로 반드시 남긴다.
        _local_log(
            "ALERT",
            f"경보 발송 실패(Slack 미수신) — elapsed={elapsed_str}, "
            f"threshold={_STALE_THRESHOLD_SEC}s — 본 로컬 로그가 유일한 기록임",
        )


def main() -> None:
    # 이 스크립트 자체가 죽어서 감시가 끊기면 안 되므로 전체를 try/except로 감싼다.
    try:
        check_heartbeat()
    except Exception as exc:
        _local_log("FATAL", f"heartbeat_monitor 자체 예외 발생 — {exc}")


if __name__ == "__main__":
    main()
