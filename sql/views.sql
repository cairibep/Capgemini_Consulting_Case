-- "Qual categoria vende mais, gera mais receita e tem maior índice de atraso?"
CREATE OR REPLACE VIEW "{schema}".vw_sales_by_category AS
SELECT
    category_name,
    COUNT(DISTINCT order_id) AS orders_count,
    COUNT(*) AS items_sold,
    ROUND(SUM(item_total)::numeric, 2) AS revenue,
    ROUND(AVG(item_total)::numeric, 2) AS avg_item_value,
    ROUND(AVG(review_score)::numeric, 2) AS avg_review_score,
    ROUND(AVG(CASE WHEN is_late THEN 1 ELSE 0 END)::numeric, 4) AS late_rate
FROM "{schema}".order_items_enriched
GROUP BY category_name;

-- "Quais estados compram mais, gastam mais e têm mais atrasos?"
CREATE OR REPLACE VIEW "{schema}".vw_sales_by_state AS
SELECT
    customer_state,
    COUNT(DISTINCT order_id) AS orders_count,
    ROUND(SUM(order_total)::numeric, 2) AS revenue,
    ROUND(AVG(order_total)::numeric, 2) AS avg_order_value,
    ROUND(AVG(review_score)::numeric, 2) AS avg_review_score,
    ROUND(AVG(CASE WHEN is_late THEN 1 ELSE 0 END)::numeric, 4) AS late_rate
FROM "{schema}".orders_enriched
GROUP BY customer_state;

-- "Quais vendedores são saudáveis, merecem atenção ou estão em risco?"
CREATE OR REPLACE VIEW "{schema}".vw_seller_performance AS
SELECT
    seller_id,
    orders_count,
    items_sold,
    ROUND(revenue::numeric, 2) AS revenue,
    ROUND(avg_review_score::numeric, 2) AS avg_review_score,
    ROUND(avg_delivery_delay_days::numeric, 2) AS avg_delivery_delay_days,
    ROUND(late_rate::numeric, 4) AS late_rate,
    ROUND(seller_health_score::numeric, 4) AS seller_health_score,
    seller_risk_level
FROM "{schema}".seller_performance;

-- "Quais clientes são VIPs, High Value, Regular ou Low Value? Quanto cada segmento contribui para a receita?"
CREATE OR REPLACE VIEW "{schema}".vw_customer_segments AS
SELECT
    customer_segment,
    COUNT(*) AS customers_count,
    ROUND(SUM(customer_lifetime_value)::numeric, 2) AS revenue,
    ROUND(AVG(customer_lifetime_value)::numeric, 2) AS avg_customer_lifetime_value,
    ROUND(AVG(avg_order_value)::numeric, 2) AS avg_order_value,
    ROUND(AVG(orders_count)::numeric, 2) AS avg_orders_per_customer,
    ROUND(
        (
            SUM(customer_lifetime_value)
            / NULLIF(SUM(SUM(customer_lifetime_value)) OVER (), 0)
        )::numeric,
        4
    ) AS revenue_share
FROM "{schema}".customer_segments
GROUP BY customer_segment;

-- "Pedidos atrasados têm avaliação pior? Quanto tempo a mais levam?"
CREATE OR REPLACE VIEW "{schema}".vw_delivery_performance AS
SELECT
    is_late,
    COUNT(*) AS orders_count,
    ROUND(AVG(review_score)::numeric, 2) AS avg_review_score,
    ROUND(AVG(delivery_delay_days)::numeric, 2) AS avg_delivery_delay_days,
    ROUND(AVG(delivery_time_days)::numeric, 2) AS avg_delivery_time_days,
    ROUND(AVG(order_total)::numeric, 2) AS avg_order_value
FROM "{schema}".orders_enriched
WHERE is_delivered = TRUE
GROUP BY is_late;

-- "Como a receita evoluiu ao longo do tempo? Há sazonalidade?"
CREATE OR REPLACE VIEW "{schema}".vw_sales_over_time AS
SELECT
    DATE_TRUNC('month', order_purchase_timestamp)              AS month,
    COUNT(DISTINCT order_id)                                   AS orders_count,
    COUNT(DISTINCT customer_unique_id)                         AS unique_customers,
    ROUND(SUM(order_total)::numeric, 2)                        AS revenue,
    ROUND(AVG(order_total)::numeric, 2)                        AS avg_order_value,
    ROUND(AVG(review_score)::numeric, 2)                       AS avg_review_score,
    ROUND(AVG(CASE WHEN is_late THEN 1 ELSE 0 END)::numeric, 4) AS late_rate
FROM "{schema}".orders_enriched
WHERE order_purchase_timestamp IS NOT NULL
GROUP BY DATE_TRUNC('month', order_purchase_timestamp);

-- "Quais cidades compram mais? Há diferença de ticket entre municípios do mesmo estado?"
CREATE OR REPLACE VIEW "{schema}".vw_sales_by_city AS
SELECT
    customer_city,
    customer_state,
    COUNT(DISTINCT order_id)                                    AS orders_count,
    ROUND(SUM(order_total)::numeric, 2)                         AS revenue,
    ROUND(AVG(order_total)::numeric, 2)                         AS avg_order_value,
    ROUND(AVG(review_score)::numeric, 2)                        AS avg_review_score,
    ROUND(AVG(CASE WHEN is_late THEN 1 ELSE 0 END)::numeric, 4) AS late_rate
FROM "{schema}".orders_enriched
GROUP BY customer_city, customer_state;

-- "Quais categorias dominam em cada estado? Há diferença regional de preferência?"
CREATE OR REPLACE VIEW "{schema}".vw_sales_by_state_category AS
SELECT
    customer_state,
    category_name,
    COUNT(DISTINCT order_id)                                    AS orders_count,
    COUNT(*)                                                    AS items_sold,
    ROUND(SUM(item_total)::numeric, 2)                          AS revenue,
    ROUND(AVG(item_total)::numeric, 2)                          AS avg_item_value,
    ROUND(AVG(review_score)::numeric, 2)                        AS avg_review_score,
    ROUND(AVG(CASE WHEN is_late THEN 1 ELSE 0 END)::numeric, 4) AS late_rate
FROM "{schema}".order_items_enriched
GROUP BY customer_state, category_name;

-- "Quais produtos individuais geram mais receita e têm melhor avaliação?"
CREATE OR REPLACE VIEW "{schema}".vw_top_products AS
SELECT
    product_id,
    category_name,
    COUNT(DISTINCT order_id)                                    AS orders_count,
    COUNT(*)                                                    AS items_sold,
    ROUND(SUM(item_total)::numeric, 2)                          AS revenue,
    ROUND(AVG(item_total)::numeric, 2)                          AS avg_item_value,
    ROUND(AVG(review_score)::numeric, 2)                        AS avg_review_score,
    ROUND(AVG(CASE WHEN is_late THEN 1 ELSE 0 END)::numeric, 4) AS late_rate
FROM "{schema}".order_items_enriched
GROUP BY product_id, category_name;
