import hashlib
import json
import os
import re
import time
from urllib.parse import parse_qs, urlparse
from dotenv import load_dotenv
load_dotenv(override=True)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from modules.common.airtable_bridge import get_table
from modules.sns.caption_generator import generate_caption
from modules.sns.content_filter import detect_and_translate, passes_keyword_filter, clean_contact_info, replace_contacts, passes_image_filter, clean_fb_metadata
from modules.sns.post_id_generator import generate_sku, get_source_group, get_platform_code
from modules.sns.image_hosting import upload_to_imgbb
from modules.common.logger import get_logger

logger = get_logger(__name__)

CHROMEDRIVER_PATH = r"C:\Users\admin\AppData\Roaming\adspower_global\cwd_global\chrome_144\chromedriver.exe"
MAX_POSTS = int(os.getenv("FB_MAX_POSTS", "10"))


def _stage_log(stage: str, t0: float, extra: str = "") -> None:
    elapsed = round(time.time() - t0, 2)
    msg = f"[STAGE:{stage}] elapsed={elapsed}s"
    if extra:
        msg += f" | {extra}"
    logger.info(msg)


def load_supplier_blocklist() -> list:
    """Airtable Supplier_Blocklist 1회 로드 — author_name, page_name 반환."""
    from modules.infra.airtable_repository import AirtableRepository
    try:
        repo = AirtableRepository()
        entries = repo.list_blocked_suppliers()
        blocklist = [
            {
                'author_name': e.get('author_name', '').strip().lower(),
                'page_name': e.get('page_name', '').strip().lower(),
                'reason_code': e.get('reason_code', ''),
            }
            for e in entries
        ]
        logger.info(f'[Blocklist] 로드 완료 | {len(blocklist)}건')
        return blocklist
    except Exception as exc:
        logger.warning(f'[Blocklist] 로드 실패 — 빈 목록 반환 | {exc}')
        return []


def is_blocked_supplier(author_name: str, blocklist: list) -> dict:
    """author_name 이 blocklist 에 있으면 매칭된 항목 반환, 없으면 None."""
    normalized = author_name.strip().lower()
    for item in blocklist:
        if item['author_name'] and item['author_name'] in normalized:
            return item
        if item['page_name'] and item['page_name'] in normalized:
            return item
    return None


def start_browser(adspower_user_id: str = "k1bto3j4"):
    import urllib.request
    r = urllib.request.urlopen(
        f"http://local.adspower.net:50325/api/v1/browser/start?user_id={adspower_user_id}",
        timeout=10,
    )
    data = json.loads(r.read())
    return data["data"]["debug_port"]


def stop_browser(adspower_user_id: str) -> None:
    import requests as _req
    try:
        _req.get(
            f"http://local.adspower.net:50325/api/v1/browser/stop?user_id={adspower_user_id}",
            timeout=(3, 7),
        )
        logger.info(f"[AdsPower] Stop API 완료 | user={adspower_user_id}")
    except Exception as exc:
        logger.warning(f"[AdsPower] Stop API 실패 | {exc}")


def get_driver(adspower_user_id: str = "k1bto3j4", proxy_opts: dict = None):
    port = start_browser(adspower_user_id)
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    if proxy_opts and proxy_opts.get("proxy_server"):
        options.add_argument(f'--proxy-server={proxy_opts["proxy_server"]}')
        logger.info(f"[FB Crawler] proxy 적용 | {proxy_opts['proxy_server']}")
    service = Service(executable_path=CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(45)
    driver.set_script_timeout(30)
    return driver


_PROFILE_PATTERNS = ("p40x40", "p50x50", "p75x75", "p100x100", "p160x160",
                     "s32x32", "s40x40", "s50x50", "s60x60", "s160x160")


def extract_image_url(post_element, driver=None):
    """포스트 내 첫 번째 콘텐츠 이미지 URL 반환.
    프로필 사진(소형 썸네일) 및 100px 미만 이미지 제외.
    """
    imgs = post_element.find_elements(By.TAG_NAME, "img")
    for img in imgs:
        src = img.get_attribute("src") or img.get_attribute("data-src") or ""
        if not (src.startswith("https://") and "scontent" in src):
            continue
        # 프로필 사진 URL 패턴 제외
        if any(p in src for p in _PROFILE_PATTERNS):
            continue
        # 렌더링된 이미지 크기 확인 (driver 있을 때) — 100px 미만은 아이콘
        if driver:
            try:
                w = int(driver.execute_script("return arguments[0].naturalWidth || 0", img))
                h = int(driver.execute_script("return arguments[0].naturalHeight || 0", img))
                if 0 < w < 100 or 0 < h < 100:
                    continue
            except Exception:
                pass
        return src
    return ""


def expand_see_more(post, driver) -> None:
    """'더 보기' / 'See more' 버튼 클릭으로 포스트 전문 펼치기. 실패 시 silent skip."""
    try:
        btns = post.find_elements(
            By.XPATH,
            ".//div[contains(text(),'더 보기') or contains(text(),'See more')]"
            "| .//span[contains(text(),'더 보기') or contains(text(),'See more')]",
        )
        if btns:
            driver.execute_script("arguments[0].click();", btns[0])
            time.sleep(1)
    except Exception:
        pass


def _validate_publish_context(
    target_publish_account_code_ref: str,
    data_classification: str,
    canary_run_id: str = "",
    post_status: str = "",
    repo=None,
):
    """Facebook 크롤을 시작하기 전에 Registry와 Credential 일치를 확인한다."""
    from modules.common.credential_resolver import (
        CredentialResolutionError,
        resolve_credential,
    )
    from modules.infra.airtable_repository import AirtableRepository
    from modules.infra.repository_interface import RepositoryValidationError

    repo = repo or AirtableRepository()
    if post_status:
        account = repo.validate_instagram_post_context(
            target_publish_account_code_ref,
            data_classification,
            canary_run_id,
            post_status,
        )
    else:
        account = repo.validate_instagram_post_context(
            target_publish_account_code_ref,
            data_classification,
            canary_run_id,
        )
    try:
        credential = resolve_credential(account["credential_key"])
    except CredentialResolutionError as exc:
        raise RepositoryValidationError("Target Publish Account Credential 검증 실패") from exc
    if credential.ig_user_id != account["ig_user_id"]:
        raise RepositoryValidationError(
            "Target Publish Account의 Registry/Credential ig_user_id 불일치"
        )
    return account


class FacebookCanaryError(RuntimeError):
    """Direct-Permalink Canary 계약 위반."""


def extract_facebook_post_id(permalink: str) -> str:
    """지원되는 Facebook permalink에서 숫자 Post ID를 결정론적으로 추출한다."""
    parsed = urlparse((permalink or "").strip())
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        hostname == "facebook.com" or hostname.endswith(".facebook.com")
    ):
        raise FacebookCanaryError("승인된 HTTPS Facebook permalink 필수")

    candidates = []
    path_match = re.search(r"/(?:posts|permalink)/(\d+)(?:/|$)", parsed.path)
    if path_match:
        candidates.append(path_match.group(1))

    query = parse_qs(parsed.query)
    for key in ("story_fbid", "fbid"):
        values = query.get(key, [])
        if len(values) == 1 and values[0].isdigit():
            candidates.append(values[0])
    unique_ids = set(candidates)
    if len(unique_ids) != 1:
        raise FacebookCanaryError(
            "permalink에서 단일 숫자 Facebook Post ID 확인 실패"
        )
    return unique_ids.pop()


def _validate_approved_canary_image_url(image_url: str) -> str:
    parsed = urlparse((image_url or "").strip())
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not hostname:
        raise FacebookCanaryError("승인된 기존 HTTPS 이미지 URL 필수")
    if hostname == "facebook.com" or hostname.endswith(".facebook.com"):
        raise FacebookCanaryError("Facebook 원본 URL은 Canary 이미지로 사용 금지")
    if "fbcdn.net" in hostname:
        raise FacebookCanaryError("fbcdn URL은 ImgBB 없이 Canary에 사용 금지")
    return image_url.strip()


def _find_exact_permalink_article(driver, expected_post_id: str):
    """Feed를 조회하지 않고 permalink 페이지에서 expected_post_id와 일치하는 article을 선택한다.

    Facebook이 동일 Post ID를 DOM article 요소 여러 개로 중복 렌더링하는 경우가
    있으므로, DOM 요소 개수가 아니라 정규화된 Facebook Post ID를 논리 게시물
    식별자로 사용한다 — expected_post_id와 일치하는 article이 1개 이상이면 모두
    동일 논리 게시물의 중복 렌더링으로 간주하고, 0개면 fail-closed 한다.

    260729 실측 확인: "게시물 숨기기" 같은 JS 전용 UI 액션 anchor는 실제 이동
    링크가 아니라 현재 보고 있는 permalink 자체를 의미 없는 href로 재사용하며
    (끝이 빈 `#`로 끝남 — 실제 목적지가 없는 클릭 핸들러 placeholder), 화면에
    뜬 모든(무관한) 게시물이 expected_post_id와 오매칭될 수 있다. href가 빈
    `#`로 끝나는 anchor와, aria-label에 "숨기기"가 포함된 anchor는 실제 게시물
    식별 근거로 인정하지 않는다.
    """
    matches = []
    for article in driver.find_elements(By.CSS_SELECTOR, "div[role='article']"):
        matched = False
        for anchor in article.find_elements(By.CSS_SELECTOR, "a[href]"):
            href = anchor.get_attribute("href") or ""
            if href.strip().endswith("#"):
                continue
            aria_label = anchor.get_attribute("aria-label") or ""
            if "숨기기" in aria_label:
                continue
            try:
                if extract_facebook_post_id(href) == expected_post_id:
                    matched = True
                    break
            except FacebookCanaryError:
                continue
        if matched:
            matches.append(article)
    if not matches:
        raise FacebookCanaryError(
            "정확한 Facebook Post article을 찾지 못함: found=0"
        )
    return matches[0]


def run_exact_permalink_canary(
    *,
    permalink: str,
    expected_post_id: str,
    approved_image_url: str,
    approved_caption: str,
    source_account_name: str,
    canary_run_id: str,
    write_guard,
    target_publish_account_code_ref: str = "IDN-000041",
) -> dict:
    """승인 permalink 1개를 검증하고 draft Instagram_Post 1건 이하만 저장한다."""
    from modules.common.account_manager import get_account
    from modules.common.canary_execution_guard import CanaryWriteOperation
    from modules.infra.airtable_repository import AirtableRepository

    if target_publish_account_code_ref != "IDN-000041":
        raise FacebookCanaryError("Facebook Canary Target Account는 IDN-000041만 허용")
    expected_post_id = (expected_post_id or "").strip()
    if not expected_post_id.isdigit():
        raise FacebookCanaryError("expected_post_id는 숫자 필수")
    if extract_facebook_post_id(permalink) != expected_post_id:
        raise FacebookCanaryError("permalink와 expected_post_id 불일치")
    stable_image_url = _validate_approved_canary_image_url(approved_image_url)
    caption = (approved_caption or "").strip()
    if not caption:
        raise FacebookCanaryError("approved_caption 필수")

    source_account = get_account((source_account_name or "").strip())
    if source_account is None or not source_account.active:
        raise FacebookCanaryError("승인된 활성 Facebook Source Account 확인 실패")

    repo = AirtableRepository()
    _validate_publish_context(
        target_publish_account_code_ref,
        "test",
        canary_run_id,
        "draft",
        repo=repo,
    )
    if repo.exists_post_by_image_url(stable_image_url):
        raise FacebookCanaryError("승인 이미지 URL의 기존 Post가 있어 신규 Write 차단")

    driver = get_driver(
        source_account.adspower_user_id,
        source_account.selenium_proxy_options(),
    )
    try:
        driver.get(permalink)
        time.sleep(12)
        _find_exact_permalink_article(driver, expected_post_id)

        payload = {
            "image_url": stable_image_url,
            "original_image_url": stable_image_url,
            "image_url_hash": hashlib.sha256(stable_image_url.encode()).hexdigest(),
            "source_url": permalink,
            "post_status": "draft",
            "caption": caption,
            "hashtag": "",
            "original_text": "",
            "converted_text": caption,
            "media_type": "image",
            "insta_post_code": f"CANARY-FB-{expected_post_id}",
            "account_code_ref": target_publish_account_code_ref,
            "data_classification": "test",
            "canary_run_id": canary_run_id,
        }
        write_guard.authorize_write(
            CanaryWriteOperation.INSTAGRAM_POST_CREATE
        )
        record_id = repo.save_instagram_post(payload)
        if not record_id:
            raise FacebookCanaryError("Instagram_Posts Create 응답 record_id 없음")
        return {
            "created": 1,
            "record_id": record_id,
            "facebook_post_id": expected_post_id,
            "post_status": "draft",
        }
    finally:
        try:
            driver.quit()
        except Exception as exc:
            logger.warning(f"[Canary/CLEANUP] driver.quit 실패 | {exc}")
        try:
            stop_browser(source_account.adspower_user_id)
        except Exception as exc:
            logger.warning(f"[Canary/CLEANUP] AdsPower Stop API 실패 | {exc}")


def save_to_airtable(
    image_url,
    source_url,
    text="",
    original_text=None,
    media_type="image",
    sku_code="",
    *,
    target_publish_account_code_ref: str,
    data_classification: str,
    canary_run_id: str = "",
):
    if not image_url:
        print("[AIRTABLE] 이미지 URL 없음 - 저장 생략")
        return
    from modules.infra.airtable_repository import AirtableRepository
    repo = AirtableRepository()
    repo.validate_instagram_post_context(
        target_publish_account_code_ref,
        data_classification,
        canary_run_id,
    )
    if repo.exists_post_by_image_url(image_url):
        print(f"[AIRTABLE] 중복 이미지 - 저장 생략: {image_url[:80]}...")
        return False
    caption, hashtags = generate_caption(text)
    print(f"[CAPTION] {caption[:60]}..." if caption else "[CAPTION] 생성 없음")
    _original = original_text or text
    try:
        original_image_url = image_url
        post_status = "failed"
        from urllib.parse import urlparse as _urlparse
        _host = (_urlparse(image_url).hostname or "").lower()
        if caption and "fbcdn.net" in _host:
            try:
                _r = upload_to_imgbb(image_url)
                if _r.get("success"):
                    image_url = _r["public_url"]
                    post_status = "ready"
                    logger.info("[ImgBB] 업로드 성공 | " + image_url[:80])
                else:
                    logger.warning("[ImgBB] 업로드 실패 | " + str(_r.get("error")))
            except Exception as _e:
                logger.warning("[ImgBB] 예외 | " + str(_e))
        elif not caption:
            logger.warning("[ImgBB] caption 없음 — imgbb 생략 | " + original_image_url[:80])

        import re as _re
        _m = _re.search(r"/(\d+_\d+(?:_\d+)*)[_.]", original_image_url)
        _hash_key = _m.group(1) if _m else original_image_url
        image_url_hash = hashlib.sha256(_hash_key.encode()).hexdigest()

        payload = {
            "image_url":          image_url,
            "original_image_url": original_image_url,
            "image_url_hash":     image_url_hash,
            "source_url":         source_url,
            "post_status":        post_status,
            "caption":            caption,
            "hashtag":            hashtags,
            "original_text":      _original,
            "converted_text":     text,
            "media_type":         media_type,
            "insta_post_code":    sku_code,
            "account_code_ref":   target_publish_account_code_ref,
            "data_classification": data_classification,
            "canary_run_id":      canary_run_id,
        }
        repo.save_instagram_post(payload)
        print(f"[AIRTABLE] 저장 완료: {image_url[:80]}...")
        return True
    except Exception as exc:
        logger.error(f"[AIRTABLE] 저장 요청 실패 | {type(exc).__name__}: {exc}")
        return False


def save_to_training_queue(image_url, source_url, text, target_id_ref):
    """학습 데이터 리뷰 큐(Training_Review_Queue)에 저장 — Instagram_Posts와 완전히 분리된 경로.
    imgbb 재호스팅 없음(원본 URL 그대로), content_filter 판정 없음 — 사람이 원본을 보고 PASS/BLOCK 판정한다.
    """
    if not image_url:
        logger.info("[Training] 이미지 URL 없음 - 저장 생략")
        return False
    from datetime import datetime, timezone
    from modules.infra.airtable_repository import AirtableRepository
    repo = AirtableRepository()
    import re as _re
    _m = _re.search(r"/(\d+_\d+(?:_\d+)*)[_.]", image_url)
    _hash_key = _m.group(1) if _m else image_url
    image_hash = hashlib.sha256(_hash_key.encode()).hexdigest()
    if repo.exists_candidate_by_hash(image_hash):
        logger.info(f"[Training] 중복 이미지 - 저장 생략: {image_url[:80]}...")
        return False
    try:
        repo.insert_training_candidate({
            "source_platform":  "facebook",
            "search_query":     target_id_ref,
            "source_url":       source_url,
            "image_url":        image_url,
            "text_content":     text,
            "image_hash":       image_hash,
            "target_id_ref":    target_id_ref,
            "collected_at":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "permission_status": "unknown",
        })
        logger.info(f"[Training] 저장 완료: {image_url[:80]}...")
        return True
    except Exception as exc:
        logger.error(f"[Training] 저장 요청 실패 | {type(exc).__name__}: {exc}")
        return False


def run_for_training(target_url, target_id_ref, max_posts=MAX_POSTS, adspower_user_id: str = "k1bto3j4", proxy_opts: dict = None):
    """학습 데이터 수집 전용 크롤 — Training_Review_Queue에만 저장, Instagram_Posts 미접촉.
    content_filter의 키워드/이미지 판정(passes_keyword_filter/passes_image_filter)을 적용하지 않는다 —
    룰이 걸러낼 사례까지 사람이 원본 그대로 보고 PASS/BLOCK 해야 룰의 오탐/누락을 학습할 수 있기 때문.
    공급자 블록리스트(법적/평판 위험)만 유지한다.
    """
    _t0 = time.time()
    _stage_log("TRAIN_JOB_START", _t0, f"user={adspower_user_id} url={target_url}")
    _blocklist = load_supplier_blocklist()

    driver = get_driver(adspower_user_id, proxy_opts)
    _stage_log("TRAIN_DRIVER", _t0, "WebDriver 연결 완료")

    saved = 0
    try:
        driver.get(target_url)
        time.sleep(12)
        driver.execute_script("window.scrollBy(0, 800);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        feed = driver.find_element(By.CSS_SELECTOR, "div[role='feed']")
        posts = feed.find_elements(By.XPATH, ".//div[@role='article']")

        if not posts:
            logger.warning(f"[Training Crawler] 포스트 없음 | url={target_url}")
            return 0

        _stage_log("TRAIN_CRAWL", _t0, f"posts={len(posts)}")
        for i, post in enumerate(posts[:max_posts], start=1):
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", post)
            time.sleep(1.5)

            image_url = extract_image_url(post, driver)
            expand_see_more(post, driver)
            raw_text = (post.text or "").encode("utf-8", errors="replace").decode("utf-8")
            raw_text = clean_fb_metadata(raw_text)
            _author_raw = raw_text.splitlines()[0] if raw_text else ""
            _matched = is_blocked_supplier(_author_raw, _blocklist)
            if _matched:
                logger.warning(f"[Training][Blocklist] 차단 | author={_author_raw!r} | matched={_matched}")
                continue
            if not image_url:
                logger.info(f"[Training Crawler] POST {i} 이미지 없음 - skip")
                continue
            if save_to_training_queue(image_url, target_url, raw_text, target_id_ref):
                saved += 1

        logger.info(f"[Training Crawler] 완료 | {saved}건 저장 | target={target_id_ref}")
        return saved
    finally:
        _stage_log("TRAIN_CLEANUP", _t0, f"user={adspower_user_id}")
        try:
            driver.quit()
        except Exception as exc:
            logger.warning(f"[TRAIN_CLEANUP] driver.quit 실패 | {exc}")
        try:
            stop_browser(adspower_user_id)
        except Exception as exc:
            logger.warning(f"[TRAIN_CLEANUP] AdsPower Stop API 실패 | {exc}")


def run_for_training_photos(target_url, target_id_ref, max_photos=50, adspower_user_id: str = "k1bto3j4", proxy_opts: dict = None, max_scrolls: int = 30, stagnant_limit: int = 5):
    """그룹 전체 사진(미디어 갤러리)을 대상으로 학습 후보를 대량 수집한다.
    메인 피드 방식(run_for_training)은 최근 게시물 몇 개만 훑어 수량이 부족하다 —
    /media 그리드를 스크롤하며 그룹이 보유한 사진 전체에 접근해 물량을 확보한다.
    캡션 텍스트는 없음(갤러리 뷰라 게시물 본문 접근 불가) — alt 속성만 참고로 저장.
    """
    _t0 = time.time()
    media_url = target_url.rstrip("/") + "/media"
    _stage_log("TRAIN_PHOTO_START", _t0, f"user={adspower_user_id} url={media_url}")

    driver = get_driver(adspower_user_id, proxy_opts)
    _stage_log("TRAIN_PHOTO_DRIVER", _t0, "WebDriver 연결 완료")

    saved = 0
    try:
        driver.get(media_url)
        time.sleep(8)

        seen_srcs = set()
        collected = []
        scroll_attempts = 0
        stagnant_rounds = 0

        while len(collected) < max_photos and scroll_attempts < max_scrolls and stagnant_rounds < stagnant_limit:
            imgs = driver.find_elements(By.TAG_NAME, "img")
            new_found = 0
            for img in imgs:
                src = img.get_attribute("src") or ""
                if not (src.startswith("https://") and "scontent" in src):
                    continue
                if any(p in src for p in _PROFILE_PATTERNS):
                    continue
                if src in seen_srcs:
                    continue
                seen_srcs.add(src)
                alt = img.get_attribute("alt") or ""
                collected.append((src, alt))
                new_found += 1

            stagnant_rounds = stagnant_rounds + 1 if new_found == 0 else 0
            driver.execute_script("window.scrollBy(0, 1600);")
            time.sleep(1.8)
            scroll_attempts += 1

        _stage_log("TRAIN_PHOTO_SCROLL", _t0, f"수집후보={len(collected)} scrolls={scroll_attempts}")

        for src, alt in collected[:max_photos]:
            if save_to_training_queue(src, media_url, alt, target_id_ref):
                saved += 1

        logger.info(f"[Training Photo Crawler] 완료 | {saved}건 저장 / 후보 {len(collected)}건 | target={target_id_ref}")
        return saved
    finally:
        _stage_log("TRAIN_PHOTO_CLEANUP", _t0, f"user={adspower_user_id}")
        try:
            driver.quit()
        except Exception as exc:
            logger.warning(f"[TRAIN_PHOTO_CLEANUP] driver.quit 실패 | {exc}")
        try:
            stop_browser(adspower_user_id)
        except Exception as exc:
            logger.warning(f"[TRAIN_PHOTO_CLEANUP] AdsPower Stop API 실패 | {exc}")


def run_all_training_targets(max_posts=MAX_POSTS) -> dict:
    """collection_purpose='training' 인 활성 Crawl_Targets 전체 순회 — Training_Review_Queue 적재만 수행."""
    from modules.infra.airtable_repository import AirtableRepository
    from modules.common.account_manager import get_default_account

    repo = AirtableRepository()
    targets = repo.fetch_active_training_targets(platform="facebook")
    acct = get_default_account()
    if not acct:
        logger.error("[Training Crawler] 활성 계정 없음 — 중단")
        return {}

    proxy_opts = acct.selenium_proxy_options()
    summary = {}
    for t in targets:
        try:
            n = run_for_training(t["target_url"], t["target_id"], max_posts, acct.adspower_user_id, proxy_opts)
            summary[t["target_id"]] = n
        except Exception as exc:
            logger.error(f"[Training Crawler] 실패 | target={t['target_id']} | url={t['target_url']} | {exc}")
            summary[t["target_id"]] = -1
    logger.info(f"[Training Crawler] 전체 완료 | {summary}")
    return summary


def run(
    target_url,
    max_posts=MAX_POSTS,
    adspower_user_id: str = "k1bto3j4",
    proxy_opts: dict = None,
    *,
    target_publish_account_code_ref: str,
    data_classification: str,
    canary_run_id: str = "",
):
    _validate_publish_context(
        target_publish_account_code_ref,
        data_classification,
        canary_run_id,
    )
    _t0 = time.time()
    _stage_log("JOB_START", _t0, f"user={adspower_user_id} url={target_url}")
    _blocklist = load_supplier_blocklist()

    _stage_log("ADSPOWER", _t0, f"user={adspower_user_id}")
    driver = get_driver(adspower_user_id, proxy_opts)
    _stage_log("DRIVER", _t0, "WebDriver 연결 완료")

    try:
        driver.get(target_url)
        time.sleep(12)  # 초기 렌더링 대기 (7 → 12초)
        _stage_log("PAGE_GET", _t0, f"url={target_url}")

        # 스크롤 다운 → lazy-load 이미지 강제 렌더링 후 상단 복귀
        driver.execute_script("window.scrollBy(0, 800);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        feed = driver.find_element(By.CSS_SELECTOR, "div[role='feed']")
        posts = feed.find_elements(By.XPATH, ".//div[@role='article']")

        if not posts:
            logger.warning(f"[FB Crawler] 포스트 없음 | url={target_url}")
            return []

        _stage_log("CRAWL", _t0, f"posts={len(posts)}")
        results = []
        for i, post in enumerate(posts[:max_posts], start=1):
            # 각 포스트를 뷰포트 중앙으로 스크롤 → lazy-load 트리거
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", post)
            time.sleep(1.5)

            image_url = extract_image_url(post, driver)
            expand_see_more(post, driver)
            # 서로게이트 등 latin-1 불가 문자 안전 처리
            raw_text = (post.text or "").encode("utf-8", errors="replace").decode("utf-8")
            raw_text = clean_fb_metadata(raw_text)
            _author_raw = raw_text.splitlines()[0] if raw_text else ""
            _matched = is_blocked_supplier(_author_raw, _blocklist)
            if _matched:
                logger.warning(f"[Blocklist] 차단 | author={_author_raw!r} | matched={_matched}")
                continue
            else:
                logger.info(f"[Blocklist] 통과 | author={_author_raw!r}")
            logger.info(f"[FB Crawler] POST {i} | image={image_url[:60] if image_url else '없음'}")
            filter_text = detect_and_translate(raw_text)
            if not filter_text or not passes_keyword_filter(filter_text):
                logger.info(f"[FB Crawler] POST {i} 필터 제외")
                continue
            if not passes_image_filter(image_url):
                logger.info(f"[FB Crawler] POST {i} 이미지 필터 제외")
                continue
            converted_text = replace_contacts(raw_text)
            sku = generate_sku(target_url)
            saved = save_to_airtable(
                image_url,
                target_url,
                converted_text,
                original_text=raw_text,
                media_type="image",
                sku_code=sku,
                target_publish_account_code_ref=target_publish_account_code_ref,
                data_classification=data_classification,
                canary_run_id=canary_run_id,
            )
            if saved:
                results.append({"target_url": target_url, "content": converted_text, "image_url": image_url})

        logger.info(f"[FB Crawler] 완료 | {len(results)}개 처리 | user={adspower_user_id}")

        try:
            from modules.metrics.crawl_monitor import record_crawl
            record_crawl(results, target_url=target_url)
        except Exception as exc:
            logger.warning(f"[FB Crawler] 이미지 비율 기록 실패 | {exc}")

        return results
    finally:
        _stage_log("CLEANUP", _t0, f"user={adspower_user_id}")
        try:
            driver.quit()
        except Exception as exc:
            logger.warning(f"[CLEANUP] driver.quit 실패 | {exc}")
        try:
            stop_browser(adspower_user_id)
        except Exception as exc:
            logger.warning(f"[CLEANUP] AdsPower Stop API 실패 | {exc}")
        try:
            pass  # lock release placeholder (현재 분산 lock 미사용)
        except Exception as exc:
            logger.warning(f"[CLEANUP] lock release 실패 | {exc}")


def run_all_accounts(
    max_posts=MAX_POSTS,
    *,
    target_publish_account_code_ref: str,
    data_classification: str,
    canary_run_id: str = "",
) -> dict:
    """활성 계정 전체의 crawl_urls를 순회하며 크롤링."""
    from modules.common.account_manager import get_active_accounts
    _validate_publish_context(
        target_publish_account_code_ref,
        data_classification,
        canary_run_id,
    )
    summary = {}
    for acct in get_active_accounts():
        if not acct.crawl_urls:
            logger.warning(f"[FB Crawler] crawl_urls 없음 — skip | account={acct.name}")
            continue
        acct_results = []
        proxy_opts = acct.selenium_proxy_options()
        for url in acct.crawl_urls:
            try:
                acct_results.extend(run(
                    url,
                    max_posts,
                    acct.adspower_user_id,
                    proxy_opts,
                    target_publish_account_code_ref=target_publish_account_code_ref,
                    data_classification=data_classification,
                    canary_run_id=canary_run_id,
                ))
            except Exception as exc:
                logger.error(f"[FB Crawler] 크롤링 실패 | account={acct.name} | url={url} | {exc}")
        summary[acct.name] = len(acct_results)
        logger.info(f"[FB Crawler] 계정 완료 | account={acct.name} | {len(acct_results)}개")
    return summary
