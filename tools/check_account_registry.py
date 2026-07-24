"""
tools/check_account_registry.py
Airtable Account_Registry 테이블에서 ACC-001 레코드를 조회해
ig_user_id / fb_page_id / account_email 값이 정상 존재하는지 검증한다.
"""
import os
import sys

from dotenv import load_dotenv
load_dotenv(override=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.common.airtable_bridge import get_table

EXPECTED = {
    "ig_user_id":    "17841476202821375",
    "fb_page_id":    "868456346356581",
    "account_email": "nguyenknv15@gmail.com",
}

TABLE = "Account_Registry"
TARGET_CODE = "ACC-001"


def run():
    print(f"[CHECK] Airtable {TABLE} → {TARGET_CODE}")
    table = get_table(TABLE)

    records = table.all(formula=f"{{account_code}}='{TARGET_CODE}'")
    if not records:
        print(f"[FAIL] {TARGET_CODE} 레코드 없음 — Airtable에 레코드를 먼저 생성하세요.")
        return

    fields = records[0].get("fields", {})
    record_id = records[0]["id"]
    print(f"[OK]   record_id = {record_id}")
    print()

    all_pass = True
    for key, expected_val in EXPECTED.items():
        actual = str(fields.get(key, "")).strip()
        if actual == expected_val:
            print(f"  ✅ {key}: {actual}")
        else:
            print(f"  ❌ {key}: 기대={expected_val!r}  실제={actual!r}")
            all_pass = False

    print()
    if all_pass:
        print("[RESULT] 모든 필드 일치 — Account_Registry ACC-001 정상.")
    else:
        print("[RESULT] 불일치 항목 있음 — Airtable에서 해당 필드 값을 수정하세요.")


if __name__ == "__main__":
    run()
