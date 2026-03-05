"""Aggregation from raw layer to analytics layer."""

from __future__ import annotations

import psycopg2


def upsert_account_daily(
    db_url: str,
    report_date: str,
    marketplace_id: str,
    client_id: str,
    account_id: str,
) -> None:
    sql = """
    WITH sc_daily AS (
        SELECT
            report_date,
            marketplace_id,
            account_id,
            COALESCE(SUM(ordered_revenue), 0) AS total_ordered_revenue,
            COALESCE(SUM(units_ordered), 0) AS total_units_ordered,
            COALESCE(SUM(page_views), 0) AS total_page_views,
            COALESCE(SUM(sessions), 0) AS total_sessions,
            COUNT(DISTINCT child_asin) AS asin_count
        FROM sc_raw.sales_traffic
        WHERE report_date = %s
          AND marketplace_id = %s
          AND account_id = %s
        GROUP BY report_date, marketplace_id, account_id
    ),
    ad_daily AS (
        SELECT
            report_date,
            COALESCE(SUM(sales), 0) AS ad_attributed_revenue,
            COALESCE(SUM(spend), 0) AS ad_spend
        FROM public.raw_search_term_data
        WHERE report_date = %s
          AND client_id = %s
        GROUP BY report_date
    )
    INSERT INTO sc_analytics.account_daily (
        report_date,
        marketplace_id,
        account_id,
        total_ordered_revenue,
        total_units_ordered,
        total_page_views,
        total_sessions,
        asin_count,
        ad_attributed_revenue,
        organic_revenue,
        organic_share_pct,
        tacos,
        computed_at
    )
    SELECT
        sc.report_date,
        sc.marketplace_id,
        sc.account_id,
        sc.total_ordered_revenue,
        sc.total_units_ordered,
        sc.total_page_views,
        sc.total_sessions,
        sc.asin_count,
        COALESCE(ad.ad_attributed_revenue, 0) AS ad_attributed_revenue,
        GREATEST(sc.total_ordered_revenue - COALESCE(ad.ad_attributed_revenue, 0), 0) AS organic_revenue,
        ROUND(
            COALESCE(
                GREATEST(sc.total_ordered_revenue - COALESCE(ad.ad_attributed_revenue, 0), 0)
                / NULLIF(sc.total_ordered_revenue, 0) * 100,
                0
            )::numeric,
            2
        ) AS organic_share_pct,
        ROUND(
            COALESCE(COALESCE(ad.ad_spend, 0) / NULLIF(sc.total_ordered_revenue, 0) * 100, 0)::numeric,
            2
        ) AS tacos,
        NOW()
    FROM sc_daily sc
    LEFT JOIN ad_daily ad
      ON sc.report_date = ad.report_date
    ON CONFLICT (report_date, marketplace_id, account_id)
    DO UPDATE SET
        total_ordered_revenue = EXCLUDED.total_ordered_revenue,
        total_units_ordered = EXCLUDED.total_units_ordered,
        total_page_views = EXCLUDED.total_page_views,
        total_sessions = EXCLUDED.total_sessions,
        asin_count = EXCLUDED.asin_count,
        ad_attributed_revenue = EXCLUDED.ad_attributed_revenue,
        organic_revenue = EXCLUDED.organic_revenue,
        organic_share_pct = EXCLUDED.organic_share_pct,
        tacos = EXCLUDED.tacos,
        computed_at = NOW()
    """
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (report_date, marketplace_id, account_id, report_date, client_id))
        conn.commit()


def upsert_osi_index(db_url: str, report_date: str, marketplace_id: str, account_id: str) -> None:
    sql = """
    WITH daily AS (
        SELECT
            report_date,
            marketplace_id,
            account_id,
            ROUND(
                COALESCE(organic_revenue / NULLIF(total_ordered_revenue, 0) * 100, 0)::numeric,
                2
            ) AS organic_share_pct
        FROM sc_analytics.account_daily
        WHERE marketplace_id = %s
          AND account_id = %s
    ),
    rolling AS (
        SELECT
            report_date,
            marketplace_id,
            account_id,
            AVG(organic_share_pct) OVER (
                PARTITION BY marketplace_id, account_id
                ORDER BY report_date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ) AS current_osi,
            NULL::numeric AS baseline_osi
        FROM daily
    ),
    baseline AS (
        SELECT
            report_date,
            marketplace_id,
            account_id,
            current_osi,
            LAG(current_osi, 28) OVER (
                PARTITION BY marketplace_id, account_id
                ORDER BY report_date
            ) AS baseline_osi
        FROM rolling
    )
    INSERT INTO sc_analytics.osi_index (
        report_date,
        marketplace_id,
        account_id,
        current_osi,
        baseline_osi,
        osi_delta,
        osi_index_value,
        computed_at
    )
    SELECT
        report_date,
        marketplace_id,
        account_id,
        ROUND(COALESCE(current_osi, 0)::numeric, 2),
        ROUND(COALESCE(baseline_osi, 0)::numeric, 2),
        ROUND(COALESCE(current_osi - baseline_osi, 0)::numeric, 2),
        ROUND(COALESCE((current_osi / NULLIF(baseline_osi, 0)) * 100, 0)::numeric, 1),
        NOW()
    FROM baseline
    WHERE report_date = %s
      AND marketplace_id = %s
      AND account_id = %s
    ON CONFLICT (report_date, marketplace_id, account_id)
    DO UPDATE SET
        current_osi = EXCLUDED.current_osi,
        baseline_osi = EXCLUDED.baseline_osi,
        osi_delta = EXCLUDED.osi_delta,
        osi_index_value = EXCLUDED.osi_index_value,
        computed_at = NOW()
    """
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (marketplace_id, account_id, report_date, marketplace_id, account_id))
        conn.commit()
