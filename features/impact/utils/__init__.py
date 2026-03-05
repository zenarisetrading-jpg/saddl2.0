"""
Impact Dashboard Utilities

Utility functions for the Impact & Results dashboard.
"""

from features.impact.utils.export_utils import (
    export_impact_data_with_version,
    check_model_version_consistency,
    render_model_version_badge,
    render_export_button
)


def get_impact_col(df) -> str:
    """
    Select the best available impact column with safe fallback.

    Priority:
    1) final_impact_v33 (v3.3 weighted)
    2) final_decision_impact (v3.2 weighted)
    3) decision_impact (raw)
    """
    if df is None:
        return 'decision_impact'
    if 'final_impact_v33' in df.columns:
        return 'final_impact_v33'
    if 'final_decision_impact' in df.columns:
        return 'final_decision_impact'
    return 'decision_impact'

__all__ = [
    'export_impact_data_with_version',
    'check_model_version_consistency',
    'render_model_version_badge',
    'render_export_button',
    'get_impact_col'
]
