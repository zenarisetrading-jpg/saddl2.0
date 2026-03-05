"""
ROAS Waterfall Component - Attribution decomposition per PRD Section 4.11

This component decomposes ROAS change into:
1. Baseline ROAS (starting point)
2. Market Forces (account-level SPC change)
3. CPC Efficiency (cost per click change)
4. Decision Impact (v3.3 impact from optimization decisions)
5. Residual (unexplained model error)
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, Any
import plotly.graph_objects as go


def calculate_roas_waterfall(df: pd.DataFrame, decision_impact_dollars: float) -> Dict[str, Any]:
    """
    Calculate ROAS waterfall decomposition per Impact Model v3.3 spec Section 3.2.

    Args:
        df: DataFrame with before/after metrics including:
            - before_spend, before_sales, before_clicks
            - observed_after_spend, observed_after_sales, after_clicks
        decision_impact_dollars: Net decision impact from v3.3 (from ImpactMetrics)

    Returns:
        dict with waterfall components:
            - baseline_roas: Starting ROAS
            - actual_roas: Ending ROAS
            - total_change: actual_roas - baseline_roas
            - market_effect: ROAS change from SPC shift
            - cpc_effect: ROAS change from CPC shift
            - decision_effect: ROAS contribution from decisions
            - residual: Unexplained variance
            - Plus underlying metrics and percentages
    """
    # =========================================================
    # TOTALS
    # =========================================================
    before_spend = df['before_spend'].sum()
    before_sales = df['before_sales'].sum()
    before_clicks = df['before_clicks'].sum()

    after_spend = df['observed_after_spend'].sum()
    after_sales = df['observed_after_sales'].sum()
    after_clicks = df['after_clicks'].sum()

    # =========================================================
    # ROAS CALCULATIONS
    # =========================================================
    baseline_roas = before_sales / before_spend if before_spend > 0 else 0
    actual_roas = after_sales / after_spend if after_spend > 0 else 0

    # =========================================================
    # MARKET FORCES (SPC change)
    # =========================================================
    # SPC = Sales Per Click
    baseline_spc = before_sales / before_clicks if before_clicks > 0 else 0
    actual_spc = after_sales / after_clicks if after_clicks > 0 else 0

    market_spc_change = actual_spc / baseline_spc if baseline_spc > 0 else 1.0

    # Market effect on ROAS (holding CPC constant)
    # If SPC dropped 12%, ROAS drops proportionally
    market_effect_roas = baseline_roas * (market_spc_change - 1)

    # =========================================================
    # CPC EFFICIENCY
    # =========================================================
    # CPC = Cost Per Click
    baseline_cpc = before_spend / before_clicks if before_clicks > 0 else 0
    actual_cpc = after_spend / after_clicks if after_clicks > 0 else 0

    cpc_change = actual_cpc / baseline_cpc if baseline_cpc > 0 else 1.0

    # CPC effect on ROAS (inverse relationship - higher CPC = lower ROAS)
    # Applied after market adjustment
    cpc_effect_roas = baseline_roas * market_spc_change * (1/cpc_change - 1) if cpc_change > 0 else 0

    # =========================================================
    # DECISION IMPACT
    # =========================================================
    # Convert dollar impact to ROAS contribution
    decision_effect_roas = decision_impact_dollars / after_spend if after_spend > 0 else 0

    # =========================================================
    # RESIDUAL
    # =========================================================
    explained_roas = baseline_roas + market_effect_roas + cpc_effect_roas + decision_effect_roas
    residual_roas = actual_roas - explained_roas

    # =========================================================
    # PERCENTAGE ATTRIBUTION
    # =========================================================
    total_change = actual_roas - baseline_roas

    def safe_pct(component, total):
        if total == 0:
            return 0
        return (component / total) * 100

    return {
        # Raw values
        'baseline_roas': baseline_roas,
        'actual_roas': actual_roas,
        'total_change': total_change,

        # Components (ROAS units)
        'market_effect': market_effect_roas,
        'cpc_effect': cpc_effect_roas,
        'decision_effect': decision_effect_roas,
        'residual': residual_roas,

        # Underlying metrics
        'baseline_spc': baseline_spc,
        'actual_spc': actual_spc,
        'spc_change_pct': (market_spc_change - 1) * 100,

        'baseline_cpc': baseline_cpc,
        'actual_cpc': actual_cpc,
        'cpc_change_pct': (cpc_change - 1) * 100,

        # Attribution percentages
        'market_pct_of_change': safe_pct(market_effect_roas, total_change),
        'cpc_pct_of_change': safe_pct(cpc_effect_roas, total_change),
        'decision_pct_of_change': safe_pct(decision_effect_roas, total_change),
        'residual_pct_of_change': safe_pct(residual_roas, total_change),

        # External vs Internal
        'external_effect': market_effect_roas + cpc_effect_roas,
        'external_pct': safe_pct(market_effect_roas + cpc_effect_roas, total_change),
        'internal_effect': decision_effect_roas,
        'internal_pct': safe_pct(decision_effect_roas, total_change),

        # For display
        'decision_impact_dollars': decision_impact_dollars,
        'before_spend': before_spend,
        'after_spend': after_spend,
        'before_sales': before_sales,
        'after_sales': after_sales,
    }


def render_roas_waterfall(
    df: pd.DataFrame,
    decision_impact_dollars: float,
    currency: str = "$"
):
    """
    Render ROAS Attribution Waterfall visualization.

    Displays how ROAS changed from baseline to actual, broken down by:
    - Market forces (external)
    - CPC efficiency (external)
    - Optimization decisions (internal)
    - Residual (unexplained)

    Args:
        df: Impact DataFrame with before/after metrics
        decision_impact_dollars: Net decision impact from ImpactMetrics
        currency: Currency symbol for display
    """
    if df.empty:
        st.info("No data available for ROAS waterfall")
        return

    # Calculate waterfall components
    wf = calculate_roas_waterfall(df, decision_impact_dollars)

    # Skip rendering if ROAS is invalid
    if wf['baseline_roas'] == 0 and wf['actual_roas'] == 0:
        st.info("Insufficient data for ROAS waterfall (zero spend)")
        return

    # Theme detection
    theme_mode = st.session_state.get('theme_mode', 'dark')
    bg_color = 'rgba(15, 23, 42, 0.6)' if theme_mode == 'dark' else 'rgba(248, 250, 252, 0.9)'
    border_color = 'rgba(255, 255, 255, 0.08)' if theme_mode == 'dark' else 'rgba(0, 0, 0, 0.08)'
    text_color = '#F8FAFC' if theme_mode == 'dark' else '#1E293B'
    subtitle_color = '#94A3B8' if theme_mode == 'dark' else '#64748B'

    # SVG icons
    chart_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>'

    # Build waterfall chart with Plotly
    categories = ['Baseline', 'Market Forces', 'CPC Efficiency', 'Decisions', 'Residual', 'Actual']

    # Values for waterfall: [baseline, market_delta, cpc_delta, decision_delta, residual_delta, actual]
    # Plotly waterfall uses measure types: 'absolute', 'relative', 'relative', ..., 'total'
    values = [
        wf['baseline_roas'],
        wf['market_effect'],
        wf['cpc_effect'],
        wf['decision_effect'],
        wf['residual'],
        wf['actual_roas']
    ]

    measures = ['absolute', 'relative', 'relative', 'relative', 'relative', 'total']

    # Color coding: negative = red, positive = green, neutral = gray
    colors = [
        '#3B82F6',  # Baseline - blue
        '#EF4444' if wf['market_effect'] < 0 else '#10B981',  # Market
        '#EF4444' if wf['cpc_effect'] < 0 else '#10B981',     # CPC
        '#EF4444' if wf['decision_effect'] < 0 else '#10B981', # Decisions
        '#64748B',  # Residual - gray
        '#3B82F6'   # Actual - blue
    ]

    # Create waterfall chart
    fig = go.Figure(go.Waterfall(
        name="ROAS",
        orientation="v",
        measure=measures,
        x=categories,
        y=values,
        text=[f"{v:+.2f}x" if m == 'relative' else f"{v:.2f}x" for v, m in zip(values, measures)],
        textposition="outside",
        connector={"line": {"color": "rgba(148, 163, 184, 0.3)", "width": 1}},
        decreasing={"marker": {"color": "#EF4444"}},
        increasing={"marker": {"color": "#10B981"}},
        totals={"marker": {"color": "#3B82F6"}},
    ))

    # Update layout for dark theme
    fig.update_layout(
        title=None,
        showlegend=False,
        height=400,
        margin=dict(l=20, r=20, t=20, b=20),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(
            color=text_color,
            size=12,
            family="Inter, sans-serif"
        ),
        xaxis=dict(
            showgrid=False,
            showline=False,
            zeroline=False,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(148, 163, 184, 0.1)',
            showline=False,
            zeroline=True,
            zerolinecolor='rgba(148, 163, 184, 0.3)',
            title="ROAS (Sales / Spend)"
        ),
    )

    # Format helper for percentages
    def fmt_pct(val):
        if abs(val) < 0.1:
            return ""
        sign = "+" if val > 0 else ""
        return f"{sign}{val:.0f}%"

    # Render container
    st.markdown(f"""
    <div style="background: {bg_color}; border: 1px solid {border_color}; border-radius: 12px; padding: 20px; margin-top: 24px;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;">
            <span style="color: {text_color};">{chart_icon}</span>
            <span style="font-size: 1.1rem; font-weight: 600; color: {text_color};">ROAS Attribution Waterfall</span>
            <span style="margin-left: auto; font-size: 0.85rem; color: {subtitle_color};">
                {wf['baseline_roas']:.2f}x → {wf['actual_roas']:.2f}x ({wf['total_change']:+.2f}x)
            </span>
        </div>
        <div style="font-size: 0.9rem; color: {subtitle_color}; margin-bottom: 16px;">
            Breaking down ROAS change into market forces, CPC efficiency, and optimization decisions
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Render chart
    st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})

    # Summary metrics below chart
    ext_sign = "+" if wf['external_effect'] >= 0 else ""
    int_sign = "+" if wf['internal_effect'] >= 0 else ""
    ext_color = '#10B981' if wf['external_effect'] >= 0 else '#EF4444'
    int_color = '#10B981' if wf['internal_effect'] >= 0 else '#EF4444'

    st.markdown(f"""
    <div style="background: {bg_color}; border: 1px solid {border_color}; border-radius: 12px; padding: 16px; margin-top: 16px;">
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; color: {text_color};">
            <div>
                <div style="font-size: 0.85rem; color: {subtitle_color}; margin-bottom: 4px;">Market Forces (SPC)</div>
                <div style="font-size: 1.3rem; font-weight: 700; color: {'#EF4444' if wf['market_effect'] < 0 else '#10B981'};">
                    {wf['market_effect']:+.2f}x
                </div>
                <div style="font-size: 0.8rem; color: {subtitle_color};">
                    SPC {wf['spc_change_pct']:+.1f}% • {fmt_pct(wf['market_pct_of_change'])} of change
                </div>
            </div>
            <div>
                <div style="font-size: 0.85rem; color: {subtitle_color}; margin-bottom: 4px;">CPC Efficiency</div>
                <div style="font-size: 1.3rem; font-weight: 700; color: {'#EF4444' if wf['cpc_effect'] < 0 else '#10B981'};">
                    {wf['cpc_effect']:+.2f}x
                </div>
                <div style="font-size: 0.8rem; color: {subtitle_color};">
                    CPC {wf['cpc_change_pct']:+.1f}% • {fmt_pct(wf['cpc_pct_of_change'])} of change
                </div>
            </div>
            <div>
                <div style="font-size: 0.85rem; color: {subtitle_color}; margin-bottom: 4px;">Optimization Decisions</div>
                <div style="font-size: 1.3rem; font-weight: 700; color: {'#EF4444' if wf['decision_effect'] < 0 else '#10B981'};">
                    {wf['decision_effect']:+.2f}x
                </div>
                <div style="font-size: 0.8rem; color: {subtitle_color};">
                    {currency}{wf['decision_impact_dollars']:,.0f} • {fmt_pct(wf['decision_pct_of_change'])} of change
                </div>
            </div>
        </div>
        <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid {border_color};">
            <div style="display: flex; justify-content: space-between; font-size: 0.9rem;">
                <span style="color: {subtitle_color};">
                    External Forces (Market + CPC): <span style="color: {ext_color}; font-weight: 600;">{ext_sign}{wf['external_effect']:.2f}x</span> ({fmt_pct(wf['external_pct'])})
                </span>
                <span style="color: {subtitle_color};">
                    Internal (Decisions): <span style="color: {int_color}; font-weight: 600;">{int_sign}{wf['internal_effect']:.2f}x</span> ({fmt_pct(wf['internal_pct'])})
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Interpretation helper
    if abs(wf['total_change']) > 0.1:
        primary_driver = max(
            [('Market Forces', abs(wf['market_effect'])),
             ('CPC Efficiency', abs(wf['cpc_effect'])),
             ('Decisions', abs(wf['decision_effect']))],
            key=lambda x: x[1]
        )

        st.markdown(f"""
        <div style="background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 8px; padding: 12px; margin-top: 12px;">
            <span style="color: {text_color}; font-size: 0.9rem;">
                💡 <strong>Primary driver:</strong> {primary_driver[0]} contributed {primary_driver[1]:.2f}x ({abs(primary_driver[1] / wf['total_change'] * 100) if wf['total_change'] != 0 else 0:.0f}%) to the ROAS change.
            </span>
        </div>
        """, unsafe_allow_html=True)
