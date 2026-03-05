from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import datetime

# ==========================================
# SCHEMA DEFINITION
# ==========================================

REQUIRED_KEYS = {
    "bids_old", "bids_new", "negatives", "paused", "harvested", 
    "term_metrics", "simulation", "run_metadata"
}

def validate_run_outputs(run_outputs: Dict[str, Any]) -> bool:
    """
    Enforce RUN_OUTPUTS schema contract.
    Returns True if valid, raises AssertionError if invalid.
    """
    if not isinstance(run_outputs, dict):
        raise AssertionError("run_outputs must be a dictionary")
    
    missing = REQUIRED_KEYS - run_outputs.keys()
    if missing:
        raise AssertionError(f"Missing required keys: {missing}")
        
    # Type checks for core buckets
    if not isinstance(run_outputs["bids_old"], dict): raise AssertionError("bids_old must be dict")
    if not isinstance(run_outputs["bids_new"], dict): raise AssertionError("bids_new must be dict")
    if not isinstance(run_outputs["negatives"], list): raise AssertionError("negatives must be list")
    if not isinstance(run_outputs["paused"], list): raise AssertionError("paused must be list")
    if not isinstance(run_outputs["harvested"], list): raise AssertionError("harvested must be list")
    if not isinstance(run_outputs["term_metrics"], dict): raise AssertionError("term_metrics must be dict")
    
    # Simulation can be None or dict
    if run_outputs["simulation"] is not None and not isinstance(run_outputs["simulation"], dict):
        raise AssertionError("simulation must be dict or None")
        
    return True

# ==========================================
# ADAPTER IMPLEMENTATION
# ==========================================

def adapt_run_outputs(raw_results: Dict[str, Any], run_id: str = "latest") -> Dict[str, Any]:
    """
    Transform legacy optimizer outputs into strict RUN_OUTPUTS schema.
    
    Args:
        raw_results: st.session_state['optimizer_results'] from legacy optimizer.
        run_id: Identifier for the run (default: "latest")
        
    Returns:
        Validated RUN_OUTPUTS dictionary.
    """
    if not raw_results:
        return _empty_run_outputs(run_id)
        
    # 1. Bids Extraction (Old vs New)
    # ------------------------------------------------
    bids_old = {}
    bids_new = {}
    paused = []
    
    # Combined bids dataframe (exact, pt, agg, auto are disjoint)
    all_bids_dfs = [
        raw_results.get("bids_exact", pd.DataFrame()),
        raw_results.get("bids_pt", pd.DataFrame()),
        raw_results.get("bids_agg", pd.DataFrame()),
        raw_results.get("bids_auto", pd.DataFrame())
    ]
    
    for df in all_bids_dfs:
        if df.empty: continue
        
        # DEBUG: Print columns to identify mismatch
        print(f"DEBUG ADAPTER: Processing Bids DF columns: {df.columns.tolist()}")
        if not df.empty:
            print(f"DEBUG ADAPTER: First row: {df.iloc[0].to_dict()}")

        # Ensure ID availability (fallback to names if IDs missing, consistent with key usage)
        # Using a composite key for uniqueness in dict: Campaign|AdGroup|Target
        for _, row in df.iterrows():
            # Create a robust unique key
            key_parts = [
                str(row.get("Campaign Name", "")),
                str(row.get("Ad Group Name", "")),
                str(row.get("Targeting", "") or row.get("Term", ""))
            ]
            target_id = "|".join(key_parts)
            
            current_bid = float(row.get("Current Bid") or row.get("CPC", 0))
            new_bid = float(row.get("New Bid", 0))
            
            bids_old[target_id] = current_bid
            bids_new[target_id] = new_bid
            
            # Paused check (Legacy optimizer sets New Bid to 0 for pauses in some contexts)
            # OR explicit state check if available
            if new_bid == 0:
                paused.append(target_id)

    # 2. Negatives Extraction
    # ------------------------------------------------
    negatives = []
    neg_dfs = [
        raw_results.get("neg_kw", pd.DataFrame()),
        raw_results.get("neg_pt", pd.DataFrame())
    ]
    
    for df in neg_dfs:
        if df.empty: continue
        for _, row in df.iterrows():
            key_parts = [
                str(row.get("Campaign Name", "")),
                str(row.get("Ad Group Name", "")),
                str(row.get("Term", ""))
            ]
            negatives.append("|".join(key_parts))

    # 3. Harvest Extraction
    # ------------------------------------------------
    harvested = []
    harvest_df = raw_results.get("harvest", pd.DataFrame())
    if not harvest_df.empty:
        for _, row in harvest_df.iterrows():
            # Harvest candidates are new terms
            term = str(row.get("Customer Search Term", "") or row.get("Harvest_Term", ""))
            harvested.append(term)

    # 4. Term Metrics Extraction (Source of Truth for stats)
    # ------------------------------------------------
    term_metrics = {}
    df_raw = raw_results.get("df", pd.DataFrame())
    
    if not df_raw.empty:
        # Group by Target ID logic to match bid keys
        # Note: 'df' is Search Term Report, so we aggregate to Target level
        # For simplicity in this adapter, we map by the same keys used for bids
        # Campaign + Ad Group + Targeting
        
        # Ensure required columns exist
        req_cols = ["Campaign Name", "Ad Group Name", "Targeting", "Spend", "Sales", "Orders"]
        available_cols = [c for c in req_cols if c in df_raw.columns]
        
        if len(available_cols) == len(req_cols):
            # Pre-calc metrics
            # Note: "Targeting" column in STR might map multiple search terms. 
            # We treat the input DF as the source of "spend_14d" (metrics from the run window)
            grouped = df_raw.groupby(["Campaign Name", "Ad Group Name", "Targeting"]).agg({
                "Spend": "sum",
                "Sales": "sum"
            }).reset_index()
            
            for _, row in grouped.iterrows():
                key_parts = [
                    str(row["Campaign Name"]),
                    str(row["Ad Group Name"]),
                    str(row["Targeting"])
                ]
                target_id = "|".join(key_parts)
                
                spend = float(row["Spend"])
                sales = float(row["Sales"])
                roas = sales / spend if spend > 0 else 0.0
                acos = (spend / sales * 100) if sales > 0 else 0.0
                
                # NOTE: Intentionally calling it spend_14d per PRD semantic, 
                # even if actual run window varies.
                term_metrics[target_id] = {
                    "spend_14d": spend,
                    "sales_14d": sales,
                    "roas": roas,
                    "acos": acos
                }

    # 5. Simulation Extraction (Expected Only)
    # ------------------------------------------------
    simulation = None
    sim_results = raw_results.get("simulation", {})
    if sim_results and "scenarios" in sim_results:
        scenarios = sim_results["scenarios"]
        expected = scenarios.get("expected")
        current_baseline = scenarios.get("current")
        
        if expected and current_baseline:
            # Calculate aggregate ACOS for efficiency gain
            old_spend = float(current_baseline.get("spend", 0))
            old_sales = float(current_baseline.get("sales", 0))
            new_spend = float(expected.get("spend", 0))
            new_sales = float(expected.get("sales", 0))
            
            old_acos = (old_spend / old_sales * 100) if old_sales > 0 else 0.0
            new_acos = (new_spend / new_sales * 100) if new_sales > 0 else 0.0
            
            simulation = {
                "old_acos": old_acos,
                "new_acos": new_acos
            }

    # 6. Metadata
    # ------------------------------------------------
    run_metadata = {
        "timestamp": datetime.now(),
        "run_id": run_id
    }

    output = {
        "bids_old": bids_old,
        "bids_new": bids_new,
        "negatives": negatives,
        "paused": paused,
        "harvested": harvested,
        "term_metrics": term_metrics,
        "simulation": simulation,
        "run_metadata": run_metadata
    }
    
    # Final Validation
    try:
        validate_run_outputs(output)
    except AssertionError as e:
        # Fallback handling or re-raise depending on strictness. 
        # For now, we log and re-raise to fail fast as requested.
        print(f"Adapter Validation Failed: {e}")
        raise e
        
    return output

def _empty_run_outputs(run_id: str) -> Dict[str, Any]:
    return {
        "bids_old": {},
        "bids_new": {},
        "negatives": [],
        "paused": [],
        "harvested": [],
        "term_metrics": {},
        "simulation": None,
        "run_metadata": {
            "timestamp": datetime.now(),
            "run_id": run_id
        }
    }
