"""Diagnostics Overview page module (draft only, not yet wired to nav)."""

from __future__ import annotations

import streamlit as st

from components.diagnostic_cards import empty_state_card, metric_card, signal_card
from components.icons import render_icon
from features.diagnostics.styles import inject_diagnostics_css
from utils.diagnostics import get_diagnostics_overview_payload


def render_overview_page() -> None:
    inject_diagnostics_css()
    st.markdown('<div class="diag-shell">', unsafe_allow_html=True)
    st.markdown(
        f"## {render_icon('layers', color='var(--diag-primary)', size=20)} Diagnostics / Overview",
        unsafe_allow_html=True,
    )
    st.caption("Draft module only. Integration to navigation is intentionally deferred.")

    try:
        payload = get_diagnostics_overview_payload(days=14)
    except Exception as exc:
        st.error(f"Unable to load diagnostics payload: {exc}")
        st.markdown(
            empty_state_card(
                "Overview unavailable",
                "Data source not ready. This module is staged for post-Gate 2 integration.",
            ),
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            metric_card(
                "Active Signals",
                str(sum(payload["signal_counts"].values())),
                delta="Across 5 diagnostic patterns",
                icon="alert",
            ),
            unsafe_allow_html=True,
        )
    with col2:
        impact = payload["impact_context"]
        st.markdown(
            metric_card(
                "Win Rate",
                f"{impact['win_rate']:.0f}%",
                delta=f"{impact['winners']}/{impact['total_actions']} validations",
                delta_tone="positive" if impact["win_rate"] >= 70 else "neutral",
                icon="trend_up",
            ),
            unsafe_allow_html=True,
        )
    with col3:
        impact = payload["impact_context"]
        st.markdown(
            metric_card(
                "Avg Impact",
                f"{impact['avg_impact']:+.1f}%",
                delta="ROAS lift from Impact Dashboard",
                delta_tone="positive" if impact["avg_impact"] >= 0 else "negative",
                icon="money",
            ),
            unsafe_allow_html=True,
        )

    st.markdown('<div class="diag-panel-title">Primary Drivers</div>', unsafe_allow_html=True)
    cards = payload["signal_cards"][:4]
    if not cards:
        st.markdown(
            empty_state_card(
                "No active signals",
                "No triggered diagnostics for the selected lookback window.",
            ),
            unsafe_allow_html=True,
        )
    for card in cards:
        st.markdown(
            signal_card(
                title=card["title"],
                severity=card["severity"],
                confidence=card["confidence"],
                report_date=card["report_date"],
                evidence=card["evidence"],
                impact_note="Impact Dashboard context is read-only and linked via summary metrics.",
            ),
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    render_overview_page()

