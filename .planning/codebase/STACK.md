# Technology Stack

**Analysis Date:** 2026-02-24

## Languages

**Primary:**
- Python 3.x - Core backend logic, ML processing, and API orchestration
  - Used in: `pipeline/`, `features/`, `app_core/`, `db/`
  - Modern Python patterns with `from __future__ import annotations` for forward-compatibility

**Secondary:**
- SQL - Data warehouse and analytics queries via PostgreSQL
  - Used in: `db/migrations/`
  - Dialects: PostgreSQL with psycopg2 driver

## Runtime

**Environment:**
- Python interpreter (version unspecified in requirements.txt but 3.8+ implied)

**Package Manager:**
- pip (Python package index)
- Lockfile: `requirements.txt` present (no poetry.lock or pipenv.lock)

## Frameworks

**Core Web Application:**
- Streamlit >=1.28.0 - Interactive web UI for PPC dashboard
  - Configuration: `.streamlit/config.toml` - Custom theme (wine/purple accent), disabled file watchers for deployment stability
  - Purpose: Serves as the entire application frontend without traditional separate frontend/backend split

**Data Processing & Analysis:**
- pandas >=2.0.0 - Data manipulation, time series analysis, aggregation
- numpy >=1.24.0 - Numerical computing, array operations
- scikit-learn >=1.3.0 - Clustering and machine learning (used for keyword clustering)

**Visualization:**
- plotly >=5.17.0 - Interactive charts and performance dashboard visualizations

**Database & ORM:**
- psycopg2-binary ==2.9.9 - PostgreSQL driver (low-level SQL execution)
- supabase >=2.0.0 - PostgreSQL hosting provider and client library
- (No traditional ORM like SQLAlchemy - raw SQL via psycopg2)

**Testing & Quality:**
- pytest ==8.3.0 - Unit and integration test runner
- pytest-mock ==3.14.0 - Mocking library for test fixtures

**Build & Deployment:**
- python-dotenv ==1.0.1 - Environment variable loading from `.env` files
- apscheduler ==3.10.4 - Scheduled job execution (pipeline scheduling)

**API & HTTP:**
- requests >=2.31.0 - HTTP client for external API calls (Amazon SP-API, Anthropic, Rainforest)
- requests-aws4auth ==1.3.1 - AWS Signature Version 4 signing for SP-API authentication

**Authentication & Security:**
- bcrypt >=4.0.1 - Password hashing for user authentication

**Document Generation:**
- fpdf2 >=2.7.0 - PDF report generation
- html2image >=2.0.0 - HTML-to-image conversion for embedded charts
- kaleido >=0.2.0 - Plotly static image export (used with plotly for PDF reports)

**Excel Support:**
- openpyxl >=3.1.0 - Modern Excel file reading/writing (.xlsx)
- xlsxwriter >=3.1.0 - Excel file generation with formatting

## Key Dependencies

**Critical for Core Operations:**
- **streamlit** - Without this, there is no UI. This is the entire application framework.
- **pandas + numpy** - Data pipeline depends entirely on these for ETL transformations
- **psycopg2-binary** - Direct PostgreSQL connectivity; loss means data access failure
- **supabase** - Manages cloud database hosting and provides client library
- **requests + requests-aws4auth** - All external API integrations depend on this for authenticated calls

**Infrastructure & Orchestration:**
- **apscheduler** - Enables scheduled pipeline runs (daily SP-API data pulls)
- **python-dotenv** - Loads secrets and configuration from environment files

**External Service Integration:**
- **api/anthropic_client.py** uses Claude Sonnet API for AI-powered analysis
- **api/rainforest_client.py** uses Rainforest API for ASIN product lookups with caching

## Configuration

**Environment Variables (Required):**
- `LWA_CLIENT_ID` - Amazon Login with Amazon (OAuth) Client ID
- `LWA_CLIENT_SECRET` - LWA Client Secret
- `LWA_REFRESH_TOKEN_UAE` - OAuth refresh token for UAE marketplace
- `AWS_ACCESS_KEY_ID` - AWS credentials for SP-API signing
- `AWS_SECRET_ACCESS_KEY` - AWS secret for SP-API signing
- `DATABASE_URL` - PostgreSQL connection string (Supabase)
- `AWS_REGION` - AWS region (default: eu-west-1)
- `MARKETPLACE_ID_UAE` - Amazon marketplace ID (default: A2VIGQ35RCS4UG for UAE)
- `APP_BASE_URL` - Application base URL for deployment (auto-detected if not set)

**Optional Environment Variables:**
- `AD_CLIENT_ID` / `CLIENT_ID` - Public client identifier for account mapping
- `SPAPI_ACCOUNT_ID` - Internal account ID for SP-API
- `ANTHROPIC_API_KEY` - Claude API key for cluster analysis
- `RAINFOREST_API_KEY` - Rainforest API key for ASIN lookups

**Environment File Locations:**
- `.env` - Project root
- `.env` - Parent directory (checked in pipeline config)
- `.streamlit/secrets.toml` - Streamlit secrets (alternative to env vars)

**Streamlit Configuration:**
- `.streamlit/config.toml` - Theme colors, UI preferences, file watching disabled for stability
  - Theme: Dark mode with wine/purple accent (#5B556F)
  - Client: Sidebar always visible, minimal toolbar
  - Server: No file watching (improves deployment stability)

**Build Configuration:**
- No build config files detected (Streamlit runs directly from Python)
- No docker, webpack, or compilation step

## Platform Requirements

**Development Environment:**
- Python 3.8+ (inferred from `from __future__ import annotations` usage)
- PostgreSQL-compatible database (Supabase or local PostgreSQL)
- Network access to:
  - Amazon SP-API endpoints (https://sellingpartnerapi-eu.amazon.com)
  - Anthropic Claude API (https://api.anthropic.com)
  - Rainforest API (https://api.rainforestapi.com)
  - Amazon OAuth endpoint (https://api.amazon.com)

**Production / Deployment:**
- **Primary:** Streamlit Cloud (saddle-adpulse.streamlit.app) - auto-detected deployment target
- **Alternative:** Docker/Kubernetes (APP_BASE_URL can override, file watcher disabled for this)
- **Database:** Supabase PostgreSQL (cloud-hosted)
- **Scheduled Tasks:** APScheduler for daily pipeline orchestration (must run continuously)

**Data Storage:**
- Primary: PostgreSQL (Supabase) - All application data and analytics
- Caching: SQLite local cache (data/asin_cache.db) - ASIN lookup caching to minimize API costs
- Session Storage: Streamlit session_state (in-memory per user session)

## Performance Characteristics

**Scaling Constraints:**
- Streamlit is single-threaded per session; concurrent users must run separate processes
- SP-API Data Kiosk queries are rate-limited; pipeline includes exponential backoff retry logic (max 4 retries with 2^attempt sleep)
- Rainforest API rate limited to 2 requests/second with rate limiter in `api/rainforest_client.py`
- ASIN cache has 30-day TTL to reduce redundant API calls

## Known External API Dependencies

**Amazon SP-API:**
- Endpoint: https://sellingpartnerapi-eu.amazon.com
- Auth: LWA (Login with Amazon) + AWS SigV4 signing
- Throttling: Retries with exponential backoff built-in

**Anthropic Claude:**
- Endpoint: https://api.anthropic.com/v1/messages
- Model: claude-sonnet-4-20250514 (default, configurable)
- Max tokens: 4000 per request

**Rainforest Amazon Product API:**
- Endpoint: https://api.rainforestapi.com/request
- Rate: 2 requests/second (enforced)
- Cache: 30-day TTL for lookups

## Deployment Notes

**Streamlit Cloud Detection:**
- Auto-detects production vs development via `get_base_url()` in `config/deployment.py`
- Checks environment hostname, headless mode, and fallback to `APP_BASE_URL` env var
- Fallback URL: http://localhost:8501 for local development

**Database Migrations:**
- Run via `python db/migrate.py` in deployment process
- 6 migration files in sequence (001-006) + rollback script (999)
- Schemas: `sc_raw` (raw data), `sc_analytics` (derived metrics)

---

*Stack analysis: 2026-02-24*
