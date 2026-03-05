"""
PPC Intelligence Cascade

Runs BEFORE the V2.1 intelligence flags (INVENTORY_RISK, HALO_ACTIVE, etc.).
Enriches the optimizer DataFrame with four layers of context:

    Layer 1: Account health signal (improving / stable / declining)
    Layer 2: Campaign efficiency per campaign (amplifier / balanced / review / drag)
             + campaign_total_orders for volume-conviction in the bid engine
    Layer 3: Keyword diagnostic per target (zero_conversion / under_bid / over_spend / optimized)
    Layer 4: Performance quadrant per target (stars / cut / profit_potential / scale_potential)

These columns are then consumed by:
    - campaign_recommendations.py  (Tier 1 campaign-level recommendations)
    - bids.py                      (volume-weighted cascade flag checks)

All new columns default to None if computation fails. Downstream code handles None gracefully.
"""

from __future__ import annotations

import pandas as pd
from features.optimizer_shared.ppc_classifications import (
    classify_keyword_diagnostic,
    classify_performance_quadrant,
    classify_campaign_efficiency,
    classify_account_health,
)


def compute_ppc_cascade(
    df: pd.DataFrame,
    target_roas: float,
    account_metrics_current: dict | None = None,
    account_metrics_prior: dict | None = None,
) -> pd.DataFrame:
    """
    Enrich the optimizer DataFrame with PPC intelligence cascade columns.

    Parameters
    ----------
    df : pd.DataFrame
        The optimizer's working DataFrame after prepare_data() has run.
        Expected columns: Campaign Name, Spend, Sales, Orders, Clicks, ROAS, CVR.
    target_roas : float
        Account-level ROAS target from client config (config["TARGET_ROAS"]).
    account_metrics_current : dict or None
        Keys 'roas' and 'acos' for the current period. Pass None to skip.
    account_metrics_prior : dict or None
        Keys 'roas' and 'acos' for the prior period. Pass None to skip
        (account_health_signal will be None — cascade degrades gracefully).

    Returns
    -------
    pd.DataFrame
        df copy with these new columns:
          account_health_signal     : str or None
          campaign_efficiency_label : str or None
          campaign_efficiency_ratio : float or None
          campaign_total_orders     : int or None  (for bid-engine conviction)
          ppc_diagnostic            : str or None
          ppc_quadrant              : str or None
    """
    df = df.copy()

    # ── Identify column names (defensive — handle both cases) ─────────────────
    campaign_col = _find_col(df, ["Campaign Name", "Campaign", "campaign_name", "campaign"])
    spend_col    = _find_col(df, ["Spend", "spend", "Cost", "cost"])
    sales_col    = _find_col(df, ["Sales", "sales"])
    roas_col     = _find_col(df, ["ROAS", "roas"])
    clicks_col   = _find_col(df, ["Clicks", "clicks"])
    orders_col   = _find_col(df, ["Orders", "orders", "Units Ordered", "Conversions"])
    cvr_col      = _find_col(df, ["CVR", "cvr", "Conversion Rate", "conversion_rate"])
    impressions_col = _find_col(df, ["Impressions", "impressions"])

    # ── Layer 1: Account Health Context ───────────────────────────────────────
    if account_metrics_current and account_metrics_prior:
        try:
            health = classify_account_health(
                roas_current=float(account_metrics_current.get("roas", 0) or 0),
                roas_prior=float(account_metrics_prior.get("roas", 0) or 0),
                acos_current=float(account_metrics_current.get("acos", 0) or 0),
                acos_prior=float(account_metrics_prior.get("acos", 0) or 0),
            )
            df["account_health_signal"] = health["health_signal"]
        except Exception:
            df["account_health_signal"] = None
    else:
        df["account_health_signal"] = None

    # ── Layer 2: Campaign Efficiency Context ──────────────────────────────────
    if campaign_col and spend_col and sales_col:
        total_spend = df[spend_col].sum()
        total_sales = df[sales_col].sum()

        if total_spend > 0 and total_sales > 0:
            try:
                camp_stats = df.groupby(campaign_col).agg(
                    camp_spend=(spend_col, "sum"),
                    camp_sales=(sales_col, "sum"),
                ).reset_index()

                camp_stats["spend_share_pct"] = (camp_stats["camp_spend"] / total_spend) * 100
                camp_stats["revenue_share_pct"] = (camp_stats["camp_sales"] / total_sales) * 100

                camp_stats[["campaign_efficiency_label", "campaign_efficiency_ratio"]] = (
                    camp_stats.apply(
                        lambda r: pd.Series(
                            classify_campaign_efficiency(r["revenue_share_pct"], r["spend_share_pct"])
                        ),
                        axis=1,
                    )
                )

                # campaign_total_orders — for volume conviction in bid engine
                if orders_col:
                    camp_orders = (
                        df.groupby(campaign_col)[orders_col]
                        .sum()
                        .reset_index()
                        .rename(columns={orders_col: "campaign_total_orders"})
                    )
                    camp_stats = camp_stats.merge(camp_orders, on=campaign_col, how="left")
                else:
                    camp_stats["campaign_total_orders"] = None

                df = df.merge(
                    camp_stats[[
                        campaign_col,
                        "campaign_efficiency_label",
                        "campaign_efficiency_ratio",
                        "campaign_total_orders",
                    ]],
                    on=campaign_col,
                    how="left",
                )
            except Exception:
                df["campaign_efficiency_label"] = None
                df["campaign_efficiency_ratio"] = None
                df["campaign_total_orders"] = None
        else:
            df["campaign_efficiency_label"] = None
            df["campaign_efficiency_ratio"] = None
            df["campaign_total_orders"] = None
    else:
        df["campaign_efficiency_label"] = None
        df["campaign_efficiency_ratio"] = None
        df["campaign_total_orders"] = None

    # ── Layer 3: Target Keyword Diagnostic ────────────────────────────────────
    if spend_col and sales_col and roas_col:
        try:
            def _diag(r):
                return classify_keyword_diagnostic(
                    spend=float(r.get(spend_col, 0) or 0),
                    sales=float(r.get(sales_col, 0) or 0),
                    roas=float(r.get(roas_col, 0) or 0),
                    target_roas=target_roas,
                    clicks=int(r.get(clicks_col, 0) or 0) if clicks_col else 0,
                    impressions=int(r.get(impressions_col, 0) or 0) if impressions_col else 0,
                )
            df["ppc_diagnostic"] = df.apply(_diag, axis=1)
        except Exception:
            df["ppc_diagnostic"] = None
    else:
        df["ppc_diagnostic"] = None

    # ── Layer 4: Performance Quadrant ─────────────────────────────────────────
    # Uses WEIGHTED average (total_sales/total_spend, total_orders/total_clicks)
    # to match executive_dashboard.py exactly.
    if roas_col and cvr_col and spend_col and sales_col and clicks_col and orders_col:
        try:
            total_spend_all = df[spend_col].sum()
            total_sales_all = df[sales_col].sum()
            total_clicks_all = df[clicks_col].sum()
            total_orders_all = df[orders_col].sum()

            avg_roas = (total_sales_all / total_spend_all) if total_spend_all > 0 else 3.0
            avg_cvr  = (total_orders_all / total_clicks_all * 100) if total_clicks_all > 0 else 5.0
            if avg_roas <= 0:
                avg_roas = 3.0
            if avg_cvr <= 0:
                avg_cvr = 5.0

            def _quad(r):
                return classify_performance_quadrant(
                    roas=float(r.get(roas_col, 0) or 0),
                    cvr=float(r.get(cvr_col, 0) or 0),
                    avg_roas=avg_roas,
                    avg_cvr=avg_cvr,
                )
            df["ppc_quadrant"] = df.apply(_quad, axis=1)
        except Exception:
            df["ppc_quadrant"] = None
    else:
        df["ppc_quadrant"] = None

    return df


# ── Helper ────────────────────────────────────────────────────────────────────

def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the first candidate column name that exists in df, or None."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


# ── Graceful-degradation smoke test ───────────────────────────────────────────

if __name__ == "__main__":
    import pandas as pd

    df_test = pd.DataFrame({
        "Spend": [100.0, 50.0, 200.0],
        "Sales": [200.0, 0.0, 800.0],
        "ROAS":  [2.0,   0.0, 4.0],
        "Clicks":      [20, 10, 50],
        "Orders":      [4,  0,  20],
        "CVR":         [0.20, 0.0, 0.40],
        "Impressions": [1000, 500, 2000],
        "Campaign Name": ["camp_a", "camp_a", "camp_b"],
    })

    result = compute_ppc_cascade(df_test, target_roas=2.5)

    assert "ppc_diagnostic" in result.columns
    assert "ppc_quadrant" in result.columns
    assert "campaign_efficiency_label" in result.columns
    assert "campaign_efficiency_ratio" in result.columns
    assert "campaign_total_orders" in result.columns
    assert "account_health_signal" in result.columns

    # Row 0: spend=100, sales=200, roas=2.0 < target 2.5 → over_spend
    assert result.loc[0, "ppc_diagnostic"] == "over_spend", result.loc[0, "ppc_diagnostic"]
    # Row 1: spend=50, sales=0 → not > 50, roas(0) < target → over_spend
    assert result.loc[1, "ppc_diagnostic"] == "over_spend", result.loc[1, "ppc_diagnostic"]
    # Row 2: spend=200, sales=800, roas=4.0 > 2.5*1.5=3.75 → under_bid
    assert result.loc[2, "ppc_diagnostic"] == "under_bid", result.loc[2, "ppc_diagnostic"]

    # account_health_signal = None (no prior passed)
    assert result["account_health_signal"].isna().all() or (result["account_health_signal"] == None).all()

    # No CVR column scenario — ppc_quadrant should degrade gracefully
    df_no_cvr = df_test.drop(columns=["CVR"])
    result2 = compute_ppc_cascade(df_no_cvr, target_roas=2.5)
    assert result2["ppc_quadrant"].isna().all() or (result2["ppc_quadrant"] == None).all()

    print("compute_ppc_cascade — all smoke tests passed ✓")
