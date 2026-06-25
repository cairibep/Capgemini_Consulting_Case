from io import StringIO

import pandas as pd
import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

# Parent tables must come before children so the load order is already correct
# if constraints were ever added at creation time.
LOAD_ORDER = [
    "geolocation_by_zip",   # parent of customers, sellers
    "customers",            # parent of orders
    "products",             # parent of order_items
    "sellers",              # parent of order_items
    "orders",               # parent of order_items, order_payments, order_reviews
    "order_items",
    "order_payments",
    "order_reviews",
    "geolocation",          # raw table, no FK target
    "category_translation", # lookup; category_name already merged into products
]

# Single-column PKs: "col". Composite PKs: "col1, col2".
PRIMARY_KEYS = {
    "geolocation_by_zip":   "geolocation_zip_code_prefix",
    "category_translation": "product_category_name",
    "customers":            "customer_id",
    "products":             "product_id",
    "sellers":              "seller_id",
    "orders":               "order_id",
    "order_items":          "order_id, order_item_id",
    "order_payments":       "order_id, payment_sequential",
    "order_reviews":        "review_id, order_id",
}

# (child_table, child_col, parent_table, parent_col, constraint_name, not_valid)
# not_valid=True creates the constraint without validating existing rows (safe for legacy data gaps).
FOREIGN_KEYS = [
    ("orders",         "customer_id",              "customers",            "customer_id",                 "fk_orders_customers",      False),
    ("order_items",    "order_id",                 "orders",               "order_id",                    "fk_order_items_orders",    False),
    ("order_items",    "product_id",               "products",             "product_id",                  "fk_order_items_products",  False),
    ("order_items",    "seller_id",                "sellers",              "seller_id",                   "fk_order_items_sellers",   False),
    ("order_payments", "order_id",                 "orders",               "order_id",                    "fk_order_payments_orders", False),
    ("order_reviews",  "order_id",                 "orders",               "order_id",                    "fk_order_reviews_orders",  False),
    # NOT VALID: gaps exist in the dataset between lookup tables and transactional tables.
    ("products",       "product_category_name",    "category_translation", "product_category_name",       "fk_products_category",     True),
    ("customers",      "customer_zip_code_prefix", "geolocation_by_zip",   "geolocation_zip_code_prefix", "fk_customers_geolocation", True),
    ("sellers",        "seller_zip_code_prefix",   "geolocation_by_zip",   "geolocation_zip_code_prefix", "fk_sellers_geolocation",   True),
]

# Extra indexes on FK columns not already covered by a PK.
EXTRA_INDEXES = [
    ("orders",         "customer_id"),
    ("order_items",    "product_id"),
    ("order_items",    "seller_id"),
    ("order_payments", "order_id"),
    ("order_reviews",  "order_id"),
    ("customers",      "customer_zip_code_prefix"),
    ("sellers",        "seller_zip_code_prefix"),
]


def get_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True)


def load_tables(
    tables: dict[str, pd.DataFrame],
    database_url: str,
    schema: str,
    drop_schema: bool = True,
) -> None:
    engine = get_engine(database_url)

    with engine.begin() as connection:
        if drop_schema:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    ordered = [t for t in LOAD_ORDER if t in tables]
    ordered += [t for t in tables if t not in ordered]

    for table_name in ordered:
        dataframe = tables[table_name]
        print(f"Loading {schema}.{table_name} ({len(dataframe)} rows)")
        _create_empty_table(dataframe, table_name, engine, schema)
        _copy_to_postgres(dataframe, table_name, database_url, schema)

    print("Creating primary keys...")
    _create_primary_keys(engine, schema, tables)

    print("Creating foreign keys...")
    _create_foreign_keys(engine, schema, tables)

    print("Creating indexes...")
    _create_indexes(engine, schema, tables)


def _create_empty_table(
    dataframe: pd.DataFrame,
    table_name: str,
    engine,
    schema: str,
) -> None:
    dataframe.head(0).to_sql(
        table_name,
        engine,
        schema=schema,
        if_exists="replace",
        index=False,
    )


def _copy_to_postgres(
    dataframe: pd.DataFrame,
    table_name: str,
    database_url: str,
    schema: str,
) -> None:
    url = make_url(database_url)
    csv_buffer = StringIO()
    dataframe.to_csv(csv_buffer, sep="\t", header=False, index=False, na_rep="\\N")
    csv_buffer.seek(0)

    columns = ", ".join(_quote(col) for col in dataframe.columns)
    table = f"{_quote(schema)}.{_quote(table_name)}"
    copy_sql = (
        f"COPY {table} ({columns}) "
        "FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t', NULL '\\N')"
    )

    with psycopg.connect(
        host=url.host,
        port=url.port,
        dbname=url.database,
        user=url.username,
        password=url.password,
    ) as connection:
        with connection.cursor() as cursor:
            with cursor.copy(copy_sql) as copy:
                copy.write(csv_buffer.getvalue())


def _create_primary_keys(engine, schema: str, tables: dict) -> None:
    with engine.begin() as conn:
        for table, cols in PRIMARY_KEYS.items():
            if table not in tables:
                continue
            conn.execute(
                text(f'ALTER TABLE {_quote(schema)}.{_quote(table)} ADD PRIMARY KEY ({cols})')
            )


def _create_foreign_keys(engine, schema: str, tables: dict) -> None:
    q = _quote(schema)
    for child_table, child_col, parent_table, parent_col, name, not_valid in FOREIGN_KEYS:
        if child_table not in tables:
            continue
        try:
            with engine.begin() as conn:
                suffix = " NOT VALID" if not_valid else ""
                conn.execute(text(
                    f"ALTER TABLE {q}.{_quote(child_table)} "
                    f"ADD CONSTRAINT {name} "
                    f"FOREIGN KEY ({child_col}) "
                    f"REFERENCES {q}.{_quote(parent_table)} ({parent_col}){suffix}"
                ))
        except Exception as exc:
            print(f"  WARNING: could not create {name}: {exc}")


def _create_indexes(engine, schema: str, tables: dict) -> None:
    q = _quote(schema)
    with engine.begin() as conn:
        for table, col in EXTRA_INDEXES:
            if table not in tables:
                continue
            conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_{col} "
                f"ON {q}.{_quote(table)} ({col})"
            ))


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


# Kept for backwards compatibility with any external callers.
def quote_name(name: str) -> str:
    return _quote(name)
