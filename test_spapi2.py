import sys
import os
import traceback
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv(".env")

# Add desktop to path
sys.path.insert(0, os.path.abspath('.'))

def test():
    cfg = {
        "endpoint": "https://sellingpartnerapi-eu.amazon.com",
        "marketplace_uae": "A2VIGQ35RCS4UG",
        "spapi_account_id": "s2c_uae_test",
        "aws_access_key": os.getenv("AWS_ACCESS_KEY_ID"),
        "aws_secret_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "aws_region": os.getenv("AWS_REGION"),
        "lwa_client_id": os.getenv("LWA_CLIENT_ID"),
        "lwa_client_secret": os.getenv("LWA_CLIENT_SECRET"),
    }
    # Set required env vars since get_token will need them
    os.environ["MARKETPLACE_ID_UAE"] = cfg["marketplace_uae"]
    
    # Needs to be active account's refresh token
    import psycopg2
    db_url = os.getenv("DATABASE_URL")
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT lwa_refresh_token FROM client_settings WHERE client_id = %s", (cfg["spapi_account_id"],))
            refresh_token = cur.fetchone()[0]
            os.environ["LWA_REFRESH_TOKEN_UAE"] = refresh_token
            cfg["refresh_token_uae"] = refresh_token

    print("Fetching token...")
    try:
        from pipelines.sp_api_client import get_token as sp_get_token
        token = sp_get_token(force_refresh=True)
        print("Token fetched")
    except Exception as e:
        print(f"Failed to fetch token: {e}")
        traceback.print_exc()
        return
    
    query_id = "317580020511"
    
    print("Polling...")
    from pipeline.data_kiosk import poll_query, download_document
    status = poll_query(cfg, token, query_id, max_wait_minutes=1)
    print(f"Status: {status.get('processingStatus')}")
    
    doc_id = status.get('dataDocumentId')
    if doc_id:
        print("Downloading...")
        records = download_document(cfg, token, doc_id)
        print(f"Got {len(records)} records")
        
        # Print a sample of the actual shape so we can see
        for r in records[:2]:
            print(r)

if __name__ == "__main__":
    test()
