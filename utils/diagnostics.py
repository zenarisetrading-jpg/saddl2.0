"""Diagnostics data access and UI formatting helpers (Phase 2 prep)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from app_core.db_manager import get_db_manager

# Load env from both desktop/.env and saddle/.env for CLI compatibility.
_HERE = Path(__file__).resolve().parent
load_dotenv(_HERE.parent / ".env")
load_dotenv(_HERE.parent.parent / ".env")


CLIENT_ID = "s2c_uae_test"
MARKETPLACE_ID = "A2VIGQ35RCS4UG"

SIGNAL_VIEWS = {
    "demand_contraction": "sc_analytics.signal_demand_contraction",
    "organic_decay": "sc_analytics.signal_organic_decay",
    "non_advertised_winners": "sc_analytics.signal_non_advertised_winners",
    "harvest_cannibalization": "sc_analytics.signal_harvest_cannibalization",
    "over_negation": "sc_analytics.signal_over_negation",
}

BOOLEAN_FLAG_COLUMN = {
    "demand_contraction": "is_demand_contraction",
    "organic_decay": "is_rank_decay",
    "non_advertised_winners": None,
    "harvest_cannibalization": "is_cannibalizing",
    "over_negation": "is_over_negated",
}

HAS_REPORT_DATE_COLUMN = {
    "demand_contraction": True,
    "organic_decay": True,
    "non_advertised_winners": False,
    "harvest_cannibalization": True,
    "over_negation": True,
}


@dataclass(frozen=True)
class SignalMeta:
    key: str
    label: str
    severity_default: str
    confidence_default: int


SIGNAL_META = {
    "demand_contraction": SignalMeta("demand_contraction", "Market Demand Contraction", "HIGH", 95),
    "organic_decay": SignalMeta("organic_decay", "Organic Rank Decay", "MEDIUM", 88),
    "non_advertised_winners": SignalMeta("non_advertised_winners", "Non-Advertised Winners", "MEDIUM", 80),
    "harvest_cannibalization": SignalMeta("harvest_cannibalization", "Harvest Cannibalization", "MEDIUM", 82),
    "over_negation": SignalMeta("over_negation", "Over-Negation", "MEDIUM", 76),
}


@st.cache_data(ttl=300, show_spinner=False)
def get_analysis_anchor_date(client_id: str = CLIENT_ID) -> date:
    """
    Latest common date across core diagnostics inputs.
    This prevents stale sources (e.g., PPC lagging) from distorting trend narratives.
    """
    scope = _resolve_scoped_account_context(client_id)
    account_id = scope["account_id"]
    marketplace_id = scope["marketplace_id"]
    query = f"""
    WITH dates AS (
      SELECT MAX(report_date)::date AS dt
      FROM sc_analytics.account_daily
      WHERE marketplace_id = '{marketplace_id}'
        AND account_id = '{account_id}'
      UNION ALL
      SELECT MAX(report_date)::date AS dt
      FROM sc_raw.sales_traffic
      WHERE marketplace_id = '{marketplace_id}'
        AND account_id = '{account_id}'
      UNION ALL
      SELECT MAX(report_date)::date AS dt
      FROM sc_raw.bsr_history
      WHERE account_id = '{account_id}'
      UNION ALL
      SELECT MAX(report_date)::date AS dt
      FROM public.raw_search_term_data
      WHERE client_id = '{client_id}'
    )
    SELECT MIN(dt) AS anchor_date
    FROM dates
    WHERE dt IS NOT NULL
    """
    try:
        result = _read_sql(query)
        if not result.empty and result.iloc[0, 0] is not None:
            value = result.iloc[0, 0]
            if hasattr(value, "date"):
                return value.date()
            if isinstance(value, date):
                return value
            return datetime.strptime(str(value), "%Y-%m-%d").date()
    except Exception:
        pass
    return date.today()


def _read_sql(query: str, params: Optional[List[Any]] = None) -> pd.DataFrame:
    """Execute a read-only query through the existing DB manager."""
    db = get_db_manager(test_mode=False)
    with db._get_connection() as conn:  # Existing manager pattern uses internal connection context.
        sql = query
        sql_params = params or []
        return pd.read_sql_query(sql, conn, params=sql_params)


def _resolve_scoped_account_context(client_id: str) -> Dict[str, str]:
    """
    Map a public client_id to active SP-API scope (account_id + marketplace_id).
    Falls back to client_id + default marketplace when no mapping row exists.
    """
    mapping_query = """
    SELECT account_id, marketplace_id
    FROM sc_raw.spapi_account_links
    WHERE public_client_id = %s
      AND is_active = TRUE
    ORDER BY updated_at DESC, id DESC
    LIMIT 1
    """
    try:
        result = _read_sql(mapping_query, [client_id])
        if not result.empty and result.iloc[0, 0]:
            account_id = str(result.iloc[0].get("account_id") or client_id)
            marketplace_id = str(result.iloc[0].get("marketplace_id") or MARKETPLACE_ID)
            return {"account_id": account_id, "marketplace_id": marketplace_id}
    except Exception:
        pass
    return {"account_id": client_id, "marketplace_id": MARKETPLACE_ID}


def _resolve_scoped_account_id(client_id: str) -> str:
    """
    Map a public client_id to internal SP-API account_id.
    Falls back to client_id if no mapping row exists.
    """
    return _resolve_scoped_account_context(client_id)["account_id"]


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _format_pct(value: Any, digits: int = 1, signed: bool = False) -> str:
    n = _safe_float(value)
    if n is None:
        return "-"
    return f"{n:+.{digits}f}%" if signed else f"{n:.{digits}f}%"


def _format_money(value: Any, currency: str = "AED", digits: int = 0) -> str:
    n = _safe_float(value)
    if n is None:
        return "-"
    return f"{n:,.{digits}f} {currency}"


def fetch_signal_view(
    signal_key: str,
    days: int = 30,
    active_only: bool = True,
    client_id: str = CLIENT_ID,
) -> pd.DataFrame:
    """Fetch rows from a signal view with optional active-signal filtering."""
    if signal_key not in SIGNAL_VIEWS:
        raise ValueError(f"Unknown signal_key: {signal_key}")

    view_name = SIGNAL_VIEWS[signal_key]
    flag_col = BOOLEAN_FLAG_COLUMN[signal_key]
    account_id = _resolve_scoped_account_id(client_id)
    clauses: List[str] = ["account_id = %s"]
    params: List[Any] = [account_id]
    if HAS_REPORT_DATE_COLUMN.get(signal_key, False):
        clauses.append("report_date >= CURRENT_DATE - %s")
        params.append(days)
    if active_only and flag_col:
        clauses.append(f"{flag_col} = TRUE")
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    order_by = "report_date DESC" if HAS_REPORT_DATE_COLUMN.get(signal_key, False) else "1 DESC"
    query = f"""
        SELECT *
        FROM {view_name}
        {where_clause}
        ORDER BY {order_by}
    """
    return _read_sql(query, params)


def fetch_all_signal_views(
    days: int = 30,
    active_only: bool = True,
    client_id: str = CLIENT_ID,
) -> Dict[str, pd.DataFrame]:
    """Fetch all signal views into a keyed dict."""
    return {
        key: fetch_signal_view(key, days=days, active_only=active_only, client_id=client_id)
        for key in SIGNAL_VIEWS
    }


def get_recent_validation_summary(client_id: str = CLIENT_ID, days: int = 14, validated_only: bool = True) -> Dict[str, Any]:
    """Read Impact Dashboard summary via existing manager API (read-only)."""
    db = get_db_manager(test_mode=False)
    # PostgresManager signature
    summary = db.get_impact_summary(client_id=client_id, before_days=14, after_days=days)

    # PostgresManager returns nested {"all": {...}, "validated": {...}}.
    # Impact Dashboard default is validated-only, but this can be switched off.
    if isinstance(summary, dict) and ("validated" in summary or "all" in summary):
        if validated_only:
            summary_metrics = summary.get("validated") or summary.get("all") or {}
        else:
            summary_metrics = summary.get("all") or summary.get("validated") or {}
    else:
        summary_metrics = summary or {}

    total_actions = int(summary_metrics.get("total_actions", 0) or 0)
    winners = int(summary_metrics.get("winners", 0) or 0)
    losers = int(summary_metrics.get("losers", max(total_actions - winners, 0)) or 0)
    win_rate = float(summary_metrics.get("win_rate", 0.0) or 0.0)
    help_rate = float(summary_metrics.get("pct_good", 0.0) or 0.0)
    avg_impact = float(summary_metrics.get("roas_lift_pct", 0.0) or 0.0)
    roas_before = float(summary_metrics.get("roas_before", 0.0) or 0.0)
    roas_after = float(summary_metrics.get("roas_after", 0.0) or 0.0)
    roas_delta_points = roas_after - roas_before

    return {
        "total_actions": total_actions,
        "winners": winners,
        "losers": losers,
        "win_rate": win_rate,
        "help_rate": help_rate,
        "avg_impact": avg_impact,
        "roas_before": roas_before,
        "roas_after": roas_after,
        "roas_delta_points": roas_delta_points,
        "after_days": days,
        "validated_only": validated_only,
        "raw": summary_metrics,
        "raw_full": summary,
    }


def format_signal_row(signal_key: str, row: pd.Series) -> Dict[str, Any]:
    """Normalize a single signal row to UI-friendly fields."""
    meta = SIGNAL_META[signal_key]
    report_date = row.get("report_date")
    if hasattr(report_date, "strftime"):
        report_date_str = report_date.strftime("%Y-%m-%d")
    else:
        report_date_str = str(report_date) if report_date is not None else ""

    evidence: List[str] = []
    if signal_key == "demand_contraction":
        evidence = [
            f"Organic CVR change: {_format_pct(row.get('organic_cvr_change_pct'), signed=True)}",
            f"Ad CVR change: {_format_pct(row.get('ad_cvr_change_pct'), signed=True)}",
            f"Avg CPC: {_safe_float(row.get('avg_cpc')) or '-'}",
        ]
    elif signal_key == "organic_decay":
        evidence = [
            f"ASIN: {row.get('child_asin', '-')}",
            f"Sessions change: {_format_pct(row.get('session_change_pct'), signed=True)}",
            f"Current BSR: {row.get('current_bsr', '-')}",
        ]
    elif signal_key == "non_advertised_winners":
        evidence = [
            f"ASIN: {row.get('child_asin', '-')}",
            f"30d revenue: {_format_money(row.get('revenue_30d'))}",
            f"Avg CVR: {_format_pct(row.get('avg_cvr'))}",
        ]
    elif signal_key == "harvest_cannibalization":
        evidence = [
            f"Harvest ROAS: {_safe_float(row.get('harvest_roas')) or '-'}",
            f"Total revenue: {_format_money(row.get('total_ordered_revenue'))}",
        ]
    elif signal_key == "over_negation":
        evidence = [
            f"Impressions: {int(row.get('total_impressions', 0) or 0):,}",
            f"CVR: {_format_pct(row.get('cvr'))}",
            f"ROAS: {_safe_float(row.get('roas')) or '-'}",
        ]

    return {
        "signal_key": signal_key,
        "title": meta.label,
        "severity": meta.severity_default,
        "confidence": meta.confidence_default,
        "report_date": report_date_str,
        "evidence": evidence,
        "raw": row.to_dict(),
    }


def format_signal_rows_for_ui(signal_key: str, df: pd.DataFrame, limit: int = 25) -> List[Dict[str, Any]]:
    """Format a signal dataframe into card-ready dictionaries."""
    if df.empty:
        return []
    return [format_signal_row(signal_key, row) for _, row in df.head(limit).iterrows()]


def get_diagnostics_overview_payload(client_id: str = CLIENT_ID, days: int = 14) -> Dict[str, Any]:
    """Fetch active signal summaries + impact context for the Overview page."""
    signals = fetch_all_signal_views(days=days, active_only=True, client_id=client_id)
    impact = get_recent_validation_summary(client_id=client_id, days=days)

    cards: List[Dict[str, Any]] = []
    for key, df in signals.items():
        cards.extend(format_signal_rows_for_ui(key, df, limit=3))

    return {
        "cards": cards,
        "impact": impact,
        "signals": signals,
    }


@st.cache_data(ttl=300, show_spinner=False)
def compute_health_score(client_id: str = CLIENT_ID, days: int = 30) -> Dict[str, Any]:
    """Compute 0-100 health score based on 4 metrics."""
    # Get current vs prior period
    account_id = _resolve_scoped_account_id(client_id)
    anchor_date = get_analysis_anchor_date(client_id=client_id)
    current_start = anchor_date - timedelta(days=days - 1)
    current_end = anchor_date
    prior_start = current_start - timedelta(days=days)
    prior_end = current_start - timedelta(days=1)

    # Helper for scalar queries -> float
    def get_scalar(sql):
        res = _read_sql(sql)
        if not res.empty and res.iloc[0, 0] is not None:
            return float(res.iloc[0, 0])
        return 0.0

    # 1. Total Sales Health (0-25 points)
    current_sales = get_scalar(f"""
        SELECT SUM(total_ordered_revenue) 
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{current_start}' AND '{current_end}'
        AND marketplace_id = '{MARKETPLACE_ID}'
        AND account_id = '{account_id}'
    """)
    prior_sales = get_scalar(f"""
        SELECT SUM(total_ordered_revenue)
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{prior_start}' AND '{prior_end}'
        AND marketplace_id = '{MARKETPLACE_ID}'
        AND account_id = '{account_id}'
    """)
    
    sales_change_pct = 0.0
    if prior_sales > 0:
        sales_change_pct = (current_sales - prior_sales) / prior_sales * 100
    sales_score = max(0, min(25, 25 * (1 + sales_change_pct/100)))

    # 2. TACOS Health (0-25 points)
    current_tacos = get_scalar(f"""
        SELECT AVG(tacos)
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{current_start}' AND '{current_end}'
        AND marketplace_id = '{MARKETPLACE_ID}'
        AND account_id = '{account_id}'
    """)
    prior_tacos = get_scalar(f"""
        SELECT AVG(tacos)
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{prior_start}' AND '{prior_end}'
        AND marketplace_id = '{MARKETPLACE_ID}'
        AND account_id = '{account_id}'
    """)
    
    tacos_change = current_tacos - prior_tacos
    tacos_score = max(0, min(25, 25 * (1 - tacos_change/10))) # Penalty for TACOS increase

    # 3. Organic Share Health (0-25 points)
    current_organic = get_scalar(f"""
        SELECT AVG(organic_share_pct)
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{current_start}' AND '{current_end}'
        AND marketplace_id = '{MARKETPLACE_ID}'
        AND account_id = '{account_id}'
    """)
    prior_organic = get_scalar(f"""
        SELECT AVG(organic_share_pct)
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{prior_start}' AND '{prior_end}'
        AND marketplace_id = '{MARKETPLACE_ID}'
        AND account_id = '{account_id}'
    """)

    organic_change = current_organic - prior_organic
    organic_score = max(0, min(25, 25 * (1 + organic_change/10)))

    # 4. BSR Health (0-25 points)
    current_bsr = get_scalar(f"""
        SELECT AVG(rank)
        FROM sc_raw.bsr_history
        WHERE report_date BETWEEN '{current_start}' AND '{current_end}'
        AND account_id = '{account_id}'
    """)
    prior_bsr = get_scalar(f"""
        SELECT AVG(rank)
        FROM sc_raw.bsr_history
        WHERE report_date BETWEEN '{prior_start}' AND '{prior_end}'
        AND account_id = '{account_id}'
    """)

    bsr_change_pct = 0.0
    if prior_bsr > 0:
        bsr_change_pct = (current_bsr - prior_bsr) / prior_bsr * 100
    
    # rank increase is BAD
    bsr_score = max(0, min(25, 25 * (1 - bsr_change_pct/20)))

    total_score = int(sales_score + tacos_score + organic_score + bsr_score)

    if total_score >= 80:
        status = "HEALTHY"
        color = "🟢"
    elif total_score >= 60:
        status = "CAUTION"
        color = "🟡"
    elif total_score >= 40:
        status = "DECLINING"
        color = "🟠"
    else:
        status = "CRITICAL"
        color = "🔴"

    return {
        'score': total_score,
        'status': status,
        'color': color,
        'sales_score': int(sales_score),
        'tacos_score': int(tacos_score),
        'organic_score': int(organic_score),
        'bsr_score': int(bsr_score),
        'sales_change_pct': sales_change_pct,
        'tacos_change': tacos_change,
        'organic_change': organic_change,
        'bsr_change_pct': bsr_change_pct,
        'current_sales': current_sales,
        'current_tacos': current_tacos,
        'current_organic': current_organic,
        'current_bsr': current_bsr,
        'as_of_date': anchor_date.isoformat(),
    }


def diagnose_root_causes(
    client_id: str = CLIENT_ID,
    days: int = 30,
    impact_days: int = 14,
    validated_only: bool = True,
) -> Dict[str, Any]:
    """Attribute performance changes to root causes."""
    account_id = _resolve_scoped_account_id(client_id)

    # 1. Check Organic Rank Decay
    bsr_res = _read_sql(f"""
        WITH current AS (
            SELECT AVG(rank) as avg_rank
            FROM sc_raw.bsr_history
            WHERE report_date >= CURRENT_DATE - {days}
              AND account_id = '{account_id}'
        ),
        prior AS (
            SELECT AVG(rank) as avg_rank
            FROM sc_raw.bsr_history
            WHERE report_date BETWEEN CURRENT_DATE - {days*2} AND CURRENT_DATE - {days} - 1
              AND account_id = '{account_id}'
        )
        SELECT 
            CASE WHEN p.avg_rank = 0 THEN 0 ELSE (c.avg_rank - p.avg_rank) / p.avg_rank * 100 END as rank_change_pct
        FROM current c, prior p
    """)
    bsr_change = 0.0
    if not bsr_res.empty and bsr_res.iloc[0, 0] is not None:
        bsr_change = float(bsr_res.iloc[0, 0])
    
    organic_decay_severity = max(0, min(100, bsr_change))

    # 2. Check Market Demand
    corr_res = _read_sql(f"""
        WITH metrics AS (
            SELECT 
                report_date,
                AVG(unit_session_percentage) as organic_cvr
            FROM sc_raw.sales_traffic
            WHERE report_date >= CURRENT_DATE - {days}
            AND marketplace_id = '{MARKETPLACE_ID}'
            AND account_id = '{account_id}'
            GROUP BY report_date
        ),
        ad_metrics AS (
            SELECT 
                report_date,
                SUM(orders)::FLOAT / NULLIF(SUM(clicks), 0) * 100 as paid_cvr
            FROM public.raw_search_term_data
            WHERE report_date >= CURRENT_DATE - {days}
            AND client_id = '{client_id}'
            GROUP BY report_date
        )
        SELECT CORR(m.organic_cvr, a.paid_cvr) as correlation
        FROM metrics m
        JOIN ad_metrics a USING (report_date)
    """)
    
    cvr_correlation = 0.0
    if not corr_res.empty and corr_res.iloc[0, 0] is not None:
        cvr_correlation = float(corr_res.iloc[0, 0])
    
    market_demand_severity = max(0, min(100, cvr_correlation * 100)) if cvr_correlation > 0.7 else 0

    # 3. Check Optimization Impact
    optimization_lift = get_recent_validation_summary(
        client_id=client_id,
        days=impact_days,
        validated_only=validated_only,
    )
    
    optimization_contribution = 0.0
    if optimization_lift.get('win_rate', 0) > 50:  # Lowered threshold to capture more positive signal
        optimization_contribution = abs(optimization_lift['avg_impact']) * 2 # Amplify signal
    
    total = organic_decay_severity + market_demand_severity + optimization_contribution
    
    if total > 0:
        organic_pct = organic_decay_severity / total * 100
        market_pct = market_demand_severity / total * 100
        optimization_pct = optimization_contribution / total * 100
    else:
        # Default to "Stable Market" if no strong signals
        organic_pct = 0
        market_pct = 100
        optimization_pct = 0
    
    return {
        'organic_decay_pct': int(organic_pct),
        'market_demand_pct': int(market_pct),
        'optimization_lift_pct': int(optimization_pct),
        'organic_severity': organic_decay_severity,
        'market_severity': market_demand_severity,
        'bsr_change': bsr_change,
        'cvr_correlation': cvr_correlation,
        'optimization_win_rate': optimization_lift.get('win_rate', 0),
        'optimization_help_rate': optimization_lift.get('help_rate', 0),
        'optimization_impact': optimization_lift.get('avg_impact', 0),
        'optimization_roas_delta_points': optimization_lift.get('roas_delta_points', 0),
        'optimization_winners': optimization_lift.get('winners', 0),
        'optimization_total_actions': optimization_lift.get('total_actions', 0),
        'impact_window_days': impact_days,
        'impact_validated_only': validated_only,
    }


def generate_recommendations(diagnosis: Dict[str, Any], health: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate prioritized action recommendations based on diagnosis."""
    recommendations = []
    
    organic_decay_pct = float(diagnosis.get('organic_decay_pct', 0) or 0)
    market_severity = float(diagnosis.get('market_severity', 0) or 0)
    cvr_corr = float(diagnosis.get('cvr_correlation', 0) or 0)
    bsr_change = float(diagnosis.get('bsr_change', 0) or 0)
    optimization_win_rate = float(diagnosis.get('optimization_win_rate', 0) or 0)
    optimization_impact = float(diagnosis.get('optimization_impact', 0) or 0)
    optimization_winners = int(diagnosis.get('optimization_winners', 0) or 0)
    optimization_total = int(diagnosis.get('optimization_total_actions', 0) or 0)

    # Rule 1: Real organic decay only (BSR worsening + meaningful share contribution)
    if organic_decay_pct > 35 and bsr_change > 0:
        recommendations.append({
            'priority': 'IMMEDIATE',
            'icon': '🎯',
            'action': 'Launch brand defense for top 5 ASINs',
            'reason': 'Stop rank decay from costing more ad spend',
            'severity': 'high'
        })
    
    # Rule 2: Demand softness only when supported by severity/correlation.
    if market_severity > 25 and cvr_corr >= 0.6:
        recommendations.append({
            'priority': 'HIGH',
            'icon': '📉',
            'action': 'Contract discovery spend 15% during demand softness',
            'reason': 'Preserve TACOS until market recovers',
            'severity': 'medium'
        })
    
    # Rule 3: Scale what is actually working when impact is positive.
    if optimization_total >= 10 and optimization_win_rate >= 45 and optimization_impact > 0:
        recommendations.append({
            'priority': 'OPPORTUNITY',
            'icon': '✅',
            'action': 'Scale patterns from validated winners',
            'reason': f"{optimization_winners}/{optimization_total} winners with +{optimization_impact:.1f}% ROAS lift",
            'severity': 'low'
        })
    elif optimization_total >= 10 and (optimization_win_rate < 35 or optimization_impact <= 0):
        recommendations.append({
            'priority': 'HIGH',
            'icon': '🧪',
            'action': 'Tighten action quality filters',
            'reason': 'Low win-rate/impact indicates weak action selection',
            'severity': 'medium'
        })
    
    # Rule 4: If BSR improving and organic growing, scale paid.
    if health.get('bsr_change_pct', 0) < -10 and health.get('organic_change', 0) > 5:
        recommendations.append({
            'priority': 'OPPORTUNITY',
            'icon': '📈',
            'action': 'Increase paid budget 20% to capitalize on organic growth',
            'reason': 'Ride the momentum while rank is improving',
            'severity': 'low'
        })
    
    # Rule 5: If TACOS spiking without revenue growth, cut waste
    if health.get('tacos_change', 0) > 5 and health.get('sales_change_pct', 0) < 2:
        recommendations.append({
            'priority': 'IMMEDIATE',
            'icon': '✂️',
            'action': 'Audit and pause bottom 20% of spend by ROAS',
            'reason': 'TACOS rising without revenue growth = waste',
            'severity': 'high'
        })

    if not recommendations:
        recommendations.append({
            'priority': 'MAINTAIN',
            'icon': '🧭',
            'action': 'Maintain current mix and monitor weekly',
            'reason': 'No dominant risk signal detected in the latest window',
            'severity': 'low'
        })
    
    priority_map = {'IMMEDIATE': 0, 'HIGH': 1, 'OPPORTUNITY': 2, 'MAINTAIN': 3}
    return sorted(recommendations, key=lambda x: priority_map.get(x['priority'], 4))


def generate_bsr_roas_interpretation(correlation: float) -> str:
    """Generate human-readable interpretation."""
    if correlation < -0.6:
        return ("Strong negative correlation: When you lose organic rank, "
                "paid ROAS declines because you're competing for traffic "
                "you used to get free. Defend organic rank OR accept lower "
                "ROAS as cost of maintaining visibility.")
    elif correlation < -0.3:
        return ("Moderate correlation: Organic rank affects paid efficiency "
                "but not the primary driver. Monitor both channels.")
    else:
        return ("Weak correlation: Organic rank and paid ROAS move independently. "
                "Focus on channel-specific optimizations.")


def compute_bsr_roas_correlation(days: int = 60, client_id: str = CLIENT_ID) -> Dict[str, Any]:
    """Compute correlation between BSR and paid ROAS."""
    account_id = _resolve_scoped_account_id(client_id)
    query = f"""
    WITH daily_bsr AS (
        SELECT 
            report_date,
            AVG(rank) as avg_bsr
        FROM sc_raw.bsr_history
        WHERE report_date >= CURRENT_DATE - {days}
          AND account_id = '{account_id}'
        GROUP BY report_date
    ),
    daily_roas AS (
        SELECT 
            report_date,
            SUM(sales) / NULLIF(SUM(spend), 0) as paid_roas
        FROM public.raw_search_term_data
        WHERE report_date >= CURRENT_DATE - {days}
        AND client_id = '{client_id}'
        GROUP BY report_date
    )
    SELECT 
        CORR(b.avg_bsr, r.paid_roas) as correlation,
        JSON_AGG(b.report_date ORDER BY b.report_date) as dates,
        JSON_AGG(b.avg_bsr ORDER BY b.report_date) as bsr_values,
        JSON_AGG(r.paid_roas ORDER BY b.report_date) as roas_values
    FROM daily_bsr b
    JOIN daily_roas r USING (report_date)
    """
    
    result = _read_sql(query)
    
    if result.empty or result.iloc[0, 0] is None:
        return {
            'correlation': 0.0,
            'dates': [],
            'bsr_values': [],
            'roas_values': [],
            'interpretation': "Insufficient data."
        }
    
    row = result.iloc[0]
    return {
        'correlation': float(row['correlation']),
        'dates': row['dates'],
        'bsr_values': row['bsr_values'],
        'roas_values': row['roas_values'],
        'interpretation': generate_bsr_roas_interpretation(float(row['correlation']))
    }


@st.cache_data(ttl=300, show_spinner=False)
def detect_cvr_divergence(days: int = 60, client_id: str = CLIENT_ID) -> Dict[str, Any]:
    """Detect if organic and paid CVR are moving together or diverging."""
    account_id = _resolve_scoped_account_id(client_id)
    query = f"""
    WITH organic_cvr AS (
        SELECT 
            report_date,
            AVG(unit_session_percentage) as organic_cvr
        FROM sc_raw.sales_traffic
        WHERE report_date >= CURRENT_DATE - {days}
        AND marketplace_id = '{MARKETPLACE_ID}'
        AND account_id = '{account_id}'
        GROUP BY report_date
    ),
    paid_cvr AS (
        SELECT 
            report_date,
            SUM(orders)::FLOAT / NULLIF(SUM(clicks), 0) * 100 as paid_cvr
        FROM public.raw_search_term_data
        WHERE report_date >= CURRENT_DATE - {days}
        AND client_id = '{client_id}'
        GROUP BY report_date
    )
    SELECT 
        CORR(o.organic_cvr, p.paid_cvr) as correlation,
        AVG(o.organic_cvr) as avg_organic_cvr,
        AVG(p.paid_cvr) as avg_paid_cvr,
        JSON_AGG(o.report_date ORDER BY o.report_date) as dates,
        JSON_AGG(o.organic_cvr ORDER BY o.report_date) as organic_values,
        JSON_AGG(p.paid_cvr ORDER BY o.report_date) as paid_values
    FROM organic_cvr o
    JOIN paid_cvr p USING (report_date)
    """
    
    result = _read_sql(query)
    
    if result.empty or result.iloc[0, 0] is None:
        return {
            'correlation': 0.0,
            'diagnosis': "No Data",
            'detail': "Insufficient data to detect divergence.",
            'dates': []
        }
        
    row = result.iloc[0]
    correlation = float(row['correlation'])
    
    if correlation > 0.7:
        diagnosis = "CVRs moving TOGETHER = MARKET PROBLEM"
        detail = "Both organic and paid CVR declining together indicates a product or market issue."
    elif correlation < 0.3:
        diagnosis = "CVRs moving INDEPENDENTLY = CHANNEL-SPECIFIC"
        detail = "Organic and paid CVR moving differently suggests channel-specific issues."
    else:
        diagnosis = "MIXED SIGNALS"
        detail = "Moderate correlation. Both market and channel factors may be at play."

    return {
        'correlation': correlation,
        'diagnosis': diagnosis,
        'detail': detail,
        'avg_organic_cvr': float(row['avg_organic_cvr']),
        'avg_paid_cvr': float(row['avg_paid_cvr']),
        'dates': row['dates'],
        'organic_values': row['organic_values'],
        'paid_values': row['paid_values']
    }


@st.cache_data(ttl=300, show_spinner=False)
def get_asin_action_table(days: int = 30, client_id: str = CLIENT_ID) -> pd.DataFrame:
    """Generate ASIN-level diagnostic table with recommendations."""
    account_id = _resolve_scoped_account_id(client_id)
    query = f"""
    WITH current_period AS (
        SELECT 
            st.child_asin,
            AVG(b.rank) as current_bsr,
            SUM(st.ordered_revenue) as current_organic_rev,
            AVG(st.unit_session_percentage) as current_organic_cvr
        FROM sc_raw.sales_traffic st
        LEFT JOIN sc_raw.bsr_history b 
            ON st.child_asin = b.asin 
            AND st.report_date = b.report_date
            AND b.account_id = '{account_id}'
        WHERE st.report_date >= CURRENT_DATE - {days}
        AND st.marketplace_id = '{MARKETPLACE_ID}'
        AND st.account_id = '{account_id}'
        GROUP BY st.child_asin
    ),
    prior_period AS (
        SELECT 
            st.child_asin,
            AVG(b.rank) as prior_bsr,
            SUM(st.ordered_revenue) as prior_organic_rev
        FROM sc_raw.sales_traffic st
        LEFT JOIN sc_raw.bsr_history b 
            ON st.child_asin = b.asin 
            AND st.report_date = b.report_date
            AND b.account_id = '{account_id}'
        WHERE st.report_date BETWEEN CURRENT_DATE - {days*2} AND CURRENT_DATE - {days} - 1
        AND st.marketplace_id = '{MARKETPLACE_ID}'
        AND st.account_id = '{account_id}'
        GROUP BY st.child_asin
    )
    SELECT 
        c.child_asin,
        c.current_bsr,
        c.current_bsr - p.prior_bsr as bsr_change,
        CASE WHEN p.prior_bsr = 0 THEN 0 ELSE (c.current_bsr - p.prior_bsr) / p.prior_bsr * 100 END as bsr_change_pct,
        c.current_organic_rev,
        CASE WHEN p.prior_organic_rev = 0 THEN 0 ELSE (c.current_organic_rev - p.prior_organic_rev) / p.prior_organic_rev * 100 END as organic_rev_change_pct,
        c.current_organic_cvr,
        NULL::NUMERIC as paid_roas,
        (COALESCE(p.prior_organic_rev, 0) - COALESCE(c.current_organic_rev, 0)) * 30 / {days} as monthly_impact
    FROM current_period c
    JOIN prior_period p ON c.child_asin = p.child_asin
    WHERE c.current_organic_rev > 100
    ORDER BY monthly_impact DESC
    LIMIT 20
    """
    
    return _read_sql(query)


@st.cache_data(ttl=300, show_spinner=False)
def get_session_trend(days: int = 30, client_id: str = CLIENT_ID) -> float:
    """Get period-over-period sessions trend percent."""
    account_id = _resolve_scoped_account_id(client_id)
    anchor_date = get_analysis_anchor_date(client_id=client_id)
    current_start = anchor_date - timedelta(days=days - 1)
    prior_start = current_start - timedelta(days=days)
    prior_end = current_start - timedelta(days=1)
    query = f"""
    WITH current AS (
        SELECT SUM(total_sessions) AS sessions
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{current_start}' AND '{anchor_date}'
          AND marketplace_id = '{MARKETPLACE_ID}'
          AND account_id = '{account_id}'
    ),
    prior AS (
        SELECT SUM(total_sessions) AS sessions
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{prior_start}' AND '{prior_end}'
          AND marketplace_id = '{MARKETPLACE_ID}'
          AND account_id = '{account_id}'
    )
    SELECT
      CASE
        WHEN COALESCE(prior.sessions, 0) = 0 THEN 0
        ELSE ((COALESCE(current.sessions, 0) - prior.sessions) / prior.sessions) * 100
      END AS pct
    FROM current, prior
    """
    result = _read_sql(query)
    if result.empty or result.iloc[0, 0] is None:
        return 0.0
    return float(result.iloc[0, 0])


@st.cache_data(ttl=300, show_spinner=False)
def get_cvr_trend(days: int = 30, client_id: str = CLIENT_ID) -> float:
    """Get period-over-period organic conversion rate trend percent."""
    account_id = _resolve_scoped_account_id(client_id)
    anchor_date = get_analysis_anchor_date(client_id=client_id)
    current_start = anchor_date - timedelta(days=days - 1)
    prior_start = current_start - timedelta(days=days)
    prior_end = current_start - timedelta(days=1)
    query = f"""
    WITH current AS (
        SELECT AVG(unit_session_percentage) AS cvr
        FROM sc_raw.sales_traffic
        WHERE report_date BETWEEN '{current_start}' AND '{anchor_date}'
          AND marketplace_id = '{MARKETPLACE_ID}'
          AND account_id = '{account_id}'
    ),
    prior AS (
        SELECT AVG(unit_session_percentage) AS cvr
        FROM sc_raw.sales_traffic
        WHERE report_date BETWEEN '{prior_start}' AND '{prior_end}'
          AND marketplace_id = '{MARKETPLACE_ID}'
          AND account_id = '{account_id}'
    )
    SELECT
      CASE
        WHEN COALESCE(prior.cvr, 0) = 0 THEN 0
        ELSE ((COALESCE(current.cvr, 0) - prior.cvr) / prior.cvr) * 100
      END AS pct
    FROM current, prior
    """
    result = _read_sql(query)
    if result.empty or result.iloc[0, 0] is None:
        return 0.0
    return float(result.iloc[0, 0])


def generate_primary_diagnosis(
    health: Dict[str, Any],
    days: int = 30,
    client_id: str = CLIENT_ID,
) -> Dict[str, Any]:
    """Generate data-driven primary diagnosis from volume + quality metrics."""
    session_trend = get_session_trend(days, client_id=client_id)
    cvr_trend = get_cvr_trend(days, client_id=client_id)
    roas_trend = float(health.get("tacos_change", 0) or 0) * -1

    if session_trend < -10 and abs(cvr_trend) < 3 and roas_trend < -15:
        return {
            "label": "Spend Mismanagement",
            "statement": (
                f"Traffic declined {abs(session_trend):.0f}% while conversion held steady "
                f"({cvr_trend:+.1f}%), but TACOS rose {abs(health.get('tacos_change', 0)):.1f}pts. "
                "Spend did not adjust with demand."
            ),
            "severity": "high",
            "type": "spend-mismanagement",
            "recommended_spend_cut": abs(session_trend),
        }
    if session_trend < -10 and abs(cvr_trend) < 3:
        return {
            "label": "Demand Softness",
            "statement": (
                f"Traffic declined {abs(session_trend):.0f}% while conversion held steady "
                f"({cvr_trend:+.1f}%). This is a volume problem, not quality."
            ),
            "severity": "high",
            "type": "volume",
        }
    if abs(session_trend) < 5 and cvr_trend < -10:
        return {
            "label": "Efficiency Loss",
            "statement": (
                f"Traffic is stable ({session_trend:+.0f}%) while conversion fell {abs(cvr_trend):.0f}% "
                f"and TACOS moved {health.get('tacos_change', 0):+.1f}pts."
            ),
            "severity": "high",
            "type": "efficiency",
        }
    if session_trend < -10 and cvr_trend < -10:
        return {
            "label": "Volume + Efficiency Decline",
            "statement": (
                f"Traffic is down {abs(session_trend):.0f}% and conversion is down {abs(cvr_trend):.0f}%. "
                "Both quantity and quality are deteriorating."
            ),
            "severity": "critical",
            "type": "both",
        }
    if session_trend > 10 and cvr_trend < -10:
        return {
            "label": "Growth Headwinds",
            "statement": (
                f"Traffic is up {session_trend:.0f}% but conversion is down {abs(cvr_trend):.0f}%. "
                "Scale is growing at lower intent."
            ),
            "severity": "medium",
            "type": "scale-quality-tradeoff",
        }
    if session_trend > 5 and cvr_trend > 5:
        return {
            "label": "Strong Growth",
            "statement": (
                f"Traffic is up {session_trend:.0f}% and conversion is up {cvr_trend:.0f}%. "
                "Growth is healthy across both axes."
            ),
            "severity": "positive",
            "type": "both-positive",
        }
    if session_trend < -10 and cvr_trend > 5:
        return {
            "label": "Efficiency Without Growth",
            "statement": (
                f"Traffic fell {abs(session_trend):.0f}% while conversion improved {cvr_trend:.0f}%. "
                "Optimization is improving quality but cutting too much volume."
            ),
            "severity": "medium",
            "type": "over-optimization",
        }
    return {
        "label": "Mixed Signals",
        "statement": (
            f"Traffic {session_trend:+.0f}%, CVR {cvr_trend:+.0f}%, "
            f"TACOS {health.get('tacos_change', 0):+.1f}pts."
        ),
        "severity": "medium",
        "type": "mixed",
    }


def _trend_percent(series: List[float], edge: int = 7) -> float:
    values = [float(v or 0) for v in series]
    if len(values) < (edge * 2):
        return 0.0
    first = float(np.mean(values[:edge]))
    last = float(np.mean(values[-edge:]))
    if first == 0:
        return 0.0
    return ((last - first) / first) * 100


def _coerce_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        return value.date()
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except Exception:
        return None


def _resolve_common_commerce_end_date(client_id: str) -> Optional[date]:
    """
    Resolve the latest available date in SP-API account_daily for the active scope.
    """
    scope = _resolve_scoped_account_context(client_id)
    account_id = scope["account_id"]
    marketplace_id = scope["marketplace_id"]
    query = f"""
    WITH max_dates AS (
      SELECT
        (SELECT MAX(report_date) FROM sc_analytics.account_daily
         WHERE marketplace_id = '{marketplace_id}'
           AND account_id = '{account_id}') AS account_daily_max_date
    )
    SELECT account_daily_max_date
    FROM max_dates
    """
    result = _read_sql(query)
    if result.empty:
        return None
    return _coerce_date(result.iloc[0].get("account_daily_max_date"))


@st.cache_data(ttl=300, show_spinner=False)
def get_revenue_breakdown(
    days: int = 90,
    client_id: str = CLIENT_ID,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Get paid vs organic revenue trend and interpretation.

    Organic revenue uses SP-API raw sales traffic (ordered_revenue).
    Paid revenue uses raw STR sales.
    This keeps organic trend visible even when paid attribution ingestion lags.
    """
    scope = _resolve_scoped_account_context(client_id)
    account_id = scope["account_id"]
    marketplace_id = scope["marketplace_id"]
    max_dates_q = f"""
    SELECT
      (SELECT MAX(report_date) FROM sc_raw.sales_traffic
       WHERE marketplace_id = '{marketplace_id}'
         AND account_id = '{account_id}') AS organic_max_date,
      (SELECT MAX(report_date) FROM public.raw_search_term_data
       WHERE client_id = '{client_id}') AS paid_max_date
    """
    max_dates_df = _read_sql(max_dates_q)
    organic_max = _coerce_date(max_dates_df.iloc[0].get("organic_max_date")) if not max_dates_df.empty else None
    paid_max = _coerce_date(max_dates_df.iloc[0].get("paid_max_date")) if not max_dates_df.empty else None
    natural_end = organic_max or paid_max or (date.today() - timedelta(days=1))
    if paid_max and organic_max:
        natural_end = max(organic_max, paid_max)

    resolved_end = end_date or natural_end
    resolved_start = start_date or (resolved_end - timedelta(days=days - 1))
    if resolved_start > resolved_end:
        return {"dates": [], "paid_revenue": [], "organic_revenue": [], "diagnosis": "Invalid date range."}

    organic_q = f"""
    SELECT
      report_date,
      SUM(COALESCE(ordered_revenue, 0)) AS organic_revenue
    FROM sc_raw.sales_traffic
    WHERE report_date BETWEEN '{resolved_start}' AND '{resolved_end}'
      AND marketplace_id = '{marketplace_id}'
      AND account_id = '{account_id}'
    GROUP BY report_date
    ORDER BY report_date
    """
    paid_q = f"""
    SELECT
      report_date,
      SUM(COALESCE(sales, 0)) AS paid_revenue
    FROM public.raw_search_term_data
    WHERE report_date BETWEEN '{resolved_start}' AND '{resolved_end}'
      AND client_id = '{client_id}'
    GROUP BY report_date
    ORDER BY report_date
    """
    organic_df = _read_sql(organic_q)
    paid_df = _read_sql(paid_q)

    # Fallback for environments where sales_traffic has not been populated yet.
    if organic_df.empty:
        organic_fallback_q = f"""
        SELECT
          report_date,
          SUM(
            CASE
              WHEN COALESCE(organic_revenue, 0) > 0 THEN COALESCE(organic_revenue, 0)
              ELSE GREATEST(COALESCE(total_ordered_revenue, 0) - COALESCE(ad_attributed_revenue, 0), 0)
            END
          ) AS organic_revenue
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{resolved_start}' AND '{resolved_end}'
          AND marketplace_id = '{marketplace_id}'
          AND account_id = '{account_id}'
        GROUP BY report_date
        ORDER BY report_date
        """
        organic_df = _read_sql(organic_fallback_q)

    if organic_df.empty and paid_df.empty:
        return {"dates": [], "paid_revenue": [], "organic_revenue": [], "diagnosis": "Insufficient data."}

    if organic_df.empty:
        organic_df = pd.DataFrame(columns=["report_date", "organic_revenue"])
    else:
        organic_df["report_date"] = pd.to_datetime(organic_df["report_date"], errors="coerce")
        organic_df["organic_revenue"] = pd.to_numeric(organic_df["organic_revenue"], errors="coerce").fillna(0.0)

    if paid_df.empty:
        paid_df = pd.DataFrame(columns=["report_date", "paid_revenue"])
    else:
        paid_df["report_date"] = pd.to_datetime(paid_df["report_date"], errors="coerce")
        paid_df["paid_revenue"] = pd.to_numeric(paid_df["paid_revenue"], errors="coerce").fillna(0.0)

    df = paid_df.merge(organic_df, on="report_date", how="outer").sort_values("report_date")
    if df.empty:
        return {"dates": [], "paid_revenue": [], "organic_revenue": [], "diagnosis": "Insufficient data."}

    df["paid_revenue"] = pd.to_numeric(df["paid_revenue"], errors="coerce").fillna(0.0)
    df["organic_revenue"] = pd.to_numeric(df["organic_revenue"], errors="coerce").fillna(0.0)

    # Remove edge-only zero rows so charts do not imply a sharp "drop to zero"
    # just because trailing days are unreported or still settling.
    non_zero_mask = (df["paid_revenue"] > 0) | (df["organic_revenue"] > 0)
    if non_zero_mask.any():
        first_idx = non_zero_mask.idxmax()
        last_idx = non_zero_mask.iloc[::-1].idxmax()
        df = df.loc[first_idx:last_idx].copy()

    paid = [float(v or 0) for v in df["paid_revenue"].tolist()]
    organic = [float(v or 0) for v in df["organic_revenue"].tolist()]
    paid_trend = _trend_percent(paid, edge=7)
    organic_trend = _trend_percent(organic, edge=7)

    if abs(paid_trend) < 5 and organic_trend < -10:
        diagnosis = "Organic is declining while paid is stable."
    elif paid_trend < -10 and abs(organic_trend) < 5:
        diagnosis = "Paid is declining while organic is stable."
    elif paid_trend < -10 and organic_trend < -10:
        diagnosis = "Both paid and organic are declining."
    else:
        diagnosis = "Revenue mix is mixed; verify channel-level trends."

    return {
        "dates": df["report_date"].dt.date.tolist(),
        "paid_revenue": paid,
        "organic_revenue": organic,
        "paid_trend_pct": paid_trend,
        "organic_trend_pct": organic_trend,
        "days_requested": days,
        "days_available": int(len(df)),
        "window_start": resolved_start.isoformat(),
        "window_end": resolved_end.isoformat(),
        "diagnosis": diagnosis,
        "as_of_date": resolved_end.isoformat(),
    }


@st.cache_data(ttl=300, show_spinner=False)
def get_bsr_trend(days: int = 90, client_id: str = CLIENT_ID) -> Dict[str, Any]:
    """Get BSR trend with rank-improvement-aware interpretation."""
    scope = _resolve_scoped_account_context(client_id)
    account_id = scope["account_id"]
    marketplace_id = scope["marketplace_id"]
    anchor_date = get_analysis_anchor_date(client_id=client_id)
    start_date = anchor_date - timedelta(days=days - 1)
    query = f"""
    SELECT
      report_date,
      AVG(rank) AS avg_rank
    FROM sc_raw.bsr_history
    WHERE report_date BETWEEN '{start_date}' AND '{anchor_date}'
      AND account_id = '{account_id}'
    GROUP BY report_date
    ORDER BY report_date
    """
    df = _read_sql(query)
    if df.empty:
        return {"dates": [], "ranks": [], "rank_change_pct": 0.0, "diagnosis": "Insufficient data.", "status": "neutral"}

    ranks = [float(v or 0) for v in df["avg_rank"].tolist()]
    rank_change_pct = _trend_percent(ranks, edge=7)
    if rank_change_pct < -10:
        diagnosis = "Rank improving. Organic visibility is strengthening."
        status = "positive"
    elif rank_change_pct > 10:
        diagnosis = "Rank declining. Organic visibility is weakening."
        status = "negative"
    else:
        diagnosis = "Rank is stable."
        status = "neutral"

    return {
        "dates": df["report_date"].tolist(),
        "ranks": ranks,
        "rank_change_pct": rank_change_pct,
        "diagnosis": diagnosis,
        "status": status,
        "as_of_date": anchor_date.isoformat(),
    }


@st.cache_data(ttl=300, show_spinner=False)
def get_bsr_traffic_overlay(
    days: int = 90,
    client_id: str = CLIENT_ID,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Build dual-axis dataset:
    - Stacked traffic (organic + paid proxy)
    - BSR on secondary axis (provided separately by get_bsr_trend)
    """
    account_id = _resolve_scoped_account_id(client_id)
    common_end = _resolve_common_commerce_end_date(client_id)
    resolved_end = end_date or common_end or (date.today() - timedelta(days=1))
    if common_end and resolved_end > common_end:
        resolved_end = common_end
    resolved_start = start_date or (resolved_end - timedelta(days=days - 1))
    if resolved_start > resolved_end:
        return {
            "dates": [],
            "organic_traffic": [],
            "paid_traffic": [],
            "organic_trend_pct": 0.0,
            "paid_trend_pct": 0.0,
            "diagnosis": "Invalid date range.",
            "as_of_date": resolved_end.isoformat(),
        }

    query = f"""
    WITH daily_sessions AS (
      SELECT
        report_date,
        COALESCE(SUM(total_sessions), 0) AS total_sessions
      FROM sc_analytics.account_daily
      WHERE report_date BETWEEN '{resolved_start}' AND '{resolved_end}'
        AND marketplace_id = '{marketplace_id}'
        AND account_id = '{account_id}'
      GROUP BY report_date
    ),
    paid_clicks AS (
      SELECT
        report_date,
        COALESCE(SUM(clicks), 0) AS paid_traffic
      FROM public.raw_search_term_data
      WHERE report_date BETWEEN '{resolved_start}' AND '{resolved_end}'
        AND client_id = '{client_id}'
      GROUP BY report_date
    )
    SELECT
      s.report_date,
      GREATEST(s.total_sessions - COALESCE(p.paid_traffic, 0), 0) AS organic_traffic,
      COALESCE(p.paid_traffic, 0) AS paid_traffic
    FROM daily_sessions s
    LEFT JOIN paid_clicks p USING (report_date)
    ORDER BY s.report_date
    """
    df = _read_sql(query)
    if df.empty:
        return {
            "dates": [],
            "organic_traffic": [],
            "paid_traffic": [],
            "organic_trend_pct": 0.0,
            "paid_trend_pct": 0.0,
            "diagnosis": "Insufficient traffic data.",
            "as_of_date": resolved_end.isoformat(),
        }

    organic = [float(v or 0) for v in df["organic_traffic"].tolist()]
    paid = [float(v or 0) for v in df["paid_traffic"].tolist()]
    organic_trend = _trend_percent(organic, edge=7)
    paid_trend = _trend_percent(paid, edge=7)

    if organic_trend < -10 and paid_trend > 5:
        diagnosis = "Organic traffic is weakening while paid traffic increases."
    elif organic_trend > 5 and paid_trend < -5:
        diagnosis = "Organic traffic is strengthening while paid traffic contracts."
    else:
        diagnosis = "Traffic mix is balanced; review BSR overlay for rank context."

    return {
        "dates": df["report_date"].tolist(),
        "organic_traffic": organic,
        "paid_traffic": paid,
        "organic_trend_pct": organic_trend,
        "paid_trend_pct": paid_trend,
        "days_requested": days,
        "days_available": int(len(df)),
        "window_start": resolved_start.isoformat(),
        "window_end": resolved_end.isoformat(),
        "diagnosis": diagnosis,
        "as_of_date": resolved_end.isoformat(),
    }


@st.cache_data(ttl=300, show_spinner=False)
def get_optimization_performance(
    days: int = 30,
    client_id: str = CLIENT_ID,
    validated_only: bool = True,
) -> Dict[str, Any]:
    """Get action validation performance aligned with Impact dashboard metrics."""
    anchor_date = get_analysis_anchor_date(client_id=client_id)
    start_date = anchor_date - timedelta(days=days - 1)
    total_query = f"""
    SELECT COUNT(*)
    FROM public.actions_log
    WHERE action_date BETWEEN '{start_date}' AND '{anchor_date}'
      AND client_id = '{client_id}'
    """
    total_rows = _read_sql(total_query)
    total_actions = int(total_rows.iloc[0, 0]) if not total_rows.empty and total_rows.iloc[0, 0] is not None else 0

    summary = get_recent_validation_summary(client_id=client_id, days=days, validated_only=validated_only)
    validated_count = int(summary.get("total_actions", 0) or 0)
    validation_rate = (validated_count / total_actions * 100) if total_actions > 0 else 0.0
    win_rate = float(summary.get("win_rate", 0) or 0)
    avg_impact = float(summary.get("avg_impact", 0) or 0)
    winners = int(summary.get("winners", 0) or 0)
    losers = int(summary.get("losers", 0) or 0)
    pending = max(total_actions - validated_count, 0)

    if win_rate > 70:
        diagnosis = f"Optimizations are working. Win rate is {win_rate:.0f}%."
        status = "positive"
    elif win_rate > 50:
        diagnosis = f"Optimizations are mixed. Win rate is {win_rate:.0f}%."
        status = "neutral"
    else:
        diagnosis = f"Optimizations are underperforming. Win rate is {win_rate:.0f}%."
        status = "negative"

    return {
        "total_actions": total_actions,
        "validated_actions": validated_count,
        "validation_rate": validation_rate,
        "win_rate": win_rate,
        "avg_impact": avg_impact,
        "wins": winners,
        "losses": losers,
        "pending": pending,
        "diagnosis": diagnosis,
        "status": status,
        "as_of_date": anchor_date.isoformat(),
    }


@st.cache_data(ttl=300, show_spinner=False)
def identify_brutal_underperformers(days: int = 30, limit: int = 10, client_id: str = CLIENT_ID) -> List[Dict[str, Any]]:
    """Identify volume-aware underperforming campaigns."""
    anchor_date = get_analysis_anchor_date(client_id=client_id)
    start_date = anchor_date - timedelta(days=days - 1)
    query = f"""
    WITH campaign_performance AS (
      SELECT
        campaign_name,
        SUM(spend) AS total_spend,
        SUM(sales) AS total_sales,
        SUM(sales) / NULLIF(SUM(spend), 0) AS roas
      FROM public.raw_search_term_data
      WHERE report_date BETWEEN '{start_date}' AND '{anchor_date}'
        AND client_id = '{client_id}'
      GROUP BY campaign_name
      HAVING SUM(spend) > 100
    )
    SELECT
      campaign_name,
      total_spend,
      total_sales,
      roas,
      CASE
        WHEN roas < 2.5 THEN total_spend - (total_sales / 2.5)
        ELSE 0
      END AS estimated_waste,
      CASE
        WHEN roas < 1.0 AND total_sales < 500 THEN 'CUT'
        WHEN roas < 1.5 AND total_sales > 2000 THEN 'REVIEW'
        WHEN roas < 1.5 THEN 'CUT'
        WHEN roas < 2.0 THEN 'REVIEW'
        ELSE 'HEALTHY'
      END AS severity
    FROM campaign_performance
    WHERE (roas < 1.5 AND total_sales < 2000) OR roas < 1.0
    ORDER BY total_spend DESC
    LIMIT {limit}
    """
    df = _read_sql(query)
    if df.empty:
        return []
    records = []
    for _, row in df.iterrows():
        records.append(
            {
                "campaign": row["campaign_name"],
                "spend": float(row["total_spend"] or 0),
                "sales": float(row["total_sales"] or 0),
                "roas": float(row["roas"] or 0),
                "waste": float(row["estimated_waste"] or 0),
                "severity": row["severity"],
            }
        )
    return records


def generate_multi_dimensional_actions(
    diagnosis: Dict[str, Any],
    health: Dict[str, Any],
    days: int = 30,
    client_id: str = CLIENT_ID,
) -> Dict[str, List[Dict[str, Any]]]:
    """Generate strategic, campaign, listing, and budget actions."""
    actions: Dict[str, List[Dict[str, Any]]] = {
        "strategic": [],
        "campaign_optimizations": [],
        "product_listing": [],
        "budget_pacing": [],
    }
    primary_type = diagnosis.get("type")

    if primary_type == "volume":
        traffic_drop = abs(get_session_trend(days, client_id=client_id))
        actions["strategic"] = [
            {"text": f"Contract discovery spend by {traffic_drop:.0f}%", "reason": "Demand volume is down."},
            {"text": "Preserve TACOS until demand stabilizes", "reason": "Prioritize efficiency in softer demand."},
        ]
    elif primary_type == "efficiency":
        actions["strategic"] = [
            {"text": "Audit traffic quality by campaign type", "reason": "Traffic quality is likely degraded."},
            {"text": "Tighten broad match expansion", "reason": "Reduce low-intent query exposure."},
        ]
    elif primary_type == "both-positive":
        actions["strategic"] = [
            {"text": "Scale budgets by 20-25%", "reason": "Both volume and quality are improving."},
            {"text": "Expand proven campaign templates", "reason": "Capitalize while trend is favorable."},
        ]
    else:
        actions["strategic"] = [
            {"text": "Hold baseline budgets and monitor daily", "reason": "Signals are mixed; avoid overreaction."},
        ]

    actions["campaign_optimizations"] = identify_brutal_underperformers(days=days, client_id=client_id)
    cvr = detect_cvr_divergence(days=days, client_id=client_id)
    if float(cvr.get("correlation", 0) or 0) > 0.7:
        actions["product_listing"] = [
            {"text": "Audit images and main title on top ASINs", "reason": "Channel CVRs are moving together."},
            {"text": "Run price-position check vs key competitors", "reason": "Likely market/product-driven conversion pressure."},
        ]
    else:
        actions["product_listing"] = [
            {"text": "Review paid query-to-ASIN relevance", "reason": "Channel-specific issue likely."},
        ]

    if float(health.get("tacos_change", 0) or 0) > 3:
        actions["budget_pacing"] = [
            {"text": "Apply stricter daily caps on auto campaigns", "reason": "TACOS has risen materially."},
            {"text": "Prioritize dayparts with higher CVR", "reason": "Concentrate spend in better-converting windows."},
        ]
    else:
        actions["budget_pacing"] = [
            {"text": "Maintain pacing and protect top campaigns", "reason": "No major overspend signal detected."},
        ]
    return actions
