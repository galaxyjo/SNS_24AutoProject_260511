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
    DRAFT     = "draft"
    REJECTED  = "rejected"


class LeadBridgeStatus(str, Enum):
    DM_RECEIVED     = "dm_received"
    AUTO_REPLIED    = "auto_replied"
    FOLLOWUP1_SENT  = "followup1_sent"
    FOLLOWUP2_SENT  = "followup2_sent"
    FOLLOWUP3_SENT  = "followup3_sent"
    LOST            = "lost"
    CLOSED          = "closed"
    CONVERTED       = "converted"


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    PASS    = "PASS"
    BLOCK   = "BLOCK"


# ── TypedDict ─────────────────────────────────────────────────────────────────

class SupplierBlockEntry(TypedDict):
    author_name:   str
    page_name:     str
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
    post_id:          str
    image_url:        str
    caption:          str
    hashtag:          str
    post_status:      str
    ig_media_id:      str
    account_code_ref: str  # 공란=기존 전역 계정 경로, 값 있음=Account_Registry.account_code 참조


class PublishAccount(TypedDict):
    """Account_Registry 조회 결과 — access_token은 절대 포함하지 않는다."""
    account_code:   str
    api_provider:   str
    ig_user_id:     str
    credential_key: str


class CrawlTarget(TypedDict, total=False):
    target_url:    str
    platform:      str
    target_id:     str
    keyword:       str
    category_code: str
    max_posts:     int


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


class TrainingCandidate(TypedDict, total=False):
    """
    review_status='PASS'는 시각적·사업적 적합성 판정일 뿐 사용 권한이 아니다.
    실제 ML 학습 투입 전 ml_training_allowed, 실제 SNS 재사용 전 sns_reuse_allowed를
    반드시 별도 확인해야 한다 — PASS가 권한 필드를 대체하지 않는다.
    """
    record_id:      str   # Airtable 내부 record ID — PATCH 호출용
    candidate_id:   str
    target_id_ref:  str
    source_platform: str
    search_query:   str
    source_url:     str
    image_url:      str   # 원본 이미지 URL — 재호스팅 안 함
    text_content:   str
    image_hash:     str
    phash:          str
    is_duplicate:   bool
    collected_at:   str
    review_status:  str
    other_note:     str
    reviewed_at:    str
    storage_key:    str   # 상대경로: training_snapshots/{sha256}.{ext} — 절대경로 금지
    mime_type:      str
    post_id:        str   # 원본ID 우선, 없으면 canonical URL SHA256 해시, 불가시 빈칸
    seller_id:      str   # 원본 작성자ID 우선, 없으면 정규화 프로필URL SHA256 해시, 불가시 빈칸
    permission_status:         str   # allowed / blocked / unknown — 소스에서 상속
    terms_checked_at:          str
    terms_source_url:          str
    candidate_block_override:  str   # 소스는 allowed여도 이 후보만 개별 차단할 사유


class _LeadInteractionCreateRequired(TypedDict):
    igsid:            str
    source:           str   # "instagram_dm" | "instagram_comment"
    interaction_type: str
    occurred_at:      str
    inquiry_message:  str


class LeadInteractionCreate(_LeadInteractionCreateRequired, total=False):
    source_event_id:  str   # FP-047 idempotency key(선택) — 댓글은 Meta comment_id


# ── 예외 ──────────────────────────────────────────────────────────────────────
# status_code/retry_after_seconds/original_error_type — 260712 GET 재검증 오탐 사고 이후 추가.
# review_batch_committer가 429/5xx/타임아웃만 재시도하고 403/404는 즉시 오류 처리하려면
# 예외에서 HTTP 상태·재시도 대기시간·원래 오류 종류(네트워크 예외가 래핑되어도 보존)를
# 읽을 수 있어야 해서, 공통 예외 계층에 옵션 속성으로 추가했다. 기존 호출부는 그대로 동작.

class RepositoryError(Exception):
    """저장소 기본 예외."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
        original_error_type: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.original_error_type = original_error_type


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
        """활성 크롤 대상 URL 목록 반환 (collection_purpose='training'인 대상은 제외 — 운영 자동게시 파이프라인 전용)."""

    @abstractmethod
    def fetch_active_training_targets(self, platform: str) -> list[CrawlTarget]:
        """collection_purpose='training' 인 활성 크롤 대상만 반환 (사람 리뷰 큐 전용, Instagram_Posts로 가지 않음)."""

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
    def get_publish_account(self, account_code: str) -> PublishAccount | None:
        """account_code로 Account_Registry 조회. 없으면 None. access_token은 반환하지 않는다
        (실제 자격증명은 modules.common.credential_resolver.resolve_credential()로 별도 조회)."""

    @abstractmethod
    def claim_post_for_upload(self, post_id: str) -> bool:
        """post_status를 'uploading'으로 원자적 마킹. 선점 성공 시 True."""

    @abstractmethod
    def mark_post_result(self, post_id: str, result: PostPublishResult) -> None:
        """업로드 결과(성공/실패)를 게시물 레코드에 기록."""

    @abstractmethod
    def fetch_posted_with_media_id(self, limit: int = 10) -> list[dict]:
        """post_status='posted' AND ig_media_id!='' 인 게시물 최대 limit 건,
        raw Airtable record dict({id, createdTime, fields}) 리스트로 반환."""

    @abstractmethod
    def fetch_posted_missing_media_id(self) -> list[dict]:
        """post_status='posted' 이면서 ig_media_id 가 비어있는 레코드 조회.
        반환: [{"id": str, ...fields}, ...]
        """

    @abstractmethod
    def fetch_all_instagram_posts(self) -> list[dict]:
        """Instagram_Posts 전체 레코드 반환(전체 페이지 순회, 날짜 필터 없음, KPI 집계용)."""

    @abstractmethod
    def fetch_all_lead_interactions(self, since_utc: str | None = None) -> list[dict]:
        """Lead_Interactions 전체 필드 반환(전체 페이지 순회). since_utc 지정 시 relay_scheduled_at >= since_utc 필터, None이면 전체 반환."""

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
    def find_lead_interaction_by_source_event(self, source: str, source_event_id: str) -> str | None:
        """(source, source_event_id) 기준 기존 레코드 조회 — FP-047 idempotency.
        find_source_item_by_hash()와 동일 계약: 있으면 record_id, 없으면 None.
        조회 자체가 실패하면(네트워크/타임아웃 등) 예외를 그대로 전파한다 —
        호출부는 반드시 None(NOT_FOUND)과 예외(LOOKUP_FAILED)를 구분해서 처리해야 하며,
        LOOKUP_FAILED를 NOT_FOUND로 취급해 생성을 진행하면 중복 레코드가 생긴다."""

    @abstractmethod
    def verify_field_exists(self, table: str, field_name: str) -> bool:
        """table에 field_name 필드가 실제로 존재하는지 Airtable Metadata API로 확인 —
        FP-047/Package1 enforce 전제조건 B(startup preflight). 테이블 자체가 없어도
        False(필드도 당연히 없음). 조회 자체가 실패하면(네트워크/권한 등) 예외를 그대로
        전파한다 — 호출부는 False(필드 없음)와 예외(조회 실패)를 구분해서 fail-closed
        판단에 반영해야 한다."""

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

    # ── Training_Review_Queue (학습 데이터 자동 수집·리뷰) ───────────────────

    @abstractmethod
    def insert_training_candidate(self, candidate: TrainingCandidate) -> str:
        """Training_Review_Queue에 신규 후보 저장. review_status 기본 PENDING. record_id 반환."""

    @abstractmethod
    def exists_candidate_by_hash(self, image_hash: str) -> bool:
        """동일 image_hash(SHA256 완전동일)의 후보가 이미 존재하는지 확인."""

    @abstractmethod
    def fetch_candidate_phashes(self, limit: int = 2000) -> list[str]:
        """근사중복(phash) 비교용 — 기존 후보의 phash 값 목록 반환 (빈 값 제외)."""

    @abstractmethod
    def fetch_next_pending_candidate(self) -> TrainingCandidate | None:
        """review_status='PENDING' 인 후보 1건 반환 (collected_at 오래된 순). 없으면 None."""

    @abstractmethod
    def fetch_pending_candidates(self, limit: int = 50) -> list[TrainingCandidate]:
        """review_status='PENDING' 인 후보 최대 limit건 반환 (collected_at 오래된 순) — 그리드 일괄 리뷰용."""

    @abstractmethod
    def save_review_decision(self, record_id: str, decision: str, other_note: str = "") -> None:
        """사람의 PASS/BLOCK 판정(+선택적 기타 메모)을 후보 레코드에 기록. review_status, reviewed_at 갱신."""

    @abstractmethod
    def get_review_status(self, record_id: str) -> str | None:
        """record_id의 현재 review_status를 GET으로 재조회. 저장 직후 실제 반영 여부 검증용.
        레코드가 없으면 None."""

    # ── 선택 기능(optional capability) — 이 인터페이스에는 두지 않는다 ───────────
    # batch_save_review_decisions()/batch_get_review_status()는 모든 저장소 구현체가
    # 반드시 지원해야 하는 필수 계약이 아니라서 여기 두지 않는다(260722 Codex 리뷰 2차
    # 지적: 기본 메서드가 NotImplementedError를 던지더라도 그 메서드 자체는 여전히
    # callable=True이므로, RepositoryInterface를 상속하고 오버라이드하지 않은 구현체가
    # review_batch_committer._supports_batch()에서 "지원함"으로 오인되어 단건 폴백 대신
    # 예외가 발생하는 결함이 있었음). 선택 계약은 modules/infra/review_batch_committer.py의
    # `BatchReviewCapability` Protocol에만 문서화하고, AirtableRepository가 이 인터페이스와
    # 무관하게 별도로 두 메서드를 구현한다. 감지는 여전히
    # callable(getattr(repo, "batch_save_review_decisions", None)) 방식이며, 이 메서드
    # 자체가 아예 존재하지 않는 구현체에서는 getattr이 None을 반환해 정확히 폴백된다.

    @abstractmethod
    def count_candidates_by_status(self) -> dict[str, int]:
        """review_status별 건수 반환 (리뷰 화면 진행률 카운터용)."""
