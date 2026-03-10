"""
Hero Banner Component - Main impact summary banner.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional

from features.impact.styles.css import get_hero_styles, BRAND_COLORS
from features.impact.data.transforms import validate_impact_columns


def render_hero_banner(
    impact_df: pd.DataFrame,
    currency: str,
    horizon_label: str = "30D",
    total_verified_impact: float = None,
    summary: Dict[str, Any] = None,
    mature_count: int = 0,
    pending_count: int = 0,
    canonical_metrics: Optional[Any] = None
):
    """
    Render the Hero Section: "Did your optimizations make money?"
    Human-centered design with YES/NO/BREAK EVEN prefix.

    Args:
        impact_df: DataFrame with impact data
        currency: Currency symbol
        horizon_label: Label for the time horizon (e.g., "14D", "30D")
        total_verified_impact: Override for total impact value
        summary: Summary dict from backend
        mature_count: Count of mature actions
        pending_count: Count of pending actions
        canonical_metrics: ImpactMetrics object (Phase 3+)
    """
    if summary is None:
        summary = {}

    if impact_df.empty:
        st.info("No data for hero calculation")
        return

    # Use canonical metrics if provided
    if canonical_metrics is None or not getattr(canonical_metrics, 'has_data', False):
        st.warning("Impact metrics unavailable")
        return

    attributed_impact = canonical_metrics.attributed_impact
    offensive_val = canonical_metrics.offensive_value
    defensive_val = canonical_metrics.defensive_value
    gap_val = canonical_metrics.gap_value
    drag_count = canonical_metrics.drag_actions
    total_wins = offensive_val + defensive_val

    # Counts for display
    offensive_count = canonical_metrics.offensive_actions
    defensive_count = canonical_metrics.defensive_actions
    gap_count = canonical_metrics.gap_actions

    # Store in session state for other sections
    st.session_state['_impact_metrics'] = {
        'attributed_impact': attributed_impact,
        'offensive_val': offensive_val,
        'defensive_val': defensive_val,
        'gap_val': gap_val,
        'total_wins': total_wins,
        'drag_count': drag_count,
        'offensive_count': offensive_count,
        'defensive_count': defensive_count,
        'gap_count': gap_count,
    }

    # Validate columns exist (v3.3)
    df = validate_impact_columns(impact_df)
    impact_col = 'final_decision_impact' if 'final_decision_impact' in df.columns else 'decision_impact'

    # Determine state
    abs_impact = abs(attributed_impact)
    before_sales = df['before_sales'].sum()
    threshold = before_sales * 0.02 if before_sales > 0 else 10

    if attributed_impact > threshold:
        answer_prefix = "YES"
        answer_color = BRAND_COLORS['green']
        subtitle = f"That's {currency}{abs_impact:,.0f} more than if you'd done nothing."
        state = 'positive'
    elif attributed_impact < -threshold:
        answer_prefix = "NOT YET"
        answer_color = BRAND_COLORS['red']
        subtitle = f"Your decisions cost {currency}{abs_impact:,.0f} compared to doing nothing."
        state = 'negative'
    else:
        answer_prefix = "BREAK EVEN"
        answer_color = BRAND_COLORS['gray']
        subtitle = f"Your decisions had minimal impact ({currency}{abs_impact:,.0f})."
        state = 'neutral'

    # Format impact display
    impact_sign = '+' if attributed_impact >= 0 else ''
    impact_display = f"{impact_sign}{currency}{attributed_impact:,.0f}"

    # Calculate incremental contribution percentage
    non_drag_mask = df['market_tag'] != 'Market Drag'
    total_before_sales = df.loc[non_drag_mask, 'before_sales'].sum()
    total_after_sales = df.loc[non_drag_mask, 'observed_after_sales'].sum()
    if not total_after_sales or total_after_sales < 100:
        incremental_pct = None
    else:
        incremental_pct = attributed_impact / total_after_sales * 100
    incremental_sign = '+' if (incremental_pct or 0) >= 0 else ''
    incremental_badge = f"{incremental_sign}{incremental_pct:.1f}% of revenue" if incremental_pct is not None and abs(incremental_pct) > 0.1 else ""

    # Progress bar calculation
    total_counted = offensive_count + defensive_count + gap_count
    win_count = offensive_count + defensive_count
    win_pct = (win_count / total_counted * 100) if total_counted > 0 else 0

    # Get styles
    theme_mode = st.session_state.get('theme_mode', 'dark')
    styles = get_hero_styles(state, theme_mode)

    # SVG Icons
    checkmark_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>'
    arrow_up_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>'

    # Build incremental badge HTML
    badge_html = ""
    if incremental_pct is not None and incremental_badge:
        badge_color = BRAND_COLORS['green'] if incremental_pct >= 0 else BRAND_COLORS['red']
        badge_html = f'<span style="display: inline-flex; align-items: center; gap: 4px; background: rgba(16, 185, 129, 0.15); color: {badge_color}; padding: 4px 12px; border-radius: 20px; font-size: 1rem; font-weight: 600; margin-left: 16px; vertical-align: middle;">{arrow_up_icon} {incremental_badge}</span>'

    # SVG icons for stats row
    trophy_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"></path><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"></path><path d="M4 22h16"></path><path d="M10 14.66V17"></path><path d="M14 14.66V17"></path><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"></path></svg>'
    gap_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'
    drag_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"></polyline><polyline points="17 18 23 18 23 12"></polyline></svg>'

    # Format dollar values for wins and gaps
    wins_value_str = f"+{currency}{total_wins:,.0f}" if total_wins >= 0 else f"{currency}{total_wins:,.0f}"
    gaps_value_str = f"{currency}{gap_val:,.0f}" if gap_val < 0 else f"+{currency}{gap_val:,.0f}"

    # Render hero banner
    st.markdown(f"""
    <div style="background: {styles['bg']}; border: {styles['border']}; border-radius: 16px; padding: 32px 40px; margin-bottom: 24px; box-shadow: {styles['glow']}; backdrop-filter: blur(10px);">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 24px;">
            <span style="color: {answer_color};">{checkmark_icon}</span>
            <span style="font-size: 1.1rem; font-weight: 600; color: #F8FAFC;">Did your optimizations make money?</span>
            <span style="margin-left: auto; font-size: 0.85rem; color: #94a3b8; opacity: 0.7;">({horizon_label}) <span title="Impact adjusted for market conditions and scale effects">v3.3</span></span>
        </div>
        <div style="font-size: 2.8rem; font-weight: 800; color: {answer_color}; margin-bottom: 8px; {styles['text_glow']}">{answer_prefix} — {impact_display}{badge_html}</div>
        <div style="background: rgba(255,255,255,0.08); border-radius: 8px; height: 12px; margin: 16px 0; overflow: hidden; border: 1px solid rgba(255,255,255,0.05);">
            <div style="background: linear-gradient(90deg, #10B981 0%, #059669 100%); height: 100%; width: {win_pct}%; border-radius: 8px;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; color: #94a3b8; font-size: 0.9rem;">
            <span style="display: inline-flex; align-items: center; gap: 4px;" title="Total value from winning actions">
                {trophy_icon} Wins: <span style="color: #10B981; font-weight: 600;">{wins_value_str}</span> <span style="opacity: 0.7;">({win_count})</span>
            </span>
            <span style="display: inline-flex; align-items: center; gap: 8px;">
                <span title="Actions where decisions underperformed expectations">{gap_icon} Gaps: <span style="color: #EF4444; font-weight: 600;">{gaps_value_str}</span> <span style="opacity: 0.7;">({gap_count})</span></span>
                <span style="margin-left: 8px; opacity: 0.7;" title="Actions excluded from impact calculation due to market conditions">| {drag_icon} Excluded: {drag_count}</span>
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

