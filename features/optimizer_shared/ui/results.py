import streamlit as st
import pandas as pd
from datetime import datetime, date
from .components import render_metric_card
from .charts import render_spend_reallocation_chart, render_action_distribution_chart
from utils.formatters import get_account_currency, format_currency, dataframe_to_excel
from features.optimizer_shared.ui.campaign_panel import render_tier1_campaign_panel


def _save_run_to_history(results: dict) -> tuple[str, str]:
    """
    Save current optimizer results to actions_log.
    Returns (level, message) where level in {"success", "warning", "info", "error"}.
    """
    from features.optimizer_shared.logging import log_optimization_events, flush_pending_actions_to_db
    from app_core.db_manager import get_db_manager

    test_mode = bool(st.session_state.get("test_mode", False))
    client_id = st.session_state.get("active_account_id", "")
    report_date = date.today().isoformat()

    if not client_id:
        return "error", "Cannot save: no active account selected."

    loggable = {
        "neg_kw": results.get("neg_kw", pd.DataFrame()),
        "neg_pt": results.get("neg_pt", pd.DataFrame()),
        "harvest": results.get("harvest", pd.DataFrame()),
        "bids_exact": results.get("bids_exact", pd.DataFrame()),
        "bids_pt": results.get("bids_pt", pd.DataFrame()),
        "bids_agg": results.get("bids_agg", pd.DataFrame()),
        "bids_auto": results.get("bids_auto", pd.DataFrame()),
    }

    queued = log_optimization_events(loggable, client_id, report_date)
    if queued <= 0:
        return "info", "No actions to save from this run."

    saved = flush_pending_actions_to_db(test_mode=test_mode)
    batch_id = st.session_state.get("last_saved_batch_id") or st.session_state.get("last_queued_batch_id", "n/a")

    # Optional verification when DB manager exposes batch read API (SQLite path).
    verified_rows = None
    try:
        db = get_db_manager(test_mode)
        if hasattr(db, "get_actions_by_batch"):
            verified_rows = len(db.get_actions_by_batch(batch_id))
    except Exception:
        verified_rows = None

    st.session_state["last_save_confirmation"] = {
        "saved": int(saved),
        "queued": int(queued),
        "batch_id": batch_id,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "verified_rows": verified_rows,
    }

    if saved <= 0:
        return "error", "Save failed: 0 rows were written to actions_log."
    if saved != queued:
        return "warning", f"Saved {saved} of {queued} queued actions (batch {batch_id})."
    return "success", f"Saved {saved} actions to history (batch {batch_id})."


def _to_numeric_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[col], errors="coerce").fillna(0)


def _compute_harvest_avg_cvr_pct(harvest: pd.DataFrame) -> float:
    """Robust CVR computation for harvest cards."""
    if harvest is None or harvest.empty:
        return 0.0

    if "Orders" in harvest.columns and "Clicks" in harvest.columns:
        orders = _to_numeric_series(harvest, "Orders").sum()
        clicks = _to_numeric_series(harvest, "Clicks").sum()
        if clicks > 0:
            return float((orders / clicks) * 100)

    for cvr_col in ("CVR", "CR7", "Conversion Rate"):
        if cvr_col in harvest.columns:
            cvr_vals = pd.to_numeric(harvest[cvr_col], errors="coerce").dropna()
            if not cvr_vals.empty:
                avg_val = float(cvr_vals.mean())
                return avg_val * 100 if avg_val <= 1 else avg_val
    return 0.0


def _render_sub_kpi_row(items: list[dict]) -> None:
    cards_html = []
    for item in items:
        label = item.get("label", "")
        value = item.get("value", "")
        subtext = item.get("subtext", "")
        accent = item.get("accent", "#94a3b8")
        cards_html.append(
            f'<div class="opt-sub-kpi">'
            f'<div class="opt-sub-kpi-label">{label}</div>'
            f'<div class="opt-sub-kpi-value">{value}</div>'
            f'<div class="opt-sub-kpi-sub"><span style="color:{accent};">{subtext}</span></div>'
            f'</div>'
        )
    st.markdown(f'<div class="opt-sub-kpi-grid">{"".join(cards_html)}</div>', unsafe_allow_html=True)


def _render_overview_breakdown(rows: list[dict]) -> None:
    row_html = []
    for row in rows:
        label = row.get("label", "")
        count = row.get("count", 0)
        impact = row.get("impact", "")
        share_pct = float(row.get("share_pct", 0.0))
        fill = max(0.0, min(100.0, share_pct))
        row_html.append(
            f'<div class="opt-overview-row">'
            f'<div>'
            f'<div class="opt-overview-label">{label}</div>'
            f'<div class="opt-overview-track"><div class="opt-overview-fill" style="width:{fill:.1f}%"></div></div>'
            f'</div>'
            f'<div class="opt-overview-count">{count:,}</div>'
            f'<div class="opt-overview-impact">{impact}</div>'
            f'<div class="opt-overview-status">Ready</div>'
            f'</div>'
        )

    st.markdown(
        (
            '<div class="opt-overview-shell">'
            '<div class="opt-overview-head">'
            '<div>Category</div>'
            '<div style="text-align:right;">Count</div>'
            '<div style="text-align:right;">Impact</div>'
            '<div style="text-align:right;">Status</div>'
            '</div>'
            f"{''.join(row_html)}"
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def _compute_intelligence_layer_counts(all_bids: pd.DataFrame) -> dict:
    cooldown_count = 0
    inventory_count = 0
    halo_count = 0
    organic_dom_count = 0

    if all_bids is not None and not all_bids.empty:
        if "Reason" in all_bids.columns:
            cooldown_count = int(
                all_bids["Reason"].astype(str).str.contains("cooldown", case=False, na=False).sum()
            )

        all_flags = []
        if "Intelligence_Flags" in all_bids.columns:
            series = all_bids["Intelligence_Flags"].replace("", pd.NA).dropna()
            for raw in series:
                all_flags.extend([x.strip() for x in str(raw).split(",") if x.strip()])

        if all_flags:
            flag_counts = pd.Series(all_flags).value_counts()
            inventory_count = int(flag_counts.get("INVENTORY_RISK", 0))
            halo_count = int(flag_counts.get("HALO_ACTIVE", 0))
            organic_dom_count = int(
                flag_counts.get("ORGANIC_CVR_DOMINANT", 0) + flag_counts.get("CANNIBALIZE_RISK", 0)
            )

    # Phase 4 cascade flag counts (from Intelligence_Flags column)
    cascade_counts = {
        "camp_drag": 0, "camp_underopt": 0, "camp_amp": 0,
        "zero_conv_block": 0, "zero_conv_watch": 0,
        "cut_quad": 0, "acct_declining": 0, "high_conviction": 0,
    }
    if not all_bids.empty and "Intelligence_Flags" in all_bids.columns:
        all_flags_cascade = []
        series = all_bids["Intelligence_Flags"].replace("", pd.NA).dropna()
        for raw in series:
            all_flags_cascade.extend([x.strip() for x in str(raw).split(",") if x.strip()])
        if all_flags_cascade:
            fc = pd.Series(all_flags_cascade).value_counts()
            cascade_counts["camp_drag"]       = int(fc.get("CAMPAIGN_DRAG", 0))
            cascade_counts["camp_underopt"]   = int(fc.get("CAMPAIGN_UNDEROPTIMIZED", 0))
            cascade_counts["camp_amp"]        = int(fc.get("CAMPAIGN_AMPLIFIER", 0))
            cascade_counts["zero_conv_block"] = int(fc.get("ZERO_CONV_BLOCK", 0))
            cascade_counts["zero_conv_watch"] = int(fc.get("ZERO_CONV_WATCH", 0))
            cascade_counts["cut_quad"]        = int(fc.get("CUT_QUADRANT", 0))
            cascade_counts["acct_declining"]  = int(fc.get("ACCOUNT_DECLINING", 0))
            cascade_counts["high_conviction"] = int(fc.get("HIGH_CONVICTION_PROMOTE", 0))

    return {
        "cooldown_count": cooldown_count,
        "inventory_count": inventory_count,
        "halo_count": halo_count,
        "organic_dom_count": organic_dom_count,
        "has_commerce": bool(st.session_state.get("v21_commerce_fetch_ok", False)),
        "cascade_counts": cascade_counts,
    }


def _render_intelligence_layer_hero(all_bids: pd.DataFrame) -> None:
    intel = _compute_intelligence_layer_counts(all_bids)
    has_commerce = intel["has_commerce"]
    cc = intel["cascade_counts"]

    cooldown = intel["cooldown_count"]
    inventory = intel["inventory_count"] if has_commerce else 0
    halo = intel["halo_count"] if has_commerce else 0
    organic = intel["organic_dom_count"] if has_commerce else 0

    protected_total = cooldown + inventory + halo + organic
    subtitle = (
        "AI safeguards actively protected bid decisions using cooldown, inventory, halo, and organic conversion signals."
        if has_commerce
        else "SP-API not connected - inventory and organic signals unavailable."
    )

    cascade_total = sum(cc.values())
    cascade_html = ""
    if cascade_total > 0:
        cascade_html = f"""
        <div style="margin-top:16px; padding-top:16px; border-top:1px solid rgba(255,255,255,0.06);">
            <div style="font-size:11px; font-weight:600; color:#64748b; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:10px;">Phase 4 PPC Cascade</div>
            <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:8px;">
                <div style="background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.15); border-radius:8px; padding:10px;">
                    <div style="font-size:11px; color:#94a3b8;">Campaign Drag</div>
                    <div style="font-size:20px; font-weight:700; color:#f87171;">{cc["camp_drag"]}</div>
                    <div style="font-size:10px; color:#64748b;">50% bid dampen</div>
                </div>
                <div style="background:rgba(251,191,36,0.08); border:1px solid rgba(251,191,36,0.15); border-radius:8px; padding:10px;">
                    <div style="font-size:11px; color:#94a3b8;">Underoptimized</div>
                    <div style="font-size:20px; font-weight:700; color:#fbbf24;">{cc["camp_underopt"]}</div>
                    <div style="font-size:10px; color:#64748b;">Flagged for review</div>
                </div>
                <div style="background:rgba(34,197,94,0.08); border:1px solid rgba(34,197,94,0.15); border-radius:8px; padding:10px;">
                    <div style="font-size:11px; color:#94a3b8;">Amplifier</div>
                    <div style="font-size:20px; font-weight:700; color:#4ade80;">{cc["camp_amp"]}</div>
                    <div style="font-size:10px; color:#64748b;">+15% throttle loosened</div>
                </div>
                <div style="background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.15); border-radius:8px; padding:10px;">
                    <div style="font-size:11px; color:#94a3b8;">Zero-Conv Block</div>
                    <div style="font-size:20px; font-weight:700; color:#f87171;">{cc["zero_conv_block"]}</div>
                    <div style="font-size:10px; color:#64748b;">Confirmed bleed blocked</div>
                </div>
                <div style="background:rgba(148,163,184,0.08); border:1px solid rgba(148,163,184,0.15); border-radius:8px; padding:10px;">
                    <div style="font-size:11px; color:#94a3b8;">Zero-Conv Watch</div>
                    <div style="font-size:20px; font-weight:700; color:#94a3b8;">{cc["zero_conv_watch"]}</div>
                    <div style="font-size:10px; color:#64748b;">Thin data, monitoring</div>
                </div>
                <div style="background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.15); border-radius:8px; padding:10px;">
                    <div style="font-size:11px; color:#94a3b8;">Cut Quadrant</div>
                    <div style="font-size:20px; font-weight:700; color:#f87171;">{cc["cut_quad"]}</div>
                    <div style="font-size:10px; color:#64748b;">70% bid dampen</div>
                </div>
                <div style="background:rgba(251,191,36,0.08); border:1px solid rgba(251,191,36,0.15); border-radius:8px; padding:10px;">
                    <div style="font-size:11px; color:#94a3b8;">Acct Declining</div>
                    <div style="font-size:20px; font-weight:700; color:#fbbf24;">{cc["acct_declining"]}</div>
                    <div style="font-size:10px; color:#64748b;">20% account dampen</div>
                </div>
                <div style="background:rgba(56,189,248,0.08); border:1px solid rgba(56,189,248,0.15); border-radius:8px; padding:10px;">
                    <div style="font-size:11px; color:#94a3b8;">High Conviction</div>
                    <div style="font-size:20px; font-weight:700; color:#38bdf8;">{cc["high_conviction"]}</div>
                    <div style="font-size:10px; color:#64748b;">+10% throttle loosened</div>
                </div>
            </div>
        </div>
        """

    st.markdown(
        f"""
        <div class="intel-hero">
            <div class="intel-hero-head">
                <div class="intel-eyebrow">Decision Intelligence</div>
                <div class="intel-title">Intelligence Layer</div>
                <div class="intel-subtitle">{subtitle}</div>
            </div>
            <div class="intel-grid">
                <div class="intel-kpi">
                    <div class="intel-kpi-label">Cooldown Pauses</div>
                    <div class="intel-kpi-value">{cooldown}</div>
                    <div class="intel-kpi-note">Actions held to prevent over-optimization</div>
                </div>
                <div class="intel-kpi">
                    <div class="intel-kpi-label">Inventory Safeguards</div>
                    <div class="intel-kpi-value">{inventory if has_commerce else "—"}</div>
                    <div class="intel-kpi-note">Bid increases blocked due to low stock risk</div>
                </div>
                <div class="intel-kpi">
                    <div class="intel-kpi-label">Halo Protections</div>
                    <div class="intel-kpi-value">{halo if has_commerce else "—"}</div>
                    <div class="intel-kpi-note">Actions adjusted to protect blended efficiency</div>
                </div>
                <div class="intel-kpi">
                    <div class="intel-kpi-label">Organic-Dominant Holds</div>
                    <div class="intel-kpi-value">{organic if has_commerce else "—"}</div>
                    <div class="intel-kpi-note">Actions held where organic conversion dominates</div>
                </div>
            </div>
            <div class="intel-impact">Total intelligence-guided interventions: <strong>{protected_total if has_commerce else cooldown}</strong></div>
            {cascade_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_results_dashboard(results: dict):
    """
    Renders the post-optimization results dashboard.

    Args:
        results (dict): Dictionary containing optimization results (df, harvest, neg_kw, etc.)
    """
    # Backward compatibility for any older trigger path.
    if st.session_state.pop("trigger_save", False):
        level, message = _save_run_to_history(results)
        if level == "success":
            st.success(f"✅ {message}")
        elif level == "warning":
            st.warning(f"⚠️ {message}")
        elif level == "info":
            st.info(message)
        else:
            st.error(f"❌ {message}")

    # 1. Extract Data
    # === PREMIUM STYLES ===
    st.markdown("""
    <style>
    /* Global Background & Typography */
    .stApp {
        background-color: #0a0f1a;
        background-image: 
            radial-gradient(at 0% 0%, rgba(45, 212, 191, 0.03) 0px, transparent 50%),
            radial-gradient(at 100% 0%, rgba(6, 182, 212, 0.03) 0px, transparent 50%);
    }

    /* Glassmorphic Card Base (Linear-style) */
    .glass-card {
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(10px);
        margin-bottom: 24px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .glass-card:hover {
        border-color: rgba(255, 255, 255, 0.08);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
    }

    /* Save Run Hero Section - Special Glow */
    .save-run-container {
        position: relative;
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(45, 212, 191, 0.2);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 40px;
        box-shadow: 0 0 0 1px rgba(45, 212, 191, 0.1), 0 10px 40px rgba(0, 0, 0, 0.4);
        overflow: hidden;
    }

    /* Subtle pulsing accent line for Save Run */
    .save-run-container::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        background: linear-gradient(to bottom, #2dd4bf, #06b6d4);
        box-shadow: 0 0 15px rgba(45, 212, 191, 0.6);
    }

    /* Typography Hierarchy */
    h2, h3, h4 {
        color: #f8fafc !important;
        font-family: 'Inter', sans-serif;
        letter-spacing: -0.01em;
    }

    .metric-label {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #64748b;
        margin-bottom: 8px;
    }

    .metric-value-hero {
        font-size: 32px;
        font-weight: 700;
        background: linear-gradient(135deg, #2dd4bf 0%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.02em;
        text-shadow: 0 10px 30px rgba(45, 212, 191, 0.2);
    }

    .metric-value-primary {
        font-size: 24px;
        font-weight: 600;
        color: #f1f5f9;
        letter-spacing: -0.01em;
    }

    .metric-subtext {
        font-size: 13px;
        color: #94a3b8;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 6px;
        margin-top: 4px;
    }

    /* Tabs - Pill Style */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }

    .stTabs [data-baseweb="tab"] {
        height: 40px;
        white-space: nowrap;
        background-color: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        color: #94a3b8;
        padding: 0 20px;
        font-size: 13px;
        font-weight: 500;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(45, 212, 191, 0.15) 0%, rgba(6, 182, 212, 0.1) 100%);
        border-color: rgba(45, 212, 191, 0.3);
        color: #2dd4bf;
        text-shadow: 0 0 20px rgba(45, 212, 191, 0.4);
    }

    .opt-tab-scope {
        display: none !important;
    }
    p:has(.opt-tab-scope) {
        display: none !important;
        margin: 0 !important;
    }

    div[data-testid="stVerticalBlock"]:has(.opt-tab-scope) div[data-testid="stHorizontalBlock"] .stButton > button[kind="secondary"] {
        border-radius: 9px !important;
        border: 1px solid rgba(148, 163, 184, 0.18) !important;
        background: linear-gradient(180deg, rgba(39, 49, 68, 0.92) 0%, rgba(24, 32, 48, 0.95) 100%) !important;
        color: #cbd5e1 !important;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 2px 7px rgba(2,6,23,0.32) !important;
        min-height: 52px !important;
    }
    div[data-testid="stVerticalBlock"]:has(.opt-tab-scope) div[data-testid="stHorizontalBlock"] .stButton > button[kind="secondary"]:hover {
        border-color: rgba(99, 102, 241, 0.35) !important;
        color: #e2e8f0 !important;
        transform: translateY(-1px) !important;
    }
    div[data-testid="stVerticalBlock"]:has(.opt-tab-scope) div[data-testid="stHorizontalBlock"] .stButton > button[kind="primary"] {
        border-radius: 9px !important;
        border: 1px solid rgba(255,255,255,0.14) !important;
        background: linear-gradient(180deg, rgba(79, 74, 102, 0.95) 0%, rgba(58, 53, 77, 0.97) 100%) !important;
        color: #e5e7eb !important;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 5px 12px rgba(2,6,23,0.4) !important;
        transform: translateY(-1px) !important;
        min-height: 52px !important;
    }

    .opt-sub-kpi-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
        margin: 8px 0 20px 0;
    }
    .opt-sub-kpi {
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.45) 0%, rgba(15, 23, 42, 0.45) 100%);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 12px;
        padding: 14px 16px;
        min-height: 102px;
    }
    .opt-sub-kpi-label {
        color: #94a3b8;
        font-size: 0.8rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 6px;
        font-weight: 600;
    }
    .opt-sub-kpi-value {
        color: #e2e8f0;
        font-size: 2.05rem;
        line-height: 1.05;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .opt-sub-kpi-sub {
        color: #94a3b8;
        font-size: 0.88rem;
        font-weight: 600;
    }

    .opt-overview-shell {
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 14px;
        overflow: hidden;
        background: linear-gradient(180deg, rgba(14, 20, 34, 0.9), rgba(11, 16, 28, 0.92));
        box-shadow: 0 8px 20px rgba(2, 6, 23, 0.34);
    }
    .opt-overview-head, .opt-overview-row {
        display: grid;
        grid-template-columns: 2fr 0.8fr 1fr 1fr;
        column-gap: 10px;
        align-items: center;
        padding: 12px 16px;
    }
    .opt-overview-head {
        background: linear-gradient(180deg, rgba(30, 41, 59, 0.85), rgba(22, 30, 46, 0.9));
        border-bottom: 1px solid rgba(148, 163, 184, 0.2);
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-size: 0.72rem;
        font-weight: 700;
    }
    .opt-overview-row {
        border-bottom: 1px solid rgba(51, 65, 85, 0.45);
    }
    .opt-overview-row:last-child {
        border-bottom: none;
    }
    .opt-overview-label {
        color: #e2e8f0;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .opt-overview-track {
        width: 100%;
        height: 6px;
        border-radius: 999px;
        background: rgba(51, 65, 85, 0.7);
        overflow: hidden;
    }
    .opt-overview-fill {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #22d3ee, #2dd4bf);
    }
    .opt-overview-count {
        color: #f1f5f9;
        font-weight: 800;
        font-size: 1.05rem;
        text-align: right;
    }
    .opt-overview-impact {
        color: #cbd5e1;
        font-size: 0.9rem;
        font-weight: 600;
        text-align: right;
    }
    .opt-overview-status {
        display: inline-flex;
        justify-content: center;
        align-items: center;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid rgba(45, 212, 191, 0.28);
        background: rgba(45, 212, 191, 0.14);
        color: #5eead4;
        font-size: 0.73rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        width: fit-content;
        justify-self: end;
    }

    .intel-hero {
        border: 1px solid rgba(56, 189, 248, 0.22);
        border-radius: 16px;
        background:
            radial-gradient(circle at 16% -20%, rgba(34, 211, 238, 0.20), transparent 45%),
            linear-gradient(145deg, rgba(8, 18, 36, 0.95), rgba(10, 16, 31, 0.95));
        padding: 18px;
        margin: 16px 0 18px 0;
        box-shadow: 0 8px 28px rgba(2, 6, 23, 0.45), inset 0 1px 0 rgba(255,255,255,0.04);
    }
    .intel-eyebrow {
        text-transform: uppercase;
        letter-spacing: 0.07em;
        font-size: 0.72rem;
        color: #67e8f9;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .intel-title {
        color: #e2e8f0;
        font-size: 1.28rem;
        font-weight: 800;
        margin-bottom: 4px;
    }
    .intel-subtitle {
        color: #94a3b8;
        font-size: 0.92rem;
        margin-bottom: 14px;
    }
    .intel-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
    }
    .intel-kpi {
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 12px;
        padding: 12px;
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.35), rgba(15, 23, 42, 0.38));
    }
    .intel-kpi-label {
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 0.72rem;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .intel-kpi-value {
        color: #e2e8f0;
        font-size: 1.9rem;
        line-height: 1;
        font-weight: 800;
        margin-bottom: 6px;
    }
    .intel-kpi-note {
        color: #9ca3af;
        font-size: 0.78rem;
        line-height: 1.35;
    }
    .intel-impact {
        margin-top: 12px;
        color: #cbd5e1;
        font-size: 0.9rem;
    }
    </style>
    """, unsafe_allow_html=True)
    harvest = results.get("harvest", pd.DataFrame())
    neg_kw = results.get("neg_kw", pd.DataFrame())
    neg_pt = results.get("neg_pt", pd.DataFrame())
    bids_ex = results.get("bids_exact", pd.DataFrame())
    bids_pt = results.get("bids_pt", pd.DataFrame())
    bids_agg = results.get("bids_agg", pd.DataFrame())
    bids_auto = results.get("bids_auto", pd.DataFrame())
    simulation = results.get("simulation", {})

    # Consolidate Bids
    direct_bids = pd.concat([bids_ex, bids_pt]) if not bids_ex.empty or not bids_pt.empty else pd.DataFrame()
    agg_bids = pd.concat([bids_agg, bids_auto]) if not bids_agg.empty or not bids_auto.empty else pd.DataFrame()

    all_bids = pd.concat([direct_bids, agg_bids]) if not direct_bids.empty or not agg_bids.empty else pd.DataFrame()

    # On-the-fly Tier 1 PAUSE filter — reads checkbox widget states directly (no re-run needed)
    _t1_recs = results.get("campaign_recs", pd.DataFrame())
    if not _t1_recs.empty and not all_bids.empty and "recommendation" in _t1_recs.columns and "campaign_name" in _t1_recs.columns:
        _pause_camp_names = set(_t1_recs.loc[_t1_recs["recommendation"] == "PAUSE", "campaign_name"].tolist())
        _camp_col = next((c for c in ["Campaign Name", "campaign_name"] if c in all_bids.columns), None)
        if _pause_camp_names and _camp_col:
            _checked_pauses = {c for c in _pause_camp_names if st.session_state.get(f"tier1_cb_{c}", False)}
            if _checked_pauses:
                all_bids = all_bids[~all_bids[_camp_col].isin(_checked_pauses)].copy()

    # 2. Calculate Display Metrics (Aggregation only - NO new logic)
    action_count = len(harvest) + len(neg_kw) + len(neg_pt) + len(all_bids)

    bid_count = len(all_bids)
    neg_count = len(neg_kw) + len(neg_pt)
    harv_count = len(harvest)

    # Calculate Savings / Waste Prevented
    neg_spend_saving = 0
    if not neg_kw.empty and "Spend" in neg_kw.columns:
        neg_spend_saving += neg_kw["Spend"].sum()
    if not neg_pt.empty and "Spend" in neg_pt.columns:
        neg_spend_saving += neg_pt["Spend"].sum()

    # Calculate bid impact
    bid_saving = 0
    reallocated = 0
    net_velocity = 0

    if not all_bids.empty and "New Bid" in all_bids.columns and "Clicks" in all_bids.columns:
        # Determine which column to use for current bid
        current_bid_col = None
        if "Current Bid" in all_bids.columns:
            current_bid_col = "Current Bid"
        elif "CPC" in all_bids.columns:
            current_bid_col = "CPC"

        if current_bid_col:
            # Simple projection: (Old Bid - New Bid) * Clicks
            all_bids["_diff"] = (all_bids[current_bid_col] - all_bids["New Bid"]) * all_bids["Clicks"]
            bid_saving = all_bids[all_bids["_diff"] > 0]["_diff"].sum()
            reallocated = abs(all_bids[all_bids["_diff"] < 0]["_diff"].sum())
            
            # Net Velocity Calculation
            velocity_series = (all_bids["New Bid"] - all_bids[current_bid_col]) * all_bids["Clicks"]
            net_velocity = velocity_series.sum()

    total_waste_prevented = neg_spend_saving + bid_saving

    # Calculate Total Spend Reference (Moved Up for Efficiency Calc)
    total_spend_ref = 0
    if "df" in results and isinstance(results["df"], pd.DataFrame) and "Spend" in results["df"].columns:
        total_spend_ref = results["df"]["Spend"].sum()

    # Calculate Total Impact
    total_impact = neg_spend_saving + bid_saving - reallocated
    
    # Calculate Efficiency % (Priority: Forecasted ROAS Lift)
    # User Request: "efficiency gain should be based on the forecasted ROAS"
    impact_pct = 0
    used_simulation_metric = False

    if simulation and "scenarios" in simulation:
        scenarios = simulation["scenarios"]
        
        # Structure check: is it 'current'/'expected' or 'balanced'/'aggressive'?
        # Assuming typical structure where "expected" is the chosen outcome
        current_metrics = scenarios.get("current", {})
        expected_metrics = scenarios.get("expected", {})
        
        # If 'expected' missing, try 'balanced' as default
        if not expected_metrics:
            expected_metrics = scenarios.get("balanced", {})

        current_roas = float(current_metrics.get("roas", 0) or 0)
        expected_roas = float(expected_metrics.get("roas", 0) or 0)

        if current_roas > 0 and expected_roas > 0:
            impact_pct = (expected_roas - current_roas) / current_roas
            used_simulation_metric = True

    # Fallback: if simulation didn't work, calculate from spend share
    if not used_simulation_metric:
        if total_spend_ref > 0:
            impact_pct = (total_impact / total_spend_ref)

    # 3. Save Run Tile (Refactored to include buttons inside)
    # Using specific container for CSS targeting
    # 3. Save Run Tile (Refactored to include buttons inside)
    # Using specific container for CSS targeting
    # 3. Save Run Tile - Native Layout Implementation
    st.markdown("""
    <style>
    /* Target ONLY the innermost container that holds our marker */
    /* This prevents parents from also getting the style */
    div[data-testid="stVerticalBlock"]:has(.save-run-marker):not(:has(div[data-testid="stVerticalBlock"])) {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(45, 212, 191, 0.2) !important;
        border-radius: 16px !important;
        padding: 24px !important;
        margin-bottom: 40px;
        box-shadow: 0 0 0 1px rgba(45, 212, 191, 0.1), 0 10px 40px rgba(0, 0, 0, 0.4);
        overflow: hidden;
        position: relative;
    }

    /* Accent line pseudo-element */
    div[data-testid="stVerticalBlock"]:has(.save-run-marker):not(:has(div[data-testid="stVerticalBlock"]))::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        background: linear-gradient(to bottom, #2dd4bf, #06b6d4);
        box-shadow: 0 0 15px rgba(45, 212, 191, 0.6);
        z-index: 1;
    }
    
    /* Ensure content is above background */
    div[data-testid="stVerticalBlock"]:has(.save-run-marker) > div {
        position: relative;
        z-index: 2;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        # Marker to trigger the CSS styling on this specific container
        st.markdown('<span class="save-run-marker"></span>', unsafe_allow_html=True)
        
        c_content, c_btns = st.columns([3, 1], gap="large")
        
        with c_content:
            st.markdown("""
            <div style="display: flex; gap: 16px; align-items: flex-start;">
                <div style="
                    width: 48px; height: 48px; 
                    background: radial-gradient(circle at center, rgba(45, 212, 191, 0.2), transparent 70%); 
                    border: 1px solid rgba(45, 212, 191, 0.3);
                    border-radius: 12px; 
                    display: flex; align-items: center; justify-content: center; 
                    font-size: 20px; color: #2dd4bf; 
                    box-shadow: 0 0 15px rgba(45, 212, 191, 0.2);
                    flex-shrink: 0;">
                    🏁
                </div>
                <div>
                    <h3 style="margin: 0 0 8px 0; font-size: 18px; font-weight: 600; letter-spacing: -0.01em; color: #f8fafc;">Save This Optimization Run</h3>
                    <p style="color: #cbd5e1; margin: 0; font-size: 15px; line-height: 1.5; font-weight: 600;">
                        After downloading your files, save this run to track actual vs. predicted performance in Impact Analysis.
                    </p>
                    <div style="
                        display: inline-flex; align-items: center; gap: 6px;
                        background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.2);
                        color: #fbbf24; padding: 4px 10px; border-radius: 6px; 
                        font-size: 12px; font-weight: 500; margin-top: 12px;">
                        ⚠️ Unsaved runs cannot be measured
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            save_meta = st.session_state.get("last_save_confirmation")
            if save_meta:
                if isinstance(save_meta.get("verified_rows"), int) and save_meta.get("verified_rows", 0) > 0:
                    st.caption(
                        f"Saved {save_meta['saved']} actions at {save_meta['saved_at']} "
                        f"(batch {save_meta['batch_id']}, verified rows: {save_meta['verified_rows']})."
                    )
                else:
                    st.caption(
                        f"Saved {save_meta['saved']} actions at {save_meta['saved_at']} "
                        f"(batch {save_meta['batch_id']})."
                    )

        with c_btns:
            # Buttons are now natively in the same container/row
            st.markdown('<div style="height: 4px"></div>', unsafe_allow_html=True) # Visual alignment tweak
            if st.button("💾 Save to History", type="primary", use_container_width=True, key="btn_save_run_hero"):
                level, message = _save_run_to_history(results)
                if level == "success":
                    st.success(f"✅ {message}")
                elif level == "warning":
                    st.warning(f"⚠️ {message}")
                elif level == "info":
                    st.info(message)
                else:
                    st.error(f"❌ {message}")
            
            st.markdown('<div style="height: 6px"></div>', unsafe_allow_html=True)
            
            if st.button("🔄 Rerun Optimizer", type="secondary", use_container_width=True, key="btn_rerun_opt"):
                if 'optimizer_results_refactored' in st.session_state:
                    del st.session_state['optimizer_results_refactored']
                st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Tier 1 Campaign Intelligence panel — shown between Save Run and Tier 2 summary
    # Results already reflect any applied Tier 1 exclusions (optimizer re-ran on filtered df)
    st.markdown(
        "<div style='display:flex;align-items:center;gap:10px;margin:8px 0 14px 0;'>"
        "<div style='width:3px;height:18px;background:linear-gradient(to bottom,#67e8f9,#06b6d4);"
        "border-radius:2px;flex-shrink:0;'></div>"
        "<span style='color:#67e8f9;font-size:0.72rem;font-weight:700;letter-spacing:0.1em;"
        "text-transform:uppercase;'>Tier 1 Optimization</span>"
        "<span style='color:#475569;font-size:0.72rem;margin-left:2px;'>"
        "Campaign-level budget &amp; scaling actions</span>"
        "<div style='flex:1;height:1px;background:rgba(51,65,85,0.5);'></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    _campaign_recs = results.get("campaign_recs", pd.DataFrame())
    render_tier1_campaign_panel(_campaign_recs)

    # 4. Tier 2 Section Header
    st.markdown(
        "<div style='display:flex;align-items:center;gap:10px;margin:20px 0 14px 0;'>"
        "<div style='width:3px;height:18px;background:linear-gradient(to bottom,#2dd4bf,#38bdf8);"
        "border-radius:2px;flex-shrink:0;'></div>"
        "<span style='color:#2dd4bf;font-size:0.72rem;font-weight:700;letter-spacing:0.1em;"
        "text-transform:uppercase;'>Tier 2 Optimization</span>"
        "<span style='color:#475569;font-size:0.72rem;margin-left:2px;'>"
        "Keyword-level bid, negative &amp; harvest actions</span>"
        "<div style='flex:1;height:1px;background:rgba(51,65,85,0.5);'></div>"
        "<span style='color:#64748b;font-size:0.7rem;'>Last run: Just now</span>"
        "<span style='background:rgba(34,197,94,0.1);color:#22c55e;padding:3px 10px;"
        "border-radius:100px;font-size:0.68rem;font-weight:600;'>✓ Complete</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    # 5. Metrics Grid (match the same KPI card format used under tabs)
    # Calculate bid increase/decrease counts safely
    bid_inc_count = 0
    bid_dec_count = 0
    if not all_bids.empty and "New Bid" in all_bids.columns:
        if "Current Bid" in all_bids.columns:
            bid_inc_count = len(all_bids[all_bids['New Bid'] > all_bids['Current Bid']])
            bid_dec_count = len(all_bids[all_bids['New Bid'] < all_bids['Current Bid']])
        elif "CPC" in all_bids.columns:
            bid_inc_count = len(all_bids[all_bids['New Bid'] > all_bids['CPC']])
            bid_dec_count = len(all_bids[all_bids['New Bid'] < all_bids['CPC']])

    # Get currency symbol for other cards
    currency = get_account_currency()
    eff_color = "#2dd4bf" if impact_pct > 0 else "#f59e0b"
    velocity_color = "#fbbf24" if net_velocity > 0 else "#22c55e"  # Orange if invest, Green if save
    velocity_label = f"+{currency}{net_velocity:,.0f} Invest" if net_velocity > 0 else f"-{currency}{abs(net_velocity):,.0f} Savings"
    harvest_value = _to_numeric_series(harvest, "Sales").sum() if "Sales" in harvest.columns else 0

    _render_sub_kpi_row([
        {"label": "Projected Efficiency", "value": f"{impact_pct:+.1%}", "subtext": "Forecasted ROAS Lift", "accent": eff_color},
        {"label": "Bid Actions", "value": f"{bid_count:,}", "subtext": velocity_label, "accent": velocity_color},
        {"label": "Negatives", "value": f"{neg_count:,}", "subtext": f"{currency}{neg_spend_saving:,.0f} Waste Blocked", "accent": "#60a5fa"},
        {"label": "Harvest", "value": f"{harv_count:,}", "subtext": f"{currency}{harvest_value:,.0f} Sales Vol", "accent": "#38bdf8"},
    ])

    st.markdown("<br>", unsafe_allow_html=True)

    # 6. Visual Impact Analysis (Header Removed)
    vc1, vc2 = st.columns([1.5, 1])

    # Calculate total spend reference
    total_spend_ref = 500000  # Default/Fallback
    if "df" in results and isinstance(results["df"], pd.DataFrame) and "Spend" in results["df"].columns:
        total_spend_ref = results["df"]["Spend"].sum()

    with vc1:
        render_spend_reallocation_chart(total_spend_ref, neg_spend_saving, bid_saving, reallocated, currency)
    with vc2:
        render_action_distribution_chart(action_count, bid_count, neg_count, harv_count)

    _render_intelligence_layer_hero(all_bids)

    st.divider()

    # 7. Tab Navigation
    tabs = ["Overview", "Negatives", "Bids", "Harvest", "Audit", "Forecast", "Downloads"]

    # Active tab state handling
    if "active_opt_tab" not in st.session_state:
        st.session_state["active_opt_tab"] = "Overview"

    with st.container():
        st.markdown('<span class="opt-tab-scope"></span>', unsafe_allow_html=True)
        t_cols = st.columns(len(tabs), gap="small")
        for i, tab in enumerate(tabs):
            with t_cols[i]:
                if st.button(
                    tab,
                    key=f"tab_{tab}",
                    use_container_width=True,
                    type="primary" if st.session_state["active_opt_tab"] == tab else "secondary",
                ):
                    st.session_state["active_opt_tab"] = tab
                    st.rerun()

    # 8. Tab Content
    active = st.session_state["active_opt_tab"]

    if active == "Overview":
        st.markdown("### Overview")
        st.caption("Decision mix and weighted contribution across optimization actions")

        if not all_bids.empty or not neg_kw.empty or not neg_pt.empty or not harvest.empty:
            neg_kw_spend = _to_numeric_series(neg_kw, "Spend").sum() if not neg_kw.empty and "Spend" in neg_kw.columns else 0
            neg_pt_spend = _to_numeric_series(neg_pt, "Spend").sum() if not neg_pt.empty and "Spend" in neg_pt.columns else 0
            harvest_sales = _to_numeric_series(harvest, "Sales").sum() if not harvest.empty and "Sales" in harvest.columns else 0
            total_core = bid_count + len(neg_kw) + len(neg_pt) + harv_count
            total_core = total_core if total_core > 0 else 1

            _render_sub_kpi_row([
                {"label": "Total Decisions", "value": f"{action_count:,}", "subtext": "Optimizer actions generated", "accent": "#22d3ee"},
                {"label": "Savings Protected", "value": f"{currency}{(neg_spend_saving + bid_saving):,.0f}", "subtext": "Negative + bid defense", "accent": "#22c55e"},
                {"label": "Growth Pipeline", "value": f"{currency}{harvest_sales:,.0f}", "subtext": "Harvest-attributed sales", "accent": "#38bdf8"},
                {"label": "Efficiency Lift", "value": f"{impact_pct:+.1%}", "subtext": "Projected ROAS movement", "accent": "#a78bfa"},
            ])

            _render_overview_breakdown([
                {"label": "Bid Adjustments", "count": bid_count, "impact": f"{currency}{reallocated:,.0f} reallocated", "share_pct": (bid_count / total_core) * 100},
                {"label": "Negative Keywords", "count": len(neg_kw), "impact": f"{currency}{neg_kw_spend:,.0f} blocked", "share_pct": (len(neg_kw) / total_core) * 100},
                {"label": "Negative ASINs", "count": len(neg_pt), "impact": f"{currency}{neg_pt_spend:,.0f} blocked", "share_pct": (len(neg_pt) / total_core) * 100},
                {"label": "Harvest Targets", "count": harv_count, "impact": f"{currency}{harvest_sales:,.0f} potential", "share_pct": (harv_count / total_core) * 100},
            ])
        else:
            st.info("No optimization actions generated.")

    elif active == "Negatives":
        st.markdown("### Negative Keywords & ASINs")

        # Combine negatives
        all_negs = pd.concat([neg_kw, neg_pt]) if not neg_kw.empty or not neg_pt.empty else pd.DataFrame()

        if not all_negs.empty:
            avg_clicks = _to_numeric_series(all_negs, "Clicks").mean() if "Clicks" in all_negs.columns else 0
            _render_sub_kpi_row([
                {"label": "Keyword Negatives", "value": f"{len(neg_kw):,}", "subtext": "Match-based blocks", "accent": "#60a5fa"},
                {"label": "ASIN Negatives", "value": f"{len(neg_pt):,}", "subtext": "Product target blocks", "accent": "#60a5fa"},
                {"label": "Waste Blocked", "value": f"{currency}{neg_spend_saving:,.0f}", "subtext": "Estimated spend prevented", "accent": "#22c55e"},
                {"label": "Avg. Clicks", "value": f"{avg_clicks:.1f}", "subtext": "Per blocked target", "accent": "#f59e0b"},
            ])

            st.markdown("<br>", unsafe_allow_html=True)
            st.dataframe(all_negs, use_container_width=True)
        else:
            st.info("No negative recommendations generated.")

    elif active == "Bids":
        st.markdown("### Bid Adjustments")

        if not all_bids.empty:
            avg_roas = _to_numeric_series(all_bids, "ROAS").mean() if "ROAS" in all_bids.columns else 0
            _render_sub_kpi_row([
                {"label": "Total Adjustments", "value": f"{bid_count:,}", "subtext": "Actionable bid updates", "accent": "#38bdf8"},
                {"label": "Bid Increases", "value": f"{bid_inc_count:,}", "subtext": "Growth actions", "accent": "#22c55e"},
                {"label": "Bid Decreases", "value": f"{bid_dec_count:,}", "subtext": "Savings actions", "accent": "#ef4444"},
                {"label": "Avg. ROAS", "value": f"{avg_roas:.2f}x", "subtext": "Across adjusted targets", "accent": "#a78bfa"},
            ])

            st.markdown("<br>", unsafe_allow_html=True)
            st.dataframe(all_bids, use_container_width=True)
        else:
            st.info("No bid adjustments generated.")

    elif active == "Harvest":
        st.markdown("### Harvest Candidates")

        if not harvest.empty:
            total_harv_spend = _to_numeric_series(harvest, "Spend").sum() if "Spend" in harvest.columns else 0
            avg_cvr_pct = _compute_harvest_avg_cvr_pct(harvest)
            _render_sub_kpi_row([
                {"label": "Harvest Targets", "value": f"{harv_count:,}", "subtext": "Qualified terms", "accent": "#38bdf8"},
                {"label": "Potential Shift", "value": f"{currency}{total_harv_spend:,.0f}", "subtext": "Spend to migrate", "accent": "#f59e0b"},
                {"label": "Avg. Conv. Rate", "value": f"{avg_cvr_pct:.1f}%", "subtext": "Weighted by clicks", "accent": "#22c55e"},
                {"label": "Launch", "value": "Ready", "subtext": "Push to Campaign Creator", "accent": "#a78bfa"},
            ])

            if st.button("🚀 Launch in Campaign Creator", key="btn_goto_harvest_creator", use_container_width=True, type="primary"):
                st.session_state['harvest_payload'] = harvest
                st.session_state['active_creator_tab'] = "Harvest Winners"
                st.session_state['current_module'] = 'creator'
                st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            st.dataframe(harvest, use_container_width=True)
        else:
            st.info("No harvest candidates identified.")

    elif active == "Audit":
        from features.optimizer_shared.ui.tabs.audit import render_audit_tab
        
        # Check if audit/heatmap data exists
        if "heatmap" in results and isinstance(results["heatmap"], pd.DataFrame):
            render_audit_tab(results["heatmap"])
        else:
            st.info("Audit data not available in this optimization run.")

    elif active == "Forecast":
        from features.simulator import SimulatorModule
        SimulatorModule().run()

    elif active == "Downloads":
        st.markdown("### Export Results")
        st.caption("Download optimization actions as Amazon-ready bulk files")

        # Import bulk export functions
        from features.bulk_export import generate_negatives_bulk, generate_bids_bulk, generate_harvest_bulk

        # Export Cards Grid
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("""
            <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 16px; padding: 24px; height: 280px; display: flex; flex-direction: column;">
                <div style="width: 48px; height: 48px; background: rgba(45, 212, 191, 0.1); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; margin-bottom: 16px;">
                    🛡️
                </div>
                <h4 style="margin: 0 0 8px 0; color: #f1f5f9; font-size: 16px; font-weight: 600;">Negative Keywords</h4>
                <div style="display: flex; align-items: center; gap: 8px; font-size: 14px; color: #94a3b8; margin-bottom: 16px;">
                    <span style="color: #22c55e;">✓</span>
                    <span>{neg_count:,} terms ready</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if not neg_kw.empty or not neg_pt.empty:
                neg_bulk_df, neg_issues = generate_negatives_bulk(neg_kw, neg_pt)
                
                # Preview Window
                with st.expander("👁️ Preview File", expanded=False):
                    st.dataframe(neg_bulk_df, use_container_width=True, height=200)

                neg_xlsx = dataframe_to_excel(neg_bulk_df)
                st.download_button(
                    "📥 Download Negatives (.xlsx)",
                    neg_xlsx,
                    "negatives_bulk.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                if neg_issues:
                    with st.expander(f"⚠️ {len(neg_issues)} validation issues"):
                        for issue in neg_issues[:5]:  # Show first 5
                            st.caption(f"• {issue.get('msg', 'Unknown issue')}")
            else:
                st.button("📥 Download Negatives", disabled=True, use_container_width=True)

        with col2:
            st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 16px; padding: 24px; height: 280px; display: flex; flex-direction: column;">
                <div style="width: 48px; height: 48px; background: rgba(45, 212, 191, 0.1); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; margin-bottom: 16px;">
                    📈
                </div>
                <h4 style="margin: 0 0 8px 0; color: #f1f5f9; font-size: 16px; font-weight: 600;">Bid Adjustments</h4>
                <div style="display: flex; align-items: center; gap: 8px; font-size: 14px; color: #94a3b8; margin-bottom: 16px;">
                    <span style="color: #22c55e;">✓</span>
                    <span>{bid_count:,} bids ready</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if not all_bids.empty:
                bids_bulk_df, bids_issues = generate_bids_bulk(all_bids)
                
                # Preview Window
                with st.expander("👁️ Preview File", expanded=False):
                    st.dataframe(bids_bulk_df, use_container_width=True, height=200)

                bids_xlsx = dataframe_to_excel(bids_bulk_df)
                st.download_button(
                    "📥 Download Bids (.xlsx)",
                    bids_xlsx,
                    "bids_bulk.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                if bids_issues:
                    with st.expander(f"⚠️ {len(bids_issues)} validation issues"):
                        for issue in bids_issues[:5]:
                            st.caption(f"• {issue.get('msg', 'Unknown issue')}")
            else:
                st.button("📥 Download Bids", disabled=True, use_container_width=True)

        with col3:
            st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 16px; padding: 24px; height: 280px; display: flex; flex-direction: column;">
                <div style="width: 48px; height: 48px; background: rgba(45, 212, 191, 0.1); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; margin-bottom: 16px;">
                    🌾
                </div>
                <h4 style="margin: 0 0 8px 0; color: #f1f5f9; font-size: 16px; font-weight: 600;">Harvest Targets</h4>
                <div style="display: flex; align-items: center; gap: 8px; font-size: 14px; color: #94a3b8; margin-bottom: 16px;">
                    <span style="color: #22c55e;">✓</span>
                    <span>{harv_count:,} targets ready</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if not harvest.empty:
                harv_bulk_df = generate_harvest_bulk(harvest)

                # Preview Window
                with st.expander("👁️ Preview File", expanded=False):
                    st.dataframe(harv_bulk_df, use_container_width=True, height=200)

                harv_xlsx = dataframe_to_excel(harv_bulk_df)
                st.download_button(
                    "📥 Download Harvest (.xlsx)",
                    harv_xlsx,
                    "harvest_bulk.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.button("📥 Download Harvest", disabled=True, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Bulk Download All
        st.markdown("""
        <div style="text-align: center; padding-top: 24px; border-top: 1px solid rgba(255, 255, 255, 0.06);">
            <p style="color: #94a3b8; font-size: 13px; margin-bottom: 16px;">Download all optimization files at once</p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("📦 Download All Files (ZIP)", type="primary", use_container_width=True):
            st.info("Bulk download feature coming soon!")
