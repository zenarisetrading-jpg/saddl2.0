-- Creates isolated raw data schema.
CREATE SCHEMA IF NOT EXISTS sc_raw;

CREATE TABLE IF NOT EXISTS sc_raw.sales_traffic (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    marketplace_id VARCHAR(20) NOT NULL,
    child_asin VARCHAR(20) NOT NULL,
    parent_asin VARCHAR(20),
    ordered_revenue NUMERIC(14,2),
    ordered_revenue_currency VARCHAR(3),
    units_ordered INTEGER,
    total_order_items INTEGER,
    page_views INTEGER,
    sessions INTEGER,
    buy_box_percentage NUMERIC(5,2),
    unit_session_percentage NUMERIC(5,2),
    pulled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    query_id VARCHAR(100),
    UNIQUE (report_date, marketplace_id, child_asin)
);

CREATE TABLE IF NOT EXISTS sc_raw.pipeline_log (
    id BIGSERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    target_date DATE NOT NULL,
    marketplace_id VARCHAR(20) NOT NULL,
    query_id VARCHAR(100),
    status VARCHAR(20) NOT NULL,
    records_written INTEGER,
    error_message TEXT,
    duration_secs INTEGER
);

CREATE INDEX IF NOT EXISTS idx_sc_raw_st_date
    ON sc_raw.sales_traffic (report_date);
CREATE INDEX IF NOT EXISTS idx_sc_raw_st_asin
    ON sc_raw.sales_traffic (child_asin);
CREATE INDEX IF NOT EXISTS idx_sc_raw_st_date_asin
    ON sc_raw.sales_traffic (report_date, child_asin);
