"""260914 — launcher/main.py::_job_fb_crawl Slack 예외 알림 복구 검증.

배경: 2026-07-30 c00a734(ERR-089 Heartbeat 추가)가 @handle_errors(task="fb_crawl")
와 def _job_fb_crawl 사이에 heartbeat 함수를 끼워 넣어 데코레이터가 이탈했다.
그 뒤 크롤링 전체실패 예외(FacebookCrawlAllTargetsFailedError)가 Slack 에 닿지 않았다.

실제 Facebook·AdsPower·Airtable·Slack 호출 없음(Mock 전용). 계정 순회·실패 집계는
실제 run_all_accounts 로직을 그대로 태운다(개별 URL 크롤 run() 만 Mock).

검증 목표:
  1. 전체 실패 예외 → 잡은 죽지 않고 Slack Mock 1회
  2. 부분 성공 → 예외 없음, Slack Mock 0회 (기존 부분성공 동작 유지)
  3. 모든 테스트에서 실제 Slack HTTP 요청 0건
"""

from types import SimpleNamespace

import pytest

KW = {
    "target_publish_account_code_ref": "IDN-000041",
    "data_classification": "production",
}


@pytest.fixture(autouse=True)
def slack_guard(monkeypatch):
    """이 파일의 모든 테스트에서 실제 Slack Webhook 호출을 차단한다.

    - send_alert 를 기록용 Mock 으로 바꾼다 → 알림 호출 횟수·내용은 여기서 검증한다.
    - HTTP 경계(requests.post)는 호출을 기록만 한다. slack_notifier._post 가 모든
      예외를 삼키므로 raise 로는 드러나지 않는다 — teardown 에서 0건을 단언한다.
    """
    import services.slack_notifier as sn

    guard = SimpleNamespace(sent=[], http_calls=[])
    monkeypatch.setattr(
        sn, "send_alert",
        lambda title, body="", level="warning": guard.sent.append(
            {"title": title, "body": body, "level": level}
        ) or True,
    )
    monkeypatch.setattr(
        sn.requests, "post",
        lambda *a, **k: guard.http_calls.append((a, k)),
    )
    yield guard
    assert guard.http_calls == [], "테스트가 실제 Slack Webhook HTTP 요청을 시도했다"


@pytest.fixture
def m():
    from launcher import main as _m
    return _m


def _patch_crawler(monkeypatch, urls):
    """계정 1개 + URL 목록으로 실제 run_all_accounts 를 태운다.
    URL 에 'bad' 가 들어가면 그 URL 크롤은 예외를 낸다."""
    acct = SimpleNamespace(
        name="account1",
        crawl_urls=urls,
        adspower_user_id="k1bto3j4",
        selenium_proxy_options=lambda: None,
    )
    monkeypatch.setattr(
        "modules.common.account_manager.get_active_accounts", lambda: [acct]
    )
    monkeypatch.setattr(
        "modules.sns.facebook_crawler._validate_publish_context",
        lambda *a, **k: None,
    )

    def _fake_run(url, *a, **k):
        if "bad" in url:
            raise RuntimeError("WinError 10061")
        return []

    monkeypatch.setattr("modules.sns.facebook_crawler.run", _fake_run)


# ── 1. 전체 실패 → Slack Mock 1회 ────────────────────────────────────────────
def test_full_failure_sends_one_slack_alert(monkeypatch, m, slack_guard):
    if m._slack is None:
        pytest.skip("SLACK_WEBHOOK_URL 미설정 — notify_fn 이 None 이라 알림 경로 검증 불가")
    _patch_crawler(monkeypatch, [f"https://fb/groups/bad{i}" for i in range(5)])

    assert hasattr(m._job_fb_crawl, "__wrapped__")      # 데코레이터 복구 확인
    assert m._job_fb_crawl(**KW) is None                # 잡은 죽지 않는다

    assert len(slack_guard.sent) == 1
    alert = slack_guard.sent[0]
    assert alert["level"] == "error"
    assert "[fb_crawl]" in alert["body"]
    assert "전체 URL 실패 계정" in alert["body"]


# ── 2. 부분 성공 → 예외 없음, Slack Mock 0회 ─────────────────────────────────
def test_partial_success_sends_no_slack_alert(monkeypatch, m, slack_guard):
    _patch_crawler(
        monkeypatch,
        [f"https://fb/groups/ok{i}" for i in range(4)] + ["https://fb/groups/bad0"],
    )

    m._job_fb_crawl.__wrapped__(**KW)    # 데코레이터 없이도 예외가 없어야 한다(기존 동작)
    assert m._job_fb_crawl(**KW) is None

    assert slack_guard.sent == []
