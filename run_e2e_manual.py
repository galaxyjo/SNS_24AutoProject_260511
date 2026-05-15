"""E2E 수동 실행 — FB크롤링 → 캡션 → Instagram 업로드"""
import os
from dotenv import load_dotenv
load_dotenv(override=True)

from core.log_initializer import init_logging
init_logging()

import time
import requests
from modules.common.airtable_bridge import get_table

print("=" * 60)
print("  E2E 수동 실행 — FB크롤링 → 캡션 → Instagram 업로드")
print("=" * 60)

# STEP 1: FB 크롤링
print("\n[STEP 1] FB 크롤링 시작...")
from modules.sns.facebook_crawler import run_all_accounts
summary = run_all_accounts()
print(f"[STEP 1] 완료 | {summary}")

# STEP 2: Instagram 업로드
print("\n[STEP 2] Instagram 업로드 시작...")
page_token = os.getenv("INSTA_ACCESS_TOKEN")
ig_user_id = os.getenv("INSTA_IG_USER_ID", "").strip()
table = get_table("Instagram_Posts")
records = table.all(formula="{post_status}='ready'")
print(f"[STEP 2] ready 레코드: {len(records)}건")

for rec in records:
    rid       = rec["id"]
    fields    = rec["fields"]
    image_url = fields.get("image_url") or fields.get("source_url", "")
    caption   = f"{fields.get('caption','')}\n{fields.get('hashtag','')}".strip()
    print(f"  처리 중: {rid} | image={image_url[:60]}...")

    success, last_err = False, None
    for attempt in range(1, 4):
        try:
            r1 = requests.post(
                f"https://graph.facebook.com/v21.0/{ig_user_id}/media",
                params={"image_url": image_url, "caption": caption, "access_token": page_token},
                timeout=30,
            )
            c1 = r1.json()
            if "id" not in c1:
                raise RuntimeError(f"미디어 생성 실패: {c1}")
            time.sleep(5)
            r2 = requests.post(
                f"https://graph.facebook.com/v21.0/{ig_user_id}/media_publish",
                params={"creation_id": c1["id"], "access_token": page_token},
                timeout=30,
            )
            c2 = r2.json()
            if "id" not in c2:
                raise RuntimeError(f"게시 실패: {c2}")
            table.update(rid, {
                "post_status": "posted",
                "ig_media_id": c2["id"],
                "retry_count": attempt - 1,
                "last_error_msg": "",
            })
            print(f"  [OK] 업로드 성공 | {rid} | ig_media_id={c2['id']}")
            success = True
            break
        except Exception as exc:
            last_err = exc
            print(f"  [ERR] attempt {attempt} 실패: {exc}")
            if attempt < 3:
                time.sleep(15)

    if not success:
        table.update(rid, {"post_status": "failed", "retry_count": 3, "last_error_msg": str(last_err)[:500]})
        print(f"  [FAIL] 최종 실패 | {rid}")

print("\n" + "=" * 60)
print("  E2E 완료")
print("=" * 60)
