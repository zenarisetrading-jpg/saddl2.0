"""
Debug page for Impact Dashboard diagnostics.
Refactored to run as a module.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from app_core.db_manager import get_db_manager
from app_core.constants import ACTION_MATURITY_DAYS

def render_debug_metrics():
    """Render the debug diagnostics UI."""
    import os
    if os.environ.get('SADDL_ENV', '').lower() == 'production':
        st.error('Debug UI is disabled in production environments.')
        st.stop()

    st.subheader("🔍 Impact Dashboard Diagnostics")
    st.caption("Debug tool to identify why impact results aren't showing")

    db = get_db_manager()

    # Client ID input
    # Try to pre-fill from session state if available
    default_client = st.session_state.get('active_account_id', 'digiaansh_test')
    client_id = st.text_input("Client ID to diagnose", value=default_client)

    allowed_ids = [a['id'] for a in st.session_state.get('user_accounts', [])]
    if client_id and client_id not in allowed_ids:
        st.error('Access denied — you can only view accounts assigned to your organization.')
        st.stop()

    if st.button("Run Diagnostics", type="primary"):
        with st.spinner("Running diagnostics..."):
            st.markdown("---")

            # Check 1: Actions exist?
            st.subheader("1️⃣ Actions Log Check")
            with db._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"""
                        SELECT
                            COUNT(*) as total_actions,
                            MIN(action_date) as earliest_action,
                            MAX(action_date) as latest_action,
                            COUNT(DISTINCT action_type) as distinct_types
                        FROM actions_log
                        WHERE client_id = {db.placeholder}
                    """, (client_id,))
                    result = cursor.fetchone()

                    if hasattr(result, 'keys'):
                        action_count = result['total_actions']
                        earliest = result['earliest_action']
                        latest = result['latest_action']
                        types = result['distinct_types']
                    else:
                        action_count = result[0]
                        earliest = result[1]
                        latest = result[2]
                        types = result[3]

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Actions", action_count)
                    with col2:
                        st.metric("Earliest", str(earliest) if earliest else "N/A")
                    with col3:
                        st.metric("Latest", str(latest) if latest else "N/A")
                    with col4:
                        st.metric("Action Types", types)

                    if action_count == 0:
                        st.error("❌ NO ACTIONS FOUND! This is the root cause. Actions were never saved to database.")
                        st.info("**Solution**: Run optimizer and click 'Save to History' when leaving the optimizer page.")
                        return # Stop execution for this check
                    else:
                        st.success(f"✅ Found {action_count} actions in database")

                    # Show action types breakdown
                    cursor.execute(f"""
                        SELECT
                            action_type,
                            COUNT(*) as count,
                            MIN(action_date) as first_action,
                            MAX(action_date) as last_action
                        FROM actions_log
                        WHERE client_id = {db.placeholder}
                        GROUP BY action_type
                        ORDER BY count DESC
                    """, (client_id,))

                    action_types = cursor.fetchall()
                    st.write("**Action Types Breakdown:**")
                    types_data = []
                    for row in action_types:
                        if hasattr(row, 'keys'):
                            types_data.append({
                                'Type': row['action_type'],
                                'Count': row['count'],
                                'First': row['first_action'],
                                'Last': row['last_action']
                            })
                        else:
                            types_data.append({
                                'Type': row[0],
                                'Count': row[1],
                                'First': row[2],
                                'Last': row[3]
                            })
                    st.dataframe(pd.DataFrame(types_data), use_container_width=True, hide_index=True)

            st.markdown("---")

            # Check 2: Performance data exists?
            st.subheader("2️⃣ Performance Data Check")
            with db._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"""
                        SELECT
                            COUNT(*) as total_rows,
                            MIN(start_date) as earliest_date,
                            MAX(start_date) as latest_date,
                            COUNT(DISTINCT campaign_name) as campaigns
                        FROM target_stats
                        WHERE client_id = {db.placeholder}
                    """, (client_id,))
                    result = cursor.fetchone()

                    if hasattr(result, 'keys'):
                        rows = result['total_rows']
                        earliest_stats = result['earliest_date']
                        latest_stats = result['latest_date']
                        campaigns = result['campaigns']
                    else:
                        rows = result[0]
                        earliest_stats = result[1]
                        latest_stats = result[2]
                        campaigns = result[3]

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Rows", f"{rows:,}")
                    with col2:
                        st.metric("Earliest", str(earliest_stats))
                    with col3:
                        st.metric("Latest", str(latest_stats))
                    with col4:
                        st.metric("Campaigns", campaigns)

                    if rows == 0:
                        st.error("❌ NO PERFORMANCE DATA! Cannot measure impact without target_stats.")
                        return
                    else:
                        st.success(f"✅ Found {rows:,} rows of performance data")

            st.markdown("---")

            # Check 3: Date overlap
            st.subheader("3️⃣ Date Overlap Analysis")
            with db._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"""
                        SELECT
                            (SELECT MAX(action_date::date) FROM actions_log WHERE client_id = {db.placeholder}) as latest_action,
                            (SELECT MAX(start_date) FROM target_stats WHERE client_id = {db.placeholder}) as latest_stats
                    """, (client_id, client_id))
                    result = cursor.fetchone()

                    if hasattr(result, 'keys'):
                        latest_action = result['latest_action']
                        latest_stats = result['latest_stats']
                    else:
                        latest_action = result[0]
                        latest_stats = result[1]

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Latest Action Date", str(latest_action))
                    with col2:
                        st.metric("Latest Stats Date", str(latest_stats))

                    days_after = 0
                    if latest_action and latest_stats:
                        days_after = (latest_stats - latest_action).days
                        st.metric("Days of Data After Actions", days_after)

                        if days_after < 0:
                            st.error(f"❌ CRITICAL: Actions are {abs(days_after)} days AFTER performance data!")
                            st.error("**Solution**: Upload fresh Search Term Reports with data AFTER the action dates.")
                        elif days_after < ACTION_MATURITY_DAYS:
                            st.warning(f"⚠️ Only {days_after} days of data after actions. Need {ACTION_MATURITY_DAYS}+ days for 14D measurement.")
                            st.info("**Solution**: Upload more recent Search Term Reports.")
                        else:
                            st.success(f"✅ {days_after} days available - sufficient for impact measurement!")
                            if days_after >= 60:
                                st.info("All horizons (14D/30D/60D) can be measured")
                            elif days_after >= 30:
                                st.info("14D and 30D horizons can be measured")
                            else:
                                st.info("Only 14D horizon can be measured")

            st.markdown("---")

            # Check 4: Campaign matching
            st.subheader("4️⃣ Campaign Name Matching")
            with db._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"""
                        WITH action_campaigns AS (
                            SELECT DISTINCT LOWER(TRIM(campaign_name)) as campaign
                            FROM actions_log
                            WHERE client_id = {db.placeholder}
                        ),
                        stats_campaigns AS (
                            SELECT DISTINCT LOWER(TRIM(campaign_name)) as campaign
                            FROM target_stats
                            WHERE client_id = {db.placeholder}
                        )
                        SELECT
                            (SELECT COUNT(*) FROM action_campaigns) as action_count,
                            (SELECT COUNT(*) FROM stats_campaigns) as stats_count,
                            (SELECT COUNT(*) FROM action_campaigns ac
                             INNER JOIN stats_campaigns sc ON ac.campaign = sc.campaign) as matching_count
                    """, (client_id, client_id))
                    result = cursor.fetchone()

                    if hasattr(result, 'keys'):
                        action_camps = result['action_count']
                        stats_camps = result['stats_count']
                        matching = result['matching_count']
                    else:
                        action_camps = result[0]
                        stats_camps = result[1]
                        matching = result[2]

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Campaigns in Actions", action_camps)
                    with col2:
                        st.metric("Campaigns in Stats", stats_camps)
                    with col3:
                        st.metric("Matching", matching)

                    if matching == 0:
                        st.error("❌ NO MATCHING CAMPAIGNS! Campaign names don't align between tables.")
                        st.error("**Solution**: Check if campaigns were renamed, or data uploaded with different naming.")

                        # Show samples
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.write("**Sample from actions_log:**")
                            cursor.execute(f"""
                                SELECT DISTINCT campaign_name
                                FROM actions_log
                                WHERE client_id = {db.placeholder}
                                LIMIT 5
                            """, (client_id,))
                            actions_sample = [row[0] if not hasattr(row, 'keys') else row['campaign_name'] for row in cursor.fetchall()]
                            for camp in actions_sample:
                                st.code(camp)

                        with col_b:
                            st.write("**Sample from target_stats:**")
                            cursor.execute(f"""
                                SELECT DISTINCT campaign_name
                                FROM target_stats
                                WHERE client_id = {db.placeholder}
                                LIMIT 5
                            """, (client_id,))
                            stats_sample = [row[0] if not hasattr(row, 'keys') else row['campaign_name'] for row in cursor.fetchall()]
                            for camp in stats_sample:
                                st.code(camp)
                    elif matching < action_camps:
                        match_rate = (matching / action_camps) * 100
                        st.warning(f"⚠️ Partial match: {match_rate:.1f}% of action campaigns have matching performance data")
                    else:
                        st.success("✅ All campaigns match!")

            st.markdown("---")

            # Final summary
            st.subheader("📊 Summary & Recommendations")

            # Re-check all conditions for final verdict
            has_actions = action_count > 0
            has_stats = rows > 0
            dates_ok = days_after >= ACTION_MATURITY_DAYS if latest_action and latest_stats else False
            camps_ok = matching > 0

            if has_actions and has_stats and dates_ok and camps_ok:
                st.success("✅ **All checks passed!** Impact data should be visible.")
                st.info("**Possible issues:**")
                st.write("- Streamlit cache needs clearing (Press 'C' in app)")
                st.write("- Session state issue (refresh page)")
                st.write("- `data_upload_timestamp` not updated after upload")
            elif not has_actions:
                st.error("❌ **Root cause: No actions in database**")
                st.write("**Fix:** Run optimizer and save actions to history")
            elif not dates_ok:
                st.error("❌ **Root cause: Insufficient data after action dates**")
                st.write("**Fix:** Upload fresh Search Term Reports with recent data")
            elif not camps_ok:
                st.error("❌ **Root cause: Campaign names don't match**")
                st.write("**Fix:** Check campaign naming consistency in data uploads")
            else:
                st.warning("⚠️ **Some checks failed** - see details above")
