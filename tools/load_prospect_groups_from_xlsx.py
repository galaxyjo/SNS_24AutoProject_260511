"""
tools/load_prospect_groups_from_xlsx.py

회장 제공 "FB 그룹 리스트.xlsx" 의 지정 시트에서 Facebook 그룹 URL 을 뽑아
Airtable Prospect_Groups 에 idempotent upsert 한다 (STEP 3-B1R, 260901).

주의:
  - 이 엑셀에는 계정 email/비밀번호 컬럼이 있다. 그 컬럼은 절대 읽지/저장하지 않는다.
  - 저장 대상은 group_url / group_id / group_name / 멤버수 note 뿐이다.
  - 이미 있는 group_id 는 건너뛴다(중복 생성 안 함).

실행:
    python tools/load_prospect_groups_from_xlsx.py
    python tools/load_prospect_groups_from_xlsx.py --dry-run
"""

import os
import re
import sys
from datetime import datetime, timezone

import openpyxl
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

XLSX = r"C:\Users\admin\OneDrive\Desktop\2025list\FB 그룹 리스트.xlsx"
SHEET = "베트남인1.수출-화장품 "   # 회장: "1시트 화장품"
TABLE = "Prospect_Groups"

BASE_ID = os.getenv("AIRTABLE_BASE_ID")
API_KEY = os.getenv("AIRTABLE_API_KEY")
H = {"Authorization": f"Bearer {API_KEY}"}
HJ = {**H, "Content-Type": "application/json"}
URL = f"https://api.airtable.com/v0/{BASE_ID}/{requests.utils.quote(TABLE)}"

DRY = "--dry-run" in sys.argv


def parse_groups(path: str, sheet: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    seen: set[str] = set()
    out: list[dict] = []
    for row in ws.iter_rows(values_only=True):
        cells = [str(c).strip() if c is not None else "" for c in row]
        name = cells[0] if cells else ""
        url_cell = cells[1] if len(cells) > 1 else ""
        desc = cells[2] if len(cells) > 2 else ""
        m = re.search(r"facebook\.com/groups/([^/?#]+)", url_cell)
        if not m:
            continue
        gid = m.group(1)
        if gid in seen:
            continue
        seen.add(gid)
        deleted = ("없어짐" in name) or ("없어짐" in desc)
        # 사람 이름이 들어온 행(원본이 /user/ 링크)은 그룹명으로 신뢰하지 않는다
        looks_like_person = bool(re.fullmatch(r"[가-힣]{2,4}", name))
        out.append({
            "group_id": gid,
            "group_url": f"https://www.facebook.com/groups/{gid}",
            "group_name": "" if looks_like_person else name[:150],
            "members_note": desc[:120],
            "deleted": deleted,
            "name_unverified": looks_like_person,
        })
    return out


def existing_group_ids() -> set[str]:
    ids: set[str] = set()
    offset = None
    while True:
        params = {"pageSize": 100, "fields[]": "group_id"}
        if offset:
            params["offset"] = offset
        r = requests.get(URL, headers=H, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        for rec in j.get("records", []):
            gid = rec.get("fields", {}).get("group_id")
            if gid:
                ids.add(str(gid))
        offset = j.get("offset")
        if not offset:
            break
    return ids


def main() -> None:
    if not BASE_ID or not API_KEY:
        print("[ERROR] .env AIRTABLE_BASE_ID / AIRTABLE_API_KEY 미설정")
        sys.exit(1)

    groups = parse_groups(XLSX, SHEET)
    print(f"엑셀 파싱: {len(groups)} 그룹 (시트={SHEET!r})")

    have = existing_group_ids()
    print(f"Prospect_Groups 기존 group_id: {len(have)}")

    to_add = [g for g in groups if g["group_id"] not in have]
    print(f"신규 추가 대상: {len(to_add)} / 이미 있음: {len(groups) - len(to_add)}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    start_n = len(have)
    created = 0
    for i, g in enumerate(to_add, start=1):
        note_bits = [g["members_note"]]
        if g["deleted"]:
            note_bits.append("SOURCE: 없어짐(deleted) 표기 — 확인 필요")
        if g["name_unverified"]:
            note_bits.append("group_name 미확정(원본이 user 링크 행)")
        note_bits.append(f"source=FB그룹리스트.xlsx/{SHEET.strip()}")
        fields = {
            "group_code": f"PG-{start_n + i:03d}",
            "group_url": g["group_url"],
            "group_id": g["group_id"],
            "group_name": g["group_name"],
            "priority": 1,   # 회장: 크롤 대상보다 먼저
            "prospecting_status": "hold" if g["deleted"] else "active",
            "added_at": now,
            "notes": " | ".join(b for b in note_bits if b),
        }
        if DRY:
            print("  DRY", fields["group_code"], g["group_id"], fields["prospecting_status"], g["group_name"][:40])
            continue
        r = requests.post(URL, headers=HJ, json={"fields": fields}, timeout=30)
        if r.status_code not in (200, 201):
            print("  ERROR", g["group_id"], r.status_code, r.text[:200])
            continue
        created += 1
        print("  +", fields["group_code"], g["group_id"], fields["prospecting_status"], g["group_name"][:40])

    print(f"\n완료: {'(dry-run)' if DRY else created} 생성")


if __name__ == "__main__":
    main()
