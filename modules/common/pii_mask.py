# modules/common/pii_mask.py
# Telegram/로그용 공용 PII 마스킹 유틸 — ERR-066에서 DM 채널(dm_auto_reply.py)용으로
# 만들었던 걸 260716 댓글 채널(comment_auto_reply.py)도 재사용하며 공용 모듈로 추출.
# modules.dm 패키지 안에 두면 modules.dm.__init__ → dm_receiver → comment_auto_reply →
# modules.dm.dm_auto_reply 순으로 순환 임포트가 발생해 여기로 분리했다.

import re

_PII_PATTERNS = [
    re.compile(r'01[0-9]-?\d{3,4}-?\d{4}'),
    re.compile(r'\d{2,4}-\d{3,4}-\d{4}'),
    re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
]


def mask_igsid(igsid: str) -> str:
    return f"{igsid[:4]}***" if igsid and len(igsid) > 4 else "***"


def telegram_preview(text: str, limit: int = 20) -> str:
    masked = text or ""
    for pat in _PII_PATTERNS:
        masked = pat.sub("***", masked)
    return masked[:limit]
