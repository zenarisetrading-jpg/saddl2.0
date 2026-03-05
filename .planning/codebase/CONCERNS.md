# Codebase Concerns

**Analysis Date:** 2026-02-24

## Tech Debt

### 1. Bare Exception Handling Throughout Pipeline
- **Issue:** Multiple functions use bare `except` or `except Exception` without distinction
- **Files:**
  - `pipeline/runner.py` (lines 90-105, 136-138)
  - `pipeline/bsr_pipeline.py` (lines 292-294)
  - `features/optimizer_shared/strategies/bids.py` (lines 91-98, etc.)
- **Impact:** Obscures debugging, masks programming errors, makes error recovery unpredictable
- **Fix approach:** Replace with specific exception types. Use `psycopg2.Error`, `RequestException`, `HTTPError` - never catch all exceptions silently
- **Priority:** Medium

### 2. Duplicate Configuration Constants Across Strategy Files
- **Issue:** BID_LIMITS, CVR_CONFIG, OPTIMIZATION_PROFILES defined in `core.py` but also partially duplicated in strategy files
- **Files:**
  - `features/optimizer_shared/core.py` (lines 27-78)
  - `features/optimizer_shared/strategies/bids.py` (lines 22-46)
  - `features/optimizer_shared/strategies/harvest.py` (imported but also uses inline config)
- **Impact:** Configuration drift, hard to maintain single source of truth
- **Fix approach:** Create `features/optimizer_shared/config.py` with all constants, import everywhere
- **Priority:** Low

### 3. Duplicated Fake/Duplicate Files Throughout Repository
- **Issue:** Repository contains numerous "2" suffixed duplicate files (e.g., `__init__ 2.py`, `config 2.py`)
- **Files:** Over 100 files listed in git status with " 2" suffix
- **Impact:** Confusion about which version is active, wasted storage, git clutter
- **Fix approach:** Audit and delete all duplicates, confirm only canonical versions remain
- **Priority:** High - cleanup should happen before next major release

### 4. Inconsistent Error Fallback Patterns
- **Issue:** Silent fallbacks without logging in critical paths
- **Files:**
  - `features/optimizer_shared/core.py` lines 384-387 (DB error silent fallback to CSV)
  - `app_core/db_manager.py` lines 450-451 (DB save fails silently in optimizer)
- **Impact:** Users may see stale/incorrect data without knowing health calc failed
- **Fix approach:** Log all fallbacks at WARNING level, add explicit health score flags indicating data source
- **Priority:** Medium

### 5. Session State Dependency Sprawl
- **Issue:** Heavy reliance on `st.session_state` throughout optimizer and dashboard code
- **Files:**
  - `features/optimizer_shared/core.py` (lines 345-346)
  - `features/optimizer_shared/strategies/bids.py` (lines 78-80, 87-98)
  - Multiple UI components
- **Impact:** Hard to test in isolation, state mutations not explicit, difficult to reason about data flow
- **Fix approach:** Extract session state usage into a dedicated manager class with explicit state contracts
- **Priority:** Low (refactor candidate for v2.2)

## Known Bugs

### 1. Market Drag Display Bug (FIXED but history preserved)
- **Symptom:** Market Drag category showing positive Impact values in Impact Dashboard
- **Files:** `features/impact/data/transforms.py` (lines 52-90) - FIXED
- **Root cause:** Dashboard recalculated `market_tag` BEFORE copying `final_decision_impact` from database, creating mismatch between category and displayed value
- **Status:** Fixed Feb 5, 2026 - database is now single source of truth
- **Prevention:** Added test in `dev_resources/tests/test_market_drag_fix.py`
- **Related:** `dev_resources/documentation/MARKET_DRAG_BUG_FIX.md`

### 2. Targeting Column Ambiguity (Mitigated)
- **Symptom:** Auto/Broad/Phrase campaigns showing search terms as "targeting" instead of generic match type
- **Files:** `features/optimizer_shared/core.py` (lines 194-214)
- **Root cause:** Fallback to Customer Search Term for all match types instead of just Exact
- **Status:** Partially mitigated - now only fills exact matches with search term, uses match type for auto/broad
- **Remaining risk:** PT campaigns (with `asin=` expressions) could still be incorrectly classified
- **Recommendation:** Add explicit validation in `prepare_data()` to verify Targeting column matches expected pattern for match type

### 3. CVR Clamping Silent Behavior
- **Symptom:** Account CVR silently clamped to [1%, 20%] without user notification
- **Files:** `features/optimizer_shared/core.py` (lines 291-294)
- **Impact:** Users with genuine CVR outside range don't see warnings
- **Risk:** Harvest and negative thresholds become incorrect for accounts with very low/high conversion rates
- **Recommendation:** Add health check dashboard card showing "CVR was clamped" when `was_clamped == True`

### 4. Date Range Detection Fallback
- **Symptom:** If no date column found, returns "Period Unknown" but continues optimization
- **Files:** `features/optimizer_shared/core.py` (lines 238-272)
- **Impact:** Weekly normalization silently becomes "1 week" which could skew multi-week analyses
- **Recommendation:** Return error or require explicit date range from user rather than silencing

## Security Considerations

### 1. Environment Variable Handling in Auth
- **Risk:** Config dict passed throughout pipeline contains secrets (refresh tokens, API keys)
- **Files:**
  - `pipeline/auth.py` (lines 9-21, 24-30)
  - `pipeline/config.py` (loads from environment)
- **Current mitigation:** Secrets loaded from environment variables at startup
- **Recommendations:**
  - Never log config dict contents (already done via print statements avoiding this)
  - Add secret masking utility if config is logged for debugging
  - Use boto3 Secrets Manager for production instead of environment variables

### 2. Database Connection String Exposure
- **Risk:** PostgreSQL database URLs may be passed as plain text strings
- **Files:**
  - `pipeline/bsr_pipeline.py` (lines 190-203)
  - Multiple files calling functions with `db_url` parameter
- **Current mitigation:** Uses environment variable `DATABASE_URL` and `DATABASE_URL_DIRECT`
- **Recommendations:**
  - Never log `db_url` in debug output
  - Implement URL masking utility for logs: `postgres://user:[MASKED]@host/db`
  - Add validation to reject URLs containing plaintext passwords

### 3. SP-API Rate Limiting Window
- **Risk:** Rate limit delay hardcoded at 0.2 seconds (5 req/sec) but no backoff for 429 errors
- **Files:** `pipeline/bsr_pipeline.py` (lines 31-53, 131, 147)
- **Current behavior:** Retries with exponential backoff on 429 but doesn't increase base delay
- **Recommendations:**
  - Implement adaptive rate limiting that tracks 429s and backs off globally
  - Add circuit breaker pattern: pause all requests if too many 429s

## Performance Bottlenecks

### 1. Large DataFrame Aggregation in Harvest Logic
- **Problem:** `identify_harvest_candidates()` aggregates discovery data with `.groupby()` without early filtering
- **Files:** `features/optimizer_shared/strategies/harvest.py` (lines 78-98)
- **Scale issue:** With 100k+ search terms, full groupby then filter is slow
- **Optimization:** Apply discovery filter BEFORE groupby to reduce dataset size first
- **Expected improvement:** ~40-50% faster for large accounts

### 2. Repeated Database Queries in Bid Optimizer
- **Problem:** Multiple sequential DB queries in `calculate_bid_optimizations()` without batching
- **Files:** `features/optimizer_shared/strategies/bids.py` (lines 82-98)
- **Queries:** `get_recent_action_dates()`, `get_target_14d_roas()`, `build_commerce_lookup()`
- **Scale issue:** Each query hits network, blocks until response
- **Optimization:** Implement batch query wrapper or async loading
- **Expected improvement:** ~30% faster for accounts with slow DB connections

### 3. Full Data Processing on Every Session State Change
- **Problem:** `st.cache_data` used but cache_key not set, so changes to filters cause re-runs
- **Files:** `features/optimizer_shared/core.py` (lines 151-235)
- **Impact:** Re-prepares entire dataset when user changes single config value
- **Fix:** Add explicit cache_key parameter: `@st.cache_data(show_spinner=False, ttl_seconds=3600)`
- **Expected improvement:** ~60% reduction in re-processing for interactive users

### 4. Full Account Health Calculation on Optimizer Load
- **Problem:** `calculate_account_health()` fetches 50k rows from database every time optimizer loads
- **Files:** `features/optimizer_shared/core.py` (lines 340-453)
- **Risk:** Slow startup if database has many old records
- **Fix approach:**
  - Limit to last 90 days only
  - Cache result for 1 hour
  - Add limit parameter to `get_target_stats_by_account()`
- **Expected improvement:** ~70% faster startup

## Fragile Areas

### 1. Pipeline Data Kiosk Integration
- **Files:** `pipeline/runner.py`, `pipeline/data_kiosk.py`
- **Fragility:** Depends on exact SP-API Data Kiosk response schema - small changes break parsing
- **Why fragile:**
  - Nested dict access without defensive checks in `transform.py` lines 16-21
  - Hard-coded field names like `analytics_salesAndTraffic_2024_04_24`
  - No schema versioning
- **Safe modification:**
  - Add schema detection logic before parsing
  - Create data class definitions for each API response type
  - Add comprehensive logging of unexpected fields
- **Test coverage:** `tests/pipeline/test_transform.py` exists but minimal coverage

### 2. Account Benchmark Calculation (CVR-based thresholds)
- **Files:** `features/optimizer_shared/core.py` (lines 276-338)
- **Fragility:** Depends on CVR calc being accurate - used for harvest, negative, and bid decisions
- **Why fragile:**
  - Raw CVR could be 0 if no orders (line 291 divides by 0 handled but returns 0.03 default)
  - Clamping to [1%, 20%] silently changes thresholds without user awareness
  - Expected clicks calc (1/account_cvr) could be huge if CVR is 1%
- **Safe modification:**
  - Add health score indicator for "low data reliability" warning
  - Require minimum 50 orders before trusting CVR
  - Show calculated benchmarks in UI for user approval
- **Test coverage:** No specific tests for edge cases (zero orders, extreme CVR)

### 3. BSR History Upsert Logic
- **Files:** `pipeline/bsr_pipeline.py` (lines 151-186)
- **Fragility:** ON CONFLICT uses composite unique key - if key columns change, duplicates appear
- **Why fragile:**
  - Unique constraint is `(report_date, marketplace_id, account_id, asin, category_id)`
  - If category_id extraction changes (lines 69, 87), old/new records don't match
  - No migration to update existing duplicates
- **Safe modification:**
  - Add schema migration validation in `verify_pipeline_tables_exist()`
  - Log row counts before/after upsert to detect duplicates
  - Create cleanup script for existing duplicates
- **Test coverage:** `tests/pipeline/test_bsr_pipeline.py` missing

### 4. Import Path Inconsistencies
- **Files:** Throughout - mixed usage of `from core.` vs `from app_core.`
- **Fragility:** Recent migration from `core/` to `app_core/` not fully complete
- **Examples:**
  - `features/optimizer_shared/core.py` uses `from app_core.db_manager import get_db_manager` (line 13)
  - Some files still import from `core/` directly
- **Safe modification:**
  - Global search-replace to ensure all imports use `app_core/`
  - Add pre-commit hook to prevent `core/` imports in new code
- **Test coverage:** No import validation tests

## Scaling Limits

### 1. SQLite Database for Production Use
- **Current capacity:** SQLite handles ~1M rows efficiently
- **Current usage:** Appears to be ~500k rows based on code patterns
- **Limit:** Will hit performance cliff around 5-10M rows or with concurrent write operations
- **Scaling path:** Migrate to PostgreSQL (already used for main data). Update `app_core/db_manager.py` to support both SQLite (test) and PostgreSQL (production)
- **Timeline:** Not urgent but plan for Q3 2026

### 2. Pipeline Concurrent Request Limits
- **Current capacity:** Single-threaded BSR pull with 0.2s delay = ~5 req/sec
- **Limit:** To pull 100k ASINs requires ~5+ hours of continuous requests
- **Scaling path:**
  - Implement thread pool for parallel BSR fetches (Amazon allows ~5-10 concurrent)
  - Add queue-based architecture for large backfills
  - Consider moving to Lambda/batch processing for scale
- **Timeline:** Becomes critical if catalog grows >100k SKUs

### 3. Account Health Calculation Memory
- **Current capacity:** Loads 50k raw records into memory
- **Limit:** Streamlit memory pressure at >500k records
- **Scaling path:**
  - Add database-level aggregation (move calculation to SQL window functions)
  - Implement streaming aggregation for large datasets
  - Add pagination to health calculation
- **Timeline:** Medium term (Q2 2026 if accounts add more data)

## Dependencies at Risk

### 1. Streamlit (Business Logic Dependency)
- **Risk:** Heavy coupling to Streamlit `st.cache_data`, `st.session_state`, `st.metrics` throughout optimization logic
- **Impact:** Difficult to unit test, impossible to use logic outside Streamlit (API, batch processing)
- **Migration plan:** Extract core optimizer to separate `optimizers/` package with pure functions, use Streamlit UI as thin wrapper
- **Priority:** Medium (needed for API endpoint support)

### 2. psycopg2 Raw Connection Management
- **Risk:** Manual connection/cursor handling throughout pipeline with try/except/finally
- **Files:** `pipeline/aggregator.py`, `pipeline/db_writer.py`, `pipeline/bsr_pipeline.py`
- **Impact:** Connection leaks possible if exceptions occur, hard to test with mocks
- **Migration plan:** Implement connection pool wrapper using `psycopg2.pool.SimpleConnectionPool`
- **Priority:** Low (works but not optimal)

### 3. pandas DataFrame Assumptions
- **Risk:** Code assumes specific DataFrame columns exist without validation
- **Files:** Multiple files in `features/optimizer_shared/`
- **Impact:** Runtime errors if upstream data changes (new CSV format, different API response)
- **Fix:** Add `assert` statements for required columns at function entry
- **Priority:** Medium

## Missing Critical Features

### 1. No Negative Keyword Validation
- **Problem:** Code identifies negative keywords but no validation that they won't accidentally block true converters
- **Files:** `features/optimizer_shared/strategies/negatives.py`
- **Impact:** Risk of over-negating profitable keywords by accident
- **Recommendation:** Add validation check comparing suggested negatives against recent winners
- **Blocks:** High-confidence negative deployment

### 2. No Multi-Account Isolation Testing
- **Problem:** Code supports multiple `client_id` values but no test validates cross-account data doesn't leak
- **Files:** All `client_id` parameter usage
- **Impact:** Risk of one client seeing another's data in rare conditions
- **Recommendation:** Add integration test with 2+ client IDs verifying filtering works throughout pipeline
- **Priority:** High - security critical

### 3. No Backfill Validation
- **Problem:** BSR and sales pipeline support backfill but no validation that backfilled data is internally consistent
- **Files:** `pipeline/runner.py` (lines 141-177), `pipeline/bsr_pipeline.py` (lines 257-303)
- **Impact:** Could load incorrect historical data without detection
- **Recommendation:** Add row count and date range validation after backfill completes
- **Blocks:** Large historical data loads

### 4. No Optimizer Dry-Run Mode
- **Problem:** Users can't preview optimization recommendations without committing
- **Files:** `features/optimizer_v2/` modules
- **Impact:** Risky for users to test new profiles without applying changes
- **Recommendation:** Add `--dry-run` flag that returns recommendations without applying
- **Priority:** Medium - improves user confidence

## Test Coverage Gaps

### 1. End-to-End Pipeline Flow
- **What's not tested:** Full pipeline from SP-API response → raw table → aggregated table
- **Files:** `pipeline/runner.py`, `pipeline/aggregator.py`
- **Risk:** Intermediate transformation bugs won't be caught until production
- **Test approach:** Create integration test that mocks SP-API, runs full pipeline, validates aggregated table schema
- **Priority:** High

### 2. Harvest Logic Edge Cases
- **What's not tested:**
  - Duplicate harvest candidates in same campaign
  - Harvesting from PT (product targeting) campaigns
  - Harvesting when existing exact match keyword has conflicting bid
- **Files:** `features/optimizer_shared/strategies/harvest.py`
- **Risk:** Generates invalid bulk file or incorrect recommendations
- **Priority:** High

### 3. CVR-Based Threshold Calculations
- **What's not tested:**
  - Account with zero orders (CVR = 0)
  - Account with 100% conversion (CVR = 1.0)
  - Threshold calculations when data is 1-3 days old (high variance)
- **Files:** `features/optimizer_shared/core.py` (lines 276-338)
- **Risk:** Thresholds become incorrect or causes division errors
- **Priority:** Medium

### 4. Database Fallback Paths
- **What's not tested:** When database is unavailable, health calc falls back to CSV data
- **Files:** `features/optimizer_shared/core.py` (lines 340-387)
- **Risk:** Silent fallback masks real DB issues
- **Test approach:** Mock `get_db_manager` to return None, verify fallback works and logs warning
- **Priority:** Medium

### 5. Error Handling in Bids Strategy
- **What's not tested:**
  - Commerce lookup fails (lines 107-113 in bids.py)
  - Database query returns empty/malformed data
  - Recent actions has conflicting timestamps
- **Risk:** Produces invalid bid recommendations
- **Priority:** Medium

## Architecture Concerns

### 1. Circular Dependency Potential
- **Issue:** `features/optimizer_shared/core.py` imports from strategy files, which import back from core
- **Files:**
  - `core.py` imports from `bids.py`, `harvest.py`, `negatives.py`
  - Strategy files import `DEFAULT_CONFIG` from `core.py`
- **Risk:** Refactoring becomes difficult, testing requires mocking entire module
- **Fix:** Move shared constants to separate `config.py`, limit imports to one direction

### 2. Mixed Concerns in Strategy Files
- **Issue:** Strategy files contain business logic, UI elements, and database queries mixed
- **Files:** `features/optimizer_shared/strategies/bids.py` (82-113 has DB queries mixed with logic)
- **Impact:** Hard to test business logic in isolation, UI changes force strategy changes
- **Recommendation:** Separate into layers: `business_logic.py`, `data_access.py`, `ui_adapters.py`

### 3. No Explicit Data Contracts
- **Issue:** No TypedDict or dataclass definitions for major data structures
- **Files:** Most Python files work with dicts without schema validation
- **Impact:** Bugs arise from missing/wrong fields discovered only at runtime
- **Recommendation:** Create `features/types.py` with dataclasses for:
  - `HarvestCandidate`, `BidRecommendation`, `NegativeKeyword`
  - Use in function signatures and add runtime validation

---

## Summary by Priority

### Critical (Fix before next release)
1. Duplicate " 2" files cluttering repo - cleanup/delete
2. Multi-account data isolation testing
3. Market Drag bug (FIXED but monitor)

### High
1. Bare exception handling throughout - standardize
2. Pipeline E2E test coverage
3. Harvest logic edge cases testing
4. Environment/config management review

### Medium
1. Silent error fallback patterns - add logging
2. CVR threshold calculation edge cases
3. Streamlit decoupling for reusability
4. Import path inconsistencies (core vs app_core)

### Low (Technical Improvement)
1. Duplicate config constants - consolidate
2. Session state sprawl - encapsulate
3. Database connection pooling - implement
4. Performance optimization for large datasets

---

*Concerns audit: 2026-02-24*
