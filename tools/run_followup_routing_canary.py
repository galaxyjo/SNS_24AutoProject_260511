"""tools/run_followup_routing_canary.py — 260730 10.5 Close Gate 보완.

팔로업 채널(_send_ig_dm)이 aijomoojin(instagram_login) 계정으로 실제
발송할 때 정확히 그 계정 자신의 credential 경로를 쓰는지(다른 계정으로
새지 않는지) 통제된 방식으로 증명한다. 실제 Lead_Interactions CRM
상태(bridge_status)는 건드리지 않고, 문자열도 [CANARY TEST]로 명시
라벨링해 손님 혼동을 최소화한다.

실행: .venv/Scripts/python.exe tools/run_followup_routing_canary.py

260730 발견(중요): 이 스크립트가 프로젝트 루트를 sys.path에 명시적으로 추가하지
않으면, 시스템 PYTHONPATH 환경변수가 C:/SNS_24AutoProject_250723을 가리키고
있어 `modules.dm`이 이 스크립트가 아니라 250723(Reference Only, 구버전)에서
잘못 resolve된다(launcher/main.py는 이미 이 문제를 피하려고 sys.path.insert
를 쓰고 있음 — 동일 패턴 적용).
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from modules.dm import dm_followup_scheduler

IGSID = "1374716158108036"          # aijomoojin 실제 손님(오늘 "가격 얼마예요?" 발신자)
ACCOUNT_CODE_REF = "IDN-000036"     # aijomoojin
TEXT = "[CANARY TEST] 10.5 Close Gate 팔로업 라우팅 검증용 메시지입니다."

if __name__ == "__main__":
    sent = dm_followup_scheduler._send_ig_dm(IGSID, TEXT, ACCOUNT_CODE_REF)
    print(f"sent={sent}")
