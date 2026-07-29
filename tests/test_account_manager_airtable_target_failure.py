"""9-10-3-A Defect B — Airtable Crawl_Targets 조회 실패가 정상 0건과 동일한 []로
둔갑해 cache에 영구 고정되는 구조를 차단했는지 검증한다.

Runtime 상태변경(Airtable Write, 실제 네트워크 호출) 없이 Mock으로만 검증한다.
"""

import pytest

from modules.common import account_manager


@pytest.fixture(autouse=True)
def _reset_cache_and_env(monkeypatch):
    """모듈 전역 캐시를 매 테스트마다 초기화 — 테스트 간 상태 누출 방지."""
    monkeypatch.setattr(account_manager, "_cache", None)
    monkeypatch.setenv("CRAWL_TARGET_SOURCE", "airtable")
    yield
    monkeypatch.setattr(account_manager, "_cache", None)


def _fake_json_accounts():
    return [
        account_manager.Account(
            name="account1",
            active=True,
            adspower_user_id="k1bto3j4",
            ig_user_id="",
            ig_access_token="",
            fb_page_id="",
            airtable_base_id="",
            crawl_urls=["https://www.facebook.com/groups/original"],
        )
    ]


class TestAirtableTargetLoadFailure:
    def test_airtable_success_applies_target_urls(self, monkeypatch):
        monkeypatch.setattr(account_manager, "_load_from_json", _fake_json_accounts)
        monkeypatch.setattr(
            account_manager,
            "_load_crawl_urls_from_airtable",
            lambda: ["https://www.facebook.com/groups/a", "https://www.facebook.com/groups/b"],
        )

        accounts = account_manager.get_active_accounts()

        assert accounts[0].crawl_urls == [
            "https://www.facebook.com/groups/a",
            "https://www.facebook.com/groups/b",
        ]

    def test_airtable_failure_propagates_instead_of_returning_empty_list(self, monkeypatch):
        monkeypatch.setattr(account_manager, "_load_from_json", _fake_json_accounts)

        def _boom():
            raise RuntimeError("Airtable 조회 실패(시뮬레이션)")

        monkeypatch.setattr(account_manager, "_load_crawl_urls_from_airtable", _boom)

        with pytest.raises(RuntimeError, match="Airtable 조회 실패"):
            account_manager.get_active_accounts()

    def test_airtable_failure_does_not_poison_cache_and_retries_next_call(self, monkeypatch):
        monkeypatch.setattr(account_manager, "_load_from_json", _fake_json_accounts)

        call_count = {"n": 0}

        def _fail_once_then_succeed():
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("첫 호출은 실패")
            return ["https://www.facebook.com/groups/recovered"]

        monkeypatch.setattr(account_manager, "_load_crawl_urls_from_airtable", _fail_once_then_succeed)

        with pytest.raises(RuntimeError):
            account_manager.get_active_accounts()

        # 실패가 cache에 []로 고정되지 않았어야 다음 호출에서 다시 Airtable을 조회한다.
        accounts = account_manager.get_active_accounts()

        assert call_count["n"] == 2
        assert accounts[0].crawl_urls == ["https://www.facebook.com/groups/recovered"]

    def test_shadow_mode_failure_is_fail_open_and_keeps_json_urls(self, monkeypatch):
        monkeypatch.setenv("CRAWL_TARGET_SOURCE", "shadow")
        monkeypatch.setattr(account_manager, "_load_from_json", _fake_json_accounts)
        monkeypatch.setattr(
            account_manager,
            "_load_crawl_urls_from_airtable",
            lambda: (_ for _ in ()).throw(RuntimeError("shadow 조회 실패")),
        )

        accounts = account_manager.get_active_accounts()

        # shadow 모드는 비교용일 뿐 — 실패해도 기존 accounts.json crawl_urls를 그대로 유지한다.
        assert accounts[0].crawl_urls == ["https://www.facebook.com/groups/original"]
