from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any
import re

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


# =============================================================================
# CURRENCY LIMITS
# =============================================================================

CURRENCY_LIMITS = {
    "SP": {
        "USD": {"min_budget": 1, "max_budget": 1_000_000, "min_bid": 0.02, "max_bid": 1000},
        "GBP": {"min_budget": 1, "max_budget": 1_000_000, "min_bid": 0.02, "max_bid": 1000},
        "EUR": {"min_budget": 1, "max_budget": 1_000_000, "min_bid": 0.02, "max_bid": 1000},
        "CAD": {"min_budget": 1, "max_budget": 1_000_000, "min_bid": 0.02, "max_bid": 1000},
        "AUD": {"min_budget": 1.4, "max_budget": 1_500_000, "min_bid": 0.1, "max_bid": 1410},
        "JPY": {"min_budget": 100, "max_budget": 21_000_000, "min_bid": 2, "max_bid": 100_000},
        "INR": {"min_budget": 500, "max_budget": 21_000_000, "min_bid": 1, "max_bid": 5000},
        "AED": {"min_budget": 4, "max_budget": 3_700_000, "min_bid": 0.5, "max_bid": 3670},
        "MXN": {"min_budget": 1, "max_budget": 21_000_000, "min_bid": 0.1, "max_bid": 20_000},
        "CNY": {"min_budget": 1, "max_budget": 21_000_000, "min_bid": 0.1, "max_bid": 1000},
    },
    "SB": {
        "USD": {"min_daily": 1, "max_daily": 1_000_000, "min_lifetime": 100, "max_lifetime": 20_000_000, "min_bid": 0.1, "max_bid": 49},
        "GBP": {"min_daily": 1, "max_daily": 1_000_000, "min_lifetime": 100, "max_lifetime": 20_000_000, "min_bid": 0.1, "max_bid": 31},
        "EUR": {"min_daily": 1, "max_daily": 1_000_000, "min_lifetime": 100, "max_lifetime": 20_000_000, "min_bid": 0.1, "max_bid": 39},
        "CAD": {"min_daily": 1, "max_daily": 1_000_000, "min_lifetime": 100, "max_lifetime": 20_000_000, "min_bid": 0.1, "max_bid": 49},
        "AUD": {"min_daily": 1.4, "max_daily": 1_500_000, "min_lifetime": 141, "max_lifetime": 28_000_000, "min_bid": 0.1, "max_bid": 70},
        "JPY": {"min_daily": 100, "max_daily": 21_000_000, "min_lifetime": 10_000, "max_lifetime": 2_000_000_000, "min_bid": 10, "max_bid": 7760},
        "INR": {"min_daily": 100, "max_daily": 21_000_000, "min_lifetime": 5_000, "max_lifetime": 200_000_000, "min_bid": 2, "max_bid": 500},
        "AED": {"min_daily": 4, "max_daily": 3_700_000, "min_lifetime": 367, "max_lifetime": 74_000_000, "min_bid": 0.5, "max_bid": 184},
        "MXN": {"min_daily": 1, "max_daily": 21_000_000, "min_lifetime": 100, "max_lifetime": 200_000_000, "min_bid": 0.1, "max_bid": 20_000},
        "CNY": {"min_daily": 1, "max_daily": 21_000_000, "min_lifetime": 100, "max_lifetime": 200_000_000, "min_bid": 1, "max_bid": 50},
    },
    "SD": {
        "USD": {"min_budget": 1, "max_budget": 1_000_000, "min_bid": 0.02, "max_bid": 1000},
    }
}


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def validate_campaign_name_chars(name: str) -> bool:
    """Validate campaign name contains only allowed characters"""
    pattern = r'^[a-zA-Z0-9\s\-_\.\,\!\?\'\"\&\(\)]+$'
    return bool(re.match(pattern, name))


def get_currency_limits(ad_type: str, currency: str) -> Optional[Dict]:
    """Get currency-specific limits for an ad type"""
    ad_type_key = {"Sponsored Products": "SP", "Sponsored Brands": "SB", "Sponsored Display": "SD"}.get(ad_type)
    if ad_type_key and ad_type_key in CURRENCY_LIMITS:
        return CURRENCY_LIMITS[ad_type_key].get(currency)
    return None


# =============================================================================
# RECOMMENDATION VALIDATOR
# =============================================================================

class RecommendationValidator:
    """
    Validates optimization recommendations at source (when generated).
    This ensures invalid recommendations never make it to bulk export.
    """

    def __init__(self, currency: str = "USD"):
        self.currency = currency
        self.limits = get_currency_limits("Sponsored Products", currency) or {
            "min_bid": 0.02,
            "max_bid": 1000,
            "min_budget": 1,
            "max_budget": 1_000_000
        }

    def validate(self, rec: "OptimizationRecommendation") -> ValidationResult:
        result = ValidationResult(is_valid=True, can_execute=True)
        if rec.recommendation_type == RecommendationType.NEGATIVE_ISOLATION:
            self._validate_isolation_negative(rec, result)
        elif rec.recommendation_type == RecommendationType.NEGATIVE_BLEEDER:
            self._validate_bleeder_negative(rec, result)
        elif rec.recommendation_type in [RecommendationType.BID_INCREASE, RecommendationType.BID_DECREASE]:
            self._validate_bid_change(rec, result)
        elif rec.recommendation_type == RecommendationType.KEYWORD_HARVEST:
            self._validate_keyword_harvest(rec, result)
        elif rec.recommendation_type in [RecommendationType.PAUSE_TARGET, RecommendationType.ENABLE_TARGET]:
            self._validate_status_change(rec, result)
        elif rec.recommendation_type == RecommendationType.CREATE_CAMPAIGN:
            self._validate_campaign_creation(rec, result)
        self._validate_common(rec, result)
        return result

    def _validate_common(self, rec, result: ValidationResult):
        if not rec.campaign_name or not rec.campaign_name.strip():
            result.add_error("CAM001", "Campaign name is required", "campaign_name")
        if rec.keyword_text and len(rec.keyword_text) > 80:
            result.add_error("KEY002", f"Keyword exceeds 80 characters ({len(rec.keyword_text)} chars)", "keyword_text")
        if rec.keyword_text and not re.match(r'^[a-zA-Z0-9\s\-]+$', rec.keyword_text):
            result.add_error("KEY003", "Keyword contains invalid characters (only alphanumeric, spaces, hyphens allowed)", "keyword_text")

    def _validate_isolation_negative(self, rec, result: ValidationResult):
        if rec.ad_group_name and rec.ad_group_name.strip():
            result.add_error("ISO001", "Ad Group must be BLANK for isolation negatives. This is a campaign-level negative.", "ad_group_name")
        if rec.match_type:
            mt = rec.match_type.lower().strip()
            if mt not in ["campaign negative exact", "campaign negative phrase"]:
                result.add_error("ISO002", f"Isolation negatives must use 'campaign negative exact' or 'campaign negative phrase'. Got: '{rec.match_type}'", "match_type")

    def _validate_bleeder_negative(self, rec, result: ValidationResult):
        if not rec.ad_group_name or not rec.ad_group_name.strip():
            result.add_error("BLD001", "Ad Group is REQUIRED for bleeder negatives. Specify which ad group to block the term in.", "ad_group_name")
        if rec.match_type:
            mt = rec.match_type.lower().strip()
            if mt not in ["negative exact", "negative phrase"]:
                result.add_error("BLD002", f"Bleeder negatives must use 'negative exact' or 'negative phrase'. Got: '{rec.match_type}'", "match_type")

    def _validate_bid_change(self, rec, result: ValidationResult):
        if rec.new_bid is None:
            result.add_error("BID_UPD002", "New bid value is required", "new_bid")
            return
        if rec.new_bid < self.limits["min_bid"]:
            result.add_error("MAX002", f"Bid {rec.new_bid} is below minimum ({self.limits['min_bid']}) for {self.currency}", "new_bid")
        if rec.new_bid > self.limits["max_bid"]:
            result.add_error("MAX003", f"Bid {rec.new_bid} exceeds maximum ({self.limits['max_bid']}) for {self.currency}", "new_bid")
        if rec.current_bid and rec.current_bid > 0:
            change_pct = abs((rec.new_bid - rec.current_bid) / rec.current_bid) * 100
            if change_pct > 300:
                result.add_warning("BID_UPD003", f"Bid change of {change_pct:.0f}% exceeds 300%. Current: {rec.current_bid}, New: {rec.new_bid}", "new_bid")
        if not rec.ad_group_name or not rec.ad_group_name.strip():
            result.add_error("ADG004", "Ad Group is required for keyword bid changes", "ad_group_name")
        is_keyword = rec.match_type and rec.match_type.lower() in ["exact", "broad", "phrase"]
        if is_keyword and rec.product_targeting_expression and rec.product_targeting_expression.strip():
            result.add_error("TAR003", f"Product Targeting Expression ('{rec.product_targeting_expression}') must be blank for keyword Match Type '{rec.match_type}'.", "product_targeting_expression")

    def _validate_keyword_harvest(self, rec, result: ValidationResult):
        if not rec.keyword_text or not rec.keyword_text.strip():
            result.add_error("KEY001", "Keyword text is required for harvest", "keyword_text")
        if not rec.match_type:
            result.add_error("KEY007", "Match type is required for harvested keyword", "match_type")
        elif rec.match_type.lower() not in ["broad", "phrase", "exact"]:
            result.add_error("KEY008", f"Invalid match type for harvest: '{rec.match_type}'", "match_type")
        if rec.campaign_targeting_type and rec.campaign_targeting_type.lower() == "auto":
            result.add_error("AUTO001", f"Cannot add positive keywords to Auto-targeting campaign '{rec.campaign_name}'", "campaign_targeting_type")

    def _validate_status_change(self, rec, result: ValidationResult):
        if not rec.keyword_text and not rec.ad_group_name:
            result.add_error("HIE001", "Must specify keyword or ad group to change status", "keyword_text")

    def _validate_campaign_creation(self, rec, result: ValidationResult):
        if rec.campaign_name and len(rec.campaign_name) > 128:
            result.add_error("CAM002", f"Campaign name exceeds 128 characters ({len(rec.campaign_name)} chars)", "campaign_name")
        if rec.campaign_name and not validate_campaign_name_chars(rec.campaign_name):
            result.add_error("CAM003", "Campaign name contains invalid characters", "campaign_name")


def validate_recommendation(
    rec: "OptimizationRecommendation",
    currency: str = None
) -> ValidationResult:
    """Convenience function to validate a single recommendation."""
    validator = RecommendationValidator(currency=currency or rec.currency)
    return validator.validate(rec)


def validate_recommendations_batch(
    recommendations: List["OptimizationRecommendation"],
    currency: str = "USD"
) -> Dict[str, Any]:
    """Validate a batch of recommendations. Returns summary statistics."""
    validator = RecommendationValidator(currency=currency)
    total = len(recommendations)
    valid_count = 0
    warning_count = 0
    error_count = 0
    for rec in recommendations:
        rec.validation_result = validator.validate(rec)
        if rec.is_valid:
            if rec.validation_result.has_warnings:
                warning_count += 1
            else:
                valid_count += 1
        else:
            error_count += 1
    return {
        "total": total,
        "valid": valid_count,
        "warnings": warning_count,
        "errors": error_count,
        "can_execute": valid_count + warning_count,
        "blocked": error_count,
        "pass_rate": (valid_count + warning_count) / total * 100 if total > 0 else 0
    }
