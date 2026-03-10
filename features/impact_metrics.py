"""
Impact Metrics - Single Source of Truth
Created: 2026-01-12
Purpose: Centralize all impact metric calculations to eliminate discrepancies

This module provides the canonical calculation for all impact-related metrics.
All dashboard components should receive an ImpactMetrics instance rather than
calculating metrics independently.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import pandas as pd
from datetime import datetime


@dataclass(frozen=True)
class ImpactMetrics:
    """
    Immutable container for all impact dashboard metrics.
    
    This is the SINGLE SOURCE OF TRUTH for impact calculations.
    All values are computed once at instantiation and cannot be modified.
    
    Usage:
        metrics = ImpactMetrics.from_dataframe(df, filters)
        # Then pass `metrics` to all render functions
    """
    
    # === Core Impact Values ===
    attributed_impact: float          # The main "Value Created" number
    decision_impact: float            # Impact excluding Market Drag rows
    decision_impact_raw: float        # Impact including all rows (preserved for debugging)
    decision_impact_roas: float       # Impact / Spend ratio
    
    # === Breakdown by Type ===
    offensive_value: float            # Offensive wins
    defensive_value: float            # Defensive wins  
    gap_value: float                  # Decision gaps
    
    # === Spend Metrics ===
    total_spend: float                # Total ad spend in period
    spend_avoided: float              # Spend saved from defensive actions
    spend_filtered_impact: float      # Impact for actions that affected ROAS (non-drag, attributed_impact col)
    
    # === Action Counts ===
    total_actions: int                # All actions in dataset
    mature_actions: int               # Actions past maturity window
    offensive_actions: int
    defensive_actions: int
    gap_actions: int
    drag_actions: int                 # Market Drag (excluded from attribution)
    
    # === Quality Metrics ===
    win_rate: float                   # Positive impact actions / total
    
    # === Metadata ===
    calculation_timestamp: str        # When metrics were computed
    filters_applied: Dict[str, Any]   # What filters were active
    horizon_days: int                 # Measurement window used
    
    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        filters: Optional[Dict[str, Any]] = None,
        horizon_days: int = 14
    ) -> 'ImpactMetrics':
        """
        Factory method - THE ONLY PLACE metrics are calculated.
        
        Args:
            df: Impact DataFrame with columns: decision_impact, market_tag, 
                final_decision_impact, is_mature, observed_after_spend
            filters: Dict with optional keys:
                - validated_only: bool
                - mature_only: bool (default True)
            horizon_days: Measurement window (14, 30, or 60)
        
        Returns:
            Frozen ImpactMetrics instance
        """
        filters = filters or {}
        
        # === Handle empty dataset ===
        if df.empty:
            return cls._empty_metrics(filters, horizon_days)
        
        # === Step 1: Apply maturity filter (default: mature only) ===
        mature_only = filters.get('mature_only', True)
        if mature_only and 'is_mature' in df.columns:
            working_df = df[df['is_mature'] == True].copy()
        else:
            working_df = df.copy()
            
        # === Step 1.5: Apply validation filter ===
        if filters.get('validated_only'):
            if 'validated' in working_df.columns:
                working_df = working_df[working_df['validated'] == True]
            elif 'validation_status' in working_df.columns:
                # Use standard regex for validation (matches Dashboard logic)
                mask = working_df['validation_status'].str.contains('✓|CPC Validated|CPC Match|Directional|Confirmed|Normalized|Volume|Strict', na=False, regex=True)
                working_df = working_df[mask]
        
        if working_df.empty:
            return cls._empty_metrics(filters, horizon_days)
        
        # === Step 2: Determine impact column ===
        # CRITICAL: Check for v3.3 columns FIRST, then fall back to v3.2
        # This ensures we use the latest model when available
        if 'final_impact_v33' in working_df.columns:
            impact_col = 'final_impact_v33'  # v3.3 weighted impact (PREFERRED)
            model_version = 'v3.3'
        elif 'final_decision_impact' in working_df.columns:
            impact_col = 'final_decision_impact'  # v3.2 weighted impact (fallback)
            model_version = 'v3.2'
        else:
            impact_col = 'decision_impact'  # Raw unweighted impact (last resort)
            model_version = 'unknown'

        # DEBUG: Trace column selection
        print(f"[ImpactMetrics] Columns available: {list(working_df.columns)}")
        print(f"[ImpactMetrics] Selected Impact Col: {impact_col}")
        print(f"[ImpactMetrics] Model Version: {model_version}")
        
        # === Step 3: Calculate breakdown by market_tag ===
        # Market tags: 'Offensive Win', 'Defensive Win', 'Gap', 'Market Drag'
        offensive_mask = working_df['market_tag'] == 'Offensive Win'
        defensive_mask = working_df['market_tag'] == 'Defensive Win'
        gap_mask = working_df['market_tag'] == 'Gap'
        drag_mask = working_df['market_tag'] == 'Market Drag'
        
        offensive_val = working_df.loc[offensive_mask, impact_col].sum() if offensive_mask.any() else 0.0
        defensive_val = working_df.loc[defensive_mask, impact_col].sum() if defensive_mask.any() else 0.0
        gap_val = working_df.loc[gap_mask, impact_col].sum() if gap_mask.any() else 0.0
        
        # === Step 4: Attributed impact EXCLUDES Market Drag ===
        attributed = offensive_val + defensive_val + gap_val
        
        # === Step 5: Total spend from observed_after_spend ===
        spend_col = 'observed_after_spend' if 'observed_after_spend' in working_df.columns else 'after_spend'
        non_drag_mask = working_df['market_tag'] != 'Market Drag'
        total_spend = working_df.loc[non_drag_mask, spend_col].sum() if spend_col in working_df.columns else 0.0
        
        # === Step 6: Decision impact (excludes Market Drag rows) ===
        decision_impact_df = working_df[working_df['market_tag'] != 'Market Drag'] if 'market_tag' in working_df.columns else working_df
        decision_impact = decision_impact_df[impact_col].sum()
        decision_impact_raw = working_df[impact_col].sum()  # All rows including drag (preserved for debugging)

        # === Step 6b: Spend-filtered impact (non-drag rows only, same as decision_impact) ===
        spend_filtered_impact = float(decision_impact)
        
        # === Step 7: Spend avoided (from spend_avoided column if exists) ===
        spend_avoided = working_df['spend_avoided'].sum() if 'spend_avoided' in working_df.columns else 0.0
        
        # === Step 8: Action counts ===
        total_actions = len(working_df)
        mature_count = len(working_df[working_df['is_mature'] == True]) if 'is_mature' in working_df.columns else total_actions
        
        # === Step 9: Quality metrics ===
        positive_impact_actions = len(working_df[working_df[impact_col] > 0])
        win_rate = positive_impact_actions / total_actions if total_actions > 0 else 0.0
        
        # === Step 10: Build immutable instance ===
        return cls(
            # Core values
            attributed_impact=float(attributed),
            decision_impact=float(decision_impact),
            decision_impact_raw=float(decision_impact_raw),
            decision_impact_roas=float(attributed / total_spend) if total_spend > 0 else 0.0,

            # Breakdown
            offensive_value=float(offensive_val),
            defensive_value=float(defensive_val),
            gap_value=float(gap_val),

            # Spend
            total_spend=float(total_spend),
            spend_avoided=float(spend_avoided),
            spend_filtered_impact=spend_filtered_impact,
            
            # Counts
            total_actions=int(total_actions),
            mature_actions=int(mature_count),
            offensive_actions=int(offensive_mask.sum()),
            defensive_actions=int(defensive_mask.sum()),
            gap_actions=int(gap_mask.sum()),
            drag_actions=int(drag_mask.sum()),
            
            # Quality
            win_rate=float(win_rate),
            
            # Metadata
            calculation_timestamp=datetime.now().isoformat(),
            filters_applied=filters,
            horizon_days=horizon_days
        )
    
    @classmethod
    def _empty_metrics(cls, filters: Dict[str, Any], horizon_days: int) -> 'ImpactMetrics':
        """Return zeroed metrics for empty datasets."""
        return cls(
            attributed_impact=0.0,
            decision_impact=0.0,
            decision_impact_raw=0.0,
            decision_impact_roas=0.0,
            offensive_value=0.0,
            defensive_value=0.0,
            gap_value=0.0,
            total_spend=0.0,
            spend_avoided=0.0,
            spend_filtered_impact=0.0,
            total_actions=0,
            mature_actions=0,
            offensive_actions=0,
            defensive_actions=0,
            gap_actions=0,
            drag_actions=0,
            win_rate=0.0,
            calculation_timestamp=datetime.now().isoformat(),
            filters_applied=filters,
            horizon_days=horizon_days
        )
    
    # === Convenience Properties ===
    
    @property
    def has_data(self) -> bool:
        """Check if metrics contain any data."""
        return self.total_actions > 0
    
    @property
    def impact_per_action(self) -> float:
        """Average impact per action taken."""
        return self.attributed_impact / self.total_actions if self.total_actions > 0 else 0
    
    @property
    def wins_count(self) -> int:
        """Total number of winning actions (offensive + defensive)."""
        return self.offensive_actions + self.defensive_actions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization or session state."""
        return {
            'attributed_impact': self.attributed_impact,
            'decision_impact': self.decision_impact,
            'decision_impact_raw': self.decision_impact_raw,
            'decision_impact_roas': self.decision_impact_roas,
            'spend_filtered_impact': self.spend_filtered_impact,
            'offensive_value': self.offensive_value,
            'defensive_value': self.defensive_value,
            'gap_value': self.gap_value,
            'total_spend': self.total_spend,
            'spend_avoided': self.spend_avoided,
            'total_actions': self.total_actions,
            'mature_actions': self.mature_actions,
            'offensive_actions': self.offensive_actions,
            'defensive_actions': self.defensive_actions,
            'gap_actions': self.gap_actions,
            'drag_actions': self.drag_actions,
            'win_rate': self.win_rate,
            'calculation_timestamp': self.calculation_timestamp,
            'horizon_days': self.horizon_days
        }
    
    def __repr__(self) -> str:
        return (
            f"ImpactMetrics("
            f"attributed=${self.attributed_impact:,.0f}, "
            f"roas={self.decision_impact_roas:.2f}x, "
            f"actions={self.total_actions})"
        )


# === Test Function ===

def test_impact_metrics():
    """
    Unit test for ImpactMetrics class.
    Run this after creating the file to verify calculations.
    """
    # Create test data matching actual dashboard column names
    test_data = pd.DataFrame({
        'decision_impact': [100, 200, -50, 150, 75],
        'final_decision_impact': [100, 200, -50, 150, 75],
        'market_tag': ['Offensive Win', 'Offensive Win', 'Defensive Win', 'Gap', 'Offensive Win'],
        'observed_after_spend': [1000, 1500, 500, 800, 600],
        'is_mature': [True, True, True, True, True],
    })
    
    # Test 1: Basic calculation
    metrics = ImpactMetrics.from_dataframe(test_data)
    
    assert metrics.offensive_value == 375, f"Expected 375, got {metrics.offensive_value}"
    assert metrics.defensive_value == -50, f"Expected -50, got {metrics.defensive_value}"
    assert metrics.gap_value == 150, f"Expected 150, got {metrics.gap_value}"
    assert metrics.attributed_impact == 475, f"Expected 475, got {metrics.attributed_impact}"
    assert metrics.total_actions == 5
    
    print("✅ Test 1 passed: Basic calculation")
    
    # Test 2: Market Drag exclusion
    test_with_drag = pd.DataFrame({
        'decision_impact': [100, -200, 50],
        'final_decision_impact': [100, -200, 50],
        'market_tag': ['Offensive Win', 'Market Drag', 'Defensive Win'],
        'observed_after_spend': [1000, 500, 800],
        'is_mature': [True, True, True],
    })
    
    metrics_drag = ImpactMetrics.from_dataframe(test_with_drag)
    
    assert metrics_drag.attributed_impact == 150, f"Expected 150 (excluding drag), got {metrics_drag.attributed_impact}"
    assert metrics_drag.drag_actions == 1
    
    print("✅ Test 2 passed: Market Drag exclusion")
    
    # Test 3: Empty dataset
    empty_df = pd.DataFrame(columns=['decision_impact', 'market_tag', 'observed_after_spend'])
    metrics_empty = ImpactMetrics.from_dataframe(empty_df)
    
    assert metrics_empty.attributed_impact == 0
    assert metrics_empty.has_data == False
    
    print("✅ Test 3 passed: Empty dataset handling")
    
    # Test 4: Immutability
    try:
        metrics.attributed_impact = 999
        print("❌ Test 4 FAILED: Should not allow mutation")
        return False
    except Exception:
        print("✅ Test 4 passed: Immutability enforced")
    
    # Test 5: ROAS calculation
    expected_roas = 475 / 4400  # attributed / total_spend
    assert abs(metrics.decision_impact_roas - expected_roas) < 0.001
    
    print("✅ Test 5 passed: ROAS calculation")
    
    print("\n✅ ALL TESTS PASSED")
    return True


if __name__ == "__main__":
    test_impact_metrics()
