"""
Card Components - Metric cards for the impact dashboard.
EXACT COPY from legacy impact_dashboard.py lines 1083-1222.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional


def render_what_worked_card(currency: str):
    """Section 2A: What Worked - Offensive + Defensive Wins. EXACT COPY from legacy."""
    metrics = st.session_state.get('_impact_metrics', {})
    total_wins = metrics.get('total_wins', 0)
    offensive_val = metrics.get('offensive_val', 0)
    defensive_val = metrics.get('defensive_val', 0)
    offensive_count = metrics.get('offensive_count', 0)
    defensive_count = metrics.get('defensive_count', 0)
    win_count = offensive_count + defensive_count
    
    # SVG icons
    rocket_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path></svg>'
    shield_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>'
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(15, 23, 42, 0.95) 100%); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 20px; height: 100%; box-shadow: 0 0 20px rgba(16, 185, 129, 0.1);">
        <div style="font-size: 0.75rem; font-weight: 700; color: #10B981; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px;">
            ✓ What Worked
        </div>
        <div style="font-size: 2rem; font-weight: 800; color: #10B981; margin-bottom: 8px; text-shadow: 0 0 20px rgba(16, 185, 129, 0.5);">
            +{currency}{total_wins:,.0f}
        </div>
        <div style="font-size: 0.9rem; color: #94a3b8; margin-bottom: 16px;">
            {win_count} decisions helped
        </div>
        <div style="border-top: 1px solid rgba(16, 185, 129, 0.2); padding-top: 12px; font-size: 0.8rem; color: #94A3B8; line-height: 1.6;">
            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
                {rocket_icon}
                <span>Offensive: +{currency}{offensive_val:,.0f} ({offensive_count})</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
                {shield_icon}
                <span>Defensive: +{currency}{defensive_val:,.0f} ({defensive_count})</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_what_didnt_card(currency: str):
    """Section 2B: What Didn't Work - Decision Gaps. EXACT COPY from legacy."""
    metrics = st.session_state.get('_impact_metrics', {})
    gap_val = metrics.get('gap_val', 0)
    gap_count = metrics.get('gap_count', 0)
    
    # Warning icon SVG
    warning_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(15, 23, 42, 0.95) 100%); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px; padding: 20px; height: 100%; box-shadow: 0 0 20px rgba(239, 68, 68, 0.1);">
        <div style="font-size: 0.75rem; font-weight: 700; color: #EF4444; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px;">
            ✗ What Didn't
        </div>
        <div style="font-size: 2rem; font-weight: 800; color: #EF4444; margin-bottom: 8px; text-shadow: 0 0 20px rgba(239, 68, 68, 0.5);">
            {currency}{gap_val:,.0f}
        </div>
        <div style="font-size: 0.9rem; color: #94a3b8; margin-bottom: 16px;">
            {gap_count} decisions hurt
        </div>
        <div style="border-top: 1px solid rgba(239, 68, 68, 0.2); padding-top: 12px; font-size: 0.8rem; color: #94A3B8; line-height: 1.6;">
            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
                {warning_icon}
                <span>Decision Gaps: Missed opportunities</span>
            </div>
            <div style="height: 16px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_decision_score_card():
    """Section 2C: Decision Score - Overall quality metric. EXACT COPY from legacy."""
    metrics = st.session_state.get('_impact_metrics', {})
    offensive_count = metrics.get('offensive_count', 0)
    defensive_count = metrics.get('defensive_count', 0)
    gap_count = metrics.get('gap_count', 0)
    
    win_count = offensive_count + defensive_count
    total_counted = win_count + gap_count
    
    if total_counted > 0:
        helped_pct = (win_count / total_counted) * 100
        hurt_pct = (gap_count / total_counted) * 100
        score = int(helped_pct - hurt_pct)
    else:
        helped_pct = 0
        hurt_pct = 0
        score = 0
    
    # Determine label and color
    if score >= 20:
        label = "Excellent"
        color = "#10B981"
    elif score >= 10:
        label = "Good"
        color = "#34D399"
    elif score >= 1:
        label = "Okay"
        color = "#6EE7B7"
    elif score == 0:
        label = "Neutral"
        color = "#9CA3AF"
    elif score >= -9:
        label = "Needs Work"
        color = "#FCA5A5"
    else:
        label = "Problem"
        color = "#EF4444"
    
    # Determine gradient colors based on score
    if score >= 10:
        card_bg = f"linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(15, 23, 42, 0.95) 100%)"
        card_border = "1px solid rgba(16, 185, 129, 0.25)"
        card_glow = f"0 0 20px rgba(16, 185, 129, 0.15)"
        text_glow = f"text-shadow: 0 0 15px rgba(16, 185, 129, 0.4);"
    elif score >= 0:
        card_bg = "linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%)"
        card_border = "1px solid rgba(148, 163, 184, 0.15)"
        card_glow = "0 4px 16px rgba(0, 0, 0, 0.3)"
        text_glow = ""
    else:
        card_bg = f"linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(15, 23, 42, 0.95) 100%)"
        card_border = "1px solid rgba(239, 68, 68, 0.25)"
        card_glow = f"0 0 20px rgba(239, 68, 68, 0.15)"
        text_glow = f"text-shadow: 0 0 15px rgba(239, 68, 68, 0.4);"
    
    st.markdown(f"""
    <div style="background: {card_bg}; border: {card_border}; border-radius: 12px; padding: 20px; height: 100%; text-align: center; box-shadow: {card_glow};">
        <div style="font-size: 0.75rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px;">Decision Score</div>
        <div style="font-size: 2.5rem; font-weight: 800; color: {color}; margin-bottom: 4px; {text_glow}">{score:+d}</div>
        <div style="font-size: 1rem; font-weight: 600; color: {color}; margin-bottom: 12px;">{label}</div>
        <div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 8px;">{helped_pct:.0f}% helped · {hurt_pct:.0f}% hurt</div>
        <div style="font-size: 0.7rem; color: #64748B; font-style: italic;">Score = % helped − % hurt</div>
    </div>
    """, unsafe_allow_html=True)


def render_data_confidence_section(impact_df: pd.DataFrame):
    """Render data confidence indicators."""
    if impact_df.empty:
        return

    total = len(impact_df)
    validated = impact_df.get('is_validated', pd.Series([True] * total)).sum()
    validation_rate = (validated / total * 100) if total > 0 else 0

    st.markdown(f"""
    <div style="background: rgba(148, 163, 184, 0.05); border-radius: 8px; padding: 12px;">
        <span style="color: #94a3b8; font-size: 0.85rem;">
            Data Confidence: <strong>{validation_rate:.0f}%</strong> validated ({validated}/{total} actions)
        </span>
    </div>
    """, unsafe_allow_html=True)


def render_value_breakdown_section(
    impact_df: pd.DataFrame,
    currency: str,
    canonical_metrics: Optional[Any] = None
):
    """Render value breakdown by category."""
    if canonical_metrics is None:
        st.info("Value breakdown unavailable")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Offensive Wins",
            f"{currency}{canonical_metrics.offensive_value:,.0f}",
            f"{canonical_metrics.offensive_actions} actions"
        )

    with col2:
        st.metric(
            "Defensive Wins",
            f"{currency}{canonical_metrics.defensive_value:,.0f}",
            f"{canonical_metrics.defensive_actions} actions"
        )

    with col3:
        st.metric(
            "Gaps",
            f"-{currency}{abs(canonical_metrics.gap_value):,.0f}",
            f"{canonical_metrics.gap_actions} actions",
            delta_color="inverse"
        )
