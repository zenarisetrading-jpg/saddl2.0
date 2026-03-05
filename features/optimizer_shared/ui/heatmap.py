"""
Optimizer Heatmap UI
Visualizes performance data using a matrix heatmap.
"""

import pandas as pd
import numpy as np

def create_heatmap(
    df: pd.DataFrame,
    config: dict,
    harvest_df: pd.DataFrame,
    neg_kw: pd.DataFrame,
    neg_pt: pd.DataFrame,
    direct_bids: pd.DataFrame,
    agg_bids: pd.DataFrame
) -> pd.DataFrame:
    """Create performance heatmap with action tracking."""
    grouped = df.groupby(["Campaign Name", "Ad Group Name"]).agg({
        "Clicks": "sum", "Spend": "sum", "Sales_Attributed": "sum",
        "Orders_Attributed": "sum", "Impressions": "sum"
    }).reset_index()
    
    # Rename to standard names for consistency
    grouped = grouped.rename(columns={"Sales_Attributed": "Sales", "Orders_Attributed": "Orders"})
    
    grouped["CTR"] = np.where(grouped["Impressions"] > 0, grouped["Clicks"] / grouped["Impressions"] * 100, 0)
    grouped["CVR"] = np.where(grouped["Clicks"] > 0, grouped["Orders"] / grouped["Clicks"] * 100, 0)
    grouped["ROAS"] = np.where(grouped["Spend"] > 0, grouped["Sales"] / grouped["Spend"], 0)
    grouped["ACoS"] = np.where(grouped["Sales"] > 0, grouped["Spend"] / grouped["Sales"] * 100, 999)
    
    grouped["Harvest_Count"] = 0
    grouped["Negative_Count"] = 0
    grouped["Bid_Increase_Count"] = 0
    grouped["Bid_Decrease_Count"] = 0
    grouped["Actions_Taken"] = ""
    
    all_bids = pd.concat([direct_bids, agg_bids]) if not direct_bids.empty or not agg_bids.empty else pd.DataFrame()
    negatives_df = pd.concat([neg_kw, neg_pt]) if not neg_kw.empty or not neg_pt.empty else pd.DataFrame()

    for idx, row in grouped.iterrows():
        camp, ag = row["Campaign Name"], row["Ad Group Name"]
        
        # Safely filter dataframes even if empty or missing columns
        h_match = pd.DataFrame()
        if not harvest_df.empty and "Campaign Name" in harvest_df.columns:
            h_match = harvest_df[(harvest_df["Campaign Name"] == camp) & (harvest_df.get("Ad Group Name", "") == ag)]
            
        n_match = pd.DataFrame()
        if not negatives_df.empty and "Campaign Name" in negatives_df.columns:
            n_match = negatives_df[(negatives_df["Campaign Name"] == camp) & (negatives_df.get("Ad Group Name", "") == ag)]
            
        b_match = pd.DataFrame()
        if not all_bids.empty and "Campaign Name" in all_bids.columns:
            b_match = all_bids[(all_bids["Campaign Name"] == camp) & (all_bids.get("Ad Group Name", "") == ag)]
        
        grouped.at[idx, "Harvest_Count"] = len(h_match)
        grouped.at[idx, "Negative_Count"] = len(n_match)
        
        # Collect reasons for Actions
        reasons = []
        if not h_match.empty and "Reason" in h_match.columns:
            reasons.extend(h_match["Reason"].dropna().astype(str).unique().tolist())
            
        if not n_match.empty and "Reason" in n_match.columns:
            reasons.extend(n_match["Reason"].dropna().astype(str).unique().tolist())
            
        if not b_match.empty and "New Bid" in b_match.columns:
            cur_bids = b_match.get("Current Bid", b_match.get("CPC", 0))
            grouped.at[idx, "Bid_Increase_Count"] = (b_match["New Bid"] > cur_bids).sum()
            grouped.at[idx, "Bid_Decrease_Count"] = (b_match["New Bid"] < cur_bids).sum()
            
            if "Reason" in b_match.columns:
                reasons.extend(b_match["Reason"].dropna().astype(str).unique().tolist())
            
        actions = []
        if grouped.at[idx, "Harvest_Count"] > 0: actions.append(f"💎 {int(grouped.at[idx, 'Harvest_Count'])} harvests")
        if grouped.at[idx, "Negative_Count"] > 0: actions.append(f"🛑 {int(grouped.at[idx, 'Negative_Count'])} negatives")
        if grouped.at[idx, "Bid_Increase_Count"] > 0: actions.append(f"⬆️ {int(grouped.at[idx, 'Bid_Increase_Count'])} increases")
        if grouped.at[idx, "Bid_Decrease_Count"] > 0: actions.append(f"⬇️ {int(grouped.at[idx, 'Bid_Decrease_Count'])} decreases")
        
        if actions:
            grouped.at[idx, "Actions_Taken"] = " | ".join(actions)
            # Summarize reasons (top 3 unique)
            unique_reasons = sorted(list(set([r for r in reasons if r])))
            if unique_reasons:
                grouped.at[idx, "Reason_Summary"] = "; ".join(unique_reasons[:3]) + ("..." if len(unique_reasons) > 3 else "")
            else:
                grouped.at[idx, "Reason_Summary"] = "Multiple actions"
        elif row["Clicks"] < config.get("MIN_CLICKS_EXACT", 5):
            grouped.at[idx, "Actions_Taken"] = "⏸️ Hold (Low volume)"
            grouped.at[idx, "Reason_Summary"] = "Low data volume"
        else:
            grouped.at[idx, "Actions_Taken"] = "✅ No action needed"
            
            # Provide more specific status based on performance
            if row["Sales"] == 0 and row["Spend"] > 10:
                grouped.at[idx, "Reason_Summary"] = "Zero Sales (Monitoring)"
            elif row["ROAS"] < config.get("TARGET_ROAS", 2.5) * 0.8:
                grouped.at[idx, "Reason_Summary"] = "Low Efficiency (Monitoring)"
            else:
                grouped.at[idx, "Reason_Summary"] = "Stable Performance"

    # Priority Scoring
    def score(val, series, high_is_better=True):
        valid = series[series > 0]
        if len(valid) < 2: return 1
        p33, p67 = valid.quantile(0.33), valid.quantile(0.67)
        return (2 if val >= p67 else 1 if val >= p33 else 0) if high_is_better else (2 if val <= p33 else 1 if val <= p67 else 0)

    grouped["Overall_Score"] = (grouped.apply(lambda r: score(r["CTR"], grouped["CTR"]), axis=1) + 
                                grouped.apply(lambda r: score(r["CVR"], grouped["CVR"]), axis=1) + 
                                grouped.apply(lambda r: score(r["ROAS"], grouped["ROAS"]), axis=1) + 
                                grouped.apply(lambda r: score(r["ACoS"], grouped["ACoS"], False), axis=1)) / 4
    
    grouped["Priority"] = grouped["Overall_Score"].apply(lambda x: "🔴 High" if x < 0.7 else ("🟡 Medium" if x < 1.3 else "🟢 Good"))
    return grouped.sort_values("Overall_Score")
