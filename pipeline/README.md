# SP-API Pipeline (Isolated Schemas)

This pipeline is isolated from production SADDL tables.

- Raw writes: `sc_raw`
- Aggregations: `sc_analytics`
- Never writes to: `saddl`

## 1) Environment

Your `DATABASE_URL` is already in `.env`.
Add only these API credentials:

- `LWA_CLIENT_ID`
- `LWA_CLIENT_SECRET`
- `LWA_REFRESH_TOKEN_UAE`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION=eu-west-1`
- `MARKETPLACE_ID_UAE=A2VIGQ35RCS4UG`

## 2) Install Dependencies

```bash
pip install -r requirements.txt
```

## 3) Run Migrations

```bash
python3 db/migrate.py
```

Verify schemas:

```bash
psql $DATABASE_URL -c "\\dn"
```

Expected schemas include:
- `saddl`
- `sc_raw`
- `sc_analytics`

## 4) Run Safety/Test Checks

```bash
./scripts/pre_commit_check.sh
```

## 5) Run One Date Manually

```bash
python3 -c "
from pipeline.runner import run_single_date
from pipeline.config import get_config
config = get_config()
run_single_date('2026-02-15', config)
"
```

## 6) Verify Data Landed

```bash
psql $DATABASE_URL -c "
SELECT COUNT(*) as records,
       COUNT(DISTINCT child_asin) as asins,
       SUM(ordered_revenue) as total_revenue
FROM sc_raw.sales_traffic
WHERE report_date = '2026-02-15';
"
```

## 7) Rollback (Pipeline Schemas Only)

```bash
python3 db/migrate.py rollback
```

This drops only:
- `sc_raw`
- `sc_analytics`

## Troubleshooting

- `dataDocumentId` missing:
  - query is not complete or failed; check `processingStatus` and `sc_raw.pipeline_log`
- auth failures (`401/403`):
  - verify LWA refresh token and app roles
- throttling (`429`):
  - wait and retry; pipeline already spaces createQuery calls
- no rows inserted:
  - inspect `sc_raw.pipeline_log.error_message`
  - inspect raw response shape and `pipeline/transform.py`
