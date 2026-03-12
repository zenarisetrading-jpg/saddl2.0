"""SP-API authentication and request helper utilities."""

from __future__ import annotations

import os
import hashlib
import hmac
from urllib.parse import parse_qsl, quote, urlparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

import requests
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*args, **kwargs):  # type: ignore
        return False
from requests.auth import AuthBase
from requests_aws4auth import AWS4Auth


load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass(frozen=True)
class SPAPISettings:
    lwa_client_id: str
    lwa_client_secret: str
    lwa_refresh_token: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    marketplace_id: str
    endpoint: str


_token_cache: Dict[str, object] = {"access_token": None, "expires_at": None}


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def get_settings(
    marketplace_id: Optional[str] = None,
    region_endpoint: Optional[str] = None,
    lwa_refresh_token: Optional[str] = None,
) -> SPAPISettings:
    """Build SP-API settings.

    When marketplace_id / region_endpoint are provided (per-client dynamic
    values fetched from client_settings), they override the env-var defaults.
    Callers that do not pass these args get the legacy env-var behaviour.
    lwa_refresh_token may be passed explicitly to avoid mutating os.environ.
    """
    effective_marketplace = marketplace_id or os.getenv("MARKETPLACE_ID_UAE", "A2VIGQ35RCS4UG")
    effective_endpoint = (
        f"https://{region_endpoint}"
        if region_endpoint and not region_endpoint.startswith("http")
        else region_endpoint
    ) or os.getenv("SP_API_ENDPOINT", "https://sellingpartnerapi-eu.amazon.com")
    effective_refresh_token = lwa_refresh_token or _required_env("LWA_REFRESH_TOKEN_UAE")
    return SPAPISettings(
        lwa_client_id=_required_env("LWA_CLIENT_ID"),
        lwa_client_secret=_required_env("LWA_CLIENT_SECRET"),
        lwa_refresh_token=effective_refresh_token,
        aws_access_key_id=_required_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_required_env("AWS_SECRET_ACCESS_KEY"),
        aws_region=os.getenv("AWS_REGION", "eu-west-1"),
        marketplace_id=effective_marketplace,
        endpoint=effective_endpoint,
    )


def get_token(force_refresh: bool = False, settings: Optional[SPAPISettings] = None) -> str:
    """Get LWA access token and cache it until 5 minutes before expiry.

    Pass ``settings`` explicitly (e.g. from _run_backfill_for) to avoid
    falling back to env-var resolution and the LWA_REFRESH_TOKEN_UAE requirement.
    """
    now = datetime.now(timezone.utc)
    cached_token = _token_cache.get("access_token")
    cached_expiry = _token_cache.get("expires_at")

    if (
        not force_refresh
        and isinstance(cached_token, str)
        and isinstance(cached_expiry, datetime)
        and cached_expiry - now > timedelta(minutes=5)
    ):
        return cached_token

    resolved_settings = settings or get_settings()
    response = requests.post(
        "https://api.amazon.com/auth/o2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": resolved_settings.lwa_refresh_token,
            "client_id": resolved_settings.lwa_client_id,
            "client_secret": resolved_settings.lwa_client_secret,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    access_token = payload["access_token"]
    expires_in = int(payload.get("expires_in", 3600))

    _token_cache["access_token"] = access_token
    _token_cache["expires_at"] = now + timedelta(seconds=expires_in)
    return access_token


def get_auth() -> AWS4Auth:
    """Build AWS4Auth helper for SP-API requests."""
    settings = get_settings()
    return AWS4Auth(
        settings.aws_access_key_id,
        settings.aws_secret_access_key,
        settings.aws_region,
        "execute-api",
        session_token=os.getenv("AWS_SESSION_TOKEN"),
    )


def make_headers(access_token: str) -> Dict[str, str]:
    """Build headers for SP-API requests."""
    return {
        "x-amz-access-token": access_token,
        "x-amz-date": datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
        "content-type": "application/json",
        "accept": "application/json",
    }
