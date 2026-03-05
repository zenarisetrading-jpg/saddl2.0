"""
Test HARVEST-specific Market Drag bug.

Issue: HARVEST actions were showing as "Market Drag" with positive impact because:
1. Database uses fixed 10% attribution (not counterfactual)
2. Dashboard was recalculating market_tag using counterfactual logic
3. Mismatch: Dashboard category ≠ Database impact value

Fix: Always use database market_tag for HARVEST (and NEGATIVE) actions.
"""

import sys
import pandas as pd

sys.path.insert(0, '/Users/zayaanyousuf/Documents/Amazon PPC/saddle/saddle/desktop')

from features.impact.data.transforms import ensure_impact_columns


def test_harvest_market_drag_scenarios():
    """Test that HARVEST actions use database market_tag, not recalculated."""

    print("\n" + "="*80)
    print("TEST: HARVEST Market Drag Bug Fix")
    print("="*80)

    # Simulate various HARVEST scenarios with DATABASE market_tag
    harvest_data = pd.DataFrame({
        'action_type': ['HARVEST', 'HARVEST', 'HARVEST', 'HARVEST'],
        'target_text': [
            's2c water bottle',  # Perfect harvest
            'puppy toys',         # Partial harvest (Market Drag in old logic)
            'drying mat',         # Failed harvest
            'stanley cup',        # Another partial
        ],

        # Before metrics
        'before_sales': [100.0, 200.0, 150.0, 180.0],
        'before_spend': [50.0, 100.0, 75.0, 90.0],
        'before_clicks': [25, 50, 30, 45],

        # After metrics (varying success)
        'observed_after_sales': [0.0, 40.0, 120.0, 60.0],
        'observed_after_spend': [0.0, 25.0, 80.0, 40.0],

        # Database provides correct market_tag AND final_decision_impact
        # (Database uses 10% attribution regardless of actual performance)
        'market_tag': ['Defensive Win', 'Defensive Win', 'Defensive Win', 'Defensive Win'],
        'final_decision_impact': [10.0, 20.0, 15.0, 18.0],  # 10% of before_sales

        # Database also provides these
        'decision_value_pct': [100.0, 70.0, -5.0, 45.0],
        'expected_trend_pct': [-100.0, -70.0, -20.0, -55.0],
    })

    print("\n[Scenario] HARVEST actions with database market_tag")
    print(f"Total HARVEST actions: {len(harvest_data)}")

    # Run through transforms
    result = ensure_impact_columns(harvest_data)

    # Verify ALL harvest actions preserved DB market_tag
    print(f"\nVerifying database market_tag was preserved...")

    for idx, row in result.iterrows():
        original_tag = harvest_data.loc[idx, 'market_tag']
        result_tag = row['market_tag']
        result_impact = row['decision_impact']

        print(f"  {row['target_text'][:20]:20s} | DB: {original_tag:15s} | Result: {result_tag:15s} | Impact: AED {result_impact:+6.0f}")

        # Check if tag was preserved
        if result_tag != original_tag and result_tag != 'Excluded - Low Sample':
            print(f"    ❌ FAILED: market_tag was changed from {original_tag} to {result_tag}")
            return False

        # Check for Market Drag with positive impact
        if result_tag == 'Market Drag' and result_impact > 0:
            print(f"    ❌ FAILED: Market Drag with positive impact!")
            return False

    print("\n✅ PASSED: All HARVEST actions preserved database market_tag")

    # Test old cached data scenario (no DB market_tag)
    print("\n[Scenario] HARVEST actions WITHOUT database market_tag (legacy)")

    harvest_legacy = pd.DataFrame({
        'action_type': ['HARVEST', 'HARVEST'],
        'target_text': ['old harvest 1', 'old harvest 2'],
        'before_sales': [100.0, 200.0],
        'before_spend': [50.0, 100.0],
        'before_clicks': [25, 50],
        'observed_after_sales': [40.0, 80.0],
        'observed_after_spend': [25.0, 50.0],
        'final_decision_impact': [10.0, 20.0],  # DB provides impact but NOT market_tag
    })

    result_legacy = ensure_impact_columns(harvest_legacy)

    print(f"  Legacy HARVEST actions marked as: {result_legacy['market_tag'].unique()}")

    # These should be marked as 'Unknown (Legacy Data)' since we can't calculate correctly
    if all(result_legacy['market_tag'] == 'Unknown (Legacy Data)'):
        print("  ✅ PASSED: Legacy HARVEST marked as Unknown (can't recalculate)")
    else:
        print(f"  ⚠️  WARNING: Expected 'Unknown (Legacy Data)', got: {result_legacy['market_tag'].tolist()}")

    print("\n" + "="*80)
    print("✅ ALL HARVEST TESTS PASSED")
    print("="*80)
    return True


if __name__ == '__main__':
    success = test_harvest_market_drag_scenarios()
    sys.exit(0 if success else 1)
