# ================================================================
# File: modules/sns/insta_uploader.py
# ================================================================

import os
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
import pandas as pd


def load_env() -> None:
    base_dir = Path(__file__).resolve().parents[2]
    env_path = base_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def get_upload_config() -> Dict[str, str]:
    load_env()
    env_upload_path = os.getenv("UPLOAD_PATH", "")
    default_path = Path(__file__).resolve().parents[2] / "data" / "fb_posts.json"

    # ✅ 수정된 부분: 존재하지 않으면 fallback 하지 않고 그대로 유지
    if env_upload_path:
        if Path(env_upload_path).exists():
            upload_path = env_upload_path
        else:
            upload_path = env_upload_path  # 존재하지 않으면 그대로 유지 → run_insta_uploader에서 오류 처리
    else:
        upload_path = str(default_path if default_path.exists() else "")

    config = {
        "INSTA_ID": os.getenv("INSTA_ID", ""),
        "INSTA_PW": os.getenv("INSTA_PW", ""),
        "UPLOAD_PATH": upload_path,
        "LOG_PATH": os.getenv("LOG_PATH", str(Path(__file__).resolve().parents[2] / "logs" / "sns")),
    }
    return config


def simulate_upload(posts: List[str]) -> List[str]:
    results = []
    for post in posts:
        if post:
            results.append(f"업로드 성공: {post[:20]}...")
        else:
            results.append("업로드 실패: 내용 없음")
    return results


def run_insta_uploader() -> Dict[str, str]:
    try:
        cfg = get_upload_config()
        Path(cfg["LOG_PATH"]).mkdir(parents=True, exist_ok=True)
        data_path = Path(cfg["UPLOAD_PATH"])
        if not data_path.exists():
            print("⚠️ 실패: 업로드 대상 파일이 존재하지 않습니다.")
            return {"status": "error", "message": "no upload data"}

        try:
            df = pd.read_json(data_path)
        except ValueError:
            print("⚠️ 실패: JSON 파일 형식 오류")
            return {"status": "error", "message": "invalid json"}

        posts = df.get("content", []).tolist() if "content" in df.columns else []
        results = simulate_upload(posts)
        log_file = Path(cfg["LOG_PATH"]) / "insta_upload_result.log"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("\n".join(results))
        print("✅ 성공: 업로드 시뮬레이션 완료")
        return {"status": "success", "count": len(results)}
    except Exception as e:
        print(f"⚠️ 실패: {e}")
        return {"status": "error", "message": str(e)}


def main() -> None:
    result = run_insta_uploader()
    if result.get("status") == "success":
        print("✅ 업로드 프로세스 완료")
    else:
        print("⚠️ 업로드 실패")


if __name__ == "__main__":
    main()
