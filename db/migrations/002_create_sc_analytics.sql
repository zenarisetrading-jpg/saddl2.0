CREATE SCHEMA IF NOT EXISTS sc_analytics;

CREATE TABLE IF NOT EXISTS sc_analytics.account_daily (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    marketplace_id VARCHAR(20) NOT NULL,
    total_ordered_revenue NUMERIC(16,2),
    total_units_ordered INTEGER,
    total_page_views INTEGER,
    total_sessions INTEGER,
    asin_count INTEGER,
    ad_attributed_revenue NUMERIC(16,2),
    organic_revenue NUMERIC(16,2),
    organic_share_pct NUMERIC(5,2),
    tacos NUMERIC(5,2),
    computed_at TIMESTAMPTZ,
    UNIQUE (report_date, marketplace_id)
);

CREATE TABLE IF NOT EXISTS sc_analytics.osi_index (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    marketplace_id VARCHAR(20) NOT NULL,
    current_osi NUMERIC(5,2),
    baseline_osi NUMERIC(5,2),
    osi_delta NUMERIC(5,2),
    osi_index_value NUMERIC(6,1),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (report_date, marketplace_id)
);

CREATE TABLE IF NOT EXISTS sc_analytics.schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    description TEXT
);

INSERT INTO sc_analytics.schema_version (version, description)
VALUES (2, 'Initial sc_analytics schema') ON CONFLICT DO NOTHING;
