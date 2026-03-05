"""Phase 1 tests for BSR pipeline behavior."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_bsr_pipeline_module():
    # Remove partially imported module state between tests if previous import failed.
    if "pipeline.bsr_pipeline" in sys.modules:
        del sys.modules["pipeline.bsr_pipeline"]
    return importlib.import_module("pipeline.bsr_pipeline")


def test_bsr_api_auth():
    """Verify BSR pipeline delegates authentication to SP-API token flow."""
    bsr_pipeline = _load_bsr_pipeline_module()

    cfg = {"lwa_client_id": "x", "lwa_client_secret": "y", "refresh_token_uae": "z"}
    with patch.object(bsr_pipeline, "get_token", return_value="token-123") as mock_get_token:
        token = bsr_pipeline.authenticate(config=cfg)
    assert token == "token-123"
    mock_get_token.assert_called_once_with(cfg)


def test_bsr_single_asin_pull():
    """Verify single-ASIN response parsing extracts category + rank."""
    bsr_pipeline = _load_bsr_pipeline_module()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "asin": "B0TEST12345",
        "salesRanks": [
            {
                "title": "Sports Nutrition Whey Protein Powders",
                "rank": 12450,
                "classificationRanks": [{"title": "Health & Personal Care", "rank": 45230}],
            }
        ],
    }
    cfg = {
        "endpoint": "https://sellingpartnerapi-eu.amazon.com",
        "marketplace_uae": "A2VIGQ35RCS4UG",
        "spapi_account_id": "s2c_uae_test",
        "aws_access_key": "ak",
        "aws_secret_key": "sk",
        "aws_region": "eu-west-1",
    }

    with patch.object(bsr_pipeline, "_request_with_retries", return_value=mock_response):
        rows = bsr_pipeline.fetch_single_asin_bsr(cfg, token="token", asin="B0TEST12345", report_date="2026-02-17")

    assert len(rows) >= 1
    assert rows[0]["asin"] == "B0TEST12345"
    assert rows[0]["category_name"] == "Sports Nutrition Whey Protein Powders"
    assert rows[0]["rank"] == 12450


def test_bsr_rate_limiting():
    """Verify 5 req/sec pacing is enforced across ASIN batch pulls."""
    bsr_pipeline = _load_bsr_pipeline_module()

    asins = [f"B0TEST{i:05d}" for i in range(100)]
    cfg = {"marketplace_uae": "A2VIGQ35RCS4UG"}

    with (
        patch.object(bsr_pipeline, "fetch_single_asin_bsr", return_value=[]),
        patch.object(bsr_pipeline.time, "sleep") as mock_sleep,
    ):
        bsr_pipeline.fetch_bsr_batch(
            config=cfg,
            token="token",
            asins=asins,
            report_date="2026-02-17",
            rate_limit_delay=0.2,
        )

    assert mock_sleep.call_count == 99
    assert all(call.args[0] == pytest.approx(0.2) for call in mock_sleep.call_args_list)


def test_bsr_upsert_idempotency():
    """Verify upsert uses proper ON CONFLICT key to remain idempotent."""
    bsr_pipeline = _load_bsr_pipeline_module()

    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_conn.__enter__.return_value = fake_conn
    fake_cursor.__enter__.return_value = fake_cursor
    fake_conn.cursor.return_value = fake_cursor
    fake_cursor.rowcount = 1

    rows = [
        {
            "report_date": "2026-02-17",
            "marketplace_id": "A2VIGQ35RCS4UG",
            "account_id": "s2c_uae_test",
            "asin": "B0TEST12345",
            "category_name": "Sports Nutrition Whey Protein Powders",
            "category_id": "cat-1",
            "rank": 12450,
        }
    ]

    with (
        patch.object(bsr_pipeline.psycopg2, "connect", return_value=fake_conn),
        patch.object(bsr_pipeline, "execute_values") as mock_execute_values,
    ):
        count = bsr_pipeline.upsert_bsr_history(rows, "postgresql://example")

    assert count == 1
    sql = mock_execute_values.call_args.args[1]
    assert "ON CONFLICT (report_date, marketplace_id, account_id, asin, category_id)" in sql
    assert "DO UPDATE SET" in sql


def test_bsr_trends_view():
    """Verify bsr_trends view includes required trend computations."""
    migration = Path("db/migrations/003_add_bsr_history.sql").read_text()

    assert "CREATE VIEW sc_analytics.bsr_trends AS" in migration or "CREATE OR REPLACE VIEW sc_analytics.bsr_trends AS" in migration
    assert "rank_change_7d" in migration
    assert "rank_status_7d" in migration
    assert "LAG(b.rank, 7)" in migration
