"""
tools/add_account_registry_outbound_limits.py

Account_Registry 에 아웃바운드 액션 일일 한도 3개를 Airtable Meta API 로 추가한다
(STEP 3-C, 260901 회장 결정 1-A).

  - daily_follow_limit   (number, precision 0)
  - daily_friend_limit   (number, precision 0)
  - daily_comment_limit  (number, precision 0)

의미(코드에서): 값이 비어있으면(미설정) = 0 = 해당 액션 자동차단(Fail-closed,
automation_enabled 와 동일 철학). 라이브 전 회장이 계정별로 명시 설정.

실행:
    python tools/add_account_registry_outbound_limits.py

전제: .env AIRTABLE_API_KEY / AIRTABLE_BASE_ID, 토큰 scope schema.bases:read+write.
안전: 이미 있는 필드는 건너뜀(중복 추가 안 함).
"""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_NAME = "Account_Registry"

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
META_URL = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"

NEW_FIELDS = [
    {"name": "daily_follow_limit", "type": "number", "options": {"precision": 0},
     "description": "STEP 3-C: 이 계정의 하루 최대 팔로우 수. 비어있으면 0(차단)."},
    {"name": "daily_friend_limit", "type": "number", "options": {"precision": 0},
     "description": "STEP 3-C: 이 계정의 하루 최대 친구요청 수. 비어있으면 0(차단)."},
    {"name": "daily_comment_limit", "type": "number", "options": {"precision": 0},
     "description": "STEP 3-C: 이 계정의 하루 최대 아웃바운드 댓글 수. 비어있으면 0(차단). (댓글 기능은 DEFER)"},
]


def main() -> None:
    if not API_KEY or not BASE_ID:
        print("[ERROR] .env AIRTABLE_API_KEY / AIRTABLE_BASE_ID 미설정")
        sys.exit(1)

    r = requests.get(META_URL, headers=HEADERS, timeout=15)
    if r.status_code == 403:
        print("[ERROR] 403 — 토큰 scope schema.bases:read 필요")
        sys.exit(1)
    r.raise_for_status()

    tables = r.json().get("tables", [])
    tbl = next((t for t in tables if t["name"] == TABLE_NAME), None)
    if not tbl:
        print(f"[ERROR] '{TABLE_NAME}' 테이블 없음")
        sys.exit(1)

    table_id = tbl["id"]
    existing = {f["name"] for f in tbl.get("fields", [])}
    field_url = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables/{table_id}/fields"

    added = 0
    for f in NEW_FIELDS:
        if f["name"] in existing:
            print(f"SKIP (이미 있음): {f['name']}")
            continue
        rr = requests.post(field_url, headers=HEADERS, json=f, timeout=15)
        if rr.status_code not in (200, 201):
            print(f"ERROR {f['name']}: {rr.status_code} {rr.text[:200]}")
            continue
        added += 1
        print(f"+ {f['name']} ({f['type']})")

    print(f"\n완료: {added} 필드 추가")


if __name__ == "__main__":
    main()
