"""
Portable deployment configuration.
Auto-detects environment and generates correct URLs.
Works on localhost, Streamlit Cloud, and custom domains WITHOUT code changes.
"""

import streamlit as st
import os
from typing import Optional


def get_base_url() -> str:
    """
    Automatically detect the base URL for the current deployment.

    Works across:
    - Local development (localhost)
    - Streamlit Cloud (*.streamlit.app)
    - Custom domains (your-domain.com)

    Returns:
        Base URL without trailing slash (e.g., "https://app.saddl.io")
    """

    # METHOD 1: Check explicit environment variable (highest priority)
    # Good for containerized deployments (Docker, Kubernetes) or manual override
    base_url = os.environ.get('APP_BASE_URL')
    if base_url:
        return base_url.rstrip('/')

    # METHOD 2: Detect Streamlit Cloud via environment variables
    # Streamlit Cloud sets specific env vars we can check
    # HOSTNAME on Streamlit Cloud is typically a container ID like "ip-10-..."
    hostname = os.environ.get('HOSTNAME', '')

    # Check if running on Streamlit Cloud (headless mode + non-local hostname)
    try:
        is_headless = st.get_option("server.headless")

        # Streamlit Cloud runs in headless mode with container-style hostnames
        if is_headless:
            # Not localhost, likely cloud deployment
            if hostname and not hostname.startswith('localhost') and not hostname.startswith('127.'):
                return "https://saddle-adpulse.streamlit.app"
    except Exception:
        pass

    # METHOD 3: Check if we're in a cloud environment by checking common indicators
    # Streamlit Cloud containers have specific characteristics
    try:
        import socket
        local_hostname = socket.gethostname()

        # Local dev machines usually have recognizable hostnames
        # Cloud containers have IDs like "ip-10-0-1-234" or random strings
        is_likely_local = any([
            'macbook' in local_hostname.lower(),
            'imac' in local_hostname.lower(),
            '.local' in local_hostname.lower(),
            'desktop' in local_hostname.lower(),
            'laptop' in local_hostname.lower(),
            local_hostname.lower() == 'localhost',
            local_hostname.startswith('127.'),
        ])

        if not is_likely_local:
            # Likely running on Streamlit Cloud or other cloud platform
            return "https://saddle-adpulse.streamlit.app"
    except Exception:
        pass

    # METHOD 4: Try Streamlit config for local development
    try:
        port = st.get_option("server.port") or 8501
        return f"http://localhost:{port}"
    except Exception:
        pass

    # METHOD 5: Ultimate fallback
    return "http://localhost:8501"


def get_environment() -> str:
    """
    Detect current deployment environment.
    
    Returns:
        "local", "streamlit_cloud", or "production"
    """
    base_url = get_base_url()
    
    if "localhost" in base_url or "127.0.0.1" in base_url:
        return "local"
    elif "streamlit.app" in base_url:
        return "streamlit_cloud"
    else:
        return "production"


def build_share_url(report_id: str) -> str:
    """
    Build shareable report URL for current environment.
    
    Args:
        report_id: Unique 8-character report identifier
    
    Returns:
        Complete shareable URL
        
    Examples:
        Local: http://localhost:8501?page=shared_report&id=a7f3e9c1
        Cloud: https://saddle.streamlit.app?page=shared_report&id=a7f3e9c1
        Custom: https://app.saddl.io?page=shared_report&id=a7f3e9c1
    """
    base_url = get_base_url()
    return f"{base_url}?page=shared_report&id={report_id}"


def get_display_url() -> str:
    """
    Get user-friendly display URL for current environment.
    
    Returns:
        Formatted URL for display purposes
    """
    base_url = get_base_url()
    env = get_environment()
    
    if env == "local":
        return "localhost (development)"
    elif env == "streamlit_cloud":
        return base_url.replace("https://", "").replace("http://", "")
    else:
        return base_url.replace("https://", "").replace("http://", "")
