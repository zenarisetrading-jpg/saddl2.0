"""
Impact Diagnostic Tool — Compare Current Logic vs DB-Only Values
This is a READ-ONLY diagnostic page that does NOT modify production behavior.
Use this to validate the "DB as source of truth" migration.
"""

from typing import Dict, Any

import numpy as np
import pandas as pd
import streamlit as st

from features.impact.data.fetchers import fetch_impact_data
from features.impact.data.transforms import ensure_impact_columns
import json
import plotly.express as px


def render_diagnostics() -> None:
    """Main entry point for diagnostic comparison tool (read-only)."""
    st.markdown("## Impact Diagnostic Tool")
    st.caption("Compare current UI logic vs DB-provided values (read-only)")

    client_id = st.session_state.get("active_account_id")
    if not client_id:
        st.warning("No account selected.")
        return

    test_mode = st.session_state.get("test_mode", False)
    cache_version = "diag_v1_" + str(st.session_state.get("data_upload_timestamp", "init"))

    with st.spinner("Loading impact data..."):
        raw_df, summary = fetch_impact_data(
            client_id,
            test_mode,
            before_days=14,
            after_days=14,
            cache_version=cache_version,
        )

    if raw_df.empty:
        st.info("No impact data available.")
        return

    st.caption(
        "DB manager in use: "
        + ("SQLite (test/local)" if test_mode else "Postgres (production)")
    )

    # Create two separate dataframes
    current_df = ensure_impact_columns(raw_df.copy())
    db_only_df = raw_df.copy()

    tab_current, tab_db, tab_diff, tab_tiers, tab_v33 = st.tabs(
        [
            "Current Logic View",
            "DB-Only View",
            "Divergence Analysis",
            "Confidence Tiering (v3.0)",
            "v3.3 Debug"
        ]
    )

    with tab_current:
        _render_current_view(current_df, summary)

    with tab_db:
        _render_db_only_view(db_only_df, summary)

    with tab_diff:
        _render_divergence_analysis(current_df, db_only_df)
        st.divider()
        _render_quadrant_validation(current_df, db_only_df)

    with tab_tiers:
        _render_confidence_tier_view(db_only_df)

    with tab_v33:
        _render_v33_debug(db_only_df)


def _render_current_view(df: pd.DataFrame, summary: Dict[str, Any]) -> None:
    """Render view using current transforms (as production)."""
    st.markdown("### Current Logic (with transforms)")
    st.caption("This uses validate_impact_columns() — same as production (v3.3)")

    _render_impact_summary(df, impact_col="decision_impact", title="Impact Summary (Current)")

    col1, col2, col3, col4 = st.columns(4)

    total_impact = df["decision_impact"].sum() if "decision_impact" in df.columns else 0
    market_drag_count = (
        (df["market_tag"] == "Market Drag").sum() if "market_tag" in df.columns else 0
    )
    gap_count = (df["market_tag"] == "Gap").sum() if "market_tag" in df.columns else 0
    harvest_count = (
        (df["action_type"].str.upper() == "HARVEST").sum()
        if "action_type" in df.columns
        else 0
    )

    col1.metric("Total Impact", f"${total_impact:,.0f}")
    col2.metric("Market Drag", int(market_drag_count))
    col3.metric("Gaps", int(gap_count))
    col4.metric("Harvests", int(harvest_count))

    st.markdown("#### Sample Data (first 20 rows)")
    display_cols = [
        "action_type",
        "target_text",
        "market_tag",
        "decision_impact",
        "final_decision_impact",
        "expected_trend_pct",
        "decision_value_pct",
    ]
    available_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[available_cols].head(20), use_container_width=True)


def _render_db_only_view(df: pd.DataFrame, summary: Dict[str, Any]) -> None:
    """Render view using only DB-provided values (no transforms)."""
    st.markdown("### DB-Only (raw from DB manager)")
    st.caption("No ensure_impact_columns() applied — pure DB values")

    _render_impact_summary(df, impact_col="final_decision_impact", title="Impact Summary (DB-Only)")

    col1, col2, col3, col4 = st.columns(4)

    total_impact = (
        df["final_decision_impact"].sum() if "final_decision_impact" in df.columns else 0
    )
    market_drag_count = (
        (df["market_tag"] == "Market Drag").sum() if "market_tag" in df.columns else 0
    )
    gap_count = (df["market_tag"] == "Gap").sum() if "market_tag" in df.columns else 0
    harvest_count = (
        (df["action_type"].str.upper() == "HARVEST").sum()
        if "action_type" in df.columns
        else 0
    )

    col1.metric("Total Impact (DB)", f"${total_impact:,.0f}")
    col2.metric("Market Drag", int(market_drag_count))
    col3.metric("Gaps", int(gap_count))
    col4.metric("Harvests", int(harvest_count))

    st.markdown("#### Sample Data (first 20 rows)")
    display_cols = [
        "action_type",
        "target_text",
        "market_tag",
        "decision_impact",
        "final_decision_impact",
        "expected_trend_pct",
        "decision_value_pct",
    ]
    available_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[available_cols].head(20), use_container_width=True)


def _render_divergence_analysis(current_df: pd.DataFrame, db_df: pd.DataFrame) -> None:
    """Compare current logic vs DB-only and highlight divergences."""
    st.markdown("### Divergence Analysis")

    st.markdown("#### Impact Summary (Side-by-Side)")
    col_left, col_right = st.columns(2)
    with col_left:
        _render_impact_summary(current_df, impact_col="decision_impact", title="Current Logic")
    with col_right:
        _render_impact_summary(db_df, impact_col="final_decision_impact", title="DB-Only")

    st.markdown("#### Delta Summary (Current − DB)")
    curr_summary = _compute_summary(current_df, impact_col="decision_impact")
    db_summary = _compute_summary(db_df, impact_col="final_decision_impact")

    delta_impact = curr_summary["total_impact"] - db_summary["total_impact"]
    delta_wins = curr_summary["wins_count"] - db_summary["wins_count"]
    delta_gaps = curr_summary["gaps_count"] - db_summary["gaps_count"]
    delta_drag = curr_summary["drag_count"] - db_summary["drag_count"]

    with st.container(horizontal=True):
        st.metric("Δ Impact", f"${delta_impact:,.0f}", border=True)
        st.metric("Δ Wins", f"{delta_wins:+d}", border=True)
        st.metric("Δ Gaps", f"{delta_gaps:+d}", border=True)
        st.metric("Δ Market Drag", f"{delta_drag:+d}", border=True)

    st.markdown("#### Summary Comparison")
    current_total = (
        current_df["decision_impact"].sum() if "decision_impact" in current_df.columns else 0
    )
    db_total = (
        db_df["final_decision_impact"].sum() if "final_decision_impact" in db_df.columns else 0
    )

    diff = current_total - db_total
    diff_pct = (diff / db_total * 100) if db_total != 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Current Total", f"${current_total:,.0f}")
    col2.metric("DB Total", f"${db_total:,.0f}")
    col3.metric("Difference", f"${diff:,.0f}", f"{diff_pct:+.1f}%")

    if abs(diff) < 1:
        st.success("No divergence detected — Current logic matches DB")
    else:
        st.warning(f"Divergence of ${abs(diff):,.0f} detected")

    _render_classification_diff(current_df, db_df)
    _render_mismatch_table(current_df, db_df)


def _compute_summary(df: pd.DataFrame, impact_col: str) -> Dict[str, Any]:
    """Compute a small, diagnostic-safe summary without mutating data."""
    if df.empty:
        return {
            "total_impact": 0.0,
            "validated_impact": 0.0,
            "offensive_value": 0.0,
            "defensive_value": 0.0,
            "gap_value": 0.0,
            "drag_count": 0,
            "wins_count": 0,
            "gaps_count": 0,
            "win_rate": 0.0,
        }

    impact = df[impact_col] if impact_col in df.columns else pd.Series([0] * len(df))
    market_tag = df.get("market_tag", pd.Series(["Unknown"] * len(df)))
    impact_tier = df.get("impact_tier", pd.Series([""] * len(df)))
    validation_status = df.get("validation_status", pd.Series([""] * len(df)))

    excluded_mask = market_tag.str.contains("Excluded", na=False) | impact_tier.str.contains("Excluded", na=False)
    offensive_mask = market_tag == "Offensive Win"
    defensive_mask = market_tag == "Defensive Win"
    gap_mask = market_tag == "Gap"
    drag_mask = market_tag == "Market Drag"

    offensive_val = impact[offensive_mask].sum()
    defensive_val = impact[defensive_mask].sum()
    gap_val = impact[gap_mask].sum()

    counted_mask = (~excluded_mask) & (impact != 0)
    wins_count = int(((offensive_mask | defensive_mask) & counted_mask).sum())
    gaps_count = int((gap_mask & counted_mask).sum())
    total_counted = wins_count + gaps_count
    win_rate = (wins_count / total_counted) * 100 if total_counted > 0 else 0

    validated_mask = validation_status.str.contains(
        "✓|CPC Validated|CPC Match|Directional|Confirmed|Normalized|Volume",
        na=False,
        regex=True,
    )
    validated_impact = impact[validated_mask].sum()

    return {
        "total_impact": float(impact.sum()),
        "validated_impact": float(validated_impact),
        "offensive_value": float(offensive_val),
        "defensive_value": float(defensive_val),
        "gap_value": float(gap_val),
        "drag_count": int(drag_mask.sum()),
        "wins_count": wins_count,
        "gaps_count": gaps_count,
        "win_rate": float(win_rate),
    }


def _render_impact_summary(df: pd.DataFrame, impact_col: str, title: str) -> None:
    """Render a compact, diagnostic summary resembling the main impact banner."""
    summary = _compute_summary(df, impact_col)

    with st.container(border=True):
        st.subheader(title)
        st.caption("Counts exclude rows marked Excluded or zero-impact")

        with st.container(horizontal=True):
            st.metric("Total Impact", f"${summary['total_impact']:,.0f}", border=True)
            st.metric("Validated Impact", f"${summary['validated_impact']:,.0f}", border=True)
            st.metric("Wins (Counted)", f"{summary['wins_count']}", border=True)
            st.metric("Gaps (Counted)", f"{summary['gaps_count']}", border=True)
            st.metric("Market Drag", f"{summary['drag_count']}", border=True)

        with st.container(horizontal=True):
            st.metric(
                "What Worked",
                f"${summary['offensive_value'] + summary['defensive_value']:,.0f}",
                border=True,
            )
            st.metric("What Didn't", f"${summary['gap_value']:,.0f}", border=True)
            st.metric("Decision Score", f"{summary['win_rate']:.0f}", border=True)


def _render_classification_diff(current_df: pd.DataFrame, db_df: pd.DataFrame) -> None:
    """Compare market_tag distributions."""
    st.markdown("#### Classification Distribution")

    current_counts = (
        current_df["market_tag"].value_counts().to_dict()
        if "market_tag" in current_df.columns
        else {}
    )
    db_counts = (
        db_df["market_tag"].value_counts().to_dict()
        if "market_tag" in db_df.columns
        else {}
    )

    all_tags = set(current_counts.keys()) | set(db_counts.keys())

    diff_data = []
    for tag in sorted(all_tags):
        c = current_counts.get(tag, 0)
        d = db_counts.get(tag, 0)
        diff_data.append(
            {
                "Market Tag": tag,
                "Current": c,
                "DB": d,
                "Diff": c - d,
                "Match": "OK" if c == d else "DIFF",
            }
        )

    st.dataframe(pd.DataFrame(diff_data), use_container_width=True, hide_index=True)


def _render_mismatch_table(current_df: pd.DataFrame, db_df: pd.DataFrame) -> None:
    """Show rows where current logic diverges from DB."""
    st.markdown("#### Row-Level Mismatches (Top 50)")

    if len(current_df) != len(db_df):
        st.error("DataFrame lengths don't match — cannot compare row-by-row")
        return

    current_impact = current_df.get("decision_impact", pd.Series([0] * len(current_df)))
    db_impact = db_df.get("final_decision_impact", pd.Series([0] * len(db_df)))

    mismatch_mask = ~np.isclose(current_impact.fillna(0).values, db_impact.fillna(0).values, rtol=0.01)
    mismatch_indices = np.where(mismatch_mask)[0][:50]

    if len(mismatch_indices) == 0:
        st.success("No row-level mismatches detected")
        return

    st.warning(f"Found {mismatch_mask.sum()} mismatches (showing first 50)")

    mismatch_rows = []
    for idx in mismatch_indices:
        mismatch_rows.append(
            {
                "Target": str(current_df.iloc[idx].get("target_text", "N/A"))[:40],
                "Action Type": current_df.iloc[idx].get("action_type", "N/A"),
                "Current Impact": float(current_impact.iloc[idx]) if idx < len(current_impact) else 0,
                "DB Impact": float(db_impact.iloc[idx]) if idx < len(db_impact) else 0,
                "Diff": float(current_impact.iloc[idx] - db_impact.iloc[idx])
                if idx < len(current_impact)
                else 0,
                "Current Tag": current_df.iloc[idx].get("market_tag", "N/A"),
                "DB Tag": db_df.iloc[idx].get("market_tag", "N/A"),
            }
        )

    st.dataframe(pd.DataFrame(mismatch_rows), use_container_width=True, hide_index=True)


def _render_quadrant_validation(current_df: pd.DataFrame, db_df: pd.DataFrame) -> None:
    """Validate quadrant classification against DB values."""
    import plotly.express as px

    st.markdown("### Decision Outcome Map Validation")

    col1, col2 = st.columns(2)
    with col1:
        color_by = st.radio("Color by", ["market_tag", "action_type"], horizontal=True)
    with col2:
        data_source = st.radio("Data source", ["DB-provided", "Recomputed"], horizontal=True)

    plot_df = db_df.copy() if data_source == "DB-provided" else current_df.copy()

    if "expected_trend_pct" not in plot_df.columns or "decision_value_pct" not in plot_df.columns:
        st.warning("Missing required columns for scatter plot")
        return

    fig = px.scatter(
        plot_df,
        x="expected_trend_pct",
        y="decision_value_pct",
        color=color_by,
        hover_data=[
            "target_text",
            "action_type",
            "market_tag",
            "decision_impact",
            "validation_status",
        ],
        title=f"Decision Outcome Map ({data_source})",
        labels={
            "expected_trend_pct": "Expected Trend % (Market)",
            "decision_value_pct": "Decision Value % (Your Alpha)",
        },
    )

    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_dash="dash", line_color="gray")

    fig.add_annotation(x=50, y=50, text="Offensive Win", showarrow=False)
    fig.add_annotation(x=-50, y=50, text="Defensive Win", showarrow=False)
    fig.add_annotation(x=50, y=-50, text="Gap", showarrow=False)
    fig.add_annotation(x=-50, y=-50, text="Market Drag", showarrow=False)

    st.plotly_chart(fig, use_container_width=True)

    _check_quadrant_mismatches(plot_df)


def _check_quadrant_mismatches(df: pd.DataFrame) -> None:
    """Check if market_tag matches computed quadrant."""
    st.markdown("#### Quadrant Consistency Check")

    def compute_quadrant(row: pd.Series) -> str:
        x = row.get("expected_trend_pct", 0)
        y = row.get("decision_value_pct", 0)
        if x >= 0 and y >= 0:
            return "Offensive Win"
        if x < 0 and y >= 0:
            return "Defensive Win"
        if x >= 0 and y < 0:
            return "Gap"
        return "Market Drag"

    df = df.copy()
    df["computed_quadrant"] = df.apply(compute_quadrant, axis=1)

    # Exclude rows explicitly marked as excluded
    excluded_mask = df.get("market_tag", pd.Series([""] * len(df))).str.contains("Excluded", na=False)
    check_df = df[~excluded_mask].copy()

    mismatch_mask = check_df.get("market_tag", "") != check_df["computed_quadrant"]
    mismatch_count = int(mismatch_mask.sum()) if hasattr(mismatch_mask, "sum") else 0

    if mismatch_count == 0:
        st.success("All market_tag values match computed quadrants")
        return

    st.warning(f"{mismatch_count} rows have mismatched quadrants")

    mismatch_df = check_df[mismatch_mask][
        ["target_text", "action_type", "market_tag", "computed_quadrant", "before_clicks"]
    ].head(20)
    st.dataframe(mismatch_df, use_container_width=True, hide_index=True)

    st.markdown("**Likely Causes:**")
    low_sample = (check_df[mismatch_mask]["before_clicks"] < 5).sum() if "before_clicks" in check_df.columns else 0
    harvest = (
        (check_df[mismatch_mask]["action_type"].str.upper() == "HARVEST").sum()
        if "action_type" in check_df.columns
        else 0
    )
    st.write(f"- Harvest actions: {int(harvest)}")


def _render_confidence_tier_view(df: pd.DataFrame) -> None:
    """Visualize confidence tier distribution and logic (v3.0)."""
    st.markdown("### Confidence Tier Analysis")
    st.caption("Distribution of Gold, Silver, and Excluded tiers based on data quality (Postgres Calculated)")

    if "confidence_tier" not in df.columns:
        st.error("⚠️ `confidence_tier` column missing. Ensure PostgresManager is updated.")
        return

    # --- SIMULATE LEGACY V2 IMPACT FOR COMPARISON ---
    # V2 Logic: Linear confidence weight (clicks/15) with no floors or concept of tiers
    df["v2_weight"] = (df["before_clicks"] / 15.0).clip(upper=1.0)
    # V2 kept even <3 click items (just with small weight)
    df["v2_impact"] = df["decision_impact"] * df["v2_weight"]

    v2_total = df["v2_impact"].sum()
    v3_total = df["final_decision_impact"].sum()
    diff = v3_total - v2_total
    
    # Excluded count (V3 excluded items that had non-zero weight in V2)
    # Typically <3 click items
    v2_active_count = len(df[df["decision_impact"] != 0])
    v3_active_count = len(df[df["confidence_tier"].isin(["gold", "silver"])])
    count_dropped = v2_active_count - v3_active_count

    st.markdown("### 🆚 V2 (Legacy) vs V3 (New)")
    st.info(f"""
    **Why did we do this?** 
    V3 eliminates unstable "noise" (<3 clicks) that V2 was counting, while boosting verified signals ("Silver Lift").
    
    **Net Change:**  
    Impact: **${diff:,.0f}** ({diff/v2_total*100:+.1f}%) 
    Items Removed (Noise): **{count_dropped}** items filtered out.
    """)
    
    col_v2, col_v3 = st.columns(2)
    col_v2.metric("Legacy V2 Impact", f"${v2_total:,.0f}", help="Raw linear weighting (Clicks/15)")
    col_v3.metric("New V3 Impact", f"${v3_total:,.0f}", f"{diff:,.0f}", help="Tiered + Floored + Validated")
    
    st.divider()

    # 1. Measured Impact (Gold + Silver)
    st.markdown("### 🎯 Measured Impact (Strict Match)")
    st.caption("Only actions with high-confidence data (Gold/Silver) are measured. All else is excluded.")
    
    # Filter for Gold/Silver AND exclude Market Drag
    measured_df = df[
        (df["confidence_tier"].isin(["gold", "silver"])) &
        (df["market_tag"] != "Market Drag")
    ]
    
    # Excluded items
    excluded_df = df[
        (df["confidence_tier"] == "excluded") |
        (df["market_tag"] == "Market Drag")
    ]
    
    total_impact = measured_df["final_decision_impact"].sum()
    validated_impact = measured_df[measured_df["confidence_tier"] == "gold"]["final_decision_impact"].sum()
    measured_count = len(measured_df)
    total_count = len(df)
    coverage_pct = (measured_count / total_count * 100) if total_count > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Net Impact (Measured)", f"${total_impact:,.0f}", help="Sum of Gold + Silver Impact (Market Drag excluded)")
    col2.metric("Measured Actions", f"{measured_count} / {total_count}", f"{coverage_pct:.1f}% Coverage")
    col3.metric("Excluded Actions", len(excluded_df), "Insufficient Data / Drag")
    col4.metric("Validated (Gold)", f"${validated_impact:,.0f}", "Highest Confidence")

    st.divider()
    
    # 2. Exclusion Analysis
    st.markdown("#### 🚫 Exclusion Analysis")
    st.caption("Why were actions excluded?")
    
    import json
    exclusion_reasons = []
    
    # Parse flags for excluded rows
    for _, row in excluded_df.iterrows():
        try:
            flags = json.loads(row['tier_flags'])
            # Market Drag is a tag, not a flag, but we treat it as an exclusion reason here
            if row.get('market_tag') == 'Market Drag':
                exclusion_reasons.append('market_drag')
            elif flags:
                # The first flag is usually the primary reason (e.g. ['spend_discontinuity'])
                exclusion_reasons.append(flags[0])
            else:
                exclusion_reasons.append('unknown')
        except:
            exclusion_reasons.append('parse_error')
            
    reason_counts = pd.Series(exclusion_reasons).value_counts().reset_index()
    reason_counts.columns = ["Reason", "Count"]
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.dataframe(reason_counts, use_container_width=True, hide_index=True)
        
    with col2:
        with st.expander("Inspect Excluded Rows"):
            st.dataframe(
                excluded_df[[
                    'action_date', 'campaign_name', 'target_text', 
                    'confidence_tier', 'tier_flags', 'before_spend', 'observed_after_spend'
                ]].sort_values('before_spend', ascending=False),
                use_container_width=True
            )
            
    st.divider()

    # 3. Tier Distribution Pie Chart
    tier_counts = df["confidence_tier"].value_counts().reset_index()
    tier_counts.columns = ["Tier", "Count"]
    
    # Custom color map
    color_map = {
        "gold": "#22c55e",      # Green
        "silver": "#f59e0b",    # Amber
        "bronze": "#ef4444",    # Red (should be 0)
        "excluded": "#6b7280"   # Gray
    }

    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("#### Tier Distribution")
        fig = px.pie(
            tier_counts,
            values="Count",
            names="Tier",
            color="Tier",
            color_discrete_map=color_map,
            hole=0.4
        )
        fig.update_traces(textinfo="percent+label")
        fig.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### Baseline Spend by Tier")
        # Ensure before_spend exists
        if "before_spend" in df.columns:
            spend_by_tier = df.groupby("confidence_tier")["before_spend"].sum().reset_index()
            total_spend = spend_by_tier["before_spend"].sum()
            spend_by_tier["% Spend"] = (spend_by_tier["before_spend"] / total_spend * 100).fillna(0)
            
            # Format comparison table
            summary_df = pd.merge(tier_counts, spend_by_tier, left_on="Tier", right_on="confidence_tier")
            summary_df = summary_df[["Tier", "Count", "before_spend", "% Spend"]]
            summary_df = summary_df.rename(columns={"before_spend": "Baseline Spend"})
            
            st.dataframe(
                summary_df.style.format({
                    "Baseline Spend": "${:,.0f}", 
                    "% Spend": "{:.1f}%"
                }), 
                use_container_width=True
            )
            
            headline_spend = summary_df[summary_df["Tier"].isin(["gold", "silver"])]["% Spend"].sum()
            st.info(f"💰 **Strict Match Coverage:** Gold + Silver account for **{headline_spend:.1f}%** of baseline spend.")
        else:
            st.warning("before_spend column missing")

    st.divider()

    # 4. JSON Flag Analysis

    st.markdown("#### Exclusion & Dampening Reasons")
    
    if "tier_flags" in df.columns:
        # Flatten flags
        all_flags = []
        for flags_json in df["tier_flags"].astype(str):
            try:
                flags = json.loads(flags_json)
                if isinstance(flags, list):
                    all_flags.extend(flags)
                else:
                    all_flags.append(str(flags))
            except json.JSONDecodeError:
                continue
        
        flag_counts = pd.Series(all_flags).value_counts().reset_index()
        flag_counts.columns = ["Flag Code", "Count"]
        
        # Add descriptions
        descriptions = {
            "clean": "Full weight (Gold)",
            "cst_match": "CST Match (90% weight)",
            "mid_sample": "Low Volume (3-15 clicks)",
            "no_baseline_sales": "No Prior Sales (0.5x)",
            "low_sample": "Too few clicks (<3) - Excluded",
            "campaign_fallback": "Campaign Level Match - Excluded",
            "no_baseline_gap": "No Baseline Spend (Gap) - Excluded",
            "new_target": "New Target Launch (0.6x)",
            "not_implemented": "Validation Not Implemented (Excluded)"
        }
        flag_counts["Description"] = flag_counts["Flag Code"].map(descriptions).fillna("Unknown")
        
        st.dataframe(flag_counts, use_container_width=True)
    else:
        st.warning("tier_flags column missing")

    # 3. Match Level Breakdown
    st.markdown("#### Match Quality")
    if "match_level" in df.columns:
        match_counts = df["match_level"].value_counts().reset_index()
        match_counts.columns = ["Match Level", "Count"]
        st.dataframe(match_counts, use_container_width=True)

    # 4. Calibration Check (Silver Weight)
    st.markdown("#### Silver Tier Weight Check")
    silver_df = df[df["confidence_tier"] == "silver"]
    if not silver_df.empty and "confidence_weight" in silver_df.columns:
        fig_hist = px.histogram(
            silver_df, 
            x="confidence_weight", 
            nbins=20,
            title="Distribution of Confidence Weights (Silver Tier)",
            labels={"confidence_weight": "Weight (0.25 - 0.84)"}
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    st.divider()

    # 5. ROW DETAIL INSPECTOR (Requested View)
    st.markdown("### 🔎 Row Detail Inspector")
    st.caption("Detailed view of all rows with their assigned tier, weight, and flags.")
    
    # Filter options
    filter_tier = st.multiselect(
        "Filter by Tier", 
        ["gold", "silver", "excluded"],
        default=["gold", "silver"]
    )
    
    detail_df = df.copy()
    if filter_tier:
        detail_df = detail_df[detail_df["confidence_tier"].isin(filter_tier)]
        
    # Select and rename columns for clarity
    show_cols = [
        "target_text", "match_level", "validation_status", "action_type", "market_tag",
        "before_start", "before_end", "after_start", "after_end",
        "before_clicks", "before_spend", "before_sales",
        "after_clicks", "observed_after_spend", "observed_after_sales",
        "expected_clicks", "expected_sales", "is_smoothed", "campaign_spc_median",
        "decision_impact", "confidence_weight", "final_decision_impact",
        "confidence_tier", "tier_flags"
    ]
    
    # Handle missing columns gracefully
    available_cols = [c for c in show_cols if c in detail_df.columns]
    
    st.dataframe(
        detail_df[available_cols].style.format({
            "decision_impact": "${:,.2f}",
            "final_decision_impact": "${:,.2f}",
            "before_spend": "${:,.2f}",
            "before_sales": "${:,.2f}",
            "observed_after_spend": "${:,.2f}",
            "observed_after_sales": "${:,.2f}",
            "expected_sales": "${:,.2f}",
            "expected_clicks": "{:.1f}",
            "campaign_spc_median": "${:,.2f}",
            "confidence_weight": "{:.3f}"
        }),
        use_container_width=True,
        height=500
    )


def _render_v33_debug(df: pd.DataFrame) -> None:
    """Render v3.3 Layered Counterfactual debug view."""
    st.markdown("### v3.3 Layered Counterfactual Debug")
    st.caption("Detailed breakdown of Market Shift, Scale Adjustment, and ROAS Waterfall.")
    
    # Check if we have v3.3 data
    required = ['impact_linear', 'impact_v33', 'market_shift', 'scale_factor']
    missing = [c for c in required if c not in df.columns]
    
    if missing:
        st.warning(f"v3.3 columns missing: {missing}. Ensure v33 Engine is active in postgres_manager.")
        return
        
    # -------------------------------------------------------------------------
    # 1. Headline Comparison (v3.2 Linear vs v3.3 Layered)
    # -------------------------------------------------------------------------
    
    # v3.2 Linear (using confidence weights)
    # Note: impact_linear and impact_v33 are unweighted in the DF, need to apply weights
    linear_total = (df['impact_linear'] * df['confidence_weight']).sum()
    
    # v3.3 Layered (using confidence weights, excluding Market Drag)
    # Market Drag exclusion is handled implicitly by confidence tiering (Excluded = 0 weight)
    # but let's be explicit like the debug script
    valid_mask = df['market_tag'] != 'Market Drag'
    v33_total = (df[valid_mask]['impact_v33'] * df[valid_mask]['confidence_weight']).sum()
    
    diff = v33_total - linear_total
    
    # Market Context
    account_shift = df['market_shift'].iloc[0] if not df.empty else 1.0
    scale_up_count = (df['click_ratio'] > 1.0).sum()
    scale_adj_count = (df['scale_factor'] < 1.0).sum()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("v3.2 Linear Impact", f"${linear_total:,.0f}", help="Original linear calculation (Sales - Clicks*SPC)")
    c2.metric("v3.3 Layered Impact", f"${v33_total:,.0f}", f"{diff:+,.0f}", help="Market + Scale adjusted impact")
    c3.metric("Market Shift (SPC)", f"{(account_shift-1)*100:+.1f}%", help="Account-wide efficiency drift")
    c4.metric("Scale Adjustments", f"{scale_adj_count}", f"{scale_adj_count/len(df)*100:.1f}% of rows", help="Rows penalized for diminishing returns")
    
    st.divider()
    
    # -------------------------------------------------------------------------
    # 2. ROAS Waterfall Visual
    # -------------------------------------------------------------------------
    st.markdown("#### ROAS Attribution Decomposition")
    st.caption("Decomposing the change in ROAS into external and internal factors.")
    
    # Calculate Waterfall components (re-implementing logic from spec)
    before_spend = df['before_spend'].sum()
    before_sales = df['before_sales'].sum()
    before_clicks = df['before_clicks'].sum()
    after_spend = df['observed_after_spend'].sum()
    after_sales = df['observed_after_sales'].sum()
    after_clicks = df['after_clicks'].sum()
    
    if before_spend > 0 and after_spend > 0:
        baseline_roas = before_sales / before_spend
        actual_roas = after_sales / after_spend
        total_change = actual_roas - baseline_roas
        
        # Components
        baseline_spc = before_sales / before_clicks if before_clicks else 0
        actual_spc = after_sales / after_clicks if after_clicks else 0
        market_spc_change = actual_spc / baseline_spc if baseline_spc > 0 else 1.0
        
        baseline_cpc = before_spend / before_clicks if before_clicks else 0
        actual_cpc = after_spend / after_clicks if after_clicks else 0
        cpc_change = actual_cpc / baseline_cpc if baseline_cpc > 0 else 1.0
        
        market_effect = baseline_roas * (market_spc_change - 1)
        cpc_effect = baseline_roas * market_spc_change * (1/cpc_change - 1) if cpc_change > 0 else 0
        
        # Decision impact -> ROAS
        # Use v33 impact for this calculation
        decision_effect = v33_total / after_spend
        
        residual = actual_roas - (baseline_roas + market_effect + cpc_effect + decision_effect)
        
        # Chart
        waterfall_data = [
            dict(Measure="Baseline ROAS", Value=baseline_roas, Type="total", Text=f"{baseline_roas:.2f}x"),
            dict(Measure="Market Forces", Value=market_effect, Type="relative", Text=f"{market_effect:+.2f}x"),
            dict(Measure="CPC Efficiency", Value=cpc_effect, Type="relative", Text=f"{cpc_effect:+.2f}x"),
            dict(Measure="Decision Impact", Value=decision_effect, Type="relative", Text=f"{decision_effect:+.2f}x"),
            dict(Measure="Residual", Value=residual, Type="relative", Text=f"{residual:+.2f}x"),
            dict(Measure="Actual ROAS", Value=actual_roas, Type="total", Text=f"{actual_roas:.2f}x")
        ]
        
        import plotly.graph_objects as go
        
        fig = go.Figure(go.Waterfall(
            name = "ROAS Decomposition",
            orientation = "v",
            measure = [d['Type'] for d in waterfall_data],
            x = [d['Measure'] for d in waterfall_data],
            textposition = "outside",
            text = [d['Text'] for d in waterfall_data],
            y = [d['Value'] for d in waterfall_data],
            connector = {"line":{"color":"rgb(63, 63, 63)"}},
        ))
        
        fig.update_layout(
            title="ROAS Walk (Start to End)",
            showlegend = False,
            height=400,
            template="plotly_dark",
            yaxis_title="ROAS",
            xaxis_title="Attribute"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Insight Text
        external_pct = (market_effect + cpc_effect) / total_change * 100 if total_change != 0 else 0
        decision_pct = decision_effect / total_change * 100 if total_change != 0 else 0
        
        st.info(f"""
        **Insight:** 
        ROAS moved from {baseline_roas:.2f}x to {actual_roas:.2f}x.
        External factors (Market + CPC) drove **{external_pct:.0f}%** of this change.
        Your Decisions drove **{decision_pct:.0f}%**.
        """)

    # -------------------------------------------------------------------------
    # 3. Top Deviations Table
    # -------------------------------------------------------------------------
    st.markdown("#### Top Impact Adjustments")
    st.caption("Rows where v3.3 differs most from Linear (showing top 10 penalties reduced)")
    
    # Calculate difference
    # Only if rows exist
    if not df.empty:
        df['diff_v33'] = df['impact_v33'] - df['impact_linear']
        
        # Best improvements (largest positive diff) - meaning penalty calculation was reduced
        top_diffs = df.nlargest(10, 'diff_v33')[
            ['target_text', 'before_spend', 'before_sales', 'click_ratio', 'impact_linear', 'impact_v33', 'diff_v33', 'scale_factor']
        ]
        
        st.dataframe(
            top_diffs.style.format({
                'before_spend': '${:,.2f}',
                'before_sales': '${:,.2f}',
                'click_ratio': '{:,.2f}x',
                'impact_linear': '${:,.2f}',
                'impact_v33': '${:,.2f}',
                'diff_v33': '+${:,.2f}',
                'scale_factor': '{:.3f}'
            }),
            use_container_width=True
        )

