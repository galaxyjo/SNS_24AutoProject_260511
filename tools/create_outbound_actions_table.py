"""
tools/create_outbound_actions_table.py

Outbound_Actions 테이블을 Airtable Meta API 로 생성한다 (STEP 3, 260901 회장 승인).
YUNA outbound engagement(현재 Follow 1종) 결과의 SSOT.

실행:
    python tools/create_outbound_actions_table.py

전제:
    .env 에 AIRTABLE_API_KEY / AIRTABLE_BASE_ID 설정.
    토큰에 schema.bases:read + schema.bases:write 권한 필요.

안전:
    - 이미 존재하면 POST 하지 않고 종료(ALREADY_EXISTS).
    - 필드는 최소 8개(모두 text 계열, singleSelect 없음).
"""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_ID = os.getenv("AIRTABLE_BASE_ID")
API_KEY = os.getenv("AIRTABLE_API_KEY")
TABLE_NAME = "Outbound_Actions"

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
META_URL = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"

FIELDS = [
    {"name": "action_code", "type": "singleLineText",
     "description": "예: OA-1A2B3C4D (uuid4 앞 8자리)"},
    {"name": "account_code_ref", "type": "singleLineText",
     "description": "Account_Registry.account_code 참조 — 예: IDN-000041(yuna18253)"},
    {"name": "target_url", "type": "url",
     "description": "대상 Facebook 프로필/페이지 URL"},
    {"name": "target_identifier", "type": "singleLineText",
     "description": "target_url 에서 결정론적으로 추출한 식별자(숫자 id 또는 username) — 중복방지 키"},
    {"name": "action_type", "type": "singleLineText",
     "description": "follow (STEP 3 범위). friend_request 는 미구현."},
    {"name": "result", "type": "singleLineText",
     "description": "success / failed — 실제 클릭 시도 결과만. skipped 는 기록하지 않음."},
    {"name": "occurred_at", "type": "singleLineText",
     "description": "ISO 8601 UTC 문자열 — 예: 2026-09-01T00:00:00Z"},
    {"name": "error_reason", "type": "multilineText",
     "description": "result=failed 사유(follow_button_not_found / state_not_confirmed / 예외 메시지)"},
]


def main() -> None:
    if not BASE_ID or not API_KEY:
        print("[ERROR] .env 의 AIRTABLE_BASE_ID / AIRTABLE_API_KEY 미설정")
        sys.exit(1)

    r = requests.get(META_URL, headers=HEADERS, timeout=15)
    if r.status_code == 403:
        print("[ERROR] 403 - 토큰에 schema.bases:read 권한 필요")
        sys.exit(1)
    r.raise_for_status()
    existing = {t["name"] for t in r.json().get("tables", [])}
    if TABLE_NAME in existing:
        print(f"ALREADY_EXISTS - {TABLE_NAME} 이미 존재. POST 금지.")
        return

    print(f"{TABLE_NAME} 없음 - 생성 진행")
    body = {"name": TABLE_NAME, "fields": FIELDS,
            "description": "STEP 3(260901) — YUNA outbound engagement action 결과 SSOT. Follow 1종부터."}
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
