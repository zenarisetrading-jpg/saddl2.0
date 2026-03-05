import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Add parent directory to path to import features
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from features.optimizer_shared.strategies.bids import calculate_bid_optimizations, MIN_CLICKS_FOR_PROMOTE

# Ensure DB context loads correctly
load_dotenv()
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    raise ValueError("DATABASE_URL not found in .env")

# ---------------------------------------------------------
# MOCKING POSTGRES MANAGER FOR CONTROLLED TESTING
# ---------------------------------------------------------
# We will inject specific data structures directly into `calculate_bid_optimizations` 
# parameters (roas_14d_lookup, cooldown_lookup) if we were running it directly, but since
# the script initializes the DB manager inside calculate_bid_optimizations we have to patch it.

from unittest.mock import patch
import app_core.db_manager

# This function creates a controlled environment to run calculate_bid_optimizations
def run_optimizer_with_mocks(df, cooldowns_df, roas_14d_df, commerce_df=None):
    if commerce_df is None:
        commerce_df = pd.DataFrame()
        
    class MockDBManager:
        def __init__(self, c_df, r_df, com_df):
            self.c_df = c_df
            self.r_df = r_df
            self.com_df = com_df
            
        def get_recent_action_dates(self, client_id):
            return self.c_df
            
        def get_target_14d_roas(self, client_id):
            return self.r_df
            
        def get_commerce_metrics_by_target(self, client_id):
            return self.com_df

        def has_active_spapi_integration(self, client_id):
            return not self.com_df.empty
            
    def mock_get_db_manager(test_mode=False):
        return MockDBManager(cooldowns_df, roas_14d_df, commerce_df)

    with (
        patch('app_core.db_manager.get_db_manager', side_effect=mock_get_db_manager),
        patch('features.optimizer_shared.strategies.bids.DataHub') as mock_datahub,
        patch('features.optimizer_shared.strategies.bids.st') as mock_st,
        patch('features.optimizer_shared.strategies.bids.enrich_with_ids', side_effect=lambda df, bulk: df),
    ):
             
        mock_st.session_state = {'test_mode': True}
        mock_datahub.return_value.get_data.return_value = pd.DataFrame()
        
        return calculate_bid_optimizations(
            df=df.copy(),
            config={"TARGET_ROAS": 2.5, "BID_UP_THROTTLE": 0.5, "BID_DOWN_THROTTLE": 0.5},
            universal_median_roas=2.0,
            data_days=14,
            client_id="s2c_uae_test"
        )

# ---------------------------------------------------------
# HELPER TO GENERATE TEST BASE DATAFRAME
# ---------------------------------------------------------
def create_base_df(target_name, match_type, clicks, spend, sales, impressions, orders=1, bid=1.0):
    return pd.DataFrame([{
        "Campaign Name": "Test Campaign",
        "Ad Group Name": "Test AdGroup",
        "Targeting": target_name,
        "Match Type": match_type,
        "Clicks": clicks,
        "Spend": spend,
        "Sales": sales,
        "Orders": orders,
        "Impressions": impressions,
        "Current Bid": bid,
        "Bid": bid,
        "Ad Group Default Bid": bid,
        "ROAS": sales / spend if spend > 0 else 0,
        "Customer Search Term": ""
    }])

# ---------------------------------------------------------
# TEST RUNNER
# ---------------------------------------------------------
def run_tests():
    print("= ================================================= =")
    print("= BID OPTIMIZER V2 TEST SUITE                       =")
    print("= ================================================= =\\n")
    
    results = []

    # ---------------------------------------------------------
    # TEST 1: Cooldown enforcement
    # ---------------------------------------------------------
    df = create_base_df("test1", "exact", 20, 10, 50, 500) # ROAS 5.0 -> Promote
    
    # Inject action from 5 days ago (should be rejected)
    c_df = pd.DataFrame([{
        "Campaign Name": "Test Campaign",
        "Ad Group Name": "Test AdGroup",
        "Targeting": "test1",
        "last_action_date": datetime.now() - timedelta(days=5)
    }])
    r_df = pd.DataFrame() # let it fallback to snapshot ROAS 5.0
    
    ex, pt, ag, au = run_optimizer_with_mocks(df, c_df, r_df)
    res = ex.iloc[0]
    pass_test = res["New Bid"] == 0.0 and "Cooldown" in res["Reason"]
    results.append(("TEST 1 - Cooldown enforcement", pass_test, res["Reason"]))

    # ---------------------------------------------------------
    # TEST 2: Cooldown pass-through
    # ---------------------------------------------------------
    df = create_base_df("test2", "exact", 20, 10, 50, 500)
    
    # Action from 20 days ago (should pass)
    c_df = pd.DataFrame([{
        "Campaign Name": "Test Campaign",
        "Ad Group Name": "Test AdGroup",
        "Targeting": "test2",
        "last_action_date": datetime.now() - timedelta(days=20)
    }])
    
    ex, pt, ag, au = run_optimizer_with_mocks(df, c_df, pd.DataFrame())
    res = ex.iloc[0]
    pass_test = res["New Bid"] > 1.0 and "Bid raised" in res["Reason"]
    results.append(("TEST 2 - Cooldown pass-through", pass_test, f"Bid: {res['New Bid']} ({res['Reason']})"))

    # ---------------------------------------------------------
    # TEST 3: Visibility boost suppression
    # ---------------------------------------------------------
    # 50 impressions, 0 orders. Should fail conversion gate.
    df = create_base_df("test3", "exact", 4, 2, 0, 50, orders=0)
    
    ex, pt, ag, au = run_optimizer_with_mocks(df, pd.DataFrame(), pd.DataFrame())
    res = ex.iloc[0]
    pass_test = res["New Bid"] == 0.0 and "Visibility Boost Suppressed" in res["Reason"]
    results.append(("TEST 3 - Visibility boost suppression", pass_test, res["Reason"]))

    # ---------------------------------------------------------
    # TEST 4: Visibility boost fires correctly
    # ---------------------------------------------------------
    # 50 impressions, 1 order. Should pass conversion gate.
    df = create_base_df("test4", "exact", 4, 2, 5, 50, orders=1)
    
    ex, pt, ag, au = run_optimizer_with_mocks(df, pd.DataFrame(), pd.DataFrame())
    res = ex.iloc[0]
    pass_test = res["New Bid"] == 1.30 and "Visibility Boost" in res["Reason"] and "Suppressed" not in res["Reason"]
    results.append(("TEST 4 - Visibility boost fires correctly", pass_test, f"Bid: {res['New Bid']} ({res['Reason']})"))

    # ---------------------------------------------------------
    # TEST 5: Thin data promote blocked
    # ---------------------------------------------------------
    # 10 clicks, ROAS 5.0 -> would normally promote, but fails 15 click gate
    df = create_base_df("test5", "exact", 10, 5, 25, 500)
    
    ex, pt, ag, au = run_optimizer_with_mocks(df, pd.DataFrame(), pd.DataFrame())
    res = ex.iloc[0]
    pass_test = res["New Bid"] == 1.0 and "Bid increase blocked" in res["Reason"] and "insufficient data" in res["Reason"]
    results.append(("TEST 5 - Thin data promote blocked", pass_test, res["Reason"]))

    # ---------------------------------------------------------
    # TEST 6: Windowed ROAS vs spike
    # ---------------------------------------------------------
    df = create_base_df("test6", "exact", 20, 10, 50, 500) # Raw ROAS = 5.0 (would promote)
    
    # 14d ROAS from DB says it actually averaged 2.0 (Target is 2.5, would bid down)
    r_df = pd.DataFrame([{
        "Campaign Name": "Test Campaign",
        "Ad Group Name": "Test AdGroup",
        "Targeting": "test6",
        "14d_avg_ROAS": 2.0
    }])
    
    ex, pt, ag, au = run_optimizer_with_mocks(df, pd.DataFrame(), r_df)
    res = ex.iloc[0]
    pass_test = res["New Bid"] < 1.0 and "Bid reduced" in res["Reason"]
    results.append(("TEST 6 - Windowed ROAS vs spike", pass_test, f"Bid: {res['New Bid']} ({res['Reason']})"))

    # ---------------------------------------------------------
    # TEST 7: Bucket ROAS multiplier
    # ---------------------------------------------------------
    # Exact Target = 2.5 * 1.0 = 2.5. Raw ROAS = 2.0. Expected Gap: 2.0/2.5 - 1 = -0.2 (Bid down)
    df_exact = create_base_df("test7a", "exact", 20, 10, 20, 500)
    
    # Auto Target = 2.5 * 0.65 = 1.625. Raw ROAS = 2.0. Expected Gap: 2.0/1.625 - 1 = +0.23 (Promote)
    df_auto = create_base_df("close-match", "auto", 20, 10, 20, 500)
    
    df_combined = pd.concat([df_exact, df_auto])
    ex, pt, ag, au = run_optimizer_with_mocks(df_combined, pd.DataFrame(), pd.DataFrame())
    
    exact_res = ex.iloc[0]
    auto_res = au.iloc[0]
    
    pass_test = "Bid reduced" in exact_res["Reason"] and "Bid raised" in auto_res["Reason"]
    msg = f"Exact ({exact_res['Reason']}) | Auto ({auto_res['Reason']})"
    results.append(("TEST 7 - Bucket ROAS multiplier", pass_test, msg))

    # ---------------------------------------------------------
    # TEST 8: Bid bounds validation
    # ---------------------------------------------------------
    # Try to bid down aggressively from 0.15 (should hit 0.30 absolute floor or min multiplier)
    # The hybrid rule: max(0.30, base_bid * 0.50)
    # Bid 0.15 -> min limit is 0.30. Since bid is ALREADY below floor, np.clip(new_bid, 0.30, max) pushes it up to 0.30.
    df = create_base_df("test8", "exact", 20, 10, 0.1, 500, bid=0.15)
    
    ex, pt, ag, au = run_optimizer_with_mocks(df, pd.DataFrame(), pd.DataFrame())
    res = ex.iloc[0]
    pass_test = res["New Bid"] == 0.30  # Snaps to min_bid_limit
    results.append(("TEST 8 - Bid bounds validation", pass_test, f"Started at 0.15, clamped to {res['New Bid']}"))

    # ---------------------------------------------------------
    # TEST 9: V2.1 INVENTORY_RISK suppresses promote
    # ---------------------------------------------------------
    df = create_base_df("test9", "exact", 20, 10, 50, 500) # ROAS 5.0 -> would promote
    
    commerce_df = pd.DataFrame([{
        "campaign_name": "Test Campaign",
        "ad_group_name": "Test AdGroup",
        "ordered_revenue": 100,
        "units_ordered": 10,
        "sessions": 50,
        "organic_cvr": 0.20,
        "days_of_supply": 5,  # TRIGGERS INVENTORY_RISK
        "product_lifecycle": "mature"
    }])
    
    ex, pt, ag, au = run_optimizer_with_mocks(df, pd.DataFrame(), pd.DataFrame(), commerce_df)
    res = ex.iloc[0]
    pass_test = res["New Bid"] == res["Current Bid"] and "inventory" in res["Reason"].lower()
    results.append(("TEST 9 - V2.1 INVENTORY_RISK suppresses promote", pass_test, res["Reason"]))

    # ---------------------------------------------------------
    # TEST 10: V2.1 HALO_ACTIVE relaxes ROAS target
    # ---------------------------------------------------------
    # Target 2.5. Raw ROAS = 2.0 (normally bid down). 
    # With HALO_ACTIVE, target becomes 2.5 * 0.8 = 2.0. ROAS matches target -> Stable.
    df = create_base_df("test10", "exact", 20, 10, 20, 500) # ROAS 2.0
    
    commerce_df_halo = pd.DataFrame([{
        "campaign_name": "Test Campaign",
        "ad_group_name": "Test AdGroup",
        "ordered_revenue": 100,
        "units_ordered": 100, # Halo triggers if total units > ad orders * 3 AND >= 30 organic units.
        "sessions": 50,
        "organic_cvr": 0.20,
        "days_of_supply": 50,
        "product_lifecycle": "mature"
    }])
    
    ex, pt, ag, au = run_optimizer_with_mocks(df, pd.DataFrame(), pd.DataFrame(), commerce_df_halo)
    res = ex.iloc[0]
    pass_test = res["New Bid"] == res["Current Bid"] and "HALO_ACTIVE" in str(res.get("Intelligence_Flags", ""))
    results.append(("TEST 10 - V2.1 HALO_ACTIVE relaxes target", pass_test, res["Reason"]))

    # ---------------------------------------------------------
    # PRINT RESULTS
    # ---------------------------------------------------------
    passed = 0
    with open('test_results_v2.txt', 'w') as f:
        f.write("BID OPTIMIZER V2 TEST RESULTS\\n")
        f.write("===============================\\n\\n")
        for i, (test_name, success, info) in enumerate(results):
            status = "PASS" if success else "FAIL"
            passed += 1 if success else 0
            
            output = f"[{status}] {test_name}\\n      Details: {info}\\n"
            print(output)
            f.write(output + "\\n")
            
        summary = f"\\nSCORE: {passed}/{len(results)} PASSED"
        print(summary)
        f.write(summary)

if __name__ == "__main__":
    run_tests()
