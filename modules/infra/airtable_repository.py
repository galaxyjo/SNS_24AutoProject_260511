"""
modules/infra/airtable_repository.py
RepositoryInterface의 Airtable 구현체.

사용법:
    from modules.infra.airtable_repository import AirtableRepository
    repo = AirtableRepository()
    records = repo.fetch_all("Source_Feeds", filters={"processing_status": "mapped"})
    repo.update("Source_Feeds", "recXXX", {"processing_status": "rejected"})
"""
import os
import requests
from dotenv import load_dotenv
from pathlib import Path

from modules.infra.repository_interface import RepositoryInterface
from modules.infra.airtable_usage_logger import log_api_call

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=True)

_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
_BASE_URL = f"https://api.airtable.com/v0/{_BASE_ID}"
_TIMEOUT = 30


def _headers(json_body: bool = False) -> dict:
    h = {"Authorization": f"Bearer {_API_KEY}"}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def _formula_from_filters(filters: dict) -> str:
    """{'field': 'value', ...} → AND({field}='value', ...) 형식 Airtable 수식."""
    if not filters:
        return ""
    parts = [f"{{{k}}}='{v}'" for k, v in filters.items()]
    return f"AND({','.join(parts)})" if len(parts) > 1 else parts[0]


class AirtableRepository(RepositoryInterface):
    """Airtable REST API 기반 Repository 구현체."""

    def _url(self, table_name: str, record_id: str = "") -> str:
        base = f"{_BASE_URL}/{requests.utils.quote(table_name)}"
        return f"{base}/{record_id}" if record_id else base

    def fetch_one(
        self,
        table_name: str,
        filters: dict | None = None,
    ) -> dict | None:
        params: dict = {"maxRecords": 1}
        if filters:
            params["filterByFormula"] = _formula_from_filters(filters)

        r = requests.get(self._url(table_name), headers=_headers(), params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        log_api_call(table_name, "GET")
        records = r.json().get("records", [])
        return records[0] if records else None

    def fetch_all(
        self,
        table_name: str,
        filters: dict | None = None,
        fields: list[str] | None = None,
    ) -> list[dict]:
        params: dict = {"pageSize": 100}
        if filters:
            params["filterByFormula"] = _formula_from_filters(filters)
        if fields:
            for i, f in enumerate(fields):
                params[f"fields[{i}]"] = f

        records, offset = [], None
        while True:
            if offset:
                params["offset"] = offset
            r = requests.get(self._url(table_name), headers=_headers(), params=params, timeout=_TIMEOUT)
            r.raise_for_status()
            log_api_call(table_name, "GET")
            data = r.json()
            records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break
        return records

    def update(
        self,
        table_name: str,
        record_id: str,
        data: dict,
    ) -> dict:
        r = requests.patch(
            self._url(table_name, record_id),
            headers=_headers(json_body=True),
            json={"fields": data},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        log_api_call(table_name, "PATCH")
        return r.json()

    def insert(
        self,
        table_name: str,
        data: dict,
    ) -> dict:
        r = requests.post(
            self._url(table_name),
            headers=_headers(json_body=True),
            json={"fields": data},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        log_api_call(table_name, "POST")
        return r.json()

    def delete(
        self,
        table_name: str,
        record_id: str,
    ) -> bool:
        r = requests.delete(
            self._url(table_name, record_id),
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        log_api_call(table_name, "DELETE")
        return r.json().get("deleted", False)
