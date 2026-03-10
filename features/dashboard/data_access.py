"""Data-access helpers for Performance Dashboard."""

from __future__ import annotations

import streamlit as st

from app_core.db_manager import get_db_manager


@st.cache_data(ttl=600, show_spinner=False)
def check_spapi_available(client_id: str) -> bool:
    """
    Return True if SP-API is connected/active for this client.

    Falls back safely to False if DB capability is unavailable.
    """
    if not client_id:
        return False

    db = get_db_manager()
    if db is None:
        return False

    if hasattr(db, "has_active_spapi_integration"):
        try:
            return bool(db.has_active_spapi_integration(client_id))
        except Exception:
            return False

    # SQLite fallback path for local/test environments:
    # rely on client_settings connection fields if present.
    placeholder = getattr(db, "placeholder", "?")
    query = (
        "SELECT lwa_refresh_token, onboarding_status"
        " FROM client_settings"
        " WHERE client_id = " + placeholder +
        " LIMIT 1"
    )
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (client_id,))
            row = cursor.fetchone()
            if not row:
                return False

            if isinstance(row, dict):
                token = row.get("lwa_refresh_token")
                status = str(row.get("onboarding_status", "")).strip().lower()
            elif hasattr(row, "keys"):
                token = row["lwa_refresh_token"]
                status = str(row["onboarding_status"]).strip().lower()
            else:
                token = row[0] if len(row) > 0 else None
                status = str(row[1]).strip().lower() if len(row) > 1 else ""

            return bool(token) and status in {"connected", "active"}
    except Exception:
        return False

