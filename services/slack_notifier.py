"""
services/slack_notifier.py — 운영 알림 호환 계층 (261106: 전송은 Telegram, 아래 Slack 설명은 과거 이력)

261106 회장 확정으로 모든 운영 알림은 Telegram(services/telegram_notifier)으로 간다. 이 모듈은 기존 호출부와
테스트가 쓰는 함수 이름(send_alert/notify_*/get_notify_fn)을 유지하는 얇은 계층이며 Slack 으로는 보내지 않는다.
환경변수: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (SLACK_WEBHOOK_URL 은 더 이상 사용하지 않음)

[이전 설명 — 2026-05-13 최초 구현 당시]
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


_EMOJI_MAP = {
    ":red_circle:": "🔴", ":warning:": "⚠️", ":white_check_mark:": "✅", ":information_source:": "ℹ️",
    ":fire:": "🔥", ":partly_sunny:": "⛅", ":snowflake:": "❄️",
}


def _payload_to_text(payload: dict) -> str:
    """Slack 형식 payload(text 또는 attachments)를 Telegram 평문으로 바꾼다."""
    parts = []
    if payload.get("text"):
        parts.append(str(payload["text"]))
    for att in payload.get("attachments") or []:
        for key in ("title", "text", "footer"):
            if att.get(key):
                parts.append(str(att[key]))
    text = "\n".join(parts)
    for code, emoji in _EMOJI_MAP.items():
        text = text.replace(code, emoji)
    return text.replace("*", "").strip()


def _post(payload: dict) -> bool:
    """261106 회장 확정: 운영 알림은 무조건 Telegram. 모듈·함수 이름(slack_*)은 호출부·테스트 호환을 위해 유지하고
    전송만 Telegram 으로 보낸다(Slack Webhook 은 더 이상 쓰지 않는다)."""
    from services import telegram_notifier
    return telegram_notifier.send_message(_payload_to_text(payload))


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
    from services import telegram_notifier
    if telegram_notifier.get_notify_fn() is None:   # TELEGRAM_BOT_TOKEN/CHAT_ID 미설정
        return None

    def _fn(msg: str) -> bool:
        # 261106: 발송 성공 여부를 돌려준다(기존 호출자는 반환값을 쓰지 않아 영향 없음)
        return send_alert(title="오류 발생", body=msg, level="error")

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


def notify_daily_report(stats: dict, date_kst: str) -> bool:
    """일일 Lead 상세 리포트 발송 (hot/warm/cold 포함)."""
    total     = stats.get("total", 0)
    converted = stats.get("converted", 0)
    rate      = f"{converted / total * 100:.1f}%" if total else "0.0%"
    body = (
        f"*총 신규 문의*: {total}건\n"
        f"*전환(주문)*: {converted}건 ({rate})\n"
        f"─────────────────\n"
        f":fire: Hot: {stats.get('hot', 0)}건  "
        f":partly_sunny: Warm: {stats.get('warm', 0)}건  "
        f":snowflake: Cold: {stats.get('cold', 0)}건\n"
        f"*Qualified*: {stats.get('qualified', 0)}건"
    )
    return send_alert(title=f"일일 Lead 리포트 ({date_kst})", body=body, level="info")


def notify_process_restart(process_name: str, status: str) -> bool:
    """watchdog 재시작 이벤트 알림."""
    level = "success" if status == "ok" else "error"
    return send_alert(
        title=f"[Watchdog] {process_name} 재시작 {status.upper()}",
        body=f"프로세스: {process_name} | 결과: {status}",
        level=level,
    )
