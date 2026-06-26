import pandas as pd


def transform(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Parse raw CSV data into correct types. No derived columns."""
    tables = {name: df.copy() for name, df in data.items()}

    clean_orders(tables["orders"])
    clean_order_items(tables["order_items"])
    clean_reviews(tables["order_reviews"])
    tables["geolocation_by_zip"] = build_geolocation_by_zip(tables["geolocation"])

    return tables


def clean_orders(orders: pd.DataFrame) -> None:
    for column in [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]:
        orders[column] = pd.to_datetime(orders[column], errors="coerce")


def clean_order_items(order_items: pd.DataFrame) -> None:
    order_items["shipping_limit_date"] = pd.to_datetime(
        order_items["shipping_limit_date"], errors="coerce"
    )


def clean_reviews(order_reviews: pd.DataFrame) -> None:
    for column in ["review_creation_date", "review_answer_timestamp"]:
        order_reviews[column] = pd.to_datetime(order_reviews[column], errors="coerce")


def build_geolocation_by_zip(geolocation: pd.DataFrame) -> pd.DataFrame:
    """One row per zip code prefix with averaged lat/lng coordinates."""
    return (
        geolocation
        .groupby("geolocation_zip_code_prefix", as_index=False)
        .agg(
            geolocation_lat=("geolocation_lat", "mean"),
            geolocation_lng=("geolocation_lng", "mean"),
            geolocation_city=("geolocation_city", "first"),
            geolocation_state=("geolocation_state", "first"),
        )
    )
