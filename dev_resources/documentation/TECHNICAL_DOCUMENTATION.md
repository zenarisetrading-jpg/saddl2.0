# PPC Optimizer - Technical Documentation

**Version**: 3.0  
**Last Updated**: January 6, 2026

---

## 1. Technology Stack

### 1.1 Current Architecture (V4)
High-performance Python application with server-side rendering.

| Layer | Technology |
|-------|------------|
| **Language** | Python 3.9+ |
| **UI Framework** | Streamlit (Reactive server-side UI) |
| **Data Processing** | Pandas (Vectorized operations) |
| **Visualization** | Plotly (Interactive charts) |
| **Database** | PostgreSQL 15+ |
| **DB Interface** | Psycopg2 / SQLAlchemy |
| **External APIs** | Amazon Bulk API (manual upload), Rainforest API (ASIN enrichment) |
| **Statistics** | SciPy (z-score confidence calculations) |

### 1.2 Future Architecture (V5 Roadmap)
Decoupled full-stack for scalability and multi-user support.

* **Frontend**: React.js 18+ with Tailwind CSS & Shadcn/UI
* **Backend**: FastAPI (async, type-safe REST API)
* **Task Queue**: Celery + Redis
* **Infrastructure**: Dockerized microservices

---

## 2. Backend Structure & Data Model

### 2.1 Database Schema (PostgreSQL)

#### **Table: `target_stats` (Granular Performance)**
Primary storage for aggregated search term and keyword performance.

| Column | Type | Purpose |
|--------|------|---------|
| `id` | SERIAL | PRIMARY KEY |
| `client_id` | VARCHAR | Account owner (REFERENCES accounts) |
| `start_date` | DATE | Week start (Monday), INDEXED |
| `campaign_name` | VARCHAR | Normalized campaign name, INDEXED |
| `ad_group_name` | VARCHAR | Normalized ad group name |
| `target_text` | TEXT | Keyword, Search Term, or PT expression, INDEXED |
| `customer_search_term` | TEXT | Raw CST for matching (added Jan 2026) |
| `match_type` | VARCHAR | exact, broad, phrase, auto, pt |
| `spend` | DECIMAL | Total ad spend |
| `sales` | DECIMAL | Attributed sales |
| `clicks` | INTEGER | Total clicks |
| `orders` | INTEGER | Conversion count |
| `impressions` | INTEGER | Total impressions |

#### **Table: `actions_log` (Optimizer History)**
Audit trail for every optimization recommendation.

| Column | Type | Purpose |
|--------|------|---------|
| `action_id` | UUID | PRIMARY KEY |
| `client_id` | VARCHAR | Account reference |
| `action_date` | TIMESTAMP | When action was logged |
| `action_type` | VARCHAR | NEGATIVE, NEGATIVE_ADD, HARVEST, BID_CHANGE |
| `campaign_name` | VARCHAR | Target campaign |
| `ad_group_name` | VARCHAR | Target ad group |
| `target_text` | TEXT | Optimized term |
| `match_type` | VARCHAR | Keyword match type |
| `old_value` | DECIMAL | Previous bid/state |
| `new_value` | DECIMAL | New bid/state |
| `reason` | TEXT | Optimization rationale |

#### **Secondary Tables**
* **`accounts`**: Client metadata, target ACoS, currency
* **`bulk_mappings`**: Campaign Name ↔ Amazon ID sync
* **`category_mappings`**: SKU groupings for roll-up reporting

---

## 3. Impact Calculation Engine

### 3.1 Before/After Windowing
Dynamic windowing anchored to action date:

```
T0 = action_date
Baseline = T0 - 14 days (pre-optimization)
Measurement = T0 + 14 days (post-optimization)
```

**Maturity Calculation** (Fixed Jan 2026):
```sql
-- Calendar days from action to latest data (not report count)
actual_after_days = latest_date - action_date + 1

-- Action is "mature" if full window is available
is_mature = actual_after_days >= 14
```

### 3.2 Confidence Weighting (Added Jan 2026)
Low-click decisions are dampened to prevent noise:

| Column | Formula | Purpose |
|--------|---------|---------|
| `confidence_weight` | `min(1.0, clicks/15) * penalty` | 0-1 weight based on data volume & source |
| `penalty` | `0.5` if `match_level='ad_group'` | 50% reduction for fallback data |
| `final_decision_impact` | `decision_impact × confidence_weight` | Dampened impact value |
| `impact_tier` | See below | Classification label |

**Impact Tier Classification:**
| Tier | Criteria | Treatment |
|------|----------|-----------|
| **Excluded** | before_clicks < 5 | Not counted |
| **Directional** | 5 ≤ clicks < 15 | Partial weight (33%-99%) |
| **Validated** | clicks ≥ 15 | Full weight (100%) |

### 3.3 Decision Impact Formulas (Technical Implementation)

The system applies specific formulas based on the `action_type` and `validation_status`:

1.  **Standard Bid Actions**: `decision_impact = observed_after_sales - expected_sales`
    *   `expected_sales` uses Counterfactual Logic (see Methodology).
2.  **Negatives**: `impact_score = before_spend` (Cost Avoidance).
3.  **Harvests**: `impact_score = net_sales_lift * 0.10`.
4.  **Spend Eliminated**: `impact_score = delta_sales - delta_spend` (Net Profit).
    *   Triggered when `action_type=BID_DOWN` AND `observed_after_spend=0`.

### 3.4 Technical Guardrails

#### ROAS Efficiency Capping (Anti-Outlier)
To prevent "lucky streak" outliers from inflating impact:
1.  Compute `implied_roas` for all targets.
2.  Derive `ROAS_Cap` from **High Confidence** targets (clicks ≥ 20): `Median + 1 * StdDev`.
3.  For **Medium Confidence** targets (clicks < 20), if `implied_roas > ROAS_Cap`, force `spc_before` to align with the cap.

#### Low-Sample Filter
*   If `before_clicks < 5`, `decision_impact` is hard-set to `0`.

### 3.5 Statistical Confidence (Z-Score Based)
Proper statistical significance testing:

```python
# Calculate z-score
mean_impact = impact_values.mean()
std_error = impact_values.std() / sqrt(n)
z_score = mean_impact / std_error

# Convert to confidence via normal CDF (capped at 99%)
confidence_pct = min(99, stats.norm.cdf(z_score) * 100)
```

| z-score | Label | Meaning |
|---------|-------|---------|
| ≥ 2.58 | Very High | 99% confident |
| ≥ 1.96 | High | 95% confident |
| ≥ 1.645 | Moderate | 90% confident |
| < 1.645 | Directional | < 90% confident |

### 3.5 Incremental Contribution %
Shows what percentage of total revenue optimizations contributed:

```python
incremental_pct = attributed_impact / (before_sales + after_sales) × 100
```

Displayed as badge: `+7.6% of revenue`

### 3.6 ROAS Attribution Waterfall (V2 - Jan 2026)

The V2 Impact Engine attributes ROAS changes to specific factors using a waterfall model in `desktop/core/roas_attribution.py`.

#### Factor Decomposition
1. **Market Forces**: External CPC/CVR changes.
   - `cpc_impact`
   - `cvr_impact`
   - `aov_impact`
2. **Structural Effects**:
   - `scale_effect`: Expected efficiency drop from higher spend.
   - `portfolio_effect`: Impact of new launches (usually lower ROAS initially).
3. **Decision Impact**: Verified value from optimization actions.
   - Formula: `(Total Verified Decision Value) / Current Spend`
4. **Residual**: "Performance Beat" (Unexplained positive/negative variance).
   - Formula: `Actual_ROAS - (Baseline + Market + Structure + Decisions)`

---

## 4. Dashboard Components

### 4.1 Hero Banner
| Metric | Source |
|--------|--------|
| **Impact Value** | Sum of `final_decision_impact` (dampened) |
| **Contribution %** | `impact / total_account_sales × 100` |
| **Confidence** | Z-score based (Very High/High/Moderate/Directional) |

### 4.2 Quadrant Breakdown
| Quadrant | Definition |
|----------|------------|
| **Offensive Win** | Increased spend, increased ROAS |
| **Defensive Win** | Decreased spend, maintained ROAS |
| **Gap** | Missed opportunity (lower than expected) |
| **Market Drag** | External factors (excluded from attributed total) |

### 4.3 Validation Statuses
| Status | Meaning |
|--------|---------|
| `✓ CPC Validated` | After CPC matches suggested bid (±30%) |
| `✓ Directional` | Spend moved in expected direction |
| `✓ Volume Match` | Click pattern confirms implementation |
| `Not validated` | Changes not confirmed |

---

## 5. Optimizer Summary Metrics

| Tile | Metric |
|------|--------|
| **Search Terms** | Unique CSTs analyzed from STR data |
| **Bids** | Total bid change recommendations |
| **Negatives** | Negative keyword + PT recommendations |
| **Harvest** | Keywords harvested to exact match |

---

## 6. Security & Maintenance

* **Database Security**: Row Level Security (RLS) planned for client_id isolation
* **Environment Config**: `.env` for DB credentials and API keys
* **Testing**: Unit tests in `tests/` directory
* **Caching**: Streamlit `@st.cache_data` with version-based invalidation

---

### January 22, 2026 (V4.1 Refactor)
* **Performance Refactor**: Implementation of persistent connection pooling using `psycopg2` and `contextmanager`.
* **Multi-Tenancy**: Added robust testing tools for multi-owner/multi-org scenarios.
* **Onboarding System**: Complete Wizard state machine and Invite flow.
* **Empty States**: Enhancements for "No Data", "No Accounts", and "Filtered Empty" states.

### January 6, 2026
* **Confidence Weighting**: Added dampening for low-click decisions
* **Maturity Fix**: `actual_after_days` now uses calendar days, not report count
* **Statistical Confidence**: Z-score based confidence with proper CDF calculation
* **Incremental Badge**: Shows "X% of revenue" contribution in Hero Banner
* **Search Terms Metric**: Replaced "Touched" with unique CST count

---

## 7. Performance & Scalability (V4.1 Refactor)

### 7.1 Database Connection Pooling
To address timeout issues under load (e.g., Auth + Invite flows), the system now uses a Singleton pattern for the `PostgresManager`.

*   **Implementation**: `core.db_manager.get_db_manager()` returns a shared instance.
*   **Connection Lifecycle**:
    *   **Old Behavior**: Each service created a new `psycopg2.connect()` per request (latency + connection exhaustion).
    *   **New Behavior**: Services reuse the pool. `_get_connection` is a `@contextmanager` that yields a connection from the pool and handles atomic commits/rollbacks.

```python
@contextmanager
def _get_connection(self):
    if hasattr(self.db_manager, '_get_connection'):
        # Reuse pool
        with self.db_manager._get_connection() as conn:
            yield conn
    else:
        # Fallback (rare)
        conn = psycopg2.connect(self.db_url)
        yield conn
        conn.close()
```

### 7.2 Multi-Tenancy Architecture
The application fully supports multi-tenancy at the **Organization** level.

*   **Data Isolation**: All queries are scoped by `organization_id` or `client_id` (Account).
*   **Role-Based Access Control (RBAC)**:
    *   **Global Role**: `OWNER`, `ADMIN`, `OPERATOR`, `VIEWER` (on the Organization).
    *   **Account Override**: Users can have specific roles per Ad Account (e.g., `VIEWER` on Account A, `OPERATOR` on Account B).
*   **Testing**: Validated via `scripts/generate_test_invite.py` which simulates full multi-user invitation/acceptance flows.

---

## 8. Application Shell & UI (V4 - Jan 2026)

### 8.1 "Native App" Shell
To reduce visual clutter and provide a SaaS-like experience, the Streamlit shell is customized via CSS injection in `desktop/ui/layout.py` or main entry point.

- **Hidden Header**: The standard Streamlit top bar (running man, hamburger menu) is hidden via `div[data-testid="stHeader"] { display: none; }`.
- **Locked Sidebar**:
    - Configured with `initial_sidebar_state="expanded"`.
    - Collapse controls hidden via `[data-testid="stSidebarCollapseButton"] { display: none; }`.
    - Result: Persistent navigation pane that users cannot accidentally close.

### 8.2 Visual Standards
- **Icons**: Transitioned from Emojis (🏆) to **SVG Vector Icons** (Lucide style) for a professional look.
    - Used in Hero Banners ("Wins", "Gaps") and KPI Cards.
- **Card Styling**: Consistent glassmorphism with 1px borders and subtle gradients matching the "Dark Premium" theme.

