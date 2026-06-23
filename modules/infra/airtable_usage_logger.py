"""
modules/infra/airtable_usage_logger.py
Airtable API 호출 횟수 추적 · 날짜별 누적 기록 · 월 집계 · 임계치 Telegram 경고.

사용법:
    from modules.infra.airtable_usage_logger import log_api_call, get_monthly_count
    log_api_call("Source_Feeds", "GET")
"""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(
    dotenv_path=Path(__file__).resolve().parents[2] / ".env",
    override=True,
)

_USAGE_FILE = Path(__file__).resolve().parents[2] / "logs" / "airtable_usage.jsonl"
_WARN_THRESHOLD = 100_000
_lock = threading.RLock()  # 재진입 가능: log_api_call → get_monthly_count 중첩 호출 허용

_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# 경고 중복 발송 방지 — 프로세스 내 1회
_threshold_notified: set[str] = set()


def _ensure_log_dir() -> None:
    _USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _this_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _send_telegram(text: str) -> None:
    if not _BOT_TOKEN or not _CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
            json={"chat_id": _CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=8,
        )
    except Exception:
        pass


def log_api_call(table: str = "", method: str = "GET") -> None:
    """API 호출 1건을 기록하고 월 누적이 임계치를 넘으면 Telegram 경고."""
    _ensure_log_dir()
    entry = {
        "ts":     datetime.now(timezone.utc).isoformat(),
        "date":   _today(),
        "month":  _this_month(),
        "table":  table,
        "method": method,
    }
    with _lock:
        with _USAGE_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        monthly = get_monthly_count(_this_month())
        if monthly > _WARN_THRESHOLD and _this_month() not in _threshold_notified:
            _threshold_notified.add(_this_month())
            _send_telegram(
                f"⚠️ *Airtable API 사용량 경고*\n"
                f"월 누적 호출 수: *{monthly:,}회*\n"
                f"임계치({_WARN_THRESHOLD:,}회) 초과\n"
                f"기준월: {_this_month()}"
            )


def get_monthly_count(month: str | None = None) -> int:
    """month='YYYY-MM' 형식. None이면 이번 달."""
    month = month or _this_month()
    if not _USAGE_FILE.exists():
        return 0
    count = 0
    with _lock:
        with _USAGE_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("month") == month:
                        count += 1
                except json.JSONDecodeError:
                    continue
    return count


def get_daily_count(date: str | None = None) -> int:
    """date='YYYY-MM-DD' 형식. None이면 오늘."""
    date = date or _today()
    if not _USAGE_FILE.exists():
        return 0
    count = 0
    with _lock:
        with _USAGE_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("date") == date:
                        count += 1
                except json.JSONDecodeError:
                    continue
    return count


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    log_api_call("Source_Feeds", "GET")
    log_api_call("Instagram_Posts", "PATCH")
    print(f"오늘 호출 수  : {get_daily_count()}")
    print(f"이번 달 호출 수: {get_monthly_count()}")
