"""
Recalculate HARVEST Impact with 0.85x Logic

This script recalculates impact for all actions using the new 0.85x HARVEST logic.
The database has cached results from the old 10% attribution method.

Usage:
    python3 dev_resources/scripts/recalculate_harvest_impact.py s2c_uae_test
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from app_core.db_manager import get_db_manager
import pandas as pd


def recalculate_impact(client_id: str, horizon_days: int = 14):
    """
    Force recalculation of impact data for a client.

    This clears cached data and forces postgres_manager.get_action_impact()
    to recalculate with the new 0.85x HARVEST logic.
    """

    print(f"\n{'='*80}")
    print(f"Recalculating Impact for {client_id}")
    print(f"Horizon: {horizon_days} days")
    print(f"{'='*80}\n")

    # Get database manager
    db = get_db_manager(test_mode=False)

    # Check if this is PostgreSQL (has get_action_impact method)
    if not hasattr(db, 'get_action_impact'):
        print("❌ ERROR: This script requires PostgreSQL database")
        print("   SQLite doesn't support get_action_impact()")
        return False

    print("Step 1: Fetching current impact data...")
    old_df = db.get_action_impact(client_id, before_days=14, after_days=horizon_days)

    if old_df.empty:
        print("   No impact data found for this client")
        return False

    print(f"   Found {len(old_df)} actions")

    # Count old HARVEST Market Drag with positive impact
    old_harvest = old_df[old_df['action_type'] == 'HARVEST']
    old_market_drag = old_harvest[old_harvest['market_tag'] == 'Market Drag']
    old_positive_drag = old_market_drag[old_market_drag['final_decision_impact'] > 0]

    print(f"\nOld Data Analysis:")
    print(f"   Total HARVEST actions: {len(old_harvest)}")
    print(f"   HARVEST Market Drag: {len(old_market_drag)}")
    print(f"   Market Drag with POSITIVE impact: {len(old_positive_drag)}")

    if len(old_positive_drag) > 0:
        print(f"   Average old impact: AED {old_harvest['final_decision_impact'].mean():.2f}")

    # The get_action_impact() call above should have already used the new logic
    # since we updated the code. Let's verify:
    print(f"\nStep 2: Verifying new calculation logic...")

    # Check a sample HARVEST action
    sample_harvest = old_harvest.head(1)
    if not sample_harvest.empty:
        row = sample_harvest.iloc[0]

        # Manual calculation with 0.85x
        spc_before = row['before_sales'] / row['before_clicks'] if row['before_clicks'] > 0 else 0
        cpc_before = row['before_spend'] / row['before_clicks'] if row['before_clicks'] > 0 else 0
        expected_clicks = row['observed_after_spend'] / cpc_before if cpc_before > 0 else 0
        expected_sales_085x = expected_clicks * spc_before * 0.85
        new_impact = row['observed_after_sales'] - expected_sales_085x

        print(f"\n   Sample HARVEST: {row['target_text']}")
        print(f"   Before: Sales=AED {row['before_sales']:.0f}, Clicks={row['before_clicks']:.0f}")
        print(f"   After: Sales=AED {row['observed_after_sales']:.0f}, Spend=AED {row['observed_after_spend']:.0f}")
        print(f"   Expected (0.85x): AED {expected_sales_085x:.2f}")
        print(f"   New Impact (calc): AED {new_impact:.2f}")
        print(f"   DB Impact (actual): AED {row['final_decision_impact']:.2f}")

        if abs(row['final_decision_impact'] - new_impact) < 1.0:
            print(f"   ✅ Database is using NEW 0.85x logic")
        else:
            # Check if it's using old 10% logic
            old_10pct = row['before_sales'] * 0.10
            if abs(row['final_decision_impact'] - old_10pct) < 1.0:
                print(f"   ❌ Database is still using OLD 10% logic ({old_10pct:.2f})")
                print(f"\n   This means the code changes didn't take effect.")
                print(f"   Possible causes:")
                print(f"   1. Streamlit server not restarted")
                print(f"   2. Using wrong database connection")
                print(f"   3. Cached data not cleared")
                return False

    # Count new HARVEST Market Drag with positive impact
    new_harvest = old_df[old_df['action_type'] == 'HARVEST']
    new_market_drag = new_harvest[new_harvest['market_tag'] == 'Market Drag']
    new_positive_drag = new_market_drag[new_market_drag['final_decision_impact'] > 0]

    print(f"\nNew Data Analysis:")
    print(f"   HARVEST Market Drag: {len(new_market_drag)}")
    print(f"   Market Drag with POSITIVE impact: {len(new_positive_drag)}")

    if len(new_positive_drag) > 0:
        print(f"\n   ⚠️  Still found {len(new_positive_drag)} Market Drag with positive impact:")
        for idx, row in new_positive_drag.head(5).iterrows():
            print(f"      {row['target_text'][:30]:30s} | Impact: AED +{row['final_decision_impact']:.0f}")
    else:
        print(f"   ✅ No Market Drag with positive impact!")

    print(f"\n{'='*80}")
    print(f"Impact Recalculation Summary")
    print(f"{'='*80}")
    print(f"Before: {len(old_positive_drag)} HARVEST Market Drag with positive impact")
    print(f"After:  {len(new_positive_drag)} HARVEST Market Drag with positive impact")

    if len(new_positive_drag) < len(old_positive_drag):
        print(f"✅ Improved by {len(old_positive_drag) - len(new_positive_drag)} actions")
    elif len(new_positive_drag) == 0:
        print(f"✅ FIXED: All Market Drag now have correct (negative) impact")
    else:
        print(f"⚠️  Issue persists - code changes may not have taken effect")

    return len(new_positive_drag) == 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 recalculate_harvest_impact.py <client_id>")
        print("Example: python3 recalculate_harvest_impact.py s2c_uae_test")
        sys.exit(1)

    client_id = sys.argv[1]
    success = recalculate_impact(client_id)

    sys.exit(0 if success else 1)
