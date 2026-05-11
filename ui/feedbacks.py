"""
ui/feedbacks.py
───────────────
Streamlit UI for the 💬 Feedbacks tab.
"""

import csv
import io
import streamlit as st

from db import (
    fetch_feedbacks, update_feedback_status, delete_feedback,
    fetch_tpl_feedbacks, update_tpl_feedback_status, delete_tpl_feedback,
)

_ICONS = {"Open": "🔴", "In Progress": "🟡", "Resolved": "🟢"}


def _feedback_section(
    title: str,
    fetch_fn,
    update_fn,
    delete_fn,
    status_key: str,
    record_key: str,
    lang_key: str = None,
    has_lang: bool = False,
    export_filename: str = None,
):
    st.markdown(f"#### {title}")

    # Filters
    f1, f2 = st.columns(2) if has_lang else (st.columns(2)[0], None)
    with f1:
        flt_st = st.selectbox(
            "Status", ["All", "Open", "In Progress", "Resolved"], key=status_key
        )
    flt_lang = "All"
    if has_lang and f2:
        with f2:
            flt_lang = st.selectbox("Language", ["All", "Scala", "Python"], key=lang_key)

    rows         = fetch_fn(flt_st, flt_lang) if has_lang else fetch_fn(flt_st)
    all_rows_cnt = fetch_fn("All", "All")     if has_lang else fetch_fn("All")

    # Summary metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total",          len(all_rows_cnt))
    m2.metric("🔴 Open",        sum(1 for r in all_rows_cnt if r["status"] == "Open"))
    m3.metric("🟡 In Progress", sum(1 for r in all_rows_cnt if r["status"] == "In Progress"))
    m4.metric("🟢 Resolved",    sum(1 for r in all_rows_cnt if r["status"] == "Resolved"))
    st.caption(f"{len(rows)} record(s) match current filter")

    if not rows:
        st.info("No feedback matches the selected filters.")
    else:
        labels = [
            f"{_ICONS.get(r['status'], '⚪')}  [{r['id']}]  {r['category']}"
            + (f"  ·  {r.get('language', '') or ''}" if has_lang else "")
            + f"  ·  {(r.get('created_at', '') or '')[:16]}"
            for r in rows
        ]
        sel_idx = st.selectbox(
            "Select a record", range(len(labels)),
            format_func=lambda i: labels[i], key=record_key
        )
        row = rows[sel_idx]
        fid = row["id"]

        st.markdown("---")
        col_meta, col_actions = st.columns([2, 1])
        with col_meta:
            st.markdown(f"**Category:** {row['category']}")
            if has_lang:
                st.markdown(f"**Language:** {row.get('language', '') or '—'}")
            st.markdown(f"**Submitted:** {(row.get('created_at', '') or '')[:16]}")
            st.markdown(f"**Status:** {_ICONS.get(row['status'], '⚪')} {row['status']}")
        with col_actions:
            st.markdown("**Update Status**")
            if st.button("✅ Mark Resolved",    key=f"{record_key}_res", use_container_width=True):
                update_fn(fid, "Resolved");    st.rerun()
            if st.button("🔄 Mark In Progress", key=f"{record_key}_wip", use_container_width=True):
                update_fn(fid, "In Progress"); st.rerun()
            if st.button("🗑 Delete Record",     key=f"{record_key}_del", use_container_width=True):
                delete_fn(fid); st.rerun()

        st.markdown("**Message:**")
        st.info(row["message"])
        if row.get("json_used"):
            with st.expander("Input snapshot"):
                st.code(row["json_used"][:1500], language="json")

    # CSV export
    if export_filename:
        all_rows = fetch_fn("All", "All") if has_lang else fetch_fn("All")
        if all_rows:
            buf = io.StringIO()
            writer = csv.DictWriter(
                buf, fieldnames=list(all_rows[0].keys()), extrasaction="ignore"
            )
            writer.writeheader(); writer.writerows(all_rows)
            st.download_button(
                "⬇️ Export CSV", buf.getvalue(),
                file_name=export_filename, mime="text/csv",
                key=f"exp_{record_key}"
            )
        else:
            st.caption("Nothing to export yet.")

    st.markdown("---")


def render():
    st.subheader("💬 Feedbacks")
    st.markdown("---")

    _feedback_section(
        "🛠 Code Generator Feedbacks",
        fetch_fn=fetch_feedbacks,
        update_fn=update_feedback_status,
        delete_fn=delete_feedback,
        status_key="fb_gen_status",
        lang_key="fb_gen_lang",
        record_key="fb_gen_rec",
        has_lang=True,
        export_filename="codecast_feedbacks.csv",
    )

    _feedback_section(
        "📄 Template Generator Feedbacks",
        fetch_fn=fetch_tpl_feedbacks,
        update_fn=update_tpl_feedback_status,
        delete_fn=delete_tpl_feedback,
        status_key="fb_tpl_status",
        record_key="fb_tpl_rec",
        has_lang=False,
        export_filename="codecast_tpl_feedbacks.csv",
    )
