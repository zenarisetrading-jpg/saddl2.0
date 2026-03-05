"""Data Kiosk query helper tests."""

from __future__ import annotations

import json

from pipeline.data_kiosk import build_query


def test_build_query_uses_aggregate_by_child():
    body = build_query("2026-02-15", "2026-02-15", "A2VIGQ35RCS4UG")
    payload = json.loads(body)
    query = payload["query"]
    assert "aggregateBy: CHILD" in query
    assert 'startDate: "2026-02-15"' in query
    assert 'endDate: "2026-02-15"' in query


def test_build_query_excludes_invalid_granularity_keys():
    body = build_query("2026-02-15", "2026-02-15", "A2VIGQ35RCS4UG")
    query = json.loads(body)["query"]
    assert "dateGranularity" not in query
    assert "asinGranularity" not in query
