"""Transform layer tests."""

from __future__ import annotations

from pipeline.transform import parse_records, validate_row


def test_parse_records_maps_fields_correctly(sample_record):
    rows = parse_records([sample_record], "A2VIGQ35RCS4UG", "query_123", "s2c_uae_test")
    assert len(rows) == 1
    row = rows[0]
    assert row["child_asin"] == "B0DSFZK5W7"
    assert row["parent_asin"] == "B0DSFYW6YL"
    assert row["ordered_revenue"] == 239.34
    assert row["units_ordered"] == 6
    assert row["sessions"] == 61
    assert row["buy_box_percentage"] == 94.74
    assert row["unit_session_percentage"] == 9.84
    assert row["marketplace_id"] == "A2VIGQ35RCS4UG"
    assert row["account_id"] == "s2c_uae_test"
    assert row["query_id"] == "query_123"


def test_validate_row_passes_valid_row(sample_record):
    rows = parse_records([sample_record], "A2VIGQ35RCS4UG", "q1", "s2c_uae_test")
    valid, reason = validate_row(rows[0])
    assert valid is True
    assert reason == ""


def test_validate_row_fails_missing_asin():
    row = {"report_date": "2026-02-09", "marketplace_id": "A2VIGQ35RCS4UG", "child_asin": None}
    valid, reason = validate_row(row)
    assert valid is False
    assert "child_asin" in reason


def test_parse_records_handles_empty_list():
    rows = parse_records([], "A2VIGQ35RCS4UG", "q1", "s2c_uae_test")
    assert rows == []


def test_parse_records_handles_nested_payload(sample_record):
    nested = {"data": {"analytics_salesAndTraffic_2024_04_24": {"salesAndTrafficByAsin": [sample_record]}}}
    rows = parse_records([nested], "A2VIGQ35RCS4UG", "q1", "s2c_uae_test")
    assert len(rows) == 1
    assert rows[0]["child_asin"] == "B0DSFZK5W7"
