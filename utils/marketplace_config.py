"""Amazon SP-API marketplace-to-region mapping and per-client config helpers."""

from __future__ import annotations

import os
from typing import Optional, Tuple

# Amazon SP-API marketplace IDs → regional endpoint hostnames.
# Source: https://developer-docs.amazon.com/sp-api/docs/marketplace-ids
MARKETPLACE_REGION_MAP: dict[str, str] = {
    # North America
    "ATVPDKIKX0DER":  "sellingpartnerapi-na.amazon.com",   # US
    "A2EUQ1WTGCTBG2": "sellingpartnerapi-na.amazon.com",   # CA
    "A1AM78C64UM0Y8": "sellingpartnerapi-na.amazon.com",   # MX
    "A2Q3Y263D00KWC": "sellingpartnerapi-na.amazon.com",   # BR

    # Europe / Middle East / Africa
    "A1F83G8C2ARO7P": "sellingpartnerapi-eu.amazon.com",   # UK
    "A1PA6795UKMFR9": "sellingpartnerapi-eu.amazon.com",   # DE
    "A13V1IB3VIYZZH": "sellingpartnerapi-eu.amazon.com",   # FR
    "APJ6JRA9NG5V4":  "sellingpartnerapi-eu.amazon.com",   # IT
    "A1RKKUPIHCS9HS": "sellingpartnerapi-eu.amazon.com",   # ES
    "A1805IZSGTT6HS": "sellingpartnerapi-eu.amazon.com",   # NL
    "A2NODRKZP88ZB9": "sellingpartnerapi-eu.amazon.com",   # SE
    "A1C3SOZRARQ6R3": "sellingpartnerapi-eu.amazon.com",   # PL
    "ARBP9OOSHTCHU":  "sellingpartnerapi-eu.amazon.com",   # EG
    "A33AVAJ2PDY3EV": "sellingpartnerapi-eu.amazon.com",   # TR
    "A17E79C6D8DWNP": "sellingpartnerapi-eu.amazon.com",   # KSA
    "A2VIGQ35RCS4UG": "sellingpartnerapi-eu.amazon.com",   # UAE
    "A21TJRUUN4KGV":  "sellingpartnerapi-eu.amazon.com",   # IN
    "AMEN7PMS3EDWL":  "sellingpartnerapi-eu.amazon.com",   # BE
    "AE08WJ6YKNBMC":  "sellingpartnerapi-eu.amazon.com",   # ZA

    # Far East
    "A1VC38T7YXB528": "sellingpartnerapi-fe.amazon.com",   # JP
    "A39IBJ37TRP1C6": "sellingpartnerapi-fe.amazon.com",   # AU
    "A19VAU5U5O7RUS": "sellingpartnerapi-fe.amazon.com",   # SG
}


def get_region_endpoint(marketplace_id: str) -> str:
    """Return the SP-API regional endpoint hostname for a marketplace ID.

    Raises ValueError if the marketplace_id is not in the known mapping.
    """
    endpoint = MARKETPLACE_REGION_MAP.get(marketplace_id)
    if not endpoint:
        raise ValueError(
            f"Unknown marketplace_id: {marketplace_id}. "
            f"Known marketplaces: {list(MARKETPLACE_REGION_MAP.keys())}"
        )
    return endpoint


def get_client_marketplace_config(
    client_id: str,
    db_url: str,
) -> Tuple[str, str]:
    """Fetch (marketplace_id, region_endpoint) for a client from client_settings.

    Falls back to the MARKETPLACE_ID_UAE env var for legacy clients that
    connected before marketplace discovery was added to the OAuth flow.
    Logs a WARNING when falling back so stale clients are easy to identify.
    """
    import psycopg2  # type: ignore

    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT marketplace_id, region_endpoint "
                    "FROM client_settings WHERE client_id = %s",
                    (client_id,),
                )
                row = cur.fetchone()
                if row and row[0] and row[1]:
                    return str(row[0]), str(row[1])
    except Exception:
        pass

    # Fallback for legacy clients without stored marketplace info
    legacy_marketplace = os.environ.get("MARKETPLACE_ID_UAE", "A2VIGQ35RCS4UG")
    legacy_endpoint = get_region_endpoint(legacy_marketplace)
    print(
        f"WARNING: client {client_id} has no stored marketplace_id, "
        f"falling back to env MARKETPLACE_ID_UAE={legacy_marketplace}"
    )
    return legacy_marketplace, legacy_endpoint
