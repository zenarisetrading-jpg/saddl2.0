"""
Core Utilities
==============
Shared logic and constants used across multiple features (Impact, Executive, Reporting).
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any

# ==========================================
# MULTI-HORIZON IMPACT MEASUREMENT CONFIG
# ==========================================
IMPACT_WINDOWS = {
    "before_window_days": 14,       # Fixed 14-day baseline for all horizons
    "maturity_buffer_days": 3,      # Days after window for attribution to settle
    
    "horizons": {
        "14D": {
            "days": 14,
            "maturity": 17,  # 14 + 3
            "label": "14-Day Impact",
        },
        "30D": {
            "days": 30,
            "maturity": 33,  # 30 + 3
            "label": "30-Day Impact",
        },
        "60D": {
            "days": 60,
            "maturity": 63,  # 60 + 3
            "label": "60-Day Impact",
        },
    },
    
    "default_horizon": "14D",
    "available_horizons": ["14D", "30D", "60D"],
}


def get_maturity_status(action_date, latest_data_date, horizon: str = "14D") -> dict:
    """
    Check if action has matured enough for impact calculation at a specific horizon.
    
    Maturity formula: action_date + horizon_days + buffer_days ≤ latest_data_date
    
    Args:
        action_date: Date the action was logged (T0)
        latest_data_date: The most recent date in the data (from DB)
        horizon: Measurement horizon - "14D", "30D", or "60D"
        
    Returns:
        dict with is_mature, maturity_date, days_until_mature, status, horizon
    """
    # Get horizon config
    if horizon not in IMPACT_WINDOWS["horizons"]:
        horizon = IMPACT_WINDOWS["default_horizon"]
    horizon_config = IMPACT_WINDOWS["horizons"][horizon]
    after_window_days = horizon_config["days"]
    maturity_buffer_days = IMPACT_WINDOWS["maturity_buffer_days"]
    
    # Parse action_date to date object
    if isinstance(action_date, str):
        try:
            action_date = datetime.strptime(action_date[:10], "%Y-%m-%d").date()
        except ValueError:
            pass # Fallback
    elif hasattr(action_date, 'date'):  # pd.Timestamp or datetime
        action_date = action_date.date()
    
    # Check if failed to parse (still date object?)
    if not isinstance(action_date, (datetime, pd.Timestamp)) and not hasattr(action_date, 'year'):
         # If pandas series passed or invalid check
         pass 

    # Parse latest_data_date
    if isinstance(latest_data_date, str):
         try:
            latest_data_date = datetime.strptime(latest_data_date[:10], "%Y-%m-%d").date()
         except ValueError:
            pass
    elif hasattr(latest_data_date, 'date'):
        latest_data_date = latest_data_date.date()
    
    # Ensure both are date objects comparisons
    # If one is None or invalid, return False/Immature
    if not hasattr(action_date, 'year') or not hasattr(latest_data_date, 'year'):
        return {
            "is_mature": False,
            "status": "Invalid Dates"
        }

    # Calculate when this action will be mature
    after_window_end = action_date + timedelta(days=after_window_days)
    maturity_date = after_window_end + timedelta(days=maturity_buffer_days)
    
    # Check against latest data date
    days_until_mature = (maturity_date - latest_data_date).days
    is_mature = latest_data_date >= maturity_date
    
    if is_mature:
        status = "Measured"
    elif latest_data_date >= after_window_end:
        status = f"Pending ({days_until_mature}d)"
    else:
        days_in = (latest_data_date - action_date).days
        status = f"In Window ({max(0, days_in)}/{after_window_days}d)"
    
    return {
        "is_mature": is_mature,
        "maturity_date": maturity_date,
        "days_until_mature": max(0, days_until_mature),
        "status": status,
        "horizon": horizon,
        "horizon_config": horizon_config,
    }
