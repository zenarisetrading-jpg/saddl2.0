"""
Commerce Intelligence Engine Component (V2.1)
"""

import pandas as pd
from typing import Dict, Any, List

def compute_intelligence_flags(
    row: pd.Series, 
    commerce_lookup: Dict[str, Dict[str, Any]], 
    config: Dict[str, Any]
) -> List[str]:
    """
    Computes V2.1 Commerce Intelligence flags for a specific target.
    
    Args:
        row: Row from the bid optimization DataFrame
        commerce_lookup: Dictionary of commerce metrics keyed by (campaign_name, ad_group_name)
        config: Optimizer configuration dictionary
        
    Returns:
        List of activated flag strings (e.g., ["INVENTORY_RISK", "HALO_ACTIVE"])
    """
    campaign = str(row.get("Campaign Name", "")).lower().strip()
    ad_group = str(row.get("Ad Group Name", "")).lower().strip()
    
    # We look up commerce metrics based on the Campaign + Ad Group
    key = f"{campaign}|{ad_group}"
    
    metrics = commerce_lookup.get(key)
    if not metrics:
        return []
        
    flags = []
    
    # 1. INVENTORY_RISK
    # Rule: < 14 days of supply OR 0 fulfillable quantity (if we have velocity)
    dos = metrics.get("days_of_supply", 999)
    if dos < 14:
        flags.append("INVENTORY_RISK")
        
    # 2. CANNIBALIZE_RISK
    # Rule: Organic CVR is extremely high compared to Paid CVR (e.g., > 3x)
    organic_cvr = metrics.get("organic_cvr", 0.0)
    paid_cvr = row.get("Orders", 0) / row.get("Clicks", 1) if row.get("Clicks", 0) > 0 else 0
    
    if organic_cvr > 0 and paid_cvr > 0:
        if organic_cvr > (paid_cvr * 3):
            # Also require exact match typically, enforced in bids.py
            flags.append("CANNIBALIZE_RISK")
            
    # 3. HALO_ACTIVE
    total_units = metrics.get("units_ordered", 0)
    ad_units = row.get("Orders", 0)
    organic_units = total_units - ad_units
    
    # Needs a config threshold or defaults to 30
    halo_min_organic = config.get("halo_min_organic_units", 30)
    
    if ad_units > 0 and total_units > (ad_units * 3) and organic_units >= halo_min_organic:
        flags.append("HALO_ACTIVE")
        
    # 4. PRODUCT LIFECYCLE
    # Add flag if it's explicitly in launch phase
    lifecycle = metrics.get("product_lifecycle", "mature")
    if lifecycle == "launch":
        flags.append("LAUNCH_PHASE")
        
    return flags

def build_commerce_lookup(commerce_df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Builds a fast O(1) lookup dictionary from the commerce_metrics dataframe.
    Groups by Campaign and Ad Group.
    """
    if commerce_df is None or commerce_df.empty:
        return {}
        
    lookup = {}
    
    # Since an ad group might have multiple SKUs, we take the mean/sum of metrics
    agg_df = commerce_df.groupby(["campaign_name", "ad_group_name"]).agg({
        "ordered_revenue": "sum",
        "units_ordered": "sum",
        "sessions": "sum",
        "organic_cvr": "mean",
        "days_of_supply": "min", # The most at-risk SKU in the ad group dictates risk
        "product_lifecycle": "first" # Assume homogeneous lifecycle within ad group
    }).reset_index()
    
    for _, row in agg_df.iterrows():
        camp = str(row["campaign_name"]).lower().strip()
        ag = str(row["ad_group_name"]).lower().strip()
        key = f"{camp}|{ag}"
        
        lookup[key] = {
            "ordered_revenue": row["ordered_revenue"],
            "units_ordered": row["units_ordered"],
            "sessions": row["sessions"],
            "organic_cvr": row["organic_cvr"],
            "days_of_supply": row["days_of_supply"],
            "product_lifecycle": row["product_lifecycle"]
        }
        
    return lookup
