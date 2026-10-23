"""tests/test_aijomoojin_carousel_publish.py — 261023 STEP 4-AG AIJOMOOJIN 2~4장 CAROUSEL 게시.

A. publish_carousel(): Meta 계약 순서(자식 → 자식 FINISHED → 부모 → 원장 기록 → 부모 FINISHED → 발행 1회),
   자식 실패·원장 기록 실패 시 발행 0회, 모호한 발행 결과는 outcome_unknown(재시도 0회).
B. _resolve_aijomoojin_slot_package(): 게시 직전 Vault 재조회 — v2만 single, v3 정상만 carousel, 나머지 HOLD.
C. 슬롯 게시 통합: carousel이면 publish_carousel·in_flight 원장·정리, HOLD면 claim·게시 0회.
D. 원장: in_flight도 reconcile 대상, 저장은 tmp → os.replace.
실제 Meta·imgbb·Airtable 호출 없음(requests는 Fake, Vault는 tmp_path).
"""

import json

import pytest
import requests

import modules.infra.airtable_repository  # noqa: F401
import launcher.main  # noqa: F401

import modules.sns.content_package_builder as cpb
from launcher import main as lm

URLS = ["https://i.ibb.co/s1.jpg", "https://i.ibb.co/s2.jpg", "https://i.ibb.co/s3.jpg"]


# ── A. publish_carousel ─────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status=200, data=None):
        self.status_code, self._data = status, data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


class _FakeGraph:
    """POST /media(자식·부모), GET /{id}(status_code), POST /media_publish 를 기록한다."""

    def __init__(self, *, fail_child=None, child_status="FINISHED", publish=None):
        self.posts, self.gets, self.publish_calls = [], [], 0
        self.fail_child, self.child_status, self.publish = fail_child, child_status, publish
        self._n = 0

    def post(self, url, params=None, timeout=None):
        params = dict(params or {})
        if url.endswith("/media_publish"):
            self.publish_calls += 1
            self.posts.append(("publish", params.get("creation_id")))
            if self.publish:
                return self.publish()
            return _Resp(200, {"id": "IGMEDIA1"})
        if params.get("media_type") == "CAROUSEL":
            self.posts.append(("parent", params.get("children"), params.get("caption")))
            return _Resp(200, {"id": "PARENT1"})
        self._n += 1
        idx = URLS.index(params["image_url"]) + 1 if params.get("image_url") in URLS else self._n
        self.posts.append(("child", params.get("image_url"), params.get("is_carousel_item"), "caption" in params))
        if self.fail_child == idx:
            return _Resp(500, {})
        return _Resp(200, {"id": f"CHILD{idx}"})

    def get(self, url, params=None, timeout=None):
        cid = url.rsplit("/", 1)[1]
        self.gets.append(cid)
        status = self.child_status if cid.startswith("CHILD") else "FINISHED"
        return _Resp(200, {"status_code": status})


@pytest.fixture
def graph(monkeypatch):
    def _make(**kw):
        g = _FakeGraph(**kw)
        monkeypatch.setattr(requests, "post", g.post)
        monkeypatch.setattr(requests, "get", g.get)
        monkeypatch.setattr("time.sleep", lambda s: None)
        return g
    return _make


class TestPublishCarousel:
    def test_meta_contract_order_and_single_publish(self, graph):
        g = graph()
        recorded = []
        out = lm.publish_carousel("rec1", URLS, "캡션\n#AI", "tok", "IGU", api_host="graph.instagram.com",
                                  on_parent_created=lambda pid: recorded.append((pid, g.publish_calls)) or True)
        assert out == {"ok": True, "ig_media_id": "IGMEDIA1", "creation_id": "PARENT1"}
        assert [p for p in g.posts if p[0] == "child"] == [
            ("child", URLS[0], "true", False), ("child", URLS[1], "true", False), ("child", URLS[2], "true", False)]
        assert ("parent", "CHILD1,CHILD2,CHILD3", "캡션\n#AI") in g.posts
        assert g.posts[-1] == ("publish", "PARENT1") and g.publish_calls == 1
        assert recorded == [("PARENT1", 0)]                    # 원장 기록은 발행 전
        assert g.gets[:3] == ["CHILD1", "CHILD2", "CHILD3"] and g.gets[-1] == "PARENT1"

    @pytest.mark.parametrize("urls", [URLS[:1], URLS + ["https://i.ibb.co/4.jpg", "https://i.ibb.co/5.jpg"],
                                      [URLS[0], URLS[0]], ["http://i.ibb.co/s1.jpg", URLS[1]], []])
    def test_invalid_item_list_makes_no_request(self, graph, urls):
        g = graph()
        assert lm.publish_carousel("rec1", urls, "c", "tok", "IGU")["error"] == "carousel_items_invalid"
        assert g.posts == [] and g.gets == []

    def test_child_create_failure_no_parent_no_publish(self, graph):
        g = graph(fail_child=2)
        out = lm.publish_carousel("rec1", URLS, "c", "tok", "IGU", on_parent_created=lambda pid: pytest.fail("부모 없음"))
        assert out == {"ok": False, "error": "child_create_failed_2"}
        assert not any(p[0] in ("parent", "publish") for p in g.posts)

    def test_child_container_error_no_parent(self, graph):
        g = graph(child_status="ERROR")
        out = lm.publish_carousel("rec1", URLS, "c", "tok", "IGU")
        assert out["ok"] is False and out["error"].startswith("child1_container_error")
        assert not any(p[0] in ("parent", "publish") for p in g.posts)

    def test_ledger_write_failure_blocks_publish(self, graph):
        g = graph()
        out = lm.publish_carousel("rec1", URLS, "c", "tok", "IGU", on_parent_created=lambda pid: False)
        assert out == {"ok": False, "error": "ledger_write_failed", "creation_id": "PARENT1"}
        assert g.publish_calls == 0

    def test_ledger_exception_blocks_publish(self, graph):
        g = graph()

        def _boom(pid):
            raise OSError("locked")
        assert lm.publish_carousel("rec1", URLS, "c", "tok", "IGU", on_parent_created=_boom)["error"] == "ledger_write_failed"
        assert g.publish_calls == 0

    def test_ambiguous_publish_is_outcome_unknown_without_retry(self, graph):
        def _timeout():
            raise requests.exceptions.ReadTimeout("read timed out")
        g = graph(publish=_timeout)
        out = lm.publish_carousel("rec1", URLS, "c", "tok", "IGU", on_parent_created=lambda pid: True)
        assert out["outcome_unknown"] is True and out["creation_id"] == "PARENT1"
        assert g.publish_calls == 1

    @pytest.mark.parametrize("n", [2, 4])
    def test_two_and_four_items(self, graph, n):
        urls = [f"https://i.ibb.co/x{i}.jpg" for i in range(n)]
        g = graph()
        assert lm.publish_carousel("rec1", urls, "c", "tok", "IGU", on_parent_created=lambda pid: True)["ok"] is True
        assert len([p for p in g.posts if p[0] == "child"]) == n


# ── B. 게시 직전 Vault 재조회 ────────────────────────────────────────────────

@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(cpb, "DEFAULT_VAULT_ROOT", tmp_path)
    (tmp_path / "content").mkdir()
    return tmp_path


def _write(vault, cid, fields):
    md_path, _ = cpb._content_paths(cid, vault)
    md_path.write_text(cpb._render_frontmatter(fields) + "\nc\n", encoding="utf-8")


def _v3(cid, n=3, **over):
    f = {"content_id": cid, "caption": "캡션", "hashtags": "#AI #자동화", "idempotency_version": 3,
         "post_format": "carousel", "carousel_required": True, "slide_count": n,
         "slide_texts": [f"s{i}" for i in range(n)], "slide_image_paths": cpb.carousel_slide_image_paths(cid, n),
         "carousel_image_urls": URLS[:n] if n <= 3 else URLS + ["https://i.ibb.co/s4.jpg"]}
    f.update(over)
    return f


def _slot_post(cid="cv3", image_url=URLS[0], caption="캡션", hashtag="#AI #자동화"):
    return {"post_id": "rec1", "image_url": image_url, "caption": caption, "hashtag": hashtag,
            "account_code_ref": "IDN-000036", "ig_media_id": "", "data_classification": "production",
            "canary_run_id": "", "post_status": "ready", "content_id": cid}


class TestResolveSlotPackage:
    def test_v2_is_legacy_single(self, vault):
        _write(vault, "cv2", {"content_id": "cv2", "caption": "c", "idempotency_version": 2})
        assert lm._resolve_aijomoojin_slot_package(_slot_post("cv2")) == ("legacy_single", None)

    def test_v3_is_carousel_with_ordered_urls(self, vault):
        _write(vault, "cv3", _v3("cv3"))
        assert lm._resolve_aijomoojin_slot_package(_slot_post()) == ("carousel", URLS)

    @pytest.mark.parametrize("post_over, fields_over, reason", [
        ({"content_id": ""}, {}, "CONTENT_ID_MISSING"),
        ({"content_id": "nope"}, {}, "VAULT_READ_FAILED"),
        ({}, {"carousel_image_urls": []}, "CAROUSEL_URLS_MISSING"),
        ({}, {"carousel_image_urls": [URLS[0], URLS[0], URLS[2]]}, "CAROUSEL_URLS_INVALID"),
        ({"image_url": URLS[1]}, {}, "COVER_URL_MISMATCH"),
        ({}, {"carousel_image_urls": [URLS[1], URLS[0], URLS[2]]}, "COVER_URL_MISMATCH"),
        ({"caption": "다른 캡션"}, {}, "CAPTION_MISMATCH"),
        ({"hashtag": "#다름"}, {}, "CAPTION_MISMATCH"),
        ({}, {"post_format": "single"}, "V3_POST_FORMAT_INVALID"),
        ({}, {"carousel_required": False}, "V3_CAROUSEL_REQUIRED_INVALID"),
        ({}, {"idempotency_version": 4}, "VERSION_UNSUPPORTED_4"),
    ])
    def test_hold_cases(self, vault, post_over, fields_over, reason):
        _write(vault, "cv3", _v3("cv3", **fields_over))
        post = _slot_post(**{k: v for k, v in post_over.items() if k != "content_id"})
        if "content_id" in post_over:
            post["content_id"] = post_over["content_id"]
        assert lm._resolve_aijomoojin_slot_package(post) == ("hold", reason)

    def test_unmarked_package_is_hold(self, vault):
        _write(vault, "cold", {"content_id": "cold", "caption": "c"})
        assert lm._resolve_aijomoojin_slot_package(_slot_post("cold")) == ("hold", "VERSION_MISSING_OR_INVALID")


# ── C. 슬롯 게시 통합 ─────────────────────────────────────────────────────────

AI_ACCOUNT = {"account_code": "IDN-000036", "api_provider": "instagram_login", "ig_user_id": "17841467725643424",
              "credential_key": "AI", "automation_enabled": True}


@pytest.fixture
def slot_env(monkeypatch, vault, tmp_path):
    import modules.common.canary_classification as cc

    monkeypatch.setenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "true")
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "false")
    monkeypatch.setenv("AIJOMOOJIN_BINDING_ADAPTER_ENABLED", "false")
    monkeypatch.setenv("AI_INSTA_IG_USER_ID", "17841467725643424")
    monkeypatch.setenv("AI_INSTA_ACCESS_TOKEN", "ai-test-token")
    monkeypatch.setattr(cc, "validate_publication_candidate", lambda *a, **k: None)
    monkeypatch.setattr(lm, "_PUBLISH_PENDING_PATH", tmp_path / "pending.json")
    slack = []
    monkeypatch.setattr(lm, "_slack", lambda msg: slack.append(msg))
    monkeypatch.setattr(lm, "fetch_media_summary", lambda *a, **k: {"media_type": "CAROUSEL_ALBUM", "children": 3})
    calls = {"claim": [], "mark": [], "ledger_at_publish": None}

    class _Repo:
        def __init__(self, posts):
            self.posts = posts

        def fetch_pending_posts_for_account(self, code, limit=10):
            return self.posts

        def get_publish_account(self, code):
            return AI_ACCOUNT

        def claim_post_for_upload(self, pid):
            calls["claim"].append(pid)
            return True

        def mark_post_result(self, pid, result):
            calls["mark"].append((pid, dict(result)))

    def _run(posts):
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: _Repo(posts))
        lm._job_aijomoojin_scheduled_post()

    return calls, slack, _run, tmp_path / "pending.json"


class TestSlotCarouselIntegration:
    def test_carousel_published_with_in_flight_then_cleared(self, monkeypatch, slot_env, vault):
        calls, slack, run, pending = slot_env
        _write(vault, "cv3", _v3("cv3"))
        seen = {}

        def _fake_carousel(rid, urls, caption, token, ig_user_id, api_host="", *, on_parent_created=None):
            assert on_parent_created("PARENT1") is True
            seen["ledger"] = json.loads(pending.read_text(encoding="utf-8"))
            seen["args"] = (rid, urls, caption, api_host)
            return {"ok": True, "ig_media_id": "IGM1", "creation_id": "PARENT1"}
        monkeypatch.setattr(lm, "publish_carousel", _fake_carousel)
        monkeypatch.setattr(lm, "publish_single", lambda *a, **k: pytest.fail("single 게시 금지"))

        run([_slot_post()])

        assert seen["args"] == ("rec1", URLS, "캡션\n#AI #자동화", "graph.instagram.com")
        assert seen["ledger"]["rec1"]["kind"] == "in_flight" and seen["ledger"]["rec1"]["creation_id"] == "PARENT1"
        assert calls["claim"] == ["rec1"] and calls["mark"][0][1]["status"] == "posted"
        assert json.loads(pending.read_text(encoding="utf-8")) == {}       # 확정 후 정리
        assert slack == []

    def test_outcome_unknown_keeps_ledger_and_no_retry(self, monkeypatch, slot_env, vault):
        calls, slack, run, pending = slot_env
        _write(vault, "cv3", _v3("cv3"))
        n = {"calls": 0}

        def _fake_carousel(rid, urls, caption, token, ig_user_id, api_host="", *, on_parent_created=None):
            n["calls"] += 1
            on_parent_created("PARENT1")
            return {"ok": False, "error": "outcome_unknown", "outcome_unknown": True, "creation_id": "PARENT1"}
        monkeypatch.setattr(lm, "publish_carousel", _fake_carousel)

        run([_slot_post()])

        assert n["calls"] == 1 and calls["mark"] == []                     # uploading 유지
        entry = json.loads(pending.read_text(encoding="utf-8"))["rec1"]
        assert entry["kind"] == "outcome_unknown" and entry["creation_id"] == "PARENT1"
        assert len(slack) == 1

    @pytest.mark.parametrize("fields_over", [{"post_format": "single"}, {"carousel_image_urls": []},
                                             {"idempotency_version": 7}])
    def test_hold_means_no_claim_no_publish(self, monkeypatch, slot_env, vault, fields_over):
        calls, slack, run, _ = slot_env
        _write(vault, "cv3", _v3("cv3", **fields_over))
        monkeypatch.setattr(lm, "publish_carousel", lambda *a, **k: pytest.fail("게시 금지"))
        monkeypatch.setattr(lm, "publish_single", lambda *a, **k: pytest.fail("single 폴백 금지"))

        run([_slot_post()])

        assert calls["claim"] == [] and calls["mark"] == []
        assert len(slack) == 1 and slack[0].startswith("[HOLD]")

    def test_v2_package_still_uses_publish_single(self, monkeypatch, slot_env, vault):
        calls, _, run, _ = slot_env
        _write(vault, "cv2", {"content_id": "cv2", "caption": "c", "idempotency_version": 2})
        used = []
        monkeypatch.setattr(lm, "publish_single", lambda *a, **k: used.append(a[1]) or {"ok": True, "ig_media_id": "m"})
        monkeypatch.setattr(lm, "publish_carousel", lambda *a, **k: pytest.fail("carousel 금지"))

        run([_slot_post("cv2", image_url="https://i.ibb.co/single.jpg")])

        assert used == ["https://i.ibb.co/single.jpg"] and calls["mark"][0][1]["status"] == "posted"


# ── D. 원장 ───────────────────────────────────────────────────────────────────

class TestLedger:
    def test_in_flight_is_reconciled_like_outcome_unknown(self, monkeypatch):
        import modules.common.credential_resolver as cr

        monkeypatch.setattr(cr, "resolve_credential", lambda key: type("C", (), {"access_token": "t"})())
        monkeypatch.setattr(requests, "get", lambda url, params=None, timeout=None: _Resp(200, {"status_code": "EXPIRED"}))
        decision, _, reason = lm._reconcile_decide({"kind": "in_flight", "creation_id": "PARENT1",
                                                    "credential_key": "AI", "api_host": "graph.instagram.com"})
        assert (decision, reason) == ("failed", "container_EXPIRED")

    def test_in_flight_without_creation_id_is_hold(self):
        assert lm._reconcile_decide({"kind": "in_flight", "creation_id": ""})[0] == "hold"

    def test_save_is_atomic_and_leaves_no_tmp(self, monkeypatch, tmp_path):
        path = tmp_path / "pending.json"
        monkeypatch.setattr(lm, "_PUBLISH_PENDING_PATH", path)
        assert lm._record_publish_pending("r1", "in_flight", creation_id="P1") is True
        assert json.loads(path.read_text(encoding="utf-8"))["r1"]["kind"] == "in_flight"
        assert not list(tmp_path.glob("*.tmp"))

    def test_save_failure_returns_false_and_keeps_old_file(self, monkeypatch, tmp_path):
        path = tmp_path / "pending.json"
        path.write_text(json.dumps({"old": {"kind": "outcome_unknown"}}), encoding="utf-8")
        monkeypatch.setattr(lm, "_PUBLISH_PENDING_PATH", path)

        def _deny(src, dst):
            raise PermissionError("locked by another process")
        monkeypatch.setattr(lm.os, "replace", _deny)
        assert lm._record_publish_pending("r1", "in_flight", creation_id="P1") is False
        assert json.loads(path.read_text(encoding="utf-8")) == {"old": {"kind": "outcome_unknown"}}
        assert not list(tmp_path.glob("*.tmp"))


# ── E. 4-AG 전문 대조 보완 — 부모 실패·중복·오계정·조회 계약 ─────────────────

class TestPublishCarouselParentFailure:
    def test_parent_create_failure_no_ledger_no_publish(self, graph, monkeypatch):
        g = graph()
        real_post = g.post

        def _post(url, params=None, timeout=None):
            if (params or {}).get("media_type") == "CAROUSEL":
                g.posts.append(("parent_fail",))
                return _Resp(500, {})
            return real_post(url, params=params, timeout=timeout)
        monkeypatch.setattr(requests, "post", _post)
        out = lm.publish_carousel("rec1", URLS, "c", "tok", "IGU",
                                  on_parent_created=lambda pid: pytest.fail("부모 없음 - 기록 금지"))
        assert out == {"ok": False, "error": "parent_create_failed"}
        assert g.publish_calls == 0

    def test_parent_container_not_finished_no_publish(self, graph, monkeypatch):
        g = graph()

        def _get(url, params=None, timeout=None):
            cid = url.rsplit("/", 1)[1]
            return _Resp(200, {"status_code": "ERROR" if cid == "PARENT1" else "FINISHED"})
        monkeypatch.setattr(requests, "get", _get)
        out = lm.publish_carousel("rec1", URLS, "c", "tok", "IGU", on_parent_created=lambda pid: True)
        assert out["ok"] is False and out["error"] == "container_error" and g.publish_calls == 0


class TestSlotCarouselGuards:
    def test_claim_failure_means_no_publish(self, monkeypatch, slot_env, vault):
        calls, _, _, _ = slot_env
        _write(vault, "cv3", _v3("cv3"))
        monkeypatch.setattr(lm, "publish_carousel", lambda *a, **k: pytest.fail("중복 게시 금지"))

        class _Repo:
            def fetch_pending_posts_for_account(self, code, limit=10):
                return [_slot_post()]

            def get_publish_account(self, code):
                return AI_ACCOUNT

            def claim_post_for_upload(self, pid):
                return False

            def mark_post_result(self, pid, result):
                pytest.fail("상태 기록 금지")
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: _Repo())
        lm._job_aijomoojin_scheduled_post()

    def test_existing_ig_media_id_means_no_publish(self, monkeypatch, slot_env, vault):
        calls, _, run, _ = slot_env
        _write(vault, "cv3", _v3("cv3"))
        monkeypatch.setattr(lm, "publish_carousel", lambda *a, **k: pytest.fail("재게시 금지"))
        post = _slot_post()
        post["ig_media_id"] = "ALREADY"
        run([post])
        assert calls["claim"] == []

    def test_wrong_account_credential_means_no_publish(self, monkeypatch, slot_env, vault):
        calls, _, run, _ = slot_env
        _write(vault, "cv3", _v3("cv3"))
        monkeypatch.setenv("AI_INSTA_IG_USER_ID", "99999999999")
        monkeypatch.setattr(lm, "publish_carousel", lambda *a, **k: pytest.fail("오계정 게시 금지"))
        run([_slot_post()])
        assert calls["claim"] == []


class TestMediaSummaryContract:
    def test_reads_account_media_type_children_permalink(self, monkeypatch):
        seen = {}

        def _get(url, params=None, timeout=None):
            seen["url"], seen["fields"] = url, params["fields"]
            return _Resp(200, {"id": "IGM1", "media_type": "CAROUSEL_ALBUM", "username": "aijomoojin",
                               "permalink": "https://www.instagram.com/p/XYZ/", "owner": {"id": "17841467725643424"},
                               "children": {"data": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}})
        monkeypatch.setattr(requests, "get", _get)
        out = lm.fetch_media_summary("IGM1", "tok", "graph.instagram.com")
        assert seen["url"] == "https://graph.instagram.com/v21.0/IGM1"
        assert {"permalink", "owner{id}", "children{id}", "media_type"} <= set(seen["fields"].split(","))
        assert out == {"id": "IGM1", "media_type": "CAROUSEL_ALBUM", "permalink": "https://www.instagram.com/p/XYZ/",
                       "username": "aijomoojin", "owner_id": "17841467725643424", "children": 3}

    def test_lookup_failure_returns_empty_without_raising(self, monkeypatch):
        def _boom(*a, **k):
            raise requests.exceptions.ConnectionError("down")
        monkeypatch.setattr(requests, "get", _boom)
        assert lm.fetch_media_summary("IGM1", "tok") == {}


# ── F. 원장 동시 갱신(lost update) 방지 ─────────────────────────────────────

import subprocess
import sys
import threading
import time


@pytest.fixture
def ledger(monkeypatch, tmp_path):
    path = tmp_path / "pending.json"
    monkeypatch.setattr(lm, "_PUBLISH_PENDING_PATH", path)
    return path


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class TestLedgerConcurrency:
    def test_reconcile_does_not_delete_entry_rerecorded_during_decision(self, monkeypatch, ledger):
        """reconcile이 오래된 snapshot으로 판정하는 사이 슬롯이 같은 rid를 in_flight로 다시 쓰고,
        다른 rid도 새로 쓴다 → reconcile 저장 후에도 두 새 기록이 남아야 한다."""
        lm._record_publish_pending("recA", "outcome_unknown", creation_id="OLD")
        old = _read(ledger)
        old["recA"]["at"] = "2000-01-01 00:00:00"                          # 30분 경과 조건 충족
        ledger.write_text(json.dumps(old), encoding="utf-8")

        def _decide(entry):
            lm._record_publish_pending("recA", "in_flight", creation_id="NEW")   # 판정 중 슬롯이 재기록
            lm._record_publish_pending("recB", "in_flight", creation_id="B1")
            return "failed", "", "container_EXPIRED"
        monkeypatch.setattr(lm, "_reconcile_decide", _decide)
        monkeypatch.setattr(lm, "_fetch_post_state", lambda rid: ("uploading", ""))
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository",
                            lambda: type("R", (), {"mark_post_result": lambda self, *a: None})())
        monkeypatch.setattr(lm, "_slack", lambda msg: None)

        lm._job_publish_reconcile()

        data = _read(ledger)
        assert data["recA"]["kind"] == "in_flight" and data["recA"]["creation_id"] == "NEW"
        assert data["recB"]["creation_id"] == "B1"

    def test_reconcile_still_removes_unchanged_resolved_entry(self, monkeypatch, ledger):
        lm._record_publish_pending("recA", "outcome_unknown", creation_id="OLD")
        old = _read(ledger)
        old["recA"]["at"] = "2000-01-01 00:00:00"
        ledger.write_text(json.dumps(old), encoding="utf-8")
        monkeypatch.setattr(lm, "_reconcile_decide", lambda entry: ("failed", "", "container_EXPIRED"))
        monkeypatch.setattr(lm, "_fetch_post_state", lambda rid: ("uploading", ""))
        monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository",
                            lambda: type("R", (), {"mark_post_result": lambda self, *a: None})())
        lm._job_publish_reconcile()
        assert _read(ledger) == {}

    def test_parallel_threads_keep_every_record(self, ledger):
        errors = []

        def _worker(i):
            if not lm._record_publish_pending(f"rec{i}", "in_flight", creation_id=f"P{i}"):
                errors.append(i)
        threads = [threading.Thread(target=_worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == [] and sorted(_read(ledger)) == sorted(f"rec{i}" for i in range(20))
        assert not list(ledger.parent.glob("*.tmp"))

    def test_other_process_holding_lock_blocks_until_released(self, ledger):
        lock_db = ledger.with_name(ledger.name + ".lock.db")
        holder = subprocess.Popen([sys.executable, "-c", (
            "import sqlite3,sys,time;c=sqlite3.connect(sys.argv[1],isolation_level=None);"
            "c.execute('BEGIN IMMEDIATE');print('locked',flush=True);time.sleep(1.5);c.execute('COMMIT')"),
            str(lock_db)], stdout=subprocess.PIPE, text=True)
        assert holder.stdout.readline().strip() == "locked"
        started = time.monotonic()
        assert lm._record_publish_pending("recX", "in_flight", creation_id="PX") is True
        waited = time.monotonic() - started
        holder.wait(timeout=10)
        assert waited >= 0.8                                               # 다른 프로세스가 풀 때까지 대기
        assert _read(ledger)["recX"]["creation_id"] == "PX"

    def test_lock_timeout_returns_false_and_keeps_file(self, monkeypatch, ledger):
        lm._record_publish_pending("keep", "outcome_unknown", creation_id="K")
        monkeypatch.setattr(lm, "_PUBLISH_PENDING_LOCK_TIMEOUT_SEC", 0.3)
        lock_db = ledger.with_name(ledger.name + ".lock.db")
        holder = subprocess.Popen([sys.executable, "-c", (
            "import sqlite3,sys,time;c=sqlite3.connect(sys.argv[1],isolation_level=None);"
            "c.execute('BEGIN IMMEDIATE');print('locked',flush=True);time.sleep(2);c.execute('COMMIT')"),
            str(lock_db)], stdout=subprocess.PIPE, text=True)
        assert holder.stdout.readline().strip() == "locked"
        assert lm._record_publish_pending("recY", "in_flight", creation_id="PY") is False
        holder.wait(timeout=10)
        assert list(_read(ledger)) == ["keep"]

    def test_unique_tmp_names_per_save(self, monkeypatch, ledger):
        names = []
        real_replace = lm.os.replace

        def _spy(src, dst):
            names.append(str(src))
            return real_replace(src, dst)
        monkeypatch.setattr(lm.os, "replace", _spy)
        lm._record_publish_pending("r1", "in_flight", creation_id="P1")
        lm._record_publish_pending("r2", "in_flight", creation_id="P2")
        assert len(names) == 2 and names[0] != names[1]
        assert all(n.endswith(".tmp") and n != str(ledger) + ".tmp" for n in names)

    def test_corrupt_ledger_is_not_overwritten(self, ledger):
        ledger.write_text("{not json", encoding="utf-8")
        assert lm._record_publish_pending("r1", "in_flight", creation_id="P1") is False
        assert ledger.read_text(encoding="utf-8") == "{not json"

    def test_clear_only_removes_target(self, ledger):
        lm._record_publish_pending("r1", "in_flight", creation_id="P1")
        lm._record_publish_pending("r2", "in_flight", creation_id="P2")
        lm._clear_publish_pending("r1")
        assert list(_read(ledger)) == ["r2"]
