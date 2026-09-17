"""
tools/set_account_outbound_limits.py

Account_Registry 의 특정 계정에 아웃바운드 일일 한도를 설정한다 (STEP 3-C, 260901).

사용:
    python tools/set_account_outbound_limits.py IDN-000041 --follow 20 --friend 10 --comment 0
    python tools/set_account_outbound_limits.py IDN-000041 --follow 20 --friend 10 --comment 0 --dry-run

전제: .env AIRTABLE_API_KEY / AIRTABLE_BASE_ID.
안전: 0/2건 조회면 중단(모호). 값 미지정 인자는 건드리지 않음.
"""

import argparse
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_ID = os.getenv("AIRTABLE_BASE_ID")
API_KEY = os.getenv("AIRTABLE_API_KEY")
H = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
URL = f"https://api.airtable.com/v0/{BASE_ID}/Account_Registry"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("account_code")
    ap.add_argument("--follow", type=int, default=None)
    ap.add_argument("--friend", type=int, default=None)
    ap.add_argument("--comment", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if not BASE_ID or not API_KEY:
        print("[ERROR] .env 미설정")
        sys.exit(1)

    safe = a.account_code.replace("'", "\\'")
    r = requests.get(URL, headers={"Authorization": f"Bearer {API_KEY}"},
                     params={"filterByFormula": f"{{account_code}}='{safe}'", "maxRecords": 2},
                     timeout=15)
    r.raise_for_status()
    recs = r.json().get("records", [])
    if len(recs) != 1:
        print(f"[ERROR] account_code='{a.account_code}' 조회 {len(recs)}건 (1건이어야 함)")
        sys.exit(1)

    rid = recs[0]["id"]
    fields = {}
    if a.follow is not None:
        fields["daily_follow_limit"] = a.follow
    if a.friend is not None:
        fields["daily_friend_limit"] = a.friend
    if a.comment is not None:
        fields["daily_comment_limit"] = a.comment
    if not fields:
        print("[ERROR] 설정할 값이 없음 (--follow/--friend/--comment 중 하나 필요)")
        sys.exit(1)

    print(f"대상: {a.account_code} ({rid})")
    print(f"변경: {fields}")
    if a.dry_run:
        print("(dry-run - PATCH 안 함)")
        return

    rr = requests.patch(f"{URL}/{rid}", headers=H, json={"fields": fields}, timeout=15)
    if rr.status_code not in (200, 201):
        print("ERROR:", rr.status_code, rr.text[:300])
        sys.exit(1)
    saved = rr.json().get("fields", {})
    print("완료:", {k: saved.get(k) for k in fields})


if __name__ == "__main__":
    main()
