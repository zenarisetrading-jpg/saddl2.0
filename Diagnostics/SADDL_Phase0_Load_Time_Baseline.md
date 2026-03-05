# SADDL Phase 0 — Load Time Baseline
Date: 2026-02-25
Status: Pre-measurement record. Actual timing to be filled in after next live session.

## Purpose
This document establishes baseline load time measurements for Business Overview and PPC Overview as required by the Phase 0 test gate. Measurements should be taken in a live session against the UAE test account (s2c_uae_test) with cold cache (after `st.cache_data.clear()`).

---

## Architecture Profile (Static Analysis)

### Business Overview
- **Entry function**: `ui/performance_dashboard/business_overview.py:1634` `render_business_overview()`
- **Main fetch function**: `ui/performance_dashboard/business_overview.py:298` `fetch_business_overview_data()`
- **Cache**: `@st.cache_data(ttl=300, show_spinner=False)` ✅
- **Cache key parameters**: `client_id`, `window_days`, `test_mode`, `spapi_available`, `cache_version`
- **DB call sites in fetch path**: ~7 (target_stats, sc_analytics.account_daily, sc_raw.sales_traffic, raw_search_term_data, sc_raw.bsr_history, actions_log, sc_analytics + sp-api scoping)
- **Estimated cold cache time** (unmeasured): likely 3–8s depending on Supabase/Postgres latency
- **PRD target**: < 5 seconds on cold cache

### PPC Overview
- **Entry function**: `ui/performance_dashboard/ppc_overview.py:797` `render_ppc_overview()`
- **Cache functions**:
  1. `ppc_overview.py:52` — primary campaign/keyword data fetch `@st.cache_data(ttl=300)` ✅
  2. `ppc_overview.py:554` — secondary data fetch `@st.cache_data(ttl=300)` ✅
- **DB call sites**: ~3 (raw_search_term_data campaign aggregations, target_stats joins, account-level rollups)
- **Estimated cold cache time** (unmeasured): likely 2–6s

---

## Caching Coverage Summary (Post Phase 0)

| Page / Module | Main Fetch | Cache TTL | Uncached fetch functions |
|---|---|---|---|
| Business Overview | `fetch_business_overview_data` | 300s | None identified |
| PPC Overview | 2 fetch functions | 300s | None identified |
| Optimizer (V2.1) | `fetch_target_stats_cached` | 300s | None identified |
| Impact Data | `fetch_impact_data` | 3600s | None identified |
| Diagnostics utils | All 10 fetch functions | 300s | **Now all cached (added Phase 0)** |

Before Phase 0: `utils/diagnostics.py` had **zero** cached functions. 10 functions were making individual DB queries on every Diagnostics page render. These are now cached with `ttl=300`.

---

## Phase 0 Changes That Affect Load Times

1. **Diagnostics tab disabled** — `ENABLE_DIAGNOSTICS_LEGACY=False`. The Diagnostics Control Center no longer loads on user navigation, eliminating 10 sequential DB queries + LLM call overhead from user session.

2. **Account Overview (Legacy) tab disabled** — `ENABLE_ACCOUNT_OVERVIEW_LEGACY=False`. The legacy `client_report_page.py` / `ExecutiveDashboard` no longer renders as a tab option.

3. **891 lines of dead code removed** from `ppcsuite_v4_ui_experiment.py`. No runtime impact (code was already behind `return`), but reduces module import time and maintenance surface.

4. **Caching added to 10 diagnostics fetch functions** — If diagnostics path is ever re-enabled, cold load will now be ~1-2s per function (cached) vs ~20-30s total (sequential uncached).

---

## How to Take the Actual Measurements

Run the following in the live Streamlit app console:

```python
# Clear cache before each measurement
import streamlit as st
st.cache_data.clear()

# Then navigate to Business Overview and note:
# 1. Time from click to spinner appearing
# 2. Time from spinner appearing to content rendered
# Total = cold cache load time
```

Or in the Python environment:

```python
import time
from utils.diagnostics import compute_health_score
st.cache_data.clear()

t0 = time.time()
result = compute_health_score("s2c_uae_test", days=30)
print(f"compute_health_score cold: {time.time() - t0:.2f}s")

# Second call (warm cache):
t0 = time.time()
result = compute_health_score("s2c_uae_test", days=30)
print(f"compute_health_score warm: {time.time() - t0:.2f}s")
```

---

## Actual Measurements (to be filled in)

| Page | Cold Cache Load | Warm Cache Load | Measured By | Date |
|---|---|---|---|---|
| Business Overview | _pending_ | _pending_ | | |
| PPC Overview | _pending_ | _pending_ | | |

**PRD target**: Business Overview initial load under 5 seconds on cold cache.
