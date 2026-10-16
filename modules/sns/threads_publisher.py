"""modules/sns/threads_publisher.py — 261016 Threads 최소 자동게시(공식 REST, 기본 OFF).

Instagram 게시가 성공해 Airtable에 posted 로 기록된 직후에만 호출된다
(launcher/main.py `_job_insta_upload`). Instagram 결과는 절대 바꾸지 않는다.

공식 흐름(developers.facebook.com/docs/threads):
  ① POST /{threads-user-id}/threads (컨테이너) → ② 상태 FINISHED 대기 → ③ POST /{threads-user-id}/threads_publish

계약:
  - 스위치: THREADS_PUBLISH_ENABLED=true + THREADS_PUBLISH_KEYS 허용 목록(credential_key) 둘 다 맞아야 실행.
  - 계정 확인: 발행 전 GET /me 의 id 가 .env {KEY}_THREADS_USER_ID 와 다르면 중단(Fail-closed).
  - 재시도 없음: 어느 단계든 실패하면 그 회차는 끝. ③에서 결과를 확정할 수 없으면 outcome_unknown.
  - 글자 수: Threads 500자 초과면 자르지 않고 건너뜀(caption_generator 의 500자 규칙과 동일, 임의 절단 금지).
  - 토큰은 로그·반환값에 넣지 않는다.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests

from modules.common.logger import get_logger
from modules.common.threads_token import get_threads_token

logger = get_logger("threads_publisher")

GRAPH = "https://graph.threads.net/v1.0/"
THREADS_MAX_TEXT = 500          # docs/design/CONTENT_PLAYBOOK_260807.md 필수 규칙과 동일(caption_generator._MAX_FINAL_PAYLOAD_CHARS)
_STATUS_DEADLINE_SEC = 60
_STATUS_POLL_SEC = 5
_TIMEOUT = 30
_PENDING_PATH = Path(__file__).resolve().parents[2] / "db" / "threads_publish_pending.json"


def enabled_for(credential_key: str) -> bool:
    if os.getenv("THREADS_PUBLISH_ENABLED", "false").strip().lower() != "true":
        return False
    allow = {k.strip() for k in os.getenv("THREADS_PUBLISH_KEYS", "").split(",") if k.strip()}
    return bool(credential_key) and credential_key in allow


def _clean(msg: str, token: str) -> str:
    return (msg.replace(token, "***") if token else msg)[:200]


def publish_threads(*, credential_key: str, image_url: str, text: str,
                    http=requests, sleep=time.sleep, clock=time.monotonic) -> dict:
    """반환: {"status": posted|failed|outcome_unknown|skipped, "threads_media_id", "creation_id", "error"}"""
    out = {"status": "skipped", "threads_media_id": "", "creation_id": "", "error": ""}
    token = get_threads_token(credential_key)
    user_id = os.getenv(f"{credential_key}_THREADS_USER_ID", "").strip()
    if not token or not user_id:
        out["error"] = "NO_THREADS_CREDENTIAL"
        return out
    if len(text or "") > THREADS_MAX_TEXT:
        out["error"] = f"TEXT_TOO_LONG:{len(text)}"
        return out

    # 계정 확인 — 다른 계정 토큰으로 게시하지 않도록 발행 전에 막는다.
    try:
        me = http.get(GRAPH + "me", params={"fields": "id", "access_token": token}, timeout=_TIMEOUT).json()
    except Exception as exc:
        out.update(status="failed", error=f"ME_CHECK_ERROR:{type(exc).__name__}")
        return out
    if str(me.get("id", "")) != user_id:
        out.update(status="failed", error="ACCOUNT_MISMATCH")
        return out

    # ① 컨테이너 — 아직 아무것도 게시되지 않았으므로 실패는 확정 실패.
    params = {"text": text or "", "access_token": token}
    if image_url:
        params.update(media_type="IMAGE", image_url=image_url)
    else:
        params["media_type"] = "TEXT"
    try:
        r1 = http.post(GRAPH + f"{user_id}/threads", params=params, timeout=_TIMEOUT)
        b1 = r1.json()
    except Exception as exc:
        out.update(status="failed", error=f"CONTAINER_ERROR:{type(exc).__name__}")
        return out
    creation_id = str(b1.get("id", "")) if r1.status_code == 200 else ""
    if not creation_id:
        out.update(status="failed", error="CONTAINER_REJECTED:" + _clean(str((b1.get("error") or {}).get("message", "")), token))
        return out
    out["creation_id"] = creation_id

    # ② FINISHED 대기 — 발행 호출 전이므로 여기서 끝나면 확정 실패(게시 안 됨).
    deadline = clock() + _STATUS_DEADLINE_SEC
    while True:
        try:
            st = http.get(GRAPH + creation_id, params={"fields": "status,error_message", "access_token": token},
                          timeout=_TIMEOUT).json().get("status", "")
        except Exception:
            st = ""
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED") or clock() >= deadline:
            out.update(status="failed", error=f"CONTAINER_{st or 'NOT_FINISHED'}")
            return out
        sleep(_STATUS_POLL_SEC)

    # ③ 발행 — 응답을 못 받으면 실제 게시 여부를 알 수 없으므로 outcome_unknown(재시도 없음).
    try:
        r2 = http.post(GRAPH + f"{user_id}/threads_publish",
                       params={"creation_id": creation_id, "access_token": token}, timeout=_TIMEOUT)
    except Exception as exc:
        out.update(status="outcome_unknown", error=f"PUBLISH_NO_RESPONSE:{type(exc).__name__}")
        return out
    if r2.status_code >= 500:
        out.update(status="outcome_unknown", error=f"PUBLISH_HTTP_{r2.status_code}")
        return out
    try:
        b2 = r2.json()
    except Exception:
        out.update(status="outcome_unknown", error="PUBLISH_UNPARSEABLE")
        return out
    media_id = str(b2.get("id", "")) if r2.status_code == 200 else ""
    if media_id:
        out.update(status="posted", threads_media_id=media_id)
    else:
        out.update(status="failed", error="PUBLISH_REJECTED:" + _clean(str((b2.get("error") or {}).get("message", "")), token))
    return out


def record_pending(rid: str, *, credential_key: str, creation_id: str, error: str,
                   account_code_ref: str = "", path: "Path | None" = None) -> None:
    """결과 불명 건을 Instagram 원장과 분리된 파일에 남긴다(수동 확인용, 토큰 없음)."""
    p = path or _PENDING_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    data[rid] = {"credential_key": credential_key, "creation_id": creation_id, "error": error,
                 "account_code_ref": account_code_ref, "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"[Threads] pending 기록 실패 | rid={rid} | {type(exc).__name__}")
