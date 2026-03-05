-- Phase 4: Create optimizer_sp_feed table
-- Pre-computed weekly commerce metrics per ASIN for optimizer intelligence layer.
-- Append-only — never update existing rows.

CREATE TABLE IF NOT EXISTS optimizer_sp_feed (
    client_id              TEXT NOT NULL,
    asin                   TEXT NOT NULL,
    week_start             DATE NOT NULL,
    sessions               INTEGER,
    page_views             INTEGER,
    total_orders           INTEGER,
    paid_orders            INTEGER,
    organic_orders         INTEGER,
    total_sales            DECIMAL(10,2),
    paid_sales             DECIMAL(10,2),
    ad_spend               DECIMAL(10,2),
    tacos                  DECIMAL(5,4),
    organic_cvr            DECIMAL(5,4),
    paid_cvr               DECIMAL(5,4),
    halo_ratio             DECIMAL(5,2),
    organic_strength       DECIMAL(5,4),
    bsr_current            INTEGER,
    bsr_14d_ago            INTEGER,
    bsr_trend_pct          DECIMAL(5,2),
    inventory_available    INTEGER,
    days_of_supply         DECIMAL(5,1),
    buy_box_pct            DECIMAL(5,2),
    product_age_days       INTEGER,
    data_source            TEXT NOT NULL DEFAULT 'spapi_auto',
    created_at             TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (client_id, asin, week_start)
);

COMMENT ON TABLE optimizer_sp_feed IS
    'Pre-computed weekly commerce metrics per ASIN for optimizer intelligence layer. Append-only.';
