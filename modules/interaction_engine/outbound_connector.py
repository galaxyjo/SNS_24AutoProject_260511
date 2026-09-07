"""
modules/interaction_engine/outbound_connector.py — YUNA outbound Follow 단일 Action (STEP 3, 260901)

목적: 기존 브라우저 harness를 REUSE 하여 Follow 를 1회 안전하게 실행하고 결과를 SSOT 에 기록한다.

REUSE:
  - 브라우저      : modules.sns.facebook_crawler.get_driver / stop_browser  (AdsPower + Selenium)
  - 계정/프로필   : modules.common.account_manager.get_default_account       (FB 크롤과 동일 프로필)
  - Kill-switch  : AirtableRepository.get_publish_account(code).automation_enabled  (Fail-closed, 260730)
  - 중복방지      : db/outbound_actions.db  (auto_liker.py 의 liked_comments.db 패턴)
결과 기록: Airtable Outbound_Actions (SSOT). success/failed 만 기록 — skipped 는 반환값만.

범위: Follow(follow_once) + 친구요청(friend_in_group). 공유/댓글은 DEFER.
안전장치:
  - dry_run=True 기본 — 브라우저를 열지 않고 Kill-switch·중복·한도만 확인 후 종료.
  - 일일 한도(STEP 3-C): Account_Registry.daily_follow_limit / daily_friend_limit.
    미설정 = 0 = 자동차단(Fail-closed). 오늘자 Outbound_Actions 건수로 판정.
  - Live: follow 는 OUTBOUND_FOLLOW_LIVE_ENABLED, friend 는 OUTBOUND_FRIEND_LIVE_ENABLED (별도).
  - 스케줄러/자동 caller 미연결 — 수동/테스트 호출 전용.
"""

from __future__ import annotations

import json
import os
import random
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from modules.common.logger import get_logger

logger = get_logger(__name__)

YUNA_ACCOUNT_CODE = "IDN-000041"
ACTION_TYPE = "follow"
LIVE_ENV = "OUTBOUND_FOLLOW_LIVE_ENABLED"

_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "outbound_actions.db"

_PAGE_SETTLE_SEC = 8
_POST_CLICK_SEC = 3

# Follow 버튼으로 인정할 라벨(POS) / 제외할 라벨(NEG — 이미 팔로우/취소/친구 버튼)
_FOLLOW_POS = ("팔로우", "Follow")
_FOLLOW_NEG = ("팔로잉", "Following", "취소", "Unfollow", "Requested", "요청됨", "친구")


class OutboundActionError(RuntimeError):
    """target URL 형식 오류·Live 게이트 미충족 등 Fail-closed 계약 위반."""


# ── 중복방지 SQLite (auto_liker 패턴) ─────────────────────────────────────────

def _ensure_db() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_DB_PATH)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS outbound_actions (
            dedup_key   TEXT PRIMARY KEY,
            result      TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        )
        """
    )
    con.commit()
    con.close()


def _dedup_key(account_code: str, target_identifier: str, action_type: str) -> str:
    return f"{account_code}|{action_type}|{target_identifier}"


def _local_seen(key: str) -> bool:
    _ensure_db()
    con = sqlite3.connect(_DB_PATH)
    row = con.execute(
        "SELECT 1 FROM outbound_actions WHERE dedup_key=?", (key,)
    ).fetchone()
    con.close()
    return row is not None


def _local_mark(key: str, result: str) -> None:
    _ensure_db()
    con = sqlite3.connect(_DB_PATH)
    con.execute(
        "INSERT OR IGNORE INTO outbound_actions (dedup_key, result, recorded_at) VALUES (?, ?, ?)",
        (key, result, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    con.commit()
    con.close()


# ── target 식별자 추출 (Fail-closed) ─────────────────────────────────────────

def _local_result(key: str) -> str:
    """로컬 dedup 행의 result 문자열(없으면 ''). like 재시도 정책용(260907) —
    기존 _local_seen(존재 여부)은 follow/friend 가 계속 쓴다."""
    _ensure_db()
    con = sqlite3.connect(_DB_PATH)
    row = con.execute(
        "SELECT result FROM outbound_actions WHERE dedup_key=?", (key,)
    ).fetchone()
    con.close()
    return (row[0] if row else "") or ""


def _local_upsert(key: str, result: str) -> None:
    """result 를 덮어쓰는 dedup 기록. like 는 이전 failed 행을 success 로 승격해야 해서
    INSERT OR IGNORE 인 _local_mark 대신 이 함수를 쓴다(follow/friend 는 미사용)."""
    _ensure_db()
    con = sqlite3.connect(_DB_PATH)
    con.execute(
        "INSERT OR REPLACE INTO outbound_actions (dedup_key, result, recorded_at) VALUES (?, ?, ?)",
        (key, result, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    con.commit()
    con.close()


def extract_target_identifier(target_url: str) -> str:
    """승인된 HTTPS Facebook 프로필/페이지 URL 에서 결정론적으로 식별자를 뽑는다."""
    parsed = urlparse((target_url or "").strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        host == "facebook.com" or host.endswith(".facebook.com")
    ):
        raise OutboundActionError("승인된 HTTPS Facebook 프로필/페이지 URL 필수")

    ids = parse_qs(parsed.query).get("id", [])
    if len(ids) == 1 and ids[0].isdigit():
        return ids[0]

    m = re.search(r"/people/[^/]+/(\d+)", parsed.path)
    if m:
        return m.group(1)

    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) == 1 and segments[0].lower() not in ("profile.php", "people"):
        return segments[0].lower()

    raise OutboundActionError("Facebook 프로필/페이지 식별자 추출 실패")


# ── Follow 버튼 판정 (사용자 동작과 동일한 정상 UI element 만) ────────────────

def _label_of(el) -> str:
    try:
        return (el.get_attribute("aria-label") or el.text or "").strip()
    except Exception:
        return ""


def _labels_of(el) -> tuple[str, ...]:
    """aria-label 과 보이는 텍스트를 각각 반환 (FB 는 둘이 다를 수 있음:
    aria-label='...친구 요청 보내기' 인데 보이는 span 텍스트는 '친구 추가')."""
    out = []
    try:
        a = (el.get_attribute("aria-label") or "").strip()
        if a:
            out.append(a)
    except Exception:
        pass
    try:
        t = (el.text or "").strip()
        if t:
            out.append(t)
    except Exception:
        pass
    return tuple(out)


def _is_follow_label(label: str) -> bool:
    if not label:
        return False
    if any(neg in label for neg in _FOLLOW_NEG):
        return False
    return any(
        label == pos or label.endswith(pos) or label.startswith(pos + " ")
        for pos in _FOLLOW_POS
    )


def _find_follow_button(driver):
    from selenium.webdriver.common.by import By

    for el in driver.find_elements(
        By.XPATH, "//*[self::button or self::a or @role='button']"
    ):
        if _is_follow_label(_label_of(el)):
            return el
    return None


def _confirm_followed(driver) -> bool:
    from selenium.webdriver.common.by import By

    for el in driver.find_elements(
        By.XPATH, "//*[self::button or self::a or @role='button']"
    ):
        if any(marker in _label_of(el) for marker in ("팔로잉", "Following")):
            return True
    return False


# ── 기본 의존성 주입 대상 (테스트는 인자로 대체) ─────────────────────────────

def _default_repo():
    from modules.infra.airtable_repository import AirtableRepository

    return AirtableRepository()


def _default_driver_factory():
    from modules.common.account_manager import get_default_account
    from modules.sns.facebook_crawler import get_driver

    acct = get_default_account()
    if not acct:
        raise OutboundActionError("활성 계정 없음 — accounts.json/.env 확인")
    return get_driver(acct.adspower_user_id, acct.selenium_proxy_options())


def _default_browser_stopper() -> None:
    from modules.common.account_manager import get_default_account
    from modules.sns.facebook_crawler import stop_browser

    acct = get_default_account()
    if acct:
        stop_browser(acct.adspower_user_id)


def _daily_limit_gate(repo, account_code: str, action_type: str, limit_key: str) -> str:
    """오늘 이 계정·action 건수가 한도 이상이면 사유 문자열, 아니면 ''.
    한도 미설정(0) = 차단(Fail-closed). friend 는 실제 전송(relationship_status=requested)만
    카운트 — 버튼 미발견 등 미전송 실패는 한도에 안 넣는다. 조회 실패는 예외 그대로 전파."""
    limits = repo.get_account_outbound_limits(account_code)
    cap = int(limits.get(limit_key, 0) or 0)
    try:
        used = repo.count_outbound_actions_today(
            account_code, action_type, requested_only=(action_type == FRIEND_ACTION)
        )
    except TypeError:  # 구 시그니처 Fake/Mock 호환
        used = repo.count_outbound_actions_today(account_code, action_type)
    if used >= cap:
        logger.warning(
            f"[Outbound] 일일 한도 — skip | {account_code} {action_type} used={used} cap={cap}"
        )
        return f"daily_limit_exceeded:{used}/{cap}"
    return ""


def _loose_identifier(url: str) -> str:
    """친구요청 대상 URL(그룹 user 링크 포함)에서 식별자를 뽑는다. 실패 시 URL 그대로."""
    try:
        return extract_target_identifier(url)
    except OutboundActionError:
        m = re.search(r"/user/(\d+)", url or "")
        if m:
            return m.group(1)
        tail = (url or "").split("?")[0].rstrip("/").split("/")[-1]
        return tail.lower() or (url or "")


# ── 공개 인터페이스 ──────────────────────────────────────────────────────────

def follow_once(
    target_url: str,
    *,
    account_code: str = YUNA_ACCOUNT_CODE,
    dry_run: bool = True,
    repo=None,
    driver_factory=None,
    browser_stopper=None,
) -> dict:
    """YUNA 계정으로 target_url 프로필/페이지에 Follow 를 1회 시도한다.

    반환 dict: {result: success|failed|skipped, reason, target_identifier,
               target_url, action_type, account_code, record_id}
    """
    target_identifier = extract_target_identifier(target_url)
    key = _dedup_key(account_code, target_identifier, ACTION_TYPE)

    def _out(result: str, reason: str = "", record_id: str = "") -> dict:
        return {
            "result": result,
            "reason": reason,
            "target_identifier": target_identifier,
            "target_url": target_url,
            "action_type": ACTION_TYPE,
            "account_code": account_code,
            "record_id": record_id,
        }

    repo = repo or _default_repo()

    # 1. Kill-switch (Fail-closed) — automation_enabled 명시 true 아니면 실행 안 함
    account = repo.get_publish_account(account_code)
    if not account or not account.get("automation_enabled", False):
        logger.warning(f"[Outbound] Kill-switch OFF — 실행 안 함 | account={account_code}")
        return _out("skipped", "automation_disabled")

    # 2. 중복 확인 (로컬 → SSOT). 이미 결과가 있으면 재실행 안 함.
    if _local_seen(key):
        logger.info(f"[Outbound] 로컬 중복 — skip | {key}")
        return _out("skipped", "duplicate_local")
    existing = repo.find_outbound_action(account_code, target_identifier, ACTION_TYPE)
    if existing:
        logger.info(f"[Outbound] SSOT 중복 — skip | {key} | rec={existing}")
        _local_mark(key, "duplicate")
        return _out("skipped", "duplicate_ssot", record_id=existing)

    # 3. 일일 한도 (Fail-closed) — 오늘 이 계정·follow 건수 >= 한도면 실행 안 함.
    #    Account_Registry.daily_follow_limit 미설정 = 0 = 차단.
    gate = _daily_limit_gate(repo, account_code, ACTION_TYPE, "follow")
    if gate:
        return _out("skipped", gate)

    # 4. dry_run — 여기서 종료. 브라우저 미기동, 기록 안 함.
    if dry_run:
        logger.info(f"[Outbound] dry_run — 클릭 안 함 | {key}")
        return _out("skipped", "dry_run")

    # 5. Live 게이트 (회장 승인)
    if os.getenv(LIVE_ENV, "").strip().lower() != "true":
        raise OutboundActionError(
            f"Live Follow 차단 — {LIVE_ENV}=true 필요(회장 승인 게이트)"
        )

    # 6. 브라우저 (기존 harness REUSE)
    make_driver = driver_factory or _default_driver_factory
    stop_browser = browser_stopper or _default_browser_stopper
    driver = make_driver()
    outcome, reason = "failed", ""
    try:
        driver.get(target_url)
        time.sleep(_PAGE_SETTLE_SEC)
        btn = _find_follow_button(driver)
        if btn is None:
            reason = "follow_button_not_found"
        else:
            btn.click()
            time.sleep(_POST_CLICK_SEC)
            if _confirm_followed(driver):
                outcome, reason = "success", ""
            else:
                reason = "state_not_confirmed"
    except OutboundActionError:
        raise
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"[:400]
        logger.warning(f"[Outbound] 예외 | {key} | {reason}")
    finally:
        try:
            driver.quit()
        except Exception as exc:
            logger.warning(f"[Outbound] driver.quit 실패 | {exc}")
        try:
            stop_browser()
        except Exception as exc:
            logger.warning(f"[Outbound] stop_browser 실패 | {exc}")

    # 7. 기록 (success/failed 만) — 로컬 dedup + SSOT
    _local_mark(key, outcome)
    record_id = ""
    try:
        record_id = repo.create_outbound_action(
            {
                "account_code_ref": account_code,
                "target_url": target_url,
                "target_identifier": target_identifier,
                "action_type": ACTION_TYPE,
                "result": outcome,
                "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "error_reason": reason,
            }
        )
    except Exception as exc:
        logger.error(
            f"[Outbound] SSOT 기록 실패 | {key} | {type(exc).__name__}: {exc}"
        )

    logger.info(
        f"[Outbound] 완료 | {key} | result={outcome} reason={reason!r} rec={record_id}"
    )
    return _out(outcome, reason, record_id)


# ── 친구추가 (STEP 3-B1R → 3-C, 260901) — Follow 와 별개 액션 ──────────────────
#
#   - dry_run=True 기본 (브라우저 미기동)
#   - Live 는 OUTBOUND_FRIEND_LIVE_ENABLED=true 필수 (follow 와 별도 게이트)
#   - 일일 한도(daily_friend_limit) Fail-closed 게이트 (STEP 3-C)
#   - 결과(success/failed)는 Outbound_Actions 에 기록 + 로컬 dedup (STEP 3-C, follow_once 와 통일)
#   - CAPTCHA / checkpoint / 로그인 승인 화면 감지 시 클릭하지 않고 중단

FRIEND_LIVE_ENV = "OUTBOUND_FRIEND_LIVE_ENABLED"
FRIEND_ACTION = "friend_request"
# STEP 3-G 프로필 경로: 한 실행에서 프로필 방문 상한(마라톤 방지)
_FRIEND_PROFILE_VISIT_CAP = 8
# Human SOP(260903): 한 그룹에서 새 회원이 안 나올 때 스크롤 재시도 한계 / 루프 안전 상한
_FRIEND_SCROLL_STALL_MAX = 4
_FRIEND_MAX_ITER = 200
# 260902: 검증에서 제외 — Ray Priya(팔로잉만 됨), 정유미(한국 이름·요청 전송됨, 회장 지시로 취소),
# Ym Ym Jong Jong(로마자 한국 이름 — _is_all_hangul_name 미탐지, 요청 전송됨·회장이 직접 취소).
_FRIEND_CANARY_SKIP_IDS = frozenset({
    "100095223146372", "100094449696301", "100093793984688",
})

_FRIEND_POS = ("친구 추가", "친구추가", "Add friend", "Add Friend",
               "친구 요청 보내기", "Add as friend")
# NEG: 이미 팔로우/친구/취소/메시지 + 알림 문장("…님이 친구 요청을 보냈습니다") 오탐 차단
_FRIEND_NEG = ("취소", "Cancel", "Respond", "응답", "Unfriend", "친구 끊기",
               "요청됨", "Requested", "Message", "메시지", "요청 완료",
               "보냈습니다", "읽은 상태로 표시", "님이 친구", "sent you", "responded")
_CHECKPOINT_MARKERS = (
    "checkpoint", "captcha", "본인 확인", "본인확인", "로그인 승인", "identity confirm",
    "security check", "보안 확인", "일시적으로 차단", "temporarily blocked",
    "unusual activity", "suspicious", "계정이 잠",
)


def _is_friend_add_label(label: str) -> bool:
    l = (label or "").strip()
    if not l:
        return False
    if any(neg in l for neg in _FRIEND_NEG):
        return False
    return any(pos in l for pos in _FRIEND_POS)


def _is_friend_add_el(el) -> bool:
    """버튼 요소의 aria-label / 보이는 텍스트 중 하나라도 '친구 추가'류면 True.
    (FB 는 aria-label 과 span 텍스트가 다른 경우가 있어 둘 다 확인)."""
    return any(_is_friend_add_label(x) for x in _labels_of(el))


def _checkpoint_detected(driver) -> str:
    """로그인 challenge / CAPTCHA / 계정 제한 화면이면 사유 문자열, 아니면 ''."""
    from selenium.webdriver.common.by import By

    try:
        url = (driver.current_url or "").lower()
    except Exception:
        url = ""
    if "checkpoint" in url or "confirmyour" in url or "/login/" in url:
        return f"url={url[:120]}"
    try:
        body = (driver.find_element(By.TAG_NAME, "body").text or "").lower()
    except Exception:
        body = ""
    for m in _CHECKPOINT_MARKERS:
        if m.lower() in body:
            return f"marker={m}"
    return ""


_PROFILE_EXCLUDE = (
    "/groups/", "/posts/", "/photo", "/permalink", "/reel", "/watch",
    "/events/", "/marketplace", "/story.php", "/media", "/about", "/hashtag/",
)


def _anchor_text(a) -> str:
    try:
        return (a.text or a.get_attribute("aria-label") or "").strip()
    except Exception:
        return ""


def _collect_articles(driver):
    """그룹 피드 article 요소들을 여러 전략으로 수집(facebook_crawler.run 방식 우선)."""
    from selenium.webdriver.common.by import By

    for getter in (
        lambda: driver.find_element(By.CSS_SELECTOR, "div[role='feed']")
        .find_elements(By.XPATH, ".//div[@role='article']"),
        lambda: driver.find_elements(By.CSS_SELECTOR, "div[role='feed'] div[role='article']"),
        lambda: driver.find_elements(By.CSS_SELECTOR, "div[role='article']"),
    ):
        try:
            arts = getter()
        except Exception:
            arts = []
        if arts:
            return arts
    return []


def _normalize_profile_href(raw: str) -> str:
    """FB 앵커 href 를 프로필 URL 로 정규화. 프로필이 아니면 ''."""
    if not raw or "facebook.com" not in raw.lower():
        return ""
    if any(x in raw.lower() for x in _PROFILE_EXCLUDE):
        # /groups/{gid}/user/{uid} 는 예외적으로 허용
        if not re.search(r"/groups/\d+/user/\d+", raw):
            return ""
    if re.search(r"/groups/\d+/user/\d+", raw):
        return raw.split("?")[0].split("#")[0]
    m = re.search(r"profile\.php\?id=\d+", raw)
    if m:
        return "https://www.facebook.com/" + m.group(0)
    clean = raw.split("?")[0].rstrip("/")
    if re.search(r"facebook\.com/[A-Za-z0-9.\-]{2,}$", clean):
        return clean
    return ""


def _article_author(art, expected_name: str = ""):
    """그룹 피드 article 1개에서 (작성자 프로필 URL, 표시 이름) 추출. 없으면 ('', '')."""
    from selenium.webdriver.common.by import By

    try:
        links = art.find_elements(By.CSS_SELECTOR, "a[href]")
    except Exception:
        links = []

    # 1순위: 그룹 멤버 링크
    for a in links:
        raw = a.get_attribute("href") or ""
        if re.search(r"/groups/\d+/user/\d+", raw):
            return _normalize_profile_href(raw), _anchor_text(a)

    # 2순위: 앵커 텍스트가 게시물 첫 줄(작성자 이름)과 일치하는 프로필 링크
    exp = (expected_name or "").strip().lower()
    if exp:
        for a in links:
            txt = _anchor_text(a).lower()
            if txt and (txt == exp or exp.startswith(txt) or txt.startswith(exp)):
                url = _normalize_profile_href(a.get_attribute("href") or "")
                if url:
                    return url, _anchor_text(a)

    # 3순위: 이름 텍스트가 있는 아무 프로필 링크
    for a in links:
        name = _anchor_text(a)
        if not name:
            continue
        url = _normalize_profile_href(a.get_attribute("href") or "")
        if url:
            return url, name
    return "", ""


def _find_group_authors(driver, limit: int = 20) -> list[dict]:
    """로드된 그룹 피드에서 게시물 작성자 목록을 반환.
    각 항목: {"profile_url": str, "name": str, "feed_text": str}. URL 못 찾은 작성자는 제외.

    facebook_crawler.run 과 동일한 초기 렌더(scrollBy 800 → 상단복귀) 후, 점진 스크롤하며
    article 을 재수집한다(FB 피드 가상화 대응)."""
    from selenium.webdriver.common.by import By

    try:
        driver.execute_script("window.scrollBy(0, 800);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
    except Exception:
        pass

    out: list[dict] = []
    seen: set[str] = set()
    processed: set[str] = set()
    no_url = 0
    max_articles = 0

    for _round in range(6):
        articles = _collect_articles(driver)
        max_articles = max(max_articles, len(articles))
        for art in articles:
            if len(out) >= limit:
                break
            try:
                sig = (art.text or "")[:60]
            except Exception:
                sig = ""
            if sig and sig in processed:
                continue
            if sig:
                processed.add(sig)
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", art)
                time.sleep(0.8)
            except Exception:
                pass
            try:
                feed_text = (art.text or "")[:800]
            except Exception:
                feed_text = ""
            first_line = feed_text.splitlines()[0][:80] if feed_text else ""
            url, name = _article_author(art, expected_name=first_line)
            if not name:
                name = first_line
            if not url:
                no_url += 1
                continue
            if url in seen:
                continue
            seen.add(url)
            out.append({"profile_url": url, "name": name, "feed_text": feed_text})
        if len(out) >= limit:
            break
        try:
            driver.execute_script("window.scrollBy(0, 2200);")
            time.sleep(2)
        except Exception:
            break

    hint = ""
    if max_articles <= 1:
        try:
            hint = " | body=" + (
                driver.find_element(By.TAG_NAME, "body").text or ""
            )[:160].replace("\n", " ")
        except Exception:
            pass
    try:
        logger.info(
            f"[Outbound] 그룹 작성자 추출 | articles={max_articles} authors={len(out)} "
            f"no_url={no_url}{hint}"
        )
    except Exception:
        pass
    return out


def _find_first_group_author_url(driver) -> str:
    """로드된 그룹 피드에서 첫 게시물 작성자의 프로필 URL 을 반환. 없으면 ''."""
    authors = _find_group_authors(driver, limit=5)
    return authors[0]["profile_url"] if authors else ""


def group_members_url(group_url: str) -> str:
    cleaned = group_url.split("?")[0].rstrip("/")
    # 이미 /members(/things_in_common 등 하위 뷰) 형태로 주어진 Ground Truth URL 은
    # 그대로 사용 — "/members" 를 중복으로 덧붙이지 않는다(STEP 3-F Ground Truth Canary).
    if "/members" in cleaned:
        return cleaned
    return cleaned + "/members"


def _find_group_members(driver, limit: int = 15) -> list[dict]:
    """현재 로드된 그룹 /members 페이지에서 회원 목록을 추출한다 (STEP 3-D1).

    회원 카드의 프로필 링크는 대부분 /groups/{gid}/user/{uid} 패턴이라, 이 링크만
    최소 selector 로 수집한다(게시물 DOM 역추출보다 안정적).
    각 항목: {"profile_url", "identifier", "name", "card_text"}.
    """
    from selenium.webdriver.common.by import By

    out: list[dict] = []
    seen: set[str] = set()
    for _round in range(10):
        try:
            links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/user/']")
        except Exception:
            links = []
        for a in links:
            if len(out) >= limit:
                break
            href = a.get_attribute("href") or ""
            m = re.search(r"/groups/\d+/user/(\d+)", href)
            if not m:
                continue
            uid = m.group(1)
            if uid in seen:
                continue
            seen.add(uid)
            name = _anchor_text(a)
            card_text = ""
            for depth in (2, 3, 4):
                try:
                    box = a.find_element(By.XPATH, f"./ancestor::div[{depth}]")
                    t = (box.text or "").strip()
                    if t and len(t) > len(name):
                        card_text = t[:300]
                        break
                except Exception:
                    continue
            if not name and card_text:
                name = card_text.splitlines()[0][:80]
            out.append({
                "profile_url": _normalize_profile_href(href) or href.split("?")[0],
                "identifier": uid,
                "name": name,
                "card_text": card_text,
            })
        if len(out) >= limit:
            break
        try:
            driver.execute_script("window.scrollBy(0, 2000);")
            time.sleep(2)
        except Exception:
            break

    hint = ""
    if len(out) == 0:
        try:
            hint = " | body=" + (
                driver.find_element(By.TAG_NAME, "body").text or ""
            )[:160].replace("\n", " ")
        except Exception:
            pass
    try:
        logger.info(f"[Outbound] 그룹 회원 추출 | extracted={len(out)}{hint}")
    except Exception:
        pass
    return out


def _pick_first_eligible_member(driver, repo, account_code: str) -> str:
    """로드된 /members 에서 최소필터(중복 아님 + Supplier_Blocklist 아님)를 통과하는
    첫 회원의 프로필 URL 을 반환. 한국여부·상세 판정은 여기서 안 함(프로필 이동 후 처리).
    없으면 ''."""
    from modules.sns.facebook_crawler import is_blocked_supplier, load_supplier_blocklist

    try:
        blocklist = load_supplier_blocklist()
    except Exception:
        blocklist = []
    for m in _find_group_members(driver, limit=15):
        ident = m.get("identifier") or _loose_identifier(m.get("profile_url", ""))
        if not ident:
            continue
        if _local_seen(_dedup_key(account_code, m["profile_url"], FRIEND_ACTION)):
            continue
        try:
            if repo.find_prospect_by_target(ident, FRIEND_ACTION) or \
               repo.find_outbound_action(account_code, ident, FRIEND_ACTION):
                continue
        except Exception:
            pass
        if is_blocked_supplier(m.get("name", ""), blocklist):
            continue
        logger.info(f"[Friend] members 후보 선택 | {ident} {m['profile_url']}")
        return m["profile_url"]
    return ""


# ── STEP 3-F/3-G: /members 회원카드 내부 '친구 추가' 버튼 (프로필 이동 없음) ──────

# 260902 STEP 3-G+R — Foreign Eligibility (GPT 지시, 이름·국적추정 금지):
#  - 이름(한글 여부/로마자 패턴)으로 국적을 판단하지 않는다.
#  - 회원카드 또는 프로필 현재 화면에 "명시적 해외 국가/도시 Evidence"가 있을 때만 eligible.
#  - 한국 기반 Evidence(Seoul/대한민국/부산 등)가 명확하면 skip.
#  - 해외 Evidence 없음 / UNKNOWN → skip (Fail-closed). 프로필 정보 저장 안 함.
_KR_CARD_KW = ("한국인", "대한민국", "korea", "south korea", "korean national",
               "내국인", "서울", "seoul", "부산", "busan", "대구", "인천", "광주",
               "대전", "울산", "경기", "gyeonggi", "incheon", "daegu")
# 명시적 해외 location Evidence (curated — 없으면 skip, Fail-closed 이므로 누락은 안전).
_OVERSEAS_LOC_KW = (
    "vietnam", "viet nam", "베트남", "hanoi", "ha noi", "하노이", "ho chi minh", "hcmc",
    "hcm city", "hochiminh", "saigon", "호치민", "호찌민", "da nang", "다낭", "hai phong",
    "indonesia", "인도네시아", "jakarta", "자카르타", "surabaya", "bandung", "bali", "발리",
    "thailand", "태국", "bangkok", "방콕", "chiang mai", "phuket", "치앙마이",
    "philippines", "필리핀", "manila", "마닐라", "cebu", "quezon", "makati", "davao",
    "malaysia", "말레이시아", "kuala lumpur", "쿠알라룸푸르", "penang", "johor", "selangor",
    "india", "인도", "delhi", "델리", "new delhi", "mumbai", "뭄바이", "bangalore",
    "bengaluru", "kolkata", "chennai", "hyderabad", "pune", "gujarat",
    "singapore", "싱가포르", "cambodia", "캄보디아", "phnom penh", "myanmar", "미얀마",
    "yangon", "laos", "라오스", "brunei",
    "usa", "u.s.a", "united states", "america", "미국", "california", "캘리포니아",
    "los angeles", "new york", "뉴욕", "texas", "seattle", "chicago", "atlanta",
    "canada", "캐나다", "toronto", "vancouver",
    "japan", "일본", "tokyo", "도쿄", "osaka", "오사카", "nagoya", "fukuoka",
    "china", "중국", "shanghai", "상하이", "guangzhou", "광저우", "shenzhen", "심천", "yiwu", "이우",
    "taiwan", "대만", "taipei", "타이베이", "taichung", "kaohsiung",
    "united kingdom", "영국", "london", "런던", "manchester",
    "australia", "호주", "sydney", "시드니", "melbourne", "멜버른", "brisbane",
    "uzbekistan", "우즈베키스탄", "tashkent", "타슈켄트", "kazakhstan", "카자흐스탄", "almaty",
    "russia", "러시아", "moscow", "mongolia", "몽골", "ulaanbaatar",
    "uae", "dubai", "두바이", "abu dhabi", "saudi", "사우디", "riyadh",
    "germany", "독일", "berlin", "france", "프랑스", "paris", "파리", "netherlands", "amsterdam",
    "turkey", "터키", "튀르키예", "istanbul", "이스탄불", "nigeria", "lagos", "kenya", "nairobi",
    "brazil", "브라질", "mexico", "멕시코", "egypt", "cairo",
)
_FRIEND_PENDING_KW = ("요청 취소", "요청됨", "친구 요청 취소", "Cancel request",
                      "Cancel Request", "Requested", "요청 완료")
# 260902: 클릭 후 "친구요청 실제 전송" 의 유일한 성공 신호 = 대상 UI 의 "요청 취소"(보낸 요청 취소).
# 버튼 소멸 / 팔로잉 / 예외없음 은 성공 아님(False Positive 재발방지, 회장·GPT 지시).
_FRIEND_SENT_KW = ("요청 취소", "친구 요청 취소", "친구 요청을 취소",
                   "Cancel request", "Cancel Request", "Cancel Friend Request")
_FOLLOWING_KW = ("팔로잉", "Following")

_FRIEND_DAILY_PATH = Path(__file__).resolve().parents[2] / "db" / "outbound_friend_daily.json"


def _kst_today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _friend_daily_load() -> dict:
    try:
        data = json.loads(_FRIEND_DAILY_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def _friend_daily_count(account_code: str) -> int:
    """오늘(로컬/KST) 이 계정이 실제로 보낸 친구요청 수 = sent_today (STEP 3-G+R).
    플랫폼 Action Budget 기준 — 발송 후 취소해도 이 수는 줄지 않는다(취소는 발송 이력을 지우지 않음).
    'currently_pending'(현재 살아있는 요청 수)는 별개 개념이며 여기서 집계하지 않는다.
    일일 한도 Gate는 이 값(sent_today)을 사용한다. 개인정보 저장 없음."""
    row = _friend_daily_load().get(account_code) or {}
    return int(row.get("count", 0)) if row.get("date") == _kst_today() else 0


def _friend_daily_save(data: dict) -> None:
    try:
        _FRIEND_DAILY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _FRIEND_DAILY_PATH.write_text(json.dumps(data), encoding="utf-8")
    except Exception as exc:
        logger.error(f"[Friend] daily 상태 저장 실패 | {type(exc).__name__}: {exc}")


def _friend_daily_increment(account_code: str) -> int:
    data = _friend_daily_load()
    row = data.get(account_code) or {}
    today = _kst_today()
    if row.get("date") == today:
        row["count"] = int(row.get("count", 0)) + 1   # blocked 등 기존 키 보존
    else:
        row = {"date": today, "count": 1}
    data[account_code] = row
    _friend_daily_save(data)
    return int(row["count"])


def _friend_daily_blocked(account_code: str) -> str:
    """오늘(KST) 이 계정이 제한 신호(checkpoint/CAPTCHA/일시차단 등)로 Fail-closed
    차단됐으면 사유 문자열, 아니면 ''. 날짜가 바뀌면 자동으로 풀린다(다음 운영일 정상)."""
    row = _friend_daily_load().get(account_code) or {}
    if row.get("date") == _kst_today() and row.get("blocked"):
        return str(row.get("blocked_reason") or "blocked")
    return ""


def _friend_daily_mark_blocked(account_code: str, reason: str) -> None:
    """제한 신호 확인 시 오늘 남은 friend 실행을 전부 skip 하도록 표시한다.
    기존 count 는 보존(그날 이미 보낸 건수는 그대로), 날짜 스탬프로 다음날 자동 해제."""
    data = _friend_daily_load()
    today = _kst_today()
    row = data.get(account_code) or {}
    if row.get("date") != today:
        row = {"date": today, "count": 0}
    row["blocked"] = True
    row["blocked_reason"] = reason
    data[account_code] = row
    _friend_daily_save(data)
    logger.warning(f"[Friend] 오늘 남은 실행 Fail-closed 차단 | {account_code} {reason}")


# 260902 STEP 3-G+R: 이름 기반 국적판정 폐기(정유미·Ym Ym Jong Jong 로마자 유출 2건).
# 판정은 오직 아래 location Evidence Gate 로만 한다.


def _click_see_all_members(driver) -> None:
    """members 페이지에 '모두 보기 / See all' 이 있으면 클릭(실패 무시)."""
    from selenium.webdriver.common.by import By

    for el in driver.find_elements(
        By.XPATH, "//*[self::a or self::div[@role='button'] or self::span]"
    ):
        t = _label_of(el)
        if t in ("모두 보기", "전체 보기", "See all", "See All"):
            try:
                driver.execute_script("arguments[0].click();", el)
                time.sleep(2)
            except Exception:
                pass
            return


# 260902 STEP 3-G: 그룹 회원목록 위젯은 전원 '팔로우'만 렌더 → 친구요청은 프로필 페이지에서만
# 가능(Root Cause 확인). 목록에서 친구버튼을 찾던 접근(_find_member_friend_cards 등)은 폐기.


def _card_has_kr_evidence(text: str) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in _KR_CARD_KW)


def _has_overseas_evidence(text: str) -> bool:
    """텍스트에 명시적 해외 국가/도시가 있으면 True (curated 목록)."""
    t = (text or "").lower()
    return any(k in t for k in _OVERSEAS_LOC_KW)


# 260902 STEP 3-G+S1 (GPT 지시): Foreign Eligibility 판정 입력을 '회원 본인 정보'로만
# Scope 제한한다. group-scoped 프로필 body 에는 그룹명("Korean Cosmetic Wholesale" 등)과
# 그룹 활동 chrome("OO님이 …에 아직 게시물…")이 섞여, _KR_CARD_KW 의 "korea" 가 그룹명을
# 오탐 → 해외 회원 전원 korea_evidence 로 skip 되던 문제(라이브 probe 확정).
_GROUP_CHROME_RE = re.compile(
    r"님이\s.{1,80}?(에 아직 게시물|그룹에 가입했|그룹의 (새 |신규 )?(멤버|회원))"
    r"|hasn'?t posted .{0,20}?(yet|in this group)"
    r"|member since |회원 가입일",
    re.IGNORECASE,
)


def _strip_group_chrome(text: str, group_name: str = "") -> str:
    """판정 입력에서 '회원 본인 정보가 아닌' 줄을 제거한다 (STEP 3-G+S1).
    제거: 그룹명이 든 줄 / 그룹 활동·가입·멤버 안내 chrome.
    유지: 회원 본인이 적은 intro·location·bio 줄. 저장/Scoring 없음 — 즉석 판정용."""
    if not text:
        return ""
    gname = (group_name or "").strip().lower()
    out = []
    for line in text.splitlines():
        l = line.strip()
        if not l:
            continue
        if gname and gname in l.lower():
            continue
        if _GROUP_CHROME_RE.search(l):
            continue
        out.append(l)
    return "\n".join(out)


def _foreign_eligibility(*texts: str) -> tuple[bool, str]:
    """이름·국적추정 없이, 현재 화면 텍스트로만 자동 친구요청 대상 자격 판정.
      (True,  "")                    : 명시적 해외 Evidence 확인 & 한국 Evidence 없음
      (False, "korea_evidence")      : 한국 기반 Evidence 명확 → skip
      (False, "no_overseas_evidence"): 해외 Evidence 없음 / UNKNOWN → skip (Fail-closed)
    저장/Scoring/Enrichment 없음 — boolean + 사유만 반환."""
    combined = " \n ".join(t for t in texts if t)
    if _card_has_kr_evidence(combined):
        return (False, "korea_evidence")
    if _has_overseas_evidence(combined):
        return (True, "")
    return (False, "no_overseas_evidence")


def _clean_group_title(s: str) -> str:
    """FB 페이지 title 정리: 미읽음 알림 수 프리픽스 '(3) ' 제거, 구분자 앞부분만."""
    t = (s or "").strip()
    t = re.sub(r"^\(\d+\+?\)\s*", "", t)          # '(3) ' / '(12+) ' 알림 프리픽스
    for sep in (" | ", " – ", " — ", " • ", " · "):
        if sep in t:
            t = t.split(sep, 1)[0].strip()
            break
    return t


def _group_name_from_page(driver) -> str:
    """회원목록 페이지에서 그룹명을 1회 추출한다 (STEP 3-G+S1, 판정 입력 오염 제거용).
    driver.title 우선(폴백 첫 h1). 실패해도 예외 없이 '' — 최악은 과잉 skip(Fail-closed)."""
    from selenium.webdriver.common.by import By

    try:
        title = _clean_group_title(getattr(driver, "title", ""))
    except Exception:
        title = ""
    if title and "facebook" not in title.lower() and 1 < len(title) < 80:
        return title
    try:
        for h in driver.find_elements(By.TAG_NAME, "h1")[:3]:
            t = _clean_group_title(h.text or "")
            if t and 1 < len(t) < 80 and "facebook" not in t.lower():
                return t
    except Exception:
        pass
    return ""


def _profile_location_text(driver, group_name: str = "") -> str:
    """열린 프로필 현재 화면에서 '회원 본인' location 관련 줄만 추린다(1회, 저장 안 함).
    그룹명·그룹 활동 chrome 은 판정 입력에서 제외한다 (STEP 3-G+S1)."""
    from selenium.webdriver.common.by import By

    try:
        body = driver.find_element(By.TAG_NAME, "body").text or ""
    except Exception:
        return ""
    body = _strip_group_chrome(body, group_name)
    keep = []
    for line in body.splitlines():
        l = line.strip()
        if not l or len(l) > 140:
            continue
        lo = l.lower()
        if any(k in lo for k in _LOCATION_HINT) \
                or any(k in lo for k in _OVERSEAS_LOC_KW) \
                or any(k in lo for k in _KR_CARD_KW):
            keep.append(l)
    return " | ".join(keep[:12])


# ── 260902 STEP 3-G+ : 대상 '본인'의 주 액션 영역만 보고 성공 판정 ─────────────
# False Positive 원인(Runtime DOM probe 확정): 전역 스캔이 프로필의 "알 수도 있는 사람"
# 카드에 있는 제3자의 "요청 취소"/"친구 추가" 버튼을 대상 본인 것으로 오인.
# 근거(probe v3/v4):
#  - full profile 뷰: 주 액션 바 = [data-pagelet="ProfileActions"] (버튼 aria 에 대상 이름 포함).
#  - group-scoped 뷰(canary 가 실제 쓰는 URL /groups/{gid}/user/{uid}/): ProfileActions·프로필 h1
#    없음. 대신 대상 액션 버튼 aria 가 항상 대상 이름 포함("친구 {name}님 추가" /
#    "{name}님에 대한 요청 취소"), 그리고 "메시지(보내기)" 버튼과 같은 최소 컨테이너에 있다.
#  - "알 수도 있는 사람" 카드 버튼은 다른 사람 이름 → 이름 대조로 자동 제외.
# → 성공 판정은 (1) 대상 이름이 든 액션 버튼을 앵커로 잡고 (2) "메시지" 버튼을 함께 담은
#   최소 컨테이너(주 액션 영역)의 라벨만 본다. 클릭 후 stale element 재사용 금지 — 매번 새로.
_FRIEND_MSG_KW = ("메시지 보내기", "메시지", "Message")
_FRIEND_NAME_ACTION_KW = _FRIEND_POS + _FRIEND_SENT_KW + _FOLLOWING_KW + (
    "팔로우", "Follow", "요청", "친구", "Friend")


def _classify_action_label(label: str) -> str:
    """주 액션 버튼 라벨 1개 → 상태. 확정적인 것부터: cancel > friends > following > add."""
    l = (label or "").strip()
    if not l:
        return ""
    if any(k in l for k in _FRIEND_SENT_KW) or re.search(r"님(에 대한|에게 보낸).{0,8}요청.{0,4}취소", l):
        return "cancel"
    if l in ("친구", "Friends") or re.search(r"^친구(\s*[·▾✓].*)?$", l) \
            or (l.startswith("친구") and "추가" not in l and "요청" not in l and "님" not in l):
        return "friends"
    if any(k in l for k in _FOLLOWING_KW):          # "팔로잉"
        return "following"
    if any(k in l for k in _FRIEND_POS) or re.search(r"친구\s+.+님\s*추가", l):
        return "add"
    return ""


def _area_friend_state(labels) -> str:
    """주 액션 영역 버튼 라벨 목록 → 대상의 친구요청 상태.
    'cancel'(요청 보냄 — 우리 목표 달성) / 'friends' / 'following' / 'add'(미발송) / 'unknown'.
    '팔로잉'과 '요청 취소'가 함께 있으면 cancel 우선(친구요청 전송 = 성공, 팔로우는 부수효과)."""
    states = {s for s in (_classify_action_label(x) for x in (labels or [])) if s}
    for pref in ("cancel", "friends", "following", "add"):
        if pref in states:
            return pref
    return "unknown"


def _name_matches(label: str, target_name: str) -> bool:
    """버튼 라벨에 대상 이름이 (느슨하게) 들어있나 — '알 수도 있는 사람' 제3자 버튼 배제용."""
    tn = (target_name or "").strip()
    if not tn or not label:
        return False
    if tn in label:
        return True
    toks = [t for t in re.split(r"\s+", tn) if len(t) >= 2]
    return len(toks) >= 2 and sum(1 for t in toks if t in label) >= 2


def _target_action_area_labels(driver, target_name: str = ""):
    """대상 '본인'의 주 액션 영역 버튼 라벨만 반환. 식별 실패 시 None.

    앵커 = 대상 이름이 든 액션 버튼(aria '친구 {name}님 추가' / '{name}님에 대한 요청 취소' 등).
    그 버튼과 '메시지' 버튼을 함께 담은 가장 가까운 조상 컨테이너의 라벨을 반환한다.
    ProfileActions pagelet 이 있으면 우선 사용. '알 수도 있는 사람' 카드(다른 이름)는 자동 제외."""
    from selenium.webdriver.common.by import By

    # 0) full-profile 뷰: ProfileActions pagelet 우선
    try:
        for pa in driver.find_elements(By.CSS_SELECTOR, "[data-pagelet='ProfileActions']"):
            btns = pa.find_elements(
                By.XPATH, ".//*[@role='button'] | .//button | .//a[@role='button']")
            labels = [x for b in btns for x in _labels_of(b)]
            if labels:
                return labels
    except Exception:
        pass

    tn = (target_name or "").strip()
    if not tn:
        return None

    try:
        allbtns = driver.find_elements(
            By.XPATH, "//*[@role='button'] | //button | //a[@role='button']")
    except Exception:
        return None

    name_btns = []
    for b in allbtns:
        labs = _labels_of(b)
        if any(_name_matches(l, tn) for l in labs) \
                and any(k in l for l in labs for k in _FRIEND_NAME_ACTION_KW):
            name_btns.append(b)

    for nb in name_btns:
        try:
            ancestors = nb.find_elements(By.XPATH, "./ancestor::div")
        except Exception:
            ancestors = []
        for anc in reversed(ancestors[-8:]):   # 가까운 8개, 가까운 조상부터
            try:
                sib = anc.find_elements(
                    By.XPATH, ".//*[@role='button'] | .//button | .//a[@role='button']")
            except Exception:
                continue
            labels = [x for b in sib for x in _labels_of(b)]
            if any(any(m in l for m in _FRIEND_MSG_KW) for l in labels):
                return labels   # 메시지 버튼 동반 = 주 액션 영역

    # 메시지 동반 컨테이너는 못 찾았지만 대상-이름 액션 버튼은 있음 → 그 라벨만이라도 (target-scoped)
    if name_btns:
        return [x for b in name_btns for x in _labels_of(b)]
    return None


def _friend_pending_present(driver, target_name: str = "") -> bool:
    """대상 '본인'이 이미 '요청 보냄/친구' 상태면 True (클릭 전 skip 판단).
    260902: 전역 스캔 폐기 — 제3자 카드의 '요청 취소'로 유효 대상을 건너뛰던 문제 제거.
    주 액션 영역을 못 찾으면 False(=진행), 판정은 클릭 후 다시 한다."""
    labels = _target_action_area_labels(driver, target_name)
    if labels is None:
        return False
    return _area_friend_state(labels) in ("cancel", "friends")


def _friend_request_confirmed(driver) -> bool:
    """(진단용 전역 스캔 — 성공판정에는 쓰지 않는다. 판정은 _target_action_area_labels 국한.)"""
    from selenium.webdriver.common.by import By

    try:
        els = driver.find_elements(
            By.XPATH, "//div[@role='button'] | //a[@role='button'] | //button"
        )
    except Exception:
        return False
    return any(any(k in _label_of(e) for k in _FRIEND_SENT_KW) for e in els)


def _dismiss_overlay(driver) -> None:
    """FB 알림 팝업 등 겹친 오버레이를 ESC 로 닫는다(실패 무시)."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception:
        pass


def _element_visible(el) -> bool:
    """요소가 화면에 실제로 렌더링돼 클릭 가능한가 — is_displayed + rect(width>0, height>0).
    DOM 에만 존재하는 0x0 placeholder 노드를 걸러낸다 (STEP 3-G+S3-FINAL, 260903)."""
    if el is None:
        return False
    try:
        if not el.is_displayed():
            return False
    except Exception:
        return False
    try:
        r = el.rect or {}
        return r.get("width", 0) > 0 and r.get("height", 0) > 0
    except Exception:
        try:
            s = el.size or {}
            return s.get("width", 0) > 0 and s.get("height", 0) > 0
        except Exception:
            return False


def _send_friend_visible(driver, btn, tgt_name: str, use_js: bool = False) -> tuple[bool, str]:
    """실제 렌더링된(rect>0) '친구 추가' 버튼 1개를 1회 클릭 (재시도 없음).
    - use_js=False (목록 카드 경로, GPT §2.A): Selenium native click.
    - use_js=True  (프로필 fallback, GPT §2.B "기존 검증된 프로필 click"): arguments[0].click()
      — 260902 발송 실증 방식. _element_visible 로 실렌더 검증 후에만 사용(0x0 유령 아님).
    클릭 후 대상 본인 주 액션 영역이 'cancel'(요청 취소)이면 성공 (target-scoped, CLOSED REUSE).
    반환 (ok, reason). reason 이 'checkpoint:'로 시작하면 호출자가 즉시 중단."""
    if not _element_visible(btn):
        return (False, "friend_button_not_visible")
    ok, aria, txt = _verify_friend_add_button(btn)
    logger.info(f"[Friend] 클릭직전 | {tgt_name!r} aria={aria!r} text={txt!r} verify={ok} js={use_js}")
    if not ok:
        return (False, "not_a_friend_add_button")
    cp = _checkpoint_detected(driver)
    if cp:
        return (False, f"checkpoint:{cp}")
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
        time.sleep(1.0)
    except Exception:
        pass
    if not _element_visible(btn):
        return (False, "friend_button_not_visible")
    try:
        if use_js:
            driver.execute_script("arguments[0].click();", btn)
        else:
            btn.click()   # Selenium native (WebDriver Element Click — in-view center)
    except Exception as exc:
        return (False, f"click_exc:{type(exc).__name__}")
    time.sleep(_POST_CLICK_SEC)
    area_labels = _target_action_area_labels(driver, tgt_name)
    logger.info(f"[Friend] 클릭직후 | 영역라벨={area_labels} | {tgt_name!r}")
    if area_labels is None:
        return (False, "target_action_area_unresolved")
    state = _area_friend_state(area_labels)
    if state == "cancel":
        return (True, "")
    if state == "friends":
        return (False, "target_already_friends")
    if state == "following":
        return (False, "friend_request_failed_following_only")
    if state == "add":
        return (False, "click_had_no_effect_still_add")
    return (False, f"target_state_unknown:{state}")


# ── 260903 STEP 3-G+S3-FINAL : 목록에서 후보선정 → 화면에 실제 보이는 버튼이면 native click,
#    안 보이면(0x0) 그 후보 프로필 1회 진입해 클릭. location/bio/국적 조사 없음. ──────
# 근거(probe 8회): 이 그룹 /members 는 첫 회원 버튼만 rect>0, 나머지는 DOM 에만 있는 0x0 노드
# → 0x0 노드 JS 클릭은 무효(실발송 0). 프로필 페이지엔 정상 버튼 존재.
# FB '친구 추가' 버튼 aria-label = "친구 {풀네임}님 추가" (visible text 는 비어있을 수 있음).
_FRIEND_ADD_NAME_RE = re.compile(r"^친구\s+(.+?)\s*님\s*추가\s*$")

# 로마자 한국 성씨 (회장 (나) 승인 — 한글 아닌 한국이름도 skip, 중국·베트남 겹침 감내).
_KOREAN_ROMAN_SURNAMES = frozenset({
    "kim", "lee", "rhee", "yi", "park", "pak", "choi", "choe", "jung", "jeong",
    "chung", "kang", "gang", "cho", "jo", "yoon", "yun", "jang", "chang", "lim",
    "im", "rim", "han", "oh", "seo", "suh", "shin", "sin", "kwon", "gwon",
    "hwang", "ahn", "an", "song", "jeon", "jun", "chun", "hong", "yang", "ko",
    "koh", "moon", "mun", "son", "sohn", "bae", "pae", "baek", "paek", "heo",
    "huh", "hur", "yoo", "ryu", "nam", "noh", "roh", "ha", "kwak", "gwak",
    "sung", "seong", "cha", "joo", "ju", "woo", "koo", "ku", "min", "jin",
    "chae", "won", "bang", "gong", "hyun", "hyeon", "ham", "byun", "byeon",
    "yeom", "yum", "do", "so", "sun", "seok", "ma", "gil", "kil", "yeon",
    "pyo", "wi", "pi", "tak", "eom", "ryoo", "lyu",
})
# 명시적 한국 거주 Evidence (카드 텍스트용 — 맨 "korea"/"korean" 제외: 도매상 bio 오탐).
_KR_LOCATION_KW = (
    "대한민국", "한국인", "south korea", "republic of korea", "서울", "seoul",
    "부산", "busan", "인천", "incheon", "대구", "daegu", "광주광역시", "gwangju",
    "대전", "daejeon", "울산", "ulsan", "경기도", "gyeonggi", "제주", "jeju",
    "한국 거주", "거주지 한국", "lives in south korea", "based in seoul",
)
_KR_PHONE_RE = re.compile(r"\+\s?82[\s\-.)]|\b01[016789][\s\-.]?\d{3,4}[\s\-.]?\d{4}\b")
_MFG_FACTORY_KW = (
    "factory", "manufacturer", "manufacturing", "工厂", "工廠", "製造", "制造",
    " oem", " odm", "oem/odm", "oem &", "공장", "제조사", "제조 공장", "제조공장",
)


def _has_hangul(s: str) -> bool:
    return any(
        "가" <= c <= "힣" or "ᄀ" <= c <= "ᇿ" or "㄰" <= c <= "㆏"
        for c in (s or "")
    )


def _should_skip_target(name: str, card_text: str = "") -> tuple[bool, str]:
    """목록 회원카드 정보만으로 '명백한 제외대상'이면 (True, 사유), 아니면 (False, '')=친구후보.
    프로필 진입·국적추정 없음 — 카드에 보이는 이름/텍스트만. (STEP 3-G+S3, 260903)
    사유: hangul_name / korean_surname / korea_location / kr_phone / mfg_factory."""
    nm = (name or "").strip()
    blob = f"{nm}\n{card_text or ''}"
    low = blob.lower()
    if _has_hangul(nm):
        return (True, "hangul_name")
    toks = [t for t in re.split(r"[\s,.]+", nm.lower()) if t]
    if toks and (toks[0] in _KOREAN_ROMAN_SURNAMES or toks[-1] in _KOREAN_ROMAN_SURNAMES):
        return (True, "korean_surname")
    if any(k in low for k in _KR_LOCATION_KW):
        return (True, "korea_location")
    if _KR_PHONE_RE.search(blob):
        return (True, "kr_phone")
    if any(k in low for k in _MFG_FACTORY_KW):
        return (True, "mfg_factory")
    return (False, "")


def _scan_member_cards(driver, group_url: str = "", limit: int = 40,
                       max_rounds: int = 20) -> list[dict]:
    """그룹 /members 목록에서 '친구 추가' 대상 후보만 추출. 팔로우전용(창작자/페이지)은 미반환.
    앵커 = aria-label '친구 {이름}님 추가' 버튼. 버튼이 화면에 실렌더인지(0x0 여부)는
    호출자가 _element_visible 로 확인해 native click / 프로필 fallback 을 결정한다.
    각 항목: {identifier(uid), name, card_text, profile_url, _btn}."""
    from selenium.webdriver.common.by import By

    base = re.sub(r"/members.*$", "", (group_url or "").split("?")[0].rstrip("/"))
    out: list[dict] = []
    seen: set[str] = set()
    stall = 0
    for _round in range(max(1, max_rounds)):
        prev = len(out)
        try:
            btns = driver.find_elements(
                By.XPATH,
                "//*[@role='button' or self::button][contains(@aria-label,'님 추가')"
                " or contains(@aria-label,'님추가')]",
            )
        except Exception:
            btns = []
        for b in btns:
            if len(out) >= limit:
                break
            try:
                aria = b.get_attribute("aria-label") or ""
            except Exception:
                continue
            mm = _FRIEND_ADD_NAME_RE.search(aria)
            if not mm:
                continue
            name = mm.group(1).strip()
            uid, card_text = "", ""
            try:
                for anc in b.find_elements(By.XPATH, "./ancestor::div[position()<=8]"):
                    links = anc.find_elements(By.CSS_SELECTOR, "a[href*='/user/']")
                    if not links:
                        continue
                    href = links[0].get_attribute("href") or ""
                    um = re.search(r"/user/(\d+)", href)
                    if um:
                        uid = um.group(1)
                    t = (anc.text or "").strip()
                    if t and len(t) > len(card_text):
                        card_text = t[:300]
                    if uid:
                        break
            except Exception:
                pass
            key = uid or name
            if not key or key in seen:
                continue
            seen.add(key)
            out.append({"identifier": uid, "name": name, "card_text": card_text,
                        "profile_url": (f"{base}/user/{uid}/" if (base and uid) else ""),
                        "_btn": b})
        if len(out) >= limit:
            break
        if _round > 0 and len(out) == prev:
            stall += 1
            if stall >= 4:
                break   # 여러 번 스크롤해도 새 카드 없음 → 목록 끝
        else:
            stall = 0
        try:
            driver.execute_script("window.scrollBy(0, 2400);")
            time.sleep(1.8)
        except Exception:
            break
    logger.info(f"[Friend] 목록 카드 스캔 | 친구가능 {len(out)}명")
    return out


def _friend_button_on_profile(driver):
    """열린 프로필 페이지에서 '친구 추가' 버튼 1개 — 화면에 실제 보이는(rect>0) 것만. 없으면 None."""
    btn = _find_friend_add_button(driver)
    return btn if _element_visible(btn) else None


def friend_request_canary(
    group_url: str,
    *,
    account_code: str = YUNA_ACCOUNT_CODE,
    max_scroll: int = 6,
    max_requests: int = 1,
    pace_range: tuple = (120, 240),
    dry_run: bool = True,
    repo=None,
    driver=None,
    driver_factory=None,
    browser_stopper=None,
) -> dict:
    """STEP 3-G HUMAN SOP (260903): 한 그룹의 /members 에서 **사람 직원처럼** 처리한다.
      현재 화면 회원 확인 → 한국인·명백한 중국공장 SKIP → 그 외 친구추가
      → 아래로 스크롤 → 새로 렌더된 회원 다시 확인 → 계속
      → 더 이상 새 회원이 없으면 종료(호출자가 다음 그룹으로).
    클릭:
      A. 목록 '친구 추가' 버튼이 실렌더(rect>0)면 Selenium native click 1회.
      B. 0x0(미렌더)이면 그 회원 프로필 1회 진입 → visible 버튼만 클릭(JS, 260902 실증)
         → **목록으로 복귀** → 계속. 프로필에서 추가 판정 없음.
    실패 정책: 일반 대상 1명의 버튼 오류는 **그 대상만 skip 하고 다음 사람 계속**.
      전체 STOP 은 CAPTCHA/checkpoint/action block/Kill-switch/daily_friend_limit/브라우저 불가만.
    `driver` 를 주면 그 브라우저를 재사용하고 종료하지 않는다(그룹 순회용).
    개인별 저장 없음. 성공 시 로컬 집계(date+count)만 +1. Kill-switch·한도·day-block CLOSED REUSE."""
    repo = repo or _default_repo()

    _sent_list: list[dict] = []

    def _out(result: str, reason: str = "", c: dict | None = None) -> dict:
        last_ok = next((r for r in reversed(_sent_list) if r.get("result") == "success"), {})
        return {
            "result": result, "reason": reason, "action_type": FRIEND_ACTION,
            "account_code": account_code,
            "target_identifier": last_ok.get("identifier", (c or {}).get("identifier", "")),
            "target_url": (c or {}).get("profile_url", ""),
            "target_name": last_ok.get("name", (c or {}).get("name", "")),
            "daily_count": _friend_daily_count(account_code),
            "sent": sum(1 for r in _sent_list if r.get("result") == "success"),
            "results": list(_sent_list),
        }

    account = repo.get_publish_account(account_code)
    if not account or not account.get("automation_enabled", False):
        logger.warning(f"[Friend] Kill-switch OFF | account={account_code}")
        return _out("skipped", "automation_disabled")
    if dry_run:
        return _out("skipped", "dry_run")
    blocked = _friend_daily_blocked(account_code)
    if blocked:   # 오늘 제한 신호 발생 → 남은 실행 전부 Fail-closed (다음 운영일 자동 해제)
        logger.warning(f"[Friend] 오늘 차단됨 — skip | {account_code} {blocked}")
        return _out("skipped", f"daily_blocked:{blocked}")
    cap = int((repo.get_account_outbound_limits(account_code) or {}).get("friend", 0) or 0)
    done_today = _friend_daily_count(account_code)
    if cap <= 0 or done_today >= cap:   # 한도 미설정(0)도 Fail-closed
        logger.warning(f"[Friend] 일일 한도 — skip | {account_code} {done_today}/{cap}")
        return _out("skipped", f"daily_limit:{done_today}/{cap}")
    if os.getenv(FRIEND_LIVE_ENV, "").strip().lower() != "true":
        raise OutboundActionError(
            f"Live 친구추가 차단 — {FRIEND_LIVE_ENV}=true 필요(회장 승인 게이트)"
        )

    own_driver = driver is None
    if own_driver:
        driver = (driver_factory or _default_driver_factory)()
    stop_browser = browser_stopper or _default_browser_stopper
    outcome, reason = "failed", ""
    members_url = group_members_url(group_url)

    def _ok_count() -> int:
        return sum(1 for r in _sent_list if r.get("result") == "success")

    try:
        driver.get(members_url)
        time.sleep(_PAGE_SETTLE_SEC)
        cp = _checkpoint_detected(driver)
        if cp:
            _friend_daily_mark_blocked(account_code, f"checkpoint:{cp}")
            return _out("skipped", f"checkpoint:{cp}")
        _click_see_all_members(driver)
        group_name = _group_name_from_page(driver)   # STEP 3-G+S1: 판정 입력 오염 제거용
        logger.info(f"[Friend] 그룹 진입 | {group_name!r} | 목표 {max_requests}건, 한도 {cap}")

        processed: set[str] = set()
        stall = 0
        for _iter in range(_FRIEND_MAX_ITER):
            if _friend_daily_count(account_code) >= cap:
                reason = reason or f"daily_limit:{cap}/{cap}"
                logger.info(f"[Friend] 일일 한도 도달 — 종료 | {cap}/{cap}")
                break
            if _ok_count() >= max_requests:
                break

            # 현재 화면에 렌더된 회원만 확인 (사람처럼)
            cards = _scan_member_cards(driver, group_url, limit=60, max_rounds=1)
            target = None
            for c in cards:
                ident = c.get("identifier") or ""
                name = c.get("name", "")
                key = ident or name
                if not key or key in processed:
                    continue
                processed.add(key)
                if ident and ident in _FRIEND_CANARY_SKIP_IDS:
                    logger.info(f"[Friend] 제외 대상 skip | {ident}")
                    continue
                card_txt = _strip_group_chrome(c.get("card_text", ""), group_name)
                skip, why_skip = _should_skip_target(name, card_txt)
                if skip:
                    logger.info(f"[Friend] 제외 — {why_skip} | {name!r}")
                    continue
                target = c
                break

            if target is None:
                # 이번 화면에 새 후보 없음 → 사람처럼 아래로 스크롤 후 다시 확인
                stall += 1
                if stall >= _FRIEND_SCROLL_STALL_MAX:
                    reason = reason or "group_exhausted"
                    logger.info("[Friend] 이 그룹에 더 이상 새 회원 없음 — 그룹 종료")
                    break
                try:
                    driver.execute_script("window.scrollBy(0, 1200);")
                    time.sleep(1.5)
                except Exception:
                    reason = reason or "scroll_failed"
                    break
                continue
            stall = 0

            ident = target.get("identifier") or ""
            name = target.get("name", "")
            logger.info(f"[Friend] 대상 후보 | {ident or '?'} {name!r}")
            btn = target.get("_btn")
            went_profile = False

            if _element_visible(btn):
                # A. 목록 버튼이 실렌더 → native click
                logger.info(f"[Friend] 목록 버튼 visible → native click | {name!r}")
                ok, why = _send_friend_visible(driver, btn, name)
            else:
                # B. 0x0 → 프로필 1회 진입해 visible 버튼만 클릭 (판정 없음)
                prof_url = target.get("profile_url", "")
                if not prof_url:
                    logger.info(f"[Friend] 프로필 URL 없음 — 이 대상 skip | {name!r}")
                    continue
                went_profile = True
                logger.info(f"[Friend] 목록 버튼 0x0 → 프로필 1회 진입 | {name!r}")
                try:
                    driver.get(prof_url)
                    time.sleep(_PAGE_SETTLE_SEC)
                except Exception as exc:
                    ok, why = False, f"profile_get_exc:{type(exc).__name__}"
                else:
                    cp = _checkpoint_detected(driver)
                    if cp:
                        _friend_daily_mark_blocked(account_code, f"checkpoint:{cp}")
                        return _out("skipped", f"checkpoint:{cp}")
                    pbtn = _friend_button_on_profile(driver)
                    if pbtn is None:
                        ok, why = False, "profile_friend_button_not_visible"
                    else:
                        # 260902 발송 실증 방식 = JS click (실렌더 검증 후에만)
                        ok, why = _send_friend_visible(
                            driver, pbtn, _profile_name_from_btn(pbtn) or name, use_js=True)

            if ok:
                n = _friend_daily_increment(account_code)
                _sent_list.append({"identifier": ident, "name": name,
                                   "result": "success", "daily_count": n})
                logger.info(f"[Friend] 친구요청 성공 | {ident or '?'} {name!r} daily_count={n}")
            elif isinstance(why, str) and why.startswith("checkpoint:"):
                _friend_daily_mark_blocked(account_code, why)   # 계정 안전 — 그날 전체 중단
                return _out("skipped", why)
            else:
                # 일반 버튼 오류 → 그 대상만 skip, 다음 사람 계속 (Human SOP §6)
                _sent_list.append({"identifier": ident, "name": name,
                                   "result": "failed", "reason": why})
                logger.info(f"[Friend] 실패 — 이 대상만 skip, 계속 | {name!r} {why}")

            if went_profile:   # 프로필 다녀왔으면 목록 복귀 후 계속
                try:
                    driver.get(members_url)
                    time.sleep(_PAGE_SETTLE_SEC)
                    _click_see_all_members(driver)
                except Exception as exc:
                    reason = f"members_return_failed:{type(exc).__name__}"
                    break
            if ok and _ok_count() < max_requests and _friend_daily_count(account_code) < cap:
                time.sleep(random.uniform(pace_range[0], pace_range[1]))

        outcome = "success" if _ok_count() > 0 else "failed"
        if outcome == "failed":
            # 실제 클릭 시도가 있었으면 마지막 실패 사유를, 없었으면 그룹 소진/후보없음을 남긴다.
            last_fail = next((r.get("reason") for r in reversed(_sent_list)
                              if r.get("result") == "failed"), "")
            reason = last_fail or reason or "no_candidate"
    except OutboundActionError:
        raise
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"[:400]
        logger.warning(f"[Friend] 예외 | {reason}")
    finally:
        if own_driver:
            try:
                driver.quit()
            except Exception as exc:
                logger.warning(f"[Friend] driver.quit 실패 | {exc}")
            try:
                stop_browser()
            except Exception as exc:
                logger.warning(f"[Friend] stop_browser 실패 | {exc}")

    logger.info(f"[Friend] canary 완료 | sent={_ok_count()} "
                f"daily_count={_friend_daily_count(account_code)} reason={reason!r}")
    return _out(outcome, reason)


_PROFILE_UNAVAILABLE = (
    "content isn't available", "this content isn't available right now",
    "이 콘텐츠는 현재 사용할 수 없", "이 페이지를 사용할 수 없", "page isn't available",
    "콘텐츠를 사용할 수 없습니다", "이 계정은 사용할 수 없",
)
_LOCATION_HINT = ("lives in", "from ", "님이 사는 곳", "님의 출신지", "출신", "거주",
                  "sống tại", "đến từ", "based in")


def _has_friend_add_button(driver) -> bool:
    """열려 있는 프로필에 '친구 추가/Add Friend' 버튼이 있으면 True. 클릭하지 않는다."""
    return _find_friend_add_button(driver) is not None


def _find_friend_add_button(driver):
    """열려 있는 프로필 페이지에서 실제 '친구 추가' 버튼 요소 1개(없으면 None).
    보이는(displayed) 것만, 알림 문장 오탐은 _FRIEND_NEG 로 이미 걸러짐."""
    from selenium.webdriver.common.by import By

    try:
        els = driver.find_elements(
            By.XPATH, "//*[@role='button'] | //button | //a[@role='button']"
        )
    except Exception:
        return None
    for e in els:
        if not _is_friend_add_el(e):
            continue
        try:
            if not e.is_displayed():
                continue
        except Exception:
            pass
        return e
    return None


def _profile_name_from_btn(el) -> str:
    """친구버튼 aria-label '친구 OOO님 추가' 에서 이름 OOO 만 추출(실패 시 '')."""
    try:
        aria = el.get_attribute("aria-label") or ""
    except Exception:
        return ""
    m = re.search(r"친구\s+(.+?)\s*님?\s*추가", aria)
    if m:
        return m.group(1).strip()
    m = re.search(r"(?:Add|send.*request to)\s+(.+)", aria, re.I)
    return m.group(1).strip() if m else ""


def _verify_friend_add_button(el):
    """클릭 직전 최종 검증 — 요소 aria-label/text 가 실제 '친구 … 추가' 버튼인가.
    반환: (ok, aria, text)."""
    aria = txt = ""
    try:
        aria = (el.get_attribute("aria-label") or "").strip()
    except Exception:
        pass
    try:
        txt = (el.text or "").strip()
    except Exception:
        pass
    both = f"{aria} {txt}"
    if any(neg in both for neg in _FRIEND_NEG):
        return (False, aria, txt)
    lo = both.lower()
    ok = bool(re.search(r"친구.{0,20}추가", aria)) or "친구 추가" in txt or "친구추가" in txt \
        or "add friend" in lo or "add as friend" in lo
    return (ok, aria, txt)


def _extract_profile_info(driver, profile_url: str) -> dict:
    """열려 있는 프로필 페이지에서 화면상 확인 가능한 최소 정보만 읽는다 (STEP 3-E).
    정보가 없으면 빈 문자열(UNKNOWN). 추측해서 채우지 않는다."""
    from selenium.webdriver.common.by import By

    name = ""
    for css in ("h1", "h1 span", "[role='main'] h1"):
        try:
            t = (driver.find_element(By.CSS_SELECTOR, css).text or "").strip()
            if t:
                name = t[:100]
                break
        except Exception:
            continue

    try:
        body = driver.find_element(By.TAG_NAME, "body").text or ""
    except Exception:
        body = ""
    low = body.lower()
    unavailable = any(m in low for m in _PROFILE_UNAVAILABLE)

    intro = ""
    for css in (
        "div[data-pagelet='ProfileTilesFeed_0']",
        "div[data-pagelet*='ProfileTiles']",
        "div[data-pagelet='ProfileActions'] ~ div",
    ):
        try:
            els = driver.find_elements(By.CSS_SELECTOR, css)
            intro = " ".join((e.text or "").strip() for e in els[:2]).strip()
            if intro:
                break
        except Exception:
            continue

    loc = ""
    for line in body.splitlines():
        l = line.strip()
        if l and any(k in l.lower() for k in _LOCATION_HINT) and len(l) < 120:
            loc += " " + l

    return {
        "display_name": name,
        "profile_url": profile_url,
        "bio_text": intro[:400],
        "location_text": loc.strip()[:200],
        "page_category": "",
        "recent_post_text": "",
        "follower_count": -1,
        "has_photo": True,
        "is_private": unavailable,
        "has_recent_activity": not unavailable,
    }


def friend_in_group(
    group_url: str,
    *,
    account_code: str = YUNA_ACCOUNT_CODE,
    dry_run: bool = True,
    target_url: str | None = None,
    target_source: str = "feed",   # "feed"(게시물 작성자, DEFER) | "members"(/members 첫 적합 회원)
    repo=None,
    driver_factory=None,
    browser_stopper=None,
) -> dict:
    """그룹에서 대상 1명(target_url 지정 시 그 사람 / 아니면 target_source 방식으로 자동선택)
    에게 친구요청 1회. Kill-switch·일일한도·중복·checkpoint·친구버튼 확인 후 클릭.

    반환 dict: {result: success|failed|skipped, reason, target_url, action_type, account_code}
    """
    def _out(result: str, reason: str = "", t_url: str = "") -> dict:
        return {
            "result": result,
            "reason": reason,
            "target_url": t_url or target_url or "",
            "action_type": FRIEND_ACTION,
            "account_code": account_code,
        }

    repo = repo or _default_repo()

    # 1. Kill-switch (Fail-closed) — 읽기 전용
    account = repo.get_publish_account(account_code)
    if not account or not account.get("automation_enabled", False):
        logger.warning(f"[Friend] Kill-switch OFF — 실행 안 함 | account={account_code}")
        return _out("skipped", "automation_disabled")

    # 2. dry_run — 브라우저 미기동
    if dry_run:
        logger.info(f"[Friend] dry_run — 클릭 안 함 | group={group_url}")
        return _out("skipped", "dry_run")

    # 3. 일일 한도 (Fail-closed) — Account_Registry.daily_friend_limit 미설정 = 0 = 차단
    gate = _daily_limit_gate(repo, account_code, FRIEND_ACTION, "friend")
    if gate:
        return _out("skipped", gate)

    # 4. Live 게이트 (follow 와 별도)
    if os.getenv(FRIEND_LIVE_ENV, "").strip().lower() != "true":
        raise OutboundActionError(
            f"Live 친구추가 차단 — {FRIEND_LIVE_ENV}=true 필요(회장 승인 게이트)"
        )

    make_driver = driver_factory or _default_driver_factory
    stop_browser = browser_stopper or _default_browser_stopper
    driver = make_driver()
    outcome, reason, resolved = "failed", "", (target_url or "")
    try:
        # 3-1. 대상 결정
        if not resolved:
            if target_source == "members":
                driver.get(group_members_url(group_url))
                time.sleep(_PAGE_SETTLE_SEC)
                cp = _checkpoint_detected(driver)
                if cp:
                    return _out("skipped", f"checkpoint:{cp}")
                resolved = _pick_first_eligible_member(driver, repo, account_code)
                if not resolved:
                    return _out("failed", "no_eligible_member", group_url)
            else:
                driver.get(group_url)
                time.sleep(_PAGE_SETTLE_SEC)
                cp = _checkpoint_detected(driver)
                if cp:
                    return _out("skipped", f"checkpoint:{cp}")
                resolved = _find_first_group_author_url(driver)
                if not resolved:
                    return _out("failed", "group_author_not_found", group_url)

        # 3-2. 대상 프로필 이동 — 그룹-유저 링크면 profile.php?id= 형태로 방문
        #      (facebook.com/{숫자id} 는 유효하지 않아 홈으로 리다이렉트됨)
        _m = re.search(r"/groups/\d+/user/(\d+)", resolved)
        visit_url = (
            f"https://www.facebook.com/profile.php?id={_m.group(1)}" if _m else resolved
        )
        driver.get(visit_url)
        time.sleep(_PAGE_SETTLE_SEC)
        cp = _checkpoint_detected(driver)
        if cp:
            return _out("skipped", f"checkpoint:{cp}", resolved)

        # 3-3. 중복(같은 사람 재요청) 방지 — 로컬만
        key = _dedup_key(account_code, resolved, FRIEND_ACTION)
        if _local_seen(key):
            return _out("skipped", "duplicate_local", resolved)

        # 3-3b. 한국 기반 명확 Evidence면 제외 (UNKNOWN 이면 진행 — 회장 정책).
        #       제외 대상은 로컬 dedup 에 마킹해 다음 canary 가 같은 사람을 다시 안 고르게 한다.
        try:
            from modules.interaction_engine.outbound_rules import evaluate
            _info = _extract_profile_info(driver, resolved)
            if _info.get("is_private"):
                _local_mark(key, "skipped_abnormal")
                return _out("skipped", "abnormal_profile", resolved)
            _r = evaluate(_info, source_is_beauty_group=True)
            if _r["filter_reason"] in ("korean_based", "korean_national"):
                _local_mark(key, f"skipped_{_r['filter_reason']}")
                return _out("skipped", f"korean_excluded:{_r['filter_reason']}", resolved)
        except Exception as exc:
            logger.warning(f"[Friend] 한국여부 확인 생략(오류) | {exc}")

        # 3-4. 친구추가 버튼 찾기
        from selenium.webdriver.common.by import By

        all_btns = driver.find_elements(
            By.XPATH, "//*[self::button or self::a or @role='button']"
        )
        btn = next((el for el in all_btns if _is_friend_add_el(el)), None)
        if btn is None:
            seen_labels = [x for x in (_label_of(el) for el in all_btns) if x][:20]
            logger.warning(
                f"[Friend] 친구버튼 미발견 | target={resolved} visit={visit_url} | 버튼목록={seen_labels}"
            )
            outcome, reason = "failed", "friend_button_not_found"
        else:
            btn.click()
            time.sleep(_POST_CLICK_SEC)
            # 3-5. 상태 재확인 — "요청 취소/Requested" 로 바뀌면 성공
            pending = any(
                any(m in _label_of(el) for m in
                    ("요청 취소", "요청됨", "Cancel request", "Requested", "Cancel Request"))
                for el in driver.find_elements(
                    By.XPATH, "//*[self::button or self::a or @role='button']"
                )
            )
            if pending:
                outcome, reason = "success", ""
                _local_mark(key, "success")
            else:
                outcome, reason = "failed", "request_state_not_confirmed"
    except OutboundActionError:
        raise
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"[:400]
        logger.warning(f"[Friend] 예외 | {reason}")
    finally:
        try:
            driver.quit()
        except Exception as exc:
            logger.warning(f"[Friend] driver.quit 실패 | {exc}")
        try:
            stop_browser()
        except Exception as exc:
            logger.warning(f"[Friend] stop_browser 실패 | {exc}")

    # 5. 기록 (success/failed 만) — 로컬 dedup + SSOT (follow_once 와 통일).
    #    친구버튼 미발견도 failed 로 기록(다음 조사 근거). checkpoint/한국제외/중복 skip 은 미기록.
    if outcome in ("success", "failed") and resolved:
        _local_mark(_dedup_key(account_code, resolved, FRIEND_ACTION), outcome)
        try:
            repo.create_outbound_action({
                "account_code_ref": account_code,
                "target_url": resolved,
                "target_identifier": _loose_identifier(resolved),
                "action_type": FRIEND_ACTION,
                "result": outcome,
                "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "error_reason": reason,
            })
        except Exception as exc:
            logger.error(
                f"[Friend] SSOT 기록 실패 | target={resolved} | {type(exc).__name__}: {exc}"
            )

    logger.info(f"[Friend] 완료 | target={resolved} result={outcome} reason={reason!r}")
    return _out(outcome, reason, resolved)


# ── Instagram Like (260907) — follow_once 와 동일 계약의 형제 액션 ────────────
#
#   외부 참조 패턴(adolfousier/socialcrabs)에서 다음 순서만 ADAPT 한다:
#     Target URL → 현재 Like 여부 확인 → Like 클릭 → '좋아요 취소' 상태로 Verify → Result
#   전체 시스템(Playwright/Node)은 도입하지 않는다 — Browser/Session/Dedup/Logger/
#   Audit 는 기존 AdsPower+Selenium harness 를 그대로 REUSE 한다.
#
#   - dry_run=True 기본 (브라우저 미기동)
#   - Live 는 OUTBOUND_LIKE_LIVE_ENABLED=true 필수 (follow/friend 와 별도 게이트)
#   - 일일 한도는 OUTBOUND_LIKE_DAILY_LIMIT (미설정=0=차단, Fail-closed).
#     Account_Registry 에는 like 한도 필드가 없다 — 스케줄러 연결 단계에서
#     daily_like_limit 로 이관하는 것을 전제로 한 Canary 한정 임시 게이트다.
#   - 계정마다 AdsPower 프로필이 다르므로 adspower_profile_id 를 명시로 받는다
#     (follow/friend 의 get_default_account() 단일 프로필 가정과 다른 점).
#   - 스케줄러/자동 caller 미연결 — 수동/테스트 호출 전용.
#   - dedup 은 like 에만 다른 계약을 쓴다(260907 GPT 판정): 성공(=already_liked 포함)만
#     영구 차단하고, 기술적 실패는 Audit 만 남기고 재시도를 허용한다.
#     friend/follow 의 dedup 계약은 이 변경의 영향을 받지 않는다.

LIKE_LIVE_ENV = "OUTBOUND_LIKE_LIVE_ENABLED"
LIKE_LIMIT_ENV = "OUTBOUND_LIKE_DAILY_LIMIT"
LIKE_ACTION = "like"

_IG_PAGE_SETTLE_SEC = 8
_IG_POST_CLICK_SEC = 3
# 게시물 본문 하트는 24px, 댓글 하트는 12px — 댓글 좋아요 오클릭 차단용 하한.
_IG_LIKE_MIN_ICON_PX = 20

# aria-label 완전일치만 인정한다(부분일치는 "Liked by ..." 등 오탐 위험).
_IG_LIKE_POS = frozenset({"좋아요", "Like"})
_IG_LIKE_NEG = frozenset({"좋아요 취소", "Unlike"})

_IG_SHORTCODE_RE = re.compile(r"^/(?:p|reel|tv)/([A-Za-z0-9_-]+)/?$")

# 아이콘에서 가장 가까운 semantic clickable 조상만 고른다(큰 컨테이너로 올라가지 않음).
_IG_CLOSEST_JS = (
    "const s = arguments[0];"
    "return s.closest('button') || s.closest('[role=\"button\"]') || null;"
)


def extract_instagram_target(target_url: str) -> str:
    """승인된 HTTPS Instagram 게시물 URL 에서 shortcode 를 뽑는다(Fail-closed)."""
    parsed = urlparse((target_url or "").strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        host == "instagram.com" or host.endswith(".instagram.com")
    ):
        raise OutboundActionError("승인된 HTTPS Instagram 게시물 URL 필수")
    m = _IG_SHORTCODE_RE.match(parsed.path)
    if not m:
        raise OutboundActionError("Instagram 게시물(p/reel/tv) 식별자 추출 실패")
    return m.group(1)


def _is_ig_unlike_label(label: str) -> bool:
    return (label or "").strip() in _IG_LIKE_NEG


def _is_ig_like_label(label: str) -> bool:
    return (label or "").strip() in _IG_LIKE_POS


def _ig_rendered(el) -> bool:
    """실렌더 검증(회장 규칙 1) — DOM 에 있다고 클릭 가능한 게 아니다.
    is_displayed()=True 이고 rect 가 0x0 이 아니어야 클릭 대상으로 인정한다."""
    try:
        if not el.is_displayed():
            return False
        rect = el.rect or {}
        return float(rect.get("width") or 0) > 0 and float(rect.get("height") or 0) > 0
    except Exception:
        return False


def _ig_post_scope(driver):
    """대상 게시물 영역(article → main). 전역 스캔 금지(회장 규칙 6) —
    같은 '좋아요' 라벨이 추천 카드·다른 게시물에도 있으므로 이 영역 안에서만 판정한다.
    영역을 못 찾으면 None 을 돌려 전역 폴백 없이 실패 처리한다."""
    from selenium.webdriver.common.by import By

    for sel in ("article", "main"):
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
        except Exception:
            els = []
        if els:
            return els[0]
    return None


def _ig_like_icons(driver) -> list:
    """대상 게시물 영역 안의 좋아요 아이콘만 [(label, element)] 로 반환.
    댓글 좋아요(12px)는 크기 하한으로, 유령노드(0x0)는 실렌더 검증으로 제외한다."""
    from selenium.webdriver.common.by import By

    scope = _ig_post_scope(driver)
    if scope is None:
        return []
    out = []
    for svg in scope.find_elements(By.CSS_SELECTOR, "svg[aria-label]"):
        try:
            label = (svg.get_attribute("aria-label") or "").strip()
        except Exception:
            continue
        if not (_is_ig_like_label(label) or _is_ig_unlike_label(label)):
            continue
        try:
            height = int(float(svg.get_attribute("height") or 0))
        except (TypeError, ValueError):
            height = 0
        if height < _IG_LIKE_MIN_ICON_PX:
            continue
        if not _ig_rendered(svg):
            logger.info(f"[Like] 유령노드(0x0) 제외 | label={label}")
            continue
        out.append((label, svg))
    return out


def _ig_like_state(driver) -> str:
    """대상 article 안의 Like/Unlike 아이콘 '존재 여부'로 판정한다(260907 GPT 판정).

    'liked'      — Unlike/좋아요 취소만 있음
    'not_liked'  — Like/좋아요만 있음
    'unknown'    — 아이콘 없음, 또는 둘 다 있어 모호함(Fail-closed)
    fill/색상/좋아요 수는 판정에 쓰지 않는다.
    """
    icons = _ig_like_icons(driver)
    if not icons:
        return "unknown"
    has_like = any(_is_ig_like_label(label) for label, _ in icons)
    has_unlike = any(_is_ig_unlike_label(label) for label, _ in icons)
    if has_unlike and not has_like:
        return "liked"
    if has_like and not has_unlike:
        return "not_liked"
    logger.warning("[Like] Like/Unlike 아이콘 동시 존재 — 모호(unknown 처리)")
    return "unknown"


def _ig_like_icon_to_click(driver):
    """클릭할 Like 아이콘(not_liked 상태의 24px 본문 하트) 1개. 없으면 None."""
    for label, svg in _ig_like_icons(driver):
        if _is_ig_like_label(label):
            return svg
    return None


def _ig_clickable(driver, svg):
    """아이콘에서 가장 가까운 semantic clickable 조상(button 우선 → [role=button]).

    큰 상위 컨테이너까지 올라가지 않는다 — 260907 Canary #1 에서 과도하게 큰
    조상을 클릭 대상으로 잡아 hit-test 가 다른 요소와 충돌했다(ElementClickIntercepted).
    반환 요소는 실렌더 검증을 통과하고 해당 아이콘을 실제 descendant 로 포함해야 한다.
    조건 미충족이면 None.
    """
    try:
        target = driver.execute_script(_IG_CLOSEST_JS, svg)
    except Exception as exc:
        logger.warning(f"[Like] closest 조회 실패 | {type(exc).__name__}: {exc}")
        return None
    if target is None:
        return None
    if not _ig_rendered(target):
        logger.info("[Like] 클릭 대상 미렌더(0x0) — 클릭하지 않음")
        return None
    try:
        contains = driver.execute_script(
            "return arguments[0].contains(arguments[1]);", target, svg
        )
    except Exception:
        contains = True  # 조회 실패는 closest 결과를 신뢰(구조상 조상)
    if not contains:
        logger.info("[Like] 클릭 대상이 아이콘을 포함하지 않음 — 클릭하지 않음")
        return None
    return target


def _ig_click_like(driver, target) -> None:
    """실렌더 검증을 통과한 요소에 JS click 을 정확히 1회 보낸다(회장 규칙 3·4·10).

    native .click() / ActionChains / 좌표 click / CDP click /
    PointerEvent·MouseEvent dispatch / 재시도 loop 는 모두 사용하지 않는다.
    """
    driver.execute_script("arguments[0].click();", target)


def _like_daily_gate(repo, account_code: str) -> str:
    """오늘 이 계정 like 건수가 한도 이상이면 사유 문자열, 아니면 ''.
    한도 미설정(0) = 차단(Fail-closed). 조회 실패는 예외 그대로 전파."""
    try:
        cap = int(os.getenv(LIKE_LIMIT_ENV, "0") or 0)
    except ValueError:
        cap = 0
    used = repo.count_outbound_actions_today(account_code, LIKE_ACTION)
    if used >= cap:
        logger.warning(
            f"[Like] 일일 한도 — skip | {account_code} used={used} cap={cap}"
        )
        return f"daily_limit_exceeded:{used}/{cap}"
    return ""


def _like_ssot_blocked(repo, account_code: str, target_identifier: str) -> str:
    """이전 '성공' 기록이 있으면 그 record_id, 없으면 ''.

    like 는 실패 attempt 가 재시도를 막지 않는다(260907 GPT 판정). result 판별이
    가능한 Repository 면 성공 기록만 차단하고, 판별 메서드가 없는 구현/Fake 에서는
    기존 계약(기록이 있으면 차단)을 그대로 유지한다.
    """
    getter = getattr(repo, "find_outbound_action_result", None)
    if getter is None:
        return repo.find_outbound_action(account_code, target_identifier, LIKE_ACTION) or ""
    found = getter(account_code, target_identifier, LIKE_ACTION)
    if found and (found.get("result") or "") == "success":
        return found.get("record_id", "") or ""
    return ""


def _like_driver_factory(adspower_profile_id: str):
    def _make():
        from modules.sns.facebook_crawler import get_driver

        return get_driver(adspower_profile_id)

    return _make


def _like_browser_stopper(adspower_profile_id: str):
    def _stop() -> None:
        from modules.sns.facebook_crawler import stop_browser

        stop_browser(adspower_profile_id)

    return _stop


def like_once(
    target_url: str,
    *,
    account_code: str,
    adspower_profile_id: str = "",
    dry_run: bool = True,
    repo=None,
    driver_factory=None,
    browser_stopper=None,
) -> dict:
    """지정 계정으로 Instagram 게시물 1건에 Like 를 1회 시도한다.

    반환 dict: {result: success|failed|skipped, reason, target_identifier,
               target_url, action_type, account_code, adspower_profile_id,
               before_state, after_state, click_count, record_id}

    이미 좋아요 상태면 클릭하지 않고 success/already_liked(no-op)로 끝낸다.
    """
    target_identifier = extract_instagram_target(target_url)
    key = _dedup_key(account_code, target_identifier, LIKE_ACTION)

    def _out(result: str, reason: str = "", record_id: str = "",
             before: str = "", after: str = "", clicks: int = 0) -> dict:
        return {
            "result": result,
            "reason": reason,
            "target_identifier": target_identifier,
            "target_url": target_url,
            "action_type": LIKE_ACTION,
            "account_code": account_code,
            "adspower_profile_id": adspower_profile_id,
            "before_state": before,
            "after_state": after,
            "click_count": clicks,
            "record_id": record_id,
        }

    repo = repo or _default_repo()

    # 1. Kill-switch (Fail-closed) — automation_enabled 명시 true 아니면 실행 안 함
    account = repo.get_publish_account(account_code)
    if not account or not account.get("automation_enabled", False):
        logger.warning(f"[Like] Kill-switch OFF — 실행 안 함 | account={account_code}")
        return _out("skipped", "automation_disabled")

    # 2. 중복 확인 — like 는 '성공' 기록만 영구 차단한다(실패는 재시도 허용).
    if _local_result(key) == "success":
        logger.info(f"[Like] 로컬 성공 기록 — skip | {key}")
        return _out("skipped", "duplicate_local")
    blocked_rec = _like_ssot_blocked(repo, account_code, target_identifier)
    if blocked_rec:
        logger.info(f"[Like] SSOT 성공 기록 — skip | {key} | rec={blocked_rec}")
        _local_upsert(key, "success")
        return _out("skipped", "duplicate_ssot", record_id=blocked_rec)

    # 3. 일일 한도 (Fail-closed)
    gate = _like_daily_gate(repo, account_code)
    if gate:
        return _out("skipped", gate)

    # 4. dry_run — 여기서 종료. 브라우저 미기동, 기록 안 함.
    if dry_run:
        logger.info(f"[Like] dry_run — 클릭 안 함 | {key}")
        return _out("skipped", "dry_run")

    # 5. Live 게이트 (회장 승인)
    if os.getenv(LIKE_LIVE_ENV, "").strip().lower() != "true":
        raise OutboundActionError(
            f"Live Like 차단 — {LIKE_LIVE_ENV}=true 필요(회장 승인 게이트)"
        )
    if driver_factory is None and not adspower_profile_id:
        raise OutboundActionError(
            "adspower_profile_id 필수 — 계정별 브라우저 지정 없이 실행 금지"
        )

    # 6. 브라우저 (기존 harness REUSE, 계정별 프로필)
    make_driver = driver_factory or _like_driver_factory(adspower_profile_id)
    stop_browser = browser_stopper or _like_browser_stopper(adspower_profile_id)
    driver = make_driver()
    outcome, reason = "failed", ""
    before_state, after_state = "", ""
    clicks = 0
    try:
        driver.get(target_url)
        time.sleep(_IG_PAGE_SETTLE_SEC)
        cp = _checkpoint_detected(driver)
        if cp:
            reason = f"checkpoint:{cp}"
            logger.warning(f"[Like] checkpoint 감지 — 클릭 안 함 | {key} | {cp}")
        else:
            before_state = _ig_like_state(driver)
            if before_state == "liked":
                # 이미 좋아요 상태 — 클릭하지 않고 성공(no-op)으로 끝낸다.
                outcome, reason = "success", "already_liked"
                after_state = before_state
            elif before_state == "unknown":
                reason = "like_button_not_found"
            else:
                icon = _ig_like_icon_to_click(driver)
                target = _ig_clickable(driver, icon) if icon is not None else None
                if target is None:
                    reason = "clickable_target_not_found"
                else:
                    _ig_click_like(driver, target)
                    clicks = 1
                    time.sleep(_IG_POST_CLICK_SEC)
                    after_state = _ig_like_state(driver)
                    if after_state == "liked":
                        outcome, reason = "success", ""
                    else:
                        reason = "state_not_confirmed"
    except OutboundActionError:
        raise
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"[:400]
        logger.warning(f"[Like] 예외 | {key} | {reason}")
    finally:
        try:
            driver.quit()
        except Exception as exc:
            logger.warning(f"[Like] driver.quit 실패 | {exc}")
        try:
            stop_browser()
        except Exception as exc:
            logger.warning(f"[Like] stop_browser 실패 | {exc}")

    # 7. 기록 — Audit 는 성공·실패 모두 남긴다(attempt 로그).
    #    로컬 영구 dedup mark 는 '성공'일 때만 — 실패는 재시도를 막지 않는다.
    if outcome == "success":
        _local_upsert(key, "success")
    record_id = ""
    try:
        record_id = repo.create_outbound_action(
            {
                "account_code_ref": account_code,
                "target_url": target_url,
                "target_identifier": target_identifier,
                "action_type": LIKE_ACTION,
                "result": outcome,
                "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "error_reason": reason,
            }
        )
    except Exception as exc:
        logger.error(f"[Like] SSOT 기록 실패 | {key} | {type(exc).__name__}: {exc}")

    logger.info(
        f"[Like] 완료 | {key} | {before_state}→{after_state} clicks={clicks} "
        f"result={outcome} reason={reason!r} rec={record_id}"
    )
    return _out(outcome, reason, record_id, before=before_state, after=after_state,
                clicks=clicks)
