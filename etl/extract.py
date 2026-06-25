from pathlib import Path

import pandas as pd


CSV_FILES = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}


def read_csvs(data_dir: Path) -> dict[str, pd.DataFrame]:
    missing = [name for name in CSV_FILES.values() if not (data_dir / name).exists()]
    if missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(f"Missing CSV files in {data_dir}: {missing_list}")

    return {
        table_name: pd.read_csv(data_dir / file_name)
        for table_name, file_name in CSV_FILES.items()
    }
