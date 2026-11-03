"""
modules/sns/reuse_replenisher.py — 041(YURA) 과거 게시 자산 재사용 보충 (261103 설계, 회장 승인)

허용 목록 계정마다 post_status=ready 행을 READY_TARGET건으로 유지한다. 후보는 IDN-000041 의
posted 행 전부이고, 캡션·해시태그는 그대로 쓰며 Gate 는 걸지 않는다(이미 041 에서 게시된 글).
같은 계정 안에서는 image_url_hash 중복을 만들지 않는다(계정 간 중복은 허용, 261102 정책).

설계 문서: docs/design/REUSE_REPLENISHER_DESIGN_261103.md
Caller: launcher/main.py `_job_reuse_replenish` (REUSE_REPLENISH_ENABLED=true 일 때만 등록).

저장소 경계(Codex 리뷰 261103 반영): Airtable 접근은 전부 RepositoryInterface(`repo`)를 통해서만 한다.
이 모듈에는 Airtable 테이블·인증 세부사항이 없다. ImgBB·Graph 호출만 `_Images` 어댑터에 있다.
READY_GLOBAL_CAP 은 "이 잡이 새로 만드는 양"에 대한 가드일 뿐, 기존 backlog 나 다른 생산자의 ready 를
정리하지 않는다. 같은 호스트의 중복 실행은 OS 파일 잠금(`db/reuse_replenish.lock`, 프로세스 종료 시 자동 해제,
stale 회수 없음)으로 막는다. 이 모듈은 Repository 의 선택 메서드(count_ready_posts_by_account 등)를 호출하므로
이를 구현하지 않은 Repository 로는 실행되지 않는다(REPO_UNSUPPORTED 로 중단).
회로 차단은 "최근 24시간 안에 생성된 R041-AUTO 행 중 현재 failed" 건수이며, 실패 시각·오류 코드 기준이 아니고
Meta 9004 전용도 아니다. 차단돼도 이미 ready 인 행의 게시 시도는 멈추지 않는다(새 행 생성만 중단).
로그에는 토큰·URL 을 남기지 않는다.
"""

import json
import os
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import requests

from modules.common.logger import get_logger

logger = get_logger(__name__)

SOURCE_ACCOUNT = "IDN-000041"
READY_TARGET = 2
READY_GLOBAL_CAP = 40
RUN_ID_PREFIX = "R041-AUTO"
FAILURE_BREAKER = 3          # 최근 24시간 안에 이 잡이 만든 행이 failed 로 끝난 건수가 이 값 이상이면 보충 중단
FAILURE_WINDOW_HOURS = 24
_ACCOUNT_RE = re.compile(r"^IDN-\d{6}$")
_ROOT = Path(__file__).resolve().parents[2]
_STATE_PATH = _ROOT / "db" / "reuse_replenish_state.json"
_LOCK_PATH = _ROOT / "db" / "reuse_replenish.lock"
_GRAPH = "https://graph.facebook.com/v21.0"


class GraphAuthError(Exception):
    """Graph API 가 토큰 오류(190/459)를 돌려줌 — 이번 회차 전체를 중단한다."""


class RepositoryFeatureUnsupported(Exception):
    """연결된 Repository 가 재사용 보충용 선택 메서드를 구현하지 않음(Codex 3차: 분류 범위 한정)."""


def _opt(repo, name: str, *args):
    """Repository 선택 메서드 호출. NotImplementedError 만 RepositoryFeatureUnsupported 로 바꾼다
    (다른 곳에서 난 NotImplementedError 는 그대로 전파해 오분류하지 않는다)."""
    try:
        return getattr(repo, name)(*args)
    except NotImplementedError as exc:
        raise RepositoryFeatureUnsupported(name) from exc


class _Images:
    def alive(self, url: str) -> bool:
        if not url:
            return False
        try:
            resp = requests.get(url, timeout=15, stream=True)
            ok = resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/")
            resp.close()
            return ok
        except requests.RequestException:
            return False

    def upload(self, source_url: str) -> str:
        from modules.sns.image_hosting import upload_to_imgbb
        res = upload_to_imgbb(source_url)
        return res["public_url"] if res.get("success") else ""

    def graph_media_url(self, ig_media_id: str) -> str:
        token = os.getenv("YUNA_INSTA_ACCESS_TOKEN") or os.getenv("INSTA_ACCESS_TOKEN") or ""
        if not (ig_media_id and token):
            return ""
        try:
            r = requests.get(f"{_GRAPH}/{ig_media_id}",
                             params={"fields": "media_url,media_type", "access_token": token}, timeout=20)
        except requests.RequestException:
            return ""
        if r.status_code != 200:
            try:
                code = r.json().get("error", {}).get("code")
            except Exception:
                code = None
            if code in (190, 459):
                raise GraphAuthError(f"graph_code={code}")
            return ""
        j = r.json()
        return j.get("media_url", "") if j.get("media_type") == "IMAGE" else ""


@contextmanager
def _file_lock(path: Path):
    """OS 수준 배타 잠금(Windows msvcrt / POSIX fcntl). 프로세스가 죽으면 OS 가 자동으로 푼다.

    stale 시간 판정이나 파일 삭제가 없어서(잠금 파일은 남겨 둔다) 오래 걸리는 살아 있는 실행을
    다른 실행이 빼앗을 수 없다. 이미 다른 핸들이 잡고 있으면 acquired=False."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+b")
    acquired = False
    try:
        if fh.seek(0, os.SEEK_END) == 0:
            fh.write(b"0")
            fh.flush()
        fh.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            acquired = False
        yield acquired
    finally:
        if acquired:
            try:
                fh.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        fh.close()


def _load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(path: Path, state: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except Exception as exc:
        logger.warning("[ReuseReplenish] 상태파일 쓰기 실패 | %s", type(exc).__name__)


def _resolve_image(src: dict, images) -> str:
    """살아 있는 image_url → 원본 재업로드 → Graph 복구 순서. 못 구하면 빈 문자열."""
    image_url = src.get("image_url", "")
    if images.alive(image_url):
        return image_url
    orig = src.get("original_image_url", "")
    if images.alive(orig):
        new = images.upload(orig)
        if new:
            return new
    media_url = images.graph_media_url(src.get("ig_media_id", ""))
    if media_url:
        return images.upload(media_url)
    return ""


def _notify_once_per_day(state: dict, key: str, now: datetime, notify, message: str) -> None:
    today = now.strftime("%Y-%m-%d")
    if state.get(key) != today:
        state[key] = today
        notify(message)


def run_once(
    accounts: list,
    repo=None,
    images=None,
    notify: Optional[Callable[[str], None]] = None,
    state_path: Path = _STATE_PATH,
    lock_path: Path = _LOCK_PATH,
    now: Optional[datetime] = None,
    ready_target: int = READY_TARGET,
    global_cap: int = READY_GLOBAL_CAP,
) -> dict:
    """한 회차 실행. 반환: {"skipped": 사유 | None, "created": {계정: 건수}, "exhausted": [...], ...}"""
    if repo is None:
        from modules.infra.airtable_repository import AirtableRepository
        repo = AirtableRepository()
    images = images or _Images()
    notify = notify or (lambda msg: None)
    now = now or datetime.now()
    result = {"skipped": None, "created": {}, "failed_images": 0, "exhausted": [], "ready": {}}

    targets = []
    for a in accounts:
        a = (a or "").strip()
        if _ACCOUNT_RE.fullmatch(a) and a != SOURCE_ACCOUNT and a not in targets:
            targets.append(a)
    if not targets:
        result["skipped"] = "NO_TARGETS"
        return result

    with _file_lock(lock_path) as acquired:
        if not acquired:
            result["skipped"] = "LOCKED"
            logger.info("[ReuseReplenish] 다른 실행이 진행 중 — 이번 회차 건너뜀")
            return result
        state = _load_state(state_path)
        try:
            _run_locked(targets, repo, images, notify, state, now, ready_target, global_cap, result)
        except RepositoryFeatureUnsupported as exc:
            # 선택 Repository 메서드를 구현하지 않은 구현체에 연결됨 — 조용히 넘기지 않고 중단한다.
            result["skipped"] = "REPO_UNSUPPORTED"
            logger.error("[ReuseReplenish] 이 Repository 는 재사용 보충용 메서드를 구현하지 않음 — 중단 | repo=%s | method=%s",
                         type(repo).__name__, exc)
        finally:
            state["last_run"] = now.strftime("%Y-%m-%d %H:%M:%S")
            state["last_result"] = dict(result)
            _save_state(state_path, state)
    return result


def _run_locked(targets, repo, images, notify, state, now, ready_target, global_cap, result) -> None:
    per_acct = _opt(repo, "count_ready_posts_by_account")
    total_ready = sum(per_acct.values())
    result["ready"] = {a: per_acct.get(a, 0) for a in targets}
    if total_ready >= global_cap:
        result["skipped"] = "GLOBAL_CAP"
        logger.info("[ReuseReplenish] 전체 ready %d건 ≥ 상한 %d — 이번 회차 생성 안 함", total_ready, global_cap)
        return

    recent_failed = _opt(repo, "count_recent_failed_posts_by_run_prefix", RUN_ID_PREFIX, FAILURE_WINDOW_HOURS)
    if recent_failed >= FAILURE_BREAKER:
        result["skipped"] = "PUBLISH_FAILURES"
        logger.error("[ReuseReplenish] 최근 %d시간 게시 실패 %d건 ≥ %d — 보충 중단",
                     FAILURE_WINDOW_HOURS, recent_failed, FAILURE_BREAKER)
        _notify_once_per_day(
            state, "failure_breaker_date", now, notify,
            f"[경고] 재사용 보충 중단 — 최근 {FAILURE_WINDOW_HOURS}시간 안에 이 잡이 만든 글 {recent_failed}건이 "
            f"게시 실패했습니다(이미지 호스트 문제 가능). 원인 확인 전까지 새 글을 만들지 않습니다.")
        return

    source = None
    run_id = f"{RUN_ID_PREFIX}-{now.strftime('%y%m%d')}"
    try:
        for acct in targets:
            need = min(ready_target - per_acct.get(acct, 0), global_cap - total_ready)
            if need <= 0:
                continue
            try:
                account = repo.get_publish_account(acct)
            except Exception as exc:
                logger.warning("[ReuseReplenish] 건너뜀 — 계정 조회 실패/모호 | account=%s | %s",
                               acct, type(exc).__name__)
                continue
            if not account or not account.get("automation_enabled"):
                logger.info("[ReuseReplenish] 건너뜀 — automation_enabled 아님 | account=%s", acct)
                continue
            if source is None:
                source = sorted(_opt(repo, "fetch_reuse_source_posts", SOURCE_ACCOUNT),
                                key=lambda p: (p.get("insta_post_code") or "~", p.get("post_id", "")))
            have = _opt(repo, "fetch_image_hashes_for_account", acct)
            made = 0
            for src in source:
                if made >= need:
                    break
                if src.get("image_url_hash") in have:
                    continue
                image_url = _resolve_image(src, images)
                if not image_url:
                    result["failed_images"] += 1
                    continue
                post = {
                    "insta_post_code": f"{run_id}-{acct[-3:]}-{now.strftime('%H%M%S')}-{made + 1}",
                    "account_code_ref": acct,
                    "post_status": "ready",
                    "image_url": image_url,
                    "original_image_url": src.get("original_image_url", ""),
                    "image_url_hash": src.get("image_url_hash", ""),
                    "source_url": src.get("source_url", ""),
                    "caption": src.get("caption", ""),
                    "hashtag": src.get("hashtag", ""),
                    "media_type": src.get("media_type") or "image",
                    "data_classification": "production",
                    "run_id": run_id,
                }
                text = (src.get("original_text") or "").strip()
                if text:
                    post["original_text"] = text
                    post["converted_text"] = text
                repo.save_instagram_post(post)
                have.add(src.get("image_url_hash"))
                made += 1
                total_ready += 1
            result["created"][acct] = made
            if made < need and all(s.get("image_url_hash") in have for s in source):
                result["exhausted"].append(acct)
    except GraphAuthError as exc:
        result["skipped"] = "GRAPH_AUTH"
        logger.error("[ReuseReplenish] Graph 토큰 오류 — 이번 회차 중단 | %s", exc)
        _notify_once_per_day(state, "graph_alert_date", now, notify,
                             "[경고] 재사용 보충 중단 — 041 Graph 토큰 오류(190/459). 토큰 확인 필요, 게시는 영향 없음.")
    for acct in result["exhausted"]:
        exhausted = state.setdefault("exhausted_notified", {})
        if not exhausted.get(acct):
            exhausted[acct] = True
            notify(f"[알림] 재사용 자산 소진 — {acct}. 새 크롤 또는 새 원본이 필요합니다.")
    logger.info("[ReuseReplenish] 완료 | created=%s ready=%s failed_images=%d exhausted=%s",
                result["created"], result["ready"], result["failed_images"], result["exhausted"])
