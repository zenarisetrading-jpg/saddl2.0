#!/usr/bin/env python3
"""
Multi-account daily SP-API pipeline runner.

Reads all active accounts from client_settings and runs the full daily
data pull (sales/traffic, aggregation, FBA inventory, BSR) for each one.

This is designed to be called from GitHub Actions once per day, but also
works perfectly fine locally.

Usage:
    cd /path/to/saddle/desktop
    python3 scripts/run_pipeline_all_accounts.py                # yesterday UTC (default)
    python3 scripts/run_pipeline_all_accounts.py 2026-02-26    # explicit date

Cloud (GitHub Actions):
    Only DATABASE_URL plus LWA_CLIENT_ID / LWA_CLIENT_SECRET need to be set
    as repository secrets.  Each account's refresh_token is read directly
    from client_settings — no per-account secrets needed.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]   # desktop/
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT.parent / ".env")        # repo root fallback
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("saddl.daily")

# ── DB helpers ─────────────────────────────────────────────────────────────────

def _get_db_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()   # strip trailing newlines from GitHub secrets
    if not url:
        sys.exit("❌  DATABASE_URL is not set.")
    return url


def _fetch_active_accounts() -> list[dict]:
    """Return all accounts with onboarding_status='active' and a stored refresh token."""
    import psycopg2
    with psycopg2.connect(_get_db_url()) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT client_id, lwa_refresh_token, marketplace_id, region_endpoint
                FROM client_settings
                WHERE onboarding_status = 'active'
                  AND lwa_refresh_token IS NOT NULL
                ORDER BY client_id
            """)
            rows = cur.fetchall()
    return [
        {
            "client_id":       r[0],
            "refresh_token":   r[1],
            "marketplace_id":  r[2] or os.getenv("MARKETPLACE_ID_UAE", "A2VIGQ35RCS4UG"),
            "region_endpoint": r[3] or "sellingpartnerapi-eu.amazon.com",
        }
        for r in rows
    ]


# ── Per-account pull ───────────────────────────────────────────────────────────

def _run_for_account(account: dict, target_dates: list[str]) -> dict:
    """
    Run the full daily pull for one account:
      1. Sales & Traffic → sc_raw.sales_traffic (batch Data Kiosk query)
      2. Aggregation     → sc_analytics.account_daily + osi_index
      3. FBA Inventory   → sc_raw.fba_inventory
      4. BSR snapshot    → sc_raw.bsr_history  (best-effort)

    Returns a result dict with row counts and any errors.
    """
    client_id       = account["client_id"]
    refresh_token   = account["refresh_token"]
    marketplace_id  = account["marketplace_id"]
    region_endpoint = account["region_endpoint"]

    result = {
        "client_id":    client_id,
        "sales_rows":   0,
        "fba_rows":     0,
        "bsr_rows":     0,
        "errors":       [],
    }

    # Swap the refresh token in env so the existing client picks up the right creds
    prev_token = os.environ.get("LWA_REFRESH_TOKEN_UAE")
    os.environ["LWA_REFRESH_TOKEN_UAE"] = refresh_token

    try:
        # Flush cached access token
        try:
            from pipelines import sp_api_client as _spc
            _spc._token_cache.update({"access_token": None, "expires_at": None})
        except Exception:
            pass

        from pipelines.sp_api_client import get_settings, get_token
        from pipelines.spapi_pipeline import (
            build_sales_traffic_query, create_data_kiosk_query,
            poll_query_status, download_query_document,
            upsert_sales_traffic, pull_fba_inventory,
        )
        from pipeline.aggregator import upsert_account_daily, upsert_osi_index

        # Inject per-account marketplace config as env vars so get_settings()
        # picks them up regardless of which version of sp_api_client is deployed
        prev_marketplace  = os.environ.get("MARKETPLACE_ID_UAE")
        prev_endpoint     = os.environ.get("SP_API_ENDPOINT")
        os.environ["MARKETPLACE_ID_UAE"] = marketplace_id
        if region_endpoint:
            os.environ["SP_API_ENDPOINT"] = (
                f"https://{region_endpoint}"
                if not region_endpoint.startswith("http")
                else region_endpoint
            )

        try:
            settings     = get_settings()
            access_token = get_token(force_refresh=True)
        finally:
            # Restore marketplace env vars
            if prev_marketplace is not None:
                os.environ["MARKETPLACE_ID_UAE"] = prev_marketplace
            else:
                os.environ.pop("MARKETPLACE_ID_UAE", None)
            if prev_endpoint is not None:
                os.environ["SP_API_ENDPOINT"] = prev_endpoint
            else:
                os.environ.pop("SP_API_ENDPOINT", None)
        db_url       = _get_db_url()

        # ── 1 & 2. Sales & Traffic + Aggregation (per date) ───────────────────
        last_submit_ts = None
        for t_date in target_dates:
            log.info("  [1/4] Data Kiosk query for %s on %s…", client_id, t_date)
            try:
                if last_submit_ts:
                    elapsed = time.time() - last_submit_ts
                    if elapsed < 62:
                        log.info("   Waiting %.1fs for Data Kiosk rate limit...", 62 - elapsed)
                        time.sleep(62 - elapsed)

                qbody   = build_sales_traffic_query(t_date, t_date, settings.marketplace_id)
                qid     = create_data_kiosk_query(access_token, qbody, region_endpoint=region_endpoint)
                last_submit_ts = time.time()

                payload = poll_query_status(
                    access_token, qid,
                    poll_seconds=30, max_wait_minutes=45,
                    region_endpoint=region_endpoint,
                )
                doc_id = payload.get("dataDocumentId")
                if doc_id:
                    records = download_query_document(access_token, doc_id, region_endpoint=region_endpoint)
                    rows_written = upsert_sales_traffic(
                        records, t_date, settings.marketplace_id, account_id=client_id
                    )
                    result["sales_rows"] += rows_written
                    log.info("  [1/4] ✓ %d rows written (client=%s, date=%s)", rows_written, client_id, t_date)
                else:
                    log.warning("  [1/4] No dataDocumentId for %s on %s", client_id, t_date)
            except Exception as e:
                msg = f"Sales/traffic failed for {t_date}: {e}"
                log.warning("  [1/4] %s", msg)
                result["errors"].append(msg)

            # ── 2. Aggregation ────────────────────────────────────────────────────
            log.info("  [2/4] Aggregating account_daily + osi_index for %s…", t_date)
            try:
                upsert_account_daily(db_url, t_date, settings.marketplace_id,
                                     client_id=client_id, account_id=client_id)
                upsert_osi_index(db_url, t_date, settings.marketplace_id, account_id=client_id)
                log.info("  [2/4] ✓ account_daily and osi_index updated")
            except Exception as e:
                msg = f"Aggregation failed for {t_date}: {e}"
                log.warning("  [2/4] %s", msg)
                result["errors"].append(msg)

        # ── 3. FBA Inventory ──────────────────────────────────────────────────
        log.info("  [3/4] FBA inventory snapshot…")
        try:
            result["fba_rows"] = pull_fba_inventory(
                client_id,
                marketplace_id=settings.marketplace_id,
                region_endpoint=region_endpoint,
            ) or 0
            log.info("  [3/4] ✓ %d rows written", result["fba_rows"])
        except Exception as e:
            msg = f"FBA inventory failed: {e}"
            log.warning("  [3/4] %s", msg)
            result["errors"].append(msg)

        # ── 4. BSR snapshot ───────────────────────────────────────────────────
        log.info("  [4/4] BSR snapshot (best-effort)…")
        try:
            import psycopg2
            from pipeline.bsr_pipeline import fetch_bsr_batch, upsert_bsr_history
            with psycopg2.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT DISTINCT child_asin FROM sc_raw.sales_traffic "
                        "WHERE marketplace_id = %s AND account_id = %s "
                        "AND child_asin IS NOT NULL LIMIT 500",
                        (settings.marketplace_id, client_id),
                    )
                    asins = [r[0] for r in cur.fetchall()]
            if asins:
                cfg = {
                    "lwa_client_id":     os.getenv("LWA_CLIENT_ID", ""),
                    "lwa_client_secret": os.getenv("LWA_CLIENT_SECRET", ""),
                    "refresh_token_uae": refresh_token,
                    "aws_access_key":    os.getenv("AWS_ACCESS_KEY_ID", ""),
                    "aws_secret_key":    os.getenv("AWS_SECRET_ACCESS_KEY", ""),
                    "aws_region":        os.getenv("AWS_REGION", "eu-west-1"),
                    "marketplace_uae":   settings.marketplace_id,
                    "spapi_account_id":  client_id,
                    "endpoint":          f"https://{region_endpoint}",
                    "database_url":      db_url,
                }
                bsr_rows = fetch_bsr_batch(cfg, token=access_token,
                                           asins=asins, report_date=target_dates[0])
                result["bsr_rows"] = upsert_bsr_history(bsr_rows, db_url)
                log.info("  [4/4] ✓ %d BSR rows written", result["bsr_rows"])
            else:
                log.info("  [4/4] No ASINs found — skipping BSR")
        except Exception as e:
            msg = f"BSR failed: {e}"
            log.warning("  [4/4] %s", msg)
            result["errors"].append(msg)

    finally:
        # Restore previous token
        if prev_token is not None:
            os.environ["LWA_REFRESH_TOKEN_UAE"] = prev_token
        else:
            os.environ.pop("LWA_REFRESH_TOKEN_UAE", None)
        try:
            from pipelines import sp_api_client as _spc
            _spc._token_cache.update({"access_token": None, "expires_at": None})
        except Exception:
            pass

    return result


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) > 1:
        target_dates = [sys.argv[1]]
    else:
        # Standard daily run:
        # D-1, D-2: yesterday + day before (cover missed runs)
        # D-7, D-14, D-30: correction lookbacks for late-arriving traffic data
        today = datetime.utcnow().date()
        offsets = [1, 2, 7, 14, 30]
        target_dates = [
            (today - timedelta(days=offset)).strftime("%Y-%m-%d")
            for offset in offsets
        ]

    log.info("═══════════════════════════════════════════════")
    log.info("  Saddle Multi-Account Daily Pull")
    log.info("  Target dates : %s", ", ".join(target_dates))
    log.info("═══════════════════════════════════════════════")

    accounts = _fetch_active_accounts()
    if not accounts:
        log.warning("No active accounts found in client_settings — nothing to do.")
        sys.exit(0)

    log.info("Found %d active account(s): %s", len(accounts),
             ", ".join(a["client_id"] for a in accounts))

    all_results = []
    for i, account in enumerate(accounts):
        log.info("")
        log.info("▶  Account %d/%d: %s (marketplace=%s)",
                 i + 1, len(accounts), account["client_id"], account["marketplace_id"])

        # Rate-limit gap between accounts (Data Kiosk allows 1 createQuery/60s per app)
        if i > 0:
            log.info("   Waiting 65s between accounts (Data Kiosk rate limit)…")
            time.sleep(65)

        result = _run_for_account(account, target_dates)
        all_results.append(result)

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info("")
    log.info("═══════════════ SUMMARY (%s) ════════════════", target_dates[0])
    any_error = False
    for r in all_results:
        status = "✅" if not r["errors"] else "⚠️"
        log.info("  %s %-20s  sales=%d  fba=%d  bsr=%d%s",
                 status, r["client_id"], r["sales_rows"], r["fba_rows"], r["bsr_rows"],
                 f"  errors={r['errors']}" if r["errors"] else "")
        if r["errors"]:
            any_error = True
    log.info("═══════════════════════════════════════════════")

    # Exit 1 if any account had errors so GitHub Actions marks the run as failed
    sys.exit(1 if any_error else 0)


if __name__ == "__main__":
    main()
