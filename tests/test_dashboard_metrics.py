import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from features.dashboard.constants import DEFAULT_TARGET_ROAS, DEFAULT_TARGET_TACOS
from features.dashboard.metrics import (
    calculate_cvr,
    calculate_days_of_cover,
    calculate_organic_pct,
    calculate_roas,
    calculate_tacos,
    compute_account_health_score,
)


def test_target_defaults():
    assert DEFAULT_TARGET_ROAS == 3.0
    assert DEFAULT_TARGET_TACOS == 0.10


def test_core_metric_division_safety():
    assert calculate_roas(300, 100) == 3.0
    assert calculate_tacos(100, 1000) == 0.1
    assert calculate_cvr(25, 500) == 0.05
    assert calculate_organic_pct(700, 1000) == 0.7
    assert calculate_days_of_cover(420, 14) == 30.0
    assert calculate_roas(100, 0) is None
    assert calculate_tacos(100, 0) is None


def test_health_score_full_components():
    result = compute_account_health_score(
        tacos_vs_target_score=80,
        organic_paid_ratio_score=70,
        inventory_days_cover_score=90,
        cvr_trend_score=60,
    )
    expected = (80 * 0.30) + (70 * 0.25) + (90 * 0.25) + (60 * 0.20)
    assert result.score == round(expected, 2)
    assert result.state == "full"
    assert result.is_partial is False
    assert result.components_used == 4


def test_health_score_minimum_data_floor():
    one_component = compute_account_health_score(
        tacos_vs_target_score=85,
        organic_paid_ratio_score=None,
        inventory_days_cover_score=None,
        cvr_trend_score=None,
    )
    assert one_component.score is None
    assert one_component.state == "neutral"
    assert one_component.is_partial is False


def test_health_score_partial_reweighting():
    result = compute_account_health_score(
        tacos_vs_target_score=100,
        organic_paid_ratio_score=None,
        inventory_days_cover_score=50,
        cvr_trend_score=None,
    )
    # Valid base weights are 0.30 and 0.25 -> normalized to 0.54545 and 0.45455
    expected = (100 * (0.30 / 0.55)) + (50 * (0.25 / 0.55))
    assert result.score == round(expected, 2)
    assert result.state == "partial"
    assert result.is_partial is True
    assert result.components_used == 2


def test_health_score_clamped():
    result = compute_account_health_score(
        tacos_vs_target_score=250,
        organic_paid_ratio_score=200,
        inventory_days_cover_score=180,
        cvr_trend_score=160,
    )
    assert result.score == 100.0
