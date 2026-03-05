# SADDL Diagnostic Tool — Implementation Guardrails & Test Requirements
## Safe Build Protocol for Claude Code

**Version:** 1.0  
**Date:** February 2026  
**Purpose:** Ensure Claude Code builds diagnostic tool safely without breaking existing SADDL functionality

---

## 1. Critical Guardrails (DO NOT VIOLATE)

### 1.1 Database Write Boundaries

**ALLOWED:**
```sql
-- ✅ CREATE/ALTER/DROP in these schemas only
CREATE TABLE sc_raw.bsr_history (...);
CREATE VIEW sc_analytics.signal_demand_contraction AS ...;
ALTER TABLE sc_analytics.account_daily ADD COLUMN ...;
DROP TABLE sc_raw.temp_table;

-- ✅ INSERT/UPDATE/DELETE in these schemas only
INSERT INTO sc_raw.bsr_history (...) VALUES (...);
UPDATE sc_analytics.account_daily SET ... WHERE ...;
DELETE FROM sc_raw.sales_traffic WHERE report_date < '2024-01-01';
```

**FORBIDDEN:**
```sql
-- ❌ NEVER touch public schema tables
INSERT INTO public.raw_search_term_data ...;  -- FORBIDDEN
UPDATE public.target_stats ...;               -- FORBIDDEN
ALTER TABLE public.accounts ...;              -- FORBIDDEN

-- ❌ NEVER touch Impact Dashboard tables
INSERT INTO [impact_dashboard_table] ...;     -- FORBIDDEN
UPDATE [impact_validation_table] ...;         -- FORBIDDEN

-- ❌ NEVER create tables/views in public schema
CREATE TABLE public.anything ...;             -- FORBIDDEN
CREATE VIEW public.anything AS ...;           -- FORBIDDEN
```

**Enforcement:**
```python
# tests/test_schema_isolation.py
def test_no_public_schema_writes():
    """
    Scans all Python files in pipeline/ and pages/ directories.
    FAILS if any SQL statements write to public schema.
    """
    forbidden_patterns = [
        r'INSERT INTO public\.',
        r'UPDATE public\.',
        r'DELETE FROM public\.',
        r'CREATE TABLE public\.',
        r'ALTER TABLE public\.',
        r'DROP TABLE public\.',
    ]
    # ... scan all files, fail on match
```

---

### 1.2 File System Boundaries

**ALLOWED:**
```
saddl/
├── pipeline/
│   ├── bsr_pipeline.py          ✅ NEW - you create this
│   └── [other pipeline files]   ✅ EXISTING - don't modify
├── pages/
│   ├── diagnostics_*.py         ✅ NEW - you create these
│   └── [other pages]            ⚠️  EXISTING - don't modify
├── db/
│   ├── migrations/
│   │   ├── 003_*.sql            ✅ NEW - you create these
│   │   └── [001, 002]           ✅ EXISTING - already run, don't modify
│   └── migrate.py               ⚠️  EXISTING - only append to MIGRATIONS list
├── utils/
│   ├── diagnostics.py           ✅ NEW - you create this
│   ├── db.py                    ⚠️  EXISTING - only add functions, don't modify existing
│   └── [other utils]            ⚠️  EXISTING - don't modify
├── components/
│   ├── icon.py                  ✅ NEW - you create this
│   └── diagnostic_cards.py      ✅ NEW - you create this
└── tests/
    ├── test_schema_isolation.py ✅ NEW - you create this
    └── test_diagnostics.py      ✅ NEW - you create this
```

**FORBIDDEN:**
```
❌ Do NOT modify app.py (main Streamlit entry point)
❌ Do NOT modify existing pages/* files (campaigns, targets, etc.)
❌ Do NOT modify existing pipeline/* files (aggregator, runner, etc.)
❌ Do NOT delete any existing files
❌ Do NOT rename any existing files
```

---

### 1.3 Dependency Boundaries

**ALLOWED:**
```python
# ✅ Import from existing modules (read-only)
from utils.db import get_db_cursor
from pipeline.config import get_config

# ✅ Add NEW dependencies to requirements.txt
# (append only, don't modify existing versions)
```

**FORBIDDEN:**
```python
# ❌ Do NOT modify existing function signatures
# WRONG:
def get_db_cursor(direct: bool = False, timeout: int = 30):  # Changed signature
    ...

# RIGHT:
def get_db_cursor_with_timeout(timeout: int = 30):  # New function
    return get_db_cursor(...)
```

---

## 2. Test Requirements

### 2.1 Schema Isolation Tests (MUST PASS)

**File:** `tests/test_schema_isolation.py`

**Required Tests:**

```python
def test_no_public_schema_references_in_sql():
    """
    Scan all SQL in migrations/ and verify NO writes to public schema.
    Pass: No forbidden patterns found
    Fail: Any INSERT/UPDATE/DELETE/ALTER targeting public schema
    """
    
def test_no_impact_dashboard_writes():
    """
    Scan all Python files and verify NO writes to Impact Dashboard tables.
    Pass: No references to impact_dashboard_* tables in INSERT/UPDATE
    Fail: Any write operations to Impact Dashboard tables
    """
    
def test_all_new_tables_in_correct_schema():
    """
    Query information_schema and verify all new tables are in sc_raw or sc_analytics.
    Pass: All tables created after baseline are in allowed schemas
    Fail: Any new tables in public or other schemas
    """
    
def test_views_only_read_from_allowed_schemas():
    """
    Parse all view definitions and verify they only SELECT from:
    - sc_raw.*
    - sc_analytics.*
    - public.raw_search_term_data (read-only)
    - public.target_stats (read-only)
    Pass: All views only read from allowed sources
    Fail: Any view attempts to modify data or read from forbidden tables
    """
```

**Run Command:**
```bash
pytest tests/test_schema_isolation.py -v
```

**Acceptance Criteria:** ALL tests MUST pass before proceeding to next phase.

---

### 2.2 BSR Pipeline Tests

**File:** `tests/test_bsr_pipeline.py`

**Required Tests:**

```python
def test_bsr_api_auth():
    """
    Verify BSR pipeline can authenticate with SP-API.
    Pass: Token exchange succeeds
    Fail: 401/403 errors
    """

def test_bsr_single_asin_pull():
    """
    Pull BSR for one known ASIN and verify data structure.
    Pass: Returns salesRankings with category and rank
    Fail: Missing fields or error response
    """

def test_bsr_rate_limiting():
    """
    Verify pipeline respects 5 req/sec rate limit.
    Pass: No 429 errors in 100-ASIN test
    Fail: Rate limit errors
    """

def test_bsr_upsert_idempotency():
    """
    Insert same BSR data twice, verify UNIQUE constraint works.
    Pass: Second insert updates, no duplicates
    Fail: Duplicate rows or constraint violation
    """

def test_bsr_trends_view():
    """
    Insert test BSR data, query bsr_trends view, verify calculations.
    Pass: rank_change_7d and rank_status_7d computed correctly
    Fail: NULL values or wrong calculations
    """
```

---

### 2.3 Signal Detection Tests

**File:** `tests/test_signal_detection.py`

**Required Tests:**

```python
def test_demand_contraction_detection():
    """
    Insert test data with declining CVRs and stable CPC.
    Query signal_demand_contraction view.
    Pass: is_demand_contraction = TRUE
    Fail: Signal not detected or false positive
    """

def test_organic_decay_detection():
    """
    Insert test data with declining sessions + worsening BSR + stable buy box.
    Query signal_organic_decay view.
    Pass: is_rank_decay = TRUE for affected ASIN
    Fail: Signal not detected
    """

def test_no_false_positives_on_growth():
    """
    Insert test data with improving metrics.
    Query all signal views.
    Pass: All signals return FALSE or empty
    Fail: False positive signals
    """

def test_signal_severity_classification():
    """
    Insert data at severity boundaries.
    Verify signals classify as HIGH/MEDIUM/LOW correctly.
    Pass: Severity matches expectations
    Fail: Misclassified severity
    """
```

---

### 2.4 Integration Tests

**File:** `tests/test_integration.py`

**Required Tests:**

```python
def test_end_to_end_signal_pipeline():
    """
    1. Run BSR pipeline for 3 ASINs
    2. Compute account_daily aggregates
    3. Query all signal views
    4. Verify signals appear in diagnostic queries
    Pass: Full pipeline executes, signals detected
    Fail: Any step fails
    """

def test_impact_dashboard_read_only():
    """
    Import diagnostic utils, call get_recent_validation_summary().
    Verify it only SELECTs from Impact Dashboard tables.
    Pass: Function returns data, no writes attempted
    Fail: Write attempt or access error
    """

def test_streamlit_page_renders():
    """
    Import diagnostics pages, verify no import errors.
    Mock st.markdown calls, verify components render.
    Pass: All pages import successfully, no exceptions
    Fail: Import errors or runtime exceptions
    """
```

---

### 2.5 Performance Tests

**File:** `tests/test_performance.py`

**Required Tests:**

```python
def test_signal_view_query_time():
    """
    Query each signal view with 90 days of data.
    Measure execution time.
    Pass: All queries complete in <2 seconds
    Fail: Any query >2 seconds
    """

def test_bsr_pipeline_runtime():
    """
    Run BSR pipeline for 100 ASINs.
    Measure total runtime.
    Pass: Completes in <30 seconds (5 req/sec = 20s + overhead)
    Fail: >60 seconds
    """

def test_trends_page_load_time():
    """
    Load trends page with 60 days of data, 4 charts.
    Measure render time.
    Pass: Page loads in <5 seconds
    Fail: >10 seconds
    """
```

---

## 3. Validation Gates (Phase Checkpoints)

### Phase 1 Gate: BSR Pipeline

**Before proceeding to Phase 2, verify:**

```bash
# 1. Schema isolation tests pass
pytest tests/test_schema_isolation.py

# 2. BSR pipeline tests pass
pytest tests/test_bsr_pipeline.py

# 3. BSR backfill completes successfully
python -c "
from pipeline.bsr_pipeline import backfill_bsr
backfill_bsr(start_date='2025-11-15', end_date='2026-02-17')
"

# 4. Verify data landed
psql $DATABASE_URL -c "
SELECT COUNT(*) as total_rows,
       COUNT(DISTINCT asin) as unique_asins,
       MIN(report_date) as earliest,
       MAX(report_date) as latest
FROM sc_raw.bsr_history;
"
# Expected: ~10,000-15,000 rows, ~100 ASINs, date range matches backfill

# 5. Verify view works
psql $DATABASE_URL -c "
SELECT asin, current_rank, rank_status_7d
FROM sc_analytics.bsr_trends
WHERE report_date = CURRENT_DATE - 1
LIMIT 5;
"
# Expected: Returns rows with rank_status values
```

**Gate Status:**
- ✅ PASS → Proceed to Phase 2
- ❌ FAIL → Fix issues, re-run tests, do not proceed

---

### Phase 2 Gate: Signal Detection

**Before proceeding to Phase 3, verify:**

```bash
# 1. Signal detection tests pass
pytest tests/test_signal_detection.py

# 2. All 5 signal views return data
for signal in demand_contraction organic_decay non_advertised_winners harvest_cannibalization over_negation
do
  psql $DATABASE_URL -c "SELECT COUNT(*) FROM sc_analytics.signal_$signal;"
done
# Expected: Each returns row count (may be 0 if no signal active, but view works)

# 3. Integration test passes
pytest tests/test_integration.py::test_end_to_end_signal_pipeline

# 4. Verify Impact Dashboard integration works
python -c "
from utils.diagnostics import get_recent_validation_summary
summary = get_recent_validation_summary(days=7)
print(summary)
"
# Expected: Returns dict with total_actions, wins, avg_impact
```

**Gate Status:**
- ✅ PASS → Proceed to Phase 3
- ❌ FAIL → Fix issues, re-run tests, do not proceed

---

### Phase 3 Gate: UI & Visualization

**Before deployment, verify:**

```bash
# 1. Streamlit pages render without errors
streamlit run pages/diagnostics_overview.py &
# Manual: Visit http://localhost:8501, verify page loads

# 2. Performance tests pass
pytest tests/test_performance.py

# 3. All components render
python -c "
from components.icon import render_icon
from components.diagnostic_cards import metric_card, signal_card
# Verify no import errors
print('Components loaded successfully')
"

# 4. CSS injection works
# Manual: Check browser inspector, verify custom CSS is applied

# 5. Cross-browser test
# Manual: Test in Chrome, Safari, Firefox
```

**Gate Status:**
- ✅ PASS → Ready for production deployment
- ❌ FAIL → Fix issues, re-run tests, do not deploy

---

## 4. Code Review Checklist

### 4.1 Database Code Review

**Before merging any SQL migration:**

```
□ Migration file numbered sequentially (003, 004, etc.)
□ Schema specified explicitly (sc_raw or sc_analytics, never public)
□ All tables have primary key
□ All tables have appropriate indexes
□ UNIQUE constraints where needed
□ Foreign keys reference existing tables correctly
□ View definitions only SELECT, never modify data
□ No hardcoded values (use variables or config)
□ Rollback script exists and tested
□ Migration updates schema_version table
```

### 4.2 Python Code Review

**Before merging any Python file:**

```
□ No imports from public schema tables for writes
□ All database connections use get_db_cursor()
□ No hardcoded credentials
□ All config from environment variables
□ Error handling on all API calls
□ Logging for all pipeline steps
□ No print() statements (use logging.info/error)
□ Type hints on all function signatures
□ Docstrings on all public functions
□ No modification of existing function signatures
```

### 4.3 Streamlit Code Review

**Before merging any page file:**

```
□ Custom CSS injected via inject_custom_css()
□ No st.experimental_* features (use stable API)
□ All queries use connection pooling
□ No long-running queries in main thread (use st.spinner)
□ Glassmorphic design system applied correctly
□ SVG icons used (no bitmap emojis)
□ Responsive design tested
□ No hardcoded colors (use CSS variables)
□ Cross-links to Impact Dashboard work
□ Mobile layout tested
```

---

## 5. Rollback Procedures

### 5.1 Database Rollback

**If something goes wrong with database changes:**

```bash
# OPTION 1: Rollback specific migration
psql $DATABASE_URL_DIRECT -c "
DROP TABLE IF EXISTS sc_raw.bsr_history CASCADE;
DROP VIEW IF EXISTS sc_analytics.bsr_trends;
DELETE FROM sc_analytics.schema_version WHERE version = 3;
"

# OPTION 2: Nuclear rollback (drops all pipeline schemas)
python db/migrate.py rollback
# Type CONFIRM when prompted
# Verify public schema untouched

# OPTION 3: Restore from backup
psql $DATABASE_URL_DIRECT < backups/sc_raw_backup_20260217.sql
```

**Post-Rollback Verification:**
```bash
# Verify public schema intact
psql $DATABASE_URL -c "
SELECT COUNT(*) FROM public.raw_search_term_data;
SELECT COUNT(*) FROM public.target_stats;
"
# Counts should match pre-deployment

# Verify Impact Dashboard intact
# Visit Impact Dashboard in browser, verify all data present
```

---

### 5.2 Code Rollback

**If Streamlit app breaks:**

```bash
# OPTION 1: Git revert
git revert <commit_hash>
git push

# OPTION 2: Cherry-pick working version
git checkout <last_working_commit> -- pages/
git commit -m "Rollback diagnostic pages to working version"
git push

# OPTION 3: Remove diagnostic pages temporarily
mv pages/diagnostics_*.py pages/.archived/
# Restart Streamlit, app works without diagnostics
```

**Post-Rollback Verification:**
```bash
# Visit app in browser
# Verify existing pages (Campaigns, Targets, Impact Dashboard) work
# Verify no 500 errors or import errors
```

---

## 6. Architecture Context for Claude Code

### 6.1 Existing System Overview

**What already exists (DO NOT MODIFY):**

```
┌──────────────────────────────────────────────────────────────┐
│  EXISTING SADDL APP (Working, Do Not Touch)                  │
├──────────────────────────────────────────────────────────────┤
│  Frontend:                                                    │
│  - Streamlit pages: Campaigns, Targets, Search Terms         │
│  - Impact Dashboard (shows optimization validation)          │
│                                                               │
│  Backend:                                                     │
│  - public schema tables (ad console data)                    │
│  - Impact Dashboard tables (optimization results)            │
│  - Existing pipelines (ad data ingestion)                    │
│                                                               │
│  Database:                                                    │
│  - PostgreSQL (Supabase)                                     │
│  - Connection pooler for app, direct for pipelines           │
└──────────────────────────────────────────────────────────────┘
         ▲
         │ INTEGRATION POINT (Read Only)
         │
┌──────────────────────────────────────────────────────────────┐
│  NEW DIAGNOSTIC TOOL (You Build This)                        │
├──────────────────────────────────────────────────────────────┤
│  Data Layer:                                                  │
│  - sc_raw schema (Seller Central raw data)                   │
│  - sc_analytics schema (computed signals & trends)           │
│                                                               │
│  Pipelines:                                                   │
│  - BSR pipeline (new)                                        │
│  - Signal detection views (new)                              │
│                                                               │
│  Frontend:                                                    │
│  - Diagnostics pages (new)                                   │
│  - Glassmorphic components (new)                             │
│                                                               │
│  Integration:                                                 │
│  - READS from Impact Dashboard (validation context)          │
│  - READS from public.raw_search_term_data (ad data)          │
│  - NEVER WRITES to existing schemas                          │
└──────────────────────────────────────────────────────────────┘
```

---

### 6.2 Data Flow

**Existing Flow (Do Not Modify):**
```
Amazon Ads API
    ↓
Existing Ingestion Pipeline
    ↓
public.raw_search_term_data
public.target_stats
    ↓
Impact Dashboard
    ↓
Optimization Validation
```

**New Flow (You Build This):**
```
Amazon SP-API
    ↓
BSR Pipeline (NEW)
    ↓
sc_raw.bsr_history (NEW)
    ↓
sc_analytics.bsr_trends (NEW VIEW)
    ↓
Signal Detection Views (NEW)
    ↓
Diagnostic Pages (NEW)
    ↑
    │ (READS ONLY)
    │
public.raw_search_term_data (EXISTING)
Impact Dashboard tables (EXISTING)
```

---

### 6.3 Connection Patterns

**For Streamlit Pages (Diagnostic UI):**
```python
from utils.db import get_db_cursor

# Always use pooled connection
with get_db_cursor() as cur:
    cur.execute("SELECT * FROM sc_analytics.signal_demand_contraction")
    results = cur.fetchall()
```

**For Pipelines (BSR, Backfills):**
```python
from utils.db import get_db_cursor

# Use direct connection for long-running operations
with get_db_cursor(direct=True) as cur:
    # Long-running backfill
    cur.execute("INSERT INTO sc_raw.bsr_history ...")
```

**For Impact Dashboard Integration:**
```python
from utils.db import get_db_cursor

# Read-only access to Impact Dashboard
with get_db_cursor() as cur:
    cur.execute("""
        SELECT COUNT(*) as wins
        FROM [impact_dashboard_table]  -- Replace with actual table
        WHERE status = 'WIN'
    """)
    wins = cur.fetchone()[0]
```

---

## 7. Common Pitfalls to Avoid

### 7.1 Database Pitfalls

❌ **Using public schema by default**
```python
# WRONG
cur.execute("CREATE TABLE bsr_history ...")  # Defaults to public schema

# RIGHT
cur.execute("CREATE TABLE sc_raw.bsr_history ...")
```

❌ **Forgetting UNIQUE constraints**
```sql
-- WRONG: Allows duplicate BSR entries
CREATE TABLE sc_raw.bsr_history (
    asin VARCHAR(20),
    report_date DATE,
    rank INTEGER
);

-- RIGHT: Prevents duplicates
CREATE TABLE sc_raw.bsr_history (
    ...,
    UNIQUE (report_date, marketplace_id, asin, category_id)
);
```

❌ **Missing indexes**
```sql
-- WRONG: No indexes, queries slow
CREATE TABLE sc_raw.bsr_history (...);

-- RIGHT: Indexes for common query patterns
CREATE INDEX idx_bsr_date_asin ON sc_raw.bsr_history (report_date, asin);
```

---

### 7.2 Python Pitfalls

❌ **Hardcoded credentials**
```python
# WRONG
API_KEY = "amzn1.application..."

# RIGHT
from pipeline.config import get_config
config = get_config()
api_key = config["lwa_client_id"]
```

❌ **Not using context managers**
```python
# WRONG: Connection leak
conn = psycopg2.connect(...)
cur = conn.cursor()
cur.execute(...)
# Forgot to close!

# RIGHT: Automatic cleanup
with get_db_cursor() as cur:
    cur.execute(...)
```

❌ **Modifying existing functions**
```python
# WRONG: Breaking existing code
def get_db_cursor(timeout=30):  # Changed signature!
    ...

# RIGHT: New function
def get_db_cursor_with_timeout(timeout=30):
    return get_db_cursor(...)
```

---

### 7.3 Streamlit Pitfalls

❌ **Not injecting custom CSS**
```python
# WRONG: Components without styles
st.markdown(metric_card(...), unsafe_allow_html=True)

# RIGHT: Inject CSS first
inject_custom_css()
st.markdown(metric_card(...), unsafe_allow_html=True)
```

❌ **Using bitmap emojis in UI**
```python
# WRONG
st.markdown("🔴 High Severity")

# RIGHT
st.markdown(f"{render_icon('alert-circle', color='var(--error-500)')} High Severity")
```

❌ **Long-running queries in main thread**
```python
# WRONG: Blocks UI
results = expensive_query()

# RIGHT: Show spinner
with st.spinner("Loading signals..."):
    results = expensive_query()
```

---

## 8. Success Criteria Summary

**Diagnostic Tool is READY FOR PRODUCTION when:**

✅ All schema isolation tests pass  
✅ All BSR pipeline tests pass  
✅ All signal detection tests pass  
✅ All integration tests pass  
✅ All performance tests pass  
✅ Phase 1, 2, 3 validation gates completed  
✅ Code review checklist items checked  
✅ Rollback procedures tested and documented  
✅ Impact Dashboard integration verified (read-only)  
✅ No modifications to public schema or existing files  
✅ Existing SADDL pages still work (smoke test)  

**Final Acceptance Test:**
```bash
# 1. Run full test suite
pytest tests/ -v

# 2. Deploy to staging
# 3. Visit all pages in browser:
#    - Campaigns ✓
#    - Targets ✓
#    - Impact Dashboard ✓
#    - Diagnostics > Overview ✓
#    - Diagnostics > Signals ✓
#    - Diagnostics > Trends ✓

# 4. Verify no console errors
# 5. Verify data displays correctly
# 6. Click cross-links to Impact Dashboard (verify they work)

# 7. If ALL above pass → Deploy to production
# 8. If ANY fail → Rollback and fix
```

---

## 9. Is This Comprehensive Enough?

**YES** — Claude Code has everything needed IF:

✅ Claude Code reads all 4 docs:
   1. This guardrails doc
   2. PRD v2 (feature spec)
   3. Backend Architecture (schema design)
   4. Frontend Architecture (UI/UX)

✅ Claude Code follows test-first approach:
   - Writes tests BEFORE implementation
   - Runs tests after each phase
   - Does not proceed to next phase until gate passes

✅ Claude Code respects boundaries:
   - Never modifies public schema
   - Never modifies existing files
   - Only creates new files in approved locations

**NO** — Additional guidance needed IF:

❌ Claude Code doesn't know actual Impact Dashboard table names
   → Provide exact table names before starting

❌ Claude Code doesn't have example of existing Streamlit page structure
   → Provide one existing page file as reference

❌ Claude Code doesn't know connection string format
   → Already in Backend Architecture, but confirm .env is configured

---

## 10. Pre-Build Checklist for Claude Code

**Before starting implementation, verify:**

```
□ All 4 documentation files read and understood
□ .env file configured with all required variables:
  - DATABASE_URL (pooled connection)
  - DATABASE_URL_DIRECT (direct connection)
  - LWA_CLIENT_ID
  - LWA_CLIENT_SECRET
  - LWA_REFRESH_TOKEN_UAE
  - AWS_ACCESS_KEY_ID
  - AWS_SECRET_ACCESS_KEY
  
□ Impact Dashboard table names confirmed:
  - [table_name] for optimization results
  - [table_name] for validation data
  
□ Existing schema baseline captured:
  psql $DATABASE_URL -c "\dt public.*" > baseline_schema.txt
  
□ Git branch created for this work:
  git checkout -b feature/diagnostic-tool
  
□ Test framework installed:
  pip install pytest pytest-mock
  
□ Rollback script tested on dev DB:
  python db/migrate.py rollback (on test database)
```

**Claude Code Confirmation Required:**
- "I have read all 4 documents"
- "I understand the schema isolation requirements"
- "I will write tests before implementation"
- "I will not modify public schema or existing files"
- "I will stop at each validation gate and report status"

---

*Guard rails v1.0 — comprehensive safety protocol for diagnostic tool build.*
