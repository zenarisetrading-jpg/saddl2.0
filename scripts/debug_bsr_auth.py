
import os
import sys
import logging
from pprint import pprint
import requests

# Add desktop to path so imports work
current_dir = os.path.dirname(os.path.abspath(__file__))
desktop_path = os.path.join(current_dir, 'desktop')
if desktop_path not in sys.path:
    sys.path.append(desktop_path)

from pipeline.config import get_config
from pipeline.auth import get_token, get_auth, make_headers

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def debug_bsr_request():
    try:
        config = get_config()
        print("Config loaded successfully.")
        print(f"Region: {config['aws_region']}")
        print(f"Marketplace: {config['marketplace_uae']}")
        print(f"Endpoint: {config['endpoint']}")
        
        print("Authenticating...")
        token = get_token(config)
        print(f"Token obtained. Length: {len(token)}")
        
        print("Making request to getMarketplaceParticipations...")
        mp_url = f"{config['endpoint']}/sellers/v1/marketplaceParticipations"
        mp_response = requests.get(
            mp_url,
            headers=make_headers(token),
            auth=get_auth(config),
            timeout=30
        )
        print(f"MP Response Status: {mp_response.status_code}")
        if mp_response.status_code != 200:
             print(f"MP Response Text: {mp_response.text}")
        else:
             print("Marketplace Participations specific check passed.")

        asin = "B00YFU7NAQ"
        url = f"{config['endpoint']}/catalog/2022-04-01/items/{asin}"
        params = {
            "marketplaceIds": config["marketplace_uae"],
            "includedData": "salesRanks",
        }
        
        print(f"Making request to {url}...")
        auth = get_auth(config)
        headers = make_headers(token)
        
        response = requests.get(
            url,
            headers=headers,
            auth=auth,
            params=params,
            timeout=30
        )
        
        print(f"Response Status: {response.status_code}")
        try:
            pprint(response.json())
        except:
            print(f"Response Text: {response.text}")
            
    except Exception as e:
        logger.exception("Debug script failed")

if __name__ == "__main__":
    # Add desktop to path so imports work
    current_dir = os.getcwd()
    if current_dir.endswith('saddle/saddle'):
        sys.path.append(os.path.join(current_dir, 'desktop'))
    elif current_dir.endswith('desktop'):
        sys.path.append(current_dir)
        
    debug_bsr_request()
