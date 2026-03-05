import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from app_core.db_manager import get_db_manager
from features.optimizer_shared.strategies.bids import calculate_bid_optimizations

load_dotenv()

def run_report():
    print("Generating Optimizer v2 Impact Report...")
    clients = ["s2c_uae_test", "s2c_test"]
    db = get_db_manager()
    
    stats = {
        "total_targets_evaluated": 0,
        "cooldown_blocks": 0,
        "visibility_suppressions": 0,
        "visibility_boosts": 0,
        "insufficient_data_promotes": 0,
        "insufficient_data_decreases": 0,
        "promotes": 0,
        "decreases": 0,
        "holds": 0
    }
    
    for client_id in clients:
        print(f"\\nProcessing client: {client_id}")
        
        # We need raw data. 
        # But get_optimizer_data might need a session state wrapper or we extract the raw DF directly from DB.
        # It's easier to just fetch raw target_stats directly for the latest day if available, 
        # or use get_target_stats_by_account and let prepare_data handle it.
        
        df_raw = db.get_target_stats_by_account(client_id, limit=50000)
        if df_raw.empty:
            print(f"Skipping {client_id} - no data.")
            continue
            
        print(f"Loaded {len(df_raw)} rows of raw performance data.")
        
        # In a real run, data goes through prepare_data first.
        # We'll just run calculate_bid_optimizations directly which handles grouping.
        
        # We must align columns so it looks like STR + Bulk combined
        col_map = {
            "spend": "Spend",
            "sales": "Sales",
            "clicks": "Clicks",
            "orders": "Orders",
            "impressions": "Impressions",
            "campaign_name": "Campaign Name",
            "ad_group_name": "Ad Group Name",
            "target_text": "Targeting",
            "match_type": "Match Type",
            "start_date": "Date"
        }
        df_prep = df_raw.rename(columns=col_map)
        if "Bid" not in df_prep.columns:
            df_prep["Bid"] = 1.0 # Mock bid 
        if "CPC" not in df_prep.columns:
            df_prep["CPC"] = np.where(df_prep["Clicks"] > 0, df_prep["Spend"] / df_prep["Clicks"], 0)
            
        config = {"TARGET_ROAS": 2.5, "BID_UP_THROTTLE": 0.5, "BID_DOWN_THROTTLE": 0.5}
        
        # RUN V2 EXPLICITLY IN DRY RUN MODE (We pass empty sets and client_id to trigger DB reads but we don't write DB here)
        print("Running optimizer...")
        ex, pt, agg, au = calculate_bid_optimizations(
            df=df_prep,
            config=config,
            harvested_terms=set(),
            negative_terms=set(),
            universal_median_roas=2.0,
            data_days=14,
            client_id=client_id # This triggers the DB calls for cooldown and 14d_roas
        )
        
        all_results = pd.concat([ex, pt, agg, au])
        if all_results.empty:
            print("No results returned.")
            continue
            
        stats["total_targets_evaluated"] += len(all_results)
        
        # Calculate impact based on Reason strings
        for reason in all_results["Reason"].dropna():
            if "Cooldown" in reason:
                stats["cooldown_blocks"] += 1
                stats["holds"] += 1
            elif "Visibility Boost Suppressed" in reason:
                stats["visibility_suppressions"] += 1
                stats["holds"] += 1
            elif "Visibility Boost: Only" in reason:
                stats["visibility_boosts"] += 1
            elif "Insufficient data for promote" in reason:
                stats["insufficient_data_promotes"] += 1
                stats["holds"] += 1
            elif "Insufficient data for decrease" in reason:
                stats["insufficient_data_decreases"] += 1
                stats["holds"] += 1
            elif "Bid Down" in reason or "Reduce" in reason:
                stats["decreases"] += 1
            elif "Promote" in reason or "Increase" in reason:
                stats["promotes"] += 1
            elif "Hold" in reason:
                stats["holds"] += 1
                
    report = f"""
BID OPTIMIZER V2 - IMPACT REPORT
================================
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Accounts Evaluated: {', '.join(clients)}
    
TOTAL TARGETS PROPOSED: {stats['total_targets_evaluated']}

ACTION BREAKDOWN:
- Bids Promoted: {stats['promotes']}
- Bids Decreased: {stats['decreases']}
- Visibility Boosts Fired: {stats['visibility_boosts']}
- Holds / No Action: {stats['holds']}

V2 LOGIC IMPACT:
- Actions Blocked by 14-Day Cooldown: {stats['cooldown_blocks']}
- Waste Prevented (Thin Data Promotes Blocked): {stats['insufficient_data_promotes']}
- Waste Prevented (Thin Data Decreases Blocked): {stats['insufficient_data_decreases']} 
- Waste Prevented (Visibility Boost suppressed on 0-converting targets): {stats['visibility_suppressions']}
"""

    print(report)
    with open('optimizer_v2_impact_report.txt', 'w') as f:
        f.write(report)
        
    print("Report saved to optimizer_v2_impact_report.txt")

if __name__ == "__main__":
    run_report()
