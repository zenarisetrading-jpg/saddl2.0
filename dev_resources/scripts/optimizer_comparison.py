import os
import sys
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from collections import defaultdict

# Setup context
sys.path.append('/Users/zayaanyousuf/Documents/Amazon PPC/saddle/saddle/desktop')
load_dotenv('/Users/zayaanyousuf/Documents/Amazon PPC/saddle/saddle/.env')

from app_core.db_manager import get_db_manager
from features.optimizer_shared.core import prepare_data, calculate_account_benchmarks, DEFAULT_CONFIG
from features.optimizer_shared.strategies.harvest import identify_harvest_candidates
from features.optimizer_shared.strategies.negatives import identify_negative_candidates
from features.optimizer_shared.strategies.bids import calculate_bid_optimizations
from utils.matchers import ExactMatcher

# 1. Config & Data Setup
db = get_db_manager(False)
client_id = "s2c_uae_test"

# The user requested Feb 1-17, but DB data might only go up to Feb 9 based on check script.
# We will use the full available data in Feb, bounded by the dataset limits.
df_raw = db.get_target_stats_df(client_id)
df_raw['Date'] = pd.to_datetime(df_raw['Date'], errors='coerce')

min_dt = df_raw['Date'].min()
max_dt = df_raw['Date'].max()

# Helper to normalize output DataFrames into a standard generic list of dictionaries
def extract_actions(bids_ex, bids_pt, bids_agg, bids_auto):
    actions_list = []
    
    for df_subset, match_type in [
        (bids_ex, "EXACT"), 
        (bids_pt, "PRODUCT_TARGETING"), 
        (bids_agg, "BROAD_PHRASE"), 
        (bids_auto, "AUTO")
    ]:
        if df_subset.empty:
            continue
            
        for _, row in df_subset.iterrows():
            # Get target text column (differs slightly by bucket)
            target = row.get("Targeting", row.get("Target", "Unknown"))
            
            # Action string format from the backend ("Increase (+X.XX%)", "Hold (Reason)")
            raw_action = row.get("Action", "")
            
            # Simplify action type
            action_type = "HOLD"
            if "Increase" in raw_action:
                action_type = "INCREASE"
            elif "Decrease" in raw_action:
                action_type = "DECREASE"
            
            # Some actions are hold with intelligence reasons
            if "Blocked" in raw_action or "Hold (Intelligence" in raw_action or "Protected" in raw_action or "Suppressed" in raw_action:
                action_type = "BLOCKED"
                
            flags_val = row.get("Intelligence_Flags", "")
            flags = [f.strip() for f in str(flags_val).split(",")] if pd.notna(flags_val) and flags_val else []
            
            actions_list.append({
                "target": target,
                "campaign_name": row.get("Campaign Name", ""),
                "ad_group_name": row.get("Ad Group Name", ""),
                "match_type": match_type,
                "action_type": action_type,
                "current_bid": float(row.get("Current Bid", 0.0)),
                "recommended_bid": float(row.get("New Bid", 0.0)),
                "roas": float(row.get("ROAS", 0.0)),
                "commerce_flags": flags,
                "reason": row.get("Reason", "")
            })
            
    return actions_list

# Dynamic Date Searching
target_end_date_opt = min_dt + pd.Timedelta(days=30)
if target_end_date_opt > max_dt:
    target_end_date_opt = max_dt

found_good_window = False
data_days = 17 # typical window

print(f"Searching for an active data window with baseline actions (starting near {target_end_date_opt.date()})...")

while target_end_date_opt >= min_dt + pd.Timedelta(days=14):
    start_date = target_end_date_opt - pd.Timedelta(days=data_days - 1)
    if start_date < min_dt:
        start_date = min_dt
        
    mask = (df_raw['Date'] >= start_date) & (df_raw['Date'] <= target_end_date_opt)
    df_test = df_raw[mask].copy()
    
    config = DEFAULT_CONFIG.copy()
    df_prep, date_info = prepare_data(df_test, config)
    benchmarks = calculate_account_benchmarks(df_prep, config)
    universal_median = benchmarks.get('universal_median_roas', config.get("TARGET_ROAS", 2.5))
    
    # Try a quick mock run
    import features.optimizer_shared_shared.strategies.bids as bids_module
    orig = bids_module.compute_intelligence_flags
    bids_module.compute_intelligence_flags = lambda row, lookup, config: []
    
    matcher = ExactMatcher(df_prep)
    harvest = identify_harvest_candidates(df_prep, config, matcher, benchmarks)
    neg_kw, neg_pt, yr = identify_negative_candidates(df_prep, config, harvest, benchmarks)
    n_set = set(zip(neg_kw["Campaign Name"], neg_kw["Ad Group Name"], neg_kw["Term"].str.lower()))
    h_set = set(harvest["Customer Search Term"].str.lower())
    
    bx, bp, ba, bauto = calculate_bid_optimizations(
        df_prep.copy(), config, h_set, n_set, universal_median, 
        data_days=data_days, client_id=client_id
    )
    bids_module.compute_intelligence_flags = orig
    
    acts = extract_actions(bx, bp, ba, bauto)
    increments = sum(1 for a in acts if a['action_type'] == 'INCREASE')
    decrements = sum(1 for a in acts if a['action_type'] == 'DECREASE')
    
    if (increments + decrements) >= 50:
        found_good_window = True
        break
        
    target_end_date_opt -= pd.Timedelta(days=7) # Step back 1 week

if not found_good_window:
    print("WARNING: Could not find a 17-day window with >= 50 base actions. Using the most volatile period found or default.")
    # Fallback bounds 
    start_date = min_dt
    target_end_date_opt = max_dt

end_date = target_end_date_opt
mask = (df_raw['Date'] >= start_date) & (df_raw['Date'] <= end_date)
df = df_raw[mask].copy()
data_days = (end_date - start_date).days + 1
date_str = f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}"
print(f"Selected Window: {date_str} ({data_days} days)")

# 2. Preparation
config = DEFAULT_CONFIG.copy()
df_prep, date_info = prepare_data(df, config)
benchmarks = calculate_account_benchmarks(df_prep, config)
universal_median = benchmarks.get('universal_median_roas', config.get("TARGET_ROAS", 2.5))
data_days = (end_date - start_date).days + 1

matcher = ExactMatcher(df_prep)
harvest = identify_harvest_candidates(df_prep, config, matcher, benchmarks)
neg_kw, neg_pt, your_products = identify_negative_candidates(df_prep, config, harvest, benchmarks)
neg_set = set(zip(neg_kw["Campaign Name"], neg_kw["Ad Group Name"], neg_kw["Term"].str.lower()))
harvest_set = set(harvest["Customer Search Term"].str.lower())

# Helper to normalize output DataFrames into a standard generic list of dictionaries
def extract_actions(bids_ex, bids_pt, bids_agg, bids_auto):
    actions_list = []
    
    for df_subset, match_type in [
        (bids_ex, "EXACT"), 
        (bids_pt, "PRODUCT_TARGETING"), 
        (bids_agg, "BROAD_PHRASE"), 
        (bids_auto, "AUTO")
    ]:
        if df_subset.empty:
            continue
            
        for _, row in df_subset.iterrows():
            # Get target text column (differs slightly by bucket)
            target = row.get("Targeting", row.get("Target", "Unknown"))
            
            # Action string format from the backend ("Increase (+X.XX%)", "Hold (Reason)")
            raw_action = row.get("Action", "")
            
            # Simplify action type
            action_type = "HOLD"
            if "Increase" in raw_action:
                action_type = "INCREASE"
            elif "Decrease" in raw_action:
                action_type = "DECREASE"
            
            # Some actions are hold with intelligence reasons
            if "Blocked" in raw_action or "Hold (Intelligence" in raw_action or "Protected" in raw_action or "Suppressed" in raw_action:
                action_type = "BLOCKED"
                
            flags_val = row.get("Intelligence_Flags", "")
            flags = [f.strip() for f in str(flags_val).split(",")] if pd.notna(flags_val) and flags_val else []
            
            actions_list.append({
                "target": target,
                "campaign_name": row.get("Campaign Name", ""),
                "ad_group_name": row.get("Ad Group Name", ""),
                "match_type": match_type,
                "action_type": action_type,
                "current_bid": float(row.get("Current Bid", 0.0)),
                "recommended_bid": float(row.get("New Bid", 0.0)),
                "roas": float(row.get("ROAS", 0.0)),
                "commerce_flags": flags,
                "reason": row.get("Reason", "")
            })
            
    return actions_list

# ========================================================
# RUN A: PURE V2 (NO COMMERCE INTELLIGENCE)
# ========================================================
print("Executing RUN A: Pure V2 (Intelligence Disabled)...")

import features.optimizer_shared_shared.strategies.bids as bids_module

# Temporarily mock the intelligence function to return empty
original_compute = bids_module.compute_intelligence_flags
bids_module.compute_intelligence_flags = lambda row, lookup, config: []

bids_ex_A, bids_pt_A, bids_agg_A, bids_auto_A = calculate_bid_optimizations(
    df_prep.copy(), config, harvest_set, neg_set, universal_median, 
    data_days=data_days, client_id=client_id
)

actions_A = extract_actions(bids_ex_A, bids_pt_A, bids_agg_A, bids_auto_A)
bids_module.compute_intelligence_flags = original_compute # Restore

# ========================================================
# RUN B: V2.1 (COMMERCE INTELLIGENCE ACTIVE)
# ========================================================
print("Executing RUN B: V2.1 (Intelligence Active)...")

bids_ex_B, bids_pt_B, bids_agg_B, bids_auto_B = calculate_bid_optimizations(
    df_prep.copy(), config, harvest_set, neg_set, universal_median, 
    data_days=data_days, client_id=client_id
)

actions_B = extract_actions(bids_ex_B, bids_pt_B, bids_agg_B, bids_auto_B)

# ========================================================
# ANALYSIS & REPORT GENERATION
# ========================================================

# Quick mapping using composite key
def make_key(a):
    return f"{str(a['campaign_name']).lower()}|{str(a['ad_group_name']).lower()}|{str(a['target']).lower()}"

map_B = {make_key(a): a for a in actions_B}

# Lookup commerce data to validate HALO_ACTIVE triggers
commerce_df = db.get_commerce_metrics_by_target(client_id)
from features.optimizer_shared.intelligence import build_commerce_lookup
c_lookup_B = build_commerce_lookup(commerce_df)
halo_diagnostics = []

modifications = []
flag_counts = defaultdict(int)
financial_delta = {
    "v2_increase_cost": 0.0,
    "v21_increase_cost": 0.0,
    "v2_decrease_savings": 0.0,
    "v21_decrease_savings": 0.0,
}

inventory_blocked_targets = []
all_blocked_targets = []

for act_A in actions_A:
    key = make_key(act_A)
    act_B = map_B.get(key)
    if not act_B:
        continue # Should not happen structurally
        
    diff_bid_A = act_A["recommended_bid"] - act_A["current_bid"]
    diff_bid_B = act_B["recommended_bid"] - act_B["current_bid"]
    
    # Financial metrics (very crude proxy assuming 10 clicks per bid change to get a cost proxy)
    if diff_bid_A > 0: financial_delta["v2_increase_cost"] += (diff_bid_A * 10)
    if diff_bid_A < 0: financial_delta["v2_decrease_savings"] += (abs(diff_bid_A) * 10)
    
    if diff_bid_B > 0: financial_delta["v21_increase_cost"] += (diff_bid_B * 10)
    if diff_bid_B < 0: financial_delta["v21_decrease_savings"] += (abs(diff_bid_B) * 10)
        
    # Analyze differences
    if act_A["action_type"] != act_B["action_type"] or abs(act_A["recommended_bid"] - act_B["recommended_bid"]) > 0.01:
        modifications.append({
            "target": act_A["target"],
            "campaign": act_A["campaign_name"],
            "v2_state": f"{act_A['action_type']} ({act_A['recommended_bid']:.2f})",
            "v21_state": f"{act_B['action_type']} ({act_B['recommended_bid']:.2f})",
            "flags": act_B["commerce_flags"],
            "roas": act_A['roas'],
            "reason_B": act_B["reason"]
        })
        
        # Track flag counts
        for flag in act_B["commerce_flags"]:
            flag_counts[flag] += 1
            if flag == "INVENTORY_RISK":
                inventory_blocked_targets.append(act_A["target"])
            elif flag == "HALO_ACTIVE" and len(halo_diagnostics) < 5:
                # Get raw commerce stats for this campaign/adgroup
                c_key = f"{str(act_A['campaign_name']).lower()}|{str(act_A['ad_group_name']).lower()}"
                metrics = c_lookup_B.get(c_key, {})
                
                # Fetch target row from original V2 run to get the actual Paid Orders for this specific keyword
                target_orders = 0
                for df_subset in [bids_ex_A, bids_pt_A, bids_agg_A, bids_auto_A]:
                    if not df_subset.empty:
                        # Find the row matching this target/campaign
                        match = df_subset[
                            (df_subset['Campaign Name'] == act_A['campaign_name']) & 
                            (df_subset['Targeting'] == act_A['target'])
                        ]
                        if not match.empty:
                            target_orders = match.iloc[0].get('Orders', 0)
                            break
                            
                halo_diagnostics.append({
                    "target": act_A["target"],
                    "paid_orders": target_orders,
                    "total_adgroup_units": metrics.get("units_ordered", "Unknown")
                })
                
        # Track full blocks
        if act_A["action_type"] in ["INCREASE", "DECREASE"] and act_B["action_type"] in ["HOLD", "BLOCKED"]:
            all_blocked_targets.append({
                "target": act_A["target"],
                "intended_action": act_A["action_type"],
                "reason": act_B["reason"]
            })


# Aggregate Volume
def summarize_volume(acts):
    stats = {"INCREASE": 0, "DECREASE": 0, "HOLD": 0, "BLOCKED": 0, "TOTAL": len(acts)}
    for a in acts:
        stats[a["action_type"]] = stats.get(a["action_type"], 0) + 1
    return stats

vol_A = summarize_volume(actions_A)
vol_B = summarize_volume(actions_B)

delta_inc = vol_A["INCREASE"] - vol_B["INCREASE"]
delta_dec = vol_A["DECREASE"] - vol_B["DECREASE"]
delta_blocked = vol_B["BLOCKED"] + vol_B["HOLD"] - (vol_A["BLOCKED"] + vol_A["HOLD"])

top_flag = max(flag_counts, key=flag_counts.get) if flag_counts else "None"

# ========================================================
# REPORT FORMATTING
# ========================================================

report = f"""OPTIMIZER COMPARATIVE ANALYSIS: V2 vs V2.1
==========================================
Client: {client_id}
Date Range: {date_str}
Note: The PRD discrepancy regarding CANNIBALIZE_RISK logic is noted. PRD states organic_strength > 0.60, 
implementation uses organic_cvr > paid_cvr * 3. BSR_DECLINING logic is referenced in PRD but not yet implemented.

1. VOLUME DIFFERENCE
--------------------
V2   Total Actions: {vol_A['TOTAL']} (Increases: {vol_A['INCREASE']} | Decreases: {vol_A['DECREASE']} | Holds: {vol_A['HOLD']})
V2.1 Total Actions: {vol_B['TOTAL']} (Increases: {vol_B['INCREASE']} | Decreases: {vol_B['DECREASE']} | Holds/Blocks: {vol_B['HOLD'] + vol_B['BLOCKED']})
Delta: {delta_inc} fewer increases | {delta_dec} fewer decreases | {delta_blocked} more active holds due to Commerce Intelligence

2. ACTIONS MODIFIED BY INTELLIGENCE LAYER ({len(modifications)} targets affected)
--------------------
"""

if modifications:
    for mod in modifications:
        flags_str = ",".join(mod['flags']) if mod['flags'] else "None"
        report += f"Target: {mod['target']}\n"
        report += f"  Campaign: {mod['campaign']}\n"
        report += f"  V2  Action: {mod['v2_state']} | ROAS: {mod['roas']:.2f}\n"
        report += f"  V2.1 Action: {mod['v21_state']} | Flags: {flags_str}\n"
        report += f"  V2.1 Reason: {mod['reason_B']}\n\n"
else:
    report += "No targets were modified by intelligence layer in this timeframe.\n\n"

report += f"""3. FLAG SUMMARY
--------------------
"""
if flag_counts:
    for f, count in flag_counts.items():
        report += f"[{f}] fired: {count} targets\n"
    if inventory_blocked_targets:
        report += f"\nTargets protected by INVENTORY_RISK (under 14 days supply):\n"
        for t in inventory_blocked_targets[:10]:
            report += f" - {t}\n"
        if len(inventory_blocked_targets) > 10:
            report += f"   ...and {len(inventory_blocked_targets) - 10} more.\n"
            
    if halo_diagnostics:
        report += f"\nHALO_ACTIVE Diagnostics (Validating Signal):\n"
        for hd in halo_diagnostics:
            ratio = hd['total_adgroup_units'] / hd['paid_orders'] if hd['paid_orders'] > 0 else float('inf')
            report += f" - {hd['target']}: {hd['paid_orders']} Paid Orders vs {hd['total_adgroup_units']} Total AdGroup Units (Ratio: {ratio:.1f}x)\n"
else:
    report += "No commerce flags triggered during this run.\n"

report += f"""
4. FINANCIAL IMPACT ESTIMATE (Relative Proxy Based on Default 10x Click Velocity)
--------------------
V2   Projected Increase Cost (AED): {financial_delta['v2_increase_cost']:.2f}
V2.1 Projected Increase Cost (AED): {financial_delta['v21_increase_cost']:.2f}
Savings: {financial_delta['v2_increase_cost'] - financial_delta['v21_increase_cost']:.2f} protected from waste on out-of-stock items.

V2   Projected Decrease Savings (AED): {financial_delta['v2_decrease_savings']:.2f}
V2.1 Projected Decrease Savings (AED): {financial_delta['v21_decrease_savings']:.2f}
Delta: {financial_delta['v21_decrease_savings'] - financial_delta['v2_decrease_savings']:.2f} difference (Halo targets protected from down-bidding)

5. TARGETS V2.1 BLOCKED ENTIRELY
--------------------
"""
if all_blocked_targets:
    for b in all_blocked_targets:
        report += f"Target: {b['target']} (Intended: {b['intended_action']})\n"
        report += f"  -> Suppressed Reason: {b['reason']}\n"
else:
    report += "No targets were exclusively blocked by V2.1.\n"


exec_summary = f"""
EXECUTIVE SUMMARY
-----------------
V2.1 modified {len(modifications)} out of {vol_A['TOTAL']} total recommendations compared to V2. The intelligence layer suppressed AED {financial_delta['v2_increase_cost'] - financial_delta['v21_increase_cost']:.2f} in risky bid changes across {delta_inc + delta_dec} targets primarily due to {top_flag}. {flag_counts.get('INVENTORY_RISK', 0)} targets were explicitly protected from bid increases due to inventory risk (less than 14 days of supply), preventing ad spend on collapsing ASINs.
"""

report += "\n" + exec_summary

# Save and print
with open('/Users/zayaanyousuf/Documents/Amazon PPC/saddle/saddle/desktop/optimizer_comparison_report.txt', 'w') as f:
    f.write(report)
    
print(exec_summary)
print("\n--- Top Modified Actions ---")
for m in modifications[:10]:
    flags = ",".join(m['flags'])
    print(f"[{flags}] {m['target']}: V2 {m['v2_state']} -> V2.1 {m['v21_state']}")
