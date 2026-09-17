"""
modules/discovery/youtube_connector.py — YouTube Data API v3 기반 계정(채널) 발굴 커넥터

Lead-Acq Track 1-2a. 기존 `modules/crawlers/base_connector.py::BaseCrawlConnector`를
그대로 상속한다(신규 ABC 없음). `naver_search_connector.py` /
`domeggook_api_connector.py`와 동일한 "requests + os.getenv 키" 패턴을 따르며,
신규 HTTP framework를 도입하지 않는다.

이 커넥터가 담당하는 것:
  - search.list(type=channel) 응답  → channelId 목록(입력 순서 보존, 중복 제거)
  - channels.list 응답              → 채널별 공통 Prospect dict
  - prospect_id                     = "youtube-" + sha256(정규화 channel_url)[:12]

담당하지 않는 것(별도 Gate): Airtable 저장 / Gemini 분류 / Scheduler 연결.

`fetch()`는 실제 API 호출 구조를 갖추되, Smoke Test(fixture + `requests.get`
monkeypatch)는 네트워크를 타지 않는다. `_extract_channel_ids` / `_normalize` /
`prospect_id`는 네트워크 없이 직접 호출 가능한 순수 로직이다.
"""

import hashlib
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from modules.crawlers.base_connector import BaseCrawlConnector, ConnectorError
from modules.common.logger import get_logger

logger = get_logger(__name__)

_SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
_CHANNELS_ENDPOINT = "https://www.googleapis.com/youtube/v3/channels"
_CHANNEL_URL_PREFIX = "https://www.youtube.com/channel/"


class YouTubeConnector(BaseCrawlConnector):
    """YouTube Data API v3 채널 발굴 커넥터 (기존 BaseCrawlConnector 상속)."""

    def __init__(self, api_key: "str | None" = None):
        # API Key는 실제 fetch()/health_check() 네트워크 호출에만 필요하다.
        # Smoke Test는 requests.get을 monkeypatch하므로 Key 없이도 인스턴스화할 수
        # 있어야 한다 — __init__에서 raise하지 않고 네트워크 호출 직전에만 검증한다.
        self.api_key = api_key if api_key is not None else os.getenv("YOUTUBE_API_KEY", "")

    # ── BaseCrawlConnector 계약 ──────────────────────────────────────────────

    def fetch(self, target: dict) -> list:
        """target(keyword)로 채널을 검색해 공통 Prospect dict 목록을 반환한다.

        target 예: {"keyword": "<검색어>", "max_posts": <int, 선택, 기본 10, 최대 50>}
        """
        query = target.get("keyword") or target.get("q") or target.get("kw")
        if not query:
            raise ConnectorError("target must have keyword")
        max_results = min(int(target.get("max_posts", 10)), 50)

        self._require_api_key()

        search_payload = self._get(
            _SEARCH_ENDPOINT,
            {
                "part": "snippet",
                "type": "channel",
                "q": query,
                "maxResults": max_results,
                "key": self.api_key,
            },
        )
        channel_ids = self._extract_channel_ids(search_payload)
        if not channel_ids:
            logger.info(f"[YouTube] 검색 결과 채널 0건 | query={query!r}")
            return []

        channels_payload = self._get(
            _CHANNELS_ENDPOINT,
            {
                "part": "snippet,statistics,brandingSettings",
                "id": ",".join(channel_ids),
                "key": self.api_key,
            },
        )
        channel_by_id = {
            c.get("id", ""): c for c in channels_payload.get("items", []) or [] if c.get("id")
        }
        search_by_id = self._search_items_by_id(search_payload)

        results = []
        for cid in channel_ids:
            channel_item = channel_by_id.get(cid)
            if not channel_item:
                logger.warning(
                    f"[YouTube] channels.list 응답에 채널 없음 — skip | channel_id={cid}"
                )
                continue
            try:
                results.append(
                    self._normalize(search_by_id.get(cid, {}), channel_item, query)
                )
            except Exception as exc:  # 개별 채널 실패가 배치를 막지 않도록 격리
                logger.warning(f"[YouTube] normalize skip | channel_id={cid} | {exc}")
        return results

    def health_check(self) -> bool:
        try:
            self._require_api_key()
            r = requests.get(
                _SEARCH_ENDPOINT,
                params={
                    "part": "snippet",
                    "type": "channel",
                    "q": "test",
                    "maxResults": 1,
                    "key": self.api_key,
                },
                timeout=10,
            )
            return r.status_code == 200
        except Exception:
            return False

    # ── 내부 HTTP (naver/domeggook 커넥터와 동일 패턴) ──────────────────────

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise ConnectorError("YOUTUBE_API_KEY not set")

    def _get(self, endpoint: str, params: dict) -> dict:
        try:
            r = requests.get(endpoint, params=params, timeout=15)
            r.raise_for_status()
        except Exception as e:
            raise ConnectorError(f"HTTP error: {e}")
        try:
            return r.json()
        except Exception as e:
            raise ConnectorError(f"JSON parse error: {e}")

    # ── 파싱 / 정규화 (순수 로직 — Smoke Test 대상) ────────────────────────

    @staticmethod
    def _channel_id_of_search_item(item: dict) -> str:
        return (
            (item.get("id", {}) or {}).get("channelId", "")
            or (item.get("snippet", {}) or {}).get("channelId", "")
        )

    @staticmethod
    def _extract_channel_ids(search_payload: dict) -> list:
        """search.list 응답에서 channelId를 입력 순서대로, 중복 제거해 반환한다."""
        seen = set()
        ordered = []
        for item in search_payload.get("items", []) or []:
            cid = YouTubeConnector._channel_id_of_search_item(item)
            if cid and cid not in seen:
                seen.add(cid)
                ordered.append(cid)
        return ordered

    @staticmethod
    def _search_items_by_id(search_payload: dict) -> dict:
        out = {}
        for item in search_payload.get("items", []) or []:
            cid = YouTubeConnector._channel_id_of_search_item(item)
            if cid and cid not in out:
                out[cid] = item
        return out

    def _normalize(self, search_item: dict, channel_item: dict, discovery_source: str) -> dict:
        """channels.list 채널 1건 → 공통 Prospect dict."""
        snippet = channel_item.get("snippet", {}) or {}
        channel_id = channel_item.get("id", "") or self._channel_id_of_search_item(search_item)
        if not channel_id or not isinstance(channel_id, str):
            raise ValueError("channel_id 없음/형식오류")

        account_url = _CHANNEL_URL_PREFIX + channel_id
        return {
            "platform": "youtube",
            "prospect_id": self.prospect_id(account_url),
            "account_url": account_url,
            "handle": snippet.get("customUrl", "") or "",
            "display_name": snippet.get("title", "") or "",
            # country: snippet.country가 없으면 빈 값. 추측 금지.
            "country": snippet.get("country", "") or "",
            "discovery_source": discovery_source,
            # evidence: 원본 응답 JSON을 그대로 보존한다(추측값 저장 금지).
            "evidence": {
                "discovery_source": discovery_source,
                "search_item": search_item,
                "channel_item": channel_item,
            },
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── prospect_id (결정론적) ────────────────────────────────────────────

    @staticmethod
    def _normalize_channel_url(account_url: str) -> str:
        p = urlparse((account_url or "").strip())
        host = (p.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        path = p.path.rstrip("/")
        return f"https://{host}{path}"

    @classmethod
    def prospect_id(cls, account_url: str) -> str:
        norm = cls._normalize_channel_url(account_url)
        digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]
        return f"youtube-{digest}"
