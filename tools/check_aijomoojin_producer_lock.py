"""tools/check_aijomoojin_producer_lock.py — 260804 Track B 6G Producer Lock
Read-only 상태확인 CLI.

`modules/common/producer_lock`은 의도적으로 PID/host/Heartbeat를 저장하지
않는다(회장 승인 조건 9 — Lease·Heartbeat·신규 Queue 금지, 최소 구현). 그래서
Lock이 오래 걸려 있을 때 "정상적으로 실행 중"인지 "Crash로 고착"됐는지
코드만으로는 구분할 수 없다 — 사람이 아래 순서로 직접 판단해야 한다.

Runbook(수동 해제 전 필수 절차):
  1. 이 스크립트를 실행해 현재 holder(owner_token)와 acquired_at을 확인한다.
  2. Windows에서 launcher(watchdog가 띄운 python 프로세스) 또는
     `tools/run_aijomoojin_producer_manual.py`를 실행한 콘솔이 실제로
     남아있는지 확인한다(Task Manager 또는 `Get-Process python`).
  3. 둘 다 이미 종료됐음을 확인한 뒤에만 아래를 실행해 강제 해제한다:
         python -c "from modules.common import producer_lock; producer_lock.force_release()"
  4. 아직 실행 중이라면(정상적으로 Gemini/Cloudflare 호출이 오래 걸리는
     경우 포함) 강제 해제하지 않는다 — 겹쳐 실행되면 중복 콘텐츠·중복
     게시 위험이 생긴다.

이 스크립트 자체는 조회만 한다 — force_release()를 자동으로 호출하지 않는다."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(dotenv_path=str(_ROOT / ".env"), override=True)

from modules.common import producer_lock

if __name__ == "__main__":
    holder = producer_lock.get_holder()
    if holder is None:
        print("LOCK_STATE: free (보유자 없음)")
    else:
        print("LOCK_STATE: held")
        print(f"  owner_token = {holder['owner_token']}")
        print(f"  acquired_at = {holder['acquired_at']} (UTC)")
        print(
            "\n강제 해제 전, launcher/수동 실행 프로세스가 실제로 종료됐는지 "
            "먼저 확인하세요(이 스크립트 상단 Runbook 참조)."
        )
