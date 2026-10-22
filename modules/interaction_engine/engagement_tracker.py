"""
modules/interaction_engine/engagement_tracker.py — Instagram 게시물 engagement 지표 수집

posted 레코드의 ig_media_id로 Graph API에서 like_count / comments_count 를 조회해
Airtable Instagram_Posts에 업데이트한다.

Airtable 필드 사전 추가 필요:
  - ig_media_id   (Single line text)
  - like_count    (Number)
  - comments_count (Number)

261022 STEP 3-B — Meta Insights(계정별 토큰, v26.0 단일 GET):
  INSIGHTS_ACCOUNT_CODES(쉼표 구분 account_code, 빈 값=OFF)에 든 계정의 최근 7일
  posted 게시물만 Insights로 수집하고, 그 레코드는 아래 레거시 조회에서 뺀다.
  핵심 4개(reach/saved/shares/profile_visits)+likes/comments가 모두 와야 1회 update,
  아니면 기존 값 유지. views는 INSIGHTS_INCLUDE_VIEWS=true일 때만 요청(선택).
  필드: insights_reach / insights_saved / insights_shares / insights_profile_visits /
  insights_views (Number), insights_collected_at (dateTime, UTC).
"""

import json
import os
from datetime import datetime, timedelta, timezone

import requests

from modules.common.airtable_bridge import get_table
from modules.common.logger import get_logger
from modules.common.log_sanitizer import redact_sensitive

logger = get_logger(__name__)

IG_API = "https://graph.facebook.com/v21.0"

INSIGHTS_API_VERSION = "v26.0"
INSIGHTS_WINDOW = timedelta(days=7)
INSIGHTS_MIN_INTERVAL = timedelta(hours=6)
# launcher/main.py PROVIDER_CONFIG와 같은 값(그 모듈을 import하지 않으려고 둔 의도적 중복).
_INSIGHTS_HOSTS = {
    "facebook_login":  "graph.facebook.com",
    "instagram_login": "graph.instagram.com",
}
# Insights 지표명 → 저장 필드. 전부 와야만 저장한다.
_INSIGHTS_REQUIRED = {
    "reach":          "insights_reach",
    "saved":          "insights_saved",
    "shares":         "insights_shares",
    "profile_visits": "insights_profile_visits",
    "likes":          "like_count",
    "comments":       "comments_count",
}
_INSIGHTS_OPTIONAL = {"views": "insights_views"}


def _fetch_metrics(media_id: str, token: str) -> dict | None:
    try:
        resp = requests.get(
            f"{IG_API}/{media_id}",
            params={"fields": "like_count,comments_count", "access_token": token},
            timeout=10,
        )
        data = resp.json()
        if "error" in data:
            logger.warning(f"[Engagement] Graph API 오류 | {media_id} | {data['error'].get('message','')}")
            return None
        return {
            "like_count":      data.get("like_count", 0),
            "comments_count":  data.get("comments_count", 0),
        }
    except Exception as exc:
        logger.warning(f"[Engagement] 조회 실패 | {media_id} | {redact_sensitive(str(exc))}")
        return None


def _insights_account_codes() -> set[str]:
    raw = os.getenv("INSIGHTS_ACCOUNT_CODES", "")
    return {c.strip() for c in raw.split(",") if c.strip()}


def _parse_airtable_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_insights_target(rec: dict, codes: set[str], now: datetime) -> bool:
    """allowlist 계정 + 생성 7일 이내 레코드(게시 시각 필드가 없어 createdTime 기준)."""
    if (rec["fields"].get("account_code_ref") or "").strip() not in codes:
        return False
    created = _parse_airtable_time(rec.get("createdTime", ""))
    return created is not None and now - created <= INSIGHTS_WINDOW


def _resolve_insights_account(account_code: str, repo) -> tuple[dict | None, str]:
    """(자격증명, 오류코드). 계정의 자기 토큰만 쓰고, Airtable·.env IG ID가 다르면 차단."""
    from modules.common.credential_resolver import CredentialResolutionError, resolve_credential

    try:
        account = repo.get_publish_account(account_code)
    except Exception:
        return None, "INSIGHTS_ACCOUNT_UNRESOLVED"
    if not account:
        return None, "INSIGHTS_ACCOUNT_UNRESOLVED"
    host = _INSIGHTS_HOSTS.get(account.get("api_provider", ""))
    if not host:
        return None, "INSIGHTS_ACCOUNT_UNRESOLVED"
    try:
        cred = resolve_credential(account.get("credential_key", ""))
    except CredentialResolutionError:
        return None, "INSIGHTS_ACCOUNT_UNRESOLVED"
    if not cred.ig_user_id or cred.ig_user_id != account.get("ig_user_id", ""):
        return None, "INSIGHTS_IG_MISMATCH"
    return {"host": host, "token": cred.access_token}, ""


def _log_usage_header(media_id: str, headers) -> None:
    """x-business-use-case-usage에서 사용률 숫자만 남긴다(business id 등은 기록하지 않음)."""
    raw = (headers or {}).get("x-business-use-case-usage")
    if not raw:
        logger.info(f"[Insights] usage | {media_id} | header=absent")
        return
    try:
        entries = [e for group in json.loads(raw).values() for e in group]
        peak = {k: max(int(e.get(k, 0) or 0) for e in entries)
                for k in ("call_count", "total_cputime", "total_time", "estimated_time_to_regain_access")}
    except (ValueError, TypeError, AttributeError):
        logger.info(f"[Insights] usage | {media_id} | header=unparsed")
        return
    logger.info(
        f"[Insights] usage | {media_id} | call_count={peak['call_count']} "
        f"total_cputime={peak['total_cputime']} total_time={peak['total_time']} "
        f"regain_min={peak['estimated_time_to_regain_access']}"
    )


def _fetch_insights(media_id: str, host: str, token: str, include_views: bool) -> tuple[dict | None, str]:
    """(저장할 필드 dict, 오류코드). 필수 지표가 하나라도 없으면 None."""
    metrics = list(_INSIGHTS_REQUIRED) + (list(_INSIGHTS_OPTIONAL) if include_views else [])
    try:
        resp = requests.get(
            f"https://{host}/{INSIGHTS_API_VERSION}/{media_id}/insights",
            params={"metric": ",".join(metrics), "period": "lifetime", "access_token": token},
            timeout=10,
        )
        _log_usage_header(media_id, resp.headers)
        data = resp.json()
    except Exception as exc:
        logger.warning(f"[Insights] 조회 실패 | {media_id} | {redact_sensitive(str(exc))}")
        return None, "INSIGHTS_REQUEST_FAILED"
    if resp.status_code != 200 or "error" in data:
        code = (data.get("error") or {}).get("code", resp.status_code) if isinstance(data, dict) else resp.status_code
        return None, f"INSIGHTS_HTTP_{code}"

    values = {}
    for item in data.get("data") or []:
        series = item.get("values") or []
        value = series[0].get("value") if series else None
        if isinstance(value, int) and not isinstance(value, bool):
            values[item.get("name")] = value
    if not values:
        return None, "INSIGHTS_EMPTY"
    if any(name not in values for name in _INSIGHTS_REQUIRED):
        return None, "INSIGHTS_METRIC_MISSING"

    fields = {field: values[name] for name, field in _INSIGHTS_REQUIRED.items()}
    if include_views and "views" in values:
        fields[_INSIGHTS_OPTIONAL["views"]] = values["views"]
    return fields, ""


def _update_insights(table, records: list, now: datetime) -> dict:
    from modules.infra.airtable_repository import AirtableRepository

    include_views = os.getenv("INSIGHTS_INCLUDE_VIEWS", "false").strip().lower() == "true"
    repo = AirtableRepository()
    accounts: dict[str, tuple[dict | None, str]] = {}
    updated = throttled = failed = 0
    for rec in records:
        fields = rec["fields"]
        media_id = fields.get("ig_media_id", "")
        last = _parse_airtable_time(fields.get("insights_collected_at", ""))
        if last is not None and now - last < INSIGHTS_MIN_INTERVAL:
            throttled += 1
            continue

        code = fields.get("account_code_ref", "").strip()
        if code not in accounts:
            accounts[code] = _resolve_insights_account(code, repo)
        cred, error = accounts[code]
        if cred is None:
            logger.warning(f"[Insights] 건너뜀 | {error} | account={code} | {media_id}")
            failed += 1
            continue

        result, error = _fetch_insights(media_id, cred["host"], cred["token"], include_views)
        if result is None:
            logger.warning(f"[Insights] 저장 안 함(기존 값 유지) | {error} | account={code} | {media_id}")
            failed += 1
            continue

        result["insights_collected_at"] = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        try:
            table.update(rec["id"], result)
            updated += 1
        except Exception as exc:
            logger.warning(f"[Insights] Airtable 업데이트 실패 | account={code} | {media_id} | {exc}")
            failed += 1

    return {"insights_updated": updated, "insights_throttled": throttled, "insights_failed": failed}


def update_engagement_metrics() -> dict:
    """
    Instagram_Posts(post_status='posted', ig_media_id 있음) 레코드의
    like_count / comments_count를 Graph API로 갱신.

    INSIGHTS_ACCOUNT_CODES가 비어 있으면 아래 레거시 동작 그대로다. 값이 있으면
    해당 계정의 최근 7일 레코드는 Insights 경로만 타고 레거시 조회에서 빠진다.
    """
    insights_codes = _insights_account_codes()
    if not insights_codes:
        return _update_legacy_engagement()

    table   = get_table("Instagram_Posts")
    records = table.all(formula="AND({post_status}='posted', {ig_media_id}!='')")
    now = datetime.now(timezone.utc)
    targets = [r for r in records if _is_insights_target(r, insights_codes, now)]
    target_ids = {r["id"] for r in targets}

    result = _update_insights(table, targets, now)
    result.update(_update_legacy_engagement(
        table=table, records=[r for r in records if r["id"] not in target_ids],
    ))
    logger.info(f"[Insights] 완료 | {result}")
    return result


def _update_legacy_engagement(table=None, records=None) -> dict:
    token = os.getenv("INSTA_ACCESS_TOKEN") or os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    if not token:
        logger.warning("[Engagement] INSTA_ACCESS_TOKEN 미설정 — 생략")
        return {"updated": 0, "skipped": 0, "failed": 0}

    if table is None:
        table   = get_table("Instagram_Posts")
        records = table.all(formula="AND({post_status}='posted', {ig_media_id}!='')")

    updated = skipped = failed = 0
    for rec in records:
        media_id = rec["fields"].get("ig_media_id", "")
        if not media_id:
            skipped += 1
            continue

        metrics = _fetch_metrics(media_id, token)
        if not metrics:
            failed += 1
            continue

        try:
            table.update(rec["id"], metrics)
            updated += 1
            logger.debug(
                f"[Engagement] 갱신 | {media_id} | "
                f"likes={metrics['like_count']} comments={metrics['comments_count']}"
            )
        except Exception as exc:
            logger.warning(f"[Engagement] Airtable 업데이트 실패 | {media_id} | {exc}")
            failed += 1

    logger.info(f"[Engagement] 완료 | updated={updated} skipped={skipped} failed={failed}")
    return {"updated": updated, "skipped": skipped, "failed": failed}
