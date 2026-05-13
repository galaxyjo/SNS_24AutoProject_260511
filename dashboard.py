import os
from dotenv import load_dotenv

load_dotenv(override=True)

from pathlib import Path
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd

from modules.common.airtable_bridge import get_table
from modules.metrics.crawl_monitor import get_summary as crawl_summary, get_recent_stats as crawl_recent

st.set_page_config(page_title="SNS 자동화 대시보드", page_icon="\U0001f4ca", layout="wide")

LOG_SCHEDULER = Path(__file__).parent / "logs" / "scheduler.log"
LOG_WEBHOOK   = Path(__file__).parent / "logs" / "webhook_stderr.log"

BRIDGE_PIPELINE = [
    "dm_received", "auto_replied",
    "followup1_sent", "followup2_sent", "followup3_sent",
    "converted",
]

GRADE_COLORS = {"hot": "#ffe0b2", "warm": "#fff9c4", "cold": "#e3f2fd"}
STATUS_BG    = {"posted": "#d4edda", "ready": "#fff3cd", "failed": "#f8d7da"}


# ── 데이터 로드 ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_posts() -> pd.DataFrame:
    records = get_table("Instagram_Posts").all()
    rows = []
    for r in records:
        f = r["fields"]
        rows.append({
            "ID":        r["id"],
            "상태":      f.get("post_status", ""),
            "이미지 URL": f.get("image_url", ""),
            "캡션":      f.get("caption", ""),
            "해시태그":  f.get("hashtag", ""),
            "재시도":    f.get("retry_count", 0),
            "오류":      f.get("last_error_msg", ""),
            "소스 URL":  f.get("source_url", ""),
            "좋아요":    f.get("like_count", 0),
            "댓글 수":   f.get("comments_count", 0),
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=30)
def load_leads() -> pd.DataFrame:
    records = get_table("Lead_Interactions").all()
    rows = []
    for r in records:
        f = r["fields"]
        rows.append({
            "ID":           r["id"],
            "코드":         f.get("interaction_code", ""),
            "유저":         f.get("inquiry_user_handle", ""),
            "메시지":       f.get("inquiry_message", "")[:80],
            "bridge_status": f.get("bridge_status", ""),
            "lead_status":  f.get("lead_status", "new"),
            "등급":         f.get("lead_grade", "cold"),
            "점수":         f.get("lead_score", 0),
            "채널":         f.get("conversation_channel", ""),
            "시각":         f.get("relay_scheduled_at", ""),
            "오류":         f.get("last_error_msg", ""),
        })
    df = pd.DataFrame(rows)
    if not df.empty and "시각" in df.columns:
        df = df.sort_values("시각", ascending=False)
    return df


def load_log(path: Path, n: int = 150) -> str:
    if not path.exists():
        return "(로그 파일 없음)"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:])


# ── 헤더 ─────────────────────────────────────────────────────────────────────

st.title("\U0001f4ca SNS 자동화 대시보드")
hcol1, hcol2 = st.columns([5, 1])
hcol1.caption(f"마지막 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (30초 캐시)")
if hcol2.button("\U0001f504 새로고침"):
    st.cache_data.clear()
    st.rerun()

# ── 데이터 로드 (탭 공유) ────────────────────────────────────────────────────

with st.spinner("Airtable 데이터 로딩 중..."):
    posts_df = load_posts()
    leads_df = load_leads()

dm_df      = leads_df[leads_df["채널"] != "instagram_comment"] if not leads_df.empty else leads_df
comment_df = leads_df[leads_df["채널"] == "instagram_comment"] if not leads_df.empty else leads_df

# ── 탭 ───────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["\U0001f4f8 콘텐츠", "\U0001f465 Lead CRM", "\U0001f4ac 댓글", "\U0001f4cb 로그", "\U0001f4ca KPI", "\U0001f5a5️ 헬스"]
)


# ════════════════════════════════════════════════════════════════════════════
# Tab 1: 콘텐츠 현황
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    total   = len(posts_df)
    posted  = (posts_df["상태"] == "posted").sum() if total else 0
    ready   = (posts_df["상태"] == "ready").sum()  if total else 0
    failed  = (posts_df["상태"] == "failed").sum() if total else 0
    srate   = f"{posted / total * 100:.1f}%" if total else "0.0%"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("전체", total)
    c2.metric("\U0001f7e2 게시 완료", posted)
    c3.metric("\U0001f7e1 대기 중", ready)
    c4.metric("\U0001f534 실패", failed)
    c5.metric("성공률", srate)

    st.divider()

    # ── FB 크롤링 이미지 비율 모니터 ─────────────────────────────────────────
    st.subheader("\U0001f4f7 FB 크롤링 이미지 비율")
    _cs = crawl_summary(hours=24)
    cr1, cr2, cr3, cr4 = st.columns(4)
    cr1.metric("크롤 횟수 (24h)", _cs["runs"])
    cr2.metric("수집 포스트", _cs["total"])
    cr3.metric("이미지 있음", _cs["with_image"])
    cr4.metric(
        "이미지 비율",
        f"{_cs['image_rate']}%",
        delta=f"-{_cs['without_image']}건 미추출" if _cs["without_image"] else None,
        delta_color="inverse",
    )

    _recent = crawl_recent(limit=30)
    if _recent:
        _chart_df = pd.DataFrame(list(reversed(_recent)))[["crawled_at", "image_rate", "total", "with_image"]]
        _chart_df["crawled_at"] = pd.to_datetime(_chart_df["crawled_at"]).dt.tz_convert("Asia/Seoul").dt.strftime("%m/%d %H:%M")
        _chart_df = _chart_df.rename(columns={"crawled_at": "시각", "image_rate": "이미지 비율(%)", "total": "전체", "with_image": "이미지 있음"})
        st.line_chart(_chart_df.set_index("시각")[["이미지 비율(%)"]], height=160)
        with st.expander("크롤 이력 상세"):
            st.dataframe(_chart_df, use_container_width=True, height=240)
    else:
        st.caption("크롤 기록 없음 — FB 크롤링 실행 후 데이터가 표시됩니다.")

    st.divider()

    cf1, cf2 = st.columns([2, 3])
    with cf1:
        status_filter = st.selectbox("상태 필터", ["전체", "posted", "ready", "failed"], key="p_status")
    with cf2:
        search = st.text_input("검색 (캡션/URL)", placeholder="검색어 입력...", key="p_search")

    filtered = posts_df.copy()
    if status_filter != "전체":
        filtered = filtered[filtered["상태"] == status_filter]
    if search:
        mask = (
            filtered["캡션"].str.contains(search, na=False)
            | filtered["이미지 URL"].str.contains(search, na=False)
            | filtered["소스 URL"].str.contains(search, na=False)
        )
        filtered = filtered[mask]

    st.subheader(f"레코드 목록 ({len(filtered)}건)")
    display_cols = ["상태", "캡션", "재시도", "오류", "이미지 URL"]

    def _color_status(val):
        return f"background-color: {STATUS_BG.get(val, '')}"

    st.dataframe(
        filtered[display_cols].style.applymap(_color_status, subset=["상태"]),
        use_container_width=True,
        height=380,
    )

    st.divider()
    st.subheader("\U0001f4ca Engagement 현황 (posted 게시물)")
    eng_df = posts_df[posts_df["상태"] == "posted"].copy() if total else pd.DataFrame()
    if not eng_df.empty and {"좋아요", "댓글 수"}.issubset(eng_df.columns):
        avg_likes    = eng_df["좋아요"].mean()
        avg_comments = eng_df["댓글 수"].mean()
        total_likes  = int(eng_df["좋아요"].sum())
        eg1, eg2, eg3 = st.columns(3)
        eg1.metric("총 좋아요", total_likes)
        eg2.metric("평균 좋아요", f"{avg_likes:.1f}")
        eg3.metric("평균 댓글 수", f"{avg_comments:.1f}")
    else:
        st.caption("ig_media_id / like_count / comments_count 필드가 Airtable에 추가되면 표시됩니다.")

    st.divider()
    st.subheader("\U0001f5bc️ 이미지 미리보기 (최근 posted 5건)")
    posted_df = posts_df[posts_df["상태"] == "posted"].tail(5)
    if posted_df.empty:
        st.info("게시 완료된 이미지가 없습니다.")
    else:
        img_cols = st.columns(min(len(posted_df), 5))
        for i, (_, row) in enumerate(posted_df.iterrows()):
            with img_cols[i]:
                try:
                    st.image(row["이미지 URL"], use_container_width=True)
                    cap = row["캡션"]
                    st.caption(cap[:50] + "..." if len(cap) > 50 else cap)
                except Exception:
                    st.warning("이미지 로드 실패")


# ════════════════════════════════════════════════════════════════════════════
# Tab 2: Lead CRM
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    total_leads = len(dm_df)
    converted   = (dm_df["lead_status"] == "converted").sum() if total_leads else 0
    hot_cnt     = (dm_df["등급"] == "hot").sum()              if total_leads else 0
    warm_cnt    = (dm_df["등급"] == "warm").sum()             if total_leads else 0
    conv_rate   = f"{converted / total_leads * 100:.1f}%" if total_leads else "0.0%"

    lc1, lc2, lc3, lc4 = st.columns(4)
    lc1.metric("\U0001f4e5 총 DM 문의", total_leads)
    lc2.metric("\U00002705 전환(주문)", int(converted))
    lc3.metric("\U0001f4c8 전환율", conv_rate)
    lc4.metric("\U0001f525 Hot 리드", int(hot_cnt))

    st.divider()

    ch1, ch2 = st.columns(2)

    with ch1:
        st.subheader("등급 분포 (cold / warm / hot)")
        grade_counts = (
            dm_df["등급"].value_counts().reindex(["cold", "warm", "hot"], fill_value=0)
            if total_leads else pd.Series({"cold": 0, "warm": 0, "hot": 0})
        )
        st.bar_chart(grade_counts)

    with ch2:
        st.subheader("팔로업 파이프라인")
        status_counts = dm_df["bridge_status"].value_counts() if total_leads else pd.Series(dtype=int)
        pipeline_data = pd.Series(
            {s: int(status_counts.get(s, 0)) for s in BRIDGE_PIPELINE},
            name="건수",
        )
        st.bar_chart(pipeline_data)

    st.divider()

    grade_filter = st.selectbox("등급 필터", ["전체", "hot", "warm", "cold"], key="l_grade")
    df_view = dm_df if grade_filter == "전체" else dm_df[dm_df["등급"] == grade_filter]
    st.subheader(f"Lead 목록 ({len(df_view)}건)")

    def _color_grade(val):
        return f"background-color: {GRADE_COLORS.get(val, '')}"

    lead_cols = ["유저", "메시지", "등급", "점수", "bridge_status", "lead_status", "시각", "오류"]
    if not df_view.empty:
        st.dataframe(
            df_view[lead_cols].style.applymap(_color_grade, subset=["등급"]),
            use_container_width=True,
            height=380,
        )
    else:
        st.info("표시할 Lead 데이터가 없습니다.")


# ════════════════════════════════════════════════════════════════════════════
# Tab 3: 댓글 현황
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    cc1, cc2, cc3 = st.columns(3)
    cc1.metric("\U0001f4ac 총 댓글", len(comment_df))
    price_cnt = (
        comment_df["메시지"].str.contains(
            "|".join(["단가", "가격", "얼마", "price", "cost"]), case=False, na=False
        ).sum()
        if not comment_df.empty else 0
    )
    neg_cnt = (
        comment_df["메시지"].str.contains(
            "|".join(["사기", "불만", "최악", "환불"]), case=False, na=False
        ).sum()
        if not comment_df.empty else 0
    )
    cc2.metric("\U0001f4b0 단가 문의", int(price_cnt))
    cc3.metric("\U0001f6a8 부정 댓글", int(neg_cnt))

    st.divider()
    st.subheader("댓글 목록")
    if comment_df.empty:
        st.info("기록된 댓글이 없습니다. 게시물에 댓글이 달리면 자동 수집됩니다.")
    else:
        comment_cols = ["유저", "메시지", "bridge_status", "시각"]
        st.dataframe(comment_df[comment_cols], use_container_width=True, height=380)


# ════════════════════════════════════════════════════════════════════════════
# Tab 4: 로그
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    log_choice = st.radio(
        "로그 선택",
        ["\U0001f4c5 스케줄러 로그", "\U0001f310 Webhook 로그"],
        horizontal=True,
    )
    log_path = LOG_SCHEDULER if "스케줄러" in log_choice else LOG_WEBHOOK
    st.text_area("로그", load_log(log_path), height=420)


# ════════════════════════════════════════════════════════════════════════════
# Tab 5: KPI 대시보드
# ════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300)
def load_kpi(period: str) -> dict:
    from modules.metrics.kpi_collector import collect_kpi
    return collect_kpi(period)

@st.cache_data(ttl=300)
def load_kpi_history() -> list:
    from modules.metrics.kpi_collector import load_snapshots
    return load_snapshots(limit=48)

@st.cache_data(ttl=15)
def load_health() -> dict:
    from modules.common.health_monitor import get_health
    return get_health()


with tab5:

    kpi_period = st.radio(
        "조회 기간",
        ["today", "7d", "30d", "all"],
        format_func=lambda x: {"today": "오늘", "7d": "최근 7일", "30d": "최근 30일", "all": "전체"}[x],
        horizontal=True,
        key="kpi_period",
    )

    with st.spinner("KPI 집계 중..."):
        try:
            kpi = load_kpi(kpi_period)
        except Exception as e:
            st.error(f"KPI 조회 실패: {e}")
            kpi = None

    if kpi:
        up   = kpi.get("upload", {})
        lead = kpi.get("lead", {})
        fup  = kpi.get("followup", {})
        com  = kpi.get("comment", {})
        q    = kpi.get("queue", {})

        # 직전 스냅샷 대비 delta 계산
        history = load_kpi_history()
        prev = history[1] if len(history) >= 2 else None

        def _delta(cur, key_path: list, fmt=None):
            """현재값 - 직전 스냅샷값. prev 없으면 None."""
            if prev is None:
                return None
            d = prev
            for k in key_path:
                d = d.get(k, {}) if isinstance(d, dict) else {}
            cur_v = cur
            prev_v = d if not isinstance(d, dict) else None
            if prev_v is None:
                return None
            delta = cur_v - prev_v if isinstance(cur_v, (int, float)) else None
            if delta is None:
                return None
            return (f"+{delta:.1f}" if fmt == "f" else f"+{delta}") if delta >= 0 else (f"{delta:.1f}" if fmt == "f" else str(delta))

        d_dm   = _delta(lead.get("total", 0),           ["lead", "total"])
        d_conv = _delta(lead.get("conversion_rate", 0), ["lead", "conversion_rate"], "f")
        d_hot  = _delta(lead.get("hot", 0),             ["lead", "hot"])
        d_up   = _delta(up.get("success_rate", 0),      ["upload", "success_rate"], "f")
        d_q    = _delta(q.get("pending", 0) if q else 0, ["queue", "pending"])

        st.subheader("핵심 지표")
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("\U0001f4e5 DM 문의",      lead.get("total", 0),           delta=d_dm)
        k2.metric("\U00002705 전환율",         f"{lead.get('conversion_rate', 0)}%", delta=d_conv)
        k3.metric("\U0001f525 Hot 리드",      lead.get("hot", 0),             delta=d_hot)
        k4.metric("\U0001f4f8 업로드 성공률", f"{up.get('success_rate', 0)}%", delta=d_up)
        k5.metric("\U0001f504 Queue 대기",    q.get("pending", 0) if q else 0, delta=d_q)

        st.divider()
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Lead 등급 분포")
            grade_data = pd.Series({
                "cold": lead.get("cold", 0),
                "warm": lead.get("warm", 0),
                "hot":  lead.get("hot", 0),
            }, name="건수")
            st.bar_chart(grade_data)

        with col_b:
            st.subheader("팔로업 파이프라인")
            pipe = fup.get("pipeline", {})
            if pipe:
                pipe_data = pd.Series(pipe, name="건수")
                st.bar_chart(pipe_data)
            else:
                st.info("팔로업 데이터 없음")

        st.divider()
        st.subheader("업로드 현황")
        u1, u2, u3, u4 = st.columns(4)
        u1.metric("전체",      up.get("total", 0))
        u2.metric("게시 완료", up.get("posted", 0))
        u3.metric("대기",      up.get("ready", 0))
        u4.metric("실패",      up.get("failed", 0))

        st.divider()
        st.subheader("시간별 KPI 추이 (SQLite 스냅샷)")
        history = load_kpi_history()
        if history:
            trend_rows = []
            for snap in reversed(history):
                ts = snap.get("collected_at", "")[:16].replace("T", " ")
                trend_rows.append({
                    "시각":     ts,
                    "DM 문의":  snap.get("lead", {}).get("total", 0),
                    "전환(주문)": snap.get("lead", {}).get("converted", 0),
                    "업로드 성공률": snap.get("upload", {}).get("success_rate", 0),
                })
            trend_df = pd.DataFrame(trend_rows).set_index("시각")
            st.line_chart(trend_df[["DM 문의", "전환(주문)"]])
            st.caption("업로드 성공률 추이")
            st.line_chart(trend_df[["업로드 성공률"]])
        else:
            st.info("스냅샷 없음 — 스케줄러 실행 후 1시간 뒤 데이터가 누적됩니다.")

        col_q1, col_q2 = st.columns(2)
        with col_q1:
            st.subheader("댓글 현황")
            st.metric("총 댓글",   com.get("total", 0))
            st.metric("단가 문의", com.get("price_inquiry", 0))
            st.metric("부정 댓글", com.get("negative", 0))
        with col_q2:
            st.subheader("Retry Queue")
            if q:
                st.metric("대기",    q.get("pending", 0))
                st.metric("완료",    q.get("completed", 0))
                st.metric("실패",    q.get("failed", 0))
            else:
                st.info("Queue 통계 조회 불가")

        collected_kst = (
            datetime.fromisoformat(kpi["collected_at"].replace("Z", "+00:00"))
            + timedelta(hours=9)
        ).strftime("%Y-%m-%d %H:%M:%S KST")
        prev_note = "직전 스냅샷 대비 delta 표시" if prev else "스냅샷 2건 이상 누적 시 delta 표시"
        st.caption(f"수집 시각: {collected_kst} | {prev_note}")


# ════════════════════════════════════════════════════════════════════════════
# Tab 6: 헬스 모니터
# ════════════════════════════════════════════════════════════════════════════
with tab6:
    with st.spinner("시스템 상태 확인 중..."):
        try:
            health = load_health()
        except Exception as e:
            st.error(f"헬스 체크 실패: {e}")
            health = None

    if health:
        overall = health.get("overall", "unknown")

        _BANNER = {
            "ok":       ("#d4edda", "#155724", "✅", "정상 운영 중"),
            "degraded": ("#fff3cd", "#856404", "⚠️", "일부 서비스 이상"),
            "down":     ("#f8d7da", "#721c24", "❌", "서비스 중단"),
        }
        bg, fg, icon, label = _BANNER.get(overall, ("#e2e3e5", "#383d41", "❓", "알 수 없음"))

        st.markdown(
            f"""<div style="background:{bg};color:{fg};padding:14px 22px;
            border-radius:8px;font-size:1.25em;font-weight:bold;margin-bottom:12px;">
            {icon}&nbsp; 시스템 상태: {label.upper()}
            &nbsp;&nbsp;<span style="font-size:0.7em;font-weight:normal;">
            ({health.get('timestamp','')})</span></div>""",
            unsafe_allow_html=True,
        )

        # ── 서비스 카드 ──────────────────────────────────────────────────────
        st.subheader("서비스 상태")
        services = health.get("services", {})

        _SVC = {
            "flask":           ("🌐", "Flask Webhook"),
            "streamlit":       ("📊", "Streamlit"),
            "ngrok":           ("🔗", "ngrok"),
            "launcher":        ("🤖", "launcher/main.py"),
        }
        _ST_ICON  = {"ok": "✅", "down": "❌", "error": "⚠️", "unknown": "❓"}
        _ST_COLOR = {"ok": "#d4edda", "down": "#f8d7da", "error": "#fff3cd", "unknown": "#e9ecef"}

        svc_cols = st.columns(4)
        for i, (key, (emoji, name)) in enumerate(_SVC.items()):
            status = services.get(key, "unknown")
            with svc_cols[i]:
                st.markdown(
                    f"""<div style="background:{_ST_COLOR.get(status,'#e9ecef')};
                    padding:18px 10px;border-radius:8px;text-align:center;min-height:100px;">
                    <div style="font-size:1.8em">{emoji}</div>
                    <div style="font-weight:600;margin:4px 0">{name}</div>
                    <div style="font-size:1.1em">{_ST_ICON.get(status,'❓')} {status.upper()}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

        st.divider()

        # ── Retry Queue + 에러 현황 ──────────────────────────────────────────
        col_rq, col_err = st.columns(2)

        with col_rq:
            st.subheader("🔄 Retry Queue")
            rq = health.get("retry_queue", {})
            if rq:
                r1, r2, r3 = st.columns(3)
                r1.metric("대기",   rq.get("pending", 0))
                r2.metric("완료",   rq.get("done", 0))
                r3.metric("실패",   rq.get("dead", 0))
            else:
                st.info("retry_queue.db 없음 (스케줄러 실행 후 생성)")

        with col_err:
            st.subheader("🚨 에러 현황 (최근 1시간)")
            err = health.get("errors", {})
            err_cnt = err.get("last_1h", 0)
            if err_cnt == 0:
                st.success("최근 1시간 에러 없음")
            else:
                st.metric("에러 건수", err_cnt)
                recent = err.get("recent", [])
                if recent:
                    st.text_area("최근 에러 로그", "\n".join(recent), height=130)

        st.divider()

        # ── FB 크롤링 URL 유효성 ────────────────────────────────────────────
        crawl_urls = health.get("crawl_urls", {})
        if crawl_urls:
            st.subheader("🔗 FB 크롤링 URL 상태")
            _URL_COLOR = {"ok": "#d4edda", "invalid": "#f8d7da", "unreachable": "#fff3cd"}
            _URL_ICON  = {"ok": "✅", "invalid": "❌", "unreachable": "⚠️"}
            for url, status in crawl_urls.items():
                label = url[:70] + "..." if len(url) > 70 else url
                st.markdown(
                    f'<div style="background:{_URL_COLOR.get(status,"#e9ecef")};'
                    f'padding:8px 12px;border-radius:6px;margin-bottom:4px;">'
                    f'{_URL_ICON.get(status,"❓")} <code>{label}</code> — <b>{status.upper()}</b></div>',
                    unsafe_allow_html=True,
                )
            st.divider()

        # ── 스케줄 잡 현황 (run_engine 등록 목록) ──────────────────────────
        st.subheader("⏱️ 등록된 스케줄 잡")
        job_rows = [
            ("fb_crawl",           "30분",       "FB 크롤링"),
            ("insta_upload",       "5분",        "Instagram 업로드"),
            ("followup_poll",      "5분",        "팔로업 DM"),
            ("comment_poll",       "5분",        "댓글 수집·자동답변"),
            ("daily_report",       "매일 09:00", "KPI 일일 리포트"),
            ("kpi_snapshot",       "1시간",      "KPI SQLite 저장"),
            ("engagement_update",  "30분",       "like/comment 수 갱신"),
            ("auto_like",          "15분",       "댓글 자동 좋아요"),
            ("ngrok_check",        "5분",        "ngrok URL 변경 감지"),
            ("crawl_url_check",    "1시간",      "FB 크롤링 URL 유효성"),
        ]
        st.dataframe(
            pd.DataFrame(job_rows, columns=["잡 ID", "주기", "역할"]),
            use_container_width=True,
            hide_index=True,
        )

        st.caption("15초 캐시 | 새로고침 버튼으로 즉시 갱신")
