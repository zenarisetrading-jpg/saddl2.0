"""
ROAS Waterfall v3.3 - Integrated with Impact Model v3.3
========================================================

Uses the same counterfactual baseline as the v3.3 impact model for perfect alignment.
This eliminates the circular dependency and reduces unexplained residual.

Key Integration Points:
- market_shift: Already calculated in postgres_manager.py
- decision_impact: Uses v3.3 layered counterfactual values
- No overlap or double-counting
"""

from typing import Dict, Any, Optional
import pandas as pd
import numpy as np


def calculate_roas_waterfall_v33(
    impact_df: pd.DataFrame,
    decision_impact_dollars: float,
    timeline: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculate v3.5 ROAS waterfall using timeline-based baseline and final ROAS.

    v3.5 uses clean 30-day periods for Baseline and Final ROAS:
    - Baseline: 30 days BEFORE first optimization
    - Final: 30 days AFTER last mature optimization

    This provides clearer storytelling than aggregating overlapping action windows.

    Args:
        impact_df: DataFrame from get_action_impact() with v3.3 columns
        decision_impact_dollars: Net v3.3 decision impact (from canonical_metrics.attributed_impact)
        timeline: Optional timeline dict from get_account_timeline_roas()
                 If not provided, falls back to action-level aggregation (v3.4 behavior)

    Returns:
        Dict with waterfall components for display
    """

    if impact_df.empty:
        return _empty_waterfall()

    # =========================================================
    # STEP 1: Get Baseline and Final ROAS
    # =========================================================
    if timeline:
        # v3.5: Use timeline-based ROAS (clean 30-day periods)
        baseline_roas = timeline['baseline_roas']
        actual_roas = timeline['final_roas']
        after_spend = timeline['after_spend']
        after_sales = timeline['after_sales']
        before_spend = timeline['before_spend']
        before_sales = timeline['before_sales']
        before_clicks = None
        after_clicks = None

        # For click-based calculations, use action-level aggregation
        action_before_clicks = impact_df['before_clicks'].sum()
        action_after_clicks = impact_df['after_clicks'].sum()

        clicks_available = action_before_clicks > 0 and action_after_clicks > 0
        if clicks_available:
            before_clicks = action_before_clicks
            after_clicks = action_after_clicks
    else:
        # v3.4: Fallback to action-level aggregation
        before_spend = impact_df['before_spend'].sum()
        before_sales = impact_df['before_sales'].sum()
        before_clicks = impact_df['before_clicks'].sum()

        after_spend = impact_df['observed_after_spend'].sum()
        after_sales = impact_df['observed_after_sales'].sum()
        after_clicks = impact_df['after_clicks'].sum()
        clicks_available = True

        if before_spend == 0 or after_spend == 0:
            return _empty_waterfall()

        baseline_roas = before_sales / before_spend
        actual_roas = after_sales / after_spend

    total_change = actual_roas - baseline_roas

    # =========================================================
    # STEP 3: Market Forces (Use v3.3 market_shift)
    # =========================================================
    # CRITICAL: Use the SAME market_shift that v3.3 impact model uses
    # This is already calculated and stored in impact_df['market_shift']

    if 'market_shift' in impact_df.columns:
        # Get market_shift from v3.3 calculation (same for all rows)
        market_shift = impact_df['market_shift'].iloc[0]
    else:
        # Fallback: Calculate it the same way v3.3 does
        baseline_spc = before_sales / before_clicks if before_clicks > 0 else 0
        actual_spc = after_sales / after_clicks if after_clicks > 0 else 0
        raw_market_shift = actual_spc / baseline_spc if baseline_spc > 0 else 1.0
        market_shift = raw_market_shift
        if raw_market_shift < 0.5 or raw_market_shift > 1.5:
            import logging; logging.getLogger(__name__).warning(f'Extreme market shift: {raw_market_shift:.3f}')

    # Market effect on ROAS (holding CPC constant)
    # If SPC dropped 12%, we EXPECT ROAS to drop proportionally
    market_effect_roas = baseline_roas * (market_shift - 1)

    # =========================================================
    # STEP 4: CPC Efficiency
    # =========================================================
    # Change in cost per click affects ROAS inversely

    if clicks_available:
        baseline_cpc = before_spend / before_clicks if before_clicks > 0 else 0
        actual_cpc = after_spend / after_clicks if after_clicks > 0 else 0
        cpc_change = actual_cpc / baseline_cpc if baseline_cpc > 0 else 1.0
        cpc_effect_roas = baseline_roas * (1/cpc_change - 1) if cpc_change > 0 else 0
    else:
        baseline_cpc = None
        actual_cpc = None
        cpc_change = 1.0
        cpc_effect_roas = 0

    # =========================================================
    # STEP 5: Structural Effects
    # =========================================================
    # Scale effect: Diminishing returns from spend changes
    spend_change_pct = (after_spend - before_spend) / before_spend if before_spend > 0 else 0

    if abs(spend_change_pct) >= 0.20:
        # Estimate 5% ROAS decline per 100% spend increase
        dilution_factor = 0.05 * spend_change_pct
        scale_effect = -dilution_factor * baseline_roas
    else:
        scale_effect = 0

    # Portfolio effect: New campaigns starting at lower ROAS
    # Count campaigns
    before_campaigns = len(impact_df['campaign_name'].unique()) if 'campaign_name' in impact_df.columns else 0
    # For after campaigns, we'd need a way to track new vs existing
    # For now, use a simple heuristic based on actions
    campaign_change_pct = 0  # Would need better data to calculate this

    if abs(campaign_change_pct) >= 0.20 and campaign_change_pct > 0:
        # New campaigns start at ~65% of baseline ROAS
        new_campaign_roas_factor = 0.65
        portfolio_effect = -campaign_change_pct * (1 - new_campaign_roas_factor) * baseline_roas
    else:
        portfolio_effect = 0

    structural_total = scale_effect + portfolio_effect

    # =========================================================
    # STEP 6: Market Drag Impact (NEW for v3.4)
    # =========================================================
    # Market Drag: Actions negatively affected by market conditions
    # These are separate from our optimization decisions

    if 'market_tag' in impact_df.columns and 'decision_impact' in impact_df.columns:
        # Calculate Market Drag impact separately
        drag_actions = impact_df[impact_df['market_tag'] == 'Market Drag']
        market_drag_dollars = drag_actions['decision_impact'].sum() if not drag_actions.empty else 0
        market_drag_roas = market_drag_dollars / after_spend if after_spend > 0 else 0
    else:
        market_drag_dollars = 0
        market_drag_roas = 0

    # =========================================================
    # STEP 7: NEW GROUPINGS (v3.4 Waterfall Structure)
    # =========================================================
    # Macro Impact = External/Market forces (Market Forces + Market Drag)
    macro_impact = market_effect_roas + market_drag_roas

    # Micro Impact = Internal/Structural effects (CPC + Structural)
    micro_impact = cpc_effect_roas + structural_total

    # Combined Forces (legacy compatibility)
    combined_forces = macro_impact + micro_impact

    # =========================================================
    # STEP 8: Decision Impact (Optimization Impact)
    # =========================================================
    # Use the measured v3.3 decision impact (campaign-level sum)
    # This is the actual attributed impact from get_action_impact()
    #
    # CRITICAL FIX: Previously used top-down (actual - counterfactual) which
    # was circular and ignored the measured +$49k impact. Now using the
    # actual measured impact passed as decision_impact_dollars.

    # Counterfactual ROAS = what ROAS would be without decisions
    counterfactual_roas = baseline_roas + combined_forces

    # Decision effect: Use the measured v3.3 impact (now called "Optimization Impact")
    optimization_impact_roas = decision_impact_dollars / after_spend if after_spend > 0 else 0
    decision_effect_roas = optimization_impact_roas  # Alias for backward compatibility

    # Calculate top-down for comparison/validation
    decision_effect_roas_topdown = actual_roas - counterfactual_roas

    # =========================================================
    # STEP 9: Residual
    # =========================================================
    # Residual = difference between top-down and bottom-up attribution
    # This captures campaign vs account-level aggregation gap
    predicted_roas = baseline_roas + combined_forces + optimization_impact_roas
    residual_roas = actual_roas - predicted_roas

    # Track the gap between measured (bottom-up) and calculated (top-down)
    attribution_gap = optimization_impact_roas - decision_effect_roas_topdown

    # Alternative calculation (should be same):
    # explained = macro + micro + optimization
    # residual = total_change - explained

    # =========================================================
    # STEP 10: Detailed Market Breakdown (for expander)
    # =========================================================
    # Break down market effect into CPC/CVR/AOV components for display
    # This is for INFORMATIONAL purposes only, not used in waterfall math

    if clicks_available:
        baseline_spc = before_sales / before_clicks if before_clicks > 0 else 0
        actual_spc = after_sales / after_clicks if after_clicks > 0 else 0
    else:
        baseline_spc = None
        actual_spc = None

    # CVR estimation (if we had order data)
    # For now, we can show SPC change and CPC change
    spc_change_pct = (market_shift - 1) * 100

    # We can decompose further if we have CVR/AOV data
    # For now, we attribute all SPC change to "market forces" broadly
    # Individual CPC/CVR/AOV impacts are informational only

    # =========================================================
    # STEP 11: Attribution Percentages
    # =========================================================
    def safe_pct(component, total):
        if abs(total) < 0.01:  # Avoid division by near-zero
            return 0
        return (component / total) * 100

    # External vs Internal split (v3.4 terminology)
    external_effect = macro_impact  # Macro = external market forces
    internal_effect = micro_impact  # Micro = internal structural effects
    optimization_effect = optimization_impact_roas  # Optimization = our decisions

    # Quality flag
    residual_magnitude = abs(residual_roas)
    if residual_magnitude < 0.10:
        quality_flag = '✓ Clean'
    elif residual_magnitude < 0.25:
        quality_flag = '✓ Good'
    elif residual_magnitude < 0.50:
        quality_flag = '⚠️ Moderate Residual'
    else:
        quality_flag = '⚠️ Large Residual'

    return {
        # ===== CORE WATERFALL VALUES (v3.4) =====
        'baseline_roas': round(baseline_roas, 2),
        'actual_roas': round(actual_roas, 2),
        'total_change': round(total_change, 2),

        # v3.4 Waterfall components (NEW)
        'macro_impact': round(macro_impact, 2),          # External: Market Forces + Market Drag
        'micro_impact': round(micro_impact, 2),          # Internal: CPC + Structural
        'optimization_impact': round(optimization_impact_roas, 2),  # Decisions
        'residual': round(residual_roas, 2),

        # Legacy compatibility (keep for backwards compat)
        'combined_forces': round(combined_forces, 2),    # = macro + micro
        'decision_effect': round(decision_effect_roas, 2),  # = optimization_impact

        # ===== DETAILED BREAKDOWN (for expander) =====
        # Market Forces
        'market_effect': round(market_effect_roas, 2),
        'market_shift': round(market_shift, 3),
        'spc_change_pct': round(spc_change_pct, 1),

        # Market Drag (NEW)
        'market_drag': round(market_drag_roas, 2),
        'market_drag_dollars': round(market_drag_dollars, 0),

        # CPC Efficiency
        'cpc_effect': round(cpc_effect_roas, 2),
        'baseline_cpc': round(baseline_cpc, 2),
        'actual_cpc': round(actual_cpc, 2),
        'cpc_change_pct': round((cpc_change - 1) * 100, 1),

        # Structural Effects
        'scale_effect': round(scale_effect, 2),
        'portfolio_effect': round(portfolio_effect, 2),
        'structural_total': round(structural_total, 2),

        # Underlying metrics
        'baseline_spc': round(baseline_spc, 2),
        'actual_spc': round(actual_spc, 2),
        'spend_change_pct': round(spend_change_pct * 100, 1),

        # ===== ATTRIBUTION PERCENTAGES =====
        # Component-level percentages
        'market_pct': round(safe_pct(market_effect_roas, total_change), 1),
        'market_drag_pct': round(safe_pct(market_drag_roas, total_change), 1),
        'cpc_pct': round(safe_pct(cpc_effect_roas, total_change), 1),
        'structural_pct': round(safe_pct(structural_total, total_change), 1),

        # v3.4 Grouped percentages (NEW)
        'macro_pct': round(safe_pct(macro_impact, total_change), 1),
        'micro_pct': round(safe_pct(micro_impact, total_change), 1),
        'optimization_pct': round(safe_pct(optimization_impact_roas, total_change), 1),
        'residual_pct': round(safe_pct(residual_roas, total_change), 1),

        # Legacy compatibility
        'combined_pct': round(safe_pct(combined_forces, total_change), 1),
        'decision_pct': round(safe_pct(decision_effect_roas, total_change), 1),

        # External vs Internal (v3.4 semantics)
        'external_effect': round(external_effect, 2),  # = macro_impact
        'external_pct': round(safe_pct(external_effect, total_change), 1),
        'internal_effect': round(internal_effect, 2),  # = micro_impact
        'internal_pct': round(safe_pct(internal_effect, total_change), 1),
        'optimization_effect': round(optimization_effect, 2),  # = optimization_impact
        'optimization_effect_pct': round(safe_pct(optimization_effect, total_change), 1),

        # ===== VALIDATION =====
        'is_valid': residual_magnitude < 0.50,
        'quality_flag': quality_flag,
        'residual_magnitude': round(residual_magnitude, 2),

        # ===== METADATA =====
        # Use measured decision impact (v3.3 campaign-level sum)
        'decision_impact_dollars': round(decision_impact_dollars, 0),  # Measured v3.3 impact
        'decision_impact_dollars_topdown': round(decision_effect_roas_topdown * after_spend, 0),  # Top-down calculation
        'attribution_gap': round(attribution_gap, 4),  # Difference between methods
        'total_spend': round(after_spend, 0),
        'model_version': 'v3.5.0' if timeline else 'v3.4.0',  # v3.5 = Timeline-based ROAS

        # Timeline metadata (v3.5 only)
        'timeline': timeline if timeline else None,
        'uses_timeline': timeline is not None,

        # Data availability flags
        'clicks_available': clicks_available,
        'market_shift_clipped': False,

        # For "VALUE CREATED" box calculation
        'counterfactual_roas': round(max(0.01, counterfactual_roas), 2),

        # Prior and current metrics (for compatibility with existing UI)
        'prior_metrics': {
            'roas': baseline_roas,
            'cpc': baseline_cpc,
            'spc': baseline_spc,
        },
        'current_metrics': {
            'roas': actual_roas,
            'cpc': actual_cpc,
            'spc': actual_spc,
        }
    }


def _empty_waterfall() -> Dict[str, Any]:
    """Return empty waterfall structure."""
    return {
        'baseline_roas': 0,
        'actual_roas': 0,
        'total_change': 0,
        # v3.4 components
        'macro_impact': 0,
        'micro_impact': 0,
        'optimization_impact': 0,
        'residual': 0,
        # Legacy compatibility
        'combined_forces': 0,
        'decision_effect': 0,
        # Detailed breakdown
        'market_effect': 0,
        'market_shift': 1.0,
        'spc_change_pct': 0,
        'market_drag': 0,
        'market_drag_dollars': 0,
        'cpc_effect': 0,
        'baseline_cpc': 0,
        'actual_cpc': 0,
        'cpc_change_pct': 0,
        'scale_effect': 0,
        'portfolio_effect': 0,
        'structural_total': 0,
        'baseline_spc': 0,
        'actual_spc': 0,
        'spend_change_pct': 0,
        # Percentages
        'market_pct': 0,
        'market_drag_pct': 0,
        'cpc_pct': 0,
        'structural_pct': 0,
        'macro_pct': 0,
        'micro_pct': 0,
        'optimization_pct': 0,
        'residual_pct': 0,
        'combined_pct': 0,
        'decision_pct': 0,
        # External/Internal split
        'external_effect': 0,
        'external_pct': 0,
        'internal_effect': 0,
        'internal_pct': 0,
        'optimization_effect': 0,
        'optimization_effect_pct': 0,
        # Metadata
        'is_valid': False,
        'quality_flag': '✗ No Data',
        'residual_magnitude': 0,
        'decision_impact_dollars': 0,
        'total_spend': 0,
        'model_version': 'v3.4.0',
        'counterfactual_roas': 0,
        'prior_metrics': {'roas': 0, 'cpc': 0, 'spc': 0},
        'current_metrics': {'roas': 0, 'cpc': 0, 'spc': 0}
    }


# =========================================================
# INFORMATIONAL: CPC/CVR/AOV Breakdown
# =========================================================
def get_market_breakdown_display(
    prior_cpc: float,
    current_cpc: float,
    baseline_roas: float,
    market_effect_roas: float
) -> Dict[str, Any]:
    """
    Calculate CPC/CVR/AOV breakdown for DISPLAY purposes only.

    Note: These are informational and may not sum perfectly to market_effect
    due to the counterfactual approach used in v3.3.

    This is provided for user understanding but NOT used in the waterfall math.
    """

    cpc_change_pct = (current_cpc - prior_cpc) / prior_cpc if prior_cpc > 0 else 0

    # CPC impact (informational - uses linear approximation)
    cpc_impact_display = -cpc_change_pct * baseline_roas

    # CVR+AOV combined (residual of market effect after CPC)
    cvr_aov_combined_display = market_effect_roas - cpc_impact_display

    # Note: We'd need actual CVR/AOV data to split this further
    # For now, we show it as combined "conversion efficiency"

    return {
        'cpc_impact': round(cpc_impact_display, 2),
        'cpc_change_pct': round(cpc_change_pct * 100, 1),
        'cvr_aov_combined': round(cvr_aov_combined_display, 2),
        'note': 'Informational only - actual market effect uses SPC shift counterfactual'
    }
