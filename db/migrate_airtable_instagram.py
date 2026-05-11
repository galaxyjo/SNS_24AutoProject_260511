"""
Airtable Instagram_Posts 테이블에 retry_count, error_message 컬럼 추가.

Airtable Metadata API 사용:
  - GET  /meta/bases/{baseId}/tables          → 테이블 ID 조회 + 기존 필드 목록
  - POST /meta/bases/{baseId}/tables/{tableId}/fields → 필드 생성

실행:
  python db/migrate_airtable_instagram.py
"""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TARGET_TABLE = "Instagram_Posts"

META_BASE_URL = "https://api.airtable.com/v0/meta/bases"

NEW_FIELDS = [
    {
        "name": "retry_count",
        "type": "number",
        "options": {"precision": 0},
    },
    {
        "name": "last_error_msg",
        "type": "multilineText",
    },
]


def _headers() -> dict:
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def get_table_meta() -> tuple[str, set[str]]:
    """Instagram_Posts 테이블 ID와 기존 필드명 집합 반환."""
    url = f"{META_BASE_URL}/{BASE_ID}/tables"
    res = requests.get(url, headers=_headers(), timeout=15)

    if res.status_code == 401:
        sys.exit("[ERROR] AIRTABLE_API_KEY 인증 실패 (401)")
    if res.status_code == 403:
        sys.exit(
            "[ERROR] Metadata API 접근 권한 없음 — Personal Access Token에 schema.bases:read 스코프 필요"
        )
    if not res.ok:
        sys.exit(f"[ERROR] 테이블 목록 조회 실패: {res.status_code} {res.text}")

    tables = res.json().get("tables", [])
    for table in tables:
        if table["name"] == TARGET_TABLE:
            existing = {f["name"] for f in table.get("fields", [])}
            return table["id"], existing

    sys.exit(f"[ERROR] '{TARGET_TABLE}' 테이블을 찾을 수 없음 (BASE_ID={BASE_ID})")


def create_field(table_id: str, field_def: dict) -> None:
    url = f"{META_BASE_URL}/{BASE_ID}/tables/{table_id}/fields"
    res = requests.post(url, headers=_headers(), json=field_def, timeout=15)

    if res.status_code == 403:
        sys.exit(
            "[ERROR] 필드 생성 권한 없음 — Personal Access Token에 schema.bases:write 스코프 필요"
        )

    if not res.ok:
        # 422 = 이미 존재하는 경우도 있으므로 메시지 출력 후 계속
        print(f"  [WARN] '{field_def['name']}' 생성 실패: {res.status_code} {res.text}")
        return

    created = res.json()
    print(
        f"  [OK] '{created['name']}' 생성 완료 (id={created['id']}, type={created['type']})"
    )


def main() -> None:
    if not API_KEY:
        sys.exit("[ERROR] AIRTABLE_API_KEY 환경변수 미설정")
    if not BASE_ID:
        sys.exit("[ERROR] AIRTABLE_BASE_ID 환경변수 미설정")

    print(f"[MIGRATE] 대상: {TARGET_TABLE} (base={BASE_ID})")

    table_id, existing_fields = get_table_meta()
    print(f"[MIGRATE] 테이블 ID: {table_id}")
    print(f"[MIGRATE] 기존 필드: {sorted(existing_fields)}\n")

    for field_def in NEW_FIELDS:
        name = field_def["name"]
        if name in existing_fields:
            print(f"  [SKIP] '{name}' 이미 존재")
            continue
        print(f"  [ADD]  '{name}' ({field_def['type']}) 생성 중...")
        create_field(table_id, field_def)

    print("\n[MIGRATE] 완료")


if __name__ == "__main__":
    main()
