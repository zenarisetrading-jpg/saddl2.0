"""Shared data access helpers for optimizer flows."""

from __future__ import annotations

import streamlit as st


@st.cache_data(ttl=300, show_spinner=False)
def fetch_target_stats_cached(client_id: str, test_mode: bool, start_date=None):
    """Cached target-stats loader used by optimizer entry and run flows."""
    from app_core.db_manager import get_db_manager

    db_manager = get_db_manager(test_mode)
    if db_manager and client_id:
        return db_manager.get_target_stats_df(client_id, start_date=start_date)
    return None
