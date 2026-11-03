"""image_pool.py — 261102 STEP 3-2: 노트 손그림 풀(일일 이미지 한도 도달 시 재사용 폴백).

DAILY_IMAGE_CAP(50)은 그대로 두고, 글자·로고 판독을 통과한 손그림을 파일로 모아 두었다가
한도에 걸렸을 때만 이 계정이 아직 쓰지 않은 손그림으로 대체한다.
  - 계정 간 재사용 허용, 같은 계정(scope) 안 중복 금지(풀 사용 기록 PRIMARY KEY).
  - 기본 OFF: IMAGE_POOL_ENABLED=true일 때만 호출부가 이 모듈을 사용한다.
  - 파일명은 전체 SHA-256({sha}.png)이라 서로 다른 이미지가 같은 파일명을 쓸 수 없다.
  - 무결성: 저장 전 실제 PNG 디코딩을 검증하고, 이미 있는 같은 해시 파일은 내용을 다시 해시로 확인한다.
    DB 변경(삽입·보존 정리)은 하나의 트랜잭션이고, 방금 새로 만든 고아 파일은 지운다.
  - 보존: 풀 항목이 IMAGE_POOL_MAX_ITEMS(기본 800)를 넘으면 가장 오래된 항목을 정리한다. 파일 삭제는 DB 커밋 뒤에
    하고, 삭제에 실패한 파일은 pool_trash에 남겨 다음 저장·꺼내기 때 다시 지운다(그 사이 같은 해시가 다시
    저장되어 풀 행이 생겼다면 파일을 지우지 않는다).
  - 풀·DB 오류는 생성 흐름을 바꾸지 않는다: 저장 실패는 경고만 남기고, 꺼내기 실패는 None을 반환해
    호출부가 기존 Fail-closed(DAILY_IMAGE_CAP_EXCEEDED)로 그대로 실패하게 한다. 실패는 항상 로그로 남긴다.
"""

import hashlib
import os
import random
import sqlite3
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from modules.common.logger import get_logger

logger = get_logger(__name__)

_ROOT = Path(__file__).resolve().parents[2]
POOL_DIR = _ROOT / "vault" / "image_pool"
POOL_DB = _ROOT / "db" / "image_pool.db"
_MIN_BYTES = 1024  # 비정상적으로 작은 파일은 풀에 넣지도, 꺼내지도 않는다
DEFAULT_MAX_ITEMS = 800  # 노트 손그림 1장 ≈ 수백 KB, 하루 생성 ≤50장 → 약 16일분


def enabled() -> bool:
    return os.getenv("IMAGE_POOL_ENABLED", "false").strip().lower() == "true"


def max_items() -> int:
    try:
        value = int(os.getenv("IMAGE_POOL_MAX_ITEMS", "").strip() or DEFAULT_MAX_ITEMS)
    except ValueError:
        return DEFAULT_MAX_ITEMS
    return value if value > 0 else DEFAULT_MAX_ITEMS


# 261103 — Flux(Cloudflare)는 JPEG를 돌려주므로 PNG만 받던 풀이 매번 거부했다(ERR 기록 대상). 흔한 래스터
# 형식만 허용하고 확장자는 실제 형식을 따른다(내용 검증은 Pillow, 이름은 SHA).
_EXT_BY_FORMAT = {"PNG": "png", "JPEG": "jpg", "BMP": "bmp", "GIF": "gif", "WEBP": "webp"}
_MAX_PIXELS = 4096 * 4096   # Flux 출력은 약 1024×1024 — 그보다 훨씬 큰 이미지는 풀에 넣지 않는다(디컴프레션 봄 방지)


def _image_format(data: bytes) -> str:
    """허용 형식이고 디코딩 검증을 통과하면 Pillow 형식명(PNG/JPEG/…)을, 아니면 ""를 반환한다."""
    if not data or len(data) < _MIN_BYTES:
        return ""
    try:
        from PIL import Image
        with Image.open(BytesIO(data)) as img:
            fmt = img.format or ""
            if fmt not in _EXT_BY_FORMAT:
                return ""
            width, height = img.size                       # 헤더만 읽은 상태 — 디코딩 전에 크기·프레임 상한을 적용한다
            if width * height > _MAX_PIXELS or getattr(img, "n_frames", 1) > 1:
                return ""
            img.verify()
        return fmt
    except Exception:  # noqa: BLE001 — 디코딩 실패는 모두 "유효하지 않음"
        return ""


def _valid_png(data: bytes) -> bool:
    """하위호환 이름 — 이제 허용 형식(PNG/JPEG/BMP/GIF/WEBP) 전체를 유효로 본다."""
    return bool(_image_format(data))


def _connect(db_path: "Path | None") -> sqlite3.Connection:
    path = Path(db_path or POOL_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS pool ("
        "sha TEXT PRIMARY KEY, path TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS pool_use ("
        "scope TEXT NOT NULL, sha TEXT NOT NULL, used_at TEXT NOT NULL, PRIMARY KEY (scope, sha))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS pool_trash ("
        "sha TEXT PRIMARY KEY, name TEXT NOT NULL, queued_at TEXT NOT NULL)"
    )
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _unlink(path: Path) -> bool:
    """파일을 지운다. 지웠거나 이미 없으면 True, 오류면 로그를 남기고 False."""
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return True
    except OSError as exc:
        logger.warning("[ImagePool] 파일 삭제 실패 | file=%s | error_type=%s", path.name, type(exc).__name__)
        return False


def _queue_trash(conn: sqlite3.Connection, sha: str, name: str) -> None:
    conn.execute("INSERT OR REPLACE INTO pool_trash (sha, name, queued_at) VALUES (?, ?, ?)", (sha, name, _now()))


def _prune(conn: sqlite3.Connection, limit: int, protect: str = "") -> int:
    """풀 항목이 limit을 넘으면 가장 오래된 항목의 DB 기록을 지우고 삭제할 파일을 pool_trash에 올린다
    (호출부 트랜잭션 안). `protect`(방금 저장한 sha)는 같은 호출에서 정리 대상이 되지 않는다.
    지운 개수를 반환한다. 실제 파일 삭제는 커밋 뒤 _drain_trash가 한다."""
    total = conn.execute("SELECT COUNT(*) FROM pool").fetchone()[0]
    excess = total - limit
    if excess <= 0:
        return 0
    old = conn.execute(
        "SELECT sha, path FROM pool WHERE sha != ? ORDER BY created_at ASC, rowid ASC LIMIT ?", (protect, excess),
    ).fetchall()
    for sha, name in old:
        conn.execute("DELETE FROM pool_use WHERE sha = ?", (sha,))
        conn.execute("DELETE FROM pool WHERE sha = ?", (sha,))
        _queue_trash(conn, sha, name)
    logger.info("[ImagePool] 보존 한도 초과 — 오래된 손그림 정리 | removed=%d | limit=%d", len(old), limit)
    return len(old)


def _drain_trash(db_path: "Path | None", directory: Path) -> None:
    """pool_trash의 파일을 지운다. 삭제에 실패하면 남겨 두었다가 다음 호출에서 다시 시도한다.
    같은 해시가 다시 저장되어 풀 행이 있으면 파일을 지우지 않고 trash 기록만 정리한다."""
    try:
        conn = _connect(db_path)
        try:
            for sha, name in conn.execute("SELECT sha, name FROM pool_trash").fetchall():
                in_use = conn.execute("SELECT 1 FROM pool WHERE sha = ?", (sha,)).fetchone() is not None
                if in_use or _unlink(directory / name):
                    conn.execute("DELETE FROM pool_trash WHERE sha = ?", (sha,))
        finally:
            conn.close()
    except (OSError, sqlite3.Error) as exc:
        logger.warning("[ImagePool] 삭제 대기 파일 정리 실패 | error_type=%s | message=%s",
                       type(exc).__name__, str(exc)[:200])


def _referenced(db_path: "Path | None", sha: str) -> "bool | None":
    """풀 DB의 어떤 행이 이 sha를 가리키는지 확인한다. DB를 읽을 수 없으면 None."""
    try:
        conn = _connect(db_path)
        try:
            return conn.execute("SELECT 1 FROM pool WHERE sha = ?", (sha,)).fetchone() is not None
        finally:
            conn.close()
    except (OSError, sqlite3.Error):
        return None


def save_sketch(scope: str, image_bytes: bytes, *, pool_dir: "Path | None" = None,
                db_path: "Path | None" = None) -> str:
    """판독을 통과한 손그림을 풀에 저장하고, 만든 계정(scope)은 이미 쓴 것으로 기록한다. sha를 반환하며
    유효한 PNG가 아니거나 실패하면 경고 로그만 남기고 ""를 반환한다(생성 흐름은 계속된다).
    DB 변경(삽입 2건 + 보존 정리)은 하나의 트랜잭션이라 중간에 실패하면 모두 되돌아간다."""
    if not scope or not image_bytes:
        return ""
    fmt = _image_format(image_bytes)
    if not fmt:
        logger.warning("[ImagePool] 허용 이미지 형식이 아니어서 저장하지 않음 | scope=%s | bytes=%d", scope, len(image_bytes))
        return ""
    sha = hashlib.sha256(image_bytes).hexdigest()
    directory = Path(pool_dir or POOL_DIR)
    target = directory / f"{sha}.{_EXT_BY_FORMAT[fmt]}"            # 전체 SHA 파일명 — 다른 이미지의 파일을 덮어쓸 수 없다
    created_new = False
    tmp = directory / f".{sha}.{os.getpid()}.tmp"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        existed = target.exists()
        existing_ok = False
        if existed:
            try:
                existing_ok = hashlib.sha256(target.read_bytes()).hexdigest() == sha
            except OSError:
                existing_ok = False
        if not existing_ok:                       # 없거나 내용이 다른(손상) 파일은 검증된 바이트로 새로 쓴다
            tmp.write_bytes(image_bytes)
            os.replace(tmp, target)
            created_new = not existed
        conn = _connect(db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO pool (sha, path, created_at) VALUES (?, ?, ?) "
                         "ON CONFLICT(sha) DO UPDATE SET path = excluded.path, created_at = excluded.created_at",
                         (sha, target.name, _now()))                      # 다시 저장하면 가장 최근 항목이 된다
            conn.execute("INSERT OR IGNORE INTO pool_use (scope, sha, used_at) VALUES (?, ?, ?)",
                         (scope, sha, _now()))
            conn.execute("DELETE FROM pool_trash WHERE sha = ?", (sha,))   # 다시 쓰는 파일은 삭제 대기에서 뺀다
            _prune(conn, max_items(), protect=sha)                         # 방금 저장한 항목은 같은 호출에서 정리하지 않는다
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()
        _drain_trash(db_path, directory)          # 커밋 뒤에 파일을 지운다(삭제 실패는 trash에 남겨 재시도)
        return sha
    except (OSError, sqlite3.Error) as exc:
        # 이번 호출이 새로 만든 파일이고 다른 행이 참조하지 않을 때만 지운다(기존 항목의 파일은 건드리지 않는다)
        if created_new and _referenced(db_path, sha) is not True:
            _unlink(target)
        logger.warning("[ImagePool] 손그림 저장 실패 | scope=%s | error_type=%s | message=%s",
                       scope, type(exc).__name__, str(exc)[:200])
        return ""
    finally:
        _unlink(tmp)


def take_unused_sketch(scope: str, *, exclude=(), pool_dir: "Path | None" = None,
                       db_path: "Path | None" = None) -> "tuple[str, bytes] | None":
    """이 scope가 아직 쓰지 않은 손그림 1장을 골라 사용 기록을 남기고 (sha, bytes)를 반환한다.
    손상·해시 불일치 항목은 풀에서 정리한다(파일은 삭제 대기). 없거나 오류면 None(호출부는 기존 실패 경로를 그대로 탄다)."""
    if not scope:
        return None
    excluded = set(exclude)
    directory = Path(pool_dir or POOL_DIR)
    try:
        conn = _connect(db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT sha, path FROM pool WHERE sha NOT IN (SELECT sha FROM pool_use WHERE scope = ?)",
                (scope,),
            ).fetchall()
            candidates = [(sha, name) for sha, name in rows if sha not in excluded]
            random.shuffle(candidates)
            picked = None
            cleaned = False
            for sha, name in candidates:
                file = directory / name
                try:
                    data = file.read_bytes()
                except OSError:
                    data = b""
                if len(data) < _MIN_BYTES or hashlib.sha256(data).hexdigest() != sha:
                    conn.execute("DELETE FROM pool_use WHERE sha = ?", (sha,))      # 손상 항목은 풀에서 정리
                    conn.execute("DELETE FROM pool WHERE sha = ?", (sha,))
                    _queue_trash(conn, sha, name)
                    cleaned = True
                    logger.warning("[ImagePool] 손상·누락 손그림 정리 | scope=%s | sha=%s", scope, sha[:12])
                    continue
                conn.execute("INSERT INTO pool_use (scope, sha, used_at) VALUES (?, ?, ?)", (scope, sha, _now()))
                picked = (sha, data)
                break
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()
        if cleaned:
            _drain_trash(db_path, directory)
        if picked is None:
            logger.warning("[ImagePool] 사용 가능한 손그림 없음 | scope=%s | candidates=%d", scope, len(candidates))
        return picked
    except (OSError, sqlite3.Error) as exc:
        logger.warning("[ImagePool] 손그림 꺼내기 실패 | scope=%s | error_type=%s | message=%s",
                       scope, type(exc).__name__, str(exc)[:200])
        return None
