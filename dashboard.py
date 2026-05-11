import os
from dotenv import load_dotenv

load_dotenv(override=True)

from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd

from modules.common.airtable_bridge import get_table

st.set_page_config(page_title="SNS 자동화 대시보드", page_icon="📊", layout="wide")

LOG_FILE = Path(__file__).parent / "logs" / "scheduler.log"

STATUS_COLOR = {
    "posted": "🟢",
    "ready": "🟡",
    "failed": "🔴",
}


@st.cache_data(ttl=30)
def load_records():
    table = get_table("Instagram_Posts")
    records = table.all()
    rows = []
    for r in records:
        f = r["fields"]
        rows.append({
            "ID": r["id"],
            "상태": f.get("post_status", ""),
            "이미지 URL": f.get("image_url", ""),
            "캡션": f.get("caption", ""),
            "해시태그": f.get("hashtag", ""),
            "재시도": f.get("retry_count", 0),
            "오류 메시지": f.get("last_error_msg", ""),
            "소스 URL": f.get("source_url", ""),
        })
    return pd.DataFrame(rows)


def load_logs(n=100):
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-n:]


# ── 헤더 ──────────────────────────────────────────────────────────────
st.title("📊 SNS 자동화 대시보드")
st.caption(f"마지막 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (30초 캐시)")

if st.button("🔄 새로고침"):
    st.cache_data.clear()
    st.rerun()

# ── 데이터 로드 ────────────────────────────────────────────────────────
with st.spinner("Airtable 데이터 로딩 중..."):
    df = load_records()

# ── 요약 지표 ──────────────────────────────────────────────────────────
total = len(df)
posted = (df["상태"] == "posted").sum()
ready = (df["상태"] == "ready").sum()
failed = (df["상태"] == "failed").sum()
success_rate = round(posted / total * 100, 1) if total else 0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("전체", total)
col2.metric("🟢 게시 완료", posted)
col3.metric("🟡 대기 중", ready)
col4.metric("🔴 실패", failed)
col5.metric("성공률", f"{success_rate}%")

st.divider()

# ── 상태별 필터 ────────────────────────────────────────────────────────
col_filter, col_search = st.columns([2, 3])
with col_filter:
    status_filter = st.selectbox("상태 필터", ["전체", "posted", "ready", "failed"])
with col_search:
    search = st.text_input("검색 (캡션/URL)", placeholder="검색어 입력...")

filtered = df.copy()
if status_filter != "전체":
    filtered = filtered[filtered["상태"] == status_filter]
if search:
    mask = (
        filtered["캡션"].str.contains(search, na=False)
        | filtered["이미지 URL"].str.contains(search, na=False)
        | filtered["소스 URL"].str.contains(search, na=False)
    )
    filtered = filtered[mask]

# ── 레코드 테이블 ──────────────────────────────────────────────────────
st.subheader(f"레코드 목록 ({len(filtered)}건)")
display_cols = ["상태", "캡션", "재시도", "오류 메시지", "이미지 URL"]

def color_status(val):
    colors = {"posted": "#d4edda", "ready": "#fff3cd", "failed": "#f8d7da"}
    return f"background-color: {colors.get(val, '')}"

styled = filtered[display_cols].style.applymap(color_status, subset=["상태"])
st.dataframe(styled, use_container_width=True, height=400)

# ── 이미지 미리보기 ────────────────────────────────────────────────────
st.divider()
st.subheader("🖼️ 이미지 미리보기 (최근 posted 5건)")
posted_df = df[df["상태"] == "posted"].tail(5)
if posted_df.empty:
    st.info("게시 완료된 이미지가 없습니다.")
else:
    cols = st.columns(min(len(posted_df), 5))
    for i, (_, row) in enumerate(posted_df.iterrows()):
        with cols[i]:
            try:
                st.image(row["이미지 URL"], use_container_width=True)
                st.caption(row["캡션"][:50] + "..." if len(row["캡션"]) > 50 else row["캡션"])
            except Exception:
                st.warning("이미지 로드 실패")

# ── 로그 뷰어 ──────────────────────────────────────────────────────────
st.divider()
st.subheader("📋 스케줄러 로그 (최근 100줄)")
log_lines = load_logs()
if log_lines:
    log_text = "\n".join(log_lines)
    st.text_area("로그", log_text, height=300)
else:
    st.info("로그 파일이 없습니다. 스케줄러를 먼저 실행해주세요.")
