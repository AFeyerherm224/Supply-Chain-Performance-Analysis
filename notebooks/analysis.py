#!/usr/bin/env python

# # Supply Chain Analytics: Supplier Performance & Inventory Risk
# **Project Overview**
# Analyzed 1,200 purchase orders across 15 suppliers (2022–2024) to:
# - Score and rank supplier reliability
# - Identify delivery delay patterns by region and category
# - Flag inventory stockout risk using a coverage gap model
# - Quantify the cost impact of late deliveries
#
# **Tools:** Python (pandas, matplotlib, seaborn), SQL (SQLite), Excel
# **Skills demonstrated:** Data cleaning, EDA, window functions, KPI design, visualization

# ---------------------------------------------------------------
# 0. SETUP
# ---------------------------------------------------------------
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import sqlite3
import warnings
import os

warnings.filterwarnings('ignore')

# Plot style
sns.set_theme(style='whitegrid', palette='muted', font='DejaVu Sans')
plt.rcParams.update({
    'figure.dpi': 120,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.titleweight': 'bold',
    'axes.titlesize': 13,
    'figure.facecolor': '#FAFAFA'
})

DATA_DIR = 'data'
OUTPUT_DIR = 'outputs'
os.makedirs(OUTPUT_DIR, exist_ok=True)
print("Environment ready.")


# ---------------------------------------------------------------
# 1. DATA LOADING & CLEANING
# ---------------------------------------------------------------
print("\n--- 1. Loading data ---")

suppliers = pd.read_csv(f'{DATA_DIR}/suppliers.csv', parse_dates=['contract_start'])
orders    = pd.read_csv(f'{DATA_DIR}/purchase_orders.csv', parse_dates=['order_date'])
inventory = pd.read_csv(f'{DATA_DIR}/inventory.csv')

# ── Data quality checks ──────────────────────────────────────
print(f"  orders shape:    {orders.shape}")
print(f"  suppliers shape: {suppliers.shape}")
print(f"  inventory shape: {inventory.shape}")

print("\n  Missing values (orders):")
print(orders.isnull().sum()[orders.isnull().sum() > 0].to_string() or "  None")

# ── Clean & enrich orders ─────────────────────────────────────
orders['year_month'] = orders['order_date'].dt.to_period('M')
orders['year']       = orders['order_date'].dt.year
orders['quarter']    = orders['order_date'].dt.to_period('Q')
orders['is_late']    = (orders['status'] == 'Late').astype(int)

# Merge supplier metadata
orders = orders.merge(
    suppliers[['supplier_id', 'supplier_name', 'region']],
    on='supplier_id', how='left'
)

# ── Outlier flag: extreme delays ──────────────────────────────
delay_q99 = orders['delay_days'].quantile(0.99)
orders['delay_outlier'] = orders['delay_days'] > delay_q99
print(f"\n  Delay 99th pct: {delay_q99:.0f} days | "
      f"Outliers flagged: {orders['delay_outlier'].sum()}")

print("\n  Dtypes (orders):")
print(orders[['order_date', 'total_cost', 'delay_days', 'is_late']].dtypes.to_string())


# ---------------------------------------------------------------
# 2. EXPLORATORY DATA ANALYSIS
# ---------------------------------------------------------------
print("\n--- 2. EDA ---")

# ── Summary stats ─────────────────────────────────────────────
print("\n  Order value summary ($):")
print(orders['total_cost'].describe().round(2).to_string())

late_pct = orders['is_late'].mean() * 100
avg_delay = orders.loc[orders['is_late']==1, 'delay_days'].mean()
total_spend = orders['total_cost'].sum()
print(f"\n  Overall late rate:   {late_pct:.1f}%")
print(f"  Avg delay (late):    {avg_delay:.1f} days")
print(f"  Total spend:         ${total_spend:,.0f}")

# ── On-time rate by category ──────────────────────────────────
cat_perf = (orders.groupby('category')
            .agg(orders=('order_id','count'),
                 on_time=('is_late', lambda x: (x==0).sum()),
                 avg_delay=('delay_days','mean'),
                 total_spend=('total_cost','sum'))
            .assign(on_time_pct=lambda df: df['on_time']/df['orders']*100)
            .round(2)
            .sort_values('on_time_pct', ascending=False))

print("\n  On-time rate by category:")
print(cat_perf[['orders', 'on_time_pct', 'avg_delay', 'total_spend']].to_string())


# ---------------------------------------------------------------
# 3. SUPPLIER PERFORMANCE SCORECARD (Python-side)
# ---------------------------------------------------------------
print("\n--- 3. Supplier scorecard ---")

sup_score = (orders.groupby(['supplier_id', 'supplier_name', 'region'])
             .agg(
                 total_orders   = ('order_id',    'count'),
                 on_time_orders = ('is_late',     lambda x: (x==0).sum()),
                 avg_delay      = ('delay_days',  'mean'),
                 total_defects  = ('defects_reported', 'sum'),
                 total_units    = ('quantity_ordered',  'sum'),
                 total_spend    = ('total_cost',  'sum')
             ).reset_index())

sup_score['on_time_pct']   = (sup_score['on_time_orders'] / sup_score['total_orders'] * 100).round(1)
sup_score['defect_rate']   = (sup_score['total_defects'] / sup_score['total_units'] * 100).round(3)

# Composite score (0–100)
sup_score['score'] = (
    sup_score['on_time_pct'] * 0.50 +
    (1 - sup_score['defect_rate'] / 100) * 100 * 0.30 +
    np.clip(20 - sup_score['avg_delay'] * 2, 0, 20) * 0.20
).round(1)

sup_score['tier'] = pd.cut(
    sup_score['score'],
    bins=[0, 65, 75, 85, 100],
    labels=['Tier 4 – At Risk', 'Tier 3 – Conditional', 'Tier 2 – Approved', 'Tier 1 – Preferred']
)

print(sup_score[['supplier_name', 'on_time_pct', 'defect_rate', 'avg_delay', 'score', 'tier']]
      .sort_values('score', ascending=False).to_string(index=False))


# ---------------------------------------------------------------
# 4. SQL ANALYSIS VIA SQLITE (in-memory)
# ---------------------------------------------------------------
print("\n--- 4. SQL analysis ---")

conn = sqlite3.connect(':memory:')
orders_sql = orders.copy()
orders_sql['year_month'] = orders_sql['year_month'].astype(str)
orders_sql['quarter']    = orders_sql['quarter'].astype(str)
suppliers.to_sql('suppliers',       conn, index=False, if_exists='replace')
orders_sql.to_sql('purchase_orders', conn, index=False, if_exists='replace')
inventory.to_sql('inventory',       conn, index=False, if_exists='replace')

# Monthly trend via SQL
monthly_sql = """
    SELECT
        STRFTIME('%Y-%m', order_date)                        AS month,
        COUNT(*)                                             AS total_orders,
        ROUND(AVG(CASE WHEN is_late = 0 THEN 100.0 ELSE 0 END), 1) AS on_time_pct,
        ROUND(AVG(delay_days), 2)                           AS avg_delay,
        ROUND(SUM(total_cost)/1000.0, 1)                   AS spend_k
    FROM purchase_orders
    GROUP BY month
    ORDER BY month
"""
monthly = pd.read_sql(monthly_sql, conn)
monthly['month_dt'] = pd.to_datetime(monthly['month'])
print(f"\n  Monthly trend rows: {len(monthly)}")
print(monthly.tail(6).to_string(index=False))

# Inventory risk via SQL
risk_sql = """
    SELECT
        i.sku, i.product_name, s.supplier_name,
        i.current_stock, i.reorder_point,
        i.days_of_supply, i.lead_time_days, i.risk_level,
        ROUND(i.days_of_supply - i.lead_time_days, 1) AS coverage_gap,
        i.stockout_count_ytd
    FROM inventory i
    JOIN suppliers s ON i.supplier_id = s.supplier_id
    ORDER BY
        CASE i.risk_level WHEN 'Critical' THEN 1 WHEN 'High' THEN 2
                          WHEN 'Medium' THEN 3 ELSE 4 END,
        coverage_gap ASC
"""
inv_risk = pd.read_sql(risk_sql, conn)
print(f"\n  Inventory items at Critical/High risk:")
print(inv_risk[inv_risk['risk_level'].isin(['Critical','High'])]
      [['product_name','supplier_name','days_of_supply','lead_time_days','coverage_gap','risk_level']]
      .head(10).to_string(index=False))
conn.close()


# ---------------------------------------------------------------
# 5. VISUALIZATIONS
# ---------------------------------------------------------------
print("\n--- 5. Generating visualizations ---")

COLORS = {
    'primary':   '#1D4E89',
    'accent':    '#E84855',
    'ok':        '#2D936C',
    'warn':      '#F4A261',
    'neutral':   '#8D99AE',
    'light':     '#EDF2F4',
}

# ── FIG 1: Supplier Scorecard (horizontal bar) ────────────────
fig, ax = plt.subplots(figsize=(10, 6))
plot_df = sup_score.sort_values('score')
bar_colors = plot_df['tier'].map({
    'Tier 1 – Preferred':   COLORS['ok'],
    'Tier 2 – Approved':    COLORS['primary'],
    'Tier 3 – Conditional': COLORS['warn'],
    'Tier 4 – At Risk':     COLORS['accent'],
})
bars = ax.barh(plot_df['supplier_name'], plot_df['score'],
               color=bar_colors, edgecolor='white', linewidth=0.5)
ax.axvline(85, color=COLORS['ok'],      linestyle='--', alpha=0.6, label='Tier 1 threshold (85)')
ax.axvline(75, color=COLORS['primary'], linestyle='--', alpha=0.6, label='Tier 2 threshold (75)')
ax.axvline(65, color=COLORS['warn'],    linestyle='--', alpha=0.6, label='Tier 3 threshold (65)')
for bar, score in zip(bars, plot_df['score']):
    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
            f'{score:.0f}', va='center', fontsize=9, color='#333')
ax.set_xlabel('Composite Performance Score (0–100)')
ax.set_title('Supplier Performance Scorecard\n(Weighted: 50% on-time, 30% quality, 20% speed)')
ax.legend(loc='lower right', fontsize=8)
ax.set_xlim(0, 105)
plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/fig1_supplier_scorecard.png', dpi=140, bbox_inches='tight')
plt.close()
print("  Saved: fig1_supplier_scorecard.png")

# ── FIG 2: Monthly On-Time Rate + Spend ───────────────────────
fig, ax1 = plt.subplots(figsize=(12, 4.5))
ax2 = ax1.twinx()
ax2.bar(monthly['month_dt'], monthly['spend_k'],
        color=COLORS['light'], alpha=0.8, label='Spend ($k)', zorder=1)
ax1.plot(monthly['month_dt'], monthly['on_time_pct'],
         color=COLORS['primary'], linewidth=2.2, marker='o', markersize=4,
         label='On-Time %', zorder=2)
ax1.axhline(80, color=COLORS['accent'], linestyle='--', linewidth=1, alpha=0.7, label='Target (80%)')
# 3-month rolling avg
rolling = monthly['on_time_pct'].rolling(3, center=True).mean()
ax1.plot(monthly['month_dt'], rolling,
         color=COLORS['ok'], linewidth=1.5, linestyle='-.', label='3-Mo Rolling Avg')
ax1.set_ylabel('On-Time Delivery Rate (%)')
ax1.set_ylim(60, 105)
ax2.set_ylabel('Total Spend ($k)', color=COLORS['neutral'])
ax1.set_title('Monthly On-Time Delivery Rate vs. Spend (2022–2024)')
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='lower left', fontsize=8)
ax1.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%b %y'))
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/fig2_monthly_delivery_trend.png', dpi=140, bbox_inches='tight')
plt.close()
print("  Saved: fig2_monthly_delivery_trend.png")

# ── FIG 3: Delay Distribution by Region (boxplot) ────────────
fig, ax = plt.subplots(figsize=(9, 5))
late_only = orders[orders['delay_days'] > 0]
region_order = (late_only.groupby('region')['delay_days']
                .median().sort_values(ascending=False).index.tolist())
sns.boxplot(data=late_only, x='region', y='delay_days',
            order=region_order, palette='Blues_d', ax=ax,
            flierprops=dict(marker='o', markerfacecolor=COLORS['accent'],
                            markersize=4, alpha=0.4))
ax.set_title('Delay Distribution by Supplier Region (Late Orders Only)')
ax.set_xlabel('Region')
ax.set_ylabel('Delay Days')
ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/fig3_delay_by_region.png', dpi=140, bbox_inches='tight')
plt.close()
print("  Saved: fig3_delay_by_region.png")

# ── FIG 4: Inventory Risk Heatmap ─────────────────────────────
fig, ax = plt.subplots(figsize=(10, 6))
risk_pivot = (inv_risk.groupby(['risk_level', 'supplier_name'])
              .size().unstack(fill_value=0))
risk_order = [r for r in ['Critical','High','Medium','Low'] if r in risk_pivot.index]
risk_pivot = risk_pivot.loc[risk_order]
sns.heatmap(risk_pivot, cmap='YlOrRd', linewidths=0.5,
            linecolor='white', annot=True, fmt='d',
            ax=ax, cbar_kws={'label': 'SKU Count'})
ax.set_title('Inventory Risk by Level & Supplier\n(Number of SKUs per cell)')
ax.set_xlabel('Supplier')
ax.set_ylabel('Risk Level')
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/fig4_inventory_risk_heatmap.png', dpi=140, bbox_inches='tight')
plt.close()
print("  Saved: fig4_inventory_risk_heatmap.png")

# ── FIG 5: Spend vs On-Time Rate (bubble chart) ───────────────
fig, ax = plt.subplots(figsize=(9, 6))
bubble_df = sup_score.copy()
scatter = ax.scatter(
    bubble_df['on_time_pct'],
    bubble_df['defect_rate'],
    s=bubble_df['total_spend'] / bubble_df['total_spend'].max() * 1200 + 80,
    c=bubble_df['score'],
    cmap='RdYlGn', alpha=0.75, edgecolors='white', linewidth=1.2,
    vmin=60, vmax=95
)
for _, row in bubble_df.iterrows():
    ax.annotate(row['supplier_name'].split()[0],
                (row['on_time_pct'], row['defect_rate']),
                fontsize=7.5, ha='center', va='bottom',
                xytext=(0, 7), textcoords='offset points', color='#333')
plt.colorbar(scatter, ax=ax, label='Performance Score')
ax.axvline(80, color='gray', linestyle='--', alpha=0.5, linewidth=1)
ax.set_xlabel('On-Time Delivery Rate (%)')
ax.set_ylabel('Defect Rate (%)')
ax.set_title('Supplier Quality vs. Reliability\n(Bubble size = total spend)')
ax.text(80.5, ax.get_ylim()[1]*0.97, 'Target →', fontsize=8, color='gray')
plt.tight_layout()
plt.savefig(f'{OUTPUT_DIR}/fig5_quality_vs_reliability.png', dpi=140, bbox_inches='tight')
plt.close()
print("  Saved: fig5_quality_vs_reliability.png")


# ---------------------------------------------------------------
# 6. KEY FINDINGS & KPI SUMMARY
# ---------------------------------------------------------------
print("\n--- 6. Key Findings ---")

critical_skus = (inv_risk['risk_level'] == 'Critical').sum()
high_skus     = (inv_risk['risk_level'] == 'High').sum()
worst_sup     = sup_score.loc[sup_score['score'].idxmin(), 'supplier_name']
best_sup      = sup_score.loc[sup_score['score'].idxmax(), 'supplier_name']
late_spend    = orders.loc[orders['is_late']==1, 'total_cost'].sum()

findings = {
    "Total Orders Analyzed":         f"{len(orders):,}",
    "Overall On-Time Rate":           f"{(1 - orders['is_late'].mean())*100:.1f}%",
    "Avg Delay (Late Orders)":        f"{avg_delay:.1f} days",
    "Total Spend":                    f"${total_spend:,.0f}",
    "Spend Affected by Late Orders":  f"${late_spend:,.0f} ({late_spend/total_spend*100:.1f}%)",
    "SKUs at Critical Risk":          str(critical_skus),
    "SKUs at High Risk":              str(high_skus),
    "Top Supplier":                   best_sup,
    "Lowest-Performing Supplier":     worst_sup,
}

print()
for k, v in findings.items():
    print(f"  {k:<35} {v}")

print(f"\n✅ Outputs saved to /{OUTPUT_DIR}/")