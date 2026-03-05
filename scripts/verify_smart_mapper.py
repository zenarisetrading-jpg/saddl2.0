
import pandas as pd
import sys
import os

# Add desktop to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from app_core.data_loader import SmartMapper

def verify_smart_mapper():
    print("Verifying SmartMapper against standard Search Term Report columns...\n")

    # Standard Sponsored Products Search Term Report Columns (as of 2024/2025)
    columns_sp = [
        "Date", "Portfolio name", "Currency", "Campaign Name", "Ad Group Name", 
        "Targeting", "Match Type", "Customer Search Term", "Impressions", "Clicks", 
        "Click-Thru Rate (CTR)", "Cost Per Click (CPC)", "Spend", "7 Day Total Sales", 
        "Total Advertising Cost of Sales (ACoS)", "Total Return on Advertising Spend (ROAS)", 
        "7 Day Total Orders", "7 Day Total Units", "7 Day Conversion Rate", 
        "7 Day Advertised SKU Units", "7 Day Other SKU Units", 
        "7 Day Advertised SKU Sales", "7 Day Other SKU Sales"
    ]

    # Sponsored Brands Search Term Report Columns (often differ slightly)
    # Note: SB reports might have "Search Term" instead of "Customer Search Term" or different attribution windows
    columns_sb = [
        "Date", "Portfolio name", "Currency", "Campaign Name", "Ad Group Name", 
        "Targeting", "Match Type", "Customer Search Term", "Impressions", "Clicks", 
        "Click-Thru Rate (CTR)", "Cost Per Click (CPC)", "Spend", "14 Day Total Sales", 
        "Total Advertising Cost of Sales (ACoS)", "Total Return on Advertising Spend (ROAS)", 
        "14 Day Total Orders", "14 Day Total Units", "14 Day Conversion Rate", 
        "14 Day Advertised SKU Units", "14 Day Other SKU Units", 
        "14 Day Advertised SKU Sales", "14 Day Other SKU Sales"
    ]

    # Create dummy DataFrames
    df_sp = pd.DataFrame(columns=columns_sp)
    df_sb = pd.DataFrame(columns=columns_sb)

    print("--- Sponsored Products Report Test ---")
    mapping_sp = SmartMapper.map_columns(df_sp)
    check_mapping(mapping_sp, "SP")

    print("\n--- Sponsored Brands Report Test ---")
    mapping_sb = SmartMapper.map_columns(df_sb)
    check_mapping(mapping_sb, "SB")
    
    # Test for commonly missing or problematic columns
    print("\n--- Edge Case: 'Search Term' instead of 'Customer Search Term' ---")
    df_edge = pd.DataFrame(columns=["Campaign Name", "Ad Group Name", "Search Term", "Spend", "Sales"])
    mapping_edge = SmartMapper.map_columns(df_edge)
    if "Customer Search Term" in mapping_edge:
        print(f"PASS: Mapped 'Search Term' to '{mapping_edge['Customer Search Term']}'")
    else:
        print("FAIL: Did not map 'Search Term'")

def check_mapping(mapping, report_type):
    required_keys = [
        "Campaign Name", "Ad Group Name", "Customer Search Term", 
        "Impressions", "Clicks", "Spend", "Sales", "Orders"
    ]
    
    missing = []
    for key in required_keys:
        if key not in mapping:
            missing.append(key)
            
    if not missing:
        print(f"[{report_type}] SUCCESS: All critical columns mapped.")
    else:
        print(f"[{report_type}] WARNING: Missing critical columns: {missing}")
        
    # Print actual mapping for review
    print(f"[{report_type}] Detailed Mapping:")
    for k, v in mapping.items():
        print(f"  {k} -> {v}")

if __name__ == "__main__":
    verify_smart_mapper()
