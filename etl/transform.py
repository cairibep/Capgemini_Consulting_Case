import pandas as pd


def transform(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Apply small cleaning steps and keep the original dataset structure."""
    tables = {name: df.copy() for name, df in data.items()}

    clean_orders(tables["orders"])
    clean_order_items(tables["order_items"])
    clean_reviews(tables["order_reviews"])
    clean_products(tables)
    tables["geolocation_by_zip"] = build_geolocation_by_zip(tables["geolocation"])

    return tables


def clean_orders(orders: pd.DataFrame) -> None:
    date_columns = [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]

    for column in date_columns:
        orders[column] = pd.to_datetime(orders[column], errors="coerce")

    delivered = orders["order_delivered_customer_date"]
    estimated = orders["order_estimated_delivery_date"]
    purchase = orders["order_purchase_timestamp"]

    orders["is_delivered"] = delivered.notna()
    orders["delivery_delay_days"] = (delivered - estimated).dt.days
    orders["delivery_time_days"] = (delivered - purchase).dt.days
    orders["is_late"] = orders["delivery_delay_days"] > 0


def clean_order_items(order_items: pd.DataFrame) -> None:
    order_items["shipping_limit_date"] = pd.to_datetime(
        order_items["shipping_limit_date"], errors="coerce"
    )
    order_items["item_total"] = order_items["price"] + order_items["freight_value"]


def clean_reviews(order_reviews: pd.DataFrame) -> None:
    date_columns = ["review_creation_date", "review_answer_timestamp"]

    for column in date_columns:
        order_reviews[column] = pd.to_datetime(order_reviews[column], errors="coerce")


def clean_products(tables: dict[str, pd.DataFrame]) -> None:
    products = tables["products"]
    translations = tables["category_translation"]

    products_with_translation = products.merge(
        translations,
        on="product_category_name",
        how="left",
    )
    products_with_translation["category_name"] = products_with_translation[
        "product_category_name_english"
    ].fillna(products_with_translation["product_category_name"])

    tables["products"] = products_with_translation


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
