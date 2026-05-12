"""
modules/interaction_engine/engagement_tracker.py — Instagram 게시물 engagement 지표 수집

posted 레코드의 ig_media_id로 Graph API에서 like_count / comments_count 를 조회해
Airtable Instagram_Posts에 업데이트한다.

Airtable 필드 사전 추가 필요:
  - ig_media_id   (Single line text)
  - like_count    (Number)
  - comments_count (Number)
"""

import os
import requests

from modules.common.airtable_bridge import get_table
from modules.common.logger import get_logger

logger = get_logger(__name__)

IG_API = "https://graph.facebook.com/v21.0"


def _fetch_metrics(media_id: str, token: str) -> dict | None:
    try:
        resp = requests.get(
            f"{IG_API}/{media_id}",
            params={"fields": "like_count,comments_count", "access_token": token},
            timeout=10,
        )
        data = resp.json()
        if "error" in data:
            logger.warning(f"[Engagement] Graph API 오류 | {media_id} | {data['error'].get('message','')}")
            return None
        return {
            "like_count":      data.get("like_count", 0),
            "comments_count":  data.get("comments_count", 0),
        }
    except Exception as exc:
        logger.warning(f"[Engagement] 조회 실패 | {media_id} | {exc}")
        return None


def update_engagement_metrics() -> dict:
    """
    Instagram_Posts(post_status='posted', ig_media_id 있음) 레코드의
    like_count / comments_count를 Graph API로 갱신.
    """
    token = os.getenv("INSTA_ACCESS_TOKEN") or os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    if not token:
        logger.warning("[Engagement] INSTA_ACCESS_TOKEN 미설정 — 생략")
        return {"updated": 0, "skipped": 0, "failed": 0}

    table   = get_table("Instagram_Posts")
    records = table.all(formula="AND({post_status}='posted', {ig_media_id}!='')")

    updated = skipped = failed = 0
    for rec in records:
        media_id = rec["fields"].get("ig_media_id", "")
        if not media_id:
            skipped += 1
            continue

        metrics = _fetch_metrics(media_id, token)
        if not metrics:
            failed += 1
            continue

        try:
            table.update(rec["id"], metrics)
            updated += 1
            logger.debug(
                f"[Engagement] 갱신 | {media_id} | "
                f"likes={metrics['like_count']} comments={metrics['comments_count']}"
            )
        except Exception as exc:
            logger.warning(f"[Engagement] Airtable 업데이트 실패 | {media_id} | {exc}")
            failed += 1

    logger.info(f"[Engagement] 완료 | updated={updated} skipped={skipped} failed={failed}")
    return {"updated": updated, "skipped": skipped, "failed": failed}
