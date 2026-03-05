"""
Optimizer Core Logic
Contains shared constants, data preparation, benchmarks, and health calculation.
"""

import pandas as pd
import numpy as np
import streamlit as st
from datetime import timedelta
from typing import Tuple, Dict, Any, Optional

from features.constants import AUTO_TARGETING_TYPES, normalize_auto_targeting
from app_core.db_manager import get_db_manager
from utils.metrics import calculate_ppc_metrics, ensure_numeric_columns

# ==========================================
# CONSTANTS
# ==========================================

BULK_COLUMNS = [
    "Product", "Entity", "Operation", "Campaign Id", "Ad Group Id", 
    "Campaign Name", "Ad Group Name", "Ad Group Default Bid", "Bid", 
    "Keyword Text", "Match Type", "Product Targeting Expression",
    "Keyword Id", "Product Targeting Id", "State"
]

# Bid Safety Limits (Option C: Hybrid - relative + absolute floor)
BID_LIMITS = {
    "MIN_BID_FLOOR": 0.30,        # Never bid below $0.30 (Amazon minimum)
    "MIN_BID_MULTIPLIER": 0.50,   # Never below 50% of current bid
    "MAX_BID_MULTIPLIER": 3.00,   # Never above 300% of current bid
}

# CVR-Based Threshold Configuration
CVR_CONFIG = {
    "CVR_FLOOR": 0.01,             # Minimum CVR for calculations (1%)
    "CVR_CEILING": 0.20,           # Maximum CVR for calculations (20%)
    "HARD_STOP_MULTIPLIER": 3.0,   # Hard stop = 3× expected clicks to convert
    "SOFT_NEGATIVE_FLOOR": 10,     # Minimum clicks for soft negative
    "HARD_STOP_FLOOR": 15,         # Minimum clicks for hard stop
}

# Universal Throttle Logic (Reactivity Model)
OPTIMIZATION_PROFILES = {
    "aggressive": {
        "label": "Aggressive (High Velocity)",
        "description": "Ruthless. Fast scaling, fast cutting.",
        "params": {
            "BID_UP_THROTTLE": 0.70,
            "BID_DOWN_THROTTLE": 0.70,
            "HARVEST_ROAS_MULT": 0.75,
            "SOFT_NEGATIVE_MULT": 1.2,
            "HARD_STOP_MULTIPLIER": 2.5
        }
    },
    "balanced": {
        "label": "Balanced (Standard)",
        "description": "Standard Growth. Moderate reactivity.",
        "params": {
            "BID_UP_THROTTLE": 0.50,
            "BID_DOWN_THROTTLE": 0.50,
            "HARVEST_ROAS_MULT": 0.85,
            "SOFT_NEGATIVE_MULT": 1.5,
            "HARD_STOP_MULTIPLIER": 3.0
        }
    },
    "conservative": {
        "label": "Conservative (Stable)",
        "description": "Stable. Low reactivity. Protect profit.",
        "params": {
            "BID_UP_THROTTLE": 0.30,
            "BID_DOWN_THROTTLE": 0.30,
            "HARVEST_ROAS_MULT": 0.95,
            "SOFT_NEGATIVE_MULT": 2.0,
            "HARD_STOP_MULTIPLIER": 4.0
        }
    }
}

DEFAULT_CONFIG = {
    # Harvest thresholds (Tier 2)
    "HARVEST_CLICKS": 10,
    "HARVEST_ORDERS": 3,           # Will be dynamic based on CVR
    # HARVEST_SALES removed - currency threshold doesn't work across geos
    "HARVEST_ROAS_MULT": 0.85,     # vs BUCKET median (85% = user custom defined)
    "MAX_BID_CHANGE": 0.25,        # Max 25% change per run
    "DEDUPE_SIMILARITY": 0.85,     # ExactMatcher threshold
    "TARGET_ROAS": 2.5,
    
    # Negative thresholds (now CVR-based, no currency dependency)
    "NEGATIVE_CLICKS_THRESHOLD": 10,  # Baseline for legacy compatibility
    # NEGATIVE_SPEND_THRESHOLD removed - currency threshold doesn't work across geos
    
    # Bid optimization
    "ALPHA_EXACT": 0.25,           # 25% step size for exact
    "ALPHA_BROAD": 0.20,           # 20% step size for broad
    "ALPHA": 0.20,
    "MAX_BID_CHANGE": 0.25,        # 25% safety cap
    "TARGET_ROAS": 2.50,
    
    # Throttle Defaults (Fallback if no profile selected)
    "BID_UP_THROTTLE": 0.50,
    "BID_DOWN_THROTTLE": 0.50,
    "SOFT_NEGATIVE_MULT": 1.5,
    "HARD_STOP_MULTIPLIER": 3.0,
    
    # Min clicks thresholds per bucket (user-configurable)
    "MIN_CLICKS_EXACT": 5,
    "MIN_CLICKS_PT": 5,
    "MIN_CLICKS_BROAD": 8,
    "MIN_CLICKS_AUTO": 8,
    
    # Harvest forecast
    "HARVEST_EFFICIENCY_MULTIPLIER": 1.30,  # 30% efficiency gain from exact match
    "HARVEST_LAUNCH_MULTIPLIER": 1.20,  # Bid multiplier for new harvest keywords (20% above current bid)
    
    # Bucket median sanity check
    "BUCKET_MEDIAN_FLOOR_MULTIPLIER": 0.5,  # Bucket median must be >= 50% of target ROAS
    
    # V2.1 Commerce Intelligence
    "halo_min_organic_units": 30,  # Minimum absolute organic units for HALO_ACTIVE flag

    # ── PPC Intelligence Cascade (Phase 4) ───────────────────────────────────
    # Master switch — set False to disable entire cascade (zero cascade flags fire)
    "cascade_enabled": True,

    # Campaign efficiency cascade
    "cascade_campaign_drag_ratio": 0.5,            # Below this ratio = potential drag
    "cascade_campaign_drag_min_orders": 20,         # Fewer than this → genuine drag (high vol = underoptimized)
    "cascade_campaign_amplifier_ratio": 1.2,        # Above this with volume = amplifier
    "cascade_campaign_amplifier_min_orders": 50,    # Min orders to trust amplifier signal

    # Target diagnostic cascade
    "cascade_zero_conv_min_spend": 30,              # Min spend to trust zero-conversion flag
    "cascade_zero_conv_min_clicks": 10,             # Min clicks to confirm zero-conversion

    # Cut quadrant cascade
    "cascade_cut_min_spend": 50,                    # Min spend to act on Cut classification
    "cascade_cut_min_clicks": 15,                   # Min clicks for Cut conviction

    # Account health cascade
    "cascade_account_declining_dampen": 0.8,        # Throttle multiplier when account is declining

    # ── Tier 1 Campaign-Level Recommendation Thresholds (Phase 4) ────────────
    # PAUSE thresholds
    "tier1_pause_max_efficiency": 0.4,              # Efficiency below this = pause candidate
    "tier1_pause_max_orders": 10,                   # Must have fewer than this to justify pause
    "tier1_pause_min_spend": 50,                    # Don't flag campaigns spending < $50
    "tier1_pause_min_weeks": 2,                     # Future — needs history (not yet enforced)

    # REDUCE_BUDGET thresholds
    "tier1_reduce_max_efficiency": 0.6,             # Below this = budget reduction candidate
    "tier1_reduce_max_pct_profitable": 0.3,         # < 30% of targets profitable → reduce

    # RESTRUCTURE thresholds
    "tier1_restructure_mixed_threshold": 0.4,       # 40%+ targets profitable but...
    "tier1_restructure_zero_conv_pct": 0.3,         # ...30%+ zero-conv = mixed bag → restructure

    # SCALE thresholds
    "tier1_scale_min_efficiency": 1.3,              # Above this = scale candidate
    "tier1_scale_min_orders": 30,                   # Need volume to trust scale signal
    "tier1_scale_min_roas_vs_target": 1.2,          # ROAS must be 20%+ above target

    # INCREASE_BUDGET thresholds
    "tier1_increase_min_efficiency": 1.0,           # Above this with orders = increase candidate
    "tier1_increase_min_orders": 20,                # Minimum orders for increase

    # Tier 1 master switch
    "tier1_enabled": True,
}

# Elasticity scenarios for simulation
ELASTICITY_SCENARIOS = {
    'conservative': {
        'cpc': 0.3,
        'clicks': 0.5,
        'cvr': 0.0,
        'probability': 0.15
    },
    'expected': {
        'cpc': 0.5,
        'clicks': 0.85,
        'cvr': 0.1,
        'probability': 0.70
    },
    'aggressive': {
        'cpc': 0.6,
        'clicks': 0.95,
        'cvr': 0.15,
        'probability': 0.15
    }
}


# ==========================================
# DATA PREPARATION
# ==========================================

@st.cache_data(show_spinner=False)
def prepare_data(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Validate and prepare data for optimization.
    Returns prepared DataFrame and date_info dict.
    """
    df = df.copy()
    # Ensure numeric columns (using shared utility)
    df = ensure_numeric_columns(df, inplace=True)

    # CPC calculation (will be replaced by calculate_ppc_metrics later)
    df["CPC"] = np.where(df["Clicks"] > 0, df["Spend"] / df["Clicks"], 0)
    
    # Standardize column names
    col_map = {
        "Campaign": "Campaign Name",
        "AdGroup": "Ad Group Name", 
        "Term": "Customer Search Term",
        "Match": "Match Type"
    }
    for old, new in col_map.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]
    
    # Ensure Match Type exists
    if "Match Type" not in df.columns:
        df["Match Type"] = "broad"
    df["Match Type"] = df["Match Type"].fillna("broad").astype(str)
    
    # Targeting column normalization
    if "Targeting" not in df.columns:
        if "Keyword" in df.columns:
            df["Targeting"] = df["Keyword"].replace("", np.nan)
        else:
            df["Targeting"] = pd.Series([np.nan] * len(df))
    else:
        # If Targeting exists but has empty strings, ensure they are NaN for filling later
        df["Targeting"] = df["Targeting"].replace("", np.nan)
    
    if "TargetingExpression" in df.columns:
        # Prefer Expression over generic Targeting which might be "*"
        df["Targeting"] = df["TargetingExpression"].fillna(df["Targeting"])
    
    # CRITICAL FIX: Only fallback to Search Term for EXACT match types
    # For Auto/Broad/Phrase, we MUST NOT use Search Term as it breaks aggregation
    df["Targeting"] = df["Targeting"].fillna("")
    
    # 1. For Exact matches, missing Targeting can be filled with Search Term
    exact_mask = df["Match Type"].str.lower() == "exact"
    missing_targeting = (df["Targeting"] == "") | (df["Targeting"] == "*")
    df.loc[exact_mask & missing_targeting, "Targeting"] = df.loc[exact_mask & missing_targeting, "Customer Search Term"]
    
    # 2. For Auto/Broad/Phrase, if Targeting is missing, use Match Type as fallback grouping key
    # This prevents "fighter jet toy" appearing in Targeting for an auto campaign
    # But checking for '*' is important too as that is generic
    generic_targeting = (df["Targeting"] == "") | (df["Targeting"] == "*")
    df.loc[~exact_mask & generic_targeting, "Targeting"] = df.loc[~exact_mask & generic_targeting, "Match Type"]
    
    df["Targeting"] = df["Targeting"].astype(str)

    # 3. Normalize Auto targeting types for consistent grouping
    # e.g., "Close-Match" -> "close-match", "Close Match" -> "close-match"
    # Using shared normalize_auto_targeting from features.constants
    df["Targeting"] = df["Targeting"].apply(normalize_auto_targeting)
    
    # Sales/Orders attributed columns
    df["Sales_Attributed"] = df["Sales"]
    df["Orders_Attributed"] = df["Orders"]

    # Derived metrics (using shared utility)
    # optimizer.py uses decimal format: 0.05 = 5%
    df = calculate_ppc_metrics(df, percentage_format='decimal', inplace=True)
    
    # Campaign-level metrics
    camp_stats = df.groupby("Campaign Name")[["Sales", "Spend"]].transform("sum")
    df["Campaign_ROAS"] = np.where(
        camp_stats["Spend"] > 0, 
        camp_stats["Sales"] / camp_stats["Spend"], 
        config["TARGET_ROAS"]
    )
    
    # Detect date range
    date_info = detect_date_range(df)
    
    return df, date_info


def detect_date_range(df: pd.DataFrame) -> dict:
    """Detect date range from data for weekly normalization."""
    # Added 'start_date' for DB loaded frames
    date_cols = ["Date", "Start Date", "date", "Report Date", "start_date"]
    date_col = None
    
    for col in date_cols:
        if col in df.columns:
            date_col = col
            break
    
    if date_col is None:
        return {"weeks": 1.0, "label": "Period Unknown", "days": 7, "start_date": None, "end_date": None}
    
    try:
        dates = pd.to_datetime(df[date_col], errors='coerce').dropna()
        if dates.empty:
            return {"weeks": 1.0, "label": "Period Unknown", "days": 7, "start_date": None, "end_date": None}
        
        min_date = dates.min()
        max_date = dates.max()
        days = (max_date - min_date).days + 1
        weeks = max(days / 7, 1.0)
        
        label = f"{days} days ({min_date.strftime('%b %d')} - {max_date.strftime('%b %d')})"
        
        return {
            "weeks": weeks, 
            "label": label, 
            "days": days,
            "start_date": min_date.date().isoformat(),  # ISO format string
            "end_date": max_date.date().isoformat()
        }
    except:
        return {"weeks": 1.0, "label": "Period Unknown", "days": 7, "start_date": None, "end_date": None}


@st.cache_data(show_spinner=False)
def calculate_account_benchmarks(df: pd.DataFrame, config: dict) -> dict:
    """
    Calculate account-level CVR benchmarks for dynamic thresholds.
    
    Returns dict with:
        - account_cvr: Clamped account-wide conversion rate
        - expected_clicks: Expected clicks needed for first conversion
        - soft_threshold: Clicks threshold for soft negative
        - hard_stop_threshold: Clicks threshold for hard stop
        - harvest_min_orders: Dynamic min orders for harvest based on CVR
    """
    # Calculate account-level CVR
    total_clicks = df['Clicks'].sum()
    total_orders = df['Orders'].sum()
    
    raw_cvr = total_orders / total_clicks if total_clicks > 0 else 0.03
    
    # Apply safety clamps (1% - 20%)
    account_cvr = np.clip(raw_cvr, CVR_CONFIG["CVR_FLOOR"], CVR_CONFIG["CVR_CEILING"])
    
    # Calculate thresholds
    expected_clicks = 1 / account_cvr
    soft_mult = config.get("SOFT_NEGATIVE_MULT", 1.5)
    hard_mult = config.get("HARD_STOP_MULTIPLIER", 3.0)
    
    soft_threshold = max(CVR_CONFIG["SOFT_NEGATIVE_FLOOR"], expected_clicks * soft_mult)
    hard_stop_threshold = max(CVR_CONFIG["HARD_STOP_FLOOR"], expected_clicks * hard_mult)
    
    # Dynamic harvest min orders: Based on harvest_clicks × account_cvr
    # Floor at 3 orders minimum
    harvest_clicks = config.get("HARVEST_CLICKS", 10)
    harvest_min_orders = max(3, int(harvest_clicks * account_cvr))
    
    # Calculate universal (account-wide) ROAS using spend-weighted average (Total Sales / Total Spend)
    # This gives realistic baseline that matches actual account performance
    valid_rows = df[df["Spend"] > 0].copy()
    total_spend = valid_rows["Spend"].sum()
    total_sales = valid_rows["Sales"].sum()
    
    if total_spend >= 100:  # Need meaningful spend for reliable ROAS
        universal_median_roas = total_sales / total_spend
    else:
        universal_median_roas = config.get("TARGET_ROAS", 2.5)

    print(f"\n=== ACCOUNT BENCHMARKS (CVR-Based) ===")
    print(f"Account CVR: {account_cvr:.1%} (raw: {raw_cvr:.1%})")
    print(f"Expected clicks to convert: {expected_clicks:.1f}")
    print(f"Soft negative threshold: {soft_threshold:.0f} clicks")
    print(f"Hard stop threshold: {hard_stop_threshold:.0f} clicks")
    print(f"Harvest min orders (dynamic): {harvest_min_orders}")
    print(f"Universal Median ROAS: {universal_median_roas:.2f}x (n={len(valid_rows)})")
    print(f"=== END BENCHMARKS ===\n")
    
    return {
        'account_cvr': account_cvr,
        'raw_cvr': raw_cvr,
        'expected_clicks': expected_clicks,
        'soft_threshold': soft_threshold,
        'hard_stop_threshold': hard_stop_threshold,
        'harvest_min_orders': harvest_min_orders,
        'universal_median_roas': universal_median_roas,
        'was_clamped': raw_cvr != account_cvr
    }

def calculate_account_health(df: pd.DataFrame) -> dict:
    """Calculate account health diagnostics for dashboard display (Last 30 Days from DB)."""
    
    # Get data from database for accurate last 30 days (not just uploaded CSV)
    try:
        db = get_db_manager(st.session_state.get('test_mode', False))
        client_id = st.session_state.get('active_account_id')
        
        if not db or not client_id:
            # Fallback to uploaded data if DB not available
            df_filtered = df.copy()
        else:
            # Pull from database to get full historical context
            df_db = db.get_target_stats_by_account(client_id, limit=50000)
            
            if df_db is None or df_db.empty:
                # No DB data, use uploaded CSV
                df_filtered = df.copy()
            else:
                # Use database data for last 30 days
                df_db['start_date'] = pd.to_datetime(df_db['start_date'], errors='coerce')
                valid_dates = df_db['start_date'].dropna()
                
                if not valid_dates.empty:
                    # CRITICAL FIX: Use actual latest date from raw_search_term_data
                    # target_stats.start_date shows Jan 12 but actual data ends Jan 17
                    max_date = valid_dates.max()
                    if hasattr(db, 'get_latest_raw_data_date'):
                        actual_latest = db.get_latest_raw_data_date(client_id)
                        if actual_latest:
                            max_date = pd.Timestamp(actual_latest)
                    
                    cutoff_date = max_date - timedelta(days=30)
                    df_filtered = df_db[df_db['start_date'] >= cutoff_date].copy()
                    
                    # Map DB columns to expected optimizer columns
                    df_filtered = df_filtered.rename(columns={
                        'spend': 'Spend',
                        'sales': 'Sales',
                        'orders': 'Orders',
                        'clicks': 'Clicks'
                    })
                else:
                    df_filtered = df.copy()
    except Exception as e:
        # On any error, fall back to uploaded data
        print(f"Health calc DB error: {e}")
        df_filtered = df.copy()
    
    # Ensure we have required columns
    if 'Spend' not in df_filtered.columns or 'Sales' not in df_filtered.columns:
        # Return empty health if data is invalid
        return {
            "health_score": 0,
            "roas_score": 0,
            "efficiency_score": 0,
            "cvr_score": 0,
            "efficiency_rate": 0,
            "waste_ratio": 100,
            "wasted_spend": 0,
            "current_roas": 0,
            "current_acos": 0,
            "cvr": 0,
            "total_spend": 0,
            "total_sales": 0
        }
    
    # Calculate metrics
    total_spend = df_filtered['Spend'].sum()
    total_sales = df_filtered['Sales'].sum()
    total_orders = df_filtered.get('Orders', pd.Series([0])).sum()
    total_clicks = df_filtered.get('Clicks', pd.Series([0])).sum()
    
    current_roas = total_sales / total_spend if total_spend > 0 else 0
    current_acos = (total_spend / total_sales * 100) if total_sales > 0 else 0
    
    # Efficiency calculation - ROW LEVEL, not aggregated
    # Each row is Campaign->AdGroup->Target->Date, check conversion at that granularity
    converting_spend = df_filtered.loc[df_filtered.get('Orders', 0) > 0, 'Spend'].sum()
    
    efficiency_rate = (converting_spend / total_spend * 100) if total_spend > 0 else 0
    wasted_spend = total_spend - converting_spend
    waste_ratio = 100 - efficiency_rate
    
    cvr = (total_orders / total_clicks * 100) if total_clicks > 0 else 0
    
    roas_score = min(100, current_roas / 4.0 * 100)
    efficiency_score = efficiency_rate
    cvr_score = min(100, cvr / 10.0 * 100)
    health_score = (roas_score * 0.4 + efficiency_score * 0.4 + cvr_score * 0.2)
    
    health_metrics = {
        "health_score": health_score,
        "roas_score": roas_score,
        "efficiency_score": efficiency_score,
        "cvr_score": cvr_score,
        "efficiency_rate": efficiency_rate,
        "waste_ratio": waste_ratio,
        "wasted_spend": wasted_spend,
        "current_roas": current_roas,
        "current_acos": current_acos,
        "cvr": cvr,
        "total_spend": total_spend,
        "total_sales": total_sales
    }
    
    # Persist to database for Home tab cockpit
    try:
        if db and client_id:
            db.save_account_health(client_id, health_metrics)
    except Exception:
        pass  # Don't break optimizer if DB save fails
    
    return health_metrics
