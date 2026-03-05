# EXECUTIVE DASHBOARD BUILD - COMPLETE SPECIFICATION

## CRITICAL CONSTRAINTS (READ FIRST)

⚠️ **NON-NEGOTIABLE RULES**:
1. **DO NOT modify any existing optimizer logic** (Phases 1, 1.5, 2, 5)
2. **DO NOT add new Amazon Ads API calls** (use existing cached data only)
3. **DO NOT change existing dashboard routes** (/actions-review, /what-if, /impact-results)
4. **DO NOT refactor shared utilities** used by other modules
5. **ALL new code must be in isolated paths** (see structure below)

✅ **ALLOWED**:
- New API endpoint: `/api/executive/overview` (read-only)
- New frontend route: `/dashboard/executive`
- New derived logic (transformations of existing metrics)
- New UI components (scoped to executive dashboard only)

---

## FILE STRUCTURE (STRICT ISOLATION)
```
backend/
├── api/routes/
│   └── executive_overview.py          # ✅ NEW - create this
├── models/
│   └── executive_schemas.py           # ✅ NEW - create this
├── services/
│   └── executive_metrics.py           # ✅ NEW - create this
└── tests/
    └── test_executive_api.py          # ✅ NEW - create this

frontend/
├── app/dashboard/executive/
│   ├── page.tsx                       # ✅ NEW - create this
│   ├── layout.tsx                     # ✅ NEW - create this (if needed)
│   └── components/
│       ├── KPICards.tsx               # ✅ NEW - create this
│       ├── KPICard.tsx                # ✅ NEW - create this
│       ├── MomentumChart.tsx          # ✅ NEW - create this
│       ├── DecisionImpact.tsx         # ✅ NEW - create this
│       ├── PerformanceOverview.tsx    # ✅ NEW - create this
│       └── QuadrantScatter.tsx        # ✅ NEW - create this
└── types/
    └── executive.ts                   # ✅ NEW - create this

tests/
└── e2e/
    └── executive_dashboard.spec.ts    # ✅ NEW - create this
```

❌ **DO NOT TOUCH**:
- `backend/optimizer/` - any files here
- `backend/api/routes/optimizer.py`
- `frontend/app/dashboard/actions-review/`
- `frontend/app/dashboard/what-if/`
- `frontend/app/dashboard/impact-results/`
- Any shared utility files used by existing dashboards

---

## PHASE 1: BACKEND FOUNDATION

### Step 1.1: Create Pydantic Schemas

**File**: `backend/models/executive_schemas.py`
```python
"""
Executive Dashboard Data Schemas
PURE DATA CONTRACTS - No business logic here
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Literal, Optional
from datetime import datetime

class KPIMetric(BaseModel):
    """Single KPI with trend data"""
    value: float
    delta_pct: float  # vs previous period
    delta_abs: float
    trend: Literal["up", "down", "stable"]
    sparkline: List[float] = Field(default_factory=list)

class KPIs(BaseModel):
    """Top-level KPI metrics"""
    revenue: KPIMetric
    net_contribution: KPIMetric
    efficiency_score: KPIMetric  # 0-100 composite
    risk_index: KPIMetric  # 0-1 (display as %)
    scale_headroom: KPIMetric  # 0-1 (display as %)

class MomentumDataPoint(BaseModel):
    """Single time period in momentum chart"""
    date: str  # ISO format
    revenue: float
    spend_allocation: Dict[str, float]  # {classification: spend_amount}
    efficiency_line: float  # % vs baseline

class DecisionCategory(BaseModel):
    """Impact from one decision type"""
    count: int
    impact: float  # revenue impact (positive or negative)
    type: Literal["promote", "prevent", "protect"]
    detail: str

class DecisionImpact(BaseModel):
    """Overall decision impact summary"""
    period: str
    net_impact: float
    net_impact_pct: float
    bid_ups: DecisionCategory
    bid_downs: DecisionCategory
    pauses: DecisionCategory
    negatives: DecisionCategory

class QuadrantPoint(BaseModel):
    """Single point in performance scatter plot"""
    x: float  # CVR
    y: float  # ROAS
    size: float  # orders or spend
    label: str
    zone: Literal["scale", "optimize", "watch", "kill"]

class PerformanceBreakdown(BaseModel):
    """Performance analysis data"""
    quadrant_data: List[QuadrantPoint]
    revenue_by_match_type: Dict[str, float]
    spend_distribution: Dict[str, float]
    cost_efficiency_scatter: List[Dict]

class ExecutiveDashboard(BaseModel):
    """Complete executive dashboard payload"""
    kpis: KPIs
    momentum: List[MomentumDataPoint]
    decision_impact: DecisionImpact
    performance: PerformanceBreakdown
    metadata: Dict

    class Config:
        json_schema_extra = {
            "example": {
                "kpis": {
                    "revenue": {
                        "value": 224550,
                        "delta_pct": -45.8,
                        "delta_abs": -190000,
                        "trend": "down",
                        "sparkline": [200000, 210000, 215000, 224550]
                    },
                    # ... other KPIs
                },
                # ... rest of structure
            }
        }
```

**Tests for Step 1.1** (create `backend/tests/test_schemas.py`):
```python
import pytest
from pydantic import ValidationError
from backend.models.executive_schemas import ExecutiveDashboard, KPIMetric

def test_kpi_metric_valid():
    """Valid KPI metric passes validation"""
    kpi = KPIMetric(
        value=100,
        delta_pct=5.0,
        delta_abs=5.0,
        trend="up"
    )
    assert kpi.value == 100
    assert kpi.trend == "up"

def test_kpi_metric_invalid_trend():
    """Invalid trend value raises error"""
    with pytest.raises(ValidationError):
        KPIMetric(
            value=100,
            delta_pct=5.0,
            delta_abs=5.0,
            trend="invalid"  # Should be "up", "down", or "stable"
        )

def test_dashboard_structure():
    """Full dashboard validates correctly"""
    data = {
        "kpis": {
            "revenue": {"value": 100, "delta_pct": 5.0, "delta_abs": 5.0, "trend": "up"},
            "net_contribution": {"value": 50, "delta_pct": 3.0, "delta_abs": 1.5, "trend": "up"},
            "efficiency_score": {"value": 82, "delta_pct": 2.0, "delta_abs": 1.6, "trend": "up"},
            "risk_index": {"value": 0.18, "delta_pct": -10.0, "delta_abs": -0.02, "trend": "down"},
            "scale_headroom": {"value": 0.42, "delta_pct": 5.0, "delta_abs": 0.02, "trend": "up"}
        },
        "momentum": [],
        "decision_impact": {
            "period": "Last 14 Days",
            "net_impact": 10000,
            "net_impact_pct": 5.0,
            "bid_ups": {"count": 10, "impact": 5000, "type": "promote", "detail": "test"},
            "bid_downs": {"count": 5, "impact": -2000, "type": "prevent", "detail": "test"},
            "pauses": {"count": 3, "impact": -1000, "type": "prevent", "detail": "test"},
            "negatives": {"count": 8, "impact": 8000, "type": "prevent", "detail": "test"}
        },
        "performance": {
            "quadrant_data": [],
            "revenue_by_match_type": {},
            "spend_distribution": {},
            "cost_efficiency_scatter": []
        },
        "metadata": {}
    }
    
    dashboard = ExecutiveDashboard(**data)
    assert dashboard.kpis.revenue.value == 100
```

**Run Tests**:
```bash
cd backend
pytest tests/test_schemas.py -v
```

✅ **Checkpoint**: All schema tests must pass before continuing

---

### Step 1.2: Create Metrics Engine

**File**: `backend/services/executive_metrics.py`
```python
"""
Executive Metrics Service
PURE TRANSFORMATION LOGIC - No database calls, no API calls
Input: Existing cached data (dict)
Output: Derived metrics (dict)
"""

import numpy as np
from typing import Dict, List, Any
from datetime import datetime, timedelta

class ExecutiveMetricsService:
    """
    Transforms existing metrics into executive-level insights.
    ALL methods are pure functions (no side effects).
    """
    
    def compute_kpis(self, data: Dict[str, Any]) -> Dict:
        """
        Compute top-line KPIs from existing metrics.
        
        Args:
            data: {
                'current_period': {'sales': float, 'spend': float, 'roas': float, ...},
                'previous_period': {...},
                'medians': {'roas': float, 'cvr': float}
            }
        
        Returns:
            Dict matching KPIs schema
        """
        current = data['current_period']
        previous = data['previous_period']
        
        # Revenue
        revenue = self._compute_metric(
            current['sales'], 
            previous['sales']
        )
        
        # Net Contribution = Revenue - Spend
        net_contribution = self._compute_metric(
            current['sales'] - current['spend'],
            previous['sales'] - previous['spend']
        )
        
        # Efficiency Score (composite: 50% ROAS + 30% CVR + 20% CPC trend)
        efficiency_score = self._compute_efficiency_score(
            current, 
            previous, 
            data['medians']
        )
        
        # Risk Index (% spend in low-performance zone)
        risk_index = self._compute_risk_index(
            data.get('campaign_performance', [])
        )
        
        # Scale Headroom (% spend in high-performance zone)
        scale_headroom = self._compute_scale_headroom(
            data.get('campaign_performance', [])
        )
        
        return {
            "revenue": revenue,
            "net_contribution": net_contribution,
            "efficiency_score": efficiency_score,
            "risk_index": risk_index,
            "scale_headroom": scale_headroom
        }
    
    def _compute_metric(self, current_value: float, previous_value: float) -> Dict:
        """Helper: compute metric with delta and trend"""
        delta_abs = current_value - previous_value
        delta_pct = (delta_abs / previous_value * 100) if previous_value != 0 else 0
        
        # Trend classification
        if delta_pct > 2:
            trend = "up"
        elif delta_pct < -2:
            trend = "down"
        else:
            trend = "stable"
        
        return {
            "value": current_value,
            "delta_abs": delta_abs,
            "delta_pct": delta_pct,
            "trend": trend,
            "sparkline": []  # Populated separately if needed
        }
    
    def _compute_efficiency_score(
        self, 
        current: Dict, 
        previous: Dict, 
        medians: Dict
    ) -> Dict:
        """
        Composite efficiency score (0-100):
        - 50% weight: ROAS vs median
        - 30% weight: CVR vs median
        - 20% weight: CPC trend (lower is better)
        """
        median_roas = medians.get('roas', 2.5)
        median_cvr = medians.get('cvr', 0.10)
        
        # ROAS component (0-50 points)
        roas_ratio = current['roas'] / median_roas
        roas_score = min(50, roas_ratio * 50)
        
        # CVR component (0-30 points)
        cvr_ratio = current['cvr'] / median_cvr
        cvr_score = min(30, cvr_ratio * 30)
        
        # CPC component (0-20 points)
        # Award 20 points if CPC decreased, 10 if stable
        cpc_delta = (current['cpc'] - previous['cpc']) / previous['cpc'] if previous.get('cpc', 0) != 0 else 0
        if cpc_delta <= -0.05:  # 5%+ decrease
            cpc_score = 20
        elif cpc_delta <= 0.05:  # Stable
            cpc_score = 15
        else:  # Increased
            cpc_score = 10
        
        total = roas_score + cvr_score + cpc_score
        
        # Compare to previous efficiency score (if exists)
        previous_efficiency = previous.get('efficiency_score', total)
        
        return self._compute_metric(total, previous_efficiency)
    
    def _compute_risk_index(self, campaigns: List[Dict]) -> Dict:
        """
        Risk Index = % of spend in low-performance quadrant
        Low performance = ROAS < median AND CVR < median
        """
        if not campaigns:
            return self._compute_metric(0, 0)
        
        total_spend = sum(c.get('spend', 0) for c in campaigns)
        if total_spend == 0:
            return self._compute_metric(0, 0)
        
        # Calculate medians
        median_roas = np.median([c.get('roas', 0) for c in campaigns])
        median_cvr = np.median([c.get('cvr', 0) for c in campaigns])
        
        # Sum spend in risky zone
        risky_spend = sum(
            c.get('spend', 0) for c in campaigns
            if c.get('roas', 0) < median_roas and c.get('cvr', 0) < median_cvr
        )
        
        risk_pct = risky_spend / total_spend
        
        # For trend, we'd need previous period data (not shown here)
        return self._compute_metric(risk_pct, risk_pct)  # Simplified
    
    def _compute_scale_headroom(self, campaigns: List[Dict]) -> Dict:
        """
        Scale Headroom = % of spend in high-performance quadrant
        High performance = ROAS > median AND CVR > median
        """
        if not campaigns:
            return self._compute_metric(0, 0)
        
        total_spend = sum(c.get('spend', 0) for c in campaigns)
        if total_spend == 0:
            return self._compute_metric(0, 0)
        
        median_roas = np.median([c.get('roas', 0) for c in campaigns])
        median_cvr = np.median([c.get('cvr', 0) for c in campaigns])
        
        scale_spend = sum(
            c.get('spend', 0) for c in campaigns
            if c.get('roas', 0) > median_roas and c.get('cvr', 0) > median_cvr
        )
        
        scale_pct = scale_spend / total_spend
        
        return self._compute_metric(scale_pct, scale_pct)
    
    def compute_momentum(
        self, 
        data: Dict, 
        granularity: str = "weekly"
    ) -> List[Dict]:
        """
        Classify momentum for each time period.
        
        CORRECTED MOMENTUM LOGIC:
        - Revenue ↑ AND Efficiency >= Median AND ΔEfficiency ↓ → "scale_push"
        - Revenue ↓ AND Efficiency >= Median AND ΔEfficiency ↑ → "efficiency_correction"
        - Revenue ↓ AND Efficiency < Median → "risk_zone"
        - Revenue ↑ AND Efficiency > Median → "healthy_scale"
        - Else → "stable"
        """
        periods = data.get('time_series', {}).get(granularity, [])
        medians = data.get('medians', {})
        
        results = []
        
        for i, period in enumerate(periods):
            if i == 0:
                # First period has no comparison
                classification = "stable"
                spend_allocation = {classification: period.get('spend', 0)}
            else:
                prev = periods[i-1]
                classification = self._classify_momentum(period, prev, medians)
                spend_allocation = {classification: period.get('spend', 0)}
            
            results.append({
                "date": period['date'],
                "revenue": period.get('sales', 0),
                "spend_allocation": spend_allocation,
                "efficiency_line": (period.get('roas', 0) / medians.get('roas', 1)) * 100
            })
        
        return results
    
    def _classify_momentum(
        self, 
        current: Dict, 
        previous: Dict, 
        medians: Dict
    ) -> str:
        """
        Apply EXACT momentum classification logic from spec.
        """
        # Calculate deltas
        delta_revenue = (
            (current['sales'] - previous['sales']) / previous['sales']
            if previous.get('sales', 0) != 0 else 0
        )
        delta_efficiency = (
            (current['roas'] - previous['roas']) / previous['roas']
            if previous.get('roas', 0) != 0 else 0
        )
        
        # Efficiency vs median
        efficiency_vs_median = current.get('roas', 0) / medians.get('roas', 1)
        
        # Apply classification rules
        if delta_revenue > 0 and efficiency_vs_median >= 1.0 and delta_efficiency < 0:
            return "scale_push"
        elif delta_revenue < 0 and efficiency_vs_median >= 1.0 and delta_efficiency > 0:
            return "efficiency_correction"
        elif delta_revenue < 0 and efficiency_vs_median < 1.0:
            return "risk_zone"
        elif delta_revenue > 0 and efficiency_vs_median > 1.0:
            return "healthy_scale"
        else:
            return "stable"
    
    def compute_decision_impact(self, data: Dict) -> Dict:
        """
        Aggregate impact of decisions from existing decision history.
        This is POST-HOC analysis only (read-only).
        """
        decisions = data.get('decision_history', [])
        
        bid_ups = self._aggregate_decisions(decisions, 'bid_increase')
        bid_downs = self._aggregate_decisions(decisions, 'bid_decrease')
        pauses = self._aggregate_decisions(decisions, 'pause')
        negatives = self._aggregate_decisions(decisions, 'negative')
        
        net_impact = sum([
            bid_ups['impact'],
            bid_downs['impact'],
            pauses['impact'],
            negatives['impact']
        ])
        
        total_revenue = data.get('current_period', {}).get('sales', 1)
        net_impact_pct = (net_impact / total_revenue * 100) if total_revenue != 0 else 0
        
        return {
            "period": "Last 14 Days",
            "net_impact": net_impact,
            "net_impact_pct": net_impact_pct,
            "bid_ups": bid_ups,
            "bid_downs": bid_downs,
            "pauses": pauses,
            "negatives": negatives
        }
    
    def _aggregate_decisions(
        self, 
        decisions: List[Dict], 
        decision_type: str
    ) -> Dict:
        """Sum impact of all decisions of a given type"""
        filtered = [d for d in decisions if d.get('type') == decision_type]
        
        total_impact = sum(d.get('measured_impact', 0) for d in filtered)
        
        # Categorize decision type
        if decision_type == 'bid_increase':
            category_type = "promote"
            detail = "Positions - Presence"
        elif decision_type == 'bid_decrease':
            category_type = "prevent"
            detail = "Preventing waste"
        elif decision_type == 'pause':
            category_type = "prevent"
            detail = "Pacsternine - Waste"
        else:  # negative
            category_type = "prevent"
            detail = "Presennin - Unses"
        
        return {
            "count": len(filtered),
            "impact": total_impact,
            "type": category_type,
            "detail": detail
        }
```

**Tests for Step 1.2** (add to `backend/tests/test_metrics.py`):
```python
import pytest
from backend.services.executive_metrics import ExecutiveMetricsService

@pytest.fixture
def service():
    return ExecutiveMetricsService()

@pytest.fixture
def sample_data():
    return {
        'current_period': {
            'sales': 100000,
            'spend': 40000,
            'roas': 2.5,
            'cvr': 0.10,
            'cpc': 5.0
        },
        'previous_period': {
            'sales': 80000,
            'spend': 35000,
            'roas': 2.0,
            'cvr': 0.08,
            'cpc': 6.0
        },
        'medians': {
            'roas': 2.5,
            'cvr': 0.10
        }
    }

def test_net_contribution_calculation(service, sample_data):
    """Net contribution = revenue - spend"""
    result = service.compute_kpis(sample_data)
    
    assert result['net_contribution']['value'] == 60000  # 100k - 40k
    assert result['net_contribution']['delta_abs'] == 15000  # 60k - 45k

def test_efficiency_score_range(service, sample_data):
    """Efficiency score must be 0-100"""
    result = service.compute_kpis(sample_data)
    
    efficiency = result['efficiency_score']['value']
    assert 0 <= efficiency <= 100

def test_momentum_classification(service):
    """Test EXACT momentum logic from spec"""
    current = {'sales': 110000, 'roas': 2.4, 'spend': 45000}
    previous = {'sales': 100000, 'roas': 2.6, 'spend': 40000}
    medians = {'roas': 2.5}
    
    # Revenue up (+10%), Efficiency >= median (2.4 < 2.5 = FALSE)
    # So NOT scale_push
    classification = service._classify_momentum(current, previous, medians)
    
    # Should be something other than scale_push
    assert classification != "scale_push"

def test_risk_index_calculation(service):
    """Risk index = % spend in low-performance quadrant"""
    campaigns = [
        {'spend': 10000, 'roas': 2.0, 'cvr': 0.08},  # Below medians
        {'spend': 15000, 'roas': 3.0, 'cvr': 0.12},  # Above medians
        {'spend': 20000, 'roas': 1.5, 'cvr': 0.06},  # Below medians
    ]
    
    result = service._compute_risk_index(campaigns)
    
    # Risky spend = 10k + 20k = 30k out of 45k total = 0.667
    expected = 30000 / 45000
    assert abs(result['value'] - expected) < 0.01

def test_decision_impact_aggregation(service):
    """Decision impact sums correctly"""
    data = {
        'decision_history': [
            {'type': 'bid_increase', 'measured_impact': 5000},
            {'type': 'bid_increase', 'measured_impact': 3000},
            {'type': 'pause', 'measured_impact': -2000},
        ],
        'current_period': {'sales': 100000}
    }
    
    result = service.compute_decision_impact(data)
    
    assert result['bid_ups']['count'] == 2
    assert result['bid_ups']['impact'] == 8000
    assert result['net_impact'] == 6000  # 8000 - 2000
```

**Run Tests**:
```bash
pytest tests/test_metrics.py -v
```

✅ **Checkpoint**: All metrics tests must pass, especially momentum classification

---

### Step 1.3: Create API Endpoint

**File**: `backend/api/routes/executive_overview.py`
```python
"""
Executive Dashboard API Endpoint
READ-ONLY - No writes, no optimizer triggers
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import datetime, timedelta
from typing import Literal

from ...models.executive_schemas import ExecutiveDashboard
from ...services.executive_metrics import ExecutiveMetricsService
from ...services.data_service import DataService  # Your existing data access
from ...auth import verify_token  # Your existing auth

router = APIRouter(prefix="/api/executive", tags=["executive"])

@router.get("/overview", response_model=ExecutiveDashboard)
async def get_executive_overview(
    start_date: datetime = Query(..., description="Start of analysis period"),
    end_date: datetime = Query(..., description="End of analysis period"),
    marketplace: str = Query("UAE Amazon", description="Marketplace filter"),
    granularity: Literal["daily", "weekly", "monthly"] = Query("weekly"),
    # Add your auth dependency here
    # current_user: User = Depends(verify_token)
):
    """
    Executive dashboard overview.
    
    **IMPORTANT**: This endpoint is READ-ONLY and does NOT:
    - Trigger any optimizer actions
    - Make new Amazon Ads API calls
    - Write to database
    
    It only transforms existing cached data into executive-level insights.
    """
    
    # Validate date range
    if end_date <= start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")
    
    delta = end_date - start_date
    if delta.days > 90:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 90 days")
    
    try:
        # Fetch existing cached data (no new API calls)
        data_service = DataService()
        raw_data = await data_service.get_cached_metrics(
            # account_id=current_user.account_id,
            start_date=start_date,
            end_date=end_date,
            marketplace=marketplace,
            granularity=granularity
        )
        
        if not raw_data:
            raise HTTPException(status_code=404, detail="No data found for this period")
        
        # Transform data using metrics service
        metrics_service = ExecutiveMetricsService()
        
        kpis = metrics_service.compute_kpis(raw_data)
        momentum = metrics_service.compute_momentum(raw_data, granularity)
        decision_impact = metrics_service.compute_decision_impact(raw_data)
        
        # Performance data (simplified for now)
        performance = {
            "quadrant_data": raw_data.get('quadrant_data', []),
            "revenue_by_match_type": raw_data.get('revenue_by_match_type', {}),
            "spend_distribution": raw_data.get('spend_distribution', {}),
            "cost_efficiency_scatter": raw_data.get('cost_efficiency_scatter', [])
        }
        
        return ExecutiveDashboard(
            kpis=kpis,
            momentum=momentum,
            decision_impact=decision_impact,
            performance=performance,
            metadata={
                "data_freshness": raw_data.get("last_updated"),
                "period": f"{start_date.date()} to {end_date.date()}",
                "granularity": granularity,
                "marketplace": marketplace
            }
        )
        
    except Exception as e:
        # Log error (use your logging setup)
        print(f"Error in executive overview: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

**Tests for Step 1.3** (add to `backend/tests/test_executive_api.py`):
```python
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from backend.main import app  # Your FastAPI app

client = TestClient(app)

def test_endpoint_returns_200_with_valid_params():
    """Endpoint returns 200 with valid parameters"""
    response = client.get(
        "/api/executive/overview",
        params={
            "start_date": "2024-04-01T00:00:00",
            "end_date": "2024-04-21T00:00:00",
            "marketplace": "UAE Amazon",
            "granularity": "weekly"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Validate structure
    assert "kpis" in data
    assert "momentum" in data
    assert "decision_impact" in data
    assert "performance" in data

def test_endpoint_returns_400_with_invalid_dates():
    """Endpoint returns 400 when end_date before start_date"""
    response = client.get(
        "/api/executive/overview",
        params={
            "start_date": "2024-04-21T00:00:00",
            "end_date": "2024-04-01T00:00:00",  # Before start
        }
    )
    
    assert response.status_code == 400

def test_response_matches_schema():
    """Response matches Pydantic schema"""
    response = client.get(
        "/api/executive/overview",
        params={
            "start_date": "2024-04-01T00:00:00",
            "end_date": "2024-04-21T00:00:00",
        }
    )
    
    data = response.json()
    
    # Validate KPI structure
    assert "revenue" in data["kpis"]
    assert "value" in data["kpis"]["revenue"]
    assert "delta_pct" in data["kpis"]["revenue"]
    assert "trend" in data["kpis"]["revenue"]
    
    # Validate momentum is array
    assert isinstance(data["momentum"], list)

def test_response_time_under_3_seconds():
    """Response time is acceptable"""
    import time
    
    start = time.time()
    response = client.get(
        "/api/executive/overview",
        params={
            "start_date": "2024-04-01T00:00:00",
            "end_date": "2024-04-21T00:00:00",
        }
    )
    duration = time.time() - start
    
    assert response.status_code == 200
    assert duration < 3.0  # Under 3 seconds
```

**Run Tests**:
```bash
pytest tests/test_executive_api.py -v
```

✅ **Checkpoint**: All API tests must pass

---

## PHASE 2: FRONTEND IMPLEMENTATION

### Step 2.1: Create TypeScript Types

**File**: `frontend/types/executive.ts`
```typescript
export interface KPIMetric {
  value: number;
  delta_pct: number;
  delta_abs: number;
  trend: 'up' | 'down' | 'stable';
  sparkline?: number[];
}

export interface KPIs {
  revenue: KPIMetric;
  net_contribution: KPIMetric;
  efficiency_score: KPIMetric;
  risk_index: KPIMetric;
  scale_headroom: KPIMetric;
}

export interface MomentumDataPoint {
  date: string;
  revenue: number;
  spend_allocation: Record<string, number>;
  efficiency_line: number;
}

export interface DecisionCategory {
  count: number;
  impact: number;
  type: 'promote' | 'prevent' | 'protect';
  detail: string;
}

export interface DecisionImpact {
  period: string;
  net_impact: number;
  net_impact_pct: number;
  bid_ups: DecisionCategory;
  bid_downs: DecisionCategory;
  pauses: DecisionCategory;
  negatives: DecisionCategory;
}

export interface ExecutiveDashboard {
  kpis: KPIs;
  momentum: MomentumDataPoint[];
  decision_impact: DecisionImpact;
  performance: any;  // Add detailed types as needed
  metadata: Record<string, any>;
}
```

---

## VALIDATION & TESTING PROTOCOL

After completing each phase:
```bash
# Backend validation
cd backend
pytest tests/ -v --cov=api/routes/executive --cov=services/executive --cov=models/executive

# Frontend validation
cd frontend
npm run type-check
npm run test:unit
npm run build  # Should succeed

# Integration validation
npm run test:e2e

# Regression check
git diff main --name-only | grep -v "executive" | wc -l
# Should be 0 (no non-executive files changed)
```

---

## SUCCESS CRITERIA CHECKLIST

- [ ] Backend: All unit tests pass (schemas, metrics, API)
- [ ] Frontend: TypeScript compiles with no errors
- [ ] Integration: E2E tests pass
- [ ] Regression: Existing dashboards unchanged
- [ ] Performance: API responds < 2s, page loads < 3s
- [ ] Isolation: No imports between executive and other modules

---
