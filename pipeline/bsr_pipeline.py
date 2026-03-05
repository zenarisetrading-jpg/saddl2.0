"""BSR pipeline for Catalog Items sales rank ingestion into isolated schemas."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import psycopg2
import requests
from psycopg2.extras import execute_values
from requests import RequestException

from pipeline.auth import get_auth, get_token, make_headers
from pipeline.config import get_config


logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")


def authenticate(config: Optional[dict] = None) -> str:
    """Get an LWA access token for SP-API calls."""
    cfg = config or get_config()
    return get_token(cfg)


def _request_with_retries(method: str, url: str, max_retries: int = 4, **kwargs):
    """Retry transient network/SP-API failures with exponential backoff."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            response = requests.request(method, url, **kwargs)
            if response.status_code == 404:
                # 404 is not retryable and usually means ASIN not found in this marketplace.
                # We should stop retrying immediately but let the caller handle it.
                raise requests.HTTPError(f"404 Client Error: Not Found {url}", response=response)
            if response.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"retryable status {response.status_code}", response=response)
            response.raise_for_status()
            return response
        except (RequestException, requests.HTTPError) as exc:
            last_exc = exc
            if isinstance(exc, requests.HTTPError) and exc.response.status_code == 404:
                # Don't retry 404s
                break
            if attempt == max_retries - 1:
                break
            time.sleep(2**attempt)
    raise last_exc


def _extract_sales_rank_rows(
    payload: Dict,
    marketplace_id: str,
    account_id: str,
    asin: str,
    report_date: str,
) -> List[dict]:
    """Normalize salesRanks payload into rows suitable for sc_raw.bsr_history."""
    rows: List[dict] = []
    sales_ranks = payload.get("salesRanks") or []
    for idx, rank_obj in enumerate(sales_ranks):
        category_name = rank_obj.get("title")
        rank_value = rank_obj.get("rank")
        category_id = rank_obj.get("classificationId") or rank_obj.get("link") or f"primary-{idx}"

        if category_name and rank_value is not None:
            rows.append(
                {
                    "report_date": report_date,
                    "marketplace_id": marketplace_id,
                    "account_id": account_id,
                    "asin": asin,
                    "category_name": category_name,
                    "category_id": str(category_id),
                    "rank": int(rank_value),
                }
            )

        for c_idx, child in enumerate(rank_obj.get("classificationRanks") or []):
            child_name = child.get("title")
            child_rank = child.get("rank")
            child_id = child.get("classificationId") or child.get("link") or f"classification-{idx}-{c_idx}"
            if child_name and child_rank is not None:
                rows.append(
                    {
                        "report_date": report_date,
                        "marketplace_id": marketplace_id,
                        "account_id": account_id,
                        "asin": asin,
                        "category_name": child_name,
                        "category_id": str(child_id),
                        "rank": int(child_rank),
                    }
                )
    return rows


def fetch_single_asin_bsr(config: dict, token: str, asin: str, report_date: str) -> List[dict]:
    """Fetch sales rank payload for a single ASIN and normalize response rows."""
    response = _request_with_retries(
        "GET",
        f"{config['endpoint']}/catalog/2022-04-01/items/{asin}",
        headers=make_headers(token),
        auth=get_auth(config),
        params={
            "marketplaceIds": config["marketplace_uae"],
            "includedData": "salesRanks",
        },
        timeout=60,
    )
    payload = response.json()
    return _extract_sales_rank_rows(
        payload,
        config["marketplace_uae"],
        config["spapi_account_id"],
        asin,
        report_date,
    )


def fetch_bsr_batch(
    config: dict,
    token: str,
    asins: List[str],
    report_date: str,
    rate_limit_delay: float = 0.2,
) -> List[dict]:
    """Fetch BSR data for a batch of ASINs while respecting 5 req/sec limits."""
    rows: List[dict] = []
    for idx, asin in enumerate(asins):
        try:
            rows.extend(fetch_single_asin_bsr(config, token=token, asin=asin, report_date=report_date))
        except requests.HTTPError as e:
            if e.response.status_code in (404, 400):
                logger.warning(f"Skipping ASIN {asin} (Status {e.response.status_code}): {e}")
                continue
            raise e
        except Exception as e:
            logger.error(f"Error fetching BSR for {asin}: {e}")
            raise e
        if idx < len(asins) - 1:
            time.sleep(rate_limit_delay)
    return rows


def upsert_bsr_history(rows: List[dict], db_url: str) -> int:
    """Upsert normalized BSR rows into sc_raw.bsr_history."""
    if not rows:
        return 0

    values = [
        (
            r["report_date"],
            r["marketplace_id"],
            r["account_id"],
            r["asin"],
            r.get("category_name"),
            r.get("category_id"),
            r.get("rank"),
        )
        for r in rows
    ]

    sql = """
        INSERT INTO sc_raw.bsr_history (
            report_date, marketplace_id, account_id, asin, category_name, category_id, rank
        ) VALUES %s
        ON CONFLICT (report_date, marketplace_id, account_id, asin, category_id)
        DO UPDATE SET
            category_name = EXCLUDED.category_name,
            rank = EXCLUDED.rank,
            pulled_at = NOW()
    """

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, values)
            affected = cur.rowcount
        conn.commit()
    return affected


def _get_write_db_url(config: dict) -> str:
    """Get a DB URL for writes. Tries direct URL first, falls back to pooler."""
    direct = os.environ.get("DATABASE_URL_DIRECT")
    if direct:
        try:
            conn = psycopg2.connect(direct, connect_timeout=5)
            conn.close()
            return direct
        except Exception:
            logger.warning("Direct DB URL unreachable, falling back to pooler URL")
    return config["database_url"]


def _get_read_db_url(config: dict) -> str:
    """Get a DB URL for read queries. Prefers pooler URL for reliability."""
    return config["database_url"]


def get_active_asins(
    db_url: str,
    marketplace_id: str,
    account_id: str,
    report_date: str,
    lookback_days: int = 7,
) -> List[str]:
    """Get active ASINs from sc_raw.sales_traffic for a report date context."""
    end = datetime.strptime(report_date, "%Y-%m-%d").date()
    start = end - timedelta(days=lookback_days - 1)
    sql = """
        SELECT DISTINCT child_asin
        FROM sc_raw.sales_traffic
        WHERE marketplace_id = %s
          AND account_id = %s
          AND report_date BETWEEN %s AND %s
          AND child_asin IS NOT NULL
        ORDER BY child_asin
    """
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (marketplace_id, account_id, start, end))
            return [row[0] for row in cur.fetchall()]


def pull_daily_bsr(report_date: str, config: Optional[dict] = None, asins: Optional[List[str]] = None) -> int:
    """Pull and upsert BSR rows for one report date."""
    cfg = config or get_config()
    write_db_url = _get_write_db_url(cfg)
    target_asins = asins or get_active_asins(
        write_db_url,
        cfg["marketplace_uae"],
        cfg["spapi_account_id"],
        report_date,
    )
    if not target_asins:
        logger.info("No active ASINs found for report_date=%s", report_date)
        return 0

    token = authenticate(cfg)
    rows = fetch_bsr_batch(cfg, token=token, asins=target_asins, report_date=report_date)
    written = upsert_bsr_history(rows, write_db_url)
    logger.info(
        "BSR pull complete report_date=%s asins=%s rows=%s",
        report_date,
        len(target_asins),
        written,
    )
    return written


def backfill_bsr(start_date: str, end_date: str, config: Optional[dict] = None) -> dict:
    """
    Backfill BSR for each date in a range (inclusive).
    Returns a summary dict with counts and date range.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    if start > end:
        raise ValueError("start_date must be <= end_date")

    cfg = config or get_config()
    read_db_url = _get_read_db_url(cfg)
    write_db_url = _get_write_db_url(cfg)
    token = authenticate(cfg)

    success_days = 0
    failed_days = 0
    total_rows = 0

    for day_offset in range((end - start).days + 1):
        report_date = (start + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        try:
            asins = get_active_asins(
                read_db_url,
                cfg["marketplace_uae"],
                cfg["spapi_account_id"],
                report_date,
            )
            if not asins:
                logger.info("Skipping %s; no active ASINs", report_date)
                success_days += 1
                continue
            rows = fetch_bsr_batch(cfg, token=token, asins=asins, report_date=report_date)
            total_rows += upsert_bsr_history(rows, write_db_url)
            success_days += 1
        except Exception:
            failed_days += 1
            logger.exception("BSR backfill failed for %s", report_date)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "success_days": success_days,
        "failed_days": failed_days,
        "rows_written": total_rows,
    }
