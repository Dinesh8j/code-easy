"""
flow_diagram.py  (v2 — simplified & accurate)
══════════════════════════════════════════════

SYNTAX  (one statement per line)
─────────────────────────────────
  start: <label>              → green start terminal
  end: <label>                → red end terminal
  step: <label>               → blue process rectangle
  if: <question>              → amber decision diamond
  yes: <label>                → process on the YES branch of the last `if`
  no: <label>                 → process on the NO  branch of the last `if`
  yes_end: <label>            → terminal that ends the YES branch
  no_end: <label>             → terminal that ends the NO  branch
  endif                       → close the current if-block; flow rejoins trunk

  Blank lines and lines starting with # are ignored.
  Inline chains: use  →  to split one line into multiple `step` nodes.

WHY THIS IS BETTER
──────────────────
  • No indentation guessing — each line has an explicit role keyword.
  • `endif` makes the rejoin point unambiguous.
  • Nested `if` blocks are supported (stack-based).
  • Arrow rendering walks an explicit edge list — no child[0] surprises.
  • Layout is a single top-down pass with a per-column cursor.
"""

from __future__ import annotations
import re, textwrap, html
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

W          = 740
CX_MAIN    = W // 2       # 370
CX_YES     = 185
CX_NO      = 555
NODE_W     = 190
DIA_W      = 220
NODE_H     = 48
DIA_H      = 64
GAP_V      = 36
PAD_TOP    = 30
FONT       = "Inter, Segoe UI, Arial, sans-serif"
FS         = 12
ARROW_CLR  = "#64748b"

COLORS = {
    "start":    ("#22c55e", "#ffffff"),
    "end":      ("#ef4444", "#ffffff"),
    "decision": ("#f59e0b", "#1e293b"),
    "process":  ("#3b82f6", "#ffffff"),
    "yes_end":  ("#ef4444", "#ffffff"),
    "no_end":   ("#ef4444", "#ffffff"),
}

# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

_uid = 0
def _nid():
    global _uid; _uid += 1; return f"n{_uid}"

@dataclass
class Node:
    nid:   str
    label: str
    kind:  str          # start | end | process | decision | yes_end | no_end
    col:   str = "main" # main | yes | no
    x:     float = 0
    y:     float = 0
    w:     float = NODE_W
    h:     float = NODE_H

    @property
    def cx(self):     return self.x
    @property
    def cy(self):     return self.y + self.h / 2
    @property
    def bottom(self): return self.y + self.h
    @property
    def top(self):    return self.y

@dataclass
class Edge:
    src:   str
    dst:   str
    label: str = ""

# ─────────────────────────────────────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────────────────────────────────────

_ARROW_SPLIT = re.compile(r'\s*→\s*|\s*->\s*')
_KW = re.compile(
    r'^(start|end|step|if|yes|no|yes_end|no_end|endif)\s*:?\s*(.*)',
    re.IGNORECASE
)

def _rows(text: str) -> list[tuple[str, str]]:
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        m = _KW.match(line)
        if m:
            kw, rest = m.group(1).lower(), m.group(2).strip()
            if kw == "step" and _ARROW_SPLIT.search(rest):
                for part in _ARROW_SPLIT.split(rest):
                    if part.strip():
                        rows.append(("step", part.strip()))
            else:
                rows.append((kw, rest))
        else:
            # bare line — expand → chains as steps
            for part in _ARROW_SPLIT.split(line):
                if part.strip():
                    rows.append(("step", part.strip()))
    return rows


def parse(text: str) -> tuple[list[Node], list[Edge]]:
    global _uid; _uid = 0

    rows  = _rows(text)
    nodes: list[Node]  = []
    edges: list[Edge]  = []
    stack: list[dict]  = []
    trunk_tail: Optional[Node] = None

    def add(node: Node):
        nonlocal trunk_tail
        nodes.append(node)

        if not stack:
            if trunk_tail:
                edges.append(Edge(trunk_tail.nid, node.nid))
            trunk_tail = node
        else:
            frame  = stack[-1]
            branch = frame["in"]
            if branch == "yes":
                if frame["yes_tail"]:
                    edges.append(Edge(frame["yes_tail"].nid, node.nid))
                else:
                    edges.append(Edge(frame["decision"].nid, node.nid, "Yes"))
                frame["yes_tail"] = node
            elif branch == "no":
                if frame["no_tail"]:
                    edges.append(Edge(frame["no_tail"].nid, node.nid))
                else:
                    edges.append(Edge(frame["decision"].nid, node.nid, "No"))
                frame["no_tail"] = node

    for kw, label in rows:

        if kw == "endif":
            if not stack:
                continue
            frame = stack.pop()
            yes_t = frame["yes_tail"]
            no_t  = frame["no_tail"]
            dec   = frame["decision"]

            yes_closed = yes_t and yes_t.kind in ("yes_end", "no_end", "end")
            no_closed  = no_t  and no_t.kind  in ("yes_end", "no_end", "end")

            new_tail = None

            if yes_t and no_t and not yes_closed and not no_closed:
                # both branches open → merge dot
                merge = Node(_nid(), "·", "process", "main", w=8, h=4)
                nodes.append(merge)
                edges.append(Edge(yes_t.nid, merge.nid))
                edges.append(Edge(no_t.nid,  merge.nid))
                new_tail = merge
            elif yes_t and not yes_closed:
                new_tail = yes_t
                if not no_t:
                    # no else-branch: direct No from decision to next trunk node
                    frame["__pending_no"] = dec
            elif no_t and not no_closed:
                new_tail = no_t

            trunk_tail = new_tail

            if frame.get("__pending_no") and trunk_tail:
                edges.append(Edge(frame["__pending_no"].nid, trunk_tail.nid, "No"))
            continue

        # Build node
        if kw == "start":
            n = Node(_nid(), label or "Start", "start", "main")
        elif kw == "end":
            n = Node(_nid(), label or "End", "end", "main")
        elif kw == "if":
            n = Node(_nid(), label, "decision", "main", w=DIA_W, h=DIA_H)
        elif kw == "yes":
            n = Node(_nid(), label, "process", "yes")
        elif kw == "no":
            n = Node(_nid(), label, "process", "no")
        elif kw == "yes_end":
            n = Node(_nid(), label or "End", "yes_end", "yes")
        elif kw == "no_end":
            n = Node(_nid(), label or "End", "no_end", "no")
        else:
            n = Node(_nid(), label, "process", "main")

        if kw == "if":
            add(n)
            stack.append({"decision": n, "yes_tail": None, "no_tail": None, "in": None})
        elif kw in ("yes", "yes_end"):
            if stack: stack[-1]["in"] = "yes"
            add(n)
        elif kw in ("no", "no_end"):
            if stack: stack[-1]["in"] = "no"
            add(n)
        else:
            add(n)

    return nodes, edges


# ─────────────────────────────────────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────────────────────────────────────

_COL_X = {"main": CX_MAIN, "yes": CX_YES, "no": CX_NO}

def layout(nodes: list[Node], edges: list[Edge]) -> float:
    cursors = {"main": float(PAD_TOP), "yes": float(PAD_TOP), "no": float(PAD_TOP)}

    for node in nodes:
        col    = node.col
        node.x = _COL_X.get(col, CX_MAIN)

        if node.kind == "decision":
            node.y = cursors["main"]
            cursors["main"] = node.bottom + GAP_V
            cursors["yes"]  = cursors["main"]
            cursors["no"]   = cursors["main"]
        else:
            if col == "main":
                # sync past tallest branch before placing
                peak = max(cursors["yes"], cursors["no"], cursors["main"])
                cursors["main"] = peak
            node.y = cursors[col]
            cursors[col] = node.bottom + GAP_V

    return max(cursors.values())


# ─────────────────────────────────────────────────────────────────────────────
# SVG rendering
# ─────────────────────────────────────────────────────────────────────────────

def _wrap(text: str, max_chars: int = 24) -> list[str]:
    return textwrap.wrap(str(text), max_chars) or [str(text)]


def _shape_svg(node: Node) -> str:
    # invisible merge dot
    if node.w <= 10:
        return f'<circle cx="{node.cx:.1f}" cy="{node.cy:.1f}" r="3" fill="{ARROW_CLR}"/>\n'

    color_key = node.kind if node.kind in COLORS else "process"
    bg, fg = COLORS[color_key]
    label_lines = _wrap(node.label)
    lh = FS + 4
    total_h = len(label_lines) * lh
    ty_start = node.cy - total_h / 2 + FS

    texts = ""
    for i, ln in enumerate(label_lines):
        ty = ty_start + i * lh
        texts += (f'<text x="{node.cx:.1f}" y="{ty:.1f}" text-anchor="middle" '
                  f'font-size="{FS}" font-family="{FONT}" fill="{fg}" font-weight="500">'
                  f'{html.escape(ln)}</text>\n')

    if node.kind == "decision":
        hw, hh = node.w / 2, node.h / 2
        cx, cy = node.cx, node.cy
        pts = f"{cx:.1f},{cy-hh:.1f} {cx+hw:.1f},{cy:.1f} {cx:.1f},{cy+hh:.1f} {cx-hw:.1f},{cy:.1f}"
        shape = f'<polygon points="{pts}" fill="{bg}" stroke="#1e293b" stroke-width="1.5"/>\n'
    elif node.kind in ("start", "end", "yes_end", "no_end"):
        r = node.h / 2
        shape = (f'<rect x="{node.cx - node.w/2:.1f}" y="{node.y:.1f}" '
                 f'width="{node.w}" height="{node.h}" rx="{r:.1f}" ry="{r:.1f}" '
                 f'fill="{bg}" stroke="#1e293b" stroke-width="1.5"/>\n')
    else:
        shape = (f'<rect x="{node.cx - node.w/2:.1f}" y="{node.y:.1f}" '
                 f'width="{node.w}" height="{node.h}" rx="8" ry="8" '
                 f'fill="{bg}" stroke="#1e293b" stroke-width="1.5"/>\n')

    return shape + texts


def _arrow_svg(src: Node, dst: Node, label: str = "") -> str:
    # Exit point from source
    if src.kind == "decision":
        if label == "Yes":
            x1, y1 = src.cx - src.w / 2, src.cy   # left diamond tip
        elif label == "No":
            x1, y1 = src.cx + src.w / 2, src.cy   # right diamond tip
        else:
            x1, y1 = src.cx, src.bottom
    elif src.w <= 10:
        x1, y1 = src.cx, src.cy
    else:
        x1, y1 = src.cx, src.bottom

    # Entry point to destination
    x2, y2 = (dst.cx, dst.cy) if dst.w <= 10 else (dst.cx, dst.top)

    same_col = abs(x1 - x2) < 5

    if same_col:
        path = f"M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}"
        lx, ly = x1 + 8, (y1 + y2) / 2
    else:
        mid_y = y1 + (y2 - y1) * 0.4
        path  = (f"M {x1:.1f} {y1:.1f} L {x1:.1f} {mid_y:.1f} "
                 f"L {x2:.1f} {mid_y:.1f} L {x2:.1f} {y2:.1f}")
        lx, ly = (x1 + x2) / 2, mid_y - 5

    lbl_svg = ""
    if label:
        lbl_svg = (f'<rect x="{lx-11:.1f}" y="{ly-12:.1f}" width="24" height="14" '
                   f'rx="3" fill="white" opacity="0.9"/>'
                   f'<text x="{lx+1:.1f}" y="{ly:.1f}" text-anchor="middle" '
                   f'font-size="10" font-family="{FONT}" fill="{ARROW_CLR}" '
                   f'font-weight="600">{html.escape(label)}</text>\n')

    return (f'<path d="{path}" fill="none" stroke="{ARROW_CLR}" stroke-width="1.8" '
            f'marker-end="url(#arrowhead)"/>\n') + lbl_svg


def _defs() -> str:
    return """<defs>
  <marker id="arrowhead" markerWidth="8" markerHeight="6"
          refX="7" refY="3" orient="auto">
    <polygon points="0 0, 8 3, 0 6" fill="#64748b"/>
  </marker>
</defs>"""


def generate_flow_svg(prompt_text: str) -> tuple[str, str]:
    """Returns (svg_string, error_message). error_message is '' on success."""
    try:
        nodes, edges = parse(prompt_text)
        if not nodes:
            return "", "No parseable content. Add at least one line."

        canvas_h = layout(nodes, edges) + 40
        nmap     = {n.nid: n for n in nodes}

        arrow_svg = "".join(
            _arrow_svg(nmap[e.src], nmap[e.dst], e.label)
            for e in edges
            if e.src in nmap and e.dst in nmap
        )
        shape_svg = "".join(_shape_svg(n) for n in nodes)

        svg = (f'<svg viewBox="0 0 {W} {canvas_h:.0f}" '
               f'xmlns="http://www.w3.org/2000/svg" '
               f'width="{W}" height="{canvas_h:.0f}" '
               f'style="background:#f8fafc;border-radius:12px;">\n'
               + _defs() + "\n"
               + arrow_svg + shape_svg
               + "</svg>")
        return svg, ""
    except Exception as e:
        import traceback
        return "", f"Diagram error: {e}\n{traceback.format_exc()}"


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar legend
# ─────────────────────────────────────────────────────────────────────────────

def legend_svg() -> str:
    items = [
        ("start",    "start: / begin:"),
        ("process",  "step: / bare line / →"),
        ("decision", "if:"),
        ("end",      "end: / yes_end: / no_end:"),
    ]
    h_total = len(items) * 32 + 16
    lines = [f'<svg viewBox="0 0 240 {h_total}" xmlns="http://www.w3.org/2000/svg" '
             f'width="240" height="{h_total}" style="background:transparent">']
    for i, (kind, label) in enumerate(items):
        bg, _ = COLORS.get(kind, ("#3b82f6", "#fff"))
        cy = 20 + i * 32
        if kind == "decision":
            lines.append(f'<polygon points="14,{cy-9} 28,{cy} 14,{cy+9} 0,{cy}" '
                         f'fill="{bg}" stroke="#1e293b" stroke-width="1"/>')
        elif kind in ("start", "end"):
            lines.append(f'<rect x="0" y="{cy-9}" width="28" height="18" rx="9" '
                         f'fill="{bg}" stroke="#1e293b" stroke-width="1"/>')
        else:
            lines.append(f'<rect x="0" y="{cy-9}" width="28" height="18" rx="4" '
                         f'fill="{bg}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="36" y="{cy+4}" font-size="11" '
                     f'font-family="{FONT}" fill="#334155">{html.escape(label)}</text>')
    lines.append("</svg>")
    return "\n".join(lines)
