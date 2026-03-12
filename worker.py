#!/usr/bin/env python3
"""
Saddle Backfill Worker
======================
Watches client_settings for newly-connected accounts and automatically
runs the SP-API historical backfill — no user or admin action needed.

Flow:
  OAuth completes  →  onboarding_status = 'connected'
  Worker detects it  →  runs backfill (sets status → 'backfilling')
  Backfill completes  →  onboarding_status = 'active'
  Data is live in the app

Run alongside the Streamlit app:
  Terminal 1:  streamlit run ppcsuite_v4_ui_experiment.py
  Terminal 2:  python worker.py

Cloud (Railway / Render / Fly.io):
  Deploy as a second service with the same env vars.
  No extra config needed — same DATABASE_URL, same SP-API keys.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("saddl.worker")

POLL_INTERVAL_SECONDS = 30   # How often to scan for new accounts
BACKFILL_DAYS         = 90   # Historical window to pull


def _get_db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("❌  DATABASE_URL is not set.")
    return url


def _connect():
    import psycopg2  # type: ignore
    return psycopg2.connect(_get_db_url())


# How many days of sales_traffic must be present to consider a backfill complete.
# Accounts with fewer days than this will be re-queued for backfill even if
# they are marked 'active' (handles interrupted backfills gracefully).
_MIN_BACKFILL_DAYS = BACKFILL_DAYS - 5   # allow a small tolerance


def _find_pending_clients() -> list[dict]:
    """
    Return accounts that need a (re-)backfill:
      1. onboarding_status = 'connected'    — OAuth done, never backfilled
      2. onboarding_status = 'backfilling'  — previous worker crashed mid-loop
      3. onboarding_status = 'active' but fewer than _MIN_BACKFILL_DAYS of
         sales_traffic data — backfill was interrupted and needs to resume
    All cases require a stored lwa_refresh_token.
    """
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cs.client_id, cs.lwa_refresh_token,
                       cs.marketplace_id, cs.region_endpoint
                FROM client_settings cs
                WHERE cs.lwa_refresh_token IS NOT NULL
                  AND (
                    -- Never backfilled, or previous worker crashed mid-run
                    cs.onboarding_status IN ('connected', 'backfilling')
                    OR
                    -- Active but incomplete sales data (interrupted backfill)
                    (
                      cs.onboarding_status = 'active'
                      AND (
                        SELECT COUNT(DISTINCT report_date)
                        FROM sc_raw.sales_traffic st
                        WHERE st.account_id = cs.client_id
                      ) < %(min_days)s
                    )
                  )
            """, {"min_days": _MIN_BACKFILL_DAYS})
            rows = cur.fetchall()

    return [
        {
            "client_id": r[0],
            "refresh_token": r[1],
            "marketplace_id": r[2],
            "region_endpoint": r[3],
        }
        for r in rows
    ]


def _run_backfill_for(
    client_id: str,
    refresh_token: str,
    marketplace_id: Optional[str] = None,
    region_endpoint: Optional[str] = None,
) -> None:
    """Run the full backfill for one client. Mirrors _backfill_thread_fn in data_hub.py."""
    from datetime import date, timedelta
    from utils.marketplace_config import get_client_marketplace_config  # type: ignore

    log.info("▶  Starting backfill  client=%s", client_id)

    # Resolve per-client marketplace config — use stored DB values when available,
    # fall back to env var for legacy clients that predate marketplace discovery.
    if not marketplace_id or not region_endpoint:
        marketplace_id, region_endpoint = get_client_marketplace_config(
            client_id, _get_db_url()
        )

    log.info("  Marketplace : %s  endpoint=%s", marketplace_id, region_endpoint)

    # Clear cached access token so we auth with this client's token
    try:
        from pipelines import sp_api_client as _spc  # type: ignore
        _spc._token_cache.update({"access_token": None, "expires_at": None})
    except Exception:
        pass

    # Mark as in-progress immediately so we don't double-pick
    _set_status(client_id, "backfilling")

    try:
        from pipelines.sp_api_client import get_settings, get_token  # type: ignore
        from pipelines.spapi_pipeline import (  # type: ignore
            build_sales_traffic_query, create_data_kiosk_query,
            poll_query_status, download_query_document,
            upsert_sales_traffic, pull_fba_inventory,
        )

        settings     = get_settings(
            marketplace_id=marketplace_id, region_endpoint=region_endpoint,
            lwa_refresh_token=refresh_token,
        )
        access_token = get_token(settings=settings, force_refresh=True)
        today        = date.today()
        start_dt     = (today - timedelta(days=BACKFILL_DAYS)).strftime("%Y-%m-%d")
        end_dt       = (today - timedelta(days=1)).strftime("%Y-%m-%d")

        log.info("  Date range  : %s → %s", start_dt, end_dt)

        # ── Step 1 — Sales & Traffic (day-by-day for daily ASIN-level granularity) ──
        # The Data Kiosk salesAndTrafficByAsin query aggregates the full date range
        # into one row per ASIN, so we submit one query per day to preserve daily
        # granularity. The rate limit is 1 createQuery per 60s; at 90 days this
        # takes ~2–3 hours — well within the expected backfill window.
        log.info("  [1/4] Submitting Data Kiosk queries day-by-day (%s → %s)…", start_dt, end_dt)
        rows_sc        = 0
        days_done      = 0
        last_submit_ts: Optional[float] = None

        # Skip days already in the DB so interrupted backfills resume cleanly
        with _connect() as _chk_conn:
            with _chk_conn.cursor() as _chk_cur:
                _chk_cur.execute(
                    "SELECT DISTINCT report_date FROM sc_raw.sales_traffic "
                    "WHERE account_id = %s",
                    (client_id,)
                )
                already_done = {r[0] for r in _chk_cur.fetchall()}
        log.info("  [1/4] %d days already in DB — will skip those", len(already_done))

        day_cur = date.fromisoformat(start_dt)
        day_end = date.fromisoformat(end_dt)

        while day_cur <= day_end:
            day_str = day_cur.isoformat()
            day_cur += timedelta(days=1)   # always advance regardless of outcome

            if date.fromisoformat(day_str) in already_done:
                days_done += 1
                continue

            try:
                # Respect Data Kiosk createQuery rate limit (1 per 60s)
                if last_submit_ts:
                    elapsed = time.time() - last_submit_ts
                    if elapsed < 62:
                        time.sleep(62 - elapsed)

                qbody          = build_sales_traffic_query(day_str, day_str, settings.marketplace_id)
                qid            = create_data_kiosk_query(access_token, qbody, region_endpoint=region_endpoint)
                last_submit_ts = time.time()

                # Poll with 10s intervals (Amazon resolves most queries in < 2 min)
                payload = poll_query_status(
                    access_token, qid,
                    poll_seconds=10, max_wait_minutes=30,
                    region_endpoint=region_endpoint,
                )
                doc_id = payload.get("dataDocumentId")
                if doc_id:
                    records  = download_query_document(access_token, doc_id, region_endpoint=region_endpoint)
                    day_rows = upsert_sales_traffic(records, day_str, settings.marketplace_id, account_id=client_id)
                    rows_sc += day_rows
                    days_done += 1
                    log.info("    %s  %d rows  (total days: %d)", day_str, day_rows, days_done)
                else:
                    log.warning("    %s  no dataDocumentId — skipping", day_str)
            except Exception as day_exc:
                log.warning("    %s  failed (continuing): %s", day_str, day_exc)

        log.info("  [1/4] ✓ %d rows written across %d days (account_id=%s)",
                 rows_sc, days_done, client_id)
        api_call_succeeded = True



        # Step 1b — Aggregate raw rows → sc_analytics.account_daily
        log.info("  [2/4] Aggregating sales/traffic → account_daily…")
        try:
            from pipeline.aggregator import upsert_account_daily, upsert_osi_index  # type: ignore
            db_url      = _get_db_url()
            agg_start   = date.fromisoformat(start_dt)
            agg_end     = date.fromisoformat(end_dt)
            agg_current = agg_start
            agg_count   = 0
            while agg_current <= agg_end:
                upsert_account_daily(
                    db_url,
                    agg_current.isoformat(),
                    settings.marketplace_id,
                    client_id=client_id,
                    account_id=client_id,
                )
                upsert_osi_index(
                    db_url,
                    agg_current.isoformat(),
                    settings.marketplace_id,
                    account_id=client_id,
                )
                agg_current += timedelta(days=1)
                agg_count   += 1
            log.info("  [2/4] ✓ %d days aggregated (account_daily + osi_index)", agg_count)
        except Exception as agg_exc:
            log.warning("  [2/4] Aggregation failed (non-fatal): %s", agg_exc)

        # Step 3 — FBA Inventory
        log.info("  [3/4] FBA inventory snapshot…")
        rows_inv = pull_fba_inventory(
            client_id,
            marketplace_id=settings.marketplace_id,
            region_endpoint=region_endpoint,
            lwa_refresh_token=refresh_token,
        )
        log.info("  [3/4] ✓ %s rows written", rows_inv)

        # Step 4 — BSR (best-effort)
        log.info("  [4/4] Best Seller Rank snapshot…")
        try:
            import psycopg2 as _pg  # type: ignore
            from pipeline.bsr_pipeline import fetch_bsr_batch, upsert_bsr_history  # type: ignore
            db_url = _get_db_url()
            with _pg.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT DISTINCT child_asin FROM sc_raw.sales_traffic "
                        "WHERE marketplace_id = %s AND report_date >= %s "
                        "AND account_id = %s AND child_asin IS NOT NULL LIMIT 500",
                        (settings.marketplace_id, start_dt, client_id),
                    )
                    asins = [r[0] for r in cur.fetchall()]
            if asins:
                cfg = {
                    "lwa_client_id":     os.getenv("LWA_CLIENT_ID", ""),
                    "lwa_client_secret": os.getenv("LWA_CLIENT_SECRET", ""),
                    "refresh_token": refresh_token,
                    "aws_access_key":    os.getenv("AWS_ACCESS_KEY_ID", ""),
                    "aws_secret_key":    os.getenv("AWS_SECRET_ACCESS_KEY", ""),
                    "aws_region":        os.getenv("AWS_REGION", "eu-west-1"),
                    "marketplace_id":    settings.marketplace_id,
                    "spapi_account_id":  client_id,
                    "endpoint":          f"https://{region_endpoint}" if region_endpoint else "https://sellingpartnerapi-eu.amazon.com",
                    "database_url":      db_url,
                }
                bsr_rows = fetch_bsr_batch(cfg, token=access_token,
                                           asins=asins, report_date=today.strftime("%Y-%m-%d"))
                rows_bsr = upsert_bsr_history(bsr_rows, db_url)
                log.info("  [4/4] ✓ %d rows written", rows_bsr)
            else:
                log.info("  [4/4] No ASINs found — skipping")
        except Exception as bsr_exc:
            log.warning("  [4/4] BSR failed (non-fatal): %s", bsr_exc)

        # ── New-account fast-path ──────────────────────────────────────
        # If the SP-API calls succeeded (no fatal exception) but returned
        # zero sales rows, the account is genuinely new with no history.
        # Mark it active immediately so onboarding completes rather than
        # retrying indefinitely on a permanently empty response.
        if api_call_succeeded and rows_sc == 0:
            log.info(
                "Account has no sales history — marking active as new account  client=%s",
                client_id,
            )
            _upsert_account_link(client_id, settings.marketplace_id)
            _set_status(client_id, "active")
            return

        # ── Sanity check before declaring victory ─────────────────────
        # If both Data Kiosk (0 rows) AND FBA inventory failed (None),
        # the account has no data at all — most likely a transient Amazon
        # API issue.  Keep status as 'connected' so the worker retries
        # on the next poll instead of silently marking the account active
        # with an empty database.
        fba_ok = rows_inv is not None and rows_inv >= 0
        sales_ok = rows_sc > 0
        if not fba_ok and not sales_ok:
            log.warning(
                "⚠️  No data written for client=%s "
                "(Data Kiosk: %d rows, FBA: %s rows). "
                "Resetting to 'connected' for retry on next poll.",
                client_id, rows_sc, rows_inv,
            )
            _set_status(client_id, "connected")
            return

        _upsert_account_link(client_id, settings.marketplace_id)
        _set_status(client_id, "active")
        log.info("✅  Backfill complete  client=%s", client_id)

    except Exception as exc:
        log.error("❌  Backfill FAILED  client=%s  error=%s", client_id, exc)
        _set_status(client_id, "connected")   # Reset so worker retries next cycle

    finally:
        try:
            from pipelines import sp_api_client as _spc  # type: ignore
            _spc._token_cache.update({"access_token": None, "expires_at": None})
        except Exception:
            pass


def _upsert_account_link(client_id: str, marketplace_id: str) -> None:
    """Ensure sc_raw.spapi_account_links has an entry for this client so the
    dashboard can resolve the correct marketplace when querying data."""
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sc_raw.spapi_account_links
                        (account_id, public_client_id, marketplace_id, is_active, notes)
                    VALUES (%s, %s, %s, TRUE, 'Auto-created by worker on backfill')
                    ON CONFLICT (account_id, marketplace_id) DO UPDATE SET
                        public_client_id = EXCLUDED.public_client_id,
                        is_active        = TRUE,
                        updated_at       = NOW()
                    """,
                    (client_id, client_id, marketplace_id),
                )
            conn.commit()
        log.info("  account_link upserted  client=%s  marketplace=%s", client_id, marketplace_id)
    except Exception as exc:
        log.warning("  account_link upsert failed (non-fatal): %s", exc)


def _set_status(client_id: str, status: str) -> None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE client_settings SET onboarding_status = %s, updated_at = NOW() "
                "WHERE client_id = %s",
                (status, client_id),
            )
        conn.commit()


def main() -> None:
    # Load .env for local dev
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    log.info("═══════════════════════════════════════════")
    log.info("Saddle Backfill Worker started")
    log.info("Poll interval : %ds", POLL_INTERVAL_SECONDS)
    log.info("Backfill window: %d days", BACKFILL_DAYS)
    log.info("═══════════════════════════════════════════")

    while True:
        try:
            pending = _find_pending_clients()
            if pending:
                log.info("Found %d account(s) needing backfill", len(pending))
                for client in pending:
                    _run_backfill_for(
                        client["client_id"],
                        client["refresh_token"],
                        marketplace_id=client.get("marketplace_id"),
                        region_endpoint=client.get("region_endpoint"),
                    )
        except Exception as exc:
            log.error("Worker poll error (will retry): %s", exc)

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
