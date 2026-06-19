import os, logging
from datetime import datetime, timezone, timedelta
import requests
from modules.sns.caption_generator import generate_caption
from modules.sns.image_hosting import upload_to_imgbb

logger = logging.getLogger(__name__)

BASE_URL = "https://api.airtable.com/v0/"

def _headers():
    return {
        "Authorization": "Bearer " + os.getenv("AIRTABLE_API_KEY"),
        "Content-Type": "application/json"
    }

def _base():
    return os.getenv("AIRTABLE_BASE_ID")

def _now():
    return datetime.now(timezone.utc)

def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

BACKOFF = {0: 10, 1: 60, 2: 300}

def _recover_stale_queued():
    """export_started_at 기준 30분 초과 QUEUED → NEW 복구"""
    threshold = _iso(_now() - timedelta(minutes=30))
    url = BASE_URL + _base() + "/Source_Items"
    r = requests.get(url, headers=_headers(), params={"maxRecords": 50})
    for rec in r.json().get("records", []):
        f = rec["fields"]
        if f.get("pipeline_status") == "QUEUED":
            started = f.get("export_started_at", "")
            if started and started < threshold:
                requests.patch(
                    url + "/" + rec["id"], headers=_headers(),
                    json={"fields": {"pipeline_status": "NEW", "export_last_error": "STALE_QUEUED_RECOVERED"}}
                )
                logger.warning("[exporter] STALE_QUEUED 복구: " + rec["id"])

def export_to_instagram_posts(target_id=None, batch_size=3, dry_run=True):
    _recover_stale_queued()

    url = BASE_URL + _base() + "/Source_Items"
    now_iso = _iso(_now())

    # NEW + READY + retry_at <= now 조회
    r = requests.get(url, headers=_headers(), params={"maxRecords": batch_size})
    candidates = [
        rec for rec in r.json().get("records", [])
        if rec["fields"].get("quality_status") == "READY"
        and rec["fields"].get("pipeline_status") == "NEW"
        and (not rec["fields"].get("export_next_retry_at") or rec["fields"]["export_next_retry_at"] <= now_iso)
        and (not target_id or rec["fields"].get("target_id") == target_id)
    ]

    result = {"exported": 0, "skipped": 0, "failed": 0}

    for rec in candidates:
        f = rec["fields"]
        sid = f.get("source_item_id", "")
        retry = int(f.get("export_retry_count", 0))

        if dry_run:
            logger.info("[exporter][DRY_RUN] payload: " + sid + " | " + f.get("title","")[:30])
            result["skipped"] += 1
            continue

        # 1. 상태 선점 NEW → QUEUED
        requests.patch(url + "/" + rec["id"], headers=_headers(), json={
            "fields": {"pipeline_status": "QUEUED", "export_started_at": now_iso}
        })

        # 2. Instagram_Posts 중복 확인
        ig_url = BASE_URL + _base() + "/Instagram_Posts"
        chk = requests.get(ig_url, headers={"Authorization": "Bearer " + os.getenv("AIRTABLE_API_KEY")},
                           params={"maxRecords": 1})
        existing = [r2 for r2 in chk.json().get("records", [])
                    if r2["fields"].get("source_item_id") == sid]
        if existing:
            requests.patch(url + "/" + rec["id"], headers=_headers(),
                           json={"fields": {"pipeline_status": "EXPORTED"}})
            logger.info("[exporter] 중복 skip EXPORTED: " + sid)
            result["skipped"] += 1
            continue

        # 3. caption 생성
        caption, hashtags = generate_caption(f.get("title", ""))
        if not caption:
            next_retry = _iso(_now() + timedelta(minutes=BACKOFF.get(retry, 300)))
            new_retry = retry + 1
            status = "FAILED" if new_retry >= 3 else "NEW"
            requests.patch(url + "/" + rec["id"], headers=_headers(), json={"fields": {
                "pipeline_status": status,
                "export_retry_count": new_retry,
                "export_last_error": "CAPTION_GENERATION_FAILED",
                "export_next_retry_at": next_retry
            }})
            logger.warning("[exporter] caption 실패: " + sid)
            result["failed"] += 1
            continue

        # 4. imgbb 업로드
        img_result = upload_to_imgbb(f.get("image_url", ""))
        if not img_result.get("success"):
            next_retry = _iso(_now() + timedelta(minutes=BACKOFF.get(retry, 300)))
            new_retry = retry + 1
            status = "FAILED" if new_retry >= 3 else "NEW"
            requests.patch(url + "/" + rec["id"], headers=_headers(), json={"fields": {
                "pipeline_status": status,
                "export_retry_count": new_retry,
                "export_last_error": "IMAGE_HOSTING_FAILED",
                "export_next_retry_at": next_retry
            }})
            logger.warning("[exporter] imgbb 실패: " + sid)
            result["failed"] += 1
            continue

        # 5. Instagram_Posts 저장
        ig_payload = {
            "source_item_id":    sid,
            "image_url":         img_result["public_url"],
            "original_image_url": f.get("image_url", ""),
            "caption":           caption + "\n\n" + hashtags,
            "image_url_hash":    img_result["content_hash"],
            "post_status":       "ready",
            "media_type":        "image",
            "source_url":        f.get("source_url", ""),
        }
        ig_r = requests.post(ig_url, headers=_headers(), json={"fields": ig_payload})
        if ig_r.status_code not in (200, 201):
            next_retry = _iso(_now() + timedelta(minutes=BACKOFF.get(retry, 300)))
            new_retry = retry + 1
            status = "FAILED" if new_retry >= 3 else "NEW"
            requests.patch(url + "/" + rec["id"], headers=_headers(), json={"fields": {
                "pipeline_status": status,
                "export_retry_count": new_retry,
                "export_last_error": "INSTAGRAM_POST_CREATE_FAILED",
                "export_next_retry_at": next_retry
            }})
            result["failed"] += 1
            continue

        # 6. Source_Items EXPORTED
        requests.patch(url + "/" + rec["id"], headers=_headers(),
                       json={"fields": {"pipeline_status": "EXPORTED"}})
        logger.info("[exporter] EXPORTED: " + sid)
        result["exported"] += 1

    logger.info("[exporter] 결과: " + str(result))
    return result
