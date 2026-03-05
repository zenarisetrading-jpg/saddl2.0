"""DB writer tests with mocks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pipeline.db_writer import upsert_sales_traffic


def test_upsert_sales_traffic_no_rows_short_circuit():
    with patch("pipeline.db_writer.psycopg2.connect") as mock_connect:
        count = upsert_sales_traffic([], "postgresql://example")
        assert count == 0
        mock_connect.assert_not_called()


def test_upsert_sales_traffic_executes_for_rows():
    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_conn.__enter__.return_value = fake_conn
    fake_cursor.__enter__.return_value = fake_cursor
    fake_conn.cursor.return_value = fake_cursor
    fake_cursor.rowcount = 1

    row = {
        "report_date": "2026-02-15",
        "marketplace_id": "A2VIGQ35RCS4UG",
        "account_id": "s2c_uae_test",
        "child_asin": "B0DSFZK5W7",
        "parent_asin": "B0DSFYW6YL",
        "ordered_revenue": 239.34,
        "ordered_revenue_currency": "AED",
        "units_ordered": 6,
        "total_order_items": 5,
        "page_views": 80,
        "sessions": 61,
        "buy_box_percentage": 94.74,
        "unit_session_percentage": 9.84,
        "query_id": "q-1",
    }

    with patch("pipeline.db_writer.psycopg2.connect", return_value=fake_conn), patch(
        "pipeline.db_writer.execute_values"
    ) as mock_execute_values:
        result = upsert_sales_traffic([row], "postgresql://example")

    assert result == 1
    assert mock_execute_values.called
