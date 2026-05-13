"""
tests/test_smoke_crawler.py — facebook_crawler 유닛 테스트

extract_image_url() 로직을 Selenium 없이 mock으로 검증.
"""

import pytest
from selenium.webdriver.common.by import By

from modules.sns.facebook_crawler import extract_image_url, _PROFILE_PATTERNS


# ── Mock 헬퍼 ─────────────────────────────────────────────────────────────────

class _Img:
    """Selenium WebElement img 모의 객체."""
    def __init__(self, src=None, data_src=None):
        self._attrs = {"src": src, "data-src": data_src}

    def get_attribute(self, name):
        return self._attrs.get(name)


class _Element:
    """Selenium WebElement post 모의 객체."""
    def __init__(self, *imgs):
        self._imgs = list(imgs)

    def find_elements(self, by, value):
        return self._imgs


class _Driver:
    """Selenium WebDriver 모의 객체."""
    def __init__(self, width=600, height=400):
        self._w = width
        self._h = height

    def execute_script(self, script, img):
        if "naturalWidth" in script:
            return self._w
        return self._h


_VALID = "https://scontent.cdninstagram.com/v/photo.jpg"
_VALID2 = "https://scontent.fgmp1-1.fna.fbcdn.net/v/img2.jpg"


# ── 기본 동작 ─────────────────────────────────────────────────────────────────

def test_no_images_returns_empty():
    assert extract_image_url(_Element()) == ""


def test_valid_scontent_url_returned():
    elem = _Element(_Img(src=_VALID))
    assert extract_image_url(elem) == _VALID


def test_data_src_fallback():
    """src 없고 data-src 있을 때 data-src 반환."""
    elem = _Element(_Img(src=None, data_src=_VALID))
    assert extract_image_url(elem) == _VALID


def test_both_src_and_data_src_uses_src():
    elem = _Element(_Img(src=_VALID, data_src=_VALID2))
    assert extract_image_url(elem) == _VALID


# ── URL 필터링 ────────────────────────────────────────────────────────────────

def test_http_url_excluded():
    http_url = "http://scontent.cdninstagram.com/photo.jpg"
    assert extract_image_url(_Element(_Img(src=http_url))) == ""


def test_non_scontent_url_excluded():
    assert extract_image_url(_Element(_Img(src="https://example.com/photo.jpg"))) == ""


def test_empty_src_excluded():
    assert extract_image_url(_Element(_Img(src=""))) == ""


def test_none_src_and_none_data_src_excluded():
    assert extract_image_url(_Element(_Img(src=None, data_src=None))) == ""


# ── 프로필 사진 패턴 필터링 ───────────────────────────────────────────────────

@pytest.mark.parametrize("pattern", _PROFILE_PATTERNS)
def test_profile_pattern_excluded(pattern):
    url = f"https://scontent.cdninstagram.com/{pattern}/photo.jpg"
    assert extract_image_url(_Element(_Img(src=url))) == ""


def test_non_profile_pattern_not_excluded():
    url = "https://scontent.cdninstagram.com/p800x600/photo.jpg"
    assert extract_image_url(_Element(_Img(src=url))) == url


# ── driver 크기 필터링 ────────────────────────────────────────────────────────

def test_large_image_with_driver_returned():
    elem = _Element(_Img(src=_VALID))
    assert extract_image_url(elem, driver=_Driver(width=800, height=600)) == _VALID


def test_small_width_with_driver_excluded():
    elem = _Element(_Img(src=_VALID))
    assert extract_image_url(elem, driver=_Driver(width=50, height=600)) == ""


def test_small_height_with_driver_excluded():
    elem = _Element(_Img(src=_VALID))
    assert extract_image_url(elem, driver=_Driver(width=800, height=50)) == ""


def test_zero_size_with_driver_not_excluded():
    """naturalWidth=0 은 미로드 상태 — 제외하지 않는다."""
    elem = _Element(_Img(src=_VALID))
    assert extract_image_url(elem, driver=_Driver(width=0, height=0)) == _VALID


def test_driver_exception_falls_back_to_returning_url():
    """execute_script 오류 시에도 URL 반환."""
    class _BrokenDriver:
        def execute_script(self, *args):
            raise RuntimeError("webdriver error")

    elem = _Element(_Img(src=_VALID))
    assert extract_image_url(elem, driver=_BrokenDriver()) == _VALID


# ── 다중 이미지 선택 ──────────────────────────────────────────────────────────

def test_first_valid_url_returned_from_multiple():
    profile = f"https://scontent.cdninstagram.com/p40x40/thumb.jpg"
    elem = _Element(_Img(src=profile), _Img(src=_VALID), _Img(src=_VALID2))
    assert extract_image_url(elem) == _VALID


def test_all_profile_images_returns_empty():
    imgs = [_Img(src=f"https://scontent.cdninstagram.com/{p}/x.jpg") for p in _PROFILE_PATTERNS]
    assert extract_image_url(_Element(*imgs)) == ""


def test_mixed_small_and_large_with_driver():
    """첫 이미지 소형, 두 번째 이미지 정상 → 두 번째 반환."""
    elem = _Element(_Img(src=_VALID), _Img(src=_VALID2))

    call_count = [0]
    class _SelectiveDriver:
        def execute_script(self, script, img):
            call_count[0] += 1
            # 첫 번째 img(VALID)는 소형, 두 번째(VALID2)는 정상
            if call_count[0] <= 2:
                return 50   # width/height 모두 50 → 제외
            return 800

    assert extract_image_url(elem, driver=_SelectiveDriver()) == _VALID2
