# ================================================================
# File: modules/sns/bot_crawler.py
# Purpose: 통합 Facebook 크롤러 실행 제어 모듈
# Author: SNS_24AutoProject_250723
# Rule: BOM 제거 / LF 통일 / 경로 상대 / fallback 환경설정 구조
# ================================================================

import os
import sys
import time
from pathlib import Path

# ------------------------------------------------
# 1️⃣ Fallback 환경설정 체인 (.env → cfg_loader.py → defaults)
# ------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from modules.cfg_loader import load_cfg_value  # pylint: disable=E0401
from modules.sns.facebook_crawler import run_facebook_crawler  # pylint: disable=E0401

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except Exception:
    pass

# 기본 설정
DEFAULTS = {
    "FACEBOOK_ENABLED": "True",
    "LOG_PATH": str(BASE_DIR / "logs" / "sns"),
    "DB_PATH": str(BASE_DIR / "db" / "sns_crawl.db"),
}


def get_env(key: str) -> str:
    """환경값 fallback 체계"""
    value = os.getenv(key)
    if value:
        return value
    value = load_cfg_value(key)
    if value:
        return value
    return DEFAULTS.get(key, "")


# ------------------------------------------------
# 2️⃣ 메인 실행 로직
# ------------------------------------------------
def run_bot_crawler():
    """페이스북 크롤러를 통합 실행"""
    enabled = get_env("FACEBOOK_ENABLED").lower() in ("true", "1", "yes")
    log_path = Path(get_env("LOG_PATH"))
    log_path.mkdir(parents=True, exist_ok=True)

    print("🚀 SNS Bot Crawler 시작")
    print(f"📂 로그 경로: {log_path}")
    if not enabled:
        print("⚠️ FACEBOOK_ENABLED=False → 크롤러 비활성화됨")
        return {"status": "skipped"}

    try:
        result = run_facebook_crawler()
        log_file = log_path / f"facebook_crawl_{int(time.time())}.log"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(str(result))
        print(f"✅ 로그 저장 완료: {log_file.name}")
        return {"status": "success", "log": str(log_file)}
    except Exception as e:
        err_file = log_path / f"facebook_crawl_error_{int(time.time())}.log"
        with open(err_file, "w", encoding="utf-8") as f:
            f.write(str(e))
        print(f"❌ 오류 발생: {e}")
        return {"status": "error", "message": str(e)}


# ------------------------------------------------
# 3️⃣ 독립 실행
# ------------------------------------------------
if __name__ == "__main__":
    run_bot_crawler()
