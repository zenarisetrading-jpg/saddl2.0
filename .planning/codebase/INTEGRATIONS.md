# Integrations

**Analysis Date:** 2026-02-24

## External APIs

### 1. Amazon SP-API (Selling Partner API)
**Purpose:** Core data ingestion — pulls advertising reports, sales data, traffic metrics
**Auth:** Amazon LWA (Login with Amazon) OAuth 2.0 + AWS Signature v4 (`requests-aws4auth`)
**Client:** `pipeline/` module handles ingestion
**Credentials (env vars):**
- `LWA_APP_ID` — Login with Amazon app ID
- `LWA_CLIENT_SECRET` — LWA OAuth client secret
- `REFRESH_TOKEN` — Per-account refresh token for SP-API
- `AWS_ACCESS_KEY` / `AWS_SECRET_KEY` — AWS IAM credentials for request signing
- `SP_API_ENDPOINT` — Regional endpoint (e.g., `https://sellingpartnerapi-eu.amazon.com`)
**Scheduling:** `APScheduler` (v3.10.4) orchestrates pipeline runs
**Key pipeline files:**
- `pipeline/runner.py` — main orchestrator
- `pipeline/bsr_pipeline.py` — BSR (Best Seller Rank) data ingestion
**Rate Limiting:** SP-API has strict rate limits; pipeline handles throttling
**Data pulled:** Search term reports, keyword performance, campaign stats, ASIN traffic

---

### 2. Anthropic Claude API
**Purpose:** AI-powered cluster analysis and strategic recommendations for search term grouping
**Client:** `api/anthropic_client.py` (`AnthropicClient` class)
**Model:** `claude-sonnet-4-20250514` (configurable via constructor)
**Base URL:** `https://api.anthropic.com/v1/messages`
**Credentials:** `ANTHROPIC_API_KEY` (env var)
**Usage pattern:**
```python
client = AnthropicClient(api_key=os.environ['ANTHROPIC_API_KEY'])
result = client.analyze_clusters(cluster_df)  # Returns opportunities + mismatches
```
**Called from:** Features module (keyword clustering / search term analysis)
**Transport:** Direct `requests` HTTP calls (no Anthropic SDK)

---

### 3. Rainforest API
**Purpose:** ASIN product lookups (title, category, pricing) for context enrichment
**Client:** `api/rainforest_client.py` (`RainforestClient` + `ASINCache` classes)
**Credentials:** `RAINFOREST_API_KEY` (env var)
**Caching:** SQLite cache at `data/asin_cache.db` with 30-day TTL to minimize API costs
**Cache schema:**
```sql
CREATE TABLE asin_lookups (
    asin TEXT,
    marketplace TEXT,
    data TEXT,
    lookup_date TIMESTAMP,
    PRIMARY KEY (asin, marketplace)
)
```
**Default marketplace:** `AE` (UAE/Dubai — primary market)
**Used for:** Enriching optimization reports with product context

---

## Database

### Supabase (PostgreSQL)
**Purpose:** Primary data store for all PPC metrics, optimization history, and action logs
**Driver:** `psycopg2-binary` (v2.9.9) — direct SQL, no ORM
**Client wrapper:** `app_core/db_manager.py` (`DatabaseManager` / `get_db_manager()`)
**Credentials (env vars):**
- `DATABASE_URL` — Full PostgreSQL connection string (Supabase)
- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_KEY` — Supabase anon/service key
**Python SDK:** `supabase>=2.0.0` (used alongside direct psycopg2)
**Key operations:**
- `save_target_stats_batch(df, client_id)` — bulk insert PPC metrics
- `get_recent_action_dates(client_id)` — cooldown lookups
- `get_target_14d_roas(client_id)` — 14-day ROAS for bid calculations
- `get_commerce_metrics_by_target(client_id)` — commerce data enrichment

**Migration files:** `db/migrations/` — raw SQL migration scripts
**Migration runner:** `db/migrate.py`

### SQLite (Local Cache)
**Purpose:** Local ASIN lookup cache only (`data/asin_cache.db`)
**Used by:** `api/rainforest_client.py`
**Not used for:** Primary application data

---

## Authentication

### App-Level Auth
**Library:** `bcrypt>=4.0.1`
**Module:** `app_core/auth.py`
**Pattern:** Username/password authentication with bcrypt hashing
**Session management:** `st.session_state` (Streamlit session)
**Storage:** User accounts stored in Supabase PostgreSQL

### Amazon LWA OAuth
**Flow:** Refresh token flow (no interactive login in runtime)
**Used by:** SP-API pipeline for per-account data ingestion
**Token storage:** Environment variables / `.env` file (not in DB)

---

## Scheduled Jobs

### APScheduler
**Version:** v3.10.4
**Purpose:** Orchestrates SP-API pipeline runs on schedule
**Scheduler type:** BackgroundScheduler (runs within Streamlit process or separate process)
**Configured in:** `pipeline/runner.py`
**Jobs:**
- Periodic SP-API data pull (frequency TBD per deployment)
- BSR pipeline runs (`pipeline/bsr_pipeline.py`)

---

## Environment Configuration

All credentials managed via `.env` file + `python-dotenv` (v1.0.1).

### Full Environment Variable Reference
| Variable | Service | Required |
|----------|---------|----------|
| `DATABASE_URL` | Supabase PostgreSQL | Yes |
| `SUPABASE_URL` | Supabase | Yes |
| `SUPABASE_KEY` | Supabase | Yes |
| `ANTHROPIC_API_KEY` | Anthropic Claude | Yes |
| `RAINFOREST_API_KEY` | Rainforest API | Yes |
| `LWA_APP_ID` | Amazon SP-API | Yes |
| `LWA_CLIENT_SECRET` | Amazon SP-API | Yes |
| `REFRESH_TOKEN` | Amazon SP-API | Yes |
| `AWS_ACCESS_KEY` | Amazon SP-API | Yes |
| `AWS_SECRET_KEY` | Amazon SP-API | Yes |
| `SP_API_ENDPOINT` | Amazon SP-API | Yes |

### `.env` File
- Loaded via `load_dotenv()` at startup
- **Not committed to git** (`.gitignore` assumed)
- Required for both application runtime and test execution

---

## Deployment

**No containerization found** (no Dockerfile, docker-compose.yml)
**Config:** `config/deployment.py` — deployment-specific settings
**Feature flags:** `config/features.py` — runtime feature toggles
**Design system:** `config/design_system.py` — UI theming constants
**Run command:** `streamlit run <entry_point>.py`
**Environment:** Local development / cloud VM (no CI/CD pipeline detected)
