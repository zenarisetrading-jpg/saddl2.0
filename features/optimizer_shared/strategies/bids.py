"""
Optimizer Bid Strategy
Logic for calculating optimal bid adjustments using bucketed performance analysis.
"""

import pandas as pd
import numpy as np
import streamlit as st
from typing import Tuple, Dict, Any, Optional, Set
from features.optimizer_shared.core import BID_LIMITS, calculate_account_benchmarks
from features.optimizer_shared.strategies.negatives import enrich_with_ids
from features.optimizer_shared.intelligence import build_commerce_lookup, compute_intelligence_flags
from app_core.data_hub import DataHub
from app_core.data_loader import is_asin
from dev_resources.tests.bulk_validation_spec import (
    OptimizationRecommendation,
    RecommendationType,
    validate_recommendation
)

# ==========================================
# CONFIGURATION CONSTANTS (BID OPTIMIZER V2)
# ==========================================

# CHANGE 1: 14-DAY COOLDOWN
COOLDOWN_DAYS = 17

# CHANGE 4: MINIMUM CLICK GATE ON PROMOTE ACTIONS
MIN_CLICKS_FOR_PROMOTE = 10
MIN_CLICKS_FOR_DECREASE = 5

# CHANGE 3: VISIBILITY BOOST CONVERSION GATE
VISIBILITY_BOOST_MIN_DAYS = 14
VISIBILITY_BOOST_MAX_IMPRESSIONS = 100
VISIBILITY_BOOST_PCT = 0.30
VISIBILITY_BOOST_ELIGIBLE_TYPES = {"exact", "phrase", "broad", "close-match"}

# CHANGE 5: ROAS TARGET BY MATCH TYPE BUCKET
BUCKET_TARGET_MULTIPLIERS = {
    "Exact": 1.00,
    "Product Targeting": 0.80,
    "Broad/Phrase": 0.85,
    "Auto": 0.65,
    "Category": 0.65,
    "Auto/Category": 0.65
}

def calculate_bid_optimizations(
    df: pd.DataFrame, 
    config: dict, 
    harvested_terms: Set[str] = None,
    negative_terms: Set[Tuple[str, str, str]] = None,
    universal_median_roas: float = None,
    data_days: int = 7,  # Number of days in dataset for visibility boost detection
    client_id: str = None # Included for DB queries
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Calculate optimal bid adjustments using vNext Bucketed Logic.
    
    Returns 4 DataFrames for 4 tabs:
    1. Exact Keywords (Match Type = exact, manual keywords only)
    2. Product Targeting (PT) - asin= or asin-expanded= syntax
    3. Aggregated Keywords (Broad/Phrase)
    4. Auto/Category (close-match, loose-match, substitutes, complements, category=)
    
    MANDATORY: Bleeders (Sales=0 with Clicks >= threshold) are EXCLUDED.
    """
    harvested_terms = harvested_terms or set()
    negative_terms = negative_terms or set()
    
    # ---------------------------------------------------------
    # CHANGE 1 (Prep) & CHANGE 2 (Prep): Fetch Database Context
    # ---------------------------------------------------------
    recent_actions = pd.DataFrame()
    roas_14d_df = pd.DataFrame()
    commerce_df = pd.DataFrame()
    commerce_lookup = {}
    st.session_state["v21_commerce_fetch_ok"] = False
    st.session_state["v21_commerce_rows"] = 0
    st.session_state["v21_spapi_missing"] = False
    
    if client_id:
        try:
            from app_core.db_manager import get_db_manager
            import psycopg2
            
            db = get_db_manager(st.session_state.get('test_mode', False))
            if db:
                try:
                    recent_actions = db.get_recent_action_dates(client_id)
                except (Exception, psycopg2.Error) as e:
                    print(f"Error loading recent actions: {e}")
                    
                try:
                    roas_14d_df = db.get_target_14d_roas(client_id)
                    print(f"Loaded {len(roas_14d_df)} 14-day ROAS records from DB.")
                except (Exception, psycopg2.Error) as e:
                    print(f"Error loading 14d ROAS: {e}")
                
                try:
                    spapi_connected = bool(
                        db.has_active_spapi_integration(client_id)
                    ) if hasattr(db, "has_active_spapi_integration") else False

                    if not spapi_connected:
                        st.session_state["v21_commerce_fetch_ok"] = False
                        st.session_state["v21_spapi_missing"] = True
                        st.session_state["v21_commerce_rows"] = 0
                        print(f"V2.1 Intelligence: SP-API not connected for {client_id}; running STR-only optimization.")
                    else:
                        commerce_df = db.get_commerce_metrics_by_target(client_id)
                        st.session_state["v21_commerce_rows"] = int(len(commerce_df))

                        if not commerce_df.empty:
                            commerce_lookup = build_commerce_lookup(commerce_df)
                            st.session_state["v21_commerce_fetch_ok"] = True
                            st.session_state["v21_spapi_missing"] = False
                            print(f"V2.1 Intelligence: Loaded {len(commerce_df)} commerce metrics rows. Mapped to {len(commerce_lookup)} entities.")
                        else:
                            st.session_state["v21_commerce_fetch_ok"] = False
                            st.session_state["v21_spapi_missing"] = True
                except (psycopg2.errors.UndefinedTable, psycopg2.ProgrammingError) as e:
                    print(f"SP-API Data Unavailable (Undefined Table): {e}")
                    st.session_state["v21_commerce_fetch_ok"] = False
                    st.session_state["v21_spapi_missing"] = True
                except Exception as e:
                    print(f"Error loading commerce metrics: {e}")
                    st.session_state["v21_commerce_fetch_ok"] = False
                    st.session_state["v21_spapi_missing"] = True

        except Exception as e:
            print(f"Database connection error in optimizer: {e}")
    
    # Create lookup dictionaries for extremely fast checking per row
    # Key Format: (Campaign Name, Ad Group Name, Targeting) lowercased string
    cooldown_lookup = {}
    if not recent_actions.empty:
        for _, row in recent_actions.iterrows():
            k = f"{str(row['Campaign Name']).lower()}|{str(row['Ad Group Name']).lower()}|{str(row['Targeting']).lower()}"
            cooldown_lookup[k] = row['last_action_date']
            
    roas_14d_lookup = {}
    if not roas_14d_df.empty:
        for _, row in roas_14d_df.iterrows():
            k = f"{str(row['Campaign Name']).lower()}|{str(row['Ad Group Name']).lower()}|{str(row['Targeting']).lower()}"
            roas_14d_lookup[k] = row['14d_avg_ROAS']
    
    # 1. Global Exclusions
    def is_excluded(row):
        # Get both Customer Search Term AND Targeting values
        cst = str(row.get("Customer Search Term", "")).strip().lower()
        targeting = str(row.get("Targeting", "")).strip().lower()
        
        # Check Harvest - if EITHER column matches harvested terms, exclude
        if cst in harvested_terms or targeting in harvested_terms:
            return True
            
        # Check Negatives (Campaign, AdGroup, Term)
        camp = str(row.get("Campaign Name", "")).strip()
        ag = str(row.get("Ad Group Name", "")).strip()
        
        # Check against both CST and Targeting
        neg_key_cst = (camp, ag, cst)
        neg_key_targeting = (camp, ag, targeting)
        if neg_key_cst in negative_terms or neg_key_targeting in negative_terms:
            return True
            
        return False
        
    # Apply Exclusion Filter
    mask_excluded = df.apply(is_excluded, axis=1)
    df_clean = df[~mask_excluded].copy()
    
    if df_clean.empty:
        empty = pd.DataFrame(columns=["Campaign Name", "Ad Group Name", "Targeting", "Match Type", "Current Bid", "New Bid"])
        return empty.copy(), empty.copy(), empty.copy(), empty.copy()
    
    
    # Calculate universal median if not provided (outlier-resistant)
    if universal_median_roas is None:
        valid_rows = df_clean[(df_clean["Spend"] > 0) & (df_clean["Sales"] > 0)].copy()
        
        if len(valid_rows) >= 10:
            # Filter to rows with meaningful spend (>= $5) to avoid low-spend outliers
            substantial_rows = valid_rows[valid_rows["Spend"] >= 5.0]
            
            if len(substantial_rows) >= 10:
                # Use winsorized median (cap at 99th percentile to remove extreme outliers)
                roas_values = substantial_rows["ROAS"].values
                cap_value = np.percentile(roas_values, 99)
                winsorized_roas = np.clip(roas_values, 0, cap_value)
                universal_median_roas = np.median(winsorized_roas)
                
                print(f"\\n=== UNIVERSAL MEDIAN CALCULATION ===")
                print(f"Total valid rows: {len(valid_rows)}")
                print(f"Substantial spend rows (>=$5): {len(substantial_rows)}")
                print(f"Raw median: {valid_rows['ROAS'].median():.2f}x")
                print(f"99th percentile cap: {cap_value:.2f}x")
                print(f"Winsorized median: {universal_median_roas:.2f}x")
                print(f"=== END UNIVERSAL MEDIAN ===\\n")
            else:
                # Not enough substantial data, fall back to all rows
                universal_median_roas = valid_rows["ROAS"].median()
                print(f"⚠️ Using all rows median: {universal_median_roas:.2f}x (only {len(substantial_rows)} rows with spend >=$5)")
        else:
            universal_median_roas = config.get("TARGET_ROAS", 2.5)
            print(f"⚠️ Insufficient data, using TARGET_ROAS: {universal_median_roas:.2f}x")
    
    # 2. Define bucket detection helpers
    AUTO_TYPES = {'close-match', 'loose-match', 'substitutes', 'complements', 'auto'}
    
    def is_auto_or_category(targeting_val):
        t = str(targeting_val).lower().strip()
        if t.startswith("category=") or "category" in t:
            return True
        if t in AUTO_TYPES:
            return True
        return False
    
    def is_pt_targeting(targeting_val):
        t = str(targeting_val).lower().strip()
        if "asin=" in t or "asin-expanded=" in t:
            return True
        if is_asin(t) and not t.startswith("category"):
            return True
        return False
    
    def is_category_targeting(targeting_val):
        t = str(targeting_val).lower().strip()
        return t.startswith("category=") or (t.startswith("category") and "=" in t)
    
    # 3. Build mutually exclusive bucket masks
    # CRITICAL: Auto bucket should ONLY include genuine auto targeting types (close-match, loose-match, etc.)
    # NOT asin-expanded or category targets, even if match_type is "auto" or "-"
    
    # First identify PT and Category targets (takes precedence)
    mask_pt_targeting = df_clean["Targeting"].apply(is_pt_targeting)
    mask_category_targeting = df_clean["Targeting"].apply(is_category_targeting)
    
    # Auto bucket: targeting type is in AUTO_TYPES AND NOT a PT/Category target
    mask_auto_by_targeting = df_clean["Targeting"].apply(lambda x: str(x).lower().strip() in AUTO_TYPES)
    mask_auto_by_matchtype = df_clean["Match Type"].str.lower().isin(["auto", "-"])
    mask_auto = (mask_auto_by_targeting | mask_auto_by_matchtype) & (~mask_pt_targeting) & (~mask_category_targeting)
    
    # PT bucket: PT targeting AND not auto
    mask_pt = mask_pt_targeting & (~mask_auto)
    
    # Category bucket: Category targeting AND not auto/PT
    mask_category = mask_category_targeting & (~mask_auto) & (~mask_pt)
    
    # Exact bucket: Match Type is exact AND not PT/Category/Auto
    mask_exact = (
        (df_clean["Match Type"].str.lower() == "exact") & 
        (~mask_pt) & 
        (~mask_category) &
        (~mask_auto)
    )
    
    # Broad/Phrase bucket: Match Type is broad/phrase AND not PT/Category/Auto
    mask_broad_phrase = (
        df_clean["Match Type"].str.lower().isin(["broad", "phrase"]) & 
        (~mask_pt) & 
        (~mask_category) &
        (~mask_auto)
    )
    
    # 4. Process each bucket
    bids_exact = _process_bucket(df_clean[mask_exact], config, 
                                  bucket_name="Exact",
                                  universal_median_roas=universal_median_roas,
                                  data_days=data_days,
                                  cooldown_lookup=cooldown_lookup,
                                  roas_14d_lookup=roas_14d_lookup,
                                  commerce_lookup=commerce_lookup)
    
    bids_pt = _process_bucket(df_clean[mask_pt], config, 
                               bucket_name="Product Targeting",
                               universal_median_roas=universal_median_roas,
                               data_days=data_days,
                               cooldown_lookup=cooldown_lookup,
                               roas_14d_lookup=roas_14d_lookup,
                               commerce_lookup=commerce_lookup)
    
    bids_agg = _process_bucket(df_clean[mask_broad_phrase], config, 
                                bucket_name="Broad/Phrase",
                                universal_median_roas=universal_median_roas,
                                data_days=data_days,
                                cooldown_lookup=cooldown_lookup,
                                roas_14d_lookup=roas_14d_lookup,
                                commerce_lookup=commerce_lookup)
    
    bids_auto = _process_bucket(df_clean[mask_auto], config, 
                                 bucket_name="Auto",
                                 universal_median_roas=universal_median_roas,
                                 data_days=data_days,
                                 cooldown_lookup=cooldown_lookup,
                                 roas_14d_lookup=roas_14d_lookup,
                                 commerce_lookup=commerce_lookup)
    
    bids_category = _process_bucket(df_clean[mask_category], config, 
                                     bucket_name="Category",
                                     universal_median_roas=universal_median_roas,
                                     data_days=data_days,
                                     cooldown_lookup=cooldown_lookup,
                                     roas_14d_lookup=roas_14d_lookup,
                                     commerce_lookup=commerce_lookup)
    
    # Combine auto and category for backwards compatibility (displayed as "Auto/Category")
    bids_auto_combined = pd.concat([bids_auto, bids_category], ignore_index=True) if not bids_category.empty else bids_auto
    
    # Clear previous consolidation negatives
    if 'consolidation_negatives' in st.session_state:
        st.session_state["consolidation_negatives"] = []
    
    # Apply deduplication to exact and PT buckets (most common for duplicates)
    bids_exact = deduplicate_bucket(bids_exact, "Exact")
    bids_pt = deduplicate_bucket(bids_pt, "PT")
    
    # FINAL ENRICHMENT: Ensure IDs are present for Bulk Export
    bulk = DataHub().get_data('bulk_id_mapping')
    
    bids_exact = enrich_with_ids(bids_exact, bulk)
    bids_pt = enrich_with_ids(bids_pt, bulk)
    bids_agg = enrich_with_ids(bids_agg, bulk)
    bids_auto_combined = enrich_with_ids(bids_auto_combined, bulk)

    return bids_exact, bids_pt, bids_agg, bids_auto_combined


def _process_bucket(segment_df: pd.DataFrame, config: dict, bucket_name: str, universal_median_roas: float, 
                    data_days: int = 7, cooldown_lookup: dict = None, roas_14d_lookup: dict = None,
                    commerce_lookup: dict = None) -> pd.DataFrame:
    """Unified bucket processor with Bucket Median ROAS classification."""
    if segment_df.empty:
        return pd.DataFrame()
    
    segment_df = segment_df.copy()
    segment_df["_targeting_norm"] = segment_df["Targeting"].astype(str).str.strip().str.lower()
    
    has_keyword_id = "KeywordId" in segment_df.columns and segment_df["KeywordId"].notna().any()
    has_targeting_id = "TargetingId" in segment_df.columns and segment_df["TargetingId"].notna().any()
    
    # CRITICAL FIX: For Auto/Category campaigns, group by Targeting TYPE (from Targeting column)
    # NOT by TargetingId, which contains individual ASIN IDs that can't be bid-adjusted
    is_auto_bucket = bucket_name in ["Auto/Category", "Auto", "Category"]
    
    if is_auto_bucket:
        # For auto campaigns: Use the Targeting column value (close-match, loose-match, substitutes, complements)
        # This preserves targeting type while avoiding individual ASIN grouping
        segment_df["_group_key"] = segment_df["_targeting_norm"]
    elif has_keyword_id or has_targeting_id:
        # For keywords/PT: use IDs for grouping
        segment_df["_group_key"] = segment_df.apply(
            lambda r: str(r.get("KeywordId") or r.get("TargetingId") or r["_targeting_norm"]).strip(),
            axis=1
        )
    else:
        # Fallback: use normalized targeting text
        segment_df["_group_key"] = segment_df["_targeting_norm"]
    
    agg_cols = {"Clicks": "sum", "Spend": "sum", "Sales": "sum", "Impressions": "sum", "Orders": "sum"}
    meta_cols = {c: "first" for c in [
        "Campaign Name", "Ad Group Name", "CampaignId", "AdGroupId", 
        "KeywordId", "TargetingId", "Match Type", "Targeting", "Campaign Targeting Type"
    ] if c in segment_df.columns}
    
    if "Current Bid" in segment_df.columns:
        agg_cols["Current Bid"] = "max"
    if "CPC" in segment_df.columns:
        agg_cols["CPC"] = "mean"
    # NEW: Include bid columns from bulk file if available
    if "Ad Group Default Bid" in segment_df.columns:
        agg_cols["Ad Group Default Bid"] = "first"
    if "Bid" in segment_df.columns:
        agg_cols["Bid"] = "first"
        
    grouped = segment_df.groupby(["Campaign Name", "Ad Group Name", "_group_key"], as_index=False).agg({**agg_cols, **meta_cols})
    grouped = grouped.drop(columns=["_group_key"], errors="ignore")
    grouped["ROAS"] = np.where(grouped["Spend"] > 0, grouped["Sales"] / grouped["Spend"], 0)
    
    # Calculate bucket ROAS using spend-weighted average (Total Sales / Total Spend)
    bucket_with_spend = grouped[grouped["Spend"] > 0]
    bucket_sample_size = len(bucket_with_spend)
    total_spend = bucket_with_spend["Spend"].sum()
    total_sales = bucket_with_spend["Sales"].sum()
    bucket_weighted_roas = total_sales / total_spend if total_spend > 0 else 0
    
    # Stat sig check
    MIN_SAMPLE_SIZE_FOR_STAT_SIG = 20
    MIN_SPEND_FOR_STAT_SIG = 100  # Need at least AED 100 spend for reliable bucket ROAS
    OUTLIER_THRESHOLD_MULTIPLIER = 1.5
    
    if bucket_sample_size < MIN_SAMPLE_SIZE_FOR_STAT_SIG or total_spend < MIN_SPEND_FOR_STAT_SIG:
        baseline_roas = universal_median_roas
        baseline_source = f"Universal Weighted ROAS (insufficient bucket data: {bucket_sample_size} rows, {total_spend:.0f} spend)"
    else:
        if bucket_weighted_roas > universal_median_roas * OUTLIER_THRESHOLD_MULTIPLIER:
            baseline_roas = universal_median_roas
            baseline_source = f"Universal Weighted ROAS (bucket {bucket_weighted_roas:.2f}x is outlier)"
        else:
            baseline_roas = bucket_weighted_roas
            baseline_source = f"Bucket Weighted ROAS (n={bucket_sample_size}, spend={total_spend:.0f})"
    
    # Sanity check floor
    target_roas = config.get("TARGET_ROAS", 2.5)
    min_acceptable_roas = target_roas * config.get("BUCKET_MEDIAN_FLOOR_MULTIPLIER", 0.5)
    
    if baseline_roas < min_acceptable_roas:
        baseline_roas = min_acceptable_roas
        baseline_source += " [FLOORED]"
    
    print(f"[{bucket_name}] Baseline: {baseline_roas:.2f}x ({baseline_source})")
    
    adgroup_stats = grouped.groupby(["Campaign Name", "Ad Group Name"]).agg({
        "Clicks": "sum", "Spend": "sum", "Sales": "sum", "Orders": "sum"
    }).reset_index()
    adgroup_stats["AG_ROAS"] = np.where(adgroup_stats["Spend"] > 0, adgroup_stats["Sales"] / adgroup_stats["Spend"], 0)
    adgroup_stats["AG_Clicks"] = adgroup_stats["Clicks"]
    adgroup_lookup = adgroup_stats.set_index(["Campaign Name", "Ad Group Name"])[["AG_ROAS", "AG_Clicks"]].to_dict('index')
    
    # Change 5: Fetch bucket-specific multiplier to apply later
    bucket_multiplier = BUCKET_TARGET_MULTIPLIERS.get(bucket_name, 1.0)
    if bucket_name == "Product Targeting":
        bucket_multiplier = BUCKET_TARGET_MULTIPLIERS.get("Product Targeting", 0.80)
    elif bucket_name == "Broad/Phrase":
        bucket_multiplier = BUCKET_TARGET_MULTIPLIERS.get("Broad/Phrase", 0.85)

    alpha = config.get("ALPHA", config.get("ALPHA_EXACT", 0.20))
    if "Broad" in bucket_name or "Auto" in bucket_name:
        alpha = config.get("ALPHA_BROAD", alpha * 0.8)

    def apply_optimization(r):
        clicks = r["Clicks"]
        orders = r.get("Orders", 0)
        cvr = (orders / clicks) if clicks > 0 else 0
        impressions = r.get("Impressions", 0)
        targeting = str(r.get("Targeting", "")).strip().lower()
        match_type = str(r.get("Match Type", "")).strip().lower()
        
        # Determine unique key for target
        k = f"{str(r['Campaign Name']).lower()}|{str(r.get('Ad Group Name', '')).lower()}|{targeting}"
        
        # ---------------------------------------------------------
        # CHANGE 1: 14-DAY COOLDOWN
        # ---------------------------------------------------------
        if cooldown_lookup and k in cooldown_lookup:
            last_action_date = pd.to_datetime(cooldown_lookup[k]).tz_localize(None)
            now = pd.Timestamp.now().tz_localize(None)
            # Need to get latest target_stats data date from DB to accurately assess maturity, using 'now' as fallback.
            # (last_action_date + 17 days) <= latest_data_date
            maturity_date = last_action_date + pd.Timedelta(days=COOLDOWN_DAYS)
            if maturity_date > now:
                return 0.0, f"Cooldown: Last action on {last_action_date.strftime('%Y-%m-%d')}, matures on {maturity_date.strftime('%Y-%m-%d')}", "Cooldown (Immature)", []

        # Priority: Bid (from bulk) → Ad Group Default Bid (from bulk) → CPC (from STR)
        base_bid = float(
            r.get("Bid") if pd.notna(r.get("Bid")) and r.get("Bid") > 0 else
            r.get("Ad Group Default Bid") if pd.notna(r.get("Ad Group Default Bid")) and r.get("Ad Group Default Bid") > 0 else
            r.get("Current Bid", 0) or r.get("CPC", 0) or 0
        )
        
        if base_bid <= 0:
            return 0.0, "Hold: No Bid/CPC Data", "Hold (No Data)", []
            
        # ---------------------------------------------------------
        # CHANGE 2: 14-DAY ROLLING AVERAGE ROAS
        # ---------------------------------------------------------
        # Use DB 14-day ROAS if available, else fallback to session state point-in-time ROAS
        if roas_14d_lookup and k in roas_14d_lookup:
            roas = float(roas_14d_lookup[k])
        else:
            roas = r["ROAS"]
        
        # ---------------------------------------------------------
        # CHANGE 3: VISIBILITY BOOST CONVERSION GATE
        # ---------------------------------------------------------
        is_eligible_for_boost = (
            match_type in VISIBILITY_BOOST_ELIGIBLE_TYPES or
            targeting in VISIBILITY_BOOST_ELIGIBLE_TYPES
        )
        
        if (is_eligible_for_boost and 
            data_days >= VISIBILITY_BOOST_MIN_DAYS and 
            impressions < VISIBILITY_BOOST_MAX_IMPRESSIONS):
            
            # Additional logic for Conversion Gate
            if orders > 0 or (clicks >= 5 and cvr > 0):
                new_bid = round(base_bid * (1 + VISIBILITY_BOOST_PCT), 2)
                return new_bid, f"Visibility Boost: Only {impressions} impressions in {data_days} days", "Visibility Boost (+30%)", []
            else:
                return 0.0, f"Visibility Boost Suppressed: No conversion signal after {data_days} days - flagged for review", "REVIEW_FLAG", []
        
        # ---------------------------------------------------------
        # CHANGE 5.5: V2.1 COMMERCE INTELLIGENCE
        # ---------------------------------------------------------
        intelligence_flags = []
        if commerce_lookup:
            intelligence_flags = compute_intelligence_flags(r, commerce_lookup, config)
            
        # Apply Intelligence Multipliers to ROAS threshold
        # If in launch or halo active, we tolerate a 20% lower ROAS target
        intel_bucket_multiplier = bucket_multiplier
        if "LAUNCH_PHASE" in intelligence_flags or "HALO_ACTIVE" in intelligence_flags:
            intel_bucket_multiplier *= 0.8
            
        # ---------------------------------------------------------
        # CHANGE 4: MINIMUM CLICK GATE ON PROMOTE ACTIONS
        # ---------------------------------------------------------
        # Only evaluate the action first using `_classify_and_bid` 
        # to determine if it's a promote or bid_down
        
        ag_key = (r["Campaign Name"], r.get("Ad Group Name", ""))
        ag_stats = adgroup_lookup.get(ag_key, {})
        
        # Primary test: Target level
        if clicks > 0 and roas > 0:
            new_bid, reason, action = _classify_and_bid(roas, baseline_roas, base_bid, alpha, f"targeting|{bucket_name}", config, intel_bucket_multiplier)
        # Fallback test: AdGroup level
        elif ag_stats.get("AG_Clicks", 0) > 0 and ag_stats.get("AG_ROAS", 0) > 0:
            new_bid, reason, action = _classify_and_bid(ag_stats["AG_ROAS"], baseline_roas, base_bid, alpha * 0.5, f"adgroup|{bucket_name}", config, intel_bucket_multiplier)
        else:
            return base_bid, f"Hold: Insufficient data ({clicks} clicks)", "Hold (Insufficient Data)", intelligence_flags
            
        # Now apply Asymmetric Click Gates
        if action == "promote":
            if clicks < MIN_CLICKS_FOR_PROMOTE:
                return base_bid, f"Bid increase blocked — insufficient data ({clicks} clicks, need {MIN_CLICKS_FOR_PROMOTE}).", "Hold (Insufficient Data For Promote)", intelligence_flags
        elif action == "bid_down":
            if clicks < MIN_CLICKS_FOR_DECREASE:
                return base_bid, f"Bid decrease blocked — insufficient data ({clicks} clicks, need {MIN_CLICKS_FOR_DECREASE}).", "Hold (Insufficient Data For Decrease)", intelligence_flags

        # ---------------------------------------------------------
        # V2.1 INTELLIGENCE ACTIONS OVERRIDE
        # ---------------------------------------------------------
        if action == "promote":
            if "INVENTORY_RISK" in intelligence_flags:
                return base_bid, "Bid increase blocked — critically low FBA stock remaining. Protecting spend until inventory is replenished.", "Hold (Intelligence: Inventory)", intelligence_flags
            
            if "CANNIBALIZE_RISK" in intelligence_flags and bucket_name == "Exact":
                # Dampen the increase by 50%
                bid_increase = new_bid - base_bid
                new_bid = round(base_bid + (bid_increase * 0.5), 2)
                reason += " Dampened 50% to prevent cannibalizing high organic conversion."
                
            if "HALO_ACTIVE" in intelligence_flags:
                reason = reason.rstrip(".") + " — organic dominates sales; target relaxed to protect total efficiency."
                
        elif action == "bid_down":
            if "BSR_DECLINING" in intelligence_flags:
                return base_bid, "Bid decrease blocked — protecting overall Best Seller Rank momentum.", "Hold (Intelligence: BSR)", intelligence_flags

        # ---------------------------------------------------------
        # PHASE 4: PPC INTELLIGENCE CASCADE FLAGS
        # Volume-weighted: ratio alone never sufficient. Must confirm
        # with order/spend/click volume before acting.
        # ---------------------------------------------------------
        if config.get("cascade_enabled", True):
            cascade_flags = []

            camp_eff_ratio  = r.get("campaign_efficiency_ratio")
            camp_orders     = int(r.get("campaign_total_orders") or 0)
            ppc_diagnostic  = r.get("ppc_diagnostic")
            ppc_quadrant    = r.get("ppc_quadrant")
            account_health  = r.get("account_health_signal")
            target_spend    = float(r.get("Spend", 0) or 0)
            target_clicks   = int(r.get("Clicks", 0) or 0)

            # ── Campaign Efficiency ────────────────────────────────────────
            if camp_eff_ratio is not None and action == "promote":
                drag_ratio      = config.get("cascade_campaign_drag_ratio", 0.5)
                drag_max_orders = config.get("cascade_campaign_drag_min_orders", 20)
                amp_ratio       = config.get("cascade_campaign_amplifier_ratio", 1.2)
                amp_min_orders  = config.get("cascade_campaign_amplifier_min_orders", 50)

                if camp_eff_ratio < drag_ratio:
                    if camp_orders < drag_max_orders:
                        # Low efficiency + low volume = confirmed drag
                        new_bid = round(base_bid + (new_bid - base_bid) * 0.5, 2)
                        reason = (
                            reason.rstrip(".")
                            + f" Bid increase dampened 50% — campaign efficiency "
                            f"{camp_eff_ratio:.2f}× with {camp_orders} orders."
                        )
                        cascade_flags.append("CAMPAIGN_DRAG")
                    else:
                        # Low efficiency + HIGH volume = underoptimized workhorse, not a drag
                        reason = (
                            reason.rstrip(".")
                            + f" [Campaign efficiency {camp_eff_ratio:.2f}× but "
                            f"{camp_orders} orders — underoptimized, not drag.]"
                        )
                        cascade_flags.append("CAMPAIGN_UNDEROPTIMIZED")

                elif camp_eff_ratio >= amp_ratio and camp_orders >= amp_min_orders:
                    # Amplifier: high efficiency + high volume = trusted signal
                    new_bid = round(base_bid + (new_bid - base_bid) * 1.15, 2)
                    reason = (
                        reason.rstrip(".")
                        + f" Throttle loosened 15% — campaign amplifier "
                        f"({camp_eff_ratio:.2f}×, {camp_orders} orders)."
                    )
                    cascade_flags.append("CAMPAIGN_AMPLIFIER")

            # ── Zero-Conversion Target ─────────────────────────────────────
            if ppc_diagnostic == "zero_conversion" and action == "promote":
                min_spend  = config.get("cascade_zero_conv_min_spend", 30)
                min_clicks = config.get("cascade_zero_conv_min_clicks", 10)

                if target_spend >= min_spend and target_clicks >= min_clicks:
                    # Confirmed bleeder — block promote
                    return base_bid, (
                        f"Bid increase blocked — ${target_spend:.0f} spend, "
                        f"{target_clicks} clicks, zero conversions."
                    ), "Hold (Intelligence: Zero-Conv)", intelligence_flags + cascade_flags + ["ZERO_CONV_BLOCK"]
                else:
                    # Thin data — informational only, do not block
                    reason = (
                        reason.rstrip(".")
                        + f" [Zero conversions detected — thin data "
                        f"(${target_spend:.0f}/{target_clicks} clicks), monitoring.]"
                    )
                    cascade_flags.append("ZERO_CONV_WATCH")

            # ── Cut Quadrant ───────────────────────────────────────────────
            if ppc_quadrant == "cut" and action == "promote":
                min_spend  = config.get("cascade_cut_min_spend", 50)
                min_clicks = config.get("cascade_cut_min_clicks", 15)

                if target_spend >= min_spend and target_clicks >= min_clicks:
                    # Confirmed Cut with conviction — dampen hard
                    new_bid = round(base_bid + (new_bid - base_bid) * 0.3, 2)
                    reason = (
                        reason.rstrip(".")
                        + f" Bid increase dampened 70% — Cut quadrant "
                        f"(${target_spend:.0f} spend, {target_clicks} clicks)."
                    )
                    cascade_flags.append("CUT_QUADRANT")

            # ── Account Health ─────────────────────────────────────────────
            if account_health == "declining" and action == "promote":
                dampen = config.get("cascade_account_declining_dampen", 0.8)
                bid_increase = new_bid - base_bid
                new_bid = round(base_bid + bid_increase * dampen, 2)
                reason = (
                    reason.rstrip(".")
                    + f" Account ROAS declining — bid increase dampened "
                    f"{int((1 - dampen) * 100)}% account-wide."
                )
                cascade_flags.append("ACCOUNT_DECLINING")

            # ── High-Conviction Promote (Stars + Amplifier + Healthy) ─────
            if (
                ppc_quadrant == "stars"
                and camp_eff_ratio is not None
                and camp_eff_ratio >= 1.0
                and account_health in ("improving", "stable", None)
                and action == "promote"
            ):
                new_bid = round(base_bid + (new_bid - base_bid) * 1.1, 2)
                reason = (
                    reason.rstrip(".")
                    + " Throttle loosened 10% — Star target in efficient campaign."
                )
                cascade_flags.append("HIGH_CONVICTION_PROMOTE")

            # Merge cascade flags into intelligence_flags for output column
            if cascade_flags:
                intelligence_flags = intelligence_flags + cascade_flags

        return new_bid, reason, action, intelligence_flags
    
    opt_results = grouped.apply(apply_optimization, axis=1)
    grouped["New Bid"] = opt_results.apply(lambda x: x[0])
    grouped["Reason"] = opt_results.apply(lambda x: x[1])
    grouped["Decision_Basis"] = opt_results.apply(lambda x: x[2])
    grouped["Intelligence_Flags"] = opt_results.apply(lambda x: ",".join(x[3]) if len(x) > 3 else "")
    grouped["Bucket"] = bucket_name
    
    # SYNC: Create recommendation objects for validation
    if not grouped.empty:
        def create_bid_rec(row):
            rec_id = f"bid_{row['Campaign Name']}_{row['Ad Group Name']}_{row['Targeting']}"
            
            # Determine recommendation type
            new_bid = row['New Bid']
            current_bid = row.get('Current Bid', 0)
            
            rec_type = RecommendationType.BID_INCREASE if new_bid > current_bid else RecommendationType.BID_DECREASE
            if new_bid == current_bid:
                # Only validate if it's an actionable change
                if row['Decision_Basis'] == "Hold (Insufficient Data)" or row['Decision_Basis'] == "Hold (No Data)":
                    return None
            
            # Determine if this is PT or Keyword based on bucket
            is_pt = row['Bucket'] in ["Product Targeting", "Auto"]
            
            try:
                rec = OptimizationRecommendation(
                    recommendation_id=rec_id,
                    recommendation_type=rec_type,
                    campaign_name=row['Campaign Name'],
                    campaign_id=row.get('CampaignId', ""),
                    campaign_targeting_type=row.get('Campaign Targeting Type', "Manual"),
                    ad_group_name=row['Ad Group Name'],
                    ad_group_id=row.get('AdGroupId', ""),
                    keyword_text=row['Targeting'] if not is_pt else None,
                    product_targeting_expression=row['Targeting'] if is_pt else None,
                    match_type=row['Match Type'],
                    current_bid=float(current_bid) if pd.notna(current_bid) else 0.0,
                    new_bid=float(new_bid),
                    currency=config.get("currency", "AED")
                )
                rec.validation_result = validate_recommendation(rec)
                return rec
            except Exception as e:
                # If validation fails, just return None, don't crash
                return None
            
        grouped['recommendation'] = grouped.apply(create_bid_rec, axis=1)
    
    return grouped


def _classify_and_bid(roas: float, median_roas: float, base_bid: float, alpha: float, 
                      data_source: str, config: dict, bucket_multiplier: float = 1.0) -> Tuple[float, str, str]:
    """
    Classify ROAS and determine bid action using PRD V2 Continuous Logic + Universal Throttles.
    Formula: Adjustment = (ROAS / Target - 1) * Throttle
    """
    # ---------------------------------------------------------
    # CHANGE 5: ROAS TARGET BY MATCH TYPE BUCKET
    # ---------------------------------------------------------
    raw_target_roas = config.get("TARGET_ROAS", 2.5)
    effective_target_roas = raw_target_roas * bucket_multiplier
    
    # Get Throttles (Defaults to Balanced layout if missing)
    up_throttle = config.get("BID_UP_THROTTLE", 0.50)
    down_throttle = config.get("BID_DOWN_THROTTLE", 0.50)
    
    # Calculate Performance Gap vs TARGET (Objective Goal), not Median (Relative)
    gap = (roas / effective_target_roas) - 1
    
    if gap > 0:
        # Outperforming - Scale Up
        adjustment = gap * up_throttle
        new_bid = base_bid * (1 + adjustment)
        adj_pct = (new_bid / base_bid) - 1
        reason = f"Bid raised +{adj_pct:.0%} — strong ROAS ({roas:.2f}×)"
        action = "promote"
    elif gap < 0:
        # Underperforming - Bid Down
        adjustment = gap * down_throttle
        new_bid = base_bid * (1 + adjustment)
        reason = f"Bid reduced — keyword spending {abs(gap):.0%} above target ROAS across 14-day window."
        action = "bid_down"
    else:
        new_bid = base_bid
        reason = f"Bid held — ROAS ({roas:.2f}×) perfectly matches target."
        action = "stable"
    
    # Cap Step Size (Per Run Safety Logic)
    # Even if formula says +100%, we limit single-run change to MAX_BID_CHANGE (e.g. 25%)
    # This prevents wild swings from one lucky week.
    max_change_pct = config.get("MAX_BID_CHANGE", 0.25)
    
    if new_bid > base_bid:
        max_allowed_step = base_bid * (1 + max_change_pct)
        if new_bid > max_allowed_step:
            new_bid = max_allowed_step
            reason = f"Bid raised +{max_change_pct:.0%} — strong ROAS ({roas:.2f}×). Bid capped at {max_change_pct:.0%} safety limit."
            
    elif new_bid < base_bid:
        min_allowed_step = base_bid * (1 - max_change_pct)
        if new_bid < min_allowed_step:
            new_bid = min_allowed_step
            reason = f"Bid reduced — keyword spending {abs(gap):.0%} above target ROAS (hit max decrease limit)."
    
    # Global Limits (Floor/Ceiling)
    min_bid_limit = max(BID_LIMITS["MIN_BID_FLOOR"], base_bid * BID_LIMITS["MIN_BID_MULTIPLIER"])
    max_bid_limit = base_bid * BID_LIMITS["MAX_BID_MULTIPLIER"]
    
    new_bid = np.clip(new_bid, min_bid_limit, max_bid_limit)
    
    return new_bid, reason, action

def deduplicate_bucket(bids_df, bucket_name):
    """Deduplicate keywords that appear in multiple campaigns within the same bucket."""
    if bids_df.empty:
        return bids_df
    
    # Normalize targeting for comparison
    bids_df = bids_df.copy()
    bids_df["_target_norm"] = bids_df["Targeting"].astype(str).str.strip().str.lower()
    
    # Find duplicates (same keyword in different campaigns)
    dup_mask = bids_df.duplicated(subset=["_target_norm"], keep=False)
    
    if not dup_mask.any():
        bids_df.drop(columns=["_target_norm"], inplace=True)
        return bids_df
    
    # For each duplicate group, keep highest ROAS, flag others
    consolidation_negatives = []
    
    for target, group in bids_df[dup_mask].groupby("_target_norm"):
        if len(group) <= 1:
            continue
        
        # Sort by ROAS descending
        sorted_group = group.sort_values("ROAS", ascending=False)
        winner = sorted_group.iloc[0]
        losers = sorted_group.iloc[1:]
        
        # Flag losers for consolidation negative
        for _, loser in losers.iterrows():
            consolidation_negatives.append({
                "Type": "Consolidation",
                "Campaign Name": loser["Campaign Name"],
                "Ad Group Name": loser.get("Ad Group Name", ""),
                "Term": loser["Targeting"],
                "Is_ASIN": is_asin(str(loser["Targeting"])),
                "Winner_Campaign": winner["Campaign Name"],
                "Winner_ROAS": winner["ROAS"],
                "Loser_ROAS": loser["ROAS"],
                "Reason": f"Consolidation: Same keyword exists in {winner['Campaign Name']} with higher ROAS ({winner['ROAS']:.2f} vs {loser['ROAS']:.2f})"
            })
    
    # Store consolidation negatives in session state for the negatives tab
    if consolidation_negatives:
        existing = st.session_state.get("consolidation_negatives", [])
        st.session_state["consolidation_negatives"] = existing + consolidation_negatives
    
    # Keep only winners (highest ROAS for each duplicate group) + all non-duplicates
    non_dups = bids_df[~dup_mask].copy()
    
    winners = []
    for target, group in bids_df[dup_mask].groupby("_target_norm"):
        winner_row = group.sort_values("ROAS", ascending=False).iloc[0:1]
        winner_row = winner_row.copy()
        winner_row["Reason"] = winner_row["Reason"].astype(str) + " [Best ROAS among duplicates]"
        winners.append(winner_row)
    
    if winners:
        winners_df = pd.concat(winners, ignore_index=True)
        result = pd.concat([non_dups, winners_df], ignore_index=True)
    else:
        result = non_dups
    
    result.drop(columns=["_target_norm"], inplace=True, errors="ignore")
    return result
