"""
Timeline Display Component (v3.6 - Native Streamlit)
Shows the Baseline → Optimization → Final timeline for ROAS attribution
Uses native Streamlit components to avoid HTML rendering issues
"""

import streamlit as st
from typing import Dict, Any


def render_timeline_card(timeline: Dict[str, Any], currency: str = "$"):
    """
    Render timeline card using native Streamlit components (no HTML).

    Args:
        timeline: Timeline dict from get_account_timeline_roas()
        currency: Currency symbol
    """

    if not timeline or timeline.get('total_actions', 0) == 0:
        st.info("📅 No timeline data available yet")
        return

    # Determine status
    has_warnings = timeline.get('baseline_warning') or timeline.get('final_warning')
    status_emoji = '⚠️' if has_warnings else '✅'
    status_text = 'Partial Data' if has_warnings else 'Complete'

    # Use native Streamlit container
    with st.container(border=True):
        # Header
        col_title, col_status = st.columns([4, 1])
        with col_title:
            st.markdown("### 📅 Analysis Timeline")
        with col_status:
            st.markdown(f"**{status_emoji} {status_text}**")

        st.divider()

        # Three columns for the three periods
        col1, col2, col3 = st.columns(3)

        # Baseline Period
        with col1:
            st.markdown("**🔵 Baseline Period**")
            if timeline['baseline_start'] and timeline['baseline_end']:
                st.caption(f"{timeline['baseline_start'].strftime('%b %d')} - {timeline['baseline_end'].strftime('%b %d, %Y')}")
                st.caption(f"({timeline['baseline_days']} days)")

            st.metric(
                label="ROAS",
                value=f"{timeline['baseline_roas']:.2f}",
                delta=None
            )

            st.caption(f"{currency}{timeline['baseline_sales']:,.0f} sales")
            st.caption(f"{currency}{timeline['baseline_spend']:,.0f} spend")

            if timeline.get('baseline_warning'):
                st.warning(timeline['baseline_warning'], icon="⚠️")

        # Optimization Period
        with col2:
            st.markdown("**🔧 Optimization Period**")
            if timeline['optimization_start'] and timeline['optimization_end']:
                st.caption(f"{timeline['optimization_start'].strftime('%b %d')} - {timeline['optimization_end'].strftime('%b %d, %Y')}")
                st.caption(f"({timeline['optimization_period_days']} days)")

            st.metric(
                label="Actions Taken",
                value=f"{timeline['total_actions']}",
                delta=None
            )

            st.caption(f"{timeline['mature_actions']} mature")
            st.caption(f"{timeline['total_actions'] - timeline['mature_actions']} pending")

        # Final Period
        with col3:
            st.markdown("**🎯 Final Period**")
            if timeline['final_start'] and timeline['final_end']:
                st.caption(f"{timeline['final_start'].strftime('%b %d')} - {timeline['final_end'].strftime('%b %d, %Y')}")
                st.caption(f"({timeline['final_days']} days)")

            # Calculate change
            roas_change = timeline['final_roas'] - timeline['baseline_roas']
            roas_change_pct = (roas_change / timeline['baseline_roas'] * 100) if timeline['baseline_roas'] > 0 else 0

            st.metric(
                label="ROAS",
                value=f"{timeline['final_roas']:.2f}",
                delta=f"{roas_change:+.2f} ({roas_change_pct:+.1f}%)"
            )

            st.caption(f"{currency}{timeline['final_sales']:,.0f} sales")
            st.caption(f"{currency}{timeline['final_spend']:,.0f} spend")

            if timeline.get('final_warning'):
                st.warning(timeline['final_warning'], icon="⚠️")

        st.divider()

        # Summary at bottom
        roas_change = timeline['final_roas'] - timeline['baseline_roas']
        if roas_change < 0:
            st.error(f"**Net Change:** {roas_change:.2f} ROAS ({(roas_change / timeline['baseline_roas'] * 100):+.1f}%)", icon="📉")
        else:
            st.success(f"**Net Change:** {roas_change:+.2f} ROAS ({(roas_change / timeline['baseline_roas'] * 100):+.1f}%)", icon="📈")
