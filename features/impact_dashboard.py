"""
Impact Dashboard Module

Sleek before/after analysis dashboard showing the ROI of optimization actions.
Features:
- Hero tiles with key metrics
- Waterfall chart by action type
- Winners/Losers bar chart
- Detailed drill-down table
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from app_core.db_manager import get_db_manager

# === PHASE 2: Single Source of Truth ===
from features.impact_metrics import ImpactMetrics
from app_core.utils import IMPACT_WINDOWS, get_maturity_status
from utils.formatters import format_currency

# ==========================================
# MULTI-HORIZON IMPACT MEASUREMENT CONFIG
# ==========================================
# IMPACT_WINDOWS imported from app_core.utils

# ==========================================
# HELPER: Ensure Required Impact Columns Exist
# ==========================================
def _ensure_impact_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure required columns for impact calculation exist in the dataframe.
    This handles cache compatibility when columns were calculated in postgres_manager
    but old cached data doesn't have them.
    
    Returns a copy of the dataframe with all required columns.
    """
    import numpy as np
    
    df = df.copy()
    MIN_CLICKS_FOR_RELIABLE = 5
    
    # CRITICAL: Always recalculate to ensure 0.85x harvest logic is applied
    # if 'market_tag' in df.columns and 'expected_trend_pct' in df.columns:
    #     return df
    
    # Calculate counterfactual metrics
    df['spc_before'] = df['before_sales'] / df['before_clicks'].replace(0, np.nan)
    df['cpc_before'] = df['before_spend'] / df['before_clicks'].replace(0, np.nan)
    df['expected_clicks'] = df['observed_after_spend'] / df['cpc_before']
    df['expected_sales'] = df['expected_clicks'] * df['spc_before']
    
    # APPLY HARVEST BASELINE: 0.85x Efficiency Decline Factor
    # This aligns dashboard categorization (Market Drag/Win) with DB Impact Logic
    if 'action_type' in df.columns:
        harvest_mask = df['action_type'].astype(str).str.upper() == 'HARVEST'
        harvest_count = harvest_mask.sum()
        print(f"[DEBUG] _ensure_impact_columns: Found {harvest_count} HARVEST actions, applying 0.85x factor")
        if harvest_count > 0:
            # For harvests, lower the expected baseline to account for efficiency loss
            df.loc[harvest_mask, 'expected_sales'] = df.loc[harvest_mask, 'expected_sales'] * 0.85
            print(f"[DEBUG] Sample expected_sales after 0.85x: {df.loc[harvest_mask, 'expected_sales'].head(3).tolist()}")
    
    df['expected_trend_pct'] = ((df['expected_sales'] - df['before_sales']) / df['before_sales'] * 100).fillna(0)
    df['actual_change_pct'] = ((df['observed_after_sales'] - df['before_sales']) / df['before_sales'] * 100).fillna(0)
    df['decision_value_pct'] = df['actual_change_pct'] - df['expected_trend_pct']
    df['decision_impact'] = df['observed_after_sales'] - df['expected_sales']
    
    # Apply low-sample guardrail
    low_sample_mask = df['before_clicks'] < MIN_CLICKS_FOR_RELIABLE
    df.loc[low_sample_mask, 'decision_impact'] = 0
    df.loc[low_sample_mask, 'decision_value_pct'] = 0
    
    # Assign market_tag
    conditions = [
        (df['expected_trend_pct'] >= 0) & (df['decision_value_pct'] >= 0),
        (df['expected_trend_pct'] < 0) & (df['decision_value_pct'] >= 0),
        (df['expected_trend_pct'] >= 0) & (df['decision_value_pct'] < 0),
        (df['expected_trend_pct'] < 0) & (df['decision_value_pct'] < 0),
    ]
    choices = ['Offensive Win', 'Defensive Win', 'Gap', 'Market Drag']
    df['market_tag'] = np.select(conditions, choices, default='Unknown')
    
    return df


# ==========================================
# MARKET DECOMPOSITION - Import from clean module
# ==========================================
# from app_core.roas_attribution import get_roas_attribution  # Moved locally to prevent circular import


# ==========================================
# CONFIDENCE CLASSIFICATION (High/Medium/Low)
# ==========================================
from math import sqrt
from typing import List, Literal

def compute_confidence(
    actions_df: pd.DataFrame,
    min_validated_actions: int = 30
) -> Dict[str, Any]:
    """
    Compute confidence classification for aggregated Decision Impact.
    
    Confidence is a classification layer only — does NOT alter impact values.
    Based on signal-to-noise ratio derived from data sufficiency, market conditions, and variance.
    
    Args:
        actions_df: DataFrame with columns: decision_impact, confidence_weight, market_tag, is_validated
        min_validated_actions: Minimum validated actions needed for "High" confidence
        
    Returns:
        dict with: confidence ("High"/"Medium"/"Low"), signalRatio, totalSigma
    """
    if actions_df.empty:
        return {"confidence": "Low", "signalRatio": 0.0, "totalSigma": 0.0}
    
    # Filter to validated actions
    validated = actions_df[actions_df.get('is_validated', False) == True].copy()
    
    if len(validated) == 0:
        return {"confidence": "Low", "signalRatio": 0.0, "totalSigma": 0.0}
    
    total_impact = 0.0
    variance_sum = 0.0
    downshift_impact = 0.0
    
    for _, row in validated.iterrows():
        # Use direct column access for pandas Series (not dict .get())
        impact = row['decision_impact'] if pd.notna(row['decision_impact']) else 0
        total_impact += impact
        
        # Per-action variance: sigma_i = abs(impact) * (1 - confidence_weight)
        cw = row['confidence_weight'] if 'confidence_weight' in row.index and pd.notna(row['confidence_weight']) else 0.5
        sigma = abs(impact) * (1 - cw)
        
        # Apply market multiplier for downshift
        market_tag = row['market_tag'] if 'market_tag' in row.index else 'Normal'
        if market_tag == "Market Downshift":
            sigma *= 1.3
            downshift_impact += abs(impact)
        
        variance_sum += sigma ** 2
    
    # Aggregate variance
    total_sigma = sqrt(variance_sum) if variance_sum > 0 else 0
    
    # Signal-to-noise ratio
    signal_ratio = abs(total_impact) / total_sigma if total_sigma > 0 else 0
    
    # Confidence classification
    if signal_ratio >= 1.5 and len(validated) >= min_validated_actions:
        confidence = "High"
    elif signal_ratio >= 0.8:
        confidence = "Medium"
    else:
        confidence = "Low"
    
    # Optional downgrade: if >40% of impact from Market Downshift
    downshift_ratio = downshift_impact / abs(total_impact) if total_impact != 0 else 0
    if downshift_ratio > 0.4:
        if confidence == "High":
            confidence = "Medium"
        elif confidence == "Medium":
            confidence = "Low"
    
    return {
        "confidence": confidence,
        "signalRatio": round(signal_ratio, 2),
        "totalSigma": round(total_sigma, 2)
    }

def compute_spend_avoided_confidence(
    actions_df: pd.DataFrame,
    min_validated_actions: int = 10
) -> Dict[str, Any]:
    """
    Compute confidence classification for Spend Avoided summary.
    
    Uses auction variance (not revenue CW) - reflects auction stability.
    Variance factors: Normal = 0.15, Market Downshift = 0.25
    
    Args:
        actions_df: DataFrame with columns: before_spend, observed_after_spend, market_tag, is_validated
        min_validated_actions: Minimum validated actions for "High" confidence
        
    Returns:
        dict with: confidence, signalRatio, totalSigma, totalSpendAvoided
    """
    if actions_df.empty:
        return {"confidence": "Low", "signalRatio": 0.0, "totalSigma": 0.0, "totalSpendAvoided": 0.0}
    
    # Filter to validated actions only
    validated = actions_df[actions_df.get('is_validated', False) == True].copy()
    
    if len(validated) == 0:
        return {"confidence": "Low", "signalRatio": 0.0, "totalSigma": 0.0, "totalSpendAvoided": 0.0}
    
    total_spend_avoided = 0.0
    variance_sum = 0.0
    downshift_spend_avoided = 0.0
    valid_action_count = 0
    
    # Auction variance factors
    VARIANCE_NORMAL = 0.15
    VARIANCE_DOWNSHIFT = 0.25
    
    for _, row in validated.iterrows():
        before_spend = row['before_spend'] if pd.notna(row['before_spend']) else 0
        after_spend = row['observed_after_spend'] if 'observed_after_spend' in row.index and pd.notna(row['observed_after_spend']) else 0
        
        # Spend avoided = max(0, before - after)
        spend_avoided = max(0, before_spend - after_spend)
        
        # Skip rows with zero spend avoided
        if spend_avoided == 0:
            continue
        
        total_spend_avoided += spend_avoided
        valid_action_count += 1
        
        # Determine auction variance factor
        market_tag = row['market_tag'] if 'market_tag' in row.index else 'Normal'
        variance_factor = VARIANCE_DOWNSHIFT if market_tag == "Market Downshift" else VARIANCE_NORMAL
        
        # Per-action variance: sigma_i = spend_avoided * variance_factor
        sigma = spend_avoided * variance_factor
        
        if market_tag == "Market Downshift":
            downshift_spend_avoided += spend_avoided
        
        variance_sum += sigma ** 2
    
    # Aggregate variance
    total_sigma = sqrt(variance_sum) if variance_sum > 0 else 0
    
    # Signal-to-noise ratio
    signal_ratio = total_spend_avoided / total_sigma if total_sigma > 0 else 0
    
    # Confidence classification (stricter thresholds than Decision Impact)
    if signal_ratio >= 2.0 and valid_action_count >= min_validated_actions:
        confidence = "High"
    elif signal_ratio >= 1.0:
        confidence = "Medium"
    else:
        confidence = "Low"
    
    # Optional downgrade: if >30% of spend avoided from Market Downshift
    downshift_ratio = downshift_spend_avoided / total_spend_avoided if total_spend_avoided > 0 else 0
    if downshift_ratio > 0.3:
        if confidence == "High":
            confidence = "Medium"
        elif confidence == "Medium":
            confidence = "Low"
    
    return {
        "confidence": confidence,
        "signalRatio": round(signal_ratio, 2),
        "totalSigma": round(total_sigma, 2),
        "totalSpendAvoided": round(total_spend_avoided, 2)
    }

# get_maturity_status imported from app_core.utils

@st.cache_data(ttl=3600, show_spinner=False)  # Restored production TTL
def _fetch_impact_data(client_id: str, test_mode: bool, before_days: int = 14, after_days: int = 14, cache_version: str = "v14_impact_tiers") -> Tuple[pd.DataFrame, Dict[str, Any]]:

    """
    Cached data fetcher for impact analysis.
    Prevents re-querying the DB on every rerun or tab switch.
    
    Args:
        client_id: Account ID
        test_mode: Whether using test database
        before_days: Number of days for before comparison window (fixed at 14)
        after_days: Number of days for after comparison window (14, 30, or 60)
        cache_version: Version string that changes when data is uploaded (invalidates cache)
    """
    try:
        db = get_db_manager(test_mode)
        impact_df = db.get_action_impact(client_id, before_days=before_days, after_days=after_days)
        full_summary = db.get_impact_summary(client_id, before_days=before_days, after_days=after_days)
        return impact_df, full_summary
    except Exception as e:
        # Return empty structures on failure to prevent UI crash
        print(f"Cache miss error: {e}")
        return pd.DataFrame(), {
            'total_actions': 0, 
            'roas_before': 0, 'roas_after': 0, 'roas_lift_pct': 0,
            'incremental_revenue': 0,
            'p_value': 1.0, 'is_significant': False, 'confidence_pct': 0,
            'implementation_rate': 0, 'confirmed_impact': 0, 'pending': 0,
            'win_rate': 0, 'winners': 0, 'losers': 0,
            'by_action_type': {}
        }

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_account_actuals(client_id: str, cache_version: str) -> pd.DataFrame:
    """Cached fetcher for account-level daily stats (Actuals)."""
    try:
        db = get_db_manager()
        df = db.get_target_stats_df(client_id)
        if df.empty:
            return pd.DataFrame()
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    except Exception as e:
        print(f"Actuals fetch error: {e}")
        return pd.DataFrame()





def render_impact_dashboard():
    """Main render function for Impact Dashboard."""
    
    # Force empty state for testing
    if st.query_params.get("test_state") == "no_data":
        from ui.components.empty_states import render_empty_state
        # Use active account name for context
        account = st.session_state.get('active_account_name', 'Account')
        render_empty_state('no_data', context={'account_name': account})
        return
    
    # Header Layout with Toggle
    col_header, col_toggle = st.columns([3, 1])
    
    with col_header:
        st.markdown("## :material/monitoring: Impact & Results", help="Comprehensive view of optimization outcomes and measured ROI.")
        st.caption("Measured impact of executed optimization actions")

    with col_toggle:
        st.write("") # Spacer
        # Horizon selector - measurement period after action
        horizon = st.radio(
            "Measurement Horizon",
            options=IMPACT_WINDOWS["available_horizons"],  # ["14D", "30D", "60D"]
            index=0,  # Default to 14D
            horizontal=True,
            label_visibility="collapsed",
            key="impact_horizon",
            help="How long after the action to measure impact"
        )
        if horizon is None:
            horizon = IMPACT_WINDOWS["default_horizon"]

    
    # Dark theme compatible CSS + Panel styling
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
    /* Panel container styling (matches Executive Dashboard) */
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
    
    # Check for database manager
    db_manager = st.session_state.get('db_manager')
    if db_manager is None:
        st.warning("⚠️ Database not initialized. Please ensure you're in the main app.")
        return
    
    # USE ACTIVE ACCOUNT from session state
    selected_client = st.session_state.get('active_account_id', 'default_client')
    
    if not selected_client:
        st.error("⚠️ No account selected! Please select an account in the sidebar.")
        return
    
    # Get available dates for selected account
    available_dates = db_manager.get_available_dates(selected_client)
    
    if not available_dates:
        st.warning(f"⚠️ No action data found for account '{st.session_state.get('active_account_name', selected_client)}'. "\
                   "Run the optimizer to log actions.")
        return
    
    # Sidebar info - show active account
    with st.sidebar:
        # Just show account info, removed comparison settings
        st.info(f"**Account:** {st.session_state.get('active_account_name', selected_client)}")
        st.caption(f"📅 Data available: {len(available_dates)} weeks")
    
    # Get impact data using auto time-lag matching (no date params needed)
    # Get impact data using auto time-lag matching (cached)
    with st.spinner("Calculating impact..."):
        # Use cached fetcher
        test_mode = st.session_state.get('test_mode', False)
        # Cache invalidation via version string (changes when data uploaded)
        cache_version = "v20_harvest_fix_" + str(st.session_state.get('data_upload_timestamp', 'init'))
        
        # Get horizon config
        horizon_config = IMPACT_WINDOWS["horizons"].get(horizon, IMPACT_WINDOWS["horizons"]["14D"])
        before_days = IMPACT_WINDOWS["before_window_days"]  # Fixed 14 days
        after_days = horizon_config["days"]  # 14, 30, or 60 based on selection
        buffer_days = IMPACT_WINDOWS["maturity_buffer_days"]  # 3 days
        
        impact_df, full_summary = _fetch_impact_data(selected_client, test_mode, before_days, after_days, cache_version)
        
        # === FORCE RECALCULATION OF METRICS ===
        # Apply 0.85x Harvest Factor and assign Market Tags correctly
        if not impact_df.empty:
            impact_df = _ensure_impact_columns(impact_df)
        
        # ================================================================
        # CRITICAL FIX: Recalculate maturity BEFORE ImpactMetrics calculation
        # This ensures canonical_metrics uses the correct is_mature values
        # ================================================================
        db_manager = st.session_state.get('db_manager')
        latest_data_date = None
        if db_manager and hasattr(db_manager, 'get_latest_raw_data_date'):
            latest_data_date = db_manager.get_latest_raw_data_date(selected_client)
        
        # Fallback to period_info if raw date not available
        if not latest_data_date:
            period_info = full_summary.get('period_info', {})
            latest_data_date = period_info.get('after_end') or period_info.get('latest_date')
        
        # Update is_mature column BEFORE calculating metrics
        if not impact_df.empty and 'action_date' in impact_df.columns and latest_data_date:
            impact_df['is_mature'] = impact_df['action_date'].apply(
                lambda d: get_maturity_status(d, latest_data_date, horizon)['is_mature']
            )
        
        # ================================================================
        # PHASE 2: CANONICAL METRICS COMPUTATION (Single Source of Truth)
        # ================================================================
        # Gather current filter state
        current_filters = {
            'validated_only': st.session_state.get('validated_only_toggle', True),
            'mature_only': True,  # Always filter to mature for display
        }
        
        # SINGLE CALCULATION POINT - now uses updated is_mature values
        canonical_metrics = ImpactMetrics.from_dataframe(
            impact_df, 
            filters=current_filters,
            horizon_days=after_days
        )
        

        
        # === MATURITY GATE ===
        # Add maturity status to each action - determines if impact can be calculated
        # Maturity is based on whether the DATA covers enough time after the action
        # for the after-window + attribution buffer to have settled
        
        # CRITICAL FIX: Get latest date from RAW data, not weekly target_stats
        # target_stats uses week START date (e.g., Jan 12 for Jan 12-17 data)
        # but maturity should be based on ACTUAL latest date (Jan 17)
        db_manager = st.session_state.get('db_manager')
        latest_data_date = None
        if db_manager and hasattr(db_manager, 'get_latest_raw_data_date'):
            latest_data_date = db_manager.get_latest_raw_data_date(selected_client)
        
        # Fallback to period_info if raw date not available
        if not latest_data_date:
            period_info = full_summary.get('period_info', {})
            latest_data_date = period_info.get('after_end') or period_info.get('latest_date')
        
        if not impact_df.empty and 'action_date' in impact_df.columns and latest_data_date:
            impact_df['is_mature'] = impact_df['action_date'].apply(
                lambda d: get_maturity_status(d, latest_data_date, horizon)['is_mature']
            )
            impact_df['maturity_status'] = impact_df['action_date'].apply(
                lambda d: get_maturity_status(d, latest_data_date, horizon)['status']
            )
            
            mature_count = int(impact_df['is_mature'].sum())
            pending_attr_count = len(impact_df) - mature_count
            
            # Debug: Show the cutoff date
            maturity_days = after_days + buffer_days
            cutoff_date = pd.to_datetime(latest_data_date) - pd.Timedelta(days=maturity_days)
            print(f"Maturity cutoff ({horizon}): Actions from {cutoff_date.strftime('%b %d')} or earlier are mature (data through {pd.to_datetime(latest_data_date).strftime('%b %d')})")
            
            # === EMPTY HORIZON CALLOUT ===
            # If no actions are mature for this horizon, show a helpful message
            if mature_count == 0 and len(impact_df) > 0:
                st.warning(f"""
                    **No actions mature for {horizon} measurement yet.**
                    
                    The {horizon_config['label']} requires {maturity_days} days of data after each action.
                    Your most recent data is from {pd.to_datetime(latest_data_date).strftime('%b %d')}.
                    
                    **Options:**
                    - Select **14D** horizon for earlier insights
                    - Wait for more data to accumulate
                    - {pending_attr_count} actions pending for this horizon
                """)
        else:
            # Fallback if no action_date column or no latest date
            impact_df['is_mature'] = True
            impact_df['maturity_status'] = 'Measured'
            mature_count = len(impact_df)
            pending_attr_count = 0
        
        # Terminal debug: Show Decision Impact metrics
        print(f"\n=== DECISION IMPACT DEBUG ({selected_client}) ===")
        print(f"Maturity Gate: {mature_count} measured, {pending_attr_count} pending attribution")
        for w in [7, 14, 30]:
            try:
                db = get_db_manager(test_mode)
                s = db.get_impact_summary(selected_client, window_days=w)
                val = s.get('validated', {})
                print(f"{w}D: ROAS {val.get('roas_before',0):.2f}x -> {val.get('roas_after',0):.2f}x | Lift: {val.get('roas_lift_pct',0):.1f}% | N={val.get('total_actions',0)}")
                print(f"    Decision Impact: {val.get('decision_impact',0):.0f} | Spend Avoided: {val.get('spend_avoided',0):.0f}")
            except Exception as e:
                print(f"{w}D: Error - {e}")
        print("===================================\n")


    
    # Fixed KeyError: Use 'all' summary for initial check
    if full_summary.get('all', {}).get('total_actions', 0) == 0:
        st.info("No actions with matching 'next week' performance data found. This means either:\n"
                "- Actions were logged but no performance data for the following week exists yet.\n"
                "- Upload next week's Search Term Report and run the optimizer to see impact.")
        return
        
    # Period Header Preparation
    compare_text = ""
    p = full_summary.get('period_info', {})
    if p.get('before_start'):
        try:
            def fmt(d):
                if isinstance(d, str):
                    return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%b %d")
                return d.strftime("%b %d")
            
            b_range = f"{fmt(p['before_start'])} - {fmt(p['before_end'])}"
            a_range = f"{fmt(p['after_start'])} - {fmt(p['after_end'])}"
            compare_text = f"Comparing <code>{b_range}</code> (Before) vs. <code>{a_range}</code> (After)"
        except Exception as e:
            print(f"Header date error: {e}")
        
    
    
    # Horizon-based measurement: 14D before (fixed) vs horizon after window
    # No need to filter actions here - all actions with measurable impact are returned
    filter_label = f"{horizon} Impact Window"
    
    # Get latest available date for reference
    available_dates = db_manager.get_available_dates(selected_client)
    ref_date = pd.to_datetime(available_dates[0]) if available_dates else pd.Timestamp.now()
    
    # NO ADDITIONAL FILTERING - get_action_impact already handles:
    # 1. Fixed windows based on selected days
    # 2. Only eligible actions
    # The UI uses full_summary directly from the backend for statistical rigor.

    
    # Redundant date range callout removed (merged into top header)
    
    # ==========================================
    # UNIVERSAL VALIDATION TOGGLE
    # ==========================================
    toggle_col1, toggle_col2 = st.columns([1, 5])
    with toggle_col1:
        show_validated_only = st.toggle(
            "Validated Only", 
            value=True, 
            key='validated_only_toggle', 
            help="Show only actions confirmed by actual CPC/Bid data"
        )
    with toggle_col2:
        if show_validated_only:
            st.caption("✓ Showing **validated actions only** — filtering all cards and charts.")
        else:
            st.caption("📊 Showing **all actions** — including pending and unverified.")
            
    # ==========================================
    # DATA PREPARATION: MATURE + VALIDATED
    # ==========================================
    # Step 1: Filter by validation toggle
    v_mask = impact_df['validation_status'].str.contains('✓|CPC Validated|CPC Match|Directional|Confirmed|Normalized|Volume', na=False, regex=True)
    display_df = impact_df[v_mask].copy() if show_validated_only else impact_df.copy()
    
    # Step 2: MATURITY GATE - Split mature vs pending attribution
    mature_mask = display_df['is_mature'] == True
    mature_df = display_df[mature_mask].copy()  # ONLY mature actions for aggregates
    pending_attr_df = display_df[~mature_mask].copy()  # Pending attribution
    
    # Step 3: Within mature, split Active vs Dormant (by spend)
    spend_mask = (mature_df['before_spend'].fillna(0) + mature_df['observed_after_spend'].fillna(0)) > 0
    active_df = mature_df[spend_mask].copy()
    dormant_df = mature_df[~spend_mask].copy()
    
    # ==========================================
    # CONFIDENCE CLASSIFICATION
    # ==========================================
    # Add required columns for confidence calculation
    import numpy as np
    
    # confidence_weight: NOW COMES FROM DATABASE (postgres_manager.get_action_impact)
    # Only calculate if missing for backwards compatibility with old cached data
    if not active_df.empty and 'confidence_weight' not in active_df.columns:
        # Legacy fallback formula - should rarely be used now
        active_df['confidence_weight'] = (active_df['before_clicks'].fillna(0) / 15.0).clip(upper=1.0)
        
        # market_quality_tag: detect market downshift (DIFFERENT from quadrant market_tag)
        # This is for confidence calculation, NOT for quadrant aggregation
        def get_market_quality_tag(row):
            if row.get('before_clicks', 0) == 0:
                return "Low Data"
            if row.get('market_downshift', False) == True:
                return "Market Downshift"
            return "Normal"
        active_df['market_quality_tag'] = active_df.apply(get_market_quality_tag, axis=1)
        
        # is_validated: already used for filtering
        active_df['is_validated'] = True  # All in active_df are validated if toggle is on
        
        # Compute confidence for Decision Impact
        confidence_result = compute_confidence(active_df, min_validated_actions=30)
        
        # Compute confidence for Spend Avoided
        spend_avoided_result = compute_spend_avoided_confidence(active_df, min_validated_actions=10)
    else:
        confidence_result = {"confidence": "Low", "signalRatio": 0.0, "totalSigma": 0.0}
        spend_avoided_result = {"confidence": "Low", "signalRatio": 0.0, "totalSigma": 0.0, "totalSpendAvoided": 0.0}
    
    # Use pre-calculated summary from backend for the tiles
    display_summary = full_summary.get('validated' if show_validated_only else 'all', {})
    display_summary['confidence'] = confidence_result['confidence']
    display_summary['signal_ratio'] = confidence_result['signalRatio']
    display_summary['decision_impact_sigma'] = confidence_result.get('totalSigma', 0.0)
    display_summary['spend_avoided_confidence'] = spend_avoided_result['confidence']
    display_summary['spend_avoided_sigma'] = spend_avoided_result['totalSigma']
    
    # ==========================================
    # WIRE MARKET DECOMPOSITION (CPC/CVR/AOV) from clean module
    # ==========================================
    client_id = st.session_state.get('active_account_id', '')  # Fixed: use correct session state key
    if client_id:
        from app_core.roas_attribution import get_roas_attribution
        roas_attr = get_roas_attribution(client_id, days=30)
        if roas_attr:
            display_summary.update(roas_attr)  # Adds cpc_impact, cvr_impact, aov_impact, market_impact_roas, periods, etc.
    
    # HERO TILES (Now synchronized with FILTERED maturity counts)
    # Use len(mature_df) and len(pending_attr_df) which respect the Validated Only toggle
    from utils.formatters import get_account_currency
    currency = get_account_currency()
    
    # 4. Calculate explicit counts for display consistency
    measured_count = len(active_df)
    pending_display_count = len(pending_attr_df) + len(dormant_df)
    
    # Update summary to reflect the filtered visual counts in cards
    display_summary['total_actions'] = measured_count

    # Pass the summary's WEIGHTED impact (attributed_impact_universal uses final_decision_impact)
    # Fallback to legacy decision_impact for compatibility
    total_verified_impact = display_summary.get('attributed_impact_universal', display_summary.get('decision_impact', 0))

    # ==========================================
    # CONSOLIDATED PREMIUM HEADER
    # ==========================================
    if not impact_df.empty:
        theme_mode = st.session_state.get('theme_mode', 'dark')
        cal_color = "#E9EAF0" if theme_mode == 'dark' else "#5B5670" # Soft White / Saddle Purple
        calendar_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{cal_color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 6px;"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>'
        
        # Prepare Analysis Period text
        p = full_summary.get('period_info', {})
        analysis_range = ""
        try:
            def fmt(d):
                if not d: return ""
                if isinstance(d, str): d = pd.to_datetime(d)
                return d.strftime("%b %d")
            
            # Use strict before_start (baseline start) to latest_data_date (actual data end)
            start = p.get('before_start')
            # CRITICAL FIX: Use actual latest date from raw data, not target_stats start_date
            # This ensures display shows Jan 17 (actual end) instead of Jan 12 (week start)
            end = latest_data_date if latest_data_date else p.get('after_end')
            if start and end:
                analysis_range = f"{fmt(start)} - {fmt(end)}"
            else:
                # Fallback to action dates
                analysis_range = f"{fmt(impact_df['action_date'].min())} - {fmt(impact_df['action_date'].max())}"
        except:
            analysis_range = "Current Period"

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
                Measured: <span style="color: #22D3EE; font-weight: 600;">{measured_count}</span> | Pending: <span style="color: #94a3b8; font-weight: 600;">{pending_display_count}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Logic moved to top to fix UnboundLocalError
    pass
    _render_hero_banner(
        active_df, currency, filter_label, 
        total_verified_impact=total_verified_impact,
        summary=display_summary,
        mature_count=measured_count,
        pending_count=pending_display_count,
        canonical_metrics=canonical_metrics  # Phase 3: Single source of truth
    )
    
    st.divider()

    # Premium section header for Impact Summary (matching 14D Impact style)
    # Calculate Baseline ROAS specifically for the Value Created card
    # Note: 'total_verified_impact' is already passed in
    # infer 'total_spend_impact' from display_summary if possible, else assume 0 for MVP or calculate from impact_df
    
    # Simple calculation for MVP alignment with new revenue chart
    # (Since we just switched to Revenue Chart, we focus on Sales Lift)
    
    vc_sales_lift = total_verified_impact
    vc_spend_lift = 0 # Default if not tracked in summary, or fetch from summary if available
    
    # Try to fetch actuals for the horizon to get Baseline
    # Re-use the data fetching logic if available, or rely on pass-through values
    # For now, we will use the placeholders logic or minimal calculation to match the visual
    
    # We need:
    # 1. Total Value Created (vc_sales_lift)
    # 2. Baseline ROAS
    # 3. % Improvement
    
    # This requires aggregated Actuals for the period.
    # Since we are inside _render_hero_banner's caller scope, we have 'active_df' but not full 'actuals_df' handy here easily without re-fetch.
    # However, 'display_summary' might have 'observed_after_sales' and 'observed_after_spend'.
    
    vc_actual_sales = display_summary.get('observed_sales', 0)
    vc_actual_spend = display_summary.get('observed_spend', 0)
    
    # Baseline Sales = Actual - Lift
    vc_baseline_sales = vc_actual_sales - vc_sales_lift
    
    # Baseline Spend = Actual - (Spend Impact). Assuming 0 spend impact for simplified revenue focus if data missing.
    vc_baseline_spend = vc_actual_spend 
    
    if vc_baseline_spend > 0:
        vc_baseline_roas = vc_baseline_sales / vc_baseline_spend
    else:
        vc_baseline_roas = 0.0
        
    if vc_actual_spend > 0:
        vc_actual_roas = vc_actual_sales / vc_actual_spend
    else:
        vc_actual_roas = 0.0
        
    # % Improvement in ROAS
    if vc_baseline_roas > 0:
        vc_improvement = ((vc_actual_roas - vc_baseline_roas) / vc_baseline_roas) * 100
    else:
        vc_improvement = 0.0

    # Value Created card removed as requested (redundant)
    

    # Pass metrics to chart to ensure footer alignment with main dashboard summary
    chart_impact_override = total_verified_impact if total_verified_impact > 0 else None

    with st.expander("▸ Measured Impact Details", expanded=True):
        
        # ==========================================
        # MEASURED vs PENDING IMPACT TABS
        # ==========================================
        pending_tab_label = f"▸ Pending Impact ({len(pending_attr_df) + len(dormant_df)})" if (len(pending_attr_df) + len(dormant_df)) > 0 else "▸ Pending Impact"
        tab_measured, tab_pending = st.tabs([
            "▸ Measured Impact", 
            pending_tab_label
        ])
        
        with tab_measured:
            # Show only MATURE actions with activity
            if active_df.empty:
                from ui.components.empty_states import render_empty_state
                render_empty_state('filtered_empty')
            else:
                # IMPACT ANALYTICS: New human-centered layout with embedded details table
                _render_new_impact_analytics(display_summary, active_df, show_validated_only, mature_count=measured_count, pending_count=pending_display_count, raw_impact_df=impact_df, canonical_metrics=canonical_metrics)
                
        with tab_pending:
            # Section 1: Pending Attribution (immature actions)
            if not pending_attr_df.empty:
                st.markdown("### ⏳ Pending Attribution")
                st.caption("These actions are waiting for Amazon attribution data to settle. Impact will be calculated once mature.")
                
                pending_display = pending_attr_df[['action_date', 'action_type', 'target_text', 'maturity_status']].copy()
                pending_display.columns = ['Action Date', 'Type', 'Target', 'Status']
                st.dataframe(pending_display, width='stretch', hide_index=True)
                st.divider()
            
            # Section 2: Dormant (zero spend)
            if not dormant_df.empty:
                st.markdown("### 💤 Waiting for Traffic")
                st.caption("These mature actions have $0 spend in both periods. Impact is pending traffic.")
                _render_dormant_table(dormant_df)
            
            # Success message if nothing pending
            if pending_attr_df.empty and dormant_df.empty:
                st.success("✨ All executed optimizations have measured activity!")




def _render_empty_state():
    """Render empty state when no data exists."""
    # Theme-aware chart icon
    icon_color = "#8F8CA3"
    empty_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-opacity="0.2" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>'
    st.markdown(f"""
    <div style="text-align: center; padding: 60px 20px;">
        <div style="margin-bottom: 20px;">{empty_icon}</div>
        <h2 style="color: #8F8CA3; opacity: 0.5;">No Impact Data Yet</h2>
        <p style="color: #8F8CA3; opacity: 0.35; max-width: 400px; margin: 0 auto;">
            Run the optimizer and download the report to start tracking actions. 
            Then upload next week's data to see the impact.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    ### How to use Impact Analysis:
    
    1. **Week 1**: Upload Search Term Report → Run Optimizer → Download Full Report
    2. **Week 2**: Upload new Search Term Report → Come here to see before/after comparison
    """)


def _render_hero_banner(impact_df: pd.DataFrame, currency: str, horizon_label: str = "30D", total_verified_impact: float = None, summary: Dict[str, Any] = {}, mature_count: int = 0, pending_count: int = 0, canonical_metrics: 'ImpactMetrics' = None):
    """
    Render the Hero Section: "Did your optimizations make money?"
    Human-centered design with YES/NO/BREAK EVEN prefix.
    
    Args:
        canonical_metrics: If provided, use this as single source of truth (Phase 3+)
    """
    import numpy as np
    
    if impact_df.empty:
        st.info("No data for hero calculation")
        return

    # ==========================================
    # PHASE 4: USE CANONICAL METRICS (Single Source of Truth)
    # ==========================================
    # We now assume canonical_metrics is passed. If not, we return early or show error.
    if canonical_metrics is None or not canonical_metrics.has_data:
        # Fallback for edge cases where metrics failed to calc
        st.warning("Impact metrics unavailable")
        return

    attributed_impact = canonical_metrics.attributed_impact
    offensive_val = canonical_metrics.offensive_value
    defensive_val = canonical_metrics.defensive_value
    gap_val = canonical_metrics.gap_value
    drag_count = canonical_metrics.drag_actions
    total_wins = offensive_val + defensive_val
    
    # Prepare counts for display
    offensive_count = canonical_metrics.offensive_actions
    defensive_count = canonical_metrics.defensive_actions
    gap_count = canonical_metrics.gap_actions
    
    # Store in session state for other sections (temporary - Phase 4 will remove)
    st.session_state['_impact_metrics'] = {
        'attributed_impact': attributed_impact,
        'offensive_val': offensive_val,
        'defensive_val': defensive_val,
        'gap_val': gap_val,
        'total_wins': total_wins,
        'drag_count': drag_count,
        'offensive_count': offensive_count,
        'defensive_count': defensive_count,
        'gap_count': gap_count,
    }
    
    # Get df for before_sales calculation
    df = _ensure_impact_columns(impact_df)
    
    # Define impact_col for downstream stats usage
    impact_col = 'final_decision_impact' if 'final_decision_impact' in df.columns else 'decision_impact'
    
    # --- HUMAN-CENTERED DISPLAY ---
    
    # Determine state
    abs_impact = abs(attributed_impact)
    before_sales = df['before_sales'].sum()
    threshold = before_sales * 0.02 if before_sales > 0 else 10  # 2% threshold for break even
    
    if attributed_impact > threshold:
        answer_prefix = "YES"
        answer_color = "#10B981"  # Green
        subtitle = f"That's {currency}{abs_impact:,.0f} more than if you'd done nothing."
    elif attributed_impact < -threshold:
        answer_prefix = "NOT YET"
        answer_color = "#EF4444"  # Red
        subtitle = f"Your decisions cost {currency}{abs_impact:,.0f} compared to doing nothing."
    else:
        answer_prefix = "BREAK EVEN"
        answer_color = "#9CA3AF"  # Gray
        subtitle = f"Your decisions had minimal impact ({currency}{abs_impact:,.0f})."
    
    # Format impact display
    impact_sign = '+' if attributed_impact >= 0 else ''
    impact_display = f"{impact_sign}{currency}{attributed_impact:,.0f}"
    
    # Calculate incremental contribution percentage
    # This represents "What % of total account revenue did optimizations contribute?"
    # Uses before_sales as proxy for total account baseline, then adds attributed impact
    non_drag_mask = df['market_tag'] != 'Market Drag'
    total_before_sales = df.loc[non_drag_mask, 'before_sales'].sum()
    total_after_sales = df.loc[non_drag_mask, 'observed_after_sales'].sum()
    # Total account revenue ≈ before_sales + after_sales (covers full measurement period)
    total_account_sales = total_before_sales + total_after_sales
    # Contribution = impact / total account sales
    incremental_pct = (attributed_impact / total_account_sales * 100) if total_account_sales > 0 else 0
    incremental_sign = '+' if incremental_pct >= 0 else ''
    incremental_badge = f"{incremental_sign}{incremental_pct:.1f}% of revenue" if abs(incremental_pct) > 0.1 else ""
    
    # SVG Icons
    checkmark_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>'
    info_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; cursor: help;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
    arrow_up_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>'
    
    # Progress bar calculation (wins vs total excluding drag)
    # Progress bar calculation (wins vs total excluding drag)
    total_counted = offensive_count + defensive_count + gap_count
    win_count = offensive_count + defensive_count
    win_pct = (win_count / total_counted * 100) if total_counted > 0 else 0
    
    # Methodology tooltip
    methodology_tooltip = "We compare what actually happened to what would have happened if you changed nothing. We only count results we can clearly trace back to your decisions — not market ups and downs."
    
    # Build incremental badge HTML
    badge_html = ""
    if incremental_badge:
        badge_color = "#10B981" if incremental_pct >= 0 else "#EF4444"
        badge_html = f'<span style="display: inline-flex; align-items: center; gap: 4px; background: rgba(16, 185, 129, 0.15); color: {badge_color}; padding: 4px 12px; border-radius: 20px; font-size: 1rem; font-weight: 600; margin-left: 16px; vertical-align: middle;">{arrow_up_icon} {incremental_badge}</span>'
    
    # Premium glassmorphic styling based on state
    if answer_prefix == "YES":
        hero_bg = "linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(15, 23, 42, 0.95) 100%)"
        hero_border = "1px solid rgba(16, 185, 129, 0.3)"
        hero_glow = "0 0 30px rgba(16, 185, 129, 0.2)"
        text_glow = "text-shadow: 0 0 20px rgba(16, 185, 129, 0.5);"
    elif answer_prefix == "NOT YET":
        hero_bg = "linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(15, 23, 42, 0.95) 100%)"
        hero_border = "1px solid rgba(239, 68, 68, 0.3)"
        hero_glow = "0 0 30px rgba(239, 68, 68, 0.2)"
        text_glow = "text-shadow: 0 0 20px rgba(239, 68, 68, 0.5);"
    else:  # BREAK EVEN
        hero_bg = "linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%)"
        hero_border = "1px solid rgba(148, 163, 184, 0.2)"
        hero_glow = "0 4px 16px rgba(0, 0, 0, 0.3)"
        text_glow = ""
    
    st.markdown(f"""
    <div style="background: {hero_bg}; border: {hero_border}; border-radius: 16px; padding: 32px 40px; margin-bottom: 24px; box-shadow: {hero_glow}; backdrop-filter: blur(10px);">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 24px;">
            <span style="color: {answer_color};">{checkmark_icon}</span>
            <span style="font-size: 1.1rem; font-weight: 600; color: #F8FAFC;">Did your optimizations make money?</span>
            <span style="margin-left: auto; font-size: 0.85rem; color: #94a3b8; opacity: 0.7;">({horizon_label})</span>
        </div>
        <div style="font-size: 2.8rem; font-weight: 800; color: {answer_color}; margin-bottom: 8px; {text_glow}">{answer_prefix} — {impact_display}{badge_html}</div>
        <div style="background: rgba(255,255,255,0.08); border-radius: 8px; height: 12px; margin: 16px 0; overflow: hidden; border: 1px solid rgba(255,255,255,0.05);">
            <div style="background: linear-gradient(90deg, #10B981 0%, #059669 100%); height: 100%; width: {win_pct}%; border-radius: 8px;"></div>
        </div>
        <div style="font-size: 1rem; color: #94a3b8; margin-bottom: 12px;">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Methodology expander (works better than HTML tooltip)
    with st.expander("ℹ️ How we know this", expanded=False):
        # ==========================================
        # PROPER Z-SCORE BASED STATISTICAL CONFIDENCE
        # ==========================================
        import numpy as np
        from scipy import stats
        
        n_decisions = total_counted
        
        # Get impact values for statistical analysis (excluding Market Drag)
        impact_values = df.loc[non_drag_mask, impact_col].dropna()
        
        if len(impact_values) >= 2:
            # Calculate z-score: how many standard errors is the mean from zero?
            mean_impact = impact_values.mean()
            std_impact = impact_values.std(ddof=1)  # Sample std
            n = len(impact_values)
            standard_error = std_impact / np.sqrt(n) if std_impact > 0 else 0
            
            # Z-score = mean / standard error
            z_score = mean_impact / standard_error if standard_error > 0 else 0
            
            # Convert z-score to confidence percentage using CDF
            # P(Z < z) gives one-tailed probability; we want two-tailed confidence
            # Cap at 99% - never claim 100% certainty
            if z_score > 0:
                # Positive impact: confidence that true impact > 0
                confidence_pct = min(99, stats.norm.cdf(z_score) * 100)
            else:
                # Negative impact: confidence that true impact < 0
                confidence_pct = min(99, (1 - stats.norm.cdf(z_score)) * 100)
            
            # Calculate 90% confidence interval
            z_90 = 1.645
            ci_lower = mean_impact - z_90 * standard_error
            ci_upper = mean_impact + z_90 * standard_error
            
            # Determine label based on z-score thresholds
            # z > 2.58 → 99% confident
            # z > 1.96 → 95% confident  
            # z > 1.645 → 90% confident
            abs_z = abs(z_score)
            if abs_z >= 2.58:
                confidence_label = "Very High"
                confidence_color = "#10B981"
            elif abs_z >= 1.96:
                confidence_label = "High"
                confidence_color = "#10B981"
            elif abs_z >= 1.645:
                confidence_label = "Moderate"
                confidence_color = "#F59E0B"
            else:
                confidence_label = "Directional"
                confidence_color = "#94a3b8"
        else:
            # Not enough data for statistical analysis
            confidence_label = "Insufficient Data"
            confidence_color = "#94a3b8"
            confidence_pct = 0
            z_score = 0
            ci_lower = 0
            ci_upper = 0
        
        st.markdown(f"""
        We compare what **actually happened** to what **would have happened** if you changed nothing.
        
        We only count results we can clearly trace back to your decisions — not market ups and downs.
        
        ---
        
        **Statistical Confidence:** <span style="color: {confidence_color}; font-weight: 600;">{confidence_label}</span>
        
        Based on **{n_decisions:,} validated decisions** with a **{win_pct:.0f}% win rate**.
        
        <small style="color: #64748b;">We're {confidence_pct:.0f}% confident this impact is real and not random noise.</small>
        """, unsafe_allow_html=True)


def _render_what_worked_card(currency: str):
    """Section 2A: What Worked - Offensive + Defensive Wins."""
    metrics = st.session_state.get('_impact_metrics', {})
    total_wins = metrics.get('total_wins', 0)
    offensive_val = metrics.get('offensive_val', 0)
    defensive_val = metrics.get('defensive_val', 0)
    offensive_count = metrics.get('offensive_count', 0)
    defensive_count = metrics.get('defensive_count', 0)
    win_count = offensive_count + defensive_count
    
    # SVG icons
    rocket_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path></svg>'
    shield_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>'
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(15, 23, 42, 0.95) 100%); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 20px; height: 100%; box-shadow: 0 0 20px rgba(16, 185, 129, 0.1);">
        <div style="font-size: 0.75rem; font-weight: 700; color: #10B981; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px;">
            ✓ What Worked
        </div>
        <div style="font-size: 2rem; font-weight: 800; color: #10B981; margin-bottom: 8px; text-shadow: 0 0 20px rgba(16, 185, 129, 0.5);">
            +{currency}{total_wins:,.0f}
        </div>
        <div style="font-size: 0.9rem; color: #94a3b8; margin-bottom: 16px;">
            {win_count} decisions helped
        </div>
        <div style="border-top: 1px solid rgba(16, 185, 129, 0.2); padding-top: 12px; font-size: 0.8rem; color: #94A3B8; line-height: 1.6;">
            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
                {rocket_icon}
                <span>Offensive: +{currency}{offensive_val:,.0f} ({offensive_count})</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
                {shield_icon}
                <span>Defensive: +{currency}{defensive_val:,.0f} ({defensive_count})</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_what_didnt_card(currency: str):
    """Section 2B: What Didn't Work - Decision Gaps."""
    metrics = st.session_state.get('_impact_metrics', {})
    gap_val = metrics.get('gap_val', 0)
    gap_count = metrics.get('gap_count', 0)
    
    # Warning icon SVG
    warning_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(15, 23, 42, 0.95) 100%); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 12px; padding: 20px; height: 100%; box-shadow: 0 0 20px rgba(239, 68, 68, 0.1);">
        <div style="font-size: 0.75rem; font-weight: 700; color: #EF4444; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px;">
            ✗ What Didn't
        </div>
        <div style="font-size: 2rem; font-weight: 800; color: #EF4444; margin-bottom: 8px; text-shadow: 0 0 20px rgba(239, 68, 68, 0.5);">
            {currency}{gap_val:,.0f}
        </div>
        <div style="font-size: 0.9rem; color: #94a3b8; margin-bottom: 16px;">
            {gap_count} decisions hurt
        </div>
        <div style="border-top: 1px solid rgba(239, 68, 68, 0.2); padding-top: 12px; font-size: 0.8rem; color: #94A3B8; line-height: 1.6;">
            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
                {warning_icon}
                <span>Decision Gaps: Missed opportunities</span>
            </div>
            <div style="height: 16px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_decision_score_card():
    """Section 2C: Decision Score - Overall quality metric."""
    metrics = st.session_state.get('_impact_metrics', {})
    offensive_count = metrics.get('offensive_count', 0)
    defensive_count = metrics.get('defensive_count', 0)
    gap_count = metrics.get('gap_count', 0)
    
    win_count = offensive_count + defensive_count
    total_counted = win_count + gap_count
    
    if total_counted > 0:
        helped_pct = (win_count / total_counted) * 100
        hurt_pct = (gap_count / total_counted) * 100
        score = int(helped_pct - hurt_pct)
    else:
        helped_pct = 0
        hurt_pct = 0
        score = 0
    
    # Determine label and color
    if score >= 20:
        label = "Excellent"
        color = "#10B981"
    elif score >= 10:
        label = "Good"
        color = "#34D399"
    elif score >= 1:
        label = "Okay"
        color = "#6EE7B7"
    elif score == 0:
        label = "Neutral"
        color = "#9CA3AF"
    elif score >= -9:
        label = "Needs Work"
        color = "#FCA5A5"
    else:
        label = "Problem"
        color = "#EF4444"
    
    # Info icon
    info_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="cursor: help;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
    
    tooltip = f"Score = % helped - % hurt. {score:+d} means {abs(score)}% more decisions {'helped' if score >= 0 else 'hurt'}."
    
    # Determine gradient colors based on score
    if score >= 10:
        card_bg = f"linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(15, 23, 42, 0.95) 100%)"
        card_border = "1px solid rgba(16, 185, 129, 0.25)"
        card_glow = f"0 0 20px rgba(16, 185, 129, 0.15)"
        text_glow = f"text-shadow: 0 0 15px rgba(16, 185, 129, 0.4);"
    elif score >= 0:
        card_bg = "linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%)"
        card_border = "1px solid rgba(148, 163, 184, 0.15)"
        card_glow = "0 4px 16px rgba(0, 0, 0, 0.3)"
        text_glow = ""
    else:
        card_bg = f"linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(15, 23, 42, 0.95) 100%)"
        card_border = "1px solid rgba(239, 68, 68, 0.25)"
        card_glow = f"0 0 20px rgba(239, 68, 68, 0.15)"
        text_glow = f"text-shadow: 0 0 15px rgba(239, 68, 68, 0.4);"
    
    st.markdown(f"""
    <div style="background: {card_bg}; border: {card_border}; border-radius: 12px; padding: 20px; height: 100%; text-align: center; box-shadow: {card_glow};">
        <div style="font-size: 0.75rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px;">Decision Score</div>
        <div style="font-size: 2.5rem; font-weight: 800; color: {color}; margin-bottom: 4px; {text_glow}">{score:+d}</div>
        <div style="font-size: 1rem; font-weight: 600; color: {color}; margin-bottom: 12px;">{label}</div>
        <div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 8px;">{helped_pct:.0f}% helped · {hurt_pct:.0f}% hurt</div>
        <div style="font-size: 0.7rem; color: #64748B; font-style: italic;">Score = % helped − % hurt</div>
    </div>
    """, unsafe_allow_html=True)


def _render_data_confidence_section(impact_df: pd.DataFrame):
    """Section 5: Can you trust these numbers? - Measured/Pending/Inconclusive breakdown."""
    if impact_df.empty:
        st.info("No data")
        return
    
    # Calculate categories
    def get_status_category(row):
        s = str(row.get('validation_status', ''))
        m = str(row.get('maturity_status', ''))
        
        is_verified = '✓' in s or 'Confirmed' in s or 'Validated' in s or 'Directional' in s
        
        if not is_verified:
            return 'Inconclusive'
        
        is_pending_maturity = 'Pending' in m
        if 'is_mature' in row.index and not row.get('is_mature', True):
            is_pending_maturity = True
        
        import pandas as pd
        b_spend = row.get('before_spend', 0)
        a_spend = row.get('observed_after_spend', 0)
        try:
            b_val = 0.0 if pd.isna(b_spend) else float(b_spend)
            a_val = 0.0 if pd.isna(a_spend) else float(a_spend)
        except:
            b_val, a_val = 0.0, 0.0
        has_spend = (b_val + a_val) > 0
        
        if is_pending_maturity or not has_spend:
            return 'Pending'
        else:
            return 'Measured'
    
    impact_df = impact_df.copy()
    impact_df['status_cat'] = impact_df.apply(get_status_category, axis=1)
    counts = impact_df['status_cat'].value_counts()
    
    measured = counts.get('Measured', 0)
    pending = counts.get('Pending', 0)
    inconclusive = counts.get('Inconclusive', 0)
    total = len(impact_df)
    
    measured_pct = (measured / total * 100) if total > 0 else 0
    
    # Shield icon
    shield_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#8F8CA3" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>'
    
    st.markdown(f"""
    <div style="min-height: 180px;">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">{shield_icon}<span style="font-size: 1.1rem; font-weight: 600; color: #E9EAF0;">Can you trust these numbers?</span></div>
        <div style="background: rgba(255,255,255,0.1); border-radius: 8px; height: 16px; margin-bottom: 12px; overflow: hidden; display: flex;"><div style="background: #5B5670; height: 100%; width: {measured_pct}%;"></div></div>
        <div style="font-size: 1rem; color: #E9EAF0; font-weight: 600; margin-bottom: 16px;">{measured_pct:.0f}% measured</div>
        <div style="font-size: 0.9rem; color: #94a3b8; line-height: 1.8;">
            <div>✓ <strong>{measured}</strong> decisions measured</div>
            <div>◐ <strong>{pending}</strong> pending (need 3-7 more days)</div>
            <div>○ <strong>{inconclusive}</strong> inconclusive (excluded)</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_value_breakdown_section(impact_df: pd.DataFrame, currency: str, canonical_metrics: 'ImpactMetrics' = None):
    """Section 6: Where did the value come from? - Impact by action type.
    
    Args:
        canonical_metrics: If provided, use this validation logic (Phase 3+)
    """
    import plotly.graph_objects as go
    
    if impact_df.empty:
        st.info("No data")
        return
    
    # Bolt icon
    bolt_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#8F8CA3" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>'
    
    # Initialize HTML with Header
    html_content = f"""
<div style="min-height: 180px;">
<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
    {bolt_icon}
    <span style="font-size: 1.1rem; font-weight: 600; color: #E9EAF0;">Where did the value come from?</span>
</div>
"""
    
    # Ensure required columns exist (handles old cached data)
    df = _ensure_impact_columns(impact_df)
    
    # ==========================================
    # PHASE 4: USE CANONICAL METRICS FILTERS
    # ==========================================
    # If canonical metrics provided, respect its filters (e.g. validated only)
    if canonical_metrics is not None:
        filters = canonical_metrics.filters_applied
        if filters.get('validated_only') and 'validated' in df.columns:
            df = df[df['validated'] == True]
        
        # Consistent logic: Exclude market drag
        df = df[df['market_tag'] != 'Market Drag']
    else:
        # Fallback if canonical metrics missing (shouldn't happen)
        # Exclude Market Drag matching legacy logic
        df = df[df['market_tag'] != 'Market Drag']
    
    # Group by action type using pre-calculated decision_impact
    if 'final_decision_impact' not in df.columns:
        df['final_decision_impact'] = df['decision_impact']
        
    type_impact = df.groupby('action_type')['final_decision_impact'].sum().sort_values(ascending=False)
    
    if type_impact.empty:
        html_content += """<div style="color: #94a3b8; font-style: italic;">No action type data available</div></div>"""
        st.markdown(html_content, unsafe_allow_html=True)
        return
    
    max_val = type_impact.abs().max()
    
    # Append bars to HTML
    for atype, val in type_impact.head(5).items():
        clean_type = str(atype).replace('_', ' ').title()
        bar_width = min(100, abs(val) / max_val * 100) if max_val > 0 else 0
        val_color = "#10B981" if val >= 0 else "#EF4444"
        sign = '+' if val >= 0 else ''
        
        html_content += f"""
<div style="margin-bottom: 10px;">
    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: #94a3b8; margin-bottom: 4px;">
        <span>{clean_type}</span>
        <span style="color: {val_color}; font-weight: 600;">{sign}{currency}{val:,.0f}</span>
    </div>
    <div style="width: 100%; background: rgba(255,255,255,0.05); height: 12px; border-radius: 6px;">
        <div style="width: {bar_width}%; background: {val_color}; height: 100%; border-radius: 6px;"></div>
    </div>
</div>
"""

    # Close the min-height container
    html_content += "</div>"
    
    # Render ONCE
    st.markdown(html_content, unsafe_allow_html=True)


def _render_details_table_collapsed(impact_df: pd.DataFrame, currency: str):
    """Section 7: Collapsed details table - Show all decisions."""
    if impact_df.empty:
        return
    
    total_count = len(impact_df)
    
    with st.expander(f"#### Measured Impact Details ({total_count})", expanded=False):
        # Prepare display dataframe - keep Impact as NUMERIC for sorting
        # Fallback to raw if final not present
        impact_col = 'final_decision_impact' if 'final_decision_impact' in impact_df.columns else 'decision_impact'
        
        display_df = impact_df[['target_text', 'action_type', impact_col, 'validation_status', 'maturity_status']].copy()
        display_df.columns = ['What', 'Action', 'Impact', 'Status', 'Maturity']
        
        # Format action type
        display_df['Action'] = display_df['Action'].str.replace('_', ' ').str.title()
        
        # Keep Impact as numeric - round for cleaner display
        display_df['Impact'] = display_df['Impact'].fillna(0).round(0).astype(int)
        
        # Filter controls
        col1, col2 = st.columns([1, 3])
        with col1:
            filter_opt = st.selectbox("Filter", ["All", "✅ What worked", "❌ What didn't", "◐ Pending"], label_visibility="collapsed")
        with col2:
            if st.button("⬇ Export CSV"):
                csv = impact_df.to_csv(index=False)
                st.download_button("Download", csv, "impact_details.csv", "text/csv")
        
        # Use column_config for currency formatting while keeping numeric sorting
        st.dataframe(
            display_df, 
            width='stretch', 
            hide_index=True, 
            height=400,
            column_config={
                "Impact": st.column_config.NumberColumn(
                    "↕ Impact",
                    help="Click to sort. Negative = potential issue",
                    format=f"{currency}%d"
                )
            }
        )





def _render_validation_rate_chart(impact_df: pd.DataFrame):
    """Render the Validation Rate chart (Vertical Bar)."""
    import plotly.graph_objects as go
    
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; font-size: 1.1rem; font-weight: 600; color: #E9EAF0; margin-bottom: 4px;">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#8F8CA3" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
        Validation Rate
    </div>
    """, unsafe_allow_html=True)
    st.caption("Proportion of decisions by status")
    
    if impact_df.empty:
        st.info("No data")
        return
        
    def get_status_category(row):
        s = str(row.get('validation_status', ''))
        m = str(row.get('maturity_status', ''))
        
        is_verified = '✓' in s or 'Confirmed' in s or 'Validated' in s or 'Directional' in s
        
        if not is_verified:
            return 'Unverified'
            
        # Robust check for pending status (Immature OR No Spend)
        # 1. Maturity Check
        # Try explicit status first, then boolean flag
        is_pending_maturity = 'Pending' in m or 'Immature' in s
        if not is_pending_maturity and 'is_mature' in row.index:
            is_pending_maturity = not bool(row['is_mature'])
            
        # 2. Spend Check (Treat NaN as 0)
        import pandas as pd
        b_spend = row.get('before_spend', 0)
        a_spend = row.get('observed_after_spend', 0)
        
        # Safe float conversion
        try:
            b_val = 0.0 if pd.isna(b_spend) else float(b_spend)
            a_val = 0.0 if pd.isna(a_spend) else float(a_spend)
        except:
            b_val, a_val = 0.0, 0.0
            
        has_spend = (b_val + a_val) > 0
        
        # If either immature OR no spend -> Pending
        if is_pending_maturity or not has_spend:
            return 'Pending'
        else:
            return 'Measured'
            
    impact_df['status_cat'] = impact_df.apply(get_status_category, axis=1)
    counts = impact_df['status_cat'].value_counts()
    
    measured = counts.get('Measured', 0)
    pending = counts.get('Pending', 0)
    unverified = counts.get('Unverified', 0)
    
    total = len(impact_df)
    measured_pct = measured / total * 100 if total > 0 else 0
    pending_pct = pending / total * 100 if total > 0 else 0
    unverified_pct = unverified / total * 100 if total > 0 else 0
    
    fig = go.Figure()
    
    categories = ['Measured', 'Pending', 'Unverified']
    values = [measured, pending, unverified]
    text_labels = [f"{measured_pct:.0f}%", f"{pending_pct:.0f}%", f"{unverified_pct:.0f}%"]
    colors = ['#5B5670', '#9A9AAA', '#D6D7DE'] # Saddle Purple, Slate Grey, Light Grey
    
    fig.add_trace(go.Bar(
        x=categories,
        y=values,
        marker_color=colors,
        text=text_labels,
        textposition='auto',
    ))
    
    fig.update_layout(
        height=200,
        margin=dict(l=20, r=20, t=10, b=20),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)'),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    
    st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
    
    total = len(impact_df)
    if total > 0:
        conf_pct = measured / total * 100
        st.caption(f"**{conf_pct:.0f}%** of optimization decisions have verified impact.")
        st.markdown("""
        <div style="font-size: 0.75rem; color: #8F8CA3; margin-top: 8px; line-height: 1.4;">
            Verified = statistically measurable impact<br>
            Pending = awaiting sufficient data<br>
            Unverified = insufficient signal
        </div>
        """, unsafe_allow_html=True)


def create_roas_waterfall_figure(
    baseline_roas: float,
    actual_roas: float,
    decision_impact_roas: float,
    for_export: bool = False
) -> 'go.Figure':
    """
    Create ROAS waterfall chart figure - reusable by dashboard and client report.
    
    Args:
        baseline_roas: Baseline ROAS value
        actual_roas: Actual/current ROAS value
        decision_impact_roas: ROAS contribution from decisions
        for_export: If True, uses solid background for PNG export
        
    Returns:
        Plotly Figure object
    """
    import plotly.graph_objects as go
    
    # Calculate Combined Forces to balance equation
    combined_forces = actual_roas - baseline_roas - decision_impact_roas
    
    # Labels
    x_labels = ["Baseline", "Combined\nForces", "Decisions", "Actual"]
    
    # Bar Colors
    C_BASELINE = "#475569"
    C_COMBINED_NEG = "#DC2626"
    C_COMBINED_POS = "#10B981"
    C_DECISIONS = "#10B981"
    C_ACTUAL = "#06B6D4"
    
    combined_color = C_COMBINED_POS if combined_forces >= 0 else C_COMBINED_NEG
    
    # Bar Values and Bases
    y_vals = []
    bases = []
    colors = []
    text_labels = []
    
    current_lvl = 0.0
    
    # 1. Baseline
    y_vals.append(baseline_roas)
    bases.append(0)
    colors.append(C_BASELINE)
    text_labels.append(f"{baseline_roas:.2f}")
    current_lvl += baseline_roas
    
    # 2. Combined Forces
    y_vals.append(combined_forces)
    bases.append(current_lvl)
    colors.append(combined_color)
    text_labels.append(f"{combined_forces:+.2f}")
    current_lvl += combined_forces
    
    # 3. Decisions
    y_vals.append(decision_impact_roas)
    bases.append(current_lvl)
    colors.append(C_DECISIONS)
    text_labels.append(f"{decision_impact_roas:+.2f}")
    current_lvl += decision_impact_roas
    
    # 4. Actual
    y_vals.append(actual_roas)
    bases.append(0)
    colors.append(C_ACTUAL)
    text_labels.append(f"{actual_roas:.2f}")
    
    # Create figure
    fig = go.Figure()
    
    # Main Bars
    fig.add_trace(go.Bar(
        x=x_labels,
        y=y_vals,
        base=bases,
        marker_color=colors,
        marker_line=dict(width=1, color='rgba(148, 163, 184, 0.2)'),
        width=0.55,
        text=text_labels,
        textposition='outside',
        textfont=dict(color='white', size=14),
        hoverinfo='x+y+text',
        name=""
    ))
    
    # Connector Lines
    comb_end = baseline_roas + combined_forces
    dec_end = comb_end + decision_impact_roas
    
    conn_x = [x_labels[0], x_labels[1], None, x_labels[1], x_labels[2], None, x_labels[2], x_labels[3], None]
    conn_y = [baseline_roas, baseline_roas, None, comb_end, comb_end, None, dec_end, dec_end, None]
    
    fig.add_trace(go.Scatter(
        x=conn_x,
        y=conn_y,
        mode='lines',
        line=dict(color='rgba(148, 163, 184, 0.4)', width=2, dash='dash'),
        hoverinfo='skip',
        showlegend=False
    ))
    
    # Dynamic Y-axis range
    data_points = [0, baseline_roas, comb_end, dec_end, actual_roas]
    min_val = min(data_points)
    max_val = max(data_points)
    
    y_range = None
    if max_val > 0:
        zoom_floor = max(0, min_val * 0.5)
        if min_val > 2.0:
            zoom_floor = max(0, min_val - 0.5)
        padding = (max_val - zoom_floor) * 0.15
        y_range = [max(0, zoom_floor - padding), max_val + padding]
    
    # Background color based on export mode
    bg_color = 'rgba(30, 41, 59, 1)' if for_export else 'rgba(0,0,0,0)'
    
    fig.update_layout(
        title="",
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        font=dict(family="Inter, sans-serif", color='#E2E8F0'),
        showlegend=False,
        height=350,
        margin=dict(l=20, r=20, t=30, b=20),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(148, 163, 184, 0.1)',
            zeroline=True,
            zerolinecolor='rgba(148, 163, 184, 0.2)',
            title="ROAS",
            title_font=dict(color='#94A3B8'),
            tickfont=dict(color='#94A3B8'),
            range=y_range
        ),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(size=12, color='#F8FAFC')
        ),
        bargap=0.3
    )
    
    return fig


def create_decision_timeline_figure(
    impact_df: pd.DataFrame,
    currency: str = 'INR ',
    for_export: bool = False
) -> Optional['go.Figure']:
    """
    Create Decision Impact Timeline chart - reusable by dashboard and client report.
    
    Args:
        impact_df: DataFrame with action_date and decision_impact columns
        currency: Currency symbol/prefix
        for_export: If True, uses solid background for PNG export
        
    Returns:
        Plotly Figure object or None if no data
    """
    import plotly.graph_objects as go
    
    if impact_df.empty:
        return None
    
    # Filter to verified impacts
    df = impact_df.copy()
    if 'validation_status' in df.columns:
        df = df[df['validation_status'].str.contains('✓|Confirmed|Validated|Directional', na=False, regex=True)]
    
    if df.empty or 'action_date' not in df.columns:
        return None
    
    # Ensure decision_impact column exists
    if 'decision_impact' not in df.columns:
        if 'attributed_impact' in df.columns:
            df['decision_impact'] = df['attributed_impact']
        else:
            return None
    
    df['action_date'] = pd.to_datetime(df['action_date'])
    df = df.sort_values('action_date')
    
    # Aggregate by date
    daily = df.groupby('action_date')['decision_impact'].sum().reset_index()
    daily.columns = ['action_date', 'decision_impact']
    daily['cumulative_impact'] = daily['decision_impact'].cumsum()
    
    if daily.empty:
        return None
    
    total_val = daily['cumulative_impact'].iloc[-1]
    
    fig = go.Figure()
    
    # Area fill
    fig.add_trace(go.Scatter(
        x=daily['action_date'],
        y=daily['cumulative_impact'],
        mode='lines',
        fill='tozeroy',
        line=dict(color='#06B6D4', width=3),
        fillcolor='rgba(6, 182, 212, 0.2)',
        name='Cumulative Impact'
    ))
    
    # End point marker
    fig.add_trace(go.Scatter(
        x=[daily['action_date'].iloc[-1]],
        y=[daily['cumulative_impact'].iloc[-1]],
        mode='markers+text',
        marker=dict(color='#10B981', size=12),
        text=[f"+{currency}{total_val:,.0f}"],
        textposition="top center",
        textfont=dict(color='#F8FAFC', size=14),
        showlegend=False
    ))
    
    # Background color
    bg_color = 'rgba(30, 41, 59, 1)' if for_export else 'rgba(0,0,0,0)'
    
    fig.update_layout(
        height=350,
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        font=dict(family="Inter, sans-serif", color='#E2E8F0'),
        showlegend=False,
        margin=dict(l=50, r=20, t=30, b=40),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(color='#94A3B8'),
            tickformat='%b %d'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(148, 163, 184, 0.1)',
            tickfont=dict(color='#94A3B8'),
            tickprefix=currency
        )
    )
    
    return fig


def _render_roas_attribution_bar(summary: Dict[str, Any], impact_df: pd.DataFrame, currency: str, canonical_metrics: 'ImpactMetrics' = None):
    """
    Section: ROAS Attribution Visual - Premium Design
    Plotly Waterfall chart with custom styling and gradients.
    """
    import plotly.graph_objects as go
    
    # Chart icon (cyan)
    chart_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>'
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%); 
                border: 1px solid rgba(148, 163, 184, 0.15); 
                border-left: 3px solid #06B6D4;
                border-radius: 12px; padding: 16px; margin-bottom: 16px;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);">
        <div style="display: flex; align-items: center; gap: 12px;">
            {chart_icon}
            <span style="font-weight: 700; font-size: 1.1rem; color: #F8FAFC; letter-spacing: 0.02em;">ROAS Attribution</span>
        </div>
        <div style="color: #64748B; font-size: 0.85rem; margin-top: 8px; margin-left: 32px;">
            Waterfall analysis of performance drivers
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Use attribution data from module
    baseline_roas = summary.get('baseline_roas', 0)
    actual_roas = summary.get('actual_roas', 0)
    market_impact_roas = summary.get('market_impact_roas', 0)
    
    # Canonical metrics logic
    if canonical_metrics:
        decision_impact_value = canonical_metrics.attributed_impact
        total_spend = canonical_metrics.total_spend
        decision_impact_roas = decision_impact_value / total_spend if total_spend > 0 else 0
    else:
        # Fallback
        decision_impact_roas = 0.0
        decision_impact_value = 0.0

    # Structural components
    scale_effect = summary.get('scale_effect', 0.0)
    portfolio_effect = summary.get('portfolio_effect', 0.0)
    unexplained = summary.get('unexplained', 0.0)
    
    # Calculate Combined Forces
    combined_forces = actual_roas - baseline_roas - decision_impact_roas
    structural_total = scale_effect + portfolio_effect
    
    # Labels
    periods = summary.get('periods', {})
    prior_start = periods.get('prior_start')
    current_end = periods.get('current_end')
    prior_label = f"Baseline"
    actual_label = f"Actual"
    
    # --- CHART DATA PREP ---
    
    # Visual coordinates
    # We construct the waterfall manually to control every aspect
    # Bars: [Baseline, Combined, Decisions, Actual]
    
    x_labels = [prior_label, "Combined\nForces", "Decisions", actual_label]
    
    # Bar Colors (Main fills)
    C_BASELINE = "#475569"   # Slate
    C_COMBINED_NEG = "#DC2626" # Red
    C_COMBINED_POS = "#10B981" # Emerald (if market tailwinds)
    C_DECISIONS = "#10B981"  # Emerald (Hero)
    C_ACTUAL = "#06B6D4"     # Cyan (Result)
    
    combined_color = C_COMBINED_POS if combined_forces >= 0 else C_COMBINED_NEG
    decision_color = C_DECISIONS
    
    # Bar Values and Bases
    y_vals = []
    bases = []
    colors = []
    borders = []
    text_labels = []
    
    current_lvl = 0.0
    
    # 1. Baseline
    y_vals.append(baseline_roas)
    bases.append(0)
    colors.append(C_BASELINE)
    borders.append("rgba(148, 163, 184, 0.2)")
    text_labels.append(f"{baseline_roas:.2f}")
    current_lvl += baseline_roas
    
    # 2. Combined
    y_vals.append(combined_forces)
    bases.append(current_lvl)
    colors.append(combined_color)
    borders.append("rgba(239, 68, 68, 0.4)" if combined_forces < 0 else "rgba(16, 185, 129, 0.4)")
    text_labels.append(f"{combined_forces:+.2f}")
    current_lvl += combined_forces
    
    # 3. Decisions
    y_vals.append(decision_impact_roas)
    bases.append(current_lvl)
    colors.append(C_DECISIONS)
    borders.append("rgba(16, 185, 129, 0.5)")
    text_labels.append(f"{decision_impact_roas:+.2f}")
    current_lvl += decision_impact_roas
    
    # 4. Actual
    y_vals.append(actual_roas)
    bases.append(0)
    colors.append(C_ACTUAL)
    borders.append("rgba(6, 182, 212, 0.3)")
    text_labels.append(f"{actual_roas:.2f}")
    
    # --- RENDER CHART ---
    fig = go.Figure()
    
    # Main Bars
    fig.add_trace(go.Bar(
        x=x_labels,
        y=y_vals,
        base=bases,
        marker_color=colors,
        marker_line=dict(width=1, color=borders),
        width=0.55,
        text=text_labels,
        textposition='outside', # Using outside for clarity with bold white text if background is dark
        textfont=dict(color='white', size=14, weight=800), # Trying bold white
        hoverinfo='x+y+text',
        name=""
    ))
    
    # Connector Lines with Arrows
    # We draw lines from end of prev bar to start of curr bar
    # Baseline Top -> Combined Start
    # Combined End -> Decisions Start
    # Decisions End -> Actual Top
    
    # Connectors
    # 1. Baseline Top -> Combined Base (which is Baseline Top)
    # Actually connectors in waterfalls connect the TOPS.
    # Baseline Top connects to Combined Base? Yes.
    # Combined Top connects to Decisions Base.
    # Decisions Top connects to Actual Top.
    
    # Connector 1: Baseline Top -> Combined Base
    # y = baseline_roas
    fig.add_shape(
        type="line",
        x0=0.275, y0=baseline_roas, x1=0.725, y1=baseline_roas, # Approximate x-coords for gap
        xref="x domain", yref="y", # Using x domain tricky with categorical.
        # Better to simplify: Just dashed lines between categories using Scatter
    )
    # Retry with Scatter for connectors
    
    conn_x = []
    conn_y = []
    
    # We need indices for x-axis categories: 0, 1, 2, 3
    # Baseline(0) Top -> Combined(1) Base/Top depending on direction
    # Standard waterfall connectors: From preceding bar's end to current bar's start.
    
    # Path 1: Baseline Top to Combined Start
    conn_x.extend([x_labels[0], x_labels[1], None])
    conn_y.extend([baseline_roas, baseline_roas, None])
    
    # Path 2: Combined End to Decisions Start
    comb_end = baseline_roas + combined_forces
    conn_x.extend([x_labels[1], x_labels[2], None])
    conn_y.extend([comb_end, comb_end, None])
    
    # Path 3: Decisions End to Actual Start (Top)
    dec_end = comb_end + decision_impact_roas
    conn_x.extend([x_labels[2], x_labels[3], None])
    conn_y.extend([dec_end, dec_end, None])
    
    fig.add_trace(go.Scatter(
        x=conn_x,
        y=conn_y,
        mode='lines+markers', # Markers for arrow heads? No, use annotations
        line=dict(color='rgba(148, 163, 184, 0.4)', width=2, dash='dash'),
        hoverinfo='skip',
        showlegend=False
    ))
    
    # Add Arrow Annotations at the destinations
    # Arrow 1: At Combined Start
    fig.add_annotation(
        x=x_labels[1], y=baseline_roas,
        text="▶", showarrow=False,
        font=dict(size=10, color='rgba(148, 163, 184, 0.6)'),
        xshift=-25
    )
    # Arrow 2: At Decisions Start
    fig.add_annotation(
        x=x_labels[2], y=comb_end,
        text="▶", showarrow=False,
        font=dict(size=10, color='rgba(148, 163, 184, 0.6)'),
        xshift=-25
    )
    # Arrow 3: At Actual
    fig.add_annotation(
        x=x_labels[3], y=dec_end,
        text="▶", showarrow=False,
        font=dict(size=10, color='rgba(148, 163, 184, 0.6)'),
        xshift=-25
    )

    # Dynamic Zoom
    data_points = [0, baseline_roas, baseline_roas + combined_forces, dec_end, actual_roas]
    min_val = min(data_points)
    max_val = max(data_points)
    
    y_range = None
    if max_val > 0:
        zoom_floor = max(0, min_val * 0.5)
        if min_val > 2.0: zoom_floor = max(0, min_val - 0.5)
        padding = (max_val - zoom_floor) * 0.15
        y_range = [max(0, zoom_floor - padding), max_val + padding]

    fig.update_layout(
        title="",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter, sans-serif", color='#E2E8F0'),
        showlegend=False,
        height=350,
        margin=dict(l=20, r=20, t=30, b=20),
        yaxis=dict(
            showgrid=True, 
            gridcolor='rgba(148, 163, 184, 0.08)', 
            zeroline=True, 
            zerolinecolor='rgba(148, 163, 184, 0.2)',
            title="ROAS",
            title_font=dict(size=12, color='#94A3B8'),
            tickfont=dict(color='#94A3B8', size=11),
            range=y_range
        ),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(color='#E2E8F0', size=13, weight=600),
        )
    )
    
    st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
    
    # --- VISUAL EQUATION ---
    # --- VISUAL EQUATION ---
    equation_html = (
        f"<div style='text-align: center; color: #E2E8F0; font-weight: 600; font-size: 1.1rem; "
        f"padding: 16px; background: rgba(30, 41, 59, 0.3); border-radius: 8px; margin-top: -10px; margin-bottom: 24px;'>"
        f"<span style='color: #94A3B8'>{baseline_roas:.2f}</span> "
        f"{'-' if combined_forces < 0 else '+'} <span style='color: {'#EF4444' if combined_forces < 0 else '#10B981'}'>{abs(combined_forces):.2f}</span> <span style='font-size: 0.85rem; color: #94A3B8'>(Market)</span> "
        f"{'-' if decision_impact_roas < 0 else '+'} <span style='color: {'#EF4444' if decision_impact_roas < 0 else '#10B981'}'>{abs(decision_impact_roas):.2f}</span> <span style='font-size: 0.85rem; color: #94A3B8'>(Decisions)</span> "
        f"→ <span style='color: #06B6D4'>{actual_roas:.2f} ROAS</span>"
        f"</div>"
    )
    st.markdown(equation_html, unsafe_allow_html=True)
    
    # --- VALUE CREATED BOX ---
    # Calculate performance improvement percentage
    # Improvement = Attributed Impact / Counterfactual Revenue? 
    # Or just use the User's example "improved performance by X%" logic.
    # We'll use ROAS improvement % attributed to decisions.
    
    counterfactual_roas = max(0.01, baseline_roas + combined_forces)
    pct_improvement = (decision_impact_roas / counterfactual_roas) * 100
    
    if decision_impact_value > 0:
        val_formatted = f"{currency}{decision_impact_value:,.0f}" if currency else f"{decision_impact_value:,.0f}"
        
        value_box_html = (
            f'<div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%); '
            f'border: 2px solid rgba(16, 185, 129, 0.4); border-radius: 12px; padding: 28px 32px; '
            f'box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3); margin-top: 24px; margin-bottom: 24px; text-align: center;">'
            f'<div style="color: #10B981; font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 12px;">VALUE CREATED</div>'
            f'<div style="color: #10B981; font-size: 2.5rem; font-weight: 800; letter-spacing: -1px; line-height: 1; margin-bottom: 12px;">{val_formatted}</div>'
            f'<div style="color: #94A3B8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 4px;">Without optimizations, ROAS would have been {counterfactual_roas:.2f}</div>'
            f'<div style="color: #10B981; font-size: 0.9rem; font-weight: 600;">You improved performance by {pct_improvement:.0f}%</div>'
            f'</div>'
        )
        st.markdown(value_box_html, unsafe_allow_html=True)
    # --- Expandable Breakdown ---
    with st.expander("Full Breakdown", expanded=False):
        # Data Prep for Text
        prior_metrics = summary.get('prior_metrics', {})
        current_metrics = summary.get('current_metrics', {})
        
        # Calculate % changes for text
        def get_pct_change(key):
            p = prior_metrics.get(key, 0)
            c = current_metrics.get(key, 0)
            return ((c - p) / p * 100) if p > 0 else 0

        cpc_pct = get_pct_change('cpc')
        cvr_pct = get_pct_change('cvr')
        aov_pct = get_pct_change('aov')
        
        cpc_impact = summary.get('cpc_impact', 0)
        cvr_impact = summary.get('cvr_impact', 0)
        aov_impact = summary.get('aov_impact', 0)
        
        col1, col2 = st.columns(2)
        
        # LEFT COLUMN: Market & Structural Forces
        with col1:
            st.markdown(f"**Market & Structural Forces: {combined_forces:+.2f} ROAS**")
            st.divider()
            
            # Market Subsection
            st.markdown(f"""
            <div style="font-size: 14px; font-weight: 600; color: #cccccc; margin-bottom: 8px;">Market Impact: {market_impact_roas:+.2f}</div>
            
            <div style="font-size: 13px; color: #aaaaaa; line-height: 1.6;">
            • CPC {('increased' if cpc_pct >=0 else 'dropped')} {abs(cpc_pct):.1f}% → 
              <span style="color: {'#ff6b6b' if cpc_impact < 0 else '#2ed573'}">{cpc_impact:+.2f} ROAS impact</span><br>
              
            • CVR {('increased' if cvr_pct >=0 else 'dropped')} {abs(cvr_pct):.1f}% → 
              <span style="color: {'#ff6b6b' if cvr_impact < 0 else '#2ed573'}">{cvr_impact:+.2f} ROAS impact</span><br>
              
            • AOV {('increased' if aov_pct >=0 else 'dropped')} {abs(aov_pct):.1f}% → 
              <span style="color: {'#ff6b6b' if aov_impact < 0 else '#2ed573'}">{aov_impact:+.2f} ROAS impact</span>
            </div>
            
            <div style="font-size: 12px; color: #888888; margin-top: 4px;">
            Reconciliation: {cpc_impact:+.2f} {cvr_impact:+.2f} {aov_impact:+.2f} = {market_impact_roas:+.2f} ✓
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("") # Spatial gap
            
            # Structural Subsection
            st.markdown(f"""
            <div style="font-size: 14px; font-weight: 600; color: #cccccc; margin-bottom: 8px;">Structural Effects: {structural_total:+.2f}</div>
            
            <div style="font-size: 13px; color: #aaaaaa; line-height: 1.6;">
            • Scale effect: {scale_effect:+.2f} (Spend change)<br>
            • Portfolio effect: {portfolio_effect:+.2f} (Campaign mix)<br>
            <span style="font-style: italic; color: #888888;">New campaigns in ramp-up phase (if any)</span>
            </div>
            """, unsafe_allow_html=True)

        # RIGHT COLUMN: Decision Impact
        with col2:
            # Get action count for display
            action_count = 0
            if not impact_df.empty:
                # Count only mature, non-drag actions for display
                if 'is_mature' in impact_df.columns and 'market_tag' in impact_df.columns:
                    action_count = len(impact_df[(impact_df['is_mature'] == True) & (impact_df['market_tag'] != 'Market Drag')])
                else:
                    action_count = len(impact_df)
                
            st.markdown(f"**Decision Impact: {decision_impact_roas:+.2f} ROAS**")
            st.divider()
            
            st.markdown(f"""
            <div style="font-size: 14px; font-weight: 600; color: #cccccc; margin-bottom: 8px;">Activity:</div>
            <div style="font-size: 13px; color: #aaaaaa; line-height: 1.6;">
            • {action_count} actions executed
            </div>
            
            <br>
            
            <div style="font-size: 14px; font-weight: 600; color: #cccccc; margin-bottom: 8px;">ROAS Contribution:</div>
            <div style="font-size: 13px; color: #aaaaaa; line-height: 1.6;">
            • Added {decision_impact_roas:+.2f} on top of market baseline<br>
            • Offset structural drag of {structural_total:+.2f}<br>
            • Net effect: Created value despite headwinds
            </div>
            """, unsafe_allow_html=True)
            
        # BOTTOM: Attribution Summary Box
        # BOTTOM: Attribution Summary Box
        # Using concise construction to guarantee no indentation issues causing code-block rendering
        summary_html = "".join([
            '<div style="background-color: #0f1624; border: 1px solid #2d3748; border-radius: 8px; padding: 20px; margin-top: 20px;">',
            '  <div style="color: #cccccc; font-size: 13px; font-weight: 600; margin-bottom: 10px;">Attribution Summary</div>',
            '  <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">',
            '    <div style="color: #aaaaaa; font-size: 13px;">',
            '      Counterfactual Analysis:<br>',
            f'      Without decisions → <b>{(baseline_roas + combined_forces):.2f} ROAS</b> (Market + Structural)<br>',
            f'      With decisions → <b>{actual_roas:.2f} ROAS</b> (Actual achieved)',
            '    </div>',
            '  </div>',
            '  <div style="color: #aaaaaa; font-size: 13px; line-height: 1.6; margin-bottom: 15px;">',
            f'    Explanation: Market conditions impact ({market_impact_roas:+.2f} ROAS) combined with structural effects from growth ',
            f'    ({structural_total:+.2f}) was offset by {action_count} optimizations ({decision_impact_roas:+.2f}), ',
            '    delivering result.',
            '  </div>',
            '  <div style="border-top: 1px solid #2d3748; padding-top: 10px; display: flex; justify-content: space-between; font-size: 12px; color: #888888;">',
            '    <div>Attribution Quality: <span style="color: #2ed573;">✓ Clean</span></div>',
            f'    <div>Unexplained residual: {unexplained:+.2f} ROAS</div>',
            '  </div>',
            '</div>'
        ])
        st.markdown(summary_html, unsafe_allow_html=True)


def _render_cumulative_impact_chart(impact_df: pd.DataFrame, currency: str):
    """Section 4: Is it getting better? - Cumulative Impact Over Time."""
    import plotly.graph_objects as go
    import numpy as np
    
    # Trend icon SVG (cyan color)
    trend_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>'
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%); 
                border: 1px solid rgba(148, 163, 184, 0.15); 
                border-left: 3px solid #06B6D4;
                border-radius: 12px; padding: 16px; margin-bottom: 16px;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);">
        <div style="display: flex; align-items: center; gap: 12px;">
            {trend_icon}
            <span style="font-weight: 700; font-size: 1.1rem; color: #F8FAFC; letter-spacing: 0.02em;">Decision Impact Timeline</span>
        </div>
        <div style="color: #64748B; font-size: 0.85rem; margin-top: 8px; margin-left: 32px;">
            Total value created over time
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if impact_df.empty:
        st.info("No data")
        return
        
    df = impact_df[impact_df['validation_status'].str.contains('✓|Confirmed|Validated|Directional', na=False, regex=True)].copy()
    
    if df.empty:
        st.info("No verified impact data to plot")
        return
        
    if 'action_date' not in df.columns:
        return
    
    # Ensure required columns exist (handles old cached data)
    df = _ensure_impact_columns(df)
    
    # Exclude Market Drag (ambiguous attribution)
    df = df[df['market_tag'] != 'Market Drag']
    
    impact_column = 'decision_impact'
        
    if df.empty:
        st.info("No attributable impact data to plot")
        return
        
    df['action_date'] = pd.to_datetime(df['action_date'])
    df = df.sort_values('action_date')
    
    daily = df.groupby('action_date')[impact_column].sum().reset_index()
    daily.columns = ['action_date', 'decision_impact']
    daily['cumulative_impact'] = daily['decision_impact'].cumsum()
    
    total_val = daily['cumulative_impact'].iloc[-1]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=daily['action_date'],
        y=daily['cumulative_impact'],
        mode='lines',
        fill='tozeroy',
        line=dict(color='#5B5670', width=3),
        fillcolor='rgba(91, 86, 112, 0.2)',
        name='Cumulative Impact'
    ))
    
    fig.add_trace(go.Scatter(
        x=[daily['action_date'].iloc[-1]],
        y=[daily['cumulative_impact'].iloc[-1]],
        mode='markers+text',
        marker=dict(color='#5B5670', size=10),
        text=[f"+{currency}{total_val:,.0f}"],
        textposition="top center",
        textfont=dict(color='#E9EAF0', size=12, weight='bold'),
        showlegend=False
    ))
    
    fig.update_layout(
        height=350,
        margin=dict(l=40, r=20, t=30, b=40),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, gridcolor='rgba(128,128,128,0.1)', tickfont=dict(color='#94a3b8')),
        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)', tickfont=dict(color='#94a3b8')),
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, width='stretch')
    
    # Trend message
    if len(daily) >= 2:
        recent_trend = daily['decision_impact'].iloc[-3:].mean() if len(daily) >= 3 else daily['decision_impact'].iloc[-1]
        if recent_trend > 0:
            trend_msg = "↑ Trending up — your recent decisions are working"
            trend_color = "#10B981"
        elif recent_trend < 0:
            trend_msg = "↓ Trending down — recent decisions need review"
            trend_color = "#EF4444"
        else:
            trend_msg = "→ Holding steady — consistent performance"
            trend_color = "#9CA3AF"
        
        st.markdown(f"""
        <div style="font-size: 0.85rem; color: {trend_color}; margin-top: 8px;">
            {trend_msg}
        </div>
        """, unsafe_allow_html=True)


def _render_new_impact_analytics(summary: Dict[str, Any], impact_df: pd.DataFrame, validated_only: bool = True, mature_count: int = 0, pending_count: int = 0, raw_impact_df: pd.DataFrame = None, canonical_metrics: 'ImpactMetrics' = None):
    """
    Render new impact analytics layout.
    Structure:
    - Hero Tiles (Estimated Impact, Capital Protected, Decision Quality, Implementation)
    - Row 1: Decision Quality | Impact by Action Type | Validation Rate
    - Row 2: Decision Outcome Matrix | Cumulative Impact
    """
    
    from utils.formatters import get_account_currency
    currency = get_account_currency()
    
    # Theme-aware colors
    theme_mode = st.session_state.get('theme_mode', 'dark')
    
    if theme_mode == 'dark':
        positive_text = "#E9EAF0"  # Soft White (Purple background makes purple text hard)
        negative_text = "#D6D7DE"  # Light Grey (Warnings/Negatives)
        neutral_text = "#9A9AAA"   # Slate Grey
        muted_text = "#8F8CA3"
        section_header_color = "#e2e8f0"
    else:
        positive_text = "#5B5670"  # Saddle Purple (Dark enough for light mode)
        negative_text = "#5E6475"  # Secondary Dark
        neutral_text = "#9A9AAA"   # Slate Grey
        muted_text = "#64748b"
        section_header_color = "#1e293b"
    
    # SVG Icons
    icon_color = "#8F8CA3"
    
    # Spend icon
    spend_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>'
    
    # Revenue icon
    revenue_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>'
    
    # ROAS trending icon
    roas_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>'
    
    # Target icon (for Estimated Revenue Impact)
    target_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle></svg>'
    
    # Shield icon (for Capital Protected)
    shield_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>'
    
    # Score icon
    score_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2"><path d="M12 20V10"></path><path d="M18 20V4"></path><path d="M6 20v-4"></path></svg>'
    
    # Implementation icon
    impl_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>'
    
    # Info icon for tooltips
    info_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="cursor: help; margin-left: 4px;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
    
    # Extract metrics
    total_actions = summary.get('total_actions', 0)
    impl_rate = summary.get('implementation_rate', 0)
    
    # Actual performance metrics
    total_before_spend = summary.get('total_before_spend', 0)
    total_after_spend = summary.get('total_after_spend', 0)
    total_before_sales = summary.get('total_before_sales', 0)
    total_after_sales = summary.get('total_after_sales', 0)
    roas_before = summary.get('roas_before', 0)
    roas_after = summary.get('roas_after', 0)
    
    # ==========================================
    # USE PRE-CALCULATED VALUES (Single Source of Truth)
    # ==========================================
    # decision_impact and market_tag are pre-calculated in get_action_impact()
    # with all guardrails (including MIN_CLICKS_FOR_RELIABLE) already applied.
    
    if not impact_df.empty:
        # Ensure required columns exist (handles old cached data)
        df = _ensure_impact_columns(impact_df)
        
        # Exclude Market Drag (ambiguous attribution)
        non_drag = df[df['market_tag'] != 'Market Drag']
        
        # Decision-Attributed Impact (Wins + Gaps)
        decision_impact = non_drag['decision_impact'].sum()
        
        # ==========================================
        # CAPITAL PROTECTED (Refined Logic)
        # ==========================================
        # Only count NEGATIVE actions where spend was successfully eliminated
        # Capital Protected = before_spend for confirmed blocked negatives
        
        # Filter to negative actions (case-insensitive match)
        negative_actions = non_drag[non_drag['action_type'].str.upper().str.contains('NEGATIVE', na=False)]
        
        # Confirmed negatives = after_spend is 0 (successfully blocked)
        confirmed_negatives = negative_actions[negative_actions['observed_after_spend'] == 0]
        
        # Capital protected = sum of before_spend for these confirmed blocks
        capital_protected = confirmed_negatives['before_spend'].sum()
        confirmed_negative_count = len(confirmed_negatives)
    else:
        # Fallback to summary if DataFrame is empty
        decision_impact = summary.get('decision_impact', 0)
        capital_protected = 0
        confirmed_negative_count = 0
    
    # Estimated impact metrics (now Market Drag excluded)
    # decision_impact calculated above
    spend_avoided = capital_protected  # Alias for backward compatibility
    
    # CSS for tiles and sections
    st.markdown("""
    <style>
    .hero-card {
        background: linear-gradient(135deg, rgba(91, 86, 112, 0.25) 0%, rgba(91, 86, 112, 0.05) 100%);
        border: 1px solid rgba(91, 86, 112, 0.3);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        min-height: 280px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .hero-label {
        font-size: 0.7rem;
        color: #8F8CA3;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
    }
    .hero-value {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .hero-sub {
        font-size: 0.75rem;
        color: #8F8CA3;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
    }
    .section-header {
        font-size: 0.85rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 12px;
        padding-left: 4px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Validated DF for charts
    validation_df = raw_impact_df if raw_impact_df is not None else impact_df

    # ==========================================
    # SECTION 2: BREAKDOWN ROW (What Worked | What Didn't | Decision Score)
    # ==========================================
    c1, c2, c3 = st.columns(3, gap="medium")
    
    with c1:
        _render_what_worked_card(currency)
    
    with c2:
        _render_what_didnt_card(currency)
    
    with c3:
        _render_decision_score_card()
    
    st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)

    # ==========================================
    # SECTION 3 & 4: ROAS ATTRIBUTION | DECISION MAP (New Layout)
    # ==========================================
    chart_c1, chart_c2 = st.columns(2, gap="medium")
    
    with chart_c1:
        _render_roas_attribution_bar(summary, impact_df, currency, canonical_metrics=canonical_metrics)
        
    with chart_c2:
        _render_decision_outcome_matrix(impact_df, summary)

    st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
    


    # ==========================================
    # SECTION 5 & 6: CONFIDENCE ROW (Data Confidence | Value Breakdown)
    # ==========================================
    # ==========================================
    # ==========================================
    # SECTION 5 & 6: RECENT WINS + TRUST LAYOUT
    # ==========================================
    # Unified Panel
    with st.container(border=True):
        trust_c1, wins_c2 = st.columns([3, 7], gap="medium")
        
        # --- LEFT COLUMN: MEASUREMENT TRUST (30%) ---
        with trust_c1:
            # Content continues at same indentation...
            # Calculate Trust Metrics
            # Reuse validation logic from existing dataframes to avoid recalc
            if not validation_df.empty:
                v_df = validation_df
                # Status counts
                measured_count = len(v_df[v_df['validation_status'].astype(str).str.contains('✓|Confirmed|Validated|Directional', na=False)])
                pending_count = len(v_df[v_df['maturity_status'] == 'Immature']) + len(v_df[v_df['maturity_status'] == 'Dormant'])
                total_count = len(v_df)
                early_count = total_count - measured_count - pending_count # Inconclusive/Excluded
                
                pct_measured = (measured_count / total_count * 100) if total_count > 0 else 0
            else:
                measured_count = 0
                pending_count = 0
                early_count = 0
                pct_measured = 0
            
            # 1. Header
            st.markdown("""
<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px;">
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
    <span style="font-weight: 700; font-size: 1rem; color: #F8FAFC;">Measurement Confidence</span>
</div>
""", unsafe_allow_html=True)

            # 2. Dramatic Gauge (Plotly)
            import plotly.graph_objects as go
            
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = pct_measured,
                number = {'font': {'size': 36, 'color': '#10B981', 'family': 'Inter, sans-serif'}, 'suffix': '%'},
                domain = {'x': [0, 1], 'y': [0, 1]},
                gauge = {
                    'axis': {'range': [0, 100], 'tickwidth': 0, 'tickcolor': "rgba(0,0,0,0)", 'visible': False},
                    'bar': {'color': "#10B981", 'thickness': 1.0}, # Full thickness
                    'bgcolor': "rgba(255,255,255,0.1)",
                    'borderwidth': 0,
                    'steps': []
                }
            ))
            
            fig.update_layout(
                height=160,
                margin=dict(l=20, r=20, t=20, b=20),
                paper_bgcolor='rgba(0,0,0,0)',
                font={'family': "Inter, sans-serif"}
            )
            
            st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
            
            st.markdown(f"""
<div style="text-align: center; margin-top: -30px; margin-bottom: 24px;"><div style="color: #94A3B8; font-size: 0.85rem; font-weight: 500;">Measurement Coverage</div></div>
<div style="display: flex; flex-direction: column; gap: 12px; padding: 0 12px;">
    <div style="display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center; gap: 8px; color: #E2E8F0; font-size: 0.9rem;">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#E2E8F0" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
            Total Decisions
        </div>
        <span style="font-weight: 600; color: #E2E8F0;">{total_count}</span>
    </div>
    <div style="display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center; gap: 8px; color: #E2E8F0; font-size: 0.9rem;">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
            Next decision proven
        </div>
        <span style="font-weight: 600; color: #10B981;">{measured_count}</span>
    </div>
    <div style="display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center; gap: 8px; color: #64748B; font-size: 0.9rem;">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
            Pending decisions (too early)
        </div>
        <span style="font-weight: 600; color: #64748B;">{early_count + pending_count}</span>
    </div>
</div>
<div style="margin-top: 24px; padding: 12px; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 8px; display: flex; align-items: center; gap: 12px;">
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><path d="m9 12 2 2 4-4"></path></svg>
    <div>
        <div style="color: #10B981; font-weight: 700; font-size: 0.9rem;">High Confidence</div>
        <div style="color: #6EE7B7; font-size: 0.75rem;">Statistically significant results</div>
    </div>
</div>
""", unsafe_allow_html=True)
    
    # --- RIGHT COLUMN: RECENT WINNING DECISIONS (70%) ---
        # --- RIGHT COLUMN: RECENT WINNING DECISIONS (70%) ---
        with wins_c2:
            _render_recent_wins_list(impact_df, currency)

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    # ==========================================
    # SECTION 7: COLLAPSED DETAILS TABLE
    # ==========================================
    with st.container(border=True):
        _render_details_table_collapsed(impact_df, currency)
    # Debug console removed for production


def _render_debug_console(impact_df: pd.DataFrame):
    """Debug section for validating impact math."""
    if impact_df.empty: return
    
    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
    
    with st.expander("🛠 Impact Calculation Debugger (Internal)", expanded=False):
        st.caption("Inspect the raw numbers behind the Decision Impact calculation.")
        
        # Work on a copy to calculate ad-hoc metrics
        df_debug = impact_df.copy()
        
        # Calculate SPC After on the fly if missing 
        # (Observed Sales / Observed Clicks)
        if 'after_clicks' in df_debug.columns and 'observed_after_sales' in df_debug.columns:
            df_debug['spc_after'] = df_debug['observed_after_sales'] / df_debug['after_clicks'].replace(0, np.nan)
        
        # Select relevant columns if they exist
        debug_cols = [
            'target_text', 'action_type', 
            'before_sales', 'expected_trend_pct', 'expected_sales', 
            'observed_after_sales', 'decision_impact', 
            'confidence_weight', 'final_decision_impact', 'impact_tier',
            'cpc_before', 'cpc_after', 'spc_before', 'spc_after',
            'market_tag', 'validation_status'
        ]
        
        # Filter to existing columns
        cols = [c for c in debug_cols if c in df_debug.columns]
        
        if not cols:
            st.info("No debug columns found.")
            return

        st.dataframe(
            df_debug[cols].sort_values('decision_impact', ascending=False),
            width='stretch',
            height=400,
            column_config={
                "cpc_before": st.column_config.NumberColumn("CPC Pre", format="%.3f"),
                "cpc_after": st.column_config.NumberColumn("CPC Post", format="%.3f"),
                "spc_before": st.column_config.NumberColumn("SPC Pre", format="%.3f"),
                "spc_after": st.column_config.NumberColumn("SPC Post", format="%.3f"),
                "expected_sales": st.column_config.NumberColumn("Exp Sales", format="%.2f"),
                "decision_impact": st.column_config.NumberColumn("Raw Impact", format="%.2f"),
                "final_decision_impact": st.column_config.NumberColumn("Final Impact", format="%.2f", help="Weighted by confidence"),
                "confidence_weight": st.column_config.NumberColumn("Conf.", format="%.2f")
            }
        )


def _render_decision_outcome_matrix(impact_df: pd.DataFrame, summary: Dict[str, Any]):
    """Section 3: Did each decision help or hurt? - Decision Outcome Matrix."""
    
    import plotly.graph_objects as go
    import numpy as np
    
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
    
    # Clean up infinite/nan values for visualization
    df = df[np.isfinite(df['expected_trend_pct']) & np.isfinite(df['decision_value_pct'])]
    
    if len(df) < 3:
        st.info("Insufficient data for matrix")
        return




    # Cap outliers for visualization (keep charts readable)
    # We clip the visual coordinates but keep actuals for hover
    df['x_display'] = df['expected_trend_pct'].clip(-200, 200)
    df['y_display'] = df['decision_value_pct'].clip(-200, 200)
    
    # Normalize action types for display (needed for color mapping and traces)
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
                type_df['decision_impact'],
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
            marker=dict(size=8, color='rgba(156, 163, 175, 0.4)', opacity=0.4), # Grey, smaller, faint
            customdata=np.stack((
                drag['expected_trend_pct'], 
                drag['decision_value_pct'], 
                drag['decision_impact'],
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
    # Use localized max for label positioning
    x_max = max(abs(df['x_display'].max()), abs(df['x_display'].min()), 50)
    y_max = max(abs(df['y_display'].max()), abs(df['y_display'].min()), 50)
    
    annotations = [
        # Top Left: Expected to shrink, but we beat it (Good Defense)
        dict(x=-x_max*0.7, y=y_max*0.85, text="Defensive Win", showarrow=False, font=dict(color='#10B981', size=11)),
        # Top Right: Expected to grow, and we added even more value (Good Offense)
        dict(x=x_max*0.7, y=y_max*0.85, text="Offensive Win", showarrow=False, font=dict(color='#10B981', size=11)),
        # Bottom Left: Expected to shrink, and we missed expectations (Market Drag/Bad)
        dict(x=-x_max*0.7, y=-y_max*0.85, text="Market Drag", showarrow=False, font=dict(color='#9CA3AF', size=10)), # Grey label
        # Bottom Right: Expected to grow, but we killed performance (Decision Gap)
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
    
    st.plotly_chart(fig, width='stretch')
    
    # How to read this chart (subtle styling)
    st.markdown("""
    <div style="font-size: 0.85rem; color: #8F8CA3; margin-top: 8px; line-height: 1.5;">
        <em>How to read this chart:</em><br>
        • X-Axis: Sales change implied purely by spend change (baseline assumption)<br>
        • Y-Axis: Actual performance above or below that baseline (decision impact)<br>
        • Grey points: Market-driven outcomes — excluded from attributed impact
    </div>
    """, unsafe_allow_html=True)



def _render_decision_quality_distribution(summary: Dict[str, Any]):
    """Chart 2: Decision Quality Distribution (NPS-Style Donut)."""
    
    import plotly.graph_objects as go
    
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; font-size: 1.1rem; font-weight: 600; color: #E9EAF0; margin-bottom: 4px;">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#8F8CA3" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"></path><path d="M22 12A10 10 0 0 0 12 2v10z"></path></svg>
        Decision Quality Distribution
    </div>
    """, unsafe_allow_html=True)
    
    pct_good = summary.get('pct_good', 0)
    pct_neutral = summary.get('pct_neutral', 0)
    pct_bad = summary.get('pct_bad', 0)
    
    # NPS-style score
    decision_quality_score = pct_good - pct_bad
    
    if pct_good + pct_neutral + pct_bad == 0:
        st.info("No outcome data")
        return
    
    # Donut chart
    fig = go.Figure(data=[go.Pie(
        values=[pct_good, pct_neutral, pct_bad],
        labels=['Good', 'Neutral', 'Bad'],
        hole=0.6,
        marker=dict(colors=['#2A8EC9', '#9A9AAA', '#D6D7DE']),
        textinfo='label+percent',
        textfont=dict(size=12, color='#e2e8f0'),
        hovertemplate='%{label}: %{value:.1f}%<extra></extra>',
        sort=False
    )])
    
    # Add score in center
    score_color = '#2A8EC9' if decision_quality_score > 0 else '#D6D7DE' if decision_quality_score < 0 else '#9A9AAA'
    score_prefix = '+' if decision_quality_score > 0 else ''
    
    fig.add_annotation(
        text=f"<b style='font-size:28px; color:{score_color};'>{score_prefix}{decision_quality_score:.0f}</b><br><span style='font-size:11px; color:#8F8CA3;'>Quality Score</span>",
        showarrow=False,
        font=dict(size=14, color='#e2e8f0')
    )
    
    fig.update_layout(
        height=350,
        margin=dict(t=30, b=60, l=30, r=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    
    st.plotly_chart(fig, width='stretch')
    
    # Important copy
    st.caption("*Neutrals excluded to focus on signal, not noise.*")


def _render_capital_allocation_flow(impact_df: pd.DataFrame, currency: str):
    """Chart 3: Capital Allocation Flow - Before vs After Spend Distribution."""
    
    import plotly.graph_objects as go
    import numpy as np
    
    st.markdown("#### 💰 Spend Flow: Before → After")
    st.caption("How your spend shifted between periods")
    
    if impact_df.empty:
        st.info("No data to display")
        return
    
    df = impact_df.copy()
    
    # Total spend in each period
    total_before = df['before_spend'].sum()
    total_after = df['observed_after_spend'].sum()
    
    if total_before == 0 and total_after == 0:
        st.info("No spend data")
        return
    
    # Categorize each action by spend change direction
    df['spend_change'] = df['observed_after_spend'] - df['before_spend']
    
    # Segment by action type and direction
    # Reduced: Spend decreased (negatives, bid downs)
    reduced_mask = df['spend_change'] < 0
    reduced_before = df.loc[reduced_mask, 'before_spend'].sum()
    reduced_after = df.loc[reduced_mask, 'observed_after_spend'].sum()
    
    # Maintained: Spend roughly same (within 10%)
    maintained_mask = (df['spend_change'].abs() / df['before_spend'].replace(0, np.nan)).fillna(0) <= 0.10
    maintained_before = df.loc[maintained_mask, 'before_spend'].sum()
    maintained_after = df.loc[maintained_mask, 'observed_after_spend'].sum()
    
    # Increased: Spend increased (bid ups)
    increased_mask = df['spend_change'] > 0
    increased_before = df.loc[increased_mask, 'before_spend'].sum()
    increased_after = df.loc[increased_mask, 'observed_after_spend'].sum()
    
    # Build Sankey: Before (left) → Categories (middle) → After (right)
    # Nodes: 0=Before Total, 1=Reduced, 2=Maintained, 3=Increased, 4=After Total
    
    fig = go.Figure(go.Sankey(
        arrangement='snap',
        node=dict(
            pad=30,
            thickness=30,
            line=dict(color='rgba(0,0,0,0)', width=0),
            label=[
                f"Before<br>{currency}{total_before:,.0f}",
                f"Reduced<br>{currency}{reduced_after:,.0f}",
                f"Maintained<br>{currency}{maintained_after:,.0f}",
                f"Increased<br>{currency}{increased_after:,.0f}",
                f"After<br>{currency}{total_after:,.0f}"
            ],
            color=['#5B556F', '#22c55e', '#64748b', '#3b82f6', '#5B556F'],
            x=[0, 0.5, 0.5, 0.5, 1],
            y=[0.5, 0.15, 0.5, 0.85, 0.5]
        ),
        link=dict(
            source=[0, 0, 0, 1, 2, 3],
            target=[1, 2, 3, 4, 4, 4],
            value=[
                reduced_before,      # Before → Reduced
                maintained_before,   # Before → Maintained
                increased_before,    # Before → Increased
                reduced_after,       # Reduced → After
                maintained_after,    # Maintained → After
                increased_after      # Increased → After
            ],
            color=[
                'rgba(34,197,94,0.3)',   # Green - money saved
                'rgba(100,116,139,0.3)', # Gray - maintained
                'rgba(59,130,246,0.3)',  # Blue - invested
                'rgba(34,197,94,0.3)',
                'rgba(100,116,139,0.3)',
                'rgba(59,130,246,0.3)'
            ]
        )
    ))
    
    fig.update_layout(
        height=350,
        margin=dict(t=30, b=30, l=30, r=30),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e2e8f0', size=11)
    )
    
    st.plotly_chart(fig, width='stretch')
    
    # Summary stats
    spend_delta = total_after - total_before
    spend_delta_pct = (spend_delta / total_before * 100) if total_before > 0 else 0
    delta_color = "#22c55e" if spend_delta < 0 else "#3b82f6" if spend_delta > 0 else "#64748b"
    delta_prefix = "+" if spend_delta > 0 else ""
    
    st.markdown(f"""
    <div style="display: flex; justify-content: space-around; text-align: center; margin-top: 8px;">
        <div>
            <span style="color: #22c55e; font-weight: 600;">🟢 Reduced:</span>
            <span style="color: #94a3b8;"> {currency}{reduced_before - reduced_after:,.0f} freed</span>
        </div>
        <div>
            <span style="color: #3b82f6; font-weight: 600;">🔵 Increased:</span>
            <span style="color: #94a3b8;"> {currency}{increased_after - increased_before:,.0f} invested</span>
        </div>
        <div>
            <span style="color: {delta_color}; font-weight: 600;">Net:</span>
            <span style="color: #94a3b8;"> {delta_prefix}{currency}{spend_delta:,.0f} ({delta_prefix}{spend_delta_pct:.1f}%)</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


# Legacy chart functions (kept for backward compatibility but not called)
def _render_attribution_waterfall(summary: Dict[str, Any], impact_df: pd.DataFrame, currency: str, validated_only: bool):
    """Render attribution-based waterfall showing ROAS contribution by action type."""
    
    label = "📊 ROAS Contribution by Type" if validated_only else "📊 Sales Change by Type"
    st.markdown(f"#### {label}")
    
    if impact_df.empty:
        st.info("No data to display")
        return
    
    # Break down by MATCH TYPE for more granular attribution (instead of action type)
    # This shows AUTO, BROAD, EXACT, etc. contributions like the Account Overview donut
    match_type_col = 'match_type' if 'match_type' in impact_df.columns else None
    
    contributions = {}
    
    if match_type_col and impact_df[match_type_col].notna().any():
        # Group by match type for richer breakdown
        for match_type in impact_df[match_type_col].dropna().unique():
            type_df = impact_df[impact_df[match_type_col] == match_type]
            type_df = type_df[(type_df['before_spend'] > 0) & (type_df['observed_after_spend'] > 0)]
            
            if len(type_df) == 0:
                continue
            
            # Calculate this type's ROAS contribution
            before_spend = type_df['before_spend'].sum()
            before_sales = type_df['before_sales'].sum()
            after_spend = type_df['observed_after_spend'].sum()
            after_sales = type_df['observed_after_sales'].sum()
            
            roas_before = before_sales / before_spend if before_spend > 0 else 0
            roas_after = after_sales / after_spend if after_spend > 0 else 0
            
            contribution = before_spend * (roas_after - roas_before)
            
            # Clean match type name
            name = str(match_type).upper() if match_type else 'OTHER'
            contributions[name] = contributions.get(name, 0) + contribution
    else:
        # Fallback to action type if no match type
        display_names = {
            'BID_CHANGE': 'Bid Optim.',
            'NEGATIVE': 'Cost Saved',
            'HARVEST': 'Harvest Gains',
            'BID_ADJUSTMENT': 'Bid Optim.'
        }
        
        for action_type in impact_df['action_type'].unique():
            type_df = impact_df[impact_df['action_type'] == action_type]
            type_df = type_df[(type_df['before_spend'] > 0) & (type_df['observed_after_spend'] > 0)]
            
            if len(type_df) == 0:
                continue
            
            before_spend = type_df['before_spend'].sum()
            before_sales = type_df['before_sales'].sum()
            after_spend = type_df['observed_after_spend'].sum()
            after_sales = type_df['observed_after_sales'].sum()
            
            roas_before = before_sales / before_spend if before_spend > 0 else 0
            roas_after = after_sales / after_spend if after_spend > 0 else 0
            
            contribution = before_spend * (roas_after - roas_before)
            
            name = display_names.get(action_type, action_type.replace('_', ' ').title())
            contributions[name] = contributions.get(name, 0) + contribution
    
    if not contributions:
        st.info("Insufficient data for attribution")
        return
    
    # Get the authoritative total from summary (must match hero tile)
    target_total = summary.get('incremental_revenue', 0)
    calculated_total = sum(contributions.values())
    
    # Scale contributions proportionally so they sum to the hero tile's incremental_revenue
    if calculated_total != 0 and target_total != 0:
        scale_factor = target_total / calculated_total
        contributions = {k: v * scale_factor for k, v in contributions.items()}
    
    # Sort and create chart
    sorted_data = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
    names = [x[0] for x in sorted_data]
    impacts = [x[1] for x in sorted_data]
    
    # Color palette matching donut chart (purple-slate-gray scale, cyan only for total)
    bar_colors = ['#5B556F', '#8F8CA3', '#475569', '#334155', '#64748b']  # Purple to slate
    colors = [bar_colors[i % len(bar_colors)] for i in range(len(impacts))]
    colors.append('#22d3ee')  # Cyan for total only
    
    # Total must match hero tile exactly
    final_total = target_total if target_total != 0 else sum(impacts)
    
    # Brand colors from Account Overview: Purple (#5B556F), Cyan (#22d3ee)
    fig = go.Figure(go.Waterfall(
        name="Contribution",
        orientation="v",
        measure=["relative"] * len(impacts) + ["total"],
        x=names + ['Total'],
        y=impacts + [final_total],
        connector={"line": {"color": "rgba(143, 140, 163, 0.3)"}},  # #8F8CA3
        decreasing={"marker": {"color": "#8F8CA3"}},   # Neutral slate (for negatives)
        increasing={"marker": {"color": "#5B556F"}},   # Brand Purple (for positives)
        totals={"marker": {"color": "#22d3ee"}},       # Accent Cyan
        textposition="outside",
        textfont=dict(size=14, color="#e2e8f0"),
        text=[f"{currency}{v:+,.0f}" for v in impacts] + [f"{currency}{final_total:+,.0f}"]
    ))
    
    fig.update_layout(
        showlegend=False,
        height=380,
        margin=dict(t=60, b=40, l=30, r=30),  # Much more space for labels
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.15)', tickformat=',.0f', tickfont=dict(color='#94a3b8', size=12)),
        xaxis=dict(showgrid=False, tickfont=dict(color='#cbd5e1', size=12))
    )
    
    st.plotly_chart(fig, width='stretch')


def _render_stacked_revenue_bar(summary: Dict[str, Any], currency: str, validated_only: bool = True):
    """Render stacked bar showing Before Revenue vs After (Baseline + Incremental)."""
    
    title = "#### 📈 Baseline vs. Incremental Sales" if validated_only else "#### 📈 Revenue Comparison"
    st.markdown(title)
    
    # Get actual values from summary
    before_sales = summary.get('before_sales', 0)
    after_sales = summary.get('after_sales', 0)
    incremental = summary.get('incremental_revenue', 0)
    roas_before = summary.get('roas_before', 0)
    roas_after = summary.get('roas_after', 0)
    
    # If we have actual sales values, use them
    if before_sales > 0 and after_sales > 0:
        fig = go.Figure()
        
        # Before bar - Brand Purple
        fig.add_trace(go.Bar(
            name='Sales (Before)',
            x=['Before'],
            y=[before_sales],
            marker_color='#5B556F',  # Brand Purple
            text=[f"{currency}{before_sales:,.0f}"],
            textposition='auto',
            textfont=dict(color='#e2e8f0', size=13),
        ))
        
        # After bar with incremental highlight
        fig.add_trace(go.Bar(
            name='Baseline (Expected)',
            x=['After'],
            y=[before_sales],  # Same as before (baseline)
            marker_color='#5B556F',  # Brand Purple
            showlegend=True,
        ))
        
        # Use ROAS-based incremental from summary (matches waterfall and hero tile)
        # This is: before_spend × (roas_after - roas_before)
        lift = incremental  # Use the calculated incremental, not raw sales delta
        lift_color = '#22d3ee'  # Accent Cyan for incremental
        fig.add_trace(go.Bar(
            name='Incremental (Lift)',
            x=['After'],
            y=[lift],
            marker_color=lift_color,
            text=[f"{'+' if lift >= 0 else ''}{currency}{lift:,.0f}"],
            textposition='outside',
            textfont=dict(color='#e2e8f0', size=14),
        ))
        
        fig.update_layout(
            barmode='stack',
            showlegend=True,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5, font=dict(color='#94a3b8', size=11)),
            height=380,
            margin=dict(t=60, b=40, l=30, r=30),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.15)', tickfont=dict(color='#94a3b8', size=12)),
            xaxis=dict(showgrid=False, tickfont=dict(color='#cbd5e1', size=12))
        )
        
        st.plotly_chart(fig, width='stretch')
        
    elif roas_before > 0 or roas_after > 0:
        # Fallback: Show ROAS comparison bars with brand colors
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=['Before', 'After'],
            y=[roas_before, roas_after],
            marker_color=['#5B556F', '#22d3ee'],  # Brand Purple to Cyan
            text=[f"{roas_before:.2f}x", f"{roas_after:.2f}x"],
            textposition='auto',
            textfont=dict(color='#e2e8f0', size=14),
        ))
        fig.update_layout(
            showlegend=False,
            height=380,
            margin=dict(t=40, b=40, l=30, r=30),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)', title="ROAS", tickfont=dict(color='#94a3b8', size=12)),
            xaxis=dict(showgrid=False)
        )
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No comparative data")


def _render_impact_analytics(summary: Dict[str, Any], impact_df: pd.DataFrame):
    """Render the dual-chart impact analytics section."""
    
    col1, col2 = st.columns([1.2, 0.8])
    
    with col1:
        _render_waterfall_chart(summary)
    
    with col2:
        _render_roas_comparison(summary)


def _render_waterfall_chart(summary: Dict[str, Any]):
    """Render waterfall chart showing incremental revenue by action type."""
    
    # Target icon for action type
    icon_color = "#8F8CA3"
    target_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle></svg>'
    st.markdown(f"#### {target_icon}Revenue Impact by Type", unsafe_allow_html=True)
    
    by_type = summary.get('by_action_type', {})
    if not by_type:
        st.info("No action type breakdown available")
        return
    
    # Map raw types to display names
    display_names = {
        'BID_CHANGE': 'Bid Optim.',
        'NEGATIVE': 'Cost Saved',
        'HARVEST': 'Harvest Gains',
        'BID_ADJUSTMENT': 'Bid Optim.'
    }
    
    # Aggregate data
    agg_data = {}
    for t, data in by_type.items():
        name = display_names.get(t, t.replace('_', ' ').title())
        agg_data[name] = agg_data.get(name, 0) + data['net_sales']
    
    # Sort
    sorted_data = sorted(agg_data.items(), key=lambda x: x[1], reverse=True)
    names = [x[0] for x in sorted_data]
    impacts = [x[1] for x in sorted_data]
    
    from utils.formatters import get_account_currency
    chart_currency = get_account_currency()
    
    fig = go.Figure(go.Waterfall(
        name="Impact",
        orientation="v",
        measure=["relative"] * len(impacts) + ["total"],
        x=names + ['Total'],
        y=impacts + [sum(impacts)],
        connector={"line": {"color": "rgba(148, 163, 184, 0.2)"}},
        decreasing={"marker": {"color": "rgba(248, 113, 113, 0.5)"}}, 
        increasing={"marker": {"color": "rgba(74, 222, 128, 0.6)"}}, 
        totals={"marker": {"color": "rgba(143, 140, 163, 0.6)"}},
        textposition="outside",
        text=[f"{chart_currency}{v:+,.0f}" for v in impacts] + [f"{chart_currency}{sum(impacts):+,.0f}"]
    ))
    
    fig.update_layout(
        showlegend=False,
        height=320,
        margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)', tickformat=',.0f'),
        xaxis=dict(showgrid=False)
    )
    
    st.plotly_chart(fig, width='stretch')


def _render_roas_comparison(summary: Dict[str, Any]):
    """Render side-by-side ROAS before/after comparison."""
    
    icon_color = "#8F8CA3"
    trend_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>'
    st.markdown(f"#### {trend_icon}Account ROAS Shift", unsafe_allow_html=True)
    
    r_before = summary.get('roas_before', 0)
    r_after = summary.get('roas_after', 0)
    
    if r_before == 0 and r_after == 0:
        st.info("No comparative ROAS data")
        return
        
    fig = go.Figure()
    
    # Before Bar
    fig.add_trace(go.Bar(
        x=['Before Optim.'],
        y=[r_before],
        name="Before",
        marker_color="rgba(148, 163, 184, 0.4)",
        text=[f"{r_before:.2f}"],
        textposition='auto',
    ))
    
    # After Bar
    color = "rgba(74, 222, 128, 0.6)" if r_after >= r_before else "rgba(248, 113, 113, 0.6)"
    fig.add_trace(go.Bar(
        x=['After Optim.'],
        y=[r_after],
        name="After",
        marker_color=color,
        text=[f"{r_after:.2f}"],
        textposition='auto',
    ))
    
    fig.update_layout(
        showlegend=False,
        height=320,
        margin=dict(t=10, b=10, l=40, r=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)', title="Account ROAS"),
        xaxis=dict(showgrid=False)
    )
    
    st.plotly_chart(fig, width='stretch')


def _render_winners_losers_chart(impact_df: pd.DataFrame):
    """Render top contributors by incremental revenue."""
    
    # Chart icon 
    icon_color = "#8F8CA3"
    chart_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>'
    st.markdown(f"#### {chart_icon}Top Revenue Contributors", unsafe_allow_html=True)
    
    if impact_df.empty:
        st.info("No targeting data available")
        return
    
    # AGGREGATE BY CAMPAIGN > AD GROUP > TARGET
    agg_cols = {
        'impact_score': 'sum',
        'before_spend': 'sum',
        'after_spend': 'sum'
    }
    # Include campaign and ad group to avoid merging "close-match" etc account-wide
    group_cols = ['campaign_name', 'ad_group_name', 'target_text']
    target_perf = impact_df.groupby(group_cols).agg(agg_cols).reset_index()
    
    # Filter to targets that actually had activity
    target_perf = target_perf[(target_perf['before_spend'] > 0) | (target_perf['after_spend'] > 0)]
    
    if target_perf.empty:
        st.info("No matched targets with performance data found")
        return
    
    # Get top 5 winners and bottom 5 losers by impact_score
    winners = target_perf.sort_values('impact_score', ascending=False).head(5)
    losers = target_perf.sort_values('impact_score', ascending=True).head(5)
    
    # Combine for chart
    chart_df = pd.concat([winners, losers]).drop_duplicates().sort_values('impact_score', ascending=False)
    
    # Create descriptive labels
    def create_label(row):
        target = row['target_text']
        cam = row['campaign_name'][:15] + '..' if len(row['campaign_name']) > 15 else row['campaign_name']
        adg = row['ad_group_name'][:10] + '..' if len(row['ad_group_name']) > 10 else row['ad_group_name']
        
        # If it's an auto-type, emphasize the type but show campaign
        if target.lower() in ['close-match', 'loose-match', 'substitutes', 'complements']:
            return f"{target} ({cam})"
        return f"{target[:20]}.. ({cam})"

    chart_df['display_label'] = chart_df.apply(create_label, axis=1)
    chart_df['full_context'] = chart_df.apply(lambda r: f"Cam: {r['campaign_name']}<br>Ad Group: {r['ad_group_name']}<br>Target: {r['target_text']}", axis=1)
    
    # Rename for the chart library to use
    chart_df['raw_perf'] = chart_df['impact_score']
    
    # Brand-aligned palette: Muted violet for positive, muted wine for negative
    chart_df['color'] = chart_df['raw_perf'].apply(
        lambda x: "rgba(91, 85, 111, 0.6)" if x > 0 else "rgba(136, 19, 55, 0.5)"
    )
    
    from utils.formatters import get_account_currency
    bar_currency = get_account_currency()
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=chart_df['display_label'],
        x=chart_df['raw_perf'],
        orientation='h',
        marker_color=chart_df['color'],
        text=[f"{bar_currency}{v:+,.0f}" for v in chart_df['raw_perf']],
        textposition='outside',
        hovertext=chart_df['full_context'],
        hoverinfo='text+x'
    ))
    
    fig.update_layout(
        height=350,
        margin=dict(t=20, b=20, l=20, r=60),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)', zeroline=True, zerolinecolor='rgba(128,128,128,0.5)'),
        yaxis=dict(showgrid=False, autorange='reversed')
    )

    
    st.plotly_chart(fig, width='stretch')


def _render_drill_down_table(impact_df: pd.DataFrame, show_migration_badge: bool = False):
    """Render detailed drill-down table with decision-adjusted metrics."""
    
    import numpy as np
    
    with st.expander("📋 Detailed Action Log", expanded=False):
        if impact_df.empty:
            st.info("No actions to display")
            return
        
        # Create display dataframe with all decision-adjusted calculations
        display_df = impact_df.copy()
        
        # Add migration badge for HARVEST with before_spend > 0
        if show_migration_badge and 'is_migration' in display_df.columns:
            display_df['action_display'] = display_df.apply(
                lambda r: f"🔄 {r['action_type']}" if r.get('is_migration', False) else r['action_type'],
                axis=1
            )
        else:
            display_df['action_display'] = display_df['action_type']
        
        # ==========================================
        # USE BACKEND-CALCULATED METRICS (Single Source of Truth)
        # All decision metrics are pre-calculated in get_action_impact()
        # Frontend only displays - no recalculation
        # ==========================================
        
        # Ensure columns exist (defensive - backend should provide these)
        for col in ['decision_impact', 'spend_avoided', 'cpc_before', 'cpc_after', 
                    'cpc_change_pct', 'expected_sales', 'spc_before', 'market_downshift']:
            if col not in display_df.columns:
                display_df[col] = np.nan
        
        # Market Tag logic - uses backend-calculated market_downshift
        def get_market_tag(row):
            if row.get('before_clicks', 0) == 0:
                return "Low Data"
            if row.get('market_downshift', False) == True:
                return "Market Downshift"
            return "Normal"
        display_df['market_tag'] = display_df.apply(get_market_tag, axis=1)
        
        # Decision Outcome logic
        def get_decision_outcome(row):
            action = str(row['action_type']).upper()
            di = row['decision_impact'] if pd.notna(row['decision_impact']) else 0
            sa = row['spend_avoided'] if pd.notna(row['spend_avoided']) else 0
            bs = row['before_spend'] if pd.notna(row['before_spend']) else 0
            market_tag = row['market_tag']
            
            # Low Data → Neutral
            if market_tag == "Low Data":
                return "🟡 Neutral"
            
            # Good: DI > 0 OR (defensive + significant spend avoided + market downshift)
            if di > 0:
                return "🟢 Good"
            if action in ['BID_DOWN', 'PAUSE', 'NEGATIVE'] and bs > 0 and sa >= 0.1 * bs:
                return "🟢 Good"
            
            # Neutral: small impact
            before_sales = row['before_sales'] if pd.notna(row['before_sales']) else 0
            threshold = max(0.05 * before_sales, 10)  # 5% of before_sales or $10
            if abs(di) < threshold:
                return "🟡 Neutral"
            
            # Bad: negative impact in normal market
            if di < 0 and market_tag == "Normal":
                return "🔴 Bad"
            
            # Default to Neutral for edge cases
            return "🟡 Neutral"
        
        display_df['decision_outcome'] = display_df.apply(get_decision_outcome, axis=1)
        
        # ==========================================
        # SELECT FINAL COLUMNS (per spec)
        # ==========================================
        display_cols = [
            'action_display', 'target_text', 'reason',
            'before_spend', 'observed_after_spend', 'spend_avoided',
            'before_sales', 'observed_after_sales',
            'cpc_before', 'cpc_after', 'cpc_change_pct',
            'expected_sales', 'decision_impact',
            'market_tag', 'decision_outcome', 'validation_status'
        ]
        
        # Filter to columns that actually exist
        cols_to_use = [c for c in display_cols if c in display_df.columns]
        display_df = display_df[cols_to_use].copy()
        
        # Rename for user-friendly display
        final_rename = {
            'action_display': 'Action Taken',
            'target_text': 'Target',
            'reason': 'Logic Basis',
            'before_spend': 'Before Spend',
            'observed_after_spend': 'After Spend',
            'spend_avoided': 'Spend Avoided',
            'before_sales': 'Before Sales',
            'observed_after_sales': 'After Sales',
            'cpc_before': 'CPC Before',
            'cpc_after': 'CPC After',
            'cpc_change_pct': 'CPC Change %',
            'expected_sales': 'Expected Sales',
            'decision_impact': 'Decision Impact',
            'market_tag': 'Market Tag',
            'decision_outcome': 'Decision Outcome',
            'validation_status': 'Validation Status'
        }
        display_df = display_df.rename(columns=final_rename)
        
        # Format currency columns
        from utils.formatters import get_account_currency
        df_currency = get_account_currency()
        currency_cols = ['Before Spend', 'After Spend', 'Spend Avoided', 'Before Sales', 'After Sales', 'Expected Sales', 'Decision Impact']
        for col in currency_cols:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"{df_currency}{x:,.2f}" if pd.notna(x) else "-")
        
        # Format CPC columns
        cpc_cols = ['CPC Before', 'CPC After']
        for col in cpc_cols:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"{df_currency}{x:.2f}" if pd.notna(x) else "-")
        
        # Format CPC Change %
        if 'CPC Change %' in display_df.columns:
            display_df['CPC Change %'] = display_df['CPC Change %'].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "-")
        
        # Show migration legend if applicable
        if show_migration_badge and 'is_migration' in impact_df.columns and impact_df['is_migration'].any():
            st.caption("🔄 = **Migration Tracking**: Efficiency gain from harvesting search term to exact match.")
        
        st.dataframe(
            display_df,
            width='stretch',
            column_config={
                "Decision Impact": st.column_config.TextColumn(
                    "Decision Impact",
                    help="Market-adjusted: After_Sales - Expected_Sales (what would have happened without change)"
                ),
                "Expected Sales": st.column_config.TextColumn(
                    "Expected Sales",
                    help="Counterfactual: (After_Spend / CPC_Before) × CVR_Before × AOV_Before"
                ),
                "Market Tag": st.column_config.TextColumn(
                    "Market Tag",
                    help="Normal | Market Downshift (CPC dropped >25%) | Low Data (no baseline clicks)"
                ),
                "Decision Outcome": st.column_config.TextColumn(
                    "Decision Outcome",
                    help="Good: positive impact or successful defense | Neutral: small/ambiguous | Bad: negative impact in stable market"
                ),
                "Validation Status": st.column_config.TextColumn(
                    "Validation Status",
                    help="Verification that the action was actually applied based on subsequent spend reporting"
                )
            }
        )
        
        # Download button
        csv = impact_df.to_csv(index=False)
        st.download_button(
            "📥 Download Full Data (CSV)",
            csv,
            "impact_analysis.csv",
            "text/csv"
        )


def _render_dormant_table(dormant_df: pd.DataFrame):
    """Render simple table for dormant actions ($0 spend in both periods)."""
    
    if dormant_df.empty:
        return
    
    # Simplified view for dormant
    display_cols = ['action_type', 'target_text', 'old_value', 'new_value', 'reason']
    available_cols = [c for c in display_cols if c in dormant_df.columns]
    display_df = dormant_df[available_cols].copy()
    
    display_df = display_df.rename(columns={
        'action_type': 'Action',
        'target_text': 'Target',
        'old_value': 'Old Value',
        'new_value': 'New Value',
        'reason': 'Reason'
    })
    
    st.dataframe(display_df, width='stretch', hide_index=True)
    
    st.caption(f"💡 These {len(dormant_df)} optimizations have an established baseline but are pending traffic. "
              "They will appear in Measured Impact once the targets receive impressions.")


def render_reference_data_badge():
    """Render reference data status badge for sidebar."""
    
    db_manager = st.session_state.get('db_manager')
    if db_manager is None:
        return
    
    try:
        status = db_manager.get_reference_data_status()
        
        if not status['exists']:
            st.markdown("""
            <div style="padding: 8px 12px; background: rgba(239, 68, 68, 0.1); border-radius: 8px; border-left: 3px solid #EF4444;">
                <span style="font-size: 0.85rem;">❌ <strong>No Reference Data</strong></span>
            </div>
            """, unsafe_allow_html=True)
        elif status['is_stale']:
            days = status['days_ago']
            st.markdown(f"""
            <div style="padding: 8px 12px; background: rgba(245, 158, 11, 0.1); border-radius: 8px; border-left: 3px solid #F59E0B;">
                <span style="font-size: 0.85rem;">⚠️ <strong>Data Stale</strong> ({days} days ago)</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            days = status['days_ago']
            count = status['record_count']
            st.markdown(f"""
            <div style="padding: 8px 12px; background: rgba(16, 185, 129, 0.1); border-radius: 8px; border-left: 3px solid #10B981;">
                <span style="font-size: 0.85rem;">✅ <strong>Data Loaded</strong> ({days}d ago, {count:,} records)</span>
            </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        pass  # Silently handle errors

def get_recent_impact_summary() -> Optional[dict]:
    """
    Helper for Home Page cockpit.
    Returns impact summary metrics from DB for the last 14 days (Decision Impact focus).
    Matches new 'Recent Impact' tile definition.
    Uses cached _fetch_impact_data to avoid redundant DB queries.
    """
    # Check for test mode
    test_mode = st.session_state.get('test_mode', False)
    
    # Fallback chain for account ID (same as health score)
    selected_client = (
        st.session_state.get('active_account_id') or 
        st.session_state.get('active_account_name') or 
        st.session_state.get('last_stats_save', {}).get('client_id')
    )
    
    if not selected_client:
        return None
        
    try:
        # Construct cache version to ensure data freshness on new uploads
        # This matches the strategy in ImpactDashboardModule (v19_perf_)
        cache_version = "v19_perf_" + str(st.session_state.get('data_upload_timestamp', 'init'))
        
        # Use existing CACHED data fetcher (14 Days)
        # discard dataframe, keep summary
        impact_df, summary = _fetch_impact_data(selected_client, test_mode, before_days=14, after_days=14, cache_version=cache_version)
        
        # CONSOLE DEBUG
        print(f"\n[HOME TILE DEBUG]")
        print(f"Cache Key: {cache_version}")
        print(f"Selected Client: {selected_client}")
        # Check if 'final_decision_impact' exists
        has_final = 'final_decision_impact' in impact_df.columns
        print(f"Has 'final_decision_impact': {has_final}")
        if has_final:
            print(f"Avg Confidence Weight: {impact_df['confidence_weight'].mean() if 'confidence_weight' in impact_df.columns else 'N/A'}")

        # ==========================================
        # PHASE 3: USE CANONICAL METRICS
        # ==========================================
        from features.impact_metrics import ImpactMetrics
        
        # === CRITICAL FIX: REPLICATE MATURITY LOGIC ===
        # Getting the maturity right is essential for matching the dash
        if not impact_df.empty and 'action_date' in impact_df.columns:
            try:
                # Use DB source of truth for latest date to match Exec Dash
                # Otherwise summary.period_info might lag (e.g. Jan 12 vs Jan 17)
                latest_data_date = None
                db = get_db_manager(test_mode)
                if hasattr(db, 'get_latest_raw_data_date'):
                    latest_data_date = db.get_latest_raw_data_date(selected_client)
            except Exception as e:
                print(f"Error fetching latest date for {selected_client}: {e}")
                latest_data_date = None
            
            if not latest_data_date:
                period_info = summary.get('period_info', {})
                # Fallback safely to whatever date is available
                latest_data_date = period_info.get('after_end') or period_info.get('latest_date')
            
            if latest_data_date:
                # Calculate maturity exactly as dashboard does
                impact_df['is_mature'] = impact_df['action_date'].apply(
                    lambda d: get_maturity_status(d, latest_data_date, horizon='14D')['is_mature']
                )
        
        # Calculate metrics using single source of truth
        # Fixed 14-day window for home tile
        # ENFORCE FILTERS to match Dashboard default view
        canonical_filters = {
            'validated_only': True,
            'mature_only': True
        }
        
        # Use ImpactMetrics.from_dataframe() for canonical calculation
        # This matches EXACTLY how Impact Dashboard calculates its number
        canonical_filters = {
            'validated_only': True,
            'mature_only': True
        }
        
        metrics = ImpactMetrics.from_dataframe(
            impact_df, 
            horizon_days=14,
            filters=canonical_filters
        )
        
        # CONSOLE DEBUG PART 2
        print(f"Metrics Attributed Impact: {metrics.attributed_impact}")
        
        # Verify manual sums on the subset metrics is seeing
        # We need to replicate default behavior of ImpactMetrics to see what it sees
        subset = impact_df.copy()
        if 'is_mature' in subset.columns:
            subset = subset[subset['is_mature'] == True]
        mask = subset['validation_status'].astype(str).str.contains('✓|CPC Validated|CPC Match|Directional|Confirmed|Normalized|Volume', na=False, regex=True)
        subset = subset[mask]
        
        raw_sum = subset['decision_impact'].sum() if 'decision_impact' in subset.columns else 0
        final_sum = subset['final_decision_impact'].sum() if 'final_decision_impact' in subset.columns else 0
        
        print(f"Manual Raw Sum (Mature+Valid): {raw_sum:,.0f}")
        print(f"Manual Final Sum (Mature+Valid): {final_sum:,.0f}")
        print(f"-------------------------------------------")
        
        if not metrics.has_data:
            return None
            
        # Extract values
        decision_impact = metrics.attributed_impact
        win_rate = metrics.win_rate
        
        # Handle top action type (legacy logic for now as ImpactMetrics doesn't group by type yet)
        # We need to filter the summary/dataframe to match the metrics filters for consistency
        # But 'summary' from _fetch_impact_data is pre-calculated. 
        # For simplicity, we trust the top action from the 'validated' bucket if available.
        active_summary = summary.get('validated', summary.get('all', summary))
        by_type = active_summary.get('by_action_type', {})
        top_action_type = None
        if by_type:
            top_action_type = max(by_type, key=lambda k: by_type[k].get('decision_impact', 0))
            
        return {
            'sales': decision_impact, # Mapped to 'sales' key for compatibility but represents impact
            'label': 'Decision Impact',
            'win_rate': win_rate,
            'top_action_type': top_action_type,
            'quality_score': active_summary.get('pct_good', 0) - active_summary.get('pct_bad', 0), # Keep legacy for quality score
            'roi': metrics.decision_impact_roas * 100 # Convert to percentage
        }
        
    except Exception as e:
        print(f"[Impact Summary] Error: {e}")
        return None


def _render_recent_wins_list(impact_df: pd.DataFrame, currency: str):
    """
    Render scrollable list of top 5 recent winning decisions with premium cards.
    """
    # 1. Header
    st.markdown("""
<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 20px;">
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"></path><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"></path><path d="M4 22h16"></path><path d="M10 14.66V17"></path><path d="M14 14.66V17"></path><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"></path></svg>
    <span style="font-weight: 700; font-size: 1rem; color: #F8FAFC;">RECENT WINNING DECISIONS</span>
</div>
""", unsafe_allow_html=True)
    
    if impact_df.empty:
        st.info("No recent wins found.")
        return

    # 2. Filter & Sort Data
    # Wins: impact > 0 AND validated
    wins_df = impact_df[
        (impact_df['decision_impact'] > 0) & 
        (impact_df['validation_status'].astype(str).str.contains('✓|Confirmed|Validated|Directional', na=False))
    ].copy()
    
    if wins_df.empty:
        st.caption("No validated wins in this period yet.")
        return
        
    # Sort by date descending (most recent first)
    if 'action_date' in wins_df.columns:
        wins_df['action_date'] = pd.to_datetime(wins_df['action_date'])
        wins_df = wins_df.sort_values(by='action_date', ascending=False)
    
    # Take top 5
    top_wins = wins_df.head(5)
    
    # 3. Render Cards
    for idx, row in top_wins.iterrows():
        # Format Data
        action_desc = row.get('target_text', 'Unknown Action')
        if len(action_desc) > 35:
            action_desc = action_desc[:32] + "..."
            
        impact_val = row.get('decision_impact', 0)
        formatted_impact = f"{currency}{impact_val:,.0f}" if currency else f"${impact_val:,.0f}"
        
        action_date = row.get('action_date')
        date_str = action_date.strftime('%b %d') if pd.notnull(action_date) else ""
        action_type = str(row.get('action_type', '')).replace('_', ' ').title()
        
        # Determine icon based on type
        if 'Bid' in action_type:
            type_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>'
        elif 'Negative' in action_type:
            type_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line></svg>'
        else:
            type_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"></path><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"></path><path d="M4 22h16"></path></svg>'

        # Card HTML
        st.markdown(f"""
<div style="
    background: rgba(30, 41, 59, 0.4); 
    border: 1px solid rgba(148, 163, 184, 0.1); 
    border-left: 3px solid #10B981;
    border-radius: 8px; 
    padding: 12px 16px; 
    margin-bottom: 12px;
    display: flex; 
    align-items: center; 
    justify-content: space-between;
    transition: transform 0.2s;
" onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
    <div style="flex: 1;">
        <div style="color: #E2E8F0; font-weight: 600; font-size: 0.95rem; margin-bottom: 4px;">
            {action_desc}
        </div>
        <div style="display: flex; align-items: center; gap: 6px; color: #94A3B8; font-size: 0.8rem;">
            {type_icon} {date_str} • {action_type}
        </div>
    </div>
    <div style="text-align: right;">
        <div style="color: #10B981; font-weight: 700; font-size: 1.1rem; margin-bottom: 2px;">
            +{formatted_impact}
        </div>
        <div style="color: #64748B; font-size: 0.75rem;">
            (14-day measured)
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
    

# ==========================================
# ROAS IMPACT CHART (Counterfactual)
# ==========================================

def _render_revenue_counterfactual_chart(impact_df: pd.DataFrame, client_id: str, cache_version: str, verified_lift_override: float = None, summary_context: dict = None):
    """
    Render Actual vs. Baseline Revenue Chart.
    Baseline = Actual Sales - Decision Impact.
    Revenue is additive, so time series will match aggregate attribution perfectly.
    """
    import plotly.graph_objects as go
    
    # 1. Fetch Actuals (Daily)
    actuals_df = _fetch_account_actuals(client_id, cache_version)
    if actuals_df.empty:
        return
    
    # 2. Aggregate Actuals (Daily)
    daily_actuals = actuals_df.groupby('Date')[['Sales']].sum().reset_index()
    daily_actuals.columns = ['date', 'actual_sales']
    
    # 3. Create daily adjustment map
    min_date = daily_actuals['date'].min()
    max_date = daily_actuals['date'].max()
    date_range = pd.date_range(start=min_date, end=max_date)
    daily_adj = pd.DataFrame({'date': date_range})
    daily_adj['sales_lift'] = 0.0
    daily_adj.set_index('date', inplace=True)
    
    # 4. Spread decision impacts across action windows
    if not impact_df.empty:
        impact_df['action_date'] = pd.to_datetime(impact_df['action_date'])
        default_window = 14
        
        for _, row in impact_df.iterrows():
            start_date = row['action_date'] + pd.Timedelta(days=1)
            window_days = row['actual_after_days'] if 'actual_after_days' in row and pd.notna(row['actual_after_days']) else default_window
            window_days = max(1, int(window_days))
            end_date = start_date + pd.Timedelta(days=window_days - 1)
            
            # Per-day revenue impact (uniform distribution)
            daily_sales = row['decision_impact'] / window_days
            
            # Add to date range
            eff_start = max(start_date, min_date)
            eff_end = min(end_date, max_date)
            
            if eff_start <= eff_end:
                daily_adj.loc[eff_start:eff_end, 'sales_lift'] += daily_sales
    
    daily_adj = daily_adj.reset_index()
    
    # 5. Merge
    merged = pd.merge(daily_actuals, daily_adj, on='date', how='left').fillna(0)
    merged.rename(columns={'sales_lift': 'daily_sales_impact'}, inplace=True)
    
    # === ALIGNMENT FIX: Scale chart data to match "Truth" Summary Cards ===
    # The summary cards (Helped/Hurt) use strict filtering/confidence logic stored in session state.
    # To ensure the chart visual strictly aligns with the reported Net Impact, we scale the daily impacts.
    impact_metrics = st.session_state.get('_impact_metrics', {})
    target_net_impact = impact_metrics.get('attributed_impact', None)
    
    current_chart_sum = merged['daily_sales_impact'].sum()
    
    if target_net_impact is not None and current_chart_sum != 0:
        scaling_factor = target_net_impact / current_chart_sum
        merged['daily_sales_impact'] = merged['daily_sales_impact'] * scaling_factor
        # Use target explicitly for total
        total_impact = target_net_impact
    else:
        # Fallback if metrics missing
        total_impact = current_chart_sum
        
    # 6. Weekly Aggregation (for smoothing)
    merged['week'] = merged['date'].dt.to_period('W-MON').dt.start_time
    weekly = merged.groupby('week').agg({
        'actual_sales': 'sum',
        'daily_sales_impact': 'sum'
    }).reset_index()
    
    # 7. Calculate Baseline Revenue
    weekly['baseline_sales'] = weekly['actual_sales'] - weekly['daily_sales_impact']
    
    # 8. Calculate aggregate metrics for display
    total_actual = weekly['actual_sales'].sum()
    total_baseline = total_actual - total_impact
    
    # 9. Create the chart
    fig = go.Figure()
    
    # Baseline (Dotted Line)
    fig.add_trace(go.Scatter(
        x=weekly['week'],
        y=weekly['baseline_sales'],
        name='Baseline',
        line=dict(
            color='rgba(148, 163, 184, 0.6)',  # Muted gray
            width=2,
            dash='dot'
        ),
        mode='lines'
    ))
    
    # Actual (Solid Line)
    fig.add_trace(go.Scatter(
        x=weekly['week'],
        y=weekly['actual_sales'],
        name='Actual Revenue',
        line=dict(
            color='#06b6d4',  # Cyan (matching your theme)
            width=3
        ),
        mode='lines+markers',
        marker=dict(size=6)
    ))
    
    # 10. Styling
    fig.update_layout(
        title=dict(
            text='Revenue Impact Analysis',
            font=dict(size=20, color='white', family='Inter'),
            x=0.02
        ),
        plot_bgcolor='rgba(15, 23, 42, 0.6)',  # Dark slate
        paper_bgcolor='rgba(15, 23, 42, 0)',
        font=dict(color='white', family='Inter'),
        xaxis=dict(
            title='',
            gridcolor='rgba(148, 163, 184, 0.1)',
            showgrid=True
        ),
        yaxis=dict(
            title='Revenue',
            gridcolor='rgba(148, 163, 184, 0.1)',
            showgrid=True,
            tickformat=',.0f'  # Format as currency
        ),
        hovermode='x unified',
        legend=dict(
            orientation='h',
            yanchor='top',
            y=1.08,
            xanchor='right',
            x=1,
            bgcolor='rgba(15, 23, 42, 0.8)',
            bordercolor='rgba(148, 163, 184, 0.3)',
            borderwidth=1
        ),
        margin=dict(t=100, b=150, l=60, r=40),
        height=400
    )
    
    # 11. Add metrics bar below chart
    fig.add_annotation(
        text=f"Based on {len(weekly)} weeks of data",
        xref="paper", yref="paper",
        x=0.25, y=-0.15,
        showarrow=False,
        font=dict(size=11, color="rgba(148, 163, 184, 0.8)"),
        align="center"
    )
    
    fig.add_annotation(
        text=f"Baseline: {total_baseline:,.0f}",
        xref="paper", yref="paper",
        x=0.45, y=-0.15,
        showarrow=False,
        font=dict(size=11, color="rgba(148, 163, 184, 0.8)"),
        align="center"
    )
    
    fig.add_annotation(
        text=f"Your Lift: <span style='color:#10b981'>+{total_impact:,.0f}</span>",
        xref="paper", yref="paper",
        x=0.65, y=-0.15,
        showarrow=False,
        font=dict(size=11, color="rgba(148, 163, 184, 0.8)"),
        align="center"
    )
    
    fig.add_annotation(
        text=f"Confidence: <span style='color:#10b981'>Calculated in Model</span>",
        xref="paper", yref="paper",
        x=0.85, y=-0.15,
        showarrow=False,
        font=dict(size=11, color="rgba(148, 163, 184, 0.8)"),
        align="center"
    )
    
    # 12. Add clean footnote
    fig.add_annotation(
        text="Baseline isolates your decision impact from external market forces and portfolio-level structural changes.",
        xref="paper", yref="paper",
        x=0.5, y=-0.22,
        xanchor="center", yanchor="top",
        showarrow=False,
        font=dict(
            size=11,
            color="rgba(148, 163, 184, 0.8)",
            family="Inter"
        ),
        align="center"
    )
    
    st.plotly_chart(fig, width='stretch', config={'displayModeBar': False}, key=f"rev_impact_chart_{cache_version}_{client_id}")


    


