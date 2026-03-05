#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/run_pipeline_backfill.sh 2025-10-20 2026-02-16
#   ./scripts/run_pipeline_backfill.sh 120
#     (backfills last N days through yesterday UTC)

if [[ $# -eq 2 ]]; then
  START_DATE="$1"
  END_DATE="$2"
elif [[ $# -eq 1 ]]; then
  DAYS="$1"
  read -r START_DATE END_DATE < <(python3 - <<PY
from datetime import datetime, timedelta
n = int("${DAYS}")
end = datetime.utcnow().date() - timedelta(days=1)
start = end - timedelta(days=n-1)
print(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
PY
)
else
  echo "Usage:"
  echo "  $0 <start_date> <end_date>"
  echo "  $0 <days_back>"
  exit 1
fi

echo "Running SP-API backfill from ${START_DATE} to ${END_DATE}"

python3 - <<PY
from pipeline.runner import run_backfill
run_backfill('${START_DATE}', '${END_DATE}')
PY
