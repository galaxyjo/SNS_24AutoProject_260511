"""261028 GPT 검수(B_MED) A~D Target Test — 허위 의료 표현·스톡 공개·출처 표기 Gate, launcher stale 경고. 네트워크 없음."""
import json
import os
import time
from datetime import datetime

import pytest

from modules.common.account_preflight import launcher_stale_warnings
from modules.sns.content_filter import passes_bmed_claims_gate, resolve_publish_gate

_PD = ("Image: skin tissue light absorption chart by R. Baraldini, Wikimedia Commons (public domain). "
       "Source: Anderson & Parrish, Science 1983 (PubMed 6836297).")
_STOCK = ("Image: stock photo by Anna Shvets via Pexels (illustrative only). "
          "Source: Fabi, Clin Cosmet Investig Dermatol 2015 (PMC4327394).")


def _cap(body="The paper shows a principle · not a guaranteed treatment result", credit=_PD):
    return f"Hook line....\n\n1.How?\n• Light is absorbed\n\n3.Key takeaway?\n: {body}\n\n{credit}\n\nDM us to book a consultation."


def test_posted_style_captions_pass():
    assert passes_bmed_claims_gate(_cap()) == (True, "PUBLISH_ALLOWED")          # 부정문 not a guaranteed → 허용
    assert passes_bmed_claims_gate(_cap("Results vary by person", _STOCK)) == (True, "PUBLISH_ALLOWED")


@pytest.mark.parametrize("phrase", [
    "Epidermis remains unharmed", "Guaranteed results", "Permanent results", "No side effects",
    "FDA approved device", "Ever wonder why top US clinics compare them?", "Painless and risk-free",
])
def test_false_medical_claims_blocked(phrase):
    ok, code = passes_bmed_claims_gate(_cap(phrase))
    assert not ok and code.startswith("BMED_BLOCKED_CLAIM:")


def test_image_credit_and_source_required():
    no_credit = "Hook\n\n: Results vary by person\n\nDM us."
    assert passes_bmed_claims_gate(no_credit) == (False, "BMED_IMAGE_CREDIT_MISSING")
    assert passes_bmed_claims_gate(_cap(credit="Image: stock photo by X via Pexels. Source: PubMed 1.")) == (
        False, "BMED_STOCK_DISCLOSURE_MISSING")
    assert passes_bmed_claims_gate(_cap(credit="Image: photo by X via Somewhere. Source: PubMed 1.")) == (
        False, "BMED_IMAGE_LICENSE_UNSTATED")
    assert passes_bmed_claims_gate(_cap(credit="Image: stock photo by X via Pexels (illustrative only).")) == (
        False, "BMED_SOURCE_MISSING")


def test_resolve_publish_gate_blocks_bmed_before_any_gemini_call():
    # BMED 코드는 AI_CONTENT Safety(Gemini 호출)보다 먼저 판정한다 → 네트워크 없이 거절 코드가 나온다.
    bad = _cap("Epidermis remains unharmed")
    allowed, code = resolve_publish_gate(bad, "IDN-000035", source_url="https://x", persona_code="PER-034",
                                         required_language="en")
    assert (allowed, code.split(":")[0]) == (False, "BMED_BLOCKED_CLAIM")


def test_non_bmed_account_not_affected():
    from modules.sns.content_filter import _BMED_ACCOUNTS
    assert "IDN-000036" not in _BMED_ACCOUNTS and "IDN-000022" not in _BMED_ACCOUNTS


def test_launcher_stale_warning(tmp_path):
    (tmp_path / "launcher").mkdir(); (tmp_path / "modules" / "sns").mkdir(parents=True)
    files = [tmp_path / "launcher" / "main.py", tmp_path / "modules" / "sns" / "content_filter.py",
             tmp_path / "modules" / "sns" / "caption_generator.py"]
    for f in files:
        f.write_text("x")
    boot = tmp_path / "boot.json"
    started = time.time() - 600
    boot.write_text(json.dumps({"commit": "abc", "started_at": datetime.fromtimestamp(started).strftime("%Y-%m-%d %H:%M:%S")}))
    for f in files:
        os.utime(f, (started - 100, started - 100))
    assert launcher_stale_warnings(boot, tmp_path) == []                       # 기동 이후 수정 없음
    os.utime(files[1], (started + 300, started + 300))
    assert launcher_stale_warnings(boot, tmp_path) == ["LAUNCHER_STALE:modules/sns/content_filter.py"]
    assert launcher_stale_warnings(tmp_path / "missing.json", tmp_path) == []  # 기록 없으면 경고 없음(NOT_READY 아님)
