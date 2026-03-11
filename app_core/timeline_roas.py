"""
Timeline-Based ROAS Calculator (v3.5)
======================================

Calculates baseline and final ROAS using clean 30-day periods:
- Baseline: 30 days BEFORE first optimization
- Final: 30 days AFTER last mature optimization

This provides clearer storytelling than aggregating overlapping action windows.
"""

from typing import Dict, Any, Optional
from datetime import date, datetime, timedelta
import pandas as pd
from app_core.constants import ACTION_MATURITY_DAYS


def get_account_timeline_roas(
    impact_df: pd.DataFrame,
    client_id: str,
    postgres_manager: Any
) -> Dict[str, Any]:
    """
    Calculate baseline and final ROAS using clean 30-day periods.

    Timeline Structure:
    ┌─────────────┬──────────────────┬─────────────┐
    │  BASELINE   │   OPTIMIZATION   │    FINAL    │
    │  (30 days)  │     PERIOD       │  (30 days)  │
    └─────────────┴──────────────────┴─────────────┘

    Args:
        impact_df: DataFrame from get_action_impact()
        client_id: Account ID
        postgres_manager: Database manager instance

    Returns:
        Dict with baseline/final ROAS, dates, and metadata
    """

    if impact_df.empty:
        return _empty_timeline()

    # =====================================================
    # STEP 1: Find Earliest Action (for Baseline)
    # =====================================================
    earliest_action = pd.to_datetime(impact_df['action_date']).min().date()

    # =====================================================
    # STEP 2: Find Latest Action with COMPLETE 30-Day Window (for Final)
    # =====================================================
    # CRITICAL: We need ACTION_MATURITY_DAYS + 30 days after the action (14 days to mature + 30 days to measure)
    # Find the latest mature action that has a COMPLETE 30-day window available

    latest_data = postgres_manager.get_latest_data_date(client_id)
    today = datetime.now().date()
    data_end = latest_data if latest_data else today

    # Priority 1: Find latest mature, non-drag action with complete 30-day window
    mature_non_drag = impact_df[
        (impact_df['is_mature'] == True) &
        (impact_df['market_tag'] != 'Market Drag')
    ].copy()

    latest_measurable = None
    final_status = 'no_mature_with_complete_window'

    if not mature_non_drag.empty:
        # Sort by date descending to check from most recent
        mature_non_drag['action_date_dt'] = pd.to_datetime(mature_non_drag['action_date'])
        mature_non_drag = mature_non_drag.sort_values('action_date_dt', ascending=False)

        # Find the latest action with a complete 30-day window
        for _, action in mature_non_drag.iterrows():
            action_date = action['action_date_dt'].date()
            window_end = action_date + timedelta(days=ACTION_MATURITY_DAYS + 30)  # ACTION_MATURITY_DAYS to mature + 30 days to measure

            if window_end <= data_end:
                # This action has a complete 30-day window!
                latest_measurable = action_date
                final_status = 'mature'
                break

    # Priority 2: Try mature actions (even if Market Drag) with complete window
    if latest_measurable is None:
        mature_any = impact_df[impact_df['is_mature'] == True].copy()

        if not mature_any.empty:
            mature_any['action_date_dt'] = pd.to_datetime(mature_any['action_date'])
            mature_any = mature_any.sort_values('action_date_dt', ascending=False)

            for _, action in mature_any.iterrows():
                action_date = action['action_date_dt'].date()
                window_end = action_date + timedelta(days=ACTION_MATURITY_DAYS + 30)

                if window_end <= data_end:
                    latest_measurable = action_date
                    final_status = 'mature_with_drag'
                    break

    # Priority 3: If still no complete window, use the oldest mature action we have
    # (This ensures we always show SOMETHING, even if very old)
    if latest_measurable is None:
        if not mature_non_drag.empty:
            latest_measurable = mature_non_drag['action_date_dt'].min().date()
            final_status = 'old_mature'
        elif not impact_df.empty:
            latest_measurable = pd.to_datetime(impact_df['action_date']).min().date()
            final_status = 'fallback'

    # =====================================================
    # STEP 3: Define 30-Day Baseline Period
    # =====================================================
    baseline_end = earliest_action - timedelta(days=ACTION_MATURITY_DAYS)  # ACTION_MATURITY_DAYS buffer before first action
    baseline_start = baseline_end - timedelta(days=30)   # 30-day period

    # Edge Case 1: Not enough historical data
    # Query earliest available data date
    earliest_data = postgres_manager.get_earliest_data_date(client_id)
    if earliest_data and baseline_start < earliest_data:
        baseline_start = earliest_data
        baseline_days = (baseline_end - baseline_start).days
        baseline_warning = f"Limited data: Using {baseline_days} days (< 30)"
    else:
        baseline_days = 30
        baseline_warning = None

    # =====================================================
    # STEP 4: Define 30-Day Final Period (ALWAYS COMPLETE)
    # =====================================================
    # Since we found a mature action with complete 30-day window, use it
    final_start = latest_measurable + timedelta(days=ACTION_MATURITY_DAYS)  # ACTION_MATURITY_DAYS after action for maturity
    final_end = final_start + timedelta(days=30)          # ALWAYS 30 days

    # No need to check data availability - we already verified in STEP 2
    # that this action has a complete 30-day window
    final_days = 30
    final_warning = None  # Never show partial data warning for Final Period

    # =====================================================
    # STEP 5: Query Account Performance from Database
    # =====================================================
    baseline_perf = postgres_manager.get_account_performance(
        client_id=client_id,
        start_date=baseline_start,
        end_date=baseline_end
    )

    final_perf = postgres_manager.get_account_performance(
        client_id=client_id,
        start_date=final_start,
        end_date=final_end
    )

    # =====================================================
    # STEP 6: Calculate ROAS
    # =====================================================
    baseline_roas = baseline_perf['sales'] / baseline_perf['spend'] \
        if baseline_perf['spend'] > 0 else 0

    final_roas = final_perf['sales'] / final_perf['spend'] \
        if final_perf['spend'] > 0 else 0

    # =====================================================
    # STEP 7: Return Complete Timeline
    # =====================================================
    return {
        # Baseline anchor
        'baseline_roas': round(baseline_roas, 2),
        'baseline_start': baseline_start,
        'baseline_end': baseline_end,
        'baseline_days': baseline_days,
        'baseline_sales': round(baseline_perf['sales'], 2),
        'baseline_spend': round(baseline_perf['spend'], 2),
        'baseline_warning': baseline_warning,

        # Final anchor
        'final_roas': round(final_roas, 2),
        'final_start': final_start,
        'final_end': final_end,
        'final_days': final_days,
        'final_sales': round(final_perf['sales'], 2),
        'final_spend': round(final_perf['spend'], 2),
        'final_status': final_status,
        'final_warning': final_warning,

        # Optimization period
        'optimization_start': earliest_action,
        'optimization_end': latest_measurable,
        'optimization_period_days': (latest_measurable - earliest_action).days,

        # Metadata
        'total_actions': len(impact_df),
        'mature_actions': len(impact_df[impact_df['is_mature'] == True]),
        'has_complete_data': baseline_warning is None and final_warning is None,

        # For backward compatibility with v3.4 waterfall
        'before_spend': baseline_perf['spend'],
        'before_sales': baseline_perf['sales'],
        'after_spend': final_perf['spend'],
        'after_sales': final_perf['sales'],
    }


def _empty_timeline() -> Dict[str, Any]:
    """Return empty timeline when no data available."""
    return {
        'baseline_roas': 0,
        'baseline_start': None,
        'baseline_end': None,
        'baseline_days': 0,
        'baseline_sales': 0,
        'baseline_spend': 0,
        'baseline_warning': 'No data available',

        'final_roas': 0,
        'final_start': None,
        'final_end': None,
        'final_days': 0,
        'final_sales': 0,
        'final_spend': 0,
        'final_status': 'no_data',
        'final_warning': 'No data available',

        'optimization_start': None,
        'optimization_end': None,
        'optimization_period_days': 0,

        'total_actions': 0,
        'mature_actions': 0,
        'has_complete_data': False,

        'before_spend': 0,
        'before_sales': 0,
        'after_spend': 0,
        'after_sales': 0,
    }
