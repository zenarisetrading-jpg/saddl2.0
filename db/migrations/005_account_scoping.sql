-- Universal account scoping for SP-API isolated schemas.
-- This migration binds sc_raw/sc_analytics rows to a specific internal account_id
-- so diagnostics and aggregations no longer leak across accounts.

CREATE TABLE IF NOT EXISTS sc_raw.spapi_account_links (
    id BIGSERIAL PRIMARY KEY,
    account_id TEXT NOT NULL,
    public_client_id TEXT NOT NULL,
    marketplace_id VARCHAR(20) NOT NULL,
    spapi_profile_id TEXT,
    seller_id TEXT,
    refresh_token_ref TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (account_id, marketplace_id)
);

ALTER TABLE sc_raw.spapi_account_links
    ADD COLUMN IF NOT EXISTS public_client_id TEXT;

ALTER TABLE sc_raw.sales_traffic
    ADD COLUMN IF NOT EXISTS account_id TEXT;

ALTER TABLE sc_raw.bsr_history
    ADD COLUMN IF NOT EXISTS account_id TEXT;

ALTER TABLE sc_raw.pipeline_log
    ADD COLUMN IF NOT EXISTS account_id TEXT;

ALTER TABLE sc_analytics.account_daily
    ADD COLUMN IF NOT EXISTS account_id TEXT;

ALTER TABLE sc_analytics.osi_index
    ADD COLUMN IF NOT EXISTS account_id TEXT;

-- Backfill current single-account historical rows to default scope.
UPDATE sc_raw.sales_traffic
SET account_id = 's2c_uae_test'
WHERE account_id IS NULL;

UPDATE sc_raw.bsr_history
SET account_id = 's2c_uae_test'
WHERE account_id IS NULL;

UPDATE sc_raw.pipeline_log
SET account_id = 's2c_uae_test'
WHERE account_id IS NULL;

UPDATE sc_analytics.account_daily
SET account_id = 's2c_uae_test'
WHERE account_id IS NULL;

UPDATE sc_analytics.osi_index
SET account_id = 's2c_uae_test'
WHERE account_id IS NULL;

UPDATE sc_raw.spapi_account_links
SET public_client_id = account_id
WHERE public_client_id IS NULL;

ALTER TABLE sc_raw.sales_traffic
    ALTER COLUMN account_id SET NOT NULL;
ALTER TABLE sc_raw.bsr_history
    ALTER COLUMN account_id SET NOT NULL;
ALTER TABLE sc_raw.pipeline_log
    ALTER COLUMN account_id SET NOT NULL;
ALTER TABLE sc_analytics.account_daily
    ALTER COLUMN account_id SET NOT NULL;
ALTER TABLE sc_analytics.osi_index
    ALTER COLUMN account_id SET NOT NULL;
ALTER TABLE sc_raw.spapi_account_links
    ALTER COLUMN public_client_id SET NOT NULL;

-- Replace unique keys to include account scope.
ALTER TABLE sc_raw.sales_traffic
    DROP CONSTRAINT IF EXISTS sales_traffic_report_date_marketplace_id_child_asin_key;
ALTER TABLE sc_raw.sales_traffic
    DROP CONSTRAINT IF EXISTS sales_traffic_report_date_marketplace_account_asin_key;
ALTER TABLE sc_raw.sales_traffic
    ADD CONSTRAINT sales_traffic_report_date_marketplace_account_asin_key
    UNIQUE (report_date, marketplace_id, account_id, child_asin);

ALTER TABLE sc_raw.bsr_history
    DROP CONSTRAINT IF EXISTS bsr_history_report_date_marketplace_id_asin_category_id_key;
ALTER TABLE sc_raw.bsr_history
    DROP CONSTRAINT IF EXISTS bsr_history_report_date_marketplace_account_asin_category_key;
ALTER TABLE sc_raw.bsr_history
    ADD CONSTRAINT bsr_history_report_date_marketplace_account_asin_category_key
    UNIQUE (report_date, marketplace_id, account_id, asin, category_id);

ALTER TABLE sc_analytics.account_daily
    DROP CONSTRAINT IF EXISTS account_daily_report_date_marketplace_id_key;
ALTER TABLE sc_analytics.account_daily
    DROP CONSTRAINT IF EXISTS account_daily_report_date_marketplace_account_key;
ALTER TABLE sc_analytics.account_daily
    ADD CONSTRAINT account_daily_report_date_marketplace_account_key
    UNIQUE (report_date, marketplace_id, account_id);

ALTER TABLE sc_analytics.osi_index
    DROP CONSTRAINT IF EXISTS osi_index_report_date_marketplace_id_key;
ALTER TABLE sc_analytics.osi_index
    DROP CONSTRAINT IF EXISTS osi_index_report_date_marketplace_account_key;
ALTER TABLE sc_analytics.osi_index
    ADD CONSTRAINT osi_index_report_date_marketplace_account_key
    UNIQUE (report_date, marketplace_id, account_id);

CREATE INDEX IF NOT EXISTS idx_sc_raw_st_account_date
    ON sc_raw.sales_traffic (account_id, report_date);
CREATE INDEX IF NOT EXISTS idx_sc_raw_bsr_account_date
    ON sc_raw.bsr_history (account_id, report_date);
CREATE INDEX IF NOT EXISTS idx_sc_analytics_account_daily_account_date
    ON sc_analytics.account_daily (account_id, report_date);
CREATE INDEX IF NOT EXISTS idx_sc_analytics_osi_account_date
    ON sc_analytics.osi_index (account_id, report_date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_spapi_link_public_marketplace_active
    ON sc_raw.spapi_account_links (public_client_id, marketplace_id)
    WHERE is_active = TRUE;

INSERT INTO sc_raw.spapi_account_links (account_id, public_client_id, marketplace_id, notes)
VALUES ('s2c_uae_test', 's2c_uae_test', 'A2VIGQ35RCS4UG', 'Auto-seeded default mapping')
ON CONFLICT (account_id, marketplace_id) DO UPDATE
SET public_client_id = EXCLUDED.public_client_id,
    updated_at = NOW();

DROP VIEW IF EXISTS sc_analytics.bsr_trends CASCADE;

CREATE VIEW sc_analytics.bsr_trends AS
SELECT
    b.account_id,
    b.asin,
    b.report_date,
    b.category_name,
    b.category_id,
    b.rank AS current_rank,
    LAG(b.rank, 1) OVER w AS rank_1d_ago,
    LAG(b.rank, 7) OVER w AS rank_7d_ago,
    LAG(b.rank, 30) OVER w AS rank_30d_ago,
    b.rank - LAG(b.rank, 7) OVER w AS rank_change_7d,
    b.rank - LAG(b.rank, 30) OVER w AS rank_change_30d,
    CASE
        WHEN b.rank < LAG(b.rank, 7) OVER w THEN 'IMPROVING'
        WHEN b.rank > LAG(b.rank, 7) OVER w * 1.1 THEN 'DECLINING'
        ELSE 'STABLE'
    END AS rank_status_7d,
    CASE
        WHEN b.rank < LAG(b.rank, 30) OVER w THEN 'IMPROVING'
        WHEN b.rank > LAG(b.rank, 30) OVER w * 1.1 THEN 'DECLINING'
        ELSE 'STABLE'
    END AS rank_status_30d
FROM sc_raw.bsr_history b
WHERE b.category_name IS NOT NULL
WINDOW w AS (PARTITION BY b.account_id, b.asin, b.category_id ORDER BY b.report_date);

INSERT INTO sc_analytics.schema_version (version, description)
VALUES (5, 'Add account scoping + public client mapping for SP-API link resolution')
ON CONFLICT DO NOTHING;
