#!/usr/bin/env python3
"""
Impact Model v3.2 vs v3.3 Comparison Report Generator
======================================================

Generates a detailed side-by-side comparison report between v3.2 and v3.3 models.

Usage:
    # With exported CSV data:
    python3 dev_resources/tests/generate_v32_v33_comparison.py --input /path/to/export.csv

    # With database connection:
    python3 dev_resources/tests/generate_v32_v33_comparison.py --client CLIENT_ID --db-url "postgres://..."

Output:
    - Console report with detailed comparison
    - Optional JSON report: --output report.json
    - Optional CSV export: --export-csv comparison.csv
"""

import sys
import os
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
import argparse
import json
from datetime import datetime
from typing import Dict, Tuple, Optional


def load_data_from_csv(filepath: str) -> pd.DataFrame:
    """Load data from exported CSV."""
    print(f"📁 Loading data from: {filepath}")
    df = pd.read_csv(filepath)
    print(f"✓ Loaded {len(df)} rows")
    return df


def load_data_from_db(client_id: str, db_url: str, before_days: int = 14, after_days: int = 14) -> pd.DataFrame:
    """Load data directly from database."""
    print(f"🔗 Connecting to database for client: {client_id}")
    from app_core.postgres_manager import PostgresManager

    manager = PostgresManager(db_url)
    df = manager.get_action_impact(client_id, before_days=before_days, after_days=after_days)
    print(f"✓ Loaded {len(df)} rows")
    return df


def validate_columns(df: pd.DataFrame) -> bool:
    """Validate that dataframe has required columns."""
    required_v33 = [
        'impact_v33', 'final_impact_v33', 'market_shift', 'scale_factor',
        'expected_sales_v33', 'decision_impact', 'final_decision_impact'
    ]

    required_v32_backup = ['decision_impact_v32', 'final_decision_impact_v32']

    has_v33 = all(col in df.columns for col in required_v33)
    has_v32_backup = all(col in df.columns for col in required_v32_backup)

    if not has_v33:
        missing = [col for col in required_v33 if col not in df.columns]
        print(f"⚠️ Missing v3.3 columns: {missing}")
        print("   This data was likely generated with v3.2 or older version")
        return False

    if not has_v32_backup:
        print("⚠️ Missing v3.2 backup columns - comparison will be limited")
        return False

    return True


def calculate_metrics(df: pd.DataFrame, version: str = "v3.3") -> Dict:
    """Calculate aggregate metrics for a specific version."""

    # Determine column names based on version
    if version == "v3.3":
        impact_col = 'decision_impact'
        final_impact_col = 'final_decision_impact'
    else:  # v3.2
        impact_col = 'decision_impact_v32'
        final_impact_col = 'final_decision_impact_v32'

    # Exclude Market Drag
    included = df[df['market_tag'] != 'Market Drag']
    excluded = df[df['market_tag'] == 'Market Drag']

    # Calculate aggregates
    total_impact = included[final_impact_col].sum()

    positive = included[included[impact_col] > 0]
    negative = included[included[impact_col] < 0]

    wins_total = positive[final_impact_col].sum()
    wins_count = len(positive)

    gaps_total = negative[final_impact_col].sum()
    gaps_count = len(negative)

    # Quadrant breakdown (use market_tag from data)
    offensive = included[included['market_tag'] == 'Offensive Win']
    defensive = included[included['market_tag'] == 'Defensive Win']
    decision_gaps = included[included['market_tag'] == 'Gap']

    return {
        'total_impact': total_impact,
        'wins_total': wins_total,
        'wins_count': wins_count,
        'gaps_total': gaps_total,
        'gaps_count': gaps_count,
        'offensive_wins_total': offensive[final_impact_col].sum(),
        'offensive_wins_count': len(offensive),
        'defensive_wins_total': defensive[final_impact_col].sum(),
        'defensive_wins_count': len(defensive),
        'decision_gaps_total': decision_gaps[final_impact_col].sum(),
        'decision_gaps_count': len(decision_gaps),
        'market_drag_total': excluded[final_impact_col].sum(),
        'market_drag_count': len(excluded),
        'total_actions': len(df),
        'measured_actions': len(included),
        'excluded_actions': len(excluded),
    }


def print_header(df: pd.DataFrame):
    """Print report header."""
    print("\n" + "="*90)
    print("📊 IMPACT MODEL COMPARISON REPORT: v3.2 vs v3.3")
    print("="*90)
    print(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Actions: {len(df)}")

    # Check data freshness
    if 'action_date' in df.columns:
        latest_action = pd.to_datetime(df['action_date']).max()
        print(f"Latest Action Date: {latest_action.strftime('%Y-%m-%d')}")

    print("\n" + "-"*90)


def print_comparison_table(v32_metrics: Dict, v33_metrics: Dict):
    """Print side-by-side comparison table."""
    print("\n📈 IMPACT COMPARISON")
    print("="*90)

    # Calculate improvements
    total_improvement = v33_metrics['total_impact'] - v32_metrics['total_impact']
    total_improvement_pct = (total_improvement / abs(v32_metrics['total_impact']) * 100) if v32_metrics['total_impact'] != 0 else 0

    wins_change = v33_metrics['wins_total'] - v32_metrics['wins_total']
    gaps_change = v33_metrics['gaps_total'] - v32_metrics['gaps_total']

    # Format table
    print(f"┌{'─'*86}┐")
    print(f"│ {'Metric':<30} │ {'v3.2 (Linear)':<20} │ {'v3.3 (Layered)':<20} │ {'Change':<10} │")
    print(f"├{'─'*86}┤")

    # Total Impact
    print(f"│ {'Total Impact':<30} │ ${v32_metrics['total_impact']:>18,.0f} │ ${v33_metrics['total_impact']:>18,.0f} │ {total_improvement:>+9,.0f} │")

    # Wins
    print(f"│ {'Positive (Wins)':<30} │ ${v32_metrics['wins_total']:>18,.0f} │ ${v33_metrics['wins_total']:>18,.0f} │ {wins_change:>+9,.0f} │")

    # Gaps
    print(f"│ {'Negative (Gaps)':<30} │ ${v32_metrics['gaps_total']:>18,.0f} │ ${v33_metrics['gaps_total']:>18,.0f} │ {gaps_change:>+9,.0f} │")

    print(f"├{'─'*86}┤")

    # Action counts
    print(f"│ {'Win Count':<30} │ {v32_metrics['wins_count']:>20} │ {v33_metrics['wins_count']:>20} │ {v33_metrics['wins_count'] - v32_metrics['wins_count']:>+10} │")
    print(f"│ {'Gap Count':<30} │ {v32_metrics['gaps_count']:>20} │ {v33_metrics['gaps_count']:>20} │ {v33_metrics['gaps_count'] - v32_metrics['gaps_count']:>+10} │")

    print(f"└{'─'*86}┘")

    # Improvement summary
    print(f"\n💡 Key Findings:")
    print(f"   • Total Impact Improvement: ${total_improvement:+,.0f} ({total_improvement_pct:+.1f}%)")

    if wins_change != 0:
        wins_change_pct = (wins_change / abs(v32_metrics['wins_total']) * 100) if v32_metrics['wins_total'] != 0 else 0
        direction = "increase" if wins_change > 0 else "decrease"
        print(f"   • Wins {direction}: ${abs(wins_change):,.0f} ({abs(wins_change_pct):.1f}%)")
    else:
        print(f"   • Wins unchanged")

    if gaps_change != 0:
        gaps_change_pct = (gaps_change / abs(v32_metrics['gaps_total']) * 100) if v32_metrics['gaps_total'] != 0 else 0
        if gaps_change > 0:
            print(f"   • Gaps reduced by: ${abs(gaps_change):,.0f} ({abs(gaps_change_pct):.1f}%)")
        else:
            print(f"   • Gaps increased by: ${abs(gaps_change):,.0f} ({abs(gaps_change_pct):.1f}%)")
    else:
        print(f"   • Gaps unchanged")


def print_quadrant_comparison(v32_metrics: Dict, v33_metrics: Dict):
    """Print quadrant breakdown comparison."""
    print("\n📊 QUADRANT BREAKDOWN")
    print("="*90)

    quadrants = [
        ('Offensive Wins', 'offensive_wins'),
        ('Defensive Wins', 'defensive_wins'),
        ('Decision Gaps', 'decision_gaps'),
        ('Market Drag (Excluded)', 'market_drag'),
    ]

    print(f"┌{'─'*86}┐")
    print(f"│ {'Quadrant':<30} │ {'v3.2 Count':<10} │ {'v3.2 Impact':<15} │ {'v3.3 Count':<10} │ {'v3.3 Impact':<15} │")
    print(f"├{'─'*86}┤")

    for name, key in quadrants:
        v32_count = v32_metrics[f'{key}_count']
        v32_impact = v32_metrics[f'{key}_total']
        v33_count = v33_metrics[f'{key}_count']
        v33_impact = v33_metrics[f'{key}_total']

        print(f"│ {name:<30} │ {v32_count:>10} │ ${v32_impact:>13,.0f} │ {v33_count:>10} │ ${v33_impact:>13,.0f} │")

    print(f"└{'─'*86}┘")


def print_adjustment_details(df: pd.DataFrame):
    """Print details about v3.3 adjustments."""
    print("\n🔧 v3.3 ADJUSTMENT DETAILS")
    print("="*90)

    # Market shift
    if 'market_shift' in df.columns:
        market_shift = df['market_shift'].iloc[0]
        market_change_pct = (market_shift - 1) * 100

        print(f"\n📉 Market Shift (Account-Level SPC Change):")
        print(f"   • Factor: {market_shift:.3f} ({market_change_pct:+.1f}%)")

        if market_shift < 1:
            print(f"   • Interpretation: Market efficiency dropped by {abs(market_change_pct):.1f}%")
            print(f"   • Impact: Penalties reduced to account for external factors")
        elif market_shift > 1:
            print(f"   • Interpretation: Market efficiency improved by {market_change_pct:.1f}%")
            print(f"   • Impact: Expectations adjusted upward")
        else:
            print(f"   • Interpretation: No significant market change detected")

    # Scale factor distribution
    if 'scale_factor' in df.columns and 'click_ratio' in df.columns:
        scale_ups = df[df['click_ratio'] > 1.0]

        if len(scale_ups) > 0:
            print(f"\n📈 Scale Factor (Diminishing Returns):")
            print(f"   • Scale-up actions: {len(scale_ups)} ({len(scale_ups)/len(df)*100:.1f}%)")
            print(f"   • Avg click ratio: {scale_ups['click_ratio'].mean():.2f}x")
            print(f"   • Avg scale factor: {scale_ups['scale_factor'].mean():.3f}")
            print(f"   • Min scale factor: {scale_ups['scale_factor'].min():.3f} (largest penalty reduction)")

    # Adjustment type breakdown
    if 'adjustment_type' in df.columns:
        print(f"\n🎯 Adjustment Types:")
        adj_counts = df['adjustment_type'].value_counts()

        type_labels = {
            'linear_positive': 'Positive outcomes (unchanged)',
            'layered_scaleup': 'Negative + Scale-up (layered)',
            'market_scaledown': 'Negative + Scale-down (market-only)'
        }

        for adj_type, count in adj_counts.items():
            label = type_labels.get(adj_type, adj_type)
            pct = count / len(df) * 100
            print(f"   • {label}: {count} ({pct:.1f}%)")


def analyze_top_changes(df: pd.DataFrame, n: int = 10):
    """Analyze actions with biggest impact changes."""
    print(f"\n🔝 TOP {n} CHANGES (v3.3 vs v3.2)")
    print("="*90)

    if 'decision_impact_v32' not in df.columns:
        print("⚠️ v3.2 backup columns not available for comparison")
        return

    df_copy = df.copy()
    df_copy['impact_improvement'] = df_copy['decision_impact'] - df_copy['decision_impact_v32']

    # Top improvements (most positive change)
    top_improved = df_copy.nlargest(n, 'impact_improvement')

    print(f"\n📈 Biggest Improvements (Penalties Reduced):")
    print(f"┌{'─'*88}┐")
    print(f"│ {'Target':<25} │ {'Ratio':<6} │ {'v3.2 Impact':<13} │ {'v3.3 Impact':<13} │ {'Change':<12} │")
    print(f"├{'─'*88}┤")

    for idx, row in top_improved.iterrows():
        target = str(row.get('target_text', 'N/A'))[:23]
        ratio = f"{row.get('click_ratio', 0):.2f}x" if 'click_ratio' in row else "N/A"
        v32 = row['decision_impact_v32']
        v33 = row['decision_impact']
        change = row['impact_improvement']

        print(f"│ {target:<25} │ {ratio:<6} │ ${v32:>11,.0f} │ ${v33:>11,.0f} │ ${change:>+10,.0f} │")

    print(f"└{'─'*88}┘")


def export_to_json(comparison_data: Dict, output_path: str):
    """Export comparison data to JSON."""
    with open(output_path, 'w') as f:
        json.dump(comparison_data, f, indent=2, default=str)
    print(f"\n✓ JSON report exported to: {output_path}")


def export_to_csv(df: pd.DataFrame, output_path: str):
    """Export comparison dataframe to CSV."""
    # Select key columns
    export_cols = [
        'action_date', 'action_type', 'target_text', 'campaign_name',
        'before_spend', 'observed_after_spend',
        'before_sales', 'observed_after_sales',
        'before_clicks', 'after_clicks',
        'decision_impact_v32', 'decision_impact',
        'final_decision_impact_v32', 'final_decision_impact',
        'market_shift', 'scale_factor', 'click_ratio',
        'market_tag', 'validation_status'
    ]

    available_cols = [col for col in export_cols if col in df.columns]
    df[available_cols].to_csv(output_path, index=False)
    print(f"✓ CSV comparison exported to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate v3.2 vs v3.3 Impact Model Comparison Report"
    )

    # Data source options
    parser.add_argument('--input', '-i', help='Path to exported CSV file')
    parser.add_argument('--client', help='Client ID (for database query)')
    parser.add_argument('--db-url', help='Database URL (required with --client)')

    # Options
    parser.add_argument('--before-days', type=int, default=14, help='Before period days (default: 14)')
    parser.add_argument('--after-days', type=int, default=14, help='After period days (default: 14)')
    parser.add_argument('--output', '-o', help='Export JSON report to file')
    parser.add_argument('--export-csv', help='Export comparison CSV to file')
    parser.add_argument('--top-n', type=int, default=10, help='Number of top changes to show (default: 10)')

    args = parser.parse_args()

    # Load data
    if args.input:
        df = load_data_from_csv(args.input)
    elif args.client and args.db_url:
        df = load_data_from_db(args.client, args.db_url, args.before_days, args.after_days)
    else:
        print("❌ Error: Must provide either --input or (--client and --db-url)")
        parser.print_help()
        sys.exit(1)

    # Validate columns
    if not validate_columns(df):
        print("\n❌ Data validation failed. Cannot generate comparison.")
        sys.exit(1)

    # Calculate metrics
    v32_metrics = calculate_metrics(df, version="v3.2")
    v33_metrics = calculate_metrics(df, version="v3.3")

    # Generate report
    print_header(df)
    print_comparison_table(v32_metrics, v33_metrics)
    print_quadrant_comparison(v32_metrics, v33_metrics)
    print_adjustment_details(df)
    analyze_top_changes(df, n=args.top_n)

    # Footer
    print("\n" + "="*90)
    print("✅ COMPARISON REPORT COMPLETE")
    print("="*90)

    # Export if requested
    if args.output:
        comparison_data = {
            'generated_at': datetime.now().isoformat(),
            'total_actions': len(df),
            'v3.2_metrics': v32_metrics,
            'v3.3_metrics': v33_metrics,
            'improvement': v33_metrics['total_impact'] - v32_metrics['total_impact'],
        }
        export_to_json(comparison_data, args.output)

    if args.export_csv:
        export_to_csv(df, args.export_csv)

    print("\n💡 Next Steps:")
    print("   1. Review the impact improvements and validate they match expectations")
    print("   2. Examine top changes to understand which actions benefited most")
    print("   3. Share report with stakeholders for approval")
    print("   4. If approved, v3.3 is ready for production")


if __name__ == "__main__":
    main()
