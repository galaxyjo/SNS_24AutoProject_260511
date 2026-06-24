"""
modules/infra/repository_interface.py
도메인 중심 저장소 추상 계약. 구현체(Airtable, SQLite 등)는 이 인터페이스를 따른다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TypedDict


# ── Enum ──────────────────────────────────────────────────────────────────────

class SourceItemStatus(str, Enum):
    NEW      = "NEW"
    QUEUED   = "QUEUED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPORTED = "EXPORTED"


class InstagramPostStatus(str, Enum):
    READY     = "ready"
    UPLOADING = "uploading"
    POSTED    = "posted"
    FAILED    = "failed"


class LeadBridgeStatus(str, Enum):
    DM_RECEIVED     = "dm_received"
    AUTO_REPLIED    = "auto_replied"
    FOLLOWUP1_SENT  = "followup1_sent"
    FOLLOWUP2_SENT  = "followup2_sent"
    FOLLOWUP3_SENT  = "followup3_sent"
    LOST            = "lost"
    CLOSED          = "closed"
    CONVERTED       = "converted"


# ── TypedDict ─────────────────────────────────────────────────────────────────

class SupplierBlockEntry(TypedDict):
    supplier_name: str
    reason_code:   str


class SourceItemRef(TypedDict):
    source_item_id: str
    content_hash:   str


class SourceItem(TypedDict, total=False):
    record_id:            str   # Airtable 내부 record ID (recXXXXX) — PATCH 호출용
    source_item_id:       str
    content_hash:         str
    image_url:            str
    text:                 str
    category_code:        str
    keyword:              str
    quality_status:       str
    filter_reason:        str
    collected_at:         str
    pipeline_status:      str
    title:                str
    source_url:           str
    target_id:            str
    original_image_url:   str
    image_url_hash:       str
    media_type:           str
    export_retry_count:   int
    export_started_at:    str
    export_last_error:    str
    export_next_retry_at: str


class InstagramPost(TypedDict, total=False):
    post_id:     str
    image_url:   str
    caption:     str
    hashtag:     str
    post_status: str
    ig_media_id: str


class CrawlTarget(TypedDict):
    target_url: str
    platform:   str


class PostPublishResult(TypedDict):
    status:           str
    platform_post_id: str
    error_code:       str


class LeadInteraction(TypedDict, total=False):
    id:                  str
    igsid:               str
    bridge_status:       str
    lead_status:         str
    lead_grade:          str
    relay_scheduled_at:  str


class LeadInteractionCreate(TypedDict):
    igsid:            str
    source:           str   # "instagram_dm" | "instagram_comment"
    interaction_type: str
    occurred_at:      str


# ── 예외 ──────────────────────────────────────────────────────────────────────

class RepositoryError(Exception):
    """저장소 기본 예외."""


class RepositoryUnavailableError(RepositoryError):
    """저장소에 연결할 수 없음."""


class RepositoryNotFoundError(RepositoryError):
    """요청한 레코드가 존재하지 않음."""


class RepositoryValidationError(RepositoryError):
    """입력 데이터가 계약을 위반함."""


# ── 인터페이스 ────────────────────────────────────────────────────────────────

class RepositoryInterface(ABC):

    @abstractmethod
    def list_blocked_suppliers(self) -> list[SupplierBlockEntry]:
        """공급업체 차단 목록 전체 반환."""

    @abstractmethod
    def exists_post_by_image_url(self, image_url: str) -> bool:
        """동일 이미지 URL(해시 기반)의 게시물이 이미 존재하는지 확인."""

    @abstractmethod
    def save_instagram_post(self, post: SourceItem) -> str:
        """Instagram_Posts 테이블에 신규 레코드 저장. 생성된 record_id 반환."""

    @abstractmethod
    def fetch_active_crawl_targets(self) -> list[CrawlTarget]:
        """활성 크롤 대상 URL 목록 반환."""

    @abstractmethod
    def find_source_item_by_hash(self, content_hash: str) -> SourceItemRef | None:
        """content_hash로 기존 Source_Item 조회. 없으면 None."""

    @abstractmethod
    def save_source_item(self, item: SourceItem) -> str:
        """Source_Items 테이블에 신규 레코드 저장. 생성된 record_id 반환."""

    @abstractmethod
    def update_source_item_status(
        self,
        source_item_id: str,
        status: SourceItemStatus,
        reason_code: str = "",
    ) -> None:
        """Source_Item 상태 갱신."""

    @abstractmethod
    def fetch_pending_posts(self, limit: int = 10) -> list[InstagramPost]:
        """post_status='ready' 인 게시물 최대 limit 건 반환."""

    @abstractmethod
    def claim_post_for_upload(self, post_id: str) -> bool:
        """post_status를 'uploading'으로 원자적 마킹. 선점 성공 시 True."""

    @abstractmethod
    def mark_post_result(self, post_id: str, result: PostPublishResult) -> None:
        """업로드 결과(성공/실패)를 게시물 레코드에 기록."""

    # ── Lead / DM / Followup ──────────────────────────────────────────────────

    @abstractmethod
    def get_base_price(self) -> float | None:
        """Instagram_Posts에서 price>0 최신값 반환. 없으면 None."""

    @abstractmethod
    def has_recent_auto_reply(self, igsid: str, within_minutes: int = 3) -> bool:
        """igsid 기준 N분 이내 auto_replied 레코드 존재 여부."""

    @abstractmethod
    def create_lead_interaction(self, data: LeadInteractionCreate) -> str:
        """Lead_Interactions 신규 레코드 생성. record_id 반환."""

    @abstractmethod
    def is_repeat_inquiry(self, igsid: str) -> bool:
        """동일 igsid의 dm_received 이외 이전 레코드 존재 여부 (재문의 판단)."""

    @abstractmethod
    def fetch_leads_due(
        self,
        statuses: list[LeadBridgeStatus],
        before_iso: str,
        limit: int = 20,
    ) -> list[LeadInteraction]:
        """relay_scheduled_at <= before_iso 이고 지정 상태인 레코드 목록 반환."""

    @abstractmethod
    def fetch_today_lead_stats(self, since_utc: str, limit: int = 200) -> list[LeadInteraction]:
        """relay_scheduled_at >= since_utc 레코드 목록 반환 (일일 리포트용)."""

    @abstractmethod
    def update_lead_replied(self, record_id: str, delay_sec: int) -> None:
        """bridge_status=auto_replied, lead_status=qualified, replied_at, response_delay_sec 갱신."""

    @abstractmethod
    def update_lead_score(self, record_id: str, score: int, grade: str) -> None:
        """lead_score, lead_grade 갱신."""

    @abstractmethod
    def update_followup_status(
        self,
        record_id: str,
        status: LeadBridgeStatus,
        next_scheduled_at: str | None = None,
    ) -> None:
        """bridge_status 및 relay_scheduled_at 갱신 (팔로업 단계 전진)."""

    @abstractmethod
    def mark_lead_lost(self, record_id: str, reason: str = "followup_timeout") -> None:
        """bridge_status=lost, lead_status=disqualified, lost_reason, lost_at 갱신."""

    @abstractmethod
    def mark_lead_closed(self, record_id: str) -> None:
        """bridge_status=closed, lead_status=converted, closed_at 갱신."""

    @abstractmethod
    def mark_lead_converted(self, record_id: str) -> None:
        """bridge_status=converted, lead_status=converted, converted_at 갱신."""

    # ── Source_Items export pipeline ─────────────────────────────────────────

    @abstractmethod
    def fetch_source_items_for_export(
        self,
        batch_size: int = 3,
        target_id: str | None = None,
    ) -> list[SourceItem]:
        """NEW + READY + retry_at <= now 인 Source_Items batch 반환. record_id 포함."""

    @abstractmethod
    def recover_stale_queued_source_items(self, threshold_iso: str) -> int:
        """QUEUED + export_started_at < threshold → NEW 복구. 처리 건수 반환."""

    @abstractmethod
    def claim_source_item_for_export(self, record_id: str, started_at_iso: str) -> None:
        """pipeline_status → QUEUED, export_started_at 설정."""

    @abstractmethod
    def update_source_item_retry(
        self,
        record_id: str,
        error_code: str,
        retry_count: int,
        next_retry_iso: str,
    ) -> None:
        """retry 카운트·에러·예약시각 갱신. retry_count >= 3 → FAILED, 미만 → NEW."""
