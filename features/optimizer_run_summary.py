from typing import Dict, Any, List, Optional
import pandas as pd

class RunSummaryBuilder:
    """
    Pure aggregation layer for Optimizer Overview.
    Consumes validated RUN_OUTPUTS schema to produce deterministic metrics.
    """
    
    def __init__(self, run_outputs: Dict[str, Any]):
        self.raw = run_outputs
        
    def build(self) -> Dict[str, Any]:
        """Build the complete summary dictionary."""
        return {
            "waste_prevented": self._calculate_waste_prevented(),
            "efficiency_gain": self._calculate_efficiency_gain(),
            "bid_stats": self._calculate_bid_stats(),
            "new_targets": self._count_harvests(),
            "negatives": self._count_negatives(),
            "top_opportunities": self._get_top_opportunities(),
            "contribution_chart": self._build_contribution_chart(),
            "metadata": self.raw.get("run_metadata", {})
        }

    # ==========================================
    # METRIC CALCULATIONS
    # ==========================================

    def _calculate_waste_prevented(self) -> Optional[float]:
        """
        Sum of spend_14d for all Targets blocked (Negatives) or Paused.
        Returns None if no data.
        """
        targets_to_exclude = set(self.raw["negatives"] + self.raw["paused"])
        
        if not targets_to_exclude:
            return 0.0
            
        total_waste = 0.0
        metrics = self.raw["term_metrics"]
        
        for target_id in targets_to_exclude:
            if target_id in metrics:
                total_waste += metrics[target_id].get("spend_14d", 0.0)
                
        return total_waste

    def _calculate_efficiency_gain(self) -> Optional[float]:
        """
        Efficiency Gain = (old_acos - new_acos) / old_acos
        Strictly uses 'expected' simulation scenario.
        """
        sim = self.raw.get("simulation")
        if not sim:
            return None
            
        old_acos = sim.get("old_acos", 0.0)
        new_acos = sim.get("new_acos", 0.0)
        
        # Division safety
        if old_acos <= 0:
            return None
            
        # Gain is reduction in ACOS (positive value = good)
        gain = (old_acos - new_acos) / old_acos
        return gain

    def _calculate_bid_stats(self) -> Dict[str, int]:
        """
        Count bid adjustments (increases, decreases, unchanged).
        """
        increases = 0
        decreases = 0
        unchanged = 0
        
        bids_old = self.raw["bids_old"]
        bids_new = self.raw["bids_new"]
        
        # Only count targets present in both (updates)
        # New targets are handled by Harvest logic usually, but if direct bid add, treated as increase
        all_targets = set(bids_old.keys()) | set(bids_new.keys())
        
        for t in all_targets:
            old = bids_old.get(t, 0.0)
            new = bids_new.get(t, 0.0)
            
            # Use epsilon for float comparison
            if abs(new - old) < 0.001:
                unchanged += 1
            elif new > old:
                increases += 1
            else:
                decreases += 1
                
        return {
            "increases": increases,
            "decreases": decreases,
            "unchanged": unchanged,
            "total_actions": increases + decreases
        }

    def _count_harvests(self) -> int:
        return len(self.raw["harvested"])

    def _count_negatives(self) -> int:
        return len(self.raw["negatives"])

    def _get_top_opportunities(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Identify top opportunity targets based on expected incrementality.
        Formula: sales_14d * (new_bid / old_bid - 1)
        Only considers bid INCREASES.
        """
        opportunities = []
        bids_old = self.raw["bids_old"]
        bids_new = self.raw["bids_new"]
        metrics = self.raw["term_metrics"]
        
        for t, new_bid in bids_new.items():
            old_bid = bids_old.get(t, 0.0)
            
            # Eligible: Bid Increased and has historical sales
            if new_bid > old_bid and t in metrics:
                sales = metrics[t].get("sales_14d", 0.0)
                if sales > 0 and old_bid > 0:
                    delta_pct = (new_bid / old_bid) - 1
                    expected_uplift = sales * delta_pct
                    
                    opportunities.append({
                        "target_id": t,
                        "uplift": expected_uplift,
                        "old_bid": old_bid, 
                        "new_bid": new_bid,
                        "sales_14d": sales
                    })
        
        # Sort descending by uplift
        opportunities.sort(key=lambda x: x["uplift"], reverse=True)
        return opportunities[:limit]

    def _build_contribution_chart(self) -> Dict[str, float]:
        """
        Calculate % of total spend affected by each action type.
        Used for the stacked bar chart.
        """
        metrics = self.raw["term_metrics"]
        total_spend = sum(m.get("spend_14d", 0) for m in metrics.values())
        
        if total_spend == 0:
            return {"Bid Up": 0, "Bid Down": 0, "Negatives": 0, "Unchanged": 1.0}
            
        action_spend = {
            "Bid Up": 0.0,
            "Bid Down": 0.0,
            "Negatives": 0.0
            # Harvest doesn't have "spend" in the same way (it's new)
        }
        
        # Categorize targets
        bids_old = self.raw["bids_old"]
        bids_new = self.raw["bids_new"]
        negatives = set(self.raw["negatives"])
        
        processed_targets = set()
        
        # 1. Negatives
        for t in negatives:
            if t in metrics:
                action_spend["Negatives"] += metrics[t].get("spend_14d", 0)
                processed_targets.add(t)
                
        # 2. Bid Changes
        for t in bids_new.keys():
            if t in processed_targets or t not in metrics:
                continue
                
            old = bids_old.get(t, 0.0)
            new = bids_new[t]
            spend = metrics[t].get("spend_14d", 0)
            
            if new > old:
                action_spend["Bid Up"] += spend
            elif new < old:
                action_spend["Bid Down"] += spend
            
            processed_targets.add(t)
            
        # Calculate ratios
        chart_data = {
            k: v / total_spend for k, v in action_spend.items()
        }
        # Implicit "Unchanged" or "Other" is the remainder, but PRD only asks for these segments
        # We can explicitly return them.
        
        return chart_data
