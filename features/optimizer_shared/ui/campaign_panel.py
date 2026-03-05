"""
Tier 1 Campaign Recommendation Panel — Compact UX

Compact single-row-per-campaign list, grouped by recommendation type.
Summary stats shown as an inline chip bar. Section headers match the
existing dark-theme palette. No cards — everything fits in ~1/3 the
vertical space of the previous grid.

Recalculation flow (unchanged):
  1. Initial run — full dataset → Tier 1 panel shown → Tier 2 uses full results
  2. User toggles checkboxes → clicks "Apply Tier 1 Selections & Recalculate Bids"
  3. tier1_accepted_campaigns stored → run_optimizer_refactored = True
  4. Optimizer re-runs on filtered df → averages / thresholds recalculate
  5. Panel reloads with selections preserved

Styling: inline styles matching the dashboard palette (#0a0f1a background,
#e2e8f0 text, rgba(148,163,184,0.12) borders). opt-sub-kpi classes (injected
by results.py) are NOT used here to stay compact. No new CSS classes.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd


# ── Recommendation metadata ───────────────────────────────────────────────────
_REC_META: dict[str, dict] = {
    "PAUSE": {
        "label":       "PAUSE",
        "section":     "Pause Candidates",
        "color":       "#ef4444",
        "border":      "rgba(239,68,68,0.3)",
        "bg":          "rgba(239,68,68,0.06)",
        "badge_bg":    "rgba(239,68,68,0.15)",
        "badge_fg":    "#fca5a5",
    },
    "REDUCE_BUDGET": {
        "label":       "REDUCE",
        "section":     "Reduce Budget",
        "color":       "#f59e0b",
        "border":      "rgba(245,158,11,0.3)",
        "bg":          "rgba(245,158,11,0.06)",
        "badge_bg":    "rgba(245,158,11,0.15)",
        "badge_fg":    "#fcd34d",
    },
    "RESTRUCTURE": {
        "label":       "RESTRUCTURE",
        "section":     "Restructure",
        "color":       "#06b6d4",
        "border":      "rgba(6,182,212,0.3)",
        "bg":          "rgba(6,182,212,0.06)",
        "badge_bg":    "rgba(6,182,212,0.15)",
        "badge_fg":    "#67e8f9",
    },
    "INCREASE_BUDGET": {
        "label":       "INCREASE",
        "section":     "Scale & Grow",
        "color":       "#22c55e",
        "border":      "rgba(34,197,94,0.3)",
        "bg":          "rgba(34,197,94,0.06)",
        "badge_bg":    "rgba(34,197,94,0.15)",
        "badge_fg":    "#86efac",
    },
    "SCALE": {
        "label":       "SCALE",
        "section":     "Scale & Grow",
        "color":       "#22c55e",
        "border":      "rgba(34,197,94,0.3)",
        "bg":          "rgba(34,197,94,0.06)",
        "badge_bg":    "rgba(34,197,94,0.15)",
        "badge_fg":    "#86efac",
    },
}

_SECTION_ORDER = ["PAUSE", "REDUCE_BUDGET", "RESTRUCTURE", "INCREASE_BUDGET"]
_ACTIONABLE    = set(_SECTION_ORDER)
_CURRENCY      = "AED"


def _f(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def render_tier1_campaign_panel(campaign_recs: pd.DataFrame) -> list[str]:
    """
    Render compact Tier 1 panel. Returns accepted campaign names.
    Also persisted to st.session_state["tier1_accepted_campaigns"].
    """
    if campaign_recs is None or campaign_recs.empty:
        return []

    actionable = campaign_recs[campaign_recs["recommendation"].isin(_ACTIONABLE)].copy()
    maintain   = campaign_recs[campaign_recs["recommendation"] == "MAINTAIN"].copy()

    previously_accepted: set[str] = set(st.session_state.get("tier1_accepted_campaigns", []))

    # ── Empty state ───────────────────────────────────────────────────────────
    if actionable.empty:
        st.markdown(
            "<div style='border:1px solid rgba(34,197,94,0.2);border-left:3px solid #22c55e;"
            "border-radius:8px;padding:10px 16px;background:rgba(34,197,94,0.05);"
            "margin-bottom:16px;'>"
            "<span style='color:#86efac;font-size:0.72rem;font-weight:700;"
            "letter-spacing:0.07em;text-transform:uppercase;'>Tier 1</span>"
            "<span style='color:#cbd5e1;font-size:0.85rem;margin-left:10px;'>"
            "✓ All campaigns within range — no campaign-level actions needed.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        return []

    # ── Summary metric cards (shared opt-sub-kpi style from results.py CSS) ──
    total_flagged = len(actionable)
    total_camps   = len(campaign_recs)
    pause_n  = int((actionable["recommendation"] == "PAUSE").sum())
    scale_n  = int(actionable["recommendation"].isin(["SCALE", "INCREASE_BUDGET"]).sum())
    impact   = _f(actionable["estimated_monthly_impact"].sum()) if "estimated_monthly_impact" in actionable.columns else 0.0

    # Read live checkbox states — Streamlit pre-populates widget state before rendering
    _pause_names = (
        set(actionable.loc[actionable["recommendation"] == "PAUSE", "campaign_name"].tolist())
        if "campaign_name" in actionable.columns else set()
    )
    _live_paused = sum(1 for c in _pause_names if st.session_state.get(f"tier1_cb_{c}", False))
    impact_sub = f"{_live_paused} paused — bids filtered live" if _live_paused > 0 else "savings potential"

    st.markdown(
        f'<div class="opt-sub-kpi-grid">'
        f'<div class="opt-sub-kpi">'
        f'<div class="opt-sub-kpi-label">Campaigns Flagged</div>'
        f'<div class="opt-sub-kpi-value">{total_flagged}</div>'
        f'<div class="opt-sub-kpi-sub"><span style="color:#94a3b8;">of {total_camps} analyzed</span></div>'
        f'</div>'
        f'<div class="opt-sub-kpi">'
        f'<div class="opt-sub-kpi-label">Pause Candidates</div>'
        f'<div class="opt-sub-kpi-value">{pause_n}</div>'
        f'<div class="opt-sub-kpi-sub"><span style="color:#fca5a5;">campaigns to pause</span></div>'
        f'</div>'
        f'<div class="opt-sub-kpi">'
        f'<div class="opt-sub-kpi-label">Scale &amp; Grow</div>'
        f'<div class="opt-sub-kpi-value">{scale_n}</div>'
        f'<div class="opt-sub-kpi-sub"><span style="color:#86efac;">scale / increase budget</span></div>'
        f'</div>'
        f'<div class="opt-sub-kpi">'
        f'<div class="opt-sub-kpi-label">Est. Monthly Impact</div>'
        f'<div class="opt-sub-kpi-value">{_CURRENCY}{abs(impact):,.0f}</div>'
        f'<div class="opt-sub-kpi-sub"><span style="color:#fcd34d;">{impact_sub}</span></div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Campaign rows grouped by section ─────────────────────────────────────
    accepted: list[str] = []

    for rec_type in _SECTION_ORDER:
        if rec_type == "INCREASE_BUDGET":
            section_df = actionable[actionable["recommendation"].isin(["INCREASE_BUDGET", "SCALE"])]
        else:
            section_df = actionable[actionable["recommendation"] == rec_type]
        if section_df.empty:
            continue

        meta = _REC_META[rec_type]

        # Section header — compact divider style
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:8px;margin:10px 0 6px 0;'>"
            f"<div style='width:3px;height:14px;background:{meta['color']};"
            f"border-radius:2px;flex-shrink:0;'></div>"
            f"<span style='color:{meta['badge_fg']};font-size:0.7rem;font-weight:700;"
            f"letter-spacing:0.07em;text-transform:uppercase;'>{meta['section']}</span>"
            f"<span style='color:#334155;font-size:0.7rem;'>— {len(section_df)}</span>"
            f"<div style='flex:1;height:1px;background:rgba(51,65,85,0.5);'></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        for _, row in section_df.iterrows():
            camp_name = str(row.get("campaign_name", row.get("Campaign Name", "")))
            roas      = _f(row.get("roas", 0))
            spend     = _f(row.get("spend", 0))
            orders    = int(_f(row.get("orders", 0)))
            impact_v  = _f(row.get("estimated_monthly_impact", 0))
            confidence = str(row.get("confidence", "")).upper()
            is_high   = confidence == "HIGH"
            row_rec   = str(row.get("recommendation", rec_type))
            row_meta  = _REC_META.get(row_rec, meta)

            default_on = (
                camp_name in previously_accepted
                or (rec_type == "PAUSE" and is_high)
            )

            # Impact display
            if impact_v > 0:
                impact_str   = f"−{_CURRENCY}{impact_v:,.0f}/mo"
                impact_color = "#22c55e"
            elif impact_v < 0:
                impact_str   = f"+{_CURRENCY}{abs(impact_v):,.0f}/mo"
                impact_color = "#f59e0b"
            else:
                impact_str   = "—"
                impact_color = "#64748b"

            conf_html = (
                f"<span style='background:rgba(239,68,68,0.15);color:#fca5a5;"
                f"font-size:0.62rem;font-weight:700;padding:1px 5px;border-radius:3px;"
                f"letter-spacing:0.04em;margin-right:4px;'>HIGH</span>"
                if is_high else ""
            )

            # Concrete action suggestion chip for non-PAUSE types
            if row_rec == "REDUCE_BUDGET":
                # Impact = spend * 0.3 → 30% cut recommended
                suggestion_html = (
                    f"<span style='background:rgba(245,158,11,0.08);color:#fbbf24;"
                    f"font-size:0.6rem;font-weight:700;padding:1px 7px;border-radius:3px;"
                    f"letter-spacing:0.03em;border:1px solid rgba(245,158,11,0.2);"
                    f"white-space:nowrap;flex-shrink:0;'>cut −30%</span>"
                )
            elif row_rec in ("INCREASE_BUDGET", "SCALE"):
                budget_add = impact_v / roas if roas > 0 else 0
                suggestion_html = (
                    f"<span style='background:rgba(34,197,94,0.08);color:#86efac;"
                    f"font-size:0.6rem;font-weight:700;padding:1px 7px;border-radius:3px;"
                    f"letter-spacing:0.03em;border:1px solid rgba(34,197,94,0.2);"
                    f"white-space:nowrap;flex-shrink:0;'>"
                    f"+{_CURRENCY}{budget_add:,.0f} budget</span>"
                )
            elif row_rec == "RESTRUCTURE":
                suggestion_html = (
                    f"<span style='background:rgba(6,182,212,0.08);color:#67e8f9;"
                    f"font-size:0.6rem;font-weight:700;padding:1px 7px;border-radius:3px;"
                    f"letter-spacing:0.03em;border:1px solid rgba(6,182,212,0.2);"
                    f"white-space:nowrap;flex-shrink:0;'>split campaign</span>"
                )
            else:
                suggestion_html = ""

            display_name = camp_name if len(camp_name) <= 42 else camp_name[:39] + "…"

            cb_col, row_col = st.columns([0.035, 0.965], gap="small")
            with cb_col:
                checked = st.checkbox(
                    " ",
                    value=default_on,
                    key=f"tier1_cb_{camp_name}",
                    label_visibility="collapsed",
                )
            with row_col:
                st.markdown(
                    f"<div style='"
                    f"display:flex;align-items:center;gap:10px;"
                    f"background:{row_meta['bg']};"
                    f"border:1px solid {row_meta['border']};"
                    f"border-left:3px solid {row_meta['color']};"
                    f"border-radius:7px;padding:7px 12px;"
                    f"margin-bottom:3px;min-height:36px;'>"
                    # Badge
                    f"<span style='background:{row_meta['badge_bg']};color:{row_meta['badge_fg']};"
                    f"font-size:0.63rem;font-weight:700;padding:2px 7px;border-radius:4px;"
                    f"letter-spacing:0.04em;text-transform:uppercase;flex-shrink:0;'>"
                    f"{row_meta['label']}</span>"
                    f"{conf_html}"
                    f"{suggestion_html}"
                    # Campaign name
                    f"<span style='color:#e2e8f0;font-size:0.82rem;font-weight:600;"
                    f"flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;"
                    f"white-space:nowrap;'>{display_name}</span>"
                    # Metrics strip
                    f"<span style='color:#64748b;font-size:0.75rem;white-space:nowrap;"
                    f"flex-shrink:0;'>"
                    f"<strong style='color:#cbd5e1;'>{roas:.1f}×</strong> ROAS"
                    f"&nbsp;&nbsp;"
                    f"<strong style='color:#cbd5e1;'>{orders}</strong> orders"
                    f"&nbsp;&nbsp;"
                    f"<strong style='color:#cbd5e1;'>{_CURRENCY}{spend:,.0f}</strong> spend"
                    f"</span>"
                    # Impact
                    f"<span style='color:{impact_color};font-size:0.75rem;font-weight:700;"
                    f"white-space:nowrap;flex-shrink:0;margin-left:4px;'>{impact_str}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            if checked:
                accepted.append(camp_name)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── Maintain in expander ──────────────────────────────────────────────────
    if not maintain.empty:
        with st.expander(
            f"✓  {len(maintain)} campaign(s) performing normally",
            expanded=False,
        ):
            disp = [c for c in ["campaign_name", "roas", "orders", "efficiency_ratio"] if c in maintain.columns]
            st.dataframe(
                maintain[disp],
                width='stretch',
                hide_index=True,
                column_config={
                    "campaign_name":    st.column_config.TextColumn("Campaign"),
                    "roas":             st.column_config.NumberColumn("ROAS",       format="%.2f×"),
                    "efficiency_ratio": st.column_config.NumberColumn("Efficiency", format="%.2f×"),
                },
            )

    # Persist selection state — results.py reads checkbox widget states on-the-fly
    st.session_state["tier1_accepted_campaigns"] = accepted
    return accepted
