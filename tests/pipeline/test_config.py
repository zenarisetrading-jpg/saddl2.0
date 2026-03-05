"""Config loader tests."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def test_config_raises_on_missing_env_vars():
    from pipeline.config import get_config

    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(EnvironmentError) as exc_info:
            get_config()
        assert "LWA_CLIENT_ID" in str(exc_info.value)


def test_config_loads_all_required_keys():
    from pipeline.config import get_config

    mock_env = {
        "LWA_CLIENT_ID": "cid",
        "LWA_CLIENT_SECRET": "csec",
        "LWA_REFRESH_TOKEN_UAE": "rtoken",
        "AWS_ACCESS_KEY_ID": "awskey",
        "AWS_SECRET_ACCESS_KEY": "awssecret",
        "DATABASE_URL": "postgresql://localhost/test",
    }
    with patch.dict(os.environ, mock_env, clear=True):
        config = get_config()
        assert config["lwa_client_id"] == "cid"
        assert config["marketplace_uae"] == "A2VIGQ35RCS4UG"
        assert config["aws_region"] == "eu-west-1"
