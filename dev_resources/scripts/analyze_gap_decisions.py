"""
Script to analyze gap decisions and identify outliers causing inflated per-decision impact.

Usage:
    streamlit run analyze_gap_decisions.py

This script will:
1. Fetch all gap decisions from the current data
2. Calculate detailed statistics
3. Identify outliers
4. Export to CSV for manual inspection
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app_core.db_manager import get_db_manager
from features.impact.data.fetchers import fetch_impact_data
from features.impact.data.transforms import ensure_impact_columns

def main():
    st.set_page_config(page_title="Gap Decision Analysis", layout="wide")

    st.title("🔍 Gap Decision Analysis")
    st.caption("Investigate why per-decision gap impact is ~410 AED vs ~33 AED for wins")

    # Initialize database
    db_manager = st.session_state.get('db_manager')
    if not db_manager:
        db_manager = get_db_manager()
        st.session_state['db_manager'] = db_manager

    # Get all clients
    clients = db_manager.get_all_clients()
    if not clients:
        st.error("No clients found in database")
        return

    # Client selector
    client_id = st.selectbox("Select Client", options=list(clients.keys()), format_func=lambda x: f"{x} - {clients[x]}")

    if st.button("Analyze Gap Decisions", type="primary"):
        with st.spinner("Fetching and analyzing data..."):
            # Fetch impact data
            impact_df, full_summary = fetch_impact_data(client_id, test_mode=False, before_days=14, after_days=14, cache_version="gap_analysis_script")

            # Apply transforms
            impact_df = ensure_impact_columns(impact_df)

            # Filter for validated and mature
            v_mask = impact_df['validation_status'].str.contains('✓|CPC Validated|CPC Match|Directional|Confirmed|Normalized|Volume', na=False, regex=True)
            mature_mask = impact_df['is_mature'] == True

            validated_df = impact_df[v_mask & mature_mask].copy()

            # Get gap decisions
            gap_df = validated_df[validated_df['market_tag'].str.contains('Gap|Opportunity', case=False, na=False)].copy()

            st.success(f"Found {len(gap_df)} gap decisions")

            if len(gap_df) == 0:
                st.warning("No gap decisions found")
                return

            # Calculate statistics
            total_impact = gap_df['decision_impact'].sum()
            avg_impact = gap_df['decision_impact'].mean()
            median_impact = gap_df['decision_impact'].median()
            std_impact = gap_df['decision_impact'].std()

            # Display summary
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Gap Impact", f"{total_impact:,.0f} AED")
            with col2:
                st.metric("Count", len(gap_df))
            with col3:
                st.metric("Avg per Gap", f"{avg_impact:,.0f} AED", help="This should be ~400 AED based on your screenshot")
            with col4:
                st.metric("Median", f"{median_impact:,.0f} AED")

            # Show distribution
            st.subheader("Impact Distribution")

            # Breakdown by clicks
            bins = [0, 5, 10, 20, 50, 1000]
            labels = ['<5', '5-10', '10-20', '20-50', '50+']
            gap_df['click_bin'] = pd.cut(gap_df['before_clicks'], bins=bins, labels=labels)
            breakdown = gap_df.groupby('click_bin', observed=True)['decision_impact'].agg(['count', 'sum', 'mean']).reset_index()
            breakdown.columns = ['Click Range', 'Count', 'Total Impact', 'Avg Impact']

            st.dataframe(breakdown, width='stretch')

            # Identify outliers
            st.subheader("Outlier Detection")

            # Method 1: Absolute threshold
            outliers_1k = gap_df[gap_df['decision_impact'].abs() > 1000]
            st.write(f"**Decisions with |impact| > 1000 AED:** {len(outliers_1k)}")

            # Method 2: Statistical outliers (> 2 std dev from mean)
            outliers_2std = gap_df[abs(gap_df['decision_impact'] - avg_impact) > 2 * std_impact]
            st.write(f"**Decisions > 2 std deviations from mean:** {len(outliers_2std)}")

            # Show outliers
            if len(outliers_1k) > 0:
                st.subheader("Extreme Outliers (|impact| > 1000)")

                outlier_cols = [
                    'action_date', 'action_type', 'target_text',
                    'before_clicks', 'before_spend', 'before_sales',
                    'observed_after_clicks', 'observed_after_spend', 'observed_after_sales',
                    'expected_sales', 'decision_impact', 'market_tag', 'validation_status'
                ]
                outlier_cols = [c for c in outlier_cols if c in outliers_1k.columns]

                st.dataframe(
                    outliers_1k[outlier_cols].sort_values('decision_impact', key=abs, ascending=False),
                    width='stretch'
                )

                # Calculate impact of removing outliers
                impact_without_outliers = gap_df[gap_df['decision_impact'].abs() <= 1000]['decision_impact'].sum()
                count_without_outliers = len(gap_df[gap_df['decision_impact'].abs() <= 1000])
                avg_without_outliers = impact_without_outliers / count_without_outliers if count_without_outliers > 0 else 0

                st.info(f"""
                **Impact of removing extreme outliers:**
                - Total impact: {total_impact:,.0f} → {impact_without_outliers:,.0f} AED ({(impact_without_outliers-total_impact)/total_impact*100:+.1f}%)
                - Avg per gap: {avg_impact:,.0f} → {avg_without_outliers:,.0f} AED ({(avg_without_outliers-avg_impact)/avg_impact*100:+.1f}%)
                - Count: {len(gap_df)} → {count_without_outliers}
                """)

            # Export to CSV
            st.subheader("Export for Analysis")

            export_cols = [
                'action_date', 'action_type', 'target_text',
                'before_clicks', 'before_spend', 'before_sales',
                'observed_after_clicks', 'observed_after_spend', 'observed_after_sales',
                'expected_sales', 'decision_impact', 'market_tag', 'validation_status'
            ]
            export_cols = [c for c in export_cols if c in gap_df.columns]

            csv = gap_df[export_cols].sort_values('decision_impact', key=abs, ascending=False).to_csv(index=False)

            st.download_button(
                label="Download Gap Decisions CSV",
                data=csv,
                file_name=f"gap_decisions_{client_id}.csv",
                mime="text/csv"
            )

            # Show detailed table
            st.subheader("All Gap Decisions")
            st.dataframe(
                gap_df[export_cols].sort_values('decision_impact', key=abs, ascending=False),
                width='stretch',
                height=400
            )

if __name__ == "__main__":
    main()
