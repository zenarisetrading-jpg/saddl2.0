"""
Confidence Classification - Statistical confidence calculations for impact metrics.
"""

from math import sqrt
from typing import Dict, Any

import pandas as pd


def compute_confidence(
    actions_df: pd.DataFrame,
    min_validated_actions: int = 30
) -> Dict[str, Any]:
    """
    Compute confidence classification for aggregated Decision Impact.

    Confidence is a classification layer only — does NOT alter impact values.
    Based on signal-to-noise ratio derived from data sufficiency, market conditions, and variance.

    Args:
        actions_df: DataFrame with columns: decision_impact, confidence_weight, market_tag, is_validated
        min_validated_actions: Minimum validated actions needed for "High" confidence

    Returns:
        dict with: confidence ("High"/"Medium"/"Low"), signalRatio, totalSigma
    """
    if actions_df.empty:
        return {"confidence": "Low", "signalRatio": 0.0, "totalSigma": 0.0}

    # Filter to validated actions
    validated = actions_df[actions_df.get('is_validated', False) == True].copy()

    if len(validated) == 0:
        return {"confidence": "Low", "signalRatio": 0.0, "totalSigma": 0.0}

    total_impact = 0.0
    variance_sum = 0.0
    downshift_impact = 0.0

    for _, row in validated.iterrows():
        # Use direct column access for pandas Series (not dict .get())
        impact = row['decision_impact'] if pd.notna(row['decision_impact']) else 0
        total_impact += impact

        # Per-action variance: sigma_i = abs(impact) * (1 - confidence_weight)
        cw = row['confidence_weight'] if 'confidence_weight' in row.index and pd.notna(row['confidence_weight']) else 0.5
        sigma = abs(impact) * (1 - cw)

        # Apply market multiplier for downshift
        market_tag = row['market_tag'] if 'market_tag' in row.index else 'Normal'
        if market_tag == "Market Downshift":
            sigma *= 1.3
            downshift_impact += abs(impact)

        variance_sum += sigma ** 2

    # Aggregate variance
    total_sigma = sqrt(variance_sum) if variance_sum > 0 else 0

    # Signal-to-noise ratio
    signal_ratio = abs(total_impact) / total_sigma if total_sigma > 0 else 0

    # Confidence classification
    if signal_ratio >= 1.5 and len(validated) >= min_validated_actions:
        confidence = "High"
    elif signal_ratio >= 0.8:
        confidence = "Medium"
    else:
        confidence = "Low"

    # Optional downgrade: if >40% of impact from Market Downshift
    downshift_ratio = downshift_impact / abs(total_impact) if total_impact != 0 else 0
    if downshift_ratio > 0.4:
        if confidence == "High":
            confidence = "Medium"
        elif confidence == "Medium":
            confidence = "Low"

    return {
        "confidence": confidence,
        "signalRatio": round(signal_ratio, 2),
        "totalSigma": round(total_sigma, 2)
    }


def compute_spend_avoided_confidence(
    actions_df: pd.DataFrame,
    min_validated_actions: int = 10
) -> Dict[str, Any]:
    """
    Compute confidence classification for Spend Avoided summary.

    Uses auction variance (not revenue CW) - reflects auction stability.
    Variance factors: Normal = 0.15, Market Downshift = 0.25

    Args:
        actions_df: DataFrame with columns: before_spend, observed_after_spend, market_tag, is_validated
        min_validated_actions: Minimum validated actions for "High" confidence

    Returns:
        dict with: confidence, signalRatio, totalSigma, totalSpendAvoided
    """
    if actions_df.empty:
        return {"confidence": "Low", "signalRatio": 0.0, "totalSigma": 0.0, "totalSpendAvoided": 0.0}

    # Filter to validated actions only
    validated = actions_df[actions_df.get('is_validated', False) == True].copy()

    if len(validated) == 0:
        return {"confidence": "Low", "signalRatio": 0.0, "totalSigma": 0.0, "totalSpendAvoided": 0.0}

    total_spend_avoided = 0.0
    variance_sum = 0.0
    downshift_spend_avoided = 0.0
    valid_action_count = 0

    # Auction variance factors
    VARIANCE_NORMAL = 0.15
    VARIANCE_DOWNSHIFT = 0.25

    for _, row in validated.iterrows():
        before_spend = row['before_spend'] if pd.notna(row['before_spend']) else 0
        after_spend = row['observed_after_spend'] if 'observed_after_spend' in row.index and pd.notna(row['observed_after_spend']) else 0

        # Spend avoided = max(0, before - after)
        spend_avoided = max(0, before_spend - after_spend)

        # Skip rows with zero spend avoided
        if spend_avoided == 0:
            continue

        total_spend_avoided += spend_avoided
        valid_action_count += 1

        # Determine auction variance factor
        market_tag = row['market_tag'] if 'market_tag' in row.index else 'Normal'
        variance_factor = VARIANCE_DOWNSHIFT if market_tag == "Market Downshift" else VARIANCE_NORMAL

        # Per-action variance: sigma_i = spend_avoided * variance_factor
        sigma = spend_avoided * variance_factor

        if market_tag == "Market Downshift":
            downshift_spend_avoided += spend_avoided

        variance_sum += sigma ** 2

    # Aggregate variance
    total_sigma = sqrt(variance_sum) if variance_sum > 0 else 0

    # Signal-to-noise ratio
    signal_ratio = total_spend_avoided / total_sigma if total_sigma > 0 else 0

    # Confidence classification (stricter thresholds than Decision Impact)
    if signal_ratio >= 2.0 and valid_action_count >= min_validated_actions:
        confidence = "High"
    elif signal_ratio >= 1.0:
        confidence = "Medium"
    else:
        confidence = "Low"

    # Optional downgrade: if >30% of spend avoided from Market Downshift
    downshift_ratio = downshift_spend_avoided / total_spend_avoided if total_spend_avoided > 0 else 0
    if downshift_ratio > 0.3:
        if confidence == "High":
            confidence = "Medium"
        elif confidence == "Medium":
            confidence = "Low"

    return {
        "confidence": confidence,
        "signalRatio": round(signal_ratio, 2),
        "totalSigma": round(total_sigma, 2),
        "totalSpendAvoided": round(total_spend_avoided, 2)
    }
