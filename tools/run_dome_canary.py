"""Safety Package S4 — 승인된 Dome Source Record 단일 Canary Runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from modules.common.canary_execution_guard import (
    CanaryExecutionGuard,
    CanaryWriteBudget,
)
from modules.crawlers.source_exporter import export_exact_source_item_canary


def execute_dome_canary(
    *,
    canary_run_id: str,
    source_record_id: str,
    approved_image_url: str,
    approved_caption: str,
) -> dict:
    guard = CanaryExecutionGuard(
        canary_run_id,
        source_record_id,
        CanaryWriteBudget.for_dome(source_record_id),
    )
    guard.begin()
    try:
        result = export_exact_source_item_canary(
            source_record_id=source_record_id,
            approved_image_url=approved_image_url,
            approved_caption=approved_caption,
            canary_run_id=canary_run_id,
            write_guard=guard,
            target_publish_account_code_ref="IDN-000041",
        )
    except Exception as exc:
        try:
            guard.fail(type(exc).__name__.upper())
        except Exception:
            pass
        raise
    guard.complete()
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="승인된 Dome Source Record 1건을 draft로만 저장"
    )
    parser.add_argument("--canary-run-id", required=True)
    parser.add_argument("--source-record-id", required=True)
    parser.add_argument("--approved-image-url", required=True)
    parser.add_argument("--approved-caption", required=True)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    result = execute_dome_canary(
        canary_run_id=args.canary_run_id,
        source_record_id=args.source_record_id,
        approved_image_url=args.approved_image_url,
        approved_caption=args.approved_caption,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
