"""
modules/common/gemini_failure_diag.py — Gemini 호출 실패 진단 1단계 (261105 설계, 회장 승인: 기록+알림만)

설계: docs/design/GEMINI_FAILURE_DIAGNOSTICS_DESIGN_261105.md
429/401/403/5xx 예외에서 Allowlist 필드만 뽑아 진단 로그 1줄을 남기고, 마지막 시도 실패 때 오류 원장
(db/error_events.db)에 기록한다. 한도 0(GEMINI_QUOTA_ZERO)·인증 실패(GEMINI_AUTH)만 계정(페르소나)당 하루 1회 Slack.

재시도·반환값·상태 변경은 하지 않는다. 어떤 실패도 예외로 전파하지 않는다(호출자 흐름 불변).
키·프롬프트·응답 본문은 저장하지 않는다(필드 Allowlist + safe_text).
참고: research_to_topic_adapter._extract_gemini_quota_fields 와 같은 구조를 읽지만, 그 모듈은
content_package_builder 를 import 하므로(순환) 여기서 별도로 구현했다.
"""

from datetime import datetime, timedelta
from typing import Callable, Optional

from modules.common import error_events as _ev
from modules.common.logger import get_logger

logger = get_logger(__name__)

GEMINI_QUOTA_ZERO = "GEMINI_QUOTA_ZERO"
GEMINI_RATE = "GEMINI_RATE"
GEMINI_AUTH = "GEMINI_AUTH"
GEMINI_TRANSIENT = "GEMINI_TRANSIENT"

_ALERT_CLASSES = frozenset({GEMINI_QUOTA_ZERO, GEMINI_AUTH})
_FIELDS = ("quota_metric", "quota_id", "quota_location", "quota_limit_value", "consumer", "retry_delay", "reason")


def extract_fields(exc: Exception) -> dict:
    """예외에서 http_code 와 Allowlist 필드만 최선노력으로 추출한다(없으면 빈 문자열)."""
    out = {"http_code": getattr(exc, "code", None), **{k: "" for k in _FIELDS}}
    details = getattr(exc, "details", None)
    items = details.get("error", {}).get("details") if isinstance(details, dict) else None
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("@type", ""))
        if kind.endswith("QuotaFailure"):
            for v in (item.get("violations") or [])[:1]:
                if isinstance(v, dict):
                    dims = v.get("quotaDimensions") if isinstance(v.get("quotaDimensions"), dict) else {}
                    out["quota_metric"] = out["quota_metric"] or str(v.get("quotaMetric", ""))
                    out["quota_id"] = out["quota_id"] or str(v.get("quotaId", ""))
                    out["quota_location"] = out["quota_location"] or str(dims.get("location") or dims.get("region") or "")
                    out["quota_limit_value"] = out["quota_limit_value"] or str(v.get("quotaValue", ""))
        elif kind.endswith("ErrorInfo"):
            meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            out["quota_metric"] = out["quota_metric"] or str(meta.get("quota_metric", ""))
            out["quota_location"] = out["quota_location"] or str(meta.get("quota_location", ""))
            out["quota_limit_value"] = out["quota_limit_value"] or str(meta.get("quota_limit_value", ""))
            out["consumer"] = out["consumer"] or str(meta.get("consumer", ""))
            out["reason"] = out["reason"] or str(item.get("reason", ""))   # 403 정지·정책 구분용(예: SERVICE_DISABLED)
        elif kind.endswith("RetryInfo"):
            out["retry_delay"] = out["retry_delay"] or str(item.get("retryDelay", ""))
    return out


def _is_zero_request_quota(fields: dict) -> bool:
    """Codex 검수(261106): 한도 값이 0 이고(`0`·`0.0` 모두), 항목이 '분당 요청 한도'(ERR-203 의 두 항목명 계열)일 때만 한도 0.
    다른 quota 항목의 0 은 일반 rate 로 둔다."""
    try:
        if float(str(fields.get("quota_limit_value", "")).strip()) != 0.0:
            return False
    except ValueError:
        return False
    ident = f"{fields.get('quota_id', '')} {fields.get('quota_metric', '')}".lower()
    return "requestsperminute" in ident or "requests_per_minute" in ident or "generate_content_requests" in ident \
        or "generatecontent" in ident or "api requests" in ident or "api_requests" in ident


def classify(fields: dict) -> Optional[str]:
    code = fields.get("http_code")
    if not isinstance(code, int):
        return None
    if code == 429:
        return GEMINI_QUOTA_ZERO if _is_zero_request_quota(fields) else GEMINI_RATE
    if code in (401, 403):
        return GEMINI_AUTH
    if code >= 500:
        return GEMINI_TRANSIENT
    return None


def record_gemini_failure(
    exc: Exception, *, account: str = "", stage: str = "carousel_generate", model: str = "",
    attempt: int = 1, final: bool = True, notify: Optional[Callable[[str], None]] = None,
    db_path=None, now: Optional[datetime] = None, notify_async: bool = True,
) -> Optional[str]:
    """진단 로그 1줄(매 시도) + 원장 기록·알림(final=True 일 때만). 분류명을 돌려주고, 예외는 전파하지 않는다."""
    try:
        fields = extract_fields(exc)
        error_class = classify(fields)
        if error_class is None:
            return None
        logger.warning(
            "[GeminiDiag] acct=%s class=%s model=%s attempt=%s http_code=%s quota_metric=%s quota_id=%s "
            "quota_location=%s quota_limit_value=%s consumer=%s retry_delay=%s reason=%s",
            _ev.safe_text(account, limit=60) or "-", error_class, _ev.safe_text(model, limit=60), attempt,
            fields["http_code"],
            _ev.safe_text(fields["quota_metric"], limit=120), _ev.safe_text(fields["quota_id"], limit=120),
            _ev.safe_text(fields["quota_location"], limit=40), _ev.safe_text(fields["quota_limit_value"], limit=20),
            _ev.safe_text(fields["consumer"], limit=60), _ev.safe_text(fields["retry_delay"], limit=20),
            _ev.safe_text(fields["reason"], limit=60),
        )
        if not final:
            return error_class
        now = now or datetime.now()
        detail = _ev.safe_text(
            f"location={fields['quota_location']} limit={fields['quota_limit_value']} "
            f"metric={fields['quota_metric']} consumer={fields['consumer']} reason={fields['reason']} "
            f"model={_ev.safe_text(model, limit=60)}")
        alert_message = None
        conn = _ev._connect(db_path or _ev._DB_PATH)
        try:
            with conn:
                _ev._insert_event(conn, now, "gemini", account, error_class, fields["http_code"], None, None,
                                  stage, "", detail)
                if notify and error_class in _ALERT_CLASSES and _ev._claim_alert_conn(conn, account, error_class, now):
                    alert_message = (
                        f"[긴급] Gemini {error_class} — {account or 'unknown'} http={fields['http_code']} "
                        f"location={fields['quota_location'] or '-'} limit={fields['quota_limit_value'] or '-'}\n"
                        f"프로젝트 한도·정지·키 상태 확인 필요 (기록·알림만 적용, 재시도·게시 로직 불변)")
        finally:
            conn.close()
        if alert_message:
            _ev._send_alert(notify, alert_message, notify_async,
                            claim=(now.strftime("%Y-%m-%d"), account or "", error_class),
                            db_path=db_path or _ev._DB_PATH)
        return error_class
    except Exception as err:  # noqa: BLE001 — 진단 실패가 생성 흐름을 바꾸면 안 된다
        logger.warning("[GeminiDiag] 기록 실패(생성 흐름 무영향) | %s", type(err).__name__)
        return None


GEMINI_RECOVERED = "GEMINI_RECOVERED"
_BROKEN_CLASSES = (GEMINI_QUOTA_ZERO, GEMINI_AUTH)
_RECOVERY_WINDOW_DAYS = 7


def record_gemini_success(
    *, account: str, model: str = "", stage: str = "carousel_generate",
    notify: Optional[Callable[[str], None]] = None, db_path=None, now: Optional[datetime] = None,
    notify_async: bool = True,
) -> bool:
    """회복 감지(261106) — 이 계정의 가장 최근 gemini 원장 기록이 한도 0·인증 실패였는데 Gemini 호출이 성공했으면
    GEMINI_RECOVERED 1행을 남기고 알린다(이후 성공은 최근 기록이 RECOVERED 라 반복 알림 없음). 기록 전용 —
    어떤 실패도 예외로 전파하지 않고, 원장 파일이 아직 없으면 아무것도 만들지 않는다."""
    try:
        path = db_path or _ev._DB_PATH
        if not account or not path.exists():
            return False
        now = now or datetime.now()
        message = None
        conn = _ev._connect(path)
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")   # Codex 검수: 조회~기록을 한 쓰기 트랜잭션으로(동시 Producer 경합 축소)
                since = (now - timedelta(days=_RECOVERY_WINDOW_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
                # 장애(한도 0·인증)·회복 이벤트만 비교한다 — 사이에 낀 RATE/TRANSIENT 때문에 회복을 놓치지 않는다.
                row = conn.execute(
                    "SELECT error_class FROM events WHERE source='gemini' AND account=? AND ts>=? "
                    "AND error_class IN (?,?,?) ORDER BY id DESC LIMIT 1",
                    (account, since, GEMINI_QUOTA_ZERO, GEMINI_AUTH, GEMINI_RECOVERED)).fetchone()
                if not row or row[0] not in _BROKEN_CLASSES:
                    return False
                _ev._insert_event(conn, now, "gemini", account, GEMINI_RECOVERED, 200, None, None, stage, "",
                                  _ev.safe_text(f"after={row[0]} model={model}"))
                message = (f"[회복] Gemini — {account} 호출 성공 (직전 상태 {row[0]}). "
                           f"한도·정지 해제 가능성, 해당 계정 Producer 재개 확인")
        finally:
            conn.close()
        logger.warning("[GeminiDiag] acct=%s class=%s after=%s model=%s", _ev.safe_text(account, limit=60),
                       GEMINI_RECOVERED, row[0], _ev.safe_text(model, limit=60))
        if notify and message:
            _ev._send_alert(notify, message, notify_async)
        return True
    except Exception as err:  # noqa: BLE001
        logger.warning("[GeminiDiag] 회복 감지 실패(생성 흐름 무영향) | %s", type(err).__name__)
        return False


def record_gemini_success_default(**kwargs) -> bool:
    kwargs.setdefault("notify", _default_notify())
    return record_gemini_success(**kwargs)


def _default_notify() -> Optional[Callable[[str], None]]:
    try:
        from services.slack_notifier import get_notify_fn
        return get_notify_fn()
    except Exception:  # noqa: BLE001
        return None


def record_gemini_failure_default(exc: Exception, **kwargs) -> Optional[str]:
    """운영 호출용 — Slack notify 를 기본 연결한다."""
    kwargs.setdefault("notify", _default_notify())
    return record_gemini_failure(exc, **kwargs)
