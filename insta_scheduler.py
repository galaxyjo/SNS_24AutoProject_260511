import os
from dotenv import load_dotenv

load_dotenv(override=True)  # airtable_bridge import 전에 반드시 먼저 실행

import time
import logging
from datetime import datetime, timedelta

import requests
from apscheduler.schedulers.blocking import BlockingScheduler

from modules.common.airtable_bridge import get_table
from modules.sns.facebook_crawler import run as fb_crawl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

PAGE_TOKEN = os.getenv("INSTA_ACCESS_TOKEN")
IG_USER_ID = os.getenv("INSTA_IG_USER_ID", "").strip()

CRAWL_TARGET_URL = "https://www.facebook.com/groups/3393946167372584"
CRAWL_INTERVAL_MINUTES = 30
POLL_INTERVAL_MINUTES = 5
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 10


def _upload(image_url: str, caption: str) -> str:
    if not PAGE_TOKEN or not IG_USER_ID:
        raise RuntimeError("INSTA_ACCESS_TOKEN 또는 INSTA_IG_USER_ID 환경변수 미설정")

    r1 = requests.post(
        f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media",
        data={"image_url": image_url, "caption": caption, "access_token": PAGE_TOKEN},
        timeout=30,
    )
    resp1 = r1.json()
    if "id" not in resp1:
        raise RuntimeError(f"미디어 생성 실패: {resp1}")

    r2 = requests.post(
        f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish",
        data={"creation_id": resp1["id"], "access_token": PAGE_TOKEN},
        timeout=30,
    )
    resp2 = r2.json()
    if "id" not in resp2:
        raise RuntimeError(f"게시 실패: {resp2}")

    return resp2["id"]


def crawl_and_store():
    logger.info(f"[크롤링] 시작: {CRAWL_TARGET_URL}")
    try:
        result = fb_crawl(CRAWL_TARGET_URL)
        if result.get("image_url"):
            logger.info(f"[크롤링] 완료 → 이미지 저장: {result['image_url'][:60]}...")
        else:
            logger.warning("[크롤링] 완료 → 이미지 없음 (Airtable 저장 생략)")
    except Exception as e:
        logger.error(f"[크롤링] 실패: {e}")


def poll_and_upload():
    logger.info("[업로드] 폴링 시작")
    table = get_table("Instagram_Posts")
    records = table.all(formula="{post_status}='ready'")
    records = [r for r in records if r["fields"].get("post_status") == "ready"]

    if not records:
        logger.info("[업로드] ready 레코드 없음")
        return

    logger.info(f"[업로드] ready 레코드 {len(records)}건 처리 시작")

    for record in records:
        record_id = record["id"]
        fields = record["fields"]
        image_url = fields.get("image_url", "") or fields.get("source_url", "")
        caption = fields.get("caption", "")
        hashtag = fields.get("hashtag", "")
        full_caption = f"{caption}\n{hashtag}".strip()

        if not image_url:
            logger.warning(f"[업로드] [{record_id}] image_url 없음 → failed 마킹")
            table.update(
                record_id,
                {
                    "post_status": "failed",
                    "last_error_msg": "image_url 없음",
                    "retry_count": 0,
                },
            )
            continue

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                post_id = _upload(image_url, full_caption)
                table.update(
                    record_id,
                    {
                        "post_status": "posted",
                        "retry_count": attempt - 1,
                        "last_error_msg": "",
                    },
                )
                logger.info(
                    f"[업로드] [{record_id}] 성공 (시도 {attempt}/{MAX_RETRIES})"
                    f" → post_id: {post_id}"
                )
                last_error = None
                break
            except Exception as e:
                last_error = e
                logger.error(
                    f"[업로드] [{record_id}] 시도 {attempt}/{MAX_RETRIES} 실패: {e}"
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS)

        if last_error is not None:
            table.update(
                record_id,
                {
                    "post_status": "failed",
                    "retry_count": MAX_RETRIES,
                    "last_error_msg": str(last_error)[:500],
                },
            )
            logger.error(
                f"[업로드] [{record_id}] {MAX_RETRIES}회 재시도 모두 실패 → failed 마킹"
            )


def main():
    scheduler = BlockingScheduler(timezone="Asia/Seoul")

    scheduler.add_job(
        crawl_and_store,
        trigger="interval",
        minutes=CRAWL_INTERVAL_MINUTES,
        id="fb_crawl",
        next_run_time=datetime.now(),
    )

    scheduler.add_job(
        poll_and_upload,
        trigger="interval",
        minutes=POLL_INTERVAL_MINUTES,
        id="insta_poll",
        next_run_time=datetime.now() + timedelta(seconds=20),
    )

    logger.info(
        f"파이프라인 시작 | 크롤링: {CRAWL_INTERVAL_MINUTES}분 간격"
        f" | 업로드 폴링: {POLL_INTERVAL_MINUTES}분 간격"
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("파이프라인 종료")


if __name__ == "__main__":
    main()
