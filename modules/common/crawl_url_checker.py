"""
modules/common/crawl_url_checker.py — FB 크롤링 URL 유효성 체크

활성 계정의 crawl_urls를 HTTP로 확인해 접근 불가·삭제된 URL을 감지하고
Slack으로 알린다. 상태 변화 시에만 알림을 발송한다.

사용법:
    from modules.common.crawl_url_checker import check_all, get_last_results
    check_all()                 # 스케줄러 잡
    results = get_last_results()  # health_monitor 에서 호출
"""

import json
import requests
from datetime import datetime, timezone
from pathlib import Path

from modules.common.logger import get_logger

logger = get_logger(__name__)

_STATE_FILE  = Path(__file__).resolve().parents[2] / "db" / "crawl_url_status.json"
_HTTP_TIMEOUT = 6
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _check_url(url: str) -> str:
    """단일 URL 체크. 반환: 'ok' | 'invalid' | 'unreachable'"""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_HTTP_TIMEOUT,
                            allow_redirects=True)
        if resp.status_code == 404:
            return "invalid"
        return "ok"   # 200 / 302 / 403 모두 URL 존재로 간주
    except requests.exceptions.Timeout:
        return "unreachable"
    except Exception:
        return "unreachable"


def _load_state() -> dict:
    if not _STATE_FILE.exists():
        return {}
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(results: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "urls": results,
    }
    _STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_last_results() -> dict:
    """마지막 체크 결과 반환 (health_monitor용). 미실행 시 {}."""
    state = _load_state()
    return state.get("urls", {})


def check_all() -> dict:
    """
    모든 활성 계정의 crawl_urls를 체크하고, 이전 상태와 비교해 Slack 알림 발송.
    반환: {url: status, ...}
    """
    from modules.common.account_manager import get_active_accounts

    accounts = get_active_accounts()
    all_urls: list[str] = []
    for acct in accounts:
        all_urls.extend(acct.crawl_urls)

    if not all_urls:
        logger.info("[CrawlURLChecker] crawl_urls 없음 — 체크 생략")
        return {}

    prev_state = _load_state().get("urls", {})
    results: dict[str, str] = {}

    for url in all_urls:
        status = _check_url(url)
        results[url] = status
        logger.info(f"[CrawlURLChecker] {status.upper()} | {url[:80]}")

    _save_state(results)
    _notify_changes(prev_state, results)
    return results


def _notify_changes(prev: dict, curr: dict) -> None:
    """이전 → 현재 상태 중 ok 이외로 변화한 항목만 Slack 알림."""
    problems: list[str] = []
    for url, status in curr.items():
        if status == "ok":
            continue
        prev_status = prev.get(url, "ok")
        # 이전에도 같은 문제였으면 재알림 생략
        if prev_status == status:
            continue
        label = "삭제/비공개" if status == "invalid" else "접근 불가(타임아웃)"
        problems.append(f"• `{url[:80]}` → *{label}*")

    if not problems:
        return

    try:
        from services.slack_notifier import send_alert
        send_alert(
            title="[FB 크롤링] URL 이상 감지",
            body="\n".join(problems) + "\n\n`configs/accounts.json`의 crawl_urls를 확인하세요.",
            level="warning",
        )
        logger.warning(f"[CrawlURLChecker] 이상 URL {len(problems)}건 — Slack 발송")
    except Exception as exc:
        logger.debug(f"[CrawlURLChecker] Slack 알림 실패 | {exc}")
