import streamlit as st

from core.flow_diagram import generate_flow_svg, legend_svg
from db import log_flow_generate

SAMPLE_FLOW = """\
start: API lands in CrmIntelligence
step: Check config_id in DB
if: config_id already present?
yes_end: Send DUPLICATE_ENTRY response
no: Create meta
no: Publish to offload queue
no: Consume the message
no: Execute the query
no: Write data to HDFS
no: Create Python RMQ message
no_end: Publish to Python service
end: Done
"""



def render():
    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("📖 Syntax reference")
        st.markdown("""
| Keyword | Shape |
|---|---|
| `start:` | 🟢 Start terminal |
| `step:` or bare line | 🔵 Process box |
| `if:` | 🔷 Decision diamond |
| `yes:` | 🔵 Yes-branch step |
| `no:` | 🔵 No-branch step |
| `yes_end:` | 🔴 Yes-branch terminal |
| `no_end:` | 🔴 No-branch terminal |
| `endif` | _(closes if block)_ |
| `end:` | 🔴 End terminal |

**Inline chaining** — use `→` on any `step:` or bare line:
`step: Validate → Transform → Save`

**Nesting** — place `yes:` / `no:` lines after an `if:`, close with `endif`.
Nest another `if:` inside a branch freely.

---
""")
        st.markdown("**Shape legend:**")
        st.markdown(legend_svg(), unsafe_allow_html=True)

    # ── Main columns ──────────────────────────────────────────────────────────
    col_in, col_out = st.columns([1, 1.6], gap="large")

    with col_in:
        st.subheader("✏️ Flow Description")
        flow_input = st.text_area(
            "flow_input", value=SAMPLE_FLOW, height=420,
            label_visibility="collapsed",
            placeholder="Type your flow steps here…"
        )
        if st.button("⚡ Generate Flow Diagram", type="primary", use_container_width=True):
            if not flow_input.strip():
                st.error("❌ Please enter a flow description."); st.stop()
            svg, err = generate_flow_svg(flow_input)
            if err:
                st.error(f"❌ {err}")
            else:
                st.session_state["flow_svg"]   = svg
                st.session_state["flow_input"] = flow_input
                log_flow_generate()
                st.success("✅ Diagram generated!")

    with col_out:
        st.subheader("📊 Flow Diagram")
        if st.session_state.get("flow_svg"):
            svg_content = st.session_state["flow_svg"]
            st.markdown(
                f'<div style="overflow-y:auto;max-height:600px;border-radius:12px;">'
                f'{svg_content}</div>',
                unsafe_allow_html=True
            )
            st.download_button(
                "⬇️ Download SVG",
                data=svg_content, file_name="flow_diagram.svg",
                mime="image/svg+xml", use_container_width=True
            )
            st.caption(
                "💡 Open the SVG in a browser or import into Draw.io / Figma / Inkscape for further editing."
            )
        else:
            st.info("Your flow diagram will appear here after you click **Generate**.")
