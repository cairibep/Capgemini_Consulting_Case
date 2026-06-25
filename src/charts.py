"""
Plotly chart builders.

Every function accepts a DataFrame and returns a Plotly Figure.
A graceful _empty() fallback is returned when the DataFrame is empty
so the app never crashes due to missing data.
"""

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
