"""260914 — content_filter.passes_image_filter OCR Gate Fail-closed 검증.

배경: OCR 단계 예외 시 True(통과)를 반환해, pytesseract 가 운영 venv 에 없던 기간
(6/4~9/14) 모든 이미지가 "OCR 실패 — 통과 처리"로 자동게시 경로에 들어갔다.

실제 네트워크·실제 OCR·실제 로그 기록 없음:
  - requests.get → 가짜 응답(PIL 로 만든 PNG)
  - pytesseract → sys.modules 에 가짜 모듈 주입
  - content_filter.logger → 기록용 가짜 로거

판정식: PASS = engine_ok AND image_read_ok AND no_block_pattern, 그 외 = 게시 금지.
"""

import io
import sys
from types import SimpleNamespace

import pytest

import modules.sns.content_filter as cf


# ── 공통 픽스처 ───────────────────────────────────────────────────────────────
class _Logger:
    def __init__(self):
        self.records = []

    def _add(self, level, msg):
        self.records.append((level, msg))

    def info(self, msg, *a, **k): self._add("info", msg)
    def warning(self, msg, *a, **k): self._add("warning", msg)
    def error(self, msg, *a, **k): self._add("error", msg)
    def debug(self, msg, *a, **k): self._add("debug", msg)

    def has(self, level, needle):
        return any(l == level and needle in m for l, m in self.records)


@pytest.fixture(autouse=True)
def log(monkeypatch):
    rec = _Logger()
    monkeypatch.setattr(cf, "logger", rec)
    return rec


def _png(w=400, h=400):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def image(monkeypatch):
    """requests.get 을 가짜 이미지 응답으로 교체. size 를 바꿔 호출할 수 있다."""
    state = SimpleNamespace(w=400, h=400, fail=False, calls=0)

    class _Resp:
        def __init__(self, content): self.content = content
        def raise_for_status(self): pass

    def _get(url, *a, **k):
        state.calls += 1
        if state.fail:
            raise ConnectionError("network down")
        return _Resp(_png(state.w, state.h))

    import requests
    monkeypatch.setattr(requests, "get", _get)
    return state


def _fake_tesseract(monkeypatch, *, text="", version_exc=None, ocr_exc=None, result=None):
    """가짜 pytesseract 모듈 주입. 호출 기록을 반환한다."""
    calls = SimpleNamespace(version=0, ocr=0)

    def get_tesseract_version():
        calls.version += 1
        if version_exc:
            raise version_exc
        return "5.5.0"

    def image_to_string(img, lang=None, timeout=None):
        calls.ocr += 1
        if ocr_exc:
            raise ocr_exc
        return text if result is None else result

    mod = SimpleNamespace(
        pytesseract=SimpleNamespace(tesseract_cmd=None),
        get_tesseract_version=get_tesseract_version,
        image_to_string=image_to_string,
    )
    monkeypatch.setitem(sys.modules, "pytesseract", mod)
    return calls


URL = "https://scontent.example.fbcdn.net/a.jpg"


# ── 1. OCR_PASS ───────────────────────────────────────────────────────────────
def test_normal_image_passes(monkeypatch, image, log):
    _fake_tesseract(monkeypatch, text="Fresh serum restock this week")
    assert cf.passes_image_filter(URL) is True
    assert log.has("info", "[ImageFilter] 통과")


# ── 2. OCR_BLOCK ──────────────────────────────────────────────────────────────
def test_phone_number_blocked(monkeypatch, image, log):
    _fake_tesseract(monkeypatch, text="Order now 010-1234-5678")
    assert cf.passes_image_filter(URL) is False
    assert log.has("info", "차단 키워드 감지")


def test_watermark_name_blocked(monkeypatch, image, log):
    _fake_tesseract(monkeypatch, text="M&Y GLOBAL official")
    assert cf.passes_image_filter(URL) is False


# ── 3. OCR_ERROR → 게시 금지 ─────────────────────────────────────────────────
def test_pytesseract_missing_is_error_and_blocked(monkeypatch, image, log):
    monkeypatch.setitem(sys.modules, "pytesseract", None)   # import 시 ImportError
    assert cf.passes_image_filter(URL) is False
    assert log.has("error", "OCR_ERROR")
    assert not log.has("warning", "통과 처리")               # 옛 Fail-open 문구 재발 금지


def test_tesseract_executable_missing_is_error(monkeypatch, image, log):
    class TesseractNotFoundError(EnvironmentError):
        pass
    calls = _fake_tesseract(monkeypatch, text="anything", version_exc=TesseractNotFoundError("not found"))
    assert cf.passes_image_filter(URL) is False
    assert log.has("error", "tesseract 실행 불가")
    assert calls.ocr == 0                                    # 엔진 확인 실패면 OCR 시도조차 안 함


def test_ocr_exception_is_error(monkeypatch, image, log):
    _fake_tesseract(monkeypatch, ocr_exc=RuntimeError("boom"))
    assert cf.passes_image_filter(URL) is False
    assert log.has("error", "OCR 실행 예외")


def test_ocr_timeout_is_error(monkeypatch, image, log):
    _fake_tesseract(monkeypatch, ocr_exc=RuntimeError("Tesseract process timeout"))
    assert cf.passes_image_filter(URL) is False
    assert log.has("error", "OCR_ERROR")


def test_non_string_result_is_error(monkeypatch, image, log):
    _fake_tesseract(monkeypatch, result=None and 0 or 12345)
    assert cf.passes_image_filter(URL) is False
    assert log.has("error", "결과 형식 이상")


# ── 4. OCR_EMPTY 정책 ─────────────────────────────────────────────────────────
def test_empty_text_with_engine_ok_passes(monkeypatch, image, log):
    calls = _fake_tesseract(monkeypatch, text="   \n ")
    assert cf.passes_image_filter(URL) is True
    assert calls.version == 1 and calls.ocr == 1             # 엔진 정상 실행 증거가 있어야 통과
    assert log.has("info", "통과(텍스트 없음)")


def test_empty_text_but_engine_check_failed_is_blocked(monkeypatch, image, log):
    _fake_tesseract(monkeypatch, text="", version_exc=OSError("cannot run"))
    assert cf.passes_image_filter(URL) is False
    assert log.has("error", "OCR_ERROR")


# ── 5. 기존 차단 경로 무변경 ──────────────────────────────────────────────────
def test_missing_url_still_blocked(monkeypatch, log):
    assert cf.passes_image_filter("") is False
    assert cf.passes_image_filter("not-a-url") is False


def test_download_failure_still_blocked(monkeypatch, image, log):
    image.fail = True
    assert cf.passes_image_filter(URL) is False
    assert log.has("warning", "다운로드 실패")


def test_small_image_still_blocked(monkeypatch, image, log):
    image.w, image.h = 200, 200
    calls = _fake_tesseract(monkeypatch, text="fine")
    assert cf.passes_image_filter(URL) is False
    assert calls.ocr == 0


# ── 6. 상태 함수 직접 단언 ────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("serum restock", "OCR_PASS"),
    ("call 010-1234-5678", "OCR_BLOCK"),
    ("", "OCR_EMPTY"),
])
def test_state_function(monkeypatch, text, expected):
    from PIL import Image
    _fake_tesseract(monkeypatch, text=text)
    state, _ = cf._ocr_image_state(Image.new("RGB", (400, 400)))
    assert state == expected


def test_crawler_still_uses_this_gate():
    import modules.sns.facebook_crawler as fc
    assert fc.passes_image_filter is cf.passes_image_filter


# ── 7. 실행파일 경로 회귀 방지 ────────────────────────────────────────────────
# 260914: 편집 중 r"...\tesseract.exe" 의 "\t" 가 TAB 문자로 바뀌어 경로가 깨졌다.
# pytesseract 를 Mock 하는 테스트들은 이를 잡지 못하므로 경로 값 자체를 단언한다.
EXPECTED_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def test_tesseract_path_has_no_control_chars():
    assert cf._TESSERACT_CMD == EXPECTED_TESSERACT
    assert "\t" not in cf._TESSERACT_CMD                     # 실제 TAB 문자 부재 확인
    assert cf._TESSERACT_CMD.endswith(r"\tesseract.exe")


@pytest.mark.skipif(
    not __import__("os").path.exists(EXPECTED_TESSERACT),
    reason="이 머신에 Tesseract 가 설치돼 있지 않음",
)
def test_tesseract_path_exists_on_this_machine():
    import os
    assert os.path.exists(cf._TESSERACT_CMD)
