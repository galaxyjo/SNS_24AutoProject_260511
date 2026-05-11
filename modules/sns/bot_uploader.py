# ================================================================
# File: modules/sns/bot_uploader.py
# ================================================================

import os
from pathlib import Path
from typing import Dict
from modules.sns import insta_uploader


def get_env_config() -> Dict[str, str]:
    base_dir = Path(__file__).resolve().parents[2]
    env_file = base_dir / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
    return {
        "UPLOAD_ENABLED": os.getenv("UPLOAD_ENABLED", "True"),
        "LOG_PATH": os.getenv("LOG_PATH", str(base_dir / "logs" / "sns")),
    }


def run_bot_uploader() -> Dict[str, str]:
    cfg = get_env_config()
    log_path = Path(cfg["LOG_PATH"])
    log_path.mkdir(parents=True, exist_ok=True)
    if cfg["UPLOAD_ENABLED"].lower() not in ("true", "1", "yes"):
        print("⚠️ 업로드 기능 비활성화됨")
        return {"status": "skipped"}

    try:
        result = insta_uploader.run_insta_uploader()
        log_file = log_path / "bot_uploader_result.log"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(str(result))
        print("✅ 업로드 자동화 성공")
        return {"status": "success", "result": result}
    except Exception as e:
        print(f"⚠️ 실패: {e}")
        err_file = log_path / "bot_uploader_error.log"
        with open(err_file, "w", encoding="utf-8") as f:
            f.write(str(e))
        return {"status": "error", "message": str(e)}


def main() -> None:
    result = run_bot_uploader()
    if result.get("status") == "success":
        print("✅ Bot 업로드 완료")
    elif result.get("status") == "skipped":
        print("⚠️ Bot 업로드 비활성화")
    else:
        print("⚠️ Bot 업로드 오류")


if __name__ == "__main__":
    main()
