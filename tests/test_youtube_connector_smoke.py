"""
tests/test_youtube_connector_smoke.py — Lead-Acq Track 1-2a Smoke Test

목적: 실제 YouTube API / Airtable / Gemini 연결 전에, YouTubeConnector가 기존
BaseCrawlConnector를 그대로 재사용해
  search.list 응답  → channelId 목록(입력 순서, 중복 제거)
  channels.list 응답 → 채널별 공통 Prospect dict
  결정론적 prospect_id
로 변환하는 로직만 검증한다.

- fixture는 YouTube Data API v3 공식 문서 기반이며 실제 응답으로는 미검증이다.
  실제 스키마 검증은 첫 실호출(별도 Gate)에서 수행한다.
- requests.get은 monkeypatch. 실제 네트워크 호출 / API Key / Airtable / Gemini /
  Scheduler 호출 없음. 기존 코드 수정 없음.
"""

import pytest

from modules.crawlers.base_connector import BaseCrawlConnector
from modules.discovery.youtube_connector import YouTubeConnector


# ── fixture: YouTube Data API v3 응답 형태(문서 기반, 미검증) ─────────────────

SEARCH_LIST_FIXTURE = {
    "kind": "youtube#searchListResponse",
    "items": [
        {
            "kind": "youtube#searchResult",
            "id": {"kind": "youtube#channel", "channelId": "UC_alpha"},
            "snippet": {
                "channelId": "UC_alpha",
                "title": "Alpha K-Beauty Wholesale",
                "description": "search snippet alpha",
            },
        },
        {
            "kind": "youtube#searchResult",
            "id": {"kind": "youtube#channel", "channelId": "UC_beta"},
            "snippet": {
                "channelId": "UC_beta",
                "title": "Beta Cosmetics Importer",
                "description": "search snippet beta",
            },
        },
        # 중복 channelId — 결과에서 제거되어야 한다.
        {
            "kind": "youtube#searchResult",
            "id": {"kind": "youtube#channel", "channelId": "UC_alpha"},
            "snippet": {"channelId": "UC_alpha", "title": "Alpha K-Beauty Wholesale (dup)"},
        },
    ],
}

CHANNELS_LIST_FIXTURE = {
    "kind": "youtube#channelListResponse",
    "items": [
        {
            "kind": "youtube#channel",
            "id": "UC_alpha",
            "snippet": {
                "title": "Alpha K-Beauty Wholesale",
                "customUrl": "@alphakbeauty",
                "description": "Full description alpha",
                "country": "KR",
            },
            "statistics": {"subscriberCount": "1200", "videoCount": "34", "viewCount": "90000"},
        },
        {
            "kind": "youtube#channel",
            "id": "UC_beta",
            "snippet": {
                "title": "Beta Cosmetics Importer",
                "customUrl": "@betacos",
                "description": "Full description beta",
                # country 없음 — 결과에서 빈 문자열이어야 한다(추측 금지).
            },
            "statistics": {"subscriberCount": "800"},
        },
    ],
}

SEARCH_KEYWORD = "korean cosmetics wholesale buyer"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _fake_requests_get_factory(search_payload, channels_payload):
    calls = []

    def _fake_get(url, params=None, timeout=None):
        calls.append({"url": url, "params": params or {}})
        if "/search" in url:
            return _FakeResponse(search_payload)
        if "/channels" in url:
            return _FakeResponse(channels_payload)
        raise AssertionError(f"예상치 못한 endpoint: {url}")

    _fake_get.calls = calls
    return _fake_get


@pytest.fixture
def connector(monkeypatch):
    fake_get = _fake_requests_get_factory(SEARCH_LIST_FIXTURE, CHANNELS_LIST_FIXTURE)
    monkeypatch.setattr("modules.discovery.youtube_connector.requests.get", fake_get)
    c = YouTubeConnector(api_key="smoke-test-dummy")  # 실제 Key 아님 — monkeypatch라 사용 안 됨
    c._fake_get = fake_get
    return c


# ── 0. 기존 ABC 재사용 확인 (신규 BaseDiscoveryConnector 없음) ────────────────

def test_subclasses_existing_base_crawl_connector():
    assert issubclass(YouTubeConnector, BaseCrawlConnector)


# ── 1. search.list → channelId 목록: 입력 순서 보존 + 중복 제거 ──────────────

def test_extract_channel_ids_order_and_dedup():
    ids = YouTubeConnector._extract_channel_ids(SEARCH_LIST_FIXTURE)
    assert ids == ["UC_alpha", "UC_beta"]


def test_fetch_channel_order_matches_search_order(connector):
    results = connector.fetch({"keyword": SEARCH_KEYWORD})
    assert [r["account_url"] for r in results] == [
        "https://www.youtube.com/channel/UC_alpha",
        "https://www.youtube.com/channel/UC_beta",
    ]


# ── 2. channels.list → 채널별 공통 dict 1개씩 ──────────────────────────────

def test_fetch_returns_one_dict_per_unique_channel(connector):
    results = connector.fetch({"keyword": SEARCH_KEYWORD})
    assert len(results) == 2
    assert all(r["platform"] == "youtube" for r in results)
    # search + channels 각 1회씩만 호출
    assert len(connector._fake_get.calls) == 2
    assert "/search" in connector._fake_get.calls[0]["url"]
    assert "/channels" in connector._fake_get.calls[1]["url"]


# ── 3. 6개 핵심 필드 매핑 + country 누락 시 빈 값 + evidence 원문 보존 ───────

def test_core_field_mapping_present_channel(connector):
    results = connector.fetch({"keyword": SEARCH_KEYWORD})
    alpha = results[0]

    assert alpha["account_url"] == "https://www.youtube.com/channel/UC_alpha"
    assert alpha["handle"] == "@alphakbeauty"
    assert alpha["display_name"] == "Alpha K-Beauty Wholesale"
    assert alpha["country"] == "KR"
    assert alpha["discovery_source"] == SEARCH_KEYWORD
    # evidence: 원본 응답 JSON 그대로 보존
    assert alpha["evidence"]["channel_item"] == CHANNELS_LIST_FIXTURE["items"][0]
    assert alpha["evidence"]["search_item"]["id"]["channelId"] == "UC_alpha"
    assert alpha["evidence"]["discovery_source"] == SEARCH_KEYWORD


def test_missing_country_maps_to_empty_string(connector):
    results = connector.fetch({"keyword": SEARCH_KEYWORD})
    beta = results[1]
    assert beta["country"] == ""          # 추측값 없음
    assert beta["handle"] == "@betacos"
    assert beta["display_name"] == "Beta Cosmetics Importer"


def test_all_six_core_keys_exist(connector):
    results = connector.fetch({"keyword": SEARCH_KEYWORD})
    for r in results:
        for key in ("account_url", "handle", "display_name", "country",
                    "discovery_source", "evidence"):
            assert key in r


# ── 4. prospect_id 결정론 ────────────────────────────────────────────────

def test_prospect_id_deterministic_same_url():
    a = YouTubeConnector.prospect_id("https://www.youtube.com/channel/UC_alpha")
    b = YouTubeConnector.prospect_id("https://www.youtube.com/channel/UC_alpha")
    assert a == b
    assert a.startswith("youtube-")
    assert len(a) == len("youtube-") + 12


def test_prospect_id_differs_for_different_url():
    a = YouTubeConnector.prospect_id("https://www.youtube.com/channel/UC_alpha")
    b = YouTubeConnector.prospect_id("https://www.youtube.com/channel/UC_beta")
    assert a != b


def test_prospect_id_in_fetch_matches_helper(connector):
    results = connector.fetch({"keyword": SEARCH_KEYWORD})
    assert results[0]["prospect_id"] == YouTubeConnector.prospect_id(
        "https://www.youtube.com/channel/UC_alpha"
    )
    assert results[1]["prospect_id"] == YouTubeConnector.prospect_id(
        "https://www.youtube.com/channel/UC_beta"
    )
    assert results[0]["prospect_id"] != results[1]["prospect_id"]
