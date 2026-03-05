"""
Miscellaneous Charts - Validation rate, quality distribution, capital flow.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, Any

from features.impact.styles.css import BRAND_COLORS
from features.impact.utils import get_impact_col


def render_validation_rate_chart(impact_df: pd.DataFrame):
    """
    Render validation rate gauge/progress chart.

    Shows percentage of actions that are validated.

    Args:
        impact_df: Impact DataFrame with validation_status column
    """
    if impact_df.empty:
        st.info("No validation data")
        return

    total = len(impact_df)
    if 'validation_status' in impact_df.columns:
        validated = impact_df['validation_status'].str.contains(
            '✓|Validated|Confirmed', na=False, regex=True
        ).sum()
    elif 'is_validated' in impact_df.columns:
        validated = impact_df['is_validated'].sum()
    else:
        validated = total

    rate = (validated / total * 100) if total > 0 else 0

    # Color based on rate
    if rate >= 80:
        color = BRAND_COLORS['green']
    elif rate >= 50:
        color = BRAND_COLORS['cyan']
    else:
        color = BRAND_COLORS['red']

    # Create gauge
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=rate,
        number={'suffix': '%', 'font': {'color': color, 'size': 36}},
        gauge={
            'axis': {'range': [0, 100], 'tickfont': {'color': '#94a3b8'}},
            'bar': {'color': color},
            'bgcolor': 'rgba(148,163,184,0.1)',
            'borderwidth': 0,
            'steps': [
                {'range': [0, 50], 'color': 'rgba(239,68,68,0.1)'},
                {'range': [50, 80], 'color': 'rgba(34,211,238,0.1)'},
                {'range': [80, 100], 'color': 'rgba(16,185,129,0.1)'},
            ],
        },
        title={'text': f"Validated: {validated}/{total}", 'font': {'color': '#94a3b8', 'size': 12}}
    ))

    fig.update_layout(
        height=200,
        margin=dict(t=30, b=10, l=20, r=20),
        paper_bgcolor='rgba(0,0,0,0)',
    )

    st.plotly_chart(fig, use_container_width=True)


def render_decision_quality_distribution(summary: Dict[str, Any]):
    """
    Render decision quality distribution pie/donut chart.

    Shows breakdown of wins vs gaps vs market drag.

    Args:
        summary: Summary dict from backend
    """
    metrics = st.session_state.get('_impact_metrics', {})

    offensive = metrics.get('offensive_count', 0)
    defensive = metrics.get('defensive_count', 0)
    gap = metrics.get('gap_count', 0)
    drag = metrics.get('drag_count', 0)

    if offensive + defensive + gap + drag == 0:
        st.info("No distribution data")
        return

    labels = ['Offensive Win', 'Defensive Win', 'Gap', 'Market Drag']
    values = [offensive, defensive, gap, drag]
    colors = [BRAND_COLORS['green'], BRAND_COLORS['cyan'],
              BRAND_COLORS['red'], BRAND_COLORS['slate']]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors),
        hole=0.6,
        textinfo='percent+label',
        textposition='outside',
        textfont=dict(size=11, color='#e2e8f0'),
        hovertemplate='%{label}: %{value} actions<br>%{percent}<extra></extra>'
    ))

    # Add center text
    total = sum(values)
    win_rate = ((offensive + defensive) / total * 100) if total > 0 else 0
    fig.add_annotation(
        text=f"<b>{win_rate:.0f}%</b><br>Win Rate",
        x=0.5, y=0.5,
        font=dict(size=16, color='#e2e8f0'),
        showarrow=False
    )

    fig.update_layout(
        showlegend=False,
        height=280,
        margin=dict(t=20, b=20, l=20, r=20),
        paper_bgcolor='rgba(0,0,0,0)',
    )

    st.plotly_chart(fig, use_container_width=True)


def render_capital_allocation_flow(impact_df: pd.DataFrame, currency: str):
    """
    Render capital allocation Sankey diagram.

    Shows flow of spend and returns through different action types.

    Args:
        impact_df: Impact DataFrame
        currency: Currency symbol
    """
    if impact_df.empty or 'action_type' not in impact_df.columns:
        st.info("No allocation data available")
        return

    # Aggregate by action type
    impact_col = get_impact_col(impact_df)
    agg = impact_df.groupby('action_type').agg({
        'before_spend': 'sum',
        'observed_after_spend': 'sum',
        'before_sales': 'sum',
        'observed_after_sales': 'sum',
        impact_col: 'sum'
    }).reset_index()

    if agg.empty:
        st.info("No allocation data")
        return

    # Simplify - just show bar comparison
    action_types = agg['action_type'].tolist()
    before_spend = agg['before_spend'].tolist()
    after_spend = agg['observed_after_spend'].tolist()

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Before Spend',
        x=action_types,
        y=before_spend,
        marker_color=BRAND_COLORS['purple_light'],
        text=[f"{currency}{v:,.0f}" for v in before_spend],
        textposition='outside'
    ))

    fig.add_trace(go.Bar(
        name='After Spend',
        x=action_types,
        y=after_spend,
        marker_color=BRAND_COLORS['cyan'],
        text=[f"{currency}{v:,.0f}" for v in after_spend],
        textposition='outside'
    ))

    fig.update_layout(
        barmode='group',
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        height=350,
        margin=dict(t=50, b=40, l=40, r=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(128,128,128,0.15)',
            tickfont=dict(color='#94a3b8')
        ),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(color='#cbd5e1')
        )
    )

    st.plotly_chart(fig, use_container_width=True)
