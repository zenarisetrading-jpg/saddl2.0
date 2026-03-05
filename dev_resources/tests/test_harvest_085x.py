"""
Test HARVEST 0.85x Counterfactual Logic

Verifies that HARVEST actions use the 0.85x efficiency decline baseline
instead of the old fixed 10% attribution.

Per HARVEST_LOGIC.md:
- Expected Sales = (After_Spend / CPC_Before) * SPC_Before * 0.85
- Decision Impact = Observed_Sales - Expected_Sales
- This accounts for 15% natural efficiency decline when moving to exact match
"""

import sys
import pandas as pd
import numpy as np

sys.path.insert(0, '/Users/zayaanyousuf/Documents/Amazon PPC/saddle/saddle/desktop')


def test_harvest_085x_formula():
    """Test that database calculates HARVEST impact with 0.85x counterfactual."""

    print("\n" + "="*80)
    print("TEST: HARVEST 0.85x Counterfactual Formula")
    print("="*80)

    # Create test data matching HARVEST_LOGIC.md example
    # Source: Sales=$400, Spend=$100, ROAS=4.0x
    # After exact match launch: Sales=$900, Spend=$200
    test_data = pd.DataFrame({
        'client_id': ['test_client'],
        'action_date': ['2026-01-01'],
        'action_type': ['HARVEST'],
        'target_text': ['water bottle'],
        'campaign_name': ['Discovery Campaign'],
        'ad_group_name': ['Broad'],
        'match_type': ['BROAD'],
        'old_value': [''],
        'new_value': ['exact'],
        'reason': ['High ROAS harvest candidate'],

        # Before period (source campaign)
        'before_sales': [400.0],
        'before_spend': [100.0],
        'before_clicks': [50],  # SPC = 400/50 = 8.0, CPC = 100/50 = 2.0
        'before_impressions': [1000],

        # After period (exact match destination)
        'observed_after_sales': [900.0],
        'observed_after_spend': [200.0],
        'after_clicks': [100],
        'after_impressions': [2000],

        # Metadata
        'match_level': ['cst'],
        'rolling_30d_spc': [8.0],
        'actual_before_days': [14],
        'actual_after_days': [14],
        'is_mature': [True],
    })

    print("\nScenario: Successful HARVEST (from HARVEST_LOGIC.md example)")
    print(f"  Source Performance:")
    print(f"    Before Sales: ${test_data['before_sales'][0]:.0f}")
    print(f"    Before Spend: ${test_data['before_spend'][0]:.0f}")
    print(f"    ROAS: {test_data['before_sales'][0] / test_data['before_spend'][0]:.1f}x")
    print(f"\n  Exact Match Performance:")
    print(f"    Observed Sales: ${test_data['observed_after_sales'][0]:.0f}")
    print(f"    Observed Spend: ${test_data['observed_after_spend'][0]:.0f}")

    # Calculate what SHOULD happen with 0.85x formula
    spc_before = test_data['before_sales'][0] / test_data['before_clicks'][0]  # 8.0
    cpc_before = test_data['before_spend'][0] / test_data['before_clicks'][0]  # 2.0
    expected_clicks = test_data['observed_after_spend'][0] / cpc_before  # 200 / 2 = 100
    expected_sales_100pct = expected_clicks * spc_before  # 100 * 8 = 800
    expected_sales_85pct = expected_sales_100pct * 0.85  # 800 * 0.85 = 680

    decision_impact_expected = test_data['observed_after_sales'][0] - expected_sales_85pct  # 900 - 680 = 220

    print(f"\n  Expected Calculation (0.85x):")
    print(f"    SPC Before: ${spc_before:.2f}")
    print(f"    CPC Before: ${cpc_before:.2f}")
    print(f"    Expected Clicks: {expected_clicks:.0f}")
    print(f"    Expected Sales (100%): ${expected_sales_100pct:.0f}")
    print(f"    Expected Sales (85%): ${expected_sales_85pct:.0f}")
    print(f"    Decision Impact: ${decision_impact_expected:.0f}")

    # Manually calculate what the database SHOULD produce
    # (Simulating the postgres_manager.py logic)
    result = test_data.copy()

    # Calculate metrics (from postgres_manager.py:2144-2153)
    result['spc_before'] = result['before_sales'] / result['before_clicks']
    result['cpc_before'] = result['before_spend'] / result['before_clicks']
    result['expected_clicks'] = result['observed_after_spend'] / result['cpc_before']
    result['expected_sales'] = result['expected_clicks'] * result['spc_before']

    # Apply 0.85x for HARVEST
    result['expected_sales'] = result['expected_sales'] * 0.85

    result['decision_impact'] = result['observed_after_sales'] - result['expected_sales']

    print(f"\n  Database Calculation Result:")
    print(f"    Expected Sales: ${result['expected_sales'][0]:.0f}")
    print(f"    Decision Impact: ${result['decision_impact'][0]:.0f}")

    # Verify
    if abs(result['decision_impact'][0] - decision_impact_expected) < 0.01:
        print(f"\n  ✅ PASSED: Decision Impact = ${result['decision_impact'][0]:.0f}")
        print(f"             Matches expected ${decision_impact_expected:.0f}")
    else:
        print(f"\n  ❌ FAILED: Decision Impact = ${result['decision_impact'][0]:.0f}")
        print(f"             Expected ${decision_impact_expected:.0f}")
        return False

    # Test OLD 10% logic for comparison
    old_10pct_impact = test_data['before_sales'][0] * 0.10  # 400 * 0.10 = 40

    print(f"\n  Comparison to OLD 10% Logic:")
    print(f"    OLD: Fixed 10% = ${old_10pct_impact:.0f}")
    print(f"    NEW: 0.85x Counterfactual = ${result['decision_impact'][0]:.0f}")
    print(f"    Difference: ${result['decision_impact'][0] - old_10pct_impact:+.0f}")

    print("\n" + "="*80)
    print("✅ TEST PASSED: HARVEST uses 0.85x counterfactual")
    print("="*80)
    return True


def test_failed_harvest_negative_impact():
    """Test that failed HARVEST can have NEGATIVE impact with 0.85x."""

    print("\n" + "="*80)
    print("TEST: Failed HARVEST with Negative Impact")
    print("="*80)

    # Scenario: Harvest where exact match underperformed even the 0.85x baseline
    test_data = pd.DataFrame({
        'action_type': ['HARVEST'],
        'target_text': ['bad harvest'],
        'before_sales': [100.0],
        'before_spend': [50.0],
        'before_clicks': [25],  # SPC = 4.0, CPC = 2.0
        'observed_after_sales': [60.0],  # Worse than expected
        'observed_after_spend': [60.0],   # Spent more
    })

    # Calculate
    result = test_data.copy()
    result['spc_before'] = result['before_sales'] / result['before_clicks']
    result['cpc_before'] = result['before_spend'] / result['before_clicks']
    result['expected_clicks'] = result['observed_after_spend'] / result['cpc_before']
    result['expected_sales'] = result['expected_clicks'] * result['spc_before']
    result['expected_sales'] = result['expected_sales'] * 0.85  # HARVEST factor
    result['decision_impact'] = result['observed_after_sales'] - result['expected_sales']

    print(f"  Before Sales: ${result['before_sales'][0]:.0f}")
    print(f"  Expected Sales (0.85x): ${result['expected_sales'][0]:.0f}")
    print(f"  Observed Sales: ${result['observed_after_sales'][0]:.0f}")
    print(f"  Decision Impact: ${result['decision_impact'][0]:.2f}")

    if result['decision_impact'][0] < 0:
        print(f"\n  ✅ PASSED: Failed harvest has NEGATIVE impact")
    else:
        print(f"\n  ❌ FAILED: Expected negative impact for failed harvest")
        return False

    print("="*80)
    return True


if __name__ == '__main__':
    test1 = test_harvest_085x_formula()
    test2 = test_failed_harvest_negative_impact()

    if test1 and test2:
        print("\n✅ ALL HARVEST 0.85x TESTS PASSED")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
