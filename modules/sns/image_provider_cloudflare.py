"""image_provider_cloudflare.py — Track B-4 Provider Adapter: Cloudflare Workers AI (FLUX.1-schnell).

Cloudflare Workers AI 공식 REST API로 신규 이미지를 생성한다(@cf/black-forest-labs/flux-1-schnell).
무료 티어 10,000 neurons/일(공식 문서 확인, 260731) — 이 프로젝트 하루 3장 사용은 여유 충분하나,
DAILY_IMAGE_CAP은 별개의 프로젝트 자체 안전장치(Fail-closed)로 SQLite에 영속 기록한다.

Provider 무관 로직(Visual Brief/Image Prompt)은 modules.sns.visual_brief에 분리돼 있다.
"""

import base64
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from modules.common.logger import get_logger

logger = get_logger(__name__)

PROVIDER_NAME = "cloudflare_workers_ai"
MODEL_NAME = "@cf/black-forest-labs/flux-1-schnell"
DAILY_IMAGE_CAP = 3
REQUEST_TIMEOUT = 30

_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "image_gen_quota.db"


@dataclass(frozen=True)
class ProviderResult:
    success: bool
    image_bytes: bytes = b""
    provider: str = ""
    model: str = ""
    generation_timestamp: str = ""
    error_code: str = ""


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS image_generations (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            provider     TEXT    NOT NULL,
            model        TEXT    NOT NULL,
            generated_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    _init_db(conn)
    return conn


def _count_today(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM image_generations WHERE date(generated_at) = date('now')"
    ).fetchone()
    return row[0] if row else 0


def _record_generation(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO image_generations (provider, model) VALUES (?, ?)",
        (PROVIDER_NAME, MODEL_NAME),
    )
    conn.commit()


def quota_available(conn: "sqlite3.Connection | None" = None) -> bool:
    """오늘(UTC) 이미 DAILY_IMAGE_CAP만큼 생성했으면 False(Fail-closed)."""
    owns_conn = conn is None
    conn = conn or _get_conn()
    try:
        return _count_today(conn) < DAILY_IMAGE_CAP
    finally:
        if owns_conn:
            conn.close()


def generate_image(
    prompt_text: str,
    negative_prompt: str = "",
    steps: int = 4,
    api_token: str = "",
    account_id: str = "",
) -> ProviderResult:
    """FLUX.1-schnell로 이미지 1장 생성. Fail-closed 조건(순서대로):
    일일 상한 초과 / Credential 미설정 / API 실패·Timeout / 응답 형식 이상."""
    conn = _get_conn()
    try:
        if not quota_available(conn):
            logger.info(f"[ImageProvider] DAILY_IMAGE_CAP_EXCEEDED | cap={DAILY_IMAGE_CAP}")
            return ProviderResult(success=False, error_code="DAILY_IMAGE_CAP_EXCEEDED")

        api_token = api_token or os.getenv("CLOUDFLARE_API_TOKEN", "")
        account_id = account_id or os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
        if not api_token or not account_id:
            logger.warning("[ImageProvider] Cloudflare credential 미설정")
            return ProviderResult(success=False, error_code="CREDENTIALS_MISSING")

        if not prompt_text or not prompt_text.strip():
            return ProviderResult(success=False, error_code="EMPTY_PROMPT")

        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{MODEL_NAME}"
        payload = {"prompt": prompt_text, "steps": max(1, min(steps, 8))}
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        try:
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {api_token}"},
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
        except Exception as exc:
            logger.warning(f"[ImageProvider] 요청 실패 | {exc}")
            return ProviderResult(success=False, error_code="REQUEST_FAILED")

        if resp.status_code != 200:
            logger.warning(f"[ImageProvider] HTTP {resp.status_code} | {resp.text[:200]}")
            return ProviderResult(success=False, error_code=f"HTTP_{resp.status_code}")

        try:
            data = resp.json()
        except Exception:
            return ProviderResult(success=False, error_code="INVALID_JSON_RESPONSE")

        if not data.get("success"):
            logger.warning(f"[ImageProvider] API success=false | {data.get('errors')}")
            return ProviderResult(success=False, error_code="API_ERROR")

        image_b64 = (data.get("result") or {}).get("image")
        if not image_b64:
            return ProviderResult(success=False, error_code="NO_IMAGE_IN_RESPONSE")

        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception:
            return ProviderResult(success=False, error_code="IMAGE_DECODE_FAILED")

        if not image_bytes:
            return ProviderResult(success=False, error_code="EMPTY_IMAGE_BYTES")

        _record_generation(conn)
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"[ImageProvider] 생성 성공 | provider={PROVIDER_NAME} | model={MODEL_NAME}")
        return ProviderResult(
            success=True,
            image_bytes=image_bytes,
            provider=PROVIDER_NAME,
            model=MODEL_NAME,
            generation_timestamp=timestamp,
        )
    finally:
        conn.close()
