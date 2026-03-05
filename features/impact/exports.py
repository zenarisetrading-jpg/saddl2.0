"""
Public Exports - Functions exposed for use by other modules.

These functions are used by:
- report_card.py: get_recent_impact_summary
- executive_dashboard.py: get_maturity_status (re-exported from app_core.utils)
- Home page: render_reference_data_badge
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app_core.db_manager import get_db_manager
from app_core.utils import get_maturity_status, IMPACT_WINDOWS

from features.impact.data.fetchers import fetch_impact_data
from features.impact.data.transforms import validate_impact_columns
from features.impact_metrics import ImpactMetrics


def render_reference_data_badge():
    """Render a badge showing the reference data period for impact analysis."""
    # Get current client and fetch dates
    client_id = st.session_state.get('active_account_id', '')
    if not client_id:
        return

    try:
        db = get_db_manager()
        dates = db.get_available_dates(client_id)
        if dates:
            latest = pd.to_datetime(dates[0]).strftime('%b %d, %Y')
            earliest = pd.to_datetime(dates[-1]).strftime('%b %d, %Y')
            st.caption(f"📅 Data: {earliest} → {latest}")
    except Exception:
        pass


def get_recent_impact_summary() -> Optional[Dict[str, Any]]:
    """
    Get a summary of recent impact metrics for the home page.

    Returns:
        dict with impact summary or None if no data
    """
    client_id = st.session_state.get('active_account_id', '')
    if not client_id:
        return None

    test_mode = st.session_state.get('test_mode', False)

    try:
        # Use 14D window for recent summary
        cache_version = st.session_state.get('data_version', 'v1')
        impact_df, full_summary = fetch_impact_data(
            client_id,
            test_mode,
            before_days=14,
            after_days=14,
            cache_version=cache_version
        )

        if impact_df.empty:
            return None

        # Get latest data date for maturity check
        db = get_db_manager(test_mode)
        available_dates = db.get_available_dates(client_id)
        latest_data_date = pd.to_datetime(available_dates[0]) if available_dates else None

        # Apply maturity filter
        if latest_data_date and 'action_date' in impact_df.columns:
            impact_df['is_mature'] = impact_df['action_date'].apply(
                lambda d: get_maturity_status(d, latest_data_date, horizon='14D')['is_mature']
            )
            mature_df = impact_df[impact_df['is_mature'] == True].copy()
        else:
            mature_df = impact_df.copy()

        if mature_df.empty:
            return None

        # Validate required v3.3 columns
        mature_df = validate_impact_columns(mature_df)

        # Calculate summary metrics
        validated = full_summary.get('validated', {})
        total_actions = len(mature_df)
        metrics = ImpactMetrics.from_dataframe(
            mature_df,
            filters={'validated_only': True, 'mature_only': True},
            horizon_days=14
        )
        attributed_impact = metrics.attributed_impact if metrics and metrics.has_data else validated.get('decision_impact', 0)

        # Count wins
        wins = len(mature_df[mature_df['market_tag'].isin(['Offensive Win', 'Defensive Win'])])
        win_rate = (wins / total_actions * 100) if total_actions > 0 else 0

        return {
            'total_actions': total_actions,
            'attributed_impact': attributed_impact,
            'win_rate': win_rate,
            'wins': wins,
            'roas_before': validated.get('roas_before', 0),
            'roas_after': validated.get('roas_after', 0),
            'roas_lift_pct': validated.get('roas_lift_pct', 0),
        }

    except Exception as e:
        print(f"Error getting recent impact summary: {e}")
        return None
