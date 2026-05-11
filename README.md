# Supply Chain Analytics: Supplier Performance & Inventory Risk

A portfolio data analytics project demonstrating end-to-end analysis of supplier
performance and inventory risk across 1,200 purchase orders, 15 suppliers, and 50 SKUs
spanning 2022–2024.

---

## Project Summary

| KPI | Value |
|-----|-------|
| Total Purchase Orders | 1,200 |
| Overall On-Time Rate | 82.6% |
| Avg Delay (Late Orders) | 7.4 days |
| Total Spend Analyzed | $275M |
| Spend at Risk (late orders) | $48.6M (17.7%) |
| SKUs at Critical Stockout Risk | 10 |
| SKUs at High Risk | 8 |

**Key finding:** Mechanical and Raw Materials categories show the lowest on-time
rates (~78%), driven largely by three Tier 3/4 suppliers. Addressing Omega Components
and BlueStar Components alone could recover ~$9M in at-risk spend.

---

## File Structure

```
supply-chain-analytics/
├── README.md
├── data/
│   ├── generate_data.py        # Reproducible synthetic dataset generation
│   ├── suppliers.csv           # 15 supplier records
│   ├── purchase_orders.csv     # 1,200 order transactions
│   └── inventory.csv           # 50 SKU inventory positions
├── sql/
│   └── supply_chain_analysis.sql   # 7 SQL queries
├── notebooks/
│   └── supply_chain_analysis.py    # Full Python analysis
├── dashboard/
│   └── index.html              # Interactive browser dashboard
└── outputs/
    ├── fig1_supplier_scorecard.png
    ├── fig2_monthly_delivery_trend.png
    ├── fig3_delay_by_region.png
    ├── fig4_inventory_risk_heatmap.png
    └── fig5_quality_vs_reliability.png
```

---

## How to Run

### Python Analysis

```bash
# 1. Install dependencies
pip install pandas numpy matplotlib seaborn

# 2. Generate the dataset
python data/generate_data.py

# 3. Run the full analysis (produces 5 charts in /outputs/)
python notebooks/supply_chain_analysis.py
```

### SQL Analysis

The SQL file is written for **SQLite** with PostgreSQL dialect notes inline.

```bash
# Run in SQLite CLI after importing CSVs, or use a tool like DBeaver / DB Browser
sqlite3 supply_chain.db < sql/supply_chain_analysis.sql
```

### Dashboard

Open `dashboard/index.html` in any modern browser — no server required.

---

## SQL Highlights

The SQL file contains 7 queries:

1. **Supplier Performance Scorecard** — multi-table JOIN + composite weighted score
2. **Monthly Delivery Trend** — `STRFTIME` grouping, running aggregates
3. **Inventory Risk Dashboard** — coverage gap model (`days_of_supply - lead_time_days`)
4. **Spend Analysis** — `SUM() OVER()` running total window function
5. **Late Delivery Root Cause** — 3-CTE chain isolating worst supplier-category pairs
6. **Supplier Tier Segmentation** — `CASE WHEN` threshold classification
7. **Schema Setup** — normalized table definitions with FK relationships

---

## Methodology

### Supplier Performance Score (0–100)
A composite metric weighted across three dimensions:

| Dimension | Weight | Rationale |
|-----------|--------|-----------|
| On-time delivery rate | 50% | Primary driver of downstream disruption |
| Defect / quality rate | 30% | Rework cost and customer impact |
| Average delay speed | 20% | Urgency of recovery when late |

### Inventory Risk Levels
Stockout risk is determined by the **coverage gap**:

```
Coverage Gap = Days of Supply − Supplier Lead Time
```

| Level | Coverage Gap | Action |
|-------|-------------|--------|
| Critical | < 0 days | Expedite order immediately |
| High | 0–7 days | Place reorder today |
| Medium | 8–14 days | Monitor daily |
| Low | > 14 days | Standard reorder cycle |

---

## Tools & Technologies

- **Python 3.10+** — pandas, numpy, matplotlib, seaborn, sqlite3
- **SQL** — SQLite (compatible with PostgreSQL/MySQL with minor edits)
- **HTML/CSS/JavaScript** — Chart.js 4.4 for interactive dashboard
- **Excel-compatible** — all CSVs open directly in Excel for pivot table analysis

---

*Dataset is fully synthetic and generated with a fixed random seed for reproducibility.*
