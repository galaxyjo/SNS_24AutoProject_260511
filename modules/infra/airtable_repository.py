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
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from modules.infra.airtable_usage_logger import log_api_call
from modules.infra.repository_interface import (
    CrawlTarget,
    InstagramPost,
    InstagramPostStatus,
    LeadBridgeStatus,
    LeadInteraction,
    LeadInteractionCreate,
    PostPublishResult,
    RepositoryError,
    RepositoryInterface,
    RepositoryNotFoundError,
    RepositoryUnavailableError,
    RepositoryValidationError,
    ReviewStatus,
    SourceItem,
    SourceItemRef,
    SourceItemStatus,
    SupplierBlockEntry,
    TrainingCandidate,
)

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=True)

_API_KEY  = os.getenv("AIRTABLE_API_KEY", "")
_BASE_ID  = os.getenv("AIRTABLE_BASE_ID", "")
_BASE_URL = f"https://api.airtable.com/v0/{_BASE_ID}"
_META_URL = f"https://api.airtable.com/v0/meta/bases/{_BASE_ID}/tables"
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
    retry_after: float | None = None
    if exc.response is not None:
        ra = exc.response.headers.get("Retry-After")
        if ra:
            try:
                retry_after = float(ra)
            except ValueError:
                retry_after = None
    if status in (401, 403):
        raise RepositoryUnavailableError(
            f"[{table}] 인증 오류 {status}: {body}", status_code=status, retry_after_seconds=retry_after,
        ) from exc
    if status == 404:
        raise RepositoryNotFoundError(
            f"[{table}] 레코드 없음: {body}", status_code=status, retry_after_seconds=retry_after,
        ) from exc
    if status == 422:
        raise RepositoryValidationError(
            f"[{table}] 입력 오류: {body}", status_code=status, retry_after_seconds=retry_after,
        ) from exc
    raise RepositoryError(
        f"[{table}] HTTP {status}: {body}", status_code=status, retry_after_seconds=retry_after,
    ) from exc


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
                    author_name=f.get("author_name", ""),
                    page_name=f.get("page_name", ""),
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
                    "filterByFormula": "AND({status}='Active', NOT({collection_purpose}='training'))",
                    "fields[0]": "target_url",
                    "fields[1]": "platform",
                    "fields[2]": "target_id",
                    "fields[3]": "keyword",
                    "fields[4]": "category_code",
                    "fields[5]": "max_posts",
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
                        target_id=f.get("target_id", ""),
                        keyword=f.get("keyword", ""),
                        category_code=f.get("category_code", ""),
                        max_posts=int(f.get("max_posts", 10)),
                    )
                )
        return result

    # ── 4-1. 학습용(training) 크롤 대상 조회 ─────────────────────────────────

    def fetch_active_training_targets(self, platform: str) -> list[CrawlTarget]:
        try:
            r = requests.get(
                _url("Crawl_Targets"),
                headers=_headers(),
                params={
                    "filterByFormula": (
                        f"AND({{status}}='Active', {{collection_purpose}}='training', {{platform}}='{platform}')"
                    ),
                    "fields[0]": "target_url",
                    "fields[1]": "platform",
                    "fields[2]": "target_id",
                    "fields[3]": "keyword",
                    "fields[4]": "category_code",
                    "fields[5]": "max_posts",
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
                        platform=f.get("platform", ""),
                        target_id=f.get("target_id", ""),
                        keyword=f.get("keyword", ""),
                        category_code=f.get("category_code", ""),
                        max_posts=int(f.get("max_posts", 10)),
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

    def fetch_posted_with_media_id(self, limit: int = 10) -> list[dict]:
        try:
            r = requests.get(
                _url("Instagram_Posts"),
                headers=_headers(),
                params={
                    "filterByFormula": "AND({post_status}='posted', {ig_media_id}!='')",
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
        records = r.json().get("records", [])
        records.sort(key=lambda rec: rec.get("createdTime", ""), reverse=True)
        return records

    def fetch_posted_missing_media_id(self) -> list[dict]:
        try:
            r = requests.get(
                _url("Instagram_Posts"),
                headers=_headers(),
                params={
                    "filterByFormula": "AND({post_status}='posted', {ig_media_id}='')",
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Instagram_Posts", "GET")
        except requests.HTTPError as e:
            _raise(e, "Instagram_Posts")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e
        records = r.json().get("records", [])
        return [{"id": rec["id"], **rec.get("fields", {})} for rec in records]

    def fetch_all_instagram_posts(self) -> list[dict]:
        try:
            r = requests.get(
                _url("Instagram_Posts"),
                headers=_headers(),
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Instagram_Posts", "GET")
        except requests.HTTPError as e:
            _raise(e, "Instagram_Posts")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e
        return [{"id": rec["id"], **rec.get("fields", {})} for rec in r.json().get("records", [])]

    def fetch_all_lead_interactions(self, since_utc: str | None = None) -> list[dict]:
        params = {}
        if since_utc:
            params["filterByFormula"] = f"{{relay_scheduled_at}}>='{since_utc}'"
        try:
            r = requests.get(
                _url("Lead_Interactions"),
                headers=_headers(),
                params=params,
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Lead_Interactions", "GET")
        except requests.HTTPError as e:
            _raise(e, "Lead_Interactions")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e
        return [{"id": rec["id"], **rec.get("fields", {})} for rec in r.json().get("records", [])]

    # ── Private: Lead_Interactions PATCH 공통 ────────────────────────────────

    def _patch_lead_interaction(self, record_id: str, fields: dict) -> None:
        try:
            r = requests.patch(
                _url("Lead_Interactions", record_id),
                headers=_headers(json_body=True),
                json={"fields": fields},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Lead_Interactions", "PATCH")
        except requests.HTTPError as e:
            _raise(e, "Lead_Interactions")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

    # ── 11. 기준 단가 조회 ────────────────────────────────────────────────────

    def get_base_price(self) -> float | None:
        try:
            r = requests.get(
                _url("Instagram_Posts"),
                headers=_headers(),
                params={
                    "filterByFormula":    "{price}>0",
                    "sort[0][field]":     "scheduled_upload_at",
                    "sort[0][direction]": "desc",
                    "maxRecords":         1,
                    "fields[0]":          "price",
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Instagram_Posts", "GET")
        except requests.HTTPError as e:
            _raise(e, "Instagram_Posts")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        records = r.json().get("records", [])
        if records:
            price = records[0].get("fields", {}).get("price")
            if price is not None:
                return float(price)
        return None

    # ── 12. 최근 자동응답 중복 확인 ───────────────────────────────────────────

    def has_recent_auto_reply(self, igsid: str, within_minutes: int = 3) -> bool:
        from datetime import timedelta
        cutoff = (
            datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        safe    = igsid.replace("'", "\\'")
        formula = (
            f"AND({{inquiry_user_handle}}='{safe}',"
            f"{{bridge_status}}='auto_replied',"
            f"IS_AFTER(CREATED_TIME(),'{cutoff}'))"
        )
        try:
            r = requests.get(
                _url("Lead_Interactions"),
                headers=_headers(),
                params={"filterByFormula": formula, "maxRecords": 1, "fields[0]": "replied_at"},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Lead_Interactions", "GET")
        except requests.HTTPError as e:
            _raise(e, "Lead_Interactions")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        return bool(r.json().get("records"))

    # ── 13. Lead Interaction 생성 ─────────────────────────────────────────────

    def create_lead_interaction(self, data: LeadInteractionCreate) -> str:
        source = data.get("source", "instagram_dm")
        prefix = "CM" if source == "instagram_comment" else "LI"
        code   = f"{prefix}-" + uuid.uuid4().hex[:8].upper()
        fields = {
            "interaction_code":     code,
            "inquiry_user_handle":  data["igsid"],
            "bridge_status":        data["interaction_type"],
            "lead_status":          "new",
            "conversation_channel": source,
            "relay_scheduled_at":   data["occurred_at"],
            "inquiry_message":      data.get("inquiry_message", ""),
        }
        if data.get("source_event_id"):
            fields["source_event_id"] = data["source_event_id"]
        try:
            r = requests.post(
                _url("Lead_Interactions"),
                headers=_headers(json_body=True),
                json={"fields": fields},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Lead_Interactions", "POST")
        except requests.HTTPError as e:
            _raise(e, "Lead_Interactions")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        return r.json().get("id", "")

    # ── FP-047: 댓글 이벤트 idempotency 조회 ────────────────────────────────────

    def find_lead_interaction_by_source_event(self, source: str, source_event_id: str) -> str | None:
        """LOOKUP_FAILED(네트워크/타임아웃 등)는 예외로 그대로 전파됨 —
        호출부가 None(NOT_FOUND)과 구분해서 처리해야 한다."""
        safe_source = source.replace("'", "\\'")
        safe_event  = source_event_id.replace("'", "\\'")
        formula = f"AND({{conversation_channel}}='{safe_source}',{{source_event_id}}='{safe_event}')"
        try:
            r = requests.get(
                _url("Lead_Interactions"),
                headers=_headers(),
                params={"filterByFormula": formula, "maxRecords": 1, "fields[0]": "source_event_id"},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Lead_Interactions", "GET")
        except requests.HTTPError as e:
            _raise(e, "Lead_Interactions")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        records = r.json().get("records", [])
        return records[0]["id"] if records else None

    # ── FP-047/Package1 enforce 전제조건 B: Airtable 필드 존재 startup preflight ──

    def verify_field_exists(self, table: str, field_name: str) -> bool:
        """Metadata API(`/v0/meta/bases/{base}/tables`)로 조회 — 이 프로젝트에서 사람이
        Airtable UI에서 실수로 필드를 지운 전례(caption/retry_count 등)가 반복됐던 것에
        대한 startup 방어선. 조회 실패(네트워크/권한 등)는 예외로 전파 — 호출부가
        False(필드 없음 확인됨)와 구분해서 fail-closed 판단에 반영해야 한다."""
        try:
            r = requests.get(_META_URL, headers=_headers(), timeout=_TIMEOUT)
            r.raise_for_status()
            log_api_call(table, "META_GET")
        except requests.HTTPError as e:
            _raise(e, table)
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        for t in r.json().get("tables", []):
            if t["name"] == table:
                return any(f["name"] == field_name for f in t.get("fields", []))
        return False  # 테이블 자체가 없으면 필드도 당연히 없음

    # ── 14. 재문의 여부 확인 ──────────────────────────────────────────────────

    def is_repeat_inquiry(self, igsid: str) -> bool:
        safe    = igsid.replace("'", "\\'")
        formula = (
            f"AND({{inquiry_user_handle}}='{safe}',"
            f"NOT({{bridge_status}}='dm_received'))"
        )
        try:
            r = requests.get(
                _url("Lead_Interactions"),
                headers=_headers(),
                params={
                    "filterByFormula": formula,
                    "maxRecords":      1,
                    "fields[0]":       "inquiry_user_handle",
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Lead_Interactions", "GET")
        except requests.HTTPError as e:
            _raise(e, "Lead_Interactions")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        return bool(r.json().get("records"))

    # ── 15. 팔로업 / LOST 대상 조회 ──────────────────────────────────────────

    def fetch_leads_due(
        self,
        statuses: list[LeadBridgeStatus],
        before_iso: str,
        limit: int = 20,
    ) -> list[LeadInteraction]:
        or_parts = ",".join(f"{{bridge_status}}='{s.value}'" for s in statuses)
        formula  = f"AND(OR({or_parts}),{{relay_scheduled_at}}<='{before_iso}')"
        try:
            r = requests.get(
                _url("Lead_Interactions"),
                headers=_headers(),
                params={
                    "filterByFormula":    formula,
                    "sort[0][field]":     "relay_scheduled_at",
                    "sort[0][direction]": "asc",
                    "maxRecords":         limit,
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Lead_Interactions", "GET")
        except requests.HTTPError as e:
            _raise(e, "Lead_Interactions")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        result: list[LeadInteraction] = []
        for rec in r.json().get("records", []):
            f = rec.get("fields", {})
            result.append(LeadInteraction(
                id=rec["id"],
                igsid=f.get("inquiry_user_handle", ""),
                bridge_status=f.get("bridge_status", ""),
                lead_status=f.get("lead_status", ""),
                relay_scheduled_at=f.get("relay_scheduled_at", ""),
            ))
        return result

    # ── 16. 오늘 Lead 목록 조회 (일일 리포트용) ──────────────────────────────

    def fetch_today_lead_stats(self, since_utc: str, limit: int = 200) -> list[LeadInteraction]:
        formula = f"{{relay_scheduled_at}}>='{since_utc}'"
        try:
            r = requests.get(
                _url("Lead_Interactions"),
                headers=_headers(),
                params={
                    "filterByFormula": formula,
                    "maxRecords":      limit,
                    "fields[0]":       "lead_status",
                    "fields[1]":       "lead_grade",
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Lead_Interactions", "GET")
        except requests.HTTPError as e:
            _raise(e, "Lead_Interactions")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        result: list[LeadInteraction] = []
        for rec in r.json().get("records", []):
            f = rec.get("fields", {})
            result.append(LeadInteraction(
                id=rec["id"],
                igsid="",
                bridge_status=f.get("bridge_status", ""),
                lead_status=f.get("lead_status", ""),
                lead_grade=f.get("lead_grade", "cold"),
                relay_scheduled_at="",
            ))
        return result

    # ── 17. 자동응답 완료 상태 갱신 ──────────────────────────────────────────

    def update_lead_replied(self, record_id: str, delay_sec: int) -> None:
        self._patch_lead_interaction(record_id, {
            "bridge_status":      LeadBridgeStatus.AUTO_REPLIED.value,
            "lead_status":        "qualified",
            "replied_at":         datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "response_delay_sec": delay_sec,
            "last_error_msg":     "",
        })

    # ── 18. Lead 스코어 갱신 ──────────────────────────────────────────────────

    def update_lead_score(self, record_id: str, score: int, grade: str) -> None:
        self._patch_lead_interaction(record_id, {
            "lead_score": score,
            "lead_grade": grade,
        })

    # ── 19. 팔로업 단계 갱신 ─────────────────────────────────────────────────

    def update_followup_status(
        self,
        record_id: str,
        status: LeadBridgeStatus,
        next_scheduled_at: str | None = None,
    ) -> None:
        fields: dict = {"bridge_status": status.value, "last_error_msg": ""}
        if next_scheduled_at:
            fields["relay_scheduled_at"] = next_scheduled_at
        self._patch_lead_interaction(record_id, fields)

    # ── 20. LOST 처리 ─────────────────────────────────────────────────────────

    def mark_lead_lost(self, record_id: str, reason: str = "followup_timeout") -> None:
        self._patch_lead_interaction(record_id, {
            "bridge_status": LeadBridgeStatus.LOST.value,
            "lead_status":   "disqualified",
            "lost_reason":   reason,
            "lost_at":       datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

    # ── 21. CLOSE 처리 ────────────────────────────────────────────────────────

    def mark_lead_closed(self, record_id: str) -> None:
        self._patch_lead_interaction(record_id, {
            "bridge_status": LeadBridgeStatus.CLOSED.value,
            "lead_status":   "converted",
            "closed_at":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

    # ── 22. 주문 전환 처리 ────────────────────────────────────────────────────

    def mark_lead_converted(self, record_id: str) -> None:
        self._patch_lead_interaction(record_id, {
            "bridge_status": LeadBridgeStatus.CONVERTED.value,
            "lead_status":   "converted",
            "converted_at":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

    # ── 23. export용 Source_Items 배치 조회 ──────────────────────────────────

    def fetch_source_items_for_export(
        self,
        batch_size: int = 3,
        target_id: str | None = None,
    ) -> list[SourceItem]:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        parts = [
            "{quality_status}='READY'",
            "{pipeline_status}='NEW'",
            f"OR({{export_next_retry_at}}='',{{export_next_retry_at}}<='{now_iso}')",
        ]
        if target_id:
            parts.append(f"{{target_id}}='{target_id}'")
        formula = "AND(" + ",".join(parts) + ")"
        try:
            r = requests.get(
                _url("Source_Items"),
                headers=_headers(),
                params={"filterByFormula": formula, "maxRecords": batch_size},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Source_Items", "GET")
        except requests.HTTPError as e:
            _raise(e, "Source_Items")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        result: list[SourceItem] = []
        for rec in r.json().get("records", []):
            f = rec.get("fields", {})
            result.append(SourceItem(
                record_id=rec["id"],
                source_item_id=f.get("source_item_id", ""),
                title=f.get("title", ""),
                image_url=f.get("image_url", ""),
                source_url=f.get("source_url", ""),
                target_id=f.get("target_id", ""),
                export_retry_count=int(f.get("export_retry_count", 0)),
            ))
        return result

    # ── 24. STALE QUEUED → NEW 복구 ───────────────────────────────────────────

    def recover_stale_queued_source_items(self, threshold_iso: str) -> int:
        formula = (
            f"AND({{pipeline_status}}='QUEUED',"
            f"{{export_started_at}}!='',"
            f"{{export_started_at}}<'{threshold_iso}')"
        )
        try:
            r = requests.get(
                _url("Source_Items"),
                headers=_headers(),
                params={"filterByFormula": formula, "maxRecords": 50},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Source_Items", "GET")
        except requests.HTTPError as e:
            _raise(e, "Source_Items")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        count = 0
        for rec in r.json().get("records", []):
            try:
                patch = requests.patch(
                    _url("Source_Items", rec["id"]),
                    headers=_headers(json_body=True),
                    json={"fields": {"pipeline_status": "NEW", "export_last_error": "STALE_QUEUED_RECOVERED"}},
                    timeout=_TIMEOUT,
                )
                patch.raise_for_status()
                log_api_call("Source_Items", "PATCH")
                count += 1
            except Exception:
                pass
        return count

    # ── 25. export 선점 (NEW → QUEUED) ────────────────────────────────────────

    def claim_source_item_for_export(self, record_id: str, started_at_iso: str) -> None:
        try:
            r = requests.patch(
                _url("Source_Items", record_id),
                headers=_headers(json_body=True),
                json={"fields": {"pipeline_status": "QUEUED", "export_started_at": started_at_iso}},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Source_Items", "PATCH")
        except requests.HTTPError as e:
            _raise(e, "Source_Items")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

    # ── 26. export 재시도 필드 갱신 ───────────────────────────────────────────

    def update_source_item_retry(
        self,
        record_id: str,
        error_code: str,
        retry_count: int,
        next_retry_iso: str,
    ) -> None:
        status = "FAILED" if retry_count >= 3 else "NEW"
        try:
            r = requests.patch(
                _url("Source_Items", record_id),
                headers=_headers(json_body=True),
                json={"fields": {
                    "pipeline_status":      status,
                    "export_retry_count":   retry_count,
                    "export_last_error":    error_code,
                    "export_next_retry_at": next_retry_iso,
                }},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Source_Items", "PATCH")
        except requests.HTTPError as e:
            _raise(e, "Source_Items")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

    # ── 27. Training_Review_Queue 신규 후보 저장 ─────────────────────────────

    def insert_training_candidate(self, candidate: TrainingCandidate) -> str:
        if not candidate.get("image_url"):
            raise RepositoryValidationError("image_url 필수")
        payload = {k: v for k, v in candidate.items() if k != "record_id" and v is not None}
        payload.setdefault("review_status", ReviewStatus.PENDING.value)
        try:
            r = requests.post(
                _url("Training_Review_Queue"),
                headers=_headers(json_body=True),
                json={"fields": payload},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Training_Review_Queue", "POST")
        except requests.HTTPError as e:
            _raise(e, "Training_Review_Queue")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        return r.json().get("id", "")

    # ── 28. 완전동일(SHA256) 중복 확인 ────────────────────────────────────────

    def exists_candidate_by_hash(self, image_hash: str) -> bool:
        try:
            r = requests.get(
                _url("Training_Review_Queue"),
                headers=_headers(),
                params={
                    "filterByFormula": f"{{image_hash}}='{image_hash}'",
                    "maxRecords": 1,
                    "fields[0]": "image_hash",
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Training_Review_Queue", "GET")
        except requests.HTTPError as e:
            _raise(e, "Training_Review_Queue")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        return bool(r.json().get("records"))

    # ── 29. 근사중복(phash) 비교용 목록 조회 ──────────────────────────────────

    def fetch_candidate_phashes(self, limit: int = 2000) -> list[str]:
        # NOTE: offset 페이지네이션 미구현(기존 코드베이스 공통 한계, kpi_collector.py 등과 동일) —
        # 단일 요청 기준 최대 100건(Airtable pageSize 상한)만 반환됨.
        try:
            r = requests.get(
                _url("Training_Review_Queue"),
                headers=_headers(),
                params={
                    "filterByFormula": "NOT({phash}='')",
                    "pageSize": min(limit, 100),
                    "fields[0]": "phash",
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Training_Review_Queue", "GET")
        except requests.HTTPError as e:
            _raise(e, "Training_Review_Queue")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        return [
            rec["fields"]["phash"]
            for rec in r.json().get("records", [])
            if rec.get("fields", {}).get("phash")
        ]

    # ── 30. 리뷰 대기 후보 1건 조회 ───────────────────────────────────────────

    def fetch_next_pending_candidate(self) -> TrainingCandidate | None:
        try:
            r = requests.get(
                _url("Training_Review_Queue"),
                headers=_headers(),
                params={
                    "filterByFormula":    f"{{review_status}}='{ReviewStatus.PENDING.value}'",
                    "sort[0][field]":     "collected_at",
                    "sort[0][direction]": "asc",
                    "maxRecords":         1,
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Training_Review_Queue", "GET")
        except requests.HTTPError as e:
            _raise(e, "Training_Review_Queue")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        records = r.json().get("records", [])
        if not records:
            return None
        rec = records[0]
        f = rec.get("fields", {})
        return TrainingCandidate(
            record_id=rec["id"],
            candidate_id=f.get("candidate_id", ""),
            target_id_ref=f.get("target_id_ref", ""),
            source_platform=f.get("source_platform", ""),
            search_query=f.get("search_query", ""),
            source_url=f.get("source_url", ""),
            image_url=f.get("image_url", ""),
            text_content=f.get("text_content", ""),
            review_status=f.get("review_status", ""),
            storage_key=f.get("storage_key", ""),
            mime_type=f.get("mime_type", ""),
            post_id=f.get("post_id", ""),
            seller_id=f.get("seller_id", ""),
            permission_status=f.get("permission_status", ""),
            candidate_block_override=f.get("candidate_block_override", ""),
        )

    # ── 30-1. 리뷰 대기 후보 다건 조회 (그리드 일괄 리뷰용) ───────────────────

    def fetch_pending_candidates(self, limit: int = 50) -> list[TrainingCandidate]:
        try:
            r = requests.get(
                _url("Training_Review_Queue"),
                headers=_headers(),
                params={
                    "filterByFormula":    f"{{review_status}}='{ReviewStatus.PENDING.value}'",
                    "sort[0][field]":     "collected_at",
                    "sort[0][direction]": "asc",
                    "maxRecords":         limit,
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Training_Review_Queue", "GET")
        except requests.HTTPError as e:
            _raise(e, "Training_Review_Queue")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        result: list[TrainingCandidate] = []
        for rec in r.json().get("records", []):
            f = rec.get("fields", {})
            result.append(TrainingCandidate(
                record_id=rec["id"],
                candidate_id=f.get("candidate_id", ""),
                target_id_ref=f.get("target_id_ref", ""),
                source_platform=f.get("source_platform", ""),
                image_url=f.get("image_url", ""),
                text_content=f.get("text_content", ""),
                review_status=f.get("review_status", ""),
            ))
        return result

    # ── 31. 사람 판정(PASS/BLOCK) 저장 ────────────────────────────────────────
    # NOTE: review_status='PASS'는 시각적·사업적 적합성 판정일 뿐 사용 권한이 아니다.
    # 이 메서드는 permission_status/ml_training_allowed/sns_reuse_allowed를 건드리지 않는다 —
    # 실제 학습/재사용 소비 코드가 그 필드들을 별도로 확인해야 한다.

    def save_review_decision(self, record_id: str, decision: str, other_note: str = "") -> None:
        payload = {
            "review_status": decision,
            "reviewed_at":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "other_note":    other_note,
        }
        try:
            r = requests.patch(
                _url("Training_Review_Queue", record_id),
                headers=_headers(json_body=True),
                json={"fields": payload},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Training_Review_Queue", "PATCH")
        except requests.HTTPError as e:
            _raise(e, "Training_Review_Queue")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

    # ── 31a-batch. 사람 판정(PASS/BLOCK) 배치 저장 — 최대 10건/호출 ─────────────
    # Airtable 배치 PATCH(요청당 최대 10건)로 순차 개별 PATCH 대비 호출 횟수를 줄인다.
    # 이 청크의 원자성(부분 성공 없음)은 Airtable 공식 문서로 확인되지 않았다 — 특히
    # 타임아웃/커넥션 오류는 응답만 유실됐을 뿐 서버에는 실제로 반영됐을 수 있다.
    # 호출자(review_batch_committer._save_all)가 저장 예외 발생 시 배치 GET으로
    # 실제 반영 여부를 재확인한 뒤에만 최종 성공/실패를 판정한다.

    _BATCH_CHUNK_SIZE = 10

    def batch_save_review_decisions(self, updates: list[dict]) -> None:
        if not updates:
            return
        if len(updates) > self._BATCH_CHUNK_SIZE:
            raise RepositoryValidationError(
                f"batch_save_review_decisions: 최대 {self._BATCH_CHUNK_SIZE}건, 받음 {len(updates)}건"
            )
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        records = [
            {
                "id": u["record_id"],
                "fields": {
                    "review_status": u["decision"],
                    "reviewed_at":   now,
                    "other_note":    u.get("other_note", ""),
                },
            }
            for u in updates
        ]
        try:
            r = requests.patch(
                _url("Training_Review_Queue"),
                headers=_headers(json_body=True),
                json={"records": records},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Training_Review_Queue", "PATCH")
        except requests.HTTPError as e:
            _raise(e, "Training_Review_Queue")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e), original_error_type=type(e).__name__) from e

    # ── 31b-batch. 배치 GET 재검증 — 최대 10건/호출 ─────────────────────────────

    def batch_get_review_status(self, record_ids: list[str]) -> dict:
        if not record_ids:
            return {}
        if len(record_ids) > self._BATCH_CHUNK_SIZE:
            raise RepositoryValidationError(
                f"batch_get_review_status: 최대 {self._BATCH_CHUNK_SIZE}건, 받음 {len(record_ids)}건"
            )
        formula = "OR(" + ",".join(f"RECORD_ID()='{rid}'" for rid in record_ids) + ")"
        try:
            r = requests.get(
                _url("Training_Review_Queue"),
                headers=_headers(),
                params={
                    "filterByFormula": formula,
                    "pageSize":        self._BATCH_CHUNK_SIZE,
                    "fields[0]":       "review_status",
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Training_Review_Queue", "GET")
        except requests.HTTPError as e:
            _raise(e, "Training_Review_Queue")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e), original_error_type=type(e).__name__) from e

        result: dict = {}
        for rec in r.json().get("records", []):
            result[rec["id"]] = rec.get("fields", {}).get("review_status")
        return result

    # ── 31b. 저장 직후 GET 재검증용 — 현재 review_status 재조회 ──────────────

    def get_review_status(self, record_id: str) -> str | None:
        try:
            r = requests.get(
                _url("Training_Review_Queue", record_id),
                headers=_headers(),
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Training_Review_Queue", "GET")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            _raise(e, "Training_Review_Queue")
        except requests.RequestException as e:
            # 상태 코드가 없는 네트워크 예외(타임아웃 등) — 원래 예외 종류를 보존해서
            # review_batch_committer가 "Timeout"류만 재시도 대상으로 분류할 수 있게 한다.
            raise RepositoryUnavailableError(str(e), original_error_type=type(e).__name__) from e

        return r.json().get("fields", {}).get("review_status")

    # ── 32. 상태별 후보 건수 (진행률 카운터) ──────────────────────────────────

    def count_candidates_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        offset = None
        while True:
            params = {"fields[0]": "review_status", "pageSize": 100}
            if offset:
                params["offset"] = offset
            try:
                r = requests.get(
                    _url("Training_Review_Queue"),
                    headers=_headers(),
                    params=params,
                    timeout=_TIMEOUT,
                )
                r.raise_for_status()
                log_api_call("Training_Review_Queue", "GET")
            except requests.HTTPError as e:
                _raise(e, "Training_Review_Queue")
            except requests.RequestException as e:
                raise RepositoryUnavailableError(str(e)) from e

            data = r.json()
            for rec in data.get("records", []):
                status = rec.get("fields", {}).get("review_status", "UNKNOWN")
                counts[status] = counts.get(status, 0) + 1

            offset = data.get("offset")
            if not offset:
                break
        return counts
