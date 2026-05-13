"""
modules/common/ngrok_monitor.py — ngrok 터널 URL 변경 감지

ngrok 로컬 API(localhost:4040)를 폴링해 URL 변경·오프라인을 감지하고
Slack으로 알림을 보낸다.

사용법:
    from modules.common.ngrok_monitor import check_ngrok_url
    check_ngrok_url()   # 스케줄러 잡에서 주기적으로 호출
"""

import json
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

from modules.common.logger import get_logger

logger = get_logger(__name__)

_NGROK_API    = "http://localhost:4040/api/tunnels"
_STATE_FILE   = Path(__file__).resolve().parents[2] / "db" / "ngrok_url.json"
_HTTP_TIMEOUT = 3


def get_current_tunnel_url() -> str | None:
    """ngrok 로컬 API에서 현재 HTTPS 터널 URL 반환. 접근 불가 시 None."""
    try:
        resp = requests.get(_NGROK_API, timeout=_HTTP_TIMEOUT)
        tunnels = resp.json().get("tunnels", [])
        for t in tunnels:
            if t.get("proto") == "https":
                return t["public_url"]
        # HTTPS 없으면 첫 번째 터널 반환
        return tunnels[0]["public_url"] if tunnels else None
    except Exception:
        return None


def _load_state() -> dict:
    if not _STATE_FILE.exists():
        return {}
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(url: str) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "url":        url,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def check_ngrok_url() -> dict:
    """
    현재 ngrok URL을 직전 상태와 비교한다.

    반환: {"status": "ok"|"changed"|"down", "url": str|None, "prev_url": str|None}
    """
    state    = _load_state()
    prev_url = state.get("url")
    curr_url = get_current_tunnel_url()

    if curr_url is None:
        logger.warning("[NgrokMonitor] ngrok 접근 불가 — 터널 오프라인")
        _notify_down()
        return {"status": "down", "url": None, "prev_url": prev_url}

    if prev_url is None:
        # 최초 실행 — URL 저장 후 조용히 종료
        _save_state(curr_url)
        logger.info(f"[NgrokMonitor] 초기 URL 저장 | {curr_url}")
        return {"status": "ok", "url": curr_url, "prev_url": None}

    if curr_url != prev_url:
        logger.warning(f"[NgrokMonitor] URL 변경 감지 | {prev_url} → {curr_url}")
        _save_state(curr_url)
        _notify_changed(prev_url, curr_url)
        return {"status": "changed", "url": curr_url, "prev_url": prev_url}

    logger.debug(f"[NgrokMonitor] URL 정상 | {curr_url}")
    return {"status": "ok", "url": curr_url, "prev_url": prev_url}


def _notify_down() -> None:
    try:
        from services.slack_notifier import send_alert
        send_alert(
            title="[ngrok] 터널 오프라인",
            body="ngrok 프로세스가 응답하지 않습니다.\nMeta Webhook DM 수신이 중단될 수 있습니다.",
            level="error",
        )
    except Exception as exc:
        logger.debug(f"[NgrokMonitor] Slack 알림 실패 | {exc}")


def _notify_changed(prev: str, curr: str) -> None:
    try:
        from services.slack_notifier import send_alert
        send_alert(
            title="[ngrok] 터널 URL 변경됨",
            body=(
                f"*이전*: {prev}\n"
                f"*현재*: {curr}\n\n"
                "Meta Webhook Callback URL을 새 URL로 업데이트하세요."
            ),
            level="warning",
        )
    except Exception as exc:
        logger.debug(f"[NgrokMonitor] Slack 알림 실패 | {exc}")
