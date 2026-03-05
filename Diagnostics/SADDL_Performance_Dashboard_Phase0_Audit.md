# SADDL Performance Dashboard — Phase 0 Audit
Date: 2026-02-23  
Scope audited: **live** `Account Overview` and `Diagnostics` routes only

## 1) Live Routing Confirmed
- `Account Overview` route: `ppcsuite_v4_ui_experiment.py:1748` -> `run_performance_hub()` -> `ui/client_report_page.py:1174` (`run()`)
- `Diagnostics` route: `ppcsuite_v4_ui_experiment.py:1762` -> `run_diagnostics_hub()` -> `features/diagnostics/control_center.py:27` (`render_control_center`)

## 2) Data Queries and Supabase Calls Inventory
Note: there are **no direct Supabase SDK calls** (`supabase-py`) in these tabs.  
Supabase/Postgres access is abstracted through `get_db_manager()` -> `PostgresManager` when `DATABASE_URL` is set (`app_core/db_manager.py:1986`).

### 2.1 Account Overview (current)

#### A) Query chain in Account Overview
- `ui/client_report_page.py:1246` -> `ExecutiveDashboard._fetch_data(...)`
- `features/executive_dashboard.py:26` `_fetch_and_process_stats(...)`:
  - `db.get_target_stats_df(client_id)`
  - Source SQL (Postgres): `app_core/postgres_manager.py:1113`
  - Tables: `target_stats`
- `features/executive_dashboard.py:563` `_fetch_impact_data(...)`:
  - `db.get_action_impact(client_id, before_days, after_days)`
  - `db.get_impact_summary(client_id, before_days, after_days)`
  - Source: `features/impact/data/fetchers.py:13`
  - Postgres SQL roots: `app_core/postgres_manager.py:2121`, `app_core/postgres_manager.py:3331`
  - Tables: `actions_log`, `target_stats`
- `features/executive_dashboard.py:582`:
  - `db.get_latest_raw_data_date(client_id)`
  - Source SQL: `app_core/postgres_manager.py:1081`
  - Table: `raw_search_term_data`
- `ui/client_report_page.py:1260` fallback loader:
  - `DataHub.load_from_database(account_id)` (`app_core/data_hub.py:490`)
  - Reads recent `start_date` windows from `target_stats`
  - Pulls: `get_target_stats_by_account`, `get_bulk_mapping`, `get_advertised_product_map`, `get_category_mappings`
  - Tables touched: `target_stats`, `bulk_mappings`, `advertised_product_cache`, `category_mappings`
- `features/report_card.py:163` inside `analyze(...)`:
  - `db_manager.get_action_impact(...)`, `get_latest_raw_data_date(...)` for decision ROI/spend efficiency
- `features/report_card.py:1785` helper:
  - `db_manager.get_account_health(client_id)` -> `account_health_metrics`
- `ui/client_report_page.py:913` share feature:
  - `db_manager.save_shared_report(...)`
  - Table: `shared_reports`

#### B) SQL methods used by Account Overview (effective)
- `get_target_stats_df` (`target_stats`)
- `get_action_impact` (`actions_log`, `target_stats`)
- `get_impact_summary` (derived from `get_action_impact`)
- `get_latest_raw_data_date` (`raw_search_term_data`)
- `get_target_stats_by_account` (`target_stats`)
- `get_bulk_mapping` (`bulk_mappings`)
- `get_advertised_product_map` (`advertised_product_cache`)
- `get_category_mappings` (`category_mappings`)
- `get_account_health` (`account_health_metrics`)
- `save_shared_report` (`shared_reports`)

### 2.2 Diagnostics (current)

#### A) Query chain in Diagnostics
- `features/diagnostics/control_center.py:52-60` calls:
  - `compute_health_score`
  - `generate_primary_diagnosis`
  - `get_revenue_breakdown`
  - `get_bsr_trend`
  - `get_bsr_traffic_overlay`
  - `detect_cvr_divergence`
  - `get_optimization_performance`
  - `generate_multi_dimensional_actions`
  - `get_asin_action_table`
  - all from `utils/diagnostics.py`
- `features/diagnostics/control_center.py:62`:
  - `fetch_impact_data(...)` -> `db.get_action_impact`, `db.get_impact_summary`

#### B) Raw SQL functions in `utils/diagnostics.py`
- `_resolve_scoped_account_id`: `sc_raw.spapi_account_links`
- `get_analysis_anchor_date`: `sc_analytics.account_daily`, `sc_raw.sales_traffic`, `sc_raw.bsr_history`, `public.raw_search_term_data`
- `fetch_signal_view` / `fetch_all_signal_views`:
  - Views: `sc_analytics.signal_demand_contraction`, `sc_analytics.signal_organic_decay`, `sc_analytics.signal_non_advertised_winners`, `sc_analytics.signal_harvest_cannibalization`, `sc_analytics.signal_over_negation`
- `compute_health_score`:
  - `sc_analytics.account_daily` (sales/tacos/organic_share)
  - `sc_raw.bsr_history` (rank)
- `diagnose_root_causes`:
  - `sc_raw.bsr_history`
  - `sc_raw.sales_traffic`
  - `public.raw_search_term_data`
- `compute_bsr_roas_correlation`:
  - `sc_raw.bsr_history`
  - `public.raw_search_term_data`
- `detect_cvr_divergence`:
  - `sc_raw.sales_traffic`
  - `public.raw_search_term_data`
- `get_asin_action_table`:
  - `sc_raw.sales_traffic`
  - `sc_raw.bsr_history`
- `get_session_trend`: `sc_analytics.account_daily`
- `get_cvr_trend`: `sc_raw.sales_traffic`
- `get_revenue_breakdown`: `sc_analytics.account_daily`
- `get_bsr_trend`: `sc_raw.bsr_history`
- `get_bsr_traffic_overlay`:
  - `sc_analytics.account_daily`
  - `public.raw_search_term_data`
- `get_optimization_performance`: `public.actions_log`
- `identify_brutal_underperformers`: `public.raw_search_term_data`

## 3) Existing Charts, Visualizations, and Metric Calculations

### 3.1 Account Overview visuals
- KPI cards: `features/executive_dashboard.py:637` (`Spend`, `Revenue`, `ROAS`, `CVR` + secondary metrics)
- Gauges: `features/executive_dashboard.py:770`, `:896`
  - `Account Health`, `Decision ROI`, `Spend Efficiency`
- Scatter quadrant: `features/executive_dashboard.py:1000`
- Quadrant donut: `features/executive_dashboard.py:1347`
- Match type table: `features/executive_dashboard.py:1433`
- Spend efficiency breakdown bar: `features/executive_dashboard.py:1240`
- Decision timeline: `features/executive_dashboard.py:1589`
- Decision impact summary card: `features/executive_dashboard.py:1862`
- Client Report custom visuals:
  - Match type table aligned: `ui/client_report_page.py:1011`
  - Spend breakdown aligned bar: `ui/client_report_page.py:1054`

### 3.2 Diagnostics visuals
- Health card (composite + 4 metric cards): `components/diagnostic_cards.py:40`
- Visual proof charts: `components/diagnostic_cards.py:117`
  - Paid vs Organic revenue (stacked area)
  - Organic/Paid traffic + BSR overlay
  - Organic vs Paid CVR trend
  - ROAS attribution waterfall (imported)
- Action cards: `components/diagnostic_cards.py:239`
- ASIN action dataframe: `components/diagnostic_cards.py:282`

### 3.3 Existing metric formulas reusable
- ROAS/CVR/CPC derivations in `_fetch_and_process_stats`: `features/executive_dashboard.py:39-41`
- Impact maturity/validation filtering: `features/executive_dashboard.py:579-617`, `features/diagnostics/control_center.py:67-99`
- Match-type classification utility usage: `features/executive_dashboard.py:48`
- Health-score computations (different logic variants):
  - Diagnostics health score: `utils/diagnostics.py:336`
  - Report card health score helper: `features/report_card.py:1633`, `:1785`

## 4) Shared Utilities Across Account Overview and Diagnostics
- `get_db_manager`: `app_core/db_manager.py:1986`
- Impact fetch abstraction: `features/impact/data/fetchers.py:13`
- Currency helper: `utils/formatters.get_account_currency`
- Impact/maturity logic:
  - `features.impact_metrics.ImpactMetrics`
  - `features.impact_dashboard.get_maturity_status`
- Streamlit cached data patterns: `@st.cache_data` in fetchers and dashboard loaders
- Session-state driven account context:
  - `active_account_id`
  - `test_mode`
  - impact horizon/validated flags

## 5) PRD Component Reuse Matrix (Phase 0 Decision)
Legend:
- `A` = exists and reusable
- `B` = exists but must be extended
- `C` = build fresh

### Tab 1 — Business Overview
- Account Health Score gauge: `B` (existing gauges exist, but scoring model/weights/data-floor/default targets are different)
- Driver callouts (score contributors): `C`
- Business KPI strip (spec-specific metric set): `B` (existing KPI cards exist; requires new metrics and card semantics)
- 14D/30D/60D trend toggle across 3 required charts: `B`
- Paid vs Organic Sales trend: `A` (exists in Diagnostics; reusable chart structure)
- TACOS trend + target line: `C` (new chart logic needed)
- Paid/Organic Sessions split chart: `B` (traffic split exists in Diagnostics overlay)
- Product-level detailed table with default `TACOS desc`: `B` (table patterns exist; data model and columns need extension)

### Tab 2 — Product
- Parent selector: `C`
- Product metrics strip: `C`
- Child ASIN variation table: `B` (ASIN table exists in Diagnostics but not full product breakdown)
- Product trends (Sales/TACOS/CVR with 14/30/60): `C`
- Product intelligence flags: `C`

### Tab 3 — Inventory Overview
- Portfolio inventory summary cards: `C`
- Days-of-cover horizontal bars: `C`
- Inventory table including `Ad Spend Blocked`: `C`
- Restock alerts sorted by urgency: `C`

### Tab 4 — Intelligence
- Existing intelligence panel (promote V2.1): `A` (reuse diagnostics/optimizer intelligence components)
- Decision attribution funnel: `C`
- Impact-over-time line (INVENTORY_RISK + HALO_ACTIVE): `B` (impact timeline exists, but flag-specific series is new)
- Decision log with filters and server-side query: `C`

### Tab 5 — PPC Overview
- PPC health strip: `B` (can reuse executive KPI card system)
- Campaign table grouped by Exact/Broad/Auto: `B` (match-type tables exist, grouping/columns/status logic new)
- Keyword diagnostics top-20 spend with flags: `B` (query/table patterns exist in diagnostics)
- Optimization history (last 5 runs + pending window): `B` (impact summary exists, presentation and state rules new)

## 6) Phase 0 Conclusion
- Audit complete for required scope.
- Reuse opportunities are strongest in:
  - Data fetch primitives (`get_target_stats_df`, `get_action_impact`, `get_impact_summary`)
  - Chart/table rendering patterns (Executive Dashboard + Diagnostics cards)
  - Maturity/validation filters
- Highest new-build areas:
  - Product tab
  - Inventory tab
  - Intelligence decision log/funnel
  - Centralized metrics module and score guardrails required by PRD

