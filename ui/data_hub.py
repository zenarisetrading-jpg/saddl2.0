"""
Data Hub UI Page

Upload all files in one place, use everywhere.
"""

import streamlit as st
from app_core.data_hub import DataHub
from datetime import datetime
from ui.onboarding import render_connect_amazon_account_button

# ============================================================
# PHASE 2 — BACKFILL HELPERS
# Backfill is now handled entirely by worker.py.
# The UI only reads onboarding_status from the DB and
# shows the appropriate status panel — no threads here.
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def _has_sp_api_data(client_id: str) -> bool:
    """Return True if sc_raw.fba_inventory already has rows for this client."""
    if not client_id:
        return False
    try:
        from app_core.db_manager import get_db_manager
        db = get_db_manager()
        if not db:
            return False
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM sc_raw.fba_inventory WHERE client_id = %s LIMIT 1",
                (client_id,),
            )
            return cursor.fetchone() is not None
    except Exception:
        return False


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_client_settings_row_cached(client_id: str):
    """Cached fetch of client SP-API settings — runs at most once per minute."""
    if not client_id:
        return None
    try:
        from app_core.db_manager import get_db_manager
        db = get_db_manager()
        if not db:
            return None
        placeholder = getattr(db, "placeholder", "%s")
        queries = [
            f"SELECT lwa_refresh_token, onboarding_status, connected_at, updated_at FROM client_settings WHERE client_id = {placeholder} LIMIT 1",
            f"SELECT lwa_refresh_token, onboarding_status, updated_at FROM client_settings WHERE client_id = {placeholder} LIMIT 1",
        ]
        # Each query gets its own connection so a failed attempt (e.g. missing
        # column) doesn't leave the shared connection in an ABORTED state,
        # which would cause the fallback query to also fail silently.
        for query in queries:
            try:
                with db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(query, (client_id,))
                    row = cursor.fetchone()
                    if row is None:
                        return None
                    if hasattr(row, "keys"):
                        return {k: row[k] for k in row.keys()}
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
            except Exception:
                continue
    except Exception:
        pass
    return None


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_ghost_account_ids_cached(registered_ids_key: str) -> set:
    """
    Return set of client_ids present in target_stats or actions_log
    that are NOT in the registered accounts list.
    registered_ids_key is a sorted-comma-joined string of known account IDs
    so the cache key changes when accounts are added/removed.
    """
    try:
        from app_core.db_manager import get_db_manager
        db = get_db_manager()
        if not db:
            return set()
        known = set(registered_ids_key.split(",")) if registered_ids_key else set()
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT client_id FROM target_stats")
            stats_ids = {row[0] for row in cursor.fetchall()}
            cursor.execute("SELECT DISTINCT client_id FROM actions_log")
            log_ids = {row[0] for row in cursor.fetchall()}
        return (stats_ids | log_ids) - known
    except Exception:
        return set()


# ============================================================

def render_data_hub():
    """Render the data hub upload interface."""

    if st.session_state.get('upload_save_failed'):
        st.warning('⚠️  A previous upload was not saved to the database. Please retry the upload.')

    # Theme-aware icon color
    icon_color = "#94a3b8"
    folder_icon = f'<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"></path></svg>'
    
    st.markdown(f"""
    <h1 style="font-family: Inter, sans-serif; font-weight: 700; display: flex; align-items: center; gap: 12px;">
        {folder_icon}
        <span>Data Hub</span>
    </h1>
    """, unsafe_allow_html=True)
    st.caption("Manage your data sources here.")
    
    # ===========================================
    # ACCOUNT CONTEXT BANNER
    # ===========================================
    active_account_id = st.session_state.get('active_account_id')
    active_account_name = st.session_state.get('active_account_name', 'No account selected')
    
    if not active_account_id:
        st.error("⚠️ **No account selected!** Please select or create an account in the sidebar.")
        return
    
    # Compact account indicator
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 20px;">
        <span style="width: 8px; height: 8px; background: #22c55e; border-radius: 50%;"></span>
        <span style="color: #94a3b8; font-size: 0.9rem;">Uploading to Account: <strong style="color: #e2e8f0;">{active_account_name}</strong></span>
        <span style="color: #22c55e;">✓</span>
    </div>
    """, unsafe_allow_html=True)

    # ===========================================
    # AMAZON SP-API CONNECTION SECTION
    # ===========================================
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 8px; margin: 8px 0 10px 0;">
        <span style="font-size: 1rem; font-weight: 700; color: #e2e8f0; letter-spacing: 0.02em;">Amazon SP-API Connection</span>
    </div>
    """, unsafe_allow_html=True)

    def _format_timestamp(value):
        if not value:
            return None
        if isinstance(value, datetime):
            ts = value
        else:
            try:
                normalized = str(value).replace("Z", "+00:00")
                ts = datetime.fromisoformat(normalized)
            except Exception:
                return str(value)
        return ts.strftime("%Y-%m-%d %H:%M:%S")

    settings_row = _fetch_client_settings_row_cached(active_account_id)
    refresh_token = settings_row.get("lwa_refresh_token") if settings_row else None
    onboarding_status = (settings_row.get("onboarding_status") if settings_row else None) or "not_connected"
    onboarding_status_norm = str(onboarding_status).strip().lower()
    is_connected = bool(refresh_token) and onboarding_status_norm in {"connected", "active", "backfilling"}

    if not is_connected:
        st.markdown("""
        <div style="
            background: rgba(245, 158, 11, 0.10);
            border: 1px solid rgba(245, 158, 11, 0.35);
            border-left: 4px solid #f59e0b;
            border-radius: 10px;
            padding: 12px 14px;
            margin-bottom: 10px;
            color: #fde68a;
            font-weight: 600;
        ">
            SP-API not connected — required for inventory, orders and fee data
        </div>
        """, unsafe_allow_html=True)
        render_connect_amazon_account_button(
            client_id=active_account_id,
            key=f"spapi_connect_{active_account_id}",
            force_new_state=True,
            label="🔗 Connect Amazon Account",
        )
    else:
        connected_at = settings_row.get("connected_at") if settings_row else None
        if not connected_at and settings_row:
            connected_at = settings_row.get("updated_at")
        connected_at_text = _format_timestamp(connected_at)
        details = f" • Connected at: {connected_at_text}" if connected_at_text else ""
        st.markdown(f"""
        <div style="
            background: rgba(34, 197, 94, 0.10);
            border: 1px solid rgba(34, 197, 94, 0.35);
            border-left: 4px solid #22c55e;
            border-radius: 10px;
            padding: 12px 14px;
            margin-bottom: 10px;
            color: #86efac;
            font-weight: 600;
        ">
            SP-API Connected <span style="
                display: inline-block;
                margin-left: 8px;
                background: rgba(34, 197, 94, 0.2);
                border: 1px solid rgba(34, 197, 94, 0.4);
                border-radius: 999px;
                padding: 2px 10px;
                font-size: 0.75rem;
                letter-spacing: 0.03em;
                text-transform: uppercase;
            ">{onboarding_status}</span>{details}
        </div>
        """, unsafe_allow_html=True)
        render_connect_amazon_account_button(
            client_id=active_account_id,
            key=f"spapi_reconnect_{active_account_id}",
            force_new_state=True,
            label="Reconnect",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ===========================================
    # PHASE 2 — SP-API BACKFILL STATUS PANEL
    # Purely informational — the worker.py process
    # handles backfill automatically after OAuth.
    # No buttons or user action needed.
    # ===========================================
    if onboarding_status_norm == "backfilling":
        # Worker is actively running — show live status
        st.markdown(
            """
            <div style="
                background: rgba(99,102,241,0.08);
                border: 1px solid rgba(99,102,241,0.30);
                border-left: 4px solid #6366f1;
                border-radius: 12px;
                padding: 20px 24px;
                margin: 0 0 20px 0;
            ">
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                    <span style="font-size:1.2rem;">⏳</span>
                    <span style="font-size:1rem;font-weight:700;color:#e2e8f0;">
                        Importing Historical Data…
                    </span>
                </div>
                <p style="color:#94a3b8;margin:0;font-size:0.85rem;">
                    Your 90-day sales, inventory, and traffic history is being pulled from Amazon.
                    This typically takes 5 – 20 minutes. The page will update automatically when complete.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("🔄 Refresh Status", key="backfill_refresh_btn"):
            st.rerun()
        return  # Hide data sources until backfill completes

    if is_connected and onboarding_status_norm == "connected":
        # Worker hasn't picked this up yet (will within 30s) or data already exists
        has_data = _has_sp_api_data(active_account_id)
        if not has_data:
            st.markdown(
                """
                <div style="
                    background: rgba(245,158,11,0.07);
                    border: 1px solid rgba(245,158,11,0.25);
                    border-left: 4px solid #f59e0b;
                    border-radius: 12px;
                    padding: 16px 20px;
                    margin: 0 0 20px 0;
                ">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span>🕐</span>
                        <span style="font-weight:600;color:#fde68a;">Historical data import queued</span>
                    </div>
                    <p style="color:#94a3b8;margin:6px 0 0 0;font-size:0.85rem;">
                        Your account is connected. Historical data import will start automatically within 30 seconds.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("🔄 Refresh Status", key="backfill_queued_refresh_btn"):
                st.rerun()
            # Fall through — still show manual upload section below

    st.markdown("---")

    # ===========================================
    # Initialize data hub
    hub = DataHub()
    
    # Guard: Ensure unified_data is initialized before rendering
    if 'unified_data' not in st.session_state or st.session_state.unified_data is None:
        st.session_state.unified_data = {
            'upload_status': {},
            'upload_timestamps': {}
        }
    
    status = hub.get_upload_status()
    summary = hub.get_summary()
    timestamps = st.session_state.unified_data.get('upload_timestamps', {})
    
    # ===========================================
    # DATA SOURCES SECTION
    # ===========================================
    st.markdown("**Data Sources**")
    
    def _get_staleness_indicator(upload_time):
        """Return staleness badge HTML."""
        if not upload_time:
            return ""
        days_ago = (datetime.now() - upload_time).days
        if days_ago > 21:
            return f'<span style="color: #f59e0b; font-size: 0.75rem; margin-left: 8px;">⚠️ {days_ago}d old</span>'
        return f'<span style="color: #64748b; font-size: 0.75rem; margin-left: 8px;">{days_ago}d ago</span>'
    
    def _render_data_source_row(name, is_loaded, metric, is_required=False, expander_key=None, upload_time=None):
        """Render a data source row with checkbox, name, and metric."""
        check_color = "#22c55e" if is_loaded else "#475569"
        check_bg = "rgba(34,197,94,0.15)" if is_loaded else "transparent"
        check_icon = "✓" if is_loaded else ""
        req_label = " — Required" if is_required else ""
        staleness = _get_staleness_indicator(upload_time)
        # Flat structure (no nested divs) — avoids Streamlit markdown sanitizer leaking tags
        st.markdown(
            f'<div style="padding:10px 16px;border-bottom:1px solid rgba(148,163,184,0.1);overflow:hidden;">'
            f'<span style="float:right;color:#94a3b8;font-size:0.85rem;">{metric}</span>'
            f'<span style="display:inline-block;width:18px;height:18px;border:2px solid {check_color};'
            f'border-radius:3px;background:{check_bg};color:{check_color};font-size:11px;'
            f'font-weight:bold;text-align:center;line-height:16px;vertical-align:middle;'
            f'margin-right:8px;">{check_icon}</span>'
            f'<span style="font-weight:600;color:#e2e8f0;vertical-align:middle;">{name}</span>'
            f'<span style="color:#64748b;font-size:0.8rem;vertical-align:middle;">{req_label}</span>'
            f'{"&nbsp;&nbsp;" + staleness if staleness else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )
    
    
    # ===========================================
    # DATA SOURCES - 2x2 Layout
    # ===========================================
    
    # Row 1: Search Terms | Advertised Products
    row1_col1, row1_col2 = st.columns(2)
    
    with row1_col1:
        str_metric = f"{summary.get('search_terms', 0):,} rows" if status['search_term_report'] else "—"
        _render_data_source_row("Search Terms", status['search_term_report'], str_metric, True, "str", timestamps.get('search_term_report'))
        
        with st.expander("", expanded=not status['search_term_report']):
            if status['search_term_report']:
                if st.button("🔄 Replace", key="replace_str"):
                    st.session_state.unified_data['upload_status']['search_term_report'] = False
                    st.rerun()
            else:
                str_file = st.file_uploader("Upload Search Term Report", type=['csv', 'xlsx', 'xls'], key='str_upload', label_visibility="collapsed")
                if str_file:
                    st.markdown(f"<small style='color: #f59e0b;'>⚠️ Uploading to: <strong>{active_account_name}</strong></small>", unsafe_allow_html=True)
                    confirm = st.checkbox(f"I confirm this data belongs to {active_account_name}", key="confirm_str")
                    if confirm:
                        with st.spinner("Processing..."):
                            success, message = hub.upload_search_term_report(str_file)
                            if success:
                                st.success('Data saved successfully.')
                                st.session_state.pop('upload_save_failed', None)
                                st.rerun()
                            else:
                                st.error(f'SAVE FAILED — your data is not persisted. Do not close this tab. Error: {message}')
                                st.session_state['upload_save_failed'] = True

    
    with row1_col2:
        adv_metric = f"{summary.get('unique_asins', 0):,} ASINs" if status['advertised_product_report'] else "—"
        _render_data_source_row("Advertised Products", status['advertised_product_report'], adv_metric, False, "adv", timestamps.get('advertised_product_report'))
        
        with st.expander("", expanded=False):
            if status['advertised_product_report']:
                if st.button("🔄 Replace", key="replace_adv"):
                    st.session_state.unified_data['upload_status']['advertised_product_report'] = False
                    st.rerun()
            else:
                adv_file = st.file_uploader("Upload Advertised Product Report", type=['csv', 'xlsx', 'xls'], key='adv_upload', label_visibility="collapsed")
                if adv_file:
                    with st.spinner("Processing..."):
                        success, message = hub.upload_advertised_product_report(adv_file)
                        if success:
                            st.success(f"✅ {message}")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
    
    # Row 2: Bulk ID Map | Category Map
    row2_col1, row2_col2 = st.columns(2)
    
    with row2_col1:
        bulk_metric = f"{summary.get('mapped_campaigns', 0):,} campaigns" if status['bulk_id_mapping'] else "—"
        _render_data_source_row("Bulk ID Map", status['bulk_id_mapping'], bulk_metric, False, "bulk", timestamps.get('bulk_id_mapping'))
        
        with st.expander("", expanded=False):
            if status['bulk_id_mapping']:
                if st.button("🔄 Replace", key="replace_bulk"):
                    st.session_state.unified_data['upload_status']['bulk_id_mapping'] = False
                    st.rerun()
            else:
                bulk_file = st.file_uploader("Upload Bulk File", type=['csv', 'xlsx', 'xls'], key='bulk_upload', label_visibility="collapsed")
                if bulk_file:
                    with st.spinner("Processing..."):
                        success, message = hub.upload_bulk_id_mapping(bulk_file)
                        if success:
                            st.success(f"✅ {message}")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
    
    with row2_col2:
        cat_metric = f"{summary.get('categorized_skus', 0):,} SKUs" if status['category_mapping'] else "—"
        _render_data_source_row("Category Map", status['category_mapping'], cat_metric, False, "cat", timestamps.get('category_mapping'))
        
        with st.expander("", expanded=False):
            if status['category_mapping']:
                if st.button("🔄 Replace", key="replace_cat"):
                    st.session_state.unified_data['upload_status']['category_mapping'] = False
                    st.rerun()
            else:
                cat_file = st.file_uploader("Upload Category Mapping", type=['csv', 'xlsx', 'xls'], key='cat_upload', label_visibility="collapsed")
                if cat_file:
                    with st.spinner("Processing..."):
                        success, message = hub.upload_category_mapping(cat_file)
                        if success:
                            st.success(f"✅ {message}")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===========================================
    # DATASET SUMMARY SECTION
    # ===========================================
    with st.expander("**Dataset Summary** (for reference)", expanded=status['search_term_report']):
        if status['search_term_report']:
            # System Ready Box
            st.markdown("""
            <div style="background: rgba(34, 197, 94, 0.08); border: 1px solid rgba(34, 197, 94, 0.3); 
                        border-radius: 10px; padding: 20px; margin-bottom: 20px;">
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                    <div style="width: 24px; height: 24px; background: #22c55e; border-radius: 4px; 
                                display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">✓</div>
                    <span style="font-size: 1.1rem; font-weight: 700; color: #e2e8f0;">System Ready</span>
                </div>
                <p style="color: #94a3b8; font-size: 0.85rem; margin: 0;">
                    ✓ Data processed. All features available.
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # 3 CTAs - All primary style with SVG icons
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Account Overview", use_container_width=True, type="primary", key="cta_overview"):
                    st.session_state['current_module'] = 'performance'
                    st.rerun()
            with c2:
                if st.button("Run Optimizer", use_container_width=True, type="primary", key="cta_optimizer"):
                    st.session_state['current_module'] = 'optimizer'
                    st.rerun()
            with c3:
                if st.button("Ask AI Strategist", use_container_width=True, type="primary", key="cta_ai"):
                    st.session_state['current_module'] = 'assistant'
                    st.rerun()
        else:
            st.info("👋 Upload a **Search Term Report** above to unlock the dashboard.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ===========================================
    # ADVANCED / ADMIN SECTION
    # ===========================================
    with st.expander("**› Advanced / Admin**", expanded=False):
        st.markdown("### Data Reassignment")
        st.warning("⚠️ **Use with caution!** This permanently moves data from one account to another.")
        
        db = st.session_state.get('db_manager')
        if db:
            # Get accounts (use cached version)
            from ui.account_manager import _fetch_accounts_cached
            from app_core.auth.service import AuthService
            auth = AuthService()
            current_user = auth.get_current_user()
            org_id = str(current_user.organization_id) if current_user else None
            registered_accounts = _fetch_accounts_cached(org_id) if org_id else []
            account_options = {name: acc_id for acc_id, name, _ in registered_accounts}
            
            # Historical/Ghost Accounts (cached 2 min to avoid full-table scans on every render)
            registered_ids_key = ",".join(sorted(account_options.values()))
            ghost_ids = _fetch_ghost_account_ids_cached(registered_ids_key)
            for gid in ghost_ids:
                account_options[f"{gid} (Legacy)"] = gid
            
            col1, col2 = st.columns(2)
            with col1:
                from_name = st.selectbox("From Account", list(account_options.keys()), key="reassign_from")
            with col2:
                to_name = st.selectbox("To Account", list(account_options.keys()), key="reassign_to")
            
            from_id = account_options[from_name]
            to_id = account_options[to_name]
            
            st.markdown("**Date Range:**")
            col3, col4 = st.columns(2)
            with col3:
                start_date = st.date_input("Start", key="reassign_start")
            with col4:
                end_date = st.date_input("End", key="reassign_end")
            
            if st.button("Preview Data to Move", key="preview_reassign"):
                st.session_state['reassign_preview_active'] = True
                
            if st.session_state.get('reassign_preview_active', False):
                try:
                    with db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT COUNT(*), SUM(spend), SUM(sales)
                            FROM target_stats
                            WHERE client_id = ? AND start_date BETWEEN ? AND ?
                        ''', (from_id, str(start_date), str(end_date)))
                        count, spend, sales = cursor.fetchone()
                        
                        cursor.execute('''
                            SELECT COUNT(*)
                            FROM actions_log
                            WHERE client_id = ? AND DATE(action_date) BETWEEN ? AND ?
                        ''', (from_id, str(start_date), str(end_date)))
                        actions_count = cursor.fetchone()[0]
                        
                    if (count and count > 0) or (actions_count and actions_count > 0):
                        st.info(f"**{count:,} rows** | **{actions_count:,} actions** | AED {spend or 0:,.0f} spend")
                        
                        confirm_move = st.checkbox(f"✅ Confirm move to {to_name}", key="final_reassign_confirm")
                        if confirm_move and st.button("Execute Move", type="primary", key="execute_reassign"):
                            # CHECK 1 — same account guard
                            if from_id == to_id:
                                st.error('Source and destination accounts are the same — reassignment cancelled.')
                                return
                            # CHECK 2 — verify source has data (full history, not just the date range)
                            count_all = db.execute_scalar("SELECT COUNT(*) FROM target_stats WHERE client_id = %s", (from_id,))
                            if not count_all or count_all == 0:
                                st.warning(f'No data found for source account {from_id} — reassignment cancelled.')
                                return
                            # Proceed with the reassignment UPDATE (unchanged)
                            affected_rows = db.reassign_data(from_id, to_id, str(start_date), str(end_date))
                            # CHECK 3 — report row count after UPDATE
                            st.success(f'Reassigned {affected_rows} rows from {from_id} to {to_id}.')
                            if affected_rows == 0:
                                st.warning('UPDATE completed but 0 rows were affected — verify account IDs.')
                            del st.session_state['reassign_preview_active']
                    else:
                        st.warning("No data found in range")
                except Exception as e:
                    st.error(f"Error: {e}")
        
        st.markdown("---")
        
        # Clear all
        if any(status.values()):
            if st.button("🗑️ Reset & Clear All Data", type="secondary"):
                hub.clear_all()
                st.success("Data cleared.")
                st.rerun()


def _validate_campaigns(hub: DataHub, account_id: str) -> dict:
    """
    Validate uploaded campaigns against historical data for this account.
    Returns dict with validation results.
    """
    from app_core.db_manager import get_db_manager
    
    uploaded_data = hub.get_data('search_term_report')
    if uploaded_data is None or 'Campaign Name' not in uploaded_data.columns:
        return {'needs_review': False, 'overlap_pct': 100}
    
    uploaded_campaigns = set(uploaded_data['Campaign Name'].dropna().unique())
    
    try:
        db = get_db_manager(st.session_state.get('test_mode', False))
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT campaign_name 
                FROM target_stats 
                WHERE client_id = ?
            ''', (account_id,))
            historical_campaigns = set(row[0] for row in cursor.fetchall())
    except:
        return {'needs_review': False, 'overlap_pct': 100}
    
    if not historical_campaigns:
        return {'needs_review': False, 'overlap_pct': 100, 'first_upload': True}
    
    overlap = uploaded_campaigns & historical_campaigns
    new_campaigns = uploaded_campaigns - historical_campaigns
    missing_campaigns = historical_campaigns - uploaded_campaigns
    
    overlap_pct = (len(overlap) / len(historical_campaigns) * 100) if historical_campaigns else 100
    needs_review = overlap_pct < 30
    
    return {
        'needs_review': needs_review,
        'overlap_pct': overlap_pct,
        'new_count': len(new_campaigns),
        'missing_count': len(missing_campaigns),
        'total_uploaded': len(uploaded_campaigns),
        'total_historical': len(historical_campaigns),
        'overlap_campaigns': overlap,
        'new_campaigns': new_campaigns,
        'missing_campaigns': missing_campaigns
    }
