-- Phase 1: Add BSR storage + trend view in isolated schemas only.

CREATE TABLE IF NOT EXISTS sc_raw.bsr_history (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    marketplace_id VARCHAR(20) NOT NULL,
    asin VARCHAR(20) NOT NULL,
    category_name VARCHAR(200),
    category_id VARCHAR(255),
    rank INTEGER,
    pulled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (report_date, marketplace_id, asin, category_id)
);

CREATE INDEX IF NOT EXISTS idx_bsr_date_asin
    ON sc_raw.bsr_history (report_date, asin);

CREATE INDEX IF NOT EXISTS idx_bsr_asin_category
    ON sc_raw.bsr_history (asin, category_id, report_date);

DROP VIEW IF EXISTS sc_analytics.bsr_trends CASCADE;

CREATE VIEW sc_analytics.bsr_trends AS
SELECT
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
WINDOW w AS (PARTITION BY b.asin, b.category_id ORDER BY b.report_date);

INSERT INTO sc_analytics.schema_version (version, description)
VALUES (3, 'Add sc_raw.bsr_history and sc_analytics.bsr_trends')
ON CONFLICT DO NOTHING;
