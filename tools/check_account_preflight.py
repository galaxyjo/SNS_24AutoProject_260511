"""tools/check_account_preflight.py — 신규 계정 온보딩 Preflight 점검 (Read-only)

CONTENT_ACCOUNTS의 계정을 READY / NOT_READY(사유코드)로 출력한다. Secret 값은 출력하지 않는다.
게시·Airtable 쓰기·재시작 없음.

사용: python tools/check_account_preflight.py [--account-code IDN-000024] [--stage all|publish|produce]
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(dotenv_path=str(_ROOT / ".env"), override=True)

import argparse

from launcher.main import CONTENT_ACCOUNTS, _content_persona_kwargs
from modules.common.account_preflight import run_account_preflight
from modules.infra.airtable_repository import AirtableRepository

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-code", default="")
    parser.add_argument("--stage", default="all", choices=["all", "publish", "produce"])
    args = parser.parse_args()
    codes = [args.account_code] if args.account_code else sorted(CONTENT_ACCOUNTS)
    repo = AirtableRepository()
    for code in codes:
        result = run_account_preflight(
            code, content_accounts=CONTENT_ACCOUNTS, repo=repo, stage=args.stage,
            persona_loader=_content_persona_kwargs,
        )
        reasons = ",".join(result["not_ready"]) or "-"
        print(f"{code} | {result['status']} | {reasons}")
