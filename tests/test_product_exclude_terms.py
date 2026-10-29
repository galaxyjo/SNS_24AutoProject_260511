"""261029 — PRODUCT Gate 뷰티 무관 제외어(PRODUCT_EXCLUDE_TERMS) Target Test.

배경: ERR-186 / 041 오염 조사 — 041 게시물 157건 중 뷰티 무관 33건. KEYWORDS 한 단어
("wholesale", "b2b", "supply")만 맞아도 통과하던 구조 때문에 금융 광고 등이 게시됐다.

네트워크·Airtable 호출 없음. 캡션은 실제 게시된 글에서 가져온 대표 사례다.

검증 목표:
  1. 실제로 통과해 게시됐던 뷰티 무관 글은 PRODUCT 키워드 필터에서 제외된다
  2. 뷰티 본업 도매 글은 기존과 같이 통과한다 (오탐 없음)
  3. 게시 직전 Gate(resolve_publish_gate)에서도 IDN-000041 기준으로 같은 판정이 난다
"""

import pytest

from modules.sns.content_filter import passes_keyword_filter, resolve_publish_gate

OFF_TOPIC = {
    "finance_261026": (
        "Struggling with cash flow for your B2B business? 😩 We offer solutions for wholesale, "
        "manufacturing, construction, and more, with options like accounts receivable factoring "
        "and purchase fund securitization. Get the working capital you need! 💸🇰🇷"
    ),
    "event_260806": (
        "Get ready for a Y2K-themed morning rave this Saturday at Bukchon! 🎶 Enjoy free coffee, "
        "caviar bites, and K-Beauty experiences with amazing DJs. Don't miss this unique start to "
        "your weekend! ✨"
    ),
    "ai_service_261011": (
        "Excited to announce we're expanding our AI content services! 🚀 We're now offering TikTok "
        "Shop setup and sales for Korean businesses, complete with supply and direct shipping to "
        "Korea. Let's reach new heights together! 🇰🇷✨"
    ),
    "supplement_omega3": (
        "Boost your well-being with Chong Kun Dang's Promega Omega-3 Triple! 🌿 Get a 3-month "
        "supply of 60 capsules to support your health. 💪\n\n#Omega3 #KoreanHealth "
        "#HealthSupplements #KoreaWellness"
    ),
    "food_cheonggukjang": (
        "Experience the rich, savory aroma of our 200g pack of Cheonggukjang! 🇰🇷 Made with the "
        "finest ingredients for a delicious and healthy meal. ✨\n\n#Cheonggukjang #KoreanFood #KBeauty"
    ),
    "household_bento": (
        "Get your hands on this convenient 100-piece set of 2-compartment bento boxes with lids! "
        "Perfect for packing meals on the go. 🥗🍱\n\n#koreapackaging #koreafood #koreakitchen"
    ),
    "drink_hangover": (
        "Feeling the after-effects of a fun night? 😴 This Korean hangover relief drink is here to "
        "save the day!\n\n#koreandrink #hangovercure #kbeauty #kfood"
    ),
    "finance_kr_raw": "도매·유통·제조 B2B 사업자분들을 위한 매출채권 팩토링, 대출 상담 안내",
}

BEAUTY = {
    "luvum_mask": (
        "Stock up on Luvum's amazing gel mask packs at wholesale prices! 🍋✨ Featuring Yuzu Gel, "
        "Vitamin Gel, and Marine PDRN Gel, each box contains 48 masks. Perfect for glowing skin! 💖\n\n"
        "#koreanskincare #kbeauty #maskpack #koreancosmetics"
    ),
    "ohui_whoo_sum": (
        "New stock has arrived! 🇰🇷 We have large quantities of OHUI, The Whoo & SUM available for "
        "wholesale at competitive prices. DM for inquiries! ✨"
    ),
    "celimax_quote": (
        "Looking for premium Korean skincare to stock? ✨ Add Celimax to your collection! Get "
        "wholesale pricing and details from Fancy Global for this powerful 15ml formula. DM us for "
        "a quick quote! 🇰🇷"
    ),
    "manufacturer_oem": (
        "We're a cosmetic manufacturing company offering wholesale export for a wide range of "
        "products like sunscreens, eye creams, mask packs, and more! 🇰🇷 Specializing in OEM."
    ),
    "round_lab": (
        "Stocking up on Round Lab sunscreen spray! ☀️ Essential for keeping your skin protected."
        "\n\n#kbeauty #koreanskincare #sunscreen"
    ),
    "gk_seoul_probiotics": (
        "✨ Score an amazing deal on the Luna Probiotics Essential Skincare Set! ✨ Get this "
        "amazing GK Seoul set at wholesale price, perfect for your skincare routine! 🇰🇷"
    ),
    "vitamin_booster": (
        "Get ready for a refreshing vitamin boost to your skincare routine! ✨ This new Arencia "
        "Vitamin Booster Shot is here to give you that fresh and radiant glow."
        "\n\n#kbeauty #koreanskincare"
    ),
    "kr_raw_wholesale": "정품 화장품 도매 공급합니다. 세럼 토너 대량 재고 있습니다",
}


@pytest.mark.parametrize("name", sorted(OFF_TOPIC))
def test_off_topic_caption_rejected_by_keyword_filter(name):
    assert passes_keyword_filter(OFF_TOPIC[name]) is False


@pytest.mark.parametrize("name", sorted(BEAUTY))
def test_beauty_caption_still_passes_keyword_filter(name):
    assert passes_keyword_filter(BEAUTY[name]) is True


@pytest.mark.parametrize("name", sorted(OFF_TOPIC))
def test_publish_gate_rejects_off_topic_for_041(name):
    allowed, code = resolve_publish_gate(OFF_TOPIC[name], "IDN-000041")
    assert (allowed, code) == (False, "DOMAIN_CONTENT_REJECTED")


@pytest.mark.parametrize("name", sorted(BEAUTY))
def test_publish_gate_allows_beauty_for_041_and_a_beauty_category(name):
    assert resolve_publish_gate(BEAUTY[name], "IDN-000041") == (True, "PUBLISH_ALLOWED")
    assert resolve_publish_gate(
        BEAUTY[name], "IDN-000051", account_category="A_BEAUTY"
    ) == (True, "PUBLISH_ALLOWED")
