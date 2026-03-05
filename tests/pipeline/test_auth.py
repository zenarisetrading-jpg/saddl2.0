"""Auth helper tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pipeline.auth import get_token, make_headers


MOCK_CONFIG = {
    "lwa_client_id": "test_client_id",
    "lwa_client_secret": "test_secret",
    "refresh_token_uae": "test_refresh_token",
    "aws_access_key": "test_aws_key",
    "aws_secret_key": "test_aws_secret",
    "aws_region": "eu-west-1",
}


def test_get_token_returns_access_token():
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "test_access_token_123"}
    mock_response.raise_for_status = MagicMock()

    with patch("pipeline.auth.requests.post", return_value=mock_response) as mock_post:
        token = get_token(MOCK_CONFIG)
        assert token == "test_access_token_123"
        call_data = mock_post.call_args[1]["data"]
        assert call_data["client_id"] == "test_client_id"
        assert call_data["grant_type"] == "refresh_token"


def test_make_headers_contains_required_fields():
    headers = make_headers("my_token")
    assert headers["x-amz-access-token"] == "my_token"
    assert headers["Content-Type"] == "application/json"


def test_make_headers_function_name_not_headers():
    from pipeline import auth

    assert not hasattr(auth, "headers")
