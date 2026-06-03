import os
from deep_translator import GoogleTranslator
import re

# 키워드 목록
KEYWORDS = [
    "wholesale", "export", "cosmetic", "k-beauty", "kbeauty",
    "skincare", "distributor", "moq", "supply", "btob", "b2b",
    "koreacosmetic", "serum", "toner", "essence", "oem", "odm", "makeup",
]

# 브랜드 allowlist — KEYWORDS 와 별도 관리
BRAND_ALLOWLIST = [
    "snuggle",
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
    if _korean_ratio(text) > 0.3:
        try:
            text = GoogleTranslator(source='ko', target='en').translate(text[:4000])
        except Exception:
            return ""
    return text

# 키워드 필터
def passes_keyword_filter(text: str) -> bool:
    lower = text.lower()
    return (
        any(kw in lower for kw in KEYWORDS)
        or any(br in lower for br in BRAND_ALLOWLIST)
    )

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
