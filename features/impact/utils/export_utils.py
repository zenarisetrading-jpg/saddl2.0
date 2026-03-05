"""
Export Utilities for Impact Dashboard

Handles data export with model version tracking and comparison warnings.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional
import io


def export_impact_data_with_version(
    df: pd.DataFrame,
    filename_prefix: str = "impact_data",
    include_metadata: bool = True
) -> bytes:
    """
    Export impact data to CSV with model version tracking.

    Args:
        df: DataFrame containing impact data
        filename_prefix: Prefix for the filename
        include_metadata: Whether to include metadata header rows

    Returns:
        bytes: CSV data as bytes

    Usage:
        csv_bytes = export_impact_data_with_version(impact_df)
        st.download_button("Download", csv_bytes, "impact.csv", "text/csv")
    """
    if df.empty:
        return b""

    # Get model version from DataFrame or system
    model_version = df['model_version'].iloc[0] if 'model_version' in df.columns else "unknown"

    # Create a copy to avoid modifying original
    export_df = df.copy()

    if include_metadata:
        # Create metadata header
        metadata = pd.DataFrame({
            'Metadata': [
                f'Export Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                f'Impact Model Version: {model_version}',
                f'Total Actions: {len(export_df)}',
                f'',  # Blank row separator
                'Column Descriptions:',
                '- final_impact_v33: Final attributed impact with v3.3 adjustments',
                '- market_shift: Account-level market condition adjustment',
                '- scale_factor: Per-action scale efficiency adjustment',
                '- decision_impact_v32: Backup v3.2 impact for comparison',
                '---DATA START---'
            ]
        })

        # Convert to CSV with metadata header
        output = io.StringIO()
        metadata.to_csv(output, index=False)
        export_df.to_csv(output, index=False)
        csv_bytes = output.getvalue().encode('utf-8')
    else:
        # Standard CSV export
        csv_bytes = export_df.to_csv(index=False).encode('utf-8')

    return csv_bytes


def check_model_version_consistency(df: pd.DataFrame) -> dict:
    """
    Check if DataFrame contains data from mixed model versions.

    Args:
        df: DataFrame with model_version column

    Returns:
        dict with:
            - is_consistent: bool
            - versions: list of versions found
            - warning_message: str (if inconsistent)
    """
    if 'model_version' not in df.columns:
        return {
            'is_consistent': True,
            'versions': ['unknown'],
            'warning_message': None
        }

    versions = df['model_version'].unique().tolist()
    is_consistent = len(versions) == 1

    warning_message = None
    if not is_consistent:
        warning_message = (
            f"⚠️ **Mixed Model Versions Detected**: This data contains actions calculated "
            f"with different impact models ({', '.join(versions)}). Direct comparison may "
            f"not be meaningful. Consider filtering by action_date or recalculating all "
            f"actions with the same model version."
        )

    return {
        'is_consistent': is_consistent,
        'versions': versions,
        'warning_message': warning_message
    }


def render_model_version_badge(df: pd.DataFrame):
    """
    Render a badge showing the current model version.

    Args:
        df: DataFrame with model_version column
    """
    version_check = check_model_version_consistency(df)

    if version_check['is_consistent']:
        version = version_check['versions'][0]
        st.caption(f"🔢 Model Version: **{version}**")
    else:
        st.warning(version_check['warning_message'])


def render_export_button(df: pd.DataFrame, filename_prefix: str = "impact_data"):
    """
    Render an export button with model version tracking.

    Args:
        df: DataFrame to export
        filename_prefix: Prefix for the downloaded filename
    """
    if df.empty:
        return

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_version = df['model_version'].iloc[0] if 'model_version' in df.columns else "unknown"
    filename = f"{filename_prefix}_{model_version}_{timestamp}.csv"

    # Export data
    csv_bytes = export_impact_data_with_version(df, filename_prefix)

    # Render download button
    st.download_button(
        label="📥 Export Impact Data",
        data=csv_bytes,
        file_name=filename,
        mime="text/csv",
        help=f"Download impact data with model version {model_version}",
        use_container_width=False
    )
