"""Gate E-B: DM/comment Graph API version centralization tests."""

import pytest

from modules.common.meta_graph import (
    get_messaging_graph_api_version,
    messaging_graph_url,
)


class _FakeResponse:
    def __init__(self, payload=None, *, ok=True):
        self._payload = payload or {}
        self.ok = ok
        self.status_code = 200 if ok else 400
        self.text = ""

    def json(self):
        return self._payload


def test_messaging_graph_url_defaults_to_v25(monkeypatch):
    monkeypatch.delenv("META_MESSAGING_GRAPH_API_VERSION", raising=False)

    assert get_messaging_graph_api_version() == "v25.0"
    assert messaging_graph_url("me/accounts") == (
        "https://graph.facebook.com/v25.0/me/accounts"
    )


def test_messaging_graph_url_honors_version_override(monkeypatch):
    monkeypatch.setenv("META_MESSAGING_GRAPH_API_VERSION", "v24.0")

    assert messaging_graph_url("/page/messages") == (
        "https://graph.facebook.com/v24.0/page/messages"
    )


@pytest.mark.parametrize(
    "version",
    ["", "25.0", "v25", "v25.0/evil", "https://example.com"],
)
def test_messaging_graph_url_rejects_invalid_version(monkeypatch, version):
    monkeypatch.setenv("META_MESSAGING_GRAPH_API_VERSION", version)

    with pytest.raises(ValueError, match="META_MESSAGING_GRAPH_API_VERSION"):
        messaging_graph_url("me/accounts")


@pytest.mark.parametrize("path", ["", "   ", "https://example.com/path"])
def test_messaging_graph_url_rejects_invalid_path(monkeypatch, path):
    monkeypatch.delenv("META_MESSAGING_GRAPH_API_VERSION", raising=False)

    with pytest.raises(ValueError, match="relative path"):
        messaging_graph_url(path)


def test_dm_auto_reply_uses_centralized_urls(monkeypatch):
    from modules.dm import dm_auto_reply

    urls = []
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("INSTA_ACCESS_TOKEN", "user-token")
    monkeypatch.setattr(
        dm_auto_reply.requests,
        "get",
        lambda url, **kwargs: (
            urls.append(url)
            or _FakeResponse({"data": [{"id": "page", "access_token": "page-token"}]})
        ),
    )
    assert dm_auto_reply._get_page_token() == "page-token"

    monkeypatch.setattr(dm_auto_reply, "_get_page_token", lambda: "page-token")
    monkeypatch.setattr(
        dm_auto_reply.requests,
        "post",
        lambda url, **kwargs: (
            urls.append(url) or _FakeResponse({"message_id": "message"})
        ),
    )
    assert dm_auto_reply.send_ig_reply("recipient", "hello") is True
    assert urls == [
        "https://graph.facebook.com/v25.0/me/accounts",
        "https://graph.facebook.com/v25.0/page/messages",
    ]


def test_dm_followup_uses_centralized_urls(monkeypatch):
    from modules.dm import dm_followup_scheduler

    urls = []
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("INSTA_ACCESS_TOKEN", "user-token")
    monkeypatch.setattr(
        dm_followup_scheduler.requests,
        "get",
        lambda url, **kwargs: (
            urls.append(url)
            or _FakeResponse({"data": [{"id": "page", "access_token": "page-token"}]})
        ),
    )
    assert dm_followup_scheduler._get_page_token() == "page-token"

    monkeypatch.setattr(dm_followup_scheduler, "_get_page_token", lambda: "page-token")
    monkeypatch.setattr(
        dm_followup_scheduler.requests,
        "post",
        lambda url, **kwargs: (
            urls.append(url) or _FakeResponse({"message_id": "message"})
        ),
    )
    assert dm_followup_scheduler._send_ig_dm("recipient", "hello") is True
    assert urls == [
        "https://graph.facebook.com/v25.0/me/accounts",
        "https://graph.facebook.com/v25.0/page/messages",
    ]


def test_comment_poller_uses_centralized_urls(monkeypatch):
    from modules.comment import comment_poller

    urls = []
    monkeypatch.setenv("INSTA_IG_USER_ID", "ig-user")
    monkeypatch.setattr(
        comment_poller.requests,
        "get",
        lambda url, **kwargs: (
            urls.append(url)
            or _FakeResponse({"data": [{"id": "item", "timestamp": "now"}]})
        ),
    )
    assert comment_poller.get_recent_media_ids() == ["item"]
    assert comment_poller.get_comments("media") == [
        {"id": "item", "timestamp": "now"}
    ]
    assert urls == [
        "https://graph.facebook.com/v25.0/ig-user/media",
        "https://graph.facebook.com/v25.0/media/comments",
    ]


def test_comment_auto_reply_uses_centralized_urls(monkeypatch):
    from modules.comment import comment_auto_reply

    urls = []
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "page")
    monkeypatch.setenv("INSTA_ACCESS_TOKEN", "user-token")
    monkeypatch.setattr(
        comment_auto_reply.requests,
        "get",
        lambda url, **kwargs: (
            urls.append(url)
            or _FakeResponse({"data": [{"id": "page", "access_token": "page-token"}]})
        ),
    )
    assert comment_auto_reply._get_page_token() == "page-token"

    monkeypatch.setattr(comment_auto_reply, "_get_page_token", lambda: "page-token")
    monkeypatch.setattr(
        comment_auto_reply.requests,
        "post",
        lambda url, **kwargs: urls.append(url) or _FakeResponse({"id": "reply"}),
    )
    assert comment_auto_reply.reply_to_comment("comment", "hello") is True
    assert urls == [
        "https://graph.facebook.com/v25.0/me/accounts",
        "https://graph.facebook.com/v25.0/comment/replies",
    ]
