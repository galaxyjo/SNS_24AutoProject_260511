"""261102 STEP 3-2 — 일일 이미지 한도 도달 시 손그림 풀 재사용 폴백 Target Test.

네트워크(Gemini·Cloudflare)·운영 풀/DB 없음 — 풀 경로는 전부 tmp로 바꾸고 생성·판독은 가짜로 바꾼다.
"""

from io import BytesIO

import pytest
from PIL import Image

import modules.sns.content_package_builder as builder
import modules.sns.image_pool as pool
import modules.sns.image_text_checker as checker
from modules.sns.carousel_content_builder import CarouselContent, Slide
from modules.sns.image_provider_cloudflare import ProviderResult


def _png(seed):
    buf = BytesIO()
    Image.new("RGB", (1024, 1024), (seed * 11 % 255, seed * 23 % 255, seed * 37 % 255)).save(buf, format="PNG")
    return buf.getvalue()


def _carousel(n=3):
    return CarouselContent(
        slot_role="REACH", template_type="HOOK_IMPACT", source_section_id="3.1",
        source_title="T", source_url="https://example.com/t",
        slides=tuple(Slide(index=i + 1, role="r", text=f"본문 {i + 1}", image_scene=f"scene-{i + 1}") for i in range(n)),
        caption="캡션입니다.\n\n저장해두세요.", hashtags=("a", "b", "c", "d", "e"), content_fingerprint="fp",
    )


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("IMAGE_POOL_ENABLED", "true")
    monkeypatch.setattr(pool, "POOL_DIR", tmp_path / "pool")
    monkeypatch.setattr(pool, "POOL_DB", tmp_path / "pool.db")
    state = {"gen_calls": 0, "cap_after": None, "checks": [], "seed": 0, "fail_slide_once": set(), "other_error": None}

    def _generate(prompt, negative_prompt=""):
        state["gen_calls"] += 1
        if state["other_error"]:
            return ProviderResult(success=False, error_code=state["other_error"])
        if state["cap_after"] is not None and state["gen_calls"] > state["cap_after"]:
            return ProviderResult(success=False, error_code="DAILY_IMAGE_CAP_EXCEEDED")
        state["seed"] += 1
        return ProviderResult(success=True, image_bytes=_png(state["seed"]))

    def _check(images, **kw):
        state["checks"].append(len(images))
        return checker.ImageCheckResult(success=True, checks=tuple(
            checker.ImageCheck(index=i + 1, has_text=False, has_logo=False) for i in range(len(images))))

    monkeypatch.setattr(builder, "generate_image", _generate)
    monkeypatch.setattr(builder, "check_images_for_text_and_logo", _check)
    state["pool"] = pool
    return state


def _build(scope, n=3):
    topic = type("T", (), {"title": "Topic"})()
    return builder._build_note_carousel_images(topic, _carousel(n), pool_scope=scope)


def test_passed_sketches_are_saved_to_pool_and_marked_used_by_creator(env, tmp_path):
    images, err = _build("IDN-000036")
    assert err == "" and len(images) == 3 and env["gen_calls"] == 3
    assert len(list((tmp_path / "pool").glob("*.png"))) == 3
    # 만든 계정은 같은 손그림을 다시 받을 수 없다
    assert pool.take_unused_sketch("IDN-000036") is None


def test_cap_exceeded_falls_back_to_pool_for_another_account_without_checking_again(env):
    _build("IDN-000036")                                   # 풀에 3장 저장
    env["cap_after"] = env["gen_calls"]                     # 이후 생성은 모두 한도 초과
    env["checks"].clear()
    images, err = _build("IDN-000027")
    assert err == "" and len(images) == 3
    assert env["checks"] == []                              # 풀 손그림은 이미 판독을 통과해 다시 판독하지 않는다


def test_same_account_never_reuses_a_sketch_and_fails_closed_when_pool_exhausted(env):
    _build("IDN-000036")
    env["cap_after"] = env["gen_calls"]
    assert _build("IDN-000027")[1] == ""                    # 027이 3장 모두 사용
    images, err = _build("IDN-000027")                      # 027에겐 남은 손그림이 없다
    assert images is None and err == "IMAGE_PROVIDER_REJECTED"   # 한도 초과의 기존 Fail-closed 코드 그대로


def test_no_duplicate_sketch_inside_one_package(env):
    _build("A")
    _build("B")                                             # 풀에 6장
    env["cap_after"] = env["gen_calls"]
    images, err = _build("C")
    assert err == "" and len({bytes(i) for i in images}) == 3


def test_flag_off_keeps_existing_behavior(env, monkeypatch, tmp_path):
    monkeypatch.setenv("IMAGE_POOL_ENABLED", "false")
    _build("IDN-000036")
    assert not (tmp_path / "pool").exists() and not (tmp_path / "pool.db").exists()   # 저장도 안 한다
    env["cap_after"] = env["gen_calls"]
    images, err = _build("IDN-000027")
    assert images is None and err == "IMAGE_PROVIDER_REJECTED"


def test_empty_scope_disables_pool(env, tmp_path):
    _build("")
    assert not (tmp_path / "pool").exists()


def test_other_provider_errors_do_not_use_pool(env):
    _build("IDN-000036")
    env["other_error"] = "HTTP_500"
    images, err = _build("IDN-000027")
    assert images is None and err == "IMAGE_GENERATION_FAILED"


def test_pool_failure_is_logged_and_falls_back_to_existing_failure(env, monkeypatch, caplog):
    import logging
    _build("IDN-000036")
    env["cap_after"] = env["gen_calls"]
    monkeypatch.setattr(pool, "POOL_DB", pool.POOL_DB.parent / "missing_dir" / ("x" * 400) / "pool.db")
    pool.logger.propagate = True
    with caplog.at_level(logging.WARNING):
        images, err = _build("IDN-000027")
    assert images is None and err == "IMAGE_PROVIDER_REJECTED"
    assert any("손그림 꺼내기 실패" in r.getMessage() or "손그림 저장 실패" in r.getMessage() or "사용 가능한 손그림 없음" in r.getMessage()
               for r in caplog.records)


def test_daily_cap_constant_unchanged():
    from modules.sns.image_provider_cloudflare import DAILY_IMAGE_CAP
    assert DAILY_IMAGE_CAP == 50


def test_corrupt_pool_file_is_skipped(env, tmp_path):
    _build("IDN-000036")
    for f in (tmp_path / "pool").glob("*.png"):
        f.write_bytes(b"x" * 2000)                          # sha 불일치(손상) → 건너뜀
    assert pool.take_unused_sketch("OTHER") is None


# ── Codex 1차 검수 반영(무결성·보존·scope) ─────────────────────────────────────

def test_non_png_or_tiny_bytes_are_not_saved(env, tmp_path):
    assert pool.save_sketch("A", b"not a png" * 400) == ""          # 1KB 이상이어도 PNG 디코딩 실패
    assert pool.save_sketch("A", b"\x89PNG") == ""
    assert not (tmp_path / "pool").exists() or not list((tmp_path / "pool").glob("*.png"))


def _img(fmt, seed=1, size=(1024, 1024)):
    buf = BytesIO()
    Image.new("RGB", size, (seed * 11 % 255, seed * 23 % 255, seed * 37 % 255)).save(buf, format=fmt)
    return buf.getvalue()


@pytest.mark.parametrize("fmt,ext", [("PNG", "png"), ("JPEG", "jpg"), ("BMP", "bmp"), ("GIF", "gif"), ("WEBP", "webp")])
def test_allowed_formats_are_saved_with_matching_extension_and_round_trip(env, tmp_path, fmt, ext):
    data = _img(fmt, seed=3)
    sha = pool.save_sketch("A", data)
    assert sha
    assert (tmp_path / "pool" / f"{sha}.{ext}").read_bytes() == data
    picked = pool.take_unused_sketch("B")
    assert picked == (sha, data)                                    # 다른 계정이 같은 바이트를 그대로 받는다


@pytest.mark.parametrize("fmt", ["TIFF", "ICO"])
def test_formats_outside_allowlist_are_not_saved(env, tmp_path, fmt):
    assert pool.save_sketch("A", _img(fmt, size=(256, 256))) == ""
    assert not (tmp_path / "pool").exists() or not list((tmp_path / "pool").iterdir())


def test_oversized_image_is_rejected_before_save(env, monkeypatch, tmp_path):
    monkeypatch.setattr(pool, "_MAX_PIXELS", 1024 * 1024 - 1)
    assert pool.save_sketch("A", _img("JPEG")) == ""                # 1024×1024는 상한 초과
    monkeypatch.setattr(pool, "_MAX_PIXELS", 1024 * 1024)
    assert pool.save_sketch("A", _img("JPEG"))                      # 정확히 상한이면 통과(경계)


def test_multi_frame_gif_and_webp_are_rejected(env, tmp_path):
    for fmt in ("GIF", "WEBP"):
        buf = BytesIO()
        frames = [Image.new("RGB", (512, 512), (i * 60, 10, 10)) for i in range(3)]
        frames[0].save(buf, format=fmt, save_all=True, append_images=frames[1:], duration=100)
        assert len(buf.getvalue()) >= 1024
        assert pool.save_sketch("A", buf.getvalue()) == ""
    assert not (tmp_path / "pool").exists() or not list((tmp_path / "pool").iterdir())


def test_empty_tiny_and_fake_extension_bytes_are_rejected(env):
    assert pool.save_sketch("A", b"") == ""
    assert pool.save_sketch("A", _img("JPEG", size=(8, 8))) == ""   # 1KB 미만
    assert pool.save_sketch("A", b"\xff\xd8\xff" + b"\x00" * 3000) == ""   # JPEG 헤더 흉내만 낸 바이트


def test_resaving_same_jpeg_keeps_single_jpg_file(env, tmp_path):
    data = _img("JPEG", seed=7)
    assert pool.save_sketch("A", data) == pool.save_sketch("B", data)
    assert [p.suffix for p in (tmp_path / "pool").iterdir()] == [".jpg"]


def test_truncated_jpeg_is_not_saved(env, tmp_path):
    assert pool.save_sketch("A", _img("JPEG")[:600] + b"\x00" * 600) == ""


def test_jpeg_from_provider_is_pooled_during_generation(env, monkeypatch, tmp_path):
    seeds = iter(range(1, 50))
    monkeypatch.setattr(builder, "generate_image",
                        lambda prompt, negative_prompt="": ProviderResult(success=True, image_bytes=_img("JPEG", next(seeds))))
    images, err = _build("IDN-000036")
    assert not err and len(images) == 3
    assert len(list((tmp_path / "pool").glob("*.jpg"))) == 3


def test_existing_corrupt_file_with_same_hash_name_is_repaired(env, tmp_path):
    data = _png(5)
    import hashlib
    sha = hashlib.sha256(data).hexdigest()
    (tmp_path / "pool").mkdir(parents=True)
    (tmp_path / "pool" / f"{sha}.png").write_bytes(b"x" * 2000)      # 같은 이름의 손상 파일
    assert pool.save_sketch("A", data) == sha
    assert (tmp_path / "pool" / f"{sha}.png").read_bytes() == data   # 검증된 바이트로 교체


def test_db_failure_leaves_no_orphan_file(env, monkeypatch, tmp_path):
    import sqlite3

    def _boom(db_path):
        raise sqlite3.OperationalError("db down")

    monkeypatch.setattr(pool, "_connect", _boom)
    assert pool.save_sketch("A", _png(6)) == ""
    assert not list((tmp_path / "pool").glob("*"))                        # png·tmp 모두 남지 않는다


def test_prune_removes_oldest_beyond_max_items(env, monkeypatch, tmp_path):
    monkeypatch.setenv("IMAGE_POOL_MAX_ITEMS", "3")
    shas = [pool.save_sketch("A", _png(10 + i)) for i in range(5)]
    assert all(shas)
    left = sorted(p.name for p in (tmp_path / "pool").glob("*.png"))
    assert len(left) == 3 and left == sorted(f"{s}.png" for s in shas[2:])   # 가장 오래된 2개 삭제
    import sqlite3
    conn = sqlite3.connect(tmp_path / "pool.db")
    assert conn.execute("select count(*) from pool").fetchone()[0] == 3
    assert conn.execute("select count(*) from pool_use where sha in (?,?)", (shas[0], shas[1])).fetchone()[0] == 0


@pytest.mark.parametrize("raw,expected", [("", 800), ("abc", 800), ("0", 800), ("-5", 800), ("25", 25)])
def test_max_items_parsing(monkeypatch, raw, expected):
    monkeypatch.setenv("IMAGE_POOL_MAX_ITEMS", raw)
    assert pool.max_items() == expected


def test_corrupt_entries_are_cleaned_when_taken(env, tmp_path):
    _build("IDN-000036")
    import sqlite3
    for f in (tmp_path / "pool").glob("*.png"):
        f.write_bytes(b"x" * 2000)
    assert pool.take_unused_sketch("OTHER") is None
    conn = sqlite3.connect(tmp_path / "pool.db")
    assert conn.execute("select count(*) from pool").fetchone()[0] == 0   # 손상 항목이 풀에서 정리됨
    assert not list((tmp_path / "pool").glob("*.png"))


def test_pool_scope_only_for_account_vaults(tmp_path):
    from pathlib import Path
    assert builder._pool_scope_for_root(builder.DEFAULT_VAULT_ROOT) == "IDN-000036"
    assert builder._pool_scope_for_root(Path("x") / "vault" / "accounts" / "IDN-000027") == "IDN-000027"
    assert builder._pool_scope_for_root(tmp_path) == ""                   # 임의 폴더·테스트 경로는 풀 미사용
    assert builder._pool_scope_for_root(Path("x") / "IDN-0000271") == ""
    assert builder._pool_scope_for_root(Path("x") / "idn-000027") == ""


# ── Codex 2차 검수 반영(트랜잭션·기존 파일 보호) ─────────────────────────────────

def _db_counts(tmp_path):
    import sqlite3
    conn = sqlite3.connect(tmp_path / "pool.db")
    return (conn.execute("select count(*) from pool").fetchone()[0],
            conn.execute("select count(*) from pool_use").fetchone()[0])


def test_prune_failure_rolls_back_whole_save(env, monkeypatch, tmp_path):
    import sqlite3
    monkeypatch.setenv("IMAGE_POOL_MAX_ITEMS", "3")
    old = [pool.save_sketch("A", _png(30 + i)) for i in range(3)]
    before_files = sorted(p.name for p in (tmp_path / "pool").glob("*.png"))
    before_counts = _db_counts(tmp_path)

    def _half_prune(conn, limit, protect=""):        # 오래된 행 하나를 지운 뒤 실패
        conn.execute("DELETE FROM pool WHERE sha = ?", (old[0],))
        raise sqlite3.OperationalError("prune failed midway")

    monkeypatch.setattr(pool, "_prune", _half_prune)
    new = _png(99)
    assert pool.save_sketch("B", new) == ""
    assert _db_counts(tmp_path) == before_counts     # 삽입·부분 삭제 모두 되돌아감
    assert sorted(p.name for p in (tmp_path / "pool").glob("*.png")) == before_files   # 새 파일 제거, 기존 파일 보존


def test_db_failure_keeps_file_referenced_by_existing_row(env, monkeypatch, tmp_path):
    import hashlib, sqlite3
    data = _png(40)
    sha = pool.save_sketch("A", data)
    target = tmp_path / "pool" / f"{sha}.png"
    target.write_bytes(b"x" * 2000)                  # 기존 항목의 파일이 손상됨
    real = pool._connect
    calls = {"n": 0}

    def _flaky(db_path):                             # 저장 중 DB 연결만 실패, 참조 확인은 성공
        calls["n"] += 1
        if calls["n"] == 1:
            raise sqlite3.OperationalError("db down")
        return real(db_path)

    monkeypatch.setattr(pool, "_connect", _flaky)
    assert pool.save_sketch("B", data) == ""
    assert target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == sha   # 복구된 파일을 지우지 않는다


def test_db_failure_on_resave_of_valid_existing_entry_does_not_delete_file(env, monkeypatch, tmp_path):
    import sqlite3
    data = _png(41)
    sha = pool.save_sketch("A", data)
    monkeypatch.setattr(pool, "_connect", lambda db: (_ for _ in ()).throw(sqlite3.OperationalError("down")))
    assert pool.save_sketch("B", data) == ""
    assert (tmp_path / "pool" / f"{sha}.png").read_bytes() == data


def test_file_delete_error_after_commit_keeps_db_consistent(env, monkeypatch, tmp_path):
    from pathlib import Path
    monkeypatch.setenv("IMAGE_POOL_MAX_ITEMS", "2")
    shas = [pool.save_sketch("A", _png(50 + i)) for i in range(2)]
    real_unlink = Path.unlink
    blocked = {"on": True}

    def _deny(self, *a, **k):
        if blocked["on"] and self.suffix == ".png":
            raise PermissionError("locked")
        return real_unlink(self, *a, **k)

    monkeypatch.setattr(Path, "unlink", _deny)
    new_sha = pool.save_sketch("A", _png(60))        # 가장 오래된 항목 정리 시 파일 삭제가 실패해도
    assert new_sha
    blocked["on"] = False
    assert _db_counts(tmp_path)[0] == 2              # DB는 한도(2)로 일관되게 정리됨


# ── Codex 3차 검수 반영(전체 SHA 파일명·삭제 실패 재시도) ─────────────────────────

def test_file_names_are_full_sha(env, tmp_path):
    sha = pool.save_sketch("A", _png(70))
    assert [p.name for p in (tmp_path / "pool").glob("*.png")] == [f"{sha}.png"] and len(sha) == 64


def test_legacy_short_prefix_named_file_is_never_overwritten(env, tmp_path):
    import hashlib, sqlite3
    other = _png(71)
    other_sha = hashlib.sha256(other).hexdigest()
    new = _png(72)
    new_sha = hashlib.sha256(new).hexdigest()
    (tmp_path / "pool").mkdir(parents=True)
    legacy = tmp_path / "pool" / f"{new_sha[:24]}.png"          # 옛 24자리 접두사 이름(다른 항목이 참조)
    legacy.write_bytes(other)
    conn = sqlite3.connect(tmp_path / "pool.db")
    conn.execute("CREATE TABLE pool (sha TEXT PRIMARY KEY, path TEXT NOT NULL, created_at TEXT NOT NULL)")
    conn.execute("CREATE TABLE pool_use (scope TEXT NOT NULL, sha TEXT NOT NULL, used_at TEXT NOT NULL, PRIMARY KEY (scope, sha))")
    conn.execute("INSERT INTO pool VALUES (?,?,?)", (other_sha, legacy.name, "2026-11-01T00:00:00+00:00"))
    conn.commit(); conn.close()
    assert pool.save_sketch("A", new) == new_sha
    assert legacy.read_bytes() == other                           # 참조 중인 다른 파일은 그대로
    assert (tmp_path / "pool" / f"{new_sha}.png").read_bytes() == new


def _trash(tmp_path):
    import sqlite3
    return [r[0] for r in sqlite3.connect(tmp_path / "pool.db").execute("select name from pool_trash").fetchall()]


def test_prune_delete_failure_is_queued_and_retried_later(env, monkeypatch, tmp_path):
    from pathlib import Path
    monkeypatch.setenv("IMAGE_POOL_MAX_ITEMS", "2")
    old = [pool.save_sketch("A", _png(80 + i)) for i in range(2)]
    real_unlink = Path.unlink
    blocked = {"on": True}

    def _deny(self, *a, **k):
        if blocked["on"] and self.suffix == ".png":
            raise PermissionError("locked")
        return real_unlink(self, *a, **k)

    monkeypatch.setattr(Path, "unlink", _deny)
    new_sha = pool.save_sketch("A", _png(90))                     # 가장 오래된 old[0] 정리, 파일 삭제는 실패
    assert new_sha
    assert _trash(tmp_path) == [f"{old[0]}.png"] and (tmp_path / "pool" / f"{old[0]}.png").exists()
    assert _db_counts(tmp_path)[0] == 2
    blocked["on"] = False                                          # 잠금 해제 후 다음 저장에서 다시 지운다
    assert pool.save_sketch("A", _png(91))
    leftover = {p.name for p in (tmp_path / "pool").glob("*.png")}
    import sqlite3
    rows = {r[0] for r in sqlite3.connect(tmp_path / "pool.db").execute("select path from pool").fetchall()}
    assert leftover - rows <= set(_trash(tmp_path))               # 풀 행이 없는 파일은 trash에만 남는다
    assert f"{old[0]}.png" not in leftover                       # 재시도로 지워짐


def test_resaving_pruned_hash_keeps_its_file_and_restores_row(env, monkeypatch, tmp_path):
    from pathlib import Path
    monkeypatch.setenv("IMAGE_POOL_MAX_ITEMS", "2")
    data0 = _png(100)
    sha0 = pool.save_sketch("A", data0)
    pool.save_sketch("A", _png(101))
    real_unlink = Path.unlink
    blocked = {"on": True}

    def _deny(self, *a, **k):
        if blocked["on"] and self.suffix == ".png":
            raise PermissionError("locked")
        return real_unlink(self, *a, **k)

    monkeypatch.setattr(Path, "unlink", _deny)
    pool.save_sketch("A", _png(102))                              # sha0 정리(파일 삭제 실패 → trash)
    assert f"{sha0}.png" in _trash(tmp_path)
    blocked["on"] = False
    assert pool.save_sketch("B", data0) == sha0                   # 같은 이미지를 다시 저장
    import sqlite3
    conn = sqlite3.connect(tmp_path / "pool.db")
    assert conn.execute("select count(*) from pool where sha=?", (sha0,)).fetchone()[0] == 1   # 풀 행 복원
    assert (tmp_path / "pool" / f"{sha0}.png").read_bytes() == data0                          # 파일 유지
    assert f"{sha0}.png" not in [r[0] for r in conn.execute("select name from pool_trash").fetchall()]


# ── Codex 4차 검수 반영(재저장 항목은 같은 호출의 보존 정리에서 제외) ────────────────

def _assert_no_orphans(tmp_path):
    """풀 디렉터리의 모든 PNG는 풀 행이 참조하거나 삭제 대기(pool_trash)에 있어야 한다."""
    import sqlite3
    conn = sqlite3.connect(tmp_path / "pool.db")
    rows = {r[0] for r in conn.execute("select path from pool").fetchall()}
    trash = {r[0] for r in conn.execute("select name from pool_trash").fetchall()}
    files = {p.name for p in (tmp_path / "pool").glob("*.png")}
    assert files <= rows | trash, files - rows - trash          # 고아 파일 0
    assert rows <= files, rows - files                          # 행은 항상 파일이 있다


def test_resaved_sha_is_protected_from_prune_in_same_call(env, monkeypatch, tmp_path):
    monkeypatch.setenv("IMAGE_POOL_MAX_ITEMS", "1")
    x = _png(110)
    sx = pool.save_sketch("A", x)
    sy = pool.save_sketch("A", _png(111))                        # X 정리, Y 유지
    assert sy and _db_counts(tmp_path)[0] == 1
    assert pool.save_sketch("B", x) == sx                        # X 다시 저장: X는 남고 오래된 Y가 정리된다
    import sqlite3
    conn = sqlite3.connect(tmp_path / "pool.db")
    assert [r[0] for r in conn.execute("select sha from pool").fetchall()] == [sx]
    assert (tmp_path / "pool" / f"{sx}.png").read_bytes() == x
    _assert_no_orphans(tmp_path)


def test_trash_item_resaved_at_prune_boundary_leaves_no_orphan(env, monkeypatch, tmp_path):
    from pathlib import Path
    monkeypatch.setenv("IMAGE_POOL_MAX_ITEMS", "2")
    a, b = _png(120), _png(121)
    sa = pool.save_sketch("A", a)
    pool.save_sketch("A", b)
    real_unlink = Path.unlink
    blocked = {"on": True}

    def _deny(self, *args, **kw):
        if blocked["on"] and self.suffix == ".png":
            raise PermissionError("locked")
        return real_unlink(self, *args, **kw)

    monkeypatch.setattr(Path, "unlink", _deny)
    pool.save_sketch("A", _png(122))                             # sa 정리, 파일 삭제 실패 → trash
    assert f"{sa}.png" in _trash(tmp_path)
    assert pool.save_sketch("B", a) == sa                        # trash 항목을 다시 저장(한도 경계, 같은 호출 prune 발생)
    blocked["on"] = False
    pool.save_sketch("A", _png(123))                             # 이후 저장으로 trash 재시도
    _assert_no_orphans(tmp_path)
    assert _db_counts(tmp_path)[0] == 2


def test_protect_works_even_when_timestamps_tie(env, monkeypatch, tmp_path):
    """created_at이 모두 같아도(초 단위 동시 저장) 방금 다시 저장한 항목이 같은 호출의 정리 대상이 되지 않는다."""
    monkeypatch.setattr(pool, "_now", lambda: "2026-11-02T00:00:00+00:00")
    monkeypatch.setenv("IMAGE_POOL_MAX_ITEMS", "3")
    x = _png(130)
    sx = pool.save_sketch("A", x)                                # rowid 가장 작은 항목
    pool.save_sketch("A", _png(131))
    pool.save_sketch("A", _png(132))
    monkeypatch.setenv("IMAGE_POOL_MAX_ITEMS", "2")              # 한도를 낮춘 뒤 가장 오래된 X를 다시 저장
    assert pool.save_sketch("B", x) == sx
    import sqlite3
    shas = {r[0] for r in sqlite3.connect(tmp_path / "pool.db").execute("select sha from pool").fetchall()}
    assert sx in shas and len(shas) == 2
    assert (tmp_path / "pool" / f"{sx}.png").read_bytes() == x
    _assert_no_orphans(tmp_path)