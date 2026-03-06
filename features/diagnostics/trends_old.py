"""Diagnostics Trends page module (draft only, not yet wired to nav)."""

from __future__ import annotations

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from components.diagnostic_cards import empty_state_card
from features.diagnostics.styles import inject_diagnostics_css
from utils.diagnostics import _read_sql


def _render_plotly_chart(df: pd.DataFrame, title: str, area: bool = False) -> None:
    """Render a Plotly chart to avoid Altair dependency issues on newer Python versions."""
    if df.empty:
        st.info(f"No data for {title.lower()}.")
        return

    chart_df = df.copy()
    chart_df.index = pd.to_datetime(chart_df.index)

    fig = go.Figure()
    for col in chart_df.columns:
        fig.add_trace(
            go.Scatter(
                x=chart_df.index,
                y=chart_df[col],
                mode="lines",
                name=str(col),
                stackgroup="one" if area else None,
            )
        )

    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
        template="plotly_dark",
        height=300,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    st.plotly_chart(fig, use_container_width=True)


def _fetch_trends_frame(days: int = 60) -> pd.DataFrame:
    return _read_sql(
        """
        SELECT
            ad.report_date,
            ad.total_ordered_revenue,
            ad.organic_revenue,
            (ad.total_ordered_revenue - ad.organic_revenue) AS paid_revenue,
            ad.tacos,
            ad.organic_share_pct
        FROM sc_analytics.account_daily ad
        WHERE ad.marketplace_id = %s
          AND ad.report_date >= CURRENT_DATE - %s
        ORDER BY ad.report_date
        """,
        ["A2VIGQ35RCS4UG", days],
    )


def _fetch_cvr_frame(days: int = 60) -> pd.DataFrame:
    return _read_sql(
        """
        WITH organic AS (
            SELECT report_date, AVG(unit_session_percentage) AS organic_cvr
            FROM sc_raw.sales_traffic
            WHERE marketplace_id = %s
              AND report_date >= CURRENT_DATE - %s
            GROUP BY report_date
        ),
        paid AS (
            SELECT
                report_date,
                SUM(orders)::NUMERIC / NULLIF(SUM(clicks), 0) * 100 AS paid_cvr
            FROM public.raw_search_term_data
            WHERE client_id = %s
              AND report_date >= CURRENT_DATE - %s
            GROUP BY report_date
        )
        SELECT
            o.report_date,
            o.organic_cvr,
            p.paid_cvr
        FROM organic o
        LEFT JOIN paid p USING (report_date)
        ORDER BY o.report_date
        """,
        ["A2VIGQ35RCS4UG", days, "s2c_uae_test", days],
    )


def render_trends_page() -> None:
    inject_diagnostics_css()
    st.markdown('<div class="diag-shell">', unsafe_allow_html=True)
    st.markdown("## Diagnostics / Trends")
    st.caption("Draft module only. Not wired to navigation or production workflows.")

    col_slider, col_refresh = st.columns([4, 1])
    with col_slider:
        days = st.select_slider("Time range", options=[30, 45, 60, 90, 120, 180], value=90)
    with col_refresh:
        if st.button("↺ Refresh", help="Clear cache and reload latest data"):
            st.cache_resource.clear()
            st.rerun()

    try:
        trend_df = _fetch_trends_frame(days=days)
        cvr_df = _fetch_cvr_frame(days=days)
    except Exception as exc:
        st.error(f"Unable to load trend data: {exc}")
        st.markdown(
            empty_state_card(
                "Trend datasets unavailable",
                "Expected until Gate 2 SQL views are validated and integrated.",
            ),
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if trend_df.empty:
        st.markdown(
            empty_state_card("No trend rows", "No account_daily rows found in the selected range."),
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.markdown("### Revenue Breakdown")
    rev_chart_df = trend_df[["report_date", "organic_revenue", "paid_revenue"]].set_index("report_date")
    try:
        _render_plotly_chart(rev_chart_df, "Revenue Breakdown", area=True)
    except Exception as exc:
        st.warning(f"Chart rendering fallback: {exc}")
        st.dataframe(rev_chart_df, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### TACOS vs Organic Share")
        tacos_df = trend_df[["report_date", "tacos", "organic_share_pct"]].set_index("report_date")
        try:
            _render_plotly_chart(tacos_df, "TACOS vs Organic Share")
        except Exception as exc:
            st.warning(f"Chart rendering fallback: {exc}")
            st.dataframe(tacos_df, use_container_width=True)
    with c2:
        st.markdown("### CVR Comparison")
        if cvr_df.empty:
            st.info("No CVR rows for selected range.")
        else:
            cvr_plot_df = cvr_df.set_index("report_date")[["organic_cvr", "paid_cvr"]]
            try:
                _render_plotly_chart(cvr_plot_df, "CVR Comparison")
            except Exception as exc:
                st.warning(f"Chart rendering fallback: {exc}")
                st.dataframe(cvr_plot_df, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    render_trends_page()
