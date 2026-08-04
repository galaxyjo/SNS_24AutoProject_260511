"""tools/run_aijomoojin_producer_manual.py — 260804 Track B 6G Producer 수동 실행
Entry Point.

Git-tracked(파일명에 `_` 접두사 없음 — `tools/_*.py`는 .gitignore 대상이라
gitignore되던 이전 방식(`tools/_canary_260801_queue_aijomoojin_post_6f.py`)은
회장 승인 조건 8("수동 실행과 Scheduler 실행이 동일 Lock을 공유해야 한다")을
일반 Commit·clone·복구 환경에서 보장하지 못했다 — 260804 Codex 2차 리뷰 지적,
해당 스크립트는 원상복구했다.

이 파일은 `launcher/main.py._job_aijomoojin_content_producer()`를 그대로
호출하기만 한다 — 새 로직을 만들지 않는다. Scheduler와 완전히 동일한 코드
경로(동일 Lock, 동일 ready/uploading 가드, 동일 stale/재개 판단, 동일 실패
처리)를 타므로 "공용 Lock 공유"가 코드 구조상 자동으로 보장된다."""

import sys
from pathlib import Path

# 260804 Codex 3차 리뷰(P2) 수정 — 절대경로 하드코딩 대신 __file__ 기준으로
# 프로젝트 루트를 계산한다(launcher/main.py의 기존 방식과 동일 패턴, 다른
# clone 경로에서도 동작).
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(dotenv_path=str(_ROOT / ".env"), override=True)

from launcher.main import _job_aijomoojin_content_producer

if __name__ == "__main__":
    _job_aijomoojin_content_producer()
