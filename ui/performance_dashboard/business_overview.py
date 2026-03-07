"""Business Overview page for Performance Dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import textwrap
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from app_core.db_manager import get_db_manager
from config.features import FeatureFlags
from features.dashboard.constants import DEFAULT_TARGET_TACOS
from features.dashboard.data_access import check_spapi_available
from features.dashboard.metrics import (
    HealthScoreResult,
    calculate_aov,
    calculate_cvr,
    calculate_days_of_cover,
    calculate_delta_pct,
    calculate_organic_pct,
    calculate_roas,
    calculate_tacos,
    compute_account_health_score,
    score_against_target_lower_better,
    score_ratio_higher_better,
    score_trend_delta,
)
from utils.formatters import get_account_currency

MARKETPLACE_ID = "A2VIGQ35RCS4UG"


@dataclass(frozen=True)
class DriverCallout:
    key: str
    text: str
    impact_points: float


def _inject_business_overview_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: radial-gradient(1200px 700px at 10% -10%, rgba(79,70,229,0.25), rgba(3,7,18,0) 60%),
                        radial-gradient(900px 600px at 85% -10%, rgba(16,185,129,0.20), rgba(3,7,18,0) 58%),
                        #030712;
        }
        .bo-topbar {
            padding: 8px 0 14px 0;
        }
        .bo-title {
            font-size: 32px;
            line-height: 1.1;
            font-weight: 800;
            color: #F9FAFB;
            letter-spacing: -0.02em;
            margin: 0;
        }
        .bo-subtitle {
            color: #9CA3AF;
            font-size: 14px;
            margin-top: 6px;
        }
        .bo-section {
            margin-top: 12px;
            margin-bottom: 10px;
            border-bottom: 1px solid rgba(75,85,99,0.55);
            padding-bottom: 8px;
        }
        .bo-section h3 {
            margin: 0;
            color: #F3F4F6;
            font-size: 22px;
            letter-spacing: -0.01em;
        }
        .bo-section p {
            margin: 4px 0 0 0;
            color: #9CA3AF;
            font-size: 13px;
        }
        .bo-hero-card {
            position: relative;
            border-radius: 14px;
            border: 1px solid rgba(55,65,81,0.9);
            background: rgba(17,24,39,0.92);
            padding: 16px;
            min-height: 138px;
            overflow: hidden;
            box-shadow: 0 14px 30px rgba(0,0,0,0.25);
        }
        .bo-hero-label {
            color: #9CA3AF;
            text-transform: uppercase;
            font-weight: 700;
            font-size: 11px;
            letter-spacing: .08em;
            margin-bottom: 5px;
        }
        .bo-hero-value {
            color: #FFFFFF;
            font-weight: 800;
            font-size: 34px;
            line-height: 1.05;
            letter-spacing: -0.02em;
            margin-bottom: 7px;
        }
        .bo-hero-sub {
            color: #6B7280;
            font-size: 12px;
        }
        .bo-trend-badge {
            float: right;
            font-size: 11px;
            font-weight: 700;
            border-radius: 8px;
            padding: 4px 8px;
        }
        .bo-metric-card {
            position: relative;
            border-radius: 14px;
            border: 1px solid rgba(55,65,81,0.9);
            background: rgba(17,24,39,0.92);
            padding: 16px;
            min-height: 138px;
            overflow: hidden;
            box-shadow: 0 14px 30px rgba(0,0,0,0.25);
            margin-bottom: 8px;
        }
        .bo-metric-value {
            color: #FFFFFF;
            font-weight: 800;
            font-size: 34px;
            line-height: 1.05;
            letter-spacing: -0.02em;
            margin-bottom: 7px;
        }
        .bo-constraint {
            border-radius: 12px;
            border: 1px solid;
            padding: 14px;
            min-height: 120px;
        }
        .bo-insight {
            border-radius: 12px;
            border: 1px solid;
            padding: 16px;
            min-height: 220px;
        }
        .bo-table-wrap {
            border: 1px solid rgba(55,65,81,0.9);
            border-radius: 12px;
            overflow: hidden;
            background: rgba(17,24,39,0.92);
            box-shadow: 0 14px 30px rgba(0,0,0,0.25);
        }
        .bo-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .bo-table thead {
            background: rgba(3,7,18,0.55);
        }
        .bo-table th {
            text-transform: uppercase;
            color: #9CA3AF;
            letter-spacing: .06em;
            font-size: 11px;
            text-align: right;
            padding: 12px 10px;
            border-bottom: 1px solid rgba(55,65,81,0.8);
        }
        .bo-table th:first-child,
        .bo-table td:first-child {
            text-align: left;
            padding-left: 16px;
        }
        .bo-table td {
            color: #D1D5DB;
            padding: 12px 10px;
            border-bottom: 1px solid rgba(55,65,81,0.55);
            text-align: right;
        }
        .bo-chip-ok, .bo-chip-warn, .bo-chip-bad {
            display: inline-block;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border: 1px solid;
        }
        .bo-chip-ok { color:#34D399; border-color: rgba(16,185,129,0.35); background: rgba(16,185,129,0.12); }
        .bo-chip-warn { color:#F59E0B; border-color: rgba(245,158,11,0.35); background: rgba(245,158,11,0.12); }
        .bo-chip-bad { color:#FB7185; border-color: rgba(244,63,94,0.35); background: rgba(244,63,94,0.12); }
        .stMetric {
            border: 1px solid rgba(55,65,81,0.9);
            border-radius: 12px;
            background: rgba(17,24,39,0.92);
            box-shadow: 0 10px 20px rgba(0,0,0,0.22);
            padding: 10px 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _placeholder(db) -> str:
    return getattr(db, "placeholder", "%s")


def _to_df_query(db, query: str, params: Tuple[Any, ...]) -> pd.DataFrame:
    with db._get_connection() as conn:
        if _placeholder(db) == "?":
            query = query.replace("%s", "?")
        return pd.read_sql_query(query, conn, params=params)


def _resolve_spapi_scope(db, client_id: str) -> Tuple[str, str]:
    ph = _placeholder(db)
    query = f"""
        SELECT account_id, marketplace_id
        FROM sc_raw.spapi_account_links
        WHERE public_client_id = {ph}
          AND is_active = TRUE
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
    """
    try:
        mapped_account_id = client_id
        marketplace_id = MARKETPLACE_ID
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (client_id,))
            row = cursor.fetchone()
            if row:
                if isinstance(row, dict):
                    mapped_account_id = str(row.get("account_id") or client_id)
                    marketplace_id = str(row.get("marketplace_id") or MARKETPLACE_ID)
                elif hasattr(row, "keys"):
                    mapped_account_id = str(row["account_id"] or client_id)
                    marketplace_id = str(row["marketplace_id"] or MARKETPLACE_ID)
                else:
                    mapped_account_id = str(row[0] if row else client_id)
                    marketplace_id = str(row[1] if row and len(row) > 1 else MARKETPLACE_ID)

            # Data can be keyed by either public client_id or internal account_id
            # depending on which ingestion path populated sc_raw.sales_traffic.
            probe_q = f"""
                SELECT COUNT(*)
                FROM sc_raw.sales_traffic
                WHERE account_id = {ph}
                  AND marketplace_id = {ph}
            """

            def _count_for(account_scope: str) -> int:
                try:
                    cursor.execute(probe_q, (account_scope, marketplace_id))
                    got = cursor.fetchone()
                    return int(got[0]) if got else 0
                except Exception:
                    return 0

            count_client = _count_for(client_id)
            count_mapped = _count_for(mapped_account_id)

            # Prefer whichever scope currently has data.
            if count_mapped > count_client:
                return mapped_account_id, marketplace_id
            return client_id, marketplace_id
    except Exception:
        return client_id, MARKETPLACE_ID


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        val = float(value)
        if pd.isna(val):
            return default
        return val
    except Exception:
        return default


def _format_currency(value: Optional[float], currency: str = "$", decimals: int = 0) -> str:
    if value is None:
        return "N/A"
    return f"{currency}{value:,.{decimals}f}"


def _format_number(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.0f}"


def _format_percent(value: Optional[float], points: bool = False, decimals: int = 1) -> str:
    if value is None:
        return "N/A"
    pct = value if points else value * 100
    return f"{pct:.{decimals}f}%"


def _delta_text(delta_pct: Optional[float]) -> str:
    if delta_pct is None:
        return "N/A"
    return f"{delta_pct:+.1f}%"


def _normalize_ratio_or_percent(series: pd.Series) -> pd.Series:
    vals = pd.to_numeric(series, errors="coerce")
    if vals.dropna().empty:
        return vals
    # account_daily.tacos is persisted in percentage points (e.g. 12.5)
    return vals / 100.0 if vals.dropna().median() > 1 else vals


@st.cache_data(ttl=300, show_spinner=False)
def fetch_business_overview_data(
    client_id: str,
    window_days: int,
    test_mode: bool,
    spapi_available: bool,
    cache_version: str,
) -> Dict[str, Any]:
    db = get_db_manager(test_mode)
    if not db or not client_id:
        return {}

    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=window_days - 1)
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=window_days - 1)

    account_id, marketplace_id = _resolve_spapi_scope(db, client_id)

    traffic_daily = pd.DataFrame()
    traffic_by_asin = pd.DataFrame()
    account_daily = pd.DataFrame()
    ad_spend_daily = pd.DataFrame()
    product_table_raw = pd.DataFrame()
    inventory_raw = pd.DataFrame()

    traffic_q = """
        SELECT
            report_date,
            SUM(COALESCE(sessions, 0)) AS sessions,
            SUM(COALESCE(page_views, 0)) AS page_views,
            SUM(COALESCE(units_ordered, 0)) AS units,
            SUM(COALESCE(ordered_revenue, 0)) AS revenue
        FROM sc_raw.sales_traffic
        WHERE account_id = %s
          AND marketplace_id = %s
          AND report_date BETWEEN %s AND %s
        GROUP BY report_date
        ORDER BY report_date
    """

    account_daily_q = """
        SELECT
            report_date,
            COALESCE(total_ordered_revenue, 0) AS total_ordered_revenue,
            COALESCE(total_units_ordered, 0) AS total_units_ordered,
            COALESCE(total_page_views, 0) AS total_page_views,
            COALESCE(total_sessions, 0) AS total_sessions,
            COALESCE(ad_attributed_revenue, 0) AS ad_attributed_revenue,
            COALESCE(organic_revenue, 0) AS organic_revenue,
            COALESCE(organic_share_pct, 0) AS organic_share_pct,
            COALESCE(tacos, 0) AS tacos
        FROM sc_analytics.account_daily
        WHERE account_id = %s
          AND marketplace_id = %s
          AND report_date BETWEEN %s AND %s
        ORDER BY report_date
    """

    ad_spend_q = """
        SELECT
            report_date,
            SUM(COALESCE(spend, 0)) AS ad_spend,
            SUM(COALESCE(sales, 0)) AS ad_sales
        FROM raw_search_term_data
        WHERE client_id = %s
          AND report_date BETWEEN %s AND %s
        GROUP BY report_date
        ORDER BY report_date
    """

    # ── Parallel fetch: target_stats, traffic, account_daily, ad_spend ────────
    from concurrent.futures import ThreadPoolExecutor

    def _run_target():
        try:
            df = db.get_target_stats_df(client_id, start_date=prev_start)
            return df if df is not None else pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def _run_traffic():
        try:
            return _to_df_query(db, traffic_q, (account_id, marketplace_id, prev_start, end_date))
        except Exception:
            return pd.DataFrame(columns=["report_date", "sessions", "page_views", "units", "revenue"])

    def _run_account_daily():
        try:
            return _to_df_query(db, account_daily_q, (account_id, marketplace_id, prev_start, end_date))
        except Exception:
            return pd.DataFrame(columns=[
                "report_date", "total_ordered_revenue", "total_units_ordered",
                "total_page_views", "total_sessions", "ad_attributed_revenue",
                "organic_revenue", "organic_share_pct", "tacos",
            ])

    def _run_ad_spend():
        try:
            return _to_df_query(db, ad_spend_q, (client_id, prev_start, end_date))
        except Exception:
            return pd.DataFrame(columns=["report_date", "ad_spend", "ad_sales"])

    with ThreadPoolExecutor(max_workers=4) as _pool:
        _f_target  = _pool.submit(_run_target)
        _f_traffic = _pool.submit(_run_traffic)
        _f_acct    = _pool.submit(_run_account_daily)
        _f_spend   = _pool.submit(_run_ad_spend)
        target_df    = _f_target.result()
        traffic_daily = _f_traffic.result()
        account_daily = _f_acct.result()
        ad_spend_daily = _f_spend.result()

    if not target_df.empty and "Date" in target_df.columns:
        target_df = target_df.copy()
        target_df["Date"] = pd.to_datetime(target_df["Date"], errors="coerce").dt.date

    target_current = target_df[
        (target_df["Date"] >= start_date) & (target_df["Date"] <= end_date)
    ].copy() if not target_df.empty else pd.DataFrame()
    target_previous = target_df[
        (target_df["Date"] >= prev_start) & (target_df["Date"] <= prev_end)
    ].copy() if not target_df.empty else pd.DataFrame()

    if not traffic_daily.empty:
        traffic_daily["report_date"] = pd.to_datetime(traffic_daily["report_date"], errors="coerce")
    if not account_daily.empty:
        account_daily["report_date"] = pd.to_datetime(account_daily["report_date"], errors="coerce")
    if not ad_spend_daily.empty:
        ad_spend_daily["report_date"] = pd.to_datetime(ad_spend_daily["report_date"], errors="coerce")

    if spapi_available:
        traffic_asin_q = """
            SELECT
                child_asin AS asin,
                SUM(COALESCE(sessions, 0)) AS sessions,
                SUM(COALESCE(page_views, 0)) AS page_views,
                SUM(COALESCE(units_ordered, 0)) AS units,
                SUM(COALESCE(ordered_revenue, 0)) AS sales
            FROM sc_raw.sales_traffic
            WHERE account_id = %s
              AND marketplace_id = %s
              AND report_date BETWEEN %s AND %s
            GROUP BY child_asin
        """
        try:
            traffic_by_asin = _to_df_query(db, traffic_asin_q, (account_id, marketplace_id, start_date, end_date))
        except Exception:
            traffic_by_asin = pd.DataFrame(columns=["asin", "sessions", "page_views", "units", "sales"])

        inv_q = """
            SELECT DISTINCT ON (asin)
                asin,
                COALESCE(sku, '') AS sku,
                COALESCE(product_name, '') AS product_name,
                COALESCE(afn_fulfillable_quantity, 0) AS afn_fulfillable_quantity,
                COALESCE(afn_total_quantity, 0) AS afn_total_quantity,
                snapshot_date
            FROM sc_raw.fba_inventory
            WHERE client_id = %s
            ORDER BY asin, snapshot_date DESC
        """
        try:
            inventory_raw = _to_df_query(db, inv_q, (client_id,))
        except Exception:
            inventory_raw = pd.DataFrame(
                columns=["asin", "sku", "product_name", "afn_fulfillable_quantity", "afn_total_quantity", "snapshot_date"]
            )

    product_q = """
        WITH sales_by_asin AS (
            SELECT
                st.child_asin AS asin,
                MAX(NULLIF(st.parent_asin, '')) AS parent_from_sales,
                SUM(COALESCE(st.sessions, 0)) AS sessions,
                SUM(COALESCE(st.page_views, 0)) AS page_views,
                SUM(COALESCE(st.units_ordered, 0)) AS units,
                SUM(COALESCE(st.ordered_revenue, 0)) AS sales
            FROM sc_raw.sales_traffic st
            WHERE st.account_id = %s
              AND st.marketplace_id = %s
              AND st.report_date BETWEEN %s AND %s
            GROUP BY st.child_asin
        ),
        apc_exact AS (
            SELECT DISTINCT
                client_id, campaign_name, ad_group_name, asin, sku
            FROM advertised_product_cache
            WHERE client_id = %s
              AND asin IS NOT NULL
              AND asin <> ''
        ),
        campaign_single_asin AS (
            SELECT
                client_id,
                campaign_name,
                MIN(asin) AS asin
            FROM apc_exact
            GROUP BY client_id, campaign_name
            HAVING COUNT(DISTINCT asin) = 1
        ),
        ad_group_single_asin AS (
            SELECT
                client_id,
                campaign_name,
                ad_group_name,
                MIN(asin) AS asin
            FROM apc_exact
            GROUP BY client_id, campaign_name, ad_group_name
            HAVING COUNT(DISTINCT asin) = 1
        ),
        spend_mapped_rows AS (
            SELECT
                COALESCE(ex.asin, agsa.asin, csa.asin) AS asin,
                COALESCE(ex.sku, '') AS sku,
                SUM(COALESCE(rst.spend, 0)) AS ad_spend,
                SUM(COALESCE(rst.sales, 0)) AS ad_sales
            FROM raw_search_term_data rst
            LEFT JOIN apc_exact ex
              ON ex.client_id = rst.client_id
             AND LOWER(ex.campaign_name) = LOWER(rst.campaign_name)
             AND LOWER(ex.ad_group_name) = LOWER(rst.ad_group_name)
            LEFT JOIN ad_group_single_asin agsa
              ON agsa.client_id = rst.client_id
             AND LOWER(agsa.campaign_name) = LOWER(rst.campaign_name)
             AND LOWER(agsa.ad_group_name) = LOWER(rst.ad_group_name)
            LEFT JOIN campaign_single_asin csa
              ON csa.client_id = rst.client_id
             AND LOWER(csa.campaign_name) = LOWER(rst.campaign_name)
            WHERE rst.client_id = %s
              AND rst.report_date BETWEEN %s AND %s
              AND COALESCE(ex.asin, agsa.asin, csa.asin) IS NOT NULL
            GROUP BY COALESCE(ex.asin, agsa.asin, csa.asin), COALESCE(ex.sku, '')
        ),
        spend_by_asin AS (
            SELECT
                asin,
                MAX(COALESCE(sku, '')) AS sku,
                SUM(COALESCE(ad_spend, 0)) AS ad_spend,
                SUM(COALESCE(ad_sales, 0)) AS ad_sales
            FROM spend_mapped_rows
            GROUP BY asin
        ),
        latest_inv AS (
            SELECT DISTINCT ON (asin)
                asin,
                COALESCE(afn_fulfillable_quantity, 0) AS fulfillable_qty
            FROM sc_raw.fba_inventory
            WHERE client_id = %s
            ORDER BY asin, snapshot_date DESC
        ),
        asin_base AS (
            SELECT asin FROM sales_by_asin
            UNION
            SELECT asin FROM spend_by_asin
        ),
        child_level AS (
            SELECT
                b.asin,
                COALESCE(s.parent_from_sales, b.asin) AS parent_asin,
                COALESCE(sp.sku, '') AS sku,
                COALESCE(s.sessions, 0) AS sessions,
                COALESCE(s.page_views, 0) AS page_views,
                COALESCE(s.units, 0) AS units,
                COALESCE(s.sales, 0) AS sales,
                COALESCE(sp.ad_spend, 0) AS ad_spend,
                COALESCE(sp.ad_sales, 0) AS ad_sales,
                COALESCE(inv.fulfillable_qty, 0) AS fulfillable_qty
            FROM asin_base b
            LEFT JOIN sales_by_asin s ON s.asin = b.asin
            LEFT JOIN spend_by_asin sp ON sp.asin = b.asin
            LEFT JOIN latest_inv inv ON inv.asin = b.asin
        ),
        parent_rollup AS (
            SELECT
                parent_asin AS asin,
                parent_asin AS parent_asin_sku,
                MAX(COALESCE(sku, '')) AS sku,
                SUM(sessions) AS sessions,
                SUM(page_views) AS page_views,
                SUM(units) AS units,
                SUM(sales) AS sales,
                SUM(ad_spend) AS ad_spend,
                SUM(ad_sales) AS ad_sales,
                SUM(fulfillable_qty) AS fulfillable_qty
            FROM child_level
            GROUP BY parent_asin
        )
        SELECT
            pr.asin,
            pr.parent_asin_sku,
            pr.sku,
            pr.sessions,
            pr.page_views,
            pr.units,
            pr.sales,
            pr.ad_spend,
            pr.ad_sales,
            CASE
                WHEN COALESCE(pr.units, 0) > 0
                THEN pr.fulfillable_qty / NULLIF((pr.units::float / %s), 0)
                ELSE NULL
            END AS days_of_cover
        FROM parent_rollup pr
    """
    try:
        product_table_raw = _to_df_query(
            db,
            product_q,
            (
                account_id,
                marketplace_id,
                start_date,
                end_date,
                client_id,
                client_id,
                start_date,
                end_date,
                client_id,
                float(max(window_days, 1)),
            ),
        )
    except Exception:
        # SQLite fallback without FULL OUTER JOIN
        product_table_raw = pd.DataFrame(
            columns=["asin", "parent_asin_sku", "sku", "sessions", "page_views", "units", "sales", "ad_sales", "ad_spend"]
        )

    if product_table_raw is None:
        product_table_raw = pd.DataFrame()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "prev_start": prev_start,
        "prev_end": prev_end,
        "account_id": account_id,
        "marketplace_id": marketplace_id,
        "target_current": target_current,
        "target_previous": target_previous,
        "traffic_daily": traffic_daily,
        "traffic_by_asin": traffic_by_asin,
        "account_daily": account_daily,
        "ad_spend_daily": ad_spend_daily,
        "product_table_raw": product_table_raw,
        "inventory_raw": inventory_raw,
    }


def compute_health_and_callouts(
    *,
    ad_spend_current: float,
    total_sales_current: Optional[float],
    organic_sales_current: Optional[float],
    ad_sales_current: Optional[float],
    avg_days_cover_current: Optional[float],
    sessions_current: Optional[float],
    units_current: Optional[float],
    sessions_previous: Optional[float],
    units_previous: Optional[float],
    target_tacos: float,
) -> Tuple[HealthScoreResult, List[DriverCallout], Dict[str, Optional[float]]]:
    tacos_current = calculate_tacos(ad_spend_current, total_sales_current or 0) if total_sales_current else None
    tacos_score = score_against_target_lower_better(tacos_current, target_tacos)

    organic_paid_ratio = calculate_roas(organic_sales_current or 0, ad_sales_current or 0) if ad_sales_current else None
    ratio_score = score_ratio_higher_better(organic_paid_ratio, baseline=1.0)

    inventory_score = score_ratio_higher_better(avg_days_cover_current, baseline=30.0)

    cvr_current = calculate_cvr(units_current or 0, sessions_current or 0) if sessions_current else None
    cvr_previous = calculate_cvr(units_previous or 0, sessions_previous or 0) if sessions_previous else None
    cvr_delta_pct = calculate_delta_pct(cvr_current, cvr_previous)
    cvr_score = score_trend_delta(cvr_delta_pct, sensitivity=1.5)

    score_result = compute_account_health_score(
        tacos_vs_target_score=tacos_score,
        organic_paid_ratio_score=ratio_score,
        inventory_days_cover_score=inventory_score,
        cvr_trend_score=cvr_score,
    )

    base_weights = {
        "tacos_vs_target": 0.30,
        "organic_paid_ratio": 0.25,
        "inventory_days_cover": 0.25,
        "cvr_trend": 0.20,
    }
    contributions = score_result.weighted_components
    callouts: List[DriverCallout] = []

    for key, weight in sorted(base_weights.items(), key=lambda x: x[1], reverse=True):
        if key not in contributions:
            continue
        max_points = weight * 100.0
        impact_points = round(max_points - contributions[key], 1)
        impact_verb = "costing" if impact_points > 0 else "adding"

        if key == "tacos_vs_target":
            text = (
                f"TACOS {_format_percent(tacos_current)} vs {_format_percent(target_tacos)} target - {impact_verb} {abs(impact_points):.0f} points"
                if tacos_current is not None
                else f"TACOS vs target - {impact_verb} {abs(impact_points):.0f} points"
            )
        elif key == "organic_paid_ratio":
            text = (
                f"Organic/Paid revenue ratio {organic_paid_ratio:.2f}x - {impact_verb} {abs(impact_points):.0f} points"
                if organic_paid_ratio is not None
                else f"Organic/Paid revenue ratio - {impact_verb} {abs(impact_points):.0f} points"
            )
        elif key == "inventory_days_cover":
            text = (
                f"Inventory days of cover {avg_days_cover_current:.1f} days - {impact_verb} {abs(impact_points):.0f} points"
                if avg_days_cover_current is not None
                else f"Inventory days of cover - {impact_verb} {abs(impact_points):.0f} points"
            )
        else:
            text = (
                f"CVR trend {_delta_text(cvr_delta_pct)} - {impact_verb} {abs(impact_points):.0f} points"
                if cvr_delta_pct is not None
                else f"CVR trend - {impact_verb} {abs(impact_points):.0f} points"
            )
        callouts.append(DriverCallout(key=key, text=text, impact_points=impact_points))

    callouts = sorted(callouts, key=lambda c: abs(c.impact_points), reverse=True)[:3]
    return score_result, callouts, {
        "tacos_current": tacos_current,
        "organic_paid_ratio": organic_paid_ratio,
        "avg_days_cover": avg_days_cover_current,
        "cvr_delta_pct": cvr_delta_pct,
    }


def build_tacos_trend_figure(df: pd.DataFrame, target_tacos: Optional[float]) -> go.Figure:
    target = target_tacos if target_tacos is not None else DEFAULT_TARGET_TACOS
    fig = go.Figure()
    if not df.empty:
        fig.add_trace(
            go.Scatter(
                x=df["report_date"],
                y=df["tacos"],
                mode="lines+markers",
                name="TACOS",
                line=dict(width=2.8, color="#38bdf8"),
                marker=dict(size=6, color="#93c5fd"),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["report_date"],
                y=[target] * len(df),
                mode="lines",
                name="Target TACOS",
                line=dict(width=2, dash="dash", color="#f59e0b"),
            )
        )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#d1d5db"),
        margin=dict(l=10, r=10, t=12, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
        yaxis=dict(tickformat=".0%", gridcolor="rgba(75,85,99,0.4)", zeroline=False),
        xaxis=dict(showgrid=False),
        hovermode="x unified",
    )
    return fig


def build_tacos_daily_series(curr_period: pd.DataFrame, ad_spend_daily: pd.DataFrame) -> pd.DataFrame:
    """Build daily TACOS series from daily ad spend and daily total sales."""
    if curr_period.empty:
        return pd.DataFrame(columns=["report_date", "tacos"])

    sales_daily = (
        curr_period[["report_date", "total_ordered_revenue"]]
        .copy()
        .assign(report_day=lambda d: pd.to_datetime(d["report_date"], errors="coerce").dt.date)
        .groupby("report_day", as_index=False)["total_ordered_revenue"]
        .sum()
        .rename(columns={"total_ordered_revenue": "total_sales"})
    )

    if ad_spend_daily is None or ad_spend_daily.empty:
        return pd.DataFrame(columns=["report_date", "tacos"])

    spend_daily = (
        ad_spend_daily[["report_date", "ad_spend"]]
        .copy()
        .assign(report_day=lambda d: pd.to_datetime(d["report_date"], errors="coerce").dt.date)
        .groupby("report_day", as_index=False)["ad_spend"]
        .sum()
    )

    tacos_series = sales_daily.merge(spend_daily, on="report_day", how="left")
    tacos_series["ad_spend"] = pd.to_numeric(tacos_series["ad_spend"], errors="coerce").fillna(0.0)
    tacos_series["total_sales"] = pd.to_numeric(tacos_series["total_sales"], errors="coerce")
    tacos_series = tacos_series[
        tacos_series["report_day"].notna()
        & tacos_series["total_sales"].notna()
        & (tacos_series["total_sales"] > 0)
        & (tacos_series["ad_spend"] > 0)
    ].copy()
    tacos_series["tacos"] = tacos_series.apply(
        lambda r: calculate_tacos(float(r["ad_spend"]), float(r["total_sales"])),
        axis=1,
    )
    tacos_series = tacos_series[
        tacos_series["tacos"].notna() & (tacos_series["tacos"] > 0) & (tacos_series["tacos"] <= 1)
    ].copy()
    tacos_series["report_date"] = pd.to_datetime(tacos_series["report_day"], errors="coerce")
    return tacos_series[["report_date", "tacos"]].sort_values("report_date")


def prepare_product_performance_table(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "ASIN",
                "SKU",
                "Revenue",
                "TACOS",
                "CVR",
                "Sessions",
                "Stock Days",
                "status",
                "ad_spend",
                "ad_sales",
                "units",
                "sales",
            ]
        )

    out = df.copy()
    out["sessions"] = pd.to_numeric(out.get("sessions", 0), errors="coerce").fillna(0)
    out["page_views"] = pd.to_numeric(out.get("page_views", 0), errors="coerce").fillna(0)
    out["units"] = pd.to_numeric(out.get("units", 0), errors="coerce").fillna(0)
    out["sales"] = pd.to_numeric(out.get("sales", out.get("ad_sales", 0)), errors="coerce").fillna(0)
    out["ad_spend"] = pd.to_numeric(out.get("ad_spend", 0), errors="coerce").fillna(0)
    out["ad_sales"] = pd.to_numeric(out.get("ad_sales", 0), errors="coerce").fillna(0)
    out["days_of_cover"] = pd.to_numeric(out.get("days_of_cover", 0), errors="coerce")

    out["CVR"] = out.apply(lambda r: calculate_cvr(r.get("units", 0), r.get("sessions", 0)) or 0.0, axis=1)
    out["TACOS"] = out.apply(lambda r: calculate_tacos(r.get("ad_spend", 0), r.get("sales", 0)) or 0.0, axis=1)
    out["SKU"] = out.get("sku", out.get("asin", "")).fillna("")

    def _status(days: Any) -> str:
        val = _safe_float(days, default=-1)
        if val < 0:
            return "warning"
        if val < 14:
            return "critical"
        if val < 30:
            return "warning"
        return "healthy"

    out["status"] = out["days_of_cover"].apply(_status)
    result = out[
        [
            "asin",
            "SKU",
            "sales",
            "TACOS",
            "CVR",
            "sessions",
            "days_of_cover",
            "status",
            "ad_spend",
            "ad_sales",
            "units",
        ]
    ].rename(
        columns={
            "asin": "ASIN",
            "sales": "Revenue",
            "sessions": "Sessions",
            "days_of_cover": "Stock Days",
        }
    )
    return result.sort_values("Revenue", ascending=False).reset_index(drop=True)


def _merge_trend_frame(
    start_date: date,
    end_date: date,
    target_current: pd.DataFrame,
    traffic_daily: pd.DataFrame,
    account_daily: pd.DataFrame,
    ad_daily: pd.DataFrame,
) -> pd.DataFrame:
    day_index = pd.DataFrame({"report_date": pd.date_range(start_date, end_date, freq="D")})

    if target_current.empty:
        target_day = pd.DataFrame(columns=["report_date", "revenue", "adSpend", "adSales"])
    else:
        target_day = (
            target_current.assign(report_date=pd.to_datetime(target_current["Date"], errors="coerce"))
            .groupby("report_date", as_index=False)
            .agg(
                revenue=("Sales", "sum"),
                adSpend=("Spend", "sum"),
                adSales=("Sales", "sum"),
            )
        )

    traffic_curr = traffic_daily[
        (traffic_daily["report_date"].dt.date >= start_date)
        & (traffic_daily["report_date"].dt.date <= end_date)
    ].copy() if not traffic_daily.empty else pd.DataFrame(columns=["report_date", "sessions", "page_views", "units", "revenue"])

    traffic_day = traffic_curr.rename(columns={"page_views": "pageViews", "units": "orders"})

    account_curr = account_daily[
        (account_daily["report_date"].dt.date >= start_date)
        & (account_daily["report_date"].dt.date <= end_date)
    ].copy() if not account_daily.empty else pd.DataFrame(
        columns=[
            "report_date",
            "organic_revenue",
            "ad_attributed_revenue",
            "total_ordered_revenue",
            "total_units_ordered",
            "total_sessions",
            "tacos",
        ]
    )

    for required in ("total_ordered_revenue", "total_units_ordered", "total_sessions"):
        if required not in account_curr.columns:
            account_curr[required] = 0

    mix_day = account_curr.rename(
        columns={
            "organic_revenue": "organicSales",
            "ad_attributed_revenue": "adSalesAccount",
            "total_ordered_revenue": "revenueAccount",
            "total_units_ordered": "ordersAccount",
            "total_sessions": "sessionsAccount",
        }
    )

    ad_curr = ad_daily[
        (ad_daily["report_date"].dt.date >= start_date)
        & (ad_daily["report_date"].dt.date <= end_date)
    ].copy() if not ad_daily.empty else pd.DataFrame(columns=["report_date", "ad_spend", "ad_sales"])
    if not ad_curr.empty:
        ad_curr["ad_sales"] = pd.to_numeric(ad_curr.get("ad_sales", 0), errors="coerce").fillna(0.0)
        ad_curr["ad_spend"] = pd.to_numeric(ad_curr.get("ad_spend", 0), errors="coerce").fillna(0.0)

    trend = day_index.merge(target_day, on="report_date", how="left")
    trend = trend.merge(traffic_day[["report_date", "sessions", "pageViews", "orders"]], on="report_date", how="left")
    trend = trend.merge(ad_curr[["report_date", "ad_spend", "ad_sales"]], on="report_date", how="left")
    trend = trend.merge(
        mix_day[
            [
                "report_date",
                "organicSales",
                "adSalesAccount",
                "revenueAccount",
                "ordersAccount",
                "sessionsAccount",
                "tacos",
            ]
        ],
        on="report_date",
        how="left",
    )

    for col in [
        "revenue",
        "adSpend",
        "ad_spend",
        "adSales",
        "ad_sales",
        "sessions",
        "pageViews",
        "orders",
        "organicSales",
        "adSalesAccount",
        "revenueAccount",
        "ordersAccount",
        "sessionsAccount",
    ]:
        trend[col] = pd.to_numeric(trend[col], errors="coerce").fillna(0.0)

    # Prefer daily PPC series (raw_search_term_data) for ad values.
    # Never fall back to weekly target_stats — it dumps a full week onto the week-start date,
    # causing false spikes. Fall back directly to adSalesAccount (account_daily) instead.
    trend["adSpend"] = trend["ad_spend"].where(trend["ad_spend"] > 0, trend["adSpend"])
    trend["adSales"] = trend["ad_sales"].where(trend["ad_sales"] > 0, trend["adSalesAccount"])

    # Primary source for trend continuity should be SP-API account_daily.
    trend["revenue"] = trend["revenueAccount"].where(trend["revenueAccount"] > 0, trend["revenue"])
    trend["orders"] = trend["ordersAccount"].where(trend["ordersAccount"] > 0, trend["orders"])
    trend["sessions"] = trend["sessionsAccount"].where(trend["sessionsAccount"] > 0, trend["sessions"])

    trend["organicSales"] = (trend["revenue"] - trend["adSales"]).clip(lower=0)
    trend["cvr"] = trend.apply(lambda r: calculate_cvr(r["orders"], r["sessions"]) or 0.0, axis=1)

    # Avoid artificial cliffs from padded trailing days with no loaded records.
    non_zero_mask = (trend["revenue"] > 0) | (trend["sessions"] > 0) | (trend["orders"] > 0)
    if non_zero_mask.any():
        first_idx = non_zero_mask.idxmax()
        last_idx = non_zero_mask.iloc[::-1].idxmax()
        trend = trend.loc[first_idx:last_idx].copy()

    trend["date_label"] = trend["report_date"].dt.strftime("%b %-d") if hasattr(trend["report_date"].dt, "strftime") else trend["report_date"].dt.strftime("%b %d")
    return trend


def _build_composed_figure(trend: pd.DataFrame, currency_symbol: str) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=trend["report_date"],
            y=trend["revenue"],
            name="Revenue",
            marker_color="#4f46e5",
            opacity=0.82,
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=trend["report_date"],
            y=trend["sessions"],
            mode="lines",
            name="Sessions",
            line=dict(color="#10b981", width=3),
        ),
        secondary_y=True,
    )
    fig.add_trace(
        go.Scatter(
            x=trend["report_date"],
            y=trend["orders"],
            mode="lines",
            name="Orders",
            line=dict(color="#f59e0b", width=3),
        ),
        secondary_y=True,
    )
    fig.update_yaxes(secondary_y=False, tickprefix=currency_symbol, gridcolor="rgba(75,85,99,0.4)")
    fig.update_yaxes(secondary_y=True, gridcolor="rgba(75,85,99,0.2)")
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        barmode="group",
        margin=dict(l=8, r=8, t=8, b=8),
        font=dict(color="#d1d5db"),
        legend=dict(orientation="h", y=1.05, x=0),
        hovermode="x unified",
    )
    return fig


def _build_paid_vs_organic_figure(trend: pd.DataFrame, currency_symbol: str) -> go.Figure:
    palette = px.colors.qualitative.Plotly
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=trend["report_date"],
            y=trend["organicSales"],
            stackgroup="one",
            mode="lines",
            line=dict(width=1.8, color="#10b981"),
            name="Organic Sales",
            fillcolor="rgba(16,185,129,0.55)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend["report_date"],
            y=trend["adSales"],
            stackgroup="one",
            mode="lines",
            line=dict(width=1.8, color=palette[0]),
            name="Ad Sales",
            fillcolor="rgba(59,130,246,0.55)",
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=8, b=8),
        font=dict(color="#d1d5db"),
        legend=dict(orientation="h", y=1.03, x=0),
        hovermode="x unified",
        yaxis=dict(tickprefix=currency_symbol, gridcolor="rgba(75,85,99,0.4)"),
    )
    return fig


def _account_tacos_series(account_daily_curr: pd.DataFrame) -> pd.DataFrame:
    if account_daily_curr.empty:
        return pd.DataFrame(columns=["report_date", "tacos"])

    df = account_daily_curr[["report_date", "total_ordered_revenue", "tacos"]].copy()
    df["total_ordered_revenue"] = pd.to_numeric(df["total_ordered_revenue"], errors="coerce")
    df["tacos"] = _normalize_ratio_or_percent(df["tacos"])
    # Bug fix: exclude days with null/zero total sales before TACOS plotting.
    df = df[
        df["report_date"].notna()
        & df["total_ordered_revenue"].notna()
        & (df["total_ordered_revenue"] > 0)
        & df["tacos"].notna()
    ].copy()
    return df[["report_date", "tacos"]].sort_values("report_date")


def _section_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="bo-section">
            <h3>{title}</h3>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(title: str, value: str, trend: str, inverse: bool = False) -> None:
    is_positive = trend.startswith("+")
    is_good = (not is_positive) if inverse else is_positive
    badge_bg = "rgba(16,185,129,0.15)" if is_good else "rgba(244,63,94,0.15)"
    badge_fg = "#34d399" if is_good else "#fb7185"

    st.markdown(
        f"""
        <div class="bo-metric-card">
            <div class="bo-hero-label">{title}</div>
            <div class="bo-metric-value">{value}</div>
            <div>
                <span class="bo-trend-badge" style="background:{badge_bg};color:{badge_fg}">{trend}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _hero_card(title: str, value: str, subtext: str, trend: str, inverse_trend: bool = False) -> None:
    is_positive = trend.startswith("+")
    is_good = (not is_positive) if inverse_trend else is_positive
    badge_bg = "rgba(16,185,129,0.15)" if is_good else "rgba(244,63,94,0.15)"
    badge_fg = "#34d399" if is_good else "#fb7185"

    st.markdown(
        f"""
        <div class="bo-hero-card">
            <div class="bo-hero-label">{title}</div>
            <div class="bo-hero-value">{value}</div>
            <div>
                <span class="bo-hero-sub">{subtext}</span>
                <span class="bo-trend-badge" style="background:{badge_bg};color:{badge_fg}">{trend}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _constraint_card(title: str, value: str, subtext: str, status: str) -> None:
    is_critical = status == "critical"
    fg = "#fb7185" if is_critical else "#f59e0b"
    bg = "rgba(244,63,94,0.10)" if is_critical else "rgba(245,158,11,0.10)"
    border = "rgba(244,63,94,0.35)" if is_critical else "rgba(245,158,11,0.35)"
    st.markdown(
        f"""
        <div class="bo-constraint" style="background:{bg}; border-color:{border}">
            <div style="font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:{fg}; font-weight:700;">{title}</div>
            <div style="font-size:30px; color:#fff; font-weight:800; line-height:1.1; margin-top:8px;">{value}</div>
            <div style="font-size:12px; color:{fg}; opacity:.9; margin-top:5px;">{subtext}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_product_table(df: pd.DataFrame, currency: str) -> None:
    if df.empty:
        st.info("No product rows available for selected window.")
        return

    rows: List[str] = []
    for _, row in df.head(20).iterrows():
        status = str(row.get("status", "warning"))
        chip_class = "bo-chip-ok" if status == "healthy" else ("bo-chip-warn" if status == "warning" else "bo-chip-bad")
        stock_days = row.get("Stock Days")
        stock_display = "N/A" if pd.isna(stock_days) else f"{float(stock_days):.0f} Days"
        rows.append(
            textwrap.dedent(
                """
                <tr>
                    <td>{parent}</td>
                    <td>{revenue}</td>
                    <td>{tacos}</td>
                    <td>{cvr}</td>
                    <td>{sessions}</td>
                    <td><span class="{chip}">{stock}</span></td>
                </tr>
                """
            ).strip().format(
                parent=row.get("SKU", "-"),
                revenue=_format_currency(_safe_float(row.get("Revenue")), currency),
                tacos=_format_percent(_safe_float(row.get("TACOS"), None)),
                cvr=_format_percent(_safe_float(row.get("CVR"), None)),
                sessions=_format_number(_safe_float(row.get("Sessions"), None)),
                chip=chip_class,
                stock=stock_display,
            )
        )

    html = textwrap.dedent(
        f"""
        <div class="bo-table-wrap">
            <table class="bo-table">
                <thead>
                    <tr>
                        <th>SKU</th>
                        <th>Revenue</th>
                        <th>TACOS</th>
                        <th>CVR</th>
                        <th>Sessions</th>
                        <th>Stock Days</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """
    ).strip()
    st.markdown(html, unsafe_allow_html=True)


def _generate_inventory_summary(product_table: pd.DataFrame) -> Dict[str, float]:
    if product_table.empty:
        return {
            "weighted_days_cover": 0.0,
            "skus_below_safe": 0.0,
            "revenue_at_risk": 0.0,
            "ad_spend_low_stock_week": 0.0,
        }

    df = product_table.copy()
    df["Revenue"] = pd.to_numeric(df["Revenue"], errors="coerce").fillna(0.0)
    df["Stock Days"] = pd.to_numeric(df["Stock Days"], errors="coerce")
    df["ad_spend"] = pd.to_numeric(df["ad_spend"], errors="coerce").fillna(0.0)

    total_rev = df["Revenue"].sum()
    top = df.sort_values("Revenue", ascending=False).copy()
    if total_rev > 0:
        top["cum_share"] = top["Revenue"].cumsum() / total_rev
        top = top[top["cum_share"] <= 0.8] if (top["cum_share"] <= 0.8).any() else top.head(min(len(top), 5))

    weights = top["Revenue"].clip(lower=0)
    weighted_days = (top["Stock Days"].fillna(0) * weights).sum() / weights.sum() if weights.sum() > 0 else top["Stock Days"].fillna(0).mean()

    low_stock = df[df["Stock Days"].fillna(0) < 14].copy()
    if low_stock.empty:
        revenue_at_risk = 0.0
        ad_burn = 0.0
    else:
        coverage_factor = ((14 - low_stock["Stock Days"].fillna(0)).clip(lower=0) / 14).clip(upper=1)
        revenue_at_risk = float((low_stock["Revenue"] * coverage_factor).sum())
        ad_burn = float((low_stock["ad_spend"] / 14.0 * 7.0).sum())

    return {
        "weighted_days_cover": float(weighted_days if pd.notna(weighted_days) else 0.0),
        "skus_below_safe": float(len(low_stock)),
        "revenue_at_risk": revenue_at_risk,
        "ad_spend_low_stock_week": ad_burn,
    }


@st.cache_data(ttl=600)
def _fetch_inventory_activity_frame(
    _db,
    *,
    client_id: str,
    account_id: str,
    marketplace_id: str,
    end_date: date,
) -> Tuple[pd.DataFrame, str]:
    start_60 = end_date - timedelta(days=59)
    start_7 = end_date - timedelta(days=6)
    q = """
        WITH sales_60 AS (
            SELECT
                child_asin AS asin,
                SUM(COALESCE(units_ordered, 0)) AS orders_60d,
                SUM(COALESCE(sessions, 0)) AS sessions_60d
            FROM sc_raw.sales_traffic
            WHERE account_id = %s
              AND marketplace_id = %s
              AND report_date BETWEEN %s AND %s
            GROUP BY child_asin
        ),
        apc_exact AS (
            SELECT DISTINCT
                client_id, campaign_name, ad_group_name, asin
            FROM advertised_product_cache
            WHERE client_id = %s
              AND asin IS NOT NULL
              AND asin <> ''
        ),
        campaign_single_asin AS (
            SELECT
                client_id,
                campaign_name,
                MIN(asin) AS asin
            FROM apc_exact
            GROUP BY client_id, campaign_name
            HAVING COUNT(DISTINCT asin) = 1
        ),
        ad_group_single_asin AS (
            SELECT
                client_id,
                campaign_name,
                ad_group_name,
                MIN(asin) AS asin
            FROM apc_exact
            GROUP BY client_id, campaign_name, ad_group_name
            HAVING COUNT(DISTINCT asin) = 1
        ),
        spend_60 AS (
            SELECT
                COALESCE(ex.asin, agsa.asin, csa.asin) AS asin,
                SUM(COALESCE(rst.spend, 0)) AS ad_spend_60d
            FROM raw_search_term_data rst
            LEFT JOIN apc_exact ex
              ON ex.client_id = rst.client_id
             AND LOWER(ex.campaign_name) = LOWER(rst.campaign_name)
             AND LOWER(ex.ad_group_name) = LOWER(rst.ad_group_name)
            LEFT JOIN ad_group_single_asin agsa
              ON agsa.client_id = rst.client_id
             AND LOWER(agsa.campaign_name) = LOWER(rst.campaign_name)
             AND LOWER(agsa.ad_group_name) = LOWER(rst.ad_group_name)
            LEFT JOIN campaign_single_asin csa
              ON csa.client_id = rst.client_id
             AND LOWER(csa.campaign_name) = LOWER(rst.campaign_name)
            WHERE rst.client_id = %s
              AND rst.report_date BETWEEN %s AND %s
              AND COALESCE(ex.asin, agsa.asin, csa.asin) IS NOT NULL
            GROUP BY COALESCE(ex.asin, agsa.asin, csa.asin)
        ),
        spend_7 AS (
            SELECT
                COALESCE(ex.asin, agsa.asin, csa.asin) AS asin,
                SUM(COALESCE(rst.spend, 0)) AS ad_spend_7d
            FROM raw_search_term_data rst
            LEFT JOIN apc_exact ex
              ON ex.client_id = rst.client_id
             AND LOWER(ex.campaign_name) = LOWER(rst.campaign_name)
             AND LOWER(ex.ad_group_name) = LOWER(rst.ad_group_name)
            LEFT JOIN ad_group_single_asin agsa
              ON agsa.client_id = rst.client_id
             AND LOWER(agsa.campaign_name) = LOWER(rst.campaign_name)
             AND LOWER(agsa.ad_group_name) = LOWER(rst.ad_group_name)
            LEFT JOIN campaign_single_asin csa
              ON csa.client_id = rst.client_id
             AND LOWER(csa.campaign_name) = LOWER(rst.campaign_name)
            WHERE rst.client_id = %s
              AND rst.report_date BETWEEN %s AND %s
              AND COALESCE(ex.asin, agsa.asin, csa.asin) IS NOT NULL
            GROUP BY COALESCE(ex.asin, agsa.asin, csa.asin)
        ),
        actions_60 AS (
            SELECT
                COALESCE(ex.asin, agsa.asin, csa.asin) AS asin,
                COUNT(*) AS actions_60d
            FROM actions_log al
            LEFT JOIN apc_exact ex
              ON ex.client_id = al.client_id
             AND LOWER(ex.campaign_name) = LOWER(al.campaign_name)
             AND LOWER(ex.ad_group_name) = LOWER(al.ad_group_name)
            LEFT JOIN ad_group_single_asin agsa
              ON agsa.client_id = al.client_id
             AND LOWER(agsa.campaign_name) = LOWER(al.campaign_name)
             AND LOWER(agsa.ad_group_name) = LOWER(al.ad_group_name)
            LEFT JOIN campaign_single_asin csa
              ON csa.client_id = al.client_id
             AND LOWER(csa.campaign_name) = LOWER(al.campaign_name)
            WHERE al.client_id = %s
              AND DATE(al.action_date) BETWEEN %s AND %s
              AND COALESCE(ex.asin, agsa.asin, csa.asin) IS NOT NULL
            GROUP BY COALESCE(ex.asin, agsa.asin, csa.asin)
        ),
        latest_inv AS (
            SELECT DISTINCT ON (asin)
                asin,
                COALESCE(afn_fulfillable_quantity, 0) AS fulfillable_qty,
                snapshot_date
            FROM sc_raw.fba_inventory
            WHERE client_id = %s
            ORDER BY asin, snapshot_date DESC
        ),
        low_stock AS (
            SELECT
                i.asin,
                CASE
                    WHEN COALESCE(s.orders_60d, 0) > 0
                    THEN i.fulfillable_qty / NULLIF((COALESCE(s.orders_60d, 0)::float / 60.0), 0)
                    ELSE NULL
                END AS days_of_cover
            FROM latest_inv i
            LEFT JOIN sales_60 s ON s.asin = i.asin
        ),
        spend_7_debug AS (
            SELECT
                COUNT(*) AS raw_rows_7d,
                SUM(COALESCE(rst.spend, 0)) AS raw_spend_7d,
                SUM(CASE WHEN COALESCE(ex.asin, csa.asin) IS NOT NULL THEN COALESCE(rst.spend, 0) ELSE 0 END) AS mapped_spend_7d,
                SUM(CASE WHEN COALESCE(ex.asin, csa.asin) IS NULL THEN COALESCE(rst.spend, 0) ELSE 0 END) AS unmapped_spend_7d
            FROM raw_search_term_data rst
            LEFT JOIN apc_exact ex
              ON ex.client_id = rst.client_id
             AND ex.campaign_name = rst.campaign_name
             AND ex.ad_group_name = rst.ad_group_name
            LEFT JOIN campaign_single_asin csa
              ON csa.client_id = rst.client_id
             AND csa.campaign_name = rst.campaign_name
            WHERE rst.client_id = %s
              AND rst.report_date BETWEEN %s AND %s
        ),
        low_stock_debug AS (
            SELECT COUNT(*) AS low_stock_asin_count
            FROM low_stock
            WHERE days_of_cover IS NOT NULL
              AND days_of_cover < 14
        ),
        asins AS (
            SELECT asin FROM sales_60
            UNION
            SELECT asin FROM spend_60
            UNION
            SELECT asin FROM actions_60
            UNION
            SELECT asin FROM low_stock
        )
        SELECT
            a.asin,
            COALESCE(s.orders_60d, 0) AS orders_60d,
            COALESCE(s.sessions_60d, 0) AS sessions_60d,
            COALESCE(sp60.ad_spend_60d, 0) AS ad_spend_60d,
            COALESCE(sp7.ad_spend_7d, 0) AS ad_spend_7d,
            COALESCE(act.actions_60d, 0) AS actions_60d,
            COALESCE(ls.days_of_cover, NULL) AS days_of_cover,
            CASE WHEN ls.days_of_cover IS NOT NULL AND ls.days_of_cover < 14 THEN 1 ELSE 0 END AS is_low_stock,
            COALESCE(sd.mapped_spend_7d, 0) AS debug_mapped_spend_7d,
            COALESCE(sd.unmapped_spend_7d, 0) AS debug_unmapped_spend_7d,
            COALESCE(sd.raw_spend_7d, 0) AS debug_raw_spend_7d,
            COALESCE(ld.low_stock_asin_count, 0) AS debug_low_stock_asin_count
        FROM asins a
        LEFT JOIN sales_60 s ON s.asin = a.asin
        LEFT JOIN spend_60 sp60 ON sp60.asin = a.asin
        LEFT JOIN spend_7 sp7 ON sp7.asin = a.asin
        LEFT JOIN actions_60 act ON act.asin = a.asin
        LEFT JOIN low_stock ls ON ls.asin = a.asin
        CROSS JOIN spend_7_debug sd
        CROSS JOIN low_stock_debug ld
    """
    params = (
        account_id, marketplace_id, start_60, end_date,
        client_id,
        client_id, start_60, end_date,
        client_id, start_7, end_date,
        client_id, start_60, end_date,
        client_id,
        client_id, start_7, end_date,
    )
    try:
        df = _to_df_query(_db, q, params)
    except Exception:
        df = pd.DataFrame(
            columns=[
                "asin",
                "orders_60d",
                "sessions_60d",
                "ad_spend_60d",
                "ad_spend_7d",
                "actions_60d",
                "days_of_cover",
                "is_low_stock",
                "debug_mapped_spend_7d",
                "debug_unmapped_spend_7d",
                "debug_raw_spend_7d",
                "debug_low_stock_asin_count",
            ]
        )
    return df, q


def _generate_inventory_summary_filtered(
    product_table: pd.DataFrame,
    activity_df: pd.DataFrame,
) -> Dict[str, float]:
    if product_table.empty:
        return {
            "weighted_days_cover": 0.0,
            "skus_below_safe": 0.0,
            "revenue_at_risk": 0.0,
            "ad_spend_low_stock_week": 0.0,
            "inactive_excluded": 0.0,
            "low_stock_asin_count": 0.0,
            "debug_mapped_spend_7d": 0.0,
            "debug_unmapped_spend_7d": 0.0,
            "debug_raw_spend_7d": 0.0,
            "audit_formula": "sum(ad_spend_7d for low-stock active ASINs)",
        }

    df = product_table.copy()
    if "ASIN" not in df.columns:
        df["ASIN"] = ""
    df["ASIN"] = df["ASIN"].astype(str)
    df["Revenue"] = pd.to_numeric(df["Revenue"], errors="coerce").fillna(0.0)
    df["Stock Days"] = pd.to_numeric(df["Stock Days"], errors="coerce")

    act = activity_df.copy() if activity_df is not None else pd.DataFrame()
    if act.empty:
        act = pd.DataFrame(
            columns=["asin", "orders_60d", "sessions_60d", "ad_spend_60d", "ad_spend_7d", "actions_60d", "days_of_cover", "is_low_stock"]
        )
    act = act.rename(columns={"asin": "ASIN"})
    for col in ("orders_60d", "sessions_60d", "ad_spend_60d", "ad_spend_7d", "actions_60d", "is_low_stock"):
        if col not in act.columns:
            act[col] = 0.0
        act[col] = pd.to_numeric(act[col], errors="coerce").fillna(0.0)
    for col in ("debug_mapped_spend_7d", "debug_unmapped_spend_7d", "debug_raw_spend_7d", "debug_low_stock_asin_count"):
        if col not in act.columns:
            act[col] = 0.0
        act[col] = pd.to_numeric(act[col], errors="coerce").fillna(0.0)
    act["ASIN"] = act["ASIN"].astype(str)

    merged = df.merge(act, on="ASIN", how="left")
    for col in ("orders_60d", "sessions_60d", "ad_spend_60d", "ad_spend_7d", "actions_60d", "is_low_stock"):
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0)

    inactive_mask = (merged["sessions_60d"] <= 0) & (merged["ad_spend_60d"] <= 0)
    eligible_mask = (merged["orders_60d"] >= 1) | (merged["actions_60d"] > 0)
    active = merged[eligible_mask & ~inactive_mask].copy()
    inactive_excluded = float(inactive_mask.sum())

    if active.empty:
        return {
            "weighted_days_cover": 0.0,
            "skus_below_safe": 0.0,
            "revenue_at_risk": 0.0,
            "ad_spend_low_stock_week": 0.0,
            "inactive_excluded": inactive_excluded,
            "low_stock_asin_count": 0.0,
            "weighted_top_n": 0,
            "debug_mapped_spend_7d": float(act["debug_mapped_spend_7d"].max() if "debug_mapped_spend_7d" in act.columns else 0.0),
            "debug_unmapped_spend_7d": float(act["debug_unmapped_spend_7d"].max() if "debug_unmapped_spend_7d" in act.columns else 0.0),
            "debug_raw_spend_7d": float(act["debug_raw_spend_7d"].max() if "debug_raw_spend_7d" in act.columns else 0.0),
            "audit_formula": "sum(ad_spend_7d for low-stock active ASINs)",
        }

    top_n = min(len(active), 75)
    top = active.sort_values("Revenue", ascending=False).head(top_n)
    weights = top["Revenue"].clip(lower=0)
    weighted_days = (top["Stock Days"].fillna(0) * weights).sum() / weights.sum() if weights.sum() > 0 else top["Stock Days"].fillna(0).mean()

    oos_mask = active["Stock Days"].fillna(-1) == 0
    low_stock = active[(active["is_low_stock"] > 0) | oos_mask].copy()
    if low_stock.empty:
        low_stock = active[active["Stock Days"].fillna(0) < 14].copy()
    if low_stock.empty:
        revenue_at_risk = 0.0
        ad_spend_7d_low_stock = 0.0
    else:
        coverage_factor = ((14 - low_stock["Stock Days"].fillna(0)).clip(lower=0) / 14).clip(upper=1)
        revenue_at_risk = float((low_stock["Revenue"] * coverage_factor).sum())
        # Exact weekly spend: raw 7-day spend mapped through advertised_product_cache by ASIN.
        ad_spend_7d_low_stock = float(low_stock["ad_spend_7d"].sum())

    return {
        "weighted_days_cover": float(weighted_days if pd.notna(weighted_days) else 0.0),
        "skus_below_safe": float(len(low_stock)),
        "revenue_at_risk": revenue_at_risk,
        "ad_spend_low_stock_week": ad_spend_7d_low_stock,
        "inactive_excluded": inactive_excluded,
        "low_stock_asin_count": float(low_stock["ASIN"].nunique() if "ASIN" in low_stock.columns else len(low_stock)),
        "weighted_top_n": top_n,
        "debug_mapped_spend_7d": float(act["debug_mapped_spend_7d"].max() if "debug_mapped_spend_7d" in act.columns else 0.0),
        "debug_unmapped_spend_7d": float(act["debug_unmapped_spend_7d"].max() if "debug_unmapped_spend_7d" in act.columns else 0.0),
        "debug_raw_spend_7d": float(act["debug_raw_spend_7d"].max() if "debug_raw_spend_7d" in act.columns else 0.0),
        "audit_formula": "ad_spend_low_stock_week = SUM(ad_spend_7d) for ASINs with Stock Days < 14 after activity filter",
    }


def _build_insights(
    *,
    product_table: pd.DataFrame,
    inventory_summary: Dict[str, float],
    tacos_value: Optional[float],
    roas_value: Optional[float],
    cvr_value: Optional[float],
    organic_pct: Optional[float],
    cvr_delta: Optional[float],
) -> Dict[str, List[str]]:
    critical: List[str] = []
    growth: List[str] = []
    efficiency: List[str] = []

    if inventory_summary.get("skus_below_safe", 0) > 0:
        critical.append(
            f"{int(inventory_summary['skus_below_safe'])} SKU(s) are below 14 days of cover; tighten spend to protect rank continuity."
        )
    if inventory_summary.get("revenue_at_risk", 0) > 0:
        critical.append(
            f"Estimated revenue at risk over next 14 days: {_format_currency(inventory_summary['revenue_at_risk'])}."
        )
    if tacos_value is not None and tacos_value > 0.16:
        critical.append(f"TACOS is elevated at {_format_percent(tacos_value)}; protect margin with tighter query controls.")
    if cvr_delta is not None and cvr_delta < -8:
        critical.append(f"CVR trend deteriorated {_delta_text(cvr_delta)} versus prior window; investigate listing and Buy Box disruptions.")

    if product_table is not None and not product_table.empty:
        healthy = product_table[(product_table["TACOS"] <= 0.10) & (product_table["CVR"] >= product_table["CVR"].median())]
        if not healthy.empty:
            top = healthy.sort_values("Revenue", ascending=False).iloc[0]
            growth.append(
                f"{top['SKU']} has efficient TACOS ({_format_percent(top['TACOS'])}) with strong CVR; increase coverage incrementally."
            )
        high_organic = product_table.sort_values("Revenue", ascending=False).head(1)
        if not high_organic.empty and organic_pct is not None and organic_pct >= 0.55:
            growth.append(
                f"Organic share is {_format_percent(organic_pct)}; prioritize top-converting parents to compound rank-led growth."
            )

    if roas_value is not None and roas_value >= 3.5:
        growth.append(f"ROAS at {roas_value:.2f}x gives room to scale high-intent placements without breaking efficiency guardrails.")

    if product_table is not None and not product_table.empty:
        inefficient = product_table[(product_table["TACOS"] > 0.18) & (product_table["Revenue"] > 0)]
        if not inefficient.empty:
            top_bad = inefficient.sort_values("TACOS", ascending=False).iloc[0]
            efficiency.append(
                f"Rebalance spend from {top_bad['SKU']} (TACOS {_format_percent(top_bad['TACOS'])}) to lower-TACOS parents."
            )
        weak_cvr = product_table[product_table["CVR"] < max(0.02, product_table["CVR"].median() * 0.7)]
        if not weak_cvr.empty:
            efficiency.append(
                f"{len(weak_cvr)} parent(s) show materially weak CVR; run search-term cleanup and listing quality checks before scaling."
            )

    if tacos_value is not None and tacos_value > 0.12:
        efficiency.append("Audit broad and auto match spend concentration; remove non-converting query clusters first.")

    # Ensure each panel remains populated with data-based defaults.
    if not critical:
        critical.append("No hard stop risks detected from current inventory and efficiency thresholds.")
    if not growth:
        growth.append("Growth remains available through top-parent budget expansion where CVR and TACOS are both in control.")
    if not efficiency:
        efficiency.append("Efficiency is stable; continue weekly negatives and placement bid discipline.")

    return {
        "critical": critical[:3],
        "growth": growth[:3],
        "efficiency": efficiency[:3],
    }


def _render_insight_panel(title: str, color: str, items: List[str]) -> None:
    cmap = {
        "rose": ("#fb7185", "rgba(244,63,94,0.08)", "rgba(244,63,94,0.34)"),
        "emerald": ("#34d399", "rgba(16,185,129,0.08)", "rgba(16,185,129,0.34)"),
        "blue": ("#60a5fa", "rgba(59,130,246,0.08)", "rgba(59,130,246,0.34)"),
    }
    fg, bg, border = cmap[color]
    rows = "".join([f"<li style='margin-bottom:8px; color:#d1d5db'>{item}</li>" for item in items])
    st.markdown(
        f"""
        <div class="bo-insight" style="background:{bg}; border-color:{border}">
            <div style="color:{fg}; font-size:12px; letter-spacing:.08em; text-transform:uppercase; font-weight:700; margin-bottom:10px;">{title}</div>
            <ul style="margin:0; padding-left:16px;">{rows}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_business_overview() -> None:
    client_id = st.session_state.get("active_account_id")
    if not client_id:
        st.warning("Please select an account first.")
        return

    _inject_business_overview_theme()

    if "biz_overview_window" not in st.session_state:
        st.session_state["biz_overview_window"] = "30D"

    top_l, top_r = st.columns([4, 2])
    with top_l:
        st.markdown(
            """
            <div class="bo-topbar">
                <h1 class="bo-title">SADDL Mission Control</h1>
                <div class="bo-subtitle">Holistic Business Overview &amp; Execution Engine</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with top_r:
        st.radio(
            "Date Range",
            ["14D", "30D", "60D"],
            horizontal=True,
            key="biz_overview_window",
            label_visibility="collapsed",
        )

    window_days = int(str(st.session_state.get("biz_overview_window", "30D")).replace("D", ""))
    test_mode = bool(st.session_state.get("test_mode", False))
    spapi_available = check_spapi_available(client_id)
    data = fetch_business_overview_data(
        client_id=client_id,
        window_days=window_days,
        test_mode=test_mode,
        spapi_available=spapi_available,
        cache_version=str(st.session_state.get("data_upload_timestamp", "init")),
    )
    if not data:
        st.info("No data available for this account.")
        return

    currency = get_account_currency()

    target_curr = data["target_current"].copy()
    target_prev = data["target_previous"].copy()
    traffic_daily = data["traffic_daily"].copy()
    account_daily = data["account_daily"].copy()
    ad_spend_daily = data["ad_spend_daily"].copy() if data.get("ad_spend_daily") is not None else pd.DataFrame()

    # Ad-side aggregates
    curr_ad_spend = 0.0
    prev_ad_spend = 0.0
    if not ad_spend_daily.empty:
        curr_ad_spend = float(
            pd.to_numeric(
                ad_spend_daily[
                    (ad_spend_daily["report_date"].dt.date >= data["start_date"])
                    & (ad_spend_daily["report_date"].dt.date <= data["end_date"])
                ].get("ad_spend", 0),
                errors="coerce",
            ).fillna(0).sum()
        )
        prev_ad_spend = float(
            pd.to_numeric(
                ad_spend_daily[
                    (ad_spend_daily["report_date"].dt.date >= data["prev_start"])
                    & (ad_spend_daily["report_date"].dt.date <= data["prev_end"])
                ].get("ad_spend", 0),
                errors="coerce",
            ).fillna(0).sum()
        )
    if curr_ad_spend <= 0 and not target_curr.empty:
        curr_ad_spend = float(pd.to_numeric(target_curr.get("Spend", 0), errors="coerce").fillna(0).sum())
    if prev_ad_spend <= 0 and not target_prev.empty:
        prev_ad_spend = float(pd.to_numeric(target_prev.get("Spend", 0), errors="coerce").fillna(0).sum())

    curr_ad_sales = 0.0
    prev_ad_sales = 0.0
    if not ad_spend_daily.empty:
        curr_ad_sales = float(
            pd.to_numeric(
                ad_spend_daily[
                    (ad_spend_daily["report_date"].dt.date >= data["start_date"])
                    & (ad_spend_daily["report_date"].dt.date <= data["end_date"])
                ].get("ad_sales", 0),
                errors="coerce",
            ).fillna(0).sum()
        )
        prev_ad_sales = float(
            pd.to_numeric(
                ad_spend_daily[
                    (ad_spend_daily["report_date"].dt.date >= data["prev_start"])
                    & (ad_spend_daily["report_date"].dt.date <= data["prev_end"])
                ].get("ad_sales", 0),
                errors="coerce",
            ).fillna(0).sum()
        )
    if curr_ad_sales <= 0 and not target_curr.empty:
        curr_ad_sales = float(pd.to_numeric(target_curr.get("Sales", 0), errors="coerce").fillna(0).sum())
    if prev_ad_sales <= 0 and not target_prev.empty:
        prev_ad_sales = float(pd.to_numeric(target_prev.get("Sales", 0), errors="coerce").fillna(0).sum())

    # Initialize business totals; populated from account-wide SP-API next.
    curr_revenue = 0.0
    prev_revenue = 0.0
    curr_units = 0.0
    prev_units = 0.0

    if not traffic_daily.empty:
        curr_traffic = traffic_daily[
            (traffic_daily["report_date"].dt.date >= data["start_date"]) &
            (traffic_daily["report_date"].dt.date <= data["end_date"])
        ]
        prev_traffic = traffic_daily[
            (traffic_daily["report_date"].dt.date >= data["prev_start"]) &
            (traffic_daily["report_date"].dt.date <= data["prev_end"])
        ]
    else:
        curr_traffic = pd.DataFrame(columns=["sessions", "page_views", "units", "revenue"])
        prev_traffic = pd.DataFrame(columns=["sessions", "page_views", "units", "revenue"])

    curr_sessions = float(pd.to_numeric(curr_traffic.get("sessions", 0), errors="coerce").fillna(0).sum())
    prev_sessions = float(pd.to_numeric(prev_traffic.get("sessions", 0), errors="coerce").fillna(0).sum())
    curr_page_views = float(pd.to_numeric(curr_traffic.get("page_views", 0), errors="coerce").fillna(0).sum())
    prev_page_views = float(pd.to_numeric(prev_traffic.get("page_views", 0), errors="coerce").fillna(0).sum())
    curr_orders_traffic = float(pd.to_numeric(curr_traffic.get("units", 0), errors="coerce").fillna(0).sum())
    prev_orders_traffic = float(pd.to_numeric(prev_traffic.get("units", 0), errors="coerce").fillna(0).sum())
    curr_sales_traffic = float(pd.to_numeric(curr_traffic.get("revenue", 0), errors="coerce").fillna(0).sum())
    prev_sales_traffic = float(pd.to_numeric(prev_traffic.get("revenue", 0), errors="coerce").fillna(0).sum())

    global_cvr = calculate_cvr(curr_orders_traffic, curr_sessions) or 0.0
    prev_cvr = calculate_cvr(prev_orders_traffic, prev_sessions) or 0.0
    global_aov = calculate_aov(curr_sales_traffic, curr_orders_traffic) or 0.0
    prev_aov = calculate_aov(prev_sales_traffic, prev_orders_traffic) or 0.0

    account_curr = account_daily[
        (account_daily["report_date"].dt.date >= data["start_date"]) &
        (account_daily["report_date"].dt.date <= data["end_date"])
    ].copy() if not account_daily.empty else pd.DataFrame()
    account_prev = account_daily[
        (account_daily["report_date"].dt.date >= data["prev_start"]) &
        (account_daily["report_date"].dt.date <= data["prev_end"])
    ].copy() if not account_daily.empty else pd.DataFrame()

    if not account_curr.empty:
        curr_revenue = float(pd.to_numeric(account_curr["total_ordered_revenue"], errors="coerce").fillna(0).sum())
        curr_units = float(pd.to_numeric(account_curr["total_units_ordered"], errors="coerce").fillna(0).sum())
        total_sales_acc = curr_revenue
    else:
        curr_revenue = curr_sales_traffic
        curr_units = curr_orders_traffic
        total_sales_acc = curr_revenue

    if not account_prev.empty:
        prev_revenue = float(pd.to_numeric(account_prev["total_ordered_revenue"], errors="coerce").fillna(0).sum())
        prev_units = float(pd.to_numeric(account_prev["total_units_ordered"], errors="coerce").fillna(0).sum())
    else:
        prev_revenue = prev_sales_traffic
        prev_units = prev_orders_traffic

    # Business TACOS must be computed as total ad spend / total sales.
    global_tacos = calculate_tacos(curr_ad_spend, curr_revenue) or 0.0
    prev_tacos = calculate_tacos(prev_ad_spend, prev_revenue) or 0.0

    # Keep paid + organic reconciled to total sales.
    ad_sales_acc = min(max(curr_ad_sales, 0.0), max(total_sales_acc, 0.0))
    organic_sales_total = max(total_sales_acc - ad_sales_acc, 0.0)

    margin_proxy = curr_revenue - curr_ad_spend - (curr_revenue * 0.30)
    prev_margin = prev_revenue - prev_ad_spend - (prev_revenue * 0.30)

    global_acos = calculate_tacos(curr_ad_spend, curr_ad_sales) or 0.0
    prev_acos = calculate_tacos(prev_ad_spend, prev_ad_sales) or 0.0
    global_roas = calculate_roas(curr_ad_sales, curr_ad_spend) or 0.0
    prev_roas = calculate_roas(prev_ad_sales, prev_ad_spend) or 0.0
    organic_pct = calculate_organic_pct(organic_sales_total, total_sales_acc) or 0.0
    ad_dependency = calculate_organic_pct(ad_sales_acc, total_sales_acc) or 0.0

    # Product frame
    product_base = data["product_table_raw"].copy() if data["product_table_raw"] is not None else pd.DataFrame()
    if not product_base.empty:
        inventory_raw = data["inventory_raw"].copy() if data["inventory_raw"] is not None else pd.DataFrame()
        for col in ("sessions", "page_views", "units", "sales"):
            if col not in product_base.columns:
                product_base[col] = 0

        if spapi_available and not inventory_raw.empty:
            product_base = product_base.merge(
                inventory_raw[["asin", "afn_fulfillable_quantity", "afn_total_quantity", "product_name", "sku"]],
                on="asin",
                how="left",
                suffixes=("", "_inv"),
            )
            product_base["units"] = pd.to_numeric(product_base.get("units", 0), errors="coerce").fillna(0)
            velocity = (product_base["units"] / max(window_days, 1)).replace(0, pd.NA)
            product_base["days_of_cover"] = pd.to_numeric(product_base.get("afn_fulfillable_quantity", 0), errors="coerce") / velocity
            product_base["days_of_cover"] = product_base["days_of_cover"].replace([pd.NA, pd.NaT], 0).fillna(0)
        else:
            product_base["days_of_cover"] = pd.NA

        product_base["sales"] = pd.to_numeric(product_base.get("sales", product_base.get("ad_sales", 0)), errors="coerce").fillna(0)
    else:
        product_base = pd.DataFrame()

    product_table = prepare_product_performance_table(product_base)
    inventory_audit_query = ""
    if spapi_available:
        db = get_db_manager(test_mode)
        activity_df, inventory_audit_query = _fetch_inventory_activity_frame(
            db,
            client_id=client_id,
            account_id=data.get("account_id", client_id),
            marketplace_id=data.get("marketplace_id", MARKETPLACE_ID),
            end_date=data["end_date"],
        )
        inventory_summary = _generate_inventory_summary_filtered(product_table, activity_df)
    else:
        inventory_summary = _generate_inventory_summary(product_table)

    trend_df = _merge_trend_frame(
        data["start_date"],
        data["end_date"],
        target_curr,
        traffic_daily,
        account_daily,
        ad_spend_daily,
    )

    # --- ROW 1: BUSINESS OUTCOMES ---
    _section_header("Business Outcomes", "Immediate business health & profitability")
    r1 = st.columns(4)
    with r1[0]:
        _hero_card("Total Revenue", _format_currency(curr_revenue, currency), "From SP-API account totals", _delta_text(calculate_delta_pct(curr_revenue, prev_revenue)))
    with r1[1]:
        _hero_card("Units Sold", _format_number(curr_units), "From SP-API account totals", _delta_text(calculate_delta_pct(curr_units, prev_units)))
    with r1[2]:
        _hero_card("Contribution Margin", _format_currency(margin_proxy, currency), "Rev - Ad Spend - COGS 30% (Est)", _delta_text(calculate_delta_pct(margin_proxy, prev_margin)))
    with r1[3]:
        _hero_card("TACOS", _format_percent(global_tacos), "Total Ad Spend / Total Sales", _delta_text(calculate_delta_pct(global_tacos, prev_tacos)), inverse_trend=True)

    # --- ROW 2: DEMAND & CONVERSION ENGINE ---
    _section_header("Demand & Conversion Engine", "Diagnose why revenue moved across the funnel")
    r2_metrics = st.columns(4)
    with r2_metrics[0]:
        render_metric_card("Sessions", _format_number(curr_sessions), _delta_text(calculate_delta_pct(curr_sessions, prev_sessions)))
    with r2_metrics[1]:
        render_metric_card("Page Views", _format_number(curr_page_views), _delta_text(calculate_delta_pct(curr_page_views, prev_page_views)))
    with r2_metrics[2]:
        render_metric_card("Conversion Rate", _format_percent(global_cvr), _delta_text(calculate_delta_pct(global_cvr, prev_cvr)))
    with r2_metrics[3]:
        render_metric_card("Avg Order Value", _format_currency(global_aov, currency), _delta_text(calculate_delta_pct(global_aov, prev_aov)), inverse=True)

    with st.container(border=True):
        st.markdown("**Trend: Sessions -> Orders -> Revenue**")
        st.plotly_chart(_build_composed_figure(trend_df, currency), use_container_width=True)

    # --- ROW 3 + 4 ---
    mix_col, ad_col = st.columns(2)
    with mix_col:
        _section_header("Paid vs Organic Mix", "Reveal growth quality & ad dependency")
        with st.container(border=True):
            top_mix = st.columns(2)
            with top_mix[0]:
                render_metric_card("Organic %", _format_percent(organic_pct), _delta_text(calculate_delta_pct(organic_pct, None)))
            with top_mix[1]:
                render_metric_card("Ad Sales %", _format_percent(ad_dependency), _delta_text(calculate_delta_pct(ad_dependency, None)))
            st.plotly_chart(_build_paid_vs_organic_figure(trend_df, currency), use_container_width=True)

    with ad_col:
        _section_header("Ad Impact", "Ads as a business lever (not campaign detail)")
        grid = st.columns(2)
        with grid[0]:
            render_metric_card("Ad Spend", _format_currency(curr_ad_spend, currency), _delta_text(calculate_delta_pct(curr_ad_spend, prev_ad_spend)), inverse=True)
        with grid[1]:
            render_metric_card("Ad Sales", _format_currency(curr_ad_sales, currency), _delta_text(calculate_delta_pct(curr_ad_sales, prev_ad_sales)))
        with grid[0]:
            render_metric_card("ROAS", f"{global_roas:.2f}x", _delta_text(calculate_delta_pct(global_roas, prev_roas)))
        with grid[1]:
            render_metric_card("ACOS", _format_percent(global_acos), _delta_text(calculate_delta_pct(global_acos, prev_acos)), inverse=True)

        with st.container(border=True):
            st.markdown("**Business TACOS**")
            curr_ad_daily = ad_spend_daily[
                (ad_spend_daily["report_date"].dt.date >= data["start_date"])
                & (ad_spend_daily["report_date"].dt.date <= data["end_date"])
            ].copy() if not ad_spend_daily.empty else pd.DataFrame()
            tacos_series = build_tacos_daily_series(account_curr, curr_ad_daily)
            st.plotly_chart(build_tacos_trend_figure(tacos_series, 0.15), use_container_width=True)
            if tacos_series.empty:
                st.caption("No valid TACOS points in selected window after excluding days with zero/null total sales.")

    # --- ROW 5: INVENTORY CONSTRAINTS ---
    if spapi_available:
        _section_header("Inventory Constraints", "Detect growth blockers before they impact scale")
        inv_cols = st.columns(4)
        with inv_cols[0]:
            _top_n_label = int(inventory_summary.get("weighted_top_n", 75))
            _constraint_card("Weighted Days of Cover", f"{inventory_summary['weighted_days_cover']:.0f} Days", f"Across top {_top_n_label} SKUs by revenue", "warning" if inventory_summary["weighted_days_cover"] < 45 else "healthy")
        with inv_cols[1]:
            _constraint_card("SKUs Below Safe Level", f"{int(inventory_summary['skus_below_safe'])} SKUs", "< 14 days of inventory left", "critical" if inventory_summary["skus_below_safe"] > 0 else "warning")
        with inv_cols[2]:
            _constraint_card("Revenue at Risk", _format_currency(inventory_summary["revenue_at_risk"], currency), "Estimated loss in next 14 days", "critical" if inventory_summary["revenue_at_risk"] > 0 else "warning")
        with inv_cols[3]:
            _constraint_card("Ad Spend on Low Stock", f"{_format_currency(inventory_summary['ad_spend_low_stock_week'], currency)}/wk", "Burning spend on constrained inventory", "warning" if inventory_summary["ad_spend_low_stock_week"] > 0 else "healthy")
        st.caption(f"{int(inventory_summary.get('inactive_excluded', 0))} inactive/discontinued SKUs excluded")
    else:
        st.info("SP-API not connected - inventory signals unavailable")

    # --- ROW 6: PRODUCT SNAPSHOT ---
    _section_header("Product Performance Snapshot", "Surface concentration & efficiency at the parent level")
    _render_product_table(product_table, currency)

    # --- ROW 7: EXECUTIVE INSIGHTS ---
    _section_header("Executive Insights", "Convert cross-data signals into immediate decisions")
    insights = _build_insights(
        product_table=product_table,
        inventory_summary=inventory_summary,
        tacos_value=global_tacos,
        roas_value=global_roas,
        cvr_value=global_cvr,
        organic_pct=organic_pct,
        cvr_delta=calculate_delta_pct(global_cvr, prev_cvr),
    )
    i_cols = st.columns(3)
    with i_cols[0]:
        _render_insight_panel("Critical Risks", "rose", insights["critical"])
    with i_cols[1]:
        _render_insight_panel("Growth Opportunities", "emerald", insights["growth"])
    with i_cols[2]:
        _render_insight_panel("Efficiency Actions", "blue", insights["efficiency"])


__all__ = [
    "DriverCallout",
    "fetch_business_overview_data",
    "compute_health_and_callouts",
    "build_tacos_trend_figure",
    "build_tacos_daily_series",
    "prepare_product_performance_table",
    "render_metric_card",
    "render_business_overview",
]
