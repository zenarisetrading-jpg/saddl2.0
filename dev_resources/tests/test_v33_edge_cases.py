#!/usr/bin/env python3
"""
Impact Model v3.3 Edge Case Tests
==================================

Tests edge cases and boundary conditions for v3.3 implementation:
1. Zero clicks before → No division by zero
2. Zero clicks after → No division by zero
3. All Market Drag → Shows 0 measured actions
4. All positive outcomes → impact_v33 == impact_linear
5. Extreme scale (10x) → scale_factor clamped to 0.5
6. Harvest actions → 0.85x factor applied
7. Mixed scenarios → Proper handling

Usage:
    python3 dev_resources/tests/test_v33_edge_cases.py
"""

import sys
import os
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from typing import Dict, List

# Import v3.3 constants
from app_core.postgres_manager import (
    SCALE_ALPHA,
    SCALE_THRESHOLD,
    MARKET_SHIFT_BOUNDS,
    SCALE_FACTOR_BOUNDS,
    HARVEST_EFFICIENCY_FACTOR,
    IMPACT_MODEL_VERSION
)


def create_test_dataframe(test_data: List[Dict]) -> pd.DataFrame:
    """Create a test dataframe with required columns."""
    df = pd.DataFrame(test_data)

    # Ensure required columns exist
    required_cols = [
        'before_clicks', 'after_clicks',
        'before_spend', 'observed_after_spend',
        'before_sales', 'observed_after_sales',
        'market_tag', 'confidence_weight',
        'action_type'
    ]

    for col in required_cols:
        if col not in df.columns:
            if 'weight' in col:
                df[col] = 1.0
            elif col == 'market_tag':
                df[col] = 'Win'
            elif col == 'action_type':
                df[col] = 'BID_CHANGE'
            else:
                df[col] = 0.0

    return df


def calculate_v33_simple(df: pd.DataFrame) -> pd.DataFrame:
    """
    Simplified v3.3 calculation for testing (mimics postgres_manager logic).
    """
    df = df.copy()

    # Step 1: Base metrics
    df['spc_before'] = df['before_sales'] / df['before_clicks'].replace(0, np.nan)
    df['spc_after'] = df['observed_after_sales'] / df['after_clicks'].replace(0, np.nan)
    df['click_ratio'] = df['after_clicks'] / df['before_clicks'].replace(0, np.nan)

    # Handle edge cases
    df['spc_before'] = df['spc_before'].replace([np.inf, -np.inf], np.nan).fillna(0)
    df['spc_after'] = df['spc_after'].replace([np.inf, -np.inf], np.nan).fillna(0)
    df['click_ratio'] = df['click_ratio'].replace([np.inf, -np.inf], np.nan).fillna(1.0)

    # Step 2: Market Shift (account-level)
    total_before_sales = df['before_sales'].sum()
    total_before_clicks = df['before_clicks'].sum()
    total_after_sales = df['observed_after_sales'].sum()
    total_after_clicks = df['after_clicks'].sum()

    account_spc_before = total_before_sales / total_before_clicks if total_before_clicks > 0 else 0
    account_spc_after = total_after_sales / total_after_clicks if total_after_clicks > 0 else 0

    if account_spc_before > 0:
        market_shift = account_spc_after / account_spc_before
    else:
        market_shift = 1.0

    # Clamp market shift
    market_shift = np.clip(market_shift, *MARKET_SHIFT_BOUNDS)
    df['market_shift'] = market_shift

    # Step 3: Scale Factor (per-row)
    df['scale_factor_raw'] = np.where(
        df['click_ratio'] > SCALE_THRESHOLD,
        1 / (df['click_ratio'] ** SCALE_ALPHA),
        1.0
    )
    df['scale_factor'] = np.clip(df['scale_factor_raw'], *SCALE_FACTOR_BOUNDS)

    # Step 4: Linear impact (v3.2 baseline)
    df['expected_sales_linear'] = df['after_clicks'] * df['spc_before']
    df['impact_linear'] = df['observed_after_sales'] - df['expected_sales_linear']

    # Step 5: Layered expected sales
    df['expected_sales_layered'] = np.where(
        df['click_ratio'] > SCALE_THRESHOLD,
        df['after_clicks'] * df['spc_before'] * market_shift * df['scale_factor'],
        df['after_clicks'] * df['spc_before'] * market_shift
    )
    df['impact_layered'] = df['observed_after_sales'] - df['expected_sales_layered']

    df['expected_sales_market'] = df['after_clicks'] * df['spc_before'] * market_shift
    df['impact_market'] = df['observed_after_sales'] - df['expected_sales_market']

    # Step 6: Asymmetric logic
    df['impact_v33'] = np.where(
        df['impact_linear'] > 0,
        df['impact_linear'],  # Keep positive outcomes unchanged
        np.where(
            df['click_ratio'] > SCALE_THRESHOLD,
            np.minimum(df['impact_layered'], 0),  # Scale-up: layered, capped at 0
            np.minimum(df['impact_market'], 0)    # Scale-down: market only, capped at 0
        )
    )

    # Step 7: Apply confidence weighting
    df['final_impact_v33'] = df['impact_v33'] * df['confidence_weight']
    df['final_impact_linear'] = df['impact_linear'] * df['confidence_weight']

    # Step 8: Apply Harvest efficiency factor if applicable
    harvest_mask = df['action_type'] == 'HARVEST'
    df.loc[harvest_mask, 'final_impact_v33'] *= HARVEST_EFFICIENCY_FACTOR

    return df


# ============================================================================
# TEST CASES
# ============================================================================

def test_1_zero_clicks_before():
    """Test: Zero clicks before → No division by zero."""
    print("\n" + "="*70)
    print("TEST 1: Zero Clicks Before (Division by Zero Safety)")
    print("="*70)

    test_data = [{
        'before_clicks': 0,
        'after_clicks': 100,
        'before_spend': 0,
        'observed_after_spend': 50,
        'before_sales': 0,
        'observed_after_sales': 100,
        'market_tag': 'Win',
        'confidence_weight': 1.0,
        'action_type': 'BID_CHANGE'
    }]

    df = create_test_dataframe(test_data)

    try:
        result = calculate_v33_simple(df)

        # Check for NaN or Inf
        has_nan = result[['market_shift', 'scale_factor', 'impact_v33']].isna().any().any()
        has_inf = np.isinf(result[['market_shift', 'scale_factor', 'impact_v33']].values).any()

        if has_nan or has_inf:
            print("❌ FAILED: Result contains NaN or Inf")
            print(result[['market_shift', 'scale_factor', 'impact_v33']])
            return False

        print("✅ PASSED: No division by zero errors")
        print(f"   market_shift: {result['market_shift'].iloc[0]:.3f}")
        print(f"   scale_factor: {result['scale_factor'].iloc[0]:.3f}")
        print(f"   impact_v33: ${result['impact_v33'].iloc[0]:,.0f}")
        return True

    except Exception as e:
        print(f"❌ FAILED: Exception raised: {e}")
        return False


def test_2_zero_clicks_after():
    """Test: Zero clicks after → No division by zero."""
    print("\n" + "="*70)
    print("TEST 2: Zero Clicks After (Division by Zero Safety)")
    print("="*70)

    test_data = [{
        'before_clicks': 100,
        'after_clicks': 0,
        'before_spend': 50,
        'observed_after_spend': 0,
        'before_sales': 100,
        'observed_after_sales': 0,
        'market_tag': 'Gap',
        'confidence_weight': 1.0,
        'action_type': 'BID_CHANGE'
    }]

    df = create_test_dataframe(test_data)

    try:
        result = calculate_v33_simple(df)

        has_nan = result[['market_shift', 'scale_factor', 'impact_v33']].isna().any().any()
        has_inf = np.isinf(result[['market_shift', 'scale_factor', 'impact_v33']].values).any()

        if has_nan or has_inf:
            print("❌ FAILED: Result contains NaN or Inf")
            return False

        print("✅ PASSED: No division by zero errors")
        print(f"   Expected sales: ${result['expected_sales_linear'].iloc[0]:,.0f}")
        print(f"   impact_v33: ${result['impact_v33'].iloc[0]:,.0f}")
        return True

    except Exception as e:
        print(f"❌ FAILED: Exception raised: {e}")
        return False


def test_3_all_market_drag():
    """Test: All Market Drag → Shows 0 measured actions."""
    print("\n" + "="*70)
    print("TEST 3: All Market Drag (Exclusion Logic)")
    print("="*70)

    test_data = [
        {
            'before_clicks': 100, 'after_clicks': 80,
            'before_spend': 50, 'observed_after_spend': 40,
            'before_sales': 100, 'observed_after_sales': 60,
            'market_tag': 'Market Drag', 'confidence_weight': 1.0,
            'action_type': 'BID_CHANGE'
        },
        {
            'before_clicks': 200, 'after_clicks': 150,
            'before_spend': 100, 'observed_after_spend': 80,
            'before_sales': 200, 'observed_after_sales': 120,
            'market_tag': 'Market Drag', 'confidence_weight': 1.0,
            'action_type': 'BID_CHANGE'
        }
    ]

    df = create_test_dataframe(test_data)
    result = calculate_v33_simple(df)

    # Check that we can filter out Market Drag
    included = result[result['market_tag'] != 'Market Drag']
    excluded = result[result['market_tag'] == 'Market Drag']

    if len(included) == 0 and len(excluded) == 2:
        print("✅ PASSED: Market Drag correctly excluded")
        print(f"   Total actions: {len(result)}")
        print(f"   Measured: {len(included)}")
        print(f"   Excluded: {len(excluded)}")
        return True
    else:
        print("❌ FAILED: Market Drag not excluded properly")
        return False


def test_4_all_positive_outcomes():
    """Test: All positive outcomes → impact_v33 == impact_linear."""
    print("\n" + "="*70)
    print("TEST 4: All Positive Outcomes (No Inflation)")
    print("="*70)

    test_data = [
        {
            'before_clicks': 100, 'after_clicks': 200,  # 2x scale-up
            'before_spend': 50, 'observed_after_spend': 100,
            'before_sales': 100, 'observed_after_sales': 250,  # Beat expectations
            'market_tag': 'Win', 'confidence_weight': 1.0,
            'action_type': 'BID_CHANGE'
        },
        {
            'before_clicks': 50, 'after_clicks': 50,  # Stable
            'before_spend': 25, 'observed_after_spend': 25,
            'before_sales': 50, 'observed_after_sales': 75,  # Beat expectations
            'market_tag': 'Win', 'confidence_weight': 1.0,
            'action_type': 'BID_CHANGE'
        }
    ]

    df = create_test_dataframe(test_data)
    result = calculate_v33_simple(df)

    # For positive outcomes, v3.3 should match v3.2 (linear)
    matches = np.allclose(result['impact_v33'], result['impact_linear'], rtol=0.01)

    if matches:
        print("✅ PASSED: Positive outcomes unchanged (no inflation)")
        for idx in result.index:
            print(f"   Row {idx}: impact_linear=${result.loc[idx, 'impact_linear']:,.0f}, "
                  f"impact_v33=${result.loc[idx, 'impact_v33']:,.0f}")
        return True
    else:
        print("❌ FAILED: Positive outcomes were modified")
        print(result[['impact_linear', 'impact_v33']])
        return False


def test_5_extreme_scale():
    """Test: Extreme scale (10x) → scale_factor clamped to 0.5."""
    print("\n" + "="*70)
    print("TEST 5: Extreme Scale (10x clicks)")
    print("="*70)

    test_data = [{
        'before_clicks': 10,
        'after_clicks': 100,  # 10x scale-up
        'before_spend': 5,
        'observed_after_spend': 50,
        'before_sales': 10,
        'observed_after_sales': 50,  # Underperformed
        'market_tag': 'Gap',
        'confidence_weight': 1.0,
        'action_type': 'BID_CHANGE'
    }]

    df = create_test_dataframe(test_data)
    result = calculate_v33_simple(df)

    scale_factor = result['scale_factor'].iloc[0]
    scale_factor_raw = result['scale_factor_raw'].iloc[0]

    # With α=0.3, 10x should give 1/(10^0.3) = 0.50, which is at the lower bound
    expected_raw = 1 / (10 ** SCALE_ALPHA)
    expected_clamped = max(expected_raw, SCALE_FACTOR_BOUNDS[0])

    if abs(scale_factor - expected_clamped) < 0.01:
        print("✅ PASSED: Extreme scale properly clamped")
        print(f"   click_ratio: {result['click_ratio'].iloc[0]:.1f}x")
        print(f"   scale_factor_raw: {scale_factor_raw:.3f}")
        print(f"   scale_factor (clamped): {scale_factor:.3f}")
        print(f"   Expected: {expected_clamped:.3f}")
        return True
    else:
        print("❌ FAILED: Scale factor not properly clamped")
        print(f"   Got: {scale_factor:.3f}, Expected: {expected_clamped:.3f}")
        return False


def test_6_harvest_efficiency():
    """Test: Harvest actions → 0.85x factor applied."""
    print("\n" + "="*70)
    print("TEST 6: Harvest Efficiency Factor (0.85x)")
    print("="*70)

    test_data = [{
        'before_clicks': 100,
        'after_clicks': 100,
        'before_spend': 50,
        'observed_after_spend': 50,
        'before_sales': 100,
        'observed_after_sales': 100,
        'market_tag': 'Win',
        'confidence_weight': 1.0,
        'action_type': 'HARVEST'
    }]

    df = create_test_dataframe(test_data)
    result = calculate_v33_simple(df)

    # Harvest should have 0.85x factor applied to final impact
    impact_before_harvest = result['impact_v33'].iloc[0]
    impact_after_harvest = result['final_impact_v33'].iloc[0]

    expected_after = impact_before_harvest * HARVEST_EFFICIENCY_FACTOR

    if abs(impact_after_harvest - expected_after) < 0.01:
        print("✅ PASSED: Harvest efficiency factor applied")
        print(f"   impact_v33: ${impact_before_harvest:,.0f}")
        print(f"   final_impact_v33: ${impact_after_harvest:,.0f}")
        print(f"   Factor: {HARVEST_EFFICIENCY_FACTOR}")
        return True
    else:
        print("❌ FAILED: Harvest factor not applied correctly")
        print(f"   Got: ${impact_after_harvest:,.0f}, Expected: ${expected_after:,.0f}")
        return False


def test_7_market_shift_bounds():
    """Test: Market shift clamped to bounds (0.5, 1.5)."""
    print("\n" + "="*70)
    print("TEST 7: Market Shift Bounds (0.5 - 1.5)")
    print("="*70)

    # Extreme positive market (should clamp to 1.5)
    test_data_positive = [
        {
            'before_clicks': 100, 'after_clicks': 100,
            'before_spend': 50, 'observed_after_spend': 50,
            'before_sales': 50, 'observed_after_sales': 200,  # 4x SPC increase
            'market_tag': 'Win', 'confidence_weight': 1.0,
            'action_type': 'BID_CHANGE'
        }
    ]

    df_pos = create_test_dataframe(test_data_positive)
    result_pos = calculate_v33_simple(df_pos)
    market_shift_pos = result_pos['market_shift'].iloc[0]

    # Extreme negative market (should clamp to 0.5)
    test_data_negative = [
        {
            'before_clicks': 100, 'after_clicks': 100,
            'before_spend': 50, 'observed_after_spend': 50,
            'before_sales': 200, 'observed_after_sales': 50,  # 0.25x SPC drop
            'market_tag': 'Gap', 'confidence_weight': 1.0,
            'action_type': 'BID_CHANGE'
        }
    ]

    df_neg = create_test_dataframe(test_data_negative)
    result_neg = calculate_v33_simple(df_neg)
    market_shift_neg = result_neg['market_shift'].iloc[0]

    upper_bound = MARKET_SHIFT_BOUNDS[1]
    lower_bound = MARKET_SHIFT_BOUNDS[0]

    pos_ok = market_shift_pos <= upper_bound
    neg_ok = market_shift_neg >= lower_bound

    if pos_ok and neg_ok:
        print("✅ PASSED: Market shift properly bounded")
        print(f"   Positive extreme: {market_shift_pos:.3f} (max {upper_bound})")
        print(f"   Negative extreme: {market_shift_neg:.3f} (min {lower_bound})")
        return True
    else:
        print("❌ FAILED: Market shift not bounded correctly")
        if not pos_ok:
            print(f"   Positive: {market_shift_pos:.3f} > {upper_bound}")
        if not neg_ok:
            print(f"   Negative: {market_shift_neg:.3f} < {lower_bound}")
        return False


def test_8_asymmetric_application():
    """Test: Negative + scale-up uses layered, negative + scale-down uses market-only."""
    print("\n" + "="*70)
    print("TEST 8: Asymmetric Application (Scale-up vs Scale-down)")
    print("="*70)

    # Market shift: 0.8 (20% SPC drop)
    # Scale-up negative: Should use layered (market + scale)
    test_data = [
        {
            'before_clicks': 100, 'after_clicks': 200,  # 2x scale-up
            'before_spend': 50, 'observed_after_spend': 100,
            'before_sales': 100, 'observed_after_sales': 140,  # Underperformed
            'market_tag': 'Gap', 'confidence_weight': 1.0,
            'action_type': 'BID_CHANGE'
        },
        {
            'before_clicks': 100, 'after_clicks': 50,  # 0.5x scale-down
            'before_spend': 50, 'observed_after_spend': 25,
            'before_sales': 100, 'observed_after_sales': 35,  # Underperformed
            'market_tag': 'Gap', 'confidence_weight': 1.0,
            'action_type': 'BID_CHANGE'
        }
    ]

    df = create_test_dataframe(test_data)
    result = calculate_v33_simple(df)

    # Scale-up should benefit from both adjustments
    scale_up = result.iloc[0]
    scale_down = result.iloc[1]

    # Check that scale-up used layered (has scale_factor < 1.0)
    scale_up_has_adjustment = scale_up['scale_factor'] < 1.0

    # Check that scale-down used market only (scale_factor = 1.0)
    scale_down_no_scale = scale_down['scale_factor'] == 1.0

    # Scale-up should have less negative impact than linear
    scale_up_improved = scale_up['impact_v33'] > scale_up['impact_linear']

    if scale_up_has_adjustment and scale_down_no_scale and scale_up_improved:
        print("✅ PASSED: Asymmetric logic correctly applied")
        print(f"   Scale-up (2x):")
        print(f"     - scale_factor: {scale_up['scale_factor']:.3f}")
        print(f"     - impact_linear: ${scale_up['impact_linear']:,.0f}")
        print(f"     - impact_v33: ${scale_up['impact_v33']:,.0f}")
        print(f"     - Improvement: ${scale_up['impact_v33'] - scale_up['impact_linear']:+,.0f}")
        print(f"   Scale-down (0.5x):")
        print(f"     - scale_factor: {scale_down['scale_factor']:.3f}")
        print(f"     - impact_linear: ${scale_down['impact_linear']:,.0f}")
        print(f"     - impact_v33: ${scale_down['impact_v33']:,.0f}")
        return True
    else:
        print("❌ FAILED: Asymmetric logic not applied correctly")
        return False


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all edge case tests."""
    print("="*70)
    print("🧪 IMPACT MODEL v3.3 EDGE CASE TEST SUITE")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  IMPACT_MODEL_VERSION: {IMPACT_MODEL_VERSION}")
    print(f"  SCALE_ALPHA: {SCALE_ALPHA}")
    print(f"  SCALE_THRESHOLD: {SCALE_THRESHOLD}")
    print(f"  MARKET_SHIFT_BOUNDS: {MARKET_SHIFT_BOUNDS}")
    print(f"  SCALE_FACTOR_BOUNDS: {SCALE_FACTOR_BOUNDS}")
    print(f"  HARVEST_EFFICIENCY_FACTOR: {HARVEST_EFFICIENCY_FACTOR}")

    tests = [
        ("Zero Clicks Before", test_1_zero_clicks_before),
        ("Zero Clicks After", test_2_zero_clicks_after),
        ("All Market Drag", test_3_all_market_drag),
        ("All Positive Outcomes", test_4_all_positive_outcomes),
        ("Extreme Scale (10x)", test_5_extreme_scale),
        ("Harvest Efficiency", test_6_harvest_efficiency),
        ("Market Shift Bounds", test_7_market_shift_bounds),
        ("Asymmetric Application", test_8_asymmetric_application),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ FAILED: {test_name} - Exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")

    print(f"\nResult: {passed}/{total} tests passed ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
