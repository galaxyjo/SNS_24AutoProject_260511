import os
from deep_translator import GoogleTranslator
import re
from modules.common.logger import get_logger

logger = get_logger(__name__)

# 키워드 목록
KEYWORDS = [
    "wholesale", "export", "cosmetic", "k-beauty", "kbeauty",
    "skincare", "distributor", "moq", "supply", "btob", "b2b",
    "koreacosmetic", "serum", "toner", "essence", "oem", "odm", "makeup",
    # 한국어 키워드
    "도매", "화장품", "스킨케어", "코스메틱", "유통", "벌크", "재고",
    "수출", "총판", "공급", "선크림", "세럼", "토너", "에센스",
]

# 브랜드 allowlist — KEYWORDS 와 별도 관리
BRAND_ALLOWLIST = [
    "snuggle",
]

# 캡션 텍스트 기준 차단 브랜드 — OCR 없이 텍스트 매칭으로 차단
# "lily"는 범용 단어이므로 오탐 주의 (필요 시 제거 가능)
CAPTION_BLOCKLIST = [
    "coslife",
    "lily",
]

# 중국어/베트남어 유니코드 범위
def _has_excluded_language(text: str) -> bool:
    chinese = any('一' <= c <= '鿿' for c in text)
    vietnamese = any(c in 'àáâãèéêìíòóôõùúýăđơưạảấầẩẫậắặẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ' for c in text.lower())
    return chinese or vietnamese

# 한글 비율 감지
def _korean_ratio(text: str) -> float:
    if not text:
        return 0.0
    korean = sum(1 for c in text if '가' <= c <= '힣')
    return korean / len(text)

# 번역 + 언어 필터
def detect_and_translate(text: str) -> str:
    if not text:
        return ""
    if _has_excluded_language(text):
        return ""
    try:
        # 한글 비율 높으면 source=ko 명시 (auto가 한글 혼용 시 번역 누락)
        src = 'ko' if _korean_ratio(text) > 0.2 else 'auto'
        text = GoogleTranslator(source=src, target='en').translate(text[:4000])
    except Exception:
        return ""
    return text

# 계정 무관 공통 차단 — Track B-1D(260731) Global Safety Gate로 추출
def _passes_global_safety(text: str) -> bool:
    lower = text.lower()
    if any(bl in lower for bl in CAPTION_BLOCKLIST):
        logger.info(f"[CaptionBlocklist] 차단 감지 — 제외")
        return False
    return True


# 키워드 필터 — Track A(PRODUCT) Domain Gate
def passes_keyword_filter(text: str) -> bool:
    lower = text.lower()
    if not _passes_global_safety(text):
        return False
    return (
        any(kw in lower for kw in KEYWORDS)
        or any(br in lower for br in BRAND_ALLOWLIST)
    )


# ── Account Domain Routing (Track B-1D, 260731) ─────────────────────────────
# Account_Registry 실측(260731) 기준 — 등록된 계정만 허용, 그 외 전부 Fail-closed.
ACCOUNT_DOMAIN_POLICY = {
    "IDN-000041": "PRODUCT",      # yuna18253 — 화장품 도매
    "IDN-000036": "AI_CONTENT",   # aijomoojin — Track B AI 생성 콘텐츠
}


_AI_CONTENT_REQUIRED_ACCOUNT = "IDN-000036"
_AI_CONTENT_REQUIRED_PERSONA = "PER-002"


def passes_ai_content_gate_v0(
    caption: str,
    account_code_ref: str,
    source_url: str,
    persona_code: str,
    required_language: str = "",
) -> tuple[bool, str]:
    """260801 AI_CONTENT Gate v0/v1(최소 구현) — GPT 검수 승인 조건 5개 + 언어일치(v1)를 확인한다.

    복잡한 키워드 사전·정책 엔진·점수 모델은 만들지 않는다(금지 항목). Gemini
    Safety는 caption_generator.check_caption_safety()를 REUSE하며, 이미 생성된
    caption을 재생성하지 않고 별도 1회 안전확인만 한다.

    260801 6E — 실측 오사고(영어 게시) 재발방지: Persona_Profile.language(예: "ko")를
    호출자가 전달하면, 기존 _korean_ratio() 임계값(caption_generator.detect_and_translate와
    동일 기준 0.2)으로 caption 실제 언어가 요구언어와 맞는지 확인한다. required_language가
    빈 값이면(기존 호출부) 이 검사를 건너뛴다 — 하위호환."""
    if account_code_ref != _AI_CONTENT_REQUIRED_ACCOUNT:
        return False, "AI_CONTENT_ACCOUNT_MISMATCH"
    if persona_code != _AI_CONTENT_REQUIRED_PERSONA:
        return False, "AI_CONTENT_PERSONA_MISMATCH"
    if not caption or not caption.strip():
        return False, "AI_CONTENT_EMPTY_CAPTION"
    if not source_url or not source_url.strip():
        return False, "AI_CONTENT_NO_SOURCE"
    if required_language.strip().lower() == "ko" and _korean_ratio(caption) <= 0.2:
        return False, "AI_CONTENT_LANGUAGE_MISMATCH"

    from modules.sns.caption_generator import check_caption_safety

    safe, reason = check_caption_safety(caption)
    if not safe:
        return False, f"AI_CONTENT_SAFETY_BLOCKED:{reason}"

    return True, "PUBLISH_ALLOWED"


def resolve_publish_gate(
    caption: str,
    account_code_ref: str,
    *,
    source_url: str = "",
    persona_code: str = "",
    required_language: str = "",
) -> tuple[bool, str]:
    """발행 직전 계정별 콘텐츠 Gate.

    Identity 검증은 이 함수의 책임이 아니다 — Caller(launcher/main.py)가 이미
    account_code_ref의 Identity를 검증한 뒤에만 호출한다는 전제(Track B-1E, 260731,
    airtable_repository.py/main.py의 기존 Identity Gate와 책임 중복 방지).

    순서: Global Safety → Domain Routing → Domain Gate.
    반환: (허용여부, 결과코드) — 결과코드는 다음 중 하나.
      GLOBAL_SAFETY_REJECTED / UNKNOWN_DOMAIN / DOMAIN_GATE_NOT_READY /
      DOMAIN_CONTENT_REJECTED / PUBLISH_ALLOWED / PUBLISH_GATE_INTERNAL_ERROR

    source_url/persona_code/required_language는 AI_CONTENT 도메인 전용 선택
    인자(260801 Gate v0/v1)다 — PRODUCT 도메인 기존 호출부(2-인자)는 그대로
    동작한다(하위호환)."""
    try:
        account_code_ref = (account_code_ref or "").strip()
        caption = caption or ""

        if not _passes_global_safety(caption):
            return False, "GLOBAL_SAFETY_REJECTED"

        domain = ACCOUNT_DOMAIN_POLICY.get(account_code_ref)
        if domain is None:
            return False, "UNKNOWN_DOMAIN"

        if domain == "PRODUCT":
            if not passes_keyword_filter(caption):
                return False, "DOMAIN_CONTENT_REJECTED"
            return True, "PUBLISH_ALLOWED"

        if domain == "AI_CONTENT":
            return passes_ai_content_gate_v0(
                caption, account_code_ref, source_url, persona_code, required_language
            )

        return False, "UNKNOWN_DOMAIN"
    except Exception as exc:
        # Blocklist 등 콘텐츠 안전규칙 위반(GLOBAL_SAFETY_REJECTED)과 구분되는
        # Router 내부 오류 전용 코드 — 원인 불명 상태를 안전규칙 위반으로 오분류하지 않는다.
        logger.warning(f"[PublishGate] Router 내부 예외 — Fail-closed | {exc}")
        return False, "PUBLISH_GATE_INTERNAL_ERROR"

# 연락처/회사명 제거
def clean_contact_info(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    skip_patterns = re.compile(
        r'(kakaotalk|wechat|line\s*:|instagram\s*:|facebook\s*:|email\s*:|'
        r'http[s]?://|www\.|@\w+|allthere|alltherekorea)',
        re.IGNORECASE
    )
    for line in lines:
        if skip_patterns.search(line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def clean_fb_metadata(text: str) -> str:
    """Facebook UI 잔여물 제거 — 작성자명·경과시간·구분점(·) 헤더 행 삭제."""
    lines = text.splitlines()
    # "이름\n숫자분/시간/일 ·" 형태 앞 2~3줄 감지 후 제거
    _time_pat = re.compile(r'^\s*\d+\s*(분|시간|일|주|개월)\s*[·•]?\s*$')
    _dot_pat   = re.compile(r'^\s*[·•]\s*$')
    _comment_pat = re.compile(r'^.{1,30}\s*(이름으로\s*댓글\s*달기|으로\s*댓글\s*달기)')
    _ui_pat = re.compile(
        r'^\s*(원본\s*보기|번역\s*평가하기|번역\s*평가|좋아요|댓글\s*달기|공유하기|저장)\s*$'
    )
    cleaned = []
    skip_next = False
    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
        # 경과시간 줄이면 바로 앞 줄(이름)도 소급 제거
        if _time_pat.match(line):
            if cleaned:
                cleaned.pop()
            continue
        if _dot_pat.match(line):
            continue
        if _comment_pat.match(line):
            continue
        if _ui_pat.match(line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _get_contact_mapping():
    return {
        "kakao": os.getenv("MY_KAKAO", "").strip(),
        "instagram": os.getenv("MY_INSTAGRAM", "").strip(),
        "email": os.getenv("MY_EMAIL", "").strip(),
        "line": os.getenv("MY_LINE", "").strip(),
        "whatsapp": os.getenv("MY_WHATSAPP", "").strip(),
        "zalo": os.getenv("MY_ZALO", "").strip(),
    }


def replace_contacts(text: str) -> str:
    """줄 단위로 플랫폼 연락처 패턴 감지 → 내 값으로 교체, 내 값 없으면 줄 제거."""
    if not text:
        return text

    from dotenv import load_dotenv
    load_dotenv(override=True)
    contacts = _get_contact_mapping()

    # (key, 패턴, 출력 레이블)
    # [^\n]* 로 앞 전화번호/이름 포함 줄 전체 매칭
    platform_patterns = [
        ("zalo",      r"(?i)[^\n]*(zalo)[:\s]*([\+\d]+)",                                      "Zalo"),
        ("whatsapp",  r"(?i)[^\n]*(whatsapp|wa)[:\s]*([\+\d]+)",                               "WhatsApp"),
        ("kakao",     r"(?i)[^\n]*(kakaotalk|kakao|카카오톡|카톡)[:\s]*(\S+)",                 "KakaoTalk"),
        ("line",      r"(?i)[^\n]*(line[\s]*id|line)[:\s]*(\S+)",                              "Line"),
        ("instagram", r"(?i)[^\n]*(instagram|insta|ig)[:\s]*@?([A-Za-z0-9._]+)",              "Instagram"),
        ("email",     r"(?i)[^\n]*(email|이메일|mail)[:\s]*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})", "Email"),
    ]

    result_lines = []
    for line in text.splitlines():
        matched = False
        for key, pattern, label in platform_patterns:
            if re.search(pattern, line):
                my_val = contacts.get(key, "").strip()
                if my_val:
                    if label == "Instagram":
                        result_lines.append(f"Instagram: @{my_val}")
                    else:
                        result_lines.append(f"{label}: {my_val}")
                # my_val 없으면 줄 제거
                matched = True
                break
        if not matched:
            result_lines.append(line)

    return "\n".join(result_lines).strip()


# ── 이미지 필터 ───────────────────────────────────────────────────────────────

_IMAGE_BLOCK_KEYWORDS = [
    r'\d{3,4}[-\s]?\d{3,4}[-\s]?\d{4}',  # 전화번호 패턴
    r'zalo', r'kakao', r'whatsapp', r'wechat', r'line\s*id',
    r'@[a-zA-Z0-9_.]+',
    r'aurora\s*shop', r'coslife', r'everglow', r'kcosmetic',
    r'damoa', r'vtk\s*cos', r'피터박',
    r'm&y\s*global',
]


def passes_image_filter(image_url: str) -> bool:
    """이미지 OCR로 워터마크/연락처/회사로고 감지 → True=통과, False=차단"""
    import requests as _req
    from PIL import Image, ImageEnhance
    from io import BytesIO

    if not image_url or not image_url.startswith("http"):
        logger.info("[ImageFilter] image_url 없음 — 차단")
        return False

    try:
        resp = _req.get(image_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception as exc:
        logger.warning(f"[ImageFilter] 다운로드 실패 — 차단 | {exc}")
        return False

    w, h = img.size
    if w < 300 or h < 300:
        logger.info(f"[ImageFilter] 이미지 너무 작음 {w}x{h} — 차단")
        return False

    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        img_ocr = img.resize((w * 2, h * 2), Image.LANCZOS)
        img_ocr = img_ocr.convert("L")
        img_ocr = ImageEnhance.Contrast(img_ocr).enhance(2.0)
        ocr_text = pytesseract.image_to_string(img_ocr, lang="eng").lower()
    except Exception as exc:
        logger.warning(f"[ImageFilter] OCR 실패 — 통과 처리 | {exc}")
        return True

    for pattern in _IMAGE_BLOCK_KEYWORDS:
        if re.search(pattern, ocr_text, re.IGNORECASE):
            logger.info(f"[ImageFilter] 차단 키워드 감지: {pattern} — 차단")
            return False

    logger.info(f"[ImageFilter] 통과 | {w}x{h}")
    return True
