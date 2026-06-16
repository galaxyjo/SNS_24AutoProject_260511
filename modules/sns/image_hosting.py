import os
import hashlib
import requests
from typing import Optional

IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"
DOWNLOAD_TIMEOUT = 15
UPLOAD_TIMEOUT = 30
MAX_FILE_SIZE = 32 * 1024 * 1024  # 32MB
ALLOWED_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def upload_to_imgbb(source_url: str, api_key: Optional[str] = None) -> dict:
    if not api_key:
        api_key = os.getenv("IMGBB_API_KEY")
    if not api_key:
        return {"success": False, "error": "IMGBB_API_KEY 미설정"}

    try:
        r = requests.get(source_url, timeout=DOWNLOAD_TIMEOUT, stream=True)
        r.raise_for_status()
    except Exception as e:
        return {"success": False, "error": f"다운로드 실패: {e}"}

    content_type = r.headers.get("Content-Type", "").split(";")[0].strip()
    if content_type not in ALLOWED_MIME:
        return {"success": False, "error": f"허용되지 않은 MIME: {content_type}"}

    chunks = []
    total = 0
    for chunk in r.iter_content(chunk_size=8192):
        total += len(chunk)
        if total > MAX_FILE_SIZE:
            return {"success": False, "error": f"파일 크기 초과: {total} bytes"}
        chunks.append(chunk)
    image_bytes = b"".join(chunks)

    if not image_bytes:
        return {"success": False, "error": "빈 이미지 데이터"}

    content_hash = hashlib.sha256(image_bytes).hexdigest()

    try:
        resp = requests.post(
            IMGBB_UPLOAD_URL,
            timeout=UPLOAD_TIMEOUT,
            params={"key": api_key},
            files={"image": ("image.jpg", image_bytes, content_type)},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"success": False, "error": f"imgbb 업로드 실패: {e}"}

    if not data.get("success"):
        return {"success": False, "error": f"imgbb 응답 실패: {data}"}

    public_url = data["data"]["url"]

    try:
        check = requests.head(public_url, timeout=10)
        if check.status_code != 200:
            return {"success": False, "error": f"공개 URL 접근 실패: {check.status_code}"}
    except Exception as e:
        return {"success": False, "error": f"URL 검증 실패: {e}"}

    return {"success": True, "public_url": public_url, "content_hash": content_hash}