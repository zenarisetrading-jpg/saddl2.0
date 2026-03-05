# Testing

**Analysis Date:** 2026-02-24

## Framework

### Primary Framework
- **pytest** (v8.3.0) — installed in requirements.txt
- **pytest-mock** (v3.14.0) — mock fixture support
- **unittest** — also used directly in some test files (class-based `TestCase` style)
- **unittest.mock** — `patch`, `MagicMock` used for dependency injection

### Test Runner
- Run via: `pytest dev_resources/tests/`
- No `pytest.ini` or `setup.cfg` found; configuration appears to be default
- Tests must be run from project root to resolve `sys.path.append` imports

---

## Directory Structure

```
dev_resources/
└── tests/
    ├── test_optimizer_v2.py          # Bid optimization logic tests
    ├── test_harvest_impact_logic.py  # Harvest impact + SQLite integration tests
    ├── test_harvest_market_drag.py   # Market Drag classification tests
    ├── test_market_drag_fix.py       # Regression test for Feb 2026 Market Drag bug
    ├── test_harvest_085x.py          # Harvest threshold edge cases
    ├── test_v33_performance.py       # v33 optimizer performance benchmarks
    ├── test_rollback_v33_to_v32.py   # Rollback validation test
    ├── alter_actions_log.py          # Dev utility (not a test)
    ├── debug_reasons.py              # Dev utility (not a test)
    ├── filter_premature.py           # Dev utility (not a test)
    ├── check_cooldown_dates.py       # Dev utility (not a test)
    ├── kill_idle_connections.py      # Dev utility (not a test)
    ├── breakdown_outcomes.py         # Dev utility (not a test)
    ├── generate_v32_v33_comparison.py # Dev utility (not a test)
    ├── harvest_validation.py         # Dev utility (not a test)
    ├── run_impact_report.py          # Dev utility (not a test)
    ├── debug_outcomes.py             # Dev utility (not a test)
    ├── bulk_validation_spec.py       # Dev utility (not a test)
    └── list_queries.py               # Dev utility (not a test)
```

**Note:** Many files in `dev_resources/tests/` are dev utilities / scripts, not actual pytest tests. Roughly 7-8 files are true test files (prefixed with `test_`).

---

## Test Patterns

### 1. Class-Based Tests (unittest.TestCase)
Used in `test_harvest_impact_logic.py`:
```python
class TestHarvestImpactLogic(unittest.TestCase):
    def setUp(self):
        # Creates temporary SQLite DB for isolation
        self.test_db_path = "test_harvest_impact.db"
        self.db = DatabaseManager(self.test_db_path)

    def tearDown(self):
        # Cleanup temp DB
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_harvest_winner(self):
        # Seeds data via DataFrame → save_target_stats_batch()
        # Then queries and asserts impact results
```

### 2. Function-Based Tests with Mocks
Used in `test_optimizer_v2.py`:
```python
def run_optimizer_with_mocks(df, cooldowns_df, roas_14d_df, commerce_df=None):
    class MockDBManager:
        def get_recent_action_dates(self, client_id): return self.c_df
        def get_target_14d_roas(self, client_id): return self.r_df

    with patch('app_core.db_manager.get_db_manager', side_effect=mock_get_db_manager), \
         patch('features.optimizer.strategies.bids.DataHub') as mock_datahub, \
         patch('features.optimizer.strategies.bids.st') as mock_st:
        mock_st.session_state = {'test_mode': True}
        return calculate_bid_optimizations(...)
```

### 3. DataFrame-Driven Testing
Most tests construct `pd.DataFrame` fixtures manually inline rather than loading fixtures from files. Example pattern:
```python
df = pd.DataFrame([{
    'Start Date': '2024-01-01',
    'Campaign Name': 'Test_Campaign',
    'Match Type': 'Exact',
    'Spend': 100.0,
    'Sales': 400.0,
    ...
}])
```

### 4. Regression Tests
`test_market_drag_fix.py` — documents the Feb 5, 2026 bug fix for Market Drag display issue:
- Verifies that `market_tag` is sourced from DB, not recomputed from raw data
- Ensures `final_decision_impact` retains correct sign for Market Drag category

---

## Mocking Patterns

### DB Manager Mocking
Tests construct a `MockDBManager` class inline that mimics the real `get_db_manager()` interface:
- `get_recent_action_dates(client_id)` → returns DataFrame
- `get_target_14d_roas(client_id)` → returns DataFrame
- `get_commerce_metrics_by_target(client_id)` → returns DataFrame

### Streamlit Session State Mocking
```python
mock_st.session_state = {'test_mode': True}
```
Used to simulate Streamlit's session state in non-UI contexts.

### SQLite as Test Database
`test_harvest_impact_logic.py` uses temporary SQLite files instead of mocking the PostgreSQL connection, allowing real SQL execution in isolation.

---

## Path Setup Pattern
All test files manually append project root to `sys.path`:
```python
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
```
This pattern is repeated in every test file — no shared `conftest.py` exists to centralize it.

---

## Coverage

### Tested Areas
| Module | Test Coverage |
|--------|--------------|
| `features/optimizer_shared/strategies/bids.py` | Moderate — bid calc logic via mocks |
| `features/impact/data/transforms.py` | Regression tests for Market Drag bug |
| Harvest logic (target promotion) | Integration tests via SQLite |
| Market Drag classification | Dedicated test file |
| v33 performance benchmarks | Benchmarking tests |

### Untested Areas (No Test Files Found)
| Module | Risk Level |
|--------|-----------|
| `api/` — SP-API integration | High |
| `pipeline/runner.py` | High |
| `pipeline/bsr_pipeline.py` | High |
| `app_core/db_manager.py` (Supabase) | High |
| `features/impact/` (full module) | Medium |
| `components/` (UI components) | Low (UI) |
| `features/keyword_harvester/` | Medium |
| Auth flow (`app_core/auth.py`) | High |
| Scheduled jobs (`apscheduler`) | Medium |

---

## Known Testing Limitations

### 1. No conftest.py
- No shared fixtures or path setup — every test file repeats `sys.path.append`
- No shared mock factories or reusable test data builders

### 2. DB-Dependent Tests
- `test_optimizer_v2.py` requires `DATABASE_URL` in `.env` for some paths
- Tests that use real Supabase/PostgreSQL cannot run in CI without credentials

### 3. Mixed Test/Utility Files
- `dev_resources/tests/` contains non-test scripts (dev utilities) alongside actual test files
- No clear separation makes it hard to run `pytest` cleanly on the whole directory

### 4. No CI/CD Integration Detected
- No `.github/workflows/`, `Makefile`, or `Dockerfile` found
- Tests appear to be run manually by developers

### 5. Streamlit UI Untestable
- No usage of `streamlit.testing.v1.AppTest` in project tests
- All UI flows are tested manually

---

## Running Tests

```bash
# Run all tests from project root
cd "/Users/zayaanyousuf/Documents/Amazon PPC/saddle/saddle/desktop"
pytest dev_resources/tests/ -v

# Run specific test file
pytest dev_resources/tests/test_optimizer_v2.py -v

# Run with output capture disabled (useful for print debugging)
pytest dev_resources/tests/ -s -v
```

**Prerequisites:**
- `DATABASE_URL` set in `.env` (for DB-dependent tests)
- Virtual env `st_env` activated: `source st_env/bin/activate`
