"""
Timeline Charts - Decision timeline and cumulative impact charts.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, Any, Optional

from features.impact.styles.css import BRAND_COLORS
from features.impact.utils import get_impact_col


def create_decision_timeline_figure(
    impact_df: pd.DataFrame,
    currency: str = "$",
    height: int = 350
) -> go.Figure:
    """
    Create a decision timeline figure showing actions over time.

    This is a factory function that returns a Plotly figure,
    used by client report generation.

    Args:
        impact_df: Impact DataFrame with action_date column
        currency: Currency symbol
        height: Chart height in pixels

    Returns:
        Plotly Figure object
    """
    if impact_df.empty or 'action_date' not in impact_df.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="No timeline data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        return fig

    df = impact_df.copy()
    df['action_date'] = pd.to_datetime(df['action_date'])

    impact_col = get_impact_col(df)

    # Group by date
    daily = df.groupby('action_date').agg({
        impact_col: 'sum',
        'action_type': 'count'
    }).reset_index()
    daily.columns = ['date', 'impact', 'count']
    daily = daily.sort_values('date')

    # Cumulative
    daily['cumulative'] = daily['impact'].cumsum()

    fig = go.Figure()

    # Bar for daily impact
    colors = [BRAND_COLORS['green'] if v >= 0 else BRAND_COLORS['red'] for v in daily['impact']]
    fig.add_trace(go.Bar(
        x=daily['date'],
        y=daily['impact'],
        name='Daily Impact',
        marker_color=colors,
        opacity=0.6
    ))

    # Line for cumulative
    fig.add_trace(go.Scatter(
        x=daily['date'],
        y=daily['cumulative'],
        name='Cumulative',
        mode='lines+markers',
        line=dict(color=BRAND_COLORS['cyan'], width=3),
        marker=dict(size=8)
    ))

    fig.update_layout(
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        height=height,
        margin=dict(t=40, b=40, l=40, r=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(128,128,128,0.15)',
            tickfont=dict(color='#94a3b8')
        ),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(color='#94a3b8')
        ),
        barmode='overlay'
    )

    return fig


def render_cumulative_impact_chart(impact_df: pd.DataFrame, currency: str):
    """
    Render cumulative impact timeline chart.

    Args:
        impact_df: Impact DataFrame
        currency: Currency symbol
    """
    if impact_df.empty:
        st.info("No timeline data available")
        return

    fig = create_decision_timeline_figure(impact_df, currency)
    st.plotly_chart(fig, use_container_width=True)


def render_revenue_counterfactual_chart(
    impact_df: pd.DataFrame,
    client_id: str,
    cache_version: str,
    verified_lift_override: float = None,
    summary_context: dict = None
):
    """
    Render revenue counterfactual comparison chart.

    Shows actual revenue vs. what would have happened without optimizations.

    Args:
        impact_df: Impact DataFrame
        client_id: Client account ID
        cache_version: Cache version for data fetching
        verified_lift_override: Override for verified lift value
        summary_context: Additional context from summary
    """
    if impact_df.empty:
        st.info("No counterfactual data available")
        return

    from utils.formatters import get_account_currency
    currency = get_account_currency()

    # Calculate totals
    actual_sales = impact_df['observed_after_sales'].sum()
    expected_sales = impact_df.get('expected_sales', impact_df['before_sales']).sum()
    lift = actual_sales - expected_sales

    if verified_lift_override is not None:
        lift = verified_lift_override

    # Create comparison chart
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=['Expected (No Action)', 'Actual'],
        y=[expected_sales, actual_sales],
        marker_color=[BRAND_COLORS['purple_light'], BRAND_COLORS['cyan']],
        text=[f"{currency}{expected_sales:,.0f}", f"{currency}{actual_sales:,.0f}"],
        textposition='outside',
        textfont=dict(size=14, color='#e2e8f0')
    ))

    # Add lift annotation
    lift_color = BRAND_COLORS['green'] if lift >= 0 else BRAND_COLORS['red']
    lift_sign = '+' if lift >= 0 else ''
    fig.add_annotation(
        x=1, y=actual_sales,
        text=f"{lift_sign}{currency}{lift:,.0f}",
        showarrow=True,
        arrowhead=2,
        arrowcolor=lift_color,
        font=dict(color=lift_color, size=16, weight='bold'),
        ax=50, ay=-30
    )

    fig.update_layout(
        showlegend=False,
        height=350,
        margin=dict(t=40, b=40, l=40, r=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(128,128,128,0.15)',
            tickfont=dict(color='#94a3b8')
        ),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(color='#cbd5e1', size=12)
        )
    )

    st.plotly_chart(fig, use_container_width=True)
