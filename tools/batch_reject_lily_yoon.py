"""
tools/batch_reject_lily_yoon.py
Source_Feeds 테이블에서 author_name = "Lily Yoon" 레코드 전체 조회 후
processing_status = "rejected" 일괄 업데이트.

DRY RUN : python tools/batch_reject_lily_yoon.py
실제 실행: python tools/batch_reject_lily_yoon.py --execute
"""
import os, sys, logging, requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

API_KEY  = os.getenv("AIRTABLE_API_KEY")
BASE_ID  = os.getenv("AIRTABLE_BASE_ID")
TABLE    = "Source_Feeds"
BASE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE}"
HEADERS  = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

FILTER   = '{author_name}="Lily Yoon"'
TARGET_STATUS = "rejected"
BATCH_SIZE = 10  # Airtable PATCH 최대 10건


def fetch_all():
    records, offset = [], None
    while True:
        params = {"filterByFormula": FILTER, "pageSize": 100}
        if offset:
            params["offset"] = offset
        r = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
    return records


def batch_update(record_ids, dry_run):
    updated = 0
    for i in range(0, len(record_ids), BATCH_SIZE):
        chunk = record_ids[i: i + BATCH_SIZE]
        payload = {
            "records": [
                {"id": rid, "fields": {"processing_status": TARGET_STATUS}}
                for rid in chunk
            ]
        }
        if dry_run:
            logger.info(f"[DRY_RUN] PATCH 생략 | chunk {i//BATCH_SIZE + 1} ({len(chunk)}건): {chunk}")
        else:
            r = requests.patch(BASE_URL, headers=HEADERS, json=payload, timeout=30)
            r.raise_for_status()
            logger.info(f"[PATCH] chunk {i//BATCH_SIZE + 1} ({len(chunk)}건) → HTTP {r.status_code}")
        updated += len(chunk)
    return updated


def main():
    dry_run = "--execute" not in sys.argv

    logger.info(f"=== batch_reject_lily_yoon 시작 | DRY_RUN={dry_run} ===")
    logger.info(f"필터: {FILTER}")

    records = fetch_all()
    logger.info(f"조회된 레코드: {len(records)}건")

    if not records:
        logger.info("처리 대상 없음 — 종료")
        return

    for rec in records:
        f = rec.get("fields", {})
        logger.info(f"  [{rec['id']}] author={f.get('author_name')} | current_status={f.get('processing_status')}")

    record_ids = [r["id"] for r in records]
    updated = batch_update(record_ids, dry_run)

    if dry_run:
        print(f"\n[DRY_RUN] 실제 변경 없음. 대상 {updated}건 확인 완료.")
        print("실제 실행하려면: python tools/batch_reject_lily_yoon.py --execute")
    else:
        print(f"\n완료: {updated}건 → processing_status='{TARGET_STATUS}' 업데이트")


if __name__ == "__main__":
    main()
