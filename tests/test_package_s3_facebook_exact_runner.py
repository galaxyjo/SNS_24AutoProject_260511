"""8단계 Safety Package S3 — Facebook Direct-Permalink Runner 테스트."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from modules.common.canary_execution_guard import CanaryWriteOperation
from modules.sns import facebook_crawler
from modules.sns.facebook_crawler import FacebookCanaryError


class _Anchor:
    def __init__(self, href, aria_label=""):
        self.href = href
        self.aria_label = aria_label

    def get_attribute(self, name):
        if name == "href":
            return self.href
        if name == "aria-label":
            return self.aria_label
        return ""


class _Article:
    def __init__(self, hrefs):
        self.hrefs = hrefs

    def find_elements(self, by, selector):
        assert selector == "a[href]"
        anchors = []
        for item in self.hrefs:
            if isinstance(item, tuple):
                href, aria_label = item
            else:
                href, aria_label = item, ""
            anchors.append(_Anchor(href, aria_label))
        return anchors


class _Driver:
    def __init__(self, articles):
        self.articles = articles
        self.selectors = []
        self.visited = []
        self.quit_called = 0

    def get(self, url):
        self.visited.append(url)

    def find_elements(self, by, selector):
        self.selectors.append(selector)
        assert selector == "div[role='article']"
        return self.articles

    def quit(self):
        self.quit_called += 1


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.facebook.com/groups/10/posts/123456/", "123456"),
        ("https://facebook.com/page/posts/234567", "234567"),
        ("https://m.facebook.com/permalink/345678/", "345678"),
        ("https://www.facebook.com/story.php?story_fbid=456789&id=10", "456789"),
        ("https://www.facebook.com/photo/?fbid=567890", "567890"),
    ],
)
def test_extract_facebook_post_id_supported_formats(url, expected):
    assert facebook_crawler.extract_facebook_post_id(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://facebook.com/posts/123",
        "https://example.com/posts/123",
        "https://facebook.com/groups/10",
        "https://facebook.com/posts/not-numeric",
        "https://facebook.com/posts/123?fbid=456",
    ],
)
def test_invalid_permalink_is_rejected(url):
    with pytest.raises(FacebookCanaryError):
        facebook_crawler.extract_facebook_post_id(url)


def test_exact_selector_requires_one_matching_article():
    driver = _Driver([
        _Article(["https://facebook.com/posts/111"]),
        _Article(["https://facebook.com/posts/222"]),
    ])
    selected = facebook_crawler._find_exact_permalink_article(driver, "222")
    assert selected is driver.articles[1]


@pytest.mark.parametrize(
    "articles",
    [
        [],
        [_Article(["https://facebook.com/posts/111"])],
        [
            _Article(["https://facebook.com/posts/111"]),
            _Article(["https://facebook.com/posts/333"]),
        ],
        [
            _Article(["https://example.com/not-a-post"]),
            _Article([]),
        ],
    ],
)
def test_exact_selector_rejects_zero_matches(articles):
    with pytest.raises(FacebookCanaryError):
        facebook_crawler._find_exact_permalink_article(_Driver(articles), "222")


@pytest.mark.parametrize(
    "articles",
    [
        [
            _Article(["https://facebook.com/posts/222"]),
            _Article(["https://facebook.com/permalink/222"]),
        ],
        [
            _Article(["https://facebook.com/posts/222"]),
            _Article(["https://facebook.com/permalink/222"]),
            _Article(["https://m.facebook.com/permalink/222"]),
        ],
    ],
)
def test_exact_selector_dedupes_duplicate_dom_for_same_post_id(articles):
    driver = _Driver(articles)
    selected = facebook_crawler._find_exact_permalink_article(driver, "222")
    assert selected is driver.articles[0]


def test_exact_selector_ignores_hide_post_ui_action_anchor():
    """260729 실측 재현: Facebook의 '게시물 숨기기' UI 액션 anchor는 실제 이동
    링크가 아니라 현재 보고 있는 permalink 자체를 href로 재사용한다(예:
    '.../posts/222#'). 무관한 게시물에 이 UI 액션만 있고 진짜 게시물 링크가
    없으면 매칭 대상이 아니어야 한다."""
    driver = _Driver([
        _Article([
            ("https://facebook.com/groups/1/posts/222#", "China Sixsix님의 게시물 숨기기"),
        ]),
    ])
    with pytest.raises(FacebookCanaryError):
        facebook_crawler._find_exact_permalink_article(driver, "222")


def test_exact_selector_prefers_real_link_over_hide_post_ui_action_anchor():
    """무관 게시물의 '숨기기' 위장 링크와, 진짜 목표 게시물의 실제 링크가 같은
    페이지에 함께 있어도 진짜 게시물만 선택돼야 한다."""
    decoy_article = _Article([
        ("https://facebook.com/groups/1/posts/222#", "무관계정님의 게시물 숨기기"),
    ])
    real_article = _Article(["https://facebook.com/groups/1/posts/222"])
    driver = _Driver([decoy_article, real_article])
    selected = facebook_crawler._find_exact_permalink_article(driver, "222")
    assert selected is real_article


def test_exact_selector_ignores_any_bare_hash_placeholder_href_regardless_of_label():
    """260729 실측 재현(2): 같은 실제 게시물 안에 '숨기기'와 무관한(aria-label에
    '숨기기'가 없는) 다른 UI 액션 anchor도 동일하게 href가 빈 `#`로 끝나면
    실제 게시물 링크로 인정하지 않는다 — aria-label 문구에 의존하지 않는다."""
    driver = _Driver([
        _Article([
            ("https://facebook.com/groups/1/posts/222#", "다른 메뉴 액션(신고 등)"),
        ]),
    ])
    with pytest.raises(FacebookCanaryError):
        facebook_crawler._find_exact_permalink_article(driver, "222")


@pytest.mark.parametrize(
    "url",
    [
        "http://img.example/existing.jpg",
        "https://facebook.com/image.jpg",
        "https://scontent.xx.fbcdn.net/image.jpg",
    ],
)
def test_unapproved_or_facebook_image_url_is_rejected(url):
    with pytest.raises(FacebookCanaryError):
        facebook_crawler._validate_approved_canary_image_url(url)


def test_exact_runner_creates_one_draft_without_feed_or_imgbb(monkeypatch):
    events = []
    permalink = "https://www.facebook.com/groups/10/posts/123456/"
    driver = _Driver([_Article([permalink])])

    class _Repo:
        def validate_instagram_post_context(
            self, account, classification, run_id, post_status
        ):
            events.append(("validate", classification, post_status))
            return {
                "account_code": account,
                "credential_key": "YUNA",
                "ig_user_id": "ig-1",
            }

        def exists_post_by_image_url(self, image_url):
            events.append(("dedup", image_url))
            return False

        def save_instagram_post(self, payload):
            events.append(("save", dict(payload)))
            return "rec-canary-post"

    class _Guard:
        def authorize_write(self, operation, **kwargs):
            events.append(("authorize", operation))
            return 1

    account = SimpleNamespace(
        name="account1",
        active=True,
        adspower_user_id="ads-1",
        selenium_proxy_options=lambda: {},
    )
    monkeypatch.setattr(
        "modules.common.account_manager.get_account",
        lambda name: account if name == "account1" else None,
    )
    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository",
        lambda: _Repo(),
    )
    monkeypatch.setattr(
        "modules.common.credential_resolver.resolve_credential",
        lambda key: SimpleNamespace(ig_user_id="ig-1"),
    )
    monkeypatch.setattr(facebook_crawler, "get_driver", lambda *a, **k: driver)
    monkeypatch.setattr(facebook_crawler, "stop_browser", MagicMock())
    monkeypatch.setattr(facebook_crawler.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        facebook_crawler,
        "upload_to_imgbb",
        MagicMock(side_effect=AssertionError("ImgBB 호출 금지")),
    )
    monkeypatch.setattr(
        facebook_crawler,
        "generate_caption",
        MagicMock(side_effect=AssertionError("Caption AI 호출 금지")),
    )

    result = facebook_crawler.run_exact_permalink_canary(
        permalink=permalink,
        expected_post_id="123456",
        approved_image_url="https://img.example/existing.jpg",
        approved_caption="Approved caption",
        source_account_name="account1",
        canary_run_id="canary-s3",
        write_guard=_Guard(),
    )

    assert result == {
        "created": 1,
        "record_id": "rec-canary-post",
        "facebook_post_id": "123456",
        "post_status": "draft",
    }
    assert driver.visited == [permalink]
    assert "div[role='feed']" not in driver.selectors
    assert driver.quit_called == 1
    assert [event[0] for event in events] == [
        "validate",
        "dedup",
        "authorize",
        "save",
    ]
    payload = events[-1][1]
    assert payload["account_code_ref"] == "IDN-000041"
    assert payload["data_classification"] == "test"
    assert payload["canary_run_id"] == "canary-s3"
    assert payload["post_status"] == "draft"


def test_exact_runner_dedupes_duplicate_dom_without_imgbb_or_extra_writes(monkeypatch):
    events = []
    permalink = "https://www.facebook.com/groups/10/posts/123456/"
    driver = _Driver([
        _Article([permalink]),
        _Article(["https://facebook.com/permalink/123456"]),
    ])

    class _Repo:
        def validate_instagram_post_context(
            self, account, classification, run_id, post_status
        ):
            events.append(("validate", classification, post_status))
            return {
                "account_code": account,
                "credential_key": "YUNA",
                "ig_user_id": "ig-1",
            }

        def exists_post_by_image_url(self, image_url):
            events.append(("dedup", image_url))
            return False

        def save_instagram_post(self, payload):
            events.append(("save", dict(payload)))
            return "rec-canary-post"

    class _Guard:
        def authorize_write(self, operation, **kwargs):
            events.append(("authorize", operation))
            return 1

    account = SimpleNamespace(
        name="account1",
        active=True,
        adspower_user_id="ads-1",
        selenium_proxy_options=lambda: {},
    )
    monkeypatch.setattr(
        "modules.common.account_manager.get_account",
        lambda name: account if name == "account1" else None,
    )
    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository",
        lambda: _Repo(),
    )
    monkeypatch.setattr(
        "modules.common.credential_resolver.resolve_credential",
        lambda key: SimpleNamespace(ig_user_id="ig-1"),
    )
    monkeypatch.setattr(facebook_crawler, "get_driver", lambda *a, **k: driver)
    monkeypatch.setattr(facebook_crawler, "stop_browser", MagicMock())
    monkeypatch.setattr(facebook_crawler.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        facebook_crawler,
        "upload_to_imgbb",
        MagicMock(side_effect=AssertionError("ImgBB 호출 금지")),
    )
    monkeypatch.setattr(
        facebook_crawler,
        "generate_caption",
        MagicMock(side_effect=AssertionError("Caption AI 호출 금지")),
    )

    result = facebook_crawler.run_exact_permalink_canary(
        permalink=permalink,
        expected_post_id="123456",
        approved_image_url="https://img.example/existing.jpg",
        approved_caption="Approved caption",
        source_account_name="account1",
        canary_run_id="canary-s3",
        write_guard=_Guard(),
    )

    assert result["created"] == 1
    assert [event[0] for event in events].count("save") == 1
    assert [event[0] for event in events] == [
        "validate",
        "dedup",
        "authorize",
        "save",
    ]


def test_exact_runner_selector_failure_consumes_no_run_id_or_write(monkeypatch):
    events = []
    permalink = "https://www.facebook.com/groups/10/posts/123456/"
    driver = _Driver([
        _Article(["https://facebook.com/posts/111"]),
        _Article(["https://facebook.com/posts/333"]),
    ])

    class _Repo:
        def validate_instagram_post_context(
            self, account, classification, run_id, post_status
        ):
            events.append(("validate", classification, post_status))
            return {
                "account_code": account,
                "credential_key": "YUNA",
                "ig_user_id": "ig-1",
            }

        def exists_post_by_image_url(self, image_url):
            events.append(("dedup", image_url))
            return False

        def save_instagram_post(self, payload):
            events.append(("save", dict(payload)))
            return "rec-canary-post"

    class _Guard:
        def authorize_write(self, operation, **kwargs):
            events.append(("authorize", operation))
            return 1

    account = SimpleNamespace(
        name="account1",
        active=True,
        adspower_user_id="ads-1",
        selenium_proxy_options=lambda: {},
    )
    monkeypatch.setattr(
        "modules.common.account_manager.get_account",
        lambda name: account if name == "account1" else None,
    )
    monkeypatch.setattr(
        "modules.infra.airtable_repository.AirtableRepository",
        lambda: _Repo(),
    )
    monkeypatch.setattr(
        "modules.common.credential_resolver.resolve_credential",
        lambda key: SimpleNamespace(ig_user_id="ig-1"),
    )
    monkeypatch.setattr(facebook_crawler, "get_driver", lambda *a, **k: driver)
    monkeypatch.setattr(facebook_crawler, "stop_browser", MagicMock())
    monkeypatch.setattr(facebook_crawler.time, "sleep", lambda seconds: None)

    with pytest.raises(FacebookCanaryError, match="찾지 못함"):
        facebook_crawler.run_exact_permalink_canary(
            permalink=permalink,
            expected_post_id="123456",
            approved_image_url="https://img.example/existing.jpg",
            approved_caption="Approved caption",
            source_account_name="account1",
            canary_run_id="canary-s3",
            write_guard=_Guard(),
        )

    assert [event[0] for event in events] == ["validate", "dedup"]
    assert driver.quit_called == 1


def test_permalink_mismatch_stops_before_browser_or_write(monkeypatch):
    get_driver = MagicMock()
    monkeypatch.setattr(facebook_crawler, "get_driver", get_driver)

    with pytest.raises(FacebookCanaryError, match="불일치"):
        facebook_crawler.run_exact_permalink_canary(
            permalink="https://facebook.com/posts/123",
            expected_post_id="456",
            approved_image_url="https://img.example/existing.jpg",
            approved_caption="Approved",
            source_account_name="account1",
            canary_run_id="canary-s3",
            write_guard=MagicMock(),
        )
    get_driver.assert_not_called()


def test_runner_cli_has_no_publish_or_batch_override():
    from tools.run_facebook_canary import build_parser

    destinations = {action.dest for action in build_parser()._actions}
    assert "max_records" not in destinations
    assert "publish" not in destinations
    assert "target_publish_account_code_ref" not in destinations


def test_tool_begins_runs_and_completes_exactly_once(monkeypatch):
    from tools import run_facebook_canary

    events = []

    class _Guard:
        def __init__(self, run_id, source, budget):
            events.append(("guard", run_id, source, budget.route.value))

        def begin(self):
            events.append(("begin",))

        def complete(self):
            events.append(("complete",))

        def fail(self, code):
            events.append(("fail", code))

    def _run(**kwargs):
        events.append(("run", kwargs["target_publish_account_code_ref"]))
        return {"created": 1}

    monkeypatch.setattr(run_facebook_canary, "CanaryExecutionGuard", _Guard)
    monkeypatch.setattr(run_facebook_canary, "run_exact_permalink_canary", _run)

    result = run_facebook_canary.execute_facebook_canary(
        canary_run_id="canary-s3",
        permalink="https://facebook.com/posts/123",
        expected_post_id="123",
        approved_image_url="https://img.example/existing.jpg",
        approved_caption="Approved",
        source_account_name="account1",
    )

    assert result == {"created": 1}
    assert events == [
        ("guard", "canary-s3", "https://facebook.com/posts/123", "facebook"),
        ("begin",),
        ("run", "IDN-000041"),
        ("complete",),
    ]


def test_tool_failure_marks_failed_and_never_completes(monkeypatch):
    from tools import run_facebook_canary

    events = []

    class _Guard:
        def __init__(self, *args, **kwargs):
            pass

        def begin(self):
            events.append("begin")

        def complete(self):
            events.append("complete")

        def fail(self, code):
            events.append(("fail", code))

    monkeypatch.setattr(run_facebook_canary, "CanaryExecutionGuard", _Guard)
    monkeypatch.setattr(
        run_facebook_canary,
        "run_exact_permalink_canary",
        MagicMock(side_effect=FacebookCanaryError("expected")),
    )

    with pytest.raises(FacebookCanaryError, match="expected"):
        run_facebook_canary.execute_facebook_canary(
            canary_run_id="canary-s3",
            permalink="https://facebook.com/posts/123",
            expected_post_id="123",
            approved_image_url="https://img.example/existing.jpg",
            approved_caption="Approved",
            source_account_name="account1",
        )

    assert events == ["begin", ("fail", "FACEBOOKCANARYERROR")]
