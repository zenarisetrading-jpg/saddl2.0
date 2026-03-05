"""
Table Components - Data tables for the impact dashboard.
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Optional

from features.impact.utils import get_impact_col


def render_details_table(impact_df: pd.DataFrame, currency: str):
    """Render collapsed details table."""
    with st.expander("📋 Action Details", expanded=False):
        if impact_df.empty:
            st.info("No actions to display")
            return

        impact_col = get_impact_col(impact_df)

        # Select display columns
        display_cols = ['action_type', 'target_text', 'market_tag', impact_col, 'validation_status']
        available_cols = [c for c in display_cols if c in impact_df.columns]

        if not available_cols:
            st.info("No displayable columns")
            return

        display_df = impact_df[available_cols].copy()

        # Format impact column
        if impact_col in display_df.columns:
            display_df[impact_col] = display_df[impact_col].apply(
                lambda x: f"{currency}{x:+,.0f}" if pd.notna(x) else "N/A"
            )

        # Rename columns for display
        column_names = {
            'action_type': 'Action',
            'target_text': 'Target',
            'market_tag': 'Category',
            impact_col: 'Impact',
            'validation_status': 'Status'
        }
        display_df = display_df.rename(columns=column_names)

        st.dataframe(display_df, width='stretch', hide_index=True)


def render_drill_down_table(impact_df: pd.DataFrame, show_migration_badge: bool = False):
    """Render detailed drill-down table with decision-adjusted metrics."""
    with st.expander("📋 Detailed Action Log", expanded=False):
        if impact_df.empty:
            st.info("No actions to display")
            return

        display_df = impact_df.copy()

        # Add migration badge for HARVEST with before_spend > 0
        if show_migration_badge and 'is_migration' in display_df.columns:
            display_df['action_display'] = display_df.apply(
                lambda r: f"🔄 {r['action_type']}" if r.get('is_migration', False) else r['action_type'],
                axis=1
            )
        else:
            display_df['action_display'] = display_df['action_type']

        impact_col = get_impact_col(display_df)

        # Ensure columns exist
        for col in [impact_col, 'spend_avoided', 'cpc_before', 'cpc_after',
                    'cpc_change_pct', 'expected_sales', 'spc_before', 'market_downshift']:
            if col not in display_df.columns:
                display_df[col] = np.nan

        # Market Tag logic
        def get_market_tag(row):
            if row.get('before_clicks', 0) == 0:
                return "Low Data"
            if row.get('market_downshift', False) == True:
                return "Market Downshift"
            return "Normal"

        if 'market_tag' not in display_df.columns:
            display_df['market_tag'] = display_df.apply(get_market_tag, axis=1)

        # Decision Outcome logic
        def get_decision_outcome(row):
            action = str(row.get('action_type', '')).upper()
            di = row[impact_col] if pd.notna(row.get(impact_col)) else 0
            sa = row['spend_avoided'] if pd.notna(row.get('spend_avoided')) else 0
            bs = row['before_spend'] if pd.notna(row.get('before_spend')) else 0
            market_tag = row.get('market_tag', 'Normal')

            if market_tag == "Low Data":
                return "🟡 Neutral"

            if di > 0:
                return "🟢 Good"
            if action in ['BID_DOWN', 'PAUSE', 'NEGATIVE'] and bs > 0 and sa >= 0.1 * bs:
                return "🟢 Good"

            before_sales = row['before_sales'] if pd.notna(row.get('before_sales')) else 0
            threshold = max(0.05 * before_sales, 10)
            if abs(di) < threshold:
                return "🟡 Neutral"

            if di < 0 and market_tag == "Normal":
                return "🔴 Bad"

            return "🟡 Neutral"

        display_df['decision_outcome'] = display_df.apply(get_decision_outcome, axis=1)

        # Select final columns
        display_cols = [
            'action_display', 'target_text', 'market_tag', impact_col, 'decision_outcome'
        ]
        available_cols = [c for c in display_cols if c in display_df.columns]

        subset_df = display_df[available_cols].copy()
        if impact_col in subset_df.columns:
            subset_df = subset_df.rename(columns={impact_col: 'Impact'})
        st.dataframe(subset_df, width='stretch', hide_index=True)


def render_dormant_table(dormant_df: pd.DataFrame):
    """Render table of dormant (zero-spend) actions."""
    if dormant_df.empty:
        return

    st.markdown("### 💤 Waiting for Traffic")
    st.caption("These mature actions have $0 spend in both periods. Impact is pending traffic.")

    display_cols = ['action_date', 'action_type', 'target_text']
    available_cols = [c for c in display_cols if c in dormant_df.columns]

    if available_cols:
        display_df = dormant_df[available_cols].copy()
        display_df.columns = ['Date', 'Type', 'Target'][:len(available_cols)]
        st.dataframe(display_df, width='stretch', hide_index=True)
