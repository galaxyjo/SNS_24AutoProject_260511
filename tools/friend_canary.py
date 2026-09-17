"""
tools/friend_canary.py — YUNA 친구추가 Live Canary 1회 (STEP 3-B1R, 260901)

회장이 AdsPower(YUNA 프로필 k1bto3j4) 켠 상태에서 직접 실행하고 브라우저 화면을 본다.
CAPTCHA / 로그인 승인 / 계정 제한 화면이 뜨면 즉시 창을 닫는다(스크립트도 자동 중단 시도).

사용:
    # dry-run(브라우저 안 엶, 게이트만 확인)
    python tools/friend_canary.py https://www.facebook.com/groups/1930721300516777

    # 실제 1회 실행 (그룹 첫 게시물 작성자에게 친구요청)
    python tools/friend_canary.py https://www.facebook.com/groups/1930721300516777 --live

    # 대상 프로필을 직접 지정
    python tools/friend_canary.py <group_url> --live --target https://www.facebook.com/<person>

Airtable 기록 안 함. 로컬 dedup(db/outbound_actions.db)만 — 같은 사람 재요청 방지.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("group_url", help="Prospect_Groups 의 Facebook 그룹 URL")
    ap.add_argument("--live", action="store_true", help="실제 클릭 실행(미지정 시 dry-run)")
    ap.add_argument("--target", default=None, help="대상 프로필 URL 직접 지정(그룹 탐색 생략)")
    args = ap.parse_args()

    if args.live:
        os.environ["OUTBOUND_FRIEND_LIVE_ENABLED"] = "true"

    from modules.interaction_engine.outbound_connector import friend_in_group

    result = friend_in_group(
        args.group_url,
        dry_run=not args.live,
        target_url=args.target,
    )
    print(result)
    # 실패/스킵은 비정상 종료로 알림(회장이 결과를 눈으로 보되 exit code 도 남김)
    sys.exit(0 if result.get("result") == "success" else 1)


if __name__ == "__main__":
    main()
