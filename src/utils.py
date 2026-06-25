"""
Formatting helpers and lightweight data-manipulation utilities.
"""

import pandas as pd


# ── Formatters ─────────────────────────────────────────────────────────────────

def fmt_currency(value: float) -> str:
    """Format a float as BRL: R$ 1.234,56"""
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def fmt_number(value: float) -> str:
    """Format an integer with thousands separator: 1.234"""
    return f"{int(value):,}".replace(",", ".")


def fmt_pct(value: float) -> str:
    """Format a 0–1 float as percentage: 12.3%"""
    return f"{value * 100:.1f}%"


# ── Aggregations ───────────────────────────────────────────────────────────────

def revenue_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate order_total by calendar month from an orders_enriched slice."""
    if df.empty or "order_purchase_timestamp" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df["month"] = (
        pd.to_datetime(df["order_purchase_timestamp"])
        .dt.to_period("M")
        .dt.to_timestamp()
    )
    return (
        df.groupby("month", as_index=False)
        .agg(revenue=("order_total", "sum"), orders=("order_id", "nunique"))
        .sort_values("month")
    )
