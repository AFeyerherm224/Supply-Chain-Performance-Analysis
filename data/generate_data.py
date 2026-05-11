import pandas as pd
import numpy as np
import os

np.random.seed(42)

# --- Suppliers ---
suppliers = pd.DataFrame({
    'supplier_id': [f'SUP{str(i).zfill(3)}' for i in range(1, 16)],
    'supplier_name': [
        'Apex Materials', 'BlueStar Components', 'CoreTech Supply',
        'Delta Logistics', 'EastBridge Mfg', 'Forte Industries',
        'Global Parts Co', 'Horizon Metals', 'IronPath Supplies',
        'JetStream Corp', 'Keystone Goods', 'LightSpeed Parts',
        'Meridian Supply', 'NorthStar Mfg', 'Omega Components'
    ],
    'region': [
        'Southeast', 'Midwest', 'West', 'Northeast', 'West',
        'Southeast', 'Midwest', 'South', 'Northeast', 'West',
        'Midwest', 'Southeast', 'South', 'Northeast', 'West'
    ],
    'category': [
        'Raw Materials', 'Electronics', 'Packaging', 'Logistics', 'Mechanical',
        'Raw Materials', 'Electronics', 'Metals', 'Packaging', 'Electronics',
        'Mechanical', 'Electronics', 'Logistics', 'Mechanical', 'Raw Materials'
    ],
    'contract_start': pd.date_range('2021-01-01', periods=15, freq='60D'),
    'on_time_delivery_rate': np.round(np.clip(np.random.normal(0.82, 0.10, 15), 0.55, 0.99), 2),
    'defect_rate': np.round(np.clip(np.random.normal(0.04, 0.02, 15), 0.005, 0.12), 3),
    'avg_lead_time_days': np.random.randint(5, 28, 15),
    'active': [True]*13 + [False, True]
})
suppliers.to_csv('/home/claude/supply-chain-analytics/data/suppliers.csv', index=False)

# --- Purchase Orders ---
n_orders = 1200
order_dates = pd.date_range('2022-01-01', '2024-12-31', periods=n_orders)
supplier_ids = np.random.choice(suppliers['supplier_id'], n_orders, p=None)

# Map supplier lead times
lead_map = dict(zip(suppliers['supplier_id'], suppliers['avg_lead_time_days']))
ontime_map = dict(zip(suppliers['supplier_id'], suppliers['on_time_delivery_rate']))

promised_days = np.array([lead_map[s] for s in supplier_ids])
is_late = np.array([np.random.rand() > ontime_map[s] for s in supplier_ids])
actual_days = promised_days + np.where(is_late, np.random.randint(1, 15, n_orders), np.random.randint(-2, 3, n_orders))
actual_days = np.clip(actual_days, 1, None)

orders = pd.DataFrame({
    'order_id': [f'PO{str(i).zfill(5)}' for i in range(1, n_orders+1)],
    'supplier_id': supplier_ids,
    'order_date': order_dates.date,
    'promised_delivery_days': promised_days,
    'actual_delivery_days': actual_days,
    'quantity_ordered': np.random.randint(50, 2000, n_orders),
    'unit_cost': np.round(np.random.uniform(2.5, 450.0, n_orders), 2),
    'category': [suppliers.loc[suppliers['supplier_id']==s, 'category'].values[0] for s in supplier_ids],
    'status': np.where(is_late, 'Late', 'On Time'),
    'defects_reported': np.random.randint(0, 20, n_orders)
})
orders['total_cost'] = np.round(orders['quantity_ordered'] * orders['unit_cost'], 2)
orders['delay_days'] = np.maximum(0, orders['actual_delivery_days'] - orders['promised_delivery_days'])
orders.to_csv('/home/claude/supply-chain-analytics/data/purchase_orders.csv', index=False)

# --- Inventory ---
products = [f'SKU{str(i).zfill(4)}' for i in range(1, 51)]
inventory = pd.DataFrame({
    'sku': products,
    'product_name': [f'Product {chr(65 + i%26)}{i//26 + 1}' for i in range(50)],
    'supplier_id': np.random.choice(suppliers['supplier_id'], 50),
    'current_stock': np.random.randint(0, 1500, 50),
    'reorder_point': np.random.randint(100, 400, 50),
    'max_stock': np.random.randint(800, 3000, 50),
    'avg_daily_demand': np.round(np.random.uniform(5, 80, 50), 1),
    'holding_cost_per_unit': np.round(np.random.uniform(0.5, 8.0, 50), 2),
    'stockout_count_ytd': np.random.randint(0, 12, 50),
    'lead_time_days': np.random.randint(5, 30, 50)
})
inventory['days_of_supply'] = np.round(inventory['current_stock'] / inventory['avg_daily_demand'], 1)
inventory['risk_level'] = pd.cut(
    inventory['days_of_supply'],
    bins=[-1, 7, 14, 30, 999],
    labels=['Critical', 'High', 'Medium', 'Low']
)
inventory.to_csv('/home/claude/supply-chain-analytics/data/inventory.csv', index=False)

print("✅ Data generated successfully")
print(f"  suppliers.csv     → {len(suppliers)} rows")
print(f"  purchase_orders.csv → {len(orders)} rows")
print(f"  inventory.csv     → {len(inventory)} rows")