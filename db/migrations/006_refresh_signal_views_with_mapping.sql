-- Compatibility migration for environments that already applied 004/005 before account-link updates.

ALTER TABLE sc_raw.spapi_account_links
    ADD COLUMN IF NOT EXISTS public_client_id TEXT;

UPDATE sc_raw.spapi_account_links
SET public_client_id = account_id
WHERE public_client_id IS NULL;

ALTER TABLE sc_raw.spapi_account_links
    ALTER COLUMN public_client_id SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_spapi_link_public_marketplace_active
    ON sc_raw.spapi_account_links (public_client_id, marketplace_id)
    WHERE is_active = TRUE;

INSERT INTO sc_raw.spapi_account_links (account_id, public_client_id, marketplace_id, notes)
VALUES ('s2c_uae_test', 's2c_uae_test', 'A2VIGQ35RCS4UG', 'Auto-seeded default mapping')
ON CONFLICT (account_id, marketplace_id) DO UPDATE
SET public_client_id = EXCLUDED.public_client_id,
    updated_at = NOW();

-- Refresh signal views to account-scoped definitions.
-- Phase 2 signal views (account-scoped).
-- These views are read-only and derive signals per mapped account.

CREATE TABLE IF NOT EXISTS sc_raw.spapi_account_links (
    id BIGSERIAL PRIMARY KEY,
    account_id TEXT NOT NULL,
    public_client_id TEXT NOT NULL,
    marketplace_id VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (account_id, marketplace_id)
);

DROP VIEW IF EXISTS sc_analytics.signal_demand_contraction;
DROP VIEW IF EXISTS sc_analytics.signal_organic_decay;
DROP VIEW IF EXISTS sc_analytics.signal_non_advertised_winners;
DROP VIEW IF EXISTS sc_analytics.signal_harvest_cannibalization;
DROP VIEW IF EXISTS sc_analytics.signal_over_negation;

CREATE OR REPLACE VIEW sc_analytics.signal_demand_contraction AS
WITH recent AS (
    SELECT
        report_date,
        marketplace_id,
        account_id,
        total_ordered_revenue,
        organic_share_pct,
        tacos
    FROM sc_analytics.account_daily
    WHERE report_date >= CURRENT_DATE - 14
),
organic_cvr AS (
    SELECT
        report_date,
        marketplace_id,
        account_id,
        AVG(unit_session_percentage) AS avg_organic_cvr
    FROM sc_raw.sales_traffic
    WHERE report_date >= CURRENT_DATE - 14
    GROUP BY report_date, marketplace_id, account_id
),
ad_metrics AS (
    SELECT
        rst.report_date,
        link.marketplace_id,
        link.account_id,
        AVG(rst.spend / NULLIF(rst.clicks, 0)) AS avg_cpc,
        SUM(rst.orders) / NULLIF(SUM(rst.clicks), 0) * 100 AS ad_cvr
    FROM public.raw_search_term_data rst
    JOIN sc_raw.spapi_account_links link
      ON link.public_client_id = rst.client_id
     AND link.is_active = TRUE
    WHERE rst.report_date >= CURRENT_DATE - 14
    GROUP BY rst.report_date, link.marketplace_id, link.account_id
)
SELECT
    r.report_date,
    r.marketplace_id,
    r.account_id,
    r.total_ordered_revenue,
    o.avg_organic_cvr,
    a.ad_cvr,
    a.avg_cpc,
    CASE
        WHEN o.avg_organic_cvr < LAG(o.avg_organic_cvr, 7) OVER w * 0.9
         AND a.ad_cvr < LAG(a.ad_cvr, 7) OVER w * 0.9
         AND a.avg_cpc BETWEEN LAG(a.avg_cpc, 7) OVER w * 0.95 AND LAG(a.avg_cpc, 7) OVER w * 1.05
        THEN TRUE ELSE FALSE
    END AS is_demand_contraction,
    (o.avg_organic_cvr / NULLIF(LAG(o.avg_organic_cvr, 7) OVER w, 0) - 1) * 100 AS organic_cvr_change_pct,
    (a.ad_cvr / NULLIF(LAG(a.ad_cvr, 7) OVER w, 0) - 1) * 100 AS ad_cvr_change_pct
FROM recent r
JOIN organic_cvr o
  ON r.report_date = o.report_date
 AND r.marketplace_id = o.marketplace_id
 AND r.account_id = o.account_id
JOIN ad_metrics a
  ON r.report_date = a.report_date
 AND r.marketplace_id = a.marketplace_id
 AND r.account_id = a.account_id
WINDOW w AS (PARTITION BY r.marketplace_id, r.account_id ORDER BY r.report_date)
ORDER BY r.report_date DESC;


CREATE OR REPLACE VIEW sc_analytics.signal_organic_decay AS
WITH asin_trends AS (
    SELECT
        st.marketplace_id,
        st.account_id,
        st.child_asin,
        st.report_date,
        st.sessions,
        st.buy_box_percentage,
        st.ordered_revenue,
        LAG(st.sessions, 7) OVER w AS sessions_7d_ago,
        LAG(st.buy_box_percentage, 7) OVER w AS bb_7d_ago,
        bt.current_rank AS current_bsr,
        bt.rank_7d_ago,
        bt.rank_status_7d
    FROM sc_raw.sales_traffic st
    LEFT JOIN sc_analytics.bsr_trends bt
      ON st.child_asin = bt.asin
     AND st.report_date = bt.report_date
     AND st.account_id = bt.account_id
    WHERE st.report_date >= CURRENT_DATE - 14
    WINDOW w AS (PARTITION BY st.marketplace_id, st.account_id, st.child_asin ORDER BY st.report_date)
)
SELECT
    marketplace_id,
    account_id,
    child_asin,
    report_date,
    sessions,
    sessions_7d_ago,
    (sessions - sessions_7d_ago) / NULLIF(sessions_7d_ago, 0) * 100 AS session_change_pct,
    current_bsr,
    rank_7d_ago,
    rank_status_7d,
    ordered_revenue,
    buy_box_percentage,
    CASE
        WHEN sessions < sessions_7d_ago * 0.85
         AND rank_status_7d = 'DECLINING'
         AND buy_box_percentage > 90
         AND ordered_revenue > 100
        THEN TRUE ELSE FALSE
    END AS is_rank_decay
FROM asin_trends
WHERE sessions_7d_ago IS NOT NULL
ORDER BY session_change_pct ASC;


CREATE OR REPLACE VIEW sc_analytics.signal_non_advertised_winners AS
WITH sc_performance AS (
    SELECT
        marketplace_id,
        account_id,
        child_asin,
        SUM(ordered_revenue) AS revenue_30d,
        SUM(units_ordered) AS units_30d,
        AVG(unit_session_percentage) AS avg_cvr,
        AVG(sessions) AS avg_sessions_per_day
    FROM sc_raw.sales_traffic
    WHERE report_date >= CURRENT_DATE - 30
    GROUP BY marketplace_id, account_id, child_asin
),
advertised_asins AS (
    SELECT DISTINCT
        link.marketplace_id,
        link.account_id,
        apc.asin
    FROM public.advertised_product_cache apc
    JOIN sc_raw.spapi_account_links link
      ON link.public_client_id = apc.client_id
     AND link.is_active = TRUE
    WHERE apc.asin IS NOT NULL
)
SELECT
    sp.marketplace_id,
    sp.account_id,
    sp.child_asin,
    sp.revenue_30d,
    sp.units_30d,
    sp.avg_cvr,
    sp.avg_sessions_per_day,
    sp.revenue_30d / 30.0 AS avg_daily_revenue,
    CASE
        WHEN sp.avg_cvr > 8 AND sp.revenue_30d > 2000 THEN 'HIGH'
        WHEN sp.avg_cvr > 5 AND sp.revenue_30d > 1000 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS priority
FROM sc_performance sp
LEFT JOIN advertised_asins aa
  ON sp.marketplace_id = aa.marketplace_id
 AND sp.account_id = aa.account_id
 AND sp.child_asin = aa.asin
WHERE aa.asin IS NULL
  AND sp.revenue_30d > 500
ORDER BY sp.revenue_30d DESC;


CREATE OR REPLACE VIEW sc_analytics.signal_harvest_cannibalization AS
WITH harvest_performance AS (
    SELECT
        rst.report_date,
        link.marketplace_id,
        link.account_id,
        SUM(CASE WHEN rst.campaign_name ILIKE '%harvest%' THEN rst.sales END) AS harvest_sales,
        SUM(CASE WHEN rst.campaign_name ILIKE '%harvest%' THEN rst.spend END) AS harvest_spend,
        SUM(CASE WHEN rst.campaign_name ILIKE '%harvest%' THEN rst.sales END)
            / NULLIF(SUM(CASE WHEN rst.campaign_name ILIKE '%harvest%' THEN rst.spend END), 0) AS harvest_roas
    FROM public.raw_search_term_data rst
    JOIN sc_raw.spapi_account_links link
      ON link.public_client_id = rst.client_id
     AND link.is_active = TRUE
    WHERE rst.report_date >= CURRENT_DATE - 14
    GROUP BY rst.report_date, link.marketplace_id, link.account_id
),
discovery_performance AS (
    SELECT
        rst.report_date,
        link.marketplace_id,
        link.account_id,
        SUM(
            CASE
                WHEN rst.campaign_name ILIKE '%broad%' OR rst.campaign_name ILIKE '%auto%'
                THEN rst.sales
            END
        ) AS discovery_sales
    FROM public.raw_search_term_data rst
    JOIN sc_raw.spapi_account_links link
      ON link.public_client_id = rst.client_id
     AND link.is_active = TRUE
    WHERE rst.report_date >= CURRENT_DATE - 14
    GROUP BY rst.report_date, link.marketplace_id, link.account_id
)
SELECT
    h.report_date,
    h.marketplace_id,
    h.account_id,
    h.harvest_sales,
    h.harvest_roas,
    d.discovery_sales,
    a.total_ordered_revenue,
    CASE
        WHEN h.harvest_roas > LAG(h.harvest_roas, 7) OVER w * 1.1
         AND a.total_ordered_revenue BETWEEN
             LAG(a.total_ordered_revenue, 7) OVER w * 0.95
             AND LAG(a.total_ordered_revenue, 7) OVER w * 1.05
        THEN TRUE ELSE FALSE
    END AS is_cannibalizing
FROM harvest_performance h
JOIN discovery_performance d
  ON h.report_date = d.report_date
 AND h.marketplace_id = d.marketplace_id
 AND h.account_id = d.account_id
JOIN sc_analytics.account_daily a
  ON a.report_date = h.report_date
 AND a.marketplace_id = h.marketplace_id
 AND a.account_id = h.account_id
WINDOW w AS (PARTITION BY h.marketplace_id, h.account_id ORDER BY h.report_date);


CREATE OR REPLACE VIEW sc_analytics.signal_over_negation AS
WITH daily_metrics AS (
    SELECT
        rst.report_date,
        link.marketplace_id,
        link.account_id,
        SUM(rst.impressions) AS total_impressions,
        SUM(rst.clicks) AS total_clicks,
        SUM(rst.spend) AS total_spend,
        SUM(rst.sales) AS total_sales,
        SUM(rst.orders) AS total_orders
    FROM public.raw_search_term_data rst
    JOIN sc_raw.spapi_account_links link
      ON link.public_client_id = rst.client_id
     AND link.is_active = TRUE
    WHERE rst.report_date >= CURRENT_DATE - 14
    GROUP BY rst.report_date, link.marketplace_id, link.account_id
)
SELECT
    report_date,
    marketplace_id,
    account_id,
    total_impressions,
    total_clicks / NULLIF(total_impressions, 0) * 100 AS ctr,
    total_orders / NULLIF(total_clicks, 0) * 100 AS cvr,
    total_sales / NULLIF(total_spend, 0) AS roas,
    total_sales,
    CASE
        WHEN total_impressions < LAG(total_impressions, 7) OVER w * 0.8
         AND (total_clicks / NULLIF(total_impressions, 0)) >=
             LAG(total_clicks / NULLIF(total_impressions, 0), 7) OVER w
         AND (total_sales / NULLIF(total_spend, 0)) >
             LAG(total_sales / NULLIF(total_spend, 0), 7) OVER w
         AND total_sales < LAG(total_sales, 7) OVER w * 0.9
        THEN TRUE ELSE FALSE
    END AS is_over_negated
FROM daily_metrics
WINDOW w AS (PARTITION BY marketplace_id, account_id ORDER BY report_date);

INSERT INTO sc_analytics.schema_version (version, description)
VALUES (6, 'Refresh account-scoped signal views + public client mapping compatibility')
ON CONFLICT DO NOTHING;
