"""
Tier 1: Campaign-Level Recommendation Engine

Runs AFTER compute_ppc_cascade() enriches the DataFrame.
Groups by campaign and produces a one-row-per-campaign recommendation table
that the user reviews BEFORE looking at individual bid adjustments.

Recommendation types (priority order — first match wins):
    PAUSE          — Confirmed drain: low efficiency + low orders + below 50% of target ROAS
    REDUCE_BUDGET  — Bleeding but salvageable: low efficiency + low profitable-target %
    RESTRUCTURE    — Mixed bag: has profitable targets but also many zero-conversion targets
    SCALE          — Proven winner: high efficiency + high volume + well above target ROAS
    INCREASE_BUDGET — Good performer with room to grow
    MAINTAIN       — No immediate action needed

Design principles:
    - NEVER recommend PAUSE on a high-volume campaign (orders >= tier1_pause_max_orders)
    - NEVER recommend SCALE on thin data (< tier1_scale_min_orders)
    - Every recommendation includes the evidence (actual numbers)
    - One recommendation per campaign — first match wins
    - All thresholds configurable in core.py DEFAULT_CONFIG
"""

from __future__ import annotations

import pandas as pd


def generate_campaign_recommendations(
    df: pd.DataFrame,
    target_roas: float,
    cfg: dict,
) -> pd.DataFrame:
    """
    Generate Tier 1 campaign-level recommendations from cascade-enriched data.

    Parameters
    ----------
    df : pd.DataFrame
        Optimizer DataFrame AFTER compute_ppc_cascade() has run.
    target_roas : float
        Account-level ROAS target.
    cfg : dict
        Config dict from core.py (contains tier1_* thresholds).

    Returns
    -------
    pd.DataFrame with one row per campaign, columns:
        campaign_name, spend, sales, orders, roas, acos,
        efficiency_ratio, efficiency_label, target_count,
        pct_targets_profitable, pct_targets_zero_conv,
        recommendation, confidence, reason, estimated_monthly_impact
    Sorted: actionable first (PAUSE/SCALE/REDUCE/INCREASE/RESTRUCTURE), then by impact.
    """
    if not cfg.get("tier1_enabled", True):
        return pd.DataFrame()

    # ── Identify column names ─────────────────────────────────────────────────
    campaign_col   = _find_col(df, ["Campaign Name", "Campaign", "campaign_name", "campaign"])
    spend_col      = _find_col(df, ["Spend", "spend"])
    sales_col      = _find_col(df, ["Sales", "sales"])
    roas_col       = _find_col(df, ["ROAS", "roas"])
    clicks_col     = _find_col(df, ["Clicks", "clicks"])
    orders_col     = _find_col(df, ["Orders", "orders", "Units Ordered", "Conversions"])
    match_type_col = _find_col(df, ["Match Type", "match_type", "Bucket"])

    if not campaign_col or not spend_col or not sales_col:
        return pd.DataFrame()

    # ── Configurable thresholds ───────────────────────────────────────────────
    pause_max_eff        = cfg.get("tier1_pause_max_efficiency", 0.4)
    pause_max_orders     = cfg.get("tier1_pause_max_orders", 10)
    pause_min_spend      = cfg.get("tier1_pause_min_spend", 50)

    reduce_max_eff       = cfg.get("tier1_reduce_max_efficiency", 0.6)
    reduce_max_pct_prof  = cfg.get("tier1_reduce_max_pct_profitable", 0.3)

    restructure_mixed    = cfg.get("tier1_restructure_mixed_threshold", 0.4)
    restructure_zc_pct   = cfg.get("tier1_restructure_zero_conv_pct", 0.3)

    scale_min_eff        = cfg.get("tier1_scale_min_efficiency", 1.3)
    scale_min_orders     = cfg.get("tier1_scale_min_orders", 30)
    scale_min_roas_pct   = cfg.get("tier1_scale_min_roas_vs_target", 1.2)

    increase_min_eff     = cfg.get("tier1_increase_min_efficiency", 1.0)
    increase_min_orders  = cfg.get("tier1_increase_min_orders", 20)

    # ── Aggregate per campaign ────────────────────────────────────────────────
    agg_dict: dict = {spend_col: "sum", sales_col: "sum"}
    if clicks_col:
        agg_dict[clicks_col] = "sum"
    if orders_col:
        agg_dict[orders_col] = "sum"

    camp_stats = df.groupby(campaign_col).agg(agg_dict).reset_index()
    camp_stats["target_count"] = df.groupby(campaign_col).size().values

    # Derived metrics
    camp_stats["roas"] = camp_stats.apply(
        lambda r: r[sales_col] / r[spend_col] if r[spend_col] > 0 else 0.0,
        axis=1,
    )
    camp_stats["acos"] = camp_stats.apply(
        lambda r: (r[spend_col] / r[sales_col] * 100) if r[sales_col] > 0 else 100.0,
        axis=1,
    )

    # Campaign efficiency ratio (from cascade if available, else compute fresh)
    if "campaign_efficiency_ratio" in df.columns and "campaign_efficiency_label" in df.columns:
        eff_ratio_map = df.groupby(campaign_col)["campaign_efficiency_ratio"].first()
        eff_label_map = df.groupby(campaign_col)["campaign_efficiency_label"].first()
        camp_stats["efficiency_ratio"] = camp_stats[campaign_col].map(eff_ratio_map).fillna(0.0)
        camp_stats["efficiency_label"] = camp_stats[campaign_col].map(eff_label_map).fillna("unknown")
    else:
        total_spend_all = camp_stats[spend_col].sum()
        total_sales_all = camp_stats[sales_col].sum()
        if total_spend_all > 0 and total_sales_all > 0:
            from features.optimizer_shared.ppc_classifications import classify_campaign_efficiency
            camp_stats["spend_share"] = camp_stats[spend_col] / total_spend_all * 100
            camp_stats["revenue_share"] = camp_stats[sales_col] / total_sales_all * 100
            camp_stats[["efficiency_label", "efficiency_ratio"]] = camp_stats.apply(
                lambda r: pd.Series(
                    classify_campaign_efficiency(r["revenue_share"], r["spend_share"])
                ),
                axis=1,
            )
        else:
            camp_stats["efficiency_ratio"] = 0.0
            camp_stats["efficiency_label"] = "unknown"

    # % targets with ROAS >= target (profitable)
    if roas_col:
        profitable_map = (
            df[df[roas_col] >= target_roas]
            .groupby(campaign_col)
            .size()
        )
        camp_stats["profitable_targets"] = (
            camp_stats[campaign_col].map(profitable_map).fillna(0).astype(int)
        )
    else:
        camp_stats["profitable_targets"] = 0

    # % targets with zero-conversion flag (from cascade)
    if "ppc_diagnostic" in df.columns:
        zc_map = (
            df[df["ppc_diagnostic"] == "zero_conversion"]
            .groupby(campaign_col)
            .size()
        )
        camp_stats["zero_conv_targets"] = (
            camp_stats[campaign_col].map(zc_map).fillna(0).astype(int)
        )
    else:
        camp_stats["zero_conv_targets"] = 0

    camp_stats["pct_profitable"] = (
        camp_stats["profitable_targets"] / camp_stats["target_count"]
    ).fillna(0.0)
    camp_stats["pct_zero_conv"] = (
        camp_stats["zero_conv_targets"] / camp_stats["target_count"]
    ).fillna(0.0)

    # Campaign type (mode of match type)
    if match_type_col:
        type_map = df.groupby(campaign_col)[match_type_col].agg(
            lambda x: x.mode().iloc[0] if not x.mode().empty else "Mixed"
        )
        camp_stats["campaign_type"] = camp_stats[campaign_col].map(type_map).fillna("Mixed")
    else:
        camp_stats["campaign_type"] = "Mixed"

    orders_key = orders_col if orders_col else None

    # ── Generate recommendations ──────────────────────────────────────────────
    recommendations = []

    for _, r in camp_stats.iterrows():
        name      = r[campaign_col]
        spend     = float(r[spend_col])
        sales     = float(r[sales_col])
        orders    = int(r[orders_key]) if orders_key else 0
        roas      = float(r["roas"])
        acos      = float(r["acos"])
        eff       = float(r["efficiency_ratio"])
        eff_label = str(r["efficiency_label"])
        targets   = int(r["target_count"])
        pct_prof  = float(r["pct_profitable"])
        pct_zc    = float(r["pct_zero_conv"])

        rec: dict = {
            "campaign_name":           name,
            "campaign_type":           r.get("campaign_type", "Mixed"),
            "spend":                   round(spend, 2),
            "sales":                   round(sales, 2),
            "orders":                  orders,
            "roas":                    round(roas, 2),
            "acos":                    round(acos, 1),
            "efficiency_ratio":        round(eff, 2),
            "efficiency_label":        eff_label,
            "target_count":            targets,
            "pct_targets_profitable":  round(pct_prof * 100, 1),
            "pct_targets_zero_conv":   round(pct_zc * 100, 1),
        }

        # ── Decision logic (priority order — first match wins) ────────────────

        # 1. PAUSE — confirmed drain
        if (
            eff < pause_max_eff
            and orders < pause_max_orders
            and spend >= pause_min_spend
            and roas < target_roas * 0.5
        ):
            rec["recommendation"] = "PAUSE"
            rec["confidence"] = "HIGH" if spend > 100 and orders <= 5 else "MEDIUM"
            rec["reason"] = (
                f"Efficiency {eff:.2f}×, only {orders} orders, "
                f"ROAS {roas:.1f}× (target {target_roas:.1f}×). "
                f"Campaign is consuming ${spend:.0f} with minimal return."
            )
            rec["estimated_monthly_impact"] = round(spend * 0.9, 0)

        # 2. REDUCE_BUDGET — bleeding but has some value
        elif (
            eff < reduce_max_eff
            and pct_prof < reduce_max_pct_prof
            and spend >= pause_min_spend
        ):
            rec["recommendation"] = "REDUCE_BUDGET"
            rec["confidence"] = "MEDIUM"
            rec["reason"] = (
                f"Efficiency {eff:.2f}×, only {pct_prof * 100:.0f}% of targets profitable. "
                f"Reduce budget to limit bleed while preserving "
                f"{int(r['profitable_targets'])} profitable targets."
            )
            rec["estimated_monthly_impact"] = round(spend * 0.3, 0)

        # 3. RESTRUCTURE — mixed bag with potential
        elif pct_prof >= restructure_mixed and pct_zc >= restructure_zc_pct:
            rec["recommendation"] = "RESTRUCTURE"
            rec["confidence"] = "MEDIUM"
            rec["reason"] = (
                f"{pct_prof * 100:.0f}% of targets are profitable but "
                f"{pct_zc * 100:.0f}% have zero conversions. "
                f"Campaign has potential — consider splitting performers into "
                f"an exact campaign and negating bleeders."
            )
            rec["estimated_monthly_impact"] = round(spend * pct_zc * 0.7, 0)

        # 4. SCALE — proven winner, high conviction
        elif (
            eff >= scale_min_eff
            and orders >= scale_min_orders
            and roas >= target_roas * scale_min_roas_pct
        ):
            roas_above_pct = int((roas / target_roas - 1) * 100)
            rec["recommendation"] = "SCALE"
            rec["confidence"] = "HIGH" if orders >= 50 else "MEDIUM"
            rec["reason"] = (
                f"Efficiency {eff:.2f}×, {orders} orders, "
                f"ROAS {roas:.1f}× ({roas_above_pct}% above target). "
                f"Strong candidate for budget increase."
            )
            rec["estimated_monthly_impact"] = round(sales * 0.15, 0)

        # 5. INCREASE_BUDGET — good performance, room to grow
        elif (
            eff >= increase_min_eff
            and orders >= increase_min_orders
            and roas >= target_roas
        ):
            rec["recommendation"] = "INCREASE_BUDGET"
            rec["confidence"] = "MEDIUM"
            rec["reason"] = (
                f"Efficiency {eff:.2f}×, {orders} orders, ROAS at or above target. "
                f"Campaign performing — test 20-30% budget increase."
            )
            rec["estimated_monthly_impact"] = round(sales * 0.10, 0)

        # 6. MAINTAIN — nothing actionable
        else:
            rec["recommendation"] = "MAINTAIN"
            rec["confidence"] = "LOW"
            rec["reason"] = (
                f"Efficiency {eff:.2f}×, {orders} orders, ROAS {roas:.1f}×. "
                f"No immediate action — optimizer handles bid-level adjustments."
            )
            rec["estimated_monthly_impact"] = 0

        recommendations.append(rec)

    if not recommendations:
        return pd.DataFrame()

    result = pd.DataFrame(recommendations)

    # Sort: actionable first, then by estimated impact descending
    _PRIORITY = {
        "PAUSE": 0, "SCALE": 1, "REDUCE_BUDGET": 2,
        "INCREASE_BUDGET": 3, "RESTRUCTURE": 4, "MAINTAIN": 5,
    }
    result["_sort"] = result["recommendation"].map(_PRIORITY).fillna(5)
    result = (
        result
        .sort_values(["_sort", "estimated_monthly_impact"], ascending=[True, False])
        .drop(columns=["_sort"])
        .reset_index(drop=True)
    )

    return result


# ── Helper ────────────────────────────────────────────────────────────────────

def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None
