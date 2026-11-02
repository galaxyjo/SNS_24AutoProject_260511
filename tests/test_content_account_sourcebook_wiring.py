"""261102 STEP 3 — 024·027·028·029 계정 전용 Sourcebook 연결(sourcebook_path) Target Test.

네트워크·Airtable·게시 없음. 기존 구조(ContentAccount.sourcebook_path → _package_kwargs)만 확인한다.
"""

from pathlib import Path

import pytest

from launcher import main as launcher_main
from modules.sns.source_selector import list_selectable_topics, parse_sourcebook, topic_matches_content_pillars

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "docs" / "design"

# 261102 Airtable Persona content_pillars 사본(계정별 Pillar). 바뀌면 이 테스트가 매칭 회귀를 알려준다.
WIRED = {
    "IDN-000024": ("SNS_AI_BEAUTY_SOURCEBOOK_IDN024_261102.md", "beauty / AI 뷰티 소개 / 뷰티 기술 트렌드", "@ai.beautique"),
    "IDN-000027": ("SNS_AI_RISK_SOURCEBOOK_IDN027_261102.md", "risk / AI 리스크 관리 / AI 원리 설명", "@neuron.xray"),
    "IDN-000028": ("SNS_AI_MARKETING_SOURCEBOOK_IDN028_261102.md", "marketing / AI 마케팅 활용 / AI 활용 팁", "@gojj771205"),
    "IDN-000029": ("SNS_AI_TOOLS_SOURCEBOOK_IDN029_261102.md", "AI 도구 사용기 / 자동화 사례 / 실천 기록 / 좋은 글", "@nohanmin"),
}
# 이번 변경 전부터 전용 Sourcebook을 쓰던 계정 — 경로가 그대로여야 한다.
UNCHANGED = {
    "IDN-000017": "SNS_BMED_SOURCEBOOK_IDN017_261028.md",
    "IDN-000018": "SNS_BMED_SOURCEBOOK_IDN018_261028.md",
    "IDN-000019": "SNS_BMED_SOURCEBOOK_IDN019_261028.md",
    "IDN-000022": "SNS_AI_NEWS_SOURCEBOOK_IDN022_261026.md",
    "IDN-000023": "SNS_KFOOD_SOURCEBOOK_IDN023_261026.md",
    "IDN-000025": "SNS_AI_SHOWHOST_SOURCEBOOK_IDN025_261101.md",
    "IDN-000030": "SNS_AI_AUTOMATION_SOURCEBOOK_IDN030_261028.md",
    "IDN-000031": "SNS_BMED_SOURCEBOOK_IDN031_261028.md",
    "IDN-000035": "SNS_BMED_SOURCEBOOK_IDN035_261028.md",
    "IDN-000038": "SNS_TRAVEL_SOURCEBOOK_IDN038_261028.md",
}


@pytest.mark.parametrize("code", sorted(WIRED))
def test_account_carries_own_sourcebook_in_package_kwargs(code):
    name, _pillars, handle = WIRED[code]
    acct = launcher_main.CONTENT_ACCOUNTS[code]
    kw = launcher_main._package_kwargs(acct)
    assert kw["sourcebook_path"] == DESIGN / name and (DESIGN / name).is_file()
    assert kw["brand_handle"] == handle
    # vault·lock·credential·env 접두사는 기존 규칙 그대로(이번 변경은 sourcebook_path만)
    assert acct.vault_root == ROOT / "vault" / "accounts" / code
    assert acct.lock_name == f"content_producer_{code}" and acct.news_enabled is False
    assert acct.credential_key == code.replace("-", "_") and acct.env_prefix == code.replace("-", "_")


@pytest.mark.parametrize("code", sorted(WIRED))
def test_own_sourcebook_gives_three_pillar_matched_topics(code):
    name, pillars, _ = WIRED[code]
    topics = list_selectable_topics(parse_sourcebook(DESIGN / name))
    matched = [t for t in topics if topic_matches_content_pillars(t, pillars)]
    assert len(topics) >= 3 and len(matched) >= 3
    assert len({t.source_url for t in matched}) >= 3          # 하루 3건에 서로 다른 원천 3개
    for t in matched:
        if t.topic_id != "1.1":   # 1.1은 공용 Sourcebook에서 그대로 가져온 기존 항목(선택 필드 없음)
            assert t.image_concept and t.card_facts and t.topic_hashtags


@pytest.mark.parametrize("code,name", sorted(UNCHANGED.items()))
def test_other_content_accounts_sourcebook_unchanged(code, name):
    assert launcher_main.CONTENT_ACCOUNTS[code].sourcebook_path == DESIGN / name


def test_aijomoojin_and_shared_sourcebook_untouched():
    assert launcher_main._package_kwargs(launcher_main.CONTENT_ACCOUNTS["IDN-000036"]) == {}
    shared = (DESIGN / "SNS_AI_STARTUP_CONTENT_SOURCEBOOK_260723.md").read_text(encoding="utf-8")
    for code, (name, _p, _h) in WIRED.items():
        new_urls = {t.source_url for t in parse_sourcebook(DESIGN / name) if t.topic_id != "1.1"}
        assert new_urls and not any(u in shared for u in new_urls)   # 신규 항목은 036의 공용 풀에 섞이지 않는다


def test_content_accounts_key_set_unchanged():
    assert set(launcher_main.CONTENT_ACCOUNTS) == {
        "IDN-000017", "IDN-000018", "IDN-000019", "IDN-000022", "IDN-000023", "IDN-000024", "IDN-000025",
        "IDN-000027", "IDN-000028", "IDN-000029", "IDN-000030", "IDN-000031", "IDN-000035", "IDN-000036",
        "IDN-000038",
    }
