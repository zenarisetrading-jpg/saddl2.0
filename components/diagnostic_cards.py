"""Render components for Diagnostic Control Center v2.1."""
from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.icons import render_icon
from features.impact.charts.waterfall import render_roas_attribution_bar
from utils.formatters import get_account_currency


def _render_html(html: str) -> None:
    if hasattr(st, "html"):
        st.html(html)
    else:
        st.markdown(html, unsafe_allow_html=True)


def _delta_class(val: float, inverse: bool = False) -> str:
    value = (val or 0) * (-1 if inverse else 1)
    if value > 0:
        return "pos"
    if value < 0:
        return "neg"
    return "neu"


def _delta_text(val: float, suffix: str = "%", inverse: bool = False, decimals: int = 1) -> str:
    value = (val or 0) * (-1 if inverse else 1)
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{decimals}f}{suffix}"


def _health_pct(score: float) -> int:
    clamped = max(0, min(25, float(score or 0)))
    return int((clamped / 25) * 100)


def render_health_card(health: Dict[str, Any], diagnosis: Dict[str, Any]) -> None:
    status_key = str(health.get("status", "CAUTION")).lower()
    diagnosis_label = diagnosis.get("label", "Mixed Signals")
    diagnosis_statement = diagnosis.get("statement", "No clear diagnosis available.")

    _render_html(
        f"""
<div class="health-card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:18px;">
    <div>
      <div class="section-kicker">Account Health Score</div>
      <div class="diag-score">{int(health.get('score', 0))}/100</div>
      <div class="diag-pill {status_key}">{render_icon('alert-circle', color='#8dd3ff', size=14)} {health.get('status', 'CAUTION')}</div>
    </div>
    <div class="diag-text-sm" style="text-align:right;">Last 30 days<br/>vs prior 30 days</div>
  </div>

  <div class="metric-grid">
    <div class="metric-card">
      <div class="metric-label">Total Sales</div>
      <div class="metric-value">${health.get('current_sales', 0):,.0f}</div>
      <div class="metric-delta {_delta_class(float(health.get('sales_change_pct', 0) or 0))}">{_delta_text(float(health.get('sales_change_pct', 0) or 0))}</div>
      <div class="mini-health">{_health_pct(health.get('sales_score', 0))}% healthy</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">TACOS</div>
      <div class="metric-value">{float(health.get('current_tacos', 0) or 0):.1f}%</div>
      <div class="metric-delta {_delta_class(float(health.get('tacos_change', 0) or 0), inverse=True)}">{_delta_text(float(health.get('tacos_change', 0) or 0), suffix=' pts', inverse=True)}</div>
      <div class="mini-health">{_health_pct(health.get('tacos_score', 0))}% healthy</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Organic Share</div>
      <div class="metric-value">{float(health.get('current_organic', 0) or 0):.1f}%</div>
      <div class="metric-delta {_delta_class(float(health.get('organic_change', 0) or 0))}">{_delta_text(float(health.get('organic_change', 0) or 0))}</div>
      <div class="mini-health">{_health_pct(health.get('organic_score', 0))}% healthy</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Avg BSR</div>
      <div class="metric-value">#{float(health.get('current_bsr', 0) or 0):,.0f}</div>
      <div class="metric-delta {_delta_class(float(health.get('bsr_change_pct', 0) or 0), inverse=True)}">{_delta_text(float(health.get('bsr_change_pct', 0) or 0), inverse=True)}</div>
      <div class="mini-health">{_health_pct(health.get('bsr_score', 0))}% healthy</div>
    </div>
  </div>

  <div class="primary-box">
    <div class="diag-title-md" style="display:flex;align-items:center;gap:8px;">{render_icon('eye', color='#9ec5ff', size=16)} Primary issue: {diagnosis_label}</div>
    <div class="diag-text-sm" style="margin-top:8px;">{diagnosis_statement}</div>
  </div>
</div>
        """
    )


def _base_chart_layout() -> Dict[str, Any]:
    return {
        "template": "plotly_dark",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "height": 280,
        "margin": dict(l=16, r=16, t=16, b=16),
        "legend": dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    }


def _render_card_title(title: str) -> None:
    _render_html(f"<div class='diag-title-md'>{title}</div>")


def _render_note(what_you_see: str, diagnosis: str) -> None:
    _render_html(
        f"""
<div class="chart-note">
  <div class="diag-text-sm" style="display:flex;align-items:center;gap:8px;">{render_icon('eye', color='#76c7ff', size=14)} {what_you_see}</div>
  <div class="diag-text-sm" style="display:flex;align-items:center;gap:8px;margin-top:6px;">{render_icon('lightbulb', color='#7be0c0', size=14)} {diagnosis}</div>
</div>
        """
    )


def render_visual_proof(
    revenue: Dict[str, Any],
    bsr: Dict[str, Any],
    traffic_bsr: Dict[str, Any],
    cvr: Dict[str, Any],
    optimization: Dict[str, Any],
    impact_summary: Dict[str, Any],
    impact_df: pd.DataFrame,
) -> None:
    st.markdown('<div class="section-head"><div><div class="section-kicker">Visual proof</div><div class="diag-title-lg">4 charts, 4 decisions</div></div></div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        _render_card_title("Why is revenue changing?")
        fig = build_paid_vs_organic_revenue_figure(revenue)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        _render_note(
            f"Paid trend {revenue.get('paid_trend_pct', 0):+.0f}% | Organic trend {revenue.get('organic_trend_pct', 0):+.0f}%.",
            revenue.get("diagnosis", "Check channel trend separation."),
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        _render_card_title("Is organic rank improving or declining?")
        fig = build_traffic_bsr_overlay_figure(traffic_bsr, bsr)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        _render_note(
            f"Organic {traffic_bsr.get('organic_trend_pct', 0):+.0f}% | Paid {traffic_bsr.get('paid_trend_pct', 0):+.0f}% | BSR {bsr.get('rank_change_pct', 0):+.1f}%.",
            traffic_bsr.get("diagnosis", bsr.get("diagnosis", "Insufficient data.")),
        )
        st.markdown('</div>', unsafe_allow_html=True)

    c3, c4 = st.columns(2)
    with c3:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        _render_card_title("Is this PPC or market problem?")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=cvr.get("dates", []), y=cvr.get("organic_values", []), mode="lines", name="Organic CVR", line=dict(width=2.1, color="#66b3ff")))
        fig.add_trace(go.Scatter(x=cvr.get("dates", []), y=cvr.get("paid_values", []), mode="lines", name="Paid CVR", line=dict(width=2.1, color="#ff6f6f")))
        fig.update_layout(**_base_chart_layout())
        fig.update_yaxes(title="CVR %")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        _render_note(
            f"Correlation r={float(cvr.get('correlation', 0) or 0):.2f}",
            cvr.get("diagnosis", "Insufficient data."),
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with c4:
        currency = get_account_currency()
        render_roas_attribution_bar(impact_summary or {}, impact_df if impact_df is not None else pd.DataFrame(), currency)


def build_paid_vs_organic_revenue_figure(revenue: Dict[str, Any]) -> go.Figure:
    """Reusable: paid vs organic revenue trend figure."""
    dates = revenue.get("dates", []) or []
    paid = revenue.get("paid_revenue", []) or []
    organic = revenue.get("organic_revenue", []) or []

    # Keep only rows where at least one channel has non-zero value.
    # This prevents visual "drop-to-zero" tails from placeholder/empty days.
    points = []
    for d, p, o in zip(dates, paid, organic):
        p_val = float(p or 0)
        o_val = float(o or 0)
        if p_val > 0 or o_val > 0:
            points.append((d, p_val, o_val))

    if points:
        x_vals = [p[0] for p in points]
        paid_vals = [p[1] for p in points]
        organic_vals = [p[2] for p in points]
    else:
        x_vals = dates
        paid_vals = [float(v or 0) for v in paid]
        organic_vals = [float(v or 0) for v in organic]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=paid_vals,
            mode="lines",
            stackgroup="one",
            name="Paid Revenue",
            line=dict(width=1.8, color="#ff8a65"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=organic_vals,
            mode="lines",
            stackgroup="one",
            name="Organic Revenue",
            line=dict(width=1.8, color="#60a5fa"),
        )
    )
    fig.update_layout(**_base_chart_layout())
    return fig


def build_traffic_bsr_overlay_figure(traffic_bsr: Dict[str, Any], bsr: Dict[str, Any]) -> go.Figure:
    """Reusable: stacked traffic with optional BSR overlay figure."""
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=traffic_bsr.get("dates", []),
            y=traffic_bsr.get("organic_traffic", []),
            name="Organic Traffic",
            marker_color="#60a5fa",
            opacity=0.8,
        )
    )
    fig.add_trace(
        go.Bar(
            x=traffic_bsr.get("dates", []),
            y=traffic_bsr.get("paid_traffic", []),
            name="Paid Traffic",
            marker_color="#ff8a65",
            opacity=0.85,
        )
    )
    if bsr and bsr.get("dates"):
        fig.add_trace(
            go.Scatter(
                x=bsr.get("dates", []),
                y=bsr.get("ranks", []),
                mode="lines",
                name="Avg BSR",
                line=dict(width=2.2, color="#f6b23f"),
                yaxis="y2",
            )
        )
    fig.update_layout(**_base_chart_layout())
    fig.update_layout(
        barmode="stack",
        yaxis=dict(title="Traffic", showgrid=True, gridcolor="rgba(148,163,184,0.12)"),
        yaxis2=dict(
            title="BSR (lower is better)",
            overlaying="y",
            side="right",
            autorange="reversed",
            showgrid=False,
        ),
    )
    return fig


def _render_action_list(items: List[Dict[str, Any]], fallback: str) -> str:
    if not items:
        return f"<ul><li>{fallback}</li></ul>"
    html = "<ul>"
    for item in items:
        text = item.get("text") or item.get("campaign") or "Action"
        reason = item.get("reason")
        if reason:
            html += f"<li>{text}<br/><span style='font-size:0.82rem;opacity:.85'>{reason}</span></li>"
        else:
            html += f"<li>{text}</li>"
    html += "</ul>"
    return html


def render_actions(actions: Dict[str, List[Dict[str, Any]]]) -> bool:
    st.markdown('<div class="section-head"><div><div class="section-kicker">Recommended actions</div><div class="diag-title-lg">Multi-dimensional response plan</div></div></div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        _render_html(
            f"""
<div class="action-card">
  <h4>{render_icon('target', color='#5ea7ff', size=15)} Strategic direction</h4>
  {_render_action_list(actions.get('strategic', []), 'Maintain baseline strategy and monitor daily.')}
</div>
            """
        )
        campaigns = actions.get("campaign_optimizations", [])
        campaign_items = []
        for c in campaigns[:8]:
            campaign_items.append(
                {
                    "text": f"{c.get('campaign', '-')}: ROAS {float(c.get('roas', 0) or 0):.2f}",
                    "reason": f"Estimated waste {float(c.get('waste', 0) or 0):,.0f} AED/month",
                }
            )
        _render_html(
            f"""
<div class="action-card" style="margin-top:12px;">
  <h4>{render_icon('alert-circle', color='#f6b23f', size=15)} Campaign optimizations</h4>
  {_render_action_list(campaign_items, 'No brutal underperformers detected in this lookback.')}
</div>
            """
        )

    with col2:
        _render_html(
            f"""
<div class="action-card">
  <h4>{render_icon('box', color='#7be0c0', size=15)} Product and listing actions</h4>
  {_render_action_list(actions.get('product_listing', []), 'No immediate listing action required.')}
</div>
<div class="action-card" style="margin-top:12px;">
  <h4>{render_icon('wallet', color='#ffd581', size=15)} Budget adjustments</h4>
  {_render_action_list(actions.get('budget_pacing', []), 'Maintain current budget pacing.')}
</div>
            """
        )

    return st.button("Review in Optimizer", type="primary", use_container_width=False)


def render_asin_table(df: pd.DataFrame) -> None:
    st.markdown('<div class="section-head"><div><div class="section-kicker">ASIN attention list</div><div class="diag-title-lg">ASINs requiring attention</div></div></div>', unsafe_allow_html=True)

    if df.empty:
        st.info("No ASINs requiring attention for this window.")
        return

    with st.expander("Expand ASIN table", expanded=False):
        show_df = df.copy()

        def _action_needed(row: pd.Series) -> str:
            bsr_change_pct = float(row.get("bsr_change_pct", 0) or 0)
            organic_rev_change_pct = float(row.get("organic_rev_change_pct", 0) or 0)
            if bsr_change_pct > 20 and organic_rev_change_pct < -15:
                return "DEFEND"
            if bsr_change_pct > 10 and organic_rev_change_pct < -5:
                return "MONITOR"
            if bsr_change_pct < -10 and organic_rev_change_pct > 10:
                return "SCALING"
            return "STABLE"

        show_df["Action Needed"] = show_df.apply(_action_needed, axis=1)
        show_df = show_df.rename(
            columns={
                "child_asin": "ASIN",
                "current_bsr": "BSR",
                "bsr_change_pct": "BSR Δ30d %",
                "current_organic_rev": "Organic Rev 30d",
                "organic_rev_change_pct": "Organic Rev Δ30d %",
                "monthly_impact": "Impact $/mo",
            }
        )
        cols = [
            c
            for c in [
                "ASIN",
                "BSR",
                "BSR Δ30d %",
                "Organic Rev 30d",
                "Action Needed",
                "Organic Rev Δ30d %",
                "Impact $/mo",
            ]
            if c in show_df.columns
        ]
        st.markdown('<div class="asin-toolbar">Sortable and filterable table for ASIN-level action triage.</div>', unsafe_allow_html=True)
        st.dataframe(show_df[cols], use_container_width=True, hide_index=True)
