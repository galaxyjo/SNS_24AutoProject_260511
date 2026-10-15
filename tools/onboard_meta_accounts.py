"""
tools/onboard_meta_accounts.py — 261015 Meta 계정 연결 자동화(Sale1 방식 ②~⑤).

Sale1(IDN-000048) 수작업 순서를 그대로 자동화한다.
  ② Galaxy 비즈니스의 공유/소유 페이지를 System User(insta_auto_bot)에 배정
  ③ me/accounts 로 Page ID·IG ID 조회
  ④ Airtable Account_Registry 빈칸 5개 입력(account_code·ig_user_id·fb_page_id·credential_key·api_provider)
  ⑤ .env 에 {credential_key}_INSTA_IG_USER_ID / _INSTA_ACCESS_TOKEN 2줄 추가
① 페이지 공유 승인은 페이지 주인이 해야 하므로 이 도구가 하지 않는다.

안전 규칙:
  - 기본은 dry-run(조회만). 쓰기는 --apply 를 줄 때만.
  - 운영 계정 IDN-000036·IDN-000041 은 제외.
  - IG username 이 Airtable 레코드 정확히 1건과 일치할 때만 매핑(0건·2건 이상은 보고만).
  - 이미 값이 있는 칸은 덮어쓰지 않는다. 다른 값이면 충돌로 보고 그 계정 전체를 건너뛴다.
  - 같은 IG ID·Page ID 가 다른 레코드에 이미 있으면 막는다.
  - automation_enabled 는 건드리지 않는다(자동게시 OFF 유지).
  - 토큰은 화면·로그에 출력하지 않는다.

실행:
    .venv/Scripts/python.exe tools/onboard_meta_accounts.py            # dry-run
    .venv/Scripts/python.exe tools/onboard_meta_accounts.py --apply --only IDN-000048
"""

import argparse
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
GRAPH = "https://graph.facebook.com/v21.0/"
BUSINESS_ID = "24274599308882640"          # Galaxy International Co., Ltd. (verified)
SYSTEM_USER_ID = "122130806499322626"      # insta_auto_bot
TOKEN_ENV = "YUNA_INSTA_ACCESS_TOKEN"      # 현재 System User Token 이 들어 있는 키(재사용)
PROTECTED_IDS = {"IDN-000036", "IDN-000041"}
PAGE_TASKS = ["CREATE_CONTENT", "MODERATE", "MESSAGING", "ANALYZE"]   # Sale1 실배정과 동일(MANAGE 불필요)
KEY_RE = re.compile(r"^[A-Z0-9_]+$")
FIELDS = ("account_code", "ig_user_id", "fb_page_id", "credential_key", "api_provider")


def norm(s) -> str:
    return re.sub(r"[\s@/]", "", str(s or "").lower())


def default_key(identity_id: str) -> str:
    return identity_id.replace("-", "_")          # IDN-000052 → IDN_000052


# ── 순수 계획 함수(테스트 대상) ──────────────────────────────────────────────

def _index(ar_records: list, field: str) -> dict:
    """값 → 그 값을 가진 identity 집합. 같은 값이 여러 레코드에 있어도 축약하지 않는다."""
    m = defaultdict(set)
    for r in ar_records:
        v = r["fields"].get(field)
        if v:
            m[str(v)].add(r["fields"].get("identity_id") or f"(identity 없음:{r['id']})")
    return m


def build_plan(pages: list, ar_records: list, pa_records: list, env_text: str,
               only: "set | None" = None) -> list:
    """pages: [{page_id, page_name, assigned(bool), ig_id, ig_username}]
    ar_records: Airtable Account_Registry raw records, pa_records: Platform_Accounts raw records.
    반환: 계정별 계획 dict 목록(status = ready / no_change / skip).
    중복은 입력 순서와 무관하게 판정하며, 중복에 걸린 항목은 모두 skip(Fail-closed)."""
    env_count = Counter(re.findall(r"^([A-Z0-9_]+)=", env_text, re.M))
    env_vals = dict(re.findall(r"^([A-Z0-9_]+)=(.*)$", env_text, re.M))
    ids_count = Counter(r["fields"].get("identity_id") for r in ar_records if r["fields"].get("identity_id"))
    by_id = {r["fields"].get("identity_id"): r for r in ar_records if r["fields"].get("identity_id")}
    used_ig, used_page, used_key = _index(ar_records, "ig_user_id"), _index(ar_records, "fb_page_id"), _index(ar_records, "credential_key")

    def ig_candidates(ig_username) -> set:
        u = norm(ig_username)
        if not u:
            return set()
        hit = {r["fields"].get("identity_id") for r in ar_records if norm(r["fields"].get("account_handle")) == u}
        hit |= {p["fields"].get("identity_id") for p in pa_records
                if p["fields"].get("platform") == "Instagram" and norm(p["fields"].get("username")) == u}
        return {h for h in hit if h}

    def page_candidates(page_id, page_name) -> set:
        """이름(FacebookPAGE 행) 기준만. Page ID 기준 매칭은 c_id 에서 따로 한다."""
        hit = set()
        n = norm(page_name)
        if n:
            hit |= {p["fields"].get("identity_id") for p in pa_records
                    if p["fields"].get("platform") == "FacebookPAGE" and norm(p["fields"].get("username")) == n}
        return {h for h in hit if h and not h.startswith("(identity 없음")}

    plan = []
    for pg in pages:
        item = {"page_id": pg["page_id"], "page_name": pg.get("page_name"), "ig_username": pg.get("ig_username"),
                "ig_id": pg.get("ig_id"), "airtable_record_id": None,
                "assign": not pg.get("assigned"), "status": "skip", "reason": "", "identity_id": None,
                "airtable": {}, "env": []}
        c_ig = ig_candidates(pg.get("ig_username"))
        c_pg = page_candidates(pg["page_id"], pg.get("page_name"))
        touched = c_ig | c_pg | used_ig.get(str(pg.get("ig_id") or ""), set()) | used_page.get(str(pg["page_id"]), set())
        if touched & PROTECTED_IDS:
            item["identity_id"] = sorted(touched & PROTECTED_IDS)[0]
            item["reason"] = "운영 계정 보호(036·041 제외)"
            plan.append(item)
            continue
        # 261015 ID 우선 매칭: Meta 고유 ID(IG ID → Page ID)로 Airtable과 1:1이면 확정.
        # 이름은 ID가 없을 때만 쓰고, ID가 있으면 보조 검증(이름 매칭이 있으면 그 안에 포함돼야 함).
        c_id = (used_ig.get(str(pg.get("ig_id") or ""), set()) | used_page.get(str(pg["page_id"]), set()))
        c_id = {h for h in c_id if not h.startswith("(identity 없음")}
        names = c_ig | c_pg
        if len(c_id) > 1:
            item["reason"] = f"ID 충돌 {sorted(c_id)}"
            plan.append(item)
            continue
        if c_id:
            if names and not (c_id <= names):
                item["reason"] = f"ID 매칭 {sorted(c_id)} ≠ 이름 매칭 {sorted(names)}"
                plan.append(item)
                continue
            cands = c_id
        else:
            if c_ig and c_pg and c_ig != c_pg:
                item["reason"] = f"IG 매칭 {sorted(c_ig)} ≠ 페이지 매칭 {sorted(c_pg)}"
                plan.append(item)
                continue
            cands = c_ig or c_pg
        if len(cands) != 1:
            item["reason"] = f"Airtable 매칭 {len(cands)}건(정확히 1건 필요)"
            plan.append(item)
            continue
        idn = next(iter(cands))
        item["identity_id"] = idn
        rec = by_id.get(idn)
        if not rec or ids_count[idn] != 1:
            item["reason"] = "Account_Registry 레코드 없음" if not rec else f"identity_id {idn} 레코드 {ids_count[idn]}건"
            plan.append(item)
            continue
        item["airtable_record_id"] = rec["id"]
        if not pg.get("ig_id"):
            if pg.get("assigned"):
                item["reason"] = "페이지에 IG 미연결"
            else:
                # 배정 전에는 IG ID 가 보이지 않는다 → identity 가 확정된 페이지만 배정하고, 매핑은 재실행에서 한다.
                item["status"] = "ready"
                item["reason"] = "배정만(IG ID 는 배정 후 재실행에서 조회·매핑)"
            plan.append(item)
            continue
        f = rec["fields"]
        key = f.get("credential_key") or default_key(idn)
        want = {"account_code": idn, "ig_user_id": pg["ig_id"], "fb_page_id": pg["page_id"],
                "credential_key": key, "api_provider": "facebook_login"}
        conflicts = [k for k, v in want.items() if f.get(k) and f.get(k) != v]
        if not KEY_RE.fullmatch(key):
            conflicts.append("credential_key 형식")
        for label, idx, val in (("ig_user_id", used_ig, pg["ig_id"]), ("fb_page_id", used_page, pg["page_id"]),
                                ("credential_key", used_key, key)):
            others = idx.get(str(val), set()) - {idn}
            if others:
                conflicts.append(f"{label} 가 {sorted(others)} 에서 사용 중")
        for suffix in ("_INSTA_IG_USER_ID", "_INSTA_ACCESS_TOKEN"):
            if env_count[key + suffix] > 1:
                conflicts.append(f".env {key}{suffix} 중복")
        env_ig = env_vals.get(f"{key}_INSTA_IG_USER_ID", "").strip()
        if env_ig and env_ig != pg["ig_id"]:
            conflicts.append(".env IG ID 불일치")
        if conflicts:
            item["reason"] = "충돌: " + ", ".join(conflicts)
            plan.append(item)
            continue
        item["airtable"] = {k: v for k, v in want.items() if not f.get(k)}
        if not env_ig:
            item["env"].append(f"{key}_INSTA_IG_USER_ID")
        if not env_vals.get(f"{key}_INSTA_ACCESS_TOKEN", "").strip():
            item["env"].append(f"{key}_INSTA_ACCESS_TOKEN")
        item["credential_key"] = key
        item["status"] = "ready" if (item["assign"] or item["airtable"] or item["env"]) else "no_change"
        plan.append(item)

    # 계획 내부 중복(같은 identity·IG·Page·키가 두 항목 이상) → 관련 항목 모두 skip(순서 무관)
    live = [p for p in plan if p["status"] in ("ready", "no_change")]
    for field in ("identity_id", "ig_id", "page_id", "credential_key"):
        cnt = Counter(p.get(field) for p in live if p.get(field))
        for p in live:
            if p.get(field) and cnt[p[field]] > 1 and p["status"] != "skip":
                p["status"], p["airtable"], p["env"] = "skip", {}, []
                p["reason"] = f"계획 내 중복 {field}={p[field]}"

    if only:
        plan = [p for p in plan if p.get("identity_id") in only]
    return plan


def render_env_append(plan: list, token: str, today: str) -> str:
    """.env 끝에 붙일 텍스트(토큰은 이 문자열에만 존재 — 출력·로그 금지)."""
    lines = []
    for p in plan:
        if p["status"] != "ready" or not p["env"]:
            continue
        lines.append(f"# {today} {p['identity_id']} {p.get('ig_username')} (insta_auto_bot System User Token, facebook_login)")
        for k in p["env"]:
            lines.append(f"{k}={p['ig_id']}" if k.endswith("_IG_USER_ID") else f"{k}={token}")
    return ("\n".join(lines) + "\n") if lines else ""


class PartialApplyError(RuntimeError):
    """실행 도중 실패. report 에 수동 원복에 필요한 정보만 담는다(Secret 없음)."""

    def __init__(self, report: dict):
        super().__init__("부분 적용 후 중단")
        self.report = report


def _check(verify, *args) -> str:
    """실패 직후 원격 상태를 Read-only 로 다시 본다. True→applied, False→not_applied, 그 외→UNKNOWN."""
    if verify is None:
        return "UNKNOWN"
    try:
        r = verify(*args)
    except Exception:
        return "UNKNOWN"
    return "applied" if r is True else ("not_applied" if r is False else "UNKNOWN")


def apply_plan(plan: list, *, assign_page, patch_airtable, append_env, token: str, today: str,
               verify_assign=None, verify_airtable=None, verify_env=None) -> dict:
    """ready 항목만 실행. I/O 는 주입받는다(테스트 가능).

    - 쓰기 직전에 대상·작업을 writes 에 'pending' 으로 먼저 기록하고, 성공하면 'applied' 로 바꾼다.
    - 쓰기가 예외(Timeout 포함)로 끝나면 재시도하지 않고, verify_* 로 원격 상태를 Read-only 재조회해
      applied / not_applied / UNKNOWN 을 판정한 뒤 즉시 중단(PartialApplyError).
    - 자동 원복은 하지 않는다. report 에는 수동 원복에 필요한 대상만 담는다(Secret 없음)."""
    done = {"assigned": 0, "airtable": 0, "env_lines": 0}
    writes = []           # [{"op","identity_id","target","fields","outcome"}]
    ready = [p for p in plan if p["status"] == "ready"]

    def stop(step, p, exc, entry):
        msg = str(exc).replace(token, "***") if token else str(exc)
        started = {w["identity_id"] for w in writes}
        raise PartialApplyError({
            "failed_step": step,
            "failed_identity": p.get("identity_id") if p else None,
            "failed_outcome": entry["outcome"],
            "error": f"{type(exc).__name__}: {msg[:160]}",
            "writes": writes,
            "manual_rollback": [w for w in writes if w["outcome"] in ("applied", "UNKNOWN")],
            "not_started": [q.get("identity_id") or q["page_id"] for q in ready
                            if (q.get("identity_id") or q["page_id"]) not in started],
        })

    def write(op, p, target, fields, call, verify, verify_args):
        entry = {"op": op, "identity_id": p.get("identity_id") if p else None, "target": target,
                 "fields": fields, "outcome": "pending"}
        writes.append(entry)
        try:
            call()
        except Exception as exc:
            entry["outcome"] = _check(verify, *verify_args)
            stop(op, p, exc, entry)
        entry["outcome"] = "applied"

    for p in ready:
        if p["assign"]:
            write("meta_assign", p, p["page_id"], [], lambda: assign_page(p["page_id"]),
                  verify_assign, (p["page_id"],))
            done["assigned"] += 1
        if p["airtable"]:
            fields = dict(p["airtable"])
            write("airtable_patch", p, p["airtable_record_id"], sorted(fields),
                  lambda: patch_airtable(p["airtable_record_id"], dict(fields)),
                  verify_airtable, (p["airtable_record_id"], fields))
            done["airtable"] += 1
    text = render_env_append(ready, token, today)
    if text:
        keys = [k for p in ready for k in p["env"]]
        write("env_append", None, ".env", keys, lambda: append_env(text), verify_env, (text,))
        done["env_lines"] = len(keys)
    return done


# ── 외부 I/O ────────────────────────────────────────────────────────────────

def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def fetch_pages(token: str) -> list:
    def get(path, **params):
        r = requests.get(GRAPH + path, params={**params, "access_token": token}, timeout=30)
        body = r.json()
        if "error" in body:
            raise RuntimeError(f"Graph GET {path.split('?')[0]} 실패: {body['error'].get('message', '')[:120]}")
        return body.get("data", [])
    assigned = {p["id"]: p for p in get("me/accounts", fields="id,name,instagram_business_account{id,username}", limit=100)}
    biz = {p["id"]: p for p in get(f"{BUSINESS_ID}/client_pages", fields="id,name", limit=100)}
    biz.update({p["id"]: p for p in get(f"{BUSINESS_ID}/owned_pages", fields="id,name", limit=100)})
    pages = []
    for pid in sorted(set(assigned) | set(biz)):
        a = assigned.get(pid)
        iba = (a or {}).get("instagram_business_account") or {}
        pages.append({"page_id": pid, "page_name": (a or biz.get(pid) or {}).get("name"), "assigned": bool(a),
                      "ig_id": iba.get("id"), "ig_username": iba.get("username")})
    return pages


def fetch_airtable(table: str) -> list:
    url = f"https://api.airtable.com/v0/{_env('AIRTABLE_BASE_ID')}/{table}"
    h = {"Authorization": f"Bearer {_env('AIRTABLE_API_KEY')}"}
    out, off = [], None
    while True:
        b = requests.get(url, headers=h, params={"pageSize": 100, **({"offset": off} if off else {})}, timeout=30).json()
        if "error" in b:
            raise RuntimeError(f"Airtable GET {table} 실패: {str(b['error'])[:120]}")
        out += b.get("records", [])
        off = b.get("offset")
        if not off:
            return out


def print_plan(plan: list) -> None:
    for p in plan:
        print(f"[{p['status']}] page={p['page_id']}({p.get('page_name')}) ig={p.get('ig_username')} "
              f"identity={p.get('identity_id')} assign={p['assign']} "
              f"airtable={sorted(p['airtable'])} env={p['env']} {p['reason']}")
    print(f"합계: ready={sum(p['status']=='ready' for p in plan)} no_change={sum(p['status']=='no_change' for p in plan)} "
          f"skip={sum(p['status']=='skip' for p in plan)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제 쓰기(기본은 dry-run)")
    ap.add_argument("--only", nargs="*", help="이 identity_id 만 처리(Canary)")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows cp949 콘솔에서 한글·기호 출력 오류 방지
    except Exception:
        pass
    sys.path.insert(0, str(ROOT))
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
    token = _env(TOKEN_ENV)
    if not token:
        print(f"{TOKEN_ENV} 없음 — 중단")
        return 2
    pages = fetch_pages(token)
    plan = build_plan(pages, fetch_airtable("Account_Registry"), fetch_airtable("Platform_Accounts"),
                      (ROOT / ".env").read_text(encoding="utf-8", errors="replace"),
                      set(args.only) if args.only else None)
    print_plan(plan)
    if not args.apply:
        print("dry-run — 아무것도 쓰지 않았습니다.")
        return 0
    if any(p["status"] == "ready" and p["assign"] for p in plan):
        print("배정이 필요한 페이지가 있습니다 — 배정 후 IG ID 를 다시 조회해야 하므로 1회 실행 후 재실행하세요.")
    stamp = datetime.now().strftime("%y%m%d_%H%M%S")
    bdir = ROOT / "backup" / f"pre_onboard_{stamp}"
    bdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / ".env", bdir / "env.bak")
    import json
    (bdir / "account_registry.json").write_text(
        json.dumps(fetch_airtable("Account_Registry"), ensure_ascii=False, indent=1), encoding="utf-8")
    at_url = f"https://api.airtable.com/v0/{_env('AIRTABLE_BASE_ID')}/Account_Registry"
    at_h = {"Authorization": f"Bearer {_env('AIRTABLE_API_KEY')}", "Content-Type": "application/json"}

    def assign_page(page_id):
        r = requests.post(GRAPH + f"{page_id}/assigned_users", timeout=30, data={
            "user": SYSTEM_USER_ID, "tasks": json.dumps(PAGE_TASKS), "business": BUSINESS_ID, "access_token": token})
        if r.status_code != 200:
            raise RuntimeError(f"배정 실패 page={page_id} status={r.status_code}")

    def patch_airtable(rid, fields):
        requests.patch(f"{at_url}/{rid}", headers=at_h, json={"fields": fields}, timeout=30).raise_for_status()

    def append_env(text):
        raw = (ROOT / ".env").read_bytes()
        nl = b"\r\n" if b"\r\n" in raw else b"\n"
        body = text.replace("\n", nl.decode()).encode("utf-8")
        (ROOT / ".env").write_bytes((raw if raw.endswith(nl) else raw + nl) + body)

    # 실패 직후 Read-only 재조회(재시도 아님). 판단 불가면 None → UNKNOWN.
    def verify_assign(page_id):
        r = requests.get(GRAPH + f"{page_id}/assigned_users", timeout=30,
                         params={"business": BUSINESS_ID, "fields": "id", "access_token": token})
        body = r.json()
        if "error" in body:
            return None
        return any(u.get("id") == SYSTEM_USER_ID for u in body.get("data", []))

    def verify_airtable(rid, fields):
        r = requests.get(f"{at_url}/{rid}", headers=at_h, timeout=30)
        if r.status_code != 200:
            return None
        cur = r.json().get("fields", {})
        same = [cur.get(k) == v for k, v in fields.items()]
        return True if all(same) else (False if not any(cur.get(k) for k in fields) else None)

    def verify_env(text):
        return text.replace("\n", "") in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").replace("\r", "").replace("\n", "")

    try:
        done = apply_plan(plan, assign_page=assign_page, patch_airtable=patch_airtable, append_env=append_env,
                          token=token, today=datetime.now().strftime("%y%m%d"),
                          verify_assign=verify_assign, verify_airtable=verify_airtable, verify_env=verify_env)
    except PartialApplyError as e:
        print("부분 적용 후 중단 — 수동 원복 정보(Secret 없음):")
        print(json.dumps(e.report, ensure_ascii=False, indent=1))
        print(f"원복: Meta 배정 → 비즈니스 설정에서 insta_auto_bot 제거 또는 "
              f"DELETE /{{page_id}}/assigned_users?user={SYSTEM_USER_ID}&business={BUSINESS_ID} | "
              f"Airtable·.env → {bdir.relative_to(ROOT)} 백업으로 복원")
        return 4
    print(f"apply 완료: {done} | 백업: {bdir.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
