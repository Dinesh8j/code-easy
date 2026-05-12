import os, sqlite3
from datetime import datetime, date
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Connection helpers
# ─────────────────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codecast.db")


def use_supabase() -> bool:
    try:
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        return bool(url and key)
    except Exception:
        return False


def _supabase():
    from supabase import create_client
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def _conn():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


# ─────────────────────────────────────────────────────────────────────────────
# Schema init (SQLite only)
# ─────────────────────────────────────────────────────────────────────────────

def init_db():
    con = _conn()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS feedbacks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            category   TEXT NOT NULL,
            message    TEXT NOT NULL,
            language   TEXT,
            json_used  TEXT,
            status     TEXT NOT NULL DEFAULT 'Open',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stats (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event      TEXT NOT NULL,
            language   TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tpl_feedbacks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            category   TEXT NOT NULL,
            message    TEXT NOT NULL,
            json_used  TEXT,
            status     TEXT NOT NULL DEFAULT 'Open',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tpl_stats (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event      TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS flow_stats (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event      TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    con.commit()
    con.close()


# ─────────────────────────────────────────────────────────────────────────────
# Code Generator — stats
# ─────────────────────────────────────────────────────────────────────────────

def log_generate(language: str):
    now = datetime.now().isoformat()
    if use_supabase():
        _supabase().table("stats").insert(
            {"event": "generate", "language": language, "created_at": now}
        ).execute()
    else:
        con = _conn()
        con.execute(
            "INSERT INTO stats (event,language,created_at) VALUES (?,?,?)",
            ("generate", language, now)
        )
        con.commit(); con.close()


def get_stats() -> dict:
    today = date.today().isoformat()
    if use_supabase():
        sb = _supabase()
        def _count(table, **filters):
            q = sb.table(table).select("*", count="exact")
            for k, v in filters.items(): q = q.eq(k, v)
            return q.execute().count or 0
        total_gen = _count("stats", event="generate")
        scala_gen = _count("stats", event="generate", language="Scala")
        py_gen    = _count("stats", event="generate", language="Python")
        today_gen = len([
            r for r in sb.table("stats").select("created_at").eq("event", "generate").execute().data
            if (r.get("created_at") or "").startswith(today)
        ])
        total_fb  = _count("feedbacks")
        open_fb   = _count("feedbacks", status="Open")
        resolved  = _count("feedbacks", status="Resolved")
        wip       = _count("feedbacks", status="In Progress")
        trend     = []
    else:
        con = _conn()
        total_gen = con.execute("SELECT COUNT(*) FROM stats WHERE event='generate'").fetchone()[0]
        today_gen = con.execute(
            "SELECT COUNT(*) FROM stats WHERE event='generate' AND created_at LIKE ?",
            (today + "%",)
        ).fetchone()[0]
        scala_gen = con.execute(
            "SELECT COUNT(*) FROM stats WHERE event='generate' AND language='Scala'"
        ).fetchone()[0]
        py_gen    = con.execute(
            "SELECT COUNT(*) FROM stats WHERE event='generate' AND language='Python'"
        ).fetchone()[0]
        total_fb  = con.execute("SELECT COUNT(*) FROM feedbacks").fetchone()[0]
        open_fb   = con.execute("SELECT COUNT(*) FROM feedbacks WHERE status='Open'").fetchone()[0]
        resolved  = con.execute("SELECT COUNT(*) FROM feedbacks WHERE status='Resolved'").fetchone()[0]
        wip       = con.execute("SELECT COUNT(*) FROM feedbacks WHERE status='In Progress'").fetchone()[0]
        trend_rows = con.execute("""
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM stats WHERE event='generate'
            GROUP BY day ORDER BY day DESC LIMIT 7
        """).fetchall()
        trend = [dict(r) for r in trend_rows]
        con.close()
    return dict(
        total_gen=total_gen, today_gen=today_gen,
        scala_gen=scala_gen, py_gen=py_gen,
        total_fb=total_fb, open_fb=open_fb,
        resolved=resolved, wip=wip, trend=trend
    )


# ─────────────────────────────────────────────────────────────────────────────
# Code Generator — feedbacks
# ─────────────────────────────────────────────────────────────────────────────

def insert_feedback(category: str, message: str, language: str, json_used: str):
    now = datetime.now().isoformat()
    if use_supabase():
        _supabase().table("feedbacks").insert({
            "category": category, "message": message, "language": language,
            "json_used": json_used[:3000], "status": "Open", "created_at": now
        }).execute()
    else:
        con = _conn()
        con.execute(
            "INSERT INTO feedbacks (category,message,language,json_used,created_at) VALUES (?,?,?,?,?)",
            (category, message, language, json_used[:3000], now)
        )
        con.commit(); con.close()


def fetch_feedbacks(status_filter="All", lang_filter="All") -> list[dict]:
    if use_supabase():
        sb = _supabase()
        q = sb.table("feedbacks").select("*").order("id", desc=True)
        if status_filter != "All": q = q.eq("status", status_filter)
        if lang_filter   != "All": q = q.eq("language", lang_filter)
        return q.execute().data or []
    else:
        con = _conn()
        sql, params = "SELECT * FROM feedbacks WHERE 1=1", []
        if status_filter != "All": sql += " AND status=?";   params.append(status_filter)
        if lang_filter   != "All": sql += " AND language=?"; params.append(lang_filter)
        sql += " ORDER BY id DESC"
        rows = [dict(r) for r in con.execute(sql, params).fetchall()]
        con.close(); return rows


def update_feedback_status(fid: int, status: str):
    if use_supabase():
        _supabase().table("feedbacks").update({"status": status}).eq("id", fid).execute()
    else:
        con = _conn()
        con.execute("UPDATE feedbacks SET status=? WHERE id=?", (status, fid))
        con.commit(); con.close()


def delete_feedback(fid: int):
    if use_supabase():
        _supabase().table("feedbacks").delete().eq("id", fid).execute()
    else:
        con = _conn()
        con.execute("DELETE FROM feedbacks WHERE id=?", (fid,))
        con.commit(); con.close()


# ─────────────────────────────────────────────────────────────────────────────
# Template Generator — stats & feedbacks
# ─────────────────────────────────────────────────────────────────────────────

def log_tpl_generate():
    now = datetime.now().isoformat()
    if use_supabase():
        _supabase().table("tpl_stats").insert({"event": "tpl_generate", "created_at": now}).execute()
    else:
        con = _conn()
        con.execute("INSERT INTO tpl_stats (event,created_at) VALUES (?,?)", ("tpl_generate", now))
        con.commit(); con.close()


def get_tpl_stats() -> dict:
    today = date.today().isoformat()
    if use_supabase():
        sb = _supabase()
        def _count(table, **filters):
            q = sb.table(table).select("*", count="exact")
            for k, v in filters.items(): q = q.eq(k, v)
            return q.execute().count or 0
        total_gen = _count("tpl_stats", event="tpl_generate")
        today_gen = len([
            r for r in sb.table("tpl_stats").select("created_at").eq("event", "tpl_generate").execute().data
            if (r.get("created_at") or "").startswith(today)
        ])
        total_fb = _count("tpl_feedbacks")
        open_fb  = _count("tpl_feedbacks", status="Open")
        resolved = _count("tpl_feedbacks", status="Resolved")
        wip      = _count("tpl_feedbacks", status="In Progress")
        trend    = []
    else:
        con = _conn()
        total_gen = con.execute("SELECT COUNT(*) FROM tpl_stats WHERE event='tpl_generate'").fetchone()[0]
        today_gen = con.execute(
            "SELECT COUNT(*) FROM tpl_stats WHERE event='tpl_generate' AND created_at LIKE ?",
            (today + "%",)
        ).fetchone()[0]
        total_fb = con.execute("SELECT COUNT(*) FROM tpl_feedbacks").fetchone()[0]
        open_fb  = con.execute("SELECT COUNT(*) FROM tpl_feedbacks WHERE status='Open'").fetchone()[0]
        resolved = con.execute("SELECT COUNT(*) FROM tpl_feedbacks WHERE status='Resolved'").fetchone()[0]
        wip      = con.execute("SELECT COUNT(*) FROM tpl_feedbacks WHERE status='In Progress'").fetchone()[0]
        trend_rows = con.execute("""
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM tpl_stats WHERE event='tpl_generate'
            GROUP BY day ORDER BY day DESC LIMIT 7
        """).fetchall()
        trend = [dict(r) for r in trend_rows]
        con.close()
    return dict(total_gen=total_gen, today_gen=today_gen,
                total_fb=total_fb, open_fb=open_fb, resolved=resolved, wip=wip, trend=trend)


def insert_tpl_feedback(category: str, message: str, json_used: str):
    now = datetime.now().isoformat()
    if use_supabase():
        _supabase().table("tpl_feedbacks").insert({
            "category": category, "message": message,
            "json_used": json_used[:3000], "status": "Open", "created_at": now
        }).execute()
    else:
        con = _conn()
        con.execute(
            "INSERT INTO tpl_feedbacks (category,message,json_used,created_at) VALUES (?,?,?,?)",
            (category, message, json_used[:3000], now)
        )
        con.commit(); con.close()


def fetch_tpl_feedbacks(status_filter="All") -> list[dict]:
    if use_supabase():
        sb = _supabase()
        q = sb.table("tpl_feedbacks").select("*").order("id", desc=True)
        if status_filter != "All": q = q.eq("status", status_filter)
        return q.execute().data or []
    else:
        con = _conn()
        sql, params = "SELECT * FROM tpl_feedbacks WHERE 1=1", []
        if status_filter != "All": sql += " AND status=?"; params.append(status_filter)
        sql += " ORDER BY id DESC"
        rows = [dict(r) for r in con.execute(sql, params).fetchall()]
        con.close(); return rows


def update_tpl_feedback_status(fid: int, status: str):
    if use_supabase():
        _supabase().table("tpl_feedbacks").update({"status": status}).eq("id", fid).execute()
    else:
        con = _conn()
        con.execute("UPDATE tpl_feedbacks SET status=? WHERE id=?", (status, fid))
        con.commit(); con.close()


def delete_tpl_feedback(fid: int):
    if use_supabase():
        _supabase().table("tpl_feedbacks").delete().eq("id", fid).execute()
    else:
        con = _conn()
        con.execute("DELETE FROM tpl_feedbacks WHERE id=?", (fid,))
        con.commit(); con.close()


# ─────────────────────────────────────────────────────────────────────────────
# Flow Diagram — stats
# ─────────────────────────────────────────────────────────────────────────────

def log_flow_generate():
    now = datetime.now().isoformat()
    if use_supabase():
        _supabase().table("flow_stats").insert({"event": "flow_generate", "created_at": now}).execute()
    else:
        con = _conn()
        con.execute("INSERT INTO flow_stats (event,created_at) VALUES (?,?)", ("flow_generate", now))
        con.commit(); con.close()


def get_feedback_passcode() -> str:
    try:    return st.secrets["FEEDBACK_PASSCODE"]
    except: return os.environ.get("FEEDBACK_PASSCODE", "life@30")


def get_flow_stats() -> dict:
    today = date.today().isoformat()
    if use_supabase():
        sb = _supabase()
        def _count(table, **filters):
            q = sb.table(table).select("*", count="exact")
            for k, v in filters.items(): q = q.eq(k, v)
            return q.execute().count or 0
        total_gen = _count("flow_stats", event="flow_generate")
        today_gen = len([
            r for r in sb.table("flow_stats").select("created_at").eq("event", "flow_generate").execute().data
            if (r.get("created_at") or "").startswith(today)
        ])
        trend = []
    else:
        con = _conn()
        total_gen = con.execute("SELECT COUNT(*) FROM flow_stats WHERE event='flow_generate'").fetchone()[0]
        today_gen = con.execute(
            "SELECT COUNT(*) FROM flow_stats WHERE event='flow_generate' AND created_at LIKE ?",
            (today + "%",)
        ).fetchone()[0]
        trend_rows = con.execute("""
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM flow_stats WHERE event='flow_generate'
            GROUP BY day ORDER BY day DESC LIMIT 7
        """).fetchall()
        trend = [dict(r) for r in trend_rows]
        con.close()
    return dict(total_gen=total_gen, today_gen=today_gen, trend=trend)
