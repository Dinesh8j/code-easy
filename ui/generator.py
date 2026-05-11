"""
ui/generator.py
───────────────
Streamlit UI for the 🛠 Code Generator tab.
"""

import json
import streamlit as st

from core.code_generator import (
    strip_comments, parse_defaults,
    generate_scala, generate_python, build_zip,
)
from db import (
    log_generate, insert_feedback, use_supabase,
)

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
        st.header("⚙️ Configuration")
        st.subheader("🌐 Target Language")
        lang_choice = st.radio(
            "lang", ["Scala", "Python"],
            index=0 if st.session_state["language"] == "Scala" else 1,
            horizontal=True, label_visibility="collapsed"
        )
        if lang_choice != st.session_state["language"]:
            st.session_state["language"] = lang_choice
            st.session_state.pop("files", None)
            st.rerun()
        lang = st.session_state["language"]

        st.markdown("---")
        root_class = st.text_input(
            "Root class name *", value="",
            placeholder="e.g. MyRequest  (required)"
        )
        package_name = (
            st.text_input("Package name (optional)", value="",
                          placeholder="e.g. com.example.myapp")
            if lang == "Scala" else ""
        )

        st.markdown("---")
        st.subheader("🔤 Enum Fields (optional)")
        st.caption("One per line — `fieldName: VAL1,VAL2`")
        enum_raw = st.text_area(
            "Enums", value="",
            placeholder="e.g.\ntrigger_type: CREATE,UPDATE,DELETE",
            height=100, label_visibility="collapsed"
        )

        st.markdown("---")
        st.subheader("🔲 Option Fields (optional)")
        st.caption("Field names to mark as optional — one per line")
        option_raw = st.text_area(
            "Options", value="",
            placeholder="e.g.\nquota_id\nclient_details",
            height=85, label_visibility="collapsed"
        )

        st.markdown("---")
        st.subheader("🏷️ Default Values (optional)")
        st.caption("One per line — `fieldName = value`")
        defaults_raw = st.text_area(
            "Defaults", value="",
            placeholder="e.g.\nstatus = SCHEDULED\nfeature_name = Insights",
            height=100, label_visibility="collapsed"
        )

        st.markdown("---")
        db_mode = "☁️ Supabase" if use_supabase() else "💾 Local SQLite"
        st.caption(f"Storage: {db_mode}")

    # ── Main columns ──────────────────────────────────────────────────────────
    col_in, col_out, col_fb = st.columns([1, 1.1, 0.8], gap="large")
    lang = st.session_state["language"]

    # Input
    with col_in:
        st.subheader(f"📥 JSON Input  →  {lang}")
        json_input = st.text_area(
            "JSON", value=SAMPLE_JSON, height=340, label_visibility="collapsed"
        )
        if st.button(f"⚡ Generate {lang} Code", type="primary", use_container_width=True):
            extra_enums = {}
            for line in enum_raw.strip().splitlines():
                if ":" in line:
                    fn, vs = line.split(":", 1)
                    vals = [v.strip() for v in vs.split(",") if v.strip()]
                    if fn.strip() and vals:
                        extra_enums[fn.strip()] = vals
            option_fields = [f.strip() for f in option_raw.strip().splitlines() if f.strip()]
            defaults      = parse_defaults(defaults_raw)
            try:
                cl, _ = strip_comments(json_input); json.loads(cl)
            except json.JSONDecodeError as e:
                st.error(f"❌ Invalid JSON: {e}"); st.stop()
            if not root_class.strip():
                st.error("❌ Root class name is required."); st.stop()
            try:
                if lang == "Scala":
                    files = generate_scala(json_input, root_class.strip(),
                                           package_name.strip(), extra_enums,
                                           option_fields, defaults)
                else:
                    files = generate_python(json_input, root_class.strip(),
                                            extra_enums, option_fields, defaults)
                st.session_state["files"]    = files
                st.session_state["json_used"] = json_input
                log_generate(lang)
                st.success(f"✅ Generated {len(files)} {lang} file(s)")
            except Exception as e:
                st.error(f"❌ {e}"); st.stop()

    # Output
    with col_out:
        st.subheader("📤 Generated Files")
        if "files" in st.session_state:
            files = st.session_state["files"]
            hl    = "scala" if lang == "Scala" else "python"
            tabs  = st.tabs([f["filename"] for f in files])
            for tab, f in zip(tabs, files):
                with tab:
                    st.caption(f.get("description", ""))
                    st.code(f["code"], language=hl)
                    st.download_button(
                        f"⬇️ {f['filename']}", f["code"],
                        file_name=f["filename"], mime="text/plain",
                        key=f"dl_{f['filename']}", use_container_width=True
                    )
            st.markdown("---")
            ext = "scala" if lang == "Scala" else "python"
            st.download_button(
                f"⬇️ Download ALL  ({root_class.strip()}_{ext}.zip)",
                build_zip(files, root_class.strip()),
                file_name=f"{root_class.strip()}_{ext}.zip",
                mime="application/zip", use_container_width=True
            )
        else:
            st.info("Generated files appear here after you click **Generate**.")

    # Feedback
    with col_fb:
        st.subheader("💬 Feedback")
        fb_cat = st.selectbox(
            "Category",
            ["Incorrect output", "Missing feature", "Wrong type inference",
             "Enum not detected", "Other"],
            label_visibility="collapsed"
        )
        fb_msg = st.text_area(
            "Message",
            placeholder="e.g. nested arrays not handled correctly…",
            height=180, label_visibility="collapsed"
        )
        if st.button("Submit Feedback", use_container_width=True):
            if not fb_msg.strip():
                st.warning("Please describe your feedback before submitting.")
            else:
                insert_feedback(
                    fb_cat, fb_msg.strip(),
                    st.session_state.get("language", ""),
                    st.session_state.get("json_used", "")
                )
                st.success("✅ Feedback submitted — thank you!")
                st.caption("Your input helps improve CodeCast.")
