import json
import streamlit as st
import streamlit.components.v1 as components

from core.flow_diagram import generate_flow_svg, legend_svg
try:
    from core.flow_diagram import generate_flow_data
except ImportError:
    generate_flow_data = None
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


def _draggable_canvas(data: dict, height: int = 640) -> str:
    """Build a self-contained HTML page with a draggable canvas diagram."""
    nodes_json = json.dumps(data["nodes"])
    edges_json = json.dumps(data["edges"])
    W          = data["W"]

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #f8fafc; font-family: Inter, Segoe UI, Arial, sans-serif; }}
  canvas {{ display: block; cursor: grab; }}
  canvas.dragging-node {{ cursor: grabbing; }}
  #toolbar {{
    display: flex; gap: 8px; padding: 8px 10px;
    background: #f1f5f9; border-bottom: 1px solid #e2e8f0;
    align-items: center; flex-wrap: wrap;
  }}
  #toolbar button {{
    padding: 4px 12px; border-radius: 6px; border: 1px solid #cbd5e1;
    background: white; font-size: 12px; cursor: pointer; color: #334155;
  }}
  #toolbar button:hover {{ background: #e2e8f0; }}
  #zoom-label {{ font-size: 12px; color: #64748b; min-width: 44px; text-align:center; }}
  #hint {{ font-size: 11px; color: #94a3b8; margin-left: auto; }}
</style>
</head>
<body>
<div id="toolbar">
  <button onclick="zoomIn()">＋ Zoom in</button>
  <button onclick="zoomOut()">－ Zoom out</button>
  <span id="zoom-label">100%</span>
  <button onclick="resetView()">⟳ Reset</button>
  <button onclick="autoLayout()">⊞ Auto layout</button>
  <span id="hint">🖱 Drag nodes to rearrange · Scroll to zoom · Drag canvas to pan</span>
</div>
<canvas id="c"></canvas>

<script>
const RAW_NODES = {nodes_json};
const RAW_EDGES = {edges_json};
const CANVAS_W  = {W};

// ── State ──────────────────────────────────────────────────────────────────
let nodes = RAW_NODES.map(n => ({{ ...n }}));   // mutable copy
let scale  = 1;
let panX   = 0, panY = 0;
let dragNode = null, dragOffX = 0, dragOffY = 0;
let isPanning = false, panStartX = 0, panStartY = 0;

// ── Colors ─────────────────────────────────────────────────────────────────
const COLORS = {{
  start:    {{ fill: '#22c55e', text: '#ffffff' }},
  end:      {{ fill: '#ef4444', text: '#ffffff' }},
  yes_end:  {{ fill: '#ef4444', text: '#ffffff' }},
  no_end:   {{ fill: '#ef4444', text: '#ffffff' }},
  decision: {{ fill: '#f59e0b', text: '#1e293b' }},
  process:  {{ fill: '#3b82f6', text: '#ffffff' }},
}};
const ARROW_CLR = '#64748b';
const FONT      = '12px Inter, Segoe UI, Arial, sans-serif';
const FONT_SM   = '10px Inter, Segoe UI, Arial, sans-serif';

// ── Canvas setup ───────────────────────────────────────────────────────────
const canvas = document.getElementById('c');
const ctx    = canvas.getContext('2d');

function resize() {{
  canvas.width  = window.innerWidth;
  canvas.height = {height} - 42;   // subtract toolbar height
  draw();
}}
window.addEventListener('resize', resize);

// ── Node helpers ───────────────────────────────────────────────────────────
function nodeMap() {{
  const m = {{}};
  nodes.forEach(n => m[n.nid] = n);
  return m;
}}

function nodeAt(wx, wy) {{
  // reverse iteration so top-drawn nodes get priority
  for (let i = nodes.length - 1; i >= 0; i--) {{
    const n = nodes[i];
    if (wx >= n.x - n.w/2 && wx <= n.x + n.w/2 &&
        wy >= n.y          && wy <= n.y + n.h)
      return n;
  }}
  return null;
}}

// ── Draw helpers ───────────────────────────────────────────────────────────
function wrapText(text, maxW) {{
  const words = text.split(' ');
  const lines = [];
  let cur = '';
  ctx.font = FONT;
  for (const w of words) {{
    const test = cur ? cur + ' ' + w : w;
    if (ctx.measureText(test).width > maxW - 16 && cur) {{
      lines.push(cur); cur = w;
    }} else {{ cur = test; }}
  }}
  if (cur) lines.push(cur);
  return lines;
}}

function drawArrow(x1, y1, x2, y2, label) {{
  ctx.save();
  ctx.strokeStyle = ARROW_CLR;
  ctx.lineWidth   = 1.8;
  ctx.beginPath();
  const sameCol = Math.abs(x1 - x2) < 5;
  if (sameCol) {{
    ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
  }} else {{
    const midY = y1 + (y2 - y1) * 0.4;
    ctx.moveTo(x1, y1); ctx.lineTo(x1, midY);
    ctx.lineTo(x2, midY); ctx.lineTo(x2, y2);
  }}
  ctx.stroke();

  // arrowhead
  const angle = Math.atan2(y2 - (sameCol ? y1 : y1 + (y2-y1)*0.4), 0);
  const headLen = 8;
  ctx.fillStyle = ARROW_CLR;
  ctx.beginPath();
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - headLen * Math.sin(Math.PI/6),
             y2 - headLen * Math.cos(Math.PI/6));
  ctx.lineTo(x2 + headLen * Math.sin(Math.PI/6),
             y2 - headLen * Math.cos(Math.PI/6));
  ctx.closePath(); ctx.fill();

  // label badge
  if (label) {{
    const lx = sameCol ? x1 + 10 : (x1+x2)/2;
    const ly = sameCol ? (y1+y2)/2 : y1 + (y2-y1)*0.4 - 6;
    ctx.font = FONT_SM;
    const tw = ctx.measureText(label).width;
    ctx.fillStyle = 'white';
    ctx.fillRect(lx - tw/2 - 4, ly - 11, tw + 8, 14);
    ctx.fillStyle = ARROW_CLR;
    ctx.textAlign = 'center';
    ctx.fillText(label, lx, ly);
  }}
  ctx.restore();
}}

function drawEdges() {{
  const nm = nodeMap();
  RAW_EDGES.forEach(e => {{
    const src = nm[e.src], dst = nm[e.dst];
    if (!src || !dst) return;

    let x1, y1;
    if (src.kind === 'decision') {{
      if (e.label === 'Yes') {{ x1 = src.x - src.w/2; y1 = src.y + src.h/2; }}
      else if (e.label === 'No') {{ x1 = src.x + src.w/2; y1 = src.y + src.h/2; }}
      else {{ x1 = src.x; y1 = src.y + src.h; }}
    }} else {{
      x1 = src.x; y1 = src.y + src.h;
    }}
    const x2 = dst.x, y2 = dst.y;
    drawArrow(x1, y1, x2, y2, e.label);
  }});
}}

function drawNode(n) {{
  const c = COLORS[n.kind] || COLORS.process;
  const hw = n.w / 2, hh = n.h / 2;
  ctx.save();

  if (n.kind === 'decision') {{
    ctx.fillStyle = c.fill;
    ctx.strokeStyle = '#1e293b'; ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(n.x,      n.y);
    ctx.lineTo(n.x + hw, n.y + hh);
    ctx.lineTo(n.x,      n.y + n.h);
    ctx.lineTo(n.x - hw, n.y + hh);
    ctx.closePath(); ctx.fill(); ctx.stroke();
  }} else {{
    const r = (n.kind === 'start' || n.kind === 'end' ||
               n.kind === 'yes_end' || n.kind === 'no_end') ? hh : 8;
    ctx.fillStyle = c.fill;
    ctx.strokeStyle = '#1e293b'; ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.roundRect(n.x - hw, n.y, n.w, n.h, r);
    ctx.fill(); ctx.stroke();
  }}

  // label
  ctx.fillStyle = c.text;
  ctx.font = FONT;
  ctx.textAlign = 'center';
  const lines = wrapText(n.label, n.w);
  const lineH = 16;
  const startY = n.y + hh - (lines.length * lineH) / 2 + 12;
  lines.forEach((ln, i) => ctx.fillText(ln, n.x, startY + i * lineH));

  ctx.restore();
}}

function draw() {{
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.save();
  ctx.translate(panX, panY);
  ctx.scale(scale, scale);
  drawEdges();
  nodes.forEach(drawNode);
  ctx.restore();
}}

// ── Coordinate conversion ──────────────────────────────────────────────────
function toWorld(cx, cy) {{
  return {{ x: (cx - panX) / scale, y: (cy - panY) / scale }};
}}

// ── Mouse events ───────────────────────────────────────────────────────────
canvas.addEventListener('mousedown', e => {{
  const w = toWorld(e.offsetX, e.offsetY);
  const hit = nodeAt(w.x, w.y);
  if (hit) {{
    dragNode  = hit;
    dragOffX  = w.x - hit.x;
    dragOffY  = w.y - hit.y;
    canvas.classList.add('dragging-node');
  }} else {{
    isPanning  = true;
    panStartX  = e.clientX - panX;
    panStartY  = e.clientY - panY;
    canvas.style.cursor = 'grabbing';
  }}
}});

canvas.addEventListener('mousemove', e => {{
  if (dragNode) {{
    const w   = toWorld(e.offsetX, e.offsetY);
    dragNode.x = w.x - dragOffX;
    dragNode.y = w.y - dragOffY;
    draw();
  }} else if (isPanning) {{
    panX = e.clientX - panStartX;
    panY = e.clientY - panStartY;
    draw();
  }}
}});

canvas.addEventListener('mouseup', () => {{
  dragNode = null;
  isPanning = false;
  canvas.classList.remove('dragging-node');
  canvas.style.cursor = 'grab';
}});

canvas.addEventListener('mouseleave', () => {{
  dragNode = null; isPanning = false;
  canvas.style.cursor = 'grab';
}});

// ── Scroll to zoom ─────────────────────────────────────────────────────────
canvas.addEventListener('wheel', e => {{
  e.preventDefault();
  const factor = e.deltaY < 0 ? 1.1 : 0.9;
  const wx = (e.offsetX - panX) / scale;
  const wy = (e.offsetY - panY) / scale;
  scale  = Math.min(3, Math.max(0.2, scale * factor));
  panX   = e.offsetX - wx * scale;
  panY   = e.offsetY - wy * scale;
  document.getElementById('zoom-label').textContent =
    Math.round(scale * 100) + '%';
  draw();
}}, {{ passive: false }});

// ── Touch support ──────────────────────────────────────────────────────────
let lastTouchX, lastTouchY;
canvas.addEventListener('touchstart', e => {{
  if (e.touches.length === 1) {{
    const t   = e.touches[0];
    const rect = canvas.getBoundingClientRect();
    const w   = toWorld(t.clientX - rect.left, t.clientY - rect.top);
    const hit = nodeAt(w.x, w.y);
    if (hit) {{
      dragNode = hit;
      dragOffX = w.x - hit.x; dragOffY = w.y - hit.y;
    }} else {{
      lastTouchX = t.clientX; lastTouchY = t.clientY;
    }}
  }}
}}, {{ passive: true }});

canvas.addEventListener('touchmove', e => {{
  if (e.touches.length === 1) {{
    const t    = e.touches[0];
    const rect = canvas.getBoundingClientRect();
    if (dragNode) {{
      const w   = toWorld(t.clientX - rect.left, t.clientY - rect.top);
      dragNode.x = w.x - dragOffX; dragNode.y = w.y - dragOffY;
    }} else {{
      panX += t.clientX - lastTouchX; panY += t.clientY - lastTouchY;
      lastTouchX = t.clientX; lastTouchY = t.clientY;
    }}
    draw();
  }}
}}, {{ passive: true }});

canvas.addEventListener('touchend', () => {{ dragNode = null; }});

// ── Toolbar actions ────────────────────────────────────────────────────────
function zoomIn()  {{
  scale = Math.min(3, scale * 1.2);
  document.getElementById('zoom-label').textContent = Math.round(scale*100)+'%';
  draw();
}}
function zoomOut() {{
  scale = Math.max(0.2, scale * 0.8);
  document.getElementById('zoom-label').textContent = Math.round(scale*100)+'%';
  draw();
}}
function resetView() {{
  nodes  = RAW_NODES.map(n => ({{ ...n }}));
  scale  = 1; panX = 0; panY = 0;
  document.getElementById('zoom-label').textContent = '100%';
  draw();
}}
function autoLayout() {{
  // snap nodes back to their original computed positions
  const orig = {{}};
  RAW_NODES.forEach(n => orig[n.nid] = n);
  nodes.forEach(n => {{ if (orig[n.nid]) {{ n.x = orig[n.nid].x; n.y = orig[n.nid].y; }} }});
  draw();
}}

// ── Init ───────────────────────────────────────────────────────────────────
resize();
</script>
</body>
</html>"""


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

            # Generate both SVG (for download) and data (for canvas)
            svg, err = generate_flow_svg(flow_input)
            if err:
                st.error(f"❌ {err}"); st.stop()

            data = None
            if generate_flow_data:
                data, err2 = generate_flow_data(flow_input)
                if err2:
                    st.error(f"❌ {err2}"); st.stop()

            st.session_state["flow_svg"]   = svg
            st.session_state["flow_data"]  = data
            st.session_state["flow_input"] = flow_input
            log_flow_generate()
            st.success("✅ Diagram generated!")

    with col_out:
        st.subheader("📊 Flow Diagram")
        if st.session_state.get("flow_svg"):
            svg_content = st.session_state["flow_svg"]
            data        = st.session_state.get("flow_data")

            if data:
                # Interactive draggable canvas
                components.html(
                    _draggable_canvas(data, height=640),
                    height=640, scrolling=False
                )
            else:
                # Fallback: static SVG (old flow_diagram.py on server)
                st.markdown(
                    f'<div style="overflow-y:auto;max-height:620px;border-radius:12px;">'
                    f'{svg_content}</div>',
                    unsafe_allow_html=True
                )

            st.download_button(
                "⬇️ Download SVG",
                data=svg_content, file_name="flow_diagram.svg",
                mime="image/svg+xml", use_container_width=True
            )
            st.caption(
                "💡 Drag nodes to rearrange · Scroll to zoom · Drag background to pan · "
                "Open SVG in Draw.io / Figma for further editing."
            )
        else:
            st.info("Your flow diagram will appear here after you click **Generate**.")
