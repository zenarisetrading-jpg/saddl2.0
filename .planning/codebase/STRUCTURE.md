# Codebase Structure

**Analysis Date:** 2026-02-24

## Directory Layout

```
/Users/zayaanyousuf/Documents/Amazon PPC/saddle/saddle/desktop/
├── ppcsuite_v4_ui_experiment.py     # Main Streamlit entry point
├── .env*                            # Environment configuration (secrets)
├── .streamlit/                      # Streamlit config
├── .planning/                       # GSD planning artifacts
│
├── app_core/                        # Core application services (data, auth, db)
│   ├── __init__.py
│   ├── auth/                        # Authentication service & middleware
│   ├── data_hub.py                  # Central data management (upload orchestration)
│   ├── data_loader.py               # CSV/file ingestion & column mapping
│   ├── db_manager.py                # SQLite database manager
│   ├── postgres_manager.py          # PostgreSQL (Supabase) database manager (178KB)
│   ├── bulk_validation.py           # Bulk file validation logic
│   ├── mapping_engine.py            # Column/entity mapping logic
│   ├── roas_attribution.py          # ROAS calculation engine
│   ├── roas_waterfall_v33.py        # Waterfall visualization data
│   ├── timeline_roas.py             # Timeline ROAS tracking
│   ├── account_utils.py             # Account management helpers
│   ├── platform_service.py          # Platform integration logic
│   ├── optimization_types.py        # Type definitions for optimization
│   ├── seeding.py                   # Database seeding (initial data)
│   └── utils.py                     # Shared utilities
│
├── api/                             # External service clients
│   ├── __init__.py
│   ├── rainforest_client.py         # ASIN/competitor data fetching
│   └── anthropic_client.py          # LLM integration (Claude)
│
├── features/                        # Feature modules (business logic)
│   ├── __init__.py
│   ├── _base.py                     # Base class for all features
│   ├── constants.py                 # Feature-wide constants
│   │
│   ├── optimizer_v2/                # V2.0 Optimizer UX shell
│   │   ├── main.py                  # Entry point delegates to optimizer_shared
│   │   ├── entry.py                 # Config/setup for V2 shell
│   │   └── runner.py                # Optimization run orchestration
│   │
│   ├── optimizer_shared/            # Core optimization algorithms (shared by all optimizer versions)
│   │   ├── __init__.py              # OptimizerModule main orchestrator (255 lines)
│   │   ├── core.py                  # Shared constants, data prep, benchmarks, health calc
│   │   ├── simulation.py            # Simulation engine (forecast impact)
│   │   ├── logging.py               # Optimization event logging
│   │   ├── intelligence.py          # AI-powered insights
│   │   ├── data_access.py           # Data fetching helpers
│   │   │
│   │   ├── strategies/              # Pluggable optimization strategies
│   │   │   ├── bids.py              # Bid optimization algorithm
│   │   │   ├── harvest.py           # Exact match harvest detection
│   │   │   └── negatives.py         # Negative keyword identification
│   │   │
│   │   └── ui/                      # Optimizer-specific UI components
│   │       ├── landing.py           # Config form & data selection
│   │       ├── results.py           # Results dashboard renderer
│   │       ├── components.py        # Shared UI widgets
│   │       ├── charts.py            # Plotly chart builders
│   │       ├── heatmap.py           # Action audit heatmap
│   │       └── tabs/                # Tabbed result views
│   │           ├── bids.py          # Bid recommendations tab
│   │           ├── harvest.py       # Harvest opportunities tab
│   │           ├── negatives.py     # Negative keywords tab
│   │           ├── audit.py         # Heatmap/audit trail tab
│   │           └── downloads.py     # Bulk export tab
│   │
│   ├── dashboard/                   # Business overview dashboard
│   │   ├── __init__.py
│   │   ├── business_overview.py     # Bridge to performance_dashboard (compatibility)
│   │   ├── metrics.py               # KPI calculations
│   │   ├── constants.py             # Dashboard constants
│   │   └── data_access.py           # Dashboard data queries
│   │
│   ├── diagnostics/                 # Diagnostic signals & health checks
│   │   ├── __init__.py
│   │   ├── control_center.py        # Main diagnostics UI
│   │   ├── overview_old.py          # Legacy overview component
│   │   ├── signals_old.py           # Legacy signal display
│   │   ├── trends_old.py            # Legacy trend component
│   │   └── styles.py                # Diagnostic UI styling
│   │
│   ├── impact/                      # Impact dashboard (storytelling, waterfall)
│   │   ├── __init__.py
│   │   ├── impact_dashboard.py      # Main impact analysis UI (180KB)
│   │   ├── impact_metrics.py        # Impact calculation logic
│   │   ├── components/              # Impact visualization components
│   │   │   ├── roas_waterfall.py    # Waterfall chart
│   │   │   └── timeline.py          # Timeline visualization
│   │   ├── diagnostics.py           # Impact-specific diagnostics
│   │   ├── utils/                   # Impact utilities
│   │   │   ├── __init__.py
│   │   │   └── export_utils.py      # Data export helpers
│   │   └── ...
│   │
│   ├── assistant.py                 # AI assistant (110KB)
│   ├── asin_mapper.py               # ASIN competitor mapping
│   ├── bulk_export.py               # Bulk file export logic
│   ├── creator.py                   # Campaign creator/generator
│   ├── debug_ui.py                  # Debug utilities
│   ├── executive_dashboard.py       # Executive summary
│   ├── kw_cluster.py                # Keyword clustering analysis
│   ├── platform_admin.py            # Admin features
│   ├── report_card.py               # Account health report (88KB)
│   ├── simulator.py                 # Optimization simulator (legacy)
│   └── ...
│
├── ui/                              # Frontend (Streamlit components & layout)
│   ├── __init__.py
│   ├── layout.py                    # Page setup, sidebar navigation, home page (40KB)
│   ├── theme.py                     # Theme manager (CSS injection)
│   ├── readme.py                    # README display
│   ├── onboarding.py                # Onboarding wizard
│   ├── account_manager.py           # Account selector UI
│   ├── action_confirmation.py       # Action confirmation dialog
│   ├── data_hub.py                  # Data hub UI wrapper
│   │
│   ├── auth/                        # Authentication UI
│   │   ├── __init__.py
│   │   └── login.py                 # Login form
│   │
│   ├── components/                  # Reusable UI components
│   │   ├── __init__.py
│   │   ├── diagnostic_cards.py      # Diagnostic metric cards
│   │   └── icons.py                 # Custom SVG icons
│   │
│   └── performance_dashboard/       # Performance analytics dashboard
│       ├── __init__.py
│       ├── business_overview.py     # Business KPIs
│       └── ...
│
├── pipeline/                        # Data ingestion (legacy, local executor)
│   ├── __init__.py
│   ├── README.md
│   ├── runner.py                    # Pipeline orchestration
│   ├── aggregator.py                # Data aggregation logic
│   ├── transform.py                 # ETL transformations
│   ├── db_writer.py                 # Write to database
│   ├── auth.py                      # Pipeline auth (API keys)
│   ├── bsr_pipeline.py              # BSR history ingestion
│   ├── data_kiosk.py                # Data Kiosk API integration
│   ├── config.py                    # Pipeline config
│   └── scheduler.py                 # Job scheduling
│
├── pipelines/                       # Data ingestion (cloud-ready, Deno)
│   ├── __init__.py
│   ├── sp_api_client.py             # Amazon Selling Partner API client
│   ├── spapi_pipeline.py            # SP-API data ingestion pipeline (17.6KB)
│   └── scheduler.py                 # Cloud scheduler
│
├── db/                              # Database schema & migrations
│   ├── migrations/                  # SQL migration files (numbered)
│   │   ├── 001_create_sc_raw.sql    # Create raw data tables
│   │   ├── 002_create_sc_analytics.sql
│   │   ├── 003_add_bsr_history.sql  # BSR tracking
│   │   ├── 004_signal_views.sql     # Analytics views
│   │   ├── 005_account_scoping.sql  # Multi-tenant isolation
│   │   └── 006_refresh_signal_views_with_mapping.sql
│   └── migrate.py                   # Migration runner
│
├── config/                          # Application configuration
│   ├── __init__.py
│   ├── features.py                  # Feature flags (FeatureFlags class)
│   ├── design_system.py             # Design tokens, colors, typography
│   └── deployment.py                # Deployment config (env detection)
│
├── utils/                           # Shared utility modules
│   ├── __init__.py
│   ├── metrics.py                   # PPC metric calculations
│   ├── formatters.py                # Currency, percentage formatting
│   ├── matchers.py                  # ExactMatcher (keyword deduplication)
│   ├── validators.py                # Data validators
│   ├── diagnostics.py               # Diagnostic helpers
│   ├── amazon_oauth.py              # OAuth flow (Amazon MWS)
│   └── email_sender.py              # Email utilities
│
├── components/                      # Reusable Vue/UI component definitions
│   ├── __init__.py
│   ├── diagnostic_cards.py
│   └── icons.py
│
├── supabase/                        # Supabase configuration
│   ├── config.toml                  # Local dev config
│   ├── functions/                   # Edge functions (Deno)
│   │   └── amazon-oauth-callback/   # OAuth callback handler
│   └── .temp/                       # Supabase CLI temp files
│
├── dev_resources/                   # Development utilities
│   ├── documentation/               # Technical specs, design docs
│   ├── migrations/                  # Extra migration scripts
│   ├── scripts/                     # Standalone analysis/admin scripts
│   └── tests/                       # Test utilities & validation specs
│
├── tests/                           # Test suite
│   ├── conftest.py                  # Pytest fixtures & config
│   ├── fixtures/                    # Test data factories
│   ├── pipeline/                    # Pipeline integration tests
│   └── *.py                         # Feature-specific tests
│
├── static/                          # Static assets
├── assets/                          # SVG icons, logos
├── data/                            # Local data directory (not committed)
├── Diagnostics/                     # Diagnostic PRDs & design docs
├── README.md                        # Project overview
└── requirements.txt                 # Python dependencies
```

## Directory Purposes

**app_core:**
- Purpose: Centralized business logic for data management, persistence, and authentication
- Contains: DataHub, database managers, auth service, data validation, mapping
- Key files: `data_hub.py` (session orchestration), `postgres_manager.py` (cloud persistence)

**api:**
- Purpose: External service integrations
- Contains: HTTP clients for Rainforest API (ASIN data), Anthropic LLM
- Key files: `rainforest_client.py` (competitor data), `anthropic_client.py` (AI)

**features:**
- Purpose: Feature-specific business logic and UI
- Contains: Organized by feature (optimizer, dashboard, diagnostics, impact)
- Key files: `optimizer_shared/` (core algorithms), `impact_dashboard.py` (storytelling)

**features/optimizer_shared:**
- Purpose: Reusable optimization algorithms and shared UI
- Contains: Bid/harvest/negative strategies, simulation engine, strategy orchestration
- Key files: `__init__.py` (OptimizerModule), `core.py` (constants, data prep), `strategies/` (algorithms)

**ui:**
- Purpose: Streamlit frontend components and page layout
- Contains: Theme system, sidebar navigation, authentication UI, component library
- Key files: `layout.py` (main page structure), `theme.py` (CSS), `onboarding.py` (wizard)

**pipeline, pipelines:**
- Purpose: Data ingestion from external sources
- `pipeline/`: Local executor (batch jobs, testing)
- `pipelines/`: Cloud-ready (Deno functions, async)
- Key files: `runner.py` (orchestration), `sp_api_client.py` (Amazon API)

**db:**
- Purpose: Database schema and migrations
- Contains: SQL migration files (numbered sequence)
- Key files: `migrations/*.sql` (versioned schema changes)

**config:**
- Purpose: Global configuration and feature flags
- Contains: Feature flag definitions, design tokens, deployment settings
- Key files: `features.py` (FeatureFlags class), `design_system.py` (theme)

**utils:**
- Purpose: Shared utilities used across all layers
- Contains: Formatters, validators, metric calculators, matchers, OAuth
- Key files: `matchers.py` (ExactMatcher), `metrics.py` (PPC calculations)

**tests:**
- Purpose: Test suite and test fixtures
- Contains: Unit tests, integration tests, fixture factories
- Key files: `conftest.py` (pytest setup), `fixtures/` (test data)

**dev_resources:**
- Purpose: Developer tools and documentation
- Contains: Design docs, implementation specs, admin scripts, validation tests
- Key files: `documentation/` (design specs), `scripts/` (analysis tools)

## Key File Locations

**Entry Points:**
- `ppcsuite_v4_ui_experiment.py`: Main Streamlit app (page config, auth, routing)
- `features/optimizer_v2/main.py`: Optimizer UX shell (delegates to optimizer_shared)
- `pipeline/runner.py`: Data pipeline orchestrator

**Configuration:**
- `.env`: Environment variables (secrets, API keys, database URLs)
- `.streamlit/`: Streamlit secrets and config
- `config/features.py`: Feature flags (FeatureFlags class)

**Core Logic:**
- `app_core/data_hub.py`: Session state management and data orchestration (30.6KB)
- `app_core/postgres_manager.py`: Database operations (178KB)
- `features/optimizer_shared/__init__.py`: Optimizer orchestration (255 lines)
- `features/optimizer_shared/strategies/`: Bid, harvest, negative algorithms

**Database:**
- `db/migrations/*.sql`: Schema (6 migrations total)
- `app_core/db_manager.py`: SQLite (local dev)
- `app_core/postgres_manager.py`: PostgreSQL (production)

**Testing:**
- `tests/conftest.py`: Pytest fixtures and configuration
- `tests/fixtures/diagnostic_test_data.py`: Test data factory
- `tests/pipeline/`: Pipeline integration tests

## Naming Conventions

**Files:**
- Feature modules: `{feature_name}.py` (e.g., `impact_dashboard.py`, `bulk_export.py`)
- Strategy modules: `{strategy}.py` in `strategies/` (e.g., `bids.py`, `harvest.py`)
- UI components: `{component_name}.py` prefixed with context (e.g., `diagnostic_cards.py`)
- API clients: `{service}_client.py` (e.g., `rainforest_client.py`)
- Database: `{db_type}_manager.py` (e.g., `postgres_manager.py`)

**Directories:**
- Feature grouping: `features/{feature_name}/` (all code for one feature)
- Sub-module grouping: `{module}/ui/`, `{module}/strategies/`, `{module}/utils/`
- Core services: Top-level `app_core/` (not nested)

**Functions:**
- Public methods: `snake_case` (e.g., `get_enriched_data()`)
- Private methods: `_snake_case` prefix (e.g., `_run_analysis()`)
- Streamlit callbacks: Prefixed with underscore to prevent display (e.g., `_fetch_target_stats_cached()`)

**Variables:**
- Session state keys: `lowercase_with_underscores` (e.g., `active_account_id`, `opt_profile`)
- Constants: `UPPER_CASE` (e.g., `BID_LIMITS`, `CVR_CONFIG`)
- DataFrame columns: Match Amazon's naming (e.g., `Campaign Name`, `Customer Search Term`)

**Types:**
- Dataframe prefixes: `df_` or `{context}_df` (e.g., `df_harvest`, `results_df`)
- Config dictionaries: `{context}_config` (e.g., `optimization_config`, `bid_config`)

## Where to Add New Code

**New Feature:**
- Create directory: `features/{feature_name}/`
- Primary code: `features/{feature_name}/main.py` or `{feature_name}.py`
- UI: `features/{feature_name}/ui.py` or `features/{feature_name}/ui/` (submodule)
- Tests: `tests/features/test_{feature_name}.py`
- Integrate: Add routing in `ppcsuite_v4_ui_experiment.py`

**New Component/Module:**
- Shared between features: Place in `features/optimizer_shared/` or top-level `utils/`
- Feature-specific: Place in `features/{feature_name}/`
- UI-only: Place in `ui/components/`
- Database operations: Place in `app_core/`

**New Optimization Strategy:**
- Location: `features/optimizer_shared/strategies/{strategy_name}.py`
- Pattern: Export main function like `identify_{strategy}_candidates(df, config, ...)`
- Integration: Import in `features/optimizer_shared/__init__.py`, call in `_run_analysis()`

**Utilities:**
- Formatting/calculation helpers: `utils/{domain}.py` (e.g., `utils/metrics.py`)
- Validators: `utils/validators.py`
- Matchers/ML: `utils/matchers.py`

**Configuration:**
- Feature flags: Add to `FeatureFlags.DEFAULTS` in `config/features.py`
- Design tokens: Add to `config/design_system.py`
- Constants: Feature-specific constants in `features/{feature_name}/constants.py`

## Special Directories

**st_env/, venv311/**
- Purpose: Python virtual environments (development and Streamlit Cloud)
- Generated: Yes (created by `python -m venv`)
- Committed: No (in .gitignore)

**.planning/codebase/**
- Purpose: GSD planning artifacts (generated by /gsd:map-codebase)
- Generated: Yes
- Committed: Yes (reference documents)

**supabase/.temp/**
- Purpose: Supabase CLI temporary files and runtime state
- Generated: Yes (by `supabase` CLI)
- Committed: No

**__pycache__/**
- Purpose: Python bytecode cache
- Generated: Yes (automatic)
- Committed: No

**data/, Diagnostics/**
- Purpose: Local development data and diagnostic documents
- Generated: Yes (development artifacts)
- Committed: No (with exceptions for design PRDs)

---

*Structure analysis: 2026-02-24*
