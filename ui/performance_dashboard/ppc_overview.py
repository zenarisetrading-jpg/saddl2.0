"""
PPC Overview Tab — SADDL AdPulse Performance Dashboard

Streamlit implementation of the PPC Overview module.
Design reference: React PPCModule component.
Styling follows business_overview.py conventions.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import streamlit as st
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any


# ===========================================================================
# EXECUTIVE DASHBOARD BRIDGE  (reuse existing chart methods)
# ===========================================================================

def _to_exec_df(cur_df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename snake_case PPC columns to title-case aliases expected by
    ExecutiveDashboard chart methods (_render_performance_scatter,
    _render_spend_breakdown, etc.).
    Also derives 'Refined Match Type' display names.
    """
    df = cur_df.rename(columns={
        "start_date":    "Date",
        "campaign_name": "Campaign Name",
        "ad_group_name": "Ad Group Name",
        "target_text":   "Targeting",
        "match_type":    "Match Type",
        "spend":         "Spend",
        "sales":         "Sales",
        "clicks":        "Clicks",
        "impressions":   "Impressions",
        "orders":        "Orders",
    })
    _mt_map = {
        "EXACT": "Exact", "BROAD": "Broad", "PHRASE": "Phrase",
        "AUTO": "Auto", "PT": "PT", "CATEGORY": "Category",
    }
    if "Match Type" in df.columns:
        df["Refined Match Type"] = df["Match Type"].apply(
            lambda x: _mt_map.get(str(x).upper(), str(x).title()) if pd.notna(x) else "Other"
        )
    return df


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_exec_data(client_id: str, test_mode: bool, start_date, end_date):
    """
    Cached wrapper around ExecutiveDashboard._fetch_data().
    Returns the full exec_data dict (canonical_metrics, impact_df, df_current …)
    or None on failure.
    """
    try:
        from features.executive_dashboard import ExecutiveDashboard
        exec_dash = ExecutiveDashboard()
        return exec_dash._fetch_data(custom_start=start_date, custom_end=end_date)
    except Exception:
        return None


# ===========================================================================
# GUARDRAILS  (PRD 6.1)
# ===========================================================================

def _safe_div(n: float, d: float) -> float:
    """Safe division — returns 0 on zero/NaN denominator."""
    if not d or pd.isna(d) or pd.isna(n):
        return 0.0
    return n / d


def _fmt_currency(v) -> str:
    if v is None or (isinstance(v, float) and (pd.isna(v) or np.isnan(v))):
        return "N/A"
    return f"${v:,.2f}"


def _fmt_roas(v) -> str:
    if v is None or (isinstance(v, float) and (pd.isna(v) or np.isnan(v))):
        return "0.00×"
    return f"{min(float(v), 99.9):.2f}×"


def _fmt_pct(v) -> str:
    if v is None or (isinstance(v, float) and (pd.isna(v) or np.isnan(v))):
        return "N/A"
    return f"{float(v) * 100:.2f}%"


def _fmt_number(v) -> str:
    if v is None or (isinstance(v, float) and (pd.isna(v) or np.isnan(v))):
        return "N/A"
    return f"{int(v):,}"


from features.optimizer_shared.ppc_classifications import classify_keyword_diagnostic as _classify_keyword_shared


def _classify_keyword(row: pd.Series, target_roas: float) -> str:
    """Flag keywords by diagnostic category. Logic lives in ppc_classifications.py."""
    _LABEL_MAP = {
        "zero_conversion": "Zero-Conversion",
        "under_bid":       "Under-Bidding",
        "over_spend":      "Over-Spending",
        "optimized":       "Optimized",
    }
    key = _classify_keyword_shared(
        spend=row["spend"],
        sales=row["sales"],
        roas=row["roas"],
        target_roas=target_roas,
        clicks=int(row.get("clicks", 0) or 0),
        impressions=int(row.get("impressions", 0) or 0),
    )
    return _LABEL_MAP.get(key, "Optimized")


# ===========================================================================
# THEME
# ===========================================================================

def _inject_ppc_theme() -> None:
    """Inject CSS matching the business_overview.py dark palette."""
    st.markdown(
        """
        <style>
        /* ── PPC Overview Cards ── */
        .ppc-health-card {
            position: relative;
            border-radius: 14px;
            border: 1px solid rgba(55,65,81,0.9);
            background: rgba(17,24,39,0.92);
            padding: 16px 16px 14px 16px;
            min-height: 118px;
            overflow: hidden;
            box-shadow: 0 14px 30px rgba(0,0,0,0.25);
            margin-bottom: 4px;
        }
        .ppc-health-label {
            color: #9CA3AF;
            text-transform: uppercase;
            font-weight: 700;
            font-size: 10px;
            letter-spacing: .09em;
            margin-bottom: 6px;
        }
        .ppc-health-value {
            color: #FFFFFF;
            font-weight: 800;
            font-size: 28px;
            line-height: 1.05;
            letter-spacing: -0.02em;
            margin-bottom: 6px;
        }
        .ppc-trend-badge {
            display: inline-block;
            font-size: 10px;
            font-weight: 700;
            border-radius: 8px;
            padding: 3px 7px;
            margin-top: 2px;
        }
        .ppc-trend-up-good   { color:#34D399; background:rgba(16,185,129,0.15); }
        .ppc-trend-up-bad    { color:#FB7185; background:rgba(244,63,94,0.15); }
        .ppc-trend-down-good { color:#34D399; background:rgba(16,185,129,0.15); }
        .ppc-trend-down-bad  { color:#FB7185; background:rgba(244,63,94,0.15); }
        .ppc-trend-flat      { color:#9CA3AF; background:rgba(156,163,175,0.10); }

        /* ── Section Headers ── */
        .ppc-section {
            margin-top: 18px;
            margin-bottom: 10px;
            border-bottom: 1px solid rgba(75,85,99,0.55);
            padding-bottom: 8px;
        }
        .ppc-section h3 {
            margin: 0;
            color: #F3F4F6;
            font-size: 18px;
            font-weight: 700;
            letter-spacing: -0.01em;
        }
        .ppc-section p {
            margin: 3px 0 0 0;
            color: #9CA3AF;
            font-size: 12px;
        }

        /* ── Table Wrapper ── */
        .ppc-table-wrap {
            border: 1px solid rgba(55,65,81,0.9);
            border-radius: 12px;
            overflow: hidden;
            background: rgba(17,24,39,0.92);
            box-shadow: 0 14px 30px rgba(0,0,0,0.25);
        }
        .ppc-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .ppc-table thead {
            background: rgba(3,7,18,0.55);
        }
        .ppc-table th {
            text-transform: uppercase;
            color: #9CA3AF;
            letter-spacing: .06em;
            font-size: 11px;
            padding: 11px 10px;
            border-bottom: 1px solid rgba(55,65,81,0.8);
            font-weight: 600;
        }
        .ppc-table th:first-child, .ppc-table td:first-child {
            text-align: left;
            padding-left: 16px;
        }
        .ppc-table td {
            color: #D1D5DB;
            padding: 11px 10px;
            border-bottom: 1px solid rgba(55,65,81,0.40);
            text-align: right;
            vertical-align: middle;
        }
        .ppc-table tr:last-child td { border-bottom: none; }
        .ppc-table tr:hover td { background: rgba(55,65,81,0.18); }

        /* ── ROAS Badges ── */
        .roas-green  { color:#34D399; background:rgba(16,185,129,0.12);  border:1px solid rgba(16,185,129,0.30);  border-radius:6px; padding:3px 8px; font-weight:700; font-size:12px; }
        .roas-amber  { color:#F59E0B; background:rgba(245,158,11,0.12);  border:1px solid rgba(245,158,11,0.30);  border-radius:6px; padding:3px 8px; font-weight:700; font-size:12px; }
        .roas-red    { color:#FB7185; background:rgba(244,63,94,0.12);   border:1px solid rgba(244,63,94,0.30);   border-radius:6px; padding:3px 8px; font-weight:700; font-size:12px; }

        /* ── Diagnostic Flag Chips ── */
        .flag-zero  { color:#F59E0B; background:rgba(245,158,11,0.12);  border:1px solid rgba(245,158,11,0.30);  border-radius:999px; padding:3px 9px; font-size:11px; font-weight:700; }
        .flag-over  { color:#FB7185; background:rgba(244,63,94,0.12);   border:1px solid rgba(244,63,94,0.30);   border-radius:999px; padding:3px 9px; font-size:11px; font-weight:700; }
        .flag-under { color:#818CF8; background:rgba(99,102,241,0.12);  border:1px solid rgba(99,102,241,0.30);  border-radius:999px; padding:3px 9px; font-size:11px; font-weight:700; }
        .flag-ok    { color:#6B7280; background:transparent;             border:1px solid rgba(107,114,128,0.20); border-radius:999px; padding:3px 9px; font-size:11px; font-weight:500; }

        /* ── Target ROAS Pill ── */
        .ppc-target-pill {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: rgba(99,102,241,0.10);
            border: 1px solid rgba(99,102,241,0.25);
            border-radius: 8px;
            padding: 4px 10px;
            font-size: 12px;
            color: #818CF8;
            font-weight: 600;
        }

        /* ── Empty State ── */
        .ppc-empty {
            border: 1px dashed rgba(55,65,81,0.7);
            border-radius: 12px;
            padding: 32px;
            text-align: center;
            color: #6B7280;
            font-size: 14px;
            background: rgba(17,24,39,0.50);
        }
        .ppc-empty-icon { font-size: 28px; margin-bottom: 8px; }

        /* ── Intelligence Log ── */
        .intel-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid rgba(55,65,81,0.40);
        }
        .intel-row:last-child { border-bottom: none; }
        .intel-date   { color: #6B7280; font-size: 11px; margin-bottom: 3px; }
        .intel-action { color: #E5E7EB; font-size: 13px; font-weight: 600; }
        .intel-count  { color: #818CF8; font-weight: 800; }
        .intel-roas-before { color: #9CA3AF; font-size: 12px; }
        .intel-roas-after-up   { color: #34D399; font-size: 12px; font-weight: 700; }
        .intel-roas-after-down { color: #FB7185; font-size: 12px; font-weight: 700; }
        .intel-pending {
            font-size: 11px; font-weight: 700;
            color: #F59E0B;
            background: rgba(245,158,11,0.10);
            border: 1px solid rgba(245,158,11,0.25);
            border-radius: 6px;
            padding: 3px 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ===========================================================================
# UI COMPONENTS
# ===========================================================================

# SVG icon library — all 20×20, fill="none", stroke-width="2", viewBox="0 0 24 24"
_ICONS: Dict[str, str] = {
    # Cyan bar-chart — PPC Health
    "health": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" '
        'stroke="#06B6D4" stroke-width="2" stroke-linecap="round">'
        '<line x1="18" y1="20" x2="18" y2="10"/>'
        '<line x1="12" y1="20" x2="12" y2="4"/>'
        '<line x1="6"  y1="20" x2="6"  y2="14"/>'
        '<line x1="2"  y1="20" x2="22" y2="20"/>'
        '</svg>'
    ),
    # Emerald table/grid — Campaign Performance
    "campaign": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" '
        'stroke="#10B981" stroke-width="2" stroke-linecap="round">'
        '<rect x="3" y="3" width="18" height="18" rx="2"/>'
        '<line x1="3" y1="9"  x2="21" y2="9"/>'
        '<line x1="3" y1="15" x2="21" y2="15"/>'
        '<line x1="9" y1="3"  x2="9"  y2="21"/>'
        '</svg>'
    ),
    # Indigo magnifying glass — Keyword Diagnostics
    "keyword": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" '
        'stroke="#818CF8" stroke-width="2" stroke-linecap="round">'
        '<circle cx="11" cy="11" r="8"/>'
        '<line x1="21" y1="21" x2="16.65" y2="16.65"/>'
        '</svg>'
    ),
    # Amber clock/history — Intelligence Log
    "intel": (
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" '
        'stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="12 8 12 12 14 14"/>'
        '<path d="M3.05 11a9 9 0 1 1 .5 4m-.5 5v-5h5"/>'
        '</svg>'
    ),
}


def _section_header(title: str, subtitle: str = "", icon: str = "") -> None:
    """
    Render a section header matching ExecutiveDashboard._chart_header() style:
    dark-gradient band, optional SVG icon left, title + subtitle.
    Uses .panel-header-content CSS (injected by ExecutiveDashboard.__init__).
    """
    svg = _ICONS.get(icon, "")
    sub = (
        f'<p style="color:#64748B;font-size:0.7rem;margin:2px 0 0 0">{subtitle}</p>'
        if subtitle else ""
    )
    st.markdown(
        f'<div class="panel-header-content" style="display:flex;align-items:center;gap:10px">'
        f'{svg}'
        f'<div><span style="font-size:1rem;color:#F5F5F7;font-weight:600">{title}</span>'
        f'{sub}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _health_card(title: str, value: str, delta: float, inverse: bool = False) -> str:
    """Return HTML for one KPI health card."""
    is_positive = delta > 0
    is_neutral = delta == 0

    if is_neutral:
        badge_cls = "ppc-trend-flat"
        arrow = "▶"
        pct = "Flat"
    else:
        is_good = (not inverse and is_positive) or (inverse and not is_positive)
        if is_good:
            badge_cls = "ppc-trend-up-good" if is_positive else "ppc-trend-down-good"
        else:
            badge_cls = "ppc-trend-up-bad" if is_positive else "ppc-trend-down-bad"
        arrow = "▲" if is_positive else "▼"
        pct = f"{arrow} {abs(delta):.1f}%"

    return f"""
    <div class="ppc-health-card">
        <div class="ppc-health-label">{title}</div>
        <div class="ppc-health-value">{value}</div>
        <span class="ppc-trend-badge {badge_cls}">{pct}</span>
    </div>
    """


def _empty_state(message: str = "No PPC data uploaded yet") -> None:
    st.markdown(
        f'<div class="ppc-empty">'
        f'<div class="ppc-empty-icon">📊</div>'
        f'<div>{message}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _roas_badge(roas: float, target: float) -> str:
    val = _fmt_roas(roas)
    if roas >= target:
        return f'<span class="roas-green">{val}</span>'
    elif roas >= target * 0.8:
        return f'<span class="roas-amber">{val}</span>'
    else:
        return f'<span class="roas-red">{val}</span>'


def _flag_chip(flag: str) -> str:
    map_ = {
        "Zero-Conversion": ('flag-zero', '⚠ Zero-Conv'),
        "Over-Spending":   ('flag-over',  '↘ Over-Spend'),
        "Under-Bidding":   ('flag-under', '↑ Under-Bid'),
        "Optimized":       ('flag-ok',    '✓ Optimized'),
    }
    cls, label = map_.get(flag, ('flag-ok', flag))
    return f'<span class="{cls}">{label}</span>'


# ===========================================================================
# DATA PROCESSING
# ===========================================================================

def _filter_by_date(df: pd.DataFrame, window_days: int) -> pd.DataFrame:
    """Return rows within window_days of the most recent date in df."""
    if df is None or df.empty:
        return df
    if "start_date" not in df.columns:
        return df
    df = df.copy()
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    cutoff = df["start_date"].max() - timedelta(days=window_days)
    return df[df["start_date"] >= cutoff]


def _build_stats(df: pd.DataFrame, prev_df: pd.DataFrame) -> Dict[str, Any]:
    """Aggregate totals and compute period-over-period deltas."""
    def _totals(d):
        if d is None or d.empty:
            return dict(spend=0, sales=0, impressions=0, clicks=0, orders=0)
        return dict(
            spend=d["spend"].sum(),
            sales=d["sales"].sum(),
            impressions=d["impressions"].sum() if "impressions" in d.columns else 0,
            clicks=d["clicks"].sum() if "clicks" in d.columns else 0,
            orders=d["orders"].sum() if "orders" in d.columns else 0,
        )

    cur = _totals(df)
    prv = _totals(prev_df)

    def _delta_pct(c, p):
        if not p:
            return 0.0
        return (c - p) / p * 100

    roas = _safe_div(cur["spend"] and cur["sales"], cur["spend"])
    acos = _safe_div(cur["spend"], cur["sales"])
    ctr  = _safe_div(cur["clicks"], cur["impressions"])
    cpc  = _safe_div(cur["spend"], cur["clicks"])

    p_roas = _safe_div(prv.get("sales", 0), prv.get("spend", 0) or 1)
    p_acos = _safe_div(prv.get("spend", 0), prv.get("sales", 0) or 1)
    p_ctr  = _safe_div(prv.get("clicks", 0), prv.get("impressions", 0) or 1)
    p_cpc  = _safe_div(prv.get("spend", 0), prv.get("clicks", 0) or 1)

    active_kw = len(df["target_text"].dropna().unique()) if (df is not None and not df.empty and "target_text" in df.columns) else 0

    return dict(
        spend=cur["spend"],
        roas=_safe_div(cur["sales"], cur["spend"]),
        acos=acos,
        impressions=cur["impressions"],
        clicks=cur["clicks"],
        ctr=ctr,
        cpc=cpc,
        active_keywords=active_kw,
        # deltas (pct change)
        d_spend=_delta_pct(cur["spend"], prv["spend"]),
        d_roas=_delta_pct(roas, p_roas),
        d_acos=_delta_pct(acos, p_acos),
        d_impressions=_delta_pct(cur["impressions"], prv["impressions"]),
        d_ctr=_delta_pct(ctr, p_ctr),
        d_cpc=_delta_pct(cpc, p_cpc),
    )


def _build_campaign_df(df: pd.DataFrame, target_roas: float) -> pd.DataFrame:
    """Aggregate target_stats to campaign level with computed metrics."""
    if df is None or df.empty:
        return pd.DataFrame()

    agg_cols = {"spend": "sum", "sales": "sum"}
    if "impressions" in df.columns:
        agg_cols["impressions"] = "sum"
    if "clicks" in df.columns:
        agg_cols["clicks"] = "sum"
    if "orders" in df.columns:
        agg_cols["orders"] = "sum"

    camp = df.groupby("campaign_name", as_index=False).agg(agg_cols)
    camp = camp[camp["spend"] > 0].copy()
    camp["roas"] = camp.apply(lambda r: _safe_div(r["sales"], r["spend"]), axis=1)
    camp["acos"] = camp.apply(lambda r: _safe_div(r["spend"], r["sales"]), axis=1)
    if "clicks" in camp.columns:
        camp["cpc"] = camp.apply(lambda r: _safe_div(r["spend"], r["clicks"]), axis=1)

    # Derive match group from campaign name suffix conventions
    def _group(name):
        n = str(name).upper()
        if "EXACT" in n:  return "Exact"
        if "BROAD" in n:  return "Broad"
        if "PHRASE" in n: return "Phrase"
        if "AUTO" in n:   return "Auto"
        if "PT" in n or "PRODUCT" in n: return "Product"
        return "Mixed"

    camp["group"] = camp["campaign_name"].apply(_group)
    return camp.sort_values("spend", ascending=False).reset_index(drop=True)


def _build_keyword_df(
    df: pd.DataFrame,
    target_roas: float,
    match_type_filter: str = "All",
) -> pd.DataFrame:
    """Aggregate to keyword level, classify diagnostics, apply match type filter."""
    if df is None or df.empty:
        return pd.DataFrame()

    group_cols = ["target_text"]
    if "match_type" in df.columns:
        group_cols.append("match_type")
    if "campaign_name" in df.columns:
        group_cols.append("campaign_name")

    agg_cols = {"spend": "sum", "sales": "sum"}
    if "impressions" in df.columns:
        agg_cols["impressions"] = "sum"
    if "clicks" in df.columns:
        agg_cols["clicks"] = "sum"
    if "orders" in df.columns:
        agg_cols["orders"] = "sum"

    kw = df.groupby(group_cols, as_index=False).agg(agg_cols)
    kw = kw[kw["spend"] > 0].copy()
    kw["roas"] = kw.apply(lambda r: _safe_div(r["sales"], r["spend"]), axis=1)

    # Apply match type filter
    if match_type_filter != "All" and "match_type" in kw.columns:
        kw = kw[kw["match_type"].str.upper() == match_type_filter.upper()]

    kw["flag"] = kw.apply(lambda r: _classify_keyword(r, target_roas), axis=1)
    return kw.sort_values("spend", ascending=False).head(20).reset_index(drop=True)


# ===========================================================================
# DATA FETCHING
# ===========================================================================

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_target_stats(client_id: str, test_mode: bool, start_date=None):
    from features.optimizer_shared.data_access import fetch_target_stats_cached
    return fetch_target_stats_cached(client_id, test_mode, start_date=start_date)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_actions(client_id: str, test_mode: bool, limit: int = 200):
    try:
        from app_core.db_manager import get_db_manager
        db = get_db_manager(test_mode)
        if db and client_id:
            return db.get_actions_by_client(client_id, limit=limit)
    except Exception:
        pass
    return []


# ===========================================================================
# SECTION RENDERERS
# ===========================================================================

def _render_health_strip(stats: Dict[str, Any]) -> None:
    cards = [
        ("Total Ad Spend",   _fmt_currency(stats["spend"]),          stats["d_spend"],       True),
        ("Blended ROAS",     _fmt_roas(stats["roas"]),                stats["d_roas"],        False),
        ("ACOS",             _fmt_pct(stats["acos"]),                 stats["d_acos"],        True),
        ("Impressions",      _fmt_number(stats["impressions"]),       stats["d_impressions"], False),
        ("CTR",              _fmt_pct(stats["ctr"]),                  stats["d_ctr"],         False),
        ("Avg. CPC",         _fmt_currency(stats["cpc"]),             stats["d_cpc"],         True),
    ]

    cols = st.columns(7)
    for idx, (title, value, delta, inverse) in enumerate(cards):
        with cols[idx]:
            st.markdown(_health_card(title, value, delta, inverse), unsafe_allow_html=True)

    # Active keywords gets its own styled card (no delta)
    with cols[6]:
        st.markdown(
            f"""
            <div class="ppc-health-card">
                <div class="ppc-health-label">Active Keywords</div>
                <div class="ppc-health-value">{_fmt_number(stats["active_keywords"])}</div>
                <span class="ppc-trend-badge ppc-trend-flat">Unique targets</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_campaign_table(
    campaign_df: pd.DataFrame,
    target_roas: float,
    max_rows: Optional[int] = 10,
) -> None:
    display_df = campaign_df.head(max_rows) if max_rows is not None else campaign_df
    if display_df.empty:
        _empty_state("No campaign data for this period")
        return

    # Build HTML table
    rows_html = ""
    for _, row in display_df.iterrows():
        cpc_val = _fmt_currency(row.get("cpc")) if "cpc" in row else "N/A"
        rows_html += f"""
        <tr>
            <td style="text-align:left">
                <div style="font-weight:600;color:#E5E7EB;font-size:13px">{row['campaign_name']}</div>
                <div style="font-size:11px;color:#6B7280">{row.get('group','')}</div>
            </td>
            <td>{_fmt_currency(row['spend'])}</td>
            <td style="color:#34D399">{_fmt_currency(row['sales'])}</td>
            <td>{_roas_badge(row['roas'], target_roas)}</td>
            <td>{_fmt_pct(row['acos'])}</td>
            <td style="color:#6B7280">{_fmt_number(row.get('impressions', 0))}</td>
            <td style="color:#6B7280">{cpc_val}</td>
        </tr>
        """

    legend = (
        '<span class="roas-green" style="font-size:11px">▶ Above Target</span> &nbsp;'
        '<span class="roas-amber" style="font-size:11px">▶ Within 20%</span> &nbsp;'
        '<span class="roas-red"   style="font-size:11px">▶ Below Target</span>'
    )

    st.markdown(
        f"""
        <div style="display:flex;justify-content:flex-end;margin-bottom:8px">{legend}</div>
        <div class="ppc-table-wrap">
        <table class="ppc-table">
            <thead>
                <tr>
                    <th>Campaign</th>
                    <th>Spend</th>
                    <th>Sales</th>
                    <th>ROAS</th>
                    <th>ACOS</th>
                    <th>Impressions</th>
                    <th>CPC</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_keyword_diagnostics(
    kw_df: pd.DataFrame,
    target_roas: float,
    max_rows: Optional[int] = 10,
) -> None:
    display_df = kw_df.head(max_rows) if max_rows is not None else kw_df
    if display_df.empty:
        _empty_state("No keyword data for this period")
        return

    rows_html = ""
    for _, row in display_df.iterrows():
        match_label = f"[{row['match_type']}]" if "match_type" in row and pd.notna(row.get("match_type")) else ""
        campaign = str(row.get("campaign_name", ""))[:48] + ("…" if len(str(row.get("campaign_name", ""))) > 48 else "")
        roas_str = f"{min(float(row['roas']), 99.9):.2f}×" if row["sales"] > 0 else "0.00×"

        rows_html += f"""
        <tr>
            <td style="text-align:left">
                <div style="font-weight:600;color:#E5E7EB;font-size:13px">{row['target_text']}</div>
                <div style="font-size:11px;color:#6B7280">{match_label}</div>
            </td>
            <td style="color:#9CA3AF;font-size:12px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{campaign}</td>
            <td>{_fmt_currency(row['spend'])}</td>
            <td style="color:#9CA3AF">{_fmt_currency(row['sales'])}</td>
            <td style="font-weight:600;color:#D1D5DB">{roas_str}</td>
            <td>{_flag_chip(row['flag'])}</td>
        </tr>
        """

    st.markdown(
        f"""
        <div class="ppc-table-wrap">
        <table class="ppc-table">
            <thead>
                <tr>
                    <th>Target Keyword</th>
                    <th>Campaign</th>
                    <th>Spend</th>
                    <th>Sales</th>
                    <th>ROAS</th>
                    <th style="text-align:center">Diagnostic Flag</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_intelligence_log(client_id: str, test_mode: bool) -> None:
    """Render SADDL Intelligence Log from optimizer action history."""
    actions = _fetch_actions(client_id, test_mode, limit=300)

    if not actions:
        _empty_state("No optimizer runs recorded yet")
        return

    # Group by date (day) to create "run" summaries
    df = pd.DataFrame(actions)
    if df.empty:
        _empty_state("No optimizer runs recorded yet")
        return

    df["action_date"] = pd.to_datetime(df["action_date"], errors="coerce")
    df["run_day"] = df["action_date"].dt.date

    runs = (
        df.groupby("run_day")
        .agg(
            action_count=("id", "count"),
            primary_type=("action_type", lambda s: s.value_counts().index[0] if len(s) else ""),
            last_time=("action_date", "max"),
        )
        .reset_index()
        .sort_values("run_day", ascending=False)
        .head(5)
    )

    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)

    rows_html = ""
    for _, run in runs.iterrows():
        day = run["run_day"]
        if day == today:
            date_label = f"Today, {run['last_time'].strftime('%I:%M %p') if pd.notna(run['last_time']) else ''}"
        elif day == yesterday:
            date_label = f"Yesterday, {run['last_time'].strftime('%I:%M %p') if pd.notna(run['last_time']) else ''}"
        else:
            date_label = str(day)

        action_type = str(run["primary_type"]).replace("_", " ").title()
        count = int(run["action_count"])

        rows_html += f"""
        <div class="intel-row">
            <div>
                <div class="intel-date">{date_label}</div>
                <div class="intel-action">
                    <span class="intel-count">{count}</span> actions &nbsp;·&nbsp; {action_type}
                </div>
            </div>
            <div>
                <span class="intel-pending">Pending impact</span>
            </div>
        </div>
        """

    st.markdown(
        f"""
        <div style="border:1px solid rgba(55,65,81,0.9);border-radius:12px;
                    background:rgba(17,24,39,0.92);padding:16px 18px;
                    box-shadow:0 14px 30px rgba(0,0,0,0.25)">
            {rows_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div style="margin-top:10px;text-align:center">'
        '<a href="#" style="color:#818CF8;font-size:12px;font-weight:600;'
        'text-decoration:none">View Full Impact Analysis →</a></div>',
        unsafe_allow_html=True,
    )


# ===========================================================================
# MAIN ENTRY POINT
# ===========================================================================

def render_ppc_overview() -> None:
    """Render the PPC Overview tab. Called from run_performance_hub()."""
    _inject_ppc_theme()

    # ── Session state defaults ──────────────────────────────────────────────
    if "ppc_window_days" not in st.session_state:
        st.session_state["ppc_window_days"] = 30
    if "ppc_match_filter" not in st.session_state:
        st.session_state["ppc_match_filter"] = "All"

    client_id = st.session_state.get("active_account_id") or ""
    test_mode = st.session_state.get("test_mode", False)
    target_roas = float(st.session_state.get("target_roas", 3.0))

    # ── Top bar ─────────────────────────────────────────────────────────────
    top_l, top_r = st.columns([5, 2])
    with top_l:
        st.markdown(
            '<div class="bo-topbar">'
            '<p class="bo-title">PPC Overview</p>'
            '<p class="bo-subtitle">Campaign and keyword-level actionability layer.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    with top_r:
        st.markdown("<div style='padding-top:12px'>", unsafe_allow_html=True)
        window_choice = st.radio(
            "Date window",
            options=[14, 30, 60],
            index=[14, 30, 60].index(st.session_state["ppc_window_days"]),
            format_func=lambda x: f"{x}D",
            horizontal=True,
            label_visibility="collapsed",
            key="ppc_window_radio",
        )
        if window_choice != st.session_state["ppc_window_days"]:
            st.session_state["ppc_window_days"] = window_choice
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    window_days: int = st.session_state["ppc_window_days"]

    # Target ROAS pill
    st.markdown(
        f'<div style="display:flex;justify-content:flex-end;margin-bottom:4px">'
        f'<span class="ppc-target-pill">⚡ Target ROAS: {target_roas:.1f}×</span></div>',
        unsafe_allow_html=True,
    )

    # ── Load data ───────────────────────────────────────────────────────────
    if not client_id:
        st.warning("Please select an account first.")
        return

    _start_date = date.today() - timedelta(days=90)
    raw_df = _fetch_target_stats(client_id, test_mode, start_date=_start_date)

    if raw_df is None or raw_df.empty:
        st.markdown("<br>", unsafe_allow_html=True)
        _empty_state("No PPC data found. Upload a bulk file via the Data Hub to get started.")
        return

    # Normalize column names: DB query returns title-case display aliases
    # e.g. "Spend" → "spend", "Campaign Name" → "campaign_name", "Date" → "start_date"
    raw_df = raw_df.copy()
    raw_df.columns = [c.strip().lower().replace(" ", "_") for c in raw_df.columns]
    raw_df = raw_df.rename(columns={"date": "start_date", "targeting": "target_text"})

    # Filter current window
    cur_df = _filter_by_date(raw_df, window_days)

    # Prior period (same length, immediately before current window)
    if "start_date" in raw_df.columns:
        raw_df["start_date"] = pd.to_datetime(raw_df["start_date"], errors="coerce")
        cur_cutoff = raw_df["start_date"].max() - timedelta(days=window_days)
        prev_cutoff = cur_cutoff - timedelta(days=window_days)
        prev_df = raw_df[
            (raw_df["start_date"] >= prev_cutoff) & (raw_df["start_date"] < cur_cutoff)
        ]
    else:
        prev_df = pd.DataFrame()

    stats = _build_stats(cur_df, prev_df)
    match_filter = st.session_state["ppc_match_filter"]

    # Prepare title-case df for ExecutiveDashboard chart methods
    df_for_charts = _to_exec_df(cur_df)

    # Compute date bounds for exec_data fetch (used by Decision Impact)
    _max_date  = raw_df["start_date"].max().date()
    _min_date  = (_max_date - timedelta(days=window_days))
    exec_data  = _fetch_exec_data(client_id, test_mode, _min_date, _max_date)

    # Instantiate ExecutiveDashboard once (CSS injected once, chart methods reused)
    try:
        from features.executive_dashboard import ExecutiveDashboard
        _exec_dash = ExecutiveDashboard()
    except Exception:
        _exec_dash = None

    # ── Section 1: PPC Health Strip ──────────────────────────────────────────
    _section_header(
        "PPC Health",
        f"Last {window_days} days · vs prior {window_days}-day period",
        icon="health",
    )
    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    _render_health_strip(stats)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 2: Decision Impact ────────────────────────────────────────────
    # NOTE: _render_decision_impact_card() and _render_decision_timeline() each call
    # self._chart_header() internally — no outer _section_header() needed here.
    if exec_data and _exec_dash:
        _di_l, _di_r = st.columns([3, 7])
        with _di_l:
            try:
                _exec_dash._render_decision_impact_card(exec_data)
            except Exception as _e:
                _section_header("Decision Impact", icon="intel")
                _empty_state(f"Impact card unavailable ({_e})")
        with _di_r:
            try:
                _exec_dash._render_decision_timeline(exec_data)
            except Exception as _e:
                _empty_state(f"Impact timeline unavailable ({_e})")
    else:
        _section_header("Decision Impact", "14-day validated attributed revenue from optimizer actions", icon="intel")
        _empty_state("Run the optimizer to generate attributed revenue data.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 3: Campaign Performance + Match Type Efficiency ──────────────
    camp_col, eff_col = st.columns([6, 4])

    with camp_col:
        _section_header(
            "Campaign Performance",
            "Sorted by spend · ROAS color-coded against target",
            icon="campaign",
        )
        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

        # Match type filter
        match_options = ["All", "Exact", "Broad", "Phrase", "Auto", "PT"]
        new_filter = st.segmented_control(
            "Match type",
            options=match_options,
            default=match_filter,
            key="ppc_match_seg",
            label_visibility="collapsed",
        ) if hasattr(st, "segmented_control") else st.selectbox(
            "Match type",
            options=match_options,
            index=match_options.index(match_filter) if match_filter in match_options else 0,
            key="ppc_match_sel",
            label_visibility="collapsed",
        )

        if new_filter != match_filter:
            st.session_state["ppc_match_filter"] = new_filter
            st.rerun()

        # Filter df by match type for campaign table
        filtered_df = cur_df.copy()
        if match_filter != "All" and "match_type" in filtered_df.columns:
            filtered_df = filtered_df[
                filtered_df["match_type"].str.upper() == match_filter.upper()
            ]

        campaign_df = _build_campaign_df(filtered_df, target_roas)
        _render_campaign_table(campaign_df, target_roas, max_rows=10)
        if len(campaign_df) > 10:
            with st.expander(f"Show all {len(campaign_df)} campaigns →"):
                _render_campaign_table(campaign_df, target_roas, max_rows=None)

    with eff_col:
        # NOTE: _render_spend_breakdown() calls self._chart_header("Where The Money Is")
        # internally — no outer header needed.
        if _exec_dash:
            try:
                _exec_dash._render_spend_breakdown({"df_current": df_for_charts, "medians": {}})
            except Exception as _e:
                _section_header("Match Type Efficiency", icon="campaign")
                _empty_state(f"Efficiency chart unavailable ({_e})")
        else:
            _section_header("Match Type Efficiency", icon="campaign")
            _empty_state("Match type efficiency unavailable")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 4: Performance Quadrants ─────────────────────────────────────
    # NOTE: _render_performance_scatter() calls self._chart_header("Performance Quadrants")
    # internally — no outer header needed.
    if _exec_dash:
        try:
            _exec_dash._render_performance_scatter({"df_current": df_for_charts, "medians": {}})
        except Exception as _e:
            _section_header("Performance Quadrants", icon="health")
            _empty_state(f"Performance quadrants unavailable ({_e})")
    else:
        _section_header("Performance Quadrants", icon="health")
        _empty_state("Performance quadrants unavailable")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 5: Keyword Diagnostics + Intelligence Log ────────────────────
    kw_col, log_col = st.columns([13, 7])

    with kw_col:
        _section_header(
            "Keyword Diagnostics",
            "Top keywords by spend · automated flagging: over-spending, under-bidding, zero-conversion",
            icon="keyword",
        )
        kw_df = _build_keyword_df(cur_df, target_roas, match_filter)
        _render_keyword_diagnostics(kw_df, target_roas, max_rows=10)
        if len(kw_df) > 10:
            with st.expander(f"Show all {len(kw_df)} keywords →"):
                _render_keyword_diagnostics(kw_df, target_roas, max_rows=None)

    with log_col:
        _section_header("SADDL Intelligence Log", "Optimizer run history", icon="intel")
        _render_intelligence_log(client_id, test_mode)

    st.markdown("<br>", unsafe_allow_html=True)
