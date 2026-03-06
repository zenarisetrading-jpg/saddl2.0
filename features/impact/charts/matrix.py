"""
Matrix Charts - Decision outcome matrix visualization.
EXACT copy from legacy impact_dashboard.py lines 2641-2807.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import Dict, Any

from features.impact.utils import get_impact_col


def _ensure_impact_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all required columns exist with defaults."""
    defaults = {
        'decision_impact': 0.0,
        'market_tag': 'Unknown',
        'before_spend': 0.0,
        'before_sales': 0.0,
        'observed_after_spend': 0.0,
        'observed_after_sales': 0.0,
        'expected_trend_pct': 0.0,
        'decision_value_pct': 0.0,
    }
    
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default
    
    return df


def render_decision_outcome_matrix(impact_df: pd.DataFrame, summary: Dict[str, Any]):
    """
    Section 3: Did each decision help or hurt? - Decision Outcome Matrix.
    EXACT copy from legacy impact_dashboard.py _render_decision_outcome_matrix.
    """
    
    # Target icon SVG (cyan color)
    target_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle></svg>'
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%); 
                border: 1px solid rgba(148, 163, 184, 0.15); 
                border-left: 3px solid #06B6D4;
                border-radius: 12px; padding: 16px; margin-bottom: 16px;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);">
        <div style="display: flex; align-items: center; gap: 12px;">
            {target_icon}
            <span style="font-weight: 700; font-size: 1.1rem; color: #F8FAFC; letter-spacing: 0.02em;">Decision Outcome Map</span>
        </div>
        <div style="color: #64748B; font-size: 0.85rem; margin-top: 8px; margin-left: 32px;">
            Each dot is one decision • Hover for details
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if impact_df.empty:
        st.info("No data to display")
        return
    
    # Filter to confirmed actions with valid data
    df = impact_df.copy()
    df = df[df['before_spend'] > 0]
    
    # Ensure required columns exist (handles old cached data)
    df = _ensure_impact_columns(df)
    impact_col = get_impact_col(df)
    
    # Clean up infinite/nan values for visualization
    df = df[np.isfinite(df['expected_trend_pct']) & np.isfinite(df['decision_value_pct'])]
    
    if len(df) < 3:
        st.info("Insufficient data for matrix")
        return

    # Cap outliers for visualization (keep charts readable)
    df['x_display'] = df['expected_trend_pct'].clip(-200, 200)
    df['y_display'] = df['decision_value_pct'].clip(-200, 200)
    
    # Normalize action types for display
    df['action_clean'] = df['action_type'].str.upper().str.replace('_CHANGE', '').str.replace('_ADD', '')
    df['action_clean'] = df['action_clean'].replace({'BID': 'Bid', 'NEGATIVE': 'Negative', 'HARVEST': 'Harvest'})
    
    fig = go.Figure()
    
    # Split data: Non-Market Drag vs Market Drag
    non_drag = df[df['market_tag'] != 'Market Drag']
    drag = df[df['market_tag'] == 'Market Drag']
    
    # 1. ACTIVE POINTS (By Type)
    for action_type, color in [('Bid', '#2A8EC9'), ('Negative', '#9A9AAA'), ('Harvest', '#8FC9D6')]:
        type_df = non_drag[non_drag['action_clean'] == action_type]
        if type_df.empty:
            continue
        
        fig.add_trace(go.Scatter(
            x=type_df['x_display'],
            y=type_df['y_display'],
            mode='markers',
            name=action_type,
            marker=dict(size=10, color=color, opacity=0.8),
            customdata=np.stack((
                type_df['expected_trend_pct'],
                type_df['decision_value_pct'],
                type_df[impact_col],
                type_df['target_text']
            ), axis=-1),
            hovertemplate=(
                "<b>%{customdata[3]}</b><br>" +
                "Expected Trend: %{customdata[0]:+.1f}%<br>" +
                "vs Expectation: %{customdata[1]:+.1f}%<br>" +
                "Net Impact: %{customdata[2]:,.0f}<extra></extra>"
            ),
            text=type_df['action_clean']
        ))
        
    # 2. MARKET DRAG POINTS (Excluded)
    if not drag.empty:
        fig.add_trace(go.Scatter(
            x=drag['x_display'],
            y=drag['y_display'],
            mode='markers',
            name='Market Drag (Excluded)',
            marker=dict(size=8, color='rgba(156, 163, 175, 0.4)', opacity=0.4),
            customdata=np.stack((
                drag['expected_trend_pct'],
                drag['decision_value_pct'],
                drag[impact_col],
                drag['target_text']
            ), axis=-1),
            hovertemplate=(
                "<b>%{customdata[3]}</b> (Market Drag)<br>" +
                "Expected Trend: %{customdata[0]:+.1f}%<br>" +
                "vs Expectation: %{customdata[1]:+.1f}%<br>" +
                "Net Impact: %{customdata[2]:,.0f}<br>" +
                "<i>Excluded from attribution</i><extra></extra>"
            ),
            showlegend=True
        ))
    
    # Add quadrant lines
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    fig.add_vline(x=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    
    # Add quadrant labels
    x_max = max(abs(df['x_display'].max()), abs(df['x_display'].min()), 50)
    y_max = max(abs(df['y_display'].max()), abs(df['y_display'].min()), 50)
    
    annotations = [
        dict(x=-x_max*0.7, y=y_max*0.85, text="Defensive Win", showarrow=False, font=dict(color='#10B981', size=11)),
        dict(x=x_max*0.7, y=y_max*0.85, text="Offensive Win", showarrow=False, font=dict(color='#10B981', size=11)),
        dict(x=-x_max*0.7, y=-y_max*0.85, text="Market Drag", showarrow=False, font=dict(color='#9CA3AF', size=10)),
        dict(x=x_max*0.7, y=-y_max*0.85, text="Decision Gap", showarrow=False, font=dict(color='#EF4444', size=11)),
    ]
    
    fig.update_layout(
        height=400,
        margin=dict(t=30, b=50, l=50, r=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            title=dict(text="Baseline sales change (%)", font=dict(color='#94a3b8')),
            showgrid=True, gridcolor='rgba(128,128,128,0.1)',
            tickfont=dict(color='#94a3b8'),
            zeroline=False
        ),
        yaxis=dict(
            title=dict(text="Delta vs Baseline (%)", font=dict(color='#94a3b8')),
            showgrid=True, gridcolor='rgba(128,128,128,0.1)',
            tickfont=dict(color='#94a3b8'),
            zeroline=False
        ),
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5,
            font=dict(color='#94a3b8', size=11)
        ),
        annotations=annotations
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # How to read this chart
    st.markdown("""
    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(148, 163, 184, 0.1); border-radius: 8px; padding: 12px 16px; font-size: 0.8rem; color: #94a3b8; display: flex; flex-direction: column; gap: 4px;">
        <div style="font-weight: 600; margin-bottom: 4px; color: #E2E8F0;">How to read this chart:</div>
        <div>• X-Axis: Sales change implied purely by spend change (baseline assumption)</div>
        <div>• Y-Axis: Actual performance above or below that baseline (decision impact)</div>
        <div>• Grey points: Market-driven outcomes — excluded from attributed impact</div>
    </div>
    """, unsafe_allow_html=True)
