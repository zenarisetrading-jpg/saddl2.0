"""Seller Central Data Kiosk pipeline for daily ASIN sales/traffic ingestion."""

from __future__ import annotations

import json
import logging
import os
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

import psycopg2
import requests

from pipelines.sp_api_client import get_auth, get_settings, get_token, make_headers


logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")


def build_sales_traffic_query(start_date: str, end_date: str, marketplace_id: str) -> str:
    """Build Data Kiosk GraphQL query body using aggregateBy=CHILD.

    Use startDate == endDate for a single-day query (returns one row per ASIN
    for that day).  Use a date range for a multi-day aggregated pull (returns
    one row per ASIN covering the whole range — daily granularity requires
    separate per-day queries).
    """
    query = f"""
    {{
      analytics_salesAndTraffic_2024_04_24 {{
        salesAndTrafficByAsin(
          startDate: \"{start_date}\"
          endDate: \"{end_date}\"
          marketplaceIds: [\"{marketplace_id}\"]
          aggregateBy: CHILD
        ) {{
          startDate
          endDate
          childAsin
          parentAsin
          sales {{
            orderedProductSales {{
              amount
              currencyCode
            }}
            unitsOrdered
            totalOrderItems
          }}
          traffic {{
            pageViews
            sessions
            buyBoxPercentage
            unitSessionPercentage
          }}
        }}
      }}
    }}
    """
    return json.dumps({"query": query})


def create_data_kiosk_query(
    access_token: str, query_body: str, region_endpoint: Optional[str] = None
) -> str:
    settings = get_settings(region_endpoint=region_endpoint)
    url = f"{settings.endpoint}/dataKiosk/2023-11-15/queries"
    response = requests.post(
        url,
        headers=make_headers(access_token),
        auth=get_auth(),
        data=query_body,
        timeout=60,
    )
    response.raise_for_status()
    query_id = response.json()["queryId"]
    logger.info("Submitted Data Kiosk query %s", query_id)
    return query_id


def poll_query_status(
    access_token: str,
    query_id: str,
    poll_seconds: int = 60,
    max_wait_minutes: int = 60,
    region_endpoint: Optional[str] = None,
) -> Dict:
    settings = get_settings(region_endpoint=region_endpoint)
    url = f"{settings.endpoint}/dataKiosk/2023-11-15/queries/{query_id}"
    max_polls = max_wait_minutes * 60 // poll_seconds

    for attempt in range(int(max_polls) + 1):
        response = requests.get(url, headers=make_headers(access_token), auth=get_auth(), timeout=60)
        response.raise_for_status()
        payload = response.json()
        status = payload.get("processingStatus")
        logger.info("Query %s status=%s attempt=%s", query_id, status, attempt)

        if status == "DONE":
            return payload
        if status in {"CANCELLED", "FATAL"}:
            raise RuntimeError(f"Data Kiosk query failed ({status}) for queryId={query_id}")

        time.sleep(poll_seconds)

    raise TimeoutError(f"Query {query_id} did not complete within {max_wait_minutes} minutes")


def download_query_document(
    access_token: str, data_document_id: str, region_endpoint: Optional[str] = None
) -> List[Dict]:
    settings = get_settings(region_endpoint=region_endpoint)
    url = f"{settings.endpoint}/dataKiosk/2023-11-15/documents/{data_document_id}"
    response = requests.get(url, headers=make_headers(access_token), auth=get_auth(), timeout=60)
    response.raise_for_status()
    document_url = response.json()["documentUrl"]

    file_response = requests.get(document_url, timeout=120)
    file_response.raise_for_status()

    rows: List[Dict] = []
    for line in file_response.text.splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def _extract_rows(payloads: Iterable[Dict]) -> List[Dict]:
    """Normalize different response wrappers to flat record rows."""
    rows: List[Dict] = []
    for payload in payloads:
        if not isinstance(payload, dict):
            continue

        if "childAsin" in payload:
            rows.append(payload)
            continue

        data = payload.get("data", payload)
        analytics = data.get("analytics_salesAndTraffic_2024_04_24") if isinstance(data, dict) else None
        if isinstance(analytics, dict):
            nested = analytics.get("salesAndTrafficByAsin", [])
            if isinstance(nested, list):
                rows.extend([r for r in nested if isinstance(r, dict)])
    return rows


def _get_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("Missing required env var: DATABASE_URL")
    return psycopg2.connect(db_url)


def upsert_sales_traffic(
    records: List[Dict],
    report_date: str,
    marketplace_id: str,
    account_id: str = "",
) -> int:
    """Write raw sales/traffic rows to sc_raw.sales_traffic.

    ``account_id`` must be the caller's local client identifier (e.g. the
    value stored in ``client_settings.client_id``) so that rows are
    isolated per tenant and can be aggregated correctly by the downstream
    ``pipeline.aggregator.upsert_account_daily`` function.
    """
    rows = _extract_rows(records)
    if not rows:
        logger.warning("No sales/traffic rows found for %s", report_date)
        return 0

    if not account_id:
        logger.warning(
            "upsert_sales_traffic called without account_id for %s — rows will be untagged",
            report_date,
        )

    sql = """
    INSERT INTO sc_raw.sales_traffic (
        report_date,
        marketplace_id,
        account_id,
        child_asin,
        parent_asin,
        ordered_revenue,
        ordered_revenue_currency,
        units_ordered,
        total_order_items,
        page_views,
        sessions,
        buy_box_percentage,
        unit_session_percentage,
        pulled_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (report_date, marketplace_id, account_id, child_asin)
    DO UPDATE SET
        parent_asin = EXCLUDED.parent_asin,
        ordered_revenue = EXCLUDED.ordered_revenue,
        ordered_revenue_currency = EXCLUDED.ordered_revenue_currency,
        units_ordered = EXCLUDED.units_ordered,
        total_order_items = EXCLUDED.total_order_items,
        page_views = EXCLUDED.page_views,
        sessions = EXCLUDED.sessions,
        buy_box_percentage = EXCLUDED.buy_box_percentage,
        unit_session_percentage = EXCLUDED.unit_session_percentage,
        pulled_at = NOW();
    """

    inserted = 0
    with _get_connection() as conn:
        with conn.cursor() as cur:
            for row in rows:
                sales = row.get("sales", {}) or {}
                traffic = row.get("traffic", {}) or {}
                ordered_sales = sales.get("orderedProductSales", {}) or {}
                cur.execute(
                    sql,
                    (
                        row.get("startDate") or report_date,
                        marketplace_id,
                        account_id or None,
                        row.get("childAsin"),
                        row.get("parentAsin"),
                        ordered_sales.get("amount"),
                        ordered_sales.get("currencyCode"),
                        sales.get("unitsOrdered"),
                        sales.get("totalOrderItems"),
                        traffic.get("pageViews"),
                        traffic.get("sessions"),
                        traffic.get("buyBoxPercentage"),
                        traffic.get("unitSessionPercentage"),
                    ),
                )
                inserted += 1
        conn.commit()

    return inserted


def upsert_account_totals(report_date: str, marketplace_id: str, account_id: str = "") -> None:
    sql = """
    INSERT INTO sc_raw.account_totals (
        report_date,
        marketplace_id,
        total_ordered_revenue,
        total_units_ordered,
        total_page_views,
        total_sessions,
        asin_count,
        computed_at
    )
    SELECT
        report_date,
        marketplace_id,
        COALESCE(SUM(ordered_revenue), 0),
        COALESCE(SUM(units_ordered), 0),
        COALESCE(SUM(page_views), 0),
        COALESCE(SUM(sessions), 0),
        COUNT(DISTINCT child_asin),
        NOW()
    FROM sc_raw.sales_traffic
    WHERE report_date = %s
      AND marketplace_id = %s
      AND (%s = '' OR account_id = %s)
    GROUP BY report_date, marketplace_id
    ON CONFLICT (report_date, marketplace_id)
    DO UPDATE SET
        total_ordered_revenue = EXCLUDED.total_ordered_revenue,
        total_units_ordered = EXCLUDED.total_units_ordered,
        total_page_views = EXCLUDED.total_page_views,
        total_sessions = EXCLUDED.total_sessions,
        asin_count = EXCLUDED.asin_count,
        computed_at = NOW();
    """

    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (report_date, marketplace_id, account_id, account_id))
        conn.commit()


def fetch_for_date(report_date: str, account_id: str = "") -> int:
    settings = get_settings()
    access_token = get_token()
    query_body = build_sales_traffic_query(report_date, report_date, settings.marketplace_id)

    query_id = create_data_kiosk_query(access_token, query_body)
    status_payload = poll_query_status(access_token, query_id)

    data_document_id: Optional[str] = status_payload.get("dataDocumentId")
    if not data_document_id:
        raise RuntimeError(f"No dataDocumentId returned for queryId={query_id}")

    payloads = download_query_document(access_token, data_document_id)
    row_count = upsert_sales_traffic(payloads, report_date, settings.marketplace_id, account_id=account_id)
    upsert_account_totals(report_date, settings.marketplace_id, account_id=account_id)
    logger.info("Processed %s rows for date=%s account_id=%s", row_count, report_date, account_id)
    return row_count


def pull_fba_inventory(
    client_id: str,
    marketplace_id: Optional[str] = None,
    region_endpoint: Optional[str] = None,
    lwa_refresh_token: Optional[str] = None,
) -> Optional[int]:
    def _as_int(value: Optional[str]) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    try:
        settings = get_settings(
            marketplace_id=marketplace_id,
            region_endpoint=region_endpoint,
            lwa_refresh_token=lwa_refresh_token,
        )
        access_token = get_token(settings=settings, force_refresh=True)
        auth = get_auth()

        print(f"Step 1: Fetching FBA inventory summaries for {client_id}...")
        parsed_rows: List[Dict] = []
        next_token = None
        page = 1

        while True:
            request_url = f"{settings.endpoint}/fba/inventory/v1/summaries"
            params = {
                "granularityType": "Marketplace",
                "granularityId": settings.marketplace_id,
                "marketplaceIds": settings.marketplace_id,
                "details": "true"
            }
            if next_token:
                params["nextToken"] = next_token

            logger.info("Fetching FBA inventory API page %d", page)

            response = None
            last_exc: Optional[Exception] = None
            for attempt in range(1, 5):
                try:
                    response = requests.get(
                        request_url,
                        params=params,
                        headers=make_headers(access_token),
                        auth=auth,
                        timeout=30,
                    )
                except Exception as req_exc:
                    last_exc = req_exc
                    logger.warning(
                        "FBA Inventory request error (attempt %d/4): %s: %s",
                        attempt, type(req_exc).__name__, req_exc,
                    )
                    if attempt < 4:
                        time.sleep(2 ** attempt)
                        continue
                    logger.error("FBA Inventory API failed after %d attempts: %s", attempt, req_exc)
                    return None

                if response.status_code == 429:
                    if attempt <= 3:
                        logger.warning("FBA Inventory API throttled (429). Waiting 10s before retry %s/3", attempt)
                        time.sleep(10)
                        continue
                    logger.error("FBA Inventory API failed after retries. status=%s body=%s", response.status_code, response.text)
                    return None
                break

            if not response or not response.ok:
                logger.error(
                    "FBA Inventory API failed. status=%s body=%s",
                    response.status_code if response else None,
                    (response.text[:500] if response else None),
                )
                return None

            data = response.json()
            payload = data.get("payload", {})
            summaries = payload.get("inventorySummaries", [])
            
            for summary in summaries:
                details = summary.get("inventoryDetails", {})
                reserved = details.get("reservedQuantity", {})
                unfulfillable = details.get("unfulfillableQuantity", {})
                
                parsed_rows.append({
                    "asin": summary.get("asin", None),
                    "fnsku": summary.get("fnSku", None),
                    "condition": summary.get("condition", None),
                    "afn-fulfillable-quantity": details.get("fulfillableQuantity", None),
                    "afn-inbound-working-quantity": details.get("inboundWorkingQuantity", None),
                    "afn-inbound-shipped-quantity": details.get("inboundShippedQuantity", None),
                    "afn-inbound-receiving-quantity": details.get("inboundReceivingQuantity", None),
                    "afn-reserved-quantity": reserved.get("totalReservedQuantity", None) if isinstance(reserved, dict) else None,
                    "afn-unsellable-quantity": unfulfillable.get("totalUnfulfillableQuantity", None) if isinstance(unfulfillable, dict) else None,
                    "afn-total-quantity": summary.get("totalQuantity", None),
                    "product-name": summary.get("productName", None)
                })
                
            next_token = data.get("pagination", {}).get("nextToken")
            if not next_token:
                break
            page += 1
            # Rate limiting for GET /fba/inventory/v1/summaries is 2 requests per second
            time.sleep(0.5)

        print(f"Step 2: {len(parsed_rows)} rows fetched")
        if not parsed_rows:
            logger.warning("FBA inventory API returned 0 rows.")
            return 0

        print("Step 3: Writing to database...")
        snapshot_date = datetime.utcnow().date()
        sql = """
        INSERT INTO sc_raw.fba_inventory (
            client_id,
            snapshot_date,
            asin,
            sku,
            fnsku,
            product_name,
            condition,
            your_price,
            mfn_listing_exists,
            afn_listing_exists,
            afn_warehouse_quantity,
            afn_fulfillable_quantity,
            afn_unsellable_quantity,
            afn_reserved_quantity,
            afn_total_quantity,
            per_unit_volume,
            afn_inbound_working_quantity,
            afn_inbound_shipped_quantity,
            afn_inbound_receiving_quantity
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (client_id, asin, snapshot_date) DO UPDATE SET
            fnsku = EXCLUDED.fnsku,
            product_name = EXCLUDED.product_name,
            condition = EXCLUDED.condition,
            afn_fulfillable_quantity = EXCLUDED.afn_fulfillable_quantity,
            afn_unsellable_quantity = EXCLUDED.afn_unsellable_quantity,
            afn_reserved_quantity = EXCLUDED.afn_reserved_quantity,
            afn_total_quantity = EXCLUDED.afn_total_quantity,
            afn_inbound_working_quantity = EXCLUDED.afn_inbound_working_quantity,
            afn_inbound_shipped_quantity = EXCLUDED.afn_inbound_shipped_quantity,
            afn_inbound_receiving_quantity = EXCLUDED.afn_inbound_receiving_quantity
        """

        logger.info("Writing %s rows to FBA inventory table", len(parsed_rows))
        rows_written = 0
        with _get_connection() as conn:
            with conn.cursor() as cur:
                for row in parsed_rows:
                    asin = row.get("asin", None)
                    if not asin:
                        continue
                    cur.execute(
                        sql,
                        (
                            client_id,
                            snapshot_date,
                            asin,
                            None,
                            row.get("fnsku", None),
                            row.get("product-name", None),
                            row.get("condition", None),
                            None,
                            None,
                            None,
                            None,
                            _as_int(row.get("afn-fulfillable-quantity", None)),
                            _as_int(row.get("afn-unsellable-quantity", None)),
                            _as_int(row.get("afn-reserved-quantity", None)),
                            _as_int(row.get("afn-total-quantity", None)),
                            None,
                            _as_int(row.get("afn-inbound-working-quantity", None)),
                            _as_int(row.get("afn-inbound-shipped-quantity", None)),
                            _as_int(row.get("afn-inbound-receiving-quantity", None)),
                        ),
                    )
                    rows_written += 1
            conn.commit()

        print(f"Step 3 complete: {rows_written} rows written")
        return rows_written
    except Exception:
        logger.error("Unhandled exception in pull_fba_inventory:\n%s", traceback.format_exc())
        return None


def run_daily_pull(client_id: str = "s2c_uae_test") -> None:
    """Pull D-1, D-2, D-3, D-7, D-30 one by one with per-date fault tolerance."""
    lookback_offsets = [1, 2, 3, 7, 30]
    today = datetime.utcnow().date()
    last_submit_ts: Optional[float] = None
    inventory_synced = False

    for offset in lookback_offsets:
        target_date = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
        logger.info("Starting SP-API pull for %s", target_date)

        try:
            if last_submit_ts:
                elapsed = time.time() - last_submit_ts
                if elapsed < 60:
                    sleep_for = 60 - elapsed
                    logger.info("Respecting createQuery rate limit; sleeping %.1fs", sleep_for)
                    time.sleep(sleep_for)

            # Fetch sales & traffic
            fetch_for_date(target_date, account_id=client_id)

            if not inventory_synced:
                try:
                    get_token(force_refresh=True)
                    pull_fba_inventory(client_id)
                    inventory_synced = True
                except Exception:
                    logger.exception("Inventory pull failed")

            last_submit_ts = time.time()
        except Exception:
            logger.exception("SP-API pull failed for %s", target_date)
            continue
