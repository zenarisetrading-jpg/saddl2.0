"""
Test to verify Market Drag can never have positive impact after the fix.

Bug Description:
- Dashboard was calculating market_tag based on recalculated decision_impact
- Then overwriting decision_impact with final_decision_impact from database
- This created mismatches where Market Drag showed positive impact

Fix:
- Use database market_tag when available (already calculated correctly)
- Only recalculate for old cached data
- Always copy final_decision_impact BEFORE calculating market_tag
"""

import sys
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, '/Users/zayaanyousuf/Documents/Amazon PPC/saddle/saddle/desktop')

from features.impact.data.transforms import ensure_impact_columns


def test_market_drag_never_positive():
    """Test that Market Drag rows never have positive decision_impact."""

    print("\n" + "="*80)
    print("TEST: Market Drag Category Consistency")
    print("="*80)

    # Test Case 1: Database provides market_tag (normal case)
    print("\n[Test Case 1] Database provides market_tag")
    df1 = pd.DataFrame({
        'action_type': ['BID_CHANGE', 'BID_CHANGE', 'HARVEST'],
        'target_text': ['water bottle', 'dog food', 'drying mat'],
        'before_sales': [100.0, 200.0, 150.0],
        'before_spend': [50.0, 100.0, 75.0],
        'before_clicks': [25, 50, 30],
        'observed_after_sales': [70.0, 140.0, 120.0],
        'observed_after_spend': [30.0, 60.0, 45.0],

        # Database already calculated these correctly
        'market_tag': ['Market Drag', 'Market Drag', 'Defensive Win'],
        'final_decision_impact': [-5.0, -10.0, 15.0],  # Market Drag has negative impact
        'decision_value_pct': [-5.0, -8.0, 10.0],
        'expected_trend_pct': [-30.0, -25.0, -20.0],
    })

    result1 = ensure_impact_columns(df1)

    # Verify Market Drag rows
    market_drag1 = result1[result1['market_tag'] == 'Market Drag']
    positive_drag1 = market_drag1[market_drag1['decision_impact'] > 0]

    print(f"  Market Drag rows: {len(market_drag1)}")
    print(f"  Market Drag with POSITIVE impact: {len(positive_drag1)}")

    if len(positive_drag1) > 0:
        print("  ❌ FAILED: Market Drag should never have positive impact!")
        print(positive_drag1[['target_text', 'market_tag', 'decision_impact']])
        return False
    else:
        print("  ✅ PASSED: All Market Drag rows have negative impact")

    # Test Case 2: Old cached data without market_tag (legacy case)
    print("\n[Test Case 2] Old cached data - dashboard must calculate market_tag")
    df2 = pd.DataFrame({
        'action_type': ['BID_CHANGE', 'BID_CHANGE'],
        'target_text': ['close-match', 'substitutes'],
        'before_sales': [100.0, 200.0],
        'before_spend': [50.0, 100.0],
        'before_clicks': [25, 50],
        'observed_after_sales': [70.0, 150.0],
        'observed_after_spend': [30.0, 70.0],

        # Database provided final impact but NO market_tag (old cached data)
        'final_decision_impact': [-8.0, 5.0],
    })

    result2 = ensure_impact_columns(df2)

    # Verify Market Drag rows
    market_drag2 = result2[result2['market_tag'] == 'Market Drag']
    positive_drag2 = market_drag2[market_drag2['decision_impact'] > 0]

    print(f"  Market Drag rows: {len(market_drag2)}")
    print(f"  Market Drag with POSITIVE impact: {len(positive_drag2)}")

    if len(positive_drag2) > 0:
        print("  ❌ FAILED: Market Drag should never have positive impact!")
        print(positive_drag2[['target_text', 'market_tag', 'decision_impact']])
        return False
    else:
        print("  ✅ PASSED: All Market Drag rows have negative impact")

    # Test Case 3: Verify the fix - final_decision_impact and market_tag must align
    print("\n[Test Case 3] Verify decision_impact matches market_tag category")

    all_results = pd.concat([result1, result2], ignore_index=True)

    for category in ['Offensive Win', 'Defensive Win', 'Gap', 'Market Drag']:
        cat_df = all_results[all_results['market_tag'] == category]
        if len(cat_df) == 0:
            continue

        positive_count = len(cat_df[cat_df['decision_impact'] > 0])
        negative_count = len(cat_df[cat_df['decision_impact'] < 0])
        zero_count = len(cat_df[cat_df['decision_impact'] == 0])

        print(f"\n  {category}:")
        print(f"    Positive impact: {positive_count}")
        print(f"    Negative impact: {negative_count}")
        print(f"    Zero impact: {zero_count}")

        # Market Drag and Gap should never have positive impact
        if category in ['Market Drag', 'Gap']:
            if positive_count > 0:
                print(f"    ❌ FAILED: {category} should not have positive impact!")
                return False

        # Offensive Win and Defensive Win should have positive impact
        if category in ['Offensive Win', 'Defensive Win']:
            if positive_count == 0 and len(cat_df) > 0:
                print(f"    ⚠️  WARNING: {category} should typically have positive impact")

    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED")
    print("="*80)
    return True


if __name__ == '__main__':
    success = test_market_drag_never_positive()
    sys.exit(0 if success else 1)
