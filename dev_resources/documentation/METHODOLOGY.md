# Saddl - Methodology & Calculation Logic

**Version:** 3.0  
**Last Updated:** January 18, 2026

This document is the **single source of truth** for the mathematical models, statistical thresholds, and logical reasoning behind the Saddl optimization engine and dashboard metrics.

---

## 1. Executive Dashboard Metrics

### 1.1 Efficiency Index ("Where The Money Is")

Measures whether a match type or segment is generating revenue efficiently relative to its spend consumption.

**Formula**:
$$ \text{Efficiency Ratio} = \frac{\text{Share of Revenue } \%}{\text{Share of Spend } \%} $$

**Classification Thresholds**:
| Status | Threshold | Color | Meaning |
|--------|-----------|-------|---------|
| **Amplifier** | Ratio > 1.0 | 🟢 Emerald | Generating more revenue share than it costs in spend. |
| **Balanced** | 0.75 - 1.0 | 🔵 Teal | Performing adequately; spend matches return. |
| **Review** | 0.50 - 0.75 | 🟡 Amber | Underperforming; potential drag on efficiency. |
| **Drag** | < 0.50 | 🔴 Rose | Inefficient; consuming budget with little return. |

### 1.2 Performance Quadrants (Scatter Plot)

Classifies campaigns into four strategic zones based on ROAS and Conversion Rate (CVR).

**Baselines**:
- **Median ROAS**: Median of all active campaigns (Fallback: 3.0x).
- **Median CVR**: Median of all active campaigns (Fallback: 5.0%).

**Quadrants**:
1.  **Stars (High ROAS, High CVR)**: Scale aggressively. (🟢 Emerald)
2.  **Scale Potential (High ROAS, Low CVR)**: Increase traffic; efficiency is high but volume is low. (🟡 Amber)
3.  **Profit Potential (Low ROAS, High CVR)**: Lower bids to improve efficiency; conversion is strong. (🔵 Cyan)
4.  **Cut (Low ROAS, Low CVR)**: Pause or aggressive negative targeting. (🔴 Rose)

### 1.3 Strategic Gauges

#### A. Decision ROI
Return on Investment for the optimizer's actions.
$$ \text{Decision ROI} = \frac{\text{Net Decision Impact (\$)}}{\text{Total Managed Spend (\$)}} \times 100 $$
- **Target**: > 5%

#### B. Spend Efficiency
Percentage of total spend flowing into "efficient" ad groups.
$$ \text{Efficiency Score} = \frac{\text{Spend in Ad Groups with ROAS} \ge 2.0}{\text{Total Spend}} \times 100 $$
- **Target**: > 50%

---

## 2. Decision Impact Engine

Our impact engine separates **Action-Driven Impact** (what you controlled) from **Market-Driven Impact** (what happened anyway).

### 2.1 Impact Formulas by Action Type

Different actions use different logic to calculate "Impact ($)".

| Action Type | Impact Formula | Logic |
| :--- | :--- | :--- |
| **NEGATIVE** | `+Before Spend` | **Cost Avoidance**. We assume the spend would have continued at the same rate but yielded no value (proven waste). |
| **HARVEST** | `+10% × Net Sales Lift` | **Efficiency Gain**. Moving a term to exact match typically yields a 10% efficiency improvement. We attribute this portion of the lift to the decision. |
| **BID CHANGE** | `(Actual Sales) - (Expected Sales)` | **Counterfactual**. "How much did we beat the expected outcome?" (See Section 2.2). |
| **VISIBILITY BOOST** | `(Actual Sales) - (Expected Sales)` | Same as Bid Change. Accounts for incremental sales gained from winning more auctions. |
| **SPEND ELIMINATED** | `(Δ Sales) - (Δ Spend)` | **Net Profit Change**. Applied when a Bid Down or Pause effectively kills spend. Measures pure profit impact (Sales Lost - Spend Saved). |

### 2.2 Counterfactual Impact Logic (Bid Changes)

For bid adjustments, we calculate what **would have happened** if efficiency remained constant at the new spend level.

1.  **Expected Clicks** = `After Spend / Before CPC`
2.  **Expected Sales** = `Expected Clicks × Baseline SPC`
3.  **Decision Impact** = `Actual After Sales - Expected Sales`

**Baseline SPC (Sales Per Click)**:
- Uses **30-Day Rolling Average** SPC to smooth out volatility.
- Fallback: Window-based SPC (Before Sales / Before Clicks) if 30D data is unavailable.

---

## 3. Validation Logic

We only count impact for actions that are **verified** to have been implemented and effective.

### 3.1 Validation Status Definitons (The "Checkmark" System)

| Status | Meaning | Criteria |
| :--- | :--- | :--- |
| **✓ Confirmed blocked** | Negative successfully blocked. | After Spend = $0.00. |
| **✓ Normalized match** | Negative significantly reduced spend. | Target spend dropped ≥50% *more* than the account-wide baseline drop. |
| **✓ Harvested (complete)** | Source term migrated fully. | Source term After Spend = $0.00. |
| **✓ Harvested (90%+ blocked)** | Source term migration near perfect. | Source spend dropped ≥90%. |
| **✓ CPC Validated** | Bid change implemented correctly. | Observed CPC is within ±15% of the suggested bid. |
| **✓ Directional match** | Bid moved in right direction. | CPC changed >5% in the intended direction (Up/Down). |
| **✓ Spend Eliminated** | Bid Down killed waste. | Action was BID_DOWN, but After Spend went to $0. (Impact = Profit Change). |
| **⚠️ NOT IMPLEMENTED** | Action failed or ignored. | Negative added but spend continued; Bid change showed no CPC movement. |

### 3.2 "Spend Eliminated" Logic
If a **Bid Down** results in the target receiving $0 spend (effectively pausing it), we treat it as a **Defensive Win**:
- **Impact Calculation**: `(After Sales - Before Sales) - (After Spend - Before Spend)`
- **Interpretation**: This is "Profit Change". Usually, sales lost is 0, so impact is simply `+Spend Saved`.

---

## 4. Statistical Guardrails (January 2026 Updates)

To prevent "fake" impact from low-data outliers (e.g., 1 click, 1 sale = 60 ROAS), we apply three layers of guardrails.

### 4.1 Low-Sample Exclusions
- **< 5 Clicks (Before)**: Impact is forced to **0**.
- **Reason**: SPC (Sales Per Click) is statistically meaningless with fewer than 5 data points.

### 4.2 ROAS Efficiency Capping
For targets with **medium confidence (5-20 clicks)**, we prevent "lucky streaks" from skewing the baseline.

- **Problem**: A target with 0.50 CPC and 1 lucky sale ($50) has 100 ROAS. If we double the bid, the model wrongly predicts $200 sales.
- **Solution**: We calculate a **ROAS Cap** based on the account's *validated high-confidence targets* (>20 clicks).
- **Formula**: `Cap = Median_ROAS + 1 × StdDev`
- **Application**: If a low-confidence target's implied ROAS > Cap, its baseline SPC is adjusted downwards to match the Cap.

### 4.3 Confidence Weighting (Soft Dampening)
For targets with **5-15 clicks**, we apply a linear weight to the final impact score.

- **Formula**: `Weight = min(1.0, Before_Clicks / 15)`
- **Effect**: A decision based on 7 clicks counts for only 46% of its calculated impact. A decision based on 15+ clicks counts for 100%.
- **Validation Override**: Confirmed Negatives and Harvests always get **100% weight** because their impact (zero spend) is binary and verifiable.
- **Ad Group Fallback Penalty**: If specific target-level data is missing and we rely on Ad Group averages, the confidence weight is penalised by **50%** (multiplied by 0.5) to account for the lower precision.

---

## 5. Time Windows & Maturity

### 5.1 Maturity Calculation
An action is "Mature" only when enough calendar days have passed to capture the full attribution window.

- **Formula**: `Days Passed = Latest_Data_Date - Action_Date + 1`
- **Criterion**: `Days Passed >= 17` (14-day window + 3-day attribution buffer).

### 5.2 Horizon Analysis
We verify impact at three intervals:
1.  **14-Day (Initial)**: Early signal.
2.  **30-Day (Confirmed)**: Attribution fully settled.
3.  **60-Day (Long-Term)**: Retention check.

---

## 6. Definitions & Glossary

| Term | Definition |
| :--- | :--- |
| **Market Drag** | Negative impact caused by a market-wide downturn (e.g., seasonality), not the decision itself. Excluded from totals. |
| **Offensive Win** | Spend Increased + Impact Positive. (Scaling a winner). |
| **Defensive Win** | Spend Decreased + Profit Increased. (Cutting waste or managing a downturn). |
| **Gap Action** | Spend Increased but Efficiency Dropped (Missed expectation). |
| **Capital Protected** | Total `Before Spend` of all confirmed blocked Negative Keywords. |
