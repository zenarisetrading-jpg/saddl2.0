#!/usr/bin/env python3
"""
Standalone SP-API historical backfill script.

Runs the same pipeline as the in-app "Start Historical Data Import" trigger
but fully outside Streamlit — safe for cloud deployments where background
threads die on process restart.

Usage:
    # Backfill 90 days (default) for a specific client
    python scripts/run_backfill.py --client-id demo

    # Backfill custom window
    python scripts/run_backfill.py --client-id demo --days 30

    # Preview without touching the DB or calling Amazon
    python scripts/run_backfill.py --client-id demo --dry-run

    # List all available clients and their current status
    python scripts/run_backfill.py --list-clients

Cloud deployment examples:
    # Railway one-off job
    railway run python scripts/run_backfill.py --client-id demo

    # Render shell / Fly.io console
    python scripts/run_backfill.py --client-id demo

    # Cron (Sunday 3am UTC)
    0 3 * * 0 cd /app && python scripts/run_backfill.py --client-id demo

Required environment variables (same as the main app):
    DATABASE_URL            Supabase PostgreSQL connection string
    LWA_CLIENT_ID           Amazon LWA client ID
    LWA_CLIENT_SECRET       Amazon LWA client secret
    AWS_ACCESS_KEY_ID       AWS access key
    AWS_SECRET_ACCESS_KEY   AWS secret key
    AWS_REGION              AWS region (default: eu-west-1)
    MARKETPLACE_ID_UAE      Marketplace ID (default: A2VIGQ35RCS4UG)

The client's LWA refresh token is read automatically from client_settings.lwa_refresh_token.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# ── Project root on sys.path so pipeline imports work ──────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Logging: timestamps + level ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("saddl.backfill")


# ══════════════════════════════════════════════════════════════════════════════
# DB HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("❌  DATABASE_URL env var is not set. Check your .env file.")
    return url


def _connect(db_url: str):
    """Return a raw psycopg2 connection."""
    import psycopg2  # type: ignore
    return psycopg2.connect(db_url)


def load_client(client_id: str) -> dict:
    """
    Fetch lwa_refresh_token and onboarding_status from client_settings.
    Raises SystemExit if client not found or token missing.
    """
    db_url = _get_db_url()
    with _connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT lwa_refresh_token, onboarding_status
                FROM client_settings
                WHERE client_id = %s
                LIMIT 1
                """,
                (client_id,),
            )
            row = cur.fetchone()

    if not row:
        sys.exit(f"❌  Client '{client_id}' not found in client_settings.")

    refresh_token, onboarding_status = row

    if not refresh_token:
        sys.exit(
            f"❌  No lwa_refresh_token stored for client '{client_id}'.\n"
            "    Connect the Amazon account via the app first."
        )

    return {"refresh_token": refresh_token, "onboarding_status": onboarding_status or ""}


def list_clients() -> None:
    """Print all clients and their current onboarding_status."""
    db_url = _get_db_url()
    with _connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT client_id, onboarding_status,
                       lwa_refresh_token IS NOT NULL AS has_token,
                       updated_at
                FROM client_settings
                ORDER BY client_id
                """
            )
            rows = cur.fetchall()

    if not rows:
        print("No clients found in client_settings.")
        return

    print(f"\n{'CLIENT ID':<30}  {'STATUS':<15}  {'TOKEN':<8}  UPDATED AT")
    print("─" * 80)
    for client_id, status, has_token, updated_at in rows:
        token_flag = "✓" if has_token else "✗"
        updated = str(updated_at)[:19] if updated_at else "—"
        print(f"{client_id:<30}  {(status or '—'):<15}  {token_flag:<8}  {updated}")
    print()


def set_onboarding_status(client_id: str, status: str) -> None:
    db_url = _get_db_url()
    with _connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE client_settings SET onboarding_status = %s, updated_at = NOW() "
                "WHERE client_id = %s",
                (status, client_id),
            )
        conn.commit()
    log.info("onboarding_status → %s  (client=%s)", status, client_id)


# ══════════════════════════════════════════════════════════════════════════════
# BACKFILL LOGIC  (mirrors _backfill_thread_fn in ui/data_hub.py)
# ══════════════════════════════════════════════════════════════════════════════

def run_backfill(client_id: str, days: int = 90, dry_run: bool = False) -> None:
    t0 = time.monotonic()

    log.info("══════════════════════════════════════════════")
    log.info("SP-API Backfill  client=%-20s  days=%d", client_id, days)
    log.info("══════════════════════════════════════════════")

    creds = load_client(client_id)
    refresh_token    = creds["refresh_token"]
    current_status   = creds["onboarding_status"].strip().lower()
    marketplace_id   = os.getenv("MARKETPLACE_ID_UAE", "A2VIGQ35RCS4UG")

    log.info("Marketplace : %s", marketplace_id)
    log.info("DB status   : %s", current_status)

    if current_status == "backfilling":
        log.warning(
            "Status is already 'backfilling' — another run may be in progress.\n"
            "If that run crashed, reset with:\n"
            "  UPDATE client_settings SET onboarding_status = 'connected' WHERE client_id = '%s';",
            client_id,
        )

    if dry_run:
        today    = date.today()
        start_dt = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        end_dt   = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        log.info("DRY RUN — would pull %s → %s for client=%s", start_dt, end_dt, client_id)
        log.info("DRY RUN — no DB writes, no Amazon API calls.")
        return

    # ── Inject client's refresh token into env so the pipeline picks it up ──
    prev_token = os.environ.get("LWA_REFRESH_TOKEN_UAE")
    os.environ["LWA_REFRESH_TOKEN_UAE"] = refresh_token

    # Clear the pipeline's cached access token so it re-auths with the correct token
    try:
        from pipelines import sp_api_client as _spc  # type: ignore
        _spc._token_cache.update({"access_token": None, "expires_at": None})
    except Exception:
        pass

    set_onboarding_status(client_id, "backfilling")

    try:
        from pipelines.sp_api_client import get_settings, get_token  # type: ignore
        from pipelines.spapi_pipeline import (  # type: ignore
            build_sales_traffic_query,
            create_data_kiosk_query,
            poll_query_status,
            download_query_document,
            upsert_sales_traffic,
            pull_fba_inventory,
        )

        settings     = get_settings()
        access_token = get_token(force_refresh=True)

        today    = date.today()
        start_dt = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        end_dt   = (today - timedelta(days=1)).strftime("%Y-%m-%d")

        log.info("Date range  : %s → %s", start_dt, end_dt)

        # ── Step 1: Sales & Traffic (Data Kiosk) ─────────────────────────
        log.info("─── [1/3] Sales & Traffic ───────────────────────────────────")
        log.info("Submitting Data Kiosk query…")
        query_body = build_sales_traffic_query(start_dt, end_dt, settings.marketplace_id)
        query_id   = create_data_kiosk_query(access_token, query_body)
        log.info("queryId = %s", query_id)

        log.info("Polling for results (up to 30 min, checking every 30s)…")
        status_payload = poll_query_status(
            access_token, query_id, poll_seconds=30, max_wait_minutes=30
        )

        data_document_id = status_payload.get("dataDocumentId")
        if not data_document_id:
            raise RuntimeError(f"No dataDocumentId returned for queryId={query_id}")

        log.info("Downloading document %s…", data_document_id)
        payloads = download_query_document(access_token, data_document_id)

        log.info("Writing rows to sc_raw.sales_traffic…")
        rows_sc = upsert_sales_traffic(payloads, end_dt, settings.marketplace_id)
        log.info("✓  %d sales/traffic rows written", rows_sc)

        # ── Step 2: FBA Inventory ─────────────────────────────────────────
        log.info("─── [2/3] FBA Inventory ─────────────────────────────────────")
        rows_inv = pull_fba_inventory(client_id)
        log.info("✓  %s inventory rows written", rows_inv)

        # ── Step 3: BSR Snapshot (best-effort — failure won't abort) ─────
        log.info("─── [3/3] Best Seller Rank ──────────────────────────────────")
        try:
            import psycopg2  # type: ignore
            from pipeline.bsr_pipeline import fetch_bsr_batch, upsert_bsr_history  # type: ignore

            db_url = _get_db_url()
            with psycopg2.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT DISTINCT child_asin
                        FROM sc_raw.sales_traffic
                        WHERE marketplace_id = %s
                          AND report_date >= %s
                          AND child_asin IS NOT NULL
                        LIMIT 500
                        """,
                        (settings.marketplace_id, start_dt),
                    )
                    bsr_asins = [r[0] for r in cur.fetchall()]

            if bsr_asins:
                log.info("Fetching BSR for %d ASINs…", len(bsr_asins))
                bsr_cfg = {
                    "lwa_client_id":     os.getenv("LWA_CLIENT_ID", ""),
                    "lwa_client_secret": os.getenv("LWA_CLIENT_SECRET", ""),
                    "refresh_token_uae": refresh_token,
                    "aws_access_key":    os.getenv("AWS_ACCESS_KEY_ID", ""),
                    "aws_secret_key":    os.getenv("AWS_SECRET_ACCESS_KEY", ""),
                    "aws_region":        os.getenv("AWS_REGION", "eu-west-1"),
                    "marketplace_uae":   settings.marketplace_id,
                    "spapi_account_id":  client_id,
                    "endpoint":          "https://sellingpartnerapi-eu.amazon.com",
                    "database_url":      db_url,
                }
                today_str = date.today().strftime("%Y-%m-%d")
                bsr_rows  = fetch_bsr_batch(
                    bsr_cfg, token=access_token, asins=bsr_asins, report_date=today_str
                )
                rows_bsr  = upsert_bsr_history(bsr_rows, db_url)
                log.info("✓  %d BSR rows written", rows_bsr)
            else:
                log.info("No ASINs found in sales data — skipping BSR snapshot")

        except Exception as bsr_exc:
            log.warning("BSR snapshot failed (non-fatal, continuing): %s", bsr_exc)

        # ── Done ──────────────────────────────────────────────────────────
        set_onboarding_status(client_id, "active")

        elapsed = time.monotonic() - t0
        log.info("══════════════════════════════════════════════")
        log.info("✅  Backfill complete  client=%s  elapsed=%.0fs", client_id, elapsed)
        log.info("══════════════════════════════════════════════")

    except Exception as exc:
        elapsed = time.monotonic() - t0
        log.error("══════════════════════════════════════════════")
        log.error("❌  Backfill FAILED  client=%s  elapsed=%.0fs", client_id, elapsed)
        log.error("Error: %s", exc)
        log.error("══════════════════════════════════════════════")
        log.info("Reverting onboarding_status → connected")
        try:
            set_onboarding_status(client_id, "connected")
        except Exception:
            pass
        sys.exit(1)

    finally:
        # Always restore the env token — never leave a foreign token in the environment
        if prev_token is not None:
            os.environ["LWA_REFRESH_TOKEN_UAE"] = prev_token
        else:
            os.environ.pop("LWA_REFRESH_TOKEN_UAE", None)

        # Clear pipeline token cache
        try:
            from pipelines import sp_api_client as _spc  # type: ignore
            _spc._token_cache.update({"access_token": None, "expires_at": None})
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    # Load .env if present (local dev convenience)
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    parser = argparse.ArgumentParser(
        description="Run SP-API historical backfill for a client outside Streamlit.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--client-id",
        metavar="ID",
        help="Client ID to backfill (must exist in client_settings)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        metavar="N",
        help="Days of history to pull (default: 90)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print plan without calling Amazon or writing to DB",
    )
    parser.add_argument(
        "--list-clients",
        action="store_true",
        help="List all clients and their current status, then exit",
    )

    args = parser.parse_args()

    if args.list_clients:
        list_clients()
        return

    if not args.client_id:
        parser.error("--client-id is required (or use --list-clients to see options)")

    run_backfill(
        client_id=args.client_id,
        days=args.days,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
