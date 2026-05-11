import streamlit as st
from db import get_stats, get_tpl_stats, get_flow_stats, use_supabase


def render():
    st.subheader("📊 Usage Stats")
    db_mode = "☁️ Supabase" if use_supabase() else "💾 Local SQLite"
    st.caption(f"Storage: {db_mode}")
    st.markdown("---")

    s  = get_stats()
    ts = get_tpl_stats()
    fs = get_flow_stats()

    # ── Overall summary ───────────────────────────────────────────────────────
    st.markdown("#### 🔢 Overall Generations")
    ov1, ov2, ov3 = st.columns(3)
    ov1.metric("🛠 Code Generator",     s["total_gen"])
    ov2.metric("📄 Template Generator", ts["total_gen"])
    ov3.metric("🔀 Flow Diagram",        fs["total_gen"])

    st.markdown("#### 📅 Today")
    td1, td2, td3 = st.columns(3)
    td1.metric("🛠 Code Generator",     s["today_gen"])
    td2.metric("📄 Template Generator", ts["today_gen"])
    td3.metric("🔀 Flow Diagram",        fs["today_gen"])

    st.markdown("---")

    # ── Code Generator breakdown ──────────────────────────────────────────────
    st.markdown("#### 🛠 Code Generator")
    cg1, cg2, cg3, cg4 = st.columns(4)
    cg1.metric("Total",  s["total_gen"])
    cg2.metric("Today",  s["today_gen"])
    cg3.metric("Scala",  s["scala_gen"])
    cg4.metric("Python", s["py_gen"])
    if s.get("trend"):
        st.caption("Last 7 days")
        cols = st.columns(len(s["trend"]))
        for col, row in zip(cols, s["trend"]):
            col.metric(row["day"][-5:], row["cnt"])

    st.markdown("---")

    # ── Template Generator breakdown ──────────────────────────────────────────
    st.markdown("#### 📄 Template Generator")
    tg1, tg2 = st.columns(4)[:2]
    tg1.metric("Total", ts["total_gen"])
    tg2.metric("Today", ts["today_gen"])
    if ts.get("trend"):
        st.caption("Last 7 days")
        cols = st.columns(len(ts["trend"]))
        for col, row in zip(cols, ts["trend"]):
            col.metric(row["day"][-5:], row["cnt"])

    st.markdown("---")

    # ── Flow Diagram breakdown ────────────────────────────────────────────────
    st.markdown("#### 🔀 Flow Diagram")
    fg1, fg2 = st.columns(4)[:2]
    fg1.metric("Total", fs["total_gen"])
    fg2.metric("Today", fs["today_gen"])
    if fs.get("trend"):
        st.caption("Last 7 days")
        cols = st.columns(len(fs["trend"]))
        for col, row in zip(cols, fs["trend"]):
            col.metric(row["day"][-5:], row["cnt"])
