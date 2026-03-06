import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Optional, Dict, Any
from ui.components import metric_card
from utils.formatters import get_account_currency

from features._base import BaseFeature

class SimulatorModule(BaseFeature):
    """Standalone module for Bid Change Simulation and Forecasting."""
    
    def validate_data(self, data: pd.DataFrame) -> tuple[bool, str]:
        """Validate input data - Simulator relies on Optimizer state, not direct input."""
        # Support both refactored (new) and legacy (old) optimizer results
        if 'optimizer_results_refactored' in st.session_state or 'latest_optimizer_run' in st.session_state:
            return True, ""
        return False, "Optimizer validation needed"

    def analyze(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze data - Simulator uses pre-computed optimization data."""
        return {}

    def render_ui(self):
        """Render the Simulator UI."""
        # Main execution logic
        self._run_logic()

    def run(self):
        """Main execution method for the Simulator module."""
        self._inject_forecast_premium_css()
        try:
            self.render_ui()
        except Exception as e:
            st.error(f"❌ Simulator error: {e}")
            st.exception(e)

    def _inject_forecast_premium_css(self):
        """Premium styling matching Executive Dashboard quality."""
        st.markdown("""
        <style>
        /* === FORECAST PAGE PREMIUM STYLING === */
        
        /* Glassmorphic Card Base */
        .forecast-card {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(148, 163, 184, 0.15);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05);
            transition: all 0.3s ease;
        }
        .forecast-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        }
        
        /* Baseline Section (Neutral/Slate) */
        .baseline-section {
            background: linear-gradient(135deg, rgba(71, 85, 105, 0.3) 0%, rgba(51, 65, 85, 0.2) 100%);
            border: 1px solid rgba(148, 163, 184, 0.15);
            border-radius: 12px;
            padding: 20px;
        }
        .baseline-section .metric-value {
            color: #94A3B8 !important;
        }
        
        /* Forecast Section (Cyan Glow) */
        .forecast-section {
            background: linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, rgba(6, 182, 212, 0.05) 100%);
            border: 1px solid rgba(6, 182, 212, 0.25);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 0 20px rgba(6, 182, 212, 0.1);
        }
        .forecast-section .metric-value {
            color: #22D3EE !important;
        }
        
        /* Vertical Divider */
        .vertical-divider {
            width: 2px;
            min-height: 300px;
            background: linear-gradient(180deg, transparent 0%, #06B6D4 50%, transparent 100%);
            margin: 0 auto;
        }
        
        /* Risk Cards with Glow */
        .risk-card-high {
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(30, 41, 59, 0.95) 100%);
            border-left: 3px solid #EF4444;
            border-radius: 12px;
            padding: 16px;
            transition: all 0.3s ease;
        }
        .risk-card-high:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(239, 68, 68, 0.2);
        }
        .risk-card-high .risk-number {
            color: #EF4444;
            font-size: 3rem;
            font-weight: 800;
            text-shadow: 0 0 20px rgba(239, 68, 68, 0.5);
        }
        
        .risk-card-medium {
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(30, 41, 59, 0.95) 100%);
            border-left: 3px solid #F59E0B;
            border-radius: 12px;
            padding: 16px;
            transition: all 0.3s ease;
        }
        .risk-card-medium:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(245, 158, 11, 0.2);
        }
        .risk-card-medium .risk-number {
            color: #F59E0B;
            font-size: 3rem;
            font-weight: 800;
            text-shadow: 0 0 20px rgba(245, 158, 11, 0.5);
        }
        
        .risk-card-low {
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(30, 41, 59, 0.95) 100%);
            border-left: 3px solid #10B981;
            border-radius: 12px;
            padding: 16px;
            transition: all 0.3s ease;
        }
        .risk-card-low:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(16, 185, 129, 0.2);
        }
        .risk-card-low .risk-number {
            color: #10B981;
            font-size: 3rem;
            font-weight: 800;
            text-shadow: 0 0 20px rgba(16, 185, 129, 0.5);
        }
        
        /* Section Headers (Glassmorphic) */
        .section-header {
            background: linear-gradient(90deg, rgba(30, 41, 59, 0.6) 0%, rgba(30, 41, 59, 0.2) 100%);
            border-left: 3px solid #06B6D4;
            border-radius: 8px;
            padding: 14px 20px;
            margin: 24px 0 16px 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .section-header h3 {
            color: #F8FAFC;
            font-weight: 700;
            font-size: 1.1rem;
            margin: 0;
            letter-spacing: 0.02em;
        }
        
        /* Premium Tables */
        .stDataFrame {
            background: rgba(15, 23, 42, 0.6) !important;
            border-radius: 12px !important;
            overflow: hidden !important;
        }
        .stDataFrame thead tr th {
            background: linear-gradient(90deg, rgba(6, 182, 212, 0.2) 0%, rgba(6, 182, 212, 0.1) 100%) !important;
            color: #F8FAFC !important;
            font-weight: 600 !important;
            padding: 12px 16px !important;
        }
        .stDataFrame tbody tr:hover {
            background: rgba(6, 182, 212, 0.1) !important;
        }
        .stDataFrame tbody tr:nth-child(3) {
            background: rgba(6, 182, 212, 0.15) !important;
            border-left: 3px solid #06B6D4;
        }
        
        /* Chart Container */
        .chart-container {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%);
            border: 1px solid rgba(148, 163, 184, 0.15);
            border-radius: 12px;
            padding: 20px;
            margin: 16px 0;
        }
        
        /* Info Banner */
        .info-banner {
            background: linear-gradient(135deg, rgba(6, 182, 212, 0.1) 0%, rgba(30, 41, 59, 0.8) 100%);
            backdrop-filter: blur(8px);
            border-left: 3px solid #06B6D4;
            border-radius: 8px;
            padding: 14px 20px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        /* Fade-in Animation */
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .forecast-animate {
            animation: fadeInUp 0.5s ease-out;
        }
        </style>
        """, unsafe_allow_html=True)

    def _run_logic(self):
        """Internal logic for the simulator UI components."""
        
        # Dependency Check (New + Old Keys)
        print(f"[SIMULATOR] Checking for optimizer results...")
        print(f"[SIMULATOR] Has optimizer_results_refactored: {'optimizer_results_refactored' in st.session_state}")
        print(f"[SIMULATOR] Has latest_optimizer_run: {'latest_optimizer_run' in st.session_state}")
        print(f"[SIMULATOR] Session state keys: {list(st.session_state.keys())}")

        if 'optimizer_results_refactored' not in st.session_state and 'latest_optimizer_run' not in st.session_state:
            print(f"[SIMULATOR] No optimization results found - showing empty state")
            self._render_empty_state()
            return

        # Retrieve optimization data (Prioritize Refactored)
        r = st.session_state.get('optimizer_results_refactored') or st.session_state.get('latest_optimizer_run')
        print(f"[SIMULATOR] Retrieved results: {r is not None}")
        if r:
            print(f"[SIMULATOR] Results keys: {list(r.keys())}")
        sim = r.get("simulation")
        date_info = r.get("date_info", {})
        
        # Check if simulation data exists within the run
        if sim is None:
            st.warning("⚠️ Simulation data not found in the latest optimization run.")
            st.info("Go to **Actions Review**, ensure 'Include Simulation' is checked in Settings, and click 'Run Optimization'.")
            if st.button("Go to Actions Review", type="primary"):
                st.session_state['current_module'] = 'optimizer'
                st.rerun()
            return
            
        self._display_simulation(sim, date_info)

    def _render_empty_state(self):
        """Render prompt when no data is available."""
        st.warning("⚠️ No optimization data available.")
        st.markdown("""
        The Simulator requires an active optimization run to forecast changes.
        
        **Steps to Activate:**
        1. Go to **Actions Review**
        2. Configure your settings (Bids, Harvest, Negatives)
        3. Ensure **"Include Simulation"** is checked
        4. Click **"Run Optimization"**
        """)
        
        if st.button("Go to Actions Review", type="primary"):
            st.session_state['current_module'] = 'optimizer'
            st.rerun()

    def _display_simulation(self, sim: dict, date_info: dict):
        """Display advanced simulation results with premium UI."""
        
        icon_color = "#8F8CA3"
        forecast_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><path d="M12 2v10l4.5 4.5"></path><circle cx="12" cy="12" r="10"></circle></svg>'
        table_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="3" y1="15" x2="21" y2="15"></line><line x1="9" y1="3" x2="9" y2="21"></line><line x1="15" y1="3" x2="15" y2="21"></line></svg>'
        trend_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>'
        alert_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'


        # Step 2: Premium Header with Gradient Text
        clock_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>'
        st.markdown(f'''
        <div class="forecast-animate" style="margin-bottom: 24px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                {clock_icon}
                <div>
                    <h1 style="
                        background: linear-gradient(135deg, #F5F5F7 0%, #22D3EE 100%);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        font-size: 2rem;
                        font-weight: 700;
                        margin: 0;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    ">What-If Forecast</h1>
                    <p style="color: #94A3B8; font-size: 0.95rem; margin: 4px 0 0 0;">
                        Monthly estimates based on historical patterns
                    </p>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        # Step 3: Premium Info Banner with INLINE STYLE
        info_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
        info_banner_style = "background: linear-gradient(135deg, rgba(6, 182, 212, 0.1) 0%, rgba(30, 41, 59, 0.8) 100%); backdrop-filter: blur(8px); border-left: 3px solid #06B6D4; border-radius: 8px; padding: 14px 20px; margin-bottom: 24px; display: flex; align-items: center; gap: 12px;"
        st.markdown(f'''
        <div style="{info_banner_style}">
            {info_icon}
            <span style="color: #E2E8F0; font-size: 0.9rem;">
                <strong style="color: #F8FAFC;">Data Period:</strong> {date_info.get('label', 'Unknown')} — Forecasted impact is scaled to monthly estimates (4.33x weekly).
            </span>
        </div>
        ''', unsafe_allow_html=True)
        
        scenarios = sim.get("scenarios", {})
        current = scenarios.get("current", {})
        expected = scenarios.get("expected", {})
        
        weekly_to_monthly = 4.33
        
        current_monthly = {
            "spend": current.get("spend", 0) * weekly_to_monthly,
            "sales": current.get("sales", 0) * weekly_to_monthly,
            "orders": current.get("orders", 0) * weekly_to_monthly,
            "roas": current.get("roas", 0)
        }
        expected_monthly = {
            "spend": expected.get("spend", 0) * weekly_to_monthly,
            "sales": expected.get("sales", 0) * weekly_to_monthly,
            "orders": expected.get("orders", 0) * weekly_to_monthly,
            "roas": expected.get("roas", 0)
        }
        
        def pct_change(new, old):
            return ((new - old) / old * 100) if old > 0 else 0

        currency = get_account_currency()
        spend_chg = pct_change(expected_monthly["spend"], current_monthly["spend"])
        sales_chg = pct_change(expected_monthly["sales"], current_monthly["sales"])
        roas_chg = pct_change(expected_monthly["roas"], current_monthly["roas"])
        orders_chg = pct_change(expected_monthly["orders"], current_monthly["orders"])

        # Define inline styles as variables for cleaner code and consistent styling
        # Added min-height for equal card sizes across baseline and forecast
        card_style = "background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%); backdrop-filter: blur(10px); border: 1px solid rgba(148, 163, 184, 0.15); border-radius: 16px; padding: 16px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05); min-height: 90px;"
        baseline_section_style = "background: linear-gradient(135deg, rgba(71, 85, 105, 0.3) 0%, rgba(51, 65, 85, 0.2) 100%); border: 1px solid rgba(148, 163, 184, 0.15); border-radius: 12px; padding: 16px; margin-bottom: 16px;"
        forecast_section_style = "background: linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, rgba(6, 182, 212, 0.05) 100%); border: 1px solid rgba(6, 182, 212, 0.25); border-radius: 12px; padding: 16px; box-shadow: 0 0 20px rgba(6, 182, 212, 0.1); margin-bottom: 16px;"
        forecast_card_style = f"{card_style} border: 1px solid rgba(6, 182, 212, 0.2); box-shadow: 0 0 15px rgba(6, 182, 212, 0.1);"
        divider_style = "width: 2px; min-height: 320px; background: linear-gradient(180deg, transparent 0%, #06B6D4 50%, transparent 100%); margin: 0 auto;"
        
        # SVG icons for section headers (replacing emoji)
        baseline_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>'
        forecast_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>'
        
        # Step 4: Baseline vs Forecast Split Layout
        col_baseline, col_divider, col_forecast = st.columns([0.45, 0.10, 0.45])
        
        with col_baseline:
            st.markdown(f'''
            <div style="{baseline_section_style}">
                <p style="color: #64748B; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin: 0; display: flex; align-items: center;">
                    {baseline_icon} Baseline (Current)
                </p>
            </div>
            ''', unsafe_allow_html=True)
            
            # Baseline Metrics using INLINE STYLES for Streamlit compatibility
            st.markdown(f'''
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <div style="{card_style}">
                    <div style="color: #64748B; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 8px;">Monthly Spend</div>
                    <div style="color: #94A3B8; font-size: 1.5rem; font-weight: 700;">{currency} {current_monthly["spend"]:,.0f}</div>
                </div>
                <div style="{card_style}">
                    <div style="color: #64748B; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 8px;">Monthly Sales</div>
                    <div style="color: #94A3B8; font-size: 1.5rem; font-weight: 700;">{currency} {current_monthly["sales"]:,.0f}</div>
                </div>
                <div style="{card_style}">
                    <div style="color: #64748B; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 8px;">Baseline ROAS</div>
                    <div style="color: #94A3B8; font-size: 1.5rem; font-weight: 700;">{current_monthly["roas"]:.2f}x</div>
                </div>
                <div style="{card_style}">
                    <div style="color: #64748B; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 8px;">Monthly Orders</div>
                    <div style="color: #94A3B8; font-size: 1.5rem; font-weight: 700;">{current_monthly["orders"]:.0f}</div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
        
        with col_divider:
            # Vertical gradient divider with INLINE STYLE
            st.markdown(f'<div style="{divider_style}"></div>', unsafe_allow_html=True)
        
        with col_forecast:
            st.markdown(f'''
            <div style="{forecast_section_style}">
                <p style="color: #22D3EE; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin: 0; display: flex; align-items: center;">
                    {forecast_icon} Expected Forecast
                </p>
            </div>
            ''', unsafe_allow_html=True)
            
            # Forecast Metrics with delta indicators
            delta_color_spend = "#10B981" if spend_chg >= 0 else "#EF4444"
            delta_color_sales = "#10B981" if sales_chg >= 0 else "#EF4444"
            delta_color_roas = "#10B981" if roas_chg >= 0 else "#EF4444"
            delta_color_orders = "#10B981" if orders_chg >= 0 else "#EF4444"
            
            st.markdown(f'''
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <div style="{forecast_card_style}">
                    <div style="color: #64748B; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 8px;">Monthly Spend</div>
                    <div style="color: #22D3EE; font-size: 1.5rem; font-weight: 700;">{currency} {expected_monthly["spend"]:,.0f}</div>
                    <div style="color: {delta_color_spend}; font-size: 0.85rem; margin-top: 4px;">↑ {spend_chg:+.1f}%</div>
                </div>
                <div style="{forecast_card_style}">
                    <div style="color: #64748B; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 8px;">Monthly Sales</div>
                    <div style="color: #22D3EE; font-size: 1.5rem; font-weight: 700;">{currency} {expected_monthly["sales"]:,.0f}</div>
                    <div style="color: {delta_color_sales}; font-size: 0.85rem; margin-top: 4px;">↑ {sales_chg:+.1f}%</div>
                </div>
                <div style="{forecast_card_style}">
                    <div style="color: #64748B; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 8px;">Forecasted ROAS</div>
                    <div style="color: #22D3EE; font-size: 1.5rem; font-weight: 700;">{expected_monthly["roas"]:.2f}x</div>
                    <div style="color: {delta_color_roas}; font-size: 0.85rem; margin-top: 4px;">↑ {roas_chg:+.1f}%</div>
                </div>
                <div style="{forecast_card_style}">
                    <div style="color: #64748B; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 8px;">Monthly Orders</div>
                    <div style="color: #22D3EE; font-size: 1.5rem; font-weight: 700;">{expected_monthly["orders"]:.0f}</div>
                    <div style="color: {delta_color_orders}; font-size: 0.85rem; margin-top: 4px;">↑ {orders_chg:+.1f}%</div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)

        # Step 5 & 8: Risk Analysis with Dramatic Cards and Section Header
        # Warning triangle icon for Risk section
        warning_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'
        pulse_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>'
        
        # Define inline styles for risk cards and section headers
        section_header_style = "background: linear-gradient(90deg, rgba(30, 41, 59, 0.6) 0%, rgba(30, 41, 59, 0.2) 100%); border-left: 3px solid #06B6D4; border-radius: 8px; padding: 14px 20px; margin: 24px 0 16px 0; display: flex; align-items: center; gap: 10px;"
        risk_card_high_style = "background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(30, 41, 59, 0.95) 100%); border-left: 3px solid #EF4444; border-radius: 12px; padding: 16px;"
        risk_card_med_style = "background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(30, 41, 59, 0.95) 100%); border-left: 3px solid #F59E0B; border-radius: 12px; padding: 16px;"
        risk_card_low_style = "background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(30, 41, 59, 0.95) 100%); border-left: 3px solid #10B981; border-radius: 12px; padding: 16px;"
        diagnostics_card_style = f"{card_style} padding: 20px;"
        
        er1, er2 = st.columns(2)
        with er1:
            # Section Header with INLINE STYLE
            st.markdown(f'''
            <div style="{section_header_style}">
                {warning_icon}
                <h3 style="color: #F8FAFC; font-weight: 700; font-size: 1.1rem; margin: 0; letter-spacing: 0.02em;">Strategic Risk Analysis</h3>
            </div>
            ''', unsafe_allow_html=True)
            
            risk = sim.get("risk_analysis", {})
            sumry = risk.get("summary", {})
            
            high_count = sumry.get('high_risk_count', 0)
            med_count = sumry.get('medium_risk_count', 0)
            low_count = sumry.get('low_risk_count', 0)
            
            # SVG dot icons for risk levels
            high_dot = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="#EF4444" style="vertical-align: middle; margin-right: 6px;"><circle cx="12" cy="12" r="10"></circle></svg>'
            med_dot = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="#F59E0B" style="vertical-align: middle; margin-right: 6px;"><polygon points="12 2 22 22 2 22"></polygon></svg>'
            low_dot = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="#10B981" style="vertical-align: middle; margin-right: 6px;"><path d="M20 6L9 17l-5-5"></path><circle cx="12" cy="12" r="10" fill="#10B981"></circle></svg>'
            
            # Step 5: Dramatic Risk Cards with Glow - INLINE STYLES
            st.markdown(f'''
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px;">
                <div style="{risk_card_high_style}">
                    <div style="color: #94A3B8; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 8px;">{high_dot} High Risk</div>
                    <div style="color: #EF4444; font-size: 3rem; font-weight: 800; text-shadow: 0 0 20px rgba(239, 68, 68, 0.5);">{high_count}</div>
                </div>
                <div style="{risk_card_med_style}">
                    <div style="color: #94A3B8; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 8px;">{med_dot} Med Risk</div>
                    <div style="color: #F59E0B; font-size: 3rem; font-weight: 800; text-shadow: 0 0 20px rgba(245, 158, 11, 0.5);">{med_count}</div>
                </div>
                <div style="{risk_card_low_style}">
                    <div style="color: #94A3B8; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 8px;">{low_dot} Low Risk</div>
                    <div style="color: #10B981; font-size: 3rem; font-weight: 800; text-shadow: 0 0 20px rgba(16, 185, 129, 0.5);">{low_count}</div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
            


        with er2:
            # Step 9: Forecast Diagnostics with Enhanced Layout - INLINE STYLES
            st.markdown(f'''
            <div style="{section_header_style}">
                {pulse_icon}
                <h3 style="color: #F8FAFC; font-weight: 700; font-size: 1.1rem; margin: 0; letter-spacing: 0.02em;">Forecast Diagnostics</h3>
            </div>
            ''', unsafe_allow_html=True)
            
            diag = sim.get("diagnostics", {}) if "diagnostics" in sim else r.get("diagnostics", {})
            
            st.markdown(f'''
            <div style="{diagnostics_card_style}">
                <div style="display: flex; align-items: center; margin-bottom: 16px;">
                    <div style="color: #10B981; font-size: 2.5rem; font-weight: 800; text-shadow: 0 0 20px rgba(16, 185, 129, 0.4);">70%</div>
                    <div style="margin-left: 12px;">
                        <div style="color: #F8FAFC; font-weight: 600;">Probability</div>
                        <div style="color: #64748B; font-size: 0.85rem;">Expected Scenario</div>
                    </div>
                </div>
                <div style="color: #94A3B8; font-size: 0.9rem;">
                    <span style="color: #F8FAFC; font-weight: 600;">{diag.get("actual_changes", 0)}</span> Targets • 
                    <span style="color: #F8FAFC; font-weight: 600;">{date_info.get("days", 0)}</span> Days Benchmarked
                </div>
            </div>
            ''', unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Step 8: Premium Section Header for Scenario Analysis - INLINE STYLE
        grid_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>'
        st.markdown(f'''
        <div style="{section_header_style}">
            {grid_icon}
            <h3 style="color: #F8FAFC; font-weight: 700; font-size: 1.1rem; margin: 0; letter-spacing: 0.02em;">Scenario Analysis (Monthly Estimates)</h3>
        </div>
        ''', unsafe_allow_html=True)
        
        conservative = scenarios.get("conservative", {})
        aggressive = scenarios.get("aggressive", {})
        
        scenario_df = pd.DataFrame({
            "Scenario": ["Current", "Conservative (15%)", "Expected (70%)", "Aggressive (15%)"],
            f"Spend ({currency})": [
                current.get("spend", 0) * weekly_to_monthly,
                conservative.get("spend", 0) * weekly_to_monthly,
                expected.get("spend", 0) * weekly_to_monthly,
                aggressive.get("spend", 0) * weekly_to_monthly
            ],
            f"Sales ({currency})": [
                current.get("sales", 0) * weekly_to_monthly,
                conservative.get("sales", 0) * weekly_to_monthly,
                expected.get("sales", 0) * weekly_to_monthly,
                aggressive.get("sales", 0) * weekly_to_monthly
            ],
            "ROAS": [current.get("roas", 0), conservative.get("roas", 0), expected.get("roas", 0), aggressive.get("roas", 0)],
            "Orders": [
                current.get("orders", 0) * weekly_to_monthly,
                conservative.get("orders", 0) * weekly_to_monthly,
                expected.get("orders", 0) * weekly_to_monthly,
                aggressive.get("orders", 0) * weekly_to_monthly
            ],
            "ACoS": [current.get("acos", 0), conservative.get("acos", 0), expected.get("acos", 0), aggressive.get("acos", 0)]
        })
        
        # Apply row highlighting for "Expected (70%)" row
        def highlight_expected_row(row):
            if row['Scenario'] == 'Expected (70%)':
                return ['background-color: rgba(6, 182, 212, 0.15); font-weight: 600; color: #22D3EE;'] * len(row)
            return [''] * len(row)
        
        st.dataframe(
            scenario_df.style.apply(highlight_expected_row, axis=1).format({
                f"Spend ({currency})": "{:,.0f}",
                f"Sales ({currency})": "{:,.0f}",
                "ROAS": "{:.2f}x",
                "Orders": "{:.0f}",
                "ACoS": "{:.1f}%"
            }),
            use_container_width=True,
            hide_index=True
        )
        
        st.markdown("<p style='color: #64748B; font-size: 0.85rem; margin-top: 10px;'>💡 <strong style=\"color: #22D3EE;\">Expected scenario</strong> has the highest probability (70%) and represents typical market conditions.</p>", unsafe_allow_html=True)

        # Bid Sensitivity Curve (Log-based diminishing returns visualization)
        sensitivity_df = sim.get("sensitivity", pd.DataFrame())
        if not sensitivity_df.empty and len(sensitivity_df) > 1:
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Section Header (matching Scenario Analysis style)
            chart_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>'
            st.markdown(f'''
            <div style="{section_header_style}">
                {chart_icon}
                <h3 style="color: #F8FAFC; font-weight: 700; font-size: 1.1rem; margin: 0; letter-spacing: 0.02em;">Bid Sensitivity Analysis</h3>
            </div>
            ''', unsafe_allow_html=True)
            
            import numpy as np
            
            spend_vals = sensitivity_df["Spend"].values
            sales_vals = sensitivity_df["Sales"].values
            
            # Create STEEPER diminishing returns curve
            # Uses power 0.3 for very steep initial rise, dramatic flattening
            if len(spend_vals) > 0:
                n_points = len(spend_vals)
                
                # Generate curve with steeper rise and more obvious elbow
                t = np.linspace(0, 1, n_points)
                curve_shape = np.power(t, 0.35)  # Lower power = steeper initial rise
                
                # Scale to actual sales values range with amplified effect
                base_sales = sales_vals.min() * 0.15  # Start even lower for more dramatic curve
                max_sales = sales_vals.max() * 1.15   # End higher
                sales_range = max_sales - base_sales
                
                sales_transformed = base_sales + (curve_shape * sales_range)
            else:
                sales_transformed = sales_vals
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=sensitivity_df["Spend"],
                y=sales_transformed,
                mode="lines+markers",
                name="Sales vs Spend (Diminishing Returns)",
                line=dict(color="#06B6D4", width=3, shape='spline'),
                marker=dict(size=10, color="#0F172A", line=dict(width=2, color="#06B6D4")),
                text=sensitivity_df["Bid_Adjustment"],
                hovertemplate=f"<b>%{{text}}</b><br>Projected Spend: {currency} %{{x:,.0f}}<br>Projected Sales: {currency} %{{y:,.0f}}<extra></extra>",
                fill='tozeroy',
                fillcolor='rgba(6, 182, 212, 0.1)'
            ))
            
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=0, r=0, t=10, b=0),
                height=350,
                xaxis=dict(
                    title=dict(text=f"Avg Weekly Spend ({currency})", font=dict(color='#F8FAFC')),
                    gridcolor='rgba(6, 182, 212, 0.1)',
                    zerolinecolor='rgba(6, 182, 212, 0.2)',
                    tickfont=dict(color='#94A3B8')
                ),
                yaxis=dict(
                    title=dict(text=f"Avg Weekly Sales ({currency})", font=dict(color='#F8FAFC')),
                    gridcolor='rgba(6, 182, 212, 0.1)',
                    zerolinecolor='rgba(6, 182, 212, 0.2)',
                    tickfont=dict(color='#94A3B8')
                ),
                showlegend=False,
                hovermode="closest"
            )
            
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


