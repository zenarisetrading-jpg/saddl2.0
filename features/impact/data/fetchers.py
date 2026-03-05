"""
Data Fetchers - Cached data fetching for impact analysis.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Tuple

from app_core.db_manager import get_db_manager


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_impact_data(
    client_id: str,
    test_mode: bool,
    before_days: int = 14,
    after_days: int = 14,
    cache_version: str = "v14_impact_tiers"
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Cached data fetcher for impact analysis.
    Prevents re-querying the DB on every rerun or tab switch.

    Args:
        client_id: Account ID
        test_mode: Whether using test database
        before_days: Number of days for before comparison window (fixed at 14)
        after_days: Number of days for after comparison window (14, 30, or 60)
        cache_version: Version string that changes when data is uploaded (invalidates cache)

    Returns:
        Tuple of (impact_df, full_summary)
    """
    try:
        db = get_db_manager(test_mode)
        impact_df = db.get_action_impact(client_id, before_days=before_days, after_days=after_days)
        full_summary = db.get_impact_summary(client_id, before_days=before_days, after_days=after_days)
        return impact_df, full_summary
    except Exception as e:
        # Return empty structures on failure to prevent UI crash
        print(f"Cache miss error: {e}")
        return pd.DataFrame(), {
            'total_actions': 0,
            'roas_before': 0, 'roas_after': 0, 'roas_lift_pct': 0,
            'incremental_revenue': 0,
            'p_value': 1.0, 'is_significant': False, 'confidence_pct': 0,
            'implementation_rate': 0, 'confirmed_impact': 0, 'pending': 0,
            'win_rate': 0, 'winners': 0, 'losers': 0,
            'by_action_type': {}
        }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_account_actuals(client_id: str, cache_version: str) -> pd.DataFrame:
    """
    Cached fetcher for account-level daily stats (Actuals).

    Args:
        client_id: Account ID
        cache_version: Version string for cache invalidation

    Returns:
        DataFrame with account actuals
    """
    try:
        db = get_db_manager()
        df = db.get_target_stats_df(client_id)
        if df.empty:
            return pd.DataFrame()
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    except Exception as e:
        print(f"Actuals fetch error: {e}")
        return pd.DataFrame()


# Backward-compatible aliases
_fetch_impact_data = fetch_impact_data
_fetch_account_actuals = fetch_account_actuals
