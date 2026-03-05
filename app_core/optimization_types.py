from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any

# =============================================================================
# OPTIMIZATION TYPES & VALIDATION STRUCTURES
# =============================================================================

class RecommendationType(Enum):
    """Types of optimization recommendations"""
    
    # Negative keywords
    NEGATIVE_ISOLATION = "negative_isolation"      # Harvest → campaign negative
    NEGATIVE_BLEEDER = "negative_bleeder"          # Block bad performer in ad group
    
    # Bid adjustments
    BID_INCREASE = "bid_increase"
    BID_DECREASE = "bid_decrease"
    VISIBILITY_BOOST = "visibility_boost"          # Low visibility boost (+30%)
    
    # Keyword promotion
    KEYWORD_HARVEST = "keyword_harvest"            # Promote to own campaign
    
    # Status changes
    PAUSE_TARGET = "pause_target"
    ENABLE_TARGET = "enable_target"
    
    # Campaign creation
    CREATE_CAMPAIGN = "create_campaign"
    
    # Product targeting
    ADD_PRODUCT_TARGET = "add_product_target"
    REMOVE_PRODUCT_TARGET = "remove_product_target"


@dataclass
class ValidationResult:
    """Result of validating a recommendation or bulk row"""
    is_valid: bool
    can_execute: bool  # False if blocking errors exist
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0
    
    def add_error(self, code: str, message: str, field: str = None):
        self.errors.append({
            "code": code,
            "message": message,
            "field": field,
            "severity": "error"
        })
        self.is_valid = False
        self.can_execute = False
    
    def add_warning(self, code: str, message: str, field: str = None):
        self.warnings.append({
            "code": code,
            "message": message,
            "field": field,
            "severity": "warning"
        })


@dataclass
class OptimizationRecommendation:
    """
    A single optimization recommendation from the optimizer.
    Validation happens at creation time, not at export.
    """
    
    # Core recommendation data
    recommendation_id: str
    recommendation_type: RecommendationType
    
    # Target details
    campaign_name: str
    campaign_id: Optional[str] = None
    campaign_targeting_type: str = "Manual"  # "Auto" or "Manual"
    ad_group_name: Optional[str] = None
    ad_group_id: Optional[str] = None
    keyword_id: Optional[str] = None
    product_targeting_id: Optional[str] = None
    
    # Keyword/target details
    keyword_text: Optional[str] = None
    match_type: Optional[str] = None
    current_bid: Optional[float] = None
    new_bid: Optional[float] = None
    
    # ASIN for product targeting
    asin: Optional[str] = None
    product_targeting_expression: Optional[str] = None
    
    # Currency for validation
    currency: str = "USD"
    
    # Validation state (populated at creation)
    validation_result: ValidationResult = field(default_factory=lambda: ValidationResult(True, True))
    
    # Execution state
    is_selected: bool = True  # User can deselect
    
    @property
    def is_valid(self) -> bool:
        return self.validation_result.is_valid
    
    @property
    def can_execute(self) -> bool:
        return self.validation_result.can_execute and self.is_selected
    
    @property
    def errors(self) -> List[Dict]:
        return self.validation_result.errors
    
    @property
    def warnings(self) -> List[Dict]:
        return self.validation_result.warnings
    
    def get_status_icon(self) -> str:
        """Return UI status icon"""
        if not self.is_valid:
            return "❌"
        elif self.validation_result.has_warnings:
            return "⚠️"
        else:
            return "✅"
    
    def get_status_color(self) -> str:
        """Return UI status color"""
        if not self.is_valid:
            return "red"
        elif self.validation_result.has_warnings:
            return "yellow"
        else:
            return "green"
