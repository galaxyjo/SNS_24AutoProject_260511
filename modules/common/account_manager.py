"""
account_manager.py — 다계정 설정 관리

계정 설정 우선순위:
  1. configs/accounts.json  (다계정 운영 시 사용)
  2. .env 환경변수           (단일 계정 하위 호환)

accounts.json 형식:
  [
    {
      "name": "account1",
      "active": true,
      "adspower_user_id": "k1bto3j4",
      "ig_user_id": "123456789",
      "ig_access_token": "EAA...",
      "fb_page_id": "987654321",
      "airtable_base_id": "appXXXXXXXXXXXXXX",
      "crawl_urls": ["https://www.facebook.com/groups/XXXXXXXX"],
      "telegram_chat_id": "",
      "proxy": {
        "enabled": false,
        "scheme": "http",
        "host": "proxy.example.com",
        "port": 8080,
        "username": "",
        "password": ""
      }
    }
  ]

사용법:
    from modules.common.account_manager import get_active_accounts, get_account

    for acct in get_active_accounts():
        print(acct.name, acct.ig_user_id)
        opts = acct.selenium_proxy_options()  # Selenium ChromeOptions에 적용
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

from modules.common.logger import get_logger

logger = get_logger(__name__)

_ACCOUNTS_JSON = Path(__file__).resolve().parents[2] / "configs" / "accounts.json"


# ── 계정 데이터 클래스 ────────────────────────────────────────────────────────

@dataclass
class Account:
    name: str
    active: bool
    adspower_user_id: str
    ig_user_id: str
    ig_access_token: str
    fb_page_id: str
    airtable_base_id: str
    crawl_urls: list[str] = field(default_factory=list)
    telegram_chat_id: str = ""
    proxy: dict = field(default_factory=dict)

    def as_env(self) -> dict:
        """계정 설정을 환경변수 딕셔너리로 반환 (기존 코드와 호환)."""
        return {
            "INSTA_ACCESS_TOKEN":   self.ig_access_token,
            "INSTA_IG_USER_ID":     self.ig_user_id,
            "FACEBOOK_PAGE_ID":     self.fb_page_id,
            "AIRTABLE_BASE_ID":     self.airtable_base_id,
            "TELEGRAM_CHAT_ID":     self.telegram_chat_id,
        }

    def selenium_proxy_options(self) -> dict[str, Any]:
        """Selenium ChromeOptions에 추가할 proxy 설정을 반환한다.

        사용 예:
            opts = acct.selenium_proxy_options()
            if opts:
                options.add_argument(f'--proxy-server={opts["proxy_server"]}')
        """
        p = self.proxy
        if not p or not p.get("enabled") or not p.get("host"):
            return {}
        host = p["host"]
        port = p.get("port", 8080)
        scheme = p.get("scheme", "http")
        user = p.get("username", "")
        pwd  = p.get("password", "")
        server = f"{scheme}://{host}:{port}"
        result: dict[str, Any] = {"proxy_server": server}
        if user and pwd:
            result["proxy_auth"] = f"{user}:{pwd}"
        return result




# ── Airtable Crawl_Targets 로더 ───────────────────────────────────────────────

def _load_crawl_urls_from_airtable() -> list[str]:
    """Airtable Crawl_Targets에서 active facebook URL 목록 반환."""
    import requests as _req
    api_key = os.getenv('AIRTABLE_API_KEY', '')
    base_id = os.getenv('AIRTABLE_BASE_ID', '')
    if not api_key or not base_id:
        logger.warning('[AccountManager] Airtable 키 없음 — crawl_urls 로드 실패')
        return []
    try:
        r = _req.get(
            f'https://api.airtable.com/v0/{base_id}/Crawl_Targets',
            headers={'Authorization': f'Bearer {api_key}'},
            params={
                'filterByFormula': "AND({status}='Active',{platform}='facebook')",
                'sort[0][field]': 'priority',
                'sort[0][direction]': 'asc',
                'maxRecords': 50,
            },
            timeout=10,
        )
        records = r.json().get('records', [])
        urls = [rec['fields']['target_url'] for rec in records if rec.get('fields', {}).get('target_url')]
        logger.info(f'[AccountManager] Airtable crawl_urls 로드 | {len(urls)}건')
        return urls
    except Exception as exc:
        logger.error(f'[AccountManager] Airtable crawl_urls 로드 실패 | {exc}')
        return []


def _shadow_compare(json_urls: list[str], airtable_urls: list[str]) -> None:
    """Shadow Mode — accounts.json vs Airtable URL 비교 로그."""
    json_set = set(json_urls)
    at_set = set(airtable_urls)
    only_json = json_set - at_set
    only_at = at_set - json_set
    logger.info(f'[Shadow] accounts.json={len(json_urls)}건 | Airtable={len(airtable_urls)}건')
    if only_json:
        logger.warning(f'[Shadow] accounts.json에만 있음: {only_json}')
    if only_at:
        logger.warning(f'[Shadow] Airtable에만 있음: {only_at}')
    if not only_json and not only_at:
        logger.info('[Shadow] 두 소스 일치 ✅')

# ── 로더 ─────────────────────────────────────────────────────────────────────

def _load_from_json() -> list[Account]:
    if not _ACCOUNTS_JSON.exists():
        return []
    try:
        data = json.loads(_ACCOUNTS_JSON.read_text(encoding="utf-8"))
        accounts = []
        for item in data:
            accounts.append(Account(
                name             = item.get("name", ""),
                active           = item.get("active", True),
                adspower_user_id = item.get("adspower_user_id", ""),
                ig_user_id       = item.get("ig_user_id", ""),
                ig_access_token  = item.get("ig_access_token", ""),
                fb_page_id       = item.get("fb_page_id") or item.get("facebook_page_id", ""),
                airtable_base_id = item.get("airtable_base_id", ""),
                crawl_urls       = item.get("crawl_urls", []),
                telegram_chat_id = item.get("telegram_chat_id", ""),
                proxy            = item.get("proxy", {}),
            ))
        logger.info(f"[AccountManager] accounts.json 로드 | {len(accounts)}개 계정")
        return accounts
    except Exception as exc:
        logger.error(f"[AccountManager] accounts.json 파싱 실패 | {exc}")
        return []


def _load_from_env() -> list[Account]:
    """환경변수 기반 단일 계정 (하위 호환)."""
    ig_user_id = os.getenv("INSTA_IG_USER_ID", "").strip()
    if not ig_user_id:
        return []
    acct = Account(
        name             = "default",
        active           = True,
        adspower_user_id = os.getenv("ADSPOWER_USER_ID", "k1bto3j4"),
        ig_user_id       = ig_user_id,
        ig_access_token  = os.getenv("INSTA_ACCESS_TOKEN", ""),
        fb_page_id       = os.getenv("FACEBOOK_PAGE_ID", ""),
        airtable_base_id = os.getenv("AIRTABLE_BASE_ID", ""),
        crawl_urls       = [],
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", ""),
    )
    logger.info("[AccountManager] 환경변수 기반 단일 계정 사용")
    return [acct]


# ── 캐시 ─────────────────────────────────────────────────────────────────────
_cache: list[Account] | None = None


def _get_all() -> list[Account]:
    global _cache
    if _cache is None:
        _cache = _load_from_json() or _load_from_env()
        if not _cache:
            logger.warning("[AccountManager] 계정 설정 없음 — accounts.json 또는 .env 확인 필요")
        # Feature Flag: CRAWL_TARGET_SOURCE
        source = os.getenv("CRAWL_TARGET_SOURCE", "accounts_json").strip()
        if source in ("shadow", "airtable") and _cache:
            at_urls = _load_crawl_urls_from_airtable()
            if source == "shadow":
                _shadow_compare(_cache[0].crawl_urls, at_urls)
            elif source == "airtable":
                _cache[0].crawl_urls = at_urls
                logger.info(f"[AccountManager] crawl_urls → Airtable 방식 적용 | {len(at_urls)}건")
    return _cache


def reload() -> None:
    """캐시를 초기화하고 재로드한다 (런타임 계정 추가 시 사용)."""
    global _cache
    _cache = None
    _get_all()


# ── 공개 API ──────────────────────────────────────────────────────────────────

def get_active_accounts() -> list[Account]:
    """활성화된 계정 목록을 반환한다."""
    return [a for a in _get_all() if a.active]


def get_account(name: str) -> Optional[Account]:
    """이름으로 특정 계정을 반환한다. 없으면 None."""
    return next((a for a in _get_all() if a.name == name), None)


def get_default_account() -> Optional[Account]:
    """첫 번째 활성 계정을 반환한다 (단일 계정 코드 호환용)."""
    accounts = get_active_accounts()
    return accounts[0] if accounts else None
