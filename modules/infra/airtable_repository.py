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
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from modules.common.canary_classification import (
    CanaryClassificationError,
    validate_post_classification,
)
from modules.infra.airtable_usage_logger import log_api_call
from modules.infra.repository_interface import (
    CrawlTarget,
    InstagramPost,
    InstagramPostCreate,
    InstagramPostStatus,
    LeadBridgeStatus,
    LeadInteraction,
    LeadInteractionCreate,
    PersonaProfile,
    PostPublishResult,
    PublishAccount,
    PublishAccountV2,
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
        """Supplier_Blocklist 전체 레코드 반환(전체 페이지 순회, P1-3/ERR-078과 동일 클래스)."""
        result: list[SupplierBlockEntry] = []
        offset = None
        while True:
            params = {"pageSize": 100}
            if offset:
                params["offset"] = offset
            try:
                r = requests.get(
                    _url("Supplier_Blocklist"),
                    headers=_headers(),
                    params=params,
                    timeout=_TIMEOUT,
                )
                r.raise_for_status()
                log_api_call("Supplier_Blocklist", "GET")
            except requests.HTTPError as e:
                _raise(e, "Supplier_Blocklist")
            except requests.RequestException as e:
                raise RepositoryUnavailableError(str(e)) from e

            data = r.json()
            for rec in data.get("records", []):
                f = rec.get("fields", {})
                result.append(
                    SupplierBlockEntry(
                        author_name=f.get("author_name", ""),
                        page_name=f.get("page_name", ""),
                        reason_code=f.get("reason_code", ""),
                    )
                )
            offset = data.get("offset")
            if not offset:
                break
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

    def validate_instagram_post_context(
        self,
        account_code_ref: str,
        data_classification: str,
        canary_run_id: str = "",
        post_status: str = "",
    ) -> PublishAccount:
        account_code_ref = (account_code_ref or "").strip()
        data_classification = (data_classification or "").strip()
        canary_run_id = (canary_run_id or "").strip()
        post_status = (post_status or "").strip()

        if not account_code_ref:
            raise RepositoryValidationError("account_code_ref 필수")

        account = self.get_publish_account(account_code_ref)
        if account is None or account.get("account_code") != account_code_ref:
            raise RepositoryValidationError(
                "account_code_ref가 Account_Registry의 단일 계정과 연결되지 않음"
            )

        try:
            validate_post_classification(
                data_classification,
                canary_run_id,
                post_status,
            )
        except CanaryClassificationError as exc:
            raise RepositoryValidationError(str(exc)) from exc

        return account

    def save_instagram_post(self, post: InstagramPostCreate) -> str:
        if not post.get("image_url"):
            raise RepositoryValidationError("image_url 필수")
        payload = {k: v for k, v in post.items() if v is not None}
        _explicit_status = (post.get("post_status") or "").strip()
        _require_approval = os.getenv("REQUIRE_APPROVAL_BEFORE_PUBLISH", "false").lower() == "true"
        _default_status = (
            InstagramPostStatus.DRAFT.value if _require_approval else InstagramPostStatus.READY.value
        )
        payload.setdefault("post_status", _default_status)
        _classification_status = (
            _explicit_status
            if payload.get("data_classification") == "test"
            else payload.get("post_status", "")
        )
        self.validate_instagram_post_context(
            payload.get("account_code_ref", ""),
            payload.get("data_classification", ""),
            payload.get("canary_run_id", ""),
            _classification_status,
        )
        if not payload.get("canary_run_id"):
            payload.pop("canary_run_id", None)
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
        """Crawl_Targets 전체 레코드 반환(전체 페이지 순회, P1-3/ERR-078과 동일 클래스)."""
        result: list[CrawlTarget] = []
        offset = None
        while True:
            params = {
                "filterByFormula": "AND({status}='Active', NOT({collection_purpose}='training'))",
                "fields[0]": "target_url",
                "fields[1]": "platform",
                "fields[2]": "target_id",
                "fields[3]": "keyword",
                "fields[4]": "category_code",
                "fields[5]": "max_posts",
                "pageSize": 100,
            }
            if offset:
                params["offset"] = offset
            try:
                r = requests.get(
                    _url("Crawl_Targets"),
                    headers=_headers(),
                    params=params,
                    timeout=_TIMEOUT,
                )
                r.raise_for_status()
                log_api_call("Crawl_Targets", "GET")
            except requests.HTTPError as e:
                _raise(e, "Crawl_Targets")
            except requests.RequestException as e:
                raise RepositoryUnavailableError(str(e)) from e

            data = r.json()
            for rec in data.get("records", []):
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
            offset = data.get("offset")
            if not offset:
                break
        return result

    # ── 4-1. 학습용(training) 크롤 대상 조회 ─────────────────────────────────

    def fetch_active_training_targets(self, platform: str) -> list[CrawlTarget]:
        """collection_purpose='training' 활성 크롤 대상 반환(전체 페이지 순회, P1-3/ERR-078과 동일 클래스)."""
        result: list[CrawlTarget] = []
        offset = None
        while True:
            params = {
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
            }
            if offset:
                params["offset"] = offset
            try:
                r = requests.get(
                    _url("Crawl_Targets"),
                    headers=_headers(),
                    params=params,
                    timeout=_TIMEOUT,
                )
                r.raise_for_status()
                log_api_call("Crawl_Targets", "GET")
            except requests.HTTPError as e:
                _raise(e, "Crawl_Targets")
            except requests.RequestException as e:
                raise RepositoryUnavailableError(str(e)) from e

            data = r.json()
            for rec in data.get("records", []):
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
            offset = data.get("offset")
            if not offset:
                break
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
                    "filterByFormula": (
                        f"AND({{post_status}}='{InstagramPostStatus.READY.value}',"
                        "OR({data_classification}=BLANK(),"
                        "{data_classification}='production'),"
                        "{canary_run_id}=BLANK())"
                    ),
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
                    account_code_ref=f.get("account_code_ref", ""),
                    data_classification=f.get("data_classification", ""),
                    canary_run_id=f.get("canary_run_id", ""),
                    source_url=f.get("source_url", ""),
                )
            )
        return result

    def fetch_pending_posts_for_account(self, account_code_ref: str, limit: int = 10) -> list[InstagramPost]:
        """260804 Track B 6G — Codex 리뷰(P1) 수정. fetch_pending_posts()와 동일한
        필터(post_status=ready, data_classification production/blank, canary_run_id
        blank)에 account_code_ref 조건만 추가해 Airtable 서버측에서 계정을 한정한다.
        다른 계정 후보 수가 얼마든(예: 50건 이상) 이 계정의 후보 존재 여부·개수와
        무관하게 항상 정확히 이 계정 것만 반환한다 — fetch_pending_posts(limit=50) 뒤
        클라이언트에서 필터링하면 다른 계정 레코드가 먼저 페이지를 채워 이 계정
        후보가 결과에서 밀려날 수 있었던 문제(슬롯 놓침)를 해소한다. 기존
        fetch_pending_posts()는 이 메서드 추가로 수정하지 않는다(다른 Caller 무영향).

        260804 Codex 2차 리뷰(P2) 수정 — account_code_ref는 다른 계정 조회
        메서드(get_publish_account 등)와 동일하게 `_ACCOUNT_CODE_PATTERN`으로
        형식을 검증하고(형식 위반은 추측 없이 빈 목록), limit도 양수만 허용한다.
        정렬은 `fetch_due_scheduled_post()`와 동일하게 `scheduled_upload_at`
        오름차순을 명시한다 — 이 필드가 비어있는 레코드가 섞여 있으면 Airtable
        정렬 규칙상 그 레코드들끼리의 상대 순서까지 보장되지는 않으나(값이
        전부 동일하게 공란), 최소한 값이 있는 레코드가 먼저 오는 것과 매
        호출마다 동일한 filter+sort 조합에 대해 재현 가능한 결과를 보장한다
        (Airtable 기본 무정렬 대비 개선). Instagram_Posts에 별도 생성시각
        필드가 없어(Schema 확장은 이번 범위 밖) 완전한 FIFO를 약속하지는
        않는다 — 이 한계는 의도적으로 남겨두고 문서화한다.

        260804 Codex 3차 리뷰(P2) 수정 — limit은 `bool`이 아닌 순수 `int`이고
        1~100 범위여야만 유효하다(그 외 None/문자열/실수/bool/0 이하/101 이상은
        전부 빈 목록으로 안전 차단, 추측 변환 없음). 상한 100은 이 메서드가
        페이지네이션을 처리하지 않기 때문에 승인된 값이다 — Caller(현재는
        `_job_aijomoojin_scheduled_post()`, limit=1)가 더 큰 값을 요구하게
        되면 그때 페이지네이션과 함께 상한 재검토가 필요하다."""
        account_code_ref = (account_code_ref or "").strip()
        if not account_code_ref or not self._ACCOUNT_CODE_PATTERN.fullmatch(account_code_ref):
            return []
        if isinstance(limit, bool) or not isinstance(limit, int) or not (1 <= limit <= 100):
            return []
        try:
            r = requests.get(
                _url("Instagram_Posts"),
                headers=_headers(),
                params={
                    "filterByFormula": (
                        f"AND({{account_code_ref}}='{account_code_ref}',"
                        f"{{post_status}}='{InstagramPostStatus.READY.value}',"
                        "OR({data_classification}=BLANK(),"
                        "{data_classification}='production'),"
                        "{canary_run_id}=BLANK())"
                    ),
                    "sort[0][field]": "scheduled_upload_at",
                    "sort[0][direction]": "asc",
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
                    account_code_ref=f.get("account_code_ref", ""),
                    data_classification=f.get("data_classification", ""),
                    canary_run_id=f.get("canary_run_id", ""),
                    source_url=f.get("source_url", ""),
                )
            )
        return result

    def get_active_post_status_for_account(self, account_code_ref: str) -> str:
        """260804 Track B 6G Producer — 이 계정에 현재 ready 또는 uploading 상태인
        레코드가 있는지 확인한다. `fetch_pending_posts_for_account()`는 ready만
        보므로(Codex 리뷰 지적) Producer의 "이미 대기 중인 게 있으면 새로 안 만든다"
        가드는 이 메서드로 별도 구현한다. 반환값은 실제 상태 문자열("ready"
        또는 "uploading"), 없으면 빈 문자열.

        260804 Codex 3차 리뷰(P2) 수정 — `maxRecords=5`짜리 단일 결합 쿼리는
        활성 레코드가 6건 이상이면(정상 설계상 발생하면 안 되지만 방어적으로)
        uploading이 조회 결과에서 아예 빠질 수 있었다. 개수 상한에 기대지
        않도록, uploading 전용 쿼리(maxRecords=1)를 먼저 실행하고, 없을 때만
        ready 전용 쿼리(maxRecords=1)를 실행한다 — 두 쿼리 각각은 "존재하는가"
        만 물으므로 활성 레코드 개수와 무관하게 항상 정확하다."""
        account_code_ref = (account_code_ref or "").strip()
        if not account_code_ref or not self._ACCOUNT_CODE_PATTERN.fullmatch(account_code_ref):
            return ""

        for status_value in ("uploading", "ready"):
            try:
                r = requests.get(
                    _url("Instagram_Posts"),
                    headers=_headers(),
                    params={
                        "filterByFormula": (
                            f"AND({{account_code_ref}}='{account_code_ref}',"
                            f"{{post_status}}='{status_value}')"
                        ),
                        "maxRecords": 1,
                    },
                    timeout=_TIMEOUT,
                )
                r.raise_for_status()
                log_api_call("Instagram_Posts", "GET")
            except requests.HTTPError as e:
                _raise(e, "Instagram_Posts")
            except requests.RequestException as e:
                raise RepositoryUnavailableError(str(e)) from e

            if r.json().get("records"):
                return status_value
        return ""

    def find_account_post_by_source_url(self, account_code_ref: str, source_url: str) -> bool:
        """260804 Track B 6G Producer — 이 계정+source_url 조합으로 이미 Airtable
        레코드가 존재하는지 확인한다(상태 무관). Vault에 `channel_status: pending`
        으로 남은 패키지를 "재개 대상"으로 오인해 이미 게시 완료된 콘텐츠를
        중복 게시하는 것을 막기 위한 안전장치 — 기존 6건(3.1~3.6)처럼 Airtable
        저장은 성공했지만 Vault 쪽 channel_status 전환 로직이 그때는 없어서
        "pending" 그대로 남은 레코드를 이 메서드로 걸러낸다."""
        account_code_ref = (account_code_ref or "").strip()
        source_url = (source_url or "").strip()
        if not account_code_ref or not self._ACCOUNT_CODE_PATTERN.fullmatch(account_code_ref):
            return False
        if not source_url:
            return False
        # 260804 Codex 2차 리뷰(P1/P2) 수정 — source_url은(account_code_ref와 달리)
        # 형식이 자유로운 URL이라 정규식으로 통째로 막을 수 없다. Airtable
        # 수식 문자열 리터럴 규칙대로 백슬래시·홑따옴표만 이스케이프한다.
        source_url_escaped = source_url.replace("\\", "\\\\").replace("'", "\\'")
        try:
            r = requests.get(
                _url("Instagram_Posts"),
                headers=_headers(),
                params={
                    "filterByFormula": (
                        f"AND({{account_code_ref}}='{account_code_ref}',"
                        f"{{source_url}}='{source_url_escaped}')"
                    ),
                    "maxRecords": 1,
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Instagram_Posts", "GET")
        except requests.HTTPError as e:
            _raise(e, "Instagram_Posts")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        return bool(r.json().get("records"))

    def fetch_due_scheduled_post(self, account_code_ref: str, now_iso: str) -> "InstagramPost | None":
        """260801 Step6B — scheduled_upload_at<=now_iso인 due Record를 특정
        계정에서 정확히 1건만 반환한다(가장 이른 예약시각 우선). 미래 예약
        (scheduled_upload_at>now_iso)은 결과에서 자동 제외된다. test/canary
        Record는 fetch_pending_posts()와 동일하게 배제한다. 기존
        fetch_pending_posts()는 이 메서드 추가로 수정하지 않는다(다른 계정·
        기존 게시경로 영향 회피)."""
        account_code_ref = (account_code_ref or "").strip()
        if not account_code_ref:
            return None
        try:
            r = requests.get(
                _url("Instagram_Posts"),
                headers=_headers(),
                params={
                    "filterByFormula": (
                        f"AND({{account_code_ref}}='{account_code_ref}',"
                        f"{{post_status}}='{InstagramPostStatus.READY.value}',"
                        f"{{scheduled_upload_at}}<=DATETIME_PARSE('{now_iso}'),"
                        "OR({data_classification}=BLANK(),{data_classification}='production'),"
                        "{canary_run_id}=BLANK())"
                    ),
                    "sort[0][field]": "scheduled_upload_at",
                    "sort[0][direction]": "asc",
                    "maxRecords": 1,
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
        if not records:
            return None
        rec = records[0]
        f = rec.get("fields", {})
        return InstagramPost(
            post_id=rec["id"],
            image_url=f.get("image_url", f.get("source_url", "")),
            caption=f.get("caption", ""),
            hashtag=f.get("hashtag", ""),
            post_status=f.get("post_status", ""),
            ig_media_id=f.get("ig_media_id", ""),
            account_code_ref=f.get("account_code_ref", ""),
            data_classification=f.get("data_classification", ""),
            canary_run_id=f.get("canary_run_id", ""),
        )

    # ── 8-1. 계정 조회 (Provider 분기용, access_token 미포함) ─────────────────

    _ACCOUNT_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

    def get_publish_account(self, account_code: str) -> PublishAccountV2 | None:
        if not account_code or not self._ACCOUNT_CODE_PATTERN.fullmatch(account_code):
            # 형식이 이상하면(공백/쉼표 등 다중값처럼 보이는 값 포함) 추측하지 않고 차단
            return None

        try:
            r = requests.get(
                _url("Account_Registry"),
                headers=_headers(),
                params={
                    "filterByFormula": f"{{account_code}}='{account_code}'",
                    "maxRecords": 2,
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Account_Registry", "GET")
        except requests.HTTPError as e:
            _raise(e, "Account_Registry")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        records = r.json().get("records", [])
        if len(records) != 1:
            # 0건(없음) 또는 2건 이상(중복, 모호함) 전부 안전하게 차단
            return None

        f = records[0].get("fields", {})
        api_provider = f.get("api_provider", "")
        if isinstance(api_provider, dict):  # singleSelect는 {"name": ...} 형태로 올 수 있음
            api_provider = api_provider.get("name", "")

        reply_mode = f.get("reply_mode", "")
        if isinstance(reply_mode, dict):  # singleSelect는 {"name": ...} 형태로 올 수 있음
            reply_mode = reply_mode.get("name", "")

        # 260730 계정별 Kill Switch(Fail-closed): Airtable checkbox는 unchecked를 키
        # 생략으로 표현해 missing과 false를 구분하지 않는다 — 명시적으로 체크(true)
        # 안 된 계정은 전부 automation_enabled=False로 취급한다(회장 승인, 우회 방지
        # 우선 — 배포 전 라이브 계정은 Airtable에서 true로 명시 설정 완료).
        return PublishAccountV2(
            account_code=f.get("account_code", ""),
            api_provider=api_provider,
            ig_user_id=f.get("ig_user_id", ""),
            credential_key=f.get("credential_key", ""),
            automation_enabled=f.get("automation_enabled", False),
            fb_page_id=f.get("fb_page_id", ""),
            reply_mode=reply_mode,
        )

    _IG_USER_ID_PATTERN = re.compile(r"^[0-9]+$")

    def get_publish_account_by_ig_user_id(self, ig_user_id: str) -> PublishAccount | None:
        """ig_user_id로 Account_Registry 역조회(Bundle B, 260726).

        0건이면 None. 2건 이상(모호)이면 RepositoryValidationError를 발생시켜
        호출부가 첫 레코드를 임의 선택하지 않도록 강제한다. 네트워크/HTTP 오류는
        RepositoryUnavailableError로 구분한다(None으로 감추지 않음)."""
        if not ig_user_id or not self._IG_USER_ID_PATTERN.fullmatch(ig_user_id):
            return None

        try:
            r = requests.get(
                _url("Account_Registry"),
                headers=_headers(),
                params={
                    "filterByFormula": f"{{ig_user_id}}='{ig_user_id}'",
                    "maxRecords": 2,
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Account_Registry", "GET")
        except requests.HTTPError as e:
            _raise(e, "Account_Registry")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        records = r.json().get("records", [])
        if len(records) == 0:
            return None
        if len(records) > 1:
            raise RepositoryValidationError(
                f"ig_user_id={ig_user_id}에 대응하는 Account_Registry 레코드가 2건 이상(모호함)"
            )

        f = records[0].get("fields", {})
        api_provider = f.get("api_provider", "")
        if isinstance(api_provider, dict):
            api_provider = api_provider.get("name", "")

        return PublishAccount(
            account_code=f.get("account_code", ""),
            api_provider=api_provider,
            ig_user_id=f.get("ig_user_id", ""),
            credential_key=f.get("credential_key", ""),
        )

    def get_account_code_ref_by_media_id(self, media_id: str) -> str:
        """260730 10.5-6단계(댓글 Routing) — ig_media_id로 Instagram_Posts 역조회."""
        if not media_id:
            return ""

        try:
            r = requests.get(
                _url("Instagram_Posts"),
                headers=_headers(),
                params={
                    "filterByFormula": f"{{ig_media_id}}='{media_id}'",
                    "maxRecords": 2,
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
        if len(records) == 0:
            return ""
        if len(records) > 1:
            raise RepositoryValidationError(
                f"ig_media_id={media_id}에 대응하는 Instagram_Posts 레코드가 2건 이상(모호함)"
            )
        return records[0].get("fields", {}).get("account_code_ref", "")

    def get_persona_by_account_code(self, account_code: str) -> PersonaProfile | None:
        """260730 10.5-5단계(Persona 연결) — Account_Registry→Persona_Profile
        Linked Record 역조회. Persona_Profile.account_code_ref는 multipleRecordLinks
        타입이라, Account_Registry 레코드의 Persona_Profile 링크 필드(연결의 반대쪽
        끝)를 통해 역조회한다(직접 filterByFormula로 링크 필드를 텍스트처럼 매칭하지
        않음 — 필드 타입 추측 금지 원칙)."""
        if not account_code or not self._ACCOUNT_CODE_PATTERN.fullmatch(account_code):
            return None

        try:
            r = requests.get(
                _url("Account_Registry"),
                headers=_headers(),
                params={
                    "filterByFormula": f"{{account_code}}='{account_code}'",
                    "maxRecords": 2,
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Account_Registry", "GET")
        except requests.HTTPError as e:
            _raise(e, "Account_Registry")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        records = r.json().get("records", [])
        if len(records) != 1:
            return None

        persona_ids = records[0].get("fields", {}).get("Persona_Profile", [])
        if not persona_ids:
            return None
        if len(persona_ids) > 1:
            raise RepositoryValidationError(
                f"account_code={account_code}에 연결된 Persona_Profile이 2건 이상(모호함)"
            )

        try:
            r2 = requests.get(
                _url("Persona_Profile", persona_ids[0]),
                headers=_headers(),
                timeout=_TIMEOUT,
            )
            r2.raise_for_status()
            log_api_call("Persona_Profile", "GET")
        except requests.HTTPError as e:
            _raise(e, "Persona_Profile")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        f = r2.json().get("fields", {})
        if not f.get("active", False):
            return None

        return PersonaProfile(
            persona_code=f.get("persona_code", ""),
            tone_style=f.get("tone_style", ""),
            greeting_template=f.get("greeting_template", ""),
            followup_template=f.get("followup_template", ""),
        )

    def get_active_persona_by_account_code_v2(self, account_code: str) -> PersonaProfile | None:
        """260801 Step4 T1 Account Binding Gate — Account_Registry Record ID와
        Persona_Profile의 원시 account_code_ref(Linked Record ID 배열)를 Python에서
        정확 비교(exact membership)한다. formula 부분문자열 매칭(FIND/ARRAYJOIN)은
        오매칭 위험(예: "IDN-000036-OLD" 부분일치)이 있어 사용하지 않는다.

        Persona_Profile 전체를 `offset`이 없어질 때까지 페이지네이션하며 조회한다
        (100건 이상이어도 뒷페이지 후보를 놓치지 않음).

        Repository 책임 범위: 특정 account_code에 연결된 active Persona 단일조회까지만
        수행한다. 특정 persona_code(예: PER-002)를 요구하는지는 이 함수의 책임이 아니며,
        호출자(향후 aijomoojin Binding Adapter)가 반환된 PersonaProfile.persona_code를
        검증해야 한다 — 이 함수는 PER-002를 하드코딩하지 않는다.

        기존 get_persona_by_account_code()는 무수정(다른 Caller 영향 회피, T1 Gate
        승인 범위)."""
        if not account_code or not self._ACCOUNT_CODE_PATTERN.fullmatch(account_code):
            return None

        try:
            r = requests.get(
                _url("Account_Registry"),
                headers=_headers(),
                params={
                    "filterByFormula": f"{{account_code}}='{account_code}'",
                    "maxRecords": 2,
                },
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Account_Registry", "GET")
        except requests.HTTPError as e:
            _raise(e, "Account_Registry")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        records = r.json().get("records", [])
        if len(records) != 1:
            return None
        account_record_id = records[0]["id"]

        candidates: list = []
        offset = None
        while True:
            params = {"pageSize": 100}
            if offset:
                params["offset"] = offset
            try:
                r2 = requests.get(
                    _url("Persona_Profile"),
                    headers=_headers(),
                    params=params,
                    timeout=_TIMEOUT,
                )
                r2.raise_for_status()
                log_api_call("Persona_Profile", "GET")
            except requests.HTTPError as e:
                _raise(e, "Persona_Profile")
            except requests.RequestException as e:
                raise RepositoryUnavailableError(str(e)) from e

            body = r2.json()
            candidates.extend(body.get("records", []))
            offset = body.get("offset")
            if not offset:
                break

        exact_matches = [
            rec for rec in candidates
            if isinstance(rec.get("fields", {}).get("account_code_ref"), list)
            and account_record_id in rec["fields"]["account_code_ref"]
            and rec.get("fields", {}).get("active", False)
        ]

        if len(exact_matches) == 0:
            return None
        if len(exact_matches) > 1:
            raise RepositoryValidationError(
                f"account_code={account_code}(Record ID={account_record_id})에 연결된 "
                f"active Persona_Profile이 정확비교 기준 2건 이상(모호함)"
            )

        f = exact_matches[0].get("fields", {})
        return PersonaProfile(
            persona_code=f.get("persona_code", ""),
            tone_style=f.get("tone_style", ""),
            greeting_template=f.get("greeting_template", ""),
            followup_template=f.get("followup_template", ""),
            language=f.get("language", ""),
        )

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
        # ERR-075: Instagram_Posts에 error_code 필드가 존재하지 않아 이 필드를 payload에
        # 넣으면 422 UNKNOWN_FIELD_NAME으로 PATCH 전체(post_status 포함)가 거부되고
        # 레코드가 uploading에 고착된다(ERR-041과 동일 클래스, retry_count/last_error_msg
        # 재발). ERR-041 선례와 동일하게 실패 사유는 Airtable에 쓰지 않고 로그로만 남긴다
        # (호출부에서 이미 logger.error로 기록됨).
        status = result.get("status", "")
        payload: dict = {"post_status": status}
        if result.get("platform_post_id"):
            payload["ig_media_id"] = result["platform_post_id"]
        # error_code는 의도적으로 payload에 넣지 않음 — 위 주석 참조. 호출부에서 이미 로깅됨.
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
        """Instagram_Posts 전체 레코드 반환(전체 페이지 순회, KPI 집계용)."""
        records: list[dict] = []
        offset = None
        while True:
            params = {"pageSize": 100}
            if offset:
                params["offset"] = offset
            try:
                r = requests.get(
                    _url("Instagram_Posts"),
                    headers=_headers(),
                    params=params,
                    timeout=_TIMEOUT,
                )
                r.raise_for_status()
                log_api_call("Instagram_Posts", "GET")
            except requests.HTTPError as e:
                _raise(e, "Instagram_Posts")
            except requests.RequestException as e:
                raise RepositoryUnavailableError(str(e)) from e
            data = r.json()
            records.extend(
                {"id": rec["id"], **rec.get("fields", {})} for rec in data.get("records", [])
            )
            offset = data.get("offset")
            if not offset:
                break
        return records

    def fetch_all_lead_interactions(self, since_utc: str | None = None) -> list[dict]:
        """Lead_Interactions 전체 레코드 반환(전체 페이지 순회). since_utc 지정 시 relay_scheduled_at>=필터."""
        records: list[dict] = []
        offset = None
        while True:
            params = {"pageSize": 100}
            if since_utc:
                params["filterByFormula"] = f"{{relay_scheduled_at}}>='{since_utc}'"
            if offset:
                params["offset"] = offset
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
            data = r.json()
            records.extend(
                {"id": rec["id"], **rec.get("fields", {})} for rec in data.get("records", [])
            )
            offset = data.get("offset")
            if not offset:
                break
        return records

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
        if data.get("account_code_ref"):
            fields["account_code_ref"] = data["account_code_ref"]
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
                account_code_ref=f.get("account_code_ref", ""),
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

    def record_reply_observability(
        self,
        record_id: str,
        *,
        reply_mode_used: str,
        persona_code_ref: str = "",
        send_status: str = "",
        prompt_version: str = "",
        persona_check_pass: bool = False,
    ) -> None:
        fields: dict = {"reply_mode_used": reply_mode_used, "persona_check_pass": persona_check_pass}
        if persona_code_ref:
            fields["persona_code_ref"] = persona_code_ref
        if send_status:
            fields["send_status"] = send_status
        if prompt_version:
            fields["prompt_version"] = prompt_version
        self._patch_lead_interaction(record_id, fields)

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
                account_code_ref=f.get("account_code_ref", ""),
            ))
        return result

    def get_source_item_by_record_id(self, record_id: str) -> SourceItem:
        if not re.fullmatch(r"rec[A-Za-z0-9]+", (record_id or "").strip()):
            raise RepositoryValidationError("유효한 Source_Items Record ID 필수")
        try:
            r = requests.get(
                _url("Source_Items", record_id),
                headers=_headers(),
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            log_api_call("Source_Items", "GET")
        except requests.HTTPError as e:
            _raise(e, "Source_Items")
        except requests.RequestException as e:
            raise RepositoryUnavailableError(str(e)) from e

        rec = r.json()
        fields = rec.get("fields", {})
        return SourceItem(
            record_id=rec.get("id", ""),
            source_item_id=fields.get("source_item_id", ""),
            title=fields.get("title", ""),
            image_url=fields.get("image_url", ""),
            source_url=fields.get("source_url", ""),
            target_id=fields.get("target_id", ""),
            quality_status=fields.get("quality_status", ""),
            pipeline_status=fields.get("pipeline_status", ""),
            export_retry_count=int(fields.get("export_retry_count", 0)),
            account_code_ref=fields.get("account_code_ref", ""),
        )

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

    def claim_source_item_for_export(
        self,
        record_id: str,
        started_at_iso: str,
        account_code_ref: str,
    ) -> None:
        if not (account_code_ref or "").strip():
            raise RepositoryValidationError("Source_Items.account_code_ref 필수")
        try:
            r = requests.patch(
                _url("Source_Items", record_id),
                headers=_headers(json_body=True),
                json={"fields": {
                    "pipeline_status": "QUEUED",
                    "export_started_at": started_at_iso,
                    "account_code_ref": account_code_ref,
                }},
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
        """근사중복(phash) 비교용 phash 목록 반환(전체 페이지 순회, limit건까지 — P1-3/ERR-078과 동일 클래스였던 결함 해소)."""
        result: list[str] = []
        offset = None
        while len(result) < limit:
            params = {
                "filterByFormula": "NOT({phash}='')",
                "pageSize": min(limit - len(result), 100),
                "fields[0]": "phash",
            }
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
            result.extend(
                rec["fields"]["phash"]
                for rec in data.get("records", [])
                if rec.get("fields", {}).get("phash")
            )
            offset = data.get("offset")
            if not offset:
                break
        return result

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
        """260805: 정렬을 desc로 변경 — Facebook CDN image_url은 며칠 내 403으로
        만료된다(Runtime 확인). 리뷰 적체가 큰 상태에서 asc(오래된 것부터)로 보이면
        화면이 죽은 이미지로 가득 차므로, 최근 수집분(=URL이 살아있을 확률이 높은
        건)부터 보여준다."""
        try:
            r = requests.get(
                _url("Training_Review_Queue"),
                headers=_headers(),
                params={
                    "filterByFormula":    f"{{review_status}}='{ReviewStatus.PENDING.value}'",
                    "sort[0][field]":     "collected_at",
                    "sort[0][direction]": "desc",
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
