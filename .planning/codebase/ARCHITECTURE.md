# Architecture

**Analysis Date:** 2026-02-24

## Pattern Overview

**Overall:** Layered, feature-driven Streamlit application with clear separation between UI presentation, business logic, data access, and external integrations.

**Key Characteristics:**
- Multi-feature modular architecture with independent feature modules (Optimizer, Dashboard, Diagnostics, Impact)
- Central data hub pattern with session state management for cross-module data sharing
- Database-centric persistence (PostgreSQL via Supabase with fallback to SQLite)
- Pipeline-driven data ingestion from Amazon Selling Partner API and CSV uploads
- Streamlit-based frontend with custom theme and component system

## Layers

**Presentation (UI Layer):**
- Purpose: Render user interface, handle user interactions, manage theme and styling
- Location: `ui/`, `components/`, `.streamlit/`
- Contains: Streamlit pages, custom components, layout logic, theme management
- Depends on: Features layer, Data Hub, Database Manager
- Used by: Main application entry point (`ppcsuite_v4_ui_experiment.py`)

**Features Layer:**
- Purpose: Implement feature-specific business logic (Optimizer, Dashboard, Diagnostics, Impact)
- Location: `features/` (organized by feature: `optimizer_v2/`, `dashboard/`, `diagnostics/`, `impact/`, `optimizer_shared/`)
- Contains: Feature orchestrators, UI rendering specific to features, analysis logic
- Depends on: Core app layer (data hub, database), shared strategies, utilities
- Used by: UI layer through navigation routing

**Shared Strategies Layer:**
- Purpose: Provide reusable optimization algorithms and calculations
- Location: `features/optimizer_shared/` (core logic, strategies, simulation, intelligence)
- Contains: Bid calculation algorithms, harvest candidate identification, negative keyword strategies, simulation engine
- Depends on: Utils (matchers, validators, formatters), constants from core
- Used by: Optimizer features and custom analysis modules

**Core Application Layer (app_core):**
- Purpose: Central data management, database operations, authentication, platform integration
- Location: `app_core/`
- Contains: DataHub (session state + file uploads), DatabaseManager/PostgresManager (persistence), auth service, data loading, mapping engine
- Depends on: External services (API clients), utilities for validation
- Used by: All layers (presentation, features, pipelines)

**Pipeline Layer:**
- Purpose: Batch data ingestion from external sources (Amazon SP-API, BSR, enrichment)
- Location: `pipeline/`, `pipelines/`
- Contains: Pipeline runners, data aggregators, transformers, schedulers, API clients
- Depends on: Core app layer (database writers), external API clients
- Used by: Scheduled execution, manual backfill operations

**Integration Layer:**
- Purpose: Third-party API clients and external service connectors
- Location: `api/`
- Contains: Rainforest ASIN cache client, Anthropic LLM client
- Depends on: External HTTP APIs
- Used by: Features requiring competitive intelligence or AI assistance

**Utilities Layer:**
- Purpose: Shared helpers and validators across all layers
- Location: `utils/`, `config/`
- Contains: Formatters (currency, percentages), metrics calculators, regex matchers, validators, feature flags
- Depends on: Pandas, standard library
- Used by: All layers

**Database Layer:**
- Purpose: Abstract database operations with support for multiple backends
- Location: `app_core/db_manager.py`, `app_core/postgres_manager.py`
- Contains: SQLite and PostgreSQL connection managers, schema management, CRUD operations
- Depends on: sqlite3 (local), psycopg2 (cloud)
- Used by: Core app layer, pipelines

## Data Flow

**User Data Upload Flow:**

1. User uploads CSV files (Search Term Report, Advertised Product Report, Bulk ID Mapping, Category Mapping) via UI
2. Upload captured in `ui/layout.py` → `DataHub.upload_*()` methods
3. DataHub validates and transforms data using `SmartMapper` for column name normalization
4. Enriched data merged and stored in Streamlit `session_state['unified_data']`
5. Data accessible to all features through `DataHub.get_data()` or `DataHub.get_enriched_data()`

**Database Read Flow:**

1. Feature requests data from `DataHub` or directly from `DatabaseManager`/`PostgresManager`
2. For local SQLite: Direct connection via `DatabaseManager` singleton (`get_db_manager()`)
3. For cloud PostgreSQL: Via `PostgresManager` with connection pooling and schema support
4. Data loaded into pandas DataFrames for analysis
5. Results cached in Streamlit session state to minimize database round-trips

**Optimization Analysis Flow:**

1. Landing page (`features/optimizer_shared/ui/landing.py`) captures user config (profile, thresholds)
2. Trigger: User clicks "Analyze" → sets `st.session_state['run_optimizer_refactored'] = True`
3. `OptimizerModule.render_ui()` detects trigger, calls `_run_analysis(df)`
4. Analysis pipeline:
   - `prepare_data()` → data cleaning, date filtering
   - `calculate_account_benchmarks()` → establishes ROAS medians by bucket
   - `identify_harvest_candidates()` → exact match growth opportunities
   - `identify_negative_candidates()` → underperforming keywords
   - `calculate_bid_optimizations()` → bid adjustment recommendations
   - `run_simulation()` → forecast impact of changes
5. Results stored in `st.session_state['optimizer_results_refactored']`
6. Results dashboard (`features/optimizer_shared/ui/results.py`) renders recommendations

**Pipeline Data Ingestion Flow:**

1. Scheduler triggers job (daily/weekly)
2. `pipeline/runner.py` orchestrates pipeline stages:
   - Connect to Amazon SP-API via `pipelines/sp_api_client.py`
   - Fetch raw data (Search Term Reports, Product Targeting, BSR history)
   - Transform data using `pipeline/transform.py`
   - Aggregate by account using `pipeline/aggregator.py`
   - Write to database via `pipeline/db_writer.py`
3. Data scoped by account_id for multi-tenant isolation
4. Historical data retained for trend analysis

**State Management:**

- Global session state: `st.session_state` (Streamlit resets on page refresh)
- Persistent state: Database (accounts, users, optimization history)
- Feature-local state: Feature module caches (session-level optimization results)
- Cross-feature sharing: Via DataHub or session state dictionaries

## Key Abstractions

**DataHub:**
- Purpose: Central gateway for all data access within a session
- Examples: `app_core/data_hub.py` (main class)
- Pattern: Singleton-like pattern through Streamlit session state. Manages upload orchestration, data validation, enrichment, and access
- Methods: `get_data()`, `get_enriched_data()`, `upload_search_term_report()`, `load_from_database()`

**DatabaseManager/PostgresManager:**
- Purpose: Abstract database persistence with consistent interface
- Examples: `app_core/db_manager.py` (SQLite), `app_core/postgres_manager.py` (PostgreSQL)
- Pattern: Implements same interface (`get_db_manager()` singleton returns appropriate impl). Supports upsert logic, connection pooling, schema migrations
- Key methods: `save_optimization_run()`, `get_target_stats_df()`, `update_bid_audit()`

**OptimizerModule:**
- Purpose: Feature orchestrator for bid/harvest/negative optimization
- Examples: `features/optimizer_shared/__init__.py` (main class)
- Pattern: Inherits from `BaseFeature`. Manages UI state, orchestrates strategy modules, synthesizes results
- Key methods: `render_ui()`, `_run_analysis()`, `_sync_config_from_state()`

**Strategy Modules:**
- Purpose: Encapsulate specific optimization algorithms
- Examples: `features/optimizer_shared/strategies/bids.py`, `harvest.py`, `negatives.py`
- Pattern: Pure functions that take DataFrames and config, return recommendation DataFrames
- Used by: OptimizerModule to compose multi-strategy analysis

**ExactMatcher:**
- Purpose: Deduplicate exact match keywords across campaigns/ad groups
- Examples: `utils/matchers.py`
- Pattern: Regex-based similarity matching with configurable threshold
- Used by: Harvest and bid optimization strategies to avoid recommending conflicting actions

**ThemeManager:**
- Purpose: Centralize UI styling and theme application
- Examples: `ui/theme.py`
- Pattern: Static utility class with cached CSS/theme data. Applies to UI via Streamlit `st.markdown(..., unsafe_allow_html=True)`
- Key methods: `apply_css()`, `get_cached_logo()`

## Entry Points

**Main Web Application:**
- Location: `ppcsuite_v4_ui_experiment.py`
- Triggers: `streamlit run ppcsuite_v4_ui_experiment.py`
- Responsibilities:
  - Streamlit page config setup
  - Environment variable loading (.env + Streamlit secrets)
  - Seeding initialization (lazy, cached)
  - Authentication middleware (requires login)
  - Navigation routing between features
  - Sidebar rendering

**Pipeline Runner:**
- Location: `pipeline/runner.py`
- Triggers: Scheduled job or manual execution
- Responsibilities: Orchestrate data ingestion from Amazon SP-API, transform, aggregate, write to database

**Feature Entry Points:**
- Dashboard: `features/dashboard/business_overview.py` (UI entry)
- Diagnostics: `features/diagnostics/` (feature module)
- Impact: `features/impact_dashboard.py` (large analysis module)
- Optimizer V2: `features/optimizer_v2/main.py` → `features/optimizer_shared/__init__.py` (actual logic)

## Error Handling

**Strategy:**
- Streamlit-native warning/error UI (`st.warning()`, `st.error()`)
- Try-catch with user-friendly messages in feature modules
- Database connection fallback (local SQLite if PostgreSQL unavailable)
- Graceful degradation (features disabled if prerequisites missing)

**Patterns:**
- Data validation errors logged and displayed with recovery suggestions
- Database errors caught in connection context managers and rolled back
- Missing data handled by redirecting to data upload flow
- API failures wrapped with retry logic in pipeline

## Cross-Cutting Concerns

**Logging:**
- Approach: Standard Python logging + Streamlit debugging. Pipeline uses `logging` module. UI uses Streamlit containers for progress/status messages
- Location: `features/optimizer_shared/logging.py` for optimization event tracking

**Validation:**
- Approach: Early validation on upload via `SmartMapper` and schema checks. Pre-analysis validation via `prepare_data()`. Strategy-specific validators for edge cases
- Location: `app_core/data_loader.py`, `app_core/bulk_validation.py`, individual strategy modules

**Authentication:**
- Approach: Email-based with optional SSO (Amazon OAuth). Session persistence via database
- Location: `app_core/auth/` (service, middleware, templates)
- Middleware: `require_auth()` decorator validates token and injects user context

**Multi-Tenancy:**
- Approach: Account scoping via `active_account_id` in session state. Database queries filtered by account_id
- Implemented in: Database queries, data hub lookups, optimization runs
- Isolation: Schema-level (Supabase RLS) + application-level (query filters)

---

*Architecture analysis: 2026-02-24*
