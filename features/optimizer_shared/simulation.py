"""
Optimizer Simulation Engine
Simulate the impact of proposed bid changes on future performance and scenarios.
"""

import pandas as pd
import numpy as np
from features.optimizer_shared.core import ELASTICITY_SCENARIOS

def run_simulation(
    df: pd.DataFrame,
    direct_bids: pd.DataFrame,
    agg_bids: pd.DataFrame,
    harvest_df: pd.DataFrame,
    config: dict,
    date_info: dict
) -> dict:
    """
    Simulate the impact of proposed bid changes on future performance.
    Uses elasticity model with scenario analysis.
    """
    num_weeks = date_info.get("weeks", 1.0)
    
    # Calculate current baseline (raw)
    current_raw = _calculate_baseline(df)
    current = _normalize_to_weekly(current_raw, num_weeks)
    
    # Combine bid changes
    all_bids = pd.concat([direct_bids, agg_bids]) if not direct_bids.empty or not agg_bids.empty else pd.DataFrame()
    
    if not all_bids.empty:
        all_bids = all_bids.copy()
        
        # Safely extract CPC and New Bid
        if "Cost Per Click (CPC)" in all_bids.columns:
            all_bids["CPC"] = pd.to_numeric(all_bids["Cost Per Click (CPC)"], errors="coerce").fillna(0)
        else:
            all_bids["CPC"] = pd.to_numeric(all_bids.get("CPC", 0), errors="coerce").fillna(0) if "CPC" in all_bids.columns else 0.0
            
        if "New Bid" in all_bids.columns:
             all_bids["New Bid"] = pd.to_numeric(all_bids["New Bid"], errors="coerce").fillna(0)
        else:
             all_bids["New Bid"] = 0.0
             
        all_bids["Bid_Change_Pct"] = np.where(
            all_bids["CPC"] > 0,
            (all_bids["New Bid"] - all_bids["CPC"]) / all_bids["CPC"],
            0
        )
    
    # Count recommendations
    total_recs = len(all_bids)
    hold_count = 0
    actual_changes = 0
    
    if not all_bids.empty and "Reason" in all_bids.columns:
        hold_mask = all_bids["Reason"].astype(str).str.contains("Hold", case=False, na=False)
        hold_count = hold_mask.sum()
        actual_changes = (~hold_mask).sum()
    
    # Run scenarios
    scenarios = {}
    for name, elasticity in ELASTICITY_SCENARIOS.items():
        forecast_raw = _forecast_scenario(all_bids, harvest_df, elasticity, current_raw, config)
        forecast = _normalize_to_weekly(forecast_raw, num_weeks)
        scenarios[name] = forecast
    
    scenarios["current"] = current
    
    # Calculate sensitivity
    sensitivity_df = _calculate_sensitivity(all_bids, harvest_df, ELASTICITY_SCENARIOS["expected"], current_raw, config, num_weeks)
    
    # Analyze risks
    risk_analysis = _analyze_risks(all_bids)
    
    return {
        "scenarios": scenarios,
        "sensitivity": sensitivity_df,
        "risk_analysis": risk_analysis,
        "date_info": date_info,
        "diagnostics": {
            "total_recommendations": total_recs,
            "actual_changes": actual_changes,
            "hold_count": hold_count,
            "harvest_count": len(harvest_df)
        }
    }


def _calculate_baseline(df: pd.DataFrame) -> dict:
    """Calculate current performance baseline."""
    total_clicks = df["Clicks"].sum()
    total_spend = df["Spend"].sum()
    total_sales = df["Sales"].sum()
    total_orders = df["Orders"].sum()
    total_impressions = df["Impressions"].sum() if "Impressions" in df.columns else 0
    
    return {
        "clicks": total_clicks,
        "spend": total_spend,
        "sales": total_sales,
        "orders": total_orders,
        "impressions": total_impressions,
        "cpc": total_spend / total_clicks if total_clicks > 0 else 0,
        "cvr": total_orders / total_clicks if total_clicks > 0 else 0,
        "roas": total_sales / total_spend if total_spend > 0 else 0,
        "acos": (total_spend / total_sales * 100) if total_sales > 0 else 0,
        "ctr": (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    }

def _normalize_to_weekly(metrics: dict, num_weeks: float) -> dict:
    """Normalize metrics to weekly averages."""
    if num_weeks <= 0:
        num_weeks = 1.0
    
    return {
        "clicks": metrics["clicks"] / num_weeks,
        "spend": metrics["spend"] / num_weeks,
        "sales": metrics["sales"] / num_weeks,
        "orders": metrics["orders"] / num_weeks,
        "impressions": metrics.get("impressions", 0) / num_weeks,
        "cpc": metrics.get("cpc", 0),
        "cvr": metrics.get("cvr", 0),
        "roas": metrics.get("roas", 0),
        "acos": metrics.get("acos", 0),
        "ctr": metrics.get("ctr", 0)
    }

def _forecast_scenario(
    bid_changes: pd.DataFrame,
    harvest_df: pd.DataFrame,
    elasticity: dict,
    baseline: dict,
    config: dict
) -> dict:
    """Forecast performance for a single scenario."""
    forecasted_changes = []
    
    # Part 1: Process bid changes
    if not bid_changes.empty:
        for _, row in bid_changes.iterrows():
            bid_change_pct = row.get("Bid_Change_Pct", 0)
            reason = str(row.get("Reason", "")).lower()
            
            # Skip holds
            if "hold" in reason or abs(bid_change_pct) < 0.005:
                continue
            
            current_clicks = float(row.get("Clicks", 0) or 0)
            current_spend = float(row.get("Spend", 0) or 0)
            current_orders = float(row.get("Orders", 0) or 0)
            current_sales = float(row.get("Sales", 0) or 0)
            current_cpc = float(row.get("CPC", 0) or row.get("Cost Per Click (CPC)", 0) or 0)
            
            if current_clicks == 0 and current_cpc == 0:
                continue
            
            current_cvr = current_orders / current_clicks if current_clicks > 0 else 0
            current_aov = current_sales / current_orders if current_orders > 0 else 0
            current_roas = current_sales / current_spend if current_spend > 0 else 0
            
            if current_aov == 0 and baseline["orders"] > 0:
                current_aov = baseline["sales"] / baseline["orders"]
            
            # Calculate baseline ROAS for comparison
            baseline_roas = baseline["sales"] / baseline["spend"] if baseline["spend"] > 0 else 1.0
            
            # Apply elasticity with ROAS-aware adjustment
            new_cpc = current_cpc * (1 + elasticity["cpc"] * bid_change_pct)
            new_clicks = current_clicks * (1 + elasticity["clicks"] * bid_change_pct)
            
            # KEY FIX: When DECREASING bids on LOW-ROAS targets, CVR doesn't decrease
            # because we're cutting wasteful traffic, not good traffic
            if bid_change_pct < 0 and current_roas < baseline_roas:
                # Below-average ROAS target: cutting this traffic is GOOD
                # CVR stays same or improves slightly (removing untargeted clicks)
                new_cvr = current_cvr * (1 + abs(elasticity["cvr"] * bid_change_pct * 0.2))
            else:
                # Normal case: CVR follows elasticity
                new_cvr = current_cvr * (1 + elasticity["cvr"] * bid_change_pct)
            
            new_orders = new_clicks * new_cvr
            new_sales = new_orders * current_aov
            new_spend = new_clicks * new_cpc
            
            forecasted_changes.append({
                "delta_clicks": new_clicks - current_clicks,
                "delta_spend": new_spend - current_spend,
                "delta_sales": new_sales - current_sales,
                "delta_orders": new_orders - current_orders
            })
    
    # Part 2: Process harvest campaigns
    if not harvest_df.empty:
        efficiency = config.get("HARVEST_EFFICIENCY_MULTIPLIER", 1.15)
        
        for _, row in harvest_df.iterrows():
            base_clicks = float(row.get("Clicks", 0) or 0)
            base_spend = float(row.get("Spend", 0) or 0)
            base_orders = float(row.get("Orders", 0) or 0)
            base_sales = float(row.get("Sales", 0) or 0)
            base_cpc = float(row.get("CPC", 0) or 0)
            
            if base_clicks < 5:
                continue
            
            # Use launch multiplier (2x) for harvest bids
            launch_mult = config.get("HARVEST_LAUNCH_MULTIPLIER", 2.0)
            base_cvr = base_orders / base_clicks if base_clicks > 0 else 0
            base_aov = base_sales / base_orders if base_orders > 0 else 0
            
            fore_clicks = base_clicks
            fore_cpc = base_cpc * 0.90  # Exact match is typically more efficient
            fore_cvr = base_cvr * efficiency  # 1.15x CVR improvement (default)
            
            fore_orders = fore_clicks * fore_cvr
            fore_sales = fore_orders * base_aov
            fore_spend = fore_clicks * fore_cpc
            
            forecasted_changes.append({
                "delta_clicks": fore_clicks - base_clicks,
                "delta_spend": fore_spend - base_spend,  # Should be NEGATIVE (savings!)
                "delta_sales": fore_sales - base_sales,  # Should be POSITIVE (better CVR!)
                "delta_orders": fore_orders - base_orders
            })
    
    # Aggregate changes
    if not forecasted_changes:
        return baseline.copy()
    
    total_delta = {
        "clicks": sum(fc["delta_clicks"] for fc in forecasted_changes),
        "spend": sum(fc["delta_spend"] for fc in forecasted_changes),
        "sales": sum(fc["delta_sales"] for fc in forecasted_changes),
        "orders": sum(fc["delta_orders"] for fc in forecasted_changes)
    }
    
    new_clicks = max(0, baseline["clicks"] + total_delta["clicks"])
    new_spend = max(0, baseline["spend"] + total_delta["spend"])
    new_sales = max(0, baseline["sales"] + total_delta["sales"])
    new_orders = max(0, baseline["orders"] + total_delta["orders"])
    
    return {
        "clicks": new_clicks,
        "spend": new_spend,
        "sales": new_sales,
        "orders": new_orders,
        "impressions": baseline.get("impressions", 0),
        "cpc": new_spend / new_clicks if new_clicks > 0 else 0,
        "cvr": new_orders / new_clicks if new_clicks > 0 else 0,
        "roas": new_sales / new_spend if new_spend > 0 else 0,
        "acos": (new_spend / new_sales * 100) if new_sales > 0 else 0,
        "ctr": baseline.get("ctr", 0)
    }

def _calculate_sensitivity(
    bid_changes: pd.DataFrame,
    harvest_df: pd.DataFrame,
    elasticity: dict,
    baseline: dict,
    config: dict,
    num_weeks: float
) -> pd.DataFrame:
    """Calculate sensitivity analysis at different bid adjustment levels."""
    adjustments = ["-30%", "-20%", "-10%", "+0%", "+10%", "+20%", "+30%"]
    multipliers = [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]
    
    results = []
    for adj, mult in zip(adjustments, multipliers):
        # Scale bid changes
        if not bid_changes.empty:
            scaled_bids = bid_changes.copy()
            scaled_bids["Bid_Change_Pct"] = scaled_bids["Bid_Change_Pct"] * mult
        else:
            scaled_bids = pd.DataFrame()
        
        forecast = _forecast_scenario(scaled_bids, harvest_df, elasticity, baseline, config)
        normalized = _normalize_to_weekly(forecast, num_weeks)
        
        results.append({
            "Bid_Adjustment": adj,
            "Spend": normalized["spend"],
            "Sales": normalized["sales"],
            "ROAS": normalized["roas"],
            "Orders": normalized["orders"],
            "ACoS": normalized["acos"]
        })
    
    return pd.DataFrame(results)

def _analyze_risks(bid_changes: pd.DataFrame) -> dict:
    """Analyze risks in proposed bid changes."""
    if bid_changes.empty:
        return {"summary": {"high_risk_count": 0, "medium_risk_count": 0, "low_risk_count": 0}, "high_risk": []}
    
    high_risk = []
    medium_risk = 0
    low_risk = 0
    
    for _, row in bid_changes.iterrows():
        reason = str(row.get("Reason", "")).lower()
        if "hold" in reason:
            continue
        
        bid_change = row.get("Bid_Change_Pct", 0)
        clicks = row.get("Clicks", 0)
        
        risk_factors = []
        
        # Large bid change
        if abs(bid_change) > 0.25:
            risk_factors.append(f"Large change ({bid_change*100:+.0f}%)")
        
        # Low data
        if clicks < 10:
            risk_factors.append(f"Low data ({clicks} clicks)")
        
        # Classify
        if len(risk_factors) >= 2 or abs(bid_change) > 0.40:
            high_risk.append({
                "keyword": row.get("Targeting", row.get("Customer Search Term", "")),
                "campaign": row.get("Campaign Name", ""),
                "bid_change": f"{bid_change*100:+.0f}%",
                "current_bid": row.get("CPC", row.get("Cost Per Click (CPC)", 0)),
                "factors": ", ".join(risk_factors)
            })
        elif len(risk_factors) == 1:
            medium_risk += 1
        else:
            low_risk += 1
    
    return {
        "summary": {
            "high_risk_count": len(high_risk),
            "medium_risk_count": medium_risk,
            "low_risk_count": low_risk
        },
        "high_risk": high_risk
    }
