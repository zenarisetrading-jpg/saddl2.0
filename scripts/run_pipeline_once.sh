#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/run_pipeline_once.sh                # defaults to yesterday UTC
#   ./scripts/run_pipeline_once.sh 2026-02-15    # explicit date

TARGET_DATE="${1:-$(python3 - <<'PY'
from datetime import datetime, timedelta
print((datetime.utcnow().date() - timedelta(days=1)).strftime('%Y-%m-%d'))
PY
)}"

echo "Running SP-API pipeline for date: ${TARGET_DATE}"

python3 - <<PY
from pipeline.runner import run_single_date
from pipeline.config import get_config
from pipelines.sp_api_client import get_token as get_spapi_token
from pipelines.spapi_pipeline import pull_fba_inventory
from pipeline.bsr_pipeline import pull_daily_bsr

config = get_config()

# 1. Sales & traffic + aggregation
written = run_single_date('${TARGET_DATE}', config)
print(f'Sales/traffic complete. Rows written: {written}')

# 2. FBA inventory snapshot
try:
    get_spapi_token(force_refresh=True)
    inv_rows = pull_fba_inventory(config['ad_client_id'])
    print(f'FBA inventory complete. Rows written: {inv_rows}')
except Exception as e:
    print(f'FBA inventory failed (non-fatal): {e}')

# 3. BSR snapshot
try:
    bsr_rows = pull_daily_bsr('${TARGET_DATE}', config)
    print(f'BSR complete. Rows written: {bsr_rows}')
except Exception as e:
    print(f'BSR failed (non-fatal): {e}')
PY
