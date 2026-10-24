"""tools/run_aijomoojin_publish_manual.py — aijomoojin 게시 잡 수동 실행
Entry Point.

`run_aijomoojin_producer_manual.py`와 동일한 이유·동일한 패턴(REUSE) —
`launcher/main.py._job_aijomoojin_scheduled_post()`를 그대로 호출하기만
한다. 새 로직을 만들지 않는다. Scheduler와 완전히 동일한 코드 경로(동일
Lock, 동일 ready/uploading 판단, 동일 Phase A/A.5/B, 동일 실패 처리)를
타므로 "공용 Lock 공유"가 코드 구조상 자동으로 보장된다."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(dotenv_path=str(_ROOT / ".env"), override=True)

import argparse

from launcher.main import AIJOMOOJIN_SLOT_ACCOUNT_CODE, CONTENT_ACCOUNTS, _job_aijomoojin_scheduled_post

if __name__ == "__main__":
    # 261024 STEP 2 — 공통 엔진 계정 선택(기본 IDN-000036). 목록에 없는 계정은 실행하지 않는다.
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-code", default=AIJOMOOJIN_SLOT_ACCOUNT_CODE)
    args = parser.parse_args()
    if args.account_code not in CONTENT_ACCOUNTS:
        sys.exit(f"알 수 없는 account_code: {args.account_code} (허용: {', '.join(CONTENT_ACCOUNTS)})")
    print(f"account_code={args.account_code}")
    _job_aijomoojin_scheduled_post(account_code=args.account_code)
