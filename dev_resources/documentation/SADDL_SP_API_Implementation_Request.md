# SADDL AdPulse - SP-API Seller Central Pipeline Implementation Request

Build the SP-API Seller Central data pipeline for SADDL AdPulse.

CONFIRMED WORKING AUTH PATTERN:
- LWA token: POST https://api.amazon.com/auth/o2/token with grant_type=refresh_token
- Request signing: AWS4Auth from requests_aws4auth library
- Endpoint: https://sellingpartnerapi-eu.amazon.com
- All credentials from .env

CONFIRMED WORKING QUERY PATTERN:
- API: Data Kiosk /dataKiosk/2023-11-15/queries
- Use aggregateBy: CHILD (not dateGranularity/asinGranularity — those are invalid)
- Document ID field in query status response: dataDocumentId (not documentId)
- Marketplace UAE: A2VIGQ35RCS4UG

CONFIRMED DATA SCHEMA (actual API response):
{
  "startDate": "2026-02-09",
  "endDate": "2026-02-15",
  "childAsin": "B0DSFZK5W7",
  "parentAsin": "B0DSFYW6YL",
  "sales": {
    "orderedProductSales": { "amount": 239.34, "currencyCode": "AED" },
    "unitsOrdered": 6,
    "totalOrderItems": 5
  },
  "traffic": {
    "pageViews": 80,
    "sessions": 61,
    "buyBoxPercentage": 94.74,
    "unitSessionPercentage": 9.84
  }
}

BUILD THIS FOLDER STRUCTURE inside the existing SADDL Streamlit project:

pipelines/
├── __init__.py
├── sp_api_client.py      # Auth helpers: get_token(), get_auth(), make_headers()
├── spapi_pipeline.py     # Full pipeline: submit query → poll → download → DB write
└── scheduler.py          # APScheduler daily job at 06:00 UTC

DATABASE (PostgreSQL):
Create and run migrations for these two tables:

1. sc_sales_traffic:
   - id BIGSERIAL PRIMARY KEY
   - report_date DATE NOT NULL
   - marketplace_id VARCHAR(20) NOT NULL
   - child_asin VARCHAR(20) NOT NULL
   - parent_asin VARCHAR(20)
   - ordered_revenue NUMERIC(14,2)
   - ordered_revenue_currency VARCHAR(3)
   - units_ordered INTEGER
   - total_order_items INTEGER
   - page_views INTEGER
   - sessions INTEGER
   - buy_box_percentage NUMERIC(5,2)
   - unit_session_percentage NUMERIC(5,2)
   - pulled_at TIMESTAMPTZ DEFAULT NOW()
   - UNIQUE (report_date, marketplace_id, child_asin)

2. sc_account_totals:
   - id BIGSERIAL PRIMARY KEY
   - report_date DATE NOT NULL
   - marketplace_id VARCHAR(20) NOT NULL
   - total_ordered_revenue NUMERIC(16,2)
   - total_units_ordered INTEGER
   - total_page_views INTEGER
   - total_sessions INTEGER
   - asin_count INTEGER
   - ad_attributed_revenue NUMERIC(16,2)
   - organic_revenue NUMERIC(16,2)
   - organic_share_pct NUMERIC(5,2)
   - tacos NUMERIC(5,2)
   - computed_at TIMESTAMPTZ
   - UNIQUE (report_date, marketplace_id)

PIPELINE LOGIC in spapi_pipeline.py:
- run_daily_pull() function that pulls these lookback dates: D-1, D-2, D-3, D-7, D-30
- For each date: submit Data Kiosk query → poll every 60s → download → upsert to sc_sales_traffic
- After each date loads: compute sc_account_totals rollup (sum across all ASINs for that date)
- Use INSERT ON CONFLICT UPDATE for all upserts
- Wrap each date in try/except — failure on one date should not stop others
- Query uses DAY granularity: set startDate = endDate = target_date

SCHEDULER in scheduler.py:
- APScheduler BackgroundScheduler
- Run run_daily_pull() daily at 06:00 UTC
- Start scheduler when Streamlit app launches (call start_scheduler() from app.py)

ENV VARIABLES to load:
LWA_CLIENT_ID
LWA_CLIENT_SECRET
LWA_REFRESH_TOKEN_UAE
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION=eu-west-1
MARKETPLACE_ID_UAE=A2VIGQ35RCS4UG
DATABASE_URL

IMPORTANT NOTES FOR CLAUDE CODE:
- Do not use the python-amazon-sp-api library — it has auth bugs with Python 3.14
- Use raw requests + requests_aws4auth only
- The function handling headers must NOT be named "headers" — name it make_headers()
  to avoid conflict with requests internals
- Data Kiosk query uses weekly aggregation when startDate=endDate —
  for daily granularity submit one query per day
- aggregateBy accepts: CHILD or PARENT
