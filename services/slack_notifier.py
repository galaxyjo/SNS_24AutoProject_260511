"""
services/slack_notifier.py — Slack Incoming Webhook 기반 운영 알림

환경변수:
  SLACK_WEBHOOK_URL  — Slack Incoming Webhook URL (필수)

사용법:
    from services.slack_notifier import notify_error, notify_info, get_notify_fn

    notify_info("업로드 완료 | 3건")
    notify_error("fb_crawl", "timeout 오류")

    # error_handler 연동 (단일 문자열 인자):
    @handle_errors(task="fb_crawl", notify_fn=get_notify_fn())
    def crawl(): ...

Slack Incoming Webhook 설정:
  1. https://api.slack.com/messaging/webhooks
  2. 앱 생성 → Incoming Webhooks 활성화 → 채널 선택 → URL 복사
  3. .env 에 SLACK_WEBHOOK_URL=https://hooks.slack.com/services/... 추가
"""

import os
import requests
from datetime import datetime, timezone, timedelta

from modules.common.logger import get_logger

logger = get_logger(__name__)

_LEVEL_EMOJI = {
    "info":    ":information_source:",
    "warning": ":warning:",
    "error":   ":red_circle:",
    "success": ":white_check_mark:",
}
_LEVEL_COLOR = {
    "info":    "#36a64f",
    "warning": "#ffcc00",
    "error":   "#cc0000",
    "success": "#2eb886",
}


def _kst_now() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S KST")


def _post(payload: dict) -> bool:
    url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not url:
        logger.debug("[Slack] SLACK_WEBHOOK_URL 미설정 — 알림 생략")
        return False
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code != 200:
            logger.warning(f"[Slack] 발송 실패 | {resp.status_code} | {resp.text[:120]}")
            return False
        return True
    except Exception as exc:
        logger.warning(f"[Slack] 발송 예외 | {exc}")
        return False


# ── 기본 발송 함수 ─────────────────────────────────────────────────────────────

def send_message(text: str, level: str = "info") -> bool:
    """단순 텍스트 메시지."""
    emoji = _LEVEL_EMOJI.get(level, "")
    return _post({"text": f"{emoji} {text}"})


def send_alert(title: str, body: str = "", level: str = "warning") -> bool:
    """색상 attachment 형식 알림."""
    attachment = {
        "color":  _LEVEL_COLOR.get(level, "#888888"),
        "title":  f"{_LEVEL_EMOJI.get(level, '')} {title}",
        "text":   body,
        "footer": f"SNS_24AutoProject | {_kst_now()}",
    }
    return _post({"attachments": [attachment]})


# ── 레벨별 단축 함수 ──────────────────────────────────────────────────────────

def notify_info(text: str) -> None:
    send_message(text, level="info")


def notify_success(text: str) -> None:
    send_message(text, level="success")


def notify_warning(text: str) -> None:
    send_message(text, level="warning")


def notify_error(label: str, error_msg: str) -> None:
    """에러 핸들러 연동용 — label + 에러 메시지 전송."""
    send_alert(
        title=f"[{label}] 오류 발생",
        body=str(error_msg)[:500],
        level="error",
    )


# ── error_handler 연동 ────────────────────────────────────────────────────────

def get_notify_fn():
    """
    error_handler.notify_fn 파라미터에 전달 가능한 callable 반환.
    SLACK_WEBHOOK_URL 미설정 시 None 반환 → error_handler가 알림 생략.

    error_handler는 notify_fn(single_string) 형태로 호출한다.
    """
    if not os.getenv("SLACK_WEBHOOK_URL"):
        return None

    def _fn(msg: str) -> None:
        send_alert(title="오류 발생", body=msg, level="error")

    return _fn


# ── 도메인 알림 함수 ──────────────────────────────────────────────────────────

def notify_daily_kpi(kpi: dict) -> bool:
    """일일 KPI 요약 발송."""
    lead = kpi.get("lead", {})
    up   = kpi.get("upload", {})
    q    = kpi.get("queue", {})
    kst  = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d")
    body = (
        f"*DM 문의*: {lead.get('total', 0)}건  |  "
        f"*전환율*: {lead.get('conversion_rate', 0)}%  |  "
        f"*Hot 리드*: {lead.get('hot', 0)}건\n"
        f"*업로드 성공률*: {up.get('success_rate', 0)}%  |  "
        f"*Queue 대기*: {q.get('pending', 0) if q else 0}건"
    )
    return send_alert(title=f"일일 KPI 요약 ({kst})", body=body, level="info")


def notify_upload_result(success: int, failed: int) -> bool:
    """업로드 배치 결과 — 실패 1건 이상 시만 발송."""
    if failed == 0:
        return True
    level = "warning" if failed <= success else "error"
    return send_alert(
        title=f"업로드 배치 완료 — 실패 {failed}건",
        body=f"성공: {success}건 | 실패: {failed}건",
        level=level,
    )


def notify_process_restart(process_name: str, status: str) -> bool:
    """watchdog 재시작 이벤트 알림."""
    level = "success" if status == "ok" else "error"
    return send_alert(
        title=f"[Watchdog] {process_name} 재시작 {status.upper()}",
        body=f"프로세스: {process_name} | 결과: {status}",
        level=level,
    )
