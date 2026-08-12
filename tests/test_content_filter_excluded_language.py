"""tests/test_content_filter_excluded_language.py — 260812 ERR-033/A003·A005 회귀 테스트.
_has_excluded_language()를 "글자 1개라도 있으면 차단"에서 "비율 기준(5%)"으로 바꾼
변경 검증. 네트워크 호출(GoogleTranslator) 없이 순수 함수만 테스트한다.

임계치 5%는 실측 기반:
  - A003/A005 실제 게시글(한국어/영어 위주 + 외국어 글자 1개 섞임) ratio ≈ 0.56%
  - 정상 베트남어 문장 샘플 4종 ratio ≈ 15~28% (아래 test_realistic_vietnamese_posts_still_excluded)
20%는 정상 베트남어 문장 범위와 겹쳐 채택하지 않았다."""

import pytest

from modules.sns.content_filter import _has_excluded_language, _excluded_language_ratio


def test_fully_vietnamese_post_still_excluded():
    """ERR-033 원 사례 — 전체가 베트남어인 게시글은 그대로 차단되어야 한다."""
    text = "Khánh Sun cung cấp NMN 36000 – Hỗ trợ sức khỏe toàn diện cho gia đình bạn"
    assert _has_excluded_language(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Chào các bạn, mình có hàng mới về nhé, ai cần inbox mình nha",
        "Hàng về liên tục, giá sỉ tốt nhất thị trường, ship toàn quốc",
        "Số lượng có hạn, đặt hàng ngay hôm nay để không bỏ lỡ ưu đãi",
    ],
)
def test_realistic_vietnamese_posts_still_excluded(text):
    """다양한 정상 베트남어 문장(성조부호 비율 15~28%)도 여전히 차단되어야 한다."""
    assert _has_excluded_language(text) is True


def test_korean_wholesale_post_with_stray_foreign_chars_now_passes():
    """A003/A005 실제 사례 — 한국어/영어 위주 정상 도매 게시글에 외국어 글자가
    극소량(임계치 미만) 섞여도 더 이상 통째로 차단되지 않아야 한다."""
    text = (
        "김정현 5월 26일 We can supply Arocell. If you are interested, "
        "please contact me. I will respond kindly. "
        "올데어코리아에서는 한국의 다수 브랜드 화장품을 수출 및 도매로 "
        "공급하고 있습니다. 아로셀 공급 가능합니다. 문의 환영합니다. "
        "감사합니다 mộ"  # 임계치 미만 소량의 베트남어 글자 1개만 섞인 상황 재현
    )
    assert _excluded_language_ratio(text) < 0.01
    assert _has_excluded_language(text) is False


def test_pure_korean_english_text_not_excluded():
    text = "국내 최대 화장품 도매 공급업체, wholesale cosmetic supply, MOQ 100개"
    assert _has_excluded_language(text) is False


def test_empty_text_not_excluded():
    assert _has_excluded_language("") is False
    assert _excluded_language_ratio("") == 0.0


def test_ratio_just_below_threshold_not_excluded():
    # 20글자 중 excluded 글자 1개 = 5% → 임계치와 같으면 차단 안 함(> 비교, >= 아님)
    text = "가" * 19 + "à"
    assert _excluded_language_ratio(text) == 0.05
    assert _has_excluded_language(text) is False


def test_ratio_just_above_threshold_excluded():
    # 19글자 중 excluded 글자 1개 ≈ 5.26% → 임계치 초과라 차단
    text = "가" * 18 + "à"
    assert _excluded_language_ratio(text) > 0.05
    assert _has_excluded_language(text) is True
