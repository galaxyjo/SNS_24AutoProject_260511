"""
tools/reassign_041_assets.py — IDN-000041(YURA) 과거 게시 자산을 폴러 계정에 재사용 (기본 DRY-RUN)

기본 실행은 Airtable·ImgBB에 아무것도 쓰지 않는다(읽기 전용 HTTP GET만 수행).
--apply 를 명시하면 지정한 대상 계정에 ready 행을 최대 MAX_APPLY_COUNT건까지 만든다.

재사용 범위(261103 회장 확정 "전부 재사용"):
  - 원본: IDN-000041 의 post_status=posted 행 전부(Facebook 그룹 글 + 도매꾹 글). 041 원본 행은 읽기만 한다.
  - 캡션·해시태그는 041 것을 그대로 쓴다(계정 간 중복 허용 정책 261102). Gemini 호출 없음.
  - Gate 는 걸지 않는다 — 이미 041 에서 게시된 글이다.
  - 대상 계정 안에서 image_url_hash 가 이미 있으면 제외(계정 내 중복 금지).
  - 이미지: image_url 이 살아 있으면 그대로 / original_image_url 이 살아 있으면 ImgBB 재업로드 /
    둘 다 죽었으면 041 의 ig_media_id 로 Graph API media_url 을 받아 ImgBB 재업로드(읽기 호출).

추적/원복: 새 행은 insta_post_code 가 run_id 로 시작하고 run_id 로 묶인다.
  원복은 run_id 가 같은 행의 post_status 를 rejected 로 바꾸는 것이다(게시 전).
  canary_run_id 는 비워 둔다 — fetch_pending_posts 가 canary_run_id 가 빈 행만 읽기 때문이다.
  fetch_pending_posts 는 전체 ready 를 limit=50 으로 읽으므로, 한 번에 넣는 총량은 50건을 넘기지 않는다.

사용법:
    .venv\\Scripts\\python.exe -I tools\\reassign_041_assets.py
    .venv\\Scripts\\python.exe -I tools\\reassign_041_assets.py --apply --target IDN-000007 --count 6 --run-id R041-261103-A007 --offset 0
"""

import argparse
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=True)

SOURCE_ACCOUNT = "IDN-000041"
TARGET_ACCOUNTS = ["IDN-000007", "IDN-000014", "IDN-000039", "IDN-000048"]
MAX_APPLY_COUNT = 12
IMAGE_TIMEOUT = 15
WORKERS = 8
GRAPH = "https://graph.facebook.com/v21.0"

_env = dotenv_values(ROOT / ".env")
_HEADERS = {"Authorization": "Bearer " + _env["AIRTABLE_API_KEY"]}
_BASE = _env["AIRTABLE_BASE_ID"]
_TABLE_URL = f"https://api.airtable.com/v0/{_BASE}/Instagram_Posts"


def _fetch(formula: str, fields: list) -> list:
    out, offset = [], None
    while True:
        params = {"filterByFormula": formula, "pageSize": 100, "fields[]": fields}
        if offset:
            params["offset"] = offset
        r = requests.get(_TABLE_URL, headers=_HEADERS, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        out += j["records"]
        offset = j.get("offset")
        if not offset:
            return out


def _alive(url: str) -> bool:
    if not url:
        return False
    try:
        resp = requests.get(url, timeout=IMAGE_TIMEOUT, stream=True)
        ok = resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/")
        resp.close()
        return ok
    except requests.RequestException:
        return False


def _graph_media_url(ig_media_id: str) -> str:
    """041 이 게시한 미디어의 현재 이미지 URL(읽기 호출). 실패하면 빈 문자열."""
    token = os.getenv("YUNA_INSTA_ACCESS_TOKEN") or os.getenv("INSTA_ACCESS_TOKEN") or ""
    if not (ig_media_id and token):
        return ""
    try:
        r = requests.get(f"{GRAPH}/{ig_media_id}", params={"fields": "media_url,media_type", "access_token": token},
                         timeout=20)
        if r.status_code != 200:
            return ""
        j = r.json()
        return j.get("media_url", "") if j.get("media_type") == "IMAGE" else ""
    except requests.RequestException:
        return ""


def _load_source() -> list:
    return _fetch(
        f"AND(FIND('{SOURCE_ACCOUNT}',{{account_code_ref}}),{{post_status}}='posted')",
        ["image_url", "original_image_url", "caption", "source_url", "image_url_hash",
         "insta_post_code", "original_text", "media_type", "hashtag", "ig_media_id"],
    )


def _existing_hashes(target: str) -> set:
    rows = _fetch(f"FIND('{target}',{{account_code_ref}})", ["image_url_hash"])
    return {r["fields"].get("image_url_hash") for r in rows if r["fields"].get("image_url_hash")}


def dry_run() -> int:
    src = _load_source()
    fb = sum(1 for r in src if "facebook.com" in (r["fields"].get("source_url") or ""))
    print(f"원본 posted: {len(src)}건 ({SOURCE_ACCOUNT}) — Facebook 그룹 {fb}건, 그 외(도매꾹 등) {len(src) - fb}건")

    def _check(rec):
        f = rec["fields"]
        return rec["id"], _alive(f.get("image_url", "")), _alive(f.get("original_image_url", ""))

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        img_state = {rid: (a, b) for rid, a, b in pool.map(_check, src)}
    live_now = sum(1 for a, b in img_state.values() if a or b)
    print(f"이미지: image_url 정상 {sum(1 for a, _ in img_state.values() if a)}, "
          f"original_image_url 정상 {sum(1 for _, b in img_state.values() if b)}, "
          f"즉시 사용 가능 {live_now}, 복구 필요 {len(src) - live_now}(Graph API ig_media_id 로 시도)")
    no_caption = sum(1 for r in src if not (r["fields"].get("caption") or "").strip())
    print(f"캡션 없음 {no_caption}건(제외)")
    for target in TARGET_ACCOUNTS:
        have = _existing_hashes(target)
        dup = sum(1 for r in src if r["fields"].get("image_url_hash") in have)
        print(f"{target}: 재사용 후보 최대 {len(src) - no_caption - dup}건 | 계정 내 중복 {dup}건 | 기존 해시 {len(have)}개")
    return 0


def apply(target: str, count: int, run_id: str, offset: int) -> int:
    from modules.sns.image_hosting import upload_to_imgbb

    if target not in TARGET_ACCOUNTS:
        print(f"허용되지 않은 대상: {target}")
        return 2
    if not (1 <= count <= MAX_APPLY_COUNT):
        print(f"count 는 1~{MAX_APPLY_COUNT} 이어야 한다")
        return 2
    if not run_id.startswith("R041-"):
        print("run-id 는 'R041-' 로 시작해야 한다")
        return 2

    src = [r for r in _load_source() if (r["fields"].get("caption") or "").strip()]
    # 결정적 순서: 원본 insta_post_code 기준. offset 으로 계정마다 다른 구간부터 시작한다.
    src.sort(key=lambda r: (r["fields"].get("insta_post_code") or "~", r["id"]))
    have_hash = _existing_hashes(target)
    already = _fetch(f"AND(FIND('{target}',{{account_code_ref}}),{{run_id}}='{run_id}')", ["insta_post_code"])
    created = len(already)
    if created:
        print(f"이미 같은 run_id 로 {created}건 존재 — 이어서 만든다")
    done, skipped = 0, 0
    n = len(src)
    for i in range(n):
        if created + done >= count:
            break
        rec = src[(offset + i) % n]
        f = rec["fields"]
        if f.get("image_url_hash") in have_hash:
            continue

        image_url = f.get("image_url", "")
        orig_url = f.get("original_image_url", "")
        how = "reuse"
        if not _alive(image_url):
            up = {"success": False}
            if _alive(orig_url):
                up = upload_to_imgbb(orig_url)
                how = "reupload_original"
            if not up.get("success"):
                media_url = _graph_media_url(f.get("ig_media_id", ""))
                if media_url:
                    up = upload_to_imgbb(media_url)
                    how = "reupload_graph"
            if not up.get("success"):
                skipped += 1
                print(f"[SKIP] 이미지 복구 실패 | src={rec['id']}")
                continue
            image_url = up["public_url"]

        seq = created + done + 1
        payload = {"fields": {
            "insta_post_code": f"{run_id}-{seq:03d}",
            "account_code_ref": target,
            "post_status": "ready",
            "image_url": image_url,
            "original_image_url": orig_url,
            "image_url_hash": f.get("image_url_hash", ""),
            "source_url": f.get("source_url", ""),
            "caption": f.get("caption", ""),
            "hashtag": f.get("hashtag", ""),
            "media_type": f.get("media_type") or "image",
            "data_classification": "production",
            "run_id": run_id,
        }}
        text = (f.get("original_text") or "").strip()
        if text:
            payload["fields"]["original_text"] = text
            payload["fields"]["converted_text"] = text
        r = requests.post(_TABLE_URL, headers={**_HEADERS, "Content-Type": "application/json"},
                          json=payload, timeout=30)
        if r.status_code != 200:
            print(f"[FAIL] 행 생성 실패 status={r.status_code} body={r.text[:200]}")
            return 1
        print(f"[OK] {r.json()['id']} | {payload['fields']['insta_post_code']} | src={rec['id']} | image={how}")
        have_hash.add(f.get("image_url_hash"))
        done += 1
    print(f"완료: {done}건 생성, 이미지 복구 실패 건너뜀 {skipped}건 (target={target}, run_id={run_id})")
    return 0 if done else 1


def main() -> int:
    global IMAGE_TIMEOUT
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--target", default="")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--run-id", default="")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--image-timeout", type=int, default=IMAGE_TIMEOUT)
    a = ap.parse_args()
    IMAGE_TIMEOUT = a.image_timeout
    if a.apply:
        return apply(a.target, a.count, a.run_id, a.offset)
    return dry_run()


if __name__ == "__main__":
    sys.exit(main())
