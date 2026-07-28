"""Safety Package S3 — 승인된 Facebook permalink 단일 Canary Runner."""

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
from modules.sns.facebook_crawler import run_exact_permalink_canary


def execute_facebook_canary(
    *,
    canary_run_id: str,
    permalink: str,
    expected_post_id: str,
    approved_image_url: str,
    approved_caption: str,
    source_account_name: str,
) -> dict:
    guard = CanaryExecutionGuard(
        canary_run_id,
        permalink,
        CanaryWriteBudget.for_facebook(),
    )
    guard.begin()
    try:
        result = run_exact_permalink_canary(
            permalink=permalink,
            expected_post_id=expected_post_id,
            approved_image_url=approved_image_url,
            approved_caption=approved_caption,
            source_account_name=source_account_name,
            canary_run_id=canary_run_id,
            write_guard=guard,
            target_publish_account_code_ref="IDN-000041",
        )
    except Exception as exc:
        try:
            guard.fail(type(exc).__name__.upper())
        except Exception:
            # Run ID는 이미 begin()에서 영구 소진됐다. 종료기록 실패가 원래
            # Root Cause를 덮어쓰지 않도록 보존한다.
            pass
        raise
    guard.complete()
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="승인된 Facebook permalink 1개를 draft로만 저장"
    )
    parser.add_argument("--canary-run-id", required=True)
    parser.add_argument("--permalink", required=True)
    parser.add_argument("--expected-post-id", required=True)
    parser.add_argument("--approved-image-url", required=True)
    parser.add_argument("--approved-caption", required=True)
    parser.add_argument("--source-account-name", required=True)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    result = execute_facebook_canary(
        canary_run_id=args.canary_run_id,
        permalink=args.permalink,
        expected_post_id=args.expected_post_id,
        approved_image_url=args.approved_image_url,
        approved_caption=args.approved_caption,
        source_account_name=args.source_account_name,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
