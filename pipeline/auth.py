"""Authentication helpers for SP-API calls."""

from __future__ import annotations

import requests
from requests_aws4auth import AWS4Auth


def get_token(config: dict) -> str:
    response = requests.post(
        "https://api.amazon.com/auth/o2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": config["refresh_token_uae"],
            "client_id": config["lwa_client_id"],
            "client_secret": config["lwa_client_secret"],
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def get_auth(config: dict) -> AWS4Auth:
    return AWS4Auth(
        config["aws_access_key"],
        config["aws_secret_key"],
        config["aws_region"],
        "execute-api",
    )


def make_headers(token: str) -> dict:
    # Never rename this to "headers" to avoid request internals collisions.
    return {
        "x-amz-access-token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
