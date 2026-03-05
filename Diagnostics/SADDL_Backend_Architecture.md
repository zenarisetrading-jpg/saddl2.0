# SADDL AdPulse — Backend Architecture
## Supabase/PostgreSQL Data Layer

**Version:** 1.0  
**Date:** February 2026  
**Stack:** Supabase (Postgres 15), Python 3.14, Streamlit

---

## 1. Architecture Overview

### 1.1 High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Streamlit Frontend (Python)                                    │
│  ├── pages/diagnostics.py                                       │
│  ├── pages/campaigns.py (existing)                              │
│  └── pages/targets.py (existing)                                │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   │ psycopg2 / SQLAlchemy
                   │ Connection Pooling (pgbouncer)
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  Supabase (Managed PostgreSQL 15)                               │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Schema: public (legacy SADDL tables)                      │ │
│  │  ├── raw_search_term_data                                  │ │
│  │  ├── target_stats                                          │ │
│  │  ├── advertised_product_ca...                              │ │
│  │  └── [12 other existing tables]                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Schema: sc_raw (Seller Central raw data)                  │ │
│  │  ├── sales_traffic          [330 rows → 8k+ after backfill]│ │
│  │  ├── bsr_history            [0 rows → populated Phase 1]   │ │
│  │  └── pipeline_log           [5 rows → audit trail]         │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Schema: sc_analytics (Computed views & indices)           │ │
│  │  ├── account_daily          [Aggregated daily metrics]     │ │
│  │  ├── osi_index              [Organic share index]          │ │
│  │  ├── bsr_trends             [VIEW: BSR rank changes]       │ │
│  │  ├── optimization_events    [Action log with validation]   │ │
│  │  ├── signal_demand_contraction     [VIEW]                  │ │
│  │  ├── signal_organic_decay          [VIEW]                  │ │
│  │  ├── signal_non_advertised_winners [VIEW]                  │ │
│  │  ├── signal_harvest_cannibalization [VIEW]                 │ │
│  │  ├── signal_over_negation          [VIEW]                  │ │
│  │  └── optimization_validation_summary [VIEW]                │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                   ▲
                   │
                   │ AWS4Auth + LWA tokens
                   │
┌─────────────────────────────────────────────────────────────────┐
│  External APIs                                                   │
│  ├── Amazon SP-API (Seller Central data)                        │
│  │   ├── Data Kiosk: Sales & Traffic                           │
│  │   └── Catalog Items: BSR                                     │
│  └── Amazon Ads API (future Phase 2)                            │
│      └── Sponsored Products: Advertised Product Report          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Schema Design Principles

### 2.1 Three-Schema Isolation

**Principle:** Separate concerns by schema to prevent accidental data corruption and enable clean rollbacks.

| Schema | Purpose | Write Access | Rollback Risk |
|---|---|---|---|
| `public` | Legacy SADDL ad console data | Existing pipelines only | HIGH — contains production campaign data |
| `sc_raw` | Amazon SP-API raw data | SP-API pipeline only | LOW — can be re-pulled from Amazon |
| `sc_analytics` | Computed metrics & signals | Aggregator & validation jobs | NONE — fully derived, can be recomputed |

**Security Rule:**  
No code in `pipeline/` directory can INSERT, UPDATE, or DELETE from `public` schema.  
Enforced by: `tests/pipeline/test_isolation.py`

### 2.2 Naming Conventions

**Tables:**
- Lowercase with underscores: `sales_traffic`, `optimization_events`
- Prefix indicates source: `sc_*` (Seller Central), `ad_*` (Ads API future)
- Suffix indicates type: `*_log` (audit), `*_history` (time series), `*_events` (transactional)

**Views:**
- Prefix indicates purpose: `signal_*` (opportunity detection), `v_*` (generic computed view)
- Descriptive: `optimization_validation_summary` not `opt_val_sum`

**Indexes:**
- Format: `idx_{table}_{columns}_{type}`
- Example: `idx_sales_traffic_date_asin` (composite), `idx_bsr_history_asin` (single column)

---

## 3. Connection Architecture

### 3.1 Pooler vs Direct Connection

Supabase provides two connection modes:

**Connection Pooler (Transaction Mode):**
```
postgresql://postgres:[PASSWORD]@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres
```
- **Use for:** Streamlit app queries (short-lived, high concurrency)
- **Max connections:** 200 (Nano compute tier)
- **Mode:** Transaction pooling (PgBouncer)
- **Limitations:** Cannot use `LISTEN/NOTIFY`, temp tables, or prepared statements across requests

**Direct Connection:**
```
postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres
```
- **Use for:** Pipeline jobs (long-running, low concurrency), schema migrations, administrative queries
- **Max connections:** 15 (Nano compute tier — shared with pooler)
- **Mode:** Direct PostgreSQL connection
- **Capabilities:** Full Postgres feature set

### 3.2 Connection Management

**Environment Variables:**
```bash
# .env
DATABASE_URL=postgresql://postgres:[PASSWORD]@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres
DATABASE_URL_DIRECT=postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres
```

**Python Connection Pattern:**

```python
# utils/db.py
import psycopg2
import os
from contextlib import contextmanager

def get_pooled_connection():
    """For Streamlit app queries — uses pooler."""
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        connect_timeout=10,
        options="-c statement_timeout=30000"  # 30s timeout
    )

def get_direct_connection():
    """For pipeline jobs and migrations — uses direct connection."""
    return psycopg2.connect(
        os.environ["DATABASE_URL_DIRECT"],
        connect_timeout=30
    )

@contextmanager
def get_db_cursor(direct: bool = False):
    """Context manager for safe connection handling."""
    conn = get_direct_connection() if direct else get_pooled_connection()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
```

**Usage:**

```python
# In Streamlit app (pooled)
from utils.db import get_db_cursor

with get_db_cursor() as cur:
    cur.execute("SELECT * FROM sc_analytics.account_daily WHERE report_date = %s", (date,))
    results = cur.fetchall()

# In pipeline (direct)
with get_db_cursor(direct=True) as cur:
    # Long-running backfill operation
    cur.execute("INSERT INTO sc_raw.sales_traffic ...")
```

---

## 4. Table Schemas (Detailed)

### 4.1 sc_raw.sales_traffic

**Purpose:** ASIN-level daily sales and traffic data from Amazon SP-API Data Kiosk.

```sql
CREATE TABLE sc_raw.sales_traffic (
    id                          BIGSERIAL PRIMARY KEY,
    report_date                 DATE NOT NULL,
    marketplace_id              VARCHAR(20) NOT NULL,
    child_asin                  VARCHAR(20) NOT NULL,
    parent_asin                 VARCHAR(20),
    
    -- Sales metrics
    ordered_revenue             NUMERIC(14,2),
    ordered_revenue_currency    VARCHAR(3),
    units_ordered               INTEGER,
    total_order_items           INTEGER,
    
    -- Traffic metrics
    page_views                  INTEGER,
    sessions                    INTEGER,
    buy_box_percentage          NUMERIC(5,2),
    unit_session_percentage     NUMERIC(5,2),  -- CVR
    
    -- Metadata
    pulled_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    query_id                    VARCHAR(100),  -- Data Kiosk query ID for audit
    
    UNIQUE (report_date, marketplace_id, child_asin)
);

-- Indexes for common query patterns
CREATE INDEX idx_sc_raw_st_date 
    ON sc_raw.sales_traffic (report_date);
    
CREATE INDEX idx_sc_raw_st_asin 
    ON sc_raw.sales_traffic (child_asin);
    
CREATE INDEX idx_sc_raw_st_date_asin 
    ON sc_raw.sales_traffic (report_date, child_asin);
    
CREATE INDEX idx_sc_raw_st_marketplace 
    ON sc_raw.sales_traffic (marketplace_id, report_date);
```

**Expected Volume:**
- ASINs per day: ~100-110 (Zenarise UAE)
- Retention: 2 years (730 days × 100 = 73,000 rows)
- Growth: ~3,000 rows/month
- Storage: ~15 MB at 2 years

**Query Patterns:**
```sql
-- Most common: fetch last N days for all ASINs
SELECT * FROM sc_raw.sales_traffic 
WHERE report_date >= CURRENT_DATE - 30
ORDER BY report_date DESC, ordered_revenue DESC;

-- ASIN trend: specific ASIN over time
SELECT report_date, sessions, ordered_revenue, unit_session_percentage
FROM sc_raw.sales_traffic
WHERE child_asin = 'B0DSFZK5W7'
  AND report_date >= CURRENT_DATE - 90
ORDER BY report_date;

-- Top performers: ASINs by revenue
SELECT child_asin, SUM(ordered_revenue) as total_revenue
FROM sc_raw.sales_traffic
WHERE report_date >= CURRENT_DATE - 30
GROUP BY child_asin
ORDER BY total_revenue DESC
LIMIT 20;
```

---

### 4.2 sc_raw.bsr_history

**Purpose:** Best Seller Rank tracking from Amazon Catalog Items API.

```sql
CREATE TABLE sc_raw.bsr_history (
    id                  BIGSERIAL PRIMARY KEY,
    report_date         DATE NOT NULL,
    marketplace_id      VARCHAR(20) NOT NULL,
    asin                VARCHAR(20) NOT NULL,
    
    -- BSR data
    category_name       VARCHAR(200),
    category_id         VARCHAR(100),
    rank                INTEGER,
    
    -- Metadata
    pulled_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (report_date, marketplace_id, asin, category_id)
);

CREATE INDEX idx_bsr_date_asin 
    ON sc_raw.bsr_history (report_date, asin);
    
CREATE INDEX idx_bsr_asin_category 
    ON sc_raw.bsr_history (asin, category_id, report_date);
```

**Expected Volume:**
- ASINs: 100
- Categories per ASIN: 1-3 (primary + subcategories)
- Daily rows: ~200
- Retention: 2 years (200 × 730 = 146,000 rows)
- Storage: ~8 MB at 2 years

**Query Pattern:**
```sql
-- Latest BSR for all ASINs (primary category only)
SELECT DISTINCT ON (asin)
    asin, category_name, rank, report_date
FROM sc_raw.bsr_history
WHERE marketplace_id = 'A2VIGQ35RCS4UG'
ORDER BY asin, report_date DESC;
```

---

### 4.3 sc_analytics.account_daily

**Purpose:** Daily rollup of account-level performance combining SC and ad data.

```sql
CREATE TABLE sc_analytics.account_daily (
    id                      BIGSERIAL PRIMARY KEY,
    report_date             DATE NOT NULL,
    marketplace_id          VARCHAR(20) NOT NULL,
    
    -- Seller Central totals
    total_ordered_revenue   NUMERIC(16,2),
    total_units_ordered     INTEGER,
    total_page_views        INTEGER,
    total_sessions          INTEGER,
    asin_count              INTEGER,
    
    -- Ad Console totals (joined)
    total_ad_spend          NUMERIC(16,2),
    ad_attributed_revenue   NUMERIC(16,2),
    
    -- Computed metrics
    organic_revenue         NUMERIC(16,2),
    organic_share_pct       NUMERIC(5,2),
    tacos                   NUMERIC(5,2),
    ad_roas                 NUMERIC(6,2),
    
    -- Metadata
    computed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE (report_date, marketplace_id)
);

CREATE INDEX idx_account_daily_date 
    ON sc_analytics.account_daily (report_date DESC);
```

**Computation Logic:**
```sql
-- Upserted daily by aggregator after sc_raw loads
INSERT INTO sc_analytics.account_daily (
    report_date, marketplace_id,
    total_ordered_revenue, total_units_ordered,
    total_page_views, total_sessions, asin_count,
    total_ad_spend, ad_attributed_revenue,
    organic_revenue, organic_share_pct, tacos, ad_roas
)
SELECT 
    st.report_date,
    st.marketplace_id,
    SUM(st.ordered_revenue) as total_ordered_revenue,
    SUM(st.units_ordered) as total_units_ordered,
    SUM(st.page_views) as total_page_views,
    SUM(st.sessions) as total_sessions,
    COUNT(DISTINCT st.child_asin) as asin_count,
    
    ad.total_ad_spend,
    ad.total_ad_sales * 0.90 as ad_attributed_revenue,  -- 10% overlap correction
    
    SUM(st.ordered_revenue) - (ad.total_ad_sales * 0.90) as organic_revenue,
    ((SUM(st.ordered_revenue) - (ad.total_ad_sales * 0.90)) / NULLIF(SUM(st.ordered_revenue), 0) * 100) as organic_share_pct,
    (ad.total_ad_spend / NULLIF(SUM(st.ordered_revenue), 0) * 100) as tacos,
    (ad.total_ad_sales / NULLIF(ad.total_ad_spend, 0)) as ad_roas
    
FROM sc_raw.sales_traffic st
LEFT JOIN (
    SELECT 
        report_date,
        SUM(spend) as total_ad_spend,
        SUM(sales) as total_ad_sales
    FROM public.raw_search_term_data
    WHERE client_id = 's2c_uae_test'
    GROUP BY report_date
) ad USING (report_date)
WHERE st.report_date = [target_date]
  AND st.marketplace_id = 'A2VIGQ35RCS4UG'
GROUP BY st.report_date, st.marketplace_id, ad.total_ad_spend, ad.total_ad_sales
ON CONFLICT (report_date, marketplace_id)
DO UPDATE SET
    total_ordered_revenue = EXCLUDED.total_ordered_revenue,
    -- ... all other columns
    computed_at = NOW();
```

---

### 4.4 sc_analytics.optimization_events

**Purpose:** Log every optimization action with before/after context for validation.

```sql
CREATE TABLE sc_analytics.optimization_events (
    id                      BIGSERIAL PRIMARY KEY,
    event_timestamp         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_date              DATE NOT NULL,
    event_type              VARCHAR(50) NOT NULL,
    
    entity_type             VARCHAR(20) NOT NULL,
    entity_id               VARCHAR(100),
    entity_name             TEXT,
    campaign_name           TEXT,
    ad_group_name           TEXT,
    
    -- What changed
    metric_changed          VARCHAR(50),
    old_value               NUMERIC,
    new_value               NUMERIC,
    change_amount           NUMERIC,
    change_pct              NUMERIC,
    
    -- Decision context
    decision_source         VARCHAR(50) NOT NULL,
    decision_reason         TEXT,
    
    -- 7-day baseline (before action)
    baseline_spend_7d       NUMERIC(14,2),
    baseline_sales_7d       NUMERIC(14,2),
    baseline_roas_7d        NUMERIC(6,2),
    account_roas_7d         NUMERIC(6,2),
    account_tacos_7d        NUMERIC(6,2),
    
    -- 7-day post-action (populated after validation)
    measured_at             TIMESTAMPTZ,
    post_spend_7d           NUMERIC(14,2),
    post_sales_7d           NUMERIC(14,2),
    post_roas_7d            NUMERIC(6,2),
    
    -- Validation results
    treated_roas_lift_pct   NUMERIC(6,2),
    account_roas_drift_pct  NUMERIC(6,2),
    optimization_impact_pts NUMERIC(6,2),
    validation_status       VARCHAR(20),
    
    user_id                 UUID,
    notes                   TEXT
);

CREATE INDEX idx_opt_events_date ON sc_analytics.optimization_events (event_date DESC);
CREATE INDEX idx_opt_events_validation ON sc_analytics.optimization_events (validation_status) 
    WHERE validation_status IS NOT NULL;
```

**Instrumentation Pattern:**

Every function that modifies bids/budgets/campaigns calls:

```python
from pipeline.event_logger import log_optimization_event

# Before making change
old_bid = get_current_bid(target_id)

# Make the change
update_bid(target_id, new_bid=2.50)

# Log it
event_id = log_optimization_event(
    event_type='BID_DECREASE',
    entity_type='TARGET',
    entity_id=target_id,
    entity_name='protein powder [exact]',
    metric_changed='bid',
    old_value=old_bid,
    new_value=2.50,
    decision_source='SADDL_AUTO_BID',
    decision_reason='ROAS below threshold for 3 consecutive days',
    campaign_name='Brand Defense Exact'
)
```

---

## 5. View Definitions (Signal Detection)

### 5.1 sc_analytics.bsr_trends

**Purpose:** Compute BSR rank changes and status for trend analysis.

```sql
CREATE VIEW sc_analytics.bsr_trends AS
SELECT 
    b.asin,
    b.report_date,
    b.category_name,
    b.category_id,
    b.rank as current_rank,
    
    -- Historical comparisons
    LAG(b.rank, 1) OVER w as rank_1d_ago,
    LAG(b.rank, 7) OVER w as rank_7d_ago,
    LAG(b.rank, 30) OVER w as rank_30d_ago,
    
    -- Deltas
    b.rank - LAG(b.rank, 7) OVER w as rank_change_7d,
    b.rank - LAG(b.rank, 30) OVER w as rank_change_30d,
    
    -- Status classification
    CASE 
        WHEN b.rank < LAG(b.rank, 7) OVER w THEN 'IMPROVING'
        WHEN b.rank > LAG(b.rank, 7) OVER w * 1.1 THEN 'DECLINING'
        ELSE 'STABLE'
    END as rank_status_7d,
    
    CASE 
        WHEN b.rank < LAG(b.rank, 30) OVER w THEN 'IMPROVING'
        WHEN b.rank > LAG(b.rank, 30) OVER w * 1.1 THEN 'DECLINING'
        ELSE 'STABLE'
    END as rank_status_30d
    
FROM sc_raw.bsr_history b
WHERE b.category_name IS NOT NULL  -- Primary category only
WINDOW w AS (PARTITION BY b.asin, b.category_id ORDER BY b.report_date);
```

**Usage:**
```sql
-- ASINs with declining BSR in last 7 days
SELECT asin, current_rank, rank_7d_ago, rank_change_7d
FROM sc_analytics.bsr_trends
WHERE report_date = CURRENT_DATE - 1
  AND rank_status_7d = 'DECLINING'
  AND current_rank > 10000  -- Meaningful decline threshold
ORDER BY rank_change_7d DESC;
```

---

### 5.2 Signal Views (Simplified — Full SQL in PRD)

All signal views follow pattern:

```sql
CREATE VIEW sc_analytics.signal_{name} AS
WITH [data_preparation] AS (...),
     [baseline_comparison] AS (...),
     [pattern_detection] AS (...)
SELECT 
    key_dimensions,
    metrics,
    CASE WHEN [pattern_conditions] THEN TRUE ELSE FALSE END as is_{signal_name}
FROM pattern_detection
ORDER BY report_date DESC;
```

**Five Signal Views:**
1. `signal_demand_contraction` — Market-wide CVR decline
2. `signal_organic_decay` — ASIN rank/traffic decline
3. `signal_non_advertised_winners` — High organic revenue, not advertised
4. `signal_harvest_cannibalization` — Harvest ROAS up, total revenue flat
5. `signal_over_negation` — Impressions down, quality metrics up

---

## 6. Performance Optimization

### 6.1 Index Strategy

**Principle:** Index for read patterns, not write patterns (writes are infrequent batch jobs).

**Date-based queries (most common):**
```sql
-- All tables with report_date get this index
CREATE INDEX idx_{table}_date ON {table} (report_date DESC);

-- Composite when filtering by date + another dimension
CREATE INDEX idx_sales_traffic_date_asin 
    ON sc_raw.sales_traffic (report_date, child_asin);
```

**ASIN lookups:**
```sql
CREATE INDEX idx_sales_traffic_asin 
    ON sc_raw.sales_traffic (child_asin);
    
CREATE INDEX idx_bsr_asin_category 
    ON sc_raw.bsr_history (asin, category_id, report_date);
```

**Partial indexes for filtered queries:**
```sql
-- Only index validated events (most query filtered by this)
CREATE INDEX idx_opt_events_validation 
    ON sc_analytics.optimization_events (validation_status) 
    WHERE validation_status IS NOT NULL;
```

### 6.2 Materialized Views (Future Optimization)

For computationally expensive views queried frequently:

```sql
CREATE MATERIALIZED VIEW sc_analytics.mv_daily_signals AS
SELECT * FROM sc_analytics.signal_demand_contraction
UNION ALL
SELECT * FROM sc_analytics.signal_organic_decay
-- ... etc
WITH DATA;

-- Refresh daily after aggregator runs
REFRESH MATERIALIZED VIEW CONCURRENTLY sc_analytics.mv_daily_signals;
```

**When to materialize:**
- View query time >2 seconds
- Queried >100 times/day
- Data freshness requirement is daily (not real-time)

---

## 7. Data Retention & Archival

### 7.1 Retention Policies

| Table | Retention | Archival Strategy |
|---|---|---|
| sc_raw.sales_traffic | 2 years | Archive to S3 after 2 years, keep aggregates |
| sc_raw.bsr_history | 2 years | Archive to S3 after 2 years |
| sc_analytics.account_daily | Indefinite | Permanent (small, valuable for trends) |
| sc_analytics.optimization_events | Indefinite | Permanent (audit trail) |
| public.raw_search_term_data | 1 year | User-controlled (existing) |

### 7.2 Archive Process (Future)

```sql
-- Monthly job: archive data older than 2 years
CREATE OR REPLACE FUNCTION archive_old_data() RETURNS void AS $$
BEGIN
    -- Export to S3 via pg_dump or Supabase Storage API
    -- Then delete from hot storage
    DELETE FROM sc_raw.sales_traffic 
    WHERE report_date < CURRENT_DATE - INTERVAL '2 years';
    
    DELETE FROM sc_raw.bsr_history
    WHERE report_date < CURRENT_DATE - INTERVAL '2 years';
END;
$$ LANGUAGE plpgsql;
```

---

## 8. Security & Access Control

### 8.1 Row Level Security (RLS)

**Principle:** Multi-tenant isolation when SADDL expands to agency model.

```sql
-- Enable RLS on all sc_* tables
ALTER TABLE sc_raw.sales_traffic ENABLE ROW LEVEL SECURITY;
ALTER TABLE sc_analytics.account_daily ENABLE ROW LEVEL SECURITY;

-- Policy: users only see their own marketplace data
CREATE POLICY tenant_isolation ON sc_raw.sales_traffic
    FOR SELECT
    USING (marketplace_id IN (
        SELECT marketplace_id FROM user_marketplaces 
        WHERE user_id = auth.uid()
    ));
```

**Current State:** RLS disabled (single-tenant Zenarise).  
**Future:** Enable when first agency client onboards.

### 8.2 Function Security

All functions that modify data:

```sql
CREATE OR REPLACE FUNCTION upsert_account_daily(...)
RETURNS void
SECURITY DEFINER  -- Runs with creator's privileges
SET search_path = sc_analytics, public
LANGUAGE plpgsql
AS $$ ... $$;
```

**SECURITY DEFINER** ensures consistent execution context regardless of caller.

---

## 9. Backup & Disaster Recovery

### 9.1 Supabase Automatic Backups

**Included in plan:**
- Daily automated backups (retained 7 days)
- Point-in-time recovery (PITR) available on Pro tier

**Manual backups before major changes:**
```bash
# Full database dump
pg_dump $DATABASE_URL_DIRECT > saddl_backup_$(date +%Y%m%d).sql

# Schema-only dump
pg_dump --schema-only $DATABASE_URL_DIRECT > saddl_schema_$(date +%Y%m%d).sql

# Specific schema dump
pg_dump --schema=sc_analytics $DATABASE_URL_DIRECT > sc_analytics_backup.sql
```

### 9.2 Recovery Procedures

**Scenario 1: Rollback pipeline schema changes**
```bash
# Already have: db/migrations/999_rollback_all.sql
python db/migrate.py rollback

# Verify public schema untouched
psql $DATABASE_URL_DIRECT -c "\dn"
```

**Scenario 2: Restore corrupted data**
```sql
-- Drop and restore from backup
DROP SCHEMA sc_raw CASCADE;
DROP SCHEMA sc_analytics CASCADE;

-- Restore from dump
psql $DATABASE_URL_DIRECT < sc_raw_backup.sql
```

**Scenario 3: Re-compute analytics from raw**
```python
# Aggregator is idempotent — can recompute any date range
from pipeline.aggregator import recompute_analytics

recompute_analytics(start_date='2025-11-01', end_date='2026-02-17')
```

---

## 10. Migration Management

### 10.1 Version Tracking

```sql
CREATE TABLE sc_analytics.schema_version (
    version         INTEGER PRIMARY KEY,
    applied_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    description     TEXT,
    script_name     VARCHAR(100)
);

INSERT INTO sc_analytics.schema_version (version, description, script_name)
VALUES 
    (1, 'Initial sc_raw schema', '001_create_sc_raw.sql'),
    (2, 'Initial sc_analytics schema', '002_create_sc_analytics.sql');
```

### 10.2 Migration Workflow

**Adding a new migration:**

```bash
# 1. Create migration file
touch db/migrations/003_add_bsr_history.sql

# 2. Write SQL
cat > db/migrations/003_add_bsr_history.sql << 'EOF'
CREATE TABLE sc_raw.bsr_history (...);
INSERT INTO sc_analytics.schema_version (version, description, script_name)
VALUES (3, 'Add BSR history table', '003_add_bsr_history.sql');
EOF

# 3. Add to migrate.py MIGRATIONS list
# 4. Run migration
python db/migrate.py

# 5. Verify
psql $DATABASE_URL_DIRECT -c "SELECT * FROM sc_analytics.schema_version ORDER BY version"
```

**Testing migrations:**

```bash
# Run on local copy first
psql $LOCAL_DATABASE_URL < db/migrations/003_add_bsr_history.sql

# If successful, run on production
python db/migrate.py
```

---

## 11. Monitoring & Observability

### 11.1 Query Performance

**Supabase Dashboard:**
- Database → Performance → Query Insights
- Shows slowest queries, index usage, table scans

**Manual inspection:**
```sql
-- Find slow queries
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 20;

-- Index usage
SELECT 
    schemaname, tablename, indexname,
    idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname IN ('sc_raw', 'sc_analytics')
ORDER BY idx_scan;
```

### 11.2 Pipeline Health

**sc_raw.pipeline_log tracks all runs:**

```sql
SELECT 
    target_date,
    status,
    records_written,
    duration_secs,
    error_message
FROM sc_raw.pipeline_log
WHERE status = 'FAILED'
ORDER BY run_at DESC
LIMIT 10;
```

**Monitoring queries:**

```python
# utils/monitoring.py
def check_pipeline_health():
    """Daily health check — runs in scheduler."""
    with get_db_cursor() as cur:
        # Check for failed runs in last 24h
        cur.execute("""
            SELECT COUNT(*) 
            FROM sc_raw.pipeline_log
            WHERE status = 'FAILED'
              AND run_at >= NOW() - INTERVAL '24 hours'
        """)
        failed = cur.fetchone()[0]
        
        if failed > 0:
            send_alert(f"Pipeline has {failed} failed runs in last 24h")
        
        # Check for stale data
        cur.execute("""
            SELECT MAX(report_date) 
            FROM sc_raw.sales_traffic
        """)
        latest = cur.fetchone()[0]
        
        if latest < datetime.now().date() - timedelta(days=2):
            send_alert(f"Sales data is stale. Latest: {latest}")
```

---

## 12. Future Enhancements

### 12.1 Real-Time Updates (Supabase Realtime)

**Use case:** Live dashboard updates when new data arrives.

```python
# Streamlit with Supabase Realtime
import streamlit as st
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def on_insert(payload):
    st.rerun()  # Refresh Streamlit app

# Subscribe to account_daily inserts
supabase.table('account_daily') \
    .on('INSERT', on_insert) \
    .subscribe()
```

**Status:** Not implemented yet. Requires Supabase client library integration.

### 12.2 Read Replicas

**Use case:** Separate analytics queries from transactional workload.

**Supabase Pro tier feature:**
- Create read replica in same region
- Point all Streamlit SELECT queries to replica
- Point all INSERT/UPDATE to primary

**Configuration:**
```bash
# .env
DATABASE_URL_PRIMARY=postgresql://...   # writes
DATABASE_URL_REPLICA=postgresql://...   # reads
```

### 12.3 Connection Pooling (PgBouncer Custom)

**Current:** Uses Supabase built-in pooler (transaction mode).

**Future:** Custom PgBouncer for session pooling if needed.

```ini
# pgbouncer.ini
[databases]
saddl = host=db.xxxx.supabase.co port=5432 dbname=postgres

[pgbouncer]
pool_mode = session
max_client_conn = 1000
default_pool_size = 20
```

---

*Backend architecture v1.0 — production-ready for Phase 1 implementation.*
