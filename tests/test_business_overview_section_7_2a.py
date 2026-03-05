import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from features.dashboard.business_overview import (  # noqa: E402
    build_tacos_daily_series,
    build_tacos_trend_figure,
    compute_health_and_callouts,
    prepare_product_performance_table,
)
from features.dashboard.constants import DEFAULT_TARGET_TACOS  # noqa: E402


def test_score_computation_full_data():
    score, callouts, diagnostics = compute_health_and_callouts(
        ad_spend_current=100.0,
        total_sales_current=2000.0,
        organic_sales_current=1200.0,
        ad_sales_current=800.0,
        avg_days_cover_current=35.0,
        sessions_current=1000.0,
        units_current=120.0,
        sessions_previous=900.0,
        units_previous=90.0,
        target_tacos=0.10,
    )
    assert score.score is not None
    assert score.components_used == 4
    assert len(callouts) == 3
    assert diagnostics["tacos_current"] is not None


def test_score_computation_missing_components():
    score, callouts, _ = compute_health_and_callouts(
        ad_spend_current=100.0,
        total_sales_current=None,
        organic_sales_current=None,
        ad_sales_current=None,
        avg_days_cover_current=None,
        sessions_current=None,
        units_current=None,
        sessions_previous=None,
        units_previous=None,
        target_tacos=0.10,
    )
    assert score.score is None
    assert score.state == "neutral"
    assert callouts == []


def test_driver_callout_math_reconciles_to_contributions():
    score, callouts, _ = compute_health_and_callouts(
        ad_spend_current=250.0,
        total_sales_current=2000.0,
        organic_sales_current=1000.0,
        ad_sales_current=1000.0,
        avg_days_cover_current=20.0,
        sessions_current=1200.0,
        units_current=100.0,
        sessions_previous=1200.0,
        units_previous=120.0,
        target_tacos=0.10,
    )
    base_weights = {
        "tacos_vs_target": 0.30,
        "organic_paid_ratio": 0.25,
        "inventory_days_cover": 0.25,
        "cvr_trend": 0.20,
    }
    for c in callouts:
        contribution = score.weighted_components[c.key]
        expected_impact = round((base_weights[c.key] * 100.0) - contribution, 1)
        assert round(c.impact_points, 1) == expected_impact


def test_tacos_target_line_default_fallback():
    df = pd.DataFrame(
        {
            "report_date": pd.to_datetime(["2026-02-01", "2026-02-02"]),
            "tacos": [0.12, 0.08],
        }
    )
    fig = build_tacos_trend_figure(df, target_tacos=None)
    assert len(fig.data) == 2
    target_trace = fig.data[1]
    assert list(target_trace.y) == [DEFAULT_TARGET_TACOS, DEFAULT_TARGET_TACOS]


def test_tacos_daily_series_filters_invalid_denominators_and_zero_spend():
    curr_period = pd.DataFrame(
        {
            "report_date": pd.to_datetime(["2026-02-01", "2026-02-02", "2026-02-03"]),
            "total_ordered_revenue": [1000.0, 1200.0, 0.0],
        }
    )
    ad_spend_daily = pd.DataFrame(
        {
            "report_date": pd.to_datetime(["2026-02-01", "2026-02-02", "2026-02-03"]),
            "ad_spend": [100.0, 0.0, 50.0],
        }
    )
    out = build_tacos_daily_series(curr_period, ad_spend_daily)
    assert len(out) == 1
    assert float(out.iloc[0]["tacos"]) == 0.1


def test_tacos_daily_series_filters_outliers_from_raw_daily_spend():
    curr_period = pd.DataFrame(
        {
            "report_date": pd.to_datetime(["2026-02-01", "2026-02-02", "2026-02-03"]),
            "total_ordered_revenue": [1000.0, 100.0, 800.0],
        }
    )
    ad_spend_daily = pd.DataFrame(
        {
            "report_date": pd.to_datetime(["2026-02-01", "2026-02-02", "2026-02-03"]),
            "ad_spend": [120.0, 140.0, 0.0],
        }
    )
    out = build_tacos_daily_series(curr_period, ad_spend_daily)
    assert len(out) == 1
    assert float(out.iloc[0]["tacos"]) == 0.12


def test_product_table_default_sort_tacos_desc():
    raw = pd.DataFrame(
        {
            "parent_asin_sku": ["A", "B", "C"],
            "sku": ["a", "b", "c"],
            "sessions": [100, 100, 100],
            "page_views": [200, 200, 200],
            "units": [10, 10, 10],
            "sales": [1000, 1000, 1000],
            "ad_spend": [100, 250, 50],
            "ad_sales": [500, 500, 500],
            "days_of_cover": [20, 20, 20],
        }
    )
    out = prepare_product_performance_table(raw)
    assert list(out["Parent ASIN / SKU"]) == ["B", "A", "C"]
