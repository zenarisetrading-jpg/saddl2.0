"""
UI Layout Components

Page setup, sidebar navigation, and home page.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta

from ui.theme import ThemeManager
# plotly is intentionally NOT imported at module level — it adds 3-10 s to cold
# start and is only needed when the Home page renders a gauge chart.
# It is imported lazily inside render_home() instead.


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_home_insights_cached(client_id: str, test_mode: bool, start_date=None):
    """Cache home page insights calculation - prevents repeated large DB queries."""
    from app_core.db_manager import get_db_manager
    db_manager = get_db_manager(test_mode)

    if not db_manager or not client_id:
        return None

    return db_manager.get_target_stats_df(client_id, start_date=start_date)


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_available_dates_cached(client_id: str):
    """Cache available dates check - rarely changes."""
    from app_core.db_manager import get_db_manager
    db = get_db_manager()

    if not db or not client_id:
        return []

    return db.get_available_dates(client_id)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_home_pillar_data(client_id: str, window_days: int = 30) -> dict:
    """
    Fetch analytics-pillar data + health-score inputs for the Phase-3 homepage.

    Queries (in order, each wrapped in try/except for graceful fallback):
      1. sc_raw.spapi_account_links  → resolve account_id / marketplace_id
      2. sc_analytics.account_daily  → revenue, tacos, organic %, sessions, units (current)
      3. sc_analytics.account_daily  → same fields for previous window (CVR delta, revenue delta)
      4. raw_search_term_data        → ad spend + last refresh date
      5. sc_raw.fba_inventory        → latest stock → derive avg days-of-cover
    """
    from app_core.db_manager import get_db_manager
    from datetime import date, timedelta

    _MKTPLACE = "A2VIGQ35RCS4UG"

    empty: dict = {
        "revenue_30d": 0.0, "revenue_prev_30d": 0.0,
        # NOTE: tacos_current is NOT read from account_daily — that column is stored
        # in percentage points (e.g. 12.5 for 12.5 %), NOT as a decimal.
        # We always compute TACOS ourselves: ad_spend / total_ordered_revenue → decimal.
        "organic_share_pct": None,    # from account_daily (percentage points, e.g. 60.2)
        "organic_sales_30d": None,    # from account_daily (AED amount)
        "ad_sales_30d":      None,    # from account_daily (AED amount)
        "ad_spend_30d": 0.0,          # from raw_search_term_data
        "sessions_current": None, "sessions_prev": None,
        "units_current": None, "units_prev": None,
        "avg_days_cover": None,
        "last_refresh_date": None,
        "spapi_available": False,
    }

    db = get_db_manager()
    if not db or not client_id:
        return empty

    today   = date.today()
    end_d   = today   - timedelta(days=1)
    start_d = end_d   - timedelta(days=window_days - 1)
    prev_e  = start_d - timedelta(days=1)
    prev_s  = prev_e  - timedelta(days=window_days - 1)

    result = dict(empty)

    # ── Step 1: Resolve SPAPI scope (needed by analytics query) ──────────────
    account_id     = client_id
    marketplace_id = _MKTPLACE
    try:
        with db._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT account_id, marketplace_id
                FROM sc_raw.spapi_account_links
                WHERE public_client_id = %s AND is_active = TRUE
                ORDER BY updated_at DESC, id DESC LIMIT 1
            """, (client_id,))
            row = cur.fetchone()
            if row:
                account_id     = str(row[0] or client_id)
                marketplace_id = str(row[1] or _MKTPLACE)
                result["spapi_available"] = True
    except Exception:
        pass

    # ── Steps 2-5: Run remaining queries in parallel ──────────────────────────
    # Queries 2+3 are merged into one round-trip (conditional aggregation).
    # Each sub-function opens its own connection so they can run concurrently.
    # NOTE: tacos excluded from account_daily — stored as percentage points (e.g.
    # 12.5 = 12.5 %); TACOS is recomputed in render_home for consistency.
    def _fetch_analytics():
        try:
            with db._get_connection() as _conn:
                _cur = _conn.cursor()
                _cur.execute("""
                    SELECT
                        SUM(CASE WHEN report_date BETWEEN %s AND %s
                            THEN COALESCE(total_ordered_revenue, 0) ELSE 0 END),
                        AVG(CASE WHEN report_date BETWEEN %s AND %s
                            THEN NULLIF(organic_share_pct, 0) END),
                        SUM(CASE WHEN report_date BETWEEN %s AND %s
                            THEN COALESCE(organic_revenue, 0) ELSE 0 END),
                        SUM(CASE WHEN report_date BETWEEN %s AND %s
                            THEN COALESCE(ad_attributed_revenue, 0) ELSE 0 END),
                        SUM(CASE WHEN report_date BETWEEN %s AND %s
                            THEN COALESCE(total_sessions, 0) ELSE 0 END),
                        SUM(CASE WHEN report_date BETWEEN %s AND %s
                            THEN COALESCE(total_units_ordered, 0) ELSE 0 END),
                        SUM(CASE WHEN report_date BETWEEN %s AND %s
                            THEN COALESCE(total_ordered_revenue, 0) ELSE 0 END),
                        SUM(CASE WHEN report_date BETWEEN %s AND %s
                            THEN COALESCE(total_sessions, 0) ELSE 0 END),
                        SUM(CASE WHEN report_date BETWEEN %s AND %s
                            THEN COALESCE(total_units_ordered, 0) ELSE 0 END)
                    FROM sc_analytics.account_daily
                    WHERE account_id = %s AND marketplace_id = %s
                      AND report_date BETWEEN %s AND %s
                """, (
                    str(start_d), str(end_d),
                    str(start_d), str(end_d),
                    str(start_d), str(end_d),
                    str(start_d), str(end_d),
                    str(start_d), str(end_d),
                    str(start_d), str(end_d),
                    str(prev_s),  str(prev_e),
                    str(prev_s),  str(prev_e),
                    str(prev_s),  str(prev_e),
                    account_id, marketplace_id,
                    str(prev_s), str(end_d),
                ))
                return _cur.fetchone()
        except Exception:
            return None

    def _fetch_ad_spend():
        try:
            with db._get_connection() as _conn:
                _cur = _conn.cursor()
                _cur.execute("""
                    SELECT COALESCE(SUM(spend), 0), MAX(report_date)
                    FROM raw_search_term_data
                    WHERE client_id = %s AND report_date BETWEEN %s AND %s
                """, (client_id, str(start_d), str(end_d)))
                return _cur.fetchone()
        except Exception:
            return None

    def _fetch_inventory():
        try:
            with db._get_connection() as _conn:
                _cur = _conn.cursor()
                _cur.execute("""
                    SELECT COALESCE(SUM(afn_fulfillable_quantity), 0)
                    FROM sc_raw.fba_inventory
                    WHERE client_id = %s
                      AND snapshot_date = (
                          SELECT MAX(snapshot_date)
                          FROM sc_raw.fba_inventory
                          WHERE client_id = %s
                      )
                """, (client_id, client_id))
                return _cur.fetchone()
        except Exception:
            return None

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as _pool:
        _f_analytics = _pool.submit(_fetch_analytics)
        _f_spend     = _pool.submit(_fetch_ad_spend)
        _f_inv       = _pool.submit(_fetch_inventory)
        row_analytics = _f_analytics.result()
        row_spend     = _f_spend.result()
        row_inv       = _f_inv.result()

    # ── Merge results ─────────────────────────────────────────────────────────
    if row_analytics:
        result.update({
            "revenue_30d":       float(row_analytics[0] or 0),
            "organic_share_pct": float(row_analytics[1]) if row_analytics[1] else None,
            "organic_sales_30d": float(row_analytics[2]) if row_analytics[2] else None,
            "ad_sales_30d":      float(row_analytics[3]) if row_analytics[3] else None,
            "sessions_current":  float(row_analytics[4]) if row_analytics[4] else None,
            "units_current":     float(row_analytics[5]) if row_analytics[5] else None,
            "revenue_prev_30d":  float(row_analytics[6] or 0),
            "sessions_prev":     float(row_analytics[7]) if row_analytics[7] else None,
            "units_prev":        float(row_analytics[8]) if row_analytics[8] else None,
        })

    if row_spend:
        result["ad_spend_30d"]     = float(row_spend[0] or 0)
        result["last_refresh_date"] = str(row_spend[1])[:10] if row_spend[1] else None

    if row_inv:
        total_inv = float(row_inv[0] or 0)
        units_cur = result.get("units_current") or 0.0
        if total_inv > 0 and units_cur > 0:
            daily_rate = units_cur / window_days
            if daily_rate > 0:
                result["avg_days_cover"] = round(total_inv / daily_rate, 1)

    return result


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_optimizer_stats_cached(client_id: str) -> dict:
    """
    Fetch optimizer pillar stats from actions_log.

    Returns:
        total_actions   int   — all-time count for this client
        last_run_date   str | None  — date of most recent action (YYYY-MM-DD)
        pending_count   int   — actions within the last 14 days (window not yet mature)
    """
    from app_core.db_manager import get_db_manager
    from datetime import date, timedelta

    empty = {"total_actions": 0, "last_run_date": None, "pending_count": 0}

    db = get_db_manager()
    if not db or not client_id:
        return empty

    cutoff = str(date.today() - timedelta(days=14))
    try:
        with db._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    COUNT(*)                                              AS total_actions,
                    MAX(action_date)::date                                AS last_run,
                    SUM(CASE WHEN action_date::date >= %s THEN 1 ELSE 0 END) AS pending
                FROM actions_log
                WHERE client_id = %s
            """, (cutoff, client_id))
            row = cur.fetchone()
            if row:
                return {
                    "total_actions": int(row[0] or 0),
                    "last_run_date": str(row[1])[:10] if row[1] else None,
                    "pending_count": int(row[2] or 0),
                }
    except Exception:
        pass

    return empty


# Lazy imports kept inside functions to prevent circular dependencies at module load

def setup_page():
    """Setup page CSS and styling."""
    # Apply dynamic theme CSS
    ThemeManager.apply_css()

def render_sidebar(navigate_to):
    """
    Render sidebar navigation.
    
    Args:
        navigate_to: Function to navigate between modules
        
    Returns:
        Selected module name
    """
    # Wrap navigate_to to check for pending actions when leaving optimizer
    def safe_navigate(target_module):
        current = st.session_state.get('current_module', 'home')
        
        # Check if leaving optimizer with pending actions that haven't been accepted
        if current == 'optimizer' and target_module != 'optimizer':
            pending = st.session_state.get('pending_actions')
            accepted = st.session_state.get('optimizer_actions_accepted', False)
            
            if pending and not accepted:
                # Store the target and show confirmation
                st.session_state['_pending_navigation_target'] = target_module
                st.session_state['_show_action_confirmation'] = True
                st.rerun()
                return
        
        navigate_to(target_module)
    # Sidebar Logo at TOP (theme-aware, prominent)
    theme_mode = st.session_state.get('theme_mode', 'dark')
    logo_data = ThemeManager.get_cached_logo(theme_mode)
    
    if logo_data:
        st.sidebar.markdown(
            f'<div style="text-align: center; padding: 15px 0 20px 0;"><img src="data:image/png;base64,{logo_data}" style="width: 200px;" /></div>',
            unsafe_allow_html=True
        )
        
    # Account selector
    from ui.account_manager import render_account_selector
    render_account_selector()
    
    st.sidebar.markdown("---")
    
    if st.sidebar.button("Home", width='stretch'):
        safe_navigate('home')
    
    if st.sidebar.button("Account Overview", width='stretch'):
        safe_navigate('performance')
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### SYSTEM")
    
    # Data Hub - central upload
    if st.sidebar.button("Data Hub", width='stretch'):
        safe_navigate('data_hub')
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### ANALYZE")
    
    # Core features
    if st.sidebar.button("Optimizer", width='stretch'):
        safe_navigate('optimizer')
    
    if st.sidebar.button("ASIN Shield", width='stretch'):
        safe_navigate('asin_mapper')
    
    if st.sidebar.button("Clusters", width='stretch'):
        safe_navigate('ai_insights')
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### ACTIONS")
    
    if st.sidebar.button("Launchpad", width='stretch'):
        safe_navigate('creator')
    
    st.sidebar.markdown("---")
    
    if st.sidebar.button("Help & Support", width='stretch', icon="❓"):
        safe_navigate('help_center')
    
    # Show undo toast if available
    from ui.action_confirmation import show_undo_toast
    show_undo_toast()
    
    # Theme Toggle at BOTTOM
    st.sidebar.markdown("---")
    ThemeManager.render_toggle()
    
    return st.session_state.get('current_module', 'home')

def render_home():  # noqa: C901 – intentionally large view function
    """
    Phase 3 Homepage — three-section layout:
      Section 1  Account Pulse   (top bar with name, health score, top driver)
      Section 2  Three Pillars   (Analytics | Optimizer | Impact cards)
      Section 3  Intelligence Briefing (deterministic prose + LLM deep-analysis button)
    """
    import streamlit as st
    from app_core.account_utils import get_active_account_id
    from ui.components.empty_states import render_empty_state
    
    # === EMPTY STATE CHECKS ===
    # Support "Test Mode" via query params to verify empty states without deleting data
    # Usage: ?test_state=no_account or ?test_state=no_data
    test_state = st.query_params.get("test_state")


    
    # 1. Check if any accounts exist at all (No Accounts)
    db = st.session_state.get('db_manager')
    has_accounts = False
    if db:
        # Get Organization Context
        from app_core.auth.service import AuthService
        auth = AuthService()
        current_user = auth.get_current_user()
        org_id = str(current_user.organization_id) if current_user else None

        # Use cached account fetcher to avoid repeated DB queries
        from ui.account_manager import _fetch_accounts_cached
        accounts = _fetch_accounts_cached(org_id) if org_id else []
        has_accounts = len(accounts) > 0
        
    # Force empty state if requested
    if test_state == "no_account" or not has_accounts:
        render_empty_state('no_account')
        return

    # 2. Check if active account has data (No Data / Syncing)
    active_account_id = st.session_state.get('active_account_id')
    account_name = st.session_state.get('active_account_name', 'Account')
    
    # Check if data loaded in DataHub or DB has data
    from app_core.data_hub import DataHub
    hub = DataHub()
    
    # Try basic data existence check
    data_exists = False
    if hub.is_loaded("search_term_report"):
        data_exists = True
    elif active_account_id and db:
        # Quick DB check (CACHED to avoid repeated queries)
        dates = _fetch_available_dates_cached(active_account_id)
        if dates and len(dates) > 0:
            data_exists = True
            
    if test_state == "no_data" or not data_exists:
        render_empty_state('no_data', context={'account_name': account_name})
        return

    # ══════════════════════════════════════════════════════════════════
    # DATA FETCH  (all queries go through @st.cache_data helpers above)
    # ══════════════════════════════════════════════════════════════════
    from utils.formatters import get_account_currency
    from features.dashboard.constants import DEFAULT_TARGET_TACOS
    from features.dashboard.metrics import (
        compute_account_health_score,
        score_against_target_lower_better,
        score_ratio_higher_better,
        score_trend_delta,
        calculate_cvr,
        calculate_delta_pct,
    )
    from features.dashboard.insights import (
        score_to_label,
        score_to_color,
        generate_deterministic_briefing,
        format_llm_context,
        call_homepage_llm,
        parse_analysis_sections,
    )

    client_id    = str(active_account_id) if active_account_id else ''
    currency     = get_account_currency()
    target_tacos = DEFAULT_TARGET_TACOS   # 0.15 (15 %)
    WINDOW       = 30

    pillar   = _fetch_home_pillar_data(client_id, WINDOW)
    opt_data = _fetch_optimizer_stats_cached(client_id)

    # Impact — session-state cache so the heavy LATERAL-join SQL only runs once per session,
    # not on every re-render. Falls back to None (Impact pillar shows "—") if not yet loaded.
    from features.impact.exports import get_recent_impact_summary
    _impact_skey = f"_home_impact_{client_id}"
    if _impact_skey not in st.session_state:
        try:
            st.session_state[_impact_skey] = get_recent_impact_summary()
        except Exception:
            st.session_state[_impact_skey] = None
    impact_summary = st.session_state[_impact_skey]

    # ══════════════════════════════════════════════════════════════════
    # HEALTH SCORE  — identical component logic to business_overview.py
    # ══════════════════════════════════════════════════════════════════
    total_sales   = pillar.get("revenue_30d", 0.0)
    ad_spend      = pillar.get("ad_spend_30d", 0.0)
    organic_sales = pillar.get("organic_sales_30d")
    ad_sales      = pillar.get("ad_sales_30d")
    avg_cover     = pillar.get("avg_days_cover")
    sessions_cur  = pillar.get("sessions_current")
    sessions_prv  = pillar.get("sessions_prev")
    units_cur     = pillar.get("units_current")
    units_prv     = pillar.get("units_prev")

    # TACOS: always ad_spend / total_revenue  → decimal (e.g. 0.153 for 15.3 %)
    tacos_current = (ad_spend / total_sales) if (total_sales and ad_spend) else None

    tacos_score   = score_against_target_lower_better(tacos_current, target_tacos)

    organic_ratio = None
    if organic_sales and ad_sales:
        organic_ratio = organic_sales / ad_sales if ad_sales > 0 else None
    ratio_score  = score_ratio_higher_better(organic_ratio, baseline=1.0)
    inv_score    = score_ratio_higher_better(avg_cover, baseline=30.0)

    cvr_current  = calculate_cvr(units_cur or 0, sessions_cur or 0) if sessions_cur else None
    cvr_prev     = calculate_cvr(units_prv or 0, sessions_prv or 0) if sessions_prv else None
    cvr_delta    = calculate_delta_pct(cvr_current, cvr_prev)
    cvr_score    = score_trend_delta(cvr_delta, sensitivity=1.5)

    health_result = compute_account_health_score(
        tacos_vs_target_score      = tacos_score,
        organic_paid_ratio_score   = ratio_score,
        inventory_days_cover_score = inv_score,
        cvr_trend_score            = cvr_score,
    )

    health_score = round(health_result.score) if health_result.state != "neutral" else None
    label        = score_to_label(health_score or 0)
    label_color  = score_to_color(health_score or 0)

    # ── Biggest-gap driver sentence ───────────────────────────────────
    top_driver = ""
    if health_result.state != "neutral" and health_result.weighted_components:
        _base_weights = {
            "tacos_vs_target":      0.30,
            "organic_paid_ratio":   0.25,
            "inventory_days_cover": 0.25,
            "cvr_trend":            0.20,
        }
        worst_key, worst_gap = "", 0.0
        for key, wt in _base_weights.items():
            if key in health_result.weighted_components:
                gap = wt * 100 - health_result.weighted_components[key]
                if gap > worst_gap:
                    worst_gap, worst_key = gap, key

        if worst_key == "tacos_vs_target" and tacos_current is not None:
            top_driver = (
                f"TACOS at {tacos_current*100:.1f}% vs {target_tacos*100:.0f}% target "
                f"\u2014 {worst_gap:.0f}-pt gap"
            )
        elif worst_key == "organic_paid_ratio" and organic_ratio is not None:
            top_driver = f"Organic/paid ratio {organic_ratio:.2f}\u00d7 is the main opportunity"
        elif worst_key == "inventory_days_cover" and avg_cover is not None:
            top_driver = f"Inventory cover {avg_cover:.0f} days \u2014 {worst_gap:.0f}-pt gap"
        elif worst_key == "cvr_trend" and cvr_delta is not None:
            top_driver = (
                f"CVR trend {'+' if cvr_delta >= 0 else ''}{cvr_delta:.1f}% "
                f"\u2014 {worst_gap:.0f}-pt gap"
            )

    # Impact pillar values
    attributed   = float(impact_summary.get('attributed_impact', 0)) if impact_summary else 0.0
    win_rate     = float(impact_summary.get('win_rate',           0)) if impact_summary else 0.0
    mature_count = int(  impact_summary.get('total_actions',      0)) if impact_summary else 0

    # Metrics bundle (shared by briefing + LLM)
    organic_pct = pillar.get("organic_share_pct")  # already in pct-points (e.g. 60.2)
    metrics_bundle = {
        "health_score":            health_score or 0,
        "tacos_current":           tacos_current,
        "target_tacos":            target_tacos,
        "revenue_30d":             total_sales,
        "revenue_prev_30d":        pillar.get("revenue_prev_30d", 0.0),
        "organic_share_pct":       organic_pct,
        "avg_days_cover":          avg_cover,
        "attributed_impact":       attributed,
        "optimizer_total_actions": opt_data.get("total_actions", 0),
        "win_rate":                win_rate,
        "currency":                currency,
        "account_name":            account_name,
        "last_refresh_date":       pillar.get("last_refresh_date"),
    }

    # ══════════════════════════════════════════════════════════════════
    # PRE-RENDER CALCULATIONS
    # ══════════════════════════════════════════════════════════════════
    if tacos_current is not None:
        _tr = (tacos_current - target_tacos) / target_tacos * 100
        tacos_color = "#EF4444" if _tr > 10 else ("#10B981" if _tr < -10 else "#F59E0B")
        tacos_cls   = "hp2-val-warn" if _tr > 10 else ("hp2-val-good" if _tr < -10 else "hp2-val")
    else:
        tacos_color = "#6B7280"
        tacos_cls   = "hp2-val"

    rev_prev      = pillar.get("revenue_prev_30d", 0.0)
    rev_trend_html = ""
    if rev_prev and total_sales:
        _rd  = (total_sales - rev_prev) / rev_prev * 100
        _tc  = "hp2-trend-dn" if _rd < 0 else "hp2-trend-up"
        # SVG arrows (no bitmap emoji)
        _arr_svg = (
            '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
            ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="m6 9 6 6 6-6"/></svg>'
            if _rd < 0 else
            '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
            ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="m18 15-6-6-6 6"/></svg>'
        )
        rev_trend_html = (
            f'<div class="hp2-trend-badge {_tc}">'
            f'{_arr_svg} {abs(_rd):.1f}% vs prior'
            f'</div>'
        )

    _spark_path = (
        "M0 30 Q60 50,120 45 T220 80 T300 110"
        if (rev_prev and total_sales and total_sales < rev_prev)
        else "M0 100 Q60 70,120 80 T220 45 T300 30"
    )

    health_pct    = health_score if health_score is not None else 0
    last_refresh  = pillar.get("last_refresh_date")
    refresh_str   = f"Last refresh: {last_refresh}" if last_refresh else "No data yet"
    rev_str       = f"{total_sales:,.0f}"           if total_sales          else "\u2014"
    tacos_val     = f"{tacos_current*100:.1f}%"     if tacos_current is not None else "\u2014"
    tacos_tgt_str = f"{target_tacos*100:.0f}%"
    org_str       = f"{organic_pct:.1f}%"           if organic_pct is not None else "\u2014"
    total_act_str = f"{opt_data.get('total_actions', 0):,}"
    last_run_str  = opt_data.get("last_run_date") or "Never"
    impact_str    = f"{currency}\u00a0{attributed:,.0f}" if attributed else "\u2014"
    win_str       = f"{win_rate:.0f}%"              if win_rate             else "\u2014"
    win_cls       = "hp2-val hp2-val-good"          if win_rate >= 60       else "hp2-val"

    cache_key       = f"{client_id}_homepage_analysis_30d"
    cached_analysis = st.session_state.get(cache_key)

    # ── HTML helper — strip indentation to prevent Markdown code-blocks ──
    import re as _re
    def _hmd(html: str) -> None:
        compact = _re.sub(r"\n[ \t]+", "\n", html.strip())
        st.markdown(compact, unsafe_allow_html=True)

    # ── Lucide-style SVG icon constants (no bitmap/emoji anywhere) ──────
    # Each is a single-line inline SVG string
    _I_SHIELD  = ('<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                  ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
                  '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
                  '<path d="m9 12 2 2 4-4"/></svg>')
    _I_CHART   = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                  ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
                  '<path d="M3 3v18h18"/><path d="M13 17V9"/>'
                  '<path d="M18 17V5"/><path d="M8 17v-3"/></svg>')
    _I_ZAP     = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                  ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
                  '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>')
    _I_TARGET  = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                  ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
                  '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/>'
                  '<circle cx="12" cy="12" r="2"/></svg>')
    _I_CHECK   = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                  ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
                  '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>')
    _I_EYE     = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                  ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
                  '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>'
                  '<circle cx="12" cy="12" r="3"/></svg>')
    _I_PIN     = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                  ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
                  '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/>'
                  '<circle cx="12" cy="10" r="3"/></svg>')
    _I_REFRESH = ('<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                  ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
                  '<path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>'
                  '<path d="M3 3v5h5"/>'
                  '<path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/>'
                  '<path d="M16 16h5v5"/></svg>')
    _I_SPARK   = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                  ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                  '<path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1'
                  ' 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2'
                  ' 0 0 1-1.275-1.275L12 3Z"/></svg>')
    _I_BAR_UP  = ('<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                  ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
                  '<path d="M3 3v18h18"/><path d="m7 16 4-4 4 4 5-5"/>'
                  '<path d="M18 7h3v3"/></svg>')

    # ══════════════════════════════════════════════════════════════════
    # CSS
    # ══════════════════════════════════════════════════════════════════
    st.markdown(f"""<style>
/* ── Account header ──────────────────────────────────────────── */
.hp2-ae-badge {{
    display:inline-flex;align-items:center;justify-content:center;
    width:32px;height:32px;border-radius:9px;
    background:linear-gradient(135deg,#6366F1,#9333EA);
    box-shadow:0 4px 14px rgba(99,102,241,0.35);
    font-size:0.68rem;font-weight:800;color:#fff;letter-spacing:0.06em;
    vertical-align:middle;flex-shrink:0;
}}
.hp2-acct-name {{
    font-size:2.2rem;font-weight:900;letter-spacing:-0.05em;
    background:linear-gradient(to right,#FFFFFF 40%,#6B7280 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    background-clip:text;display:inline-block;line-height:1.1;
}}
.hp2-refresh-row {{
    display:flex;align-items:center;gap:6px;
    font-size:0.7rem;font-weight:600;color:#374151;
    text-transform:uppercase;letter-spacing:0.12em;margin-top:6px;
}}
.hp2-refresh-row svg {{ opacity:0.5; }}

/* ── Glassmorphic icon wrap (used in pillar titles + AI cards) ── */
.hp2-icon-wrap {{
    width:34px;height:34px;border-radius:10px;flex-shrink:0;
    display:flex;align-items:center;justify-content:center;
    background:rgba(255,255,255,0.06);
    border:1px solid rgba(255,255,255,0.1);
    backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);
}}
/* pillar-specific icon wrap colours */
.hp2-pillar-analytics .hp2-icon-wrap {{
    background:rgba(99,102,241,0.14);border-color:rgba(99,102,241,0.25);
}}
.hp2-pillar-optimizer .hp2-icon-wrap {{
    background:rgba(6,182,212,0.14);border-color:rgba(6,182,212,0.25);
}}
.hp2-pillar-impact .hp2-icon-wrap {{
    background:rgba(244,63,94,0.14);border-color:rgba(244,63,94,0.25);
}}
/* AI card-specific icon wrap colours */
.hp2-ai-achievements .hp2-ai-icon-wrap {{
    background:rgba(16,185,129,0.14);border-color:rgba(16,185,129,0.25);
}}
.hp2-ai-monitor .hp2-ai-icon-wrap {{
    background:rgba(245,158,11,0.14);border-color:rgba(245,158,11,0.25);
}}
.hp2-ai-actions .hp2-ai-icon-wrap {{
    background:rgba(99,102,241,0.18);border-color:rgba(99,102,241,0.28);
}}
/* SVG stroke colours per context */
.hp2-pillar-analytics .hp2-icon-wrap svg {{ stroke:#818CF8; }}
.hp2-pillar-optimizer .hp2-icon-wrap svg {{ stroke:#22D3EE; }}
.hp2-pillar-impact    .hp2-icon-wrap svg {{ stroke:#FB7185; }}
.hp2-ai-achievements  .hp2-ai-icon-wrap svg {{ stroke:#34D399; }}
.hp2-ai-monitor       .hp2-ai-icon-wrap svg {{ stroke:#FBBF24; }}
.hp2-ai-actions       .hp2-ai-icon-wrap svg {{ stroke:#818CF8; }}

/* ── Health gauge card ────────────────────────────────────────── */
.hp2-gauge-card {{
    background:rgba(17,17,22,0.90);
    border:1px solid {label_color}28;border-radius:24px;
    padding:28px 20px 24px 20px;
    display:flex;flex-direction:column;align-items:center;
    justify-content:center;min-height:298px;
    position:relative;overflow:hidden;
    box-shadow:0 0 50px {label_color}0D;
}}
.hp2-gauge-card::before {{
    content:'';position:absolute;inset:0;
    background:radial-gradient(ellipse at 50% 25%,{label_color}0A 0%,transparent 65%);
    pointer-events:none;
}}
.hp2-gauge-badge {{
    position:absolute;top:18px;left:20px;
    display:flex;align-items:center;gap:8px;
}}
.hp2-gauge-badge svg {{ stroke:{label_color}; }}
.hp2-gauge-badge-text {{
    font-size:0.62rem;font-weight:800;color:#4B5563;
    text-transform:uppercase;letter-spacing:0.16em;
}}
/* CSS conic-gradient ring */
.hp2-gauge-ring {{
    width:176px;height:176px;border-radius:50%;
    position:relative;display:flex;align-items:center;
    justify-content:center;margin-top:14px;
}}
.hp2-gauge-hole {{
    width:148px;height:148px;border-radius:50%;
    background:rgba(12,12,18,0.98);
    position:absolute;
    display:flex;flex-direction:column;align-items:center;justify-content:center;
    z-index:1;
}}
.hp2-gauge-num   {{ font-size:4.8rem;font-weight:900;color:#fff;letter-spacing:-5px;line-height:1; }}
.hp2-gauge-denom {{
    font-size:0.68rem;font-weight:700;color:#374151;
    text-transform:uppercase;letter-spacing:0.1em;margin-top:3px;
}}
.hp2-health-chip {{
    margin-top:18px;padding:8px 26px;border-radius:999px;
    background:{label_color}16;border:1px solid {label_color}30;
    color:{label_color};font-size:0.74rem;font-weight:800;
    text-transform:uppercase;letter-spacing:0.14em;
    box-shadow:0 0 18px {label_color}18;
}}

/* ── Revenue card ─────────────────────────────────────────────── */
.hp2-rev-card {{
    background:rgba(17,17,22,0.85);
    border:1px solid rgba(255,255,255,0.06);border-radius:24px;
    padding:26px 28px;position:relative;overflow:hidden;min-height:138px;
}}
.hp2-rev-card::before {{
    content:'';position:absolute;inset:0;
    background:linear-gradient(135deg,rgba(99,102,241,0.06) 0%,rgba(168,85,247,0.02) 55%,transparent 100%);
    pointer-events:none;
}}
.hp2-rev-label {{
    font-size:0.68rem;font-weight:700;color:#4B5563;
    text-transform:uppercase;letter-spacing:0.16em;
    display:flex;align-items:center;gap:7px;margin-bottom:10px;
}}
.hp2-rev-label svg {{ stroke:#6366F1;opacity:0.7; }}
.hp2-rev-row {{ display:flex;align-items:baseline;gap:7px;position:relative;z-index:1; }}
.hp2-rev-cur {{ font-size:1.6rem;font-weight:700;color:#374151;line-height:1; }}
.hp2-rev-amt {{
    font-size:4.2rem;font-weight:900;color:#fff;
    letter-spacing:-4px;line-height:1;font-variant-numeric:tabular-nums;
}}
.hp2-trend-badge {{
    display:inline-flex;align-items:center;gap:5px;
    padding:4px 12px;border-radius:999px;font-size:0.78rem;font-weight:700;
    position:absolute;top:22px;right:24px;z-index:1;
}}
.hp2-trend-dn {{
    background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.25);color:#F87171;
}}
.hp2-trend-up {{
    background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.25);color:#34D399;
}}
.hp2-sparkline {{
    position:absolute;bottom:0;right:0;opacity:0.10;
    pointer-events:none;transform:translate(8%,12%);
}}

/* ── Driver card ──────────────────────────────────────────────── */
.hp2-driver-card {{
    background:rgba(17,17,22,0.82);
    border:1px solid rgba(255,255,255,0.05);border-radius:24px;
    padding:20px 22px;display:flex;align-items:center;
    justify-content:space-between;gap:14px;
    position:relative;overflow:hidden;
    background-image:linear-gradient(135deg,{label_color}07 0%,transparent 55%);
}}
.hp2-driver-lbl  {{
    font-size:0.65rem;font-weight:800;color:#374151;
    text-transform:uppercase;letter-spacing:0.16em;margin-bottom:4px;
}}
.hp2-driver-desc {{ color:#4B5563;font-size:0.84rem;font-weight:500; }}
.hp2-driver-pill {{
    display:inline-flex;align-items:center;gap:12px;
    background:{label_color}10;border:1px solid {label_color}22;
    padding:12px 18px;border-radius:16px;flex-shrink:0;
    box-shadow:0 0 18px {label_color}0C;
}}
.hp2-driver-pill-icon {{
    width:36px;height:36px;background:{label_color}1A;border-radius:50%;
    display:flex;align-items:center;justify-content:center;flex-shrink:0;
}}
.hp2-driver-pill-icon svg {{ stroke:{label_color}; }}
.hp2-driver-val {{ color:{label_color};font-size:1rem;font-weight:800;line-height:1.25; }}
.hp2-driver-sub {{
    color:{label_color}88;font-size:0.64rem;font-weight:700;
    text-transform:uppercase;letter-spacing:0.1em;margin-top:2px;
}}

/* ── Section divider ──────────────────────────────────────────── */
.hp2-section-hdr {{ display:flex;align-items:center;gap:12px;margin:26px 0 14px 0; }}
.hp2-section-hdr-text {{
    font-size:0.65rem;font-weight:800;text-transform:uppercase;
    letter-spacing:0.2em;color:#374151;white-space:nowrap;
}}
.hp2-section-hdr-line {{ flex:1;height:1px;background:rgba(55,65,81,0.38); }}

/* ── Pillar cards ─────────────────────────────────────────────── */
.hp2-pillar {{
    background:rgba(17,17,22,0.65);
    border:1px solid rgba(255,255,255,0.05);border-radius:20px;padding:20px;
    position:relative;overflow:hidden;
    transition:border-color 0.25s ease,box-shadow 0.25s ease;
}}
.hp2-pillar-analytics:hover {{
    border-color:rgba(99,102,241,0.38);box-shadow:0 0 30px rgba(99,102,241,0.07);
}}
.hp2-pillar-optimizer:hover {{
    border-color:rgba(6,182,212,0.38);box-shadow:0 0 30px rgba(6,182,212,0.07);
}}
.hp2-pillar-impact:hover {{
    border-color:rgba(244,63,94,0.38);box-shadow:0 0 30px rgba(244,63,94,0.07);
}}
.hp2-pillar-glow {{
    position:absolute;top:0;right:0;width:120px;height:120px;
    border-radius:50%;transform:translate(44%,-44%);pointer-events:none;
}}
.hp2-pillar-analytics .hp2-pillar-glow {{
    background:radial-gradient(circle,rgba(99,102,241,0.16) 0%,transparent 70%);
}}
.hp2-pillar-optimizer .hp2-pillar-glow {{
    background:radial-gradient(circle,rgba(6,182,212,0.16) 0%,transparent 70%);
}}
.hp2-pillar-impact .hp2-pillar-glow {{
    background:radial-gradient(circle,rgba(244,63,94,0.16) 0%,transparent 70%);
}}
.hp2-pillar-hdr {{
    display:flex;justify-content:space-between;align-items:center;
    margin-bottom:18px;position:relative;
}}
.hp2-pillar-title {{
    font-size:0.88rem;font-weight:800;color:#F1F5F9;
    display:flex;align-items:center;gap:9px;
}}
.hp2-metric-2col {{ display:grid;grid-template-columns:1fr 1fr;gap:14px; }}
.hp2-metric-lbl {{
    font-size:0.65rem;font-weight:700;color:#374151;
    text-transform:uppercase;letter-spacing:0.11em;margin-bottom:6px;
}}
.hp2-metric-lbl-note {{ color:#2D3748;font-size:0.6rem; }}
.hp2-val    {{ font-size:1.8rem;font-weight:800;color:#fff;letter-spacing:-0.5px;line-height:1.1; }}
.hp2-val-sm {{ font-size:0.9rem;font-weight:600;color:#94A3B8;line-height:1.4;margin-top:4px; }}
.hp2-val-warn {{ color:{tacos_color} !important; }}
.hp2-val-good {{ color:#34D399 !important; }}

/* ── Intel briefing ───────────────────────────────────────────── */
.hp2-exec-banner {{
    background:linear-gradient(to right,rgba(99,102,241,0.09),rgba(168,85,247,0.04),transparent);
    border-left:3px solid rgba(99,102,241,0.65);border-radius:0 16px 16px 0;
    padding:16px 20px;margin-bottom:18px;color:#CBD5E1;
    font-size:0.9rem;line-height:1.85;
}}

/* ── AI insight cards ─────────────────────────────────────────── */
.hp2-ai-card {{
    background:rgba(17,17,22,0.55);
    border:1px solid rgba(255,255,255,0.05);border-radius:20px;padding:20px;
    position:relative;overflow:hidden;
}}
.hp2-ai-actions {{
    background:rgba(99,102,241,0.04);border-color:rgba(99,102,241,0.18);
}}
.hp2-ai-actions::before {{
    content:'';position:absolute;top:0;right:0;width:110px;height:110px;
    background:radial-gradient(circle,rgba(99,102,241,0.12) 0%,transparent 70%);
    transform:translate(40%,-40%);pointer-events:none;
}}
.hp2-ai-hdr {{ display:flex;align-items:center;gap:10px;margin-bottom:18px; }}
.hp2-ai-icon-wrap {{
    width:34px;height:34px;border-radius:10px;flex-shrink:0;
    display:flex;align-items:center;justify-content:center;
    backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);
}}
.hp2-ai-title  {{ font-size:0.9rem;font-weight:800;color:#F1F5F9; }}
.hp2-ai-items  {{ display:flex;flex-direction:column;gap:13px; }}
.hp2-ai-item   {{ display:flex;align-items:flex-start;gap:11px; }}
.hp2-ai-dot    {{ width:7px;height:7px;border-radius:50%;margin-top:7px;flex-shrink:0; }}
.hp2-ai-achievements .hp2-ai-dot {{
    background:#10B981;box-shadow:0 0 7px rgba(16,185,129,0.75);
}}
.hp2-ai-monitor .hp2-ai-dot {{
    background:#F59E0B;box-shadow:0 0 7px rgba(245,158,11,0.75);
}}
.hp2-ai-actions .hp2-ai-dot {{
    background:#818CF8;box-shadow:0 0 7px rgba(129,140,248,0.75);
}}
.hp2-ai-text   {{ font-size:0.84rem;color:#94A3B8;line-height:1.65; }}
.hp2-ai-actions .hp2-ai-text {{ color:#CBD5E1;font-weight:500; }}
.hp2-ai-text strong {{ color:#E2E8F0;font-weight:700; }}
</style>""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════
    # HEADER ROW
    # ══════════════════════════════════════════════════════════════════
    h_left, h_right = st.columns([7, 3])
    with h_left:
        _hmd(
            f'<div style="margin-bottom:4px;">'
            f'<div style="display:flex;align-items:center;gap:13px;margin-bottom:6px;">'
            f'<span class="hp2-ae-badge">AE</span>'
            f'<span class="hp2-acct-name">{account_name}</span>'
            f'</div>'
            f'<div class="hp2-refresh-row">{_I_REFRESH}&ensp;{refresh_str}</div>'
            f'</div>'
        )
    with h_right:
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        if cached_analysis:
            if st.button(
                "Regenerate Analysis",
                key="hp2_regen_top",
                width='stretch',
            ):
                del st.session_state[cache_key]
                st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════
    # HERO BENTO — Gauge (4) | Revenue + Driver (8)
    # ══════════════════════════════════════════════════════════════════
    hero_L, hero_R = st.columns([4, 8])

    with hero_L:
        if health_score is not None:
            _grad  = (
                f"conic-gradient(from -90deg,"
                f"{label_color} 0% {health_pct}%,"
                f"rgba(55,65,81,0.5) {health_pct}% 100%)"
            )
            _glow  = f"0 0 28px {label_color}35, 0 0 48px {label_color}15"
            gauge_inner = (
                f'<div class="hp2-gauge-ring" '
                f'style="background:{_grad};box-shadow:{_glow};">'
                f'<div class="hp2-gauge-hole">'
                f'<span class="hp2-gauge-num">{health_score}</span>'
                f'<span class="hp2-gauge-denom">/ 100</span>'
                f'</div></div>'
                f'<div class="hp2-health-chip">{label}</div>'
            )
        else:
            gauge_inner = (
                '<div style="color:#374151;font-size:4rem;font-weight:900;'
                'letter-spacing:-4px;margin-top:20px;line-height:1;">&mdash;</div>'
                '<div style="color:#374151;font-size:0.7rem;font-weight:700;'
                'text-transform:uppercase;letter-spacing:0.12em;margin-top:10px;">'
                'Awaiting data</div>'
            )

        _hmd(
            f'<div class="hp2-gauge-card">'
            f'<div class="hp2-gauge-badge">'
            f'<div class="hp2-icon-wrap" style="background:rgba(255,255,255,0.05);'
            f'border-color:{label_color}25;width:28px;height:28px;border-radius:8px;">'
            f'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="{label_color}"'
            f' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
            f'<path d="m9 12 2 2 4-4"/></svg>'
            f'</div>'
            f'<span class="hp2-gauge-badge-text">Account Health</span>'
            f'</div>'
            f'{gauge_inner}'
            f'</div>'
        )

    with hero_R:
        _hmd(
            f'<div class="hp2-rev-card">'
            f'{rev_trend_html}'
            f'<div class="hp2-rev-label">'
            f'{_I_BAR_UP} Revenue 30D'
            f'</div>'
            f'<div class="hp2-rev-row">'
            f'<span class="hp2-rev-cur">{currency}</span>'
            f'<span class="hp2-rev-amt">{rev_str}</span>'
            f'</div>'
            f'<svg class="hp2-sparkline" width="260" height="110" viewBox="0 0 300 120" fill="none">'
            f'<path d="{_spark_path}" stroke="#818CF8" stroke-width="7"'
            f' stroke-linecap="round" fill="none"/>'
            f'</svg>'
            f'</div>'
        )

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        if top_driver:
            _parts = top_driver.split(" \u2014 ", 1)
            _main  = _parts[0]
            _sub   = _parts[1] if len(_parts) > 1 else ""
            _sub_html = f'<div class="hp2-driver-sub">{_sub}</div>' if _sub else ""
            driver_pill = (
                f'<div class="hp2-driver-pill">'
                f'<div class="hp2-driver-pill-icon">'
                f'<svg width="14" height="14" viewBox="0 0 24 24" fill="none"'
                f' stroke="{label_color}" stroke-width="2.5"'
                f' stroke-linecap="round" stroke-linejoin="round">'
                f'<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/>'
                f'<circle cx="12" cy="10" r="3"/>'
                f'</svg>'
                f'</div>'
                f'<div>'
                f'<div class="hp2-driver-val">{_main}</div>'
                f'{_sub_html}'
                f'</div>'
                f'</div>'
            )
        else:
            driver_pill = (
                '<div style="color:#374151;font-size:0.85rem;">'
                'Score components still loading\u2026</div>'
            )

        _hmd(
            f'<div class="hp2-driver-card">'
            f'<div>'
            f'<div class="hp2-driver-lbl">Top Score Driver</div>'
            f'<div class="hp2-driver-desc">'
            f'Primary factor influencing the current health score'
            f'</div>'
            f'</div>'
            f'{driver_pill}'
            f'</div>'
        )

    # ══════════════════════════════════════════════════════════════════
    # SECTION 2 — PERFORMANCE PILLARS
    # ══════════════════════════════════════════════════════════════════
    _hmd(
        '<div class="hp2-section-hdr">'
        '<span class="hp2-section-hdr-text">Performance Pillars</span>'
        '<span class="hp2-section-hdr-line"></span>'
        '</div>'
    )

    p1, p2, p3 = st.columns(3)

    with p1:
        _hmd(
            f'<div class="hp2-pillar hp2-pillar-analytics">'
            f'<div class="hp2-pillar-glow"></div>'
            f'<div class="hp2-pillar-hdr">'
            f'<span class="hp2-pillar-title">'
            f'<div class="hp2-icon-wrap">{_I_CHART}</div>'
            f'Analytics'
            f'</span>'
            f'</div>'
            f'<div class="hp2-metric-2col">'
            f'<div>'
            f'<div class="hp2-metric-lbl">TACOS '
            f'<span class="hp2-metric-lbl-note">vs {tacos_tgt_str}</span></div>'
            f'<div class="{tacos_cls}">{tacos_val}</div>'
            f'</div>'
            f'<div>'
            f'<div class="hp2-metric-lbl">Organic Share</div>'
            f'<div class="hp2-val">{org_str}</div>'
            f'</div>'
            f'</div>'
            f'</div>'
        )
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button(
            "\u2192  Account Overview",
            key="hp2_nav_analytics",
            width='stretch',
        ):
            st.session_state["_nav_loading"] = True
            st.session_state["current_module"] = "performance"
            st.rerun()

    with p2:
        _hmd(
            f'<div class="hp2-pillar hp2-pillar-optimizer">'
            f'<div class="hp2-pillar-glow"></div>'
            f'<div class="hp2-pillar-hdr">'
            f'<span class="hp2-pillar-title">'
            f'<div class="hp2-icon-wrap">{_I_ZAP}</div>'
            f'Optimizer'
            f'</span>'
            f'</div>'
            f'<div class="hp2-metric-2col">'
            f'<div>'
            f'<div class="hp2-metric-lbl">Total Actions</div>'
            f'<div class="hp2-val">{total_act_str}</div>'
            f'</div>'
            f'<div>'
            f'<div class="hp2-metric-lbl">Last Run</div>'
            f'<div class="hp2-val-sm">{last_run_str}</div>'
            f'</div>'
            f'</div>'
            f'</div>'
        )
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button(
            "\u2192  Optimizer",
            key="hp2_nav_optimizer",
            width='stretch',
        ):
            st.session_state["_nav_loading"] = True
            st.session_state["current_module"] = "optimizer"
            st.rerun()

    with p3:
        _hmd(
            f'<div class="hp2-pillar hp2-pillar-impact">'
            f'<div class="hp2-pillar-glow"></div>'
            f'<div class="hp2-pillar-hdr">'
            f'<span class="hp2-pillar-title">'
            f'<div class="hp2-icon-wrap">{_I_TARGET}</div>'
            f'Impact &amp; Results'
            f'</span>'
            f'</div>'
            f'<div class="hp2-metric-2col">'
            f'<div>'
            f'<div class="hp2-metric-lbl">Attributed 30D</div>'
            f'<div class="hp2-val" style="font-size:1.35rem;">{impact_str}</div>'
            f'</div>'
            f'<div>'
            f'<div class="hp2-metric-lbl">Win Rate</div>'
            f'<div class="{win_cls}">{win_str}</div>'
            f'</div>'
            f'</div>'
            f'</div>'
        )
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button(
            "\u2192  Impact & Results",
            key="hp2_nav_impact",
            width='stretch',
        ):
            st.session_state["_nav_loading"] = True
            st.session_state["current_module"] = "impact_v2"
            st.rerun()

    # ══════════════════════════════════════════════════════════════════
    # SECTION 3 — INTELLIGENCE BRIEFING
    # ══════════════════════════════════════════════════════════════════
    _hmd(
        '<div class="hp2-section-hdr">'
        '<span class="hp2-section-hdr-text">Intelligence Briefing</span>'
        '<span class="hp2-section-hdr-line"></span>'
        '</div>'
    )

    briefing = generate_deterministic_briefing(metrics_bundle)
    _hmd(f'<div class="hp2-exec-banner">{briefing}</div>')

    if cached_analysis:
        sections = parse_analysis_sections(cached_analysis)
        if sections:
            achievements = sections.get("key_achievements", [])
            monitor_list = sections.get("areas_to_monitor", [])
            actions_list = sections.get("recommended_actions", [])

            def _ai_items(items: list) -> str:
                return "".join(
                    f'<div class="hp2-ai-item">'
                    f'<div class="hp2-ai-dot"></div>'
                    f'<p class="hp2-ai-text">{item}</p>'
                    f'</div>'
                    for item in items
                )

            ai1, ai2, ai3 = st.columns(3)

            with ai1:
                _hmd(
                    f'<div class="hp2-ai-card hp2-ai-achievements">'
                    f'<div class="hp2-ai-hdr">'
                    f'<div class="hp2-ai-icon-wrap">{_I_CHECK}</div>'
                    f'<span class="hp2-ai-title">Key Achievements</span>'
                    f'</div>'
                    f'<div class="hp2-ai-items">{_ai_items(achievements)}</div>'
                    f'</div>'
                )

            with ai2:
                _hmd(
                    f'<div class="hp2-ai-card hp2-ai-monitor">'
                    f'<div class="hp2-ai-hdr">'
                    f'<div class="hp2-ai-icon-wrap">{_I_EYE}</div>'
                    f'<span class="hp2-ai-title">Areas to Monitor</span>'
                    f'</div>'
                    f'<div class="hp2-ai-items">{_ai_items(monitor_list)}</div>'
                    f'</div>'
                )

            with ai3:
                _hmd(
                    f'<div class="hp2-ai-card hp2-ai-actions">'
                    f'<div class="hp2-ai-hdr">'
                    f'<div class="hp2-ai-icon-wrap">{_I_TARGET}</div>'
                    f'<span class="hp2-ai-title">Recommended Actions</span>'
                    f'</div>'
                    f'<div class="hp2-ai-items">{_ai_items(actions_list)}</div>'
                    f'</div>'
                )

        else:
            _hmd(
                f'<div class="hp2-exec-banner"'
                f' style="border-left-color:rgba(16,185,129,0.55);">'
                f'{_I_SPARK}&ensp;{cached_analysis}'
                f'</div>'
            )

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("Regenerate Analysis", key="hp2_regen_llm"):
            del st.session_state[cache_key]
            st.rerun()

    else:
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        if st.button(
            "Generate Deep Analysis",
            key="hp2_gen_llm",
            type="primary",
            help="Produces Key Achievements, Areas to Monitor, and Recommended Actions using AI.",
        ):
            with st.spinner("Generating strategic analysis\u2026"):
                ctx  = format_llm_context(metrics_bundle)
                text = call_homepage_llm(ctx, account_name=account_name)
                st.session_state[cache_key] = text
            st.rerun()
