import os
import hashlib
import time
import requests
from pathlib import Path
from typing import Optional

IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"
DOWNLOAD_TIMEOUT = 15
UPLOAD_TIMEOUT = 30
MAX_FILE_SIZE = 32 * 1024 * 1024  # 32MB
ALLOWED_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp"}

# 260923 P1-2 Sprint1 — imgbb POST 성공 후의 공개 URL 검증(HEAD) 전용 설정.
# 업로드 자체가 아니라 이 검증이 일시 Timeout으로 실패해 정상 URL을 실패 처리한
# 사례가 4슬롯 발생했다(09-22 07:00/19:01, 09-23 07:00/10:00 — 전부
# "URL 검증 실패: ... Read timeout", 해당 URL은 이후 HEAD 200 정상 확인).
HEAD_TIMEOUT = 10
HEAD_MAX_ATTEMPTS = 3
HEAD_RETRY_DELAYS = (2, 5)  # 1→2 회차 대기, 2→3 회차 대기
# 일시 오류로 보고 재시도할 HTTP 상태: 408(Request Timeout) / 429(Too Many Requests) / 5xx
HEAD_RETRYABLE_STATUS = (408, 429)


def _is_retryable_status(status_code: int) -> bool:
    """재시도 대상 상태코드인지 판정한다. 408·429·5xx만 일시 오류로 본다."""
    return status_code in HEAD_RETRYABLE_STATUS or status_code >= 500


def _verify_public_url(public_url: str) -> dict:
    """imgbb POST 성공 이후의 공개 URL 접근 검증.

    재시도 대상: Timeout/RequestException 등 네트워크 예외, HTTP 408·429·5xx.
    즉시 실패: 408·429를 제외한 4xx(확정적 응답이라 재시도가 무의미).
    업로드 POST는 이 함수 안에서 절대 재호출하지 않는다(중복 업로드 방지).
    모두 실패하면 기존과 동일한 error 문자열로 Fail-closed한다.
    """
    last_error = ""
    for attempt in range(1, HEAD_MAX_ATTEMPTS + 1):
        try:
            check = requests.head(public_url, timeout=HEAD_TIMEOUT)
            if check.status_code == 200:
                return {"ok": True}
            last_error = f"공개 URL 접근 실패: {check.status_code}"
            if not _is_retryable_status(check.status_code):
                return {"ok": False, "error": last_error}
        except Exception as e:
            last_error = f"URL 검증 실패: {e}"
        if attempt < HEAD_MAX_ATTEMPTS:
            time.sleep(HEAD_RETRY_DELAYS[attempt - 1])
    return {"ok": False, "error": last_error}


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


def upload_local_file_to_imgbb(local_path, api_key: Optional[str] = None) -> dict:
    """260801 Step6B — 로컬 이미지 파일(Track B `content_package_builder.py` 산출물
    등)을 imgbb에 직접 업로드해 공개 HTTPS URL을 반환한다.

    기존 upload_to_imgbb()는 원격 source_url을 먼저 다운로드하는 FB 크롤 파이프라인
    전용이라(Caller: source_exporter.py/facebook_crawler.py) 로컬 생성 이미지에는
    맞지 않는다 — 다운로드 단계만 생략하고 나머지(imgbb POST + 공개 URL 검증)는
    동일 패턴을 그대로 재사용한다."""
    if not api_key:
        api_key = os.getenv("IMGBB_API_KEY")
    if not api_key:
        return {"success": False, "error": "IMGBB_API_KEY 미설정"}

    path = Path(local_path)
    if not path.exists():
        return {"success": False, "error": f"파일 없음: {local_path}"}

    try:
        image_bytes = path.read_bytes()
    except OSError as e:
        return {"success": False, "error": f"파일 읽기 실패: {e}"}

    if not image_bytes:
        return {"success": False, "error": "빈 이미지 데이터"}
    if len(image_bytes) > MAX_FILE_SIZE:
        return {"success": False, "error": f"파일 크기 초과: {len(image_bytes)} bytes"}

    content_hash = hashlib.sha256(image_bytes).hexdigest()

    try:
        resp = requests.post(
            IMGBB_UPLOAD_URL,
            timeout=UPLOAD_TIMEOUT,
            params={"key": api_key},
            files={"image": (path.name, image_bytes, "image/png")},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"success": False, "error": f"imgbb 업로드 실패: {e}"}

    if not data.get("success"):
        return {"success": False, "error": f"imgbb 응답 실패: {data}"}

    public_url = data["data"]["url"]

    verified = _verify_public_url(public_url)
    if not verified["ok"]:
        return {"success": False, "error": verified["error"]}

    return {"success": True, "public_url": public_url, "content_hash": content_hash}