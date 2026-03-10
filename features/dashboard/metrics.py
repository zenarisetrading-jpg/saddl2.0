"""Centralized metric computations for Performance Dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Dict, Optional


def _safe_div(numerator: float, denominator: float) -> Optional[float]:
    if denominator in (None, 0):
        return None
    value = numerator / denominator
    return value if isfinite(value) else None


def calculate_roas(ad_sales: float, ad_spend: float) -> Optional[float]:
    return _safe_div(ad_sales, ad_spend)


def calculate_tacos(ad_spend: float, total_sales: float) -> Optional[float]:
    result = _safe_div(ad_spend, total_sales)
    if result is None:
        return None
    # Returns percentage scale — 25 means 25% TACoS
    return result * 100


def calculate_cvr(orders: float, sessions: float) -> Optional[float]:
    return _safe_div(orders, sessions)


def calculate_organic_pct(organic_sales: float, total_sales: float) -> Optional[float]:
    return _safe_div(organic_sales, total_sales)


def calculate_days_of_cover(fba_units: float, daily_units_sold: float) -> Optional[float]:
    return _safe_div(fba_units, daily_units_sold)


def calculate_aov(total_sales: float, units_sold: float) -> Optional[float]:
    return _safe_div(total_sales, units_sold)


def calculate_delta_pct(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None or previous == 0:
        return None
    value = ((current - previous) / abs(previous)) * 100.0
    return value if isfinite(value) else None


def score_against_target_lower_better(actual: Optional[float], target: Optional[float]) -> Optional[float]:
    if actual is None or target in (None, 0):
        return None
    if actual <= target:
        return 100.0
    over = ((actual - target) / target) * 100.0
    return _clamp_0_100(100.0 - over)


def score_ratio_higher_better(actual: Optional[float], baseline: float = 1.0) -> Optional[float]:
    if actual is None or baseline == 0:
        return None
    return _clamp_0_100((actual / baseline) * 100.0)


def score_trend_delta(delta_pct: Optional[float], sensitivity: float = 1.0) -> Optional[float]:
    if delta_pct is None:
        return None
    return _clamp_0_100(50.0 + (delta_pct * sensitivity))


@dataclass(frozen=True)
class HealthScoreResult:
    score: Optional[float]
    is_partial: bool
    state: str
    components_used: int
    weighted_components: Dict[str, float]


def _clamp_0_100(value: float) -> float:
    return max(0.0, min(100.0, value))


def compute_account_health_score(
    *,
    tacos_vs_target_score: Optional[float],
    organic_paid_ratio_score: Optional[float],
    inventory_days_cover_score: Optional[float],
    cvr_trend_score: Optional[float],
) -> HealthScoreResult:
    """
    Weighted account health score.

    Rules:
    - Weights: TACOS 30%, organic/paid ratio 25%, inventory 25%, CVR trend 20%.
    - If fewer than 2 valid components exist -> neutral fallback (score=None).
    - If 2-3 valid components exist -> proportional reweighting and partial state.
    - Clamp final score to [0, 100].
    """
    base_weights = {
        "tacos_vs_target": 0.30,
        "organic_paid_ratio": 0.25,
        "inventory_days_cover": 0.25,
        "cvr_trend": 0.20,
    }
    raw_scores = {
        "tacos_vs_target": tacos_vs_target_score,
        "organic_paid_ratio": organic_paid_ratio_score,
        "inventory_days_cover": inventory_days_cover_score,
        "cvr_trend": cvr_trend_score,
    }

    valid_scores = {
        key: float(value)
        for key, value in raw_scores.items()
        if value is not None and isfinite(float(value))
    }
    components_used = len(valid_scores)

    if components_used < 2:
        return HealthScoreResult(
            score=None,
            is_partial=False,
            state="neutral",
            components_used=components_used,
            weighted_components={},
        )

    valid_weight_sum = sum(base_weights[key] for key in valid_scores)
    weighted_components: Dict[str, float] = {}
    total = 0.0

    for key, score in valid_scores.items():
        normalized_weight = base_weights[key] / valid_weight_sum
        contribution = _clamp_0_100(score) * normalized_weight
        weighted_components[key] = contribution
        total += contribution

    return HealthScoreResult(
        score=round(_clamp_0_100(total), 2),
        is_partial=components_used < 4,
        state="partial" if components_used < 4 else "full",
        components_used=components_used,
        weighted_components=weighted_components,
    )
