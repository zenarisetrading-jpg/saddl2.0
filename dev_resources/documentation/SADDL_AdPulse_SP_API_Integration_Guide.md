# SADDL AdPulse — SP-API Integration Guide
## Seller Central Business Report Pipeline

**Version:** 1.0  
**Scope:** Full implementation walkthrough — credentials, authorization, data pull, SADDL integration  
**Audience:** SADDL engineering / Aslam (founder build)

---

## Overview

This guide covers end-to-end implementation of the Amazon Selling Partner API (SP-API) pipeline to pull Business Report data (Sales & Traffic) into SADDL's Demand-Adjusted Optimization (DAO) module.

**Two API paths exist for this data. Use Data Kiosk (Path B) as the primary:**

| Path | API | Report Type | Recommendation |
|---|---|---|---|
| A | Reports API | `GET_SALES_AND_TRAFFIC_REPORT` | Functional but older pattern |
| B | Data Kiosk API | `Analytics_SalesAndTraffic_2024_04_24` | **Use this — newer, richer, GraphQL-based** |

Data Kiosk is Amazon's current-generation analytics API. It returns ASIN-level sales and traffic in structured JSON (not CSV parsing), supports daily/weekly/monthly granularity, and is what Amazon recommends for new integrations.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AMAZON SYSTEMS                              │
│                                                                     │
│  Seller Central Account (Zenarise)                                  │
│       │                                                             │
│       ▼                                                             │
│  SP-API Gateway (api.amazon.com / api.amazonservices.com for UAE)   │
│       │                                                             │
│       ├── Data Kiosk API  ──── Sales & Traffic by ASIN (daily)     │
│       ├── Reports API     ──── GET_SALES_AND_TRAFFIC_REPORT (CSV)  │
│       └── Sales API       ──── Order metrics (supplementary)       │
└──────────────────┬──────────────────────────────────────────────────┘
                   │  HTTPS + OAuth 2.0 (LWA tokens)
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SADDL DATA PIPELINE                              │
│                                                                     │
│  Token Manager  →  API Client  →  Parser  →  Normalizer            │
│                                              │                      │
│                                              ▼                      │
│                                    Raw Data Store (PostgreSQL)      │
│                                              │                      │
│                                              ▼                      │
│                                    Index Computation Engine         │
│                                    (OSI, BHI, CDI inputs)          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Credentials Setup (One-Time)

This is the most bureaucratic part. Do it once; everything downstream is automated.

### Step 1.1 — Register as SP-API Developer

You need a **Professional selling account** (you have this as Zenarise).

1. Log in to Seller Central (sellercentral.amazon.ae for UAE)
2. Navigate to: **Apps & Services → Develop Apps**
3. Click **"Developer Central"**
4. Click **"Add New App Client"** or **"Register as Developer"**
5. Fill out the Developer Profile:
   - **App name:** SADDL AdPulse
   - **Purpose:** Internal business analytics tool for own seller account
   - **Developer type:** Select **"Private Developer"** — this is key. Since SADDL is initially accessing only Zenarise's account (your own), you don't need the Public Developer route. Private developer apps are self-authorized, no app store listing required.
6. For data access purpose, describe: *"Automated retrieval of sales and traffic analytics to power internal PPC optimization decision engine"*
7. Submit and wait for approval (typically 1–3 business days)

### Step 1.2 — Request Required Roles

In your developer profile, request the following roles:

| Role | Why Needed |
|---|---|
| **Selling Partner Insights** | Required for Sales & Traffic report, Data Kiosk analytics |
| **Analytics** | Required for Data Kiosk API access |
| **Reports** | Required for Reports API fallback |

To request: In Developer Central → Developer Profile → Data Access section → check the roles above → save and resubmit for approval.

### Step 1.3 — Create Your Application

Once developer profile is approved:

1. In Developer Central, click **"Add New App Client"**
2. Fill in:
   - **App name:** SADDL AdPulse Data Pipeline
   - **IAM ARN:** (from Step 1.4 below — come back to this)
   - **Roles:** Select the roles approved in Step 1.2
3. Save — you'll get a **Client ID** and **Client Secret**. Store these securely.

### Step 1.4 — Create AWS IAM User

SP-API uses AWS Signature Version 4 for request signing. You need an AWS IAM user.

1. Go to [aws.amazon.com](https://aws.amazon.com) → create a free account if needed (you only need IAM — no paid services required)
2. Navigate to **IAM → Users → Create User**
3. Name it: `saddl-spapi-user`
4. Attach policy: `AmazonSellingPartnerAPI` (or create custom policy with minimum permissions)
5. Create **Access Keys** for the user: save the **Access Key ID** and **Secret Access Key**
6. Copy the **IAM User ARN** (format: `arn:aws:iam::123456789:user/saddl-spapi-user`)
7. Go back to Step 1.3 and paste this ARN into your app registration

### Step 1.5 — Self-Authorization (Generate Refresh Token)

Since this is a private app for your own account:

1. In Developer Central, find your app → click **"Authorize"**
2. This initiates a self-authorization flow that generates a **Refresh Token**
3. Save this token — it does not expire unless you revoke it
4. This refresh token, combined with your Client ID and Client Secret, lets you generate access tokens to make API calls

**Your complete credentials set:**
```
LWA_CLIENT_ID     = "amzn1.application-oa2-client.xxxxxxxx"
LWA_CLIENT_SECRET = "amzn1.oa2-cs.v1.xxxxxxxx"  
LWA_REFRESH_TOKEN = "Atzr|xxxxxxxx"
AWS_ACCESS_KEY_ID     = "AKIAXXXXXXXX"
AWS_SECRET_ACCESS_KEY = "xxxxxxxxxxxxxxxx"
AWS_REGION            = "eu-west-1"  # for UAE/Middle East marketplace
MARKETPLACE_ID        = "A2VIGQ35RCS4UG"  # Amazon.ae marketplace ID
```

Store all credentials in environment variables or a secrets manager — **never hardcode in source files.**

---

## Part 2: Token Exchange Flow

SP-API uses two-layer authentication: an LWA (Login with Amazon) OAuth token layer on top of AWS Signature V4 signing.

### Access Token Flow (Implemented in SADDL Token Manager)

```python
import requests

def get_lwa_access_token(client_id, client_secret, refresh_token):
    """Exchange refresh token for short-lived access token (1 hour TTL)."""
    response = requests.post(
        "https://api.amazon.com/auth/o2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    )
    response.raise_for_status()
    return response.json()["access_token"]
```

Access tokens expire in **1 hour**. SADDL's token manager should cache the token and refresh ~5 minutes before expiry, not on every request.

### Request Signing (AWS Signature V4)

Every SP-API request must be signed with AWS credentials. Use the `boto3` library or `requests-aws4auth`:

```python
pip install boto3 requests requests-aws4auth
```

---

## Part 3: Data Kiosk API — Primary Data Source

Data Kiosk is the recommended modern approach. It uses GraphQL queries to request specific datasets and returns structured JSON.

### Step 3.1 — How Data Kiosk Works

Data Kiosk is asynchronous:
1. **Submit a query** → Amazon queues it
2. **Poll for status** → query processes (typically 5–30 minutes)
3. **Download document** → fetch the result when ready

### Step 3.2 — Full Python Implementation

```python
import boto3
import requests
import json
import time
import os
from requests_aws4auth import AWS4Auth
from datetime import datetime, timedelta

# ── Configuration ──────────────────────────────────────────────────────────────

ENDPOINT = "https://sellingpartnerapi-eu.amazon.com"  # EU endpoint covers UAE
MARKETPLACE_ID = "A2VIGQ35RCS4UG"  # Amazon.ae

LWA_CLIENT_ID     = os.environ["LWA_CLIENT_ID"]
LWA_CLIENT_SECRET = os.environ["LWA_CLIENT_SECRET"]
LWA_REFRESH_TOKEN = os.environ["LWA_REFRESH_TOKEN"]
AWS_ACCESS_KEY_ID     = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_REGION = "eu-west-1"


# ── Auth Helpers ───────────────────────────────────────────────────────────────

def get_access_token():
    """Get LWA access token (cache this — expires in 1 hour)."""
    response = requests.post(
        "https://api.amazon.com/auth/o2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": LWA_REFRESH_TOKEN,
            "client_id": LWA_CLIENT_ID,
            "client_secret": LWA_CLIENT_SECRET,
        }
    )
    response.raise_for_status()
    return response.json()["access_token"]


def get_aws_auth():
    """Get AWS Signature V4 auth for request signing."""
    return AWS4Auth(
        AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY,
        AWS_REGION,
        "execute-api"
    )


def get_headers(access_token):
    return {
        "x-amz-access-token": access_token,
        "x-amz-date": datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ── Data Kiosk Query ───────────────────────────────────────────────────────────

def build_sales_traffic_query(start_date: str, end_date: str) -> str:
    """
    GraphQL query for ASIN-level daily sales and traffic.
    
    start_date, end_date: "YYYY-MM-DD" format
    Returns all key metrics needed for OSI, BHI, CDI computation.
    """
    return json.dumps({
        "query": f"""
        {{
          analytics_salesAndTraffic_2024_04_24 {{
            salesAndTrafficByAsin(
              startDate: "{start_date}"
              endDate: "{end_date}"
              marketplaceIds: ["{MARKETPLACE_ID}"]
              dateGranularity: DAY
              asinGranularity: CHILD
            ) {{
              startDate
              endDate
              asin
              sales {{
                orderedProductSales {{
                  amount
                  currencyCode
                }}
                orderedProductSalesB2B {{
                  amount
                  currencyCode
                }}
                unitsOrdered
                unitsOrderedB2B
                totalOrderItems
              }}
              traffic {{
                browserPageViews
                browserPageViewsB2B
                mobileAppPageViews
                mobileAppPageViewsB2B
                pageViews
                pageViewsB2B
                browserSessions
                mobileAppSessions
                sessions
                sessionsB2B
                buyBoxPercentage
                buyBoxPercentageB2B
                orderItemSessionPercentage
                orderItemSessionPercentageB2B
                unitSessionPercentage
                unitSessionPercentageB2B
              }}
            }}
          }}
        }}
        """
    })


# ── Data Kiosk API Calls ───────────────────────────────────────────────────────

def create_data_kiosk_query(access_token: str, query_body: str) -> str:
    """Submit a Data Kiosk query and return the queryId."""
    url = f"{ENDPOINT}/dataKiosk/2023-11-15/queries"
    
    response = requests.post(
        url,
        headers=get_headers(access_token),
        auth=get_aws_auth(),
        data=query_body
    )
    response.raise_for_status()
    query_id = response.json()["queryId"]
    print(f"Query submitted: {query_id}")
    return query_id


def poll_query_status(access_token: str, query_id: str, max_wait_minutes: int = 60) -> dict:
    """Poll until query is DONE or CANCELLED. Returns final query object."""
    url = f"{ENDPOINT}/dataKiosk/2023-11-15/queries/{query_id}"
    elapsed = 0
    
    while elapsed < max_wait_minutes:
        response = requests.get(
            url,
            headers=get_headers(access_token),
            auth=get_aws_auth()
        )
        response.raise_for_status()
        query = response.json()
        status = query.get("processingStatus")
        
        print(f"[{elapsed}min] Query {query_id} status: {status}")
        
        if status == "DONE":
            return query
        elif status in ("CANCELLED", "FATAL"):
            raise RuntimeError(f"Query failed with status: {status}")
        
        time.sleep(60)  # wait 1 minute between polls
        elapsed += 1
    
    raise TimeoutError(f"Query {query_id} did not complete within {max_wait_minutes} minutes")


def download_query_document(access_token: str, document_id: str) -> list:
    """Download and parse the query result document."""
    # First get the document URL
    url = f"{ENDPOINT}/dataKiosk/2023-11-15/documents/{document_id}"
    response = requests.get(
        url,
        headers=get_headers(access_token),
        auth=get_aws_auth()
    )
    response.raise_for_status()
    document_url = response.json()["documentUrl"]
    
    # Download the actual data (no auth needed — it's a presigned S3 URL)
    data_response = requests.get(document_url)
    data_response.raise_for_status()
    
    # Data Kiosk returns JSONL (one JSON object per line)
    lines = data_response.text.strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


# ── Main Pipeline Function ─────────────────────────────────────────────────────

def fetch_sales_traffic_data(start_date: str, end_date: str) -> list:
    """
    Full pipeline: authenticate → query → poll → download → return parsed data.
    
    Returns list of ASIN-level daily records.
    """
    access_token = get_access_token()
    query_body = build_sales_traffic_query(start_date, end_date)
    
    query_id = create_data_kiosk_query(access_token, query_body)
    query_result = poll_query_status(access_token, query_id)
    
    document_id = query_result.get("documentId")
    if not document_id:
        raise ValueError("Query completed but no documentId returned")
    
    records = download_query_document(access_token, document_id)
    print(f"Downloaded {len(records)} ASIN-day records")
    return records


# ── Daily Scheduler Entry Point ────────────────────────────────────────────────

def run_daily_pull():
    """
    Runs daily at 06:00 account local time.
    Pulls yesterday + lookback days to catch attribution updates.
    """
    today = datetime.utcnow().date()
    
    # Lookback schedule: pull D-1, D-2, D-3, D-7, D-30
    # Catches Amazon's retroactive attribution updates
    lookback_offsets = [1, 2, 3, 7, 30]
    
    for offset in lookback_offsets:
        target_date = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
        print(f"\nPulling data for: {target_date}")
        
        try:
            records = fetch_sales_traffic_data(target_date, target_date)
            upsert_to_database(records, target_date)
        except Exception as e:
            print(f"Error pulling {target_date}: {e}")
            # Log error, continue with other dates
            continue


# ── Database Integration ───────────────────────────────────────────────────────

def upsert_to_database(records: list, report_date: str):
    """
    Upsert ASIN-level records into SADDL's raw data store.
    Uses UPSERT (INSERT ON CONFLICT UPDATE) so re-pulls overwrite stale data.
    """
    import psycopg2  # or your ORM of choice
    
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    
    for record in records:
        asin_data = record.get("salesAndTrafficByAsin", [])
        
        for row in asin_data:
            sales = row.get("sales", {})
            traffic = row.get("traffic", {})
            
            cur.execute("""
                INSERT INTO sc_sales_traffic (
                    report_date,
                    marketplace_id,
                    asin,
                    ordered_revenue,
                    ordered_revenue_currency,
                    units_ordered,
                    total_order_items,
                    page_views,
                    sessions,
                    buy_box_percentage,
                    unit_session_percentage,
                    order_item_session_percentage,
                    pulled_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (report_date, marketplace_id, asin)
                DO UPDATE SET
                    ordered_revenue = EXCLUDED.ordered_revenue,
                    units_ordered = EXCLUDED.units_ordered,
                    total_order_items = EXCLUDED.total_order_items,
                    page_views = EXCLUDED.page_views,
                    sessions = EXCLUDED.sessions,
                    buy_box_percentage = EXCLUDED.buy_box_percentage,
                    unit_session_percentage = EXCLUDED.unit_session_percentage,
                    order_item_session_percentage = EXCLUDED.order_item_session_percentage,
                    pulled_at = NOW()
            """, (
                row.get("startDate"),
                MARKETPLACE_ID,
                row.get("asin"),
                sales.get("orderedProductSales", {}).get("amount"),
                sales.get("orderedProductSales", {}).get("currencyCode"),
                sales.get("unitsOrdered"),
                sales.get("totalOrderItems"),
                traffic.get("pageViews"),
                traffic.get("sessions"),
                traffic.get("buyBoxPercentage"),
                traffic.get("unitSessionPercentage"),
                traffic.get("orderItemSessionPercentage"),
            ))
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"Upserted {sum(len(r.get('salesAndTrafficByAsin', [])) for r in records)} rows")
```

---

## Part 4: Database Schema

### Table: `sc_sales_traffic` (Raw Seller Central Data)

```sql
CREATE TABLE sc_sales_traffic (
    id                          BIGSERIAL PRIMARY KEY,
    report_date                 DATE NOT NULL,
    marketplace_id              VARCHAR(20) NOT NULL,
    asin                        VARCHAR(20) NOT NULL,
    
    -- Sales metrics
    ordered_revenue             NUMERIC(14,2),
    ordered_revenue_currency    VARCHAR(3),
    units_ordered               INTEGER,
    total_order_items           INTEGER,
    
    -- Traffic metrics
    page_views                  INTEGER,
    sessions                    INTEGER,
    buy_box_percentage          NUMERIC(5,2),
    unit_session_percentage     NUMERIC(5,2),   -- CVR proxy (organic)
    order_item_session_percentage NUMERIC(5,2),
    
    -- Metadata
    pulled_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (report_date, marketplace_id, asin)
);

CREATE INDEX idx_sc_st_date ON sc_sales_traffic (report_date);
CREATE INDEX idx_sc_st_asin ON sc_sales_traffic (asin);
CREATE INDEX idx_sc_st_date_asin ON sc_sales_traffic (report_date, asin);
```

### Table: `sc_account_totals` (Daily Account Rollup — for OSI Computation)

```sql
CREATE TABLE sc_account_totals (
    id                      BIGSERIAL PRIMARY KEY,
    report_date             DATE NOT NULL,
    marketplace_id          VARCHAR(20) NOT NULL,
    
    -- Totals across all ASINs
    total_ordered_revenue   NUMERIC(16,2),
    total_units_ordered     INTEGER,
    total_page_views        INTEGER,
    total_sessions          INTEGER,
    asin_count              INTEGER,         -- how many ASINs had data this day
    
    -- Computed after join with ad console
    ad_attributed_revenue   NUMERIC(16,2),   -- populated by ad console pipeline
    organic_revenue         NUMERIC(16,2),   -- computed: total - ad_attributed
    organic_share_pct       NUMERIC(5,2),    -- computed: organic / total * 100
    tacos                   NUMERIC(5,2),    -- computed: ad_spend / total_revenue * 100
    
    computed_at             TIMESTAMPTZ,
    
    UNIQUE (report_date, marketplace_id)
);
```

---

## Part 5: Fallback — Reports API (GET_SALES_AND_TRAFFIC_REPORT)

If Data Kiosk has an outage or query failure, fall back to the Reports API. This is the older CSV-based approach.

```python
def fetch_via_reports_api(start_date: str, end_date: str, access_token: str) -> list:
    """Fallback: Reports API for sales & traffic data."""
    
    # Step 1: Create report
    url = f"{ENDPOINT}/reports/2021-06-30/reports"
    body = {
        "reportType": "GET_SALES_AND_TRAFFIC_REPORT",
        "marketplaceIds": [MARKETPLACE_ID],
        "dataStartTime": f"{start_date}T00:00:00Z",
        "dataEndTime": f"{end_date}T23:59:59Z",
        "reportOptions": {
            "dateGranularity": "DAY",
            "asinGranularity": "CHILD"
        }
    }
    response = requests.post(url, headers=get_headers(access_token),
                              auth=get_aws_auth(), json=body)
    response.raise_for_status()
    report_id = response.json()["reportId"]
    
    # Step 2: Poll for report completion
    report_url = f"{ENDPOINT}/reports/2021-06-30/reports/{report_id}"
    for _ in range(60):
        time.sleep(60)
        r = requests.get(report_url, headers=get_headers(access_token), auth=get_aws_auth())
        r.raise_for_status()
        report = r.json()
        if report["processingStatus"] == "DONE":
            document_id = report["reportDocumentId"]
            break
    
    # Step 3: Get document URL
    doc_url = f"{ENDPOINT}/reports/2021-06-30/documents/{document_id}"
    doc_r = requests.get(doc_url, headers=get_headers(access_token), auth=get_aws_auth())
    doc_r.raise_for_status()
    download_url = doc_r.json()["url"]
    
    # Step 4: Download CSV
    csv_r = requests.get(download_url)
    csv_r.raise_for_status()
    
    import csv
    import io
    reader = csv.DictReader(io.StringIO(csv_r.text), delimiter="\t")
    return list(reader)
```

---

## Part 6: Computed Views for DAO Module

These SQL views are what the Index Computation Engine reads. They are the bridge between raw SP-API data and the CDI/OSI calculations.

### View: Daily Organic Share (OSI Input)

```sql
CREATE OR REPLACE VIEW v_daily_organic_share AS
SELECT
    s.report_date,
    s.marketplace_id,
    
    -- Seller Central totals
    s.total_ordered_revenue AS sc_total_revenue,
    
    -- Ad console attributed (joined from ad data table)
    COALESCE(a.attributed_sales_14d, 0) AS ad_attributed_revenue,
    
    -- Organic computed
    s.total_ordered_revenue - COALESCE(a.attributed_sales_14d * 0.90, 0) 
        AS organic_revenue_adjusted,  -- 0.90 = attribution overlap correction
    
    -- OSI
    ROUND(
        (s.total_ordered_revenue - COALESCE(a.attributed_sales_14d * 0.90, 0))
        / NULLIF(s.total_ordered_revenue, 0) * 100,
        2
    ) AS organic_share_pct,
    
    -- TACOS
    ROUND(
        COALESCE(a.total_spend, 0) / NULLIF(s.total_ordered_revenue, 0) * 100,
        2
    ) AS tacos

FROM sc_account_totals s
LEFT JOIN ad_console_daily_totals a
    ON s.report_date = a.report_date
    AND s.marketplace_id = a.marketplace_id

WHERE s.report_date >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY s.report_date DESC;
```

### View: OSI 7-Day Rolling vs Baseline (for OSI Index Calculation)

```sql
CREATE OR REPLACE VIEW v_osi_index AS
WITH daily_osi AS (
    SELECT
        report_date,
        marketplace_id,
        organic_share_pct,
        AVG(organic_share_pct) OVER (
            ORDER BY report_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS osi_7d_avg
    FROM v_daily_organic_share
),
baseline AS (
    SELECT
        report_date,
        marketplace_id,
        osi_7d_avg,
        LAG(osi_7d_avg, 28) OVER (
            PARTITION BY marketplace_id ORDER BY report_date
        ) AS osi_baseline_7d_avg  -- same 7-day window, 4 weeks prior
    FROM daily_osi
)
SELECT
    report_date,
    marketplace_id,
    osi_7d_avg AS current_osi,
    osi_baseline_7d_avg AS baseline_osi,
    ROUND(osi_7d_avg - osi_baseline_7d_avg, 2) AS osi_delta,
    ROUND(osi_7d_avg / NULLIF(osi_baseline_7d_avg, 0) * 100, 1) AS osi_index
FROM baseline
WHERE osi_baseline_7d_avg IS NOT NULL  -- only where baseline exists (28+ days of data)
ORDER BY report_date DESC;
```

---

## Part 7: Scheduler Setup

### Cron Job (if self-hosted)

```bash
# In your crontab or scheduler config
# Run daily at 06:00 UTC (09:00 UAE time)
0 6 * * * /usr/bin/python3 /app/saddl/pipelines/sp_api_pipeline.py >> /var/log/saddl/sp_api.log 2>&1
```

### If using a job queue (Celery / Redis)

```python
# tasks.py
from celery import Celery
from celery.schedules import crontab

app = Celery("saddl")

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Daily pull at 06:00 UTC
    sender.add_periodic_task(
        crontab(hour=6, minute=0),
        pull_seller_central_data.s(),
    )

@app.task
def pull_seller_central_data():
    from pipelines.sp_api_pipeline import run_daily_pull
    run_daily_pull()
```

---

## Part 8: Agency Client Integration (Multi-Seller)

When SADDL onboards agency clients, each client authorizes their own Seller Central account via OAuth. Here's how that differs from the self-authorization above.

### For Each Agency Client

1. **SADDL registers as a Public Developer** (separate from your private developer profile) — this requires listing on the Amazon Appstore, which involves a review process (4–6 weeks typically)
2. Each client completes an **OAuth authorization flow** on a SADDL-hosted URL
3. The flow generates a **unique refresh token per client**
4. SADDL stores each client's refresh token, encrypted, in the database
5. All API calls are made with the client's specific token

### Multi-Tenant Token Storage

```sql
CREATE TABLE seller_authorizations (
    id                  BIGSERIAL PRIMARY KEY,
    saddl_account_id    UUID NOT NULL REFERENCES accounts(id),
    seller_id           VARCHAR(50) NOT NULL,  -- Amazon Seller ID
    marketplace_id      VARCHAR(20) NOT NULL,
    
    -- Encrypted tokens (use pgcrypto or application-level encryption)
    refresh_token_enc   BYTEA NOT NULL,
    
    -- Status
    is_active           BOOLEAN DEFAULT TRUE,
    authorized_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_token_use      TIMESTAMPTZ,
    
    UNIQUE (saddl_account_id, seller_id, marketplace_id)
);
```

### OAuth Flow (for agency clients)

```python
# When client clicks "Connect Amazon Account" in SADDL
def get_oauth_url(state_token: str) -> str:
    """Generate the Amazon OAuth URL to redirect the client to."""
    return (
        "https://sellercentral.amazon.ae/apps/authorize/consent"
        f"?application_id={LWA_CLIENT_ID}"
        f"&state={state_token}"
        f"&redirect_uri=https://app.saddl.io/oauth/amazon/callback"
        "&version=beta"
    )

# Amazon redirects back to your callback URL with ?code=xxx&state=xxx
def handle_oauth_callback(code: str, state_token: str) -> str:
    """Exchange auth code for refresh token."""
    response = requests.post(
        "https://api.amazon.com/auth/o2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "https://app.saddl.io/oauth/amazon/callback",
            "client_id": LWA_CLIENT_ID,
            "client_secret": LWA_CLIENT_SECRET,
        }
    )
    response.raise_for_status()
    refresh_token = response.json()["refresh_token"]
    # Encrypt and store per seller_authorizations schema above
    return refresh_token
```

---

## Part 9: Marketplace IDs Reference

SADDL operates in GCC — use these marketplace IDs:

| Marketplace | Country | Marketplace ID | SP-API Endpoint |
|---|---|---|---|
| Amazon.ae | UAE | `A2VIGQ35RCS4UG` | `sellingpartnerapi-eu.amazon.com` |
| Amazon.sa | Saudi Arabia | `A17E79C6D8DWNP` | `sellingpartnerapi-eu.amazon.com` |
| Amazon.eg | Egypt | `ARBP9OOSHTCHU` | `sellingpartnerapi-eu.amazon.com` |
| Amazon.com | US | `ATVPDKIKX0DER` | `sellingpartnerapi-na.amazon.com` |
| Amazon.co.uk | UK | `A1F83G8C2ARO7P` | `sellingpartnerapi-eu.amazon.com` |

---

## Part 10: Rate Limits & Error Handling

### Data Kiosk Rate Limits

| Operation | Rate Limit | Burst |
|---|---|---|
| createQuery | 0.0167 req/sec | 1 request |
| getQuery | 2 req/sec | 2 requests |
| getDocument | 0.0167 req/sec | 1 request |

This means **1 query creation per minute maximum**. For SADDL's daily lookback of 5 dates, spread query submissions 60 seconds apart.

### Retry Logic

```python
import time
import functools

def retry_with_backoff(max_retries=3, base_delay=30):
    """Decorator for SP-API calls with exponential backoff on throttling."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.HTTPError as e:
                    if e.response.status_code == 429:  # Throttled
                        delay = base_delay * (2 ** attempt)
                        print(f"Throttled. Retrying in {delay}s...")
                        time.sleep(delay)
                    elif e.response.status_code in (500, 503):  # Server error
                        delay = base_delay * (2 ** attempt)
                        print(f"Server error {e.response.status_code}. Retry in {delay}s...")
                        time.sleep(delay)
                    else:
                        raise  # Don't retry 4xx (bad request, auth issues)
            raise RuntimeError(f"Max retries exceeded for {func.__name__}")
        return wrapper
    return decorator

# Usage
@retry_with_backoff(max_retries=3, base_delay=30)
def create_data_kiosk_query_safe(access_token, query_body):
    return create_data_kiosk_query(access_token, query_body)
```

---

## Part 11: Integration Points with SADDL DAO Module

Once the pipeline is running, this is how the data flows into the existing SADDL spec:

```
SP-API Daily Pull (06:00 UTC)
        │
        ▼
sc_sales_traffic (raw table)
        │
        ├──► sc_account_totals (daily rollup)
        │
        ├──► v_daily_organic_share (join with ad console data)
        │
        └──► v_osi_index (rolling OSI calculation)
                │
                ▼
        Index Computation Engine
                │
                ├──► OSI → CDI input (weight 0.20)
                ├──► unit_session_percentage → CRI supplement
                └──► buy_box_percentage → listing health flag
                        │
                        ▼
                Composite Demand Index (CDI)
                        │
                        ▼
                Spend Envelope Engine
```

### Required Join: Seller Central + Ad Console

The critical computation — Organic Share — requires both data sources to be available for the same date. The join key is `(report_date, marketplace_id)`.

Ensure the ad console pipeline (already in SADDL) populates `ad_console_daily_totals` with:
- `total_spend` (total ad spend for the day)
- `attributed_sales_14d` (14-day attributed ad sales)

These are already in the existing SADDL data model from the Amazon Advertising API pipeline.

---

## Quick Start Checklist

- [ ] Professional Seller account confirmed (Zenarise — done)
- [ ] Developer Central account created (Seller Central → Apps & Services → Develop Apps)
- [ ] Developer profile submitted with Selling Partner Insights + Analytics roles
- [ ] AWS account created, IAM user `saddl-spapi-user` created with Access Keys
- [ ] SP-API application registered with IAM ARN
- [ ] Self-authorization completed — refresh token stored in secrets manager
- [ ] Marketplace ID confirmed as `A2VIGQ35RCS4UG` (UAE)
- [ ] `run_daily_pull()` tested against last 7 days of data
- [ ] `sc_sales_traffic` table populated with Zenarise ASIN-level data
- [ ] `v_osi_index` view returning values (requires 28+ days of data for baseline)
- [ ] CDI computation updated to ingest OSI from new view
- [ ] Daily cron job / Celery task active

---

*For agency client onboarding (multi-tenant), initiate Public Developer registration separately — that process runs in parallel with Phase 1 and typically takes 4–6 weeks for Amazon approval.*
