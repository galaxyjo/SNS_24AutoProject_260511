# -*- coding: utf-8 -*-
"""
pipeline_feed_ingest.py

ROLE
- Read target_url records from adapter_airtable.py
- Pass each URL to facebook_crawler.py
- Save crawl results via airtable_bridge.py
- Force processing_status = "gpt_ready"
- Keep existing module roles unchanged

MASTER TREE POSITION
- C:\\SNS_24AutoProject_250723\\modules\\sns\\pipeline_feed_ingest.py

Windows PowerShell
    python .\modules\sns\pipeline_feed_ingest.py
    python .\modules\sns\pipeline_feed_ingest.py --limit 5
    python .\modules\sns\pipeline_feed_ingest.py --dry-run
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple


# =========================================================
# PROJECT ROOT PATH FIX
# =========================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# =========================================================
# LOGGING
# =========================================================
LOG_LEVEL = os.getenv("FEED_INGEST_LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("pipeline_feed_ingest")


# =========================================================
# IMPORT HELPERS
# =========================================================
def import_first_available(module_names: List[str]):
    """
    Try multiple module paths and return the first successfully imported module.
    """
    last_error = None

    for name in module_names:
        try:
            module = importlib.import_module(name)
            logger.info("Imported module: %s", name)
            return module
        except Exception as exc:
            last_error = exc
            logger.debug("Import failed: %s | %s", name, exc)

    raise ImportError(
        f"Unable to import any module from candidates: {module_names}. "
        f"Last error: {last_error}"
    )


def resolve_callable(module: Any, candidate_names: List[str]) -> Optional[Callable]:
    """
    Return the first callable found in module by candidate name list.
    """
    for name in candidate_names:
        fn = getattr(module, name, None)
        if callable(fn):
            logger.info("Resolved callable: %s.%s", module.__name__, name)
            return fn
    return None


def call_flex(fn: Callable, *args, **kwargs) -> Any:
    """
    Best-effort function call.
    Order:
    1) exact args + kwargs
    2) filtered kwargs only
    3) positional args only
    4) first positional arg if single-parameter function
    """
    sig = inspect.signature(fn)
    params = sig.parameters

    accepts_var_kw = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
    )

    if accepts_var_kw:
        try:
            return fn(*args, **kwargs)
        except TypeError:
            pass

    try:
        return fn(*args, **kwargs)
    except TypeError:
        pass

    filtered_kwargs = {k: v for k, v in kwargs.items() if k in params}
    if filtered_kwargs:
        try:
            return fn(**filtered_kwargs)
        except TypeError:
            pass

    try:
        return fn(*args)
    except TypeError:
        pass

    if len(params) == 1 and args:
        try:
            return fn(args[0])
        except TypeError:
            pass

    raise TypeError(
        f"Unable to call function {fn.__module__}.{fn.__name__} "
        f"with args={args}, kwargs={kwargs}"
    )


# =========================================================
# MODULE LOADING
# =========================================================
def load_modules() -> Tuple[Any, Any, Any]:
    """
    Load adapter_airtable, facebook_crawler, airtable_bridge
    using MasterTree-aware candidates.
    """
    adapter_module = import_first_available(
        [
            "modules.adapter.adapter_airtable",
            "modules.adapter_airtable",          # 추가
            "modules.common.adapter_airtable",
            "adapter_airtable",
            "modules.adapter_airtable",
            "modules.adapters.adapter_airtable",
            "modules.sns.adapter_airtable",
        ]
    )

    crawler_module = import_first_available(
        [
            "modules.sns.facebook_crawler",
            "facebook_crawler",
            "modules.facebook_crawler",
            "modules.common.facebook_crawler",
        ]
    )

    bridge_module = import_first_available(
        [
            "modules.common.airtable_bridge",
            "airtable_bridge",
            "modules.airtable_bridge",
            "modules.adapters.airtable_bridge",
            "modules.sns.airtable_bridge",
        ]
    )

    return adapter_module, crawler_module, bridge_module


# =========================================================
# NORMALIZATION HELPERS
# =========================================================
def safe_iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_target_url(item: Any) -> Optional[str]:
    """
    Normalize one item into target_url if possible.
    """
    if isinstance(item, str):
        item = item.strip()
        return item or None

    if isinstance(item, dict):
        return (
            item.get("target_url")
            or item.get("url")
            or item.get("Target_URL")
            or item.get("URL")
            or item.get("source_url")
            or item.get("facebook_url")
        )

    return None


def normalize_target_records(raw: Any) -> List[Dict[str, Any]]:
    """
    Normalize adapter output to:
    [
        {"target_url": "...", ...},
        ...
    ]
    """
    records: List[Dict[str, Any]] = []

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                url = extract_target_url(item)
                if url:
                    records.append({"target_url": url})
            elif isinstance(item, dict):
                url = extract_target_url(item)
                if url:
                    normalized = dict(item)
                    normalized["target_url"] = url
                    records.append(normalized)

    elif isinstance(raw, dict):
        possible_lists = [
            raw.get("records"),
            raw.get("items"),
            raw.get("data"),
            raw.get("urls"),
            raw.get("target_urls"),
            raw.get("results"),
        ]

        for bucket in possible_lists:
            if isinstance(bucket, list):
                for item in bucket:
                    if isinstance(item, str):
                        url = extract_target_url(item)
                        if url:
                            records.append({"target_url": url})
                    elif isinstance(item, dict):
                        url = extract_target_url(item)
                        if url:
                            normalized = dict(item)
                            normalized["target_url"] = url
                            records.append(normalized)
                break

        if not records:
            url = extract_target_url(raw)
            if url:
                normalized = dict(raw)
                normalized["target_url"] = url
                records.append(normalized)

    deduped: List[Dict[str, Any]] = []
    seen = set()

    for rec in records:
        url = rec.get("target_url")
        if url and url not in seen:
            seen.add(url)
            deduped.append(rec)

    return deduped


# =========================================================
# ADAPTER: READ TARGET URLS
# =========================================================
def get_target_records(adapter_module: Any, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Read target_url records from adapter_airtable.py
    """
    candidate_fns = [
        "get_target_urls",
        "fetch_target_urls",
        "read_target_urls",
        "get_source_feed_targets",
        "fetch_source_feed_targets",
        "read_source_feed_targets",
        "get_pending_target_urls",
        "get_records",
        "fetch_records",
        "read_records",
    ]
    fn = resolve_callable(adapter_module, candidate_fns)

    if fn is None:
        raise AttributeError(
            f"No compatible read function found in {adapter_module.__name__}. "
            f"Tried: {candidate_fns}"
        )

    candidate_calls = [
        {"limit": limit},
        {"max_records": limit},
        {"page_size": limit},
        {},
    ]

    raw = None
    last_error = None

    for kwargs in candidate_calls:
        try:
            clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}
            raw = call_flex(fn, **clean_kwargs)
            logger.info("Adapter fetch succeeded with kwargs=%s", clean_kwargs)
            break
        except Exception as exc:
            last_error = exc
            logger.debug("Adapter fetch failed with kwargs=%s | %s", kwargs, exc)

    if raw is None:
        raise RuntimeError(
            f"Failed to fetch target records from {adapter_module.__name__}: {last_error}"
        )

    records = normalize_target_records(raw)

    if not records:
        logger.warning("No target_url records found.")
        return []

    logger.info("Fetched %s unique target record(s).", len(records))
    return records


# =========================================================
# CRAWLER: EXECUTE
# =========================================================
def run_crawler(crawler_module: Any, target_url: str) -> Any:
    """
    Execute facebook_crawler.py with one target URL.
    """
    candidate_fns = [
        "run",  # ✅ 추가
        "crawl",
        "crawl_url",
        "crawl_target_url",
        "crawl_facebook",
        "crawl_facebook_url",
        "run_crawler",
        "fetch_posts",
        "fetch_feed",
        "get_posts",
        "get_feed",
        "main",
    ]
    fn = resolve_callable(crawler_module, candidate_fns)

    if fn is None:
        raise AttributeError(
            f"No compatible crawler function found in {crawler_module.__name__}. "
            f"Tried: {candidate_fns}"
        )

    candidate_calls = [
        {"target_url": target_url},
        {"url": target_url},
        {"facebook_url": target_url},
        {"source_url": target_url},
        {"post_url": target_url},
        {},
    ]

    last_error = None

    for kwargs in candidate_calls:
        try:
            if kwargs:
                result = call_flex(fn, **kwargs)
            else:
                result = call_flex(fn, target_url)

            logger.info("Crawler executed successfully for: %s", target_url)
            return result

        except Exception as exc:
            last_error = exc
            logger.debug("Crawler call failed with kwargs=%s | %s", kwargs, exc)

    raise RuntimeError(
        f"Failed to crawl target_url={target_url}. Last error: {last_error}"
    )


# =========================================================
# CRAWLER OUTPUT -> WRITE PAYLOADS
# =========================================================
def normalize_crawl_output(
    crawl_result: Any,
    target_record: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Convert crawler output to Airtable-ready payloads.
    Guarantees processing_status='gpt_ready'
    """
    target_url = target_record.get("target_url", "")
    now_utc = safe_iso_utc_now()
    items: List[Dict[str, Any]] = []

    if isinstance(crawl_result, list):
        items = [x for x in crawl_result if isinstance(x, dict)]

    elif isinstance(crawl_result, dict):
        for key in ("posts", "items", "data", "results", "records"):
            bucket = crawl_result.get(key)
            if isinstance(bucket, list):
                items = [x for x in bucket if isinstance(x, dict)]
                break

        if not items:
            items = [crawl_result]

    payloads: List[Dict[str, Any]] = []

    for idx, item in enumerate(items, start=1):
        payload = dict(item)

        payload.setdefault("target_url", target_url)
        payload.setdefault("source_url", target_url)
        payload.setdefault("processing_status", "gpt_ready")
        payload.setdefault("ingested_at", now_utc)

        if "title" not in payload and "post_title" in payload:
            payload["title"] = payload["post_title"]

        if "content" not in payload:
            payload["content"] = (
                payload.get("text")
                or payload.get("message")
                or payload.get("body")
                or payload.get("caption")
                or ""
            )

        if "external_id" not in payload:
            payload["external_id"] = (
                payload.get("post_id")
                or payload.get("id")
                or payload.get("fb_post_id")
                or f"{target_url}__{idx}"
            )

        payloads.append(payload)

    if not payloads:
        payloads.append(
            {
                "target_url": target_url,
                "source_url": target_url,
                "content": "",
                "processing_status": "gpt_ready",
                "ingested_at": now_utc,
                "external_id": f"{target_url}__empty",
                "note": "Crawler returned no structured items.",
            }
        )

    return payloads


# =========================================================
# BRIDGE: WRITE TO AIRTABLE
# =========================================================
def save_payload(bridge_module: Any, payload: Dict[str, Any], dry_run: bool = False) -> Any:
    """
    Save one payload using airtable_bridge.py
    """
    if "processing_status" not in payload or not payload["processing_status"]:
        payload["processing_status"] = "gpt_ready"

    candidate_fns = [
        "create_source_feed_record"
        "write_source_feed",
        "create_source_feed",
        "insert_source_feed",
        "save_source_feed",
        "push_source_feed",
        "upsert_source_feed",
        "create_record",
        "insert_record",
        "write_record",
        "save_record",
        "upsert_record",
    ]
    fn = resolve_callable(bridge_module, candidate_fns)

    if fn is None:
        raise AttributeError(
            f"No compatible write function found in {bridge_module.__name__}. "
            f"Tried: {candidate_fns}"
        )

    if dry_run:
        logger.info(
            "[DRY-RUN] Payload not written:\n%s",
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        return {"dry_run": True, "payload": payload}

    candidate_calls = [
        {"record": payload},
        {"data": payload},
        {"payload": payload},
        {"fields": payload},
        {},
    ]

    last_error = None

    for kwargs in candidate_calls:
        try:
            if kwargs:
                result = call_flex(fn, **kwargs)
            else:
                result = call_flex(fn, payload)

            logger.info(
                "Airtable write succeeded | external_id=%s",
                payload.get("external_id"),
            )
            return result

        except Exception as exc:
            last_error = exc
            logger.debug("Write call failed with kwargs=%s | %s", kwargs, exc)

    raise RuntimeError(
        f"Failed to write payload through {bridge_module.__name__}. Last error: {last_error}"
    )


# =========================================================
# PIPELINE EXECUTION
# =========================================================
def process_one_target(
    crawler_module: Any,
    bridge_module: Any,
    target_record: Dict[str, Any],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Process one target_url:
    read -> crawl -> normalize -> write
    """
    target_url = target_record.get("target_url")

    if not target_url:
        return {
            "target_url": None,
            "status": "skipped",
            "reason": "missing target_url",
            "written_count": 0,
            "error_count": 0,
            "errors": [],
        }

    logger.info("Processing target_url: %s", target_url)

    crawl_result = run_crawler(crawler_module, target_url)
    payloads = normalize_crawl_output(crawl_result, target_record)

    written_count = 0
    errors: List[str] = []

    for payload in payloads:
        try:
            save_payload(bridge_module, payload, dry_run=dry_run)
            written_count += 1
        except Exception as exc:
            err_msg = f"{type(exc).__name__}: {exc}"
            logger.error("Write failed | target_url=%s | %s", target_url, err_msg)
            errors.append(err_msg)

    result_status = "success" if written_count > 0 else "failed"

    return {
        "target_url": target_url,
        "status": result_status,
        "written_count": written_count,
        "error_count": len(errors),
        "errors": errors,
    }


def run_pipeline(limit: Optional[int] = None, dry_run: bool = False) -> Dict[str, Any]:
    adapter_module, crawler_module, bridge_module = load_modules()
    target_records = get_target_records(adapter_module, limit=limit)

    results: List[Dict[str, Any]] = []

    for rec in target_records:
        try:
            result = process_one_target(
                crawler_module=crawler_module,
                bridge_module=bridge_module,
                target_record=rec,
                dry_run=dry_run,
            )
        except Exception as exc:
            target_url = rec.get("target_url")
            logger.error("Pipeline failed for %s\n%s", target_url, traceback.format_exc())
            result = {
                "target_url": target_url,
                "status": "failed",
                "written_count": 0,
                "error_count": 1,
                "errors": [f"{type(exc).__name__}: {exc}"],
            }

        results.append(result)

    total_targets = len(results)
    success_targets = sum(1 for r in results if r["status"] == "success")
    failed_targets = sum(1 for r in results if r["status"] == "failed")
    total_written = sum(int(r.get("written_count", 0)) for r in results)

    summary = {
        "total_targets": total_targets,
        "success_targets": success_targets,
        "failed_targets": failed_targets,
        "total_written_records": total_written,
        "dry_run": dry_run,
        "results": results,
    }

    logger.info("Pipeline summary: %s", json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


# =========================================================
# CLI
# =========================================================
def parse_args():
    parser = argparse.ArgumentParser(
        description="Airtable -> Facebook Crawler -> Airtable ingest pipeline"
    )
    parser.add_argument("--limit", type=int, default=None, help="Process only N target URLs")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to Airtable")
    return parser.parse_args()


def main():
    args = parse_args()
    summary = run_pipeline(limit=args.limit, dry_run=args.dry_run)

    print("=" * 80)
    print("FEED INGEST PIPELINE RESULT")
    print("=" * 80)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("=" * 80)

    if summary["failed_targets"] > 0 and summary["success_targets"] == 0:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()