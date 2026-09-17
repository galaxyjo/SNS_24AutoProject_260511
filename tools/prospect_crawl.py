"""
tools/prospect_crawl.py — 그룹 회원 크롤 / Prospect 1명 enrichment (STEP 3-D1 / 3-E, 260901)

회장이 AdsPower(YUNA 프로필 k1bto3j4) 켠 상태에서 직접 실행한다.
Follow/Friend/Like/Comment/Message 클릭 없음. View + Read + Queue Write 만.
CAPTCHA / 로그인 승인 / 계정 제한 화면이 뜨면 스크립트가 자동 중단, 회장은 창을 닫는다.

[그룹 회원 목록 크롤 — STEP 3-D1]
    python tools/prospect_crawl.py PG-009                        # dry-run
    python tools/prospect_crawl.py PG-009 --run --no-write --max 15   # 결과만 출력
    python tools/prospect_crawl.py PG-009 --run                       # + Prospect_Queue 적재

[Prospect 1명 프로필 확인 → Queue 기록 — STEP 3-E]
    python tools/prospect_crawl.py --enrich "<회원 프로필 URL>" --group PG-009        # dry-run
    python tools/prospect_crawl.py --enrich "<회원 프로필 URL>" --group PG-009 --run   # 프로필 1회 방문 + Queue 1건
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("group", nargs="?", help="Prospect_Groups 의 group_code(PG-###) 또는 group_url")
    ap.add_argument("--run", action="store_true", help="실제 실행(미지정 시 dry-run)")
    ap.add_argument("--no-write", dest="write", action="store_false", help="Prospect_Queue 미기록, 결과만 출력")
    ap.add_argument("--max", type=int, default=15, help="추출할 회원 최대 수")
    ap.add_argument("--source", default="members", choices=["members", "feed"])
    ap.add_argument("--action", default=None, choices=["follow", "friend_request"],
                    help="미지정 시 crawl=follow / enrich=friend_request")
    ap.add_argument("--enrich", metavar="PROFILE_URL", help="[STEP 3-E] 이 회원 프로필 1명만 확인 → Queue 1건")
    ap.add_argument("--group", dest="enrich_group", help="[STEP 3-E] --enrich 대상의 source_group_code (예: PG-009)")
    ap.add_argument("--friend-canary", dest="friend_canary", metavar="PG-### | URL",
                    help="[STEP 3-G] 그룹 → 해외 회원 프로필 → '친구 추가' 1회. --run 필수.")
    ap.add_argument("--friend-daily", dest="friend_daily", metavar="PG-### | URL",
                    help="[STEP 3-G] 한 세션에서 daily_friend_limit 까지 2~4분 랜덤 간격 연속 발송. --run 필수.")
    ap.add_argument("--max-requests", dest="max_requests", type=int, default=10,
                    help="--friend-daily 목표 건수(상한, 실제는 daily_friend_limit 로 제한). 기본 10.")
    ap.add_argument("--kpi", action="store_true", help="[STEP 3-G] 오늘 친구요청 성공 집계(로컬) 출력")
    a = ap.parse_args()

    if a.kpi:
        # STEP 3-G: 개인별 저장 없음 — 로컬 date+count 집계만 본다
        from modules.interaction_engine.outbound_connector import (
            YUNA_ACCOUNT_CODE, _friend_daily_count, _kst_today)
        print(f"DATE : {_kst_today()}")
        print(f"YUNA friend_requests_success_today : {_friend_daily_count(YUNA_ACCOUNT_CODE)}")
        sys.exit(0)

    if a.friend_canary or a.friend_daily:
        if a.run:
            os.environ["OUTBOUND_FRIEND_LIVE_ENABLED"] = "true"
        from modules.interaction_engine.outbound_pipeline import friend_canary_from_group
        target = a.friend_daily or a.friend_canary
        n = a.max_requests if a.friend_daily else 1
        result = friend_canary_from_group(target, max_requests=n, dry_run=not a.run)
        print("RESULT :", {k: v for k, v in result.items() if k != "friend"})
        fr = result.get("friend") or {}
        print("FRIEND :", {k: v for k, v in fr.items() if k != "results"})
        for r in fr.get("results", []):
            print("  -", r)
        sys.exit(0 if fr.get("result") == "success"
                or (result.get("status") == "done" and not a.run) else 1)

    if a.enrich:
        if not a.enrich_group:
            ap.error("--enrich 사용 시 --group PG-### 필요")
        from modules.interaction_engine.outbound_pipeline import enrich_one_prospect
        result = enrich_one_prospect(
            a.enrich, group_code=a.enrich_group,
            action_type=a.action or "friend_request", dry_run=not a.run,
        )
        print(result)
        sys.exit(0 if result.get("status") in ("written", "dedup", "dry_run") else 1)

    if not a.group:
        ap.error("group (PG-### 또는 URL) 필요 — 또는 --enrich 사용")

    from modules.interaction_engine.outbound_pipeline import crawl_group_prospects
    result = crawl_group_prospects(
        a.group, action_type=a.action or "follow", source=a.source,
        max_authors=a.max, write=a.write, dry_run=not a.run,
    )
    print({k: v for k, v in result.items() if k != "samples"})
    for s in result.get("samples", []):
        print("  -", s["decision"], "|", s.get("reason", ""), "| score", s.get("score"),
              "|", s["name"][:40], "|", s["url"])
    sys.exit(0 if result.get("status") in ("done", "dry_run") else 1)


if __name__ == "__main__":
    main()
