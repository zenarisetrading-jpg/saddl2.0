"""
Impact Dashboard v2 - Main Entry Point

This module orchestrates the Impact & Results dashboard using
clean, modular components.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any

# Core imports
from app_core.utils import IMPACT_WINDOWS, get_maturity_status
from features.impact_metrics import ImpactMetrics

# Local imports
from features.impact.data.fetchers import fetch_impact_data
from features.impact.data.transforms import validate_impact_columns
from features.impact.components.hero import render_hero_banner
from features.impact.components.analytics import render_impact_analytics
from features.impact.components.tables import render_dormant_table
from features.impact.utils import (
    check_model_version_consistency,
    render_export_button
)


def _inject_styles():
    """Inject dashboard-specific CSS styles."""
    st.markdown("""
    <style>
    /* Dark theme buttons */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
    }
    .stDownloadButton > button:hover {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        transform: translateY(-1px);
    }
    /* Data table dark theme compatibility */
    .stDataFrame {
        background: transparent !important;
    }
    /* Panel container styling */
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
    </style>
    """, unsafe_allow_html=True)


def _render_header():
    """Render dashboard header with horizon selector."""
    col_header, col_toggle = st.columns([3, 1])

    with col_header:
        st.markdown("## :material/monitoring: Impact & Results", help="Comprehensive view of optimization outcomes and measured ROI.")
        st.caption("Measured impact of executed optimization actions")

    with col_toggle:
        st.write("")  # Spacer
        horizon = st.radio(
            "Measurement Horizon",
            options=IMPACT_WINDOWS["available_horizons"],
            index=0,
            horizontal=True,
            label_visibility="collapsed",
            key="impact_horizon_v2",
            help="How long after the action to measure impact"
        )
        if horizon is None:
            horizon = IMPACT_WINDOWS["default_horizon"]

    return horizon


def _render_period_header(horizon_config: Dict, latest_data_date, full_summary: Dict, measured_count: int, pending_count: int):
    """Render the period header with analysis date range."""
    theme_mode = st.session_state.get('theme_mode', 'dark')
    cal_color = "#E9EAF0" if theme_mode == 'dark' else "#5B5670"
    calendar_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{cal_color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 6px;"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>'

    # Prepare Analysis Period text
    p = full_summary.get('period_info', {})
    analysis_range = "Current Period"
    try:
        def fmt(d):
            if not d:
                return ""
            if isinstance(d, str):
                d = pd.to_datetime(d)
            return d.strftime("%b %d")

        start = p.get('before_start')
        end = latest_data_date if latest_data_date else p.get('after_end')
        if start and end:
            analysis_range = f"{fmt(start)} - {fmt(end)}"
    except Exception:
        pass

    compare_text = f"Analysis Period: <code>{analysis_range}</code>"

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%);
                border: 1px solid rgba(148, 163, 184, 0.15);
                border-left: 3px solid #06B6D4;
                border-radius: 12px; padding: 16px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);">
        <div style="display: flex; align-items: center; gap: 8px;">
            {calendar_icon}
            <span style="font-weight: 600; font-size: 1.1rem; color: #F8FAFC; margin-right: 12px;">{horizon_config['label']}</span>
            <span style="color: #94a3b8; font-size: 0.95rem;">{compare_text}</span>
        </div>
        <div style="color: #94a3b8; font-size: 0.85rem; font-family: monospace;">
            Measured: <span style="color: #22D3EE; font-weight: 600;">{measured_count}</span> | Pending: <span style="color: #94a3b8; font-weight: 600;">{pending_count}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_impact_dashboard_v2():
    """
    Main render function for Impact Dashboard v2.

    This is the refactored version using modular components.
    """
    # Force empty state for testing
    if st.query_params.get("test_state") == "no_data":
        from ui.components.empty_states import render_empty_state
        account = st.session_state.get('active_account_name', 'Account')
        render_empty_state('no_data', context={'account_name': account})
        return

    # Inject styles
    _inject_styles()

    # Render header and get horizon selection
    horizon = _render_header()

    # Check for database manager
    db_manager = st.session_state.get('db_manager')
    if db_manager is None:
        st.warning("⚠️ Database not initialized. Please ensure you're in the main app.")
        return

    # Get active account
    selected_client = st.session_state.get('active_account_id', 'default_client')
    if not selected_client:
        st.error("⚠️ No account selected! Please select an account in the sidebar.")
        return

    # Get available dates
    try:
        available_dates = db_manager.get_available_dates(selected_client)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'get_available_dates failed: {e}', exc_info=True)
        st.error('Impact data could not be loaded — database temporarily unreachable. Please refresh.')
        st.stop()
    if not available_dates:
        st.warning(f"⚠️ No action data found for account '{st.session_state.get('active_account_name', selected_client)}'. "
                   "Run the optimizer to log actions.")
        return

    # Sidebar info
    with st.sidebar:
        st.info(f"**Account:** {st.session_state.get('active_account_name', selected_client)}")
        st.caption(f"📅 Data available: {len(available_dates)} weeks")

    # Fetch impact data
    with st.spinner("Calculating impact..."):
        test_mode = st.session_state.get('test_mode', False)
        cache_version = "v20_perf_" + str(st.session_state.get('data_upload_timestamp', 'init'))

        # Get horizon config
        horizon_config = IMPACT_WINDOWS["horizons"].get(horizon, IMPACT_WINDOWS["horizons"]["14D"])
        before_days = IMPACT_WINDOWS["before_window_days"]
        after_days = horizon_config["days"]
        buffer_days = IMPACT_WINDOWS["maturity_buffer_days"]

        result = fetch_impact_data(selected_client, test_mode, before_days, after_days, cache_version)
        if isinstance(result, dict) and result.get('status') == 'error':
            st.error('Impact data could not be loaded. This is a temporary error — not a reflection of your optimization results. Please refresh the page.')
            st.stop()
        impact_df, full_summary = result

        # Get latest data date
        latest_data_date = None
        if hasattr(db_manager, 'get_latest_raw_data_date'):
            try:
                latest_data_date = db_manager.get_latest_raw_data_date(selected_client)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f'get_latest_raw_data_date failed: {e}', exc_info=True)
                latest_data_date = None
        if not latest_data_date:
            period_info = full_summary.get('period_info', {})
            latest_data_date = period_info.get('after_end') or period_info.get('latest_date')

        # Calculate maturity
        if not impact_df.empty and 'action_date' in impact_df.columns and latest_data_date:
            impact_df['is_mature'] = impact_df['action_date'].apply(
                lambda d: get_maturity_status(d, latest_data_date, horizon)['is_mature']
            )
            impact_df['maturity_status'] = impact_df['action_date'].apply(
                lambda d: get_maturity_status(d, latest_data_date, horizon)['status']
            )

        # Calculate canonical metrics
        current_filters = {
            'validated_only': st.session_state.get('validated_only_toggle_v2', True),
            'mature_only': True,
        }
        canonical_metrics = ImpactMetrics.from_dataframe(impact_df, filters=current_filters, horizon_days=after_days)

    # Handle empty state
    if impact_df.empty:
        st.info("No impact data available. Run the optimizer and upload next week's data to see impact.")
        return

    if full_summary.get('all', {}).get('total_actions', 0) == 0:
        st.info("No actions with matching 'next week' performance data found.")
        return

    # Validate required v3.3 columns
    impact_df = validate_impact_columns(impact_df)

    # Filter by maturity
    if 'is_mature' in impact_df.columns:
        mature_count = int(impact_df['is_mature'].sum())
        pending_attr_count = len(impact_df) - mature_count
    else:
        impact_df['is_mature'] = True
        mature_count = len(impact_df)
        pending_attr_count = 0

    # Check for empty mature set
    if mature_count == 0 and len(impact_df) > 0:
        maturity_days = after_days + buffer_days
        st.warning(f"""
            **No actions mature for {horizon} measurement yet.**

            The {horizon_config['label']} requires {maturity_days} days of data after each action.

            **Options:**
            - Select **14D** horizon for earlier insights
            - Wait for more data to accumulate
            - {pending_attr_count} actions pending for this horizon
        """)

    # ==========================================
    # PHASE 5: Model Version Consistency Check & Export
    # ==========================================
    version_check = check_model_version_consistency(impact_df)
    if not version_check['is_consistent']:
        st.warning(version_check['warning_message'])

    # Validation toggle and export button
    toggle_col1, toggle_col2, export_col = st.columns([1, 4, 1])
    with toggle_col1:
        show_validated_only = st.toggle(
            "Validated Only",
            value=True,
            key='validated_only_toggle_v2',
            help="Show only actions confirmed by actual CPC/Bid data"
        )
    with toggle_col2:
        if show_validated_only:
            st.caption("✓ Showing **validated actions only** — filtering all cards and charts.")
        else:
            st.caption("📊 Showing **all actions** — including pending and unverified.")
    with export_col:
        render_export_button(impact_df, filename_prefix=f"impact_{horizon}")

    # Filter data
    v_mask = impact_df['validation_status'].str.contains('✓|CPC Validated|CPC Match|Directional|Confirmed|Normalized|Volume|Strict', na=False, regex=True)
    display_df = impact_df[v_mask].copy() if show_validated_only else impact_df.copy()

    # Split by maturity
    mature_mask = display_df['is_mature'] == True
    mature_df = display_df[mature_mask].copy()
    pending_attr_df = display_df[~mature_mask].copy()

    # Split by spend activity
    spend_mask = (mature_df['before_spend'].fillna(0) + mature_df['observed_after_spend'].fillna(0)) > 0
    active_df = mature_df[spend_mask].copy()
    dormant_df = mature_df[~spend_mask].copy()

    # Get display metrics
    from utils.formatters import get_account_currency
    currency = get_account_currency()
    measured_count = len(active_df)
    pending_display_count = len(pending_attr_df) + len(dormant_df)

    # Render period header
    if not impact_df.empty:
        _render_period_header(horizon_config, latest_data_date, full_summary, measured_count, pending_display_count)

    # Get display summary
    display_summary = full_summary.get('validated' if show_validated_only else 'all', {})

    # Get verified impact (needed for attribution calculation)
    total_verified_impact = display_summary.get('attributed_impact_universal', display_summary.get('decision_impact', 0))

    # ==========================================
    # ROAS ATTRIBUTION WATERFALL - DISABLED (v3.3 Phase 1)
    # ==========================================
    # ISSUE IDENTIFIED: The current roas_attribution.py logic has a mathematical flaw:
    # - CPC/CVR/AOV decomposition explains 100% of ROAS change (by definition)
    # - Adding Decision Impact on top forces Residual = -Decision_Impact (always)
    # - This makes "Residual" meaningless (not unexplained variance, just circular math)
    #
    # v3.3 FIX (deferred to Phase 3 or v3.4):
    # - Use account-level SPC shift (counterfactual baseline) instead of observed decomposition
    # - Separate Market Forces (external) from Decision Impact (internal)
    # - Calculate legitimate residual as: Actual - (Baseline + Market + CPC + Decision)
    #
    # STATUS: Waterfall chart hidden until v3.3 proper implementation is complete
    # ==========================================

    # [DISABLED - v3.2 BACKUP]
    # if selected_client:
    #     from app_core.roas_attribution import get_roas_attribution
    #     roas_attr = get_roas_attribution(selected_client, days=30, decision_impact_value=total_verified_impact)
    #     if roas_attr:
    #         display_summary.update(roas_attr)

    # Render hero banner
    render_hero_banner(
        active_df, currency, horizon_config['label'],
        total_verified_impact=total_verified_impact,
        summary=display_summary,
        mature_count=measured_count,
        pending_count=pending_display_count,
        canonical_metrics=canonical_metrics
    )

    # [DISABLED - v3.2 BACKUP]
    # Render ROAS Attribution Waterfall (v3.3)
    # if not active_df.empty and canonical_metrics and getattr(canonical_metrics, 'has_data', False):
    #     render_roas_waterfall(
    #         active_df,
    #         decision_impact_dollars=canonical_metrics.attributed_impact,
    #         currency=currency
    #     )

    st.divider()

    # Render main analytics
    with st.expander("▸ Measured Impact Details", expanded=True):
        pending_tab_label = f"▸ Pending Impact ({len(pending_attr_df) + len(dormant_df)})" if (len(pending_attr_df) + len(dormant_df)) > 0 else "▸ Pending Impact"
        tab_measured, tab_pending = st.tabs(["▸ Measured Impact", pending_tab_label])

        with tab_measured:
            if active_df.empty:
                from ui.components.empty_states import render_empty_state
                render_empty_state('filtered_empty')
            else:
                render_impact_analytics(
                    display_summary, active_df, show_validated_only,
                    mature_count=measured_count, pending_count=pending_display_count,
                    raw_impact_df=impact_df, canonical_metrics=canonical_metrics
                )

        with tab_pending:
            if not pending_attr_df.empty:
                st.markdown("### ⏳ Pending Attribution")
                st.caption("These actions are waiting for Amazon attribution data to settle.")
                pending_display = pending_attr_df[['action_date', 'action_type', 'target_text', 'maturity_status']].copy()
                pending_display.columns = ['Action Date', 'Type', 'Target', 'Status']
                st.dataframe(pending_display, use_container_width=True, hide_index=True)
                st.divider()

            if not dormant_df.empty:
                render_dormant_table(dormant_df)

            if pending_attr_df.empty and dormant_df.empty:
                st.success("✨ All executed optimizations have measured activity!")
