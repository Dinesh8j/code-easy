import streamlit as st
import streamlit.components.v1 as components

from core.flow_diagram import generate_flow_svg, legend_svg
from db import log_flow_generate

SAMPLE_FLOW = """\
start: Receive API request
if: Auth token present?
yes: Validate token signature
  if: Token valid?
  yes: Parse request body
    if: Body valid?
    yes: Process business logic
    yes: Save result to DB
    yes_end: Return 200 OK
    no_end: Return 400 Bad Request
  endif
  no_end: Return 403 Forbidden
endif
no_end: Return 401 Unauthorized
endif
end: Done"""

LLM_PROMPT = """\
You are a flow description writer. Convert the process I describe into \
plain-text using ONLY these keywords — one per line:

  start: <label>       → start of flow (green)
  step: <label>        → a process step (blue)  [or just write a bare line]
  if: <question>       → decision diamond (amber)
  yes: <label>         → step on the YES branch
  no: <label>          → step on the NO branch
  yes_end: <label>     → terminal ending the YES branch (red)
  no_end: <label>      → terminal ending the NO branch (red)
  endif                → close the if-block (no label)
  end: <label>         → end of flow (red)

  Use → between labels on one line to chain steps: step: Validate → Save → Notify
  Blank lines and # comments are ignored.
  No markdown, no bullets, no indentation — explicit keywords only.

Example output for "describe user login":
start: User submits login form
if: Email exists?
yes: Validate password
  if: Password correct?
  yes: Generate JWT → Return 200 OK
  no_end: Return 401 Invalid credentials
endif
no_end: Return 404 User not found
endif
end: Done

Now write the flow for: [PASTE YOUR PROCESS DESCRIPTION HERE]"""


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
        st.markdown("**🤖 LLM prompt — paste into ChatGPT / Claude:**")
        st.code(LLM_PROMPT, language="text")
        st.markdown("---")
        st.markdown("**Shape legend:**")
        components.html(legend_svg(), height=150)

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
            components.html(
                f'<div style="overflow-y:auto;max-height:600px;border-radius:12px;">'
                f'{svg_content}</div>',
                height=620, scrolling=True
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
