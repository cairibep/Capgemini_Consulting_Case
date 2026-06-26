"""
Plotly chart builders.

Every function accepts a DataFrame and returns a Plotly Figure.
A graceful _empty() fallback is returned when the DataFrame is empty
so the app never crashes due to missing data.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PALETTE = px.colors.qualitative.Plotly
TEMPLATE = "plotly_white"


# ── Time series ────────────────────────────────────────────────────────────────

def revenue_over_time(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty("Sem dados para o período selecionado")
    fig = px.area(
        df,
        x="month",
        y="revenue",
        labels={"month": "Mês", "revenue": "Receita (R$)"},
        template=TEMPLATE,
        color_discrete_sequence=PALETTE,
    )
    fig.update_traces(
        line_color=PALETTE[0],
        fillcolor="rgba(99,110,250,0.12)",
        hovertemplate="<b>%{x|%b %Y}</b><br>Receita: R$ %{y:,.2f}<extra></extra>",
    )
    fig.update_layout(
        title="Receita Mensal",
        hovermode="x unified",
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.0f",
    )
    return fig


# ── Category charts ────────────────────────────────────────────────────────────

def revenue_by_category(df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    if df.empty or "revenue" not in df.columns:
        return _empty("Dados de categoria indisponíveis")
    top = df.nlargest(top_n, "revenue").copy()
    fig = px.bar(
        top,
        x="revenue",
        y="category_name",
        orientation="h",
        labels={"revenue": "Receita (R$)", "category_name": "Categoria"},
        template=TEMPLATE,
        color="revenue",
        color_continuous_scale="Blues",
        text="revenue",
    )
    fig.update_traces(
        texttemplate="R$ %{text:,.0f}",
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Receita: R$ %{x:,.2f}<extra></extra>",
    )
    fig.update_layout(
        title=f"Top {top_n} Categorias por Receita",
        yaxis=dict(autorange="reversed"),
        xaxis_tickprefix="R$ ",
        xaxis_tickformat=",.0f",
    )
    fig.update_coloraxes(showscale=False)
    return fig


def category_share_treemap(df: pd.DataFrame) -> go.Figure:
    if df.empty or "revenue" not in df.columns:
        return _empty("Dados de categoria indisponíveis")
    total = df["revenue"].sum()
    df = df.copy()
    df["share_pct"] = (df["revenue"] / total * 100).round(2)
    fig = px.treemap(
        df,
        path=["category_name"],
        values="revenue",
        color="revenue",
        color_continuous_scale="Blues",
        template=TEMPLATE,
        hover_data={"share_pct": ":.2f"},
        custom_data=["share_pct"],
    )
    fig.update_traces(
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Receita: R$ %{value:,.2f}<br>"
            "Share: %{customdata[0]:.2f}%<extra></extra>"
        )
    )
    fig.update_layout(title="Participação de Receita por Categoria")
    fig.update_coloraxes(showscale=False)
    return fig


# ── Geographic chart ───────────────────────────────────────────────────────────

def revenue_by_state(df: pd.DataFrame) -> go.Figure:
    if df.empty or "revenue" not in df.columns:
        return _empty("Dados por estado indisponíveis")
    fig = px.bar(
        df.sort_values("revenue", ascending=False),
        x="customer_state",
        y="revenue",
        labels={"customer_state": "Estado", "revenue": "Receita (R$)"},
        template=TEMPLATE,
        color="revenue",
        color_continuous_scale="Teal",
        text="revenue",
    )
    fig.update_traces(
        texttemplate="R$ %{text:,.0f}",
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Receita: R$ %{y:,.2f}<extra></extra>",
    )
    fig.update_layout(
        title="Receita por Estado",
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.0f",
    )
    fig.update_coloraxes(showscale=False)
    return fig


# ── Customer segment chart ─────────────────────────────────────────────────────

def customer_segments_donut(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty("View vw_customer_segments indisponível")
    fig = px.pie(
        df,
        names="customer_segment",
        values="revenue",
        hole=0.55,
        template=TEMPLATE,
        color_discrete_sequence=PALETTE,
    )
    fig.update_traces(
        textposition="outside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>Receita: R$ %{value:,.2f}<br>Share: %{percent}<extra></extra>",
    )
    fig.update_layout(title="Receita por Segmento de Cliente", showlegend=False)
    return fig


# ── Delivery chart ─────────────────────────────────────────────────────────────

def delivery_kpi_bars(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty("View vw_delivery_performance indisponível")
    df = df.copy()
    df["label"] = df["is_late"].map({True: "Com Atraso", False: "No Prazo"})
    fig = px.bar(
        df,
        x="label",
        y="orders_count",
        color="label",
        color_discrete_map={"No Prazo": "#2ecc71", "Com Atraso": "#e74c3c"},
        template=TEMPLATE,
        text="orders_count",
        labels={"label": "", "orders_count": "Pedidos"},
    )
    fig.update_traces(
        texttemplate="%{text:,}",
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Pedidos: %{y:,}<extra></extra>",
    )
    fig.update_layout(title="Pedidos: No Prazo vs Com Atraso", showlegend=False)
    return fig


# ── Operational quality scatter ───────────────────────────────────────────────

def category_quality_scatter(df: pd.DataFrame) -> go.Figure:
    """Scatter: avg review score (Y) vs late rate (X), bubble size = revenue.

    Each bubble is a category. Quadrants reveal operational health at a glance:
    top-left = best (low delay, high satisfaction), bottom-right = worst.
    """
    required = {"category_name", "avg_review_score", "late_rate", "revenue"}
    if df.empty or not required.issubset(df.columns):
        return _empty("Dados insuficientes para o scatter de qualidade")

    df = df.copy().dropna(subset=["avg_review_score", "late_rate", "revenue"])

    fig = px.scatter(
        df,
        x="late_rate",
        y="avg_review_score",
        size="revenue",
        color="revenue",
        color_continuous_scale="Blues",
        hover_name="category_name",
        hover_data={
            "revenue": ":,.2f",
            "late_rate": ":.1%",
            "avg_review_score": ":.2f",
            "orders_count": True,
        },
        labels={
            "late_rate": "Taxa de Atraso",
            "avg_review_score": "Nota Média (1–5)",
            "revenue": "Receita (R$)",
            "orders_count": "Pedidos",
        },
        size_max=55,
        template=TEMPLATE,
    )

    # Reference lines: medians
    med_x = df["late_rate"].median()
    med_y = df["avg_review_score"].median()
    fig.add_vline(x=med_x, line_dash="dot", line_color="#aaa", annotation_text="mediana atraso", annotation_position="top right")
    fig.add_hline(y=med_y, line_dash="dot", line_color="#aaa", annotation_text="mediana nota", annotation_position="bottom right")

    fig.update_traces(
        marker_line_width=0.5,
        marker_line_color="white",
    )
    fig.update_layout(
        title="Qualidade Operacional por Categoria — Nota vs Taxa de Atraso",
        xaxis_tickformat=".0%",
        coloraxis_showscale=False,
        height=520,
    )
    return fig


# ── State × category heatmap ──────────────────────────────────────────────────

def state_category_heatmap(
    df: pd.DataFrame,
    top_n_cats: int = 12,
    top_n_states: int = 15,
    normalize: bool = False,
) -> go.Figure:
    """Heatmap: states (rows) × top N categories (cols), coloured by revenue.

    Source: vw_sales_by_state_category.

    Args:
        top_n_cats:   number of categories to show (by total revenue)
        top_n_states: number of states to show (by total revenue)
        normalize:    when True, colour by % of each state's total revenue
                      instead of absolute value — removes the SP dominance effect
    """
    required = {"customer_state", "category_name", "revenue"}
    if df.empty or not required.issubset(df.columns):
        return _empty("View vw_sales_by_state_category indisponível")

    # Limit to top categories and top states
    top_cats = (
        df.groupby("category_name")["revenue"].sum()
        .nlargest(top_n_cats).index.tolist()
    )
    top_states = (
        df.groupby("customer_state")["revenue"].sum()
        .nlargest(top_n_states).index.tolist()
    )
    filtered = df[
        df["category_name"].isin(top_cats) & df["customer_state"].isin(top_states)
    ]

    # Pivot: states as rows, categories as columns
    pivot = filtered.pivot_table(
        index="customer_state",
        columns="category_name",
        values="revenue",
        aggfunc="sum",
        fill_value=0,
    )

    # Sort by total revenue (most important top-left)
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
    pivot = pivot[pivot.sum(axis=0).sort_values(ascending=False).index]

    # Keep the raw values for hover before any transformation
    pivot_raw = pivot.copy()

    if normalize:
        # Each cell = % of that state's total revenue across ALL categories
        row_totals = pivot_raw.sum(axis=1)
        pivot_display = pivot_raw.div(row_totals, axis=0) * 100
        color_label = "Share da receita do estado (%)"
        hover_z_fmt = ":.1f"
        hover_z_suffix = "%"
        colorbar_ticksuffix = "%"
        colorbar_tickformat = ".1f"
    else:
        # Log1p transform: compresses the SP spike so other states get colour
        pivot_display = np.log1p(pivot_raw)
        color_label = "Receita (escala log)"
        hover_z_fmt = ",.2f"
        hover_z_suffix = ""
        colorbar_ticksuffix = ""
        colorbar_tickformat = ",.0f"

    fig = px.imshow(
        pivot_display,
        labels=dict(x="Categoria", y="Estado", color=color_label),
        color_continuous_scale="Blues",
        aspect="auto",
        template=TEMPLATE,
        text_auto=False,
    )

    # Inject actual revenue values into customdata for hover
    fig.update_traces(
        customdata=pivot_raw.values,
        hovertemplate=(
            "<b>%{y} × %{x}</b><br>"
            f"Receita: R$ %{{customdata:{hover_z_fmt}}}{hover_z_suffix}"
            "<extra></extra>"
        ),
    )
    mode_label = "% por estado" if normalize else "receita absoluta (escala log)"
    fig.update_layout(
        title=f"Receita por Estado × Categoria — top {top_n_cats} categorias · {top_n_states} estados · {mode_label}",
        xaxis_tickangle=-40,
        coloraxis_colorbar=dict(
            title=color_label,
            tickformat=colorbar_tickformat,
            ticksuffix=colorbar_ticksuffix,
        ),
        height=max(400, top_n_states * 28 + 160),
        margin=dict(b=130),
    )
    return fig


# ── Seller health distribution ─────────────────────────────────────────────────

def seller_risk_bars(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty("View vw_seller_performance indisponível")
    agg = (
        df.groupby("seller_risk_level", as_index=False)
        .agg(sellers=("seller_id", "count"), revenue=("revenue", "sum"))
    )
    color_map = {"Healthy": "#2ecc71", "Watch": "#f39c12", "At Risk": "#e74c3c"}
    fig = px.bar(
        agg,
        x="seller_risk_level",
        y="sellers",
        color="seller_risk_level",
        color_discrete_map=color_map,
        template=TEMPLATE,
        text="sellers",
        labels={"seller_risk_level": "Nível de Risco", "sellers": "Vendedores"},
    )
    fig.update_traces(textposition="outside", showlegend=False)
    fig.update_layout(title="Vendedores por Nível de Risco")
    return fig


# ── Fallback ───────────────────────────────────────────────────────────────────

def _empty(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=msg,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=14, color="#888"),
    )
    fig.update_layout(template=TEMPLATE, height=300)
    return fig
