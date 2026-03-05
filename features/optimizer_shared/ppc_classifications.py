"""
PPC Intelligence Classifications — Shared Pure Functions

Zero Streamlit/Plotly/UI dependencies. These functions are the single source of
truth for target/campaign/account classification logic used by:
  - PPC Overview (ppc_overview.py) — display labels
  - Executive Dashboard (executive_dashboard.py) — quadrant charts
  - Optimizer Cascade (ppc_cascade.py) — row enrichment before bid engine

Thresholds are copied exactly from the UI files so both surfaces always agree.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# 1. KEYWORD DIAGNOSTIC CLASSIFIER
#    Source: ppc_overview.py _classify_keyword() — thresholds copied exactly
# ---------------------------------------------------------------------------

def classify_keyword_diagnostic(
    spend: float,
    sales: float,
    roas: float,
    target_roas: float,
    clicks: int = 0,
    impressions: int = 0,
) -> str:
    """
    Classify a target's diagnostic status.

    Returns one of:
        'zero_conversion' — spending > $50 with zero sales
        'under_bid'       — ROAS more than 1.5× above target (could bid more)
        'over_spend'      — ROAS below target (spending more than justified)
        'optimized'       — within acceptable range

    Thresholds mirror ppc_overview.py _classify_keyword() exactly.
    """
    if sales == 0 and spend > 50:
        return "zero_conversion"
    if roas > 0 and roas > target_roas * 1.5:
        return "under_bid"
    if roas < target_roas:
        return "over_spend"
    return "optimized"


# ---------------------------------------------------------------------------
# 2. PERFORMANCE QUADRANT CLASSIFIER
#    Source: executive_dashboard.py classify() — thresholds copied exactly
#    NOTE: avg_roas and avg_cvr must be WEIGHTED averages (total_sales/total_spend,
#    total_orders/total_clicks*100), not simple means of per-row ratios.
# ---------------------------------------------------------------------------

def classify_performance_quadrant(
    roas: float,
    cvr: float,
    avg_roas: float,
    avg_cvr: float,
) -> str:
    """
    Classify a target into a performance quadrant.

    Returns one of:
        'stars'            — ROAS >= avg AND CVR >= avg
        'scale_potential'  — ROAS >= avg AND CVR < avg
        'profit_potential' — ROAS < avg  AND CVR >= avg
        'cut'              — ROAS < avg  AND CVR < avg

    avg_roas / avg_cvr must be caller-computed weighted averages:
        avg_roas = total_sales / total_spend
        avg_cvr  = (total_orders / total_clicks) * 100

    Comparison uses >= consistent with executive_dashboard.py.
    """
    if roas >= avg_roas and cvr >= avg_cvr:
        return "stars"
    if roas >= avg_roas:
        return "scale_potential"
    if cvr >= avg_cvr:
        return "profit_potential"
    return "cut"


# ---------------------------------------------------------------------------
# 3. CAMPAIGN EFFICIENCY INDEX CLASSIFIER
#    New classification (no prior implementation). Thresholds from spec.
# ---------------------------------------------------------------------------

def classify_campaign_efficiency(
    revenue_share_pct: float,
    spend_share_pct: float,
) -> tuple[str, float]:
    """
    Classify a campaign's efficiency index.

    ratio = revenue_share_pct / spend_share_pct
      - ratio > 1.0       → 'amplifier' (generates more revenue than spend share)
      - 0.75 <= ratio <= 1.0 → 'balanced'
      - 0.5  <= ratio < 0.75 → 'review'
      - ratio < 0.5       → 'drag'

    Returns (label, ratio).
    If spend_share_pct is 0, returns ('drag', 0.0) to avoid division by zero.
    """
    if spend_share_pct <= 0:
        return ("drag", 0.0)

    ratio = revenue_share_pct / spend_share_pct

    if ratio > 1.0:
        label = "amplifier"
    elif ratio >= 0.75:
        label = "balanced"
    elif ratio >= 0.5:
        label = "review"
    else:
        label = "drag"

    return (label, round(ratio, 4))


# ---------------------------------------------------------------------------
# 4. ACCOUNT HEALTH TREND CLASSIFIER
#    New function — computes trend direction from current vs. prior period.
# ---------------------------------------------------------------------------

def classify_account_health(
    roas_current: float,
    roas_prior: float,
    acos_current: float,
    acos_prior: float,
) -> dict:
    """
    Compute account-level health context from current vs. prior period.

    Returns dict with:
        roas_trend_pct  — float, e.g. +21.2 means ROAS improved 21.2%
        acos_trend_pct  — float, e.g. -17.5 means ACOS improved (fell) 17.5%
        health_signal   — 'improving' | 'stable' | 'declining'

    Health signal thresholds:
        improving: ROAS up > 10% AND ACOS down > 10%
        declining: ROAS down > 10% OR  ACOS up   > 10%
        stable:    everything else
    """
    roas_trend_pct = (
        (roas_current - roas_prior) / roas_prior * 100
        if roas_prior > 0
        else 0.0
    )
    acos_trend_pct = (
        (acos_current - acos_prior) / acos_prior * 100
        if acos_prior > 0
        else 0.0
    )

    if roas_trend_pct > 10 and acos_trend_pct < -10:
        health_signal = "improving"
    elif roas_trend_pct < -10 or acos_trend_pct > 10:
        health_signal = "declining"
    else:
        health_signal = "stable"

    return {
        "roas_trend_pct": round(roas_trend_pct, 1),
        "acos_trend_pct": round(acos_trend_pct, 1),
        "health_signal": health_signal,
    }


# ---------------------------------------------------------------------------
# SELF-TESTS — run with: python -m features.optimizer_shared.ppc_classifications
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # --- keyword diagnostic ---
    assert classify_keyword_diagnostic(spend=100, sales=0, roas=0, target_roas=2.5) == "zero_conversion", \
        "high spend + zero sales → zero_conversion"
    assert classify_keyword_diagnostic(spend=30, sales=0, roas=0, target_roas=2.5) == "over_spend", \
        "low spend + zero sales → not zero_conversion (spend <= 50), roas(0) < target → over_spend"
    assert classify_keyword_diagnostic(spend=100, sales=500, roas=5.0, target_roas=2.5) == "under_bid", \
        "roas 5.0 > 2.5*1.5=3.75 → under_bid"
    assert classify_keyword_diagnostic(spend=100, sales=200, roas=2.0, target_roas=2.5) == "over_spend", \
        "roas 2.0 < target 2.5 → over_spend"
    assert classify_keyword_diagnostic(spend=100, sales=300, roas=3.0, target_roas=2.5) == "optimized", \
        "roas 3.0 >= target 2.5 and <= 2.5*1.5=3.75 → optimized"
    # Boundary: exactly at 1.5× threshold → NOT under_bid (roas > not >=)
    assert classify_keyword_diagnostic(spend=100, sales=375, roas=3.75, target_roas=2.5) == "optimized", \
        "roas exactly at 1.5× threshold → optimized (not strictly greater)"

    print("✓ classify_keyword_diagnostic — all tests passed")

    # --- performance quadrant ---
    assert classify_performance_quadrant(roas=5.0, cvr=10.0, avg_roas=3.0, avg_cvr=7.0) == "stars"
    assert classify_performance_quadrant(roas=5.0, cvr=3.0, avg_roas=3.0, avg_cvr=7.0) == "scale_potential"
    assert classify_performance_quadrant(roas=1.0, cvr=10.0, avg_roas=3.0, avg_cvr=7.0) == "profit_potential"
    assert classify_performance_quadrant(roas=1.0, cvr=2.0, avg_roas=3.0, avg_cvr=7.0) == "cut"
    # Boundary: exactly at avg → stars (>= not >)
    assert classify_performance_quadrant(roas=3.0, cvr=7.0, avg_roas=3.0, avg_cvr=7.0) == "stars"

    print("✓ classify_performance_quadrant — all tests passed")

    # --- campaign efficiency ---
    label, ratio = classify_campaign_efficiency(revenue_share_pct=30, spend_share_pct=10)
    assert label == "amplifier" and ratio == 3.0, f"got {label}, {ratio}"

    label, ratio = classify_campaign_efficiency(revenue_share_pct=10, spend_share_pct=10)
    assert label == "balanced" and ratio == 1.0, f"got {label}, {ratio}"

    label, ratio = classify_campaign_efficiency(revenue_share_pct=8, spend_share_pct=10)
    assert label == "balanced" and ratio == 0.8, f"got {label}, {ratio}"

    label, ratio = classify_campaign_efficiency(revenue_share_pct=6, spend_share_pct=10)
    assert label == "review" and ratio == 0.6, f"got {label}, {ratio}"

    label, ratio = classify_campaign_efficiency(revenue_share_pct=3, spend_share_pct=10)
    assert label == "drag" and ratio == 0.3, f"got {label}, {ratio}"

    label, ratio = classify_campaign_efficiency(revenue_share_pct=0, spend_share_pct=0)
    assert label == "drag" and ratio == 0.0, "zero spend share → drag"

    print("✓ classify_campaign_efficiency — all tests passed")

    # --- account health ---
    health = classify_account_health(
        roas_current=2.79, roas_prior=2.30,
        acos_current=35.79, acos_prior=43.40,
    )
    assert health["health_signal"] == "improving", f"got {health}"
    assert health["roas_trend_pct"] > 0
    assert health["acos_trend_pct"] < 0

    health2 = classify_account_health(
        roas_current=2.0, roas_prior=2.30,
        acos_current=50.0, acos_prior=43.40,
    )
    assert health2["health_signal"] == "declining", f"got {health2}"

    health3 = classify_account_health(
        roas_current=2.3, roas_prior=2.30,
        acos_current=43.4, acos_prior=43.40,
    )
    assert health3["health_signal"] == "stable", f"got {health3}"

    health_no_prior = classify_account_health(
        roas_current=2.5, roas_prior=0,
        acos_current=40.0, acos_prior=0,
    )
    assert health_no_prior["health_signal"] == "stable"

    print("✓ classify_account_health — all tests passed")
    print("\nAll classification tests passed ✓")
