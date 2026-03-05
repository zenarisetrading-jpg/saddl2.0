# SADDL Diagnostic Tool — Context Variables
## Environment-Specific Configuration for Claude Code

**Version:** 1.0  
**Date:** February 2026  
**Purpose:** Provide exact table names, column mappings, and integration patterns from existing SADDL system

---

## 1. Environment Variables

### 1.1 Current Status

```
✅ DATABASE_URL (pooler connection) - SET
❌ DATABASE_URL_DIRECT (direct connection) - NOT SET
✅ LWA_CLIENT_ID - SET
✅ LWA_CLIENT_SECRET - SET
✅ LWA_REFRESH_TOKEN_UAE - SET
✅ AWS_ACCESS_KEY_ID - SET
✅ AWS_SECRET_ACCESS_KEY - SET
```

### 1.2 Required Action

**Add to .env file:**
```bash
DATABASE_URL_DIRECT=postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres
```

**How to get:**
1. Go to Supabase Dashboard
2. Settings → Database → Connection string
3. Click "Direct connection" tab (NOT pooler)
4. Copy the full URL
5. Paste into .env

**Why needed:**
- Migrations require direct connection (pooler doesn't support schema modifications)
- BSR pipeline backfill uses direct connection for long-running operations
- Aggregator computations use direct connection

---

## 2. Existing Database Schema

### 2.1 Public Schema Tables (DO NOT MODIFY)

**Ad Console Data:**
```sql
-- Search term level daily data
public.raw_search_term_data (129,527 rows)
  Columns: report_date, client_id, campaign_name, customer_search_term, 
           spend, sales, clicks, impressions, orders

-- Target level weekly aggregates  
public.target_stats (163,305 rows)
  Columns: start_date, end_date, client_id, campaign_name, ad_group_name,
           target_text, match_type, spend, sales, clicks, impressions, orders

-- ASIN to campaign mapping (not regularly updated)
public.advertised_product_ca... (4,508 rows)
  Note: Not used in current reporting, stale data
```

**Impact Dashboard Data:**
```sql
-- Action logging and impact tracking
public.actions_log (6,452 rows)
  Columns: 
    - action_date (DATE)
    - client_id (TEXT)
    - target_text (TEXT)
    - campaign_name (TEXT)
    - ad_group_name (TEXT)
    - match_type (TEXT)
    - action_type (TEXT) -- 'BID_INCREASE', 'BID_DECREASE', 'NEGATIVE_ADDED', etc.
    - old_value (NUMERIC)
    - new_value (NUMERIC)
    - reason (TEXT)
    - [other columns for validation and tracking]
```

**Other Tables:**
- `accounts` (10 rows) - Client account metadata
- `account_health_metrics` (6 rows) - Health scores
- `amazon_accounts` (4 rows) - Amazon seller account linking
- `bulk_mappings` (432,258 rows) - Bulk ASIN/keyword mappings
- `category_mappings` (504 rows) - Product categories
- `shared_reports` (25 rows) - Shared report configs
- `users` (12 rows) - User accounts
- `organizations` (10 rows) - Organization hierarchy
- `beta_signups` (7 rows) - Beta user tracking

---

### 2.2 New Schemas (You Create These)

**sc_raw (Seller Central Raw Data):**
```sql
-- Already created by existing pipeline
sc_raw.sales_traffic (330 rows → will be ~8,000 after backfill)
sc_raw.pipeline_log (5 rows → audit trail)

-- You create in Phase 1
sc_raw.bsr_history (0 rows → populate in Phase 1)
```

**sc_analytics (Computed Analytics):**
```sql
-- Already created by existing pipeline
sc_analytics.account_daily (populated)
sc_analytics.osi_index (placeholder)

-- You create in Phase 1-2
sc_analytics.bsr_trends (VIEW)
sc_analytics.signal_demand_contraction (VIEW)
sc_analytics.signal_organic_decay (VIEW)
sc_analytics.signal_non_advertised_winners (VIEW)
sc_analytics.signal_harvest_cannibalization (VIEW)
sc_analytics.signal_over_negation (VIEW)
```

---

## 3. Impact Dashboard Integration

### 3.1 Table Access Pattern

**Read-Only Access to Impact Dashboard:**

```python
from app_core.db_manager import get_db_manager

# Get database manager (handles test_mode flag)
db = get_db_manager(test_mode=False)

# Fetch impact data
impact_df = db.get_action_impact(
    client_id='s2c_uae_test',  # Zenarise UAE account
    before_days=14,
    after_days=14  # or 30, 60
)

# Fetch summary stats
summary = db.get_impact_summary(
    client_id='s2c_uae_test',
    before_days=14,
    after_days=14
)
```

### 3.2 Impact Summary Structure

**Returned from `db.get_impact_summary()`:**

```python
{
    'total_actions': int,           # Count of optimization actions
    'roas_before': float,           # Average ROAS before actions
    'roas_after': float,            # Average ROAS after actions
    'roas_lift_pct': float,         # % change in ROAS
    'incremental_revenue': float,   # Revenue impact
    'p_value': float,               # Statistical significance
    'is_significant': bool,         # p < 0.05
    'confidence_pct': float,        # Confidence level
    'implementation_rate': float,   # % of actions implemented
    'confirmed_impact': int,        # Actions with confirmed results
    'pending': int,                 # Actions still measuring
    'win_rate': float,              # % of winning actions
    'winners': int,                 # Count of wins
    'losers': int,                  # Count of losses
    'by_action_type': {             # Breakdown by action type
        'BID_DECREASE': {...},
        'BID_INCREASE': {...},
        'NEGATIVE_ADDED': {...},
        # etc.
    }
}
```

### 3.3 Integration in Diagnostic Tool

**Usage Example:**

```python
# In diagnostics overview page
def render_optimization_context(client_id: str):
    """Show recent optimization performance as context for signals."""
    
    db = get_db_manager(test_mode=False)
    summary = db.get_impact_summary(client_id, before_days=14, after_days=14)
    
    st.markdown(f"""
    ### Recent Optimization Performance
    
    Last 14 days: {summary['total_actions']} actions validated  
    Win Rate: {summary['win_rate']:.0f}% ({summary['winners']}/{summary['total_actions']})  
    Avg Impact: {summary['roas_lift_pct']:+.1f}% ROAS lift
    
    **Interpretation:**  
    Your optimizations ARE working. The ROAS decline is driven by external 
    demand contraction, not failed optimization.
    
    [View Details in Impact Dashboard →](/impact)
    """)
```

**DO NOT:**
- ❌ Write to `actions_log` table
- ❌ Modify impact calculation logic
- ❌ Duplicate validation code
- ❌ Create your own optimization tracking

**DO:**
- ✅ Read from Impact Dashboard via `get_db_manager()`
- ✅ Display summary stats as context
- ✅ Link to Impact Dashboard for details
- ✅ Reference validation results in signal recommendations

---

## 4. Existing Code Structure

### 4.1 Directory Layout

```
saddl/
├── app_core/
│   ├── postgres_manager.py      # Database interface (uses psycopg2)
│   ├── db_manager.py            # Wrapper that selects postgres vs sqlite
│   └── utils.py                 # Shared utilities
├── features/
│   ├── impact/                  # Impact Dashboard module
│   │   ├── main.py
│   │   ├── data/
│   │   │   ├── fetchers.py      # Cached data fetching
│   │   │   └── transforms.py
│   │   ├── components/
│   │   │   ├── hero.py
│   │   │   ├── analytics.py
│   │   │   └── tables.py
│   │   └── utils.py
│   ├── optimizer/               # Optimization engine
│   ├── bids_tab.py             # Existing tabs
│   ├── harvest_tab.py
│   ├── negatives_tab.py
│   └── [other features]
├── pipeline/
│   ├── auth.py                  # SP-API auth (existing)
│   ├── data_kiosk.py            # SC data pull (existing)
│   ├── runner.py                # Pipeline orchestration (existing)
│   └── [you add bsr_pipeline.py here]
└── ppcsuite_v4_ui_experiment.py # Main Streamlit entry point
```

### 4.2 Page Structure Pattern

**Existing pages follow this pattern:**

```python
import streamlit as st
import sys
import os
from pathlib import Path

# Add current directory to path to fix imports on Cloud
current_dir = Path(__file__).parent.absolute()
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# ==========================================
# PAGE CONFIGURATION (Must be very first ST command)
# ==========================================
st.set_page_config(
    page_title="Saddle AdPulse",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🚀",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

import pandas as pd
from datetime import datetime
from app_core.db_manager import get_db_manager

# Feature imports
from features.impact.data.fetchers import fetch_impact_data

# ... rest of page code
```

**Your diagnostic pages should follow same pattern.**

---

### 4.3 Database Connection Pattern

**Existing pattern (use this):**

```python
from app_core.db_manager import get_db_manager

# Get manager
db = get_db_manager(test_mode=False)

# Query using manager methods
df = db.execute_query("SELECT * FROM sc_analytics.signal_demand_contraction")

# Or use direct cursor for custom queries
with db.get_cursor() as cur:
    cur.execute("""
        SELECT * FROM sc_analytics.bsr_trends
        WHERE report_date >= CURRENT_DATE - 7
    """)
    results = cur.fetchall()
```

**Note:** `db_manager.py` wraps `postgres_manager.py` and handles:
- Connection pooling
- Test mode vs production mode switching
- Query caching
- Error handling

**For your new code:**
- Use existing `get_db_manager()` pattern
- Don't create new connection management
- Follow existing caching patterns with `@st.cache_data`

---

### 4.4 Caching Pattern

**Existing pattern (use this):**

```python
import streamlit as st

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_signal_data(
    client_id: str,
    cache_version: str = "v1"
) -> pd.DataFrame:
    """
    Cached fetcher for diagnostic signals.
    
    Args:
        client_id: Account ID
        cache_version: Version string for cache invalidation
    
    Returns:
        DataFrame with signal data
    """
    db = get_db_manager(test_mode=False)
    query = """
        SELECT * FROM sc_analytics.signal_demand_contraction
        WHERE report_date >= CURRENT_DATE - 7
    """
    return db.execute_query(query)
```

**Cache invalidation:**
- `cache_version` parameter changes when data updates
- `ttl=3600` expires cache after 1 hour
- Manual: `st.cache_data.clear()`

---

## 5. Client Configuration

### 5.1 Active Client

**Current testing client:**
```
client_id: 's2c_uae_test'
marketplace_id: 'A2VIGQ35RCS4UG'
marketplace_name: 'United Arab Emirates'
```

**All queries should filter by this client_id initially.**

### 5.2 Future Multi-Client Support

When diagnostic tool needs to support multiple clients:

```python
# Get client list from accounts table
clients = db.execute_query("""
    SELECT client_id, account_name 
    FROM accounts 
    WHERE status = 'active'
""")

# Add client selector in sidebar
selected_client = st.sidebar.selectbox(
    "Select Account",
    options=clients['client_id'].tolist(),
    format_func=lambda x: clients[clients['client_id'] == x]['account_name'].iloc[0]
)
```

**For Phase 1-3:** Hard-code `client_id='s2c_uae_test'`  
**For Phase 4+:** Add multi-client support

---

## 6. BSR API Configuration

### 6.1 Endpoint Details

**Catalog Items API:**
```
Base URL: https://sellingpartnerapi-eu.amazon.com
Endpoint: /catalog/2022-04-01/items/{asin}
Method: GET
Rate Limit: 5 requests/second
Authentication: AWS Signature v4 + LWA token
```

**Query Parameters:**
```
marketplaceIds: A2VIGQ35RCS4UG
includedData: salesRanks
```

**Response Structure:**
```json
{
  "asin": "B0DSFZK5W7",
  "salesRanks": [
    {
      "title": "Sports Nutrition Whey Protein Powders",
      "link": "https://...",
      "rank": 12450,
      "classificationRanks": [
        {
          "title": "Health & Personal Care",
          "link": "https://...",
          "rank": 45230
        }
      ]
    }
  ]
}
```

**Extract:**
- Primary category: `salesRanks[0].title`
- Primary rank: `salesRanks[0].rank`
- Store in `sc_raw.bsr_history` with both category name and rank

---

### 6.2 Rate Limiting Implementation

**Use existing pattern from data_kiosk.py:**

```python
import time

def fetch_bsr_batch(asins: list, rate_limit_delay: float = 0.2):
    """
    Fetch BSR for multiple ASINs with rate limiting.
    
    Args:
        asins: List of ASINs to fetch
        rate_limit_delay: Seconds between requests (0.2 = 5/sec)
    """
    results = []
    for asin in asins:
        bsr_data = fetch_single_asin_bsr(asin)
        results.append(bsr_data)
        time.sleep(rate_limit_delay)  # 5 req/sec = 0.2s delay
    return results
```

---

## 7. Testing Configuration

### 7.1 Test Data Setup

**For local testing without hitting APIs:**

```python
# tests/fixtures/test_data.py
import pandas as pd
from datetime import date, timedelta

def create_test_sales_traffic():
    """Create sample sales/traffic data for testing."""
    dates = pd.date_range(end=date.today(), periods=30)
    asins = ['B0ASIN001', 'B0ASIN002', 'B0ASIN003']
    
    data = []
    for d in dates:
        for asin in asins:
            data.append({
                'report_date': d,
                'marketplace_id': 'A2VIGQ35RCS4UG',
                'child_asin': asin,
                'ordered_revenue': 100 + (hash(str(d) + asin) % 200),
                'units_ordered': 10 + (hash(str(d) + asin) % 20),
                'sessions': 50 + (hash(str(d) + asin) % 100),
                'unit_session_percentage': 8.0 + (hash(str(d) + asin) % 5),
            })
    
    return pd.DataFrame(data)

def create_test_bsr_data():
    """Create sample BSR data for testing."""
    dates = pd.date_range(end=date.today(), periods=30)
    asins = ['B0ASIN001', 'B0ASIN002', 'B0ASIN003']
    
    data = []
    for d in dates:
        for asin in asins:
            data.append({
                'report_date': d,
                'marketplace_id': 'A2VIGQ35RCS4UG',
                'asin': asin,
                'category_name': 'Sports Nutrition Whey Protein',
                'rank': 15000 + (hash(str(d) + asin) % 10000),
            })
    
    return pd.DataFrame(data)
```

### 7.2 Mock API Responses

**For testing BSR pipeline without API calls:**

```python
# tests/mocks/sp_api_mocks.py
def mock_bsr_response(asin: str):
    """Mock BSR API response."""
    return {
        "asin": asin,
        "salesRanks": [
            {
                "title": "Sports Nutrition Whey Protein Powders",
                "rank": 12450
            }
        ]
    }
```

---

## 8. Deployment Checklist

**Before handing to Claude Code, verify:**

```
□ DATABASE_URL_DIRECT added to .env
□ All .env variables confirmed present
□ Baseline schema captured (run script from guardrails doc)
□ Git branch created: feature/diagnostic-tool
□ Test database backup taken
□ Existing Impact Dashboard tested and working
□ Existing pages (campaigns, targets) tested and working
□ All 5 documents reviewed:
  1. PRD v2
  2. Backend Architecture
  3. Frontend Architecture
  4. Implementation Guardrails
  5. This Context Variables doc
```

---

## 9. Quick Reference

### 9.1 Key Tables Summary

| Table | Schema | Purpose | Access |
|---|---|---|---|
| actions_log | public | Impact Dashboard tracking | READ ONLY |
| raw_search_term_data | public | Ad console data | READ ONLY |
| target_stats | public | Target performance | READ ONLY |
| sales_traffic | sc_raw | SC ASIN-level data | READ/WRITE |
| bsr_history | sc_raw | BSR tracking | READ/WRITE (you create) |
| account_daily | sc_analytics | Daily rollups | READ/WRITE |
| signal_* | sc_analytics | Detection views | READ (you create) |

### 9.2 Key Functions Summary

| Function | Module | Purpose |
|---|---|---|
| get_db_manager() | app_core.db_manager | Get database instance |
| get_action_impact() | postgres_manager | Fetch impact data |
| get_impact_summary() | postgres_manager | Fetch impact summary |
| fetch_impact_data() | features.impact.data.fetchers | Cached impact fetch |

### 9.3 Key Constants

```python
CLIENT_ID = 's2c_uae_test'
MARKETPLACE_ID = 'A2VIGQ35RCS4UG'
BSR_RATE_LIMIT = 0.2  # seconds between requests
CACHE_TTL = 3600  # 1 hour
```

---

*Context Variables v1.0 — complete environment configuration for safe build.*
