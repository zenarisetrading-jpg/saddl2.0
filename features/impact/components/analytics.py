"""
Analytics Layout Component - Main analytics section orchestrator.
MATCHES legacy impact_dashboard.py _render_new_impact_analytics structure.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import Dict, Any, Optional

from features.impact.components.cards import (
    render_what_worked_card,
    render_what_didnt_card,
    render_decision_score_card,
)
from features.impact.components.tables import render_details_table
from features.impact.components.timeline import render_timeline_card
from features.impact.charts.waterfall import render_roas_attribution_bar
from features.impact.charts.matrix import render_decision_outcome_matrix
from app_core.timeline_roas import get_account_timeline_roas
# Note: render_cumulative_impact_chart available but not used in legacy analytics layout


def _render_recent_wins_list(impact_df: pd.DataFrame, currency: str):
    """
    Render scrollable list of top 5 recent winning decisions with premium cards.
    EXACT copy from legacy impact_dashboard.py lines 3783-3871.
    """
    # 1. Header
    st.markdown("""
<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 20px;">
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"></path><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"></path><path d="M4 22h16"></path><path d="M10 14.66V17"></path><path d="M14 14.66V17"></path><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"></path></svg>
    <span style="font-weight: 700; font-size: 1rem; color: #F8FAFC;">RECENT WINNING DECISIONS</span>
</div>
""", unsafe_allow_html=True)
    
    if impact_df.empty:
        st.info("No recent wins found.")
        return

    # 2. Determine which impact column to use (v3.3+ compatibility)
    if 'final_impact_v33' in impact_df.columns:
        impact_col = 'final_impact_v33'
    elif 'final_decision_impact' in impact_df.columns:
        impact_col = 'final_decision_impact'
    else:
        impact_col = 'decision_impact'

    # Filter & Sort Data
    wins_df = impact_df[
        (impact_df[impact_col] > 0) &
        (impact_df['validation_status'].astype(str).str.contains('✓|Confirmed|Validated|Directional|Strict', na=False))
    ].copy()

    if wins_df.empty:
        st.caption("No validated wins in this period yet.")
        return

    # Sort by date descending
    if 'action_date' in wins_df.columns:
        wins_df['action_date'] = pd.to_datetime(wins_df['action_date'])
        wins_df = wins_df.sort_values(by='action_date', ascending=False)

    # Take top 5
    top_wins = wins_df.head(5)

    # 3. Render Cards
    for idx, row in top_wins.iterrows():
        action_desc = row.get('target_text', 'Unknown Action')
        if len(action_desc) > 35:
            action_desc = action_desc[:32] + "..."

        # Use v3.3+ impact column if available
        impact_val = row.get(impact_col, 0)
        formatted_impact = f"{currency}{impact_val:,.0f}" if currency else f"${impact_val:,.0f}"
        
        action_date = row.get('action_date')
        date_str = action_date.strftime('%b %d') if pd.notnull(action_date) else ""
        action_type = str(row.get('action_type', '')).replace('_', ' ').title()
        
        # Determine icon based on type
        if 'Bid' in action_type:
            type_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>'
        elif 'Negative' in action_type:
            type_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg>'
        else:
            type_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"></path><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"></path><path d="M4 22h16"></path></svg>'

        st.markdown(
            f'<div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(148, 163, 184, 0.1); border-left: 3px solid #10B981; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">'
            f'<div style="flex: 1;">'
            f'<div style="color: #E2E8F0; font-weight: 600; font-size: 0.95rem; margin-bottom: 4px;">{action_desc}</div>'
            f'<div style="display: flex; align-items: center; gap: 6px; color: #94A3B8; font-size: 0.8rem;">{type_icon} {date_str} &bull; {action_type}</div>'
            f'</div>'
            f'<div style="text-align: right;">'
            f'<div style="color: #10B981; font-weight: 700; font-size: 1.1rem; margin-bottom: 2px;">+{formatted_impact}</div>'
            f'<div style="color: #64748B; font-size: 0.75rem;">(14-day measured)</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_measurement_confidence(validation_df: pd.DataFrame):
    """
    Render Measurement Confidence gauge section.
    COPIED from legacy impact_dashboard.py lines 2484-2573.
    """
    # Calculate Trust Metrics
    if not validation_df.empty:
        v_df = validation_df
        measured_count = len(v_df[v_df['validation_status'].astype(str).str.contains('✓|Confirmed|Validated|Directional', na=False)])
        pending_count = len(v_df[v_df['maturity_status'] == 'Immature']) + len(v_df[v_df['maturity_status'] == 'Dormant'])
        total_count = len(v_df)
        early_count = total_count - measured_count - pending_count
        
        pct_measured = (measured_count / total_count * 100) if total_count > 0 else 0
    else:
        measured_count = 0
        pending_count = 0
        early_count = 0
        total_count = 0
        pct_measured = 0
    
    # 1. Header
    st.markdown("""
<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;">
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
    <span style="font-weight: 700; font-size: 1rem; color: #F8FAFC;">Measurement Confidence</span>
</div>
""", unsafe_allow_html=True)

    # 2. Gauge (Plotly)
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = pct_measured,
        number = {'font': {'size': 36, 'color': '#10B981', 'family': 'Inter, sans-serif'}, 'suffix': '%'},
        domain = {'x': [0, 1], 'y': [0, 1]},
        gauge = {
            'axis': {'range': [0, 100], 'tickwidth': 0, 'tickcolor': "rgba(0,0,0,0)", 'visible': False},
            'bar': {'color': "#10B981", 'thickness': 1.0},
            'bgcolor': "rgba(255,255,255,0.1)",
            'borderwidth': 0,
            'steps': []
        }
    ))
    
    fig.update_layout(
        height=160,
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        font={'family': "Inter, sans-serif"}
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    st.markdown(f"""
<div style="text-align: center; margin-top: -30px; margin-bottom: 24px;"><div style="color: #94A3B8; font-size: 0.85rem; font-weight: 500;">Measurement Coverage</div></div>
<div style="display: flex; flex-direction: column; gap: 12px; padding: 0 12px;">
    <div style="display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center; gap: 8px; color: #E2E8F0; font-size: 0.9rem;">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#E2E8F0" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
            Total Decisions
        </div>
        <span style="font-weight: 600; color: #E2E8F0;">{total_count}</span>
    </div>
    <div style="display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center; gap: 8px; color: #E2E8F0; font-size: 0.9rem;">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
            Next decision proven
        </div>
        <span style="font-weight: 600; color: #10B981;">{measured_count}</span>
    </div>
    <div style="display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center; gap: 8px; color: #64748B; font-size: 0.9rem;">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
            Pending decisions (too early)
        </div>
        <span style="font-weight: 600; color: #64748B;">{early_count + pending_count}</span>
    </div>
</div>
<div style="margin-top: 24px; padding: 12px; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 8px; display: flex; align-items: center; gap: 12px;">
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><path d="m9 12 2 2 4-4"></path></svg>
    <div>
        <div style="color: #10B981; font-weight: 700; font-size: 0.9rem;">High Confidence</div>
        <div style="color: #6EE7B7; font-size: 0.75rem;">Statistically significant results</div>
    </div>
</div>
""", unsafe_allow_html=True)


def render_impact_analytics(
    summary: Dict[str, Any],
    impact_df: pd.DataFrame,
    validated_only: bool = True,
    mature_count: int = 0,
    pending_count: int = 0,
    raw_impact_df: pd.DataFrame = None,
    canonical_metrics: Optional[Any] = None
):
    """
    Render the main impact analytics section.
    MATCHES legacy _render_new_impact_analytics layout EXACTLY:

    - Row 1: Timeline (v3.5)
    - Row 2: What Worked | What Didn't | Decision Score
    - Row 3: ROAS Attribution | Decision Outcome Map
    - Row 4: Measurement Confidence | Recent Winning Decisions
    - Row 5: Details Table (collapsed)
    """
    from utils.formatters import get_account_currency
    currency = get_account_currency()

    # Validated DF for charts
    validation_df = raw_impact_df if raw_impact_df is not None else impact_df

    # ==========================================
    # SECTION 1: TIMELINE CARD (HIDDEN)
    # ==========================================
    # Timeline card intentionally hidden per dashboard requirements.
    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    # ==========================================
    # SECTION 2: BREAKDOWN ROW (What Worked | What Didn't | Decision Score)
    # ==========================================
    c1, c2, c3 = st.columns(3, gap="medium")
    
    with c1:
        render_what_worked_card(currency)
    
    with c2:
        render_what_didnt_card(currency)
    
    with c3:
        render_decision_score_card()
    
    st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)

    # ==========================================
    # SECTION 3 & 4: ROAS ATTRIBUTION | DECISION MAP
    # ==========================================
    chart_c1, chart_c2 = st.columns(2, gap="medium")

    with chart_c1:
        # CRITICAL FIX: Calculate spend-filtered impact for ROAS waterfall
        # The waterfall should only include actions that affected ROAS (spend > 0)
        # NOT the full canonical_metrics which includes zero-spend actions

        # Use the impact_df that's passed in (already filtered to active_df with spend)
        # Calculate the decision impact directly from this filtered dataset
        if not impact_df.empty:
            # Determine which column to use
            has_v33 = 'final_impact_v33' in impact_df.columns
            has_v32 = 'final_decision_impact' in impact_df.columns

            if has_v33:
                impact_col = 'final_impact_v33'
            elif has_v32:
                impact_col = 'final_decision_impact'
            else:
                impact_col = 'decision_impact'

            # Debug: Show what we're using
            # st.caption(f"🔍 Column check: v3.3={has_v33}, v3.2={has_v32}, using: {impact_col}")
            # st.caption(f"🔍 Total rows in impact_df: {len(impact_df)}")

            # Exclude Market Drag from attribution
            if 'market_tag' in impact_df.columns:
                has_drag = (impact_df['market_tag'] == 'Market Drag').sum()
                non_drag = impact_df[impact_df['market_tag'] != 'Market Drag']
                spend_filtered_impact = non_drag[impact_col].sum()
                # st.caption(f"🔍 Market Drag actions excluded: {has_drag}")
                # st.caption(f"🔍 Non-drag rows: {len(non_drag)}, Impact: ${spend_filtered_impact:,.2f}")
            else:
                spend_filtered_impact = impact_df[impact_col].sum()
                # st.caption(f"🔍 No market_tag column, using all rows")

            # Show column sums for debugging
            # if has_v33:
            #     v33_sum = impact_df['final_impact_v33'].sum()
            #     st.caption(f"🔍 final_impact_v33 sum (all rows): ${v33_sum:,.2f}")
            # if has_v32:
            #     v32_sum = impact_df['final_decision_impact'].sum()
            #     st.caption(f"🔍 final_decision_impact sum (all rows): ${v32_sum:,.2f}")
        else:
            spend_filtered_impact = 0.0

        # Pass the spend-filtered impact to waterfall (v3.4 - action-level aggregation)
        # NOTE: We do NOT pass timeline here - it's only for display context
        render_roas_attribution_bar(summary, impact_df, currency,
                                   decision_impact_override=spend_filtered_impact,
                                   timeline=None)  # Use v3.4 action-level aggregation
        
    with chart_c2:
        render_decision_outcome_matrix(impact_df, summary)

    st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)

    # ==========================================
    # SECTION 5 & 6: MEASUREMENT CONFIDENCE | RECENT WINS
    # ==========================================
    with st.container(border=True):
        trust_c1, wins_c2 = st.columns([3, 7], gap="medium")
        
        with trust_c1:
            _render_measurement_confidence(validation_df)
    
        with wins_c2:
            _render_recent_wins_list(impact_df, currency)

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    # ==========================================
    # SECTION 7: COLLAPSED DETAILS TABLE
    # ==========================================
    with st.container(border=True):
        render_details_table(impact_df, currency)
