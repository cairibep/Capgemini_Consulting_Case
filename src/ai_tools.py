"""
Thin query layer over analytical views for the AI Business Analyst agent.

Only pre-defined, parameterised SQL is executed here — never free-form LLM SQL.
Each function returns a list of dicts (JSON-serialisable) or an error dict.
"""
from __future__ import annotations

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

# ── Allowed values for validated params ────────────────────────────────────────

_CATEGORY_ORDER_COLS = frozenset({
    "revenue", "orders_count", "items_sold", "avg_review_score", "late_rate"
})
_STATE_ORDER_COLS = frozenset({
    "revenue", "orders_count", "avg_order_value", "avg_review_score", "late_rate"
})
_SELLER_ORDER_COLS = frozenset({
    "revenue", "orders_count", "avg_review_score", "late_rate", "seller_health_score"
})
_RISK_LEVELS = frozenset({"At Risk", "Watch", "Healthy"})

MAX_LIMIT = 50

SCHEMA = os.getenv("POSTGRES_SCHEMA", "analytics")


# ── Engine ─────────────────────────────────────────────────────────────────────

def _engine():
    user     = quote_plus(os.getenv("POSTGRES_USER", "olist"))
    password = quote_plus(os.getenv("POSTGRES_PASSWORD", "olist"))
    host     = os.getenv("POSTGRES_HOST", "localhost")
    port     = os.getenv("POSTGRES_PORT", "5432")
    db       = os.getenv("POSTGRES_DB", "olist")
    url      = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url, pool_pre_ping=True)


def _view(name: str) -> str:
    return f'"{SCHEMA}".{name}'


def _run(sql: str, params: dict | None = None) -> list[dict] | dict:
    """Execute a parameterised query and return rows as a list of dicts."""
    try:
        with _engine().connect() as conn:
            result = conn.execute(text(sql), params or {})
            cols   = list(result.keys())
            return [dict(zip(cols, row)) for row in result.fetchall()]
    except SQLAlchemyError as exc:
        return {"error": str(exc)}


# ── Tools ──────────────────────────────────────────────────────────────────────

def get_sales_by_category(limit: int = 10, order_by: str = "revenue") -> list[dict] | dict:
    """
    Returns sales metrics aggregated by product category.

    Args:
        limit:    Number of rows to return (1–50). Default 10.
        order_by: Column to sort by descending.
                  Allowed: revenue, orders_count, items_sold,
                           avg_review_score, late_rate.
    """
    limit    = min(max(1, int(limit)), MAX_LIMIT)
    order_by = order_by if order_by in _CATEGORY_ORDER_COLS else "revenue"

    sql = f"""
        SELECT category_name, orders_count, items_sold,
               revenue, avg_item_value, avg_review_score, late_rate
        FROM {_view("vw_sales_by_category")}
        ORDER BY {order_by} DESC NULLS LAST
        LIMIT :limit
    """
    return _run(sql, {"limit": limit})


def get_sales_by_state(limit: int = 10, order_by: str = "revenue") -> list[dict] | dict:
    """
    Returns sales metrics aggregated by customer state (UF).

    Args:
        limit:    Number of rows to return (1–50). Default 10.
        order_by: Column to sort by descending.
                  Allowed: revenue, orders_count, avg_order_value,
                           avg_review_score, late_rate.
    """
    limit    = min(max(1, int(limit)), MAX_LIMIT)
    order_by = order_by if order_by in _STATE_ORDER_COLS else "revenue"

    sql = f"""
        SELECT customer_state, orders_count, revenue,
               avg_order_value, avg_review_score, late_rate
        FROM {_view("vw_sales_by_state")}
        ORDER BY {order_by} DESC NULLS LAST
        LIMIT :limit
    """
    return _run(sql, {"limit": limit})


def get_customer_segments() -> list[dict] | dict:
    """
    Returns all customer segments with headcount, revenue, LTV and revenue share.
    No parameters — the view is fully pre-aggregated.
    """
    sql = f"""
        SELECT customer_segment, customers_count, revenue,
               avg_customer_lifetime_value, avg_order_value,
               avg_orders_per_customer, revenue_share
        FROM {_view("vw_customer_segments")}
        ORDER BY revenue DESC
    """
    return _run(sql)


def get_seller_performance(
    limit: int = 10,
    risk_level: str | None = None,
) -> list[dict] | dict:
    """
    Returns seller performance data, optionally filtered by risk level.

    Args:
        limit:      Number of sellers to return (1–50). Default 10.
        risk_level: Optional filter. Allowed: "At Risk", "Watch", "Healthy".
                    Omit to return top sellers regardless of risk.
    """
    limit = min(max(1, int(limit)), MAX_LIMIT)

    if risk_level is not None and risk_level not in _RISK_LEVELS:
        return {
            "error": (
                f"Invalid risk_level '{risk_level}'. "
                f"Allowed values: {sorted(_RISK_LEVELS)}"
            )
        }

    if risk_level:
        sql = f"""
            SELECT seller_id, orders_count, items_sold, revenue,
                   avg_review_score, avg_delivery_delay_days,
                   late_rate, seller_health_score, seller_risk_level
            FROM {_view("vw_seller_performance")}
            WHERE seller_risk_level = :risk_level
            ORDER BY revenue DESC NULLS LAST
            LIMIT :limit
        """
        return _run(sql, {"risk_level": risk_level, "limit": limit})

    sql = f"""
        SELECT seller_id, orders_count, items_sold, revenue,
               avg_review_score, avg_delivery_delay_days,
               late_rate, seller_health_score, seller_risk_level
        FROM {_view("vw_seller_performance")}
        ORDER BY revenue DESC NULLS LAST
        LIMIT :limit
    """
    return _run(sql, {"limit": limit})


def get_delivery_performance() -> list[dict] | dict:
    """
    Returns delivery performance split by on-time vs late orders,
    including review scores, average delay and delivery time.
    """
    sql = f"""
        SELECT is_late, orders_count, avg_review_score,
               avg_delivery_delay_days, avg_delivery_time_days, avg_order_value
        FROM {_view("vw_delivery_performance")}
        ORDER BY is_late
    """
    return _run(sql)


def get_sales_over_time(limit: int = 24) -> list[dict] | dict:
    """
    Returns monthly sales metrics in chronological order (most recent first).

    Args:
        limit: Number of months to return (1–50). Default 24 (two years).
    """
    limit = min(max(1, int(limit)), MAX_LIMIT)

    sql = f"""
        SELECT
            month,
            orders_count,
            unique_customers,
            revenue,
            avg_order_value,
            avg_review_score,
            late_rate
        FROM {_view("vw_sales_over_time")}
        ORDER BY month DESC
        LIMIT :limit
    """
    rows = _run(sql, {"limit": limit})
    # Return chronological order so the model reads oldest → newest
    if isinstance(rows, list):
        return list(reversed(rows))
    return rows


def get_sales_by_city(
    limit: int = 15,
    order_by: str = "revenue",
    state: str | None = None,
) -> list[dict] | dict:
    """
    Returns sales metrics aggregated by city, optionally filtered by state.

    Args:
        limit:    Number of rows to return (1–50). Default 15.
        order_by: Column to sort by descending.
                  Allowed: revenue, orders_count, avg_order_value,
                           avg_review_score, late_rate.
        state:    Optional 2-letter state code to filter (e.g. "SP", "RJ").
    """
    limit    = min(max(1, int(limit)), MAX_LIMIT)
    order_by = order_by if order_by in _STATE_ORDER_COLS else "revenue"

    if state:
        sql = f"""
            SELECT customer_city, customer_state, orders_count,
                   revenue, avg_order_value, avg_review_score, late_rate
            FROM {_view("vw_sales_by_city")}
            WHERE UPPER(customer_state) = UPPER(:state)
            ORDER BY {order_by} DESC NULLS LAST
            LIMIT :limit
        """
        return _run(sql, {"state": state, "limit": limit})

    sql = f"""
        SELECT customer_city, customer_state, orders_count,
               revenue, avg_order_value, avg_review_score, late_rate
        FROM {_view("vw_sales_by_city")}
        ORDER BY {order_by} DESC NULLS LAST
        LIMIT :limit
    """
    return _run(sql, {"limit": limit})


def get_sales_by_state_category(
    state: str | None = None,
    limit: int = 10,
    order_by: str = "revenue",
) -> list[dict] | dict:
    """
    Returns sales metrics broken down by (state, category).
    When a state is provided, returns top categories within that state.
    Without a state, returns the top (state, category) pairs globally.

    Args:
        state:    Optional 2-letter state code to filter (e.g. "SP", "RJ").
        limit:    Number of rows to return (1–50). Default 10.
        order_by: Column to sort by descending.
                  Allowed: revenue, orders_count, items_sold,
                           avg_review_score, late_rate.
    """
    limit    = min(max(1, int(limit)), MAX_LIMIT)
    order_by = order_by if order_by in _CATEGORY_ORDER_COLS else "revenue"

    if state:
        sql = f"""
            SELECT customer_state, category_name, orders_count,
                   items_sold, revenue, avg_item_value, avg_review_score, late_rate
            FROM {_view("vw_sales_by_state_category")}
            WHERE UPPER(customer_state) = UPPER(:state)
            ORDER BY {order_by} DESC NULLS LAST
            LIMIT :limit
        """
        return _run(sql, {"state": state, "limit": limit})

    sql = f"""
        SELECT customer_state, category_name, orders_count,
               items_sold, revenue, avg_item_value, avg_review_score, late_rate
        FROM {_view("vw_sales_by_state_category")}
        ORDER BY {order_by} DESC NULLS LAST
        LIMIT :limit
    """
    return _run(sql, {"limit": limit})


def get_top_products(
    limit: int = 10,
    order_by: str = "revenue",
    category: str | None = None,
) -> list[dict] | dict:
    """
    Returns top products by sales metrics, optionally filtered by category.

    Args:
        limit:    Number of products to return (1–50). Default 10.
        order_by: Column to sort by descending.
                  Allowed: revenue, orders_count, items_sold,
                           avg_review_score, late_rate.
        category: Optional category name to filter (exact match).
    """
    limit    = min(max(1, int(limit)), MAX_LIMIT)
    order_by = order_by if order_by in _CATEGORY_ORDER_COLS else "revenue"

    if category:
        sql = f"""
            SELECT product_id, category_name, orders_count,
                   items_sold, revenue, avg_item_value, avg_review_score, late_rate
            FROM {_view("vw_top_products")}
            WHERE LOWER(category_name) = LOWER(:category)
            ORDER BY {order_by} DESC NULLS LAST
            LIMIT :limit
        """
        return _run(sql, {"category": category, "limit": limit})

    sql = f"""
        SELECT product_id, category_name, orders_count,
               items_sold, revenue, avg_item_value, avg_review_score, late_rate
        FROM {_view("vw_top_products")}
        ORDER BY {order_by} DESC NULLS LAST
        LIMIT :limit
    """
    return _run(sql, {"limit": limit})


def get_business_overview() -> dict:
    """
    Returns a high-level business snapshot combining totals from all views:
    total revenue, total orders, top category, top state, overall late rate,
    count of at-risk sellers, and VIP customer revenue share.
    """
    queries = {
        "revenue_total": (
            f"SELECT COALESCE(SUM(revenue), 0) AS total "
            f"FROM {_view('vw_sales_by_state')}"
        ),
        "orders_total": (
            f"SELECT COALESCE(SUM(orders_count), 0) AS total "
            f"FROM {_view('vw_sales_by_state')}"
        ),
        "top_category": (
            f"SELECT category_name, revenue "
            f"FROM {_view('vw_sales_by_category')} "
            f"ORDER BY revenue DESC LIMIT 1"
        ),
        "top_state": (
            f"SELECT customer_state, revenue "
            f"FROM {_view('vw_sales_by_state')} "
            f"ORDER BY revenue DESC LIMIT 1"
        ),
        "avg_late_rate": (
            f"SELECT ROUND(AVG(late_rate)::numeric, 4) AS avg_late_rate "
            f"FROM {_view('vw_sales_by_state')}"
        ),
        "at_risk_sellers": (
            f"SELECT COUNT(*) AS count "
            f"FROM {_view('vw_seller_performance')} "
            f"WHERE seller_risk_level = 'At Risk'"
        ),
        "vip_revenue_share": (
            f"SELECT revenue_share, customers_count "
            f"FROM {_view('vw_customer_segments')} "
            f"WHERE customer_segment = 'VIP'"
        ),
    }

    overview: dict = {}
    for key, sql in queries.items():
        rows = _run(sql)
        if isinstance(rows, list):
            overview[key] = rows[0] if rows else {}
        else:
            overview[key] = rows  # propagate error dict

    return overview
