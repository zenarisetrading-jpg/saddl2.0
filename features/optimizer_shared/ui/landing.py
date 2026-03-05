import streamlit as st
import datetime
from .components import render_status_badge

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_daily_stats_cached(client_id: str, test_mode: bool):
    """Fetch daily PPC data from raw_search_term_data for the landing page.
    
    Uses the daily table (report_date) instead of weekly target_stats so that
    the date picker and KPIs match Campaign Manager's daily granularity exactly.
    """
    from app_core.db_manager import get_db_manager
    import pandas as pd
    db_manager = get_db_manager(test_mode)
    if not db_manager or not client_id:
        return None
    try:
        with db_manager._get_connection() as conn:
            query = """
                SELECT
                    report_date AS "Date",
                    customer_search_term AS "Customer Search Term",
                    SUM(spend) AS "Spend",
                    SUM(sales) AS "Sales"
                FROM raw_search_term_data
                WHERE client_id = %s
                  AND report_date >= CURRENT_DATE - INTERVAL '65 days'
                GROUP BY report_date, customer_search_term
            """
            df = pd.read_sql(query, conn, params=(client_id,))
            if not df.empty and 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
            return df
    except Exception:
        return None

def render_landing_page(config: dict):
    """
    Premium optimizer landing page - 10/10 polish.
    """

    # === PREMIUM STYLES ===
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Global - Scoped to Main to protect Sidebar */
    .main * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Subtle Background Pattern */
    .stApp {
        background-image:
            repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.01) 2px, rgba(255,255,255,0.01) 4px);
    }

    /* Hero Section - DRAMATIC */
    .optimizer-hero {
        display: flex;
        align-items: flex-start;
        justify-content: flex-start;
        gap: 60px;
        padding: 80px 24px 60px;
        max-width: 1400px;
        margin: 0 auto;
        position: relative;
    }

    /* Radial Glow Behind Title */
    .optimizer-hero::before {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 500px;
        height: 500px;
        background: radial-gradient(circle at 50% 50%, rgba(45, 212, 191, 0.12) 0%, transparent 60%);
        pointer-events: none;
        z-index: 0;
    }

    /* Status Badge */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(45, 212, 191, 0.08);
        border: 1px solid rgba(45, 212, 191, 0.2);
        border-radius: 20px;
        padding: 6px 16px;
        margin-top: 0;
        margin-bottom: 0;
        font-size: 13px;
        font-weight: 500;
        color: #2dd4bf;
        position: relative;
        z-index: 1;
    }

    /* Pulsing Dot */
    .status-dot {
        width: 8px;
        height: 8px;
        background: #2dd4bf;
        border-radius: 50%;
        animation: pulse 2s ease-in-out infinite;
        box-shadow: 0 0 8px rgba(45, 212, 191, 0.6);
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(1.1); }
    }

    .optimizer-hero h1 {
        font-size: 4.2rem;
        font-weight: 700;
        line-height: 1;
        letter-spacing: -0.02em;
        margin-bottom: 16px;
        position: relative;
        z-index: 1;
        flex-shrink: 0;
        white-space: nowrap;
    }

    .optimizer-hero .brand-text {
        color: #f8fafc;
        text-shadow: 0 2px 20px rgba(0,0,0,0.3);
    }

    .optimizer-hero .brand-highlight {
        background: linear-gradient(135deg, #2dd4bf 0%, #06b6d4 50%, #2dd4bf 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        background-size: 200% 200%;
        animation: gradientShift 3s ease infinite;
    }

    @keyframes gradientShift {
        0%, 100% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
    }

    .optimizer-hero .subtitle {
        font-size: 1.125rem;
        color: #94a3b8;
        max-width: 500px;
        margin: 0;
        margin-top: 20px;
        line-height: 1.7;
        font-weight: 400;
        position: relative;
        z-index: 1;
        flex: 1;
    }

    /* Section Labels - Premium Typography */
    .section-header {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        color: #64748b;
        margin-bottom: 16px;
    }

    /* Account Snapshot Cards - DEPTH */
    .metrics-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin: 48px auto 64px;
        max-width: 1400px;
        padding: 0 24px;
    }

    .metric-card {
        background: linear-gradient(145deg, rgba(45, 55, 72, 0.6) 0%, rgba(30, 41, 59, 0.4) 100%);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        border-left: 3px solid rgba(45, 212, 191, 0.3);
        border-radius: 12px;
        padding: 24px;
        transition: all 0.2s ease;
        position: relative;
        overflow: hidden;
        min-width: 200px;
        flex: 1 1 200px;
    }

    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
        border-left-color: rgba(45, 212, 191, 0.6);
    }

    .metric-label {
        font-size: 11px;
        font-weight: 600;
        color: #94a3b8;
        margin-bottom: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    .metric-value {
        font-size: clamp(24px, 2.5vw, 28px);
        font-weight: 600;
        color: #f1f5f9;
        line-height: 1;
        white-space: nowrap;
    }

    /* Main Content */
    .content-wrapper {
        max-width: 900px;
        margin: 0 auto;
        padding: 0 24px;
    }

    /* Glassmorphic Control Panel Container - Targeted via :has() */
    /* Applies to the Horizontal Block containing the Analysis Section */
    div[data-testid="stHorizontalBlock"]:has(.analysis-section) {
        background:
            radial-gradient(ellipse 800px 400px at top center, rgba(45, 212, 191, 0.12) 0%, transparent 50%),
            linear-gradient(145deg, rgba(30, 41, 59, 0.5) 0%, rgba(15, 23, 42, 0.4) 100%);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-top: 2px solid rgba(255, 255, 255, 0.15);
        border-radius: 24px;
        padding: 40px;
        backdrop-filter: blur(20px) saturate(180%);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        box-shadow:
            0 12px 40px rgba(0, 0, 0, 0.4),
            inset 0 1px 0 rgba(255, 255, 255, 0.12),
            inset 0 -1px 0 rgba(0, 0, 0, 0.2),
            0 0 80px rgba(45, 212, 191, 0.08);
        margin-bottom: 32px;
        position: relative;
        min-height: 420px;
        isolation: isolate;
    }

    /* Shiny border pseudo-element */
    div[data-testid="stHorizontalBlock"]:has(.analysis-section)::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        border-radius: 24px;
        padding: 1px;
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.15) 0%, transparent 50%);
        -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
        -webkit-mask-composite: xor;
        mask-composite: exclude;
        pointer-events: none;
        z-index: 3;
    }

    /* Analysis Window */
    .analysis-section {
        margin-bottom: 32px;
    }

    /* Date Inputs - Main Only */
    .main .stDateInput > div > div {
        background: rgba(30, 41, 59, 0.6) !important;
        border: 1px solid rgba(148, 163, 184, 0.12) !important;
        border-radius: 10px !important;
        transition: all 0.2s ease !important;
    }

    .main .stDateInput > div > div:hover {
        border-color: rgba(45, 212, 191, 0.3) !important;
    }

    .main .stDateInput label {
        font-size: 13px !important;
        font-weight: 500 !important;
        color: #cbd5e1 !important;
    }

    /* Strategy Cards - Unselected State - Glassmorphic */
    .main div[data-testid="column"] .stButton > button[kind="secondary"] {
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.3) 0%, rgba(15, 23, 42, 0.2) 100%) !important;
        border: 1.5px solid rgba(148, 163, 184, 0.2) !important;
        border-radius: 16px !important;
        padding: 12px 20px 24px !important;
        color: #cbd5e1 !important;
        font-weight: 500 !important;
        font-size: 13px !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        height: auto !important;
        min-height: 130px !important;
        white-space: pre-line !important;
        text-align: center !important;
        line-height: 1.6 !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        margin-top: -16px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
    }

    .main div[data-testid="column"] .stButton > button[kind="secondary"]:hover {
        background: linear-gradient(145deg, rgba(34, 211, 238, 0.12) 0%, rgba(30, 41, 59, 0.3) 100%) !important;
        border-color: rgba(34, 211, 238, 0.4) !important;
        color: #f8fafc !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 0 24px rgba(34, 211, 238, 0.2), 0 6px 16px rgba(0, 0, 0, 0.3) !important;
    }

    /* Strategy Cards - SELECTED STATE (DOMINANT) - Main Only */
    /* CRITICAL: Override Streamlit's solid gradient with transparent glassmorphic */
    .main div[data-testid="column"] .stButton > button[kind="primary"] {
        background: linear-gradient(145deg, rgba(34, 211, 238, 0.15) 0%, rgba(34, 211, 238, 0.08) 100%) !important;
        border: 2px solid #22d3ee !important;
        border-radius: 16px !important;
        padding: 12px 20px 24px !important;
        color: #f8fafc !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        box-shadow: 0 0 32px rgba(34, 211, 238, 0.4), 0 6px 16px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255,255,255,0.12) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        height: auto !important;
        min-height: 130px !important;
        white-space: pre-line !important;
        text-align: center !important;
        line-height: 1.6 !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        margin-top: -16px !important;
    }

    .main div[data-testid="column"] .stButton > button[kind="primary"]:hover {
        background: linear-gradient(145deg, rgba(34, 211, 238, 0.2) 0%, rgba(34, 211, 238, 0.12) 100%) !important;
        box-shadow: 0 0 40px rgba(34, 211, 238, 0.5), 0 8px 20px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255,255,255,0.15) !important;
        transform: translateY(-2px) !important;
    }

    /* Exclude the Start Optimization button from strategy styling */
    .action-row .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2dd4bf 0%, #14b8a6 100%) !important;
        color: #0a0f1a !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        padding: 14px 32px !important;
        border-radius: 10px !important;
        border: none !important;
        box-shadow: 0 4px 20px rgba(45, 212, 191, 0.35) !important;
        transition: all 0.2s ease !important;
        width: 100% !important;
        height: 48px !important;
        letter-spacing: 0.3px !important;
        white-space: nowrap !important;
        margin-top: 0 !important;
        min-height: auto !important;
        backdrop-filter: none !important;
    }

    .action-row .stButton > button[kind="primary"]:hover {
        background: #14b8a6 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(45, 212, 191, 0.3) !important;
    }

    /* SVG Icons - Positioned above buttons */
    .strategy-card-svg {
        width: 48px;
        height: 48px;
        margin: 0 auto 16px;
        display: block;
        pointer-events: none;
        position: relative;
        z-index: 10;
    }

    .strategy-card-svg svg {
        width: 100%;
        height: 100%;
        stroke: #94a3b8 !important;
        fill: none !important;
        stroke-width: 2 !important;
        transition: all 0.3s ease;
    }

    /* Icon changes based on following button state */
    [data-testid="column"]:has(button[kind="secondary"]:hover) .strategy-card-svg svg {
        stroke: #22d3ee !important;
        filter: drop-shadow(0 0 10px rgba(34, 211, 238, 0.6));
    }

    [data-testid="column"]:has(button[kind="primary"]:not(.action-row button)) .strategy-card-svg svg {
        stroke: #22d3ee !important;
        filter: drop-shadow(0 0 12px rgba(34, 211, 238, 0.8));
    }

    [data-testid="column"]:has(button[kind="primary"]:not(.action-row button):hover) .strategy-card-svg svg {
        stroke: #06b6d4 !important;
        filter: drop-shadow(0 0 15px rgba(34, 211, 238, 1));
    }

    /* Action Row - Button + Toggle */
    .action-row {
        margin-top: 32px;
    }

    .action-row [data-testid="column"] {
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    /* Start Button styling moved to line 319 (combined with primary override) */

    /* Simulation Toggle - Compact */
    .action-row .stCheckbox {
        margin: 0 !important;
    }

    .action-row .stCheckbox label {
        font-weight: 600 !important;
        color: #f8fafc !important;
        font-size: 14px !important;
    }

    .simulation-subtext {
        font-size: 12px;
        color: #64748b;
        margin-top: 4px;
        margin-left: 24px;
        line-height: 1.4;
    }


    /* Checkbox - Teal Accent */
    .stCheckbox label {
        font-weight: 600 !important;
        color: #f8fafc !important;
        font-size: 15px !important;
    }

    .stCheckbox input[type="checkbox"]:checked {
        background-color: #2dd4bf !important;
        border-color: #2dd4bf !important;
    }

    /* Advanced Configuration - Subtle Accordion */
    div[data-testid="stExpander"] {
        background: rgba(30, 41, 59, 0.2);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 12px;
        margin-top: 16px;
        transition: all 0.2s ease;
    }

    div[data-testid="stExpander"]:hover {
        background: rgba(30, 41, 59, 0.3);
        border-color: rgba(148, 163, 184, 0.15);
    }

    div[data-testid="stExpander"] summary {
        color: #cbd5e1 !important;
        font-weight: 500 !important;
        font-size: 14px !important;
    }

    /* Number Inputs - Main Only */
    .main .stNumberInput > div > div {
        background: rgba(30, 41, 59, 0.6) !important;
        border: 1px solid rgba(148, 163, 184, 0.12) !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }

    .main .stNumberInput > div > div:hover {
        border-color: rgba(45, 212, 191, 0.3) !important;
    }

    .main .stNumberInput label {
        font-size: 13px !important;
        font-weight: 500 !important;
        color: #cbd5e1 !important;
    }

    /* Caption Text */
    .stCaption {
        color: #64748b !important;
        font-size: 13px !important;
        margin-top: 8px !important;
    }

    /* Column Gap Override - Main Only */
    .main [data-testid="column"] {
        gap: 40px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # === FETCH DATA ===
    from app_core.data_hub import DataHub
    from utils.formatters import get_account_currency
    import pandas as pd

    hub = DataHub()
    client_id = st.session_state.get('active_account_id')
    test_mode = st.session_state.get('test_mode', False)

    max_date = datetime.date.today()
    min_date = max_date - datetime.timedelta(days=60)
    df = None

    if client_id:
        try:
            db_df = _fetch_daily_stats_cached(client_id, test_mode)
            if db_df is not None and not db_df.empty:
                df = db_df.copy()
                if 'Date' in df.columns:
                    try:
                        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                        df_min = df['Date'].min()
                        df_max = df['Date'].max()
                        if pd.notna(df_min) and pd.notna(df_max):
                            min_date = df_min.date()
                            # No +6-day buffer — raw daily data, use actual last date
                            max_date = df_max.date()
                    except Exception:
                        pass
        except Exception:
            pass
    elif hub.is_loaded("search_term_report"):
        df_raw = hub.get_data("search_term_report")
        if df_raw is not None and not df_raw.empty:
            df = df_raw.copy()
            date_col = "Date" if "Date" in df.columns else None
            if date_col:
                try:
                    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                    df_max = df[date_col].max()
                    df_min = df[date_col].min()
                    if pd.notna(df_max) and pd.notna(df_min):
                        max_date = df_max.date()
                        min_date = df_min.date()
                except Exception:
                    pass

    if "opt_start_date" not in st.session_state:
        st.session_state["opt_start_date"] = max(min_date, max_date - datetime.timedelta(days=30))
    if "opt_end_date" not in st.session_state:
        st.session_state["opt_end_date"] = max_date

    s_min, s_max = min_date, max_date
    if st.session_state["opt_start_date"] < s_min:
        st.session_state["opt_start_date"] = s_min
    if st.session_state["opt_start_date"] > s_max:
        st.session_state["opt_start_date"] = s_max
    if st.session_state["opt_end_date"] < s_min:
        st.session_state["opt_end_date"] = s_min
    if st.session_state["opt_end_date"] > s_max:
        st.session_state["opt_end_date"] = s_max

    # === HERO SECTION WITH STATUS BADGE ===
    st.markdown("""
    <div class="optimizer-hero">
        <div style="flex-shrink: 0;">
            <h1>
                <span class="brand-highlight">PPC OPTIMIZER</span>
            </h1>
            <div class="status-badge">
                <div class="status-dot"></div>
                Ready to Optimize
            </div>
        </div>
        <p class="subtitle">
            Intelligent bid adjustments, negative keyword isolation, and harvest opportunities—powered by decision-first analytics.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # === ACCOUNT SNAPSHOT ===
    if df is not None and not df.empty:
        filtered_df = df[
            (df['Date'].dt.date >= st.session_state["opt_start_date"]) &
            (df['Date'].dt.date <= st.session_state["opt_end_date"])
        ]

        if not filtered_df.empty:
            currency = get_account_currency()
            total_spend = filtered_df['Spend'].sum() if 'Spend' in filtered_df.columns else 0
            total_sales = filtered_df['Sales'].sum() if 'Sales' in filtered_df.columns else 0
            current_roas = total_sales / total_spend if total_spend > 0 else 0
            current_acos = (total_spend / total_sales * 100) if total_sales > 0 else 0
            # Unique search terms (not row count)
            num_terms = filtered_df['Customer Search Term'].nunique() if 'Customer Search Term' in filtered_df.columns else len(filtered_df)

            if total_spend >= 100000:
                spend_display = f"{currency}{total_spend/1000:.0f}K"
            else:
                spend_display = f"{currency}{total_spend:,.0f}"

            days_in_period = (st.session_state["opt_end_date"] - st.session_state["opt_start_date"]).days + 1

            st.markdown(f"""
            <div class="section-header" style="text-align: center;">ACCOUNT SNAPSHOT</div>
            <div class="metrics-row">
                <div class="metric-card">
                    <div class="metric-label">Total Spend ({days_in_period}d)</div>
                    <div class="metric-value">{spend_display}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Current ROAS</div>
                    <div class="metric-value">{current_roas:.2f}x</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Current ACOS</div>
                    <div class="metric-value">{current_acos:.1f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Search Terms</div>
                    <div class="metric-value">{num_terms:,}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # === MAIN CONTENT ===
    st.markdown('<div class="content-wrapper">', unsafe_allow_html=True)
    # Styles applied via CSS :has() selector on stHorizontalBlock

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        # ANALYSIS WINDOW
        st.markdown('<div class="analysis-section"><div class="section-header">ANALYSIS WINDOW</div></div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.date_input(
                "Start",
                min_value=s_min,
                max_value=s_max,
                key="opt_start_date"
            )
        with c2:
            st.date_input(
                "End",
                min_value=s_min,
                max_value=s_max,
                key="opt_end_date"
            )

        days_selected = (st.session_state["opt_end_date"] - st.session_state["opt_start_date"]).days + 1
        st.caption(f"{days_selected} days • Last STR upload: 23:45")

    with col_right:
        # OPTIMIZATION STRATEGY
        st.markdown('<div class="section-header">OPTIMIZATION STRATEGY</div>', unsafe_allow_html=True)

        # NUCLEAR OPTION: Inline styles to override everything
        st.markdown("""
        <style>
        /* Force transparent glassmorphic on strategy buttons */
        .main div[data-testid="column"] .stButton > button[kind="primary"] {
            background: linear-gradient(145deg, rgba(34, 211, 238, 0.15), rgba(34, 211, 238, 0.08)) !important;
            border: 2px solid #22d3ee !important;
            box-shadow: 0 0 32px rgba(34, 211, 238, 0.4) !important;
        }
        </style>
        """, unsafe_allow_html=True)

        current_profile = st.session_state.get("opt_profile", "balanced")

        # Strategy cards with SVG icons
        col1, col2, col3 = st.columns(3)

        # SVG icon definitions
        shield_svg = '''<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'/></svg>'''
        sliders_svg = '''<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><line x1='4' y1='9' x2='20' y2='9'/><line x1='4' y1='15' x2='20' y2='15'/><line x1='10' y1='3' x2='8' y2='21'/><line x1='16' y1='3' x2='14' y2='21'/></svg>'''
        zap_svg = '''<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polygon points='13 2 3 14 12 14 11 22 21 10 12 10 13 2'/></svg>'''

        # Callback to update profile safely
        def set_profile(profile_name):
            st.session_state["opt_profile"] = profile_name

        with col1:
            btn_type = "primary" if current_profile == "conservative" else "secondary"
            # Add SVG icon above button text
            st.markdown(f'<div class="strategy-card-svg">{shield_svg}</div>', unsafe_allow_html=True)
            st.button(
                "**Conservative**\n\nSafer, gradual changes",
                width='stretch',
                type=btn_type,
                key="strat_conservative",
                on_click=set_profile,
                args=("conservative",)
            )

        with col2:
            btn_type = "primary" if current_profile == "balanced" else "secondary"
            st.markdown(f'<div class="strategy-card-svg">{sliders_svg}</div>', unsafe_allow_html=True)
            st.button(
                "**Balanced**\n\nOptimal risk-reward",
                width='stretch',
                type=btn_type,
                key="strat_balanced",
                on_click=set_profile,
                args=("balanced",)
            )

        with col3:
            btn_type = "primary" if current_profile == "aggressive" else "secondary"
            st.markdown(f'<div class="strategy-card-svg">{zap_svg}</div>', unsafe_allow_html=True)
            st.button(
                "**Aggressive**\n\nFaster, bigger moves",
                width='stretch',
                type=btn_type,
                key="strat_aggressive",
                on_click=set_profile,
                args=("aggressive",)
            )

        # ACTION ROW: Toggle (left) + Button (right)
        st.markdown('<div class="action-row">', unsafe_allow_html=True)

        col_toggle, col_button = st.columns([1, 1])

        with col_toggle:
            simulation_enabled = st.checkbox(
                "Include Simulation & Forecasting",
                value=st.session_state.get("opt_test_mode", False),
                key="opt_test_mode"
            )
            st.markdown('<p class="simulation-subtext">Project impact before applying</p>', unsafe_allow_html=True)

        with col_button:
            def start_optimization():
                st.session_state["_nav_loading"] = True
                st.session_state["run_optimizer_refactored"] = True
                
            st.button(
                "⚡ Start Optimization →", 
                type="primary", 
                width='stretch', 
                key="start_opt_btn",
                on_click=start_optimization
            )

        st.markdown('</div>', unsafe_allow_html=True)


    # ADVANCED CONFIGURATION
    with st.expander("⚙️ Advanced Configuration"):
        st.markdown("Fine-tune specific thresholds and parameters.")
        c1, c2 = st.columns(2)
        with c1:
            st.number_input(
                "Target ROAS",
                min_value=1.0,
                max_value=10.0,
                value=float(st.session_state.get("opt_target_roas", 2.5)),
                step=0.1,
                key="opt_target_roas"
            )
        with c2:
            st.number_input(
                "Negative Clicks Threshold",
                min_value=1,
                max_value=50,
                value=int(st.session_state.get("opt_neg_clicks_threshold", 10)),
                step=1,
                key="opt_neg_clicks_threshold"
            )

        st.markdown("---")
        st.markdown("**Bid Optimization Levers**")
        
        b1, b2, b3 = st.columns(3)
        with b1:
            st.number_input(
                "Max Bid Change Cap (%)",
                min_value=5,
                max_value=100,
                value=int(st.session_state.get("opt_max_bid_change", 25)),
                step=5,
                key="opt_max_bid_change",
                help="Maximum % increase/decrease allowed in a single run"
            )
        with b2:
            st.number_input(
                "Step Size: Exact (%)",
                min_value=1,
                max_value=50,
                value=int(st.session_state.get("opt_alpha_exact", 25)),
                step=1,
                key="opt_alpha_exact",
                help="Aggressiveness for Exact Match adjustments"
            )
        with b3:
            st.number_input(
                "Step Size: Broad/Phrase (%)",
                min_value=1,
                max_value=50,
                value=int(st.session_state.get("opt_alpha_broad", 20)),
                step=1,
                key="opt_alpha_broad",
                help="Aggressiveness for Broad/Phrase/Auto adjustments"
            )

    st.markdown('</div>', unsafe_allow_html=True)
