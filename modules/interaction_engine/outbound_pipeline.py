"""
modules/interaction_engine/outbound_pipeline.py — 그룹 → 후보 → Prospect_Queue (STEP 3-C, 260901)

입력 → 판단 → 기록 오케스트레이터. 클릭(follow/friend) 은 하지 않는다.

흐름 (STEP 3-D1, 회장 260901 — 운영 기준):
  Prospect_Groups 의 그룹 1개
  → 그룹 /members 페이지에서 회원 프로필 URL 수집 (source="members", 기본)
  → outbound_rules.evaluate 로 필터/스코어
  → (write=True) Prospect_Queue 에 status(filtered_out/scored/needs_review) 로 적재
  회장은 Prospect_Queue 에서 scored·needs_review 를 검토 → approved → (별도) 실행.
  ※ source="feed"(게시물 작성자 DOM 역추출)는 DEFER — _find_group_authors 코드는 남겨둠.

REUSE:
  - 브라우저      : facebook_crawler.get_driver / stop_browser  (기존 콘텐츠 크롤과 동일 프로필·리스크)
  - 작성자 추출   : outbound_connector._find_group_authors
  - 차단 대조     : facebook_crawler.load_supplier_blocklist / is_blocked_supplier
  - 필터/스코어   : outbound_rules.evaluate
  - checkpoint   : outbound_connector._checkpoint_detected
  - 중복/한도     : AirtableRepository (find_prospect_by_target / find_outbound_action)

안전:
  - dry_run=True 기본 — 브라우저 미기동, 계획만 반환.
  - 읽기 전용(클릭 없음) — Live 게이트 env 없음. 단 checkpoint 감지 시 즉시 중단.
  - scored 도 자동 approved 로 넘기지 않는다(status='scored' 로만) — 승인은 사람이.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone

from modules.common.logger import get_logger
from modules.interaction_engine import outbound_connector as oc
from modules.interaction_engine.outbound_rules import evaluate

logger = get_logger(__name__)

YUNA_ACCOUNT_CODE = "IDN-000041"
_PAGE_SETTLE_SEC = 12  # facebook_crawler.run 과 동일

# rules.evaluate decision → Prospect_Queue.status
_STATUS_BY_DECISION = {
    "filtered_out": "filtered_out",
    "needs_review": "needs_review",
    "scored": "scored",
}


def _default_repo():
    from modules.infra.airtable_repository import AirtableRepository
    return AirtableRepository()


def _resolve_group(repo, group_url_or_code: str) -> dict | None:
    """Prospect_Groups 에서 group_url 또는 group_code 로 그룹 1건을 찾는다."""
    import requests
    from modules.infra import airtable_repository as ar

    key = (group_url_or_code or "").strip()
    field = "group_url" if key.startswith("http") else "group_code"
    safe = key.replace("'", "\\'")
    r = requests.get(
        ar._url("Prospect_Groups"), headers=ar._headers(),
        params={"filterByFormula": f"{{{field}}}='{safe}'", "maxRecords": 1},
        timeout=ar._TIMEOUT,
    )
    r.raise_for_status()
    recs = r.json().get("records", [])
    if not recs:
        # Prospect_Groups 에 없어도 raw 그룹 URL 이면 ad-hoc 허용(회장이 직접 URL 지정).
        # /members/things_in_common 같은 하위 뷰가 붙어 있으면 그대로 보존한다(STEP 3-G Ground Truth).
        m = re.search(r"facebook\.com/groups/([^/?#]+)(/members[^?#]*)?", key)
        if m:
            gid, sub = m.group(1), (m.group(2) or "")
            return {"group_code": f"ADHOC-{gid[:20]}",
                    "group_url": f"https://www.facebook.com/groups/{gid}{sub}",
                    "prospecting_status": "adhoc"}
        return None
    f = recs[0].get("fields", {})
    return {"group_code": f.get("group_code", ""), "group_url": f.get("group_url", ""),
            "prospecting_status": f.get("prospecting_status", "")}


def _build_info(author: dict) -> dict:
    """추출된 작성자 → ProspectInfo. 피드에서 보이는 정보만(프로필 심층조회 안 함)."""
    txt = author.get("card_text") or author.get("feed_text") or ""
    return {
        "display_name": author.get("name", ""),
        "profile_url": author.get("profile_url", ""),
        "bio_text": txt,
        "location_text": "",
        "page_category": "",
        "recent_post_text": txt,
        "follower_count": -1,
        "has_photo": True,
        "is_private": False,
        "has_recent_activity": True,
    }


def crawl_group_prospects(
    group_url_or_code: str,
    *,
    action_type: str = "follow",
    source: str = "members",   # "members"(기본, /members 페이지) | "feed"(게시물 작성자 — DEFER)
    max_authors: int = 20,
    write: bool = True,
    dry_run: bool = True,
    repo=None,
    driver_factory=None,
    browser_stopper=None,
) -> dict:
    """그룹 1개에서 Prospect 후보를 수집 → 필터 → (write=True 면) Prospect_Queue 적재.
    클릭(follow/friend) 없음. source='members' 가 현재 운영 기준(회장 260901)."""
    if action_type not in ("follow", "friend_request"):
        raise ValueError(f"action_type must be follow|friend_request, got {action_type!r}")
    if source not in ("members", "feed"):
        raise ValueError(f"source must be members|feed, got {source!r}")

    repo = repo or _default_repo()
    group = _resolve_group(repo, group_url_or_code)
    if not group or not group["group_url"]:
        return {"status": "error", "reason": "group_not_in_prospect_groups",
                "query": group_url_or_code}

    base = {"status": "", "group_code": group["group_code"], "group_url": group["group_url"],
            "source": source, "action_type": action_type, "write": write,
            "crawled": 0, "created": 0, "filtered_out": 0, "needs_review": 0,
            "scored": 0, "skipped_dup": 0, "samples": []}

    if dry_run:
        base["status"] = "dry_run"
        logger.info(f"[Pipeline] dry_run | group={group['group_code']} source={source}")
        return base

    from modules.sns.facebook_crawler import load_supplier_blocklist, is_blocked_supplier

    blocklist = load_supplier_blocklist()
    make_driver = driver_factory or oc._default_driver_factory
    stop_browser = browser_stopper or oc._default_browser_stopper
    driver = make_driver()
    try:
        if source == "members":
            driver.get(oc.group_members_url(group["group_url"]))
        else:
            driver.get(group["group_url"])
        time.sleep(_PAGE_SETTLE_SEC)
        cp = oc._checkpoint_detected(driver)
        if cp:
            base["status"] = "aborted"
            base["reason"] = f"checkpoint:{cp}"
            return base

        if source == "members":
            candidates = oc._find_group_members(driver, limit=max_authors)
        else:
            candidates = oc._find_group_authors(driver, limit=max_authors)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        for a in candidates:
            base["crawled"] += 1
            ident = a.get("identifier") or oc._loose_identifier(a.get("profile_url", ""))

            if repo.find_prospect_by_target(ident, action_type) or \
               repo.find_outbound_action(YUNA_ACCOUNT_CODE, ident, action_type):
                base["skipped_dup"] += 1
                continue

            bl = is_blocked_supplier(a.get("name", ""), blocklist)
            info = _build_info(a)
            res = evaluate(info, blocklist_hit=bool(bl), source_is_beauty_group=True)
            status = _STATUS_BY_DECISION[res["decision"]]
            base[res["decision"]] += 1
            if len(base["samples"]) < 15:
                base["samples"].append({
                    "name": a.get("name", ""), "url": a.get("profile_url", ""),
                    "decision": res["decision"], "reason": res["filter_reason"],
                    "score": res["score"],
                })

            if not write:
                continue
            try:
                repo.create_prospect({
                    "source_group_code_ref": group["group_code"],
                    "target_url": a.get("profile_url", ""),
                    "target_identifier": ident,
                    "display_name": a.get("name", ""),
                    "action_type": action_type,
                    "status": status,
                    "score": res["score"],
                    "score_detail": res["score_detail"],
                    "filter_reason": res["filter_reason"],
                    "evidence": (info.get("bio_text", "") or "")[:500],
                    "collected_at": now,
                })
                base["created"] += 1
            except Exception as exc:
                logger.error(f"[Pipeline] create_prospect 실패 | {ident} | {type(exc).__name__}: {exc}")

        base["status"] = "done"
        logger.info(f"[Pipeline] 완료 | {dict((k, v) for k, v in base.items() if k != 'samples')}")
        return base
    finally:
        try:
            driver.quit()
        except Exception as exc:
            logger.warning(f"[Pipeline] driver.quit 실패 | {exc}")
        try:
            stop_browser()
        except Exception as exc:
            logger.warning(f"[Pipeline] stop_browser 실패 | {exc}")


CANARY_READY = "CANARY_TARGET_READY"


def friend_canary_from_group(
    group_url_or_code: str,
    *,
    account_code: str = YUNA_ACCOUNT_CODE,
    max_requests: int = 1,
    pace_range: tuple = (120, 240),
    dry_run: bool = True,
    repo=None,
    driver_factory=None,
    browser_stopper=None,
) -> dict:
    """STEP 3-G: 그룹 /members 목록 → 해외 회원 프로필 → '친구 추가' 클릭.
    max_requests>1 이면 한 세션에서 daily_friend_limit 까지 pace_range(초) 랜덤 간격으로 연속 발송.
    개인 저장 없음. 일일 집계는 canary 가 반환하는 daily_count 를 그대로 쓴다."""
    repo = repo or _default_repo()
    group = _resolve_group(repo, group_url_or_code)
    if not group or not group["group_url"]:
        return {"status": "error", "reason": "group_not_in_prospect_groups",
                "query": group_url_or_code}

    result = oc.friend_request_canary(
        group["group_url"], account_code=account_code,
        max_requests=max_requests, pace_range=pace_range,
        dry_run=dry_run, repo=repo,
        driver_factory=driver_factory, browser_stopper=browser_stopper,
    )
    logger.info(f"[FriendCanary] group={group['group_code']} → {result}")

    out = {"status": "done", "group_code": group["group_code"], "friend": result}
    if not dry_run:
        out["daily_count"] = result.get("daily_count")
        out["sent"] = result.get("sent")
    return out


# ── STEP 3-F: Friend KPI (Outbound_Actions REUSE, 별도 KPI 시스템 없음) ─────────

def daily_friend_kpi(account_code: str = YUNA_ACCOUNT_CODE, *, repo=None) -> dict:
    """오늘(UTC) friend_request KPI. Source = Outbound_Actions."""
    repo = repo or _default_repo()
    from datetime import datetime as _dt, timezone as _tz
    today = _dt.now(_tz.utc).strftime("%Y-%m-%d")
    rows = repo.list_outbound_actions_since(account_code, "friend_request", today)
    cap = int(repo.get_account_outbound_limits(account_code).get("friend", 0) or 0)
    attempted = len(rows)
    success = sum(1 for r in rows if r.get("result") == "success")
    sent = sum(1 for r in rows if r.get("relationship_status") == "requested")
    return {
        "friend_requests_attempted_today": attempted,
        "friend_requests_success_today": success,
        "friend_requests_failed_today": attempted - success,
        "daily_limit": cap,
        "remaining_today": max(0, cap - sent),
    }


def monthly_friend_kpi(account_code: str = YUNA_ACCOUNT_CODE, *, repo=None) -> dict:
    """이번 달(UTC) friend_request KPI + 실제 친구된 수(relationship_status=accepted)."""
    repo = repo or _default_repo()
    from datetime import datetime as _dt, timezone as _tz
    month = _dt.now(_tz.utc).strftime("%Y-%m")
    rows = repo.list_outbound_actions_since(account_code, "friend_request", month)
    sent = sum(1 for r in rows if r.get("relationship_status") in ("requested", "accepted"))
    accepted = sum(1 for r in rows if r.get("relationship_status") == "accepted")
    rate = round(accepted / sent, 4) if sent else 0.0
    return {
        "friend_requests_sent_this_month": sent,
        "friends_accepted_this_month": accepted,
        "acceptance_rate": rate,
    }


def enrich_one_prospect(
    target_url: str,
    *,
    group_code: str,
    action_type: str = "friend_request",
    account_code: str = YUNA_ACCOUNT_CODE,
    dry_run: bool = True,
    repo=None,
    driver_factory=None,
    browser_stopper=None,
) -> dict:
    """회원 1명의 프로필을 1회 방문 → (한국제외 / 정상프로필 / 친구버튼존재 / 중복 / Kill-switch /
    일일한도) 확인 → Prospect_Queue 1건 기록 (STEP 3-E). **클릭 없음.**
    조건 전부 통과 시 status=CANARY_TARGET_READY, 아니면 filtered_out."""
    if action_type not in ("follow", "friend_request"):
        raise ValueError(f"action_type must be follow|friend_request, got {action_type!r}")
    limit_key = "friend" if action_type == "friend_request" else "follow"

    repo = repo or _default_repo()
    ident = oc._loose_identifier(target_url)
    out = {"status": "", "group_code": group_code, "target_url": target_url,
           "target_identifier": ident, "action_type": action_type}

    existing = repo.find_prospect_by_target(ident, action_type) or \
        repo.find_outbound_action(account_code, ident, action_type)
    if existing:
        out.update({"status": "dedup", "record_id": existing, "duplicate": True})
        logger.info(f"[Enrich] 이미 존재 — skip | {ident} rec={existing}")
        return out
    out["duplicate"] = False

    if dry_run:
        out["status"] = "dry_run"
        logger.info(f"[Enrich] dry_run | {target_url}")
        return out

    # 시스템 상태 게이트 (read-only) — 결과는 RESULT 에만, 레코드는 별개
    acct = repo.get_publish_account(account_code)
    kill_switch_on = bool(acct and acct.get("automation_enabled", False))
    limits = repo.get_account_outbound_limits(account_code)
    cap = int(limits.get(limit_key, 0) or 0)
    used = repo.count_outbound_actions_today(account_code, action_type)
    limit_ok = used < cap
    out.update({"kill_switch": "on" if kill_switch_on else "off",
                "daily_limit": f"{'ok' if limit_ok else 'exceeded'}:{used}/{cap}"})

    from modules.sns.facebook_crawler import load_supplier_blocklist, is_blocked_supplier

    blocklist = load_supplier_blocklist()
    make_driver = driver_factory or oc._default_driver_factory
    stop_browser = browser_stopper or oc._default_browser_stopper
    driver = make_driver()
    try:
        driver.get(target_url)
        time.sleep(_PAGE_SETTLE_SEC)
        cp = oc._checkpoint_detected(driver)
        if cp:
            out.update({"status": "aborted", "reason": f"checkpoint:{cp}"})
            return out
        info = oc._extract_profile_info(driver, target_url)
        friend_button = oc._has_friend_add_button(driver)
    finally:
        try:
            driver.quit()
        except Exception as exc:
            logger.warning(f"[Enrich] driver.quit 실패 | {exc}")
        try:
            stop_browser()
        except Exception as exc:
            logger.warning(f"[Enrich] stop_browser 실패 | {exc}")

    bl = is_blocked_supplier(info.get("display_name", ""), blocklist)
    res = evaluate(info, blocklist_hit=bool(bl), source_is_beauty_group=True)
    reason = res["filter_reason"]
    korean_excluded = reason in ("korean_based", "korean_national")
    profile_normal = not info.get("is_private", False) and reason != "abnormal_profile"

    if korean_excluded:
        q_status, q_reason = "filtered_out", reason
    elif not profile_normal:
        q_status, q_reason = "filtered_out", "abnormal_profile"
    elif reason in ("blocklist", "other_industry"):
        q_status, q_reason = "filtered_out", reason
    elif not friend_button:
        q_status, q_reason = "filtered_out", "friend_button_not_found"
    else:
        q_status, q_reason = CANARY_READY, ""

    evidence = (
        f"loc={info.get('location_text') or 'UNKNOWN'} | "
        f"bio={(info.get('bio_text') or 'UNKNOWN')[:180]} | "
        f"friend_button={'yes' if friend_button else 'no'} | "
        f"rule={res['decision']}/{reason} | "
        f"kill_switch={out['kill_switch']} daily_limit={out['daily_limit']}"
    )
    rid = repo.create_prospect({
        "source_group_code_ref": group_code,
        "target_url": target_url,
        "target_identifier": ident,
        "display_name": info.get("display_name", ""),
        "action_type": action_type,
        "status": q_status,
        "score": res["score"],
        "score_detail": res["score_detail"],
        "filter_reason": q_reason,
        "evidence": evidence[:500],
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    out.update({
        "status": "written", "record_id": rid, "queue_status": q_status,
        "display_name": info.get("display_name", ""),
        "location_text": info.get("location_text", ""),
        "profile_normal": profile_normal,
        "korean_exclusion": korean_excluded,
        "friend_button": "found" if friend_button else "not_found",
        "rule": f"{res['decision']}/{reason}",
    })
    logger.info(
        f"[Enrich] 완료 | {ident} queue_status={q_status} friend_button={friend_button} "
        f"kill_switch={out['kill_switch']} daily_limit={out['daily_limit']} rec={rid}"
    )
    return out


# ── STEP 3-G HUMAN SOP (260903): Airtable 그룹 순회 → 하루 한도까지 친구요청 ─────────
# Airtable 역할은 "어떤 그룹을 방문할지" URL 목록 제공뿐. 개인/결과/수율 저장 없음.

def _active_group_urls(repo=None) -> list[tuple[str, str]]:
    """Prospect_Groups 의 active 그룹 (group_code, group_url) 목록 — Airtable 순서 그대로."""
    import requests
    from modules.infra import airtable_repository as ar

    r = requests.get(
        ar._url("Prospect_Groups"), headers=ar._headers(),
        params={"filterByFormula": "{prospecting_status}='active'", "maxRecords": 100},
        timeout=ar._TIMEOUT,
    )
    r.raise_for_status()
    out = []
    for rec in r.json().get("records", []):
        f = rec.get("fields", {})
        url = (f.get("group_url") or "").strip()
        if url:
            out.append((f.get("group_code", "?"), url))
    return out


_STOP_ALL_PREFIXES = ("checkpoint", "daily_blocked", "automation_disabled")


def friend_daily_run(
    account_code: str = YUNA_ACCOUNT_CODE,
    *,
    dry_run: bool = True,
    max_per_run: int | None = None,
    repo=None,
    group_urls: list | None = None,
    pace_range: tuple = (30, 60),
    driver_factory=None,
    browser_stopper=None,
) -> dict:
    """STEP 3-G Human SOP: Airtable active 그룹을 순서대로 방문하며 daily_friend_limit 까지
    친구요청한다. 브라우저 1개를 그룹 간 재사용하고, 현재 그룹이 소진되면 다음 그룹으로 계속한다.
    한도(10건) 도달 시 즉시 종료. 계정 안전 신호(checkpoint/day-block/Kill-switch)면 전체 중단.
    max_per_run 을 주면 **이번 실행에서만** 그 건수까지 보낸다(24시간 분산 스케줄용, 예: 1)."""
    repo = repo or _default_repo()
    cap = int((repo.get_account_outbound_limits(account_code) or {}).get("friend", 0) or 0)
    sent_before = oc._friend_daily_count(account_code)
    out: dict = {"status": "", "account_code": account_code, "cap": cap,
                 "sent_before": sent_before, "sent": 0, "groups_visited": [], "results": []}

    groups = group_urls if group_urls is not None else _active_group_urls(repo)
    if dry_run:
        out["status"] = "dry_run"
        out["groups"] = [g for g, _ in groups]
        return out
    if cap <= 0 or sent_before >= cap:
        out.update({"status": "skipped", "reason": f"daily_limit:{sent_before}/{cap}"})
        return out
    if not groups:
        out.update({"status": "failed", "reason": "no_active_groups"})
        return out

    driver = (driver_factory or oc._default_driver_factory)()
    stop_browser = browser_stopper or oc._default_browser_stopper
    try:
        for gcode, gurl in groups:
            remaining = cap - oc._friend_daily_count(account_code)
            if max_per_run is not None:
                remaining = min(remaining,
                                max_per_run - (oc._friend_daily_count(account_code) - sent_before))
            if remaining <= 0:
                out["status"] = "done"
                break
            logger.info(f"[FriendDaily] 그룹 진입 | {gcode} | 남은 {remaining}건")
            res = oc.friend_request_canary(
                gurl, account_code=account_code, max_requests=remaining,
                pace_range=pace_range, dry_run=False, repo=repo, driver=driver,
            )
            out["groups_visited"].append(gcode)
            out["results"].append({"group_code": gcode, "result": res.get("result"),
                                   "reason": res.get("reason"), "sent": res.get("sent")})
            reason = str(res.get("reason") or "")
            if res.get("result") == "skipped" and reason.startswith(_STOP_ALL_PREFIXES):
                out.update({"status": "stopped", "reason": reason})
                logger.warning(f"[FriendDaily] 계정 안전 신호 — 전체 중단 | {reason}")
                break
    finally:
        try:
            driver.quit()
        except Exception as exc:
            logger.warning(f"[FriendDaily] driver.quit 실패 | {exc}")
        try:
            stop_browser()
        except Exception as exc:
            logger.warning(f"[FriendDaily] stop_browser 실패 | {exc}")

    out["daily_count"] = oc._friend_daily_count(account_code)
    out["sent"] = out["daily_count"] - sent_before
    out["status"] = out["status"] or "done"
    logger.info(f"[FriendDaily] 완료 | status={out['status']} sent={out['sent']} "
                f"daily_count={out['daily_count']}/{cap} groups={out['groups_visited']}")
    return out
