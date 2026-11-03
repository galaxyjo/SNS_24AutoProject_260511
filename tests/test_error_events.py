"""modules/common/error_events.py 단위 테스트 — 모든 DB 는 tmp_path, 네트워크·운영 경로 접근 없음."""

from datetime import datetime, timedelta

import pytest

from modules.common import error_events as ee

NOW = datetime(2026, 11, 3, 20, 0, 0)
SECRET = "EAABsecretTOKEN123456789"


def _rec(*args, **kwargs):
    """알림을 동기로 보내 결과를 결정적으로 확인한다(운영 기본은 별도 스레드)."""
    kwargs.setdefault("notify_async", False)
    return ee.record_publish_failure(*args, **kwargs)



def _http_failure(code, subcode=None, http=400, message="Boom"):
    sub = f", subcode={subcode}" if subcode is not None else ""
    return {
        "ok": False,
        "error": (f"{http} Client Error: Bad Request for url: https://graph.facebook.com/v21.0/178/media"
                  f"?image_url=https%3A%2F%2Fi.ibb.co%2Fx.jpg&caption=hello&access_token={SECRET}"),
        "detail": f" | meta_error=(message={message}, type=OAuthException, code={code}{sub}, fbtrace_id=abc)",
    }


@pytest.mark.parametrize("http,code,subcode,expected", [
    (400, 190, None, ee.META_AUTH), (400, 102, None, ee.META_AUTH),
    (400, 190, 458, ee.META_AUTH), (400, 190, 459, ee.META_AUTH), (400, 190, 460, ee.META_AUTH),
    (400, 190, 463, ee.META_AUTH), (400, 190, 467, ee.META_AUTH), (400, 100, 463, ee.META_AUTH),
    (400, 459, None, ee.META_UNCLASSIFIED),          # 459 등은 최상위 code 가 아니라 190 의 subcode 로 온다(Codex 리뷰)
    (400, 80004, None, ee.META_UNCLASSIFIED), (400, 80006, None, ee.META_UNCLASSIFIED),   # Ads·Messenger 맥락, 분류표 제외
    (400, 10, None, ee.META_PERMISSION), (400, 200, None, ee.META_PERMISSION), (400, 299, None, ee.META_PERMISSION),
    (400, 300, None, ee.META_UNCLASSIFIED),
    (400, 368, None, ee.META_POLICY_BLOCK), (400, 100, 2207050, ee.META_POLICY_BLOCK),
    (400, 4, None, ee.META_RATE_LIMIT), (400, 613, None, ee.META_RATE_LIMIT), (429, None, None, ee.META_RATE_LIMIT),
    (400, 9004, 2207052, ee.META_MEDIA_FETCH), (400, 9004, None, ee.META_MEDIA_FETCH),
    (400, 1, None, ee.META_TRANSIENT), (500, None, None, ee.META_TRANSIENT), (503, 190, None, ee.META_AUTH),
    (400, 999999, None, ee.META_UNCLASSIFIED), (None, None, None, ee.META_UNCLASSIFIED),
])
def test_classification_table(http, code, subcode, expected):
    assert ee.classify_meta_error(http, code, subcode) == expected


def test_subcode_takes_precedence_over_code():
    assert ee.classify_meta_error(400, 190, 2207050) == ee.META_POLICY_BLOCK
    assert ee.classify_meta_error(400, 100, 2207052) == ee.META_MEDIA_FETCH


def test_parse_real_looking_failure():
    parsed = ee.parse_publish_failure(_http_failure(9004, 2207052))
    assert parsed == {"error_class": ee.META_MEDIA_FETCH, "http": 400, "code": 9004, "subcode": 2207052}


@pytest.mark.parametrize("raw,expected", [
    ({"ok": False, "error": "outcome_unknown", "outcome_unknown": True}, ee.META_OUTCOME_UNKNOWN),
    ({"ok": False, "error": "container_error", "creation_id": "1"}, ee.META_CONTAINER),
    ({"ok": False, "error": "container_finished_timeout"}, ee.META_CONTAINER),
    ({"ok": False, "error": "child2_container_error"}, ee.META_CONTAINER),
    ({"ok": False, "error": "parent_create_failed"}, ee.META_CONTAINER),
    ({"ok": False, "error": "image_url_missing"}, ee.PUBLISH_INTERNAL),
    ({"ok": False, "error": "ledger_write_failed"}, ee.PUBLISH_INTERNAL),
    ({"ok": False, "error": "HTTPSConnectionPool: Read timed out. (read timeout=30)"}, ee.META_TRANSIENT),
    ({"ok": False, "error": "ConnectionError: reset"}, ee.META_TRANSIENT),
    ({}, ee.PUBLISH_INTERNAL),
])
def test_parse_non_http_failures(raw, expected):
    assert ee.parse_publish_failure(raw)["error_class"] == expected


def _rows(db):
    import sqlite3
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute("SELECT account, error_class, severity, http, code, subcode, stage, record_id, "
                            "detail_head FROM events ORDER BY id").fetchall()
    finally:
        conn.close()


def test_record_stores_structured_fields_and_no_secrets(tmp_path):
    db = tmp_path / "ev.db"
    cls = _rec(_http_failure(190, None, message="Session expired"), account_code="IDN-000007",
                                    record_id="recX", stage="poller_publish", db_path=db, now=NOW)
    assert cls == ee.META_AUTH
    (row,) = _rows(db)
    assert row[:8] == ("IDN-000007", ee.META_AUTH, "P1", 400, 190, None, "poller_publish", "recX")
    head = row[8]
    assert SECRET not in head and "access_token=" not in head and "caption=hello" not in head
    assert "<params>" in head and len(head) <= 200


def test_auth_alert_once_per_account_per_day(tmp_path):
    db, msgs = tmp_path / "ev.db", []
    kw = dict(record_id="r", stage="s", notify=msgs.append, db_path=db)
    _rec(_http_failure(190), account_code="IDN-000007", now=NOW, **kw)
    _rec(_http_failure(190, 459), account_code="IDN-000007", now=NOW + timedelta(hours=1), **kw)
    assert len(msgs) == 1 and "IDN-000007" in msgs[0] and "META_AUTH" in msgs[0] and "190" in msgs[0]
    _rec(_http_failure(190), account_code="IDN-000014", now=NOW, **kw)          # 다른 계정
    _rec(_http_failure(190), account_code="IDN-000007", now=NOW + timedelta(days=1), **kw)
    assert len(msgs) == 3
    assert len(_rows(db)) == 4                                                                      # 알림은 줄여도 기록은 전부 남는다
    assert all(SECRET not in m for m in msgs)


def test_non_alert_classes_are_recorded_without_alert(tmp_path):
    db, msgs = tmp_path / "ev.db", []
    for raw in (_http_failure(9004, 2207052), _http_failure(4), {"ok": False, "error": "outcome_unknown",
                                                                 "outcome_unknown": True}):
        _rec(raw, account_code="IDN-000007", record_id="r", stage="s", notify=msgs.append,
                                  db_path=db, now=NOW)
    assert msgs == [] and [r[1] for r in _rows(db)] == [ee.META_MEDIA_FETCH, ee.META_RATE_LIMIT, ee.META_OUTCOME_UNKNOWN]


def test_permission_and_policy_alert(tmp_path):
    msgs = []
    for raw in (_http_failure(10), _http_failure(100, 2207050)):
        _rec(raw, account_code="IDN-000007", record_id="r", stage="s", notify=msgs.append,
                                  db_path=tmp_path / "ev.db", now=NOW)
    assert len(msgs) == 2


def test_recording_never_raises(tmp_path):
    # DB 경로가 디렉터리라 sqlite 가 열 수 없다 → 예외 전파 없이 None
    assert _rec(_http_failure(190), account_code="IDN-000007", record_id="r", stage="s",
                                     db_path=tmp_path) is None


def test_notify_failure_does_not_raise_but_event_is_kept(tmp_path):
    def boom(_msg):
        raise RuntimeError("slack down")

    db = tmp_path / "ev.db"
    assert _rec(_http_failure(190), account_code="IDN-000007", record_id="r", stage="s",
                notify=boom, db_path=db, now=NOW) == ee.META_AUTH            # 알림 실패는 삼키고 분류는 돌려준다
    assert len(_rows(db)) == 1


def test_notify_runs_in_a_separate_thread_by_default(tmp_path):
    """Codex 리뷰: Slack 발송(최대 5초)이 게시 실패 처리 경로를 늦추지 않도록 기본은 별도 스레드."""
    import threading

    done, seen = threading.Event(), {}

    def notify(_msg):
        seen["thread"] = threading.current_thread().name
        done.set()

    ee.record_publish_failure(_http_failure(190), account_code="IDN-000007", record_id="r", stage="s",
                              notify=notify, db_path=tmp_path / "ev.db", now=NOW)      # notify_async 기본값
    assert done.wait(3) and seen["thread"] == "errevt-notify"


def test_event_and_alert_claim_use_one_connection(tmp_path, monkeypatch):
    calls = {"n": 0}
    real = ee._connect

    def counting(path):
        calls["n"] += 1
        return real(path)

    monkeypatch.setattr(ee, "_connect", counting)
    _rec(_http_failure(190), account_code="IDN-000007", record_id="r", stage="s", notify=lambda m: None,
         db_path=tmp_path / "ev.db", now=NOW)
    assert calls["n"] == 1


def test_summarize_groups_and_filters_by_time(tmp_path):
    db = tmp_path / "ev.db"
    for acct, raw, when in (("IDN-000007", _http_failure(190), NOW), ("IDN-000007", _http_failure(190), NOW),
                            ("IDN-000014", _http_failure(9004, 2207052), NOW),
                            ("IDN-000007", _http_failure(190), NOW - timedelta(days=3))):
        _rec(raw, account_code=acct, record_id="r", stage="s", db_path=db, now=when)
    rows = ee.summarize(24, ("account", "class"), db_path=db, now=NOW + timedelta(hours=1))
    assert rows[0][:3] == ("IDN-000007", ee.META_AUTH, 2) and len(rows) == 2
    assert ee.summarize(24 * 7, ("class",), db_path=db, now=NOW + timedelta(hours=1))[0][:2] == (ee.META_AUTH, 3)
    with pytest.raises(ValueError):
        ee.summarize(24, ("password",), db_path=db)


def test_cli_prints_summary_and_rejects_bad_args(tmp_path, monkeypatch, capsys):
    db = tmp_path / "ev.db"
    monkeypatch.setattr(ee, "_DB_PATH", db)
    _rec(_http_failure(190), account_code="IDN-000007", record_id="r", stage="s", db_path=db,
                              now=datetime.now())
    assert ee.main(["--since", "24h", "--by", "account,class"]) == 0
    assert "IDN-000007 | META_AUTH | 1건" in capsys.readouterr().out
    assert ee.main(["--since", "xx"]) == 2 and ee.main(["--by", "token"]) == 2


def test_safe_text_strips_query_and_secrets_and_truncates():
    raw = _http_failure(190)["error"]
    out = ee.safe_text(raw)
    assert SECRET not in out and "access_token=" not in out and "caption=hello" not in out and "image_url=" not in out
    assert out.startswith("400 Client Error") and "<params>" in out
    assert len(ee.safe_text("x" * 500)) == 200 and len(ee.safe_text("x" * 500, limit=50)) == 50
    assert ee.safe_text("", None, "ok") == "ok"


@pytest.mark.parametrize("text", [
    "boom access%5Ftoken=" + SECRET + " tail",                                       # 인코딩된 키 이름
    "https://graph.facebook.com/v21.0/1/media\n?access_token=" + SECRET,            # URL 뒤 줄바꿈에 쿼리
    "https://graph.facebook.com/v21.0/1/media%3Faccess_token%3D" + SECRET,          # 전체 인코딩
    "failed with " + SECRET + " and more",                                           # 키 이름 없는 값만
    "Bearer-less token IGAA" + "x" * 30 + " leaked",
    "key AIza" + "y" * 35 + " end",
])
def test_safe_text_resists_encoding_and_newline_bypasses(text):
    out = ee.safe_text(text)
    assert SECRET not in out and "IGAAxxxx" not in out and "AIzayyyy" not in out
    assert "access_token=" + SECRET not in out


def test_launcher_slack_messages_for_publish_failures_use_safe_text():
    """261103 발견: 게시 실패 Slack 알림이 requests 예외 문자열(access_token 쿼리 포함)을 그대로 보냈다. 3곳 고정."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "launcher" / "main.py").read_text(encoding="utf-8")
    assert "error={raw.get('error','')}" not in src
    assert "{res.get('error','')} | account_ref" not in src
    assert src.count("_error_events.safe_text(") >= 3


def test_launcher_hook_swallows_errors(monkeypatch):
    import launcher.main as lm

    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr("modules.common.error_events.record_publish_failure", boom)
    lm._record_meta_failure({"ok": False, "error": "x"}, account_code="IDN-000007", rid="r", stage="s")  # 예외 없음
