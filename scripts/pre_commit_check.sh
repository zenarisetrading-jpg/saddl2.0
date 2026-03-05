#!/bin/bash
set -e

echo "=== Syntax checks ==="
for f in pipeline/*.py; do
  python -m py_compile "$f"
  echo "  OK $f"
done

echo "=== Import checks ==="
python -c "from pipeline.config import get_config; print('  OK config')"
python -c "from pipeline.auth import get_token, make_headers; print('  OK auth')"
python -c "from pipeline.transform import parse_records; print('  OK transform')"
python -c "from pipeline.db_writer import upsert_sales_traffic; print('  OK db_writer')"

echo "=== Isolation tests ==="
pytest tests/pipeline/test_isolation.py -v -q

echo "=== Full test suite ==="
pytest tests/pipeline/ -v -q

echo ""
echo "All checks passed. Safe to commit."
