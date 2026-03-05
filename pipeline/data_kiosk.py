"""Data Kiosk API calls for sales/traffic extraction."""

from __future__ import annotations

import json
import time
from typing import Dict, List

import requests
from requests import RequestException

from pipeline.auth import get_auth, make_headers


def _request_with_retries(method: str, url: str, max_retries: int = 4, **kwargs):
    """Retry transient network/SP-API failures with exponential backoff."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            response = requests.request(method, url, **kwargs)
            if response.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"retryable status {response.status_code}", response=response)
            response.raise_for_status()
            return response
        except (RequestException, requests.HTTPError) as exc:
            last_exc = exc
            if attempt == max_retries - 1:
                break
            sleep_for = 2 ** attempt
            time.sleep(sleep_for)
    raise last_exc


def build_query(start_date: str, end_date: str, marketplace_id: str) -> str:
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


def create_query(config: dict, token: str, query_body: str) -> str:
    response = _request_with_retries(
        "POST",
        f"{config['endpoint']}/dataKiosk/2023-11-15/queries",
        headers=make_headers(token),
        auth=get_auth(config),
        data=query_body,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["queryId"]


def get_query(config: dict, token: str, query_id: str) -> Dict:
    response = _request_with_retries(
        "GET",
        f"{config['endpoint']}/dataKiosk/2023-11-15/queries/{query_id}",
        headers=make_headers(token),
        auth=get_auth(config),
        timeout=60,
    )
    return response.json()


def poll_query(config: dict, token: str, query_id: str, max_wait_minutes: int = 60) -> Dict:
    elapsed = 0
    while elapsed < max_wait_minutes:
        status_obj = get_query(config, token, query_id)
        status = status_obj.get("processingStatus")
        if status == "DONE":
            return status_obj
        if status in ("FATAL", "CANCELLED"):
            raise RuntimeError(f"Query {query_id} failed with status={status}")
        time.sleep(60)
        elapsed += 1
    raise TimeoutError(f"Query {query_id} exceeded {max_wait_minutes} minutes")


def download_document(config: dict, token: str, data_document_id: str) -> List[Dict]:
    response = _request_with_retries(
        "GET",
        f"{config['endpoint']}/dataKiosk/2023-11-15/documents/{data_document_id}",
        headers=make_headers(token),
        auth=get_auth(config),
        timeout=60,
    )
    document_url = response.json()["documentUrl"]

    blob = _request_with_retries("GET", document_url, timeout=120)

    rows: List[Dict] = []
    for line in blob.text.splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows
