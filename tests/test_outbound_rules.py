"""STEP 3-C (260901) — modules.interaction_engine.outbound_rules.evaluate 검증. 순수 함수."""

from modules.interaction_engine import outbound_rules as r

_BASE = {
    "display_name": "Anna Nguyen",
    "profile_url": "https://www.facebook.com/anna.kbeauty",
    "bio_text": "Korean cosmetics wholesale supplier, ship worldwide",
    "location_text": "Ho Chi Minh, Vietnam",
    "page_category": "Beauty, cosmetic & personal care",
    "recent_post_text": "New arrival: Korean serum and sunscreen wholesale price",
    "follower_count": 6000,
    "has_photo": True,
    "is_private": False,
    "has_recent_activity": True,
}


def _info(**over):
    d = dict(_BASE)
    d.update(over)
    return d


def test_blocklist_hit_filtered():
    out = r.evaluate(_info(), blocklist_hit=True)
    assert out["decision"] == "filtered_out"
    assert out["filter_reason"] == "blocklist"


def test_duplicate_filtered():
    out = r.evaluate(_info(), already_seen=True)
    assert out["decision"] == "filtered_out" and out["filter_reason"] == "duplicate"


def test_private_profile_filtered():
    out = r.evaluate(_info(is_private=True))
    assert out["decision"] == "filtered_out" and out["filter_reason"] == "abnormal_profile"


def test_no_photo_or_inactive_filtered():
    assert r.evaluate(_info(has_photo=False))["filter_reason"] == "abnormal_profile"
    assert r.evaluate(_info(has_recent_activity=False))["filter_reason"] == "abnormal_profile"


def test_no_signal_and_not_beauty_group_filtered():
    out = r.evaluate(_info(bio_text="hello", page_category="", display_name="Bob",
                           location_text="", recent_post_text="good morning everyone"))
    assert out["decision"] == "filtered_out" and out["filter_reason"] == "not_beauty"


def test_other_industry_evidence_filtered():
    out = r.evaluate(_info(bio_text="car repair shop", page_category="Automotive",
                           recent_post_text="engine oil change service", display_name="Bob",
                           location_text=""), source_is_beauty_group=True)
    assert out["decision"] == "filtered_out" and out["filter_reason"] == "other_industry"


def test_beauty_group_no_keyword_goes_to_review():
    # 뷰티 그룹 출신 + 뷰티/판매 키워드 없음 + 타업종 증거 없음 → needs_review
    out = r.evaluate(_info(bio_text="", page_category="", display_name="Mooncher Kim",
                           location_text="", recent_post_text="Now accepting for 3CE! limited quantities"),
                     source_is_beauty_group=True)
    assert out["decision"] in ("needs_review", "scored")
    # "3CE" + "accepting" + "limited quantities" 가 이제 키워드에 잡혀 최소 review 이상


def test_brand_only_post_recognized_as_beauty():
    out = r.evaluate(_info(bio_text="", page_category="", location_text="Manila, Philippines",
                           recent_post_text="COSRX and Anua restock, order now",
                           display_name="Shop PH"), source_is_beauty_group=True)
    assert out["decision"] in ("scored", "needs_review")
    assert out["filter_reason"] != "not_beauty"


def test_korean_individual_filtered():
    out = r.evaluate(_info(display_name="김서연", bio_text="일상 육아 맘스타그램",
                           location_text="서울", page_category="", recent_post_text="오늘 날씨"))
    assert out["decision"] == "filtered_out" and out["filter_reason"] in ("korean_national", "not_beauty")


def test_korea_based_domestic_seller_filtered():
    # 화장품 언급은 있으나 무역/해외 신호 전무 + 한국 위치 → korean_based
    out = r.evaluate(_info(bio_text="화장품 스킨케어 좋아요", location_text="서울",
                           page_category="", recent_post_text="신상 화장품 후기",
                           display_name="박지민"))
    assert out["decision"] == "filtered_out" and out["filter_reason"] == "korean_based"


def test_overseas_beauty_seller_scored_high():
    out = r.evaluate(_info())
    assert out["decision"] == "scored"
    assert out["score"] >= 55
    assert "beauty=" in out["score_detail"]


def test_korea_resident_foreign_seller_lower_overseas():
    # 한국 거주 + 해외 고객 명시 → 대상 유지, overseas 점수만 낮음
    out = r.evaluate(_info(location_text="Incheon, Korea",
                           bio_text="Korean cosmetics wholesale, export to Vietnam"))
    assert out["decision"] in ("scored", "needs_review")
    assert "overseas=15" in out["score_detail"] or "overseas=22" in out["score_detail"]


def test_unknown_nationality_needs_review():
    out = r.evaluate(_info(location_text="", bio_text="cosmetics wholesale supplier",
                           recent_post_text="wholesale cosmetics"))
    assert out["decision"] == "needs_review"
    assert out["filter_reason"] == "overseas_unknown"


def test_borderline_score_needs_review():
    out = r.evaluate(_info(), score_cutoff=100, review_band=100)
    assert out["decision"] == "needs_review" and out["filter_reason"] == "score_borderline"
