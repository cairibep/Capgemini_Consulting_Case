CREATE OR REPLACE VIEW "{schema}".vw_sales_by_category AS
SELECT
    category_name,
    COUNT(DISTINCT order_id)                                       AS orders_count,
    COUNT(*)                                                       AS items_sold,
    ROUND(SUM(item_total)::numeric, 2)                            AS revenue,
    ROUND(AVG(item_total)::numeric, 2)                            AS avg_item_value,
    ROUND(AVG(review_score)::numeric, 2)                          AS avg_review_score,
    ROUND(AVG(CASE WHEN is_late THEN 1 ELSE 0 END)::numeric, 4)  AS late_rate
FROM "{schema}".order_items_enriched
GROUP BY category_name;

CREATE OR REPLACE VIEW "{schema}".vw_sales_by_state AS
SELECT
    customer_state,
    COUNT(DISTINCT order_id)                                       AS orders_count,
    ROUND(SUM(order_total)::numeric, 2)                           AS revenue,
    ROUND(AVG(order_total)::numeric, 2)                           AS avg_order_value,
    ROUND(AVG(review_score)::numeric, 2)                          AS avg_review_score,
    ROUND(AVG(CASE WHEN is_late THEN 1 ELSE 0 END)::numeric, 4)  AS late_rate
FROM "{schema}".orders_enriched
GROUP BY customer_state;

CREATE OR REPLACE VIEW "{schema}".vw_seller_performance AS
SELECT
    seller_id,
    orders_count,
    items_sold,
    ROUND(revenue::numeric, 2)                  AS revenue,
    ROUND(avg_review_score::numeric, 2)         AS avg_review_score,
    ROUND(avg_delivery_delay_days::numeric, 2)  AS avg_delivery_delay_days,
    ROUND(late_rate::numeric, 4)                AS late_rate,
    ROUND(seller_health_score::numeric, 4)      AS seller_health_score,
    seller_risk_level
FROM "{schema}".seller_performance;

CREATE OR REPLACE VIEW "{schema}".vw_customer_segments AS
SELECT
    customer_segment,
    COUNT(*)                                              AS customers_count,
    ROUND(SUM(customer_lifetime_value)::numeric, 2)      AS revenue,
    ROUND(AVG(customer_lifetime_value)::numeric, 2)      AS avg_customer_lifetime_value,
    ROUND(AVG(avg_order_value)::numeric, 2)              AS avg_order_value,
    ROUND(AVG(orders_count)::numeric, 2)                 AS avg_orders_per_customer,
    ROUND(
        (
            SUM(customer_lifetime_value)
            / NULLIF(SUM(SUM(customer_lifetime_value)) OVER (), 0)
        )::numeric,
        4
    ) AS revenue_share
FROM "{schema}".customer_segments
GROUP BY customer_segment;

CREATE OR REPLACE VIEW "{schema}".vw_delivery_performance AS
SELECT
    is_late,
    COUNT(*)                                           AS orders_count,
    ROUND(AVG(review_score)::numeric, 2)              AS avg_review_score,
    ROUND(AVG(delivery_delay_days)::numeric, 2)       AS avg_delivery_delay_days,
    ROUND(AVG(delivery_time_days)::numeric, 2)        AS avg_delivery_time_days,
    ROUND(AVG(order_total)::numeric, 2)               AS avg_order_value
FROM "{schema}".orders_enriched
WHERE is_delivered = TRUE
GROUP BY is_late;
