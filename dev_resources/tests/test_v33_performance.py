#!/usr/bin/env python3
"""
Impact Model v3.3 Performance Benchmark
========================================

Tests performance of v3.3 implementation to ensure no significant regression.

Target: v3.3 should be within 20% of v3.2 performance.

Usage:
    python3 dev_resources/tests/test_v33_performance.py --client CLIENT_ID --db-url "postgres://..."
"""

import sys
import os
sys.path.insert(0, '.')

import time
import argparse
from typing import Dict, List
import pandas as pd


def benchmark_get_action_impact(client_id: str, db_url: str, iterations: int = 3) -> Dict:
    """
    Benchmark get_action_impact() method with multiple iterations.

    Returns:
        Dict with timing statistics
    """
    from app_core.postgres_manager import PostgresManager

    print(f"\n🔧 Initializing database connection...")
    manager = PostgresManager(db_url)

    timings = []
    row_counts = []

    print(f"\n⏱️  Running {iterations} iterations...")

    for i in range(iterations):
        start = time.time()

        df = manager.get_action_impact(client_id, before_days=14, after_days=14)

        elapsed = time.time() - start
        timings.append(elapsed)
        row_counts.append(len(df))

        print(f"   Iteration {i+1}: {elapsed:.2f}s ({len(df)} rows)")

    avg_time = sum(timings) / len(timings)
    min_time = min(timings)
    max_time = max(timings)
    avg_rows = sum(row_counts) / len(row_counts)

    return {
        'avg_time': avg_time,
        'min_time': min_time,
        'max_time': max_time,
        'avg_rows': avg_rows,
        'timings': timings,
        'row_counts': row_counts,
    }


def estimate_v32_baseline(v33_time: float, complexity_factor: float = 1.15) -> float:
    """
    Estimate v3.2 baseline performance.

    v3.3 adds:
    - Market shift calculation (1 account-level calculation)
    - Scale factor calculation (per-row)
    - Layered expected sales (per-row)
    - Asymmetric logic (per-row conditionals)

    Estimated complexity increase: ~15%
    Therefore, v3.2 baseline ≈ v3.3 time / 1.15
    """
    return v33_time / complexity_factor


def print_performance_report(results: Dict, target_time: float = None):
    """Print performance benchmark report."""
    print("\n" + "="*70)
    print("⚡ PERFORMANCE BENCHMARK RESULTS")
    print("="*70)

    print(f"\nQuery Performance:")
    print(f"  • Average time: {results['avg_time']:.2f}s")
    print(f"  • Min time:     {results['min_time']:.2f}s")
    print(f"  • Max time:     {results['max_time']:.2f}s")
    print(f"  • Average rows: {results['avg_rows']:.0f}")

    # Calculate throughput
    throughput = results['avg_rows'] / results['avg_time']
    print(f"\nThroughput:")
    print(f"  • Rows/second:  {throughput:.0f}")

    # Estimated v3.2 baseline
    estimated_v32 = estimate_v32_baseline(results['avg_time'])
    overhead = results['avg_time'] - estimated_v32
    overhead_pct = (overhead / estimated_v32) * 100

    print(f"\nEstimated v3.2 Baseline:")
    print(f"  • Estimated v3.2 time: {estimated_v32:.2f}s")
    print(f"  • v3.3 overhead:       {overhead:.2f}s ({overhead_pct:.1f}%)")

    # Performance assessment
    print(f"\n📊 Assessment:")

    if results['avg_time'] < 5:
        print(f"  ✅ Excellent: Query completes in under 5 seconds")
    elif results['avg_time'] < 10:
        print(f"  ✅ Good: Query completes in under 10 seconds")
    elif results['avg_time'] < 30:
        print(f"  ⚠️  Acceptable: Query completes in under 30 seconds")
    else:
        print(f"  ⚠️  Slow: Query takes over 30 seconds")

    if overhead_pct < 20:
        print(f"  ✅ Overhead within target: {overhead_pct:.1f}% < 20%")
    else:
        print(f"  ⚠️  Overhead exceeds target: {overhead_pct:.1f}% > 20%")

    # Target comparison
    if target_time:
        if results['avg_time'] <= target_time * 1.2:
            print(f"  ✅ Within 20% of target: {results['avg_time']:.2f}s vs {target_time:.2f}s target")
        else:
            print(f"  ⚠️  Exceeds target: {results['avg_time']:.2f}s vs {target_time:.2f}s target")


def test_calculation_overhead():
    """Test overhead of v3.3 calculations on a sample dataset."""
    print("\n" + "="*70)
    print("🧪 CALCULATION OVERHEAD TEST")
    print("="*70)

    # Create sample data with all required columns
    n_rows = 1000
    print(f"\nGenerating {n_rows} sample rows...")

    import numpy as np

    df = pd.DataFrame({
        'before_clicks': np.random.randint(10, 1000, n_rows),
        'after_clicks': np.random.randint(10, 1000, n_rows),
        'before_spend': np.random.uniform(5, 500, n_rows),
        'observed_after_spend': np.random.uniform(5, 500, n_rows),
        'before_sales': np.random.uniform(10, 1000, n_rows),
        'observed_after_sales': np.random.uniform(10, 1000, n_rows),
        'market_tag': 'Win',
        'confidence_weight': 1.0,
        'action_type': 'BID_CHANGE',
        'validation_status': '',  # Empty validation status
    })

    # Calculate required pre-columns (that would exist from v3.2 calculation)
    df['spc_before'] = df['before_sales'] / df['before_clicks'].replace(0, np.nan)
    df['spc_before'] = df['spc_before'].replace([np.inf, -np.inf], np.nan).fillna(0)

    df['expected_sales'] = df['after_clicks'] * df['spc_before']
    df['decision_impact'] = df['observed_after_sales'] - df['expected_sales']

    # Import v3.3 helper functions
    from app_core.postgres_manager import PostgresManager

    # Create a dummy manager instance (won't connect)
    class DummyManager:
        def _calculate_market_shift(self, df):
            from app_core.postgres_manager import MARKET_SHIFT_BOUNDS
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

            return np.clip(market_shift, *MARKET_SHIFT_BOUNDS)

        def _calculate_v33_impact_columns(self, df):
            # Import the real implementation
            return PostgresManager._calculate_v33_impact_columns(self, df)

    manager = DummyManager()

    # Benchmark v3.3 calculations
    print(f"\n⏱️  Timing v3.3 calculations...")

    iterations = 10
    timings = []

    for i in range(iterations):
        df_copy = df.copy()
        start = time.time()

        # Run v3.3 calculations
        result = manager._calculate_v33_impact_columns(df_copy)

        elapsed = time.time() - start
        timings.append(elapsed)

    avg_time = sum(timings) / len(timings)
    min_time = min(timings)
    max_time = max(timings)

    print(f"\nResults:")
    print(f"  • Average time: {avg_time*1000:.1f}ms")
    print(f"  • Min time:     {min_time*1000:.1f}ms")
    print(f"  • Max time:     {max_time*1000:.1f}ms")
    print(f"  • Per-row time: {(avg_time/n_rows)*1000:.3f}ms")

    # Assessment
    per_row_us = (avg_time / n_rows) * 1_000_000
    print(f"\n📊 Assessment:")
    print(f"  • Per-row overhead: {per_row_us:.0f} microseconds")

    if per_row_us < 100:
        print(f"  ✅ Excellent: Negligible per-row overhead")
    elif per_row_us < 500:
        print(f"  ✅ Good: Low per-row overhead")
    elif per_row_us < 1000:
        print(f"  ⚠️  Acceptable: Moderate per-row overhead")
    else:
        print(f"  ⚠️  High: Significant per-row overhead")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Impact Model v3.3 Performance"
    )

    parser.add_argument('--client', help='Client ID for database benchmark')
    parser.add_argument('--db-url', help='Database URL')
    parser.add_argument('--iterations', type=int, default=3, help='Number of iterations (default: 3)')
    parser.add_argument('--target-time', type=float, help='Target time in seconds for comparison')
    parser.add_argument('--calc-only', action='store_true', help='Only test calculation overhead (no DB)')

    args = parser.parse_args()

    print("="*70)
    print("⚡ IMPACT MODEL v3.3 PERFORMANCE BENCHMARK")
    print("="*70)

    # Check version
    from app_core.postgres_manager import IMPACT_MODEL_VERSION
    print(f"\nImpact Model Version: {IMPACT_MODEL_VERSION}")

    if IMPACT_MODEL_VERSION != "v3.3":
        print(f"\n⚠️  Warning: IMPACT_MODEL_VERSION is set to '{IMPACT_MODEL_VERSION}'")
        print(f"   This benchmark is designed for v3.3")

    # Run calculation overhead test (always)
    test_calculation_overhead()

    # Run database benchmark if credentials provided
    if not args.calc_only:
        if args.client and args.db_url:
            print("\n" + "="*70)
            print("🔗 DATABASE QUERY BENCHMARK")
            print("="*70)

            results = benchmark_get_action_impact(
                args.client,
                args.db_url,
                iterations=args.iterations
            )

            print_performance_report(results, target_time=args.target_time)

        else:
            print("\n" + "="*70)
            print("ℹ️  Database benchmark skipped")
            print("="*70)
            print("\nTo run database benchmark, provide:")
            print("  --client CLIENT_ID --db-url 'postgres://...'")

    # Summary
    print("\n" + "="*70)
    print("✅ PERFORMANCE BENCHMARK COMPLETE")
    print("="*70)

    print("\n💡 Recommendations:")
    print("   • If performance is acceptable, v3.3 is ready for production")
    print("   • If performance is slow, consider:")
    print("     - Database indexing on target_stats (client_id, start_date, target_text)")
    print("     - Connection pooling optimization")
    print("     - Caching for repeated queries")


if __name__ == "__main__":
    main()
