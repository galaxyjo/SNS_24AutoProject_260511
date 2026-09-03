"""
modules/interaction_engine/outbound_rules.py — 아웃바운드 Prospect 필터·스코어 (STEP 3-C, 260901)

회장 정책:
  - 대상 = 해외 화장품/뷰티 판매 사업자(외국인). 한국인/한국 기반 개인 제외.
  - 한국 거주 외국인 셀러는 대상에 포함하되 Overseas 점수에서 낮게(자연 하위 랭크).
  - 구매의향 / Reply / Inquiry / Buyer 증거는 점수에 넣지 않는다(후행 KPI).
  - 이름만으로 국적을 추정하지 않는다. bio/location/게시물 Evidence 로만 판단.
  - 애매하면(국적 UNKNOWN·점수 경계·근거 약함) 자동 제외/자동 승인 하지 않고 needs_review.

순수 함수 — Airtable/Selenium 미접촉. 입력은 크롤 단계가 만든 ProspectInfo dict.
키워드/배점은 v1(튜닝 대상). 회장이 그룹을 추가하며 조정한다.
"""

from __future__ import annotations

import re
from typing import TypedDict


class ProspectInfo(TypedDict, total=False):
    display_name: str
    profile_url: str
    bio_text: str           # 프로필 소개/intro (없으면 "")
    location_text: str      # 프로필에 표기된 도시/국가 (없으면 "")
    page_category: str      # 페이지면 카테고리 (개인이면 "")
    recent_post_text: str   # 최근 게시물 본문 합친 것 (없으면 "")
    follower_count: int     # 팔로워/친구 수 (모르면 -1)
    has_photo: bool
    is_private: bool
    has_recent_activity: bool


class RuleResult(TypedDict):
    decision: str        # "filtered_out" | "needs_review" | "scored"
    filter_reason: str   # decision != scored 일 때 사유, 아니면 ""
    score: int           # 0~100 (scored 일 때만 의미)
    score_detail: str


# ── v2 키워드 (튜닝 대상) ────────────────────────────────────────────────────

_BEAUTY_KW = (
    "cosmetic", "cosmetics", "skincare", "skin care", "k-beauty", "kbeauty",
    "beauty", "makeup", "serum", "toner", "essence", "mask pack", "sunscreen",
    "ampoule", "cushion", "lip", "cleanser", "moisturizer", "sheet mask",
    "mỹ phẩm", "dưỡng da", "kem chống nắng", "son", "화장품", "뷰티", "스킨케어",
    "마스크팩", "메이크업", "쿠션", "선크림", "앰플", "에센스",
    # K-뷰티 브랜드명 (판매글이 브랜드만 언급하는 경우 대비)
    "3ce", "laneige", "innisfree", "cosrx", "sulwhasoo", "mediheal", "missha",
    "the face shop", "etude", "tonymoly", "dr.jart", "dr jart", "some by mi",
    "anua", "beauty of joseon", "round lab", "torriden", "mixsoon", "abib",
    "d'alba", "dalba", "numbuzin", "skin1004", "isntree", "mise en scene",
)
_TRADE_KW = (
    "wholesale", "distributor", "supplier", "reseller", "retail", "import",
    "export", "dropship", "b2b", "oem", "odm", "bulk",
    # 판매 말투 (판매글에서 자주 나오는 표현)
    "accepting orders", "place your order", "pre-order", "preorder", "in stock",
    "restock", "best-selling", "best seller", "wholesale price", "price list",
    "min order", "moq", "ready stock", "limited quantities", "dm for price",
    "inbox for price", "order now", "shipping worldwide",
    "sỉ", "phân phối", "nhà phân phối", "nguồn hàng", "đại lý", "nhập khẩu",
    "giá sỉ", "bảng giá", "đặt hàng", "còn hàng", "order",
    "도매", "유통", "총판", "수입", "수출", "도매가", "주문", "재고",
)
_OTHER_INDUSTRY_KW = (
    "car for sale", "used car", "auto repair", "car repair", "vehicle",
    "real estate", "apartment for rent", "house for sale", "부동산", "매매",
    "restaurant", "food delivery", "recruitment agency", "job vacancy",
    "insurance", "보험", "loan", "대출", "여행사", "tour package",
    "phone repair", "laptop", "electronics repair",
)
_KR_LOCATION_KW = (
    "korea", "south korea", "republic of korea", "한국", "대한민국",
    "seoul", "서울", "incheon", "인천", "busan", "부산", "경기", "gyeonggi",
    "대구", "daegu", "광주", "gwangju",
)
_OVERSEAS_KW = (
    "vietnam", "viet nam", "việt nam", "thailand", "thái lan", "russia", "russian",
    "philippines", "indonesia", "malaysia", "cambodia", "myanmar", "mongolia",
    "laos", "singapore", "japan", "china", "taiwan", "usa", "u.s.", "united states",
    "europe", "dubai", "uae",
    "베트남", "태국", "러시아", "필리핀", "인도네시아", "말레이시아", "몽골", "미얀마",
)
_OVERSEAS_CUSTOMER_HINT = (
    "ship worldwide", "international shipping", "export to", "xuất khẩu",
    "giao hàng quốc tế", "수출", "해외 배송", "해외배송", "worldwide",
)
_KR_INDIVIDUAL_HINT = (
    "일상", "육아", "맘스타그램", "직장인", "취준", "여행에미치다", "먹방",
    "학생", "대학생", "회사원",
)


def _hit(text: str, kws) -> bool:
    t = (text or "").lower()
    return any(k in t for k in kws)


def _hit_word(text: str, kws) -> bool:
    """지명 키워드용 — ASCII 는 단어경계(\\b)로 매칭해 'korea' 가 'korean cosmetics' 에
    오탐되지 않게 한다. 한글 등 비ASCII 는 그대로 substring."""
    t = (text or "").lower()
    for k in kws:
        if k.isascii():
            if re.search(r"\b" + re.escape(k) + r"\b", t):
                return True
        elif k in t:
            return True
    return False


def _blob(info: ProspectInfo) -> str:
    return " ".join(str(info.get(k, "")) for k in
                    ("display_name", "bio_text", "location_text",
                     "page_category", "recent_post_text")).lower()


# ── 메인 ─────────────────────────────────────────────────────────────────────

def evaluate(
    info: ProspectInfo,
    *,
    already_seen: bool = False,
    blocklist_hit: bool = False,
    source_is_beauty_group: bool = False,
    score_cutoff: int = 55,
    review_band: int = 10,
) -> RuleResult:
    """Prospect 1명을 필터→스코어 판정한다.

    source_is_beauty_group=True (엄선된 K-뷰티 그룹 출신): 뷰티/판매 키워드가 안 잡혀도
    바로 버리지 않고 needs_review(beauty_unconfirmed) 로 보낸다. 명백한 타업종
    증거가 있을 때만 filtered_out(other_industry).
    """
    blob = _blob(info)

    # ── Hard filter ──────────────────────────────────────────────────
    if blocklist_hit:
        return _r("filtered_out", "blocklist")
    if already_seen:
        return _r("filtered_out", "duplicate")
    if info.get("is_private"):
        return _r("filtered_out", "abnormal_profile")
    if not info.get("has_photo", False) or not info.get("has_recent_activity", False):
        return _r("filtered_out", "abnormal_profile")

    beauty = _hit(blob, _BEAUTY_KW)
    trade = _hit(blob, _TRADE_KW)
    kr_loc = _hit_word(blob, _KR_LOCATION_KW)
    overseas_loc = _hit_word(blob, _OVERSEAS_KW)
    overseas_hint = _hit(blob, _OVERSEAS_CUSTOMER_HINT)
    kr_individual = _hit(blob, _KR_INDIVIDUAL_HINT) and not (beauty and trade)

    # 한국 기반 → 제외 (뷰티 키워드 유무와 무관하게 먼저 판정)
    if kr_individual:
        return _r("filtered_out", "korean_national")
    if kr_loc and not overseas_loc and not overseas_hint and not trade:
        return _r("filtered_out", "korean_based")

    # 업종 판정
    if not beauty and not trade:
        if _hit(blob, _OTHER_INDUSTRY_KW):
            return _r("filtered_out", "other_industry")
        if source_is_beauty_group:
            # 뷰티 그룹 출신 + 한국기반 아님 — 키워드 없어도 회장 검토로
            return _r("needs_review", "beauty_unconfirmed")
        return _r("filtered_out", "not_beauty")

    # ── Score ───────────────────────────────────────────────────────
    s_beauty = (15 if _hit(info.get("bio_text", ""), _BEAUTY_KW) else 0) \
        + (10 if _hit(info.get("page_category", ""), _BEAUTY_KW + _TRADE_KW) else 0) \
        + (15 if (_hit(info.get("recent_post_text", ""), _BEAUTY_KW)
                  or _hit(info.get("recent_post_text", ""), _TRADE_KW)) else 0)
    s_beauty = min(s_beauty, 40)

    if overseas_loc and not kr_loc:
        s_overseas = 30
    elif overseas_loc and kr_loc:
        s_overseas = 22
    elif kr_loc and overseas_hint:
        s_overseas = 15
    elif overseas_hint:
        s_overseas = 12
    else:
        s_overseas = 0

    fc = info.get("follower_count", -1)
    s_active = (8 if info.get("has_recent_activity") else 0) \
        + (4 if info.get("has_photo") else 0) \
        + (4 if info.get("bio_text") else 0) \
        + (4 if isinstance(fc, int) and 30 <= fc <= 200000 else 0)
    s_active = min(s_active, 20)

    s_dedup = 6 + (4 if str(info.get("profile_url", "")).startswith("https://") else 0)

    total = s_beauty + s_overseas + s_active + s_dedup
    detail = (f"beauty={s_beauty}/40 overseas={s_overseas}/30 "
              f"active={s_active}/20 dedup={s_dedup}/10 = {total}/100")

    # 국적 근거가 전혀 없음(해외/한국 둘 다 미확인) → 회장 검토
    if s_overseas == 0 and not kr_loc:
        return _r("needs_review", "overseas_unknown", total, detail)
    # 점수 경계 → 회장 검토
    if abs(total - score_cutoff) <= review_band:
        return _r("needs_review", "score_borderline", total, detail)
    if total < score_cutoff:
        return _r("filtered_out", "low_score", total, detail)
    return _r("scored", "", total, detail)


def _r(decision: str, reason: str, score: int = 0, detail: str = "") -> RuleResult:
    return {"decision": decision, "filter_reason": reason,
            "score": score, "score_detail": detail}
