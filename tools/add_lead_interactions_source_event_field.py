"""
tools/add_lead_interactions_source_event_field.py

Lead_Interactions 테이블에 source_event_id 필드(singleLineText)를 추가합니다.
FP-047 댓글 이벤트 idempotency 설계(docs/design/FP047_COMMENT_EVENT_IDEMPOTENCY_260715.md)의
Airtable 측 dedup 키 — (conversation_channel, source_event_id) 조합으로 사용.

실행:
    python tools/add_lead_interactions_source_event_field.py

전제 조건:
    .env 에 AIRTABLE_API_KEY, AIRTABLE_BASE_ID 설정 필요.
    API 토큰에 schema.bases:write 권한 필요.
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_NAME = "Lead_Interactions"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

NEW_FIELDS = [
    {
        "name": "source_event_id",
        "type": "singleLineText",
        "description": "FP-047 idempotency key — 댓글은 Meta comment_id, 향후 DM 채널 확장 대비 범용 명명",
    },
]


def get_table_id(base_id: str, table_name: str) -> str:
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    res = requests.get(url, headers=HEADERS, timeout=10)

    if res.status_code == 403:
        print("[ERROR] 403 Forbidden — API 토큰에 schema.bases:read 권한이 없습니다.")
        sys.exit(1)

    res.raise_for_status()
    tables = res.json().get("tables", [])

    for t in tables:
        if t["name"] == table_name:
            return t["id"]

    available = [t["name"] for t in tables]
    print(f"[ERROR] '{table_name}' 테이블을 찾을 수 없습니다. 현재 목록: {available}")
    sys.exit(1)


def get_existing_field_names(base_id: str, table_id: str) -> set:
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    res = requests.get(url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    for t in res.json().get("tables", []):
        if t["id"] == table_id:
            return {f["name"] for f in t.get("fields", [])}
    return set()


def add_field(base_id: str, table_id: str, field: dict) -> bool:
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables/{table_id}/fields"
    res = requests.post(url, headers=HEADERS, json=field, timeout=10)

    if res.status_code == 200:
        created = res.json()
        print(f"  [OK] '{created['name']}' (id={created['id']}) 추가 완료")
        return True

    if res.status_code == 422:
        detail = res.json().get("error", {})
        print(f"  [SKIP] '{field['name']}' — {detail.get('message', '이미 존재하거나 충돌')}")
        return False

    print(f"  [ERROR] '{field['name']}' 추가 실패 — HTTP {res.status_code}: {res.text}")
    return False


def main():
    if not API_KEY or not BASE_ID:
        print("[ERROR] .env 에 AIRTABLE_API_KEY, AIRTABLE_BASE_ID 가 설정되지 않았습니다.")
        sys.exit(1)

    print(f"Base: {BASE_ID}")
    print(f"Table: {TABLE_NAME}\n")

    table_id = get_table_id(BASE_ID, TABLE_NAME)
    print(f"table_id = {table_id}\n")

    existing = get_existing_field_names(BASE_ID, table_id)
    print(f"기존 필드 수: {len(existing)}개\n")

    added = 0
    for field in NEW_FIELDS:
        if field["name"] in existing:
            print(f"  [SKIP] '{field['name']}' — 이미 존재함")
            continue
        if add_field(BASE_ID, table_id, field):
            added += 1

    print(f"\n완료: {added}개 추가")


if __name__ == "__main__":
    main()
