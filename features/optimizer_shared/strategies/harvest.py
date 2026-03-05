"""
Optimizer Harvest Strategy
Logic for identifying high-performing search terms to promote to Exact match.
"""

import pandas as pd
import numpy as np
import streamlit as st
from utils.matchers import ExactMatcher
from features.optimizer_shared.core import calculate_account_benchmarks, DEFAULT_CONFIG
from features.bulk_export import strip_targeting_prefix

def identify_harvest_candidates(
    df: pd.DataFrame, 
    config: dict, 
    matcher: ExactMatcher,
    account_benchmarks: dict = None
) -> pd.DataFrame:
    """
    Identify high-performing search terms to harvest as exact match keywords.
    Winner campaign/SKU trumps others based on performance when KW appears in multiple campaigns.
    
    CHANGES:
    - Uses BUCKET median ROAS (not campaign ROAS) for consistent baseline
    - Uses CVR-based dynamic min orders
    - Winner score: Sales + ROAS×5 (reduced from ×10)
    """
    
    # Use benchmarks if provided
    if account_benchmarks is None:
        account_benchmarks = calculate_account_benchmarks(df, config)
    
    universal_median_roas = account_benchmarks.get('universal_median_roas', config.get("TARGET_ROAS", 2.5))
    
    # Use dynamic min orders from CVR analysis
    min_orders_threshold = account_benchmarks.get('harvest_min_orders', config["HARVEST_ORDERS"])
    
    # Filter for discovery campaigns (non-exact, non-PT)
    # Exclude: exact match types, PT campaigns, and harvest destination campaigns
    harvest_dest_pattern = r'harvestexact|harvest_exact|_exact_|exactmatch'
    
    # Discovery = non-exact match type AND not a harvest destination campaign
    discovery_mask = (
        (~df["Match Type"].str.contains("exact", case=False, na=False)) &
        (~df["Match Type"].str.upper().isin(["PT", "PRODUCT TARGETING"])) &
        (~df["Campaign Name"].str.contains(harvest_dest_pattern, case=False, na=False))
    )
    discovery_df = df[discovery_mask].copy()
    
    if discovery_df.empty:
        return pd.DataFrame(columns=["Customer Search Term", "Harvest_Term", "Campaign Name", "Ad Group Name", "ROAS", "Spend", "Sales", "Orders"])
    
    # CRITICAL: Use Customer Search Term for harvest (actual user queries)
    # NOT Targeting (which contains targeting expressions like close-match, category=, etc.)
    harvest_column = "Customer Search Term" if "Customer Search Term" in discovery_df.columns else "Targeting"
    
    # PT PREFIX STRIPPING: Strip asin= and asin-expanded= prefixes so clean ASINs can be harvested
    discovery_df[harvest_column] = discovery_df[harvest_column].apply(strip_targeting_prefix)
    
    # CRITICAL: Filter OUT targeting expressions that are NOT actual search queries
    # NOTE: asin= and asin-expanded= are now ALLOWED after prefix stripping
    targeting_expression_patterns = [
        r'^close-match$', r'^loose-match$', r'^substitutes$', r'^complements$', r'^auto$',
        r'^category=', r'^keyword-group=',  # PT (asin=) now allowed
    ]
    
    # Create mask for rows that are actual search queries (not targeting expressions)
    is_actual_search_query = ~discovery_df[harvest_column].str.lower().str.strip().str.match(
        '|'.join(targeting_expression_patterns), na=False
    )
    
    # Filter to only actual search queries
    discovery_df = discovery_df[is_actual_search_query].copy()
    
    if discovery_df.empty:
        return pd.DataFrame(columns=["Customer Search Term", "Harvest_Term", "Campaign Name", "Ad Group Name", "ROAS", "Spend", "Sales", "Orders"])
    
    # Aggregate by Customer Search Term for harvest
    agg_cols = {
        "Impressions": "sum", "Clicks": "sum", "Spend": "sum",
        "Sales": "sum", "Orders": "sum", "CPC": "mean"
    }
    
    # Also keep Targeting for reference
    if "Targeting" in discovery_df.columns and harvest_column != "Targeting":
        agg_cols["Targeting"] = "first"
    
    grouped = discovery_df.groupby(harvest_column, as_index=False).agg(agg_cols)
    grouped["ROAS"] = np.where(grouped["Spend"] > 0, grouped["Sales"] / grouped["Spend"], 0)
    
    # Rename to Harvest_Term for consistency
    grouped = grouped.rename(columns={harvest_column: "Harvest_Term"})
    grouped["Customer Search Term"] = grouped["Harvest_Term"]
    
    # CHANGE #3: Winner selection score rebalanced (ROAS×5 instead of ×10)
    # Get metadata from BEST performing instance (winner selection)
    # Rank by Sales (primary), then ROAS (secondary)
    discovery_df["_perf_score"] = discovery_df["Sales"] + (discovery_df["ROAS"] * 5)
    discovery_df["_rank"] = discovery_df.groupby("Customer Search Term")["_perf_score"].rank(
        method="first", ascending=False
    )
    
    # Build metadata columns list
    meta_cols = ["Customer Search Term", "Campaign Name", "Ad Group Name", "Campaign_ROAS"]
    if "CampaignId" in discovery_df.columns:
        meta_cols.append("CampaignId")
    if "AdGroupId" in discovery_df.columns:
        meta_cols.append("AdGroupId")
    if "SKU_advertised" in discovery_df.columns:
        meta_cols.append("SKU_advertised")
    if "ASIN_advertised" in discovery_df.columns:
        meta_cols.append("ASIN_advertised")
    
    # Get winner row for each Customer Search Term value
    meta_df = discovery_df[discovery_df["_rank"] == 1][meta_cols].drop_duplicates("Customer Search Term")
    merged = pd.merge(grouped, meta_df, on="Customer Search Term", how="left")
    
    # Ensure Customer Search Term column exists for downstream compatibility
    if "Customer Search Term" not in merged.columns:
        merged["Customer Search Term"] = merged["Harvest_Term"]
    
    # Step 2: Calculate bucket ROAS using spend-weighted average (Total Sales / Total Spend)
    # This matches the actual bucket performance shown in UI, not skewed by many 0-sale rows
    bucket_with_spend = merged[merged["Spend"] > 0]
    bucket_sample_size = len(bucket_with_spend)
    total_spend = bucket_with_spend["Spend"].sum()
    total_sales = bucket_with_spend["Sales"].sum()
    bucket_weighted_roas = total_sales / total_spend if total_spend > 0 else 0

    # Step 3: Stat sig check - need minimum data for reliable bucket ROAS
    MIN_SAMPLE_SIZE_FOR_STAT_SIG = 20
    MIN_SPEND_FOR_STAT_SIG = 100  # Need at least AED 100 spend for reliable bucket ROAS
    OUTLIER_THRESHOLD_MULTIPLIER = 1.5

    if bucket_sample_size < MIN_SAMPLE_SIZE_FOR_STAT_SIG or total_spend < MIN_SPEND_FOR_STAT_SIG:
        baseline_roas = universal_median_roas  # Use universal
        baseline_source = "Universal Median (insufficient bucket data)"
    else:
        # Step 4: Outlier detection
        if bucket_weighted_roas > universal_median_roas * OUTLIER_THRESHOLD_MULTIPLIER:
            baseline_roas = universal_median_roas  # Outlier, use universal
            baseline_source = "Universal Median (bucket is outlier)"
        else:
            baseline_roas = bucket_weighted_roas  # Valid, use bucket weighted ROAS
            baseline_source = f"Bucket Weighted ROAS (spend={total_spend:.0f})"

    print(f"\n=== HARVEST BASELINE ===")
    print(f"Baseline ROAS: {baseline_roas:.2f}x ({baseline_source})")
    print(f"Required ROAS: {baseline_roas * config['HARVEST_ROAS_MULT']:.2f}x")
    print(f"=== END HARVEST BASELINE ===\n")
    
    # Apply harvest thresholds (Tier 2)
    # High-ROAS term exception
    def calculate_roas_threshold(row):
        term_roas = row["ROAS"]
        if term_roas >= universal_median_roas:
            return term_roas >= (universal_median_roas * config["HARVEST_ROAS_MULT"])
        else:
            return term_roas >= (baseline_roas * config["HARVEST_ROAS_MULT"])

    # Individual threshold checks for debugging
    pass_clicks = merged["Clicks"] >= config["HARVEST_CLICKS"]
    pass_orders = merged["Orders"] >= min_orders_threshold  # CHANGE #5: CVR-based dynamic threshold
    # pass_sales = merged["Sales"] >= config["HARVEST_SALES"]  # REMOVED: Currency threshold doesn't work across geos
    pass_roas = merged.apply(calculate_roas_threshold, axis=1)
    
    # Currency-based threshold (HARVEST_SALES) removed - only clicks, orders, ROAS matter
    harvest_mask = pass_clicks & pass_orders & pass_roas
    
    candidates = merged[harvest_mask].copy()
    
    # DEBUG: Show why terms fail
    print(f"\n=== HARVEST DEBUG ===")
    print(f"Discovery rows: {len(discovery_df)}")
    print(f"Grouped search terms: {len(grouped)}")
    print(f"Threshold config: Clicks>={config['HARVEST_CLICKS']}, Orders>={min_orders_threshold} (CVR-based), ROAS>{config['HARVEST_ROAS_MULT']}x bucket median")
    print(f"Pass clicks: {pass_clicks.sum()}, Pass orders: {pass_orders.sum()}, Pass ROAS: {pass_roas.sum()}")
    print(f"After ALL thresholds: {len(candidates)} candidates")
    
    if len(candidates) > 0:
        print(f"\\nTop 5 candidates BEFORE dedupe:")
        for _, r in candidates.head(5).iterrows():
            print(f"  - '{r['Customer Search Term']}': {r['Clicks']} clicks, {r['Orders']} orders, ${r['Sales']:.2f} sales")
    
    # Dedupe against existing exact keywords
    survivors = []
    deduped = []
    for _, row in candidates.iterrows():
        matched, match_info = matcher.find_match(row["Customer Search Term"], config["DEDUPE_SIMILARITY"])
        if not matched:
            survivors.append(row)
        else:
            deduped.append((row["Customer Search Term"], match_info))
    
    print(f"\\nDedupe results:")
    print(f"  - Survivors (new harvest): {len(survivors)}")
    print(f"  - Deduped (already exist): {len(deduped)}")
    print(f"=== END HARVEST DEBUG ===\\n")
    
    survivors_df = pd.DataFrame(survivors)
    
    if not survivors_df.empty:
        # Calculate New Bid using priority: Bid → Ad Group Default Bid → Current Bid → CPC
        # Apply launch multiplier (+10% above current bid by default)
        launch_mult = DEFAULT_CONFIG.get("HARVEST_LAUNCH_MULTIPLIER", 1.1)
        
        def get_base_bid(row):
            """Get base bid with priority: Bid → Ad Group Default Bid → Current Bid → CPC"""
            for col in ["Bid", "Ad Group Default Bid", "Current Bid"]:
                if col in row.index and pd.notna(row.get(col)) and float(row.get(col) or 0) > 0:
                    return float(row.get(col))
            # Fallback to CPC
            return float(row.get("CPC", 0) or 0)
        
        survivors_df["Base Bid"] = survivors_df.apply(get_base_bid, axis=1)
        survivors_df["New Bid"] = survivors_df["Base Bid"] * launch_mult
        survivors_df = survivors_df.sort_values("Sales", ascending=False)
    
    if survivors_df.empty:
        # Fallback empty structure
        return pd.DataFrame(columns=["Customer Search Term", "Harvest_Term", "Campaign Name", "Ad Group Name", "ROAS", "Spend", "Sales", "Orders", "New Bid"])

    return survivors_df
