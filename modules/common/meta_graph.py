"""Meta Graph API URL helpers for DM and comment endpoints."""

import os
import re


_GRAPH_BASE_URL = "https://graph.facebook.com"
_INSTAGRAM_GRAPH_BASE_URL = "https://graph.instagram.com"
_DEFAULT_MESSAGING_VERSION = "v25.0"
_VERSION_PATTERN = re.compile(r"^v\d+\.\d+$")


def get_messaging_graph_api_version() -> str:
    """Return the configured DM/comment Graph API version.

    The strict format check prevents malformed configuration from silently
    changing the Graph host or URL path.
    """
    version = os.getenv(
        "META_MESSAGING_GRAPH_API_VERSION",
        _DEFAULT_MESSAGING_VERSION,
    ).strip()
    if not _VERSION_PATTERN.fullmatch(version):
        raise ValueError(
            "META_MESSAGING_GRAPH_API_VERSION must match 'v<major>.<minor>'"
        )
    return version


def messaging_graph_url(path: str) -> str:
    """Build a versioned Graph API URL for a relative endpoint path."""
    normalized = str(path).strip().lstrip("/")
    if not normalized or "://" in normalized:
        raise ValueError("Graph API path must be a non-empty relative path")
    return f"{_GRAPH_BASE_URL}/{get_messaging_graph_api_version()}/{normalized}"


def instagram_login_graph_url(path: str) -> str:
    """260730 Multi-account DM Routing — instagram_login Provider(예: aijomoojin) 전용.
    facebook_login과 달리 Page Token 교환 없이 graph.instagram.com에 직접 요청한다."""
    normalized = str(path).strip().lstrip("/")
    if not normalized or "://" in normalized:
        raise ValueError("Graph API path must be a non-empty relative path")
    return f"{_INSTAGRAM_GRAPH_BASE_URL}/{get_messaging_graph_api_version()}/{normalized}"
