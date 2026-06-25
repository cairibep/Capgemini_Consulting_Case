"""
Database connection and query helpers for the Streamlit dashboard.

All public functions are cached with st.cache_data so the database is not
hit on every Streamlit re-run.
"""

import os
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

SCHEMA = os.getenv("POSTGRES_SCHEMA", "analytics")


# ── Engine ─────────────────────────────────────────────────────────────────────

def _get_engine():
    user = quote_plus(os.getenv("POSTGRES_USER", "olist"))
    password = quote_plus(os.getenv("POSTGRES_PASSWORD", "olist"))
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "55432")
    db = os.getenv("POSTGRES_DB", "olist")
    url = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url, pool_pre_ping=True)


def _schema() -> str:
    return f'"{SCHEMA}"'


# ── Generic query ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="Consultando banco de dados…")
def query(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Execute a parameterised SQL query and return a DataFrame.

    Returns an empty DataFrame and shows a Streamlit error on failure
    so the app never crashes due to a missing view or connectivity issue.
    """
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})
    except Exception as exc:
        st.error(f"Erro ao consultar o banco: {exc}")
        return pd.DataFrame()


# ── View loaders ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def load_view(view_name: str) -> pd.DataFrame:
    """Load a full pre-aggregated view (no filters)."""
    return query(f"SELECT * FROM {_schema()}.{view_name}")


# ── Filtered loaders (queries go to base tables) ───────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def load_orders_enriched(
    date_start: str | None = None,
    date_end: str | None = None,
    states: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Load orders_enriched with optional date / state filters."""
    filters = ["1=1"]
    params: dict = {}

    if date_start:
        filters.append("order_purchase_timestamp >= :date_start")
        params["date_start"] = date_start
    if date_end:
        # Include the full last day
        filters.append("order_purchase_timestamp < (:date_end ::date + INTERVAL '1 day')")
        params["date_end"] = date_end
    if states:
        filters.append("customer_state = ANY(:states)")
        params["states"] = list(states)

    where = " AND ".join(filters)
    sql = f"""
        SELECT
            order_id,
            customer_unique_id,
            customer_state,
            order_purchase_timestamp,
            order_total,
            review_score,
            is_late,
            is_delivered
        FROM {_schema()}.orders_enriched
        WHERE {where}
    """
    return query(sql, params or None)


@st.cache_data(ttl=300, show_spinner=False)
def load_items_enriched(
    date_start: str | None = None,
    date_end: str | None = None,
    states: tuple[str, ...] | None = None,
    categories: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Load order_items_enriched with optional date / state / category filters."""
    filters = ["1=1"]
    params: dict = {}

    if date_start:
        filters.append("order_purchase_timestamp >= :date_start")
        params["date_start"] = date_start
    if date_end:
        filters.append("order_purchase_timestamp < (:date_end ::date + INTERVAL '1 day')")
        params["date_end"] = date_end
    if states:
        filters.append("customer_state = ANY(:states)")
        params["states"] = list(states)
    if categories:
        filters.append("category_name = ANY(:categories)")
        params["categories"] = list(categories)

    where = " AND ".join(filters)
    sql = f"""
        SELECT
            order_id,
            product_id,
            category_name,
            item_total,
            customer_state,
            seller_state,
            order_purchase_timestamp,
            review_score,
            is_late
        FROM {_schema()}.order_items_enriched
        WHERE {where}
    """
    return query(sql, params or None)


# ── Sidebar filter options ─────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def get_filter_options() -> dict:
    """Return distinct values used to populate sidebar widgets."""
    states_df = query(
        f"SELECT DISTINCT customer_state "
        f"FROM {_schema()}.orders_enriched "
        "WHERE customer_state IS NOT NULL ORDER BY customer_state"
    )
    cats_df = query(
        f"SELECT DISTINCT category_name "
        f"FROM {_schema()}.order_items_enriched "
        "WHERE category_name IS NOT NULL ORDER BY category_name"
    )
    dates_df = query(
        f"SELECT MIN(order_purchase_timestamp) AS min_date, "
        f"       MAX(order_purchase_timestamp) AS max_date "
        f"FROM {_schema()}.orders_enriched"
    )
    return {
        "states": states_df["customer_state"].tolist() if not states_df.empty else [],
        "categories": cats_df["category_name"].tolist() if not cats_df.empty else [],
        "min_date": dates_df["min_date"].iloc[0] if not dates_df.empty else None,
        "max_date": dates_df["max_date"].iloc[0] if not dates_df.empty else None,
    }
