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
    
