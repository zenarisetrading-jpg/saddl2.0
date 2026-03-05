"""Diagnostics Signals page module (draft only, not yet wired to nav)."""

from __future__ import annotations

import streamlit as st

from components.diagnostic_cards import empty_state_card, signal_card
from features.diagnostics.styles import inject_diagnostics_css
from utils.diagnostics import SIGNAL_VIEWS, fetch_all_signal_views, format_signal_rows_for_ui


def render_signals_page() -> None:
    inject_diagnostics_css()
    st.markdown('<div class="diag-shell">', unsafe_allow_html=True)
    st.markdown("## Diagnostics / Signals")
    st.caption("Draft module only. Intended to be integrated after Phase 2 validation gate.")

    col1, col2 = st.columns([1, 1])
    with col1:
        days = st.selectbox("Lookback window", options=[7, 14, 30, 60], index=2)
    with col2:
        active_only = st.toggle("Active signals only", value=True)

    try:
        signal_frames = fetch_all_signal_views(days=days, active_only=active_only)
    except Exception as exc:
        st.error(f"Unable to query signal views: {exc}")
        st.markdown(
            empty_state_card(
                "Signal views unavailable",
                "SQL drafts are staged in db/migrations/004_signal_views.sql and not executed yet.",
            ),
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for key in SIGNAL_VIEWS:
        rows = format_signal_rows_for_ui(key, signal_frames[key], limit=50)
        st.markdown(f"### {key.replace('_', ' ').title()} ({len(rows)})")
        if not rows:
            st.markdown(
                empty_state_card(
                    "No signals in selection",
                    "This can be expected depending on market conditions and lookback range.",
                ),
                unsafe_allow_html=True,
            )
            continue
        for row in rows[:10]:
            st.markdown(
                signal_card(
                    title=row["title"],
                    severity=row["severity"],
                    confidence=row["confidence"],
                    report_date=row["report_date"],
                    evidence=row["evidence"],
                    impact_note="Recommendation confidence should be interpreted with Impact Dashboard outcomes.",
                ),
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    render_signals_page()

