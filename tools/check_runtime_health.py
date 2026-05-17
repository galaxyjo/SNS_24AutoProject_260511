"""
tools/check_runtime_health.py — 런타임 헬스 체크 도구
실행: python tools/check_runtime_health.py
"""
import os
import sys
import socket
import sqlite3
import subprocess
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)


def _check_port(port: int) -> bool:
    try:
        with socket.create_connection(("localhost", port), timeout=3):
            return True
    except OSError:
        return False


def _get_pid_by_cmdline(keyword: str) -> int | None:
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             f"Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             f"Where-Object {{$_.CommandLine -like '*{keyword}*'}} | "
             f"Select-Object -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=10
        )
        pids = [int(p.strip()) for p in result.stdout.strip().splitlines() if p.strip().isdigit()]
        return pids[0] if pids else None
    except Exception:
        return None


def _get_n8n_pid() -> int | None:
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-CimInstance Win32_Process | "
             "Where-Object {$_.CommandLine -like '*n8n*'} | "
             "Select-Object -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=10
        )
        pids = [int(p.strip()) for p in result.stdout.strip().splitlines() if p.strip().isdigit()]
        return pids[0] if pids else None
    except Exception:
        return None


def _check_airtable() -> tuple[bool, str]:
    try:
        import requests
        api_key = os.getenv("AIRTABLE_API_KEY", "")
        base_id = os.getenv("AIRTABLE_BASE_ID", "")
        if not api_key or not base_id:
            return False, "AIRTABLE_API_KEY / AIRTABLE_BASE_ID 미설정"
        url = f"https://api.airtable.com/v0/{base_id}/Instagram_Posts?maxRecords=1"
        resp = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=8)
        return resp.status_code == 200, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


def _get_latest_crawl() -> str:
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "crawl_stats.db")
    if not os.path.exists(db_path):
        return "crawl_stats.db 없음"
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT crawled_at FROM crawl_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return row[0] if row else "기록 없음"
    except Exception as e:
        return f"조회 실패: {e}"


def _get_airtable_status_counts() -> dict:
    try:
        import requests
        api_key = os.getenv("AIRTABLE_API_KEY", "")
        base_id = os.getenv("AIRTABLE_BASE_ID", "")
        if not api_key or not base_id:
            return {}
        counts: dict = {}
        offset = None
        while True:
            params: dict = {"fields[]": "post_status", "pageSize": 100}
            if offset:
                params["offset"] = offset
            resp = requests.get(
                f"https://api.airtable.com/v0/{base_id}/Instagram_Posts",
                headers={"Authorization": f"Bearer {api_key}"},
                params=params, timeout=10
            )
            data = resp.json()
            for rec in data.get("records", []):
                st = rec.get("fields", {}).get("post_status", "unknown")
                counts[st] = counts.get(st, 0) + 1
            offset = data.get("offset")
            if not offset:
                break
        return counts
    except Exception as e:
        return {"error": str(e)}


def run_health_check():
    print(f"\n{'='*60}")
    print(f"  SNS_24AutoProject — Runtime Health Check")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # 1. Launcher PID
    launcher_pid = _get_pid_by_cmdline("launcher")
    status = f"PID {launcher_pid}" if launcher_pid else "NOT RUNNING"
    icon = "✅" if launcher_pid else "❌"
    print(f"{icon} launcher/main.py  : {status}")

    # 2. n8n PID
    n8n_pid = _get_n8n_pid()
    status = f"PID {n8n_pid}" if n8n_pid else "NOT RUNNING"
    icon = "✅" if n8n_pid else "❌"
    print(f"{icon} n8n process        : {status}")

    # 3. Port 5000 (Flask)
    port5000 = _check_port(5000)
    icon = "✅" if port5000 else "❌"
    print(f"{icon} Port 5000 (Flask)  : {'OPEN' if port5000 else 'CLOSED'}")

    # 4. Port 5678 (n8n)
    port5678 = _check_port(5678)
    icon = "✅" if port5678 else "❌"
    print(f"{icon} Port 5678 (n8n)    : {'OPEN' if port5678 else 'CLOSED'}")

    # 5. Airtable API
    print()
    at_ok, at_msg = _check_airtable()
    icon = "✅" if at_ok else "❌"
    print(f"{icon} Airtable API       : {'OK' if at_ok else 'FAIL'} ({at_msg})")

    # 6. 최근 크롤 시간
    latest_crawl = _get_latest_crawl()
    print(f"📅 Last crawl time   : {latest_crawl}")

    # 7 & 8. Airtable 레코드 상태 분포
    print()
    print("📊 Instagram_Posts 상태 분포:")
    counts = _get_airtable_status_counts()
    if "error" in counts:
        print(f"   ⚠️  조회 실패: {counts['error']}")
    else:
        ready  = counts.get("ready", 0)
        failed = counts.get("failed", 0)
        posted = counts.get("posted", 0)
        uploading = counts.get("uploading", 0)
        for st, cnt in sorted(counts.items()):
            icon = "🔴" if st == "failed" else "🟢" if st == "posted" else "🟡"
            print(f"   {icon} {st:<12}: {cnt}")
        print(f"\n   ready={ready}  failed={failed}  posted={posted}  uploading={uploading}")
        if failed > 0:
            print(f"   ⚠️  failed 레코드 {failed}건 — 확인 필요")

    print(f"\n{'='*60}\n")

    # 요약 판정
    all_ok = all([launcher_pid, port5000, at_ok])
    if all_ok:
        print("전체 상태: 정상 운영 중\n")
    else:
        issues = []
        if not launcher_pid:
            issues.append("launcher 미실행")
        if not port5000:
            issues.append("포트 5000 닫힘")
        if not at_ok:
            issues.append("Airtable API 응답 없음")
        print(f"전체 상태: 점검 필요 — {', '.join(issues)}\n")


if __name__ == "__main__":
    run_health_check()
