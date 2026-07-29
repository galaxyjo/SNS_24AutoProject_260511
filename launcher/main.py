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
from modules.sns.content_filter import passes_keyword_filter

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
    """
    import requests as _req

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
            # 서버가 명확히 거부 — 게시 안 됐음이 확실하므로 재시도 없이 실패 확정
            logger.error(f"[publish_single] media_publish 명확한 실패(HTTP {r2.status_code}) | rid={rid} | creation_id={creation_id}")
            return {"ok": False, "error": f"http_{r2.status_code}"}

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

        # 발행 직전 텍스트 Quality Gate (기본 비활성 — PUBLISH_TEXT_GATE_ENABLED=true 시에만 적용)
        if os.getenv("PUBLISH_TEXT_GATE_ENABLED", "false").lower() == "true":
            if not passes_keyword_filter(caption):
                logger.info(f"[PublishGate] 텍스트 차단 | rid={post_id}")
                from modules.infra.repository_interface import PostPublishResult as _PPR
                repo.mark_post_result(post_id, _PPR(status="rejected", platform_post_id="", error_code=""))
                continue

        if not account_code_ref:
            logger.warning(
                "[Main] account_code_ref 공란 — Legacy 전역 계정 fallback 금지, 처리 보류 | rid=%s",
                post_id,
            )
            continue
        else:
            # ── 신규 경로: 계정별 Provider 분기(260725 설계, 기본 비활성) ──
            if not routing_enabled:
                logger.info(
                    "[Main] account_code_ref 존재하나 라우팅 비활성(INSTAGRAM_PROVIDER_ROUTING_ENABLED=false) "
                    "— 처리 보류 | rid=%s | account_code_ref=%s", post_id, account_code_ref,
                )
                continue

            account = repo.get_publish_account(account_code_ref)
            if account is None:
                logger.warning(
                    "[Main] account_code_ref 조회 실패(없음/중복/형식오류) — 처리 보류 | rid=%s | account_code_ref=%s",
                    post_id, account_code_ref,
                )
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
    # FP-047: comment_airtable_record 핸들러는 반드시 rq.start() 이전에 eager 등록해야
    # 함 — 기존 ig_auto_reply/ig_followup처럼 실패 시점에 지연등록하면 재시작 후 pending
    # task가 handler를 못 찾고 dead 처리될 위험이 있음(설계문서 §6).
    _register_comment_retry_handlers(rq)
    logger.info("[Main] comment_airtable_record retry handler 등록 완료")
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
