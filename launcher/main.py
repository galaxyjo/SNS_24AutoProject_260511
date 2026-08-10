"""
launcher/main.py — SNS_24AutoProject 통합 실행 진입점

단일 프로세스로 전체 서비스를 구동한다:
  - Flask Webhook 서버 (port 5000)          ← 메인 스레드
  - APScheduler: FB 크롤링 / Instagram 업로드 ← 백그라운드 스레드
  - APScheduler: 팔로업·댓글·일일 리포트     ← 백그라운드 스레드 (dm_receiver 내)
  - RetryQueue 워커                          ← 백그라운드 데몬 스레드

사용법:
    python launcher/main.py
    python -m launcher.main

Streamlit 대시보드는 별도 프로세스:
    streamlit run dashboard.py
"""

import io
import os
import sys

# 백그라운드 프로세스에서 stdout/stderr 인코딩을 UTF-8로 강제 설정
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 프로젝트 루트를 sys.path에 추가 (launcher/ 하위에서 실행 시 필요)
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(override=True)

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from core.log_initializer import init_logging
from core.error_handler import handle_errors
from modules.common.logger import get_logger
from modules.common.retry_queue import get_retry_queue
from modules.common.canary_safe_mode import (
    get_canary_safe_mode_state,
    mask_canary_run_id,
)
from modules.common.health_monitor import get_health, print_health
from modules.comment.comment_auto_reply import register_retry_handlers as _register_comment_retry_handlers
from modules.infra.airtable_usage_logger import log_api_call
from modules.common.log_sanitizer import redact_sensitive
from modules.sns.content_filter import resolve_publish_gate

init_logging()
logger = get_logger(__name__)

CRAWL_INTERVAL_MIN = int(os.getenv("CRAWL_INTERVAL_MINUTES", "30"))
UPLOAD_POLL_MIN    = int(os.getenv("POLL_INTERVAL_MINUTES", "5"))
WEBHOOK_PORT       = int(os.getenv("WEBHOOK_PORT", "5000"))
PRODUCT_PUBLISH_ACCOUNT_CODE = "IDN-000041"
PRODUCT_DATA_CLASSIFICATION = "production"

# Slack 알림 (SLACK_WEBHOOK_URL 미설정 시 None → 알림 생략)
try:
    from services.slack_notifier import get_notify_fn as _get_notify_fn
    _slack = _get_notify_fn()
except Exception:
    _slack = None


# ── 이미지 전처리 ─────────────────────────────────────────────────────────────

_IG_RATIO_MIN = 0.8    # 4:5  (세로형 최대)
_IG_RATIO_MAX = 1.91   # 1.91:1 (가로형 최대)


def _preprocess_image(image_url: str) -> str:
    """Instagram 허용 비율(4:5 ~ 1.91:1) 확인 후 필요 시 center-crop → imgbb 업로드.

    Returns:
        imgbb 영구 URL  — 비율 보정 후 업로드 성공 시
        original URL   — 비율 유효하거나 오류 시 (폴백)
    IMGBB_API_KEY 미설정 시 원본 URL 그대로 반환.
    """
    imgbb_key = os.getenv("IMGBB_API_KEY", "").strip()
    if not imgbb_key:
        logger.warning("[Preprocess] IMGBB_API_KEY 미설정 — 전처리 생략")
        return image_url

    try:
        import base64
        from PIL import Image
        import requests as _req

        resp = _req.get(image_url, timeout=15)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        w, h = img.size
        ratio = w / h

        if _IG_RATIO_MIN <= ratio <= _IG_RATIO_MAX:
            return image_url  # 유효 범위 — 전처리 불필요

        if ratio > _IG_RATIO_MAX:
            # 너무 넓음 → 너비 크롭 (center)
            new_w = int(h * _IG_RATIO_MAX)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            # 너무 길음 → 높이 크롭 (center)
            new_h = int(w / _IG_RATIO_MIN)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))

        logger.info(f"[Preprocess] 비율 보정 완료 | {w}x{h} ratio={ratio:.2f} → crop 후 imgbb 업로드")

        # 크롭 이미지를 메모리에서 base64 인코딩 후 imgbb 업로드
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        upload_resp = _req.post(
            "https://api.imgbb.com/1/upload",
            data={"key": imgbb_key, "image": b64},
            timeout=30,
        )
        upload_data = upload_resp.json()
        if not upload_data.get("success"):
            raise RuntimeError(f"imgbb 업로드 실패: {upload_data}")

        imgbb_url = upload_data["data"]["url"]
        logger.info(f"[Preprocess] imgbb 업로드 완료 | {imgbb_url}")
        return imgbb_url

    except Exception as exc:
        logger.warning(f"[Preprocess] 이미지 전처리 실패 — 원본 URL 사용 | {exc}")
        return image_url


# ── 잡 함수 ───────────────────────────────────────────────────────────────────

@handle_errors(task="fb_crawl", notify_fn=_slack)
def _job_scheduler_heartbeat_main():
    """ERR-089 관측 보강 — 이 스케줄러 루프가 살아있음을 60초 간격으로 남긴다.
    이 줄이 끊기면(watchdog.ps1 측 stale 판정) 루프 자체가 멈췄다는 뜻이다."""
    logger.info("[SchedulerHeartbeat][main] alive")


def _job_fb_crawl(
    *,
    target_publish_account_code_ref: str,
    data_classification: str,
    canary_run_id: str = "",
):
    from modules.sns.facebook_crawler import run_all_accounts
    summary = run_all_accounts(
        target_publish_account_code_ref=target_publish_account_code_ref,
        data_classification=data_classification,
        canary_run_id=canary_run_id,
    )
    logger.info(f"[Main] fb_crawl 완료 | {summary}")


@handle_errors(task="kpi_snapshot", notify_fn=_slack)
def _job_kpi_snapshot():
    from modules.metrics.kpi_collector import run_hourly_snapshot
    run_hourly_snapshot()


@handle_errors(task="engagement_update", notify_fn=_slack)
def _job_engagement_update():
    from modules.interaction_engine.interaction_scheduler import run_engagement_update
    run_engagement_update()


@handle_errors(task="auto_like", notify_fn=_slack)
def _job_auto_like():
    from modules.interaction_engine.interaction_scheduler import run_auto_like
    run_auto_like()


class DomeCrawlAllTargetsFailedError(RuntimeError):
    """이번 사이클의 도매꾹 타겟 전체가 실패했을 때 @handle_errors/Slack로 전달하기 위한
    예외. 개별 타겟·아이템 실패는 재발생시키지 않는다(격리 목적) — 전체가 공쳤을 때만 사용."""


@handle_errors(task="dome_crawl", notify_fn=_slack)
def _job_dome_crawl():
    import os as _os
    from modules.crawlers.domeggook_api_connector import DomeggookApiConnector
    from modules.crawlers.quality_gate import run_gate
    from dotenv import load_dotenv
    from modules.infra.airtable_repository import AirtableRepository
    from modules.infra.repository_interface import SourceItem, SourceItemStatus
    load_dotenv()

    repo = AirtableRepository()

    raw_targets = repo.fetch_active_crawl_targets()
    targets = [t for t in raw_targets if t.get("platform") == "domeggook"]
    if not targets:
        logger.info("[dome_crawl] Active 타겟 없음 — 스킵")
        return

    conn = DomeggookApiConnector()
    failed_targets: list[str] = []
    for rec in targets:
        f = rec
        target_id = f.get("target_id", "")
        try:
            target = {
                "target_id":     target_id,
                "kw":            f.get("keyword", ""),
                "category_code": f.get("category_code", ""),
                "max_posts":     min(int(f.get("max_posts", 10)), 10),
            }
            items = conn.fetch(target)
            gated = run_gate(items)
            ready = [i for i in gated if i["quality_status"] == "READY"]
            logger.info(f"[dome_crawl] {target['target_id']} fetch={len(items)} ready={len(ready)}")

            for item in ready:
                try:
                    payload = {k: v for k, v in {
                        "source_item_id":  item["source_item_id"],
                        "target_id":       target["target_id"],
                        "source_platform": item["source_platform"],
                        "source_url":      item.get("source_url") or None,
                        "title":           item["title"],
                        "unit_price":      item.get("unit_price"),
                        "currency":        item["currency"],
                        "min_order_qty":   item.get("min_order_qty"),
                        "image_url":       item.get("image_url") or None,
                        "seller_id":       item.get("seller_id") or None,
                        "category_code":   item.get("category_code") or None,
                        "keyword":         item.get("keyword") or None,
                        "content_hash":    item["content_hash"],
                        "quality_status":  item["quality_status"],
                        "filter_reason":   item.get("filter_reason", ""),
                        "collected_at":    item["collected_at"],
                        "pipeline_status": "NEW",
                    }.items() if v is not None}

                    # Upsert: content_hash 기준 중복 확인 → 신규/변경 분기
                    existing_ref = repo.find_source_item_by_hash(item["content_hash"])
                    if existing_ref:
                        continue  # 동일 hash 존재 → SKIP

                    source_item = SourceItem(**{k: v for k, v in payload.items() if v is not None})
                    saved_id = repo.save_source_item(source_item)
                    if saved_id:
                        repo.update_source_item_status(
                            saved_id,
                            SourceItemStatus.NEW,
                        )
                except Exception as exc:
                    logger.error(
                        f"[dome_crawl] 아이템 저장 실패 | target={target_id} | "
                        f"item={item.get('source_item_id', '')} | {exc}"
                    )
        except Exception as exc:
            logger.error(f"[dome_crawl] 타겟 처리 실패 | target_id={target_id} | {exc}")
            failed_targets.append(target_id)

    if failed_targets and len(failed_targets) == len(targets):
        raise DomeCrawlAllTargetsFailedError(f"전체 타겟 실패: {failed_targets}")


@handle_errors(task="dome_export", notify_fn=_slack)
def _job_dome_export(
    *,
    target_publish_account_code_ref: str,
    data_classification: str,
    canary_run_id: str = "",
):
    if os.getenv('DOME_EXPORT_ENABLED', 'true').lower() == 'false':
        logger.info('[dome_export] DISABLED by feature flag')
        return
    from modules.crawlers.source_exporter import export_to_instagram_posts
    result = export_to_instagram_posts(
        target_id=None,
        batch_size=5,
        dry_run=False,
        target_publish_account_code_ref=target_publish_account_code_ref,
        data_classification=data_classification,
        canary_run_id=canary_run_id,
    )
    logger.info(f"[dome_export] {result}")


@handle_errors(task="comment_dead_monitor", notify_fn=_slack)
def _job_comment_dead_monitor():
    """FP-047 — comment_airtable_record retry_queue dead 건 능동 알림(설계문서 §5)."""
    from modules.comment.comment_retry_dead_monitor import check_dead_comment_tasks
    n = check_dead_comment_tasks()
    if n:
        logger.warning(f"[comment_dead_monitor] 신규 dead 알림 {n}건")


# Provider별 Meta Graph API 호스트 — 계정마다 다른 로그인 방식(260725 설계)을 고정 매핑한다.
# 미등록 Provider는 이 dict에 없으므로 .get()이 None을 반환해 호출부에서 게시 전 차단된다(폴백 금지).
PROVIDER_CONFIG = {
    "facebook_login":  {"host": "graph.facebook.com"},
    "instagram_login": {"host": "graph.instagram.com"},
}


def publish_single(rid, image_url, caption, access_token, ig_user_id, api_host="graph.facebook.com"):
    """
    단일 Record 게시 실행 함수.
    APScheduler와 n8n Endpoint가 공통으로 호출한다.
    Token/ig_user_id는 호출자가 주입 — 이 함수는 저장소를 모른다.
    api_host: Provider별 Graph API 호스트(기본값 graph.facebook.com — 기존 호출부는 인자를 안 주므로 동작 무변경).
    로그에 access_token 출력 금지.

    Phase A(컨테이너 생성 /media)와 Phase B(발행 /media_publish)를 분리한다 —
    creation_id를 한 번 확보한 이후에는 어떤 예외·응답이 와도 새 컨테이너를
    만들지 않는다(같은 이미지 중복게시 방지, 260725 Codex 리뷰 STOP ITEM).
    Phase B에서 서버가 실제로 게시했는지 확정할 수 없는 모호한 실패
    (ReadTimeout/ConnectionError/5xx/파싱실패 등)는 재시도하지 않고
    outcome_unknown=True로 즉시 반환한다 — 호출자는 이를 실패로 치환하지
    말고 uploading 상태로 격리한 뒤 수동 확인을 받아야 한다.

    Phase A와 Phase B 사이에 컨테이너 status_code=FINISHED를 확인한다
    (ERR-107/FP-078, 260810) — Phase A 성공 직후 컨테이너가 아직
    IN_PROGRESS인 상태에서 Phase B를 호출해 HTTP 400(outcome_unknown)이
    반복 발생함을 Read-only 사후 조회로 확인함(같은 creation_id가 몇 분
    뒤 조회 시 FINISHED로 나타남). 이 대기 단계는 Phase B 호출 전이므로
    여기서 끝나는 실패는 "게시 여부 불명"이 아니라 "발행 시도 자체를
    안 함"이 확실하다 — outcome_unknown이 아닌 확정 실패로 반환한다.
    대기는 time.monotonic() 기반 전체 deadline(기본 30초)으로 제한한다 —
    Codex 리뷰(260810) P1: 개별 GET timeout을 고정 30초 × 최대 10회로
    두면 누적 최대 330초까지 걸려 5분 주기·max_instances=1 스케줄러의
    다음 실행을 막을 수 있으므로, 매 GET의 timeout도 남은 예산 이내로
    제한한다.
    """
    import requests as _req
    import time as _time

    if not image_url:
        logger.error(f"[publish_single] image_url 없음 | rid={rid}")
        return {"ok": False, "error": "image_url_missing"}

    image_url = _preprocess_image(image_url)

    # ── Phase A: 컨테이너 생성 (/media) — 아직 아무것도 게시 안 됐으므로 안전하게 재시도 ──
    creation_id = None
    for attempt in range(1, 4):
        try:
            r1 = _req.post(
                f"https://{api_host}/v21.0/{ig_user_id}/media",
                params={"image_url": image_url, "caption": caption,
                        "access_token": access_token},
                timeout=30,
            )
            r1.raise_for_status()
            creation_id = r1.json()["id"]
            break
        except Exception as e:
            logger.warning(f"[publish_single] media 생성 시도 {attempt}/3 실패 | rid={rid} | {redact_sensitive(str(e))}")
            if attempt == 3:
                logger.error(f"[publish_single] 3회 실패 최종(media 생성) | rid={rid}")
                return {"ok": False, "error": str(e)}

    # ── Phase A.5: 컨테이너 처리 완료 대기 (status_code=FINISHED) — 아직 Phase B(발행)를
    # 호출하지 않았으므로 여기서 반환하는 실패는 확정 실패다(outcome_unknown 아님).
    # Codex 리뷰(260810) P1/P2 반영: 전체 대기를 monotonic 기반 deadline으로 제한하고,
    # 개별 GET timeout도 남은 예산 이내로 제한하며, 예산이 없으면 sleep하지 않는다 ──
    _CONTAINER_WAIT_DEADLINE_SECONDS = 30
    _CONTAINER_POLL_INTERVAL_SECONDS = 3
    deadline = _time.monotonic() + _CONTAINER_WAIT_DEADLINE_SECONDS
    container_ready = False
    poll_attempt = 0
    while True:
        remaining = deadline - _time.monotonic()
        if remaining <= 0:
            break
        poll_attempt += 1
        try:
            r_status = _req.get(
                f"https://{api_host}/v21.0/{creation_id}",
                params={"fields": "status_code", "access_token": access_token},
                timeout=min(_CONTAINER_WAIT_DEADLINE_SECONDS, remaining),
            )
            r_status.raise_for_status()
            status_code = r_status.json().get("status_code")
        except Exception as e:
            logger.warning(
                f"[publish_single] 컨테이너 상태 조회 시도 {poll_attempt} 실패 | "
                f"rid={rid} | creation_id={creation_id} | {redact_sensitive(str(e))}"
            )
            remaining = deadline - _time.monotonic()
            if remaining > 0:
                _time.sleep(min(_CONTAINER_POLL_INTERVAL_SECONDS, remaining))
            continue

        if status_code == "FINISHED":
            container_ready = True
            break
        if status_code in ("ERROR", "EXPIRED"):
            logger.error(
                f"[publish_single] 컨테이너 처리 실패(status_code={status_code}) — 발행 시도 안 함 | "
                f"rid={rid} | creation_id={creation_id}"
            )
            return {"ok": False, "error": f"container_{status_code.lower()}", "creation_id": creation_id}
        if status_code is None:
            # Codex P2 — status_code 필드 자체가 없는 응답은 IN_PROGRESS와 다른 신호다.
            # 재시도로 해소될 성질이 아니므로(필드명 변경/버전 변경 가능성) 운영 진단이
            # 가능하도록 별도 확정 실패로 즉시 반환한다.
            logger.error(
                f"[publish_single] 컨테이너 상태 응답에 status_code 없음 — 발행 시도 안 함 | "
                f"rid={rid} | creation_id={creation_id}"
            )
            return {"ok": False, "error": "container_status_missing", "creation_id": creation_id}

        # status_code == "IN_PROGRESS"(또는 문서화되지 않은 그 외 값) — 남은 예산 안에서만 대기
        remaining = deadline - _time.monotonic()
        if remaining <= 0:
            break
        _time.sleep(min(_CONTAINER_POLL_INTERVAL_SECONDS, remaining))

    if not container_ready:
        logger.error(
            f"[publish_single] 컨테이너 FINISHED 대기 시간초과({_CONTAINER_WAIT_DEADLINE_SECONDS}초) — 발행 시도 안 함 | "
            f"rid={rid} | creation_id={creation_id}"
        )
        return {"ok": False, "error": "container_finished_timeout", "creation_id": creation_id}

    # ── Phase B: 발행 (/media_publish) — creation_id 확보 후 새 컨테이너 생성 절대 금지 ──
    for attempt in range(1, 4):
        try:
            r2 = _req.post(
                f"https://{api_host}/v21.0/{ig_user_id}/media_publish",
                params={"creation_id": creation_id, "access_token": access_token},
                timeout=30,
            )
        except _req.exceptions.ConnectTimeout as e:
            # 서버 연결 전 timeout — 요청이 전달 안 됐으므로 같은 creation_id로 재시도해도 안전
            logger.warning(
                f"[publish_single] media_publish ConnectTimeout, 재시도 {attempt}/3 | "
                f"rid={rid} | creation_id={creation_id} | {redact_sensitive(str(e))}"
            )
            if attempt == 3:
                logger.error(f"[publish_single] media_publish 결과 불명(ConnectTimeout 3회) | rid={rid} | creation_id={creation_id}")
                return {"ok": False, "error": "outcome_unknown", "outcome_unknown": True, "creation_id": creation_id}
            continue
        except (_req.exceptions.ReadTimeout, _req.exceptions.ConnectionError,
                _req.exceptions.ChunkedEncodingError) as e:
            # 요청이 서버에 도달했을 가능성이 있는 모호한 실패 — 재시도하면 중복게시 위험, 즉시 중단
            logger.error(
                f"[publish_single] media_publish 결과 불명(모호한 전송오류) — 재시도 중단 | "
                f"rid={rid} | creation_id={creation_id} | {redact_sensitive(str(e))}"
            )
            return {"ok": False, "error": "outcome_unknown", "outcome_unknown": True, "creation_id": creation_id}
        except Exception as e:
            # 분류되지 않은 예외 — "서버가 게시하지 않았음이 확실한가?"를 확신할 수 없으므로 보수적으로 중단
            logger.error(
                f"[publish_single] media_publish 결과 불명(미분류 예외) — 재시도 중단 | "
                f"rid={rid} | creation_id={creation_id} | {redact_sensitive(str(e))}"
            )
            return {"ok": False, "error": "outcome_unknown", "outcome_unknown": True, "creation_id": creation_id}

        # 여기 도달 = 네트워크 레벨 예외 없이 HTTP 응답을 받음 → 상태코드/본문으로 분류
        if r2.status_code >= 500:
            # Meta 5xx는 멱등성이 보장되지 않음 — 보수적으로 모호한 실패 취급, 재시도 없음
            logger.error(f"[publish_single] media_publish 결과 불명(HTTP {r2.status_code}) — 재시도 중단 | rid={rid} | creation_id={creation_id}")
            return {"ok": False, "error": "outcome_unknown", "outcome_unknown": True, "creation_id": creation_id}

        if r2.status_code >= 400:
            # 260801 6D — 실측 사고 2건 확인: HTTP 400을 "명확한 거부"로 간주했으나
            # 실제로는 동일 요청이 400을 반환한 직후(수십 초 내) 서버측에서 조용히
            # 게시가 성공한 사례가 2건 발생, 그 상태에서 재시도가 실제 중복게시를
            # 만들었다(aijomoojin Canary, media_id 17900221041544868/18021773060855830).
            # "명확한 실패"라는 기존 가정이 틀렸으므로 5xx와 동일하게 outcome_unknown으로
            # 격리하고 재시도하지 않는다 — 재게시 여부는 실계정 확인 후 사람이 결정한다.
            logger.error(f"[publish_single] media_publish 결과 불명(HTTP {r2.status_code}) — 재시도 중단 | rid={rid} | creation_id={creation_id}")
            return {"ok": False, "error": "outcome_unknown", "outcome_unknown": True, "creation_id": creation_id}

        try:
            ig_media_id = r2.json()["id"]
        except (ValueError, KeyError):
            # 200인데 본문 파싱 실패/id 없음 — 실제로는 게시됐을 수 있으므로 모호한 실패로 취급
            logger.error(f"[publish_single] media_publish 결과 불명(응답 파싱 실패/id 없음) — 재시도 중단 | rid={rid} | creation_id={creation_id}")
            return {"ok": False, "error": "outcome_unknown", "outcome_unknown": True, "creation_id": creation_id}

        if not ig_media_id:
            # 200 + {"id": "" 또는 None} — id 키는 있지만 값이 비어있음, 성공으로 오인하면 안 됨(260725 Codex 재검수)
            logger.error(f"[publish_single] media_publish 결과 불명(id 값이 비어있음) — 재시도 중단 | rid={rid} | creation_id={creation_id}")
            return {"ok": False, "error": "outcome_unknown", "outcome_unknown": True, "creation_id": creation_id}

        logger.info(f"[publish_single] 성공 | rid={rid} | ig_media_id={ig_media_id}")
        return {"ok": True, "ig_media_id": ig_media_id}

    # 이론상 도달 불가(각 분기가 continue/return으로 종료) — 안전망
    return {"ok": False, "error": "outcome_unknown", "outcome_unknown": True, "creation_id": creation_id}


@handle_errors(task="insta_upload", notify_fn=_slack)
def _job_insta_upload():
    from modules.infra.airtable_repository import AirtableRepository
    from modules.infra.repository_interface import PostPublishResult
    from modules.common.credential_resolver import CredentialResolutionError, resolve_credential
    from modules.common.canary_classification import (
        CanaryClassificationError,
        validate_publication_candidate,
    )

    routing_enabled = os.getenv("INSTAGRAM_PROVIDER_ROUTING_ENABLED", "false").strip().lower() == "true"

    repo  = AirtableRepository()
    posts = repo.fetch_pending_posts(limit=50)
    if not posts:
        return

    logger.info(f"[Main] insta_upload | {len(posts)}건 처리 시작")
    for post in posts:
        post_id           = post["post_id"]
        logger.info(f"[Approval] ready 레코드 처리 시작 | rid={post_id}")
        image_url         = post.get("image_url", "")
        caption           = f"{post.get('caption','')}\n{post.get('hashtag','')}".strip()
        account_code_ref  = post.get("account_code_ref", "")

        # 260804 Track B 6G Codex 리뷰(P0) 수정 — aijomoojin 슬롯 스케줄 Flag가
        # 켜져 있으면 이 5분 폴링 경로는 IDN-000036을 절대 처리하지 않는다.
        # 이 조건이 없으면 _job_aijomoojin_scheduled_post()(전용 Cron)와 이
        # 경로가 같은 레코드를 동시에 노려 슬롯 제한이 무력화되고 중복게시
        # 위험이 생긴다 — 다른 계정은 이 분기 자체에 영향받지 않는다.
        if account_code_ref == "IDN-000036" and os.getenv(
            "AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "false"
        ).strip().lower() == "true":
            logger.info(
                "[Main] aijomoojin 슬롯 스케줄 모드 활성 — 5분 폴링에서 제외, "
                "전용 Cron만 처리 | rid=%s", post_id,
            )
            continue

        # S2: Query 필터가 잘못되거나 Record 상태가 외부에서 바뀌어도 claim 전에 재차 차단.
        try:
            validate_publication_candidate(
                post.get("data_classification", ""),
                post.get("canary_run_id", ""),
                post.get("post_status", ""),
            )
        except CanaryClassificationError as exc:
            logger.warning(
                "[CanaryPublishBlock] 공개 게시 차단 | rid=%s | reason=%s",
                post_id,
                exc,
            )
            continue

        # ig_media_id 있으면 이미 업로드된 레코드 — 재업로드 차단
        if post.get("ig_media_id"):
            logger.warning("[Main] unverified ig_media_id detected — skip | post_id=%s", post_id)
            continue

        # ── Identity Gate (main.py 소유, Router보다 항상 우선) ──
        # 순서 고정: Identity → Global Safety → Domain Routing → Domain Gate → Publish
        # (Track B-1G, 260731). gate_enabled=false일 때는 기존 로그·동작(경고만, mark_post_result
        # 없음) 100% 보존 — 신규 IDENTITY_REJECTED 리포팅은 gate_enabled=true일 때만 추가.
        gate_enabled = os.getenv("PUBLISH_TEXT_GATE_ENABLED", "false").lower() == "true"

        def _identity_reject(reason_log: str, is_warning: bool = True) -> None:
            if gate_enabled:
                logger.info(f"[PublishGate] IDENTITY_REJECTED | rid={post_id}")
                from modules.infra.repository_interface import PostPublishResult as _PPR
                repo.mark_post_result(post_id, _PPR(status="rejected", platform_post_id="", error_code="IDENTITY_REJECTED"))
            elif is_warning:
                logger.warning(reason_log)
            else:
                logger.info(reason_log)

        if not account_code_ref:
            _identity_reject(
                f"[Main] account_code_ref 공란 — Legacy 전역 계정 fallback 금지, 처리 보류 | rid={post_id}"
            )
            continue

        # ── 신규 경로: 계정별 Provider 분기(260725 설계, 기본 비활성) ──
        if not routing_enabled:
            logger.info(
                "[Main] account_code_ref 존재하나 라우팅 비활성(INSTAGRAM_PROVIDER_ROUTING_ENABLED=false) "
                "— 처리 보류 | rid=%s | account_code_ref=%s", post_id, account_code_ref,
            )
            continue

        account = repo.get_publish_account(account_code_ref)
        if account is None:
            _identity_reject(
                f"[Main] account_code_ref 조회 실패(없음/중복/형식오류) — 처리 보류 | rid={post_id} | account_code_ref={account_code_ref}"
            )
            continue

        # 260730 계정별 Kill Switch(Fail-closed) — Airtable에서 명시적으로 체크
        # 안 된 계정은 게시하지 않는다. claim_post_for_upload() 이전이라 uploading
        # 마킹·Retry Queue 어디에도 진입하지 않고, post_status=ready 그대로 유지된다.
        if not account.get("automation_enabled", False):
            _identity_reject(
                f"[Main] 계정별 Kill Switch OFF — 처리 보류 | rid={post_id} | account_code_ref={account_code_ref}",
                is_warning=False,
            )
            continue

        # 발행 직전 계정별 콘텐츠 Gate (기본 비활성 — PUBLISH_TEXT_GATE_ENABLED=true 시에만 적용)
        # Identity는 위에서 이미 통과했으므로 Router는 Global Safety → Domain Routing →
        # Domain Gate만 수행한다(중복 구현 금지).
        if gate_enabled:
            # 260801 AI_CONTENT Gate v0/v1 — PRODUCT 도메인은 이 인자들을 쓰지 않으므로
            # 기존 동작 100% 보존(하위호환 kwargs).
            _persona_code = ""
            _required_language = ""
            try:
                _persona = repo.get_active_persona_by_account_code_v2(account_code_ref)
                _persona_code = _persona.get("persona_code", "") if _persona else ""
                _required_language = _persona.get("language", "") if _persona else ""
            except Exception:
                _persona_code = ""
                _required_language = ""
            allowed, gate_result = resolve_publish_gate(
                caption, account_code_ref,
                source_url=post.get("source_url", ""),
                persona_code=_persona_code,
                required_language=_required_language,
            )
            if not allowed:
                logger.info(f"[PublishGate] {gate_result} | rid={post_id}")
                from modules.infra.repository_interface import PostPublishResult as _PPR
                _safety_operational_failure = gate_result.startswith((
                    "AI_CONTENT_SAFETY_RETRY_EXHAUSTED:",
                    "AI_CONTENT_SAFETY_CHECK_FAILED:",
                ))
                _gate_status = "failed" if _safety_operational_failure else "rejected"
                repo.mark_post_result(post_id, _PPR(status=_gate_status, platform_post_id="", error_code=gate_result))
                continue

        provider_conf = PROVIDER_CONFIG.get(account["api_provider"])
        if provider_conf is None:
            logger.warning(
                "[Main] 미지원 api_provider — 처리 보류 | rid=%s | api_provider=%r",
                post_id, account["api_provider"],
            )
            continue

        try:
            cred = resolve_credential(account["credential_key"])
        except CredentialResolutionError as e:
            logger.warning(f"[Main] credential 해석 실패 — 처리 보류 | rid={post_id} | {e}")
            continue

        if cred.ig_user_id != account["ig_user_id"]:
            # Airtable ig_user_id와 .env ig_user_id가 다르면 어느 쪽도 신뢰하지 않고 차단(GPT 감사 필수조건)
            logger.warning(
                "[Main] ig_user_id 불일치(Airtable vs .env) — 처리 보류 | rid=%s | account_code_ref=%s",
                post_id, account_code_ref,
            )
            continue

        token      = cred.access_token
        ig_user_id = cred.ig_user_id
        api_host   = provider_conf["host"]

        # 260801 Step5 T1 Delta — aijomoojin 전용 Binding Adapter. account_code_ref가
        # IDN-000036이 아니거나 Feature Flag가 false면 이 모듈을 import조차 하지
        # 않는다(다른 계정·Flag off 경로에 이 신규 코드 자체가 관여하지 않도록 격리).
        # "IDN-000036" 리터럴은 modules.common.aijomoojin_binding_adapter의
        # AIJOMOOJIN_ACCOUNT_CODE와 중복되나, import 자체를 피하기 위한 의도적 중복.
        if account_code_ref == "IDN-000036" and os.getenv(
            "AIJOMOOJIN_BINDING_ADAPTER_ENABLED", "false"
        ).strip().lower() == "true":
            from modules.common.aijomoojin_binding_adapter import verify_aijomoojin_binding
            if not verify_aijomoojin_binding(account_code_ref, repo):
                logger.warning(
                    "[Main] aijomoojin Binding 검증 실패 — 처리 보류 | rid=%s | account_code_ref=%s",
                    post_id, account_code_ref,
                )
                continue

        # claim: uploading 마킹 (non-atomic, single-worker only) — 자격증명 해석 성공 이후에만 도달
        if not repo.claim_post_for_upload(post_id):
            continue

        raw = publish_single(post_id, image_url, caption, token, ig_user_id, api_host=api_host)

        if raw.get("outcome_unknown"):
            # media_publish 결과 불명(응답 유실 가능) — 자동으로 failed/재게시 처리하지 않는다.
            # claim_post_for_upload()가 이미 남긴 uploading 상태 그대로 격리하고, 운영자가
            # 실제 Instagram 계정을 직접 확인한 뒤 수동으로 상태를 확정해야 한다(260725 Codex 리뷰).
            logger.error(
                "[Main] OUTCOME_UNKNOWN — 수동 확인 필요 | rid=%s | creation_id=%s | account_ref=%s | stage=media_publish",
                post_id, raw.get("creation_id", ""), account_code_ref or "legacy",
            )
            if _slack:
                _slack(
                    f"[긴급] Instagram 게시 결과 불명 — 수동 확인 필요\n"
                    f"rid={post_id} | creation_id={raw.get('creation_id','')} | "
                    f"account_ref={account_code_ref or 'legacy'}\n"
                    f"Instagram 계정에서 실제 게시 여부를 직접 확인한 뒤 Airtable 상태를 수동으로 확정하세요."
                )
            continue

        pub_result = PostPublishResult(
            status="posted" if raw.get("ok") else "failed",
            platform_post_id=raw.get("ig_media_id", ""),
            error_code=raw.get("error", ""),
        )
        try:
            repo.mark_post_result(post_id, pub_result)
            if not raw.get("ok") and _slack:
                # ERR-076: HTTP 4xx "명확한 실패"도 실제로는 컨테이너 처리 지연이었던
                # 사례가 실측됨(aijomoojin, 260725) — Airtable에는 error_code를 넣지
                # 않으므로(ERR-075/041 재발 방지, mark_post_result 참조) creation_id를
                # 복구 가능하게 Slack으로만 알린다. 분류·재시도 로직은 변경 없음.
                _slack(
                    f"[알림] Instagram 게시 실패 확정 — 필요 시 creation_id로 수동 재시도 확인\n"
                    f"rid={post_id} | error={raw.get('error','')} | "
                    f"creation_id={raw.get('creation_id','')} | account_ref={account_code_ref or 'legacy'}"
                )
        except Exception as exc:
            # claim_post_for_upload()가 이미 UPLOADING으로 바꿔둔 상태라, 여기서 실패하면
            # 그 레코드는 다음 사이클의 fetch_pending_posts()(post_status=READY만 조회)
            # 대상에서 빠져 영구 고착된다 — 나머지 후보 게시물 처리는 계속 진행한다.
            if raw.get("ok"):
                logger.error(
                    "[Main] IG 게시는 성공했으나 Airtable 상태 기록 실패 — uploading에 고착, "
                    "수동 확인 필요 | rid=%s | ig_media_id=%s | %s",
                    post_id, raw.get("ig_media_id", ""), exc,
                )
                if _slack:
                    _slack(
                        f"[긴급] IG 게시 성공, Airtable 상태 기록 실패 — 수동 확인 필요\n"
                        f"rid={post_id} | ig_media_id={raw.get('ig_media_id','')}"
                    )
            else:
                logger.error(
                    "[Main] 게시 실패 상태 기록도 실패 — uploading에 고착 | rid=%s | %s",
                    post_id, exc,
                )
            continue


AIJOMOOJIN_SLOT_ACCOUNT_CODE = "IDN-000036"


@handle_errors(task="aijomoojin_slot_post", notify_fn=_slack)
def _job_aijomoojin_scheduled_post():
    """260804 Track B 6G — aijomoojin 전용 슬롯 게시(260810부터 5슬롯
    06:00/09:00/12:00/15:00/18:00 ICT, 이전 3슬롯 06:00/10:00/17:00에서 확대).

    다른 계정 경로는 전혀 건드리지 않는다. `_job_insta_upload()`에는 260804
    Codex 리뷰(P0) 수정으로 "Flag ON이면 IDN-000036 skip" 조건 1개만 추가됐다
    — 이 조건은 account_code_ref=="IDN-000036"일 때만 평가되므로 다른 계정의
    동작은 완전히 무변화다.

    슬롯당 최대 1건은 이 함수가 아니라 APScheduler 계약이 보장한다 — 각 슬롯은
    독립된 CronTrigger 1개(하루 1회만 fire)이고 `max_instances=1`로 겹침
    실행을 막는다. 이 함수 자체도 매 호출마다 후보 1건만 시도한다(성공·실패와
    무관하게 추가 후보로 넘어가지 않음).

    Catch-up(놓친 슬롯을 나중에 몰아 처리)은 `misfire_grace_time`(launcher/main.py
    등록부, 60초로 축소 — 260804 Codex 리뷰 P2 정정)이 담당한다 — 정확히는
    "0건"이 아니라 "60초 초과 지연은 Skip, 60초 이내 지연은 Scheduler
    Jitter로 허용"이다(정확한 표현으로 정정, 이전 보고의 "Catch-up 0건"
    표현이 부정확했음).

    Feature Flag 재확인의 실제 의미(260804 Codex 2차 리뷰 P1 정정 — 이전
    "재시작 없이 즉시 원복" 서술은 부정확했음): `load_dotenv(override=True)`는
    이 모듈 import 시점(launcher 기동 시) 1회만 실행되어 그 값이 프로세스
    환경(`os.environ`)에 고정된다. `os.getenv()`는 그 이후 매번 같은 값을
    읽을 뿐 `.env` 파일을 다시 읽지 않는다 — 즉 `.env` 파일만 고쳐서는
    Runtime 재시작 없이 이 값이 바뀌지 않으며, 아래의 재확인도 그 고정된
    프로세스 값을 다시 읽는 것뿐이다. **실제 원복(끄기)에는 `.env` 수정 +
    launcher 재시작이 필요하다** — 다른 기존 Flag(`PUBLISH_TEXT_GATE_ENABLED`
    등)와 동일한 제약이며 이 Delta가 예외를 만든 것이 아니다. 아래 재확인은
    "재시작 없는 즉시 원복" 수단이 아니라, Scheduler 등록 시점과 실행 시점
    사이에 프로세스가 재시작되며 값이 실제로 바뀐 경우(예: 서비스 재시작
    직후 잔류 실행)에 등록 당시 값과 실행 당시 값이 어긋나지 않도록 하는
    방어적 일관성 확인이다.

    Publish Ledger(Step6B, `modules/common/publish_ledger.py`)는 260804 회장
    결정에 따라 의도적으로 쓰지 않는다(ISOLATED_UNAPPROVED·Live 미검증,
    별도 단계에서 재승인 여부 재검토 예정) — 대신 `_job_insta_upload()`와
    동일한 계정 한정 조회·claim·게시 안전장치를 그대로 REUSE한다."""
    if os.getenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "false").strip().lower() != "true":
        logger.info("[AijomoojinSlot] Flag 프로세스 환경값 false — 이번 실행 스킵")
        return

    from modules.infra.airtable_repository import AirtableRepository
    from modules.infra.repository_interface import PostPublishResult
    from modules.common.credential_resolver import CredentialResolutionError, resolve_credential
    from modules.common.canary_classification import (
        CanaryClassificationError,
        validate_publication_candidate,
    )

    repo = AirtableRepository()
    # 260804 Codex 리뷰(P1) 수정 — fetch_pending_posts(limit=50) 뒤 클라이언트
    # 필터 방식은 다른 계정 레코드가 50건을 먼저 채우면 이 계정 후보가 결과에서
    # 밀려날 수 있었다. 계정 한정 서버측 쿼리로 전환해 다른 계정 후보 수와
    # 무관하게 항상 이 계정 것만 조회한다.
    posts = repo.fetch_pending_posts_for_account(AIJOMOOJIN_SLOT_ACCOUNT_CODE, limit=1)
    if not posts:
        logger.info("[AijomoojinSlot] ready 후보 없음 — 이번 슬롯 스킵")
        return

    post = posts[0]
    post_id = post["post_id"]
    image_url = post.get("image_url", "")
    caption = f"{post.get('caption','')}\n{post.get('hashtag','')}".strip()

    try:
        validate_publication_candidate(
            post.get("data_classification", ""),
            post.get("canary_run_id", ""),
            post.get("post_status", ""),
        )
    except CanaryClassificationError as exc:
        logger.warning(
            "[AijomoojinSlot][CanaryPublishBlock] 공개 게시 차단 | rid=%s | reason=%s", post_id, exc,
        )
        return

    if post.get("ig_media_id"):
        logger.warning("[AijomoojinSlot] unverified ig_media_id detected — skip | post_id=%s", post_id)
        return

    account = repo.get_publish_account(AIJOMOOJIN_SLOT_ACCOUNT_CODE)
    if account is None:
        logger.warning("[AijomoojinSlot] 계정 조회 실패(없음/중복/형식오류) — 이번 슬롯 스킵 | rid=%s", post_id)
        return

    # 260730 계정별 Kill Switch(Fail-closed) — claim 이전이라 uploading 마킹 없음, post_status=ready 유지.
    if not account.get("automation_enabled", False):
        logger.info("[AijomoojinSlot] 계정별 Kill Switch OFF — 이번 슬롯 스킵 | rid=%s", post_id)
        return

    gate_enabled = os.getenv("PUBLISH_TEXT_GATE_ENABLED", "false").lower() == "true"
    if gate_enabled:
        _persona_code = ""
        _required_language = ""
        try:
            _persona = repo.get_active_persona_by_account_code_v2(AIJOMOOJIN_SLOT_ACCOUNT_CODE)
            _persona_code = _persona.get("persona_code", "") if _persona else ""
            _required_language = _persona.get("language", "") if _persona else ""
        except Exception:
            _persona_code = ""
            _required_language = ""

        # 260805 Codex 리뷰(P0) — 게시 직전 최종 Safety 확인도 aijomoojin 전용
        # Gemini Credential로 격리한다(Research 단계만 격리하고 여기서 다시
        # 전역 GEMINI_API_KEY를 쓰면 "1이메일=1페르소나" 원칙이 깨진다).
        import modules.sns.research_to_topic_adapter as _research_adapter
        try:
            _safety_client = _research_adapter._get_client()
        except RuntimeError as e:
            logger.warning(
                f"[AijomoojinSlot] AIJOMOOJIN_GEMINI_API_KEY 미설정 — 이번 슬롯 스킵 | rid={post_id} | {e}"
            )
            return

        allowed, gate_result = resolve_publish_gate(
            caption, AIJOMOOJIN_SLOT_ACCOUNT_CODE,
            source_url=post.get("source_url", ""),
            persona_code=_persona_code,
            required_language=_required_language,
            safety_client=_safety_client,
            safety_throttle=_research_adapter._throttle,
            safety_model=_research_adapter.RESEARCH_MODEL,
        )
        if not allowed:
            logger.info(f"[AijomoojinSlot][PublishGate] {gate_result} | rid={post_id}")
            _safety_operational_failure = gate_result.startswith((
                "AI_CONTENT_SAFETY_RETRY_EXHAUSTED:",
                "AI_CONTENT_SAFETY_CHECK_FAILED:",
            ))
            _gate_status = "failed" if _safety_operational_failure else "rejected"
            repo.mark_post_result(post_id, PostPublishResult(status=_gate_status, platform_post_id="", error_code=gate_result))
            return

    provider_conf = PROVIDER_CONFIG.get(account["api_provider"])
    if provider_conf is None:
        logger.warning(
            "[AijomoojinSlot] 미지원 api_provider — 이번 슬롯 스킵 | rid=%s | api_provider=%r",
            post_id, account["api_provider"],
        )
        return

    try:
        cred = resolve_credential(account["credential_key"])
    except CredentialResolutionError as e:
        logger.warning(f"[AijomoojinSlot] credential 해석 실패 — 이번 슬롯 스킵 | rid={post_id} | {e}")
        return

    if cred.ig_user_id != account["ig_user_id"]:
        logger.warning(
            "[AijomoojinSlot] ig_user_id 불일치(Airtable vs .env) — 이번 슬롯 스킵 | rid=%s", post_id,
        )
        return

    if os.getenv("AIJOMOOJIN_BINDING_ADAPTER_ENABLED", "false").strip().lower() == "true":
        from modules.common.aijomoojin_binding_adapter import verify_aijomoojin_binding
        if not verify_aijomoojin_binding(AIJOMOOJIN_SLOT_ACCOUNT_CODE, repo):
            logger.warning("[AijomoojinSlot] Binding 검증 실패 — 이번 슬롯 스킵 | rid=%s", post_id)
            return

    if not repo.claim_post_for_upload(post_id):
        logger.info("[AijomoojinSlot] claim 실패(이미 선점됨) — 이번 슬롯 스킵 | rid=%s", post_id)
        return

    raw = publish_single(
        post_id, image_url, caption, cred.access_token, cred.ig_user_id, api_host=provider_conf["host"],
    )

    if raw.get("outcome_unknown"):
        logger.error(
            "[AijomoojinSlot] OUTCOME_UNKNOWN — 자동재게시 금지, 수동확인 필요 | rid=%s | creation_id=%s",
            post_id, raw.get("creation_id", ""),
        )
        if _slack:
            _slack(
                f"[긴급] aijomoojin 슬롯 게시 결과 불명 — 수동 확인 필요\n"
                f"rid={post_id} | creation_id={raw.get('creation_id','')}"
            )
        return

    pub_result = PostPublishResult(
        status="posted" if raw.get("ok") else "failed",
        platform_post_id=raw.get("ig_media_id", ""),
        error_code=raw.get("error", ""),
    )
    try:
        repo.mark_post_result(post_id, pub_result)
        if not raw.get("ok") and _slack:
            _slack(
                f"[알림] aijomoojin 슬롯 게시 실패 확정\n"
                f"rid={post_id} | error={raw.get('error','')} | creation_id={raw.get('creation_id','')}"
            )
    except Exception as exc:
        if raw.get("ok"):
            logger.error(
                "[AijomoojinSlot] IG 게시는 성공했으나 Airtable 상태 기록 실패 — uploading 고착, "
                "수동 확인 필요 | rid=%s | ig_media_id=%s | %s",
                post_id, raw.get("ig_media_id", ""), exc,
            )
            if _slack:
                _slack(
                    f"[긴급] aijomoojin 슬롯 게시 성공, Airtable 상태 기록 실패 — 수동 확인 필요\n"
                    f"rid={post_id} | ig_media_id={raw.get('ig_media_id','')}"
                )
        else:
            logger.error(
                "[AijomoojinSlot] 게시 실패 상태 기록도 실패 — uploading 고착 | rid=%s | %s", post_id, exc,
            )


AIJOMOOJIN_PRODUCER_ACCOUNT_CODE = "IDN-000036"
# 260805 Track B 7B-5 — Account_Registry의 기존 credential_key 값(Instagram
# 자격증명과 동일 키, 문서/테스트로 확인된 "AI")을 그대로 REUSE한다. 별도
# Airtable 조회를 새로 추가하지 않고 이 함수가 이미 하드코딩해 쓰는
# AIJOMOOJIN_PRODUCER_ACCOUNT_CODE와 동일한 스타일의 상수로 둔다.
AIJOMOOJIN_PRODUCER_CREDENTIAL_KEY = "AI"
# 260805 Track B 7B-5 — 전용 Gemini Key(nguyenknv15/aijomoojin) 사용 시 고정할
# 모델. 오늘(Commit 778e245) Runtime Evidence로 확인됨: 이 프로젝트에서
# "gemini-2.5-flash-lite"/"gemini-2.5-flash"는 HTTP 404("no longer available
# to new users")이고 "gemini-3.5-flash-lite"만 성공 확인됐다.
# `research_to_topic_adapter.RESEARCH_MODEL`과 같은 값이지만, "Sourcebook
# 소진 시 그 모듈을 아예 import하지 않는다"는 기존 불변조건(회귀 테스트로
# 고정됨)을 지키기 위해 import하지 않고 리터럴을 그대로 둔다.
AIJOMOOJIN_PRODUCER_GEMINI_MODEL = "gemini-3.5-flash-lite"


@handle_errors(task="aijomoojin_content_producer", notify_fn=_slack)
def _job_aijomoojin_content_producer(producer_hour: "int | None" = None):
    """260804 Track B 6G — aijomoojin 전용 콘텐츠 Producer(Sourcebook Topic →
    캡션·이미지 → Vault → Airtable ready). 매일 05:00/08:00/11:00/14:00/17:00
    ICT(각 게시 슬롯 1시간 전, 260810부터 5슬롯으로 확대)에 실행 — 하루 목표
    5건에 맞춰 슬롯마다 1회.

    260805 Track B 7B-4 — `producer_hour`(선택, 기본 None)은 Carousel Canary
    (`modules/sns/carousel_content_builder.py`) slot_role 연결용이다. 이
    값이 주어지고 `slot_role_for_producer_hour()`가 알려진 역할로 매핑하면
    `create_content_package()`에 `slot_role`/`template_type`을 함께 넘겨
    Carousel 부가 생성을 시도한다. 생략(기존 Scheduler 등록 그대로, 인자 없이
    호출)하면 `slot_role=None`이라 Carousel 생성 자체를 시도하지 않고 기존
    단일 caption+이미지 경로만 100% 그대로 동작한다 — 이 값을 넘기지 않는 한
    이번 변경은 Runtime에 아무 영향이 없다.

    REUSE 원칙(회장 승인 필수조건 1) — 검증된 생성 경로(`create_content_package`,
    `modules/sns/source_selector.py`·`caption_generator.py`·
    `image_provider_cloudflare.py`)는 이 함수가 전혀 수정하지 않는다. 이
    함수는 그 검증된 경로를 스케줄에 연결하는 얇은 오케스트레이션일 뿐이다.

    안전조건(회장 승인 필수조건 2~9, 260804 Codex 3차 리뷰 반영):
      2. 이미 ready/uploading 레코드가 있으면 신규 생성하지 않는다
         (`get_active_post_status_for_account`).
      3. Airtable 저장이 확정된 뒤에만 Vault `channel_status`를
         pending→queued로 전환한다(`mark_channel_status`).
      4. ImgBB·Airtable 실패/결과불명 시 pending을 그대로 두고 이번 실행
         안에서 재시도하지 않는다 — 다음 예약 실행이 `find_pending_channel_package()`
         로 같은 패키지를 다시 시도할 수 있으나, 그건 "자동 재실행 루프"가
         아니라 슬롯마다 1회 시도하는 동일 원칙의 반복이다(3슬롯 게시와 동일 설계).
      5. uploading 레코드 발견 시 새로 만들지 않고 즉시 HOLD+Slack 알림.
      6. `NO_SELECTABLE_TOPIC`은 실패가 아니라 정상 종료 — Sourcebook은 이
         함수가 절대 수정하지 않는다, 알림만 남긴다.
      7. 기존 6건(3.1~3.6)처럼 Airtable 저장은 성공했으나 이 메커니즘이
         없던 시절이라 channel_status가 "pending"으로 남은 stale 항목은
         `find_account_post_by_source_url()`로 걸러내고 절대 건드리지 않는다.
      8~9. `modules/common/producer_lock`(owner-token, 자동만료 없음, 수동
         해제)으로 이 Job과 `tools/run_aijomoojin_producer_manual.py`(수동
         실행 — 이 함수를 그대로 호출만 하므로 동일 Lock을 코드 구조상
         자동 공유한다)가 동일 Lock을 공유한다 — 둘 중 하나가 실행 중이면
         다른 쪽은 즉시 스킵한다(대기 없음). 260804 Codex 2차 리뷰 지적으로
         gitignore되는 `tools/_canary_260801_queue_aijomoojin_post_6f.py`에
         Lock을 붙이는 방식은 폐기했다(일반 Commit·clone에 배포 안 됨) —
         그 스크립트는 원상복구된 상태로 남아있고 이 Producer Lock 계약과
         무관하다.

    Publish Ledger(Step6B)는 여전히 DEFER 상태 그대로 — 이 Producer는 그것과
    무관한 별도의, 훨씬 좁은 목적의 Lock만 사용한다.

    260804 Codex 2차 리뷰(P0) 수정 — 이 Job은 `AIJOMOOJIN_CONTENT_PRODUCER_ENABLED`
    뿐 아니라 `AIJOMOOJIN_SLOT_SCHEDULE_ENABLED`도 함께 true여야만 진행한다.
    Producer가 만든 ready 레코드를 실제로 06/10/17 ICT 슬롯에서만 게시하게
    막는 것은 `_job_insta_upload()`의 그 Flag 기반 skip 조건인데, Producer만
    켜고 그 Flag를 깜빡하면(또는 끄면) 5분 폴링 Job이 그 ready를 슬롯 밖
    아무 때나 즉시 게시해버린다 — 두 Flag가 항상 함께 켜져야 하는 계약을
    코드로 강제한다(사람이 실수로 하나만 켜는 것을 차단)."""
    producer_flag = os.getenv("AIJOMOOJIN_CONTENT_PRODUCER_ENABLED", "false").strip().lower() == "true"
    slot_flag = os.getenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "false").strip().lower() == "true"
    if not (producer_flag and slot_flag):
        logger.info(
            "[AijomoojinProducer] Flag 조합 불충족(Producer=%s, SlotSchedule=%s) — "
            "이번 실행 스킵", producer_flag, slot_flag,
        )
        return

    from modules.common import producer_lock
    from modules.infra.airtable_repository import AirtableRepository
    from modules.sns.content_package_builder import (
        DEFAULT_VAULT_ROOT,
        VaultScanError,
        _content_paths,
        create_content_package,
        find_pending_channel_packages,
        mark_channel_status,
        read_frontmatter,
    )
    from modules.sns.image_hosting import upload_local_file_to_imgbb

    owner_token = producer_lock.new_owner_token()
    if not producer_lock.acquire(owner_token):
        # 260804 Codex 3차 리뷰(P1) 수정 — Lock에는 PID/host가 없어(의도적으로
        # Lease/Heartbeat를 안 만들었음) "반복되면 그냥 풀어라"는 안내는 위험하다
        # — 정상적으로 오래 걸리는 실행(Gemini/Cloudflare 대기 등) 중에 실수로
        # 풀면 겹쳐 실행될 수 있다. 문구를 "보유 프로세스 종료를 먼저 확인"으로
        # 바꾸고, `tools/check_aijomoojin_producer_lock.py`(Read-only 상태확인
        # CLI, 신규 tracked)를 안내한다 — force_release() 자체는 여전히 사람이
        # 직접 실행해야 하는 별도 함수(코드 경로에서 호출 안 함).
        holder = producer_lock.get_holder()
        logger.info("[AijomoojinProducer] Lock 선점 실패(다른 실행 진행 중) — 이번 실행 스킵 | holder=%s", holder)
        if _slack:
            _slack(
                f"[알림] aijomoojin Producer Lock 선점 실패 — 다른 실행이 보유 중입니다\n"
                f"holder={holder}\n"
                f"(반복되면: launcher/수동 실행 프로세스가 실제로 종료됐는지 먼저 "
                f"확인한 뒤에만 producer_lock.force_release()로 수동 해제하세요 — "
                f"`tools/check_aijomoojin_producer_lock.py`로 상태 확인 가능)"
            )
        return

    try:
        repo = AirtableRepository()

        active_status = repo.get_active_post_status_for_account(AIJOMOOJIN_PRODUCER_ACCOUNT_CODE)
        if active_status == "uploading":
            logger.warning("[AijomoojinProducer] uploading 레코드 발견 — HOLD, 신규 생성 안 함")
            if _slack:
                _slack(
                    "[HOLD] aijomoojin Producer — uploading 상태 레코드가 있어 "
                    "신규 콘텐츠 생성을 중단합니다. 수동 확인이 필요합니다."
                )
            return
        if active_status == "ready":
            logger.info("[AijomoojinProducer] 이미 ready 레코드 존재 — 신규 생성 스킵")
            return

        try:
            pending_content_ids = find_pending_channel_packages(DEFAULT_VAULT_ROOT)
        except VaultScanError as exc:
            logger.error(f"[AijomoojinProducer] Vault 스캔 실패 — 이번 실행 중단 | {exc}")
            if _slack:
                _slack(f"[긴급] aijomoojin Producer Vault 스캔 실패 — 수동 확인 필요\n{exc}")
            return

        # 260804 Codex 2차 리뷰(P0) 수정 — pending 후보가 여럿일 때 앞쪽 stale
        # 1건에서 멈추지 않고 전부 순회해, 진짜 미완료 패키지를 찾으면 그것을
        # 재개한다(stale은 전부 건드리지 않고 그냥 지나침, 회장 필수조건 7).
        content_id = None
        for candidate_id in pending_content_ids:
            candidate_fields = read_frontmatter(candidate_id, DEFAULT_VAULT_ROOT)
            candidate_source_url = candidate_fields.get("source_url", "") if candidate_fields else ""
            already_in_airtable = (
                repo.find_account_post_by_source_url(AIJOMOOJIN_PRODUCER_ACCOUNT_CODE, candidate_source_url)
                if candidate_source_url else False
            )
            if already_in_airtable:
                logger.info(
                    "[AijomoojinProducer] pending 마커가 stale(이미 Airtable 존재) — "
                    "건드리지 않고 통과 | content_id=%s", candidate_id,
                )
                continue
            content_id = candidate_id
            logger.info("[AijomoojinProducer] 미완료 pending 패키지 재개 | content_id=%s", content_id)
            break

        if content_id is None:
            from modules.sns.carousel_content_builder import (
                DEFAULT_TEMPLATE_BY_SLOT_ROLE,
                slot_role_for_producer_hour,
            )
            slot_role = (
                slot_role_for_producer_hour(producer_hour)
                if producer_hour is not None else None
            )
            template_type = DEFAULT_TEMPLATE_BY_SLOT_ROLE.get(slot_role) if slot_role else None

            # 260805 Track B 7B-5 — 페르소나(nguyenknv15/aijomoojin) 전용 Gemini
            # Key만 사용한다. 공유 corea.galaxy/전역 GEMINI_API_KEY로 자동
            # fallback하지 않는다(Fail-closed) — account_code → credential_key
            # → Gemini 자격증명 순서로 기존 Resolver를 REUSE한다.
            from google import genai
            from modules.common.credential_resolver import (
                CredentialResolutionError,
                resolve_gemini_credential,
            )
            try:
                gemini_cred = resolve_gemini_credential(AIJOMOOJIN_PRODUCER_CREDENTIAL_KEY)
            except CredentialResolutionError as exc:
                logger.error(
                    "[AijomoojinProducer] 전용 Gemini 자격증명 없음 — 공유 Key로 "
                    "fallback하지 않고 안전 종료 | error_code=MISSING_PERSONA_GEMINI_CREDENTIAL | %s",
                    exc,
                )
                if _slack:
                    _slack(
                        "[알림] aijomoojin Producer — 전용 Gemini 자격증명(credential_key="
                        f"{AIJOMOOJIN_PRODUCER_CREDENTIAL_KEY}) 조회 실패. 공유 Key로 "
                        "대체하지 않고 이번 실행을 중단합니다(MISSING_PERSONA_GEMINI_CREDENTIAL)."
                    )
                return
            aijomoojin_gemini_client = genai.Client(api_key=gemini_cred.api_key)

            result = create_content_package(
                target_language="ko", slot_role=slot_role, template_type=template_type,
                gemini_client=aijomoojin_gemini_client,
                gemini_model=AIJOMOOJIN_PRODUCER_GEMINI_MODEL,
            )
            if not result.success and result.error_code == "NO_SELECTABLE_TOPIC":
                # 260805 회장 지시(Sourcebook SSOT 복구) — Research-to-Topic
                # Adapter(Google Search Grounding/URL Context) fallback을 생산
                # 경로에서 제거했다. Sourcebook을 유일한 원천 SSOT로 유지하기
                # 위해, 선택 가능한 Topic이 없으면 인터넷 검색 없이 그대로
                # 안전 종료한다(scan_used_source_urls()가 "오늘 사용한 URL"만
                # 제외하므로 내일 슬롯에서 같은 원천이 다시 선택 가능해진다).
                logger.info(
                    "[AijomoojinProducer] 선택 가능한 Sourcebook Topic 없음 — 안전 종료 "
                    "(Sourcebook 전용 SSOT, 인터넷 검색 Fallback 없음)"
                )
                if _slack:
                    _slack(
                        "[알림] aijomoojin Producer — 선택 가능한 Sourcebook Topic이 없습니다"
                        "(오늘 이미 사용한 원천 제외 기준). 인터넷 검색 Fallback은 사용하지 "
                        "않습니다 — 다음 정규 슬롯 또는 다음 날 재평가됩니다."
                    )
                return

            if not result.success:
                logger.error(f"[AijomoojinProducer] 콘텐츠 생성 실패 | error_code={result.error_code}")
                if _slack:
                    _slack(f"[알림] aijomoojin Producer 콘텐츠 생성 실패 | error_code={result.error_code}")
                return
            content_id = result.content_id
            logger.info(f"[AijomoojinProducer] 신규 패키지 생성 | content_id={content_id}")

        fields = read_frontmatter(content_id, DEFAULT_VAULT_ROOT)
        if fields is None:
            logger.error(f"[AijomoojinProducer] frontmatter 재읽기 실패 — 이번 실행 중단 | content_id={content_id}")
            return
        caption = fields.get("caption", "")
        source_url = fields.get("source_url", "")
        _, img_path = _content_paths(content_id, DEFAULT_VAULT_ROOT)

        upload = upload_local_file_to_imgbb(str(img_path))
        if not upload.get("success"):
            logger.error(
                "[AijomoojinProducer] imgbb 업로드 실패 — pending 유지, 재시도 없음 | "
                "content_id=%s | %s", content_id, upload.get("error"),
            )
            if _slack:
                _slack(
                    f"[알림] aijomoojin Producer imgbb 업로드 실패 — pending 유지, 수동 확인 필요\n"
                    f"content_id={content_id}"
                )
            return

        image_url = upload["public_url"]

        if repo.exists_post_by_image_url(image_url):
            logger.warning(
                "[AijomoojinProducer] 동일 image_url 이미 존재 — 중복 방지, pending 유지 | "
                "content_id=%s", content_id,
            )
            return

        try:
            record_id = repo.save_instagram_post({
                "account_code_ref": AIJOMOOJIN_PRODUCER_ACCOUNT_CODE,
                "image_url": image_url,
                "caption": caption,
                "post_status": "ready",
                "data_classification": "production",
                "source_url": source_url,
            })
        except Exception as exc:
            logger.error(
                "[AijomoojinProducer] Airtable 저장 실패/결과불명 — pending 유지, 재시도 없음 | "
                "content_id=%s | %s", content_id, exc,
            )
            if _slack:
                _slack(
                    f"[긴급] aijomoojin Producer Airtable 저장 실패/결과불명 — 수동 확인 필요\n"
                    f"content_id={content_id} | image_url={image_url}"
                )
            return

        if not record_id:
            # 260804 Codex 3차 리뷰(P1) 수정 — source_url 기반 확인은 "이 계정에
            # 이 source_url을 가진 레코드가 하나라도 있는가"만 물어서, 과거의
            # posted/failed 레코드가 있어도 True가 나와 이번 저장 성공을
            # 증명하지 못했다. image_url은 이번 imgbb 업로드로 방금 새로 생성된
            # 고유 URL이라(과거 레코드와 우연히 같을 수 없음) exists_post_by_image_url
            # (기존 REUSE)로 바꿔 "정확히 이번 저장"만 확인한다.
            confirmed = repo.exists_post_by_image_url(image_url)
            if not confirmed:
                logger.error(
                    "[AijomoojinProducer] Airtable 저장 결과불명(빈 record_id, read-after-write "
                    "미확인) — pending 유지, 재시도 없음 | content_id=%s", content_id,
                )
                if _slack:
                    _slack(
                        f"[긴급] aijomoojin Producer Airtable 저장 결과불명(빈 record_id) — "
                        f"수동 확인 필요\ncontent_id={content_id} | image_url={image_url}"
                    )
                return
            logger.warning(
                "[AijomoojinProducer] record_id는 비어있었으나 read-after-write로 저장 확인됨 | "
                "content_id=%s", content_id,
            )

        marked = mark_channel_status(content_id, "queued", DEFAULT_VAULT_ROOT)
        if not marked:
            logger.error(
                "[AijomoojinProducer] Airtable 저장은 성공했으나 channel_status 전환 실패 — "
                "수동 확인 필요 | content_id=%s | record_id=%s", content_id, record_id,
            )
            if _slack:
                _slack(
                    f"[긴급] aijomoojin Producer — ready 레코드는 생성됐으나 Vault channel_status "
                    f"전환 실패\ncontent_id={content_id} | record_id={record_id}"
                )
            return

        logger.info(f"[AijomoojinProducer] 완료 | content_id={content_id} | record_id={record_id}")
    finally:
        producer_lock.release(owner_token)


# ── 스케줄러 설정 ─────────────────────────────────────────────────────────────

def _build_scheduler(canary_safe_mode: bool = False) -> BackgroundScheduler:
    now = datetime.now()
    sched = BackgroundScheduler(timezone="Asia/Seoul")
    if canary_safe_mode:
        logger.warning("[CanarySafeMode] 일반 Scheduler Job 등록 0건")
        return sched
    sched.add_job(_job_fb_crawl,     "interval", minutes=CRAWL_INTERVAL_MIN,
                  id="fb_crawl",     next_run_time=now + timedelta(seconds=60),
                  kwargs={
                      "target_publish_account_code_ref": PRODUCT_PUBLISH_ACCOUNT_CODE,
                      "data_classification": PRODUCT_DATA_CLASSIFICATION,
                  })
    sched.add_job(_job_insta_upload, "interval", minutes=UPLOAD_POLL_MIN,
                  id="insta_upload", next_run_time=now + timedelta(seconds=120),
                  max_instances=1)
    sched.add_job(_job_kpi_snapshot, "interval", hours=1,
                  id="kpi_snapshot", next_run_time=now + timedelta(seconds=180))
    sched.add_job(_job_engagement_update, "interval", minutes=30,
                  id="engagement_update", next_run_time=now + timedelta(seconds=240))
    #DISABLED_260603 sched.add_job(_job_auto_like, "interval", minutes=15,
    #DISABLED_260603               id="auto_like", next_run_time=now + timedelta(seconds=70))
    sched.add_job(_job_dome_crawl, "interval", minutes=60,
                  id="dome_crawl", next_run_time=now + timedelta(seconds=300))
    sched.add_job(_job_dome_export, "interval", minutes=10,
                  id="dome_export", next_run_time=now + timedelta(seconds=360),
                  max_instances=1, coalesce=True,
                  kwargs={
                      "target_publish_account_code_ref": PRODUCT_PUBLISH_ACCOUNT_CODE,
                      "data_classification": PRODUCT_DATA_CLASSIFICATION,
                  })
    sched.add_job(_job_comment_dead_monitor, "interval", minutes=15,
                  id="comment_dead_monitor", next_run_time=now + timedelta(seconds=420),
                  max_instances=1, coalesce=True)
    sched.add_job(_job_scheduler_heartbeat_main, "interval", seconds=60,
                  id="scheduler_heartbeat_main", next_run_time=now + timedelta(seconds=10),
                  max_instances=1, coalesce=True)
    # 260804 Track B 6G — aijomoojin 전용 3슬롯(06:00/10:00/17:00 ICT) 정식 운영모드.
    # 기본 false(미등록) — 다른 계정·기존 insta_upload Job과 완전히 분리된 신규
    # Job이라, 이 Flag를 끄면 이 3줄이 사라진다. 단, 이 등록은 launcher 기동
    # 시점(load_dotenv가 프로세스 환경을 고정하는 시점) 1회만 평가되므로,
    # `.env` 파일만 고쳐서는 반영되지 않는다 — 원복(끄기)에는 `.env` 수정 +
    # launcher 재시작이 반드시 필요하다(260804 Codex 2차 리뷰 P1 정정 — 이전
    # "재시작 없이 즉시 원복" 서술은 부정확했음, 다른 기존 Flag와 동일 제약).
    # `_job_aijomoojin_scheduled_post()` 내부의 재확인은 그 제약을 없애는
    # 수단이 아니라 방어적 일관성 확인일 뿐이다(함수 docstring 참조).
    # misfire_grace_time=60(260804 Codex 리뷰 P2 수정, 300→60초 축소) — 슬롯
    # 시각을 60초 넘게 놓치면 그 회차는 Skip(Catch-up 없음), 60초 이내 지연은
    # Scheduler Jitter로만 허용한다("Catch-up 0건"이 아니라 "60초 초과만 Skip"
    # 이 정확한 표현 — 이전 300초 값·표현 둘 다 부정확했음).
    # 260810 회장 지시 — 하루 3슬롯(06/10/17)에서 5슬롯(06/09/12/15/18, 3시간
    # 간격)으로 확대. Producer 슬롯도 각각 1시간 전으로 짝 유지(아래 참조).
    if os.getenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "false").strip().lower() == "true":
        for _slot_hour in (6, 9, 12, 15, 18):
            sched.add_job(
                _job_aijomoojin_scheduled_post, "cron",
                hour=_slot_hour, minute=0, timezone="Asia/Bangkok",
                id=f"aijomoojin_slot_{_slot_hour:02d}00",
                max_instances=1, coalesce=False, misfire_grace_time=60,
            )
    # 260804 Track B 6G — aijomoojin 전용 Content Producer(05:00/09:00/16:00 ICT,
    # 각 게시 슬롯 1시간 전). 기본 false(미등록), 게시 3슬롯과 완전히 분리된
    # 신규 Job — 다른 계정·기존 insta_upload/게시 슬롯 Job은 전혀 영향받지 않는다.
    # 원복(끄기)에는 `.env` 수정 + launcher 재시작이 필요하다(위 게시 슬롯과
    # 동일 제약, Job 본문에서도 Flag를 다시 확인해 방어적 일관성만 추가로 확인).
    # 260804 Codex 2차 리뷰(P0) 수정 — AIJOMOOJIN_SLOT_SCHEDULE_ENABLED도 함께
    # true여야 등록한다. Producer만 켜고 슬롯 Flag를 깜빡하면 5분 폴링 Job이
    # Producer가 만든 ready를 슬롯 밖에서 즉시 게시해버리는 조합을 등록
    # 단계에서부터 차단한다(Job 본문의 재확인과 이중 방어).
    #
    # ⚠ 안전한 원복 순서(260804 Codex 3차 리뷰 P1 — 두 Flag를 "동시에" 끄고
    # 재시작하면, 그 시점에 이미 만들어진 ready 레코드 1건은 이 등록 조건이
    # 아니라 _job_insta_upload()의 skip 조건(AIJOMOOJIN_SLOT_SCHEDULE_ENABLED만
    # 봄)에 걸리는데, 그 Flag도 이미 꺼져 있으므로 5분 폴링 Job이 슬롯 밖에서
    # 즉시 게시해버릴 수 있다):
    #   1) AIJOMOOJIN_CONTENT_PRODUCER_ENABLED만 먼저 false로 바꾸고 재시작
    #      (Producer 중단, 3슬롯 게시는 그대로 유지 — 새 ready 생성만 멈춤).
    #   2) Airtable에서 이 계정 ready/uploading 레코드가 0건인지 확인한다
    #      (다음 슬롯을 기다리거나 수동으로 상태 확인).
    #   3) 0건 확인 후에만 AIJOMOOJIN_SLOT_SCHEDULE_ENABLED도 false로 바꾸고
    #      재시작한다.
    # 260810 회장 지시 — 게시 5슬롯(06/09/12/15/18)에 맞춰 Producer도 각 슬롯
    # 1시간 전(05/08/11/14/17)으로 확대.
    if (
        os.getenv("AIJOMOOJIN_CONTENT_PRODUCER_ENABLED", "false").strip().lower() == "true"
        and os.getenv("AIJOMOOJIN_SLOT_SCHEDULE_ENABLED", "false").strip().lower() == "true"
    ):
        for _producer_hour in (5, 8, 11, 14, 17):
            sched.add_job(
                _job_aijomoojin_content_producer, "cron",
                hour=_producer_hour, minute=0, timezone="Asia/Bangkok",
                id=f"aijomoojin_producer_{_producer_hour:02d}00",
                max_instances=1, coalesce=False, misfire_grace_time=60,
            )
    return sched


# ── 시작 배너 ────────────────────────────────────────────────────────────────

def _print_banner(canary_safe_mode: bool = False):
    logger.info("=" * 60)
    logger.info("  SNS_24AutoProject — 통합 서버 시작")
    logger.info(f"  Flask Webhook   : http://localhost:{WEBHOOK_PORT}")
    logger.info(f"  FB 크롤링       : {CRAWL_INTERVAL_MIN}분 간격")
    logger.info(f"  Instagram 업로드: {UPLOAD_POLL_MIN}분 간격")
    logger.info(f"  Canary Safe Mode: {canary_safe_mode}")
    logger.info(f"  Streamlit       : python -m streamlit run dashboard.py")
    logger.info("=" * 60)


# ── 진입점 ────────────────────────────────────────────────────────────────────

def _start_background_services(canary_safe_mode: bool):
    """Safe Mode에서는 모든 자동 Side Effect worker와 Job을 시작하지 않는다."""
    if canary_safe_mode:
        scheduler = _build_scheduler(canary_safe_mode=True)
        logger.warning(
            "[CanarySafeMode] RetryQueue·주 Scheduler·DM Scheduler 시작 0건"
        )
        return None, scheduler

    rq = get_retry_queue()
    # FP-047/ERR-097: 모든 retry_queue 핸들러는 반드시 rq.start() 이전에 eager 등록해야
    # 함 — 실패 시점에만 지연등록하면 재시작 후 pending task가 handler를 못 찾고 dead
    # 처리될 위험이 있음(설계문서 §6). 260730 ERR-097에서 comment_airtable_record 외
    # 6개 핸들러(ig_auto_reply/ig_followup/dm_record_interaction/order_mark_converted/
    # lead_update_score/lead_mark_closed)가 동일 위험에 노출돼 있음을 확인해 전부 이관.
    # modules.dm/modules.crm은 여기서 처음 lazy import한다(기존 start_scheduler/app과
    # 동일 패턴) — 파일 최상단에서 import하면 modules.dm.__init__의 canary_safe_mode
    # 체크가 launcher 자체의 Safe Mode 판단보다 먼저 실행되는 순서 변경이 생기므로 피한다.
    from modules.dm.dm_auto_reply import register_retry_handlers as _register_dm_auto_reply_retry_handlers
    from modules.dm.dm_followup_scheduler import register_retry_handlers as _register_followup_retry_handlers
    from modules.dm.dm_receiver import register_retry_handlers as _register_dm_receiver_retry_handlers
    from modules.crm.order_detector import register_retry_handlers as _register_order_retry_handlers
    from modules.crm.lead_scorer import register_retry_handlers as _register_lead_scorer_retry_handlers
    from modules.crm.lead_closer import register_retry_handlers as _register_lead_closer_retry_handlers

    _register_comment_retry_handlers(rq)
    _register_dm_auto_reply_retry_handlers(rq)
    _register_followup_retry_handlers(rq)
    _register_dm_receiver_retry_handlers(rq)
    _register_order_retry_handlers(rq)
    _register_lead_scorer_retry_handlers(rq)
    _register_lead_closer_retry_handlers(rq)
    logger.info("[Main] retry_queue 핸들러 7종 eager 등록 완료(comment/ig_auto_reply/ig_followup/dm_record_interaction/order/lead_score/lead_close)")
    rq.start()

    # 2. 크롤링·업로드 스케줄러 시작 (백그라운드)
    scheduler = _build_scheduler()
    scheduler.start()
    logger.info("[Main] 스케줄러 시작")

    # Flask 내부 팔로업·댓글·리포트 스케줄러
    from modules.dm.dm_receiver import start_scheduler
    start_scheduler()
    return rq, scheduler


def main():
    # W1: 모든 실제 Runtime은 영속 Boot Policy 없이는 Production으로
    # fallback하지 않는다. Safe Policy의 armed→active 전환도 worker 전이다.
    safe_mode_state = get_canary_safe_mode_state(
        require_boot_policy=True,
        activate_boot_policy=True,
    )
    logger.info(
        "[RuntimeBootPolicy] "
        f"source={safe_mode_state.source} "
        f"mode={'safe' if safe_mode_state.enabled else 'production'} "
        f"state={safe_mode_state.policy_state} "
        f"purpose={safe_mode_state.purpose} "
        f"run_id={mask_canary_run_id(safe_mode_state.run_id)}"
    )
    rq, scheduler = _start_background_services(safe_mode_state.enabled)

    # Safe Mode에서도 health endpoint를 제공하기 위해 Flask는 유지한다.
    from modules.dm.dm_receiver import app

    _print_banner(safe_mode_state.enabled)

    # 4. 시작 시 헬스체크
    try:
        h = get_health()
        logger.info(f"[Main] 시작 헬스체크 | overall={h['overall']} | services={h['services']}")
    except Exception:
        pass

    # 5. Flask 메인 스레드 실행 (블로킹)
    try:
        app.run(host="0.0.0.0", port=WEBHOOK_PORT, debug=False, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        logger.info("[Main] 종료 신호 수신")
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        if rq is not None:
            rq.stop()
        logger.info("[Main] 종료 완료")


if __name__ == "__main__":
    main()
