"""Performance dashboard shared modules."""

from .constants import DEFAULT_TARGET_ROAS, DEFAULT_TARGET_TACOS
from .metrics import (
    calculate_roas,
    calculate_tacos,
    calculate_cvr,
    calculate_organic_pct,
    calculate_days_of_cover,
    compute_account_health_score,
)
from .data_access import check_spapi_available

__all__ = [
    "DEFAULT_TARGET_ROAS",
    "DEFAULT_TARGET_TACOS",
    "calculate_roas",
    "calculate_tacos",
    "calculate_cvr",
    "calculate_organic_pct",
    "calculate_days_of_cover",
    "compute_account_health_score",
    "check_spapi_available",
]

