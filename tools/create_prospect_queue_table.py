"""
tools/create_prospect_queue_table.py

Prospect_Queue 테이블을 Airtable Meta API 로 생성한다 (STEP 3-C, 260901 회장 결정 2).

친추/팔로우 대상 개인(그룹 게시물 작성자 = 판매자)의 작업 큐이자 SSOT.
Prospect_Groups(그룹 목록) → 크롤 → 이 테이블(개인 후보) → 필터/스코어 →
Approval(status=needs_review) → 실행 → Outbound_Actions 기록.

status 흐름:
  new → filtered_out | scored
  scored → needs_review | approved
  approved → actioned | failed
  needs_review → approved | skipped   (회장이 검토)

실행:
    python tools/create_prospect_queue_table.py

전제: .env AIRTABLE_API_KEY / AIRTABLE_BASE_ID, 토큰 scope schema.bases:read+write.
안전: 이미 존재하면 POST 안 함(ALREADY_EXISTS).
"""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_ID = os.getenv("AIRTABLE_BASE_ID")
API_KEY = os.getenv("AIRTABLE_API_KEY")
TABLE_NAME = "Prospect_Queue"

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
META_URL = f"https://api.airtable.com/v0/meta/bases/{BASE_ID}/tables"

FIELDS = [
    {"name": "prospect_code", "type": "singleLineText",
     "description": "PQ-000001 형식"},
    {"name": "source_group_code_ref", "type": "singleLineText",
     "description": "Prospect_Groups.group_code 참조"},
    {"name": "target_url", "type": "url",
     "description": "대상 개인 Facebook 프로필 URL"},
    {"name": "target_identifier", "type": "singleLineText",
     "description": "target_url 에서 추출한 식별자 — 중복방지 키"},
    {"name": "display_name", "type": "singleLineText",
     "description": "화면에 보이는 이름(회장의 외국인 육안 확인용 — 이름만으로 국적 자동판정 금지)"},
    {"name": "action_type", "type": "singleLineText",
     "description": "follow / friend_request"},
    {"name": "status", "type": "singleLineText",
     "description": "new / filtered_out / scored / needs_review / approved / actioned / skipped / failed"},
    {"name": "score", "type": "number", "options": {"precision": 0},
     "description": "B1R 4-signal 합계 0~100"},
    {"name": "score_detail", "type": "multilineText",
     "description": "beauty/overseas/active/dedup 배점 내역"},
    {"name": "filter_reason", "type": "singleLineText",
     "description": "filtered_out 사유: korean_based / not_beauty / blocklist / duplicate / abnormal_profile"},
    {"name": "evidence", "type": "multilineText",
     "description": "beauty·overseas·active 근거(프로필 bio/게시물에서 확인된 것만)"},
    {"name": "review_note", "type": "multilineText",
     "description": "needs_review 시 회장 판단 메모"},
    {"name": "collected_at", "type": "singleLineText",
     "description": "ISO 8601 UTC"},
    {"name": "actioned_at", "type": "singleLineText",
     "description": "ISO 8601 UTC — 실제 실행 시각"},
    {"name": "outbound_action_ref", "type": "singleLineText",
     "description": "실행 후 Outbound_Actions.action_code"},
]


def main() -> None:
    if not BASE_ID or not API_KEY:
        print("[ERROR] .env AIRTABLE_BASE_ID / AIRTABLE_API_KEY 미설정")
        sys.exit(1)

    r = requests.get(META_URL, headers=HEADERS, timeout=15)
    if r.status_code == 403:
        print("[ERROR] 403 — 토큰 scope schema.bases:read 필요")
        sys.exit(1)
    r.raise_for_status()
    if TABLE_NAME in {t["name"] for t in r.json().get("tables", [])}:
        print(f"ALREADY_EXISTS - {TABLE_NAME}. POST 금지.")
        return

    print(f"{TABLE_NAME} 없음 - 생성 진행")
    body = {"name": TABLE_NAME, "fields": FIELDS,
            "description": "STEP 3-C(260901) - 친추/팔로우 대상 개인 작업 큐 + SSOT. Prospect_Groups(그룹) → 크롤 → 여기(개인)."}
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
