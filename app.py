import streamlit as st

from db import init_db, use_supabase
import ui.generator  as tab_generator
import ui.template   as tab_template
import ui.flow       as tab_flow
import ui.stats      as tab_stats
import ui.feedbacks  as tab_feedbacks


st.set_page_config(page_title="CodeEasy", page_icon="🎯", layout="wide")

if not use_supabase():
    init_db()

_DEFAULTS = {"language": "Scala", "active_tab": "generator", "flow_svg": ""}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


h1, h2, h3, h4, h5, h6 = st.columns([2.4, 1, 1, 1, 1, 1])

with h1:
    st.markdown("## 🎯 CodeEasy")
    st.caption("Generate Scala case classes or Python dataclasses from any JSON sample — instantly")

_tabs = [
    ("h2", "generator", "🛠 Generator"),
    ("h3", "template",  "📄 Template"),
    ("h4", "flow",      "🔀 Flow Diagram"),
    ("h5", "stats",     "📊 Stats"),
    ("h6", "feedbacks", "💬 Feedbacks"),
]

for col, tab_id, label in zip([h2, h3, h4, h5, h6], ["generator","template","flow","stats","feedbacks"],
                               ["🛠 Generator","📄 Template","🔀 Flow Diagram","📊 Stats","💬 Feedbacks"]):
    with col:
        is_active = st.session_state["active_tab"] == tab_id
        if st.button(label, use_container_width=True,
                     type="primary" if is_active else "secondary"):
            st.session_state["active_tab"] = tab_id
            st.rerun()

st.markdown("---")

_active = st.session_state["active_tab"]

if   _active == "generator": tab_generator.render()
elif _active == "template":  tab_template.render()
elif _active == "flow":      tab_flow.render()
elif _active == "stats":     tab_stats.render()
elif _active == "feedbacks": tab_feedbacks.render()

st.markdown("---")
st.markdown("""
    <div style="text-align:center;color:gray;font-size:13px;padding:6px 0">
        For custom requirements, feature requests or incorrect outputs — reach out directly:<br>
        <a href="mailto:dinesh.jr@zohocorp.com" style="color:#4F8BF9;text-decoration:none;">
            📧 dinesh.jr@zohocorp.com
        </a>
    </div>""", unsafe_allow_html=True)
