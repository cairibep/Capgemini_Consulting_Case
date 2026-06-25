import numpy as np
import pandas as pd

ORDER_DATE_COLUMNS = [
    "order_purchase_timestamp",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]

def _days_between(end: pd.Series, start: pd.Series) -> pd.Series:
    return (end - start).dt.total_seconds() / 86400


def _min_max_score(series: pd.Series) -> pd.Series:
    min_value = series.min()
    max_value = series.max()
    if pd.isna(min_value) or pd.isna(max_value) or max_value == min_value:
        return pd.Series(0.0, index=series.index)
    return (series - min_value) / (max_value - min_value)


def build_orders_enriched(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    orders = data["orders"].copy()
    customers = data["customers"].copy()
    payments = data["order_payments"].copy()
    reviews = data["order_reviews"].copy()

    for column in ORDER_DATE_COLUMNS:
        orders[column] = pd.to_datetime(orders[column], errors="coerce")

    payments_by_order = (
        payments.groupby("order_id", as_index=False)
        .agg(payment_total=("payment_value", "sum"))
    )

    reviews_by_order = (
        reviews.groupby("order_id", as_index=False)
        .agg(
            review_score=("review_score", "mean"),
            review_count=("review_id", "nunique"),
        )
    )

    orders_enriched = (
        orders.merge(customers, on="customer_id", how="left")
        .merge(payments_by_order, on="order_id", how="left")
        .merge(reviews_by_order, on="order_id", how="left")
    )

    delivered = orders_enriched["order_delivered_customer_date"]
    estimated = orders_enriched["order_estimated_delivery_date"]
    purchased = orders_enriched["order_purchase_timestamp"]

    orders_enriched["is_delivered"] = delivered.notna()
    orders_enriched["delivery_delay_days"] = _days_between(delivered, estimated)
    orders_enriched["delivery_time_days"] = _days_between(delivered, purchased)
    orders_enriched["is_late"] = orders_enriched["delivery_delay_days"] > 0
    orders_enriched["order_total"] = orders_enriched["payment_total"].fillna(0)
    orders_enriched["avg_order_value"] = orders_enriched["order_total"]

    return orders_enriched[
        [
            "order_id",
            "customer_id",
            "customer_unique_id",
            "customer_city",
            "customer_state",
            "order_status",
            "order_purchase_timestamp",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
            "is_delivered",
            "delivery_delay_days",
            "delivery_time_days",
            "is_late",
            "order_total",
            "avg_order_value",
            "review_score",
            "review_count",
        ]
    ]


def build_order_items_enriched(data: dict[str, pd.DataFrame], orders_enriched: pd.DataFrame) -> pd.DataFrame:
    order_items = data["order_items"].copy()
    products = data["products"].copy()
    sellers = data["sellers"].copy()
    translations = data["category_translation"].copy()

    order_items["shipping_limit_date"] = pd.to_datetime(
        order_items["shipping_limit_date"], errors="coerce"
    )
    order_items["item_total"] = order_items["price"] + order_items["freight_value"]

    if "category_name" not in products.columns:
        products = products.merge(translations, on="product_category_name", how="left")
        products["category_name"] = products["product_category_name_english"].fillna(
            products["product_category_name"]
        )

    order_context = orders_enriched[
        [
            "order_id",
            "customer_state",
            "order_purchase_timestamp",
            "is_delivered",
            "delivery_delay_days",
            "delivery_time_days",
            "is_late",
            "review_score",
        ]
    ]

    items_enriched = (
        order_items.merge(
            products[["product_id", "product_category_name", "category_name"]],
            on="product_id",
            how="left",
        )
        .merge(
            sellers[["seller_id", "seller_city", "seller_state"]],
            on="seller_id",
            how="left",
        )
        .merge(order_context, on="order_id", how="left")
    )

    items_enriched["category_name"] = items_enriched["category_name"].fillna("unknown")

    return items_enriched[
        [
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
            "item_total",
            "product_category_name",
            "category_name",
            "seller_city",
            "seller_state",
            "customer_state",
            "order_purchase_timestamp",
            "is_delivered",
            "delivery_delay_days",
            "delivery_time_days",
            "is_late",
            "review_score",
        ]
    ]


def build_customer_segments(orders_enriched: pd.DataFrame) -> pd.DataFrame:
    customer_metrics = (
        orders_enriched.groupby("customer_unique_id", as_index=False)
        .agg(
            orders_count=("order_id", "nunique"),
            total_spent=("order_total", "sum"),
            avg_order_value=("order_total", "mean"),
            first_purchase_at=("order_purchase_timestamp", "min"),
            last_purchase_at=("order_purchase_timestamp", "max"),
            avg_review_score=("review_score", "mean"),
            late_orders=("is_late", "sum"),
        )
        .rename(columns={"total_spent": "customer_lifetime_value"})
    )

    customer_metrics["late_order_rate"] = (
        customer_metrics["late_orders"] / customer_metrics["orders_count"]
    )

    conditions = [
        customer_metrics["customer_lifetime_value"] > 2000,
        customer_metrics["customer_lifetime_value"] > 1000,
        customer_metrics["customer_lifetime_value"] > 300,
    ]
    choices = ["VIP", "High Value", "Regular"]
    customer_metrics["customer_segment"] = np.select(
        conditions, choices, default="Low Value"
    )

    return customer_metrics


def build_seller_performance(order_items_enriched: pd.DataFrame) -> pd.DataFrame:
    seller_metrics = (
        order_items_enriched.groupby("seller_id", as_index=False)
        .agg(
            orders_count=("order_id", "nunique"),
            items_sold=("order_item_id", "count"),
            revenue=("item_total", "sum"),
            avg_review_score=("review_score", "mean"),
            avg_delivery_delay_days=("delivery_delay_days", "mean"),
            late_items=("is_late", "sum"),
        )
    )

    seller_metrics["late_rate"] = (
        seller_metrics["late_items"] / seller_metrics["items_sold"]
    ).fillna(0)
    seller_metrics["avg_review_score"] = seller_metrics["avg_review_score"].fillna(0)
    seller_metrics["avg_delivery_delay_days"] = seller_metrics[
        "avg_delivery_delay_days"
    ].fillna(0)

    seller_metrics["revenue_score"] = _min_max_score(seller_metrics["revenue"])
    seller_metrics["review_score_normalized"] = seller_metrics["avg_review_score"] / 5
    seller_metrics["delay_score"] = _min_max_score(
        seller_metrics["avg_delivery_delay_days"].clip(lower=0)
    )
    seller_metrics["seller_health_score"] = (
        0.5 * seller_metrics["revenue_score"]
        + 0.3 * seller_metrics["review_score_normalized"]
        - 0.2 * seller_metrics["delay_score"]
    )
    seller_metrics["seller_risk_level"] = pd.cut(
        seller_metrics["seller_health_score"],
        bins=[-np.inf, 0.15, 0.35, np.inf],
        labels=["At Risk", "Watch", "Healthy"],
    ).astype(str)

    return seller_metrics


def build_analytics_tables(raw_tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    orders_enriched = build_orders_enriched(raw_tables)
    order_items_enriched = build_order_items_enriched(raw_tables, orders_enriched)
    customer_segments = build_customer_segments(orders_enriched)
    seller_performance = build_seller_performance(order_items_enriched)

    return {
        "orders_enriched": orders_enriched,
        "order_items_enriched": order_items_enriched,
        "customer_segments": customer_segments,
        "seller_performance": seller_performance,
    }
