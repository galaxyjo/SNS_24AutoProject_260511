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
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPORTED = "EXPORTED"


class InstagramPostStatus(str, Enum):
    READY     = "ready"
    UPLOADING = "uploading"
    POSTED    = "posted"
    FAILED    = "failed"


# ── TypedDict ─────────────────────────────────────────────────────────────────

class SupplierBlockEntry(TypedDict):
    supplier_name: str
    reason_code:   str


class SourceItemRef(TypedDict):
    source_item_id: str
    content_hash:   str


class SourceItem(TypedDict, total=False):
    source_item_id: str
    content_hash:   str
    image_url:      str
    text:           str
    category_code:  str
    keyword:        str
    quality_status: str
    filter_reason:  str
    collected_at:   str
    pipeline_status: str


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
