"""
modules/infra/airtable_repository.py
RepositoryInterface의 Airtable REST API 구현체.

사용법:
    from modules.infra.airtable_repository import AirtableRepository
    repo = AirtableRepository()
    targets = repo.fetch_active_crawl_targets()
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from modules.infra.airtable_usage_logger import log_api_call
from modules.infra.repository_interface import (
    CrawlTarget,
    InstagramPost,
    InstagramPostStatus,
    PostPublishResult,
    RepositoryError,
    RepositoryInterface,
    RepositoryNotFoundError,
    RepositoryUnavailableError,
    RepositoryValidationError,
    SourceItem,
    SourceItemRef,
    SourceItemStatus,
    SupplierBlockEntry,
)

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=True)

_API_KEY  = os.getenv("AIRTABLE_API_KEY", "")
_BASE_ID  = os.getenv("AIRTABLE_BASE_ID", "")
_BASE_URL = f"https://api.airtable.com/v0/{_BASE_ID}"
_TIMEOUT  = 30


def _headers(json_body: bool = False) -> dict:
    h = {"Authorization": f"Bearer {_API_KEY}"}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def _url(table: str, record_id: str = "") -> str:
    base = f"{_BASE_URL}/{requests.utils.quote(table)}"
    return f"{base}/{record_id}" if record_id else base


def _raise(exc: requests.HTTPError, table: str) -> None:
    status = exc.response.status_code if exc.response is not None else 0
    body   = exc.response.text[:200] if exc.response is not None else ""
    if status in (401, 403):
        raise RepositoryUnavailableError(f"[{table}] 인증 오류 {status}: {body}") from exc
    if status == 404:
        raise RepositoryNotFoundError(f"[{table}] 레코드 없음: {body}") from exc
    if status == 422:
        raise RepositoryValidationError(f"[{table}] 입력 오류: {body}") from exc
    raise RepositoryError(f"[{table}] HTTP {status}: {body}") from exc


def _image_url_hash(image_url: str) -> str:
    import re
    m = re.search(r"/(\d+_\d+(?:_\d+)*)[_.]", image_url)
    key = m.group(1) if m else image_url
    return hashlib.sha256(key.encode()).hexdigest()


class AirtableRepository(RepositoryInterface):
    """Airtable REST API 기반 RepositoryInterface 구현체."""

    # ── 1. 차단 공급업체 목록 ──────────────────────────────────────────────────

    def list_blocked_suppliers(self) -> list[SupplierBlockEntry]:
        try:
            r = requests.get(
                _url("Supplier_Blocklist"),
                headers=_headers(),
                params={"pageSize": 100},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Supplier_Blocklist", "GET")
        except requests.HTTPError as e:
            _raise(e, "Supplier_Blocklist")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        result: list[SupplierBlockEntry] = []
        for rec in r.json().get("records", []):
            f = rec.get("fields", {})
            result.append(
                SupplierBlockEntry(
                    supplier_name=f.get("supplier_name", ""),
                    reason_code=f.get("reason_code", ""),
                )
            )
        return result

    # ── 2. 이미지 URL 중복 확인 ───────────────────────────────────────────────

    def exists_post_by_image_url(self, image_url: str) -> bool:
        h = _image_url_hash(image_url)
        try:
            r = requests.get(
                _url("Instagram_Posts"),
                headers=_headers(),
                params={"filterByFormula": f"{{image_url_hash}}='{h}'", "maxRecords": 1},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Instagram_Posts", "GET")
        except requests.HTTPError as e:
            _raise(e, "Instagram_Posts")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        return bool(r.json().get("records"))

    # ── 3. Instagram 게시물 저장 ──────────────────────────────────────────────

    def save_instagram_post(self, post: SourceItem) -> str:
        if not post.get("image_url"):
            raise RepositoryValidationError("image_url 필수")
        payload = {k: v for k, v in post.items() if v is not None}
        payload.setdefault("post_status", InstagramPostStatus.READY.value)
        try:
            r = requests.post(
                _url("Instagram_Posts"),
                headers=_headers(json_body=True),
                json={"fields": payload},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Instagram_Posts", "POST")
        except requests.HTTPError as e:
            _raise(e, "Instagram_Posts")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        return r.json().get("id", "")

    # ── 4. 활성 크롤 대상 조회 ────────────────────────────────────────────────

    def fetch_active_crawl_targets(self) -> list[CrawlTarget]:
        try:
            r = requests.get(
                _url("Crawl_Targets"),
                headers=_headers(),
                params={
                    "filterByFormula": "{status}='Active'",
                    "fields[0]": "target_url",
                    "fields[1]": "platform",
                    "pageSize": 100,
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Crawl_Targets", "GET")
        except requests.HTTPError as e:
            _raise(e, "Crawl_Targets")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        result: list[CrawlTarget] = []
        for rec in r.json().get("records", []):
            f = rec.get("fields", {})
            if f.get("target_url"):
                result.append(
                    CrawlTarget(
                        target_url=f["target_url"],
                        platform=f.get("platform", "facebook"),
                    )
                )
        return result

    # ── 5. content_hash로 Source_Item 조회 ───────────────────────────────────

    def find_source_item_by_hash(self, content_hash: str) -> SourceItemRef | None:
        try:
            r = requests.get(
                _url("Source_Items"),
                headers=_headers(),
                params={
                    "filterByFormula": f"{{content_hash}}='{content_hash}'",
                    "maxRecords": 1,
                    "fields[0]": "source_item_id",
                    "fields[1]": "content_hash",
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Source_Items", "GET")
        except requests.HTTPError as e:
            _raise(e, "Source_Items")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        records = r.json().get("records", [])
        if not records:
            return None
        f = records[0].get("fields", {})
        return SourceItemRef(
            source_item_id=f.get("source_item_id", records[0]["id"]),
            content_hash=f.get("content_hash", content_hash),
        )

    # ── 6. Source_Item 저장 ───────────────────────────────────────────────────

    def save_source_item(self, item: SourceItem) -> str:
        if not item.get("content_hash"):
            raise RepositoryValidationError("content_hash 필수")
        payload = {k: v for k, v in item.items() if v is not None}
        payload.setdefault("pipeline_status", SourceItemStatus.NEW.value)
        try:
            r = requests.post(
                _url("Source_Items"),
                headers=_headers(json_body=True),
                json={"fields": payload},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Source_Items", "POST")
        except requests.HTTPError as e:
            _raise(e, "Source_Items")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        return r.json().get("id", "")

    # ── 7. Source_Item 상태 갱신 ──────────────────────────────────────────────

    def update_source_item_status(
        self,
        source_item_id: str,
        status: SourceItemStatus,
        reason_code: str = "",
    ) -> None:
        payload: dict = {"pipeline_status": status.value}
        if reason_code:
            payload["filter_reason"] = reason_code
        try:
            r = requests.patch(
                _url("Source_Items", source_item_id),
                headers=_headers(json_body=True),
                json={"fields": payload},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Source_Items", "PATCH")
        except requests.HTTPError as e:
            _raise(e, "Source_Items")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

    # ── 8. 업로드 대기 게시물 조회 ────────────────────────────────────────────

    def fetch_pending_posts(self, limit: int = 10) -> list[InstagramPost]:
        try:
            r = requests.get(
                _url("Instagram_Posts"),
                headers=_headers(),
                params={
                    "filterByFormula": f"{{post_status}}='{InstagramPostStatus.READY.value}'",
                    "maxRecords": limit,
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Instagram_Posts", "GET")
        except requests.HTTPError as e:
            _raise(e, "Instagram_Posts")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        result: list[InstagramPost] = []
        for rec in r.json().get("records", []):
            f = rec.get("fields", {})
            result.append(
                InstagramPost(
                    post_id=rec["id"],
                    image_url=f.get("image_url", f.get("source_url", "")),
                    caption=f.get("caption", ""),
                    hashtag=f.get("hashtag", ""),
                    post_status=f.get("post_status", ""),
                    ig_media_id=f.get("ig_media_id", ""),
                )
            )
        return result

    # ── 9. 업로드 선점 마킹 ───────────────────────────────────────────────────

    def claim_post_for_upload(self, post_id: str) -> bool:
        # WARNING: non-atomic — Airtable은 CAS를 지원하지 않음.
        # 단일 worker 환경에서만 안전. 다중 worker 시 중복 업로드 위험.
        try:
            r = requests.patch(
                _url("Instagram_Posts", post_id),
                headers=_headers(json_body=True),
                json={"fields": {"post_status": InstagramPostStatus.UPLOADING.value}},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Instagram_Posts", "PATCH")
            return True
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return False
            _raise(e, "Instagram_Posts")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e
        return False

    # ── 10. 업로드 결과 기록 ──────────────────────────────────────────────────

    def mark_post_result(self, post_id: str, result: PostPublishResult) -> None:
        status = result.get("status", "")
        payload: dict = {"post_status": status}
        if result.get("platform_post_id"):
            payload["ig_media_id"] = result["platform_post_id"]
        if result.get("error_code"):
            payload["error_code"] = result["error_code"]
        try:
            r = requests.patch(
                _url("Instagram_Posts", post_id),
                headers=_headers(json_body=True),
                json={"fields": payload},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Instagram_Posts", "PATCH")
        except requests.HTTPError as e:
            _raise(e, "Instagram_Posts")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e
