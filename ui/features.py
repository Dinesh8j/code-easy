"""
ui/features.py
──────────────
Features & Dependency Impact Tracker tab.

Two panels:
  Left  — Register / edit features with their dependency checkboxes
  Right — Mark dependencies as DOWN and instantly see all impacted features
"""

import streamlit as st
from db import (
    upsert_feature, fetch_all_features, delete_feature,
    fetch_all_dependencies, fetch_dep_statuses,
    set_dep_status, get_impacted_features,
)

# ── Master dependency list (extend once you share the full list) ──────────
ALL_DEPS = [
    "RMQ",
    "Presto",
    "CrmIntelligence",
    "Rag",
    "LLM",
    "CrmIntelligencePy",
    "HDFS",
    "Kafka",
    "Redis",
    "MySQL",
    "MongoDB",
    "Elasticsearch",
    "S3",
    "ZFS",
]


def _dep_badge(dep: str, is_down: bool) -> str:
    color = "#ef4444" if is_down else "#22c55e"
    icon  = "🔴" if is_down else "🟢"
    return f"{icon} **{dep}**"


def render():
    st.subheader("🔗 Features & Dependency Impact Tracker")
    st.markdown("---")

    tab_register, tab_impact = st.tabs(
        ["📋 Register Features", "🚨 Impact Checker"]
    )

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — Register / manage features
    # ══════════════════════════════════════════════════════════════════════
    with tab_register:
        col_form, col_list = st.columns([1, 1.2], gap="large")

        # ── Add / edit feature form ───────────────────────────────────────
        with col_form:
            st.markdown("#### ➕ Add / Update Feature")

            fname = st.text_input(
                "Feature name *",
                placeholder="e.g. Similarity, Forecast, Insights…",
                key="feat_name_input"
            )

            st.markdown("**Dependencies used by this feature:**")

            # Pre-fill checkboxes if editing an existing feature
            prefill: set[str] = set()
            features = fetch_all_features()
            editing  = next((f for f in features
                             if f["name"].lower() == fname.strip().lower()), None)
            if editing:
                prefill = set(editing["dependencies"])
                st.info(f"✏️ Updating existing feature **{editing['name']}**")

            # Render checkboxes in 2 columns
            dep_cols = st.columns(2)
            selected_deps: list[str] = []
            for i, dep in enumerate(ALL_DEPS):
                with dep_cols[i % 2]:
                    checked = st.checkbox(
                        dep,
                        value=(dep in prefill),
                        key=f"dep_cb_{dep}_{fname}"
                    )
                    if checked:
                        selected_deps.append(dep)

            st.markdown("")
            if st.button("💾 Save Feature", type="primary",
                          use_container_width=True, key="save_feat"):
                if not fname.strip():
                    st.error("❌ Feature name is required.")
                elif not selected_deps:
                    st.error("❌ Select at least one dependency.")
                else:
                    upsert_feature(fname.strip(), selected_deps)
                    st.success(f"✅ Feature **{fname.strip()}** saved with "
                               f"{len(selected_deps)} dependenc"
                               f"{'y' if len(selected_deps)==1 else 'ies'}.")
                    st.rerun()

        # ── Saved features list ───────────────────────────────────────────
        with col_list:
            st.markdown("#### 📦 Registered Features")
            features = fetch_all_features()

            if not features:
                st.info("No features registered yet. Add one on the left.")
            else:
                dep_statuses = fetch_dep_statuses()
                for f in features:
                    deps      = f["dependencies"]
                    down_deps = [d for d in deps
                                 if dep_statuses.get(d, {}).get("is_down")]
                    status_icon = "🔴" if down_deps else "🟢"

                    with st.expander(
                        f"{status_icon} **{f['name']}**  "
                        f"·  {len(deps)} dep{'s' if len(deps)!=1 else ''}",
                        expanded=False
                    ):
                        # Dependency chips
                        chip_html = ""
                        for d in deps:
                            is_down = dep_statuses.get(d, {}).get("is_down", False)
                            bg  = "#fee2e2" if is_down else "#dbeafe"
                            clr = "#b91c1c" if is_down else "#1d4ed8"
                            chip_html += (
                                f'<span style="display:inline-block;margin:2px 4px 2px 0;'
                                f'padding:2px 10px;border-radius:12px;'
                                f'background:{bg};color:{clr};font-size:12px;'
                                f'font-weight:500;">{d}</span>'
                            )
                        st.markdown(chip_html, unsafe_allow_html=True)

                        if down_deps:
                            st.warning(
                                f"⚠️ Currently affected by: "
                                f"{', '.join(f'**{d}**' for d in down_deps)}"
                            )

                        upd = (f["updated_at"] or "")[:16]
                        st.caption(f"Last updated: {upd}")

                        if st.button("🗑 Delete", key=f"del_feat_{f['id']}",
                                     use_container_width=True):
                            delete_feature(f["id"])
                            st.rerun()

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — Impact checker
    # ══════════════════════════════════════════════════════════════════════
    with tab_impact:
        st.markdown("#### 🚨 Mark Dependencies as Down")
        st.caption("Toggle which dependencies are currently down — "
                   "impacted features update instantly.")

        dep_statuses = fetch_dep_statuses()
        all_known    = sorted(set(ALL_DEPS) |
                              set(fetch_all_dependencies()))

        # ── Status toggles ────────────────────────────────────────────────
        st.markdown("**Dependency status:**")
        toggle_cols = st.columns(3)
        changed     = False

        for i, dep in enumerate(all_known):
            with toggle_cols[i % 3]:
                current_down = dep_statuses.get(dep, {}).get("is_down", False)
                new_down = st.toggle(
                    f"{'🔴' if current_down else '🟢'}  {dep}",
                    value=current_down,
                    key=f"toggle_{dep}"
                )
                if new_down != current_down:
                    set_dep_status(dep, new_down)
                    changed = True

        if changed:
            st.rerun()

        # ── Impact summary ────────────────────────────────────────────────
        st.markdown("---")
        down_list = [d for d in all_known
                     if dep_statuses.get(d, {}).get("is_down", False)]

        if not down_list:
            st.success("✅ All dependencies are UP — no features impacted.")
        else:
            st.error(
                f"🔴 **{len(down_list)} dependenc"
                f"{'y' if len(down_list)==1 else 'ies'} DOWN:** "
                + ", ".join(f"`{d}`" for d in down_list)
            )

            impacted = get_impacted_features(down_list)

            st.markdown(f"#### ⚠️ {len(impacted)} Impacted Feature"
                        f"{'s' if len(impacted) != 1 else ''}")

            if not impacted:
                st.info("No registered features use these dependencies.")
            else:
                for f in impacted:
                    affected = f["affected_deps"]
                    all_deps = f["dependencies"]

                    with st.container():
                        st.markdown(
                            f'<div style="border:1.5px solid #ef4444;border-radius:10px;'
                            f'padding:12px 16px;margin-bottom:10px;background:#fff5f5;">'
                            f'<b style="font-size:15px;">🔴 {f["name"]}</b>',
                            unsafe_allow_html=True
                        )

                        # Show all deps, highlight affected ones
                        chip_html = ""
                        for d in all_deps:
                            is_hit = d in affected
                            bg  = "#fee2e2" if is_hit else "#f1f5f9"
                            clr = "#b91c1c" if is_hit else "#475569"
                            brd = "#fca5a5" if is_hit else "#e2e8f0"
                            chip_html += (
                                f'<span style="display:inline-block;margin:2px 4px 2px 0;'
                                f'padding:2px 10px;border-radius:12px;'
                                f'border:1px solid {brd};'
                                f'background:{bg};color:{clr};font-size:12px;'
                                f'font-weight:{"600" if is_hit else "400"};">'
                                f'{"⚠️ " if is_hit else ""}{d}</span>'
                            )
                        st.markdown(
                            chip_html + "</div>",
                            unsafe_allow_html=True
                        )

            # ── Summary table ─────────────────────────────────────────────
            if impacted:
                st.markdown("---")
                st.markdown("#### 📊 Impact Summary")
                rows = []
                for f in impacted:
                    rows.append({
                        "Feature":           f["name"],
                        "Down Dependencies": ", ".join(f["affected_deps"]),
                        "Total Deps":        len(f["dependencies"]),
                    })
                st.dataframe(rows, use_container_width=True, hide_index=True)
