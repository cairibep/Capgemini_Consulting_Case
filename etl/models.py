import numpy as np
import pandas as pd


def _days_between(end: pd.Series, start: pd.Series) -> pd.Series:
    return (end - start).dt.total_seconds() / 86400


def _min_max_score(series: pd.Series) -> pd.Series:
    lo, hi = series.min(), series.max()
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return pd.Series(0.0, index=series.index)
    return (series - lo) / (hi - lo)


def build_orders_enriched(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    orders = data["orders"].copy()
    payments = (
        data["order_payments"]
        .groupby("order_id", as_index=False)
        .agg(payment_total=("payment_value", "sum"))
    )
    reviews = (
        data["order_reviews"]
        .groupby("order_id", as_index=False)
        .agg(
            review_score=("review_score", "mean"),
            review_count=("review_id", "nunique"),
        )
    )

    df = (
        orders
        .merge(data["customers"], on="customer_id", how="left")
        .merge(payments, on="order_id", how="left")
        .merge(reviews, on="order_id", how="left")
    )

    delivered = df["order_delivered_customer_date"]
    estimated = df["order_estimated_delivery_date"]
    purchased = df["order_purchase_timestamp"]

    df["is_delivered"] = delivered.notna()
    df["delivery_delay_days"] = _days_between(delivered, estimated)
    df["delivery_time_days"] = _days_between(delivered, purchased)
    df["is_late"] = df["delivery_delay_days"] > 0
    df["order_total"] = df["payment_total"].fillna(0)
    df["avg_order_value"] = df["order_total"]

    return df[[
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
    ]]


def build_order_items_enriched(data: dict[str, pd.DataFrame], orders_enriched: pd.DataFrame) -> pd.DataFrame:
    items = data["order_items"].copy()
    items["item_total"] = items["price"] + items["freight_value"]

    products = data["products"].merge(
        data["category_translation"], on="product_category_name", how="left"
    )
    products["category_name"] = products["product_category_name_english"].fillna(
        products["product_category_name"]
    )

    order_context = orders_enriched[[
        "order_id",
        "customer_state",
        "order_purchase_timestamp",
        "is_delivered",
        "delivery_delay_days",
        "delivery_time_days",
        "is_late",
        "review_score",
    ]]

    return (
        items
        .merge(
            products[["product_id", "product_category_name", "category_name"]],
            on="product_id",
            how="left",
        )
        .merge(
            data["sellers"][["seller_id", "seller_city", "seller_state"]],
            on="seller_id",
            how="left",
        )
        .merge(order_context, on="order_id", how="left")
        .assign(category_name=lambda d: d["category_name"].fillna("unknown"))
    )[[
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
    ]]


def build_customer_segments(orders_enriched: pd.DataFrame) -> pd.DataFrame:
    df = (
        orders_enriched
        .groupby("customer_unique_id", as_index=False)
        .agg(
            orders_count=("order_id", "nunique"),
            customer_lifetime_value=("order_total", "sum"),
            avg_order_value=("order_total", "mean"),
            first_purchase_at=("order_purchase_timestamp", "min"),
            last_purchase_at=("order_purchase_timestamp", "max"),
            avg_review_score=("review_score", "mean"),
            late_orders=("is_late", "sum"),
        )
    )
    df["late_order_rate"] = df["late_orders"] / df["orders_count"]
    df["customer_segment"] = np.select(
        [
            df["customer_lifetime_value"] > 2000,
            df["customer_lifetime_value"] > 1000,
            df["customer_lifetime_value"] > 300,
        ],
        ["VIP", "High Value", "Regular"],
        default="Low Value",
    )
    return df


def build_seller_performance(order_items_enriched: pd.DataFrame) -> pd.DataFrame:
    df = (
        order_items_enriched
        .groupby("seller_id", as_index=False)
        .agg(
            orders_count=("order_id", "nunique"),
            items_sold=("order_item_id", "count"),
            revenue=("item_total", "sum"),
            avg_review_score=("review_score", "mean"),
            avg_delivery_delay_days=("delivery_delay_days", "mean"),
            late_items=("is_late", "sum"),
        )
        .assign(
            late_rate=lambda d: (d["late_items"] / d["items_sold"]).fillna(0),
            avg_review_score=lambda d: d["avg_review_score"].fillna(0),
            avg_delivery_delay_days=lambda d: d["avg_delivery_delay_days"].fillna(0),
        )
    )

    df["revenue_score"] = _min_max_score(df["revenue"])
    df["review_score_normalized"] = df["avg_review_score"] / 5
    df["delay_score"] = _min_max_score(df["avg_delivery_delay_days"].clip(lower=0))
    df["seller_health_score"] = (
        0.5 * df["revenue_score"]
        + 0.3 * df["review_score_normalized"]
        - 0.2 * df["delay_score"]
    )
    df["seller_risk_level"] = pd.cut(
        df["seller_health_score"],
        bins=[-np.inf, 0.15, 0.35, np.inf],
        labels=["At Risk", "Watch", "Healthy"],
    ).astype(str)

    return df


def build_analytics_tables(raw_tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    orders_enriched = build_orders_enriched(raw_tables)
    order_items_enriched = build_order_items_enriched(raw_tables, orders_enriched)
    return {
        "orders_enriched": orders_enriched,
        "order_items_enriched": order_items_enriched,
        "customer_segments": build_customer_segments(orders_enriched),
        "seller_performance": build_seller_performance(order_items_enriched),
    }
