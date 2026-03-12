"""Configuration loader for isolated SP-API pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

import psycopg2
from dotenv import load_dotenv


_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT.parent / ".env")


def get_config() -> Dict[str, str]:
    required = [
        "LWA_CLIENT_ID",
        "LWA_CLIENT_SECRET",
        "LWA_REFRESH_TOKEN_UAE",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "DATABASE_URL",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")

    marketplace_id = os.environ.get("MARKETPLACE_ID_UAE", "A2VIGQ35RCS4UG").strip()
    ad_client_id = os.environ.get("AD_CLIENT_ID", os.environ.get("CLIENT_ID", "s2c_uae_test")).strip()
    database_url = os.environ["DATABASE_URL"].strip()
    env_spapi_account_id = os.environ.get("SPAPI_ACCOUNT_ID", "s2c_uae_test").strip()

    spapi_account_id = _resolve_spapi_account_id(
        database_url=database_url,
        ad_client_id=ad_client_id,
        marketplace_id=marketplace_id,
        fallback=env_spapi_account_id,
    )

    return {
        "lwa_client_id": os.environ["LWA_CLIENT_ID"].strip(),
        "lwa_client_secret": os.environ["LWA_CLIENT_SECRET"].strip(),
        "refresh_token": os.environ["LWA_REFRESH_TOKEN_UAE"].strip(),
        "aws_access_key": os.environ["AWS_ACCESS_KEY_ID"].strip(),
        "aws_secret_key": os.environ["AWS_SECRET_ACCESS_KEY"].strip(),
        "aws_region": os.environ.get("AWS_REGION", "eu-west-1").strip(),
        "marketplace_id": marketplace_id,
        "spapi_account_id": spapi_account_id,
        "ad_client_id": ad_client_id,
        "database_url": database_url,
        "endpoint": "https://sellingpartnerapi-eu.amazon.com",
    }


def _resolve_spapi_account_id(
    database_url: str,
    ad_client_id: str,
    marketplace_id: str,
    fallback: str,
) -> str:
    """
    Resolve internal SP-API account_id from client mapping table.
    Falls back to configured env value when mapping table is unavailable.
    """
    sql = """
        SELECT account_id
        FROM sc_raw.spapi_account_links
        WHERE public_client_id = %s
          AND marketplace_id = %s
          AND is_active = TRUE
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
    """
    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (ad_client_id, marketplace_id))
                row = cur.fetchone()
                if row and row[0]:
                    return str(row[0])
    except Exception:
        return fallback
    return fallback
