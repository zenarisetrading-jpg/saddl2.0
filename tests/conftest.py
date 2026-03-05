"""Shared test fixtures for pipeline tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_record():
    return {
        "startDate": "2026-02-09",
        "endDate": "2026-02-15",
        "childAsin": "B0DSFZK5W7",
        "parentAsin": "B0DSFYW6YL",
        "sales": {
            "orderedProductSales": {"amount": 239.34, "currencyCode": "AED"},
            "unitsOrdered": 6,
            "totalOrderItems": 5,
        },
        "traffic": {
            "pageViews": 80,
            "sessions": 61,
            "buyBoxPercentage": 94.74,
            "unitSessionPercentage": 9.84,
        },
    }
