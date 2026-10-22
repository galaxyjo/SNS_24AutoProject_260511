"""261022 B1 — 발행 Gate 도메인 판정에 Account_Registry.category 사용 검증.

ACCOUNT_DOMAIN_POLICY(기존 2계정)가 항상 우선이고, 그 외 계정은 category가
CATEGORY_DOMAIN_POLICY에 있을 때만 도메인을 받는다. 그 외는 기존과 같이 UNKNOWN_DOMAIN.
실제 Airtable·게시·Gemini 호출 없음 — 전부 Mock.
"""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from modules.infra.airtable_repository import AirtableRepository
from modules.sns.content_filter import resolve_publish_gate

PRODUCT_CAPTION = "wholesale k-beauty skincare export"


# ── 1. content_filter: category 매핑 ──────────────────────────────────────────
class TestCategoryDomain:
    def test_a_beauty_account_gets_product_domain(self):
        allowed, code = resolve_publish_gate(PRODUCT_CAPTION, "IDN-000048", account_category="A_BEAUTY")
        assert (allowed, code) == (True, "PUBLISH_ALLOWED")

    def test_a_beauty_account_still_runs_product_keyword_filter(self):
        allowed, code = resolve_publish_gate("random unrelated text", "IDN-000048", account_category="A_BEAUTY")
        assert (allowed, code) == (False, "DOMAIN_CONTENT_REJECTED")

    @pytest.mark.parametrize("category", ["", "  ", "D_AI", "B_MED", "C_TRAVEL", "E_AESTHETIC", "UNCATEGORIZED", "a_beauty"])
    def test_unmapped_category_stays_unknown_domain(self, category):
        allowed, code = resolve_publish_gate(PRODUCT_CAPTION, "IDN-000048", account_category=category)
        assert (allowed, code) == (False, "UNKNOWN_DOMAIN")

    def test_omitted_category_keeps_old_unknown_domain(self):
        assert resolve_publish_gate(PRODUCT_CAPTION, "IDN-000048") == (False, "UNKNOWN_DOMAIN")

    def test_category_with_surrounding_spaces_is_trimmed(self):
        allowed, _ = resolve_publish_gate(PRODUCT_CAPTION, "IDN-000048", account_category=" A_BEAUTY ")
        assert allowed is True

    def test_account_dict_wins_over_category_for_ai_account(self):
        """IDN-000036은 category가 A_BEAUTY여도 AI_CONTENT Gate를 탄다(PRODUCT로 바뀌지 않음)."""
        allowed, code = resolve_publish_gate(PRODUCT_CAPTION, "IDN-000036", account_category="A_BEAUTY")
        assert allowed is False
        assert code in ("AI_CONTENT_PERSONA_MISMATCH", "AI_CONTENT_NO_SOURCE")

    def test_account_dict_wins_over_category_for_yuna(self):
        """IDN-000041은 category가 미등록 값이어도 기존 PRODUCT 그대로."""
        allowed, code = resolve_publish_gate(PRODUCT_CAPTION, "IDN-000041", account_category="D_AI")
        assert (allowed, code) == (True, "PUBLISH_ALLOWED")

    def test_global_safety_runs_before_category(self):
        with patch("modules.sns.content_filter._passes_global_safety", return_value=False):
            assert resolve_publish_gate(PRODUCT_CAPTION, "IDN-000048", account_category="A_BEAUTY") == (
                False, "GLOBAL_SAFETY_REJECTED")


# ── 2. Repository: category 파싱 ─────────────────────────────────────────────
def _repo_with_fields(fields):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"records": [{"fields": fields}]}
    with patch("modules.infra.airtable_repository.requests.get", return_value=resp), \
         patch("modules.infra.airtable_repository.log_api_call"):
        return AirtableRepository().get_publish_account("IDN-000048")


class TestRepositoryCategory:
    def test_category_singleselect_dict_is_parsed_to_name(self):
        acct = _repo_with_fields({"account_code": "IDN-000048", "category": {"name": "A_BEAUTY"}})
        assert acct["category"] == "A_BEAUTY"

    def test_category_plain_string_is_kept(self):
        acct = _repo_with_fields({"account_code": "IDN-000048", "category": "A_BEAUTY"})
        assert acct["category"] == "A_BEAUTY"

    def test_missing_category_is_empty_string(self):
        acct = _repo_with_fields({"account_code": "IDN-000048"})
        assert acct["category"] == ""

    def test_existing_fields_unchanged(self):
        acct = _repo_with_fields({
            "account_code": "IDN-000048", "api_provider": {"name": "facebook_login"},
            "ig_user_id": "1", "credential_key": "SALE1", "automation_enabled": True,
            "category": {"name": "A_BEAUTY"},
        })
        assert acct["api_provider"] == "facebook_login"
        assert acct["credential_key"] == "SALE1"
        assert acct["automation_enabled"] is True
        assert "access_token" not in acct


# ── 3. launcher: category가 Gate로 전달되고, Kill Switch가 여전히 먼저 막는다 ──
@pytest.fixture
def launcher(monkeypatch):
    monkeypatch.delenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", raising=False)
    monkeypatch.setenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "true")
    monkeypatch.setenv("PUBLISH_TEXT_GATE_ENABLED", "true")
    from launcher import main as m
    return m


def _setup(monkeypatch, m, *, automation_enabled, account):
    calls = SimpleNamespace(gate=[], claim=[], mark=[])
    record = {"post_id": "recB1", "image_url": "http://img", "caption": PRODUCT_CAPTION,
              "hashtag": "", "account_code_ref": "IDN-000048"}

    class Repo:
        def fetch_pending_posts(self, limit=50):
            return [dict(record)]

        def get_publish_account(self, code):
            return dict(account, automation_enabled=automation_enabled)

        def get_active_persona_by_account_code_v2(self, code):
            return None

        def claim_post_for_upload(self, post_id):
            calls.claim.append(post_id)
            return False

        def mark_post_result(self, post_id, result):
            calls.mark.append((post_id, dict(result)))

    def _gate(caption, code, **k):
        calls.gate.append((code, k.get("account_category")))
        return True, "PUBLISH_ALLOWED"

    monkeypatch.setattr("modules.infra.airtable_repository.AirtableRepository", lambda: Repo())
    monkeypatch.setattr("modules.common.canary_classification.validate_publication_candidate",
                        lambda *a, **k: None)
    monkeypatch.setattr(m, "resolve_publish_gate", _gate)
    monkeypatch.setattr(m, "publish_single", lambda *a, **k: pytest.fail("must not publish"))
    monkeypatch.setattr("modules.common.credential_resolver.resolve_credential",
                        lambda key: SimpleNamespace(ig_user_id="1", access_token="fake"))
    return calls


ACCOUNT = {"account_code": "IDN-000048", "api_provider": "facebook_login", "ig_user_id": "1",
           "credential_key": "SALE1", "category": "A_BEAUTY"}


def test_launcher_passes_account_category_to_gate(monkeypatch, launcher):
    calls = _setup(monkeypatch, launcher, automation_enabled=True, account=ACCOUNT)
    launcher._job_insta_upload()
    assert calls.gate == [("IDN-000048", "A_BEAUTY")]
    assert calls.claim == ["recB1"]


def test_launcher_passes_empty_category_when_account_has_none(monkeypatch, launcher):
    acct = {k: v for k, v in ACCOUNT.items() if k != "category"}
    calls = _setup(monkeypatch, launcher, automation_enabled=True, account=acct)
    launcher._job_insta_upload()
    assert calls.gate == [("IDN-000048", "")]


def test_kill_switch_off_still_blocks_before_gate(monkeypatch, launcher, caplog):
    calls = _setup(monkeypatch, launcher, automation_enabled=False, account=ACCOUNT)
    with caplog.at_level(logging.INFO):
        launcher._job_insta_upload()
    assert calls.gate == [] and calls.claim == [] and calls.mark == []
    assert "Kill Switch OFF" in caplog.text
