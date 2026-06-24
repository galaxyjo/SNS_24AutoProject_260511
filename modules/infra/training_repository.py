"""
modules/infra/training_repository.py
Product_Training_Set 테이블 전용 저장소.
도메꾹 수집/분석 파이프라인 전용 — 운영 RepositoryInterface와 분리.
"""
from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from modules.infra.airtable_usage_logger import log_api_call

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=True)

_TABLE   = "Product_Training_Set"
_TIMEOUT = 30


def _url(record_id: str = "") -> str:
    base_id = os.getenv("AIRTABLE_BASE_ID", "")
    base = f"https://api.airtable.com/v0/{base_id}/{requests.utils.quote(_TABLE)}"
    return f"{base}/{record_id}" if record_id else base


def _headers(json_body: bool = False) -> dict:
    h = {"Authorization": f"Bearer {os.getenv('AIRTABLE_API_KEY', '')}"}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


class TrainingRepository:
    """Product_Training_Set Airtable REST API 래퍼."""

    def upsert_training_record(self, training_record_id: str, fields: dict) -> str:
        """training_record_id 기준 중복 확인 후 PATCH 또는 POST. record_id 반환."""
        safe_id = training_record_id.replace("'", "\\'")
        r = requests.get(
            _url(),
            headers=_headers(),
            params={
                "maxRecords": 1,
                "filterByFormula": f"{{training_record_id}}='{safe_id}'",
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        log_api_call(_TABLE, "GET")

        existing = r.json().get("records", [])
        if existing:
            record_id = existing[0]["id"]
            patch = requests.patch(
                _url(record_id),
                headers=_headers(json_body=True),
                json={"fields": fields},
                timeout=_TIMEOUT,
            )
            patch.raise_for_status()
            log_api_call(_TABLE, "PATCH")
            return record_id

        post = requests.post(
            _url(),
            headers=_headers(json_body=True),
            json={"fields": fields},
            timeout=_TIMEOUT,
        )
        post.raise_for_status()
        log_api_call(_TABLE, "POST")
        return post.json().get("id", "")
