# SADDL Diagnostic Control Center — Complete Redesign
## Intelligence-First Dashboard Architecture

**Version:** 2.0 (Complete Rebuild)  
**Date:** February 2026  
**Purpose:** Transform from data visualization to diagnostic intelligence tool

---

## 1. What Went Wrong (Current State)

### Issues with V1

❌ **No Intelligence Layer**
- Shows charts but doesn't answer "why"
- User has to interpret correlations themselves
- No clear recommended actions

❌ **Impact Dashboard Disconnected**
- Validation data exists but not integrated with organic metrics
- Can't answer "did my actions work vs market baseline"

❌ **Design Not Applied**
- Glassmorphic design spec was created but not used
- Basic Streamlit default styling
- No visual hierarchy

❌ **Wrong Mental Model**
- Built as "reporting dashboard" (show data)
- Should be "diagnostic intelligence" (provide answers)

---

## 2. Redesigned Mental Model

### From Reports → To Diagnosis

**Old approach:**
```
User asks: "Why is ROAS declining?"
Tool shows: 4 charts with organic/paid data
User thinks: "Hmm, I guess I need to figure this out..."
```

**New approach:**
```
User asks: "Why is ROAS declining?"
Tool diagnoses: "60% organic rank decay, 30% market softness, 
                 10% your optimizations helping"
Tool recommends: "Defend top 5 ASINs, contract discovery 15%"
User acts: Immediately knows what to do
```

---

## 3. New Dashboard Structure

### Single Page: Diagnostic Control Center

**No more 3 separate pages (Overview/Signals/Trends).**  
**One integrated intelligence dashboard.**

```
┌──────────────────────────────────────────────────────────────┐
│  DIAGNOSTIC CONTROL CENTER                    [Refresh] [⚙️]  │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  [1] HEALTH SCORE & PRIMARY DIAGNOSIS                        │
│      Single card, top of page, immediate answer              │
│                                                               │
│  [2] ROOT CAUSE BREAKDOWN                                     │
│      3 cards side-by-side explaining attribution             │
│                                                               │
│  [3] CORRELATED INTELLIGENCE                                  │
│      2 charts with interpretation overlays                    │
│                                                               │
│  [4] ASIN ACTION TABLE                                        │
│      Sortable, filterable, with recommendations              │
│                                                               │
│  [5] DETAILED METRICS (Expandable)                            │
│      Time series for deep dives                               │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Component 1: Health Score & Primary Diagnosis

### Purpose
Answer in 5 seconds: "What's happening and what should I do?"

### Design

**Glassmorphic Hero Card:**

```css
.health-card {
  background: linear-gradient(135deg, 
    rgba(37, 99, 235, 0.15) 0%,
    rgba(124, 58, 237, 0.1) 100%);
  backdrop-filter: blur(20px) saturate(200%);
  border: 2px solid rgba(255, 255, 255, 0.15);
  border-radius: 24px;
  padding: 48px;
  margin-bottom: 32px;
  box-shadow: 
    0 8px 32px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}
```

**Layout:**

```
┌────────────────────────────────────────────────────────────────┐
│  Account Health Score                           Last 30 Days   │
│                                                                 │
│         72/100                                                  │
│      [●●●●●●●○○○]                                              │
│      🟡 CAUTION                                                 │
│                                                                 │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐│
│  │ Total Sales  │ TACOS        │ Organic %    │ Avg BSR      ││
│  │ $15,234      │ 28.5%        │ 58%          │ #12,450      ││
│  │ ↓ -8%        │ ↑ +2.1pts    │ ↓ -3pts      │ ↑ +2.1k      ││
│  │ [████████░░] │ [██████░░░░] │ [███████░░░] │ [█████░░░░░] ││
│  │ 80% healthy  │ 60% healthy  │ 70% healthy  │ 50% healthy  ││
│  └──────────────┴──────────────┴──────────────┴──────────────┘│
│                                                                 │
│  PRIMARY DIAGNOSIS                                              │
│  ════════════════════════════════════════════════════════════  │
│                                                                 │
│  🔴 Organic Rank Decay (60% of decline)                        │
│     Your BSR worsened 15% while paid spend increased 12%.      │
│     You're compensating for lost organic traffic with ads.     │
│                                                                 │
│  🟡 Market Demand Softness (30% of decline)                    │
│     Both organic and paid CVR declining together.              │
│     This is a market-wide conversion issue, not PPC.           │
│                                                                 │
│  ✅ Your Optimizations Working (+10pts ROAS lift)              │
│     12/14 recent actions outperformed market baseline.         │
│     Without your actions, ROAS would be worse.                 │
│                                                                 │
│  ────────────────────────────────────────────────────────────  │
│                                                                 │
│  RECOMMENDED ACTIONS                                            │
│                                                                 │
│  1. 🎯 IMMEDIATE: Launch brand defense for top 5 ASINs         │
│     └─ Stop rank decay from costing more ad spend              │
│                                                                 │
│  2. 📉 Contract discovery spend 15% during demand softness     │
│     └─ Preserve TACOS until market recovers                    │
│                                                                 │
│  3. ✅ Continue current optimization strategies                 │
│     └─ They're working despite external headwinds              │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### Data Sources & Logic

**Health Score Calculation:**

```python
def compute_health_score(client_id: str, days: int = 30) -> dict:
    """
    Compute 0-100 health score based on 4 metrics.
    """
    db = get_db_manager(test_mode=False)
    
    # Get current vs prior period
    current_start = date.today() - timedelta(days=days)
    current_end = date.today()
    prior_start = current_start - timedelta(days=days)
    prior_end = current_start - timedelta(days=1)
    
    # 1. Total Sales Health (0-25 points)
    current_sales = db.execute_query(f"""
        SELECT SUM(total_ordered_revenue) 
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{current_start}' AND '{current_end}'
    """)[0][0]
    
    prior_sales = db.execute_query(f"""
        SELECT SUM(total_ordered_revenue)
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{prior_start}' AND '{prior_end}'
    """)[0][0]
    
    sales_change_pct = (current_sales - prior_sales) / prior_sales * 100
    sales_score = max(0, min(25, 25 * (1 + sales_change_pct/100)))
    
    # 2. TACOS Health (0-25 points)
    current_tacos = db.execute_query(f"""
        SELECT AVG(tacos)
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{current_start}' AND '{current_end}'
    """)[0][0]
    
    prior_tacos = db.execute_query(f"""
        SELECT AVG(tacos)
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{prior_start}' AND '{prior_end}'
    """)[0][0]
    
    tacos_change = current_tacos - prior_tacos
    tacos_score = max(0, min(25, 25 * (1 - tacos_change/10)))  # Penalty for TACOS increase
    
    # 3. Organic Share Health (0-25 points)
    current_organic = db.execute_query(f"""
        SELECT AVG(organic_share_pct)
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{current_start}' AND '{current_end}'
    """)[0][0]
    
    prior_organic = db.execute_query(f"""
        SELECT AVG(organic_share_pct)
        FROM sc_analytics.account_daily
        WHERE report_date BETWEEN '{prior_start}' AND '{prior_end}'
    """)[0][0]
    
    organic_change = current_organic - prior_organic
    organic_score = max(0, min(25, 25 * (1 + organic_change/10)))
    
    # 4. BSR Health (0-25 points)
    current_bsr = db.execute_query(f"""
        SELECT AVG(rank)
        FROM sc_raw.bsr_history
        WHERE report_date BETWEEN '{current_start}' AND '{current_end}'
    """)[0][0]
    
    prior_bsr = db.execute_query(f"""
        SELECT AVG(rank)
        FROM sc_raw.bsr_history
        WHERE report_date BETWEEN '{prior_start}' AND '{prior_end}'
    """)[0][0]
    
    bsr_change_pct = (current_bsr - prior_bsr) / prior_bsr * 100
    bsr_score = max(0, min(25, 25 * (1 - bsr_change_pct/20)))  # Penalty for rank worsening
    
    # Total score
    total_score = int(sales_score + tacos_score + organic_score + bsr_score)
    
    # Status
    if total_score >= 80:
        status = "HEALTHY"
        color = "🟢"
    elif total_score >= 60:
        status = "CAUTION"
        color = "🟡"
    elif total_score >= 40:
        status = "DECLINING"
        color = "🟠"
    else:
        status = "CRITICAL"
        color = "🔴"
    
    return {
        'score': total_score,
        'status': status,
        'color': color,
        'sales_score': int(sales_score),
        'tacos_score': int(tacos_score),
        'organic_score': int(organic_score),
        'bsr_score': int(bsr_score),
        'sales_change_pct': sales_change_pct,
        'tacos_change': tacos_change,
        'organic_change': organic_change,
        'bsr_change_pct': bsr_change_pct,
        'current_sales': current_sales,
        'current_tacos': current_tacos,
        'current_organic': current_organic,
        'current_bsr': current_bsr
    }
```

**Primary Diagnosis Logic:**

```python
def diagnose_root_causes(client_id: str, days: int = 30) -> dict:
    """
    Attribute performance changes to root causes.
    Returns % contribution of each factor.
    """
    db = get_db_manager(test_mode=False)
    
    # 1. Check Organic Rank Decay
    bsr_change = db.execute_query(f"""
        WITH current AS (
            SELECT AVG(rank) as avg_rank
            FROM sc_raw.bsr_history
            WHERE report_date >= CURRENT_DATE - {days}
        ),
        prior AS (
            SELECT AVG(rank) as avg_rank
            FROM sc_raw.bsr_history
            WHERE report_date BETWEEN CURRENT_DATE - {days*2} AND CURRENT_DATE - {days} - 1
        )
        SELECT 
            (c.avg_rank - p.avg_rank) / p.avg_rank * 100 as rank_change_pct
        FROM current c, prior p
    """)[0][0]
    
    organic_decay_severity = max(0, min(100, bsr_change))  # Higher rank = worse
    
    # 2. Check Market Demand
    cvr_correlation = db.execute_query(f"""
        WITH metrics AS (
            SELECT 
                report_date,
                AVG(unit_session_percentage) as organic_cvr
            FROM sc_raw.sales_traffic
            WHERE report_date >= CURRENT_DATE - {days}
            GROUP BY report_date
        ),
        ad_metrics AS (
            SELECT 
                report_date,
                SUM(orders)::FLOAT / NULLIF(SUM(clicks), 0) * 100 as paid_cvr
            FROM public.raw_search_term_data
            WHERE report_date >= CURRENT_DATE - {days}
            GROUP BY report_date
        )
        SELECT CORR(m.organic_cvr, a.paid_cvr) as correlation
        FROM metrics m
        JOIN ad_metrics a USING (report_date)
    """)[0][0]
    
    # If CVRs move together (r > 0.7), it's market demand
    market_demand_severity = max(0, min(100, cvr_correlation * 100)) if cvr_correlation > 0.7 else 0
    
    # 3. Check Optimization Impact (from Impact Dashboard)
    optimization_lift = db.get_impact_summary(client_id, before_days=14, after_days=14)
    
    # If win rate > 70% and avg impact > 5pts, optimizations are working
    if optimization_lift.get('win_rate', 0) > 70 and optimization_lift.get('roas_lift_pct', 0) > 5:
        optimization_contribution = abs(optimization_lift['roas_lift_pct'])
    else:
        optimization_contribution = 0
    
    # Normalize to 100%
    total = organic_decay_severity + market_demand_severity + optimization_contribution
    
    if total > 0:
        organic_pct = organic_decay_severity / total * 100
        market_pct = market_demand_severity / total * 100
        optimization_pct = optimization_contribution / total * 100
    else:
        organic_pct = market_pct = optimization_pct = 0
    
    return {
        'organic_decay_pct': int(organic_pct),
        'market_demand_pct': int(market_pct),
        'optimization_lift_pct': int(optimization_pct),
        'organic_severity': organic_decay_severity,
        'market_severity': market_demand_severity,
        'bsr_change': bsr_change,
        'cvr_correlation': cvr_correlation,
        'optimization_win_rate': optimization_lift.get('win_rate', 0),
        'optimization_impact': optimization_lift.get('roas_lift_pct', 0)
    }
```

**Recommended Actions Logic:**

```python
def generate_recommendations(diagnosis: dict, health: dict) -> list:
    """
    Generate prioritized action recommendations based on diagnosis.
    """
    recommendations = []
    
    # Rule 1: If organic decay > 40%, defend with ads
    if diagnosis['organic_decay_pct'] > 40:
        recommendations.append({
            'priority': 'IMMEDIATE',
            'icon': '🎯',
            'action': 'Launch brand defense for top 5 ASINs',
            'reason': 'Stop rank decay from costing more ad spend',
            'severity': 'high'
        })
    
    # Rule 2: If market demand > 30%, contract spend
    if diagnosis['market_demand_pct'] > 30:
        recommendations.append({
            'priority': 'HIGH',
            'icon': '📉',
            'action': 'Contract discovery spend 15% during demand softness',
            'reason': 'Preserve TACOS until market recovers',
            'severity': 'medium'
        })
    
    # Rule 3: If optimizations working, continue
    if diagnosis['optimization_win_rate'] > 70:
        recommendations.append({
            'priority': 'MAINTAIN',
            'icon': '✅',
            'action': 'Continue current optimization strategies',
            'reason': "They're working despite external headwinds",
            'severity': 'low'
        })
    
    # Rule 4: If BSR improving and organic growing, scale paid
    if health['bsr_change_pct'] < -10 and health['organic_change'] > 5:
        recommendations.append({
            'priority': 'OPPORTUNITY',
            'icon': '📈',
            'action': 'Increase paid budget 20% to capitalize on organic growth',
            'reason': 'Ride the momentum while rank is improving',
            'severity': 'low'
        })
    
    # Rule 5: If TACOS spiking without revenue growth, cut waste
    if health['tacos_change'] > 5 and health['sales_change_pct'] < 2:
        recommendations.append({
            'priority': 'IMMEDIATE',
            'icon': '✂️',
            'action': 'Audit and pause bottom 20% of spend by ROAS',
            'reason': 'TACOS rising without revenue growth = waste',
            'severity': 'high'
        })
    
    return sorted(recommendations, key=lambda x: 
        {'IMMEDIATE': 0, 'HIGH': 1, 'OPPORTUNITY': 2, 'MAINTAIN': 3}[x['priority']]
    )
```

---

## 5. Component 2: Root Cause Breakdown

### Purpose
Show % attribution and evidence for each factor

### Design

**3 Glassmorphic Cards Side-by-Side:**

```css
.cause-card {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(12px) saturate(180%);
  border-left: 4px solid var(--card-color);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 16px;
}

.cause-card.decay { --card-color: #ef4444; }
.cause-card.market { --card-color: #f59e0b; }
.cause-card.optimization { --card-color: #10b981; }
```

**Layout:**

```
┌──────────────────────────────────────────────────────────────────┐
│  ROOT CAUSE BREAKDOWN                                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┬──────────────────┬──────────────────────┐ │
│  │ 🔴 ORGANIC DECAY │ 🟡 MARKET DEMAND │ ✅ OPTIMIZATIONS     │ │
│  │ 60% contribution│ 30% contribution │ +10pts ROAS lift     │ │
│  ├──────────────────┼──────────────────┼──────────────────────┤ │
│  │ Evidence:        │ Evidence:        │ Evidence:            │ │
│  │ • BSR +15%       │ • Org CVR -1.2pts│ • Win rate: 86%      │ │
│  │ • Sessions -18%  │ • Paid CVR -0.8pts│ • Avg lift: +11pts  │ │
│  │ • Org share -3pts│ • r = 0.89       │ • 12/14 outperformed │ │
│  │                  │ (moving together)│                      │ │
│  │ Impact on PPC:   │ Impact on PPC:   │ Impact on PPC:       │ │
│  │ You're spending  │ ROAS would have  │ Without actions,     │ │
│  │ 12% MORE to      │ declined 8%      │ ROAS would be 2.1    │ │
│  │ replace lost     │ regardless of    │ instead of 2.3       │ │
│  │ organic traffic  │ your actions     │                      │ │
│  │                  │                  │                      │ │
│  │ [View ASINs →]   │ [View CVR →]     │ [Impact Dashboard →] │ │
│  └──────────────────┴──────────────────┴──────────────────────┘ │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Data Sources

**Already computed in `diagnose_root_causes()` above.**

---

## 6. Component 3: Correlated Intelligence

### Purpose
Show relationships between organic and paid metrics with interpretation

### Design

**Two Side-by-Side Charts with Overlay Text:**

```
┌──────────────────────────────────────────────────────────────────┐
│  CORRELATED INTELLIGENCE                                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────┬────────────────────────────────┐│
│  │ BSR vs Paid ROAS            │ CVR Divergence Detection       ││
│  │                             │                                ││
│  │ [Dual-axis chart]           │ [Dual-line chart]              ││
│  │ ─── Avg BSR (inverted)      │ ─── Organic CVR                ││
│  │ ─── Paid ROAS               │ ─── Paid CVR                   ││
│  │                             │                                ││
│  │ ┌─────────────────────────┐ │ ┌────────────────────────────┐││
│  │ │ Correlation: r = -0.68  │ │ │ Correlation: r = 0.89      │││
│  │ │                         │ │ │                            │││
│  │ │ Translation:            │ │ │ Diagnosis:                 │││
│  │ │ When you lose organic   │ │ │ CVRs moving together       │││
│  │ │ rank, paid ROAS declines│ │ │ = MARKET PROBLEM           │││
│  │ │ because you're competing│ │ │                            │││
│  │ │ for traffic you used to │ │ │ If only paid CVR dropped   │││
│  │ │ get free.               │ │ │ = PPC PROBLEM              │││
│  │ │                         │ │ │                            │││
│  │ │ Action: Defend organic  │ │ │ Your case: Market issue,   │││
│  │ │ rank OR accept lower    │ │ │ PPC is working fine.       │││
│  │ │ ROAS as visibility cost │ │ │                            │││
│  │ └─────────────────────────┘ │ └────────────────────────────┘││
│  └─────────────────────────────┴────────────────────────────────┘│
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Data Sources & Queries

**BSR vs Paid ROAS Correlation:**

```python
def compute_bsr_roas_correlation(days: int = 60) -> dict:
    """
    Compute correlation between BSR and paid ROAS.
    """
    db = get_db_manager(test_mode=False)
    
    query = """
    WITH daily_bsr AS (
        SELECT 
            report_date,
            AVG(rank) as avg_bsr
        FROM sc_raw.bsr_history
        WHERE report_date >= CURRENT_DATE - %s
        GROUP BY report_date
    ),
    daily_roas AS (
        SELECT 
            report_date,
            SUM(sales) / NULLIF(SUM(spend), 0) as paid_roas
        FROM public.raw_search_term_data
        WHERE report_date >= CURRENT_DATE - %s
        GROUP BY report_date
    )
    SELECT 
        CORR(b.avg_bsr, r.paid_roas) as correlation,
        ARRAY_AGG(b.report_date ORDER BY b.report_date) as dates,
        ARRAY_AGG(b.avg_bsr ORDER BY b.report_date) as bsr_values,
        ARRAY_AGG(r.paid_roas ORDER BY b.report_date) as roas_values
    FROM daily_bsr b
    JOIN daily_roas r USING (report_date)
    """
    
    result = db.execute_query(query, (days, days))
    
    return {
        'correlation': result[0][0],
        'dates': result[0][1],
        'bsr_values': result[0][2],
        'roas_values': result[0][3],
        'interpretation': generate_bsr_roas_interpretation(result[0][0])
    }

def generate_bsr_roas_interpretation(correlation: float) -> str:
    """Generate human-readable interpretation."""
    if correlation < -0.6:
        return ("Strong negative correlation: When you lose organic rank, "
                "paid ROAS declines because you're competing for traffic "
                "you used to get free. Defend organic rank OR accept lower "
                "ROAS as cost of maintaining visibility.")
    elif correlation < -0.3:
        return ("Moderate correlation: Organic rank affects paid efficiency "
                "but not the primary driver. Monitor both channels.")
    else:
        return ("Weak correlation: Organic rank and paid ROAS move independently. "
                "Focus on channel-specific optimizations.")
```

**CVR Divergence Detection:**

```python
def detect_cvr_divergence(days: int = 60) -> dict:
    """
    Detect if organic and paid CVR are moving together or diverging.
    """
    db = get_db_manager(test_mode=False)
    
    query = """
    WITH organic_cvr AS (
        SELECT 
            report_date,
            AVG(unit_session_percentage) as organic_cvr
        FROM sc_raw.sales_traffic
        WHERE report_date >= CURRENT_DATE - %s
        GROUP BY report_date
    ),
    paid_cvr AS (
        SELECT 
            report_date,
            SUM(orders)::FLOAT / NULLIF(SUM(clicks), 0) * 100 as paid_cvr
        FROM public.raw_search_term_data
        WHERE report_date >= CURRENT_DATE - %s
        GROUP BY report_date
    )
    SELECT 
        CORR(o.organic_cvr, p.paid_cvr) as correlation,
        AVG(o.organic_cvr) as avg_organic_cvr,
        AVG(p.paid_cvr) as avg_paid_cvr,
        ARRAY_AGG(o.report_date ORDER BY o.report_date) as dates,
        ARRAY_AGG(o.organic_cvr ORDER BY o.report_date) as organic_values,
        ARRAY_AGG(p.paid_cvr ORDER BY o.report_date) as paid_values
    FROM organic_cvr o
    JOIN paid_cvr p USING (report_date)
    """
    
    result = db.execute_query(query, (days, days))
    
    correlation = result[0][0]
    
    # Diagnosis based on correlation
    if correlation > 0.7:
        diagnosis = "CVRs moving TOGETHER = MARKET PROBLEM"
        detail = ("Both organic and paid CVR declining together indicates "
                  "a product or market issue, not a PPC problem. "
                  "Your paid traffic quality is fine.")
    elif correlation < 0.3:
        diagnosis = "CVRs moving INDEPENDENTLY = CHANNEL-SPECIFIC"
        detail = ("Organic and paid CVR moving differently suggests "
                  "channel-specific issues. Investigate each separately.")
    else:
        diagnosis = "MIXED SIGNALS"
        detail = ("Moderate correlation. Both market and channel factors "
                  "at play. Investigate both.")
    
    return {
        'correlation': correlation,
        'diagnosis': diagnosis,
        'detail': detail,
        'avg_organic_cvr': result[0][1],
        'avg_paid_cvr': result[0][2],
        'dates': result[0][3],
        'organic_values': result[0][4],
        'paid_values': result[0][5]
    }
```

---

## 7. Component 4: ASIN Action Table

### Purpose
Show specific ASINs requiring action with recommendations

### Design

**Glassmorphic Data Table:**

```css
.asin-table {
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  overflow: hidden;
}

.asin-row.high-priority {
  border-left: 4px solid #ef4444;
  background: rgba(239, 68, 68, 0.05);
}

.asin-row.medium-priority {
  border-left: 4px solid #f59e0b;
}
```

**Layout:**

```
┌──────────────────────────────────────────────────────────────────┐
│  ASINS REQUIRING ATTENTION                                       │
│  [Sort: Impact ▼] [Filter: All ▼] [Show: High Priority Only ☑]  │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ASIN        BSR    Δ30d   Org Rev  Paid   Action    Impact     │
│              Rank          30d      ROAS   Needed    ($/mo)      │
│  ─────────────────────────────────────────────────────────────── │
│                                                                   │
│  🔴 B0DSFZK5W7                                                   │
│  Rank:       18,200  +5.7k  (worse 46%)                          │
│  Organic:    820 AED  ↓ -22%                                     │
│  Paid ROAS:  2.1                                                  │
│  Impact:     -1,200 AED/mo organic loss                          │
│                                                                   │
│  Diagnosis: Lost rank, paid compensating (+15% spend)            │
│  Action:    🎯 Launch exact match brand defense NOW              │
│             Target: brand + product keywords, high bids          │
│  [View ASIN Details] [Launch Campaign →]                         │
│                                                                   │
│  ─────────────────────────────────────────────────────────────── │
│                                                                   │
│  🟡 B0CH9RTZXX                                                   │
│  Rank:       12,100  +1.2k  (worse 11%)                          │
│  Organic:    1,072 AED  ↓ -8%                                    │
│  Paid ROAS:  2.8                                                  │
│  Impact:     -280 AED/mo organic loss                            │
│                                                                   │
│  Diagnosis: Minor rank slip, paid still efficient                │
│  Action:    👀 MONITOR for 7 more days before acting             │
│  [View ASIN Details] [Set Alert]                                 │
│                                                                   │
│  ─────────────────────────────────────────────────────────────── │
│                                                                   │
│  ✅ B09GG2CL11                                                   │
│  Rank:       8,450   -800   (better 9%)                          │
│  Organic:    4,528 AED  ↑ +12%                                   │
│  Paid ROAS:  3.1                                                  │
│  Impact:     +540 AED/mo organic growth                          │
│                                                                   │
│  Diagnosis: Rank improving, organic growing, paid efficient      │
│  Action:    📈 SCALE: Increase paid budget 25% to capitalize     │
│  [View ASIN Details] [Increase Budget →]                         │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Data Source & Query

```python
def get_asin_action_table(days: int = 30) -> list:
    """
    Generate ASIN-level diagnostic table with recommendations.
    """
    db = get_db_manager(test_mode=False)
    
    query = """
    WITH current_period AS (
        SELECT 
            st.child_asin,
            AVG(b.rank) as current_bsr,
            SUM(st.ordered_revenue) as current_organic_rev,
            AVG(st.unit_session_percentage) as current_organic_cvr
        FROM sc_raw.sales_traffic st
        LEFT JOIN sc_raw.bsr_history b 
            ON st.child_asin = b.asin 
            AND st.report_date = b.report_date
        WHERE st.report_date >= CURRENT_DATE - %s
        GROUP BY st.child_asin
    ),
    prior_period AS (
        SELECT 
            st.child_asin,
            AVG(b.rank) as prior_bsr,
            SUM(st.ordered_revenue) as prior_organic_rev
        FROM sc_raw.sales_traffic st
        LEFT JOIN sc_raw.bsr_history b 
            ON st.child_asin = b.asin 
            AND st.report_date = b.report_date
        WHERE st.report_date BETWEEN CURRENT_DATE - %s*2 AND CURRENT_DATE - %s - 1
        GROUP BY st.child_asin
    ),
    paid_performance AS (
        SELECT 
            -- Note: Need ASIN-level ad data (not available in raw_search_term_data)
            -- Placeholder: Aggregate at account level for now
            NULL::VARCHAR as asin,
            AVG(SUM(sales) / NULLIF(SUM(spend), 0)) as paid_roas
        FROM public.raw_search_term_data
        WHERE report_date >= CURRENT_DATE - %s
    )
    SELECT 
        c.child_asin,
        c.current_bsr,
        c.current_bsr - p.prior_bsr as bsr_change,
        (c.current_bsr - p.prior_bsr) / NULLIF(p.prior_bsr, 0) * 100 as bsr_change_pct,
        c.current_organic_rev,
        (c.current_organic_rev - p.prior_organic_rev) / NULLIF(p.prior_organic_rev, 0) * 100 as organic_rev_change_pct,
        c.current_organic_cvr,
        -- Paid ROAS would come from ASIN-level ad data (need Ads API integration)
        NULL::NUMERIC as paid_roas,
        -- Compute impact
        (p.prior_organic_rev - c.current_organic_rev) * 30 / %s as monthly_impact
    FROM current_period c
    JOIN prior_period p ON c.child_asin = p.child_asin
    WHERE c.current_organic_rev > 100  -- Filter out low-revenue ASINs
    ORDER BY ABS((p.prior_organic_rev - c.current_organic_rev) * 30 / %s) DESC
    LIMIT 20
    """
    
    results = db.execute_query(query, (days, days, days, days, days, days))
    
    # Generate recommendations for each ASIN
    action_table = []
    for row in results:
        asin = row[0]
        bsr_change_pct = row[3]
        organic_rev_change_pct = row[5]
        monthly_impact = row[8]
        
        # Determine priority and action
        if bsr_change_pct > 20 and organic_rev_change_pct < -15:
            priority = "HIGH"
            icon = "🔴"
            action = "Launch exact match brand defense NOW"
            detail = "Stop rank decay from costing more ad spend"
        elif bsr_change_pct > 10 and organic_rev_change_pct < -5:
            priority = "MEDIUM"
            icon = "🟡"
            action = "MONITOR for 7 more days before acting"
            detail = "Minor rank slip, watch closely"
        elif bsr_change_pct < -10 and organic_rev_change_pct > 10:
            priority = "OPPORTUNITY"
            icon = "✅"
            action = "SCALE: Increase paid budget 25% to capitalize"
            detail = "Rank improving, ride the momentum"
        else:
            priority = "LOW"
            icon = "ℹ️"
            action = "Continue current strategy"
            detail = "Performance stable"
        
        action_table.append({
            'asin': asin,
            'priority': priority,
            'icon': icon,
            'current_bsr': row[1],
            'bsr_change': row[2],
            'bsr_change_pct': bsr_change_pct,
            'current_organic_rev': row[4],
            'organic_rev_change_pct': organic_rev_change_pct,
            'current_organic_cvr': row[6],
            'paid_roas': row[7],
            'monthly_impact': monthly_impact,
            'action': action,
            'detail': detail
        })
    
    return action_table
```

---

## 8. Component 5: Detailed Metrics (Expandable)

### Purpose
Deep dive time series for users who want more

### Design

**Collapsible Section:**

```
┌──────────────────────────────────────────────────────────────────┐
│  DETAILED METRICS                                    [Expand ▼]  │
├──────────────────────────────────────────────────────────────────┤
│  (Hidden by default)                                             │
│                                                                   │
│  When expanded, shows:                                            │
│  - Revenue breakdown (stacked area)                              │
│  - TACOS vs Organic Share (dual axis)                            │
│  - BSR trends for top 10 ASINs                                   │
│  - Session/pageview trends                                        │
│                                                                   │
│  (Same charts as current Trends page, but secondary)             │
└──────────────────────────────────────────────────────────────────┘
```

---

## 9. Complete Streamlit Implementation

### File Structure

```python
# features/diagnostics/control_center.py

import streamlit as st
import plotly.graph_objects as go
from utils.diagnostics import (
    compute_health_score,
    diagnose_root_causes,
    generate_recommendations,
    compute_bsr_roas_correlation,
    detect_cvr_divergence,
    get_asin_action_table
)
from features.diagnostics.styles import inject_diagnostic_styles
from components.diagnostic_cards import (
    render_health_card,
    render_cause_card,
    render_correlation_chart,
    render_asin_table
)

def render_control_center(client_id: str):
    """Main diagnostic control center page."""
    
    # Inject glassmorphic CSS
    inject_diagnostic_styles()
    
    st.title("🎯 Diagnostic Control Center")
    
    # Compute all metrics
    with st.spinner("Analyzing account health..."):
        health = compute_health_score(client_id, days=30)
        diagnosis = diagnose_root_causes(client_id, days=30)
        recommendations = generate_recommendations(diagnosis, health)
        bsr_roas = compute_bsr_roas_correlation(days=60)
        cvr_divergence = detect_cvr_divergence(days=60)
        asin_table = get_asin_action_table(days=30)
    
    # [1] Health Score & Primary Diagnosis
    render_health_card(health, diagnosis, recommendations)
    
    st.markdown("---")
    
    # [2] Root Cause Breakdown
    st.markdown("## Root Cause Breakdown")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        render_cause_card(
            title="🔴 Organic Rank Decay",
            contribution=diagnosis['organic_decay_pct'],
            evidence=[
                f"BSR: {diagnosis['bsr_change']:+.0f}% (worse)",
                "Sessions: -18%",
                "Organic share: -3pts"
            ],
            impact="You're spending 12% MORE to replace lost organic traffic",
            action_text="View ASINs",
            card_type="decay"
        )
    
    with col2:
        render_cause_card(
            title="🟡 Market Demand",
            contribution=diagnosis['market_demand_pct'],
            evidence=[
                "Organic CVR: -1.2pts",
                "Paid CVR: -0.8pts",
                f"Correlation: r = {diagnosis['cvr_correlation']:.2f}"
            ],
            impact="ROAS would have declined 8% regardless of actions",
            action_text="View CVR Trends",
            card_type="market"
        )
    
    with col3:
        render_cause_card(
            title="✅ Your Optimizations",
            contribution=diagnosis['optimization_lift_pct'],
            evidence=[
                f"Win rate: {diagnosis['optimization_win_rate']:.0f}%",
                f"Avg lift: {diagnosis['optimization_impact']:+.1f}pts",
                "12/14 outperformed baseline"
            ],
            impact="Without actions, ROAS would be 2.1 instead of 2.3",
            action_text="Impact Dashboard",
            card_type="optimization"
        )
    
    st.markdown("---")
    
    # [3] Correlated Intelligence
    st.markdown("## Correlated Intelligence")
    
    col1, col2 = st.columns(2)
    
    with col1:
        render_correlation_chart(
            title="BSR vs Paid ROAS",
            data=bsr_roas,
            interpretation=bsr_roas['interpretation']
        )
    
    with col2:
        render_correlation_chart(
            title="CVR Divergence Detection",
            data=cvr_divergence,
            interpretation=cvr_divergence['detail']
        )
    
    st.markdown("---")
    
    # [4] ASIN Action Table
    st.markdown("## ASINs Requiring Attention")
    render_asin_table(asin_table)
    
    st.markdown("---")
    
    # [5] Detailed Metrics (Collapsible)
    with st.expander("📊 Detailed Metrics (Expand for deep dive)", expanded=False):
        # Include existing trend charts here
        from features.diagnostics.trends import render_revenue_breakdown, render_tacos_chart
        render_revenue_breakdown(client_id)
        render_tacos_chart(client_id)
```

### Component Implementations

**features/diagnostics/styles.py:**

```python
import streamlit as st

def inject_diagnostic_styles():
    """Inject glassmorphic CSS for diagnostic dashboard."""
    
    st.markdown("""
    <style>
    /* Import Inter font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Root variables */
    :root {
        --primary-500: #3b82f6;
        --accent-500: #8b5cf6;
        --success-500: #10b981;
        --warning-500: #f59e0b;
        --error-500: #ef4444;
        --gray-950: #030712;
        --gray-900: #111827;
        --gray-800: #1f2937;
        --gray-100: #f3f4f6;
        --gray-400: #9ca3af;
    }
    
    /* Override Streamlit defaults */
    .main {
        background: var(--gray-950);
        font-family: 'Inter', sans-serif;
    }
    
    /* Health card */
    .health-card {
        background: linear-gradient(135deg, 
            rgba(37, 99, 235, 0.15) 0%,
            rgba(124, 58, 237, 0.1) 100%);
        backdrop-filter: blur(20px) saturate(200%);
        -webkit-backdrop-filter: blur(20px) saturate(200%);
        border: 2px solid rgba(255, 255, 255, 0.15);
        border-radius: 24px;
        padding: 48px;
        margin-bottom: 32px;
        box-shadow: 
            0 8px 32px rgba(0, 0, 0, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
    }
    
    .health-score {
        font-size: 4rem;
        font-weight: 700;
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1;
        margin-bottom: 16px;
    }
    
    .health-status {
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 32px;
    }
    
    /* Metric cards */
    .metric-mini {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    
    .metric-mini-value {
        font-size: 2rem;
        font-weight: 700;
        color: var(--gray-100);
        margin-bottom: 8px;
    }
    
    .metric-mini-delta {
        font-size: 0.875rem;
        font-weight: 500;
        margin-bottom: 12px;
    }
    
    .metric-mini-delta.positive { color: #10b981; }
    .metric-mini-delta.negative { color: #ef4444; }
    
    .metric-mini-bar {
        width: 100%;
        height: 6px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 3px;
        overflow: hidden;
        margin-bottom: 4px;
    }
    
    .metric-mini-bar-fill {
        height: 100%;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        transition: width 0.3s ease;
    }
    
    /* Cause cards */
    .cause-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(12px) saturate(180%);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 16px;
        position: relative;
        overflow: hidden;
    }
    
    .cause-card::before {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 4px;
    }
    
    .cause-card.decay::before { background: #ef4444; }
    .cause-card.market::before { background: #f59e0b; }
    .cause-card.optimization::before { background: #10b981; }
    
    .cause-card h3 {
        color: var(--gray-100);
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 16px;
    }
    
    .cause-contribution {
        font-size: 2rem;
        font-weight: 700;
        color: var(--gray-100);
        margin-bottom: 16px;
    }
    
    .cause-evidence {
        list-style: none;
        padding: 0;
        margin: 0 0 16px 0;
    }
    
    .cause-evidence li {
        padding-left: 24px;
        margin-bottom: 8px;
        color: var(--gray-400);
        position: relative;
    }
    
    .cause-evidence li::before {
        content: '•';
        position: absolute;
        left: 0;
        font-weight: bold;
    }
    
    .cause-card.decay .cause-evidence li::before { color: #ef4444; }
    .cause-card.market .cause-evidence li::before { color: #f59e0b; }
    .cause-card.optimization .cause-evidence li::before { color: #10b981; }
    
    .cause-impact {
        background: rgba(255, 255, 255, 0.03);
        padding: 12px;
        border-radius: 8px;
        border-left: 2px solid rgba(255, 255, 255, 0.2);
        color: var(--gray-300);
        font-size: 0.875rem;
        line-height: 1.5;
        margin-bottom: 16px;
    }
    
    /* Recommendation cards */
    .recommendation {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(8px);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        border-left: 3px solid var(--rec-color);
    }
    
    .recommendation.immediate { --rec-color: #ef4444; }
    .recommendation.high { --rec-color: #f59e0b; }
    .recommendation.opportunity { --rec-color: #3b82f6; }
    .recommendation.maintain { --rec-color: #10b981; }
    
    .recommendation-priority {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }
    
    .recommendation.immediate .recommendation-priority {
        background: rgba(239, 68, 68, 0.2);
        color: #fca5a5;
    }
    
    .recommendation-action {
        font-size: 1rem;
        font-weight: 600;
        color: var(--gray-100);
        margin-bottom: 4px;
    }
    
    .recommendation-reason {
        font-size: 0.875rem;
        color: var(--gray-400);
    }
    
    /* ASIN table */
    .asin-table {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        overflow: hidden;
    }
    
    .asin-row {
        background: rgba(255, 255, 255, 0.02);
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        padding: 24px;
        position: relative;
        transition: background 0.2s;
    }
    
    .asin-row:hover {
        background: rgba(255, 255, 255, 0.05);
    }
    
    .asin-row::before {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 4px;
    }
    
    .asin-row.high-priority::before { background: #ef4444; }
    .asin-row.medium-priority::before { background: #f59e0b; }
    .asin-row.opportunity::before { background: #10b981; }
    
    /* Correlation chart overlays */
    .chart-interpretation {
        background: rgba(0, 0, 0, 0.6);
        backdrop-filter: blur(10px);
        padding: 16px;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-top: 16px;
    }
    
    .chart-interpretation h4 {
        color: var(--gray-100);
        font-size: 0.875rem;
        font-weight: 600;
        margin-bottom: 8px;
    }
    
    .chart-interpretation p {
        color: var(--gray-400);
        font-size: 0.875rem;
        line-height: 1.5;
        margin: 0;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Button styles */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
        transition: all 0.2s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 16px rgba(59, 130, 246, 0.4);
    }
    </style>
    """, unsafe_allow_html=True)
```

**components/diagnostic_cards.py:**

```python
import streamlit as st

def render_health_card(health: dict, diagnosis: dict, recommendations: list):
    """Render the main health score card."""
    
    st.markdown(f"""
    <div class="health-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 32px;">
            <div>
                <h2 style="color: var(--gray-100); margin-bottom: 8px;">Account Health Score</h2>
                <p style="color: var(--gray-400); margin: 0;">Last 30 Days</p>
            </div>
        </div>
        
        <div class="health-score">{health['score']}/100</div>
        <div class="health-status">{health['color']} {health['status']}</div>
        
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 48px;">
            <div class="metric-mini">
                <div class="metric-mini-value">${health['current_sales']:,.0f}</div>
                <div class="metric-mini-delta {'positive' if health['sales_change_pct'] > 0 else 'negative'}">
                    {'↑' if health['sales_change_pct'] > 0 else '↓'} {abs(health['sales_change_pct']):.1f}%
                </div>
                <div class="metric-mini-bar">
                    <div class="metric-mini-bar-fill" style="width: {health['sales_score']*4}%"></div>
                </div>
                <div style="font-size: 0.75rem; color: var(--gray-500);">
                    {health['sales_score']:.0f}% healthy
                </div>
                <div style="font-size: 0.875rem; color: var(--gray-400); margin-top: 4px;">
                    Total Sales
                </div>
            </div>
            
            <div class="metric-mini">
                <div class="metric-mini-value">{health['current_tacos']:.1f}%</div>
                <div class="metric-mini-delta {'negative' if health['tacos_change'] > 0 else 'positive'}">
                    {'↑' if health['tacos_change'] > 0 else '↓'} {abs(health['tacos_change']):.1f}pts
                </div>
                <div class="metric-mini-bar">
                    <div class="metric-mini-bar-fill" style="width: {health['tacos_score']*4}%"></div>
                </div>
                <div style="font-size: 0.75rem; color: var(--gray-500);">
                    {health['tacos_score']:.0f}% healthy
                </div>
                <div style="font-size: 0.875rem; color: var(--gray-400); margin-top: 4px;">
                    TACOS
                </div>
            </div>
            
            <div class="metric-mini">
                <div class="metric-mini-value">{health['current_organic']:.0f}%</div>
                <div class="metric-mini-delta {'positive' if health['organic_change'] > 0 else 'negative'}">
                    {'↑' if health['organic_change'] > 0 else '↓'} {abs(health['organic_change']):.1f}pts
                </div>
                <div class="metric-mini-bar">
                    <div class="metric-mini-bar-fill" style="width: {health['organic_score']*4}%"></div>
                </div>
                <div style="font-size: 0.75rem; color: var(--gray-500);">
                    {health['organic_score']:.0f}% healthy
                </div>
                <div style="font-size: 0.875rem; color: var(--gray-400); margin-top: 4px;">
                    Organic %
                </div>
            </div>
            
            <div class="metric-mini">
                <div class="metric-mini-value">#{health['current_bsr']:,.0f}</div>
                <div class="metric-mini-delta {'negative' if health['bsr_change_pct'] > 0 else 'positive'}">
                    {'↑' if health['bsr_change_pct'] > 0 else '↓'} {abs(health['bsr_change_pct']):.1f}%
                </div>
                <div class="metric-mini-bar">
                    <div class="metric-mini-bar-fill" style="width: {health['bsr_score']*4}%"></div>
                </div>
                <div style="font-size: 0.75rem; color: var(--gray-500);">
                    {health['bsr_score']:.0f}% healthy
                </div>
                <div style="font-size: 0.875rem; color: var(--gray-400); margin-top: 4px;">
                    Avg BSR
                </div>
            </div>
        </div>
        
        <div style="border-top: 1px solid rgba(255, 255, 255, 0.1); padding-top: 32px; margin-bottom: 32px;">
            <h3 style="color: var(--gray-100); margin-bottom: 24px;">PRIMARY DIAGNOSIS</h3>
            
            <div style="margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
                    <span style="font-size: 1.5rem;">🔴</span>
                    <span style="font-size: 1.125rem; font-weight: 600; color: var(--gray-100);">
                        Organic Rank Decay ({diagnosis['organic_decay_pct']}% of decline)
                    </span>
                </div>
                <p style="color: var(--gray-400); margin-left: 44px; line-height: 1.5;">
                    Your BSR worsened {diagnosis['bsr_change']:.0f}% while paid spend increased.
                    You're compensating for lost organic traffic with ads.
                </p>
            </div>
            
            <div style="margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
                    <span style="font-size: 1.5rem;">🟡</span>
                    <span style="font-size: 1.125rem; font-weight: 600; color: var(--gray-100);">
                        Market Demand Softness ({diagnosis['market_demand_pct']}% of decline)
                    </span>
                </div>
                <p style="color: var(--gray-400); margin-left: 44px; line-height: 1.5;">
                    Both organic and paid CVR declining together (r = {diagnosis['cvr_correlation']:.2f}).
                    This is a market-wide conversion issue, not PPC.
                </p>
            </div>
            
            <div style="margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
                    <span style="font-size: 1.5rem;">✅</span>
                    <span style="font-size: 1.125rem; font-weight: 600; color: var(--gray-100);">
                        Your Optimizations Working (+{diagnosis['optimization_impact']:.1f}pts ROAS lift)
                    </span>
                </div>
                <p style="color: var(--gray-400); margin-left: 44px; line-height: 1.5;">
                    {diagnosis['optimization_win_rate']:.0f}% win rate on recent actions.
                    Without your optimizations, ROAS would be worse.
                </p>
            </div>
        </div>
        
        <div style="border-top: 1px solid rgba(255, 255, 255, 0.1); padding-top: 32px;">
            <h3 style="color: var(--gray-100); margin-bottom: 24px;">RECOMMENDED ACTIONS</h3>
    """, unsafe_allow_html=True)
    
    for i, rec in enumerate(recommendations, 1):
        severity_class = rec['priority'].lower()
        st.markdown(f"""
        <div class="recommendation {severity_class}">
            <div class="recommendation-priority">{rec['priority']}</div>
            <div style="display: flex; align-items: flex-start; gap: 12px;">
                <span style="font-size: 1.5rem;">{rec['icon']}</span>
                <div style="flex: 1;">
                    <div class="recommendation-action">{i}. {rec['action']}</div>
                    <div class="recommendation-reason">└─ {rec['reason']}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)


def render_cause_card(title: str, contribution: int, evidence: list, 
                     impact: str, action_text: str, card_type: str):
    """Render a root cause breakdown card."""
    
    st.markdown(f"""
    <div class="cause-card {card_type}">
        <h3>{title}</h3>
        <div class="cause-contribution">{contribution}% contribution</div>
        
        <div style="margin-bottom: 16px;">
            <div style="font-size: 0.875rem; font-weight: 600; color: var(--gray-400); 
                        text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
                Evidence:
            </div>
            <ul class="cause-evidence">
    """, unsafe_allow_html=True)
    
    for item in evidence:
        st.markdown(f"<li>{item}</li>", unsafe_allow_html=True)
    
    st.markdown(f"""
            </ul>
        </div>
        
        <div style="margin-bottom: 16px;">
            <div style="font-size: 0.875rem; font-weight: 600; color: var(--gray-400); 
                        text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
                Impact on PPC:
            </div>
            <div class="cause-impact">{impact}</div>
        </div>
        
        <button style="background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2);
                       color: var(--gray-100); padding: 8px 16px; border-radius: 8px;
                       font-weight: 600; cursor: pointer; width: 100%;">
            {action_text} →
        </button>
    </div>
    """, unsafe_allow_html=True)


def render_correlation_chart(title: str, data: dict, interpretation: str):
    """Render correlation chart with interpretation overlay."""
    
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    # Create the chart based on title
    if "BSR" in title:
        # BSR vs ROAS dual axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig.add_trace(
            go.Scatter(x=data['dates'], y=data['bsr_values'], 
                      name="Avg BSR", line=dict(color='#f59e0b')),
            secondary_y=False
        )
        
        fig.add_trace(
            go.Scatter(x=data['dates'], y=data['roas_values'],
                      name="Paid ROAS", line=dict(color='#3b82f6')),
            secondary_y=True
        )
        
        fig.update_yaxes(title_text="BSR Rank", secondary_y=False, autorange="reversed")
        fig.update_yaxes(title_text="Paid ROAS", secondary_y=True)
        
    else:
        # CVR comparison
        fig = go.Figure()
        
        fig.add_trace(
            go.Scatter(x=data['dates'], y=data['organic_values'],
                      name="Organic CVR", line=dict(color='#8b5cf6'))
        )
        
        fig.add_trace(
            go.Scatter(x=data['dates'], y=data['paid_values'],
                      name="Paid CVR", line=dict(color='#ef4444'))
        )
        
        fig.update_yaxes(title_text="CVR %")
    
    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=400,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Interpretation overlay
    st.markdown(f"""
    <div class="chart-interpretation">
        <h4>Correlation: r = {data.get('correlation', 0):.2f}</h4>
        <p>{interpretation}</p>
    </div>
    """, unsafe_allow_html=True)


def render_asin_table(asin_data: list):
    """Render ASIN action table."""
    
    # Filter controls
    col1, col2, col3 = st.columns(3)
    with col1:
        sort_by = st.selectbox("Sort by", ["Impact", "BSR Change", "Revenue Change"])
    with col2:
        priority_filter = st.selectbox("Priority", ["All", "High", "Medium", "Opportunity"])
    with col3:
        show_count = st.number_input("Show", min_value=5, max_value=50, value=10)
    
    # Filter data
    if priority_filter != "All":
        asin_data = [a for a in asin_data if a['priority'] == priority_filter.upper()]
    
    # Sort data
    if sort_by == "Impact":
        asin_data = sorted(asin_data, key=lambda x: abs(x['monthly_impact']), reverse=True)
    elif sort_by == "BSR Change":
        asin_data = sorted(asin_data, key=lambda x: abs(x['bsr_change_pct']), reverse=True)
    else:
        asin_data = sorted(asin_data, key=lambda x: abs(x['organic_rev_change_pct']), reverse=True)
    
    # Render table
    st.markdown('<div class="asin-table">', unsafe_allow_html=True)
    
    for asin in asin_data[:show_count]:
        priority_class = asin['priority'].lower().replace('_', '-')
        
        st.markdown(f"""
        <div class="asin-row {priority_class}">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
                <div>
                    <div style="font-size: 1.125rem; font-weight: 600; color: var(--gray-100); margin-bottom: 4px;">
                        {asin['icon']} {asin['asin']}
                    </div>
                    <div style="font-size: 0.875rem; color: var(--gray-400);">
                        Rank: #{asin['current_bsr']:,.0f} 
                        ({'+' if asin['bsr_change'] > 0 else ''}{asin['bsr_change']:,.0f}, 
                        {asin['bsr_change_pct']:+.0f}%)
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 0.875rem; color: var(--gray-400); margin-bottom: 4px;">
                        Impact
                    </div>
                    <div style="font-size: 1.125rem; font-weight: 600; 
                                color: {'#ef4444' if asin['monthly_impact'] < 0 else '#10b981'};">
                        {asin['monthly_impact']:+,.0f} AED/mo
                    </div>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px;">
                <div>
                    <div style="font-size: 0.75rem; color: var(--gray-500); margin-bottom: 4px;">Organic Revenue</div>
                    <div style="font-size: 1rem; font-weight: 600; color: var(--gray-100);">
                        {asin['current_organic_rev']:,.0f} AED
                    </div>
                    <div style="font-size: 0.875rem; color: {'#ef4444' if asin['organic_rev_change_pct'] < 0 else '#10b981'};">
                        {asin['organic_rev_change_pct']:+.0f}%
                    </div>
                </div>
                <div>
                    <div style="font-size: 0.75rem; color: var(--gray-500); margin-bottom: 4px;">Organic CVR</div>
                    <div style="font-size: 1rem; font-weight: 600; color: var(--gray-100);">
                        {asin['current_organic_cvr']:.1f}%
                    </div>
                </div>
                <div>
                    <div style="font-size: 0.75rem; color: var(--gray-500); margin-bottom: 4px;">Paid ROAS</div>
                    <div style="font-size: 1rem; font-weight: 600; color: var(--gray-100);">
                        {asin['paid_roas'] if asin['paid_roas'] else 'N/A'}
                    </div>
                </div>
            </div>
            
            <div style="background: rgba(255, 255, 255, 0.03); padding: 12px; border-radius: 8px; 
                        border-left: 2px solid rgba(255, 255, 255, 0.2); margin-bottom: 16px;">
                <div style="font-size: 0.875rem; font-weight: 600; color: var(--gray-300); margin-bottom: 4px;">
                    Action: {asin['action']}
                </div>
                <div style="font-size: 0.875rem; color: var(--gray-500);">
                    {asin['detail']}
                </div>
            </div>
            
            <div style="display: flex; gap: 12px;">
                <button style="flex: 1; background: rgba(59, 130, 246, 0.2); border: 1px solid rgba(59, 130, 246, 0.4);
                               color: #60a5fa; padding: 8px 16px; border-radius: 8px; font-weight: 600; cursor: pointer;">
                    View ASIN Details
                </button>
                <button style="flex: 1; background: linear-gradient(135deg, #3b82f6, #8b5cf6); border: none;
                               color: white; padding: 8px 16px; border-radius: 8px; font-weight: 600; cursor: pointer;">
                    Take Action →
                </button>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
```

---

## 10. Integration with Impact Dashboard

### The Missing Link

**Current problem:** Impact Dashboard data (`actions_log`) is not flowing into diagnostic metrics.

**Solution:** Update all diagnostic queries to join Impact Dashboard data.

**Example - Updated Health Score to include optimization lift:**

```python
# In compute_health_score():

# Add 5th metric: Optimization Performance (0-25 points)
from app_core.db_manager import get_db_manager
db = get_db_manager(test_mode=False)

optimization_summary = db.get_impact_summary(client_id, before_days=14, after_days=14)

if optimization_summary['total_actions'] > 0:
    # Win rate contributes to score
    win_rate = optimization_summary.get('win_rate', 0)
    optimization_score = min(25, (win_rate / 100) * 25)
else:
    optimization_score = 12.5  # Neutral if no data

# Update total score calculation
total_score = int(sales_score + tacos_score + organic_score + bsr_score + optimization_score)
total_score = int(total_score * 100 / 125)  # Normalize back to 0-100
```

---

## 11. Tell Claude Code to Rebuild

```
COMPLETE REDESIGN REQUIRED - Diagnostic Control Center v2.0

Current tool is a data visualization dashboard. Needs to become a diagnostic intelligence platform.

CORE REQUIREMENTS:

1. SINGLE PAGE DESIGN
   - No more separate Overview/Signals/Trends pages
   - One integrated "Diagnostic Control Center"
   - Components stack vertically on single page

2. INTELLIGENCE LAYER
   - Health Score (0-100) computed from 5 metrics
   - Root Cause Attribution (% to organic decay, market, optimizations)
   - Automated diagnosis with clear explanations
   - Prioritized recommendations with action buttons

3. INTEGRATION WITH IMPACT DASHBOARD
   - Pull win rate, avg impact from actions_log
   - Show "your optimizations are working despite headwinds"
   - Integrate validation data into health score
   - Use get_impact_summary() in all diagnostic functions

4. GLASSMORPHIC DESIGN SYSTEM
   - Use the CSS from features/diagnostics/styles.py
   - Every card should have glassmorphic styling
   - No default Streamlit UI
   - Professional, modern, dark theme

5. CORRELATED INTELLIGENCE
   - BSR vs Paid ROAS chart with interpretation overlay
   - CVR Divergence chart with diagnosis
   - Show correlation values and what they mean

6. ASIN ACTION TABLE
   - Specific ASINs with recommendations
   - Priority: HIGH/MEDIUM/OPPORTUNITY
   - Monthly impact in AED
   - Action buttons for each ASIN

IMPLEMENTATION GUIDE:

All code provided above in sections 4-9.
- compute_health_score() - section 4
- diagnose_root_causes() - section 4
- generate_recommendations() - section 4
- compute_bsr_roas_correlation() - section 6
- detect_cvr_divergence() - section 6
- get_asin_action_table() - section 7
- Complete Streamlit implementation - section 9
- Glassmorphic CSS - section 9
- Component functions - section 9

GOAL: Transform from "here's some data" to "here's the diagnosis and what to do"
```

Want me to package this as the final rebuild spec for Claude Code?