"""tests/test_webhook_signature.py — modules/common/webhook_signature.py 단위테스트(ERR-082).

Meta 공식 규격(X-Hub-Signature-256: sha256=<raw body HMAC-SHA256 hex digest>) 검증기의
정상/실패 케이스 10종. Flask Route와 무관한 순수함수 레벨 테스트."""

import hashlib
import hmac

from modules.common.webhook_signature import verify_meta_signature

SECRET = "unit-test-secret"


def _sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_valid_signature_passes():
    body = b'{"object":"instagram"}'
    assert verify_meta_signature(body, _sign(body), SECRET) is True


def test_missing_header_rejected():
    body = b'{"a":1}'
    assert verify_meta_signature(body, None, SECRET) is False


def test_empty_header_rejected():
    body = b'{"a":1}'
    assert verify_meta_signature(body, "", SECRET) is False


def test_wrong_prefix_rejected():
    body = b'{"a":1}'
    bad_prefix = "sha1=" + hmac.new(SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert verify_meta_signature(body, bad_prefix, SECRET) is False


def test_digest_length_error_rejected():
    body = b'{"a":1}'
    assert verify_meta_signature(body, "sha256=abcd1234", SECRET) is False


def test_non_hex_digest_rejected():
    body = b'{"a":1}'
    bad_hex = "sha256=" + ("zz" * 32)  # 64자 길이는 맞지만 hex 아님
    assert verify_meta_signature(body, bad_hex, SECRET) is False


def test_wrong_secret_rejected():
    body = b'{"a":1}'
    assert verify_meta_signature(body, _sign(body, SECRET), "other-secret") is False


def test_tampered_body_rejected():
    body = b'{"a":1}'
    sig = _sign(body)
    assert verify_meta_signature(body + b"x", sig, SECRET) is False


def test_unicode_and_whitespace_body_verified_correctly():
    body = '{"text": "  안녕하세요 \n 공백/유니코드 이모지 포함  "}'.encode("utf-8")
    assert verify_meta_signature(body, _sign(body), SECRET) is True


def test_missing_secret_rejected():
    body = b'{"a":1}'
    sig = _sign(body)
    assert verify_meta_signature(body, sig, "") is False
    assert verify_meta_signature(body, sig, None) is False
