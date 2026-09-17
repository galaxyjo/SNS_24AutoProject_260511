"""
tools/create_prospect_groups_table.py

Prospect_Groups 테이블을 Airtable Meta API 로 생성한다 (STEP 3-B1R, 260901 회장 승인).
친구추가/Follow Prospecting 대상 Facebook 그룹 목록. 콘텐츠 크롤 대상(Crawl_Targets)과
분리 — 이 테이블의 그룹은 "그룹 작성자 = 판매자 후보" 추출용이다.

실행:
    python tools/create_prospect_groups_table.py

전제:
    .env 에 AIRTABLE_API_KEY / AIRTABLE_BASE_ID.
    토큰 scope: schema.bases:read + schema.bases:write.

안전:
    - 이미 존재하면 POST 하지 않고 종료(ALREADY_EXISTS).
    - 필드 8개(전부 text 계열 + number 1개).
"""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_ID = os.getenv("AIRTABLE_BASE_ID")
API_KEY = os.getenv("AIRTABLE_API_KEY")
TABLE_NAME = "Prospect_Groups"

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
META_URL = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"

FIELDS = [
    {"name": "group_code", "type": "singleLineText",
     "description": "PG-001 형식"},
    {"name": "group_url", "type": "url",
     "description": "Facebook 그룹 URL (회장 제공)"},
    {"name": "group_id", "type": "singleLineText",
     "description": "그룹 URL 에서 추출한 숫자 id"},
    {"name": "group_name", "type": "singleLineText",
     "description": "그룹 표시명(선택)"},
    {"name": "priority", "type": "number", "options": {"precision": 0},
     "description": "처리 순서. 낮을수록 먼저. 회장 제공 그룹 = 1"},
    {"name": "prospecting_status", "type": "singleLineText",
     "description": "active / hold / done"},
    {"name": "added_at", "type": "singleLineText",
     "description": "ISO 8601 UTC 문자열"},
    {"name": "notes", "type": "multilineText"},
]


def main() -> None:
    if not BASE_ID or not API_KEY:
        print("[ERROR] .env 의 AIRTABLE_BASE_ID / AIRTABLE_API_KEY 미설정")
        sys.exit(1)

    r = requests.get(META_URL, headers=HEADERS, timeout=15)
    if r.status_code == 403:
        print("[ERROR] 403 — 토큰에 schema.bases:read 권한 필요")
        sys.exit(1)
    r.raise_for_status()
    existing = {t["name"] for t in r.json().get("tables", [])}
    if TABLE_NAME in existing:
        print(f"ALREADY_EXISTS - {TABLE_NAME} 이미 존재. POST 금지.")
        return

    print(f"{TABLE_NAME} 없음 - 생성 진행")
    body = {"name": TABLE_NAME, "fields": FIELDS,
            "description": "STEP 3-B1R(260901) - 친구추가/Follow Prospecting 대상 FB 그룹. Crawl_Targets(콘텐츠 크롤)와 분리."}
    r2 = requests.post(META_URL, headers=HEADERS, json=body, timeout=15)
    print("POST status:", r2.status_code)
    if r2.status_code not in (200, 201):
        print("ERROR:", r2.text[:500])
        sys.exit(1)

    d = r2.json()
    print("table_id:", d.get("id"))
    for f in d.get("fields", []):
        print("  ", f["name"], "|", f["type"])


if __name__ == "__main__":
    main()
