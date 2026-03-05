"""
Executive Dashboard - Clean Version
Uses pre-calculated metrics, focuses on visual impact + decision proof
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional
from utils.formatters import get_account_currency
from features.impact_metrics import ImpactMetrics
from features.report_card import get_account_health_score
from features.constants import classify_match_type
from ui.theme import ThemeManager

from features.impact_dashboard import get_maturity_status, _fetch_impact_data
from features.optimizer_shared.ppc_classifications import classify_performance_quadrant as _classify_quadrant_shared
from app_core.db_manager import get_db_manager

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_and_process_stats(client_id: str, cache_version: str, start_date=None) -> Optional[pd.DataFrame]:
    """
    Cached fetcher for target stats.
    Includes expensive pre-processing:
    - Date conversion
    - Match type classification
    - Base metric calculation
    """
    try:
        db = get_db_manager()
        df = db.get_target_stats_df(client_id, start_date=start_date)
        
        if df.empty:
            return None
            
        # Calculate metrics
        df['Date'] = pd.to_datetime(df['Date'])
        df['ROAS'] = (df['Sales'] / df['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
        df['CVR'] = (df['Orders'] / df['Clicks'] * 100).replace([np.inf, -np.inf], 0).fillna(0)
        df['CPC'] = (df['Spend'] / df['Clicks']).replace([np.inf, -np.inf], 0).fillna(0)
        
        # Unified Match Type Logic (expensive loop)
        df['Refined Match Type'] = df['Match Type'].fillna('-').astype(str)
        if 'Targeting' in df.columns:
            df['Refined Match Type'] = df.apply(classify_match_type, axis=1)
            
        return df
    except Exception as e:
        print(f"Stats fetch error: {e}")
        return None






def create_revenue_timeline_figure(
    df_current: pd.DataFrame, 
    impact_df: pd.DataFrame, 
    currency: str = 'INR ',
    for_export: bool = False
) -> Optional['go.Figure']:
    """
    Create Revenue Trend with Decision Markers - reusable by dashboard and client report.
    
    Args:
        df_current: DataFrame with Date and Sales columns (daily data)
        impact_df: DataFrame with action_impact data
        currency: Currency symbol/prefix
        for_export: If True, uses solid background for PNG export
        
    Returns:
        Plotly Figure object or None if no data
    """
    import plotly.graph_objects as go
    
    if impact_df is None or impact_df.empty:
        return None
        
    if df_current.empty or 'Date' not in df_current.columns or 'Sales' not in df_current.columns:
        return None
        
    df = df_current.copy()
    
    # === FILTER: Match ImpactMetrics logic ===
    impact_col = 'final_decision_impact' if 'final_decision_impact' in impact_df.columns else 'decision_impact'
    
    if impact_col not in impact_df.columns:
        return None
    
    # Filter: mature + validated (same as ImpactMetrics)
    filtered = impact_df.copy()
    immature_df = pd.DataFrame()  # Track immature windows for pending markers
    
    if 'is_mature' in impact_df.columns:
        filtered = impact_df[impact_df['is_mature'] == True].copy()
        immature_df = impact_df[impact_df['is_mature'] == False].copy()
    
    if 'validation_status' in filtered.columns:
        mask = filtered['validation_status'].str.contains(
            '✓|CPC Validated|CPC Match|Directional|Confirmed|Normalized|Volume', 
            na=False, regex=True
        )
        filtered = filtered[mask]
    
    # Allow showing pending markers even if no validated actions yet
    if filtered.empty and immature_df.empty:
        return None
    
    # === AGGREGATE BY ACTION WINDOW (Weekly) ===
    window_data = []
    pending_window_data = []
    
    # Mature + validated windows
    if not filtered.empty:
        filtered['action_date'] = pd.to_datetime(filtered['action_date'])
        filtered['Week'] = filtered['action_date'].dt.to_period('W').apply(lambda x: x.start_time)
        
        for week, group in filtered.groupby('Week'):
            offensive = group.loc[group['market_tag'] == 'Offensive Win', impact_col].sum()
            defensive = group.loc[group['market_tag'] == 'Defensive Win', impact_col].sum()
            gap = group.loc[group['market_tag'] == 'Gap', impact_col].sum()
            drag = group.loc[group['market_tag'] == 'Market Drag', impact_col].sum()
            
            attributed = offensive + defensive + gap
            total_actions = len(group)
            
            window_data.append({
                'week': week,
                'attributed': attributed,
                'offensive': offensive,
                'defensive': defensive,
                'gap': gap,
                'drag': drag,
                'actions': total_actions,
                'is_pending': False
            })
    
    # Immature (pending) windows
    if not immature_df.empty:
        immature_df['action_date'] = pd.to_datetime(immature_df['action_date'])
        immature_df['Week'] = immature_df['action_date'].dt.to_period('W').apply(lambda x: x.start_time)
        
        for week, group in immature_df.groupby('Week'):
            mature_weeks = [w['week'] for w in window_data]
            if week not in mature_weeks:
                total_actions = len(group)
                pending_window_data.append({
                    'week': week,
                    'attributed': 0,
                    'offensive': 0,
                    'defensive': 0,
                    'gap': 0,
                    'drag': 0,
                    'actions': total_actions,
                    'is_pending': True
                })
    
    all_windows = window_data + pending_window_data
    if not all_windows:
        return None
    
    window_df = pd.DataFrame(all_windows).sort_values('week')
    
    # Get weekly revenue for Y-axis positioning
    df['Week'] = df['Date'].dt.to_period('W').apply(lambda x: x.start_time)
    weekly_revenue = df.groupby('Week')['Sales'].sum().reset_index()
    
    # === CREATE VISUALIZATION ===
    fig = go.Figure()
    
    # Revenue trend line
    fig.add_trace(go.Scatter(
        x=weekly_revenue['Week'],
        y=weekly_revenue['Sales'],
        mode='lines',
        name='Revenue Trend',
        line=dict(color='#64748B', width=2.5, shape='spline'),
        hovertemplate='%{x|%b %d}<br>Revenue: ' + currency + ' %{y:,.0f}<extra></extra>',
        showlegend=True
    ))
    
    # Match windows to revenue points
    marker_weeks = []
    marker_revenues = []
    marker_colors = []
    marker_opacities = []
    
    # Colors
    C_SUCCESS = '#10B981'
    C_DANGER = '#EF4444'
    C_PENDING = '#64748B'
    
    for _, row in window_df.iterrows():
        revenue_match = weekly_revenue[weekly_revenue['Week'] == row['week']]['Sales'].values
        if len(revenue_match) > 0:
            marker_weeks.append(row['week'])
            marker_revenues.append(revenue_match[0])
            
            if row.get('is_pending', False):
                marker_colors.append(C_PENDING)
                marker_opacities.append(0.5)
            else:
                # Color logic from Dashboard: Success if attributed >= 0, else Danger
                color = C_SUCCESS if row['attributed'] >= 0 else C_DANGER
                marker_colors.append(color)
                marker_opacities.append(0.9)
    
    # Add action window markers
    if marker_weeks:
        fig.add_trace(go.Scatter(
            x=marker_weeks,
            y=marker_revenues,
            mode='markers',
            name='Action Windows',
            marker=dict(
                size=12,
                color=marker_colors,
                opacity=marker_opacities,
                symbol='circle',
                line=dict(width=2, color='white')
            ),
            showlegend=True
        ))
    
    # Layout (Matches Dashboard aesthetics but cleaner for export)
    bg_color = 'rgba(30, 41, 59, 1)' if for_export else 'rgba(0,0,0,0)'
    
    fig.update_layout(
        title="",
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(family="Inter, sans-serif", color="#E2E8F0"),
        height=350,
        margin=dict(t=20, b=20, l=40, r=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor='rgba(0,0,0,0)'
        ),
        xaxis=dict(
            showgrid=False,
            gridcolor='rgba(255,255,255,0.05)',
            tickfont=dict(color='#94A3B8')
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.05)',
            tickfont=dict(color='#94A3B8'),
            tickprefix=currency
        )
    )
    
    return fig


class ExecutiveDashboard:
    """
    Clean executive dashboard:
    - 4 KPI cards (Spend, Revenue, ROAS, CVR)
    - 3 Gauges vs targets (Efficiency, Risk, Scale Headroom)
    - Simple performance views
    - Decision impact using pre-calculated metrics
    """
    
    # Performance targets
    TARGETS = {
        'efficiency_score': 80,  # 0-100 scale
        'risk_index': 20,        # % (lower is better)
        'scale_headroom': 40     # % (higher is better)
    }
    
    # Brand colors (Premium SaaS Palette)
    COLORS = {
        'primary': '#06B6D4',    # Cyan
        'success': '#10B981',    # Emerald
        'warning': '#F59E0B',    # Amber
        'danger': '#EF4444',     # Rose
        'purple': '#8B5CF6',     # Violet
        'blue': '#3B82F6',       # Sky Blue
        'teal': '#14B8A6',       # Teal
        'gray': '#64748B',       # Slate 500
        'card_bg': 'rgba(30, 41, 59, 0.6)',
        'border': 'rgba(148, 163, 184, 0.15)'
    }
    
    # Gauge tooltips for user clarity
    GAUGE_TOOLTIPS = {
        'efficiency_score': 'Weighted score: 50% ROAS vs target (default 3.0x), 30% CVR vs benchmark, 20% base stability.',
        'risk_index': 'Percentage of total spend going to targets with 0 orders (bleeders/waste).',
        'scale_headroom': 'Percentage of spend on high-performing targets (ROAS and CVR above median) with room to scale.'
    }
    
    def __init__(self):
        self.client_id = st.session_state.get('active_account_id')
        self.db_manager = st.session_state.get('db_manager')
        self._inject_css()
    
    def _inject_css(self):
        """Premium styling."""
        st.markdown("""
        <style>
        .premium-card {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(148, 163, 184, 0.15);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05);
            transition: all 0.3s ease;
        }
        .premium-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.08);
            border-color: rgba(6, 182, 212, 0.3);
        }
        /* Style Streamlit's native container with border */
        [data-testid="stVerticalBlock"] > div:has(> .panel-header-content) {
            background: rgba(15, 23, 42, 0.6) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 12px !important;
            padding: 0 !important;
        }
        .panel-header-content {
            background: linear-gradient(90deg, rgba(30, 41, 59, 0.9) 0%, rgba(30, 41, 59, 0.4) 100%);
            padding: 14px 20px;
            border-radius: 12px 12px 0 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            margin-bottom: 0;
        }
        .panel-body {
            padding: 16px 20px;
        }
        .kpi-label {
            color: #94a3b8;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
            margin-bottom: 12px;
        }
        .kpi-value {
            color: #F5F5F7;
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 8px;
        }
        .kpi-delta {
            font-size: 0.9rem;
            font-weight: 600;
        }
        .impact-hero {
            text-align: center;
            padding: 32px;
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(6, 182, 212, 0.1) 100%);
            border-radius: 12px;
            margin-bottom: 20px;
            border: 1px solid rgba(16, 185, 129, 0.2);
        }
        .impact-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 16px;
            margin-bottom: 8px;
            background: rgba(30, 41, 59, 0.4);
            border-radius: 8px;
            border-left: 3px solid;
        }
        .impact-row:hover {
            background: rgba(30, 41, 59, 0.6);
            transform: translateX(4px);
            transition: all 0.2s ease;
        }
        .status-excellent { color: #10B981; }
        .status-good { color: #14B8A6; }
        .status-fair { color: #F59E0B; }
        .status-poor { color: #EF4444; }
        </style>
        """, unsafe_allow_html=True)
    

    
    def _hex_to_rgba(self, hex_code: str, opacity: float) -> str:
        """Convert hex color to rgba string."""
        hex_code = hex_code.lstrip('#')
        r = int(hex_code[0:2], 16)
        g = int(hex_code[2:4], 16)
        b = int(hex_code[4:6], 16)
        return f"rgba({r}, {g}, {b}, {opacity})"
    
    def _svg_icon(self, icon_type: str, size: int = 20) -> str:
        """Return SVG icon HTML for chart headers."""
        icons = {
            'target': f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
            'chart': f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" stroke-width="2"><path d="M3 3v18h18"/><path d="M18 9l-5 5-4-4-3 3"/></svg>',
            'pie': f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="#8B5CF6" stroke-width="2"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/></svg>',
            'lightbulb': f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2"><path d="M9 18h6"/><path d="M10 22h4"/><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"/></svg>',
            'timeline': f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="#22C55E" stroke-width="2"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>',
            'table': f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/><line x1="15" y1="3" x2="15" y2="21"/></svg>',
            'money': f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>',
        }
        return icons.get(icon_type, '')
    
    def _chart_header(self, title: str, icon_type: str, subtitle: str = None) -> None:
        """Render a chart header with SVG icon and shaded header background."""
        icon_svg = self._svg_icon(icon_type, 20)
        if subtitle:
            st.markdown(f'''<div class="panel-header-content" style="display: flex; align-items: center; gap: 10px;">{icon_svg}<div><span style="font-size: 1rem; color: #F5F5F7; font-weight: 600;">{title}</span><p style="color: #64748B; font-size: 0.7rem; margin: 2px 0 0 0;">{subtitle}</p></div></div>''', unsafe_allow_html=True)
        else:
            st.markdown(f'''<div class="panel-header-content" style="display: flex; align-items: center; gap: 10px;">{icon_svg}<span style="font-size: 1rem; color: #F5F5F7; font-weight: 600;">{title}</span></div>''', unsafe_allow_html=True)
    
    def run(self):
        """Main entry point."""
        # Header row with date picker
        header_col, picker_col = st.columns([3, 1])
        
        with header_col:
            st.markdown("""
            <h2 style="
                font-family: Inter, sans-serif; 
                font-weight: 700; 
                font-size: 2rem;
                display: flex;
                align-items: center;
                gap: 12px;
                background: linear-gradient(135deg, #F5F5F7 0%, #22D3EE 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 8px;
            ">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" stroke-width="2">
                    <rect x="3" y="3" width="7" height="7" rx="1"/>
                    <rect x="14" y="3" width="7" height="7" rx="1"/>
                    <rect x="14" y="14" width="7" height="7" rx="1"/>
                    <rect x="3" y="14" width="7" height="7" rx="1"/>
                </svg>
                Executive Dashboard
            </h2>
            <p style="color: #94a3b8; font-size: 0.95rem; margin-bottom: 16px;">
                Performance overview with decision impact measurement
            </p>
            """, unsafe_allow_html=True)
        
        with picker_col:
            st.write("")  # Spacer
            # Date range selector
            date_range = st.selectbox(
                "Period",
                options=["Last 7 Days", "Last 14 Days", "Last 30 Days", "Last 60 Days"],
                index=3,  # Default to Last 60 Days
                key="exec_dash_date_range",
                label_visibility="collapsed"
            )
            # Map to days
            days_map = {"Last 7 Days": 7, "Last 14 Days": 14, "Last 30 Days": 30, "Last 60 Days": 60}
            self._selected_days = days_map.get(date_range, 30)
        
        if not self.client_id or not self.db_manager:
            st.warning("⚠️ Please select an account.")
            return
        
        # Fetch data
        with st.spinner("Loading metrics..."):
            data = self._fetch_data()
        
        if data is None:
            st.info("📭 No data available.")
            return
        
        # Render sections
        self._render_kpi_cards(data)
        st.markdown("<br>", unsafe_allow_html=True)
        
        self._render_gauges(data)
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Row 1 (70:30): Performance Quadrants | Revenue by Quadrant (Donut)
        col1, col2 = st.columns([7, 3])
        with col1:
            with st.container(border=True):
                self._render_performance_scatter(data)
        with col2:
            with st.container(border=True):
                self._render_quadrant_donut(data)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Row 2 (30:70): Decision Impact Card | Decision Impact Timeline
        col1, col2 = st.columns([3, 7])
        with col1:
            with st.container(border=True):
                self._render_decision_impact_card(data)
        with col2:
            with st.container(border=True):
                self._render_decision_timeline(data)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Row 3 (70:30): Match Type Table | Efficiency Index (Where The Money Is)
        col1, col2 = st.columns([7, 3])
        with col1:
            with st.container(border=True):
                self._render_match_type_table(data)
        with col2:
            with st.container(border=True):
                self._render_spend_breakdown(data)
    
    def _fetch_data(self, custom_start=None, custom_end=None) -> Optional[Dict[str, Any]]:
        """Fetch all data. Supports custom date range."""
        try:
            # Use cached fetcher
            # Version key ensures cache invalidation on new data upload
            stats_cache_version = "v1_" + str(st.session_state.get('data_upload_timestamp', 'init'))

            # Compute minimal fetch window: cover current + previous period so we
            # don't full-scan all history.  custom_start/end come from ppc_overview
            # (_min_date, _max_date).  For the default case, buffer 2× selected_days.
            if custom_start and custom_end:
                _cs = pd.to_datetime(custom_start)
                _ce = pd.to_datetime(custom_end)
                _dur = (_ce - _cs).days + 1
                _fetch_start = (_cs - timedelta(days=_dur)).date()
            else:
                _selected = getattr(self, '_selected_days', 60)
                _fetch_start = date.today() - timedelta(days=_selected * 2 + 10)

            print(f"[EXEC_DASH] Fetching data for client_id: {self.client_id}")
            df = _fetch_and_process_stats(self.client_id, stats_cache_version, start_date=_fetch_start)
            print(f"[EXEC_DASH] Data fetched: {len(df) if df is not None else 0} rows")

            if df is None or df.empty:
                print(f"[EXEC_DASH] No data found - returning None")
                return None
            
            # Date Range Logic
            if custom_start and custom_end:
                # Use provided custom range
                current_start = pd.to_datetime(custom_start)
                current_end = pd.to_datetime(custom_end)
                duration_days = (current_end - current_start).days + 1
                previous_start = current_start - timedelta(days=duration_days)
                
                # Filter strict range
                df_current = df[(df['Date'] >= current_start) & (df['Date'] <= current_end)].copy()
                df_previous = df[(df['Date'] >= previous_start) & (df['Date'] < current_start)].copy()
                
                print(f"[EXEC_DASH] Custom Range: {current_start.date()} - {current_end.date()}")
            else:
                # Default Logic: Relative to max data date
                selected_days = getattr(self, '_selected_days', 60)
                max_date = df['Date'].max()
                current_start = max_date - timedelta(days=selected_days)
                current_end = max_date # Implicit end
                previous_start = current_start - timedelta(days=selected_days)
                
                df_current = df[df['Date'] >= current_start].copy()
                df_previous = df[(df['Date'] >= previous_start) & (df['Date'] < current_start)].copy()
                print(f"[EXEC_DASH] Relative Range (Last {selected_days}): {current_start.date()} - {current_end.date()}")

                
            # Get decision impact (use pre-calculated metrics from DB)
            # Also fetch the official summary for alignment with Impact Dashboard
            # get_action_impact and get_impact_summary replaced by unified cached fetcher
            
            # Use dynamic cache version to match impact_dashboard.py and force fresh fetch
            cache_version = "v19_perf_" + str(st.session_state.get('data_upload_timestamp', 'init'))
            
            impact_df, impact_summary = _fetch_impact_data(
                self.client_id,
                test_mode=False, 
                before_days=14,
                after_days=14,
                cache_version=cache_version
            )
                
                
            # Initialize for scope
            latest_data_date = None
            
            # === CRITICAL FIX: REPLICATE MATURITY LOGIC ===
            # Getting the maturity right is essential for matching the dash
            if not impact_df.empty and 'action_date' in impact_df.columns:
                # CRITICAL FIX: Get latest date from RAW data, not weekly target_stats
                # target_stats uses week START date (e.g., Jan 12 for Jan 12-17 data)
                # but maturity should be based on ACTUAL latest date (Jan 17)
                if hasattr(self.db_manager, 'get_latest_raw_data_date'):
                    latest_data_date = self.db_manager.get_latest_raw_data_date(self.client_id)
                
                # Fallback to max_date from target_stats if raw date not available
                if not latest_data_date:
                    latest_data_date = df['Date'].max().date()
                
                if latest_data_date:
                    # Calculate maturity exactly as Impact Dashboard does
                    # Ensure imported get_maturity_status is used
                    impact_df['is_mature'] = impact_df['action_date'].apply(
                        lambda d: get_maturity_status(d, latest_data_date, horizon='14D')['is_mature']
                    )
                    impact_df['maturity_status'] = impact_df['action_date'].apply(
                        lambda d: get_maturity_status(d, latest_data_date, horizon='14D')['status']
                    )
            
            # Use ImpactMetrics.from_dataframe() for canonical calculation
            # This matches EXACTLY how Impact Dashboard calculates its number
            canonical_filters = {
                'validated_only': True,  # Match Impact Dashboard default
                'mature_only': True,      # Only mature actions
            }
            try:
                canonical_metrics = ImpactMetrics.from_dataframe(
                    impact_df,
                    filters=canonical_filters,
                    horizon_days=14
                )
            except Exception:
                canonical_metrics = None
            
            # Medians for benchmarking
            medians = {
                'roas': df_current['ROAS'].median(),
                'cvr': df_current['CVR'].median(),
                'cpc': df_current['CPC'].median()
            }
            
            return {
                'df_current': df_current,
                'df_previous': df_previous,
                'impact_df': impact_df,
                'impact_summary': impact_summary,  # Official summary for alignment
                'canonical_metrics': canonical_metrics,  # Canonical calculation
                'medians': medians,
                'date_range': {
                    'start': current_start,
                    # Use actual latest date if adhering to defaults, else use custom end
                    'end': current_end.date() if (custom_end or not latest_data_date) else latest_data_date
                }
            }
        except Exception as e:
            st.error(f"Error: {e}")
            return None
    
    def _render_kpi_cards(self, data: Dict[str, Any]):
        """Render 4 simple KPI cards."""
        df_curr = data['df_current']
        df_prev = data['df_previous']
        
        # Current metrics
        curr_spend = df_curr['Spend'].sum()
        curr_sales = df_curr['Sales'].sum()
        curr_roas = curr_sales / curr_spend if curr_spend > 0 else 0
        curr_cvr = (df_curr['Orders'].sum() / df_curr['Clicks'].sum() * 100) if df_curr['Clicks'].sum() > 0 else 0
        
        # Previous metrics
        prev_spend = df_prev['Spend'].sum()
        prev_sales = df_prev['Sales'].sum()
        prev_roas = prev_sales / prev_spend if prev_spend > 0 else 0
        prev_cvr = (df_prev['Orders'].sum() / df_prev['Clicks'].sum() * 100) if df_prev['Clicks'].sum() > 0 else 0
        
        # Calculate deltas
        def delta(curr, prev):
            return ((curr - prev) / abs(prev) * 100) if prev != 0 else 0
        
        # Date range
        dr = data['date_range']
        # Calculate actual duration (ensure both are same type)
        start = pd.Timestamp(dr['start']) if dr['start'] else pd.Timestamp.now()
        end = pd.Timestamp(dr['end']) if dr['end'] else pd.Timestamp.now()
        duration = (end - start).days
        
        st.markdown(f"""
        <p style='color: #64748b; font-size: 0.85rem; margin-bottom: 20px;'>
            📅 {start.strftime('%b %d')} – {end.strftime('%b %d, %Y')} 
            <span style="color: #475569;">vs. Previous {duration} Days</span>
        </p>
        """, unsafe_allow_html=True)
        
        # Render 4 cards
        cols = st.columns(4)
        
        # Get dynamic currency
        currency = get_account_currency()
        
        cards = [
            ("SPEND", f"{currency} {curr_spend/1000:.0f}K", delta(curr_spend, prev_spend)),
            ("REVENUE", f"{currency} {curr_sales/1000:.0f}K", delta(curr_sales, prev_sales)),
            ("ROAS", f"{curr_roas:.2f}x", delta(curr_roas, prev_roas)),
            ("CVR", f"{curr_cvr:.2f}%", delta(curr_cvr, prev_cvr))
        ]
        
        for col, (label, value, delta_pct) in zip(cols, cards):
            delta_color = self.COLORS['success'] if delta_pct > 0 else self.COLORS['danger'] if delta_pct < 0 else self.COLORS['gray']
            delta_icon = '↑' if delta_pct > 0 else '↓' if delta_pct < 0 else '→'
            
            col.markdown(f"""
            <div class="premium-card">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{value}</div>
                <div class="kpi-delta" style="color: {delta_color};">
                    {delta_icon} {abs(delta_pct):.1f}%
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # === SECONDARY METRICS (Expandable Section) ===
        st.markdown("<br>", unsafe_allow_html=True)  # Gap before expander
        
        # Calculate secondary metrics
        total_orders = df_curr['Orders'].sum()
        total_clicks = df_curr['Clicks'].sum()
        total_impr = df_curr['Impressions'].sum()
        total_acos = (curr_spend / curr_sales * 100) if curr_sales > 0 else 0
        total_cpc = (curr_spend / total_clicks) if total_clicks > 0 else 0
        
        # Prev for deltas
        prev_orders = df_prev['Orders'].sum()
        prev_clicks = df_prev['Clicks'].sum()
        prev_acos = (prev_spend / prev_sales * 100) if prev_sales > 0 else 0
        prev_cpc = (prev_spend / prev_clicks) if prev_clicks > 0 else 0
        
        with st.expander("View More Metrics", expanded=False):
            sc1, sc2, sc3, sc4, sc5 = st.columns(5)
            
            # Orders
            orders_delta = delta(total_orders, prev_orders)
            orders_color = self.COLORS['success'] if orders_delta > 0 else self.COLORS['danger'] if orders_delta < 0 else self.COLORS['gray']
            orders_icon = '↑' if orders_delta > 0 else '↓' if orders_delta < 0 else '→'
            sc1.markdown(f"""
            <div class="premium-card">
                <div class="kpi-label">🛒 ORDERS</div>
                <div class="kpi-value">{total_orders:,.0f}</div>
                <div class="kpi-delta" style="color: {orders_color};">{orders_icon} {abs(orders_delta):.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
            
            # ACOS (lower is better, so inverted color)
            acos_delta = delta(total_acos, prev_acos)
            acos_color = self.COLORS['danger'] if acos_delta > 0 else self.COLORS['success'] if acos_delta < 0 else self.COLORS['gray']
            acos_icon = '↑' if acos_delta > 0 else '↓' if acos_delta < 0 else '→'
            sc2.markdown(f"""
            <div class="premium-card">
                <div class="kpi-label">⭕ ACOS</div>
                <div class="kpi-value">{total_acos:.2f}%</div>
                <div class="kpi-delta" style="color: {acos_color};">{acos_icon} {abs(acos_delta):.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Impressions (no delta)
            sc3.markdown(f"""
            <div class="premium-card">
                <div class="kpi-label">👁️ IMPRESSIONS</div>
                <div class="kpi-value">{total_impr:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Clicks (no delta)  
            sc4.markdown(f"""
            <div class="premium-card">
                <div class="kpi-label">🖱️ CLICKS</div>
                <div class="kpi-value">{total_clicks:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # CPC
            cpc_delta = delta(total_cpc, prev_cpc)
            cpc_color = self.COLORS['danger'] if cpc_delta > 0 else self.COLORS['success'] if cpc_delta < 0 else self.COLORS['gray']
            cpc_icon = '↑' if cpc_delta > 0 else '↓' if cpc_delta < 0 else '→'
            sc5.markdown(f"""
            <div class="premium-card">
                <div class="kpi-label">💵 CPC</div>
                <div class="kpi-value">{currency} {total_cpc:.2f}</div>
                <div class="kpi-delta" style="color: {cpc_color};">{cpc_icon} {abs(cpc_delta):.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
    
    def _render_gauges(self, data: Dict[str, Any]):
        """Render 3 CFO-level gauge charts: Account Health, Decision ROI, Spend Efficiency."""
        df_curr = data['df_current']
        canonical_metrics = data.get('canonical_metrics')  # ImpactMetrics instance
        impact_df = data.get('impact_df')
        
        # Current aggregates
        curr_spend = df_curr['Spend'].sum()
        curr_sales = df_curr['Sales'].sum()
        total_orders = df_curr['Orders'].sum()
        total_clicks = df_curr['Clicks'].sum()
        curr_roas = curr_sales / curr_spend if curr_spend > 0 else 0
        curr_cvr = (total_orders / total_clicks * 100) if total_clicks > 0 else 0
        
        # ============================================================
        # 1. ACCOUNT HEALTH (0-100 from Decision Cockpit)
        # ============================================================
        # Pull from the same source as Decision Cockpit (report_card.py)
        account_health = get_account_health_score(self.client_id)
        if account_health is None:
            # Fallback to local calculation if DB unavailable
            target_roas = st.session_state.get('target_roas', 3.0)
            target_cvr = 5.0
            roas_score = min(50, (curr_roas / target_roas) * 50) if target_roas > 0 else 25
            cvr_score = min(30, (curr_cvr / target_cvr) * 30) if target_cvr > 0 else 15
            account_health = roas_score + cvr_score + 20
        
        # ============================================================
        # 2. DECISION ROI (% return on optimizer actions)
        # ============================================================
        # Formula: Net Decision Impact / Managed Spend × 100
        if canonical_metrics and canonical_metrics.attributed_impact != 0:
            net_impact = canonical_metrics.attributed_impact
            # Get managed spend from impact_df
            if impact_df is not None and 'observed_after_spend' in impact_df.columns:
                managed_spend = impact_df['observed_after_spend'].sum()
            else:
                managed_spend = canonical_metrics.total_spend
            
            decision_roi = (net_impact / managed_spend * 100) if managed_spend > 0 else 0
        else:
            decision_roi = 0
        
        # Clamp to reasonable display range (-50% to 50%)
        decision_roi_display = max(-50, min(50, decision_roi))
        
        # ============================================================
        # 3. SPEND EFFICIENCY (% of spend in Ad Groups with ROAS >= 2.5)
        # ============================================================
        # Aggregate at Ad Group level first (CFO-level view)
        min_roas_threshold = 2.5
        
        if 'Ad Group Name' in df_curr.columns:
            # Aggregate by Ad Group
            adgroup_agg = df_curr.groupby('Ad Group Name').agg({
                'Spend': 'sum',
                'Sales': 'sum'
            }).reset_index()
            adgroup_agg['ROAS'] = (adgroup_agg['Sales'] / adgroup_agg['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
            
            efficient_spend = adgroup_agg[adgroup_agg['ROAS'] >= min_roas_threshold]['Spend'].sum()
        else:
            # Fallback to target level if Ad Group not available
            if 'ROAS' not in df_curr.columns:
                df_curr = df_curr.copy()
                df_curr['ROAS'] = (df_curr['Sales'] / df_curr['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
            efficient_spend = df_curr[df_curr['ROAS'] >= min_roas_threshold]['Spend'].sum()
        
        spend_efficiency = (efficient_spend / curr_spend * 100) if curr_spend > 0 else 0
        
        # ============================================================
        # RENDER GAUGES
        # ============================================================
        # ============================================================
        # RENDER GAUGES
        # ============================================================
        cols = st.columns(3)
        
        with cols[0]:
            self._render_gauge(
                "Account Health",
                account_health,
                80,  # Target: 80 points
                0, 100,
                "pts",
                [
                    (0, 40, self.COLORS['danger']),      # Rose (Poor)
                    (40, 60, self.COLORS['warning']),    # Amber (Fair)
                    (60, 80, self.COLORS['teal']),       # Teal (Good)
                    (80, 100, self.COLORS['success'])    # Emerald (Excellent)
                ],
                tooltip=self.GAUGE_TOOLTIPS['efficiency_score']
            )
        
        with cols[1]:
            self._render_gauge(
                "Decision ROI",
                decision_roi_display,
                5,  # Target: 5% ROI
                -50, 50,
                "%",
                [
                    (-50, 0, self.COLORS['danger']),     # Rose (Negative)
                    (0, 10, self.COLORS['warning']),     # Amber (Low positive)
                    (10, 30, self.COLORS['teal']),       # Teal (Good)
                    (30, 50, self.COLORS['success'])     # Emerald (Excellent)
                ],
                tooltip="Net Decision Impact ÷ Managed Spend. Shows return on optimizer actions."
            )
        
        with cols[2]:
            self._render_gauge(
                "Spend Efficiency",
                spend_efficiency,
                50,  # Target: 50%
                0, 100,
                "%",
                [
                    (0, 30, self.COLORS['danger']),      # Rose (Poor)
                    (30, 50, self.COLORS['warning']),    # Amber (Fair)
                    (50, 70, self.COLORS['teal']),       # Teal (Good)
                    (70, 100, self.COLORS['success'])    # Emerald (Excellent)
                ],
                tooltip=f"Percentage of spend in Ad Groups with ROAS ≥ {min_roas_threshold}x"
            )
    
    def _render_gauge(
        self,
        title: str,
        value: float,
        target: float,
        min_val: float,
        max_val: float,
        suffix: str,
        color_zones: list,
        inverse: bool = False,
        tooltip: str = ""
    ):
        """Render single gauge chart."""
        # Determine status and bar_color based on which color zone the value falls into
        bar_color = self.COLORS['warning']  # Default
        zone_type = 'warning'
        
        for zone_start, zone_end, zone_color in color_zones:
            if zone_start <= value <= zone_end:
                bar_color = zone_color
                # Determine zone type based on color
                if zone_color == self.COLORS['success']:
                    zone_type = 'excellent'
                elif zone_color == self.COLORS['teal']:
                    zone_type = 'good'
                elif zone_color == self.COLORS['warning']:
                    zone_type = 'fair'
                else:
                    zone_type = 'poor'
                break
        
        # Set status label
        if zone_type == 'excellent':
            status = "🌟 Excellent"
            status_class = "status-excellent"
        elif zone_type == 'good':
            status = "✅ Good"
            status_class = "status-good"
        elif zone_type == 'fair':
            status = "⚠️ Fair"
            status_class = "status-fair"
        else:
            status = "🔴 Poor"
            status_class = "status-poor"
            
        if inverse:
             # Invert logic if needed (though simple mapping above usually handles it)
             pass
        
        # Create gauge
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=value,
            number={
                'suffix': suffix,
                'font': {'size': 32, 'color': '#F5F5F7', 'family': 'Inter, sans-serif'}
            },
            title={
                'text': title,
                'font': {'size': 14, 'color': '#94a3b8', 'family': 'Inter, sans-serif'}
            },
            gauge={
                'axis': {
                    'range': [min_val, max_val],
                    'tickwidth': 1,
                    'tickcolor': "#64748b",
                    'tickfont': {'size': 10, 'color': '#64748b'}
                },
                'bar': {'color': bar_color, 'thickness': 0.55},  # Dynamic bar color
                'bgcolor': "rgba(30, 41, 59, 0.3)",
                'borderwidth': 2,
                'bordercolor': "rgba(255, 255, 255, 0.1)",
                'steps': [],
                'threshold': {
                    'line': {'color': self.COLORS['primary'], 'width': 3},
                    'thickness': 0.75,
                    'value': target
                }
            }
        ))
        
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font={'color': "#F5F5F7", 'family': "Inter, sans-serif"},
            height=180,
            margin=dict(l=15, r=15, t=50, b=5)
        )
        
        st.plotly_chart(fig, width='stretch')
        
        # Status below gauge with tooltip
        tooltip_html = f'<span title="{tooltip}" style="cursor: help; border-bottom: 1px dotted #64748b;">ⓘ</span>' if tooltip else ''
        st.markdown(f"""
        <div style="text-align: center; margin-top: -10px; margin-bottom: 8px;">
            <div class="{status_class}" style="font-size: 0.9rem; font-weight: 600; margin-bottom: 2px;">
                {status}
            </div>
            <div style="color: #64748b; font-size: 0.75rem;">
                Target: {target}{suffix} {tooltip_html}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    def _render_performance_scatter(self, data: Dict[str, Any]):
        """ROAS vs CVR scatter with quadrant gradient fills and capped outliers."""
        self._chart_header("Performance Quadrants", "target")
        
        df = data['df_current']
        medians = data['medians']
        
        # Aggregate by campaign
        camp_perf = df.groupby('Campaign Name').agg({
            'Sales': 'sum',
            'Spend': 'sum',
            'Clicks': 'sum',
            'Orders': 'sum'
        }).reset_index()
        
        camp_perf['ROAS'] = (camp_perf['Sales'] / camp_perf['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
        camp_perf['CVR'] = (camp_perf['Orders'] / camp_perf['Clicks'] * 100).replace([np.inf, -np.inf], 0).fillna(0)
        camp_perf = camp_perf[camp_perf['Spend'] > 10]
        
        if camp_perf.empty:
            st.info("Not enough data.")
            return
        
        # Use WEIGHTED AVERAGE for quadrant dividers (total metrics, not mean of ratios)
        total_spend = camp_perf['Spend'].sum()
        total_sales = camp_perf['Sales'].sum()
        total_clicks = camp_perf['Clicks'].sum()
        total_orders = camp_perf['Orders'].sum()

        avg_roas = (total_sales / total_spend) if total_spend > 0 else 0
        avg_cvr = (total_orders / total_clicks * 100) if total_clicks > 0 else 0

        # Ensure values are never 0 (fallback to reasonable defaults)
        if avg_roas <= 0:
            avg_roas = 3.0  # Default 3x ROAS
        if avg_cvr <= 0:
            avg_cvr = 5.0   # Default 5% CVR
        
        # Cap outliers for better visualization
        roas_cap = avg_roas * 3
        cvr_cap = avg_cvr * 3
        camp_perf['ROAS_display'] = camp_perf['ROAS'].clip(upper=roas_cap)
        camp_perf['CVR_display'] = camp_perf['CVR'].clip(upper=cvr_cap)
        
        # Quadrant classification — logic lives in ppc_classifications.py
        _QUAD_LABEL = {
            "stars": "Stars", "scale_potential": "Scale Potential",
            "profit_potential": "Profit Potential", "cut": "Cut",
        }
        camp_perf['Zone'] = camp_perf.apply(
            lambda r: _QUAD_LABEL[_classify_quadrant_shared(r['ROAS'], r['CVR'], avg_roas, avg_cvr)],
            axis=1,
        )
        
        # Create base figure
        fig = go.Figure()
        
        # Chart bounds
        x_min, x_max = 0, cvr_cap
        y_min, y_max = 0, roas_cap
        avg_x, avg_y = avg_cvr, avg_roas
        
        # Add quadrant labels only (NO shading)
        fig.add_annotation(x=avg_x/2, y=y_max*0.9, text="Scale Potential", showarrow=False,
                          font=dict(size=12, color='rgba(255,255,255,0.4)'))
        fig.add_annotation(x=(avg_x + x_max)/2, y=y_max*0.9, text="Stars", showarrow=False,
                          font=dict(size=12, color='rgba(6, 182, 212, 0.6)'))
        fig.add_annotation(x=avg_x/2, y=y_min + (avg_y * 0.1), text="Cut", showarrow=False,
                          font=dict(size=12, color='rgba(255,255,255,0.3)'))
        fig.add_annotation(x=(avg_x + x_max)/2, y=y_min + (avg_y * 0.1), text="Profit Potential", showarrow=False,
                          font=dict(size=12, color='rgba(255,255,255,0.3)'))
        
        # Zone colors for scatter points - Premium Palette
        zone_colors = {
            'Stars': self.COLORS['success'],           # Emerald
            'Scale Potential': self.COLORS['warning'], # Amber
            'Profit Potential': self.COLORS['primary'], # Cyan
            'Cut': self.COLORS['danger']               # Rose
        }
        
        # Add scatter points by zone
        for zone in ['Cut', 'Profit Potential', 'Scale Potential', 'Stars']:
            zone_data = camp_perf[camp_perf['Zone'] == zone]
            if not zone_data.empty:
                fig.add_trace(go.Scatter(
                    x=zone_data['CVR_display'],
                    y=zone_data['ROAS_display'],
                    mode='markers',
                    name=zone,
                    marker=dict(
                        size=np.sqrt(zone_data['Spend']) / 3 + 8,
                        color=zone_colors[zone],
                        opacity=0.9,
                        line=dict(width=1, color='rgba(255,255,255,0.5)')
                    ),
                    text=zone_data['Campaign Name'],
                    hovertemplate='<b>%{text}</b><br>CVR: %{x:.2f}%<br>ROAS: %{y:.2f}x<br><extra></extra>'
                ))
        
        # Add average divider lines (reference lines)
        fig.add_hline(y=avg_roas, line_dash="dash", line_color=self.COLORS['gray'], line_width=1.5)
        fig.add_vline(x=avg_cvr, line_dash="dash", line_color=self.COLORS['gray'], line_width=1.5)
        
        # Add average labels
        fig.add_annotation(x=x_min, y=avg_roas, text=f"Avg ROAS: {avg_roas:.1f}x",
                          showarrow=False, xanchor='left', font=dict(size=9, color='rgba(255,255,255,0.5)'))
        fig.add_annotation(x=avg_cvr, y=y_min, text=f"Avg CVR: {avg_cvr:.1f}%",
                          showarrow=False, yanchor='bottom', font=dict(size=9, color='rgba(255,255,255,0.5)'))
        
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=480,  # Extended to match Decision Impact section
            margin=dict(l=10, r=10, t=10, b=30),
            xaxis=dict(
                title="CVR (%)", 
                showgrid=False, 
                range=[x_min, x_max],
                zeroline=False
            ),
            yaxis=dict(
                title="ROAS", 
                showgrid=False, 
                range=[y_min, y_max],
                zeroline=False
            ),
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
        )
        
        st.plotly_chart(fig, width='stretch')
    


    def _render_campaign_trends(self, data: Dict[str, Any]):
        """Render dynamic campaign trends (Sales vs ACOS) with dropdowns."""
        st.markdown("### 📈 Campaign Trend Analysis")
        
        df = data['df_current'].copy()
        if df.empty or 'Date' not in df.columns:
            st.info("No data available for trends.")
            return

        # Use full dataframe for trends if columns missing in df_current, or just ensure columns exist
        # If Impression/Orders/Clicks are missing, fill 0
        for col in ['Impressions', 'Orders', 'Clicks']:
            if col not in df.columns:
                df[col] = 0

        # Layout: Controls (Inside the column)
        c1, c2, c3 = st.columns([1, 1, 1])
        time_frame = c1.selectbox("Timeframe", ["Weekly", "Monthly", "Quarterly", "Yearly"], index=0, key="exec_trend_time")
        metric_bar = c2.selectbox("Bar Metric", ["Sales", "Spend", "Orders", "Clicks", "Impressions"], index=0, key="exec_trend_bar")
        metric_line = c3.selectbox("Line Metric", ["ACOS", "ROAS", "CPC", "CTR", "CVR"], index=0, key="exec_trend_line")
        
        # Resample Data based on selection
        trend_df = df.set_index('Date').sort_index()
        
        # Resampling Rules: W=Weekly, M=Monthly, Q=Quarterly, Y=Yearly
        rule_map = {"Weekly": 'W-MON', "Monthly": 'M', "Quarterly": 'Q', "Yearly": 'Y'}
        rule = rule_map.get(time_frame, 'W-MON')
        
        resampled = trend_df.resample(rule).agg({
            'Spend': 'sum', 'Sales': 'sum', 'Orders': 'sum', 
            'Clicks': 'sum', 'Impressions': 'sum'
        }).reset_index()
        
        # Recalculate rates
        resampled['ROAS'] = np.where(resampled['Spend'] > 0, resampled['Sales'] / resampled['Spend'], 0)
        resampled['ACOS'] = np.where(resampled['Sales'] > 0, resampled['Spend'] / resampled['Sales'] * 100, 0)
        resampled['CPC'] = np.where(resampled['Clicks'] > 0, resampled['Spend'] / resampled['Clicks'], 0)
        resampled['CTR'] = np.where(resampled['Impressions'] > 0, resampled['Clicks'] / resampled['Impressions'] * 100, 0)
        resampled['CVR'] = np.where(resampled['Clicks'] > 0, resampled['Orders'] / resampled['Clicks'] * 100, 0)
        
        # Plot Trend
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Bar Chart
        fig.add_trace(go.Bar(
            x=resampled['Date'], 
            y=resampled[metric_bar], 
            name=metric_bar,
            marker_color='#5B556F', # Brand Purple
            marker_line_width=0,
            opacity=0.9,
            hovertemplate=f'{metric_bar}: %{{y:,.1f}}<extra></extra>'
        ), secondary_y=False)
        
        # Line Chart (Dual Axis)
        fig.add_trace(go.Scatter(
            x=resampled['Date'], 
            y=resampled[metric_line], 
            name=metric_line,
            mode='lines+markers',
            line=dict(color='#22d3ee', width=3), # Accent Cyan
            marker=dict(size=6, color='#22d3ee', line=dict(width=2, color='#0F172A')),
            hovertemplate=f'{metric_line}: %{{y:,.2f}}<extra></extra>'
        ), secondary_y=True)
        
        # Get dynamic template
        chart_template = ThemeManager.get_chart_template()
        is_dark = st.session_state.get('theme_mode', 'dark') == 'dark'
        bg_color = 'rgba(0,0,0,0)' 
        text_color = '#f3f4f6' if is_dark else '#1f2937'
        
        fig.update_layout(
            title=dict(text=f"{metric_bar} vs {metric_line} ({time_frame})", font=dict(color=text_color)),
            hovermode='x unified',
            template=chart_template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font=dict(color=text_color),
            height=400,  # Slightly taller to accommodate controls
            margin=dict(l=0, r=0, t=40, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        # Y-Axis 1
        fig.update_yaxes(
            title=dict(text=metric_bar, font=dict(color=text_color)), 
            tickfont=dict(color=text_color), 
            showgrid=False,
            zeroline=False,
            secondary_y=False
        )
        
        # Y-Axis 2
        fig.update_yaxes(
            title=dict(text=metric_line, font=dict(color=text_color)), 
            tickfont=dict(color=text_color), 
            showgrid=True,
            gridcolor='rgba(255,255,255,0.05)',
            secondary_y=True,
            zeroline=False
        )
        
        st.plotly_chart(fig, width='stretch')

    def _render_spend_breakdown(self, data: Dict[str, Any]):
        """Render 'Where The Money Is' spend breakdown with Efficiency Ratio."""
        self._chart_header("Where The Money Is", "money", "Efficiency Index = Revenue % / Spend %")
        
        df = data['df_current'].copy()
        if df.empty:
            st.info("No data available.")
            return

        # Use pre-calculated 'Refined Match Type' if available, otherwise fallback
        group_col = 'Refined Match Type' if 'Refined Match Type' in df.columns else 'Match Type'
        
        # Aggregate spend and sales
        breakdown = df.groupby(group_col).agg({'Spend': 'sum', 'Sales': 'sum'}).reset_index()
        total_spend = breakdown['Spend'].sum()
        total_sales = breakdown['Sales'].sum()
        
        # Calculate Percentages
        breakdown['Pct_Spend'] = (breakdown['Spend'] / total_spend * 100).fillna(0)
        breakdown['Pct_Sales'] = (breakdown['Sales'] / total_sales * 100).fillna(0)
        
        # Calculate Efficiency Ratio (Revenue % / Spend %)
        # Avoid division by zero
        breakdown['Efficiency_Ratio'] = breakdown.apply(
            lambda x: x['Pct_Sales'] / x['Pct_Spend'] if x['Pct_Spend'] > 0 else 0, axis=1
        )
        
        # Filter out empty rows (Spend = 0) before sorting
        breakdown = breakdown[breakdown['Spend'] > 0]
        
        # Sort by Efficiency Ratio desc (visually top-down in Plotly requires ascending=True)
        breakdown = breakdown.sort_values('Efficiency_Ratio', ascending=True)
        
        # Determine Color Score and Label (Premium Palette)
        def get_status(ratio):
            if ratio >= 1.0:
                return "Amplifier", self.COLORS['success'] # Emerald
            elif 0.75 <= ratio < 1.0:
                return "Balanced", self.COLORS['teal']     # Teal
            elif 0.5 <= ratio < 0.75:
                # Add intermediary state for better granularity
                return "Review", self.COLORS['warning']    # Amber
            else:
                return "Drag", self.COLORS['danger']       # Rose
        
        breakdown['Status_Label'] = breakdown['Efficiency_Ratio'].apply(lambda x: get_status(x)[0])
        breakdown['Color'] = breakdown['Efficiency_Ratio'].apply(lambda x: get_status(x)[1])
        
        # Map nice display names for types
        type_names = {
            'AUTO': 'Auto', 'BROAD': 'Broad', 'PHRASE': 'Phrase', 
            'EXACT': 'Exact', 'PT': 'Product', 'CATEGORY': 'Category', 'OTHER': 'Other'
        }
        breakdown['DisplayName'] = breakdown[group_col].apply(lambda x: type_names.get(str(x).upper(), str(x).title()))
        
        # Horizontal Bar Chart
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            y=breakdown['DisplayName'],
            x=breakdown['Efficiency_Ratio'],
            orientation='h',
            marker_color=breakdown['Color'],
            text=breakdown['Efficiency_Ratio'].apply(lambda x: f"{x:.2f}x"),
            textposition='inside',
            insidetextanchor='end',
            textfont=dict(color='white', weight='bold'),
            hovertemplate=(
                "<b>%{y}</b><br>" +
                "Efficiency: <b>%{x:.2f}x</b><br>" +
                "Spend Share: %{customdata[0]:.1f}%<br>" +
                "Rev Share: %{customdata[1]:.1f}%<br>" +
                "<extra></extra>"
            ),
            customdata=breakdown[['Pct_Spend', 'Pct_Sales']]
        ))
        
        # Add Reference Line at 1.0 (Parity)
        fig.add_vline(x=1.0, line_width=1, line_dash="dash", line_color=self.COLORS['gray'], annotation_text="Parity (1.0)", annotation_position="top right")

        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=450,
            margin=dict(l=10, r=10, t=30, b=10),
            xaxis=dict(
                showgrid=True, 
                gridcolor='rgba(255,255,255,0.1)',
                title=dict(text="Efficiency Ratio (Rev % / Spend %)", font=dict(size=10, color='gray')),
                zeroline=False
            ),
            yaxis=dict(showgrid=False, tickfont=dict(color='rgba(255,255,255,0.8)')),
            uniformtext=dict(mode='hide', minsize=10)
        )
        
        st.plotly_chart(fig, width='stretch')
        
        # Add legend/explanation for the ratio
        # Add legend/explanation for the ratio
        st.caption(
            f"Efficiency Index: <span style='color:{self.COLORS['success']}'>Amplifier (>1.0)</span> • "
            f"<span style='color:{self.COLORS['teal']}'>Balanced (0.75-1.0)</span> • "
            f"<span style='color:{self.COLORS['warning']}'>Review (0.5-0.75)</span> • "
            f"<span style='color:{self.COLORS['danger']}'>Drag (<0.5)</span>", 
            unsafe_allow_html=True
        )

    def _render_quadrant_donut(self, data: Dict[str, Any]):
        """Render Revenue by Quadrant as a Donut Chart."""
        self._chart_header("Revenue by Quadrant", "pie")
        
        df = data['df_current']
        if df.empty:
            st.info("No data available.")
            return
        
        # Reuse aggregation logic from _render_quadrant_waterfall
        camp_perf = df.groupby('Campaign Name').agg({
            'Sales': 'sum', 'Spend': 'sum', 'Clicks': 'sum', 'Orders': 'sum'
        }).reset_index()
        
        camp_perf['ROAS'] = (camp_perf['Sales'] / camp_perf['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
        camp_perf['CVR'] = (camp_perf['Orders'] / camp_perf['Clicks'] * 100).replace([np.inf, -np.inf], 0).fillna(0)
        
        subset = camp_perf[camp_perf['Spend'] > 10]
        
        # Use WEIGHTED AVERAGE for quadrant dividers (total metrics, not mean of ratios)
        if not subset.empty:
            total_spend = subset['Spend'].sum()
            total_sales = subset['Sales'].sum()
            total_clicks = subset['Clicks'].sum()
            total_orders = subset['Orders'].sum()
            avg_roas = (total_sales / total_spend) if total_spend > 0 else 3.0
            avg_cvr = (total_orders / total_clicks * 100) if total_clicks > 0 else 5.0
        else:
            avg_roas = 3.0
            avg_cvr = 5.0

        # Ensure values are reasonable (same fallback as scatter)
        if avg_roas <= 0: avg_roas = 3.0
        if avg_cvr <= 0: avg_cvr = 5.0
        
        # Classify quadrants - SAME LABELS AS SCATTER (logic in ppc_classifications.py)
        _QUAD_LABEL = {
            "stars": "Stars", "scale_potential": "Scale Potential",
            "profit_potential": "Profit Potential", "cut": "Cut",
        }
        camp_perf['Quadrant'] = camp_perf.apply(
            lambda r: _QUAD_LABEL[_classify_quadrant_shared(r['ROAS'], r['CVR'], avg_roas, avg_cvr)],
            axis=1,
        )
        
        # Aggregate by quadrant
        quad_sales = camp_perf.groupby('Quadrant')['Sales'].sum().reset_index()
        
        colors = {
            'Stars': self.COLORS['success'],           # Emerald
            'Scale Potential': self.COLORS['warning'], # Amber
            'Profit Potential': self.COLORS['primary'], # Cyan
            'Cut': self.COLORS['danger']               # Rose
        }
        quad_sales['Color'] = quad_sales['Quadrant'].map(colors)
        
        fig = go.Figure(data=[go.Pie(
            labels=quad_sales['Quadrant'],
            values=quad_sales['Sales'],
            hole=0.5,
            marker_colors=[colors.get(q, '#64748B') for q in quad_sales['Quadrant']],
            textposition='inside',
            textinfo='percent+label',
            textfont=dict(size=11, color='white')
        )])
        
        currency = get_account_currency()
        total = quad_sales['Sales'].sum()
        
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=350,
            margin=dict(l=10, r=10, t=20, b=10),
            showlegend=False,
            annotations=[dict(
                text=f"<b>{currency} {total:,.0f}</b>",
                x=0.5, y=0.5,
                font_size=14, font_color='#F5F5F7',
                showarrow=False
            )]
        )
        
        st.plotly_chart(fig, width='stretch')

    def _render_match_type_table(self, data: Dict[str, Any]):
        """Render Match Type breakdown table (from Performance Overview)."""
        self._chart_header("Performance by Match Type", "table")
        
        df = data['df_current'].copy()
        if df.empty:
            st.info("No data available.")
            return
        
        # Use Refined Match Type if available
        group_col = 'Refined Match Type' if 'Refined Match Type' in df.columns else 'Match Type'
        
        # Aggregate (same as performance_snapshot.py lines 743-755)
        agg_cols = {'Spend': 'sum', 'Sales': 'sum', 'Orders': 'sum', 'Clicks': 'sum', 'Impressions': 'sum'}
        grouped = df.groupby(group_col).agg(agg_cols).reset_index()
        
        # Calculate metrics
        grouped['ACOS'] = np.where(grouped['Sales'] > 0, grouped['Spend'] / grouped['Sales'] * 100, 0)
        grouped['ROAS'] = np.where(grouped['Spend'] > 0, grouped['Sales'] / grouped['Spend'], 0)
        grouped['CTR'] = np.where(grouped['Impressions'] > 0, grouped['Clicks'] / grouped['Impressions'] * 100, 0)
        grouped['CVR'] = np.where(grouped['Clicks'] > 0, grouped['Orders'] / grouped['Clicks'] * 100, 0)
        grouped['CPC'] = np.where(grouped['Clicks'] > 0, grouped['Spend'] / grouped['Clicks'], 0)
        
        # Sort by Spend descending and remove empty rows
        grouped = grouped[grouped['Spend'] > 0]  # Filter out empty rows
        grouped = grouped.sort_values('Spend', ascending=False)
        
        # Display DataFrame with formatting
        currency = get_account_currency()
        st.dataframe(
            grouped,
            width='stretch',
            column_config={
                group_col: st.column_config.TextColumn("Match Type"),
                'Spend': st.column_config.NumberColumn(f"Spend", format=f"{currency} %.2f"),
                'Sales': st.column_config.NumberColumn(f"Sales", format=f"{currency} %.2f"),
                'Orders': st.column_config.NumberColumn("Orders", format="%d"),
                'Clicks': st.column_config.NumberColumn("Clicks", format="%d"),
                'Impressions': st.column_config.NumberColumn("Impressions", format="%d"),
                'ACOS': st.column_config.NumberColumn("ACOS", format="%.2f%%"),
                'ROAS': st.column_config.NumberColumn("ROAS", format="%.2fx"),
                'CTR': st.column_config.NumberColumn("CTR", format="%.2f%%"),
                'CVR': st.column_config.NumberColumn("CVR", format="%.2f%%"),
                'CPC': st.column_config.NumberColumn("CPC", format=f"{currency} %.2f"),
            },
            hide_index=True,
            height=350
        )


    
    def _render_quadrant_waterfall(self, data: Dict[str, Any]):
        """Render 'Revenue Distribution by Performance Quadrant' waterfall."""
        st.markdown("### 📊 Revenue Distribution by Performance Quadrant")
        
        df = data['df_current']
        if df.empty:
            st.info("No data available.")
            return

        # 1. Reuse EXACT Aggregation Logic from Scatter
        camp_perf = df.groupby('Campaign Name').agg({
            'Sales': 'sum', 'Spend': 'sum', 'Clicks': 'sum', 'Orders': 'sum'
        }).reset_index()
        
        camp_perf['ROAS'] = (camp_perf['Sales'] / camp_perf['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
        camp_perf['CVR'] = (camp_perf['Orders'] / camp_perf['Clicks'] * 100).replace([np.inf, -np.inf], 0).fillna(0)
        
        # 2. Reuse Threshold Logic - WEIGHTED AVERAGE (to match scatter 1:1)
        subset = camp_perf[camp_perf['Spend'] > 10]
        if subset.empty:
            avg_roas = 3.0
            avg_cvr = 5.0
        else:
            total_spend = subset['Spend'].sum()
            total_sales = subset['Sales'].sum()
            total_clicks = subset['Clicks'].sum()
            total_orders = subset['Orders'].sum()
            avg_roas = (total_sales / total_spend) if total_spend > 0 else 3.0
            avg_cvr = (total_orders / total_clicks * 100) if total_clicks > 0 else 5.0
            # Fallbacks
            if avg_roas <= 0: avg_roas = 3.0
            if avg_cvr <= 0: avg_cvr = 5.0
            
        # 3. Classify ALL campaigns into Quadrants (logic in ppc_classifications.py)
        _QUAD_LABEL = {
            "stars": "Stars", "scale_potential": "Scale Potential",
            "profit_potential": "Profit Potential", "cut": "Cut",
        }
        camp_perf['Zone'] = camp_perf.apply(
            lambda r: _QUAD_LABEL[_classify_quadrant_shared(r['ROAS'], r['CVR'], avg_roas, avg_cvr)],
            axis=1,
        )
        
        # 4. Aggregate Revenue by Zone
        zone_metrics = camp_perf.groupby('Zone')['Sales'].sum().reset_index()
        total_revenue = zone_metrics['Sales'].sum()
        
        # Ensure order: Stars, Scale Potential, Profit Potential, Cut
        custom_order = {'Stars': 0, 'Scale Potential': 1, 'Profit Potential': 2, 'Cut': 3}
        zone_metrics['Order'] = zone_metrics['Zone'].map(custom_order)
        zone_metrics = zone_metrics.sort_values('Order')
        
        # 5. Visualization (Waterfall)
        zones = zone_metrics['Zone'].tolist()
        values = zone_metrics['Sales'].tolist()
        
        # Append Total
        x_data = zones + ["Total"]
        y_data = values + [0] # 0 for total column
        measures = ["relative"] * len(zones) + ["total"]
        text_labels = [f"${v:,.0f}" for v in values] + [f"${total_revenue:,.0f}"]
        
        # Colors from Scatter
        zone_colors = {
            'Stars': '#22C55E',      # Green
            'Scale Potential': '#F59E0B',   # Orange 
            'Profit Potential': '#F59E0B',   # Orange
            'Cut': '#EF4444'         # Red
        }
        colors = [zone_colors.get(z, '#94a3b8') for z in zones] + [self.COLORS['slate']]
        
        fig = go.Figure(go.Bar(
            name="Revenue",
            x=x_data,
            y=values + [total_revenue], # Explicitly set Total value for Bar chart
            text=text_labels,
            textposition="auto",
            marker_color=colors, # go.Bar supports list of zeros
            marker_line_width=0
        ))

        fig.update_layout(
            title=dict(text="Where Revenue Lives by Performance State", font=dict(color='#f3f4f6')),
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=400,
            margin=dict(l=10, r=10, t=40, b=10),
            yaxis=dict(
                title="Revenue ($)", 
                showgrid=True, 
                gridcolor='rgba(255,255,255,0.05)',
                tickfont=dict(color='rgba(255,255,255,0.8)')
            ),
            xaxis=dict(
                tickfont=dict(color='rgba(255,255,255,0.8)'),
                showgrid=False
            )
        )
        
        st.plotly_chart(fig, width='stretch')

    def _render_decision_timeline(self, data: Dict[str, Any]):
        """
        Decision Impact Timeline
        Shows one marker per action window with breakdown by market_tag
        """
        self._chart_header("Decision Impact Timeline", "timeline")
        st.markdown("""
        <p style="color: #64748b; font-size: 0.85rem; margin-bottom: 16px;">
            Each marker represents an action window • Hover for impact breakdown
        </p>
        """, unsafe_allow_html=True)
        
        df = data['df_current']
        impact_df = data.get('impact_df')
        
        if impact_df is None or impact_df.empty:
            st.info("No decision data available for timeline.")
            return
        
        # === FILTER: Match ImpactMetrics logic ===
        impact_col = 'final_decision_impact' if 'final_decision_impact' in impact_df.columns else 'decision_impact'
        
        if impact_col not in impact_df.columns:
            st.warning("⚠️ No impact metrics available.")
            return
        
        # Filter: mature + validated (same as ImpactMetrics)
        filtered = impact_df.copy()
        immature_df = pd.DataFrame()  # Track immature windows for pending markers
        
        if 'is_mature' in impact_df.columns:
            filtered = impact_df[impact_df['is_mature'] == True].copy()
            immature_df = impact_df[impact_df['is_mature'] == False].copy()
        
        if 'validation_status' in filtered.columns:
            mask = filtered['validation_status'].str.contains(
                '✓|CPC Validated|CPC Match|Directional|Confirmed|Normalized|Volume', 
                na=False, regex=True
            )
            filtered = filtered[mask]
        
        # Allow showing pending markers even if no validated actions yet
        if filtered.empty and immature_df.empty:
            st.info("ℹ️ No validated decisions in this period.")
            return
        
        # === AGGREGATE BY ACTION WINDOW (Weekly) ===
        window_data = []
        pending_window_data = []
        
        # Mature + validated windows
        if not filtered.empty:
            filtered['action_date'] = pd.to_datetime(filtered['action_date'])
            filtered['Week'] = filtered['action_date'].dt.to_period('W').apply(lambda x: x.start_time)
            
            for week, group in filtered.groupby('Week'):
                offensive = group.loc[group['market_tag'] == 'Offensive Win', impact_col].sum()
                defensive = group.loc[group['market_tag'] == 'Defensive Win', impact_col].sum()
                gap = group.loc[group['market_tag'] == 'Gap', impact_col].sum()
                drag = group.loc[group['market_tag'] == 'Market Drag', impact_col].sum()
                
                attributed = offensive + defensive + gap
                total_actions = len(group)
                
                window_data.append({
                    'week': week,
                    'attributed': attributed,
                    'offensive': offensive,
                    'defensive': defensive,
                    'gap': gap,
                    'drag': drag,
                    'actions': total_actions,
                    'is_pending': False
                })
        
        # Immature (pending) windows - show grayed out
        if not immature_df.empty:
            immature_df['action_date'] = pd.to_datetime(immature_df['action_date'])
            immature_df['Week'] = immature_df['action_date'].dt.to_period('W').apply(lambda x: x.start_time)
            
            for week, group in immature_df.groupby('Week'):
                # Check if this week is already in mature windows
                mature_weeks = [w['week'] for w in window_data]
                if week not in mature_weeks:
                    total_actions = len(group)
                    pending_window_data.append({
                        'week': week,
                        'attributed': 0,
                        'offensive': 0,
                        'defensive': 0,
                        'gap': 0,
                        'drag': 0,
                        'actions': total_actions,
                        'is_pending': True
                    })
        
        all_windows = window_data + pending_window_data
        if not all_windows:
            st.info("No action windows to display.")
            return
        
        window_df = pd.DataFrame(all_windows).sort_values('week')
        
        # Get weekly revenue for Y-axis positioning
        df['Week'] = df['Date'].dt.to_period('W').apply(lambda x: x.start_time)
        weekly_revenue = df.groupby('Week')['Sales'].sum().reset_index()
        
        # Show canonical total
        canonical_metrics = data.get('canonical_metrics')
        if canonical_metrics and canonical_metrics.has_data:
            total_impact = canonical_metrics.attributed_impact
        else:
            total_impact = window_df['attributed'].sum()
        
        currency = get_account_currency()
        st.markdown(f"""
        <p style="color: #64748b; font-size: 0.8rem; margin-bottom: 12px;">
            {len(window_df)} action windows • Attributed Impact: <span style="color: {'#10B981' if total_impact >= 0 else '#EF4444'}; font-weight: 600;">
            {'+ ' if total_impact >= 0 else ''}{currency} {abs(total_impact):,.0f}</span>
        </p>
        """, unsafe_allow_html=True)
        
        # === CREATE VISUALIZATION ===
        fig = go.Figure()
        
        # Revenue trend line
        fig.add_trace(go.Scatter(
            x=weekly_revenue['Week'],
            y=weekly_revenue['Sales'],
            mode='lines',
            name='Revenue Trend',
            line=dict(color='#64748B', width=2.5, shape='spline'),
            hovertemplate='%{x|%b %d}<br>Revenue: ' + currency + ' %{y:,.0f}<extra></extra>',
            showlegend=True
        ))
        
        # Match windows to revenue points
        marker_weeks = []
        marker_revenues = []
        marker_colors = []
        marker_attributed_impacts = []
        marker_pending = []
        hover_texts = []
        custom_data = []
        marker_opacities = []
        
        for _, row in window_df.iterrows():
            revenue_match = weekly_revenue[weekly_revenue['Week'] == row['week']]['Sales'].values
            if len(revenue_match) > 0:
                marker_weeks.append(row['week'])
                marker_revenues.append(revenue_match[0])
                marker_attributed_impacts.append(row['attributed'])
                
                is_pending = row.get('is_pending', False)
                marker_pending.append(is_pending)
                
                if is_pending:
                    # Pending: gray, semi-transparent
                    marker_colors.append('#64748B')
                    marker_opacities.append(0.5)
                    hover_text = (
                        f"<b>⏳ PENDING: {row['week'].strftime('%b %d, %Y')}</b><br>"
                        f"<b>{row['actions']} actions</b><br>"
                        f"────────────────<br>"
                        f"Status: Measuring impact...<br>"
                        f"0 verified actions<br>"
                        f"────────────────<br>"
                        f"<i>Impact will be shown after 14+ days</i>"
                    )
                else:
                    # Mature: color based on attributed impact sign
                    color = self.COLORS['success'] if row['attributed'] >= 0 else self.COLORS['danger']
                    marker_colors.append(color)
                    marker_opacities.append(0.9)
                    hover_text = (
                        f"<b>Action Window: {row['week'].strftime('%b %d, %Y')}</b><br>"
                        f"<b>{row['actions']} actions</b><br>"
                        f"────────────────<br>"
                        f"🟢 Offensive Win: {currency} {row['offensive']:,.0f}<br>"
                        f"🔵 Defensive Win: {currency} {row['defensive']:,.0f}<br>"
                        f"🟡 Gap Action: {currency} {row['gap']:,.0f}<br>"
                        f"⚫ Market Drag: {currency} {row['drag']:,.0f}<br>"
                        f"────────────────<br>"
                        f"<b>Attributed: {'+' if row['attributed'] >= 0 else ''}{currency} {row['attributed']:,.0f}</b>"
                    )
                hover_texts.append(hover_text)
        
        # Add action window markers
        if marker_weeks:
            # Color logic based on impact magnitude
            final_marker_colors = []
            for imp in marker_attributed_impacts:
                if imp > 1000:
                    final_marker_colors.append(self.COLORS['success']) # Emerald
                elif imp >= 0:
                    final_marker_colors.append(self.COLORS['teal'])    # Teal
                elif imp >= -1000:
                    final_marker_colors.append(self.COLORS['warning']) # Amber
                else:
                    final_marker_colors.append(self.COLORS['danger'])  # Rose
            
            # Handle pending transparency and line
            final_opacities = []
            final_lines = []
            
            for is_pend in marker_pending:
                if is_pend:
                    final_opacities.append(0.5)
                    final_lines.append(dict(width=1, color='rgba(148, 163, 184, 0.5)'))
                else:
                    final_opacities.append(0.9)
                    final_lines.append(dict(width=2, color='#F8FAFC'))

            fig.add_trace(go.Scatter(
                x=marker_weeks,
                y=marker_revenues,
                mode='markers',
                name='Actions',
                marker=dict(
                    color=final_marker_colors,
                    size=16,
                    symbol='circle',
                    opacity=final_opacities
                ),
                customdata=list(zip(marker_attributed_impacts, marker_pending)), # Store for hover
                hovertemplate='%{hovertext}<extra></extra>',
                hovertext=hover_texts,
                showlegend=True
            ))
            
            # Update trace with array properties for line where needed
            # This needs to be done after the trace is added, as marker.line can't take arrays directly in dict.
            fig.data[-1].marker.line = dict(color=[l['color'] for l in final_lines], width=[l['width'] for l in final_lines])
             
        # Layout
        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=400,
            margin=dict(l=0, r=0, t=20, b=60),
            xaxis=dict(
                title=None,
                showgrid=False,
                tickformat='%b %d',
                tickfont=dict(size=11, color='#94a3b8')
            ),
            yaxis=dict(
                title=f'Revenue ({currency})',
                showgrid=True,
                gridcolor='rgba(255,255,255,0.05)',
                tickfont=dict(size=11, color='#94a3b8')
            ),
            legend=dict(
                orientation='h',
                yanchor='top',
                y=-0.15,
                xanchor='center',
                x=0.5,
                font=dict(size=11, color='#94a3b8')
            ),
            hovermode='closest',
            hoverlabel=dict(
                bgcolor='#1E293B',
                font_size=12,
                font_family='Inter, sans-serif',
                font_color='#F5F5F7',
                bordercolor='#334155'
            )
        )
        
        st.plotly_chart(fig, width='stretch')

    def _render_decision_impact_card(self, data: Dict[str, Any]):
        """Render decision impact using CANONICAL metrics from ImpactMetrics."""
        self._chart_header("Decision Impact", "lightbulb")
        
        # Use canonical_metrics - THE SINGLE SOURCE OF TRUTH
        canonical_metrics = data.get('canonical_metrics')
        
        if canonical_metrics is None or not canonical_metrics.has_data:
            st.info("ℹ️ No validated decision data available.")
            return
        
        try:
            # === READ FROM CANONICAL METRICS - NO RECALCULATION ===
            net_impact = canonical_metrics.attributed_impact  # THE 18,765 NUMBER
            
            # Breakdown by market_tag (Offensive / Defensive / Gap)
            offensive = canonical_metrics.offensive_value
            defensive = canonical_metrics.defensive_value
            gap = canonical_metrics.gap_value
            
            # Counts
            offensive_count = canonical_metrics.offensive_actions
            defensive_count = canonical_metrics.defensive_actions
            gap_count = canonical_metrics.gap_actions
            
            # === RENDER ===
            
            impact_color = self.COLORS['success'] if net_impact >= 0 else self.COLORS['danger']
            currency = get_account_currency()
            
            st.markdown(f"""
            <div class="impact-hero" style="margin-top: 16px;">
                <div style="color: #94a3b8; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;">
                    NET IMPACT (14D VALIDATED)
                </div>
                <div style="color: {impact_color}; font-size: 2.8rem; font-weight: 700;">
                    {'+ ' if net_impact >= 0 else ''}{currency} {abs(net_impact):,.0f}
                </div>
                <div style="color: #64748b; font-size: 0.8rem; margin-top: 8px;">
                    {canonical_metrics.mature_actions} mature actions
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Category breakdown (using market-tag based values from ImpactMetrics)
            # Category breakdown (using market-tag based values from ImpactMetrics)
            categories = [
                ("Offensive Wins", offensive, offensive_count, self.COLORS['success']), # Emerald
                ("Defensive Wins", defensive, defensive_count, self.COLORS['warning']), # Amber
                ("Gap Actions", gap, gap_count, self.COLORS['primary'])                 # Cyan
            ]
            
            for label, impact, count, color in categories:
                if count == 0:
                    continue
                
                icon = '↑' if impact >= 0 else '↓'
                row_display = f"{icon} {currency} {abs(impact):,.0f}"
                
                st.markdown(f"""
                <div class="impact-row" style="border-left-color: {color};">
                    <div>
                        <div style="color: #F5F5F7; font-weight: 600; font-size: 0.9rem;">
                            {label}
                        </div>
                        <div style="color: #64748b; font-size: 0.75rem;">
                            {count} actions
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="color: {color}; font-weight: 700; font-size: 1rem;">
                            {row_display}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
        except Exception as e:
            st.error(f"❌ Error: {e}")
            import traceback
            with st.expander("Debug Info"):
                st.code(traceback.format_exc())
    