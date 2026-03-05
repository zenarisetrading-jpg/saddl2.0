import sys
import os
import json
import time
from pathlib import Path

# Add desktop to path
desktop_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(desktop_dir))

from pipelines.sp_api_client import get_settings, get_token, get_auth, make_headers
import requests
import gzip
import csv
import io

def run():
    settings = get_settings()
    access_token = get_token()

    print("Requesting report...")
    url = f"{settings.endpoint}/reports/2021-06-30/reports"
    response = requests.post(
        url,
        headers=make_headers(access_token),
        auth=get_auth(),
        json={
            "reportType": "GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA",
            "marketplaceIds": [settings.marketplace_id]
        },
        timeout=60,
    )
    if response.status_code != 202:
        print("Failed to request report:", response.status_code, response.text)
        return

    report_id = response.json()["reportId"]
    print(f"Report ID: {report_id}")

    while True:
        status_url = f"{settings.endpoint}/reports/2021-06-30/reports/{report_id}"
        resp = requests.get(status_url, headers=make_headers(access_token), auth=get_auth(), timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        status = payload.get("processingStatus")
        print(f"Status: {status}")
        
        if status == "DONE":
            document_id = payload["reportDocumentId"]
            break
        if status in {"CANCELLED", "FATAL"}:
            print("Report failed.")
            return
        time.sleep(10)

    doc_url = f"{settings.endpoint}/reports/2021-06-30/documents/{document_id}"
    doc_resp = requests.get(doc_url, headers=make_headers(access_token), auth=get_auth(), timeout=60)
    doc_resp.raise_for_status()
    doc_info = doc_resp.json()
    download_url = doc_info["url"]
    compression = doc_info.get("compressionAlgorithm")
    
    print("Downloading document...")
    file_resp = requests.get(download_url, timeout=120)
    file_resp.raise_for_status()
    
    if compression == "GZIP":
        content = gzip.decompress(file_resp.content).decode('utf-8')
    else:
        content = file_resp.text

    lines = content.splitlines()
    print("Report Headers:")
    if lines:
        print(lines[0])
        print("First data row:")
        if len(lines) > 1:
            print(lines[1])
            
if __name__ == "__main__":
    run()
