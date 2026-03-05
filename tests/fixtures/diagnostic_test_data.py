"""Mock diagnostics datasets for UI/testing (draft-only prep)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List

import pandas as pd


def _dates(days: int = 14) -> List[date]:
    today = date.today()
    return [today - timedelta(days=days - i - 1) for i in range(days)]


def make_signal_dataframe(signal_key: str, days: int = 14) -> pd.DataFrame:
    ds = _dates(days)
    if signal_key == "demand_contraction":
        return pd.DataFrame(
            {
                "report_date": ds,
                "avg_organic_cvr": [3.5 - i * 0.05 for i in range(days)],
                "ad_cvr": [3.7 - i * 0.04 for i in range(days)],
                "avg_cpc": [1.82 + (i % 3) * 0.01 for i in range(days)],
                "is_demand_contraction": [i >= 7 for i in range(days)],
                "organic_cvr_change_pct": [-(i * 1.1) for i in range(days)],
                "ad_cvr_change_pct": [-(i * 0.9) for i in range(days)],
            }
        )
    if signal_key == "organic_decay":
        return pd.DataFrame(
            {
                "report_date": ds,
                "child_asin": ["B0TESTASIN01"] * days,
                "sessions": [110 - i * 3 for i in range(days)],
                "sessions_7d_ago": [120 - i * 2 for i in range(days)],
                "session_change_pct": [-(6 + i * 0.8) for i in range(days)],
                "current_bsr": [13000 + i * 320 for i in range(days)],
                "rank_7d_ago": [11500 + i * 280 for i in range(days)],
                "rank_status_7d": ["DECLINING"] * days,
                "ordered_revenue": [340 - i * 7 for i in range(days)],
                "buy_box_percentage": [95] * days,
                "is_rank_decay": [i >= 5 for i in range(days)],
            }
        )
    if signal_key == "non_advertised_winners":
        return pd.DataFrame(
            {
                "report_date": [ds[-1]] * 3,
                "child_asin": ["B0WIN0001", "B0WIN0002", "B0WIN0003"],
                "revenue_30d": [4300, 2600, 1200],
                "units_30d": [130, 88, 37],
                "avg_cvr": [11.2, 8.6, 6.2],
                "avg_sessions_per_day": [38, 29, 17],
                "avg_daily_revenue": [143.3, 86.7, 40.0],
                "priority": ["HIGH", "HIGH", "MEDIUM"],
            }
        )
    if signal_key == "harvest_cannibalization":
        return pd.DataFrame(
            {
                "report_date": ds,
                "harvest_sales": [1500 + i * 28 for i in range(days)],
                "harvest_roas": [2.0 + i * 0.03 for i in range(days)],
                "discovery_sales": [780 - i * 6 for i in range(days)],
                "total_ordered_revenue": [4850 + (i % 2) * 22 for i in range(days)],
                "is_cannibalizing": [i >= 7 for i in range(days)],
            }
        )
    if signal_key == "over_negation":
        return pd.DataFrame(
            {
                "report_date": ds,
                "total_impressions": [12000 - i * 260 for i in range(days)],
                "ctr": [0.32 + i * 0.002 for i in range(days)],
                "cvr": [3.0 + i * 0.01 for i in range(days)],
                "roas": [1.9 + i * 0.04 for i in range(days)],
                "total_sales": [4200 - i * 70 for i in range(days)],
                "is_over_negated": [i >= 6 for i in range(days)],
            }
        )
    raise ValueError(f"Unknown signal_key: {signal_key}")


def make_overview_payload() -> Dict:
    return {
        "generated_at_utc": "2026-02-18T00:00:00",
        "client_id": "s2c_uae_test",
        "marketplace_id": "A2VIGQ35RCS4UG",
        "signal_counts": {
            "demand_contraction": 5,
            "organic_decay": 3,
            "non_advertised_winners": 3,
            "harvest_cannibalization": 4,
            "over_negation": 4,
        },
        "signal_cards": [
            {
                "signal_key": "demand_contraction",
                "title": "Market Demand Contraction",
                "severity": "HIGH",
                "confidence": 95,
                "report_date": "2026-02-17",
                "evidence": [
                    "Organic CVR change: -11.0%",
                    "Ad CVR change: -9.0%",
                    "Avg CPC: 1.84",
                ],
                "raw": {},
            }
        ],
        "impact_context": {
            "total_actions": 12,
            "winners": 10,
            "win_rate": 83.3,
            "avg_impact": 12.4,
            "raw": {},
        },
    }

