"""Transform Data Kiosk payloads into DB-ready rows."""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple


def _extract_records(raw_records: Iterable[Dict]) -> List[Dict]:
    records: List[Dict] = []
    for rec in raw_records:
        if not isinstance(rec, dict):
            continue
        if "childAsin" in rec:
            records.append(rec)
            continue
        data = rec.get("data", rec)
        analytics = data.get("analytics_salesAndTraffic_2024_04_24") if isinstance(data, dict) else None
        if isinstance(analytics, dict):
            for row in analytics.get("salesAndTrafficByAsin", []):
                if isinstance(row, dict):
                    records.append(row)
    return records


def parse_records(raw_records: list, marketplace_id: str, query_id: str, account_id: str) -> list:
    rows = []
    for rec in _extract_records(raw_records):
        sales = rec.get("sales", {})
        traffic = rec.get("traffic", {})
        ops = sales.get("orderedProductSales", {})

        rows.append(
            {
                "report_date": rec.get("startDate"),
                "marketplace_id": marketplace_id,
                "account_id": account_id,
                "child_asin": rec.get("childAsin"),
                "parent_asin": rec.get("parentAsin"),
                "ordered_revenue": ops.get("amount"),
                "ordered_revenue_currency": ops.get("currencyCode"),
                "units_ordered": sales.get("unitsOrdered"),
                "total_order_items": sales.get("totalOrderItems"),
                "page_views": traffic.get("pageViews"),
                "sessions": traffic.get("sessions"),
                "buy_box_percentage": traffic.get("buyBoxPercentage"),
                "unit_session_percentage": traffic.get("unitSessionPercentage"),
                "query_id": query_id,
            }
        )
    return rows


def validate_row(row: dict) -> Tuple[bool, str]:
    if not row.get("child_asin"):
        return False, "missing child_asin"
    if not row.get("report_date"):
        return False, "missing report_date"
    if not row.get("marketplace_id"):
        return False, "missing marketplace_id"
    return True, ""
