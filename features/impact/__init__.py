"""
Impact Dashboard v2 - Refactored Module

This module provides the Impact & Results dashboard functionality,
broken down into clean, focused sub-modules.

Public API:
    - render_impact_dashboard: Main dashboard render function
    - get_recent_impact_summary: Export for home page
    - get_maturity_status: Re-exported from app_core.utils
    - create_roas_waterfall_figure: Chart factory for reports
    - create_decision_timeline_figure: Chart factory for reports
"""

# Main entry point
from features.impact.main import render_impact_dashboard_v2

# Public exports for external modules (report_card.py, executive_dashboard.py)
from features.impact.exports import (
    get_recent_impact_summary,
    render_reference_data_badge,
)

# Re-export from app_core.utils for backward compatibility
from app_core.utils import get_maturity_status

# Chart factories used by client reports
from features.impact.charts.waterfall import create_roas_waterfall_figure
from features.impact.charts.timeline import create_decision_timeline_figure

# Alias for final migration
render_impact_dashboard = render_impact_dashboard_v2

__all__ = [
    'render_impact_dashboard',
    'render_impact_dashboard_v2',
    'get_recent_impact_summary',
    'get_maturity_status',
    'render_reference_data_badge',
    'create_roas_waterfall_figure',
    'create_decision_timeline_figure',
]
