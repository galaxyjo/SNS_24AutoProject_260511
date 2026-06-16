"""
tools/backfill_failed_images.py
단일 레코드 Backfill 전용. 하드 가드 12개 적용.
DRY_RUN: python tools/backfill_failed_images.py --record-id <id>
실제실행: python tools/backfill_failed_images.py --record-id <id> --max-records 1 --execute
"""
import os, sys, argparse, hashlib, logging, requests
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.sns.image_hosting import upload_to_imgbb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

API_KEY   = os.getenv("AIRTABLE_API_KEY")
BASE_ID   = os.getenv("AIRTABLE_BASE_ID")
IMGBB_KEY = os.getenv("IMGBB_API_KEY")
BASE_URL  = f"https://api.airtable.com/v0/{BASE_ID}/Instagram_Posts"
HEADERS   = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def abort(msg):
    logger.error(f"[ABORT] {msg}")
    sys.exit(1)


def fetch_record(record_id):
    r = requests.get(f"{BASE_URL}/{record_id}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def is_fbcdn(url):
    return "fbcdn.net" in (urlparse(url).hostname or "").lower()


def guard_check(rec, record_id):
    f = rec.get("fields", {})
    if rec["id"] != record_id:
        abort(f"GUARD1: record_id 불일치 {rec['id']} != {record_id}")
    if f.get("post_status") != "failed":
        abort(f"GUARD2: post_status={f.get('post_status')} — failed 아님")
    if f.get("ig_media_id"):
        abort(f"GUARD3: ig_media_id 존재 — 이미 게시된 레코드")
    if not is_fbcdn(str(f.get("image_url", ""))):
        abort(f"GUARD4: image_url이 fbcdn.net 아님")
    if not f.get("caption"):
        abort(f"GUARD5: caption 없음")
    orig = f.get("original_image_url", "")
    if orig and orig != f.get("image_url", ""):
        abort(f"GUARD6: original_image_url 이미 존재하고 image_url과 다름 — 중복 처리 위험")
    logger.info("[GUARD] 6개 가드 통과")
    return f


def verify_counts(expected_ready, expected_failed):
    def count(formula):
        r = requests.get(BASE_URL, headers=HEADERS,
                         params={"filterByFormula": formula, "pageSize": 1}, timeout=30)
        r.raise_for_status()
        # 전체 건수는 offset 없이 100건 조회로 근사
        all_r = requests.get(BASE_URL, headers=HEADERS,
                             params={"filterByFormula": formula, "pageSize": 100}, timeout=30)
        return len(all_r.json().get("records", []))
    ready  = count("{post_status}='ready'")
    failed = count("{post_status}='failed'")
    posted = count("{post_status}='posted'")
    logger.info(f"[COUNT] ready={ready} failed={failed} posted={posted}")
    if ready != expected_ready:
        abort(f"GUARD_COUNT: ready={ready} 예상={expected_ready}")
    if posted != 10:
        abort(f"GUARD_COUNT: posted={posted} 예상=10")
    return ready, failed, posted


def rollback(record_id, original_url):
    logger.warning(f"[ROLLBACK] {record_id} → image_url 복구, status=failed")
    requests.patch(f"{BASE_URL}/{record_id}", headers=HEADERS, json={
        "fields": {"image_url": original_url, "post_status": "failed"}
    }, timeout=30)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-id", required=True)
    parser.add_argument("--max-records", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if not args.record_id:
        abort("--record-id 필수")
    if args.max_records != 1:
        abort(f"--max-records는 반드시 1이어야 함: {args.max_records}")

    logger.info(f"=== Backfill 시작 | record_id={args.record_id} | execute={args.execute} ===")

    # 실행 전 상태 조회
    rec = fetch_record(args.record_id)
    fields = guard_check(rec, args.record_id)
    original_url = fields["image_url"]

    logger.info(f"[PRE] post_status={fields['post_status']}")
    logger.info(f"[PRE] image_url={original_url[:120]}")
    logger.info(f"[PRE] caption 존재={bool(fields.get('caption'))}")
    logger.info(f"[PRE] ig_media_id={fields.get('ig_media_id','없음')}")

    if not args.execute:
        logger.info("[DRY_RUN] --execute 없음 — 변경 없이 종료")
        return

    # 실행 전 건수 확인
    verify_counts(expected_ready=0, expected_failed=149)

    # STEP1: 다운로드 + imgbb 업로드
    result = upload_to_imgbb(original_url, api_key=IMGBB_KEY)
    if not result["success"]:
        abort(f"STEP1/2 실패: {result['error']}")

    public_url   = result["public_url"]
    content_hash = result["content_hash"]
    logger.info(f"[IMGBB] 성공 | url={public_url[:80]}")
    logger.info(f"[HASH] SHA256={content_hash}")

    # STEP3: 공개 URL 재검증
    try:
        chk = requests.get(public_url, timeout=10)
        ct  = chk.headers.get("Content-Type","")
        if chk.status_code != 200 or "image/" not in ct or len(chk.content) == 0:
            abort(f"STEP3: URL 검증 실패 status={chk.status_code} ct={ct}")
        logger.info(f"[VERIFY] HTTP={chk.status_code} CT={ct} size={len(chk.content)}")
    except Exception as e:
        abort(f"STEP3: URL 검증 예외: {e}")

    # STEP4: Airtable 단일 PATCH
    patch = requests.patch(f"{BASE_URL}/{args.record_id}", headers=HEADERS, json={"fields": {
        "original_image_url": original_url,
        "image_url":          public_url,
        "post_status":        "ready"
    }}, timeout=30)
    patch.raise_for_status()
    logger.info(f"[PATCH] HTTP={patch.status_code}")

    # 실행 후 검증
    rec2   = fetch_record(args.record_id)
    f2     = rec2["fields"]
    logger.info(f"[POST] post_status={f2.get('post_status')}")
    logger.info(f"[POST] image_url={str(f2.get('image_url',''))[:80]}")
    logger.info(f"[POST] original_image_url={str(f2.get('original_image_url',''))[:80]}")
    logger.info(f"[POST] ig_media_id={f2.get('ig_media_id','없음')}")

    if f2.get("post_status") != "ready":
        rollback(args.record_id, original_url)
        abort("POST 검증: post_status != ready — rollback 실행")

    verify_counts(expected_ready=1, expected_failed=148)
    logger.info("=== Phase 2-B 완료 ===")


if __name__ == "__main__":
    main()