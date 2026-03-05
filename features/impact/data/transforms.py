"""
Data Transforms - DataFrame transformations for impact calculations.
"""

import numpy as np
import pandas as pd


def validate_impact_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate that required Impact Model v3.3 columns exist in the dataframe.

    This function replaces the old ensure_impact_columns() which redundantly
    recalculated impact values. With v3.3, ALL impact calculations are done
    in postgres_manager.get_action_impact().

    Args:
        df: Impact DataFrame from postgres_manager

    Returns:
        The same DataFrame (unmodified) if validation passes

    Raises:
        ValueError: If required v3.3 columns are missing
    """
    # Required core columns (existed in v3.2)
    required_core = [
        'decision_impact',
        'final_decision_impact',
        'market_tag',
        'expected_sales'
    ]

    # Required v3.3 columns (new in v3.3)
    required_v33 = [
        'market_shift',
        'scale_factor',
        'impact_v33',
        'final_impact_v33'
    ]

    missing_core = [col for col in required_core if col not in df.columns]
    missing_v33 = [col for col in required_v33 if col not in df.columns]

    if missing_core:
        raise ValueError(
            f"Database missing required core columns: {missing_core}. "
            f"This indicates a problem with postgres_manager.get_action_impact()."
        )

    if missing_v33:
        # v3.3 columns missing means Impact Model v3.3 is not active
        # This is not an error if IMPACT_MODEL_VERSION = "v3.2"
        import warnings
        warnings.warn(
            f"Impact Model v3.3 columns missing: {missing_v33}. "
            f"Using v3.2 values. Set IMPACT_MODEL_VERSION='v3.3' in postgres_manager.py to enable v3.3.",
            UserWarning
        )

    return df


# [DEPRECATED] Legacy function kept for backwards compatibility
# Remove this after confirming all code paths use validate_impact_columns()
def ensure_impact_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    DEPRECATED: This function is deprecated as of Impact Model v3.3.
    Use validate_impact_columns() instead.

    All impact calculations are now performed in postgres_manager.get_action_impact().
    This function now simply validates columns and returns the dataframe unmodified.
    """
    return validate_impact_columns(df)
