# Coding Conventions

**Analysis Date:** 2026-02-24

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `anthropic_client.py`, `rainforest_client.py`)
- Classes and dataclasses: PascalCase (e.g., `AnthropicClient`, `ValidationResult`, `RateLimiter`)
- Directories: `snake_case` (e.g., `app_core/`, `pipelines/`, `features/`)

**Functions:**
- Public functions: `snake_case` (e.g., `validate_isolation_negative()`, `get_period_metrics()`)
- Private/internal functions: `_snake_case` prefix (e.g., `_build_analysis_prompt()`, `_init_db()`, `_call_api()`)
- Boolean getters: `is_*` or `has_*` pattern (e.g., `is_valid`, `has_warnings`)
- Computed properties: Use `@property` decorator with `snake_case` names (e.g., `error_count`, `warning_count`)

**Variables:**
- Constants: `UPPER_SNAKE_CASE` (e.g., `CURRENCY_LIMITS`, `ERROR_MESSAGES`, `MOCK_CONFIG`)
- Instance variables: `snake_case` (e.g., `self.api_key`, `self.db_path`, `self.rate_limiter`)
- Parameters: `snake_case` (e.g., `client_id`, `marketplace`, `start_date`)
- Private attributes: `_snake_case` prefix (e.g., `_init_db()`, `_dates()`)

**Types:**
- Enums: PascalCase (e.g., `ValidationSeverity`, `NegativeType`, `RecommendationType`)
- NamedTuple: PascalCase (e.g., `OrganizationSummary`, `OrganizationResult`)
- Dataclasses: PascalCase (e.g., `ValidationIssue`, `ValidationResult`)

## Code Style

**Formatting:**
- Not enforced by explicit tool (no `.eslintrc`, `.prettierrc`, or similar detected)
- Follows PEP 8 standard for Python (4-space indentation observed)
- Line length: ~100 characters typical but not strictly enforced
- Imports use triple-quoted docstrings with `from __future__ import annotations`

**Module headers:**
- Triple-quoted docstring at top of file describing module purpose
- Example from `utils/validators.py`:
  ```python
  """
  Data Validation Utilities

  Common validation functions for all features.
  """
  ```

**Linting:**
- pytest 8.3.0 for test running
- pytest-mock 3.14.0 for mocking support
- No explicit linting tool configured (ESLint/pylint/flake8)

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first, for PEP 563)
2. Standard library imports (`os`, `sys`, `json`, `requests`, `sqlite3`, `time`)
3. Third-party imports (`pandas`, `numpy`, `pytest`, `dataclasses`, `enum`, `typing`)
4. Local/relative imports (from pipeline, app_core, features modules)

**Path Aliases:**
- No explicit aliases detected
- Direct imports from package roots: `from pipeline.auth import get_token`
- Relative imports within tests: `from features.dashboard.metrics import calculate_roas`

**Example from `api/anthropic_client.py`:**
```python
import requests
import json
import pandas as pd
from typing import Dict, List, Any

class AnthropicClient:
    """Client for Anthropic Claude API."""
```

## Error Handling

**Patterns:**
- Broad exception catching with `except Exception as e` for API calls
  - Example from `api/rainforest_client.py`:
    ```python
    try:
        response = requests.get(self.base_url, params=params, timeout=30)
    except Exception as e:
        print(f"❌ {asin}: Exception - {str(e)}")
        result = {'asin': asin.upper(), 'status': 'error', 'error': str(e)}
        return result
    ```

- Specific exception handling for database operations
  - Example from `app_core/postgres_manager.py`:
    ```python
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
        # Handle connection errors
    except psycopg2.IntegrityError:
        # Handle constraint violations
    ```

- Custom exception classes for auth errors
  - Example from `app_core/auth/middleware.py`:
    ```python
    class AuthError(Exception):
        """Base class for authentication errors."""

    class PermissionDenied(AuthError):
        """Derived auth error for access control."""
    ```

- Return tuples for validation results (not exceptions)
  - Pattern: `(is_valid: bool, error_message: str)` or properties on result objects
  - Example from `utils/validators.py`:
    ```python
    def validate_search_term_report(df, col_map) -> Tuple[bool, str]:
        # ... validation logic
        return False, f"Missing required columns: {', '.join(missing)}"
    ```

- Dataclass-based results with property methods for validation state
  - Example from `app_core/bulk_validation.py`:
    ```python
    @dataclass
    class ValidationResult:
        issues: List[ValidationIssue] = field(default_factory=list)

        @property
        def is_valid(self) -> bool:
            """True if no CRITICAL or ERROR level issues."""
            return not any(i.severity in [...] for i in self.issues)
    ```

## Logging

**Framework:** Inconsistent - mix of `logging` module and `print()` statements

**Logging approach (when used):**
- Standard library `logging` module in production code
- Example from `app_core/platform_service.py`:
  ```python
  import logging
  logging.basicConfig(level=logging.INFO)
  logger = logging.getLogger(__name__)
  logger.error(f"Error listing organizations: {e}")
  ```

**Print statements (debug mode):**
- Heavy use of `print()` for debugging, especially in development
- Example from `api/rainforest_client.py`:
  ```python
  print(f"DEBUG CACHE HIT {asin}: Title='{cached.get('title', 'N/A')}'")
  print(f"DEBUG {asin}: Full API Response")
  print(f"{'='*80}")
  ```

**When to log:**
- API failures and retries
- Connection pool health checks
- Database operation counts and summaries
- Authentication errors
- Data transformation warnings

## Comments

**When to Comment:**
- Explain WHY, not WHAT
- Document non-obvious business logic (e.g., validation rules, calculations)
- Mark temporary workarounds with uppercase labels: `# DEBUG:`, `# TODO:`, `# FIXME:`
- Explain edge cases and fallback behavior

**JSDoc/TSDoc:**
- Python uses triple-quoted docstrings, not JSDoc
- Format: Multi-line docstrings with summary, then blank line, then detailed description

**Examples from codebase:**
```python
def calculate_cpc_impact(prior: Dict, current: Dict) -> float:
    """CPC impact on ROAS (inverse relationship - higher CPC = lower ROAS)."""
    # One-liner for simple calculations

def validate_isolation_negative(row: dict, idx: int) -> List[ValidationIssue]:
    """
    Validate Isolation (campaign-level) negative.

    Rules:
    - Ad Group MUST BE BLANK
    - Match Type MUST be 'campaign negative exact' or 'campaign negative phrase'
    - Status ONLY 'enabled' or 'deleted'
    - Max Bid MUST BE BLANK
    """
    # Multi-line for complex functions
```

## Function Design

**Size:**
- Most functions 20-50 lines
- Complex functions documented with multi-line docstrings
- Single responsibility principle observed (separate parse, validate, transform functions)

**Parameters:**
- Type hints used consistently: `def func(param: Type) -> ReturnType:`
- Common pattern: `(self, config: dict, client_id: str, date: str) -> Optional[Dict[str, Any]]`
- Optional parameters default to `None`: `marketplace: str = 'AE'`

**Return Values:**
- Tuples for validation: `(bool, str)` — success flag + message
- Dicts for structured results: `Dict[str, Any]`
- Optional types: `Optional[Dict]` when result may be None
- Dataclass results for complex multi-field returns
- Properties instead of getters (e.g., `result.is_valid` not `result.get_is_valid()`)

**Example structure from `api/rainforest_client.py`:**
```python
def lookup_asin(self, asin: str, marketplace: str = 'AE') -> Dict:
    """
    Lookup single ASIN with caching.

    Args:
        asin: Amazon ASIN to lookup
        marketplace: Amazon marketplace (AE, US, UK, etc.)

    Returns:
        Dict with product details or error info
    """
    # Docstring explains args and return contract
```

## Module Design

**Exports:**
- Public classes and functions at module level
- Private functions prefixed with underscore
- Common pattern: Main class at module level, helper functions below

**Barrel Files:**
- Used in feature modules for organizing imports
- Example from `features/impact/data/__init__.py`:
  ```python
  from features.impact.data.fetchers import (...)
  from features.impact.data.transforms import (...)
  ```

**Class organization:**
- `__init__()` method first
- Public methods next
- Private methods (prefixed with `_`) last
- Properties with `@property` decorator alongside their usage context

**Example from `api/rainforest_client.py`:**
```python
class RainforestClient:
    """Client for Rainforest Amazon Product API."""

    def __init__(self, api_key: str, cache_db: str = 'data/asin_cache.db'):
        # Initialization

    def lookup_asin(self, asin: str, marketplace: str = 'AE') -> Dict:
        # Public method

    def batch_lookup(self, asin_list: list, marketplace: str = 'AE') -> list:
        # Public method

    def __del__(self):
        # Cleanup
```

## Testing-Specific Conventions

- Test files use `test_` prefix: `test_auth.py`, `test_aggregator.py`
- Test functions: `test_<what_is_being_tested>`: e.g., `test_get_token_returns_access_token()`
- Fixtures in `conftest.py` or `fixtures/` directory with descriptive names
- Mock objects follow `mock_*` or `fake_*` naming: `mock_response`, `fake_conn`, `fake_cursor`
- Constants for test data: `MOCK_CONFIG`, `mock_env`

## TypeScript Conventions (Supabase Functions)

- File: `/supabase/functions/amazon-oauth-callback/index.ts`
- URL and constant names: `UPPER_SNAKE_CASE` (e.g., `AMAZON_TOKEN_URL`, `STREAMLIT_APP_URL`)
- Variable names: `camelCase` (e.g., `tokenResponse`, `refreshToken`, `dbError`)
- Async/await pattern used for HTTP and database operations
- Environment variables accessed via `Deno.env.get()`

---

*Convention analysis: 2026-02-24*
