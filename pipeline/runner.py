"""Pipeline orchestration entry points."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from pipeline.aggregator import upsert_account_daily, upsert_osi_index
from pipeline.auth import get_token
from pipeline.config import get_config
from pipeline.data_kiosk import build_query, create_query, download_document, poll_query
from pipeline.db_writer import log_pipeline_run, upsert_sales_traffic, verify_pipeline_tables_exist
from pipeline.transform import parse_records, validate_row
from pipelines.sp_api_client import get_token as get_spapi_token
from pipelines.spapi_pipeline import pull_fba_inventory


logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")


def run_single_date(target_date: str, config: Optional[dict] = None) -> int:
    cfg = config or get_config()
    start = time.time()
    query_id: Optional[str] = None
    verify_pipeline_tables_exist(cfg["database_url"])

    try:
        token = get_token(cfg)
        body = build_query(target_date, target_date, cfg["marketplace_uae"])
        query_id = create_query(cfg, token, body)
        log_pipeline_run(
            cfg["database_url"],
            target_date,
            cfg["marketplace_uae"],
            cfg["spapi_account_id"],
            query_id,
            "SUBMITTED",
        )

        status_obj = poll_query(cfg, token, query_id)
        data_document_id = status_obj.get("dataDocumentId")
        if not data_document_id:
            raise RuntimeError(f"Query {query_id} returned DONE without dataDocumentId")

        raw_records = download_document(cfg, token, data_document_id)
        parsed_rows = parse_records(
            raw_records,
            cfg["marketplace_uae"],
            query_id,
            cfg["spapi_account_id"],
        )

        valid_rows = []
        for row in parsed_rows:
            ok, _reason = validate_row(row)
            if ok:
                valid_rows.append(row)

        written = upsert_sales_traffic(valid_rows, cfg["database_url"])
        upsert_account_daily(
            cfg["database_url"],
            target_date,
            cfg["marketplace_uae"],
            cfg["ad_client_id"],
            cfg["spapi_account_id"],
        )
        upsert_osi_index(
            cfg["database_url"],
            target_date,
            cfg["marketplace_uae"],
            cfg["spapi_account_id"],
        )

        duration = int(time.time() - start)
        log_pipeline_run(
            cfg["database_url"],
            target_date,
            cfg["marketplace_uae"],
            cfg["spapi_account_id"],
            query_id,
            "DONE",
            records=written,
            duration=duration,
        )
        return written
    except Exception as exc:
        duration = int(time.time() - start)
        try:
            log_pipeline_run(
                cfg["database_url"],
                target_date,
                cfg["marketplace_uae"],
                cfg["spapi_account_id"],
                query_id,
                "FAILED",
                error=str(exc),
                duration=duration,
            )
        except Exception:
            logger.exception("Failed to write FAILED status to sc_raw.pipeline_log")
        raise


def run_daily_pull() -> None:
    cfg = get_config()
    lookback_offsets = [1, 2, 3, 7, 30]
    today = datetime.utcnow().date()
    last_submit_ts: Optional[float] = None
    inventory_synced = False

    for offset in lookback_offsets:
        target_date = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
        logger.info("Starting pipeline pull for %s", target_date)
        try:
            if last_submit_ts:
                elapsed = time.time() - last_submit_ts
                if elapsed < 60:
                    time.sleep(60 - elapsed)
            written = run_single_date(target_date, cfg)
            logger.info("Completed %s rows for %s", written, target_date)

            if not inventory_synced:
                try:
                    logger.info("Starting FBA Inventory pull for %s", cfg["spapi_account_id"])
                    get_spapi_token(force_refresh=True)
                    pull_fba_inventory(cfg["ad_client_id"])
                    inventory_synced = True
                except Exception:
                    logger.exception("Inventory pull failed")

            last_submit_ts = time.time()
        except Exception:
            logger.exception("Failed pull for %s", target_date)
            continue


def run_backfill(start_date: str, end_date: str) -> None:
    """
    Backfill continuous daily history from start_date to end_date (inclusive).
    Dates must be in YYYY-MM-DD format.
    """
    cfg = get_config()
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    if start > end:
        raise ValueError("start_date must be <= end_date")

    day_count = (end - start).days + 1
    logger.info("Starting backfill from %s to %s (%s days)", start_date, end_date, day_count)

    last_submit_ts: Optional[float] = None
    success = 0
    failed = 0

    for i in range(day_count):
        target_date = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        logger.info("Backfill pull for %s", target_date)
        try:
            if last_submit_ts:
                elapsed = time.time() - last_submit_ts
                if elapsed < 60:
                    time.sleep(60 - elapsed)
            written = run_single_date(target_date, cfg)
            logger.info("Backfill success %s rows for %s", written, target_date)
            success += 1
            last_submit_ts = time.time()
        except Exception:
            logger.exception("Backfill failed for %s", target_date)
            failed += 1
            continue

    logger.info("Backfill complete. success=%s failed=%s total=%s", success, failed, day_count)


if __name__ == "__main__":
    run_daily_pull()
