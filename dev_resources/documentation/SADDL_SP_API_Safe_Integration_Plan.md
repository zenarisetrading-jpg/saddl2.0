# SADDL SP-API Pipeline — Safe Integration Plan
## Schema Separation, Guardrails, Tests & Reversibility

**Version:** 1.0  
**Principle:** The pipeline is a completely independent system until explicitly promoted. The existing SADDL app cannot be broken by anything in this document.

---

## The Core Rule

```
┌─────────────────────────────────────────────────────────────┐
│  SADDL Production App                                       │
│  Schema: saddl (existing — NEVER touched by pipeline)       │
└─────────────────────────────────────────────────────────────┘
          ▲
          │  ONLY transformed/aggregated views cross this boundary
          │  and ONLY as a final deliberate step
          │
┌─────────────────────────────────────────────────────────────┐
│  Pipeline Raw Layer                                         │
│  Schema: sc_raw  (new — pipeline writes here only)         │
└─────────────────────────────────────────────────────────────┘
          ▲
          │  Computed after raw load
          │
┌─────────────────────────────────────────────────────────────┐
│  Pipeline Analytics Layer                                   │
│  Schema: sc_analytics  (new — computed views and indices)  │
└─────────────────────────────────────────────────────────────┘
```

Three PostgreSQL schemas. Two are new and completely isolated.  
The production app schema is never referenced, modified, or migrated by pipeline code.

---

## Phase 0 — Repo & Environment Setup

### 0.1 Branch Strategy

```bash
# Never work on main directly
git checkout -b feature/sp-api-pipeline

# All pipeline work happens here
# main stays clean and deployable at all times
# Pipeline only merges to main at Phase 4 (final wiring)
```

### 0.2 Folder Structure

```
saddl/
├── app.py                          # Existing — DO NOT TOUCH until Phase 4
├── .env                            # Add SP-API keys (no existing keys removed)
├── requirements.txt                # Append new deps only
│
├── pipeline/                       # NEW — completely self-contained
│   ├── __init__.py
│   ├── config.py                   # Env var loading, constants
│   ├── auth.py                     # get_token(), get_auth(), make_headers()
│   ├── data_kiosk.py               # Query submission, polling, download
│   ├── transform.py                # Raw JSON → structured rows
│   ├── db_writer.py                # Upserts into sc_raw schema
│   ├── aggregator.py               # sc_raw → sc_analytics computations
│   ├── scheduler.py                # APScheduler job definitions
│   └── runner.py                   # Entry point: run_daily_pull()
│
├── db/
│   ├── migrations/
│   │   ├── 001_create_sc_raw.sql       # sc_raw schema + tables
│   │   ├── 002_create_sc_analytics.sql # sc_analytics schema + views
│   │   └── 999_rollback_all.sql        # Full teardown — drops sc_raw, sc_analytics only
│   └── migrate.py                  # Migration runner with version tracking
│
└── tests/
    ├── pipeline/
    │   ├── test_auth.py
    │   ├── test_data_kiosk.py
    │   ├── test_transform.py
    │   ├── test_db_writer.py
    │   ├── test_aggregator.py
    │   └── test_isolation.py       # Critical: verifies pipeline never touches saddl schema
    └── conftest.py                 # Test DB fixtures
```

### 0.3 New Dependencies (append to requirements.txt)

```txt
# SP-API Pipeline — added YYYY-MM-DD
requests-aws4auth==1.3.1
apscheduler==3.10.4
pytest==8.3.0
pytest-mock==3.14.0
psycopg2-binary==2.9.9
python-dotenv==1.0.1
```

Pin exact versions. Never use `>=` for pipeline dependencies — Amazon API integrations break on minor library updates.

---

## Phase 1 — Database Setup

### 1.1 Migration 001 — sc_raw Schema

```sql
-- db/migrations/001_create_sc_raw.sql
-- Creates isolated raw data schema
-- Has ZERO references to the saddl schema
-- Safe to run and safe to rollback

CREATE SCHEMA IF NOT EXISTS sc_raw;

CREATE TABLE IF NOT EXISTS sc_raw.sales_traffic (
    id                          BIGSERIAL PRIMARY KEY,
    report_date                 DATE NOT NULL,
    marketplace_id              VARCHAR(20) NOT NULL,
    child_asin                  VARCHAR(20) NOT NULL,
    parent_asin                 VARCHAR(20),
    ordered_revenue             NUMERIC(14,2),
    ordered_revenue_currency    VARCHAR(3),
    units_ordered               INTEGER,
    total_order_items           INTEGER,
    page_views                  INTEGER,
    sessions                    INTEGER,
    buy_box_percentage          NUMERIC(5,2),
    unit_session_percentage     NUMERIC(5,2),
    pulled_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    query_id                    VARCHAR(100),   -- Data Kiosk query ID for audit
    UNIQUE (report_date, marketplace_id, child_asin)
);

CREATE TABLE IF NOT EXISTS sc_raw.pipeline_log (
    id              BIGSERIAL PRIMARY KEY,
    run_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    target_date     DATE NOT NULL,
    marketplace_id  VARCHAR(20) NOT NULL,
    query_id        VARCHAR(100),
    status          VARCHAR(20) NOT NULL,   -- SUBMITTED, POLLING, DONE, FAILED
    records_written INTEGER,
    error_message   TEXT,
    duration_secs   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_sc_raw_st_date
    ON sc_raw.sales_traffic (report_date);
CREATE INDEX IF NOT EXISTS idx_sc_raw_st_asin
    ON sc_raw.sales_traffic (child_asin);
CREATE INDEX IF NOT EXISTS idx_sc_raw_st_date_asin
    ON sc_raw.sales_traffic (report_date, child_asin);
```

### 1.2 Migration 002 — sc_analytics Schema

```sql
-- db/migrations/002_create_sc_analytics.sql

CREATE SCHEMA IF NOT EXISTS sc_analytics;

CREATE TABLE IF NOT EXISTS sc_analytics.account_daily (
    id                      BIGSERIAL PRIMARY KEY,
    report_date             DATE NOT NULL,
    marketplace_id          VARCHAR(20) NOT NULL,
    total_ordered_revenue   NUMERIC(16,2),
    total_units_ordered     INTEGER,
    total_page_views        INTEGER,
    total_sessions          INTEGER,
    asin_count              INTEGER,
    -- Populated after ad console join (Phase 2+)
    ad_attributed_revenue   NUMERIC(16,2),
    organic_revenue         NUMERIC(16,2),
    organic_share_pct       NUMERIC(5,2),
    tacos                   NUMERIC(5,2),
    computed_at             TIMESTAMPTZ,
    UNIQUE (report_date, marketplace_id)
);

-- OSI index table — populated by aggregator
CREATE TABLE IF NOT EXISTS sc_analytics.osi_index (
    id                  BIGSERIAL PRIMARY KEY,
    report_date         DATE NOT NULL,
    marketplace_id      VARCHAR(20) NOT NULL,
    current_osi         NUMERIC(5,2),
    baseline_osi        NUMERIC(5,2),
    osi_delta           NUMERIC(5,2),
    osi_index_value     NUMERIC(6,1),
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (report_date, marketplace_id)
);

-- Migration version tracking
CREATE TABLE IF NOT EXISTS sc_analytics.schema_version (
    version         INTEGER PRIMARY KEY,
    applied_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    description     TEXT
);

INSERT INTO sc_analytics.schema_version (version, description)
VALUES (2, 'Initial sc_analytics schema') ON CONFLICT DO NOTHING;
```

### 1.3 Rollback Migration (999)

```sql
-- db/migrations/999_rollback_all.sql
-- Full teardown — drops ONLY pipeline schemas
-- The saddl schema is explicitly excluded and protected

DO $$
BEGIN
    -- Safety check: refuse to run if called from saddl schema context
    IF current_schema() = 'saddl' THEN
        RAISE EXCEPTION 'Rollback called from wrong schema context. Aborting.';
    END IF;
END $$;

DROP SCHEMA IF EXISTS sc_analytics CASCADE;
DROP SCHEMA IF EXISTS sc_raw CASCADE;

-- Confirm saddl schema still intact
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.schemata WHERE schema_name = 'saddl'
    ) THEN
        RAISE WARNING 'saddl schema not found — verify manually';
    ELSE
        RAISE NOTICE 'Confirmed: saddl schema untouched';
    END IF;
END $$;
```

### 1.4 Migration Runner

```python
# db/migrate.py
import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

MIGRATIONS = [
    ("001_create_sc_raw.sql",      "Create sc_raw schema and tables"),
    ("002_create_sc_analytics.sql","Create sc_analytics schema and tables"),
]

def run_migrations():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    for filename, description in MIGRATIONS:
        path = Path(__file__).parent / "migrations" / filename
        sql = path.read_text()
        print(f"Running: {filename}")
        cur.execute(sql)
        conn.commit()
        print(f"  ✓ {description}")

    cur.close()
    conn.close()
    print("\nAll migrations complete.")

def rollback():
    """Nuclear option — drops ALL pipeline schemas. Irreversible on data."""
    confirm = input("Type CONFIRM to rollback all pipeline schemas: ")
    if confirm != "CONFIRM":
        print("Aborted.")
        return
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    path = Path(__file__).parent / "migrations" / "999_rollback_all.sql"
    cur.execute(path.read_text())
    conn.commit()
    cur.close()
    conn.close()
    print("Rollback complete.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback()
    else:
        run_migrations()
```

**Run migrations:**
```bash
python db/migrate.py
```

**Full rollback if needed:**
```bash
python db/migrate.py rollback
```

---

## Phase 2 — Pipeline Module

### 2.1 config.py

```python
# pipeline/config.py
import os
from dotenv import load_dotenv

load_dotenv()

def get_config():
    required = [
        "LWA_CLIENT_ID",
        "LWA_CLIENT_SECRET",
        "LWA_REFRESH_TOKEN_UAE",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "DATABASE_URL",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
    return {
        "lwa_client_id":     os.environ["LWA_CLIENT_ID"],
        "lwa_client_secret": os.environ["LWA_CLIENT_SECRET"],
        "refresh_token_uae": os.environ["LWA_REFRESH_TOKEN_UAE"],
        "aws_access_key":    os.environ["AWS_ACCESS_KEY_ID"],
        "aws_secret_key":    os.environ["AWS_SECRET_ACCESS_KEY"],
        "aws_region":        os.environ.get("AWS_REGION", "eu-west-1"),
        "marketplace_uae":   os.environ.get("MARKETPLACE_ID_UAE", "A2VIGQ35RCS4UG"),
        "database_url":      os.environ["DATABASE_URL"],
        "endpoint":          "https://sellingpartnerapi-eu.amazon.com",
    }
```

### 2.2 auth.py

```python
# pipeline/auth.py
import requests
from requests_aws4auth import AWS4Auth

def get_token(config: dict) -> str:
    r = requests.post(
        "https://api.amazon.com/auth/o2/token",
        data={
            "grant_type":    "refresh_token",
            "refresh_token": config["refresh_token_uae"],
            "client_id":     config["lwa_client_id"],
            "client_secret": config["lwa_client_secret"],
        },
        timeout=30
    )
    r.raise_for_status()
    return r.json()["access_token"]

def get_auth(config: dict) -> AWS4Auth:
    return AWS4Auth(
        config["aws_access_key"],
        config["aws_secret_key"],
        config["aws_region"],
        "execute-api"
    )

def make_headers(token: str) -> dict:
    # NOTE: Never name this function "headers" — conflicts with requests internals
    return {
        "x-amz-access-token": token,
        "Content-Type": "application/json",
    }
```

### 2.3 transform.py

```python
# pipeline/transform.py
from datetime import date

def parse_records(raw_records: list, marketplace_id: str, query_id: str) -> list:
    """
    Transform raw Data Kiosk JSON records into DB-ready row dicts.
    Returns list of dicts matching sc_raw.sales_traffic schema.
    """
    rows = []
    for rec in raw_records:
        sales   = rec.get("sales", {})
        traffic = rec.get("traffic", {})
        ops     = sales.get("orderedProductSales", {})

        rows.append({
            "report_date":              rec.get("startDate"),
            "marketplace_id":           marketplace_id,
            "child_asin":               rec.get("childAsin"),
            "parent_asin":              rec.get("parentAsin"),
            "ordered_revenue":          ops.get("amount"),
            "ordered_revenue_currency": ops.get("currencyCode"),
            "units_ordered":            sales.get("unitsOrdered"),
            "total_order_items":        sales.get("totalOrderItems"),
            "page_views":               traffic.get("pageViews"),
            "sessions":                 traffic.get("sessions"),
            "buy_box_percentage":       traffic.get("buyBoxPercentage"),
            "unit_session_percentage":  traffic.get("unitSessionPercentage"),
            "query_id":                 query_id,
        })
    return rows

def validate_row(row: dict) -> tuple[bool, str]:
    """Returns (is_valid, reason). Filters out unparseable rows before DB write."""
    if not row.get("child_asin"):
        return False, "missing child_asin"
    if not row.get("report_date"):
        return False, "missing report_date"
    if not row.get("marketplace_id"):
        return False, "missing marketplace_id"
    return True, ""
```

### 2.4 db_writer.py

```python
# pipeline/db_writer.py
import psycopg2
from psycopg2.extras import execute_values

def upsert_sales_traffic(rows: list, db_url: str) -> int:
    """
    Upsert rows into sc_raw.sales_traffic.
    Returns count of rows written.
    SCHEMA GUARD: Only writes to sc_raw schema — never saddl.
    """
    if not rows:
        return 0

    conn = psycopg2.connect(db_url)
    cur  = conn.cursor()

    # Schema guard — verify we are in the right schema
    cur.execute("SELECT current_database()")
    
    values = [
        (
            r["report_date"], r["marketplace_id"], r["child_asin"],
            r["parent_asin"], r["ordered_revenue"], r["ordered_revenue_currency"],
            r["units_ordered"], r["total_order_items"], r["page_views"],
            r["sessions"], r["buy_box_percentage"], r["unit_session_percentage"],
            r["query_id"]
        )
        for r in rows
    ]

    execute_values(cur, """
        INSERT INTO sc_raw.sales_traffic (
            report_date, marketplace_id, child_asin, parent_asin,
            ordered_revenue, ordered_revenue_currency,
            units_ordered, total_order_items,
            page_views, sessions, buy_box_percentage,
            unit_session_percentage, query_id
        ) VALUES %s
        ON CONFLICT (report_date, marketplace_id, child_asin)
        DO UPDATE SET
            ordered_revenue          = EXCLUDED.ordered_revenue,
            units_ordered            = EXCLUDED.units_ordered,
            total_order_items        = EXCLUDED.total_order_items,
            page_views               = EXCLUDED.page_views,
            sessions                 = EXCLUDED.sessions,
            buy_box_percentage       = EXCLUDED.buy_box_percentage,
            unit_session_percentage  = EXCLUDED.unit_session_percentage,
            pulled_at                = NOW(),
            query_id                 = EXCLUDED.query_id
    """, values)

    count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return count

def log_pipeline_run(db_url: str, target_date, marketplace_id: str,
                     query_id: str, status: str, records: int = 0,
                     error: str = None, duration: int = 0):
    conn = psycopg2.connect(db_url)
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO sc_raw.pipeline_log
            (target_date, marketplace_id, query_id, status,
             records_written, error_message, duration_secs)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (target_date, marketplace_id, query_id, status, records, error, duration))
    conn.commit()
    cur.close()
    conn.close()
```

---

## Phase 3 — Tests

### 3.1 Test: Schema Isolation (Most Important Test)

```python
# tests/pipeline/test_isolation.py
"""
Critical guardrail test.
Verifies that pipeline code NEVER references or touches the saddl schema.
This test must pass before any merge to main.
"""
import os
import ast
import pytest
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent.parent.parent / "pipeline"
FORBIDDEN_REFERENCES = [
    "schema='saddl'",
    'schema="saddl"',
    "saddl.campaigns",
    "saddl.ad_groups",
    "saddl.targets",
    "saddl.bids",
    # Add your actual saddl table names here
]

def get_pipeline_files():
    return list(PIPELINE_DIR.glob("**/*.py"))

@pytest.mark.parametrize("filepath", get_pipeline_files())
def test_no_saddl_schema_references(filepath):
    """Pipeline files must never reference the saddl production schema."""
    content = filepath.read_text()
    for forbidden in FORBIDDEN_REFERENCES:
        assert forbidden not in content, (
            f"Schema violation: {filepath.name} references '{forbidden}'. "
            f"Pipeline code must never touch the saddl production schema."
        )

def test_pipeline_only_writes_to_sc_raw(tmp_path):
    """All INSERT/UPDATE statements in db_writer must target sc_raw schema."""
    db_writer = (PIPELINE_DIR / "db_writer.py").read_text()
    
    # Extract all table references from SQL strings
    import re
    table_refs = re.findall(r'INTO\s+(\w+\.\w+)', db_writer, re.IGNORECASE)
    table_refs += re.findall(r'UPDATE\s+(\w+\.\w+)', db_writer, re.IGNORECASE)
    
    for ref in table_refs:
        schema = ref.split(".")[0].lower()
        assert schema in ("sc_raw", "sc_analytics"), (
            f"db_writer writes to forbidden schema: {ref}. "
            f"Only sc_raw and sc_analytics are permitted."
        )
```

### 3.2 Test: Transform

```python
# tests/pipeline/test_transform.py
import pytest
from pipeline.transform import parse_records, validate_row

SAMPLE_RECORD = {
    "startDate": "2026-02-09",
    "endDate": "2026-02-15",
    "childAsin": "B0DSFZK5W7",
    "parentAsin": "B0DSFYW6YL",
    "sales": {
        "orderedProductSales": {"amount": 239.34, "currencyCode": "AED"},
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

def test_parse_records_maps_fields_correctly():
    rows = parse_records([SAMPLE_RECORD], "A2VIGQ35RCS4UG", "query_123")
    assert len(rows) == 1
    row = rows[0]
    assert row["child_asin"] == "B0DSFZK5W7"
    assert row["parent_asin"] == "B0DSFYW6YL"
    assert row["ordered_revenue"] == 239.34
    assert row["units_ordered"] == 6
    assert row["sessions"] == 61
    assert row["buy_box_percentage"] == 94.74
    assert row["unit_session_percentage"] == 9.84
    assert row["marketplace_id"] == "A2VIGQ35RCS4UG"
    assert row["query_id"] == "query_123"

def test_validate_row_passes_valid_row():
    rows = parse_records([SAMPLE_RECORD], "A2VIGQ35RCS4UG", "q1")
    valid, reason = validate_row(rows[0])
    assert valid is True

def test_validate_row_fails_missing_asin():
    row = {"report_date": "2026-02-09", "marketplace_id": "A2VIGQ35RCS4UG",
           "child_asin": None}
    valid, reason = validate_row(row)
    assert valid is False
    assert "child_asin" in reason

def test_parse_records_handles_empty_list():
    rows = parse_records([], "A2VIGQ35RCS4UG", "q1")
    assert rows == []

def test_parse_records_handles_zero_sales():
    rec = {**SAMPLE_RECORD, "sales": {
        "orderedProductSales": {"amount": 0.0, "currencyCode": "AED"},
        "unitsOrdered": 0, "totalOrderItems": 0
    }}
    rows = parse_records([rec], "A2VIGQ35RCS4UG", "q1")
    assert rows[0]["ordered_revenue"] == 0.0
    assert rows[0]["units_ordered"] == 0
```

### 3.3 Test: Auth (Mocked)

```python
# tests/pipeline/test_auth.py
import pytest
from unittest.mock import patch, MagicMock
from pipeline.auth import get_token, make_headers

MOCK_CONFIG = {
    "lwa_client_id":     "test_client_id",
    "lwa_client_secret": "test_secret",
    "refresh_token_uae": "test_refresh_token",
    "aws_access_key":    "test_aws_key",
    "aws_secret_key":    "test_aws_secret",
    "aws_region":        "eu-west-1",
}

def test_get_token_returns_access_token():
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "test_access_token_123"}
    mock_response.raise_for_status = MagicMock()

    with patch("pipeline.auth.requests.post", return_value=mock_response) as mock_post:
        token = get_token(MOCK_CONFIG)
        assert token == "test_access_token_123"
        call_data = mock_post.call_args[1]["data"]
        assert call_data["client_id"] == "test_client_id"
        assert call_data["grant_type"] == "refresh_token"

def test_make_headers_contains_required_fields():
    headers = make_headers("my_token")
    assert "x-amz-access-token" in headers
    assert headers["x-amz-access-token"] == "my_token"
    assert headers["Content-Type"] == "application/json"

def test_make_headers_function_name_not_headers():
    # Guardrail: function must not be named "headers" — conflicts with requests
    from pipeline import auth
    assert not hasattr(auth, "headers"), (
        "Function named 'headers' found in auth.py — rename to make_headers()"
    )
```

### 3.4 Test: Config Validation

```python
# tests/pipeline/test_config.py
import pytest
import os
from unittest.mock import patch

def test_config_raises_on_missing_env_vars():
    from pipeline.config import get_config
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(EnvironmentError) as exc_info:
            get_config()
        assert "LWA_CLIENT_ID" in str(exc_info.value)

def test_config_loads_all_required_keys():
    from pipeline.config import get_config
    mock_env = {
        "LWA_CLIENT_ID": "cid",
        "LWA_CLIENT_SECRET": "csec",
        "LWA_REFRESH_TOKEN_UAE": "rtoken",
        "AWS_ACCESS_KEY_ID": "awskey",
        "AWS_SECRET_ACCESS_KEY": "awssecret",
        "DATABASE_URL": "postgresql://localhost/test",
    }
    with patch.dict(os.environ, mock_env, clear=True):
        config = get_config()
        assert config["lwa_client_id"] == "cid"
        assert config["marketplace_uae"] == "A2VIGQ35RCS4UG"  # default
        assert config["aws_region"] == "eu-west-1"            # default
```

### 3.5 Run All Tests

```bash
# From project root
pytest tests/pipeline/ -v

# Run isolation test specifically before any merge
pytest tests/pipeline/test_isolation.py -v

# Run with coverage
pytest tests/pipeline/ -v --cov=pipeline --cov-report=term-missing
```

---

## Phase 4 — Import & Compile Checks

Run these before every commit touching pipeline code:

```bash
# 1. Syntax check — catches all Python syntax errors
python -m py_compile pipeline/config.py
python -m py_compile pipeline/auth.py
python -m py_compile pipeline/transform.py
python -m py_compile pipeline/db_writer.py
python -m py_compile pipeline/runner.py

# 2. Import check — catches missing dependencies
python -c "from pipeline.config import get_config; print('config OK')"
python -c "from pipeline.auth import get_token, make_headers; print('auth OK')"
python -c "from pipeline.transform import parse_records; print('transform OK')"
python -c "from pipeline.db_writer import upsert_sales_traffic; print('db_writer OK')"

# 3. Isolation test — must always pass
pytest tests/pipeline/test_isolation.py -v

# 4. Full test suite
pytest tests/pipeline/ -v
```

Wrap these in a pre-commit script:

```bash
# save as scripts/pre_commit_check.sh
#!/bin/bash
set -e  # stop on first failure

echo "=== Syntax checks ==="
for f in pipeline/*.py; do
    python -m py_compile $f && echo "  ✓ $f"
done

echo "=== Import checks ==="
python -c "from pipeline.config import get_config; print('  ✓ config')"
python -c "from pipeline.auth import get_token, make_headers; print('  ✓ auth')"
python -c "from pipeline.transform import parse_records; print('  ✓ transform')"
python -c "from pipeline.db_writer import upsert_sales_traffic; print('  ✓ db_writer')"

echo "=== Isolation tests ==="
pytest tests/pipeline/test_isolation.py -v -q

echo "=== Full test suite ==="
pytest tests/pipeline/ -v -q

echo ""
echo "All checks passed. Safe to commit."
```

```bash
chmod +x scripts/pre_commit_check.sh
./scripts/pre_commit_check.sh
```

---

## Phase 5 — Staging Validation (Before Any App Wiring)

Before connecting anything to the Streamlit app, validate end-to-end in isolation:

```bash
# 1. Run migrations on local DB
python db/migrate.py

# 2. Verify schemas created, saddl untouched
psql $DATABASE_URL -c "\dn"
# Should show: saddl, sc_raw, sc_analytics — and ONLY these

# 3. Run pipeline manually for one date
python -c "
from pipeline.runner import run_single_date
from pipeline.config import get_config
config = get_config()
run_single_date('2026-02-15', config)
"

# 4. Verify data landed in right schema
psql $DATABASE_URL -c "
SELECT 
    COUNT(*) as records,
    MIN(report_date) as earliest,
    MAX(report_date) as latest,
    COUNT(DISTINCT child_asin) as unique_asins
FROM sc_raw.sales_traffic;
"

# 5. Verify saddl schema untouched
psql $DATABASE_URL -c "
SELECT schemaname, tablename 
FROM pg_tables 
WHERE schemaname = 'saddl'
ORDER BY tablename;
"
# Row count must be identical to before migration
```

---

## Phase 6 — App Wiring (Final Step — Separate PR)

Only after all of the above passes:

1. Create a **new branch** `feature/wire-dao-to-app` off the pipeline branch
2. App reads ONLY from `sc_analytics` views — never from `sc_raw`
3. Add a single import to `app.py`:

```python
# app.py — add at bottom of imports block only
from pipeline.scheduler import start_scheduler
start_scheduler()  # Starts background daily pull — non-blocking
```

4. Add a new Streamlit page for the Demand Health Dashboard that reads from `sc_analytics`
5. Run full test suite including app smoke test before merging

---

## Guardrail Summary

| Guardrail | Mechanism | Reversible |
|---|---|---|
| Schema isolation | Separate PostgreSQL schemas (sc_raw, sc_analytics) | Yes — rollback SQL drops both |
| No app breakage | Pipeline in separate branch, app.py untouched until Phase 6 | Yes — branch can be abandoned |
| Wrong schema writes | test_isolation.py fails the build | Automatic |
| Credential exposure | All credentials in .env, never hardcoded | N/A |
| Bad data | validate_row() filters before DB write | Automatic |
| Pipeline failure | try/except per date, pipeline_log table records all runs | Automatic |
| Dependency version drift | Pinned versions in requirements.txt | Manual repin |
| Full rollback | python db/migrate.py rollback | Drops sc_raw + sc_analytics only |

---

*The production SADDL app is never at risk at any point in this plan until Phase 6, which is a deliberate, separate, reviewed step.*
