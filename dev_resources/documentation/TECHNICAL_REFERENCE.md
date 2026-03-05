# Saddl AdPulse - Comprehensive Technical Reference

**Version**: 4.0  
**Last Updated**: January 14, 2026

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Entry Points & Application Flow](#2-entry-points--application-flow)
3. [PostgreSQL Database Schema](#3-postgresql-database-schema)
4. [Core Modules Reference](#4-core-modules-reference)
5. [Features Modules Reference](#5-features-modules-reference)
6. [UI Layer Reference](#6-ui-layer-reference)
7. [Data Flow & Session State](#7-data-flow--session-state)
8. [Action Storage & Impact Tracking](#8-action-storage--impact-tracking)
9. [Scripts Reference](#9-scripts-reference)
10. [Authentication & User Management](#10-authentication--user-management)

---

## 1. Architecture Overview

### 1.1 Technology Stack

| Layer | Technology |
|-------|------------|
| **Language** | Python 3.9+ |
| **UI Framework** | Streamlit (Reactive server-side UI) |
| **Data Processing** | Pandas (Vectorized operations) |
| **Visualization** | Plotly (Interactive charts) |
| **Database** | PostgreSQL 15+ (Supabase) |
| **DB Interface** | psycopg2 / Connection Pooling |
| **External APIs** | Rainforest API (ASIN enrichment), Anthropic (AI Assistant) |
| **Statistics** | SciPy (z-score confidence calculations) |

### 1.2 Directory Structure

```
desktop/
├── ppcsuite_v4_ui_experiment.py   # ⭐ MAIN ENTRY POINT
├── run.sh                          # Streamlit launcher script
├── requirements.txt                # Python dependencies
│
├── core/                           # Backend logic
│   ├── postgres_manager.py         # Database operations (111KB)
│   ├── data_hub.py                 # Data ingestion & session management
│   ├── data_loader.py              # File parsing utilities
│   ├── bulk_validation.py          # Amazon bulk file validation
│   ├── column_mapper.py            # Column normalization
│   ├── mapping_engine.py           # SKU/ASIN mapping logic
│   ├── performance_calc.py         # Metric calculations
│   └── roas_attribution.py         # ROAS decomposition logic
│
├── features/                       # Feature modules
│   ├── optimizer.py                # Harvest/Bids/Negatives engine (114KB)
│   ├── impact_dashboard.py         # Impact measurement UI (143KB)
│   ├── impact_metrics.py           # Metrics calculation (single source)
│   ├── bulk_export.py              # Amazon bulk file generation
│   ├── creator.py                  # Campaign creation wizard
│   ├── assistant.py                # AI Strategist chat
│   ├── performance_snapshot.py     # Account overview
│   ├── report_card.py              # Health scoring
│   ├── asin_mapper.py              # ASIN enrichment UI
│   └── simulator.py                # Bid simulation
│
├── ui/                             # UI components
│   ├── layout.py                   # Sidebar, home page
│   ├── components.py               # Reusable UI widgets
│   ├── styles.py                   # CSS injection
│   ├── theme.py                    # Brand theming
│   └── auth/                       # Login components
│
├── auth/                           # Authentication service
│   ├── service.py                  # Auth logic
│   ├── middleware.py               # Session management
│   └── ui.py                       # Login/signup UI
│
├── migrations/                     # Database schema migrations
├── tests/                          # Test & diagnostic scripts
├── scripts/                        # Utility scripts
└── landing/                        # Marketing website (HTML/CSS/JS)
```

---

## 2. Entry Points & Application Flow

### 2.1 Main Entry Point

**File**: `ppcsuite_v4_ui_experiment.py`

This is the **only** entry point for the Streamlit application. Launched via:

```bash
./run.sh  # Executes: streamlit run ppcsuite_v4_ui_experiment.py
```

### 2.2 Key Functions

| Function | Lines | Purpose |
|----------|-------|---------|
| `main()` | 1032-1435 | Main router - handles authentication, navigation, module routing |
| `run_performance_hub()` | 116-169 | Renders Account Overview + Report Card |
| `run_consolidated_optimizer()` | 174-1018 | Full optimizer workflow with results tabs |

### 2.3 Navigation Flow

```
main()
  │
  ├─► Authentication Check (render_login if not logged in)
  │
  ├─► Sidebar Rendering (account selector, navigation)
  │
  └─► Module Routing based on st.session_state['current_module']:
       ├─► 'home'         → render_home() from ui/layout.py
       ├─► 'overview'     → run_performance_hub()
       ├─► 'optimizer'    → run_consolidated_optimizer()
       ├─► 'impact'       → render_impact_dashboard() from features/impact_dashboard.py
       ├─► 'data_hub'     → render_data_hub() from ui/data_hub.py
       ├─► 'creator'      → CreatorModule().run()
       ├─► 'asin_mapper'  → ASINMapperModule().run()
       └─► 'assistant'    → render_assistant() from features/assistant.py
```

---

## 3. PostgreSQL Database Schema

### 3.1 Core Tables (Created by `postgres_manager._init_schema()`)

#### `accounts`
Account metadata for all clients.

| Column | Type | Description |
|--------|------|-------------|
| `account_id` | TEXT | **PRIMARY KEY** - Unique account identifier |
| `account_name` | TEXT | Display name |
| `account_type` | TEXT | 'brand' (default) |
| `metadata` | TEXT | JSON metadata |
| `created_at` | TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | Last update |

---

#### `raw_search_term_data`
**Raw daily data storage** - Preserves original STR upload at daily granularity before weekly aggregation.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT4 | PRIMARY KEY (auto-increment) |
| `client_id` | TEXT | Account reference |
| `report_date` | DATE | Original report date (daily) |
| `campaign_name` | TEXT | Campaign name as uploaded |
| `ad_group_name` | TEXT | Ad group name as uploaded |
| `targeting` | TEXT | Targeting expression |
| `customer_search_term` | TEXT | Actual search query |
| `match_type` | TEXT | Match type |
| `impressions` | INTEGER | Daily impressions |
| `clicks` | INTEGER | Daily clicks |
| `spend` | DECIMAL | Daily spend |
| `sales` | DECIMAL | Daily sales |
| `orders` | INTEGER | Daily orders |
| `created_at` | TIMESTAMP | Insert timestamp |

> **Note**: This table exists in Supabase and stores the raw uploaded data before it gets aggregated weekly into `target_stats`. Useful for re-aggregation, auditing, and granular daily analysis.

---

#### `target_stats`
**Primary data table** - Granular keyword/search term performance by week.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | PRIMARY KEY |
| `client_id` | TEXT | Account reference (INDEXED) |
| `start_date` | DATE | Week start (Monday), INDEXED |
| `campaign_name` | TEXT | Normalized campaign name |
| `ad_group_name` | TEXT | Normalized ad group name |
| `target_text` | TEXT | Keyword/targeting expression (for bids) |
| `customer_search_term` | TEXT | Actual search query (for harvest/negatives) |
| `match_type` | TEXT | exact, broad, phrase, auto, pt |
| `spend` | DOUBLE PRECISION | Total ad spend |
| `sales` | DOUBLE PRECISION | Attributed sales |
| `clicks` | INTEGER | Total clicks |
| `impressions` | INTEGER | Total impressions |
| `orders` | INTEGER | Conversion count |
| `created_at` | TIMESTAMP | Insert time |
| `updated_at` | TIMESTAMP | Last update |

**Unique Constraint**: `(client_id, start_date, campaign_name, ad_group_name, target_text, customer_search_term, match_type)`

---

#### `actions_log`
**Audit trail** - Every optimization action logged.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | PRIMARY KEY |
| `action_date` | TIMESTAMP | When action was logged |
| `client_id` | TEXT | Account reference |
| `batch_id` | TEXT | Batch grouping for undo capability |
| `entity_name` | TEXT | Entity being modified |
| `action_type` | TEXT | NEGATIVE, HARVEST, BID_CHANGE, etc. |
| `old_value` | TEXT | Previous value |
| `new_value` | TEXT | New value |
| `reason` | TEXT | Optimization rationale |
| `campaign_name` | TEXT | Target campaign |
| `ad_group_name` | TEXT | Target ad group |
| `target_text` | TEXT | Keyword/term modified |
| `match_type` | TEXT | Match type |

**Indexes**: `idx_actions_log_batch`, `idx_actions_log_client`

---

#### `weekly_stats`
Aggregated weekly performance snapshots.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | PRIMARY KEY |
| `client_id` | TEXT | Account reference |
| `start_date` | DATE | Week start |
| `end_date` | DATE | Week end |
| `spend` | DOUBLE PRECISION | Total spend |
| `sales` | DOUBLE PRECISION | Total sales |
| `roas` | DOUBLE PRECISION | ROAS for the week |

---

#### `bulk_mappings`
Campaign/Ad Group ID mappings for bulk exports.

| Column | Type | Description |
|--------|------|-------------|
| `client_id` | TEXT | Account reference |
| `campaign_name` | TEXT | Campaign display name |
| `campaign_id` | TEXT | Amazon Campaign ID |
| `ad_group_name` | TEXT | Ad Group display name |
| `ad_group_id` | TEXT | Amazon Ad Group ID |
| `keyword_text` | TEXT | Keyword text |
| `keyword_id` | TEXT | Amazon Keyword ID |
| `targeting_expression` | TEXT | PT expression |
| `targeting_id` | TEXT | Amazon Targeting ID |
| `sku` | TEXT | Product SKU |
| `match_type` | TEXT | Match type |

---

#### `category_mappings`
SKU-to-category mappings for roll-up reporting.

| Column | Type | Description |
|--------|------|-------------|
| `client_id` | TEXT | Account reference |
| `sku` | TEXT | Product SKU |
| `category` | TEXT | Top-level category |
| `sub_category` | TEXT | Sub-category |

**Primary Key**: `(client_id, sku)`

---

#### `advertised_product_cache`
Campaign → SKU/ASIN mapping cache.

| Column | Type | Description |
|--------|------|-------------|
| `client_id` | TEXT | Account reference |
| `campaign_name` | TEXT | Campaign name |
| `ad_group_name` | TEXT | Ad group name |
| `sku` | TEXT | Product SKU |
| `asin` | TEXT | Amazon ASIN |

---

#### `account_health_metrics`
Cached health scores for Home dashboard.

| Column | Type | Description |
|--------|------|-------------|
| `client_id` | TEXT | **PRIMARY KEY** |
| `health_score` | DOUBLE PRECISION | Overall 0-100 score |
| `roas_score` | DOUBLE PRECISION | ROAS component |
| `waste_score` | DOUBLE PRECISION | Waste component |
| `cvr_score` | DOUBLE PRECISION | CVR component |
| `waste_ratio` | DOUBLE PRECISION | % of spend wasted |
| `wasted_spend` | DOUBLE PRECISION | $ wasted |
| `current_roas` | DOUBLE PRECISION | Current ROAS |
| `current_acos` | DOUBLE PRECISION | Current ACoS |
| `cvr` | DOUBLE PRECISION | Conversion rate |
| `total_spend` | DOUBLE PRECISION | Total spend |
| `total_sales` | DOUBLE PRECISION | Total sales |

---

### 3.2 User Management Tables (Migration 002)

#### `organizations`
Multi-tenant organization support.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | PRIMARY KEY |
| `name` | VARCHAR(255) | Organization name |
| `type` | VARCHAR(20) | 'AGENCY' or 'SELLER' |
| `subscription_plan` | VARCHAR(50) | Billing tier |
| `amazon_account_limit` | INT | Max accounts allowed |
| `seat_price` | DECIMAL | Per-seat price |
| `status` | VARCHAR(20) | 'ACTIVE' or 'SUSPENDED' |

---

#### `users`
User accounts with roles.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | PRIMARY KEY |
| `organization_id` | UUID | FK → organizations |
| `email` | VARCHAR(255) | UNIQUE email |
| `password_hash` | VARCHAR(255) | Hashed password |
| `role` | VARCHAR(20) | OWNER, ADMIN, OPERATOR, VIEWER |
| `billable` | BOOLEAN | Counts toward seat limit |
| `status` | VARCHAR(20) | 'ACTIVE' or 'DISABLED' |
| `last_login_at` | TIMESTAMPTZ | Last login time |

---

#### `amazon_accounts`
Amazon Advertising accounts linked to organizations.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | PRIMARY KEY |
| `organization_id` | UUID | FK → organizations |
| `display_name` | VARCHAR(255) | Account display name |
| `marketplace` | VARCHAR(50) | US, UK, UAE, etc. |
| `status` | VARCHAR(20) | 'ACTIVE' or 'DISABLED' |

---

#### `user_account_overrides` (Migration 004)
Per-account role restrictions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | PRIMARY KEY |
| `user_id` | UUID | FK → users |
| `amazon_account_id` | UUID | FK → amazon_accounts |
| `role` | VARCHAR(20) | 'VIEWER' or 'OPERATOR' only |

**Trigger**: `enforce_override_downgrade` prevents role escalation.

---

### 3.3 Ingestion Tables (Migration 001 - V2)

#### `ingestion_events_v2`
Audit trail for data ingestion.

| Column | Type | Description |
|--------|------|-------------|
| `ingestion_id` | UUID | PRIMARY KEY |
| `account_id` | UUID | Account reference |
| `source` | ENUM | EMAIL, API, MANUAL |
| `status` | ENUM | RECEIVED, PROCESSING, COMPLETED, FAILED, QUARANTINE, DUPLICATE_IGNORED |
| `raw_file_path` | VARCHAR(512) | File location |
| `source_fingerprint` | VARCHAR(128) | Dedup hash |
| `metadata` | JSONB | Sender, filename, row counts |

---

#### `search_terms_v2`
V2 normalized search term data.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | PRIMARY KEY |
| `account_id` | UUID | Account reference |
| `ingestion_id` | UUID | FK → ingestion_events_v2 |
| `report_date` | DATE | Report date |
| `campaign_name` | VARCHAR(512) | Campaign |
| `ad_group_name` | VARCHAR(512) | Ad group |
| `search_term` | TEXT | Search term |
| `impressions` | INTEGER | Impressions |
| `clicks` | INTEGER | Clicks |
| `spend` | DECIMAL | Spend |
| `sales_7d` | DECIMAL | 7-day attributed sales |

---

#### `beta_signups`
Landing page beta access requests.

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | PRIMARY KEY |
| `name` | VARCHAR(255) | User name |
| `email` | VARCHAR(255) | UNIQUE email |
| `role` | VARCHAR(50) | seller, agency, inhouse, other |
| `accounts` | VARCHAR(20) | 1, 2-5, 6-20, 20+ |
| `monthly_spend` | VARCHAR(50) | Spend tier |
| `goal` | TEXT | Free text |
| `source` | VARCHAR(50) | landing_page |
| `status` | VARCHAR(20) | pending, contacted, approved, declined |

---

## 4. Core Modules Reference

### 4.1 `core/postgres_manager.py`

**Class**: `PostgresManager`

Central database interface with connection pooling.

| Method | Purpose |
|--------|---------|
| `__init__(db_url)` | Initialize pool, run schema migration |
| `_get_connection()` | Context manager for connections |
| `save_raw_search_term_data(df, client_id)` | Save daily STR data with deduplication |
| `reaggregate_target_stats(client_id, weeks)` | Rebuild weekly stats from raw daily data |
| `save_target_stats_batch(df, client_id)` | Save search term report (legacy) |
| `get_target_stats_df(client_id)` | Get all target stats as DataFrame |
| `log_actions(actions, client_id, batch_id)` | Log optimization actions |
| `get_action_impact(client_id, before_days, after_days)` | Get impact analysis data |
| `save_category_mapping(df, client_id)` | Save SKU→category mapping |
| `save_bulk_mapping(df, client_id)` | Save ID mappings for bulk export |

**Configuration Constants**:
- `BID_VALIDATION_CONFIG`: CPC match thresholds, impression thresholds
- `HARVEST_VALIDATION_CONFIG`: Spend drop thresholds, migration tiers

---

### 4.2 `core/data_hub.py`

**Class**: `DataHub`

Central data management for session state.

| Method | Purpose |
|--------|---------|
| `upload_search_term_report(file)` | Parse/validate STR, save to DB |
| `upload_advertised_product_report(file)` | Parse advertised products |
| `upload_bulk_id_mapping(file)` | Parse bulk ID sheet |
| `upload_category_mapping(file)` | Parse category mappings |
| `load_from_database(account_id)` | Load 4 weeks of data from DB |
| `get_enriched_data()` | Get merged dataset |
| `get_summary()` | Get data statistics |

---

### 4.3 `core/bulk_validation.py`

Amazon bulk file format validation.

| Function | Purpose |
|----------|---------|
| `validate_bulk_file(df)` | Validate bulk export compliance |
| `check_required_columns(df)` | Verify required columns exist |
| `validate_entity_types(df)` | Check entity types are valid |

---

## 5. Features Modules Reference

### 5.1 `features/optimizer.py`

**Main optimization engine** - 2,474 lines

| Function | Purpose |
|----------|---------|
| `prepare_data(df, config)` | Validate/prepare data for optimization |
| `calculate_account_benchmarks(df, config)` | CVR benchmarks, dynamic thresholds |
| `identify_harvest_candidates(df, config, matcher)` | Find high-performing terms to harvest |
| `identify_negative_candidates(df, config, harvest_df)` | Find bleeders to negate |
| `calculate_bid_optimizations(df, config)` | Calculate bid adjustments by bucket |
| `enrich_with_ids(df, bulk)` | Map recommendations to Amazon IDs |
| `run_simulation(...)` | Forecast bid change impact |

**Configuration**: `DEFAULT_CONFIG` dict with thresholds for harvest, bids, negatives.

---

### 5.2 `features/impact_dashboard.py`

**Impact measurement UI** - 3,254 lines

| Function | Purpose |
|----------|---------|
| `render_impact_dashboard()` | Main render function |
| `_fetch_impact_data(client_id, ...)` | Cached data fetcher |
| `_render_hero_banner(...)` | "Did optimizations make money?" section |
| `_render_what_worked_card(...)` | Offensive/Defensive wins |
| `_render_value_breakdown_section(...)` | Impact by action type |
| `compute_confidence(actions_df)` | Z-score based confidence calculation |
| `get_maturity_status(action_date, ...)` | Check if action has matured |

**Configuration**: `IMPACT_WINDOWS` with horizon settings (14D, 30D, 60D).

---

### 5.3 `features/executive_dashboard.py`

**Executive Dashboard UI** - Main command center.

| Function/Class | Purpose |
|----------------|---------|
| `ExecutiveDashboard` | Main class managing the dashboard state and rendering. |
| `run()` | Main entry point; renders headers, filters, and grid layout. |
| `_render_kpi_cards(...)` | Renders top-row metrics with gradient styles. |
| `_render_performance_scatter(...)` | Plots ROAS vs CVR quadrants (Stars, Scale, Profit, Cut). |
| `_render_quadrant_donut(...)` | Donut chart showing revenue share by performance quadrant. |
| `_render_spend_breakdown(...)` | "Where The Money Is" Efficiency Index bar chart. |
| `_render_decision_timeline(...)` | Interactive timeline of optimization actions. |

**Key Components**:
- **Consolidated Data**: Merges `target_stats` (performance), `actions_log` (decisions), and `account_health` (scores).
- **Premium Palette**: Uses custom `COLORS` dictionary (Cyan/Emerald/Amber/Rose) defined locally for strict brand control.
- **Panel Containers**: Wraps charts in `st.container(border=True)` for consistent styling.

---

### 5.3 `features/bulk_export.py`

Amazon bulk file generators.

| Function | Purpose |
|----------|---------|
| `generate_negatives_bulk(neg_kw, neg_pt)` | Generate negative keywords bulk file |
| `generate_bids_bulk(bids_df)` | Generate bid updates bulk file |
| `generate_harvest_bulk(harvest_df, ...)` | Generate harvest campaign structure |
| `validate_negatives_bulk(df)` | Validate export compliance |

---

### 5.4 `features/assistant.py`

AI Strategist chat interface.

| Function | Purpose |
|----------|---------|
| `render_assistant()` | Main chat UI |
| `get_platform_context()` | Build context for Claude |
| `process_user_message(msg)` | Send to Anthropic API |

---

## 6. UI Layer Reference

### 6.1 `ui/layout.py`

| Function | Purpose |
|----------|---------|
| `setup_page()` | Inject CSS styling |
| `render_sidebar(navigate_to)` | Account selector, navigation menu |
| `render_home()` | Home dashboard with insights |

### 6.2 `ui/theme.py`

**Class**: `ThemeManager`

Brand color management.

| Constant | Value | Usage |
|----------|-------|-------|
| `PRIMARY` | #5B556F | Main purple |
| `SECONDARY` | #8F8CA3 | Slate accent |
| `ACCENT` | #22d3ee | Cyan highlights |
| `SUCCESS` | #22c55e | Green indicators |
| `DANGER` | #ef4444 | Red warnings |

---

## 7. Data Flow & Session State

### 7.1 Session State Keys

| Key | Type | Purpose |
|-----|------|---------|
| `active_account_id` | str | Currently selected account |
| `active_account_name` | str | Display name |
| `unified_data` | dict | All loaded datasets |
| `optimizer_results` | dict | Harvest, Negative, Bid results |
| `pending_actions` | list | Actions awaiting save |
| `current_module` | str | Current page/tab |

### 7.2 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA FLOW                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Upload (Data Hub)                                               │
│      │                                                           │
│      ▼                                                           │
│  DataHub.upload_search_term_report()                            │
│      │                                                           │
│      ├──────────────────────────────────────────────────────────►│
│      │                                                           │
│      │  ┌─────────────────────────┐   ┌─────────────────────┐   │
│      │  │ RAW DAILY STORAGE       │   │ WEEKLY AGGREGATION   │   │
│      │  │ raw_search_term_data DB │   │ target_stats DB      │   │
│      │  │ (preserves daily rows)  │   │ (aggregated by week) │   │
│      │  └─────────────────────────┘   └─────────────────────┘   │
│      │                                                           │
│      ▼                                                           │
│  Session State: st.session_state.unified_data['str']            │
│      │                                                           │
│      ├──────────────────────────────────────────────────────┐   │
│      │                                                       │   │
│      ▼                                                       ▼   │
│  Optimizer Module                              Impact Dashboard  │
│      │                                               │           │
│      ▼                                               │           │
│  optimizer.prepare_data()                            │           │
│  optimizer.identify_harvest_candidates()             │           │
│  optimizer.identify_negative_candidates()            │           │
│  optimizer.calculate_bid_optimizations()             │           │
│      │                                               │           │
│      ▼                                               │           │
│  Session State: pending_actions                      │           │
│      │                                               │           │
│      ▼ (User confirms save)                          │           │
│  PostgresManager.log_actions() ──► actions_log DB   │           │
│                                         │            │           │
│                                         ▼            ▼           │
│                           PostgresManager.get_action_impact()    │
│                                         │                        │
│                                         ▼                        │
│                               Impact Dashboard Display           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Action Storage & Impact Tracking

### 8.1 How Actions Are Stored

1. **User runs optimizer** → Results stored in `st.session_state['pending_actions']`
2. **User navigates away** → Confirmation dialog appears
3. **User clicks "Save to History"** → `PostgresManager.log_actions()` called
4. **Each action logged to `actions_log` table** with:
   - `batch_id`: Groups actions for undo
   - `action_type`: HARVEST, NEGATIVE, BID_CHANGE
   - `target_text`: The keyword/term
   - `old_value` / `new_value`: Before/after values
   - `reason`: Why recommendation was made

### 8.2 Impact Calculation Flow

```python
# 1. Get actions with before/after windows
impact_df = postgres_manager.get_action_impact(
    client_id=account_id,
    before_days=14,
    after_days=14
)

# 2. Calculate decision impact per action
# decision_impact = observed_after_sales - expected_after_sales
# expected_after_sales = before_sales * (after_days / before_days)

# 3. Apply confidence weighting
# confidence_weight = min(1.0, before_clicks / 15)
# final_impact = decision_impact * confidence_weight

# 4. Calculate statistical confidence (z-score)
# z = mean_impact / (std / sqrt(n))
# confidence_pct = stats.norm.cdf(z) * 100
```

---

## 9. Scripts Reference

### 9.1 `/migrations/` (Database Migrations)

| File | Purpose |
|------|---------|
| `001_ingestion_v2_schema.sql` | V2 ingestion tables |
| `002_org_users_schema.sql` | Organizations, Users, Roles |
| `003_add_password_security.sql` | Password requirements |
| `004_account_access_overrides.sql` | Per-account permissions |
| `add_cst_column.sql` | Add customer_search_term column |
| `create_beta_signups.sql` | Beta signup table |

### 9.2 `/tests/` (Diagnostic Scripts)

| File | Purpose |
|------|---------|
| `bulk_validation_spec.py` | Validation architecture tests |
| `test_prd_compliance.py` | PRD requirement validation |
| `verify_impact_values.py` | Impact calculation verification |
| `check_impact.py` | Quick impact query |

### 9.3 `/scripts/` (Utility Scripts)

| File | Purpose |
|------|---------|
| `validate_roas_attribution.py` | ROAS attribution verification |
| `decompose_market_impact.py` | Market factor analysis |
| `final_validation.py` | End-to-end validation |

---

## 10. Authentication & User Management

### 10.1 Auth Service (`auth/service.py`)

| Function | Purpose |
|----------|---------|
| `authenticate(email, password)` | Verify credentials |
| `create_user(org_id, email, password, role)` | Create new user |
| `get_user_permissions(user_id)` | Get role + overrides |
| `check_account_access(user_id, account_id)` | Verify account access |

### 10.2 Role Hierarchy

| Role | Level | Capabilities |
|------|-------|--------------|
| OWNER | 4 | Full access, billing, delete org |
| ADMIN | 3 | User management, all accounts |
| OPERATOR | 2 | Run optimizer, export, view all |
| VIEWER | 1 | Read-only access |

### 10.3 Override Rules
- Overrides can only **downgrade** access (ADMIN→OPERATOR, OPERATOR→VIEWER)
- Enforced by database trigger `enforce_override_downgrade`
- UI hides accounts with NO ACCESS override

---

## Appendix: Quick Reference

### A. Environment Variables

```bash
DATABASE_URL=postgresql://user:pass@host:5432/db
ANTHROPIC_API_KEY=sk-ant-...
RAINFOREST_API_KEY=...
```

### B. Running the App

```bash
cd desktop
./run.sh
# Or directly:
streamlit run ppcsuite_v4_ui_experiment.py
```

### C. Common Queries

```sql
-- Get action impact for account
SELECT * FROM actions_log WHERE client_id = 'account_id';

-- Get recent target stats
SELECT * FROM target_stats 
WHERE client_id = 'account_id' 
ORDER BY start_date DESC 
LIMIT 1000;

-- Check bulk mappings
SELECT * FROM bulk_mappings WHERE client_id = 'account_id';
```

---

**Document maintained by**: Engineering Team  
**For questions**: Refer to `APP_FLOW.md` for user flows, `METHODOLOGY.md` for calculation details.
