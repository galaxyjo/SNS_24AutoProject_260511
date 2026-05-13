"""
tools/add_instagram_posts_fields.py

Instagram_Posts 테이블에 engagement 필드 3개를 Airtable Meta API로 추가합니다.
  - ig_media_id   (singleLineText)
  - like_count    (number, precision=0)
  - comments_count (number, precision=0)

실행:
    python tools/add_instagram_posts_fields.py

전제 조건:
    .env 에 AIRTABLE_API_KEY, AIRTABLE_BASE_ID 설정 필요.
    API 토큰에 schema.bases:write 권한이 있어야 합니다.
    (Airtable > Account > Personal Access Tokens > Scopes 에서 확인)
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_NAME = "Instagram_Posts"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

NEW_FIELDS = [
    {
        "name": "ig_media_id",
        "type": "singleLineText",
    },
    {
        "name": "like_count",
        "type": "number",
        "options": {"precision": 0},
    },
    {
        "name": "comments_count",
        "type": "number",
        "options": {"precision": 0},
    },
]


def get_table_id(base_id: str, table_name: str) -> str:
    """Meta API로 테이블 목록을 조회해 table_name의 ID를 반환."""
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    res = requests.get(url, headers=HEADERS, timeout=10)

    if res.status_code == 403:
        print("[ERROR] 403 Forbidden — API 토큰에 schema.bases:read 권한이 없습니다.")
        print("        Airtable > Account > Personal Access Tokens > 해당 토큰 편집")
        print("        > Scopes 에서 schema.bases:read / schema.bases:write 추가")
        sys.exit(1)

    res.raise_for_status()
    tables = res.json().get("tables", [])

    for t in tables:
        if t["name"] == table_name:
            return t["id"]

    available = [t["name"] for t in tables]
    print(f"[ERROR] '{table_name}' 테이블을 찾을 수 없습니다.")
    print(f"        현재 Base의 테이블 목록: {available}")
    sys.exit(1)


def get_existing_field_names(base_id: str, table_id: str) -> set:
    """이미 존재하는 필드 이름 목록을 반환 (중복 추가 방지)."""
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

    print("1) 테이블 ID 조회 중...")
    table_id = get_table_id(BASE_ID, TABLE_NAME)
    print(f"   table_id = {table_id}\n")

    print("2) 기존 필드 목록 조회 중...")
    existing = get_existing_field_names(BASE_ID, table_id)
    print(f"   기존 필드 수: {len(existing)}개\n")

    print("3) 필드 추가 시작:")
    added = 0
    skipped = 0
    for field in NEW_FIELDS:
        if field["name"] in existing:
            print(f"  [SKIP] '{field['name']}' — 이미 존재함")
            skipped += 1
            continue
        ok = add_field(BASE_ID, table_id, field)
        if ok:
            added += 1

    print(f"\n완료: {added}개 추가 / {skipped}개 스킵 (이미 존재)")

    if added > 0:
        print("\n[다음 단계]")
        print("  engagement_tracker.py 와 auto_liker.py 가 이제 정상 동작합니다.")
        print("  python -m modules.interaction_engine.interaction_scheduler 로 단독 테스트 가능.")


if __name__ == "__main__":
    main()
