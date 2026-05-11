-- ============================================================
-- Supply Chain Analytics: SQL Analysis Scripts
-- Author: Aidan Feyerherm
-- Description: Supplier performance, delivery reliability,
--              and inventory risk analysis using SQL.
-- Tools: SQLite / PostgreSQL compatible (minor dialect notes inline)
-- ============================================================

-- ============================================================
-- SECTION 1: DATABASE SETUP
-- ============================================================

CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id             TEXT PRIMARY KEY,
    supplier_name           TEXT,
    region                  TEXT,
    category                TEXT,
    contract_start          DATE,
    on_time_delivery_rate   REAL,
    defect_rate             REAL,
    avg_lead_time_days      INTEGER,
    active                  BOOLEAN
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    order_id                TEXT PRIMARY KEY,
    supplier_id             TEXT REFERENCES suppliers(supplier_id),
    order_date              DATE,
    promised_delivery_days  INTEGER,
    actual_delivery_days    INTEGER,
    quantity_ordered        INTEGER,
    unit_cost               REAL,
    category                TEXT,
    status                  TEXT,
    defects_reported        INTEGER,
    total_cost              REAL,
    delay_days              INTEGER
);

CREATE TABLE IF NOT EXISTS inventory (
    sku                     TEXT PRIMARY KEY,
    product_name            TEXT,
    supplier_id             TEXT REFERENCES suppliers(supplier_id),
    current_stock           INTEGER,
    reorder_point           INTEGER,
    max_stock               INTEGER,
    avg_daily_demand        REAL,
    holding_cost_per_unit   REAL,
    stockout_count_ytd      INTEGER,
    lead_time_days          INTEGER,
    days_of_supply          REAL,
    risk_level              TEXT
);


-- ============================================================
-- SECTION 2: SUPPLIER PERFORMANCE SCORECARD
-- Ranks suppliers by a composite score across delivery,
-- quality, and cost efficiency.
-- ============================================================

WITH supplier_metrics AS (
    SELECT
        s.supplier_id,
        s.supplier_name,
        s.region,
        s.category,
        COUNT(po.order_id)                                      AS total_orders,
        ROUND(AVG(po.delay_days), 1)                            AS avg_delay_days,
        ROUND(
            SUM(CASE WHEN po.status = 'On Time' THEN 1 ELSE 0 END) * 100.0
            / COUNT(po.order_id), 1
        )                                                        AS actual_on_time_pct,
        ROUND(SUM(po.defects_reported) * 100.0
            / NULLIF(SUM(po.quantity_ordered), 0), 2)           AS defect_rate_pct,
        ROUND(SUM(po.total_cost) / 1000.0, 1)                  AS total_spend_k,
        ROUND(AVG(po.unit_cost), 2)                             AS avg_unit_cost
    FROM suppliers s
    JOIN purchase_orders po ON s.supplier_id = po.supplier_id
    WHERE s.active = TRUE
    GROUP BY s.supplier_id, s.supplier_name, s.region, s.category
),
scored AS (
    SELECT *,
        -- Composite score: higher = better supplier
        ROUND(
            (actual_on_time_pct * 0.5)
            + ((1 - defect_rate_pct / 100.0) * 100 * 0.3)
            + (CASE WHEN avg_delay_days = 0 THEN 20
                    WHEN avg_delay_days <= 2 THEN 15
                    WHEN avg_delay_days <= 5 THEN 8
                    ELSE 0 END) * 0.2
        , 1) AS performance_score
    FROM supplier_metrics
)
SELECT
    RANK() OVER (ORDER BY performance_score DESC) AS rank,
    supplier_name,
    region,
    category,
    total_orders,
    actual_on_time_pct      AS on_time_pct,
    avg_delay_days,
    defect_rate_pct,
    total_spend_k           AS spend_k,
    performance_score
FROM scored
ORDER BY performance_score DESC;


-- ============================================================
-- SECTION 3: MONTHLY DELIVERY TREND ANALYSIS
-- Tracks on-time delivery rate and average delay over time.
-- Useful for identifying seasonal patterns or degradation.
-- ============================================================

SELECT
    STRFTIME('%Y-%m', order_date)                               AS month,         -- SQLite
    -- TO_CHAR(order_date, 'YYYY-MM')                           AS month,         -- PostgreSQL
    COUNT(*)                                                    AS total_orders,
    SUM(CASE WHEN status = 'On Time' THEN 1 ELSE 0 END)        AS on_time_count,
    ROUND(
        SUM(CASE WHEN status = 'On Time' THEN 1 ELSE 0 END) * 100.0
        / COUNT(*), 1
    )                                                           AS on_time_pct,
    ROUND(AVG(delay_days), 1)                                   AS avg_delay_days,
    ROUND(SUM(total_cost) / 1000.0, 1)                         AS total_spend_k
FROM purchase_orders
GROUP BY STRFTIME('%Y-%m', order_date)
ORDER BY month;


-- ============================================================
-- SECTION 4: INVENTORY RISK DASHBOARD QUERY
-- Identifies items at risk of stockout based on days of supply
-- relative to supplier lead time.
-- ============================================================

SELECT
    i.sku,
    i.product_name,
    s.supplier_name,
    s.region,
    i.current_stock,
    i.reorder_point,
    i.avg_daily_demand,
    i.days_of_supply,
    i.lead_time_days,
    i.stockout_count_ytd,
    i.risk_level,
    -- Coverage gap: negative = we'll run out before restocking
    ROUND(i.days_of_supply - i.lead_time_days, 1)              AS coverage_gap_days,
    -- Estimated holding cost per month
    ROUND(i.current_stock * i.holding_cost_per_unit * 30, 2)   AS monthly_holding_cost
FROM inventory i
JOIN suppliers s ON i.supplier_id = s.supplier_id
WHERE i.risk_level IN ('Critical', 'High')
ORDER BY
    CASE i.risk_level WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 ELSE 3 END,
    coverage_gap_days ASC;


-- ============================================================
-- SECTION 5: SPEND ANALYSIS BY CATEGORY (WITH WINDOW FUNCTIONS)
-- Shows each category's share of total spend and running total.
-- ============================================================

WITH category_spend AS (
    SELECT
        category,
        COUNT(DISTINCT supplier_id)             AS supplier_count,
        COUNT(order_id)                         AS order_count,
        ROUND(SUM(total_cost), 2)               AS total_spend,
        ROUND(AVG(unit_cost), 2)                AS avg_unit_cost,
        ROUND(AVG(delay_days), 1)               AS avg_delay_days
    FROM purchase_orders
    GROUP BY category
)
SELECT
    category,
    supplier_count,
    order_count,
    total_spend,
    avg_unit_cost,
    avg_delay_days,
    ROUND(total_spend * 100.0 / SUM(total_spend) OVER (), 1)   AS pct_of_total_spend,
    ROUND(SUM(total_spend) OVER (
        ORDER BY total_spend DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ), 2)                                                        AS running_total_spend
FROM category_spend
ORDER BY total_spend DESC;


-- ============================================================
-- SECTION 6: LATE DELIVERY ROOT CAUSE ANALYSIS
-- Uses a CTE chain to isolate worst-performing supplier-category
-- combinations and quantify the business impact.
-- ============================================================

WITH late_orders AS (
    SELECT *
    FROM purchase_orders
    WHERE status = 'Late'
),
impact AS (
    SELECT
        supplier_id,
        category,
        COUNT(*)                                                AS late_order_count,
        ROUND(AVG(delay_days), 1)                              AS avg_delay_days,
        MAX(delay_days)                                         AS max_delay_days,
        ROUND(SUM(total_cost), 2)                              AS affected_spend,
        SUM(quantity_ordered)                                   AS affected_units
    FROM late_orders
    GROUP BY supplier_id, category
),
ranked AS (
    SELECT
        i.*,
        s.supplier_name,
        s.region,
        RANK() OVER (PARTITION BY i.category ORDER BY i.late_order_count DESC) AS rank_in_category
    FROM impact i
    JOIN suppliers s ON i.supplier_id = s.supplier_id
)
SELECT
    supplier_name,
    region,
    category,
    late_order_count,
    avg_delay_days,
    max_delay_days,
    affected_spend,
    affected_units,
    rank_in_category
FROM ranked
WHERE rank_in_category <= 3
ORDER BY category, rank_in_category;


-- ============================================================
-- SECTION 7: SUPPLIER RELIABILITY SEGMENTATION
-- Classifies suppliers into tiers using performance thresholds.
-- Useful for contract negotiation and vendor management.
-- ============================================================

WITH perf AS (
    SELECT
        s.supplier_id,
        s.supplier_name,
        s.category,
        s.region,
        ROUND(
            SUM(CASE WHEN po.status = 'On Time' THEN 1 ELSE 0 END) * 100.0
            / COUNT(po.order_id), 1
        )                               AS on_time_pct,
        ROUND(AVG(po.delay_days), 1)   AS avg_delay,
        COUNT(po.order_id)              AS orders
    FROM suppliers s
    JOIN purchase_orders po ON s.supplier_id = po.supplier_id
    WHERE s.active = TRUE
    GROUP BY s.supplier_id, s.supplier_name, s.category, s.region
)
SELECT
    supplier_name,
    category,
    region,
    on_time_pct,
    avg_delay,
    orders,
    CASE
        WHEN on_time_pct >= 90 AND avg_delay <= 1 THEN 'Tier 1 – Preferred'
        WHEN on_time_pct >= 80 AND avg_delay <= 3 THEN 'Tier 2 – Approved'
        WHEN on_time_pct >= 70                    THEN 'Tier 3 – Conditional'
        ELSE                                           'Tier 4 – At Risk'
    END AS supplier_tier,
    CASE
        WHEN on_time_pct >= 90 AND avg_delay <= 1 THEN 'Renew / expand contract'
        WHEN on_time_pct >= 80 AND avg_delay <= 3 THEN 'Monitor quarterly'
        WHEN on_time_pct >= 70                    THEN 'Issue improvement plan'
        ELSE                                           'Review / consider replacing'
    END AS recommended_action
FROM perf
ORDER BY on_time_pct DESC;