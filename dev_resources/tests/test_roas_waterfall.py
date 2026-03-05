#!/usr/bin/env python3
"""
Test ROAS Waterfall Component

Validates the ROAS waterfall calculation logic against expected values
from Impact Model v3.3 specification.
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from features.impact.components.roas_waterfall import calculate_roas_waterfall


def test_basic_calculation():
    """Test basic waterfall calculation with known values."""
    print("\n" + "="*70)
    print("TEST 1: Basic ROAS Waterfall Calculation")
    print("="*70)

    # Create sample data
    df = pd.DataFrame({
        'before_spend': [1000, 500],
        'before_sales': [4000, 2000],
        'before_clicks': [200, 100],
        'observed_after_spend': [1200, 600],
        'observed_after_sales': [4200, 1800],  # Mixed results
        'after_clicks': [240, 120],
    })

    # Decision impact (from v3.3)
    decision_impact = -300  # Negative impact

    # Calculate waterfall
    result = calculate_roas_waterfall(df, decision_impact)

    # Print results
    print(f"\n📊 Input Summary:")
    print(f"  Before: {result['before_sales']:,.0f} sales / {result['before_spend']:,.0f} spend = {result['baseline_roas']:.2f}x ROAS")
    print(f"  After:  {result['after_sales']:,.0f} sales / {result['after_spend']:,.0f} spend = {result['actual_roas']:.2f}x ROAS")
    print(f"  Total Change: {result['total_change']:+.2f}x")

    print(f"\n🔍 Waterfall Components:")
    print(f"  1. Market Effect (SPC {result['spc_change_pct']:+.1f}%): {result['market_effect']:+.2f}x")
    print(f"  2. CPC Effect ({result['cpc_change_pct']:+.1f}%):       {result['cpc_effect']:+.2f}x")
    print(f"  3. Decision Effect (${decision_impact:,.0f}):    {result['decision_effect']:+.2f}x")
    print(f"  4. Residual (unexplained):       {result['residual']:+.2f}x")

    print(f"\n📈 Attribution Breakdown:")
    print(f"  External (Market + CPC): {result['external_effect']:+.2f}x ({result['external_pct']:.0f}%)")
    print(f"  Internal (Decisions):    {result['internal_effect']:+.2f}x ({result['internal_pct']:.0f}%)")

    # Validation: sum should equal total change (within rounding)
    total_components = result['market_effect'] + result['cpc_effect'] + result['decision_effect'] + result['residual']
    expected_actual = result['baseline_roas'] + total_components

    print(f"\n✅ Validation:")
    print(f"  Expected Actual ROAS: {expected_actual:.2f}x")
    print(f"  Calculated Actual ROAS: {result['actual_roas']:.2f}x")
    print(f"  Difference: {abs(expected_actual - result['actual_roas']):.4f}x")

    assert abs(expected_actual - result['actual_roas']) < 0.01, "Waterfall components don't sum to actual ROAS!"

    print("\n✅ TEST 1 PASSED")
    return result


def test_spc_drop_scenario():
    """Test scenario where market SPC drops significantly."""
    print("\n" + "="*70)
    print("TEST 2: Market SPC Drop Scenario")
    print("="*70)

    # Simulate 12% SPC drop (market headwind)
    df = pd.DataFrame({
        'before_spend': [1000],
        'before_sales': [5000],   # SPC = 5000/100 = 50
        'before_clicks': [100],
        'observed_after_spend': [1000],
        'observed_after_sales': [4400],  # SPC = 4400/100 = 44 (-12%)
        'after_clicks': [100],  # Same clicks
    })

    decision_impact = 0  # No decision impact

    result = calculate_roas_waterfall(df, decision_impact)

    print(f"\n📊 Scenario: Market SPC dropped {result['spc_change_pct']:.1f}%")
    print(f"  Baseline ROAS: {result['baseline_roas']:.2f}x")
    print(f"  Actual ROAS: {result['actual_roas']:.2f}x")
    print(f"  Market Effect: {result['market_effect']:+.2f}x ({result['market_pct_of_change']:.0f}% of change)")

    # Market effect should dominate
    assert abs(result['spc_change_pct'] - (-12.0)) < 1.0, "SPC change calculation incorrect"
    assert abs(result['market_pct_of_change']) > 90, "Market effect should dominate in SPC drop scenario"

    print("\n✅ TEST 2 PASSED")


def test_cpc_increase_scenario():
    """Test scenario where CPC increases (efficiency drops)."""
    print("\n" + "="*70)
    print("TEST 3: CPC Increase Scenario")
    print("="*70)

    # Simulate CPC increase
    df = pd.DataFrame({
        'before_spend': [1000],  # CPC = 1000/100 = 10
        'before_sales': [5000],
        'before_clicks': [100],
        'observed_after_spend': [1200],  # CPC = 1200/100 = 12 (+20%)
        'observed_after_sales': [5000],  # Same SPC
        'after_clicks': [100],
    })

    decision_impact = 0

    result = calculate_roas_waterfall(df, decision_impact)

    print(f"\n📊 Scenario: CPC increased {result['cpc_change_pct']:+.1f}%")
    print(f"  Baseline ROAS: {result['baseline_roas']:.2f}x")
    print(f"  Actual ROAS: {result['actual_roas']:.2f}x")
    print(f"  CPC Effect: {result['cpc_effect']:+.2f}x ({result['cpc_pct_of_change']:.0f}% of change)")

    # CPC effect should be negative and dominate
    assert result['cpc_effect'] < 0, "CPC increase should have negative effect"
    assert abs(result['cpc_pct_of_change']) > 80, "CPC effect should dominate in CPC increase scenario"

    print("\n✅ TEST 3 PASSED")


def test_decision_impact_scenario():
    """Test scenario where optimization decisions drive change."""
    print("\n" + "="*70)
    print("TEST 4: Decision Impact Scenario")
    print("="*70)

    # Stable market and CPC, but positive decision impact
    df = pd.DataFrame({
        'before_spend': [1000],
        'before_sales': [4000],  # 4x ROAS
        'before_clicks': [100],
        'observed_after_spend': [1000],
        'observed_after_sales': [4500],  # Better sales
        'after_clicks': [100],  # Same clicks
    })

    decision_impact = 500  # Strong positive decision impact

    result = calculate_roas_waterfall(df, decision_impact)

    print(f"\n📊 Scenario: Strong optimization decisions (+${decision_impact:,.0f})")
    print(f"  Baseline ROAS: {result['baseline_roas']:.2f}x")
    print(f"  Actual ROAS: {result['actual_roas']:.2f}x")
    print(f"  Decision Effect: {result['decision_effect']:+.2f}x ({result['decision_pct_of_change']:.0f}% of change)")

    # Decision effect should be positive
    assert result['decision_effect'] > 0, "Positive decision impact should have positive effect"

    print("\n✅ TEST 4 PASSED")


def test_zero_spend_handling():
    """Test that zero spend is handled gracefully."""
    print("\n" + "="*70)
    print("TEST 5: Zero Spend Edge Case")
    print("="*70)

    df = pd.DataFrame({
        'before_spend': [0],
        'before_sales': [0],
        'before_clicks': [0],
        'observed_after_spend': [100],
        'observed_after_sales': [400],
        'after_clicks': [10],
    })

    decision_impact = 0

    result = calculate_roas_waterfall(df, decision_impact)

    print(f"\n📊 Zero spend scenario:")
    print(f"  Baseline ROAS: {result['baseline_roas']:.2f}x")
    print(f"  Actual ROAS: {result['actual_roas']:.2f}x")

    # Should not crash
    assert result['baseline_roas'] == 0, "Zero spend should yield zero baseline ROAS"

    print("\n✅ TEST 5 PASSED")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print("🧪 ROAS WATERFALL COMPONENT TESTS")
    print("="*70)

    try:
        test_basic_calculation()
        test_spc_drop_scenario()
        test_cpc_increase_scenario()
        test_decision_impact_scenario()
        test_zero_spend_handling()

        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        return True

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
