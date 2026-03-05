import os
import urllib.parse
import uuid
import streamlit as st

def generate_amazon_oauth_url(client_id: str | None = None, force_new_state: bool = False) -> str:
    """
    Generates the Amazon SP-API OAuth consent URL.
    Creates a unique state token to track this connection request.
    """
    # Existing-account path: use the provided client_id as OAuth state.
    # Callback persists this value as client_settings.client_id.
    if client_id:
        state = str(client_id)
    else:
        # Onboarding/new-account path keeps previous behavior.
        if force_new_state or 'amazon_oauth_state' not in st.session_state:
            st.session_state['amazon_oauth_state'] = f"sc-{uuid.uuid4().hex[:12]}"
        state = st.session_state['amazon_oauth_state']

    # SP-API Application ID (amzn1.sellerapps.app.* or amzn1.sp.solution.*)
    # This is the App ID from Seller Central → Partner Network → Develop Apps
    # NOTE: This is distinct from LWA_CLIENT_ID (amzn1.application-oa2-client.*),
    # which is only used for token exchange — NOT for the consent URL.
    application_id = os.environ.get("SP_API_APPLICATION_ID", "")
    if not application_id:
        raise EnvironmentError(
            "SP_API_APPLICATION_ID is not set. Add it to your .env file. "
            "Find it in Seller Central → Partner Network → Develop Apps."
        )

    params = {
        "application_id": application_id,
        "state": state,
        "version": "beta",
    }

    base_url = "https://sellercentral.amazon.com/apps/authorize/consent"
    return f"{base_url}?{urllib.parse.urlencode(params)}"
