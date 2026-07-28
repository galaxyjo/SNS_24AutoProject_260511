"""modules/common/webhook_signature.py — Meta Webhook X-Hub-Signature-256 검증(ERR-082).

Meta 공식 규격: 헤더 형식은 "sha256=<raw body의 HMAC-SHA256 hex digest>".
Raw Body(파싱 전 원본 bytes) 기준으로 계산해야 하며, JSON 재직렬화 결과로 계산하면
공백/키 순서 차이로 불일치가 발생할 수 있다 — 반드시 request.get_data() 원본을 그대로 넘길 것.

Fail-closed: 아래 실패 조건 중 하나라도 해당하면 False를 반환한다(예외를 던지지 않음).
Secret·Raw Body·Signature 원문·계산된 Digest는 로그에 출력하지 않는다(호출부 책임이지만
이 모듈 자체도 어떤 값도 print/logger 호출을 하지 않아 노출 경로 자체가 없다).
"""

import hmac
import hashlib

_SIGNATURE_PREFIX = "sha256="
_DIGEST_HEX_LENGTH = hashlib.sha256().digest_size * 2  # 64


def verify_meta_signature(raw_body: bytes, signature_header: str | None, app_secret: str | None) -> bool:
    """Raw Body가 app_secret으로 서명한 X-Hub-Signature-256 헤더와 일치하는지 검증한다.

    다음 중 하나라도 해당하면 False:
    - signature_header가 None/빈 문자열
    - "sha256=" 접두어 누락
    - digest 부분 길이가 64자(SHA-256 hex)가 아님
    - digest 부분이 유효한 hex 문자열이 아님
    - app_secret이 None/빈 문자열
    - 계산된 digest와 불일치
    """
    if not signature_header:
        return False
    if not app_secret:
        return False
    if not signature_header.startswith(_SIGNATURE_PREFIX):
        return False

    digest_hex = signature_header[len(_SIGNATURE_PREFIX):]
    if len(digest_hex) != _DIGEST_HEX_LENGTH:
        return False
    try:
        expected_digest = bytes.fromhex(digest_hex)
    except ValueError:
        return False

    computed_digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).digest()

    return hmac.compare_digest(computed_digest, expected_digest)
