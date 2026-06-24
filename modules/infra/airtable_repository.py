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
