"""
ui/template.py
──────────────
Streamlit UI for the 📄 Template Generator tab.
"""

import json
import streamlit as st

from core.template_generator import generate_xml_template
from db import log_tpl_generate, insert_tpl_feedback, use_supabase

SAMPLE_JSON = """{
  "config_id": "1373587000007063007",
  "quota_id": "1373587000007063011",
  "client_details": {
    "notify_callback_url": "https://crmlab19.localzoho.com/crm/forecast/notify"
  },
  "trigger_type": "CREATE"
}"""


def render():
    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Template Config")
        st.markdown("---")
        tpl_root_name = st.text_input(
            "Root template name *", value="",
            placeholder="e.g. businessPatternCreateTemplate  (required)"
        )
        st.markdown("---")
        st.markdown("""
**Tips for JSON input:**

- Paste any valid JSON — string values in quotes are automatically typed as `String`.
- Nested objects automatically get their own `<jsontemplate>` block.
- `max-len` values are estimated heuristically — always review before committing.
        """)
        st.markdown("---")
        db_mode = "☁️ Supabase" if use_supabase() else "💾 Local SQLite"
        st.caption(f"Storage: {db_mode}")

    # ── Main columns ──────────────────────────────────────────────────────────
    col_in, col_out, col_fb = st.columns([1, 1.1, 0.8], gap="large")

    # Input
    with col_in:
        st.subheader("📥 JSON Input  →  XML Template")
        tpl_json_input = st.text_area(
            "JSON", value=SAMPLE_JSON, height=340, label_visibility="collapsed"
        )
        if st.button("⚡ Generate XML Template", type="primary", use_container_width=True):
            if not tpl_root_name.strip():
                st.error("❌ Root template name is required."); st.stop()
            try:
                json.loads(tpl_json_input)
            except json.JSONDecodeError as e:
                st.error(f"❌ Invalid JSON: {e}"); st.stop()
            try:
                xml_out = generate_xml_template(tpl_json_input, tpl_root_name.strip())
                st.session_state["tpl_xml_out"]   = xml_out
                st.session_state["tpl_root_name"] = tpl_root_name.strip()
                st.session_state["tpl_json_used"] = tpl_json_input
                log_tpl_generate()
                st.success("✅ XML template generated!")
            except Exception as e:
                st.error(f"❌ {e}"); st.stop()

    # Output
    with col_out:
        st.subheader("📤 Generated XML Template")
        if "tpl_xml_out" in st.session_state:
            xml_content = st.session_state["tpl_xml_out"]
            tpl_rn      = st.session_state["tpl_root_name"]
            filename    = f"{tpl_rn}.xml"
            st.code(xml_content, language="xml")
            st.download_button(
                f"⬇️ Download  {filename}",
                data=xml_content, file_name=filename,
                mime="text/xml", use_container_width=True
            )
            st.caption(
                "⚠️ The template name may already exist in `security.xml` and `max-len` values "
                "are estimated — please review and update them as needed before adding to the file."
            )
        else:
            st.info("Generated XML template appears here after you click **Generate**.")

    # Feedback
    with col_fb:
        st.subheader("💬 Feedback")
        tpl_fb_cat = st.selectbox(
            "Category",
            ["Incorrect type", "Wrong max-len", "Missing nested block",
             "Template name issue", "Other"],
            label_visibility="collapsed", key="tpl_fb_cat"
        )
        tpl_fb_msg = st.text_area(
            "Message",
            placeholder="e.g. nested array not generating its own template block…",
            height=180, label_visibility="collapsed", key="tpl_fb_msg"
        )
        if st.button("Submit Feedback", use_container_width=True, key="tpl_fb_submit"):
            if not tpl_fb_msg.strip():
                st.warning("Please describe your feedback before submitting.")
            else:
                insert_tpl_feedback(
                    tpl_fb_cat, tpl_fb_msg.strip(),
                    st.session_state.get("tpl_json_used", "")
                )
                st.success("✅ Feedback submitted — thank you!")
                st.caption("Your input helps improve the Template Generator.")
