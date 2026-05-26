"""
tools/create_persona_profile_table.py
Airtable Metadata API로 Persona_Profile 테이블과 전체 필드를 생성한다.
"""
import os, sys, requests
from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_NAME = "Persona_Profile"
META_URL = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

# account_code_ref 링크 필드를 위해 Account_Registry 테이블 ID 먼저 조회
def get_table_id(name: str) -> str | None:
    res = requests.get(META_URL, headers=HEADERS, timeout=10)
    res.raise_for_status()
    for t in res.json().get("tables", []):
        if t["name"] == name:
            return t["id"]
    return None


def table_exists() -> bool:
    res = requests.get(META_URL, headers=HEADERS, timeout=10)
    res.raise_for_status()
    return any(t["name"] == TABLE_NAME for t in res.json().get("tables", []))


def build_fields(account_registry_id: str) -> list[dict]:
    return [
        # persona_code는 Airtable Name 필드(자동 생성)를 재활용하므로 첫 필드로 선언
        # → 테이블 생성 시 fields[0]이 primary field가 됨
        {"name": "persona_code",       "type": "singleLineText"},
        {"name": "account_code_ref",   "type": "multipleRecordLinks",
         "options": {"linkedTableId": account_registry_id}},
        {"name": "persona_name",       "type": "singleLineText"},
        {"name": "persona_role",       "type": "singleLineText"},
        {"name": "mbti_type",          "type": "singleLineText"},
        {"name": "tone_style",         "type": "multilineText"},
        {"name": "greeting_template",  "type": "multilineText"},
        {"name": "followup_template",  "type": "multilineText"},
        {"name": "language",           "type": "singleLineText"},
        {"name": "active",             "type": "checkbox",
         "options": {"color": "greenBright", "icon": "check"}},
        {"name": "created_at",         "type": "date",
         "options": {"dateFormat": {"name": "iso"}}},
        {"name": "last_updated",       "type": "date",
         "options": {"dateFormat": {"name": "iso"}}},
    ]


def create_table(fields: list[dict]) -> dict:
    payload = {"name": TABLE_NAME, "fields": fields}
    res = requests.post(META_URL, headers=HEADERS, json=payload, timeout=15)
    res.raise_for_status()
    return res.json()


def run():
    print(f"[1] 사전 확인 — {TABLE_NAME} 테이블 존재 여부")
    if table_exists():
        print(f"[SKIP] {TABLE_NAME} 이미 존재함 — 중복 생성 생략.")
        sys.exit(0)

    print(f"[2] Account_Registry 테이블 ID 조회")
    acct_table_id = get_table_id("Account_Registry")
    if not acct_table_id:
        print("[FAIL] Account_Registry 테이블을 찾을 수 없음.")
        sys.exit(1)
    print(f"     → {acct_table_id}")

    print(f"[3] {TABLE_NAME} 테이블 생성 요청")
    fields = build_fields(acct_table_id)
    result = create_table(fields)

    new_id = result.get("id", "")
    created_fields = [f["name"] for f in result.get("fields", [])]

    print(f"[OK] 테이블 생성 완료 — table_id: {new_id}")
    print(f"     생성된 필드 ({len(created_fields)}개):")
    for fn in created_fields:
        print(f"       - {fn}")


if __name__ == "__main__":
    run()
