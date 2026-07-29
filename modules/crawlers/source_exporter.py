import hashlib
import os
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

from modules.infra.airtable_repository import AirtableRepository
from modules.infra.repository_interface import SourceItemStatus
from modules.sns.caption_generator import generate_caption
from modules.sns.image_hosting import upload_to_imgbb
from modules.common.logger import get_logger

logger = get_logger(__name__)

BACKOFF = {0: 10, 1: 60, 2: 300}


class DomeCanaryError(RuntimeError):
    """Exact-Record Dome Canary 계약 위반."""


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _recover_stale_queued(repo: AirtableRepository) -> None:
    threshold = _iso(_now() - timedelta(minutes=30))
    count = repo.recover_stale_queued_source_items(threshold)
    if count:
        logger.warning(f"[exporter] STALE_QUEUED 복구: {count}건")


def _validate_approved_canary_image_url(image_url: str) -> str:
    parsed = urlparse((image_url or "").strip())
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not hostname:
        raise DomeCanaryError("승인된 기존 HTTPS 이미지 URL 필수")
    if hostname == "facebook.com" or hostname.endswith(".facebook.com"):
        raise DomeCanaryError("Facebook 원본 URL은 Canary 이미지로 사용 금지")
    if "fbcdn.net" in hostname:
        raise DomeCanaryError("fbcdn URL은 ImgBB 없이 Canary에 사용 금지")
    return image_url.strip()


def export_exact_source_item_canary(
    *,
    source_record_id: str,
    approved_image_url: str,
    approved_caption: str,
    canary_run_id: str,
    write_guard,
    target_publish_account_code_ref: str = "IDN-000041",
) -> dict:
    """정확한 Source_Items Record 1건만 draft Post로 변환한다."""
    from modules.common.canary_execution_guard import CanaryWriteOperation

    if target_publish_account_code_ref != "IDN-000041":
        raise DomeCanaryError("Dome Canary Target Account는 IDN-000041만 허용")
    if not re.fullmatch(r"rec[A-Za-z0-9]+", source_record_id or ""):
        raise DomeCanaryError("유효한 source_record_id 필수")
    stable_image_url = _validate_approved_canary_image_url(approved_image_url)
    caption = (approved_caption or "").strip()
    if not caption:
        raise DomeCanaryError("approved_caption 필수")

    repo = AirtableRepository()
    repo.validate_instagram_post_context(
        target_publish_account_code_ref,
        "test",
        canary_run_id,
        "draft",
    )
    item = repo.get_source_item_by_record_id(source_record_id)
    if item.get("record_id") != source_record_id:
        raise DomeCanaryError("조회된 Source Record ID 불일치")
    if not item.get("source_item_id"):
        raise DomeCanaryError("Source Item ID 공란")
    if item.get("quality_status") != "READY":
        raise DomeCanaryError("Source Item quality_status=READY 필요")
    if item.get("pipeline_status") != "NEW":
        raise DomeCanaryError("Source Item pipeline_status=NEW 필요")
    source_account = (item.get("account_code_ref") or "").strip()
    if source_account and source_account != target_publish_account_code_ref:
        raise DomeCanaryError("Source와 Target Publish Account 불일치")
    if repo.exists_post_by_image_url(stable_image_url):
        raise DomeCanaryError("승인 이미지 URL의 기존 Post가 있어 신규 Write 차단")

    first_patch_authorized = False
    final_patch_authorized = False
    try:
        write_guard.authorize_write(
            CanaryWriteOperation.SOURCE_ITEM_PATCH,
            record_id=source_record_id,
        )
        first_patch_authorized = True
        repo.claim_source_item_for_export(
            source_record_id,
            _iso(_now()),
            target_publish_account_code_ref,
        )

        payload = {
            "source_item_id": item["source_item_id"],
            "image_url": stable_image_url,
            "original_image_url": stable_image_url,
            "caption": caption,
            "image_url_hash": hashlib.sha256(stable_image_url.encode()).hexdigest(),
            "post_status": "draft",
            "media_type": "image",
            "source_url": item.get("source_url", ""),
            "account_code_ref": target_publish_account_code_ref,
            "data_classification": "test",
            "canary_run_id": canary_run_id,
        }
        write_guard.authorize_write(
            CanaryWriteOperation.INSTAGRAM_POST_CREATE
        )
        post_record_id = repo.save_instagram_post(payload)
        if not post_record_id:
            raise DomeCanaryError("Instagram_Posts Create 응답 record_id 없음")

        write_guard.authorize_write(
            CanaryWriteOperation.SOURCE_ITEM_PATCH,
            record_id=source_record_id,
        )
        final_patch_authorized = True
        repo.update_source_item_status(
            source_record_id,
            SourceItemStatus.EXPORTED,
        )
        return {
            "created": 1,
            "post_record_id": post_record_id,
            "source_record_id": source_record_id,
            "post_status": "draft",
        }
    except Exception:
        # Claim 예산을 썼지만 종료 PATCH 예산은 아직 남아 있을 때만 지정
        # Record를 REJECTED로 고정한다. 자동 Retry·stale 복구는 호출하지 않는다.
        if first_patch_authorized and not final_patch_authorized:
            try:
                write_guard.authorize_write(
                    CanaryWriteOperation.SOURCE_ITEM_PATCH,
                    record_id=source_record_id,
                )
                repo.update_source_item_status(
                    source_record_id,
                    SourceItemStatus.REJECTED,
                    reason_code="CANARY_FAILED",
                )
            except Exception:
                # 세 번째 Write·자동 Retry는 금지. 원래 오류를 보존한다.
                pass
        raise


def export_to_instagram_posts(
    target_id=None,
    batch_size=3,
    dry_run=True,
    *,
    target_publish_account_code_ref: str,
    data_classification: str,
    canary_run_id: str = "",
):
    repo = AirtableRepository()
    # Source_Items PATCH를 포함한 어떤 상태변경보다 먼저 공통 계약을 검증한다.
    repo.validate_instagram_post_context(
        target_publish_account_code_ref,
        data_classification,
        canary_run_id,
    )
    _recover_stale_queued(repo)

    now_iso = _iso(_now())
    candidates = repo.fetch_source_items_for_export(batch_size=batch_size, target_id=target_id)

    result = {"exported": 0, "skipped": 0, "failed": 0}

    for item in candidates:
        record_id = item["record_id"]
        sid = item.get("source_item_id", "")
        retry = item.get("export_retry_count", 0)
        source_account_code_ref = item.get("account_code_ref", "")

        if dry_run:
            logger.info(f"[exporter][DRY_RUN] payload: {sid} | {item.get('title', '')[:30]}")
            result["skipped"] += 1
            continue

        if source_account_code_ref and source_account_code_ref != target_publish_account_code_ref:
            logger.error(
                "[exporter] Scheduler·Source 계정 불일치 — Post 생성 차단 | "
                f"source_item_id={sid}"
            )
            result["failed"] += 1
            continue

        # 1. 상태 선점 NEW → QUEUED
        try:
            repo.claim_source_item_for_export(
                record_id,
                now_iso,
                target_publish_account_code_ref,
            )
        except Exception as exc:
            logger.error(f"[exporter] 상태 선점 실패 — skip: {sid} | {exc}")
            result["failed"] += 1
            continue

        # 2. Instagram_Posts 중복 확인 (image_url_hash 기준)
        try:
            is_duplicate = repo.exists_post_by_image_url(item.get("image_url", ""))
        except Exception as exc:
            logger.error(f"[exporter] 중복 확인 실패 — skip: {sid} | {exc}")
            result["failed"] += 1
            continue
        if is_duplicate:
            try:
                repo.update_source_item_status(record_id, SourceItemStatus.EXPORTED)
            except Exception as exc:
                logger.error(f"[exporter] 중복 skip 상태갱신 실패 — skip: {sid} | {exc}")
                result["failed"] += 1
                continue
            logger.info(f"[exporter] 중복 skip EXPORTED: {sid}")
            result["skipped"] += 1
            continue

        # 3. caption 생성
        caption, hashtags = generate_caption(item.get("title", ""))
        if not caption:
            new_retry = retry + 1
            repo.update_source_item_retry(
                record_id, "CAPTION_GENERATION_FAILED", new_retry,
                _iso(_now() + timedelta(minutes=BACKOFF.get(retry, 300))),
            )
            logger.warning(f"[exporter] caption 실패: {sid}")
            result["failed"] += 1
            continue

        # 4. imgbb 업로드
        img_result = upload_to_imgbb(item.get("image_url", ""))
        if not img_result.get("success"):
            new_retry = retry + 1
            repo.update_source_item_retry(
                record_id, "IMAGE_HOSTING_FAILED", new_retry,
                _iso(_now() + timedelta(minutes=BACKOFF.get(retry, 300))),
            )
            logger.warning(f"[exporter] imgbb 실패: {sid}")
            result["failed"] += 1
            continue

        # 5. Instagram_Posts 저장
        ig_payload = {
            "source_item_id":     sid,
            "image_url":          img_result["public_url"],
            "original_image_url": item.get("image_url", ""),
            "caption":            caption + "\n\n" + hashtags,
            "image_url_hash":     img_result["content_hash"],
            "post_status":        "ready",
            "media_type":         "image",
            "source_url":         item.get("source_url", ""),
            "account_code_ref":   target_publish_account_code_ref,
            "data_classification": data_classification,
            "canary_run_id":      canary_run_id,
        }
        try:
            repo.save_instagram_post(ig_payload)
        except Exception as exc:
            new_retry = retry + 1
            repo.update_source_item_retry(
                record_id, "INSTAGRAM_POST_CREATE_FAILED", new_retry,
                _iso(_now() + timedelta(minutes=BACKOFF.get(retry, 300))),
            )
            logger.warning(f"[exporter] IG 저장 실패: {sid} | {exc}")
            result["failed"] += 1
            continue

        # 6. Source_Items EXPORTED — 반환 계약(exported/skipped/failed)은 그대로 유지하고,
        # IG 저장(5번)은 이미 성공했다는 사실은 구조화 로그로만 구분한다.
        try:
            repo.update_source_item_status(record_id, SourceItemStatus.EXPORTED)
        except Exception as exc:
            logger.error(
                f"[exporter] IG 저장은 성공했으나 Source_Items 상태갱신 실패 — 수동 확인 필요: "
                f"{sid} | {exc}"
            )
            result["failed"] += 1
            continue
        logger.info(f"[exporter] EXPORTED: {sid}")
        result["exported"] += 1

    logger.info(f"[exporter] 결과: {result}")
    return result
