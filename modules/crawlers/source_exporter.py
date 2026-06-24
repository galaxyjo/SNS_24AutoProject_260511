import os
from datetime import datetime, timezone, timedelta

from modules.infra.airtable_repository import AirtableRepository
from modules.infra.repository_interface import SourceItemStatus
from modules.sns.caption_generator import generate_caption
from modules.sns.image_hosting import upload_to_imgbb
from modules.common.logger import get_logger

logger = get_logger(__name__)

BACKOFF = {0: 10, 1: 60, 2: 300}


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _recover_stale_queued(repo: AirtableRepository) -> None:
    threshold = _iso(_now() - timedelta(minutes=30))
    count = repo.recover_stale_queued_source_items(threshold)
    if count:
        logger.warning(f"[exporter] STALE_QUEUED 복구: {count}건")


def export_to_instagram_posts(target_id=None, batch_size=3, dry_run=True):
    repo = AirtableRepository()
    _recover_stale_queued(repo)

    now_iso = _iso(_now())
    candidates = repo.fetch_source_items_for_export(batch_size=batch_size, target_id=target_id)

    result = {"exported": 0, "skipped": 0, "failed": 0}

    for item in candidates:
        record_id = item["record_id"]
        sid = item.get("source_item_id", "")
        retry = item.get("export_retry_count", 0)

        if dry_run:
            logger.info(f"[exporter][DRY_RUN] payload: {sid} | {item.get('title', '')[:30]}")
            result["skipped"] += 1
            continue

        # 1. 상태 선점 NEW → QUEUED
        repo.claim_source_item_for_export(record_id, now_iso)

        # 2. Instagram_Posts 중복 확인 (image_url_hash 기준)
        if repo.exists_post_by_image_url(item.get("image_url", "")):
            repo.update_source_item_status(record_id, SourceItemStatus.EXPORTED)
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

        # 6. Source_Items EXPORTED
        repo.update_source_item_status(record_id, SourceItemStatus.EXPORTED)
        logger.info(f"[exporter] EXPORTED: {sid}")
        result["exported"] += 1

    logger.info(f"[exporter] 결과: {result}")
    return result
