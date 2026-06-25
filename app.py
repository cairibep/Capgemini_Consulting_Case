"""
Olist Analytics Dashboard
Consulting Case · Data & AI

Run with:
    streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Olist Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

import pandas as pd

from src.db import (
    get_filter_options,
    load_items_enriched,
    load_orders_enriched,
    load_view,
)
from src.charts import (
    category_share_treemap,
    customer_segments_donut,
    delivery_kpi_bars,
    revenue_by_category,
    revenue_by_state,
    revenue_over_time,
    seller_risk_bars,
)
from src.utils import fmt_currency, fmt_number, fmt_pct, revenue_by_month

# ── Global styles ──────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
    [data-testid="stMetricLabel"] { font-size: 0.85rem; color: #666; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 📊 Olist Analytics")
    st.caption("Consulting Case · Data & AI")
    st.divider()

    page = st.radio(
        "Página",
        ["Executive Overview", "Produtos & Clientes", "AI Business Analyst"],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown("### Filtros")

    opts = get_filter_options()

    # Date range
    min_date = pd.to_datetime(opts["min_date"]).date() if opts["min_date"] else None
    max_date = pd.to_datetime(opts["max_date"]).date() if opts["max_date"] else None

    if min_date and max_date:
        date_range = st.date_input(
            "Período",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            format="DD/MM/YYYY",
        )
        date_start = str(date_range[0]) if len(date_range) > 0 else None
        date_end = str(date_range[1]) if len(date_range) > 1 else None
    else:
        date_start = date_end = None
        st.info("Datas indisponíveis.")

    # State filter
    selected_states = st.multiselect(
        "Estado (UF)",
        opts["states"],
        placeholder="Todos os estados",
    )

    # Category filter
    selected_cats = st.multiselect(
        "Categoria",
        opts["categories"],
        placeholder="Todas as categorias",
    )

    st.divider()
    if st.button("Limpar filtros", use_container_width=True):
        st.rerun()

# Convert to tuples so Streamlit cache keys are hashable
states_param = tuple(selected_states) if selected_states else None
cats_param = tuple(selected_cats) if selected_cats else None


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

orders = load_orders_enriched(date_start, date_end, states_param)
items = load_items_enriched(date_start, date_end, states_param, cats_param)

# When a category filter is active, restrict orders to those that contain at
# least one item from the selected categories (semi-join via order_id).
# orders_enriched has no category column, so this cross-table filter must be
# applied in Python after both DataFrames are loaded.
if cats_param and not items.empty:
    valid_order_ids = items["order_id"].unique()
    orders = orders[orders["order_id"].isin(valid_order_ids)]

# Pre-aggregated views — not filtered by sidebar (already aggregated)
vw_category = load_view("vw_sales_by_category")
vw_state = load_view("vw_sales_by_state")
vw_segments = load_view("vw_customer_segments")
vw_delivery = load_view("vw_delivery_performance")
vw_sellers = load_view("vw_seller_performance")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 · Executive Overview
# ══════════════════════════════════════════════════════════════════════════════

if page == "Executive Overview":
    st.title("Executive Overview")
    st.caption("Visão consolidada de performance · Dataset Olist Brazilian E-Commerce")

    # ── KPI row ────────────────────────────────────────────────────────────────
    total_revenue = orders["order_total"].sum() if not orders.empty else 0.0
    total_orders = orders["order_id"].nunique() if not orders.empty else 0
    avg_ticket = (total_revenue / total_orders) if total_orders > 0 else 0.0
    unique_customers = orders["customer_unique_id"].nunique() if not orders.empty else 0

    # Delivery rate
    if not orders.empty and "is_delivered" in orders.columns:
        delivered_rate = orders["is_delivered"].mean()
    else:
        delivered_rate = 0.0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Receita Total", fmt_currency(total_revenue))
    col2.metric("Pedidos", fmt_number(total_orders))
    col3.metric("Ticket Médio", fmt_currency(avg_ticket))
    col4.metric("Clientes Únicos", fmt_number(unique_customers))
    col5.metric("Taxa de Entrega", fmt_pct(delivered_rate))

    st.divider()

    # ── Revenue over time ──────────────────────────────────────────────────────
    monthly = revenue_by_month(orders)
    st.plotly_chart(revenue_over_time(monthly), use_container_width=True)

    st.divider()

    # ── Category + State ───────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        # When a filter is active, aggregate from base items table for accuracy;
        # otherwise use the pre-aggregated view for speed
        if states_param or cats_param or date_start:
            cat_data = (
                items.groupby("category_name", as_index=False)
                .agg(revenue=("item_total", "sum"), orders_count=("order_id", "nunique"))
                if not items.empty
                else pd.DataFrame()
            )
        else:
            cat_data = vw_category
        st.plotly_chart(revenue_by_category(cat_data), use_container_width=True)

    with col_b:
        if states_param or date_start:
            state_data = (
                orders.groupby("customer_state", as_index=False)
                .agg(revenue=("order_total", "sum"), orders_count=("order_id", "nunique"))
                if not orders.empty
                else pd.DataFrame()
            )
        else:
            state_data = vw_state
        st.plotly_chart(revenue_by_state(state_data), use_container_width=True)

    st.divider()

    # ── Customer segments + Delivery + Sellers ─────────────────────────────────
    col_c, col_d, col_e = st.columns(3)
    with col_c:
        st.plotly_chart(customer_segments_donut(vw_segments), use_container_width=True)
    with col_d:
        st.plotly_chart(delivery_kpi_bars(vw_delivery), use_container_width=True)
    with col_e:
        st.plotly_chart(seller_risk_bars(vw_sellers), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 · Produtos & Clientes
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Produtos & Clientes":
    st.title("Produtos & Clientes")

    # ── Category ranking ───────────────────────────────────────────────────────
    st.subheader("Ranking de Categorias por Receita")

    if not items.empty:
        cat_agg = (
            items.groupby("category_name", as_index=False)
            .agg(
                revenue=("item_total", "sum"),
                orders=("order_id", "nunique"),
                avg_review=("review_score", "mean"),
                late_rate=("is_late", "mean"),
            )
            .sort_values("revenue", ascending=False)
            .reset_index(drop=True)
        )
        total_rev = cat_agg["revenue"].sum()
        cat_agg["share_%"] = (cat_agg["revenue"] / total_rev * 100).round(2)
        cat_agg["cumulative_%"] = cat_agg["share_%"].cumsum().round(2)

        # Treemap
        st.plotly_chart(category_share_treemap(cat_agg), use_container_width=True)

        # Pareto insight
        n_pareto = max(1, round(len(cat_agg) * 0.2))
        top20 = cat_agg.head(n_pareto)
        pareto_share = top20["share_%"].sum()
        st.info(
            f"📌 As **top {len(top20)} categorias** (~20% do total) "
            f"representam **{pareto_share:.1f}%** da receita — "
            f"regra de Pareto {'confirmada ✅' if pareto_share >= 70 else 'parcialmente observada'}."
        )

        # Detailed table
        st.subheader("Tabela Detalhada")
        display = cat_agg.rename(
            columns={
                "category_name": "Categoria",
                "revenue": "Receita (R$)",
                "orders": "Pedidos",
                "avg_review": "Nota Média",
                "late_rate": "Taxa Atraso",
                "share_%": "Share (%)",
                "cumulative_%": "Acumulado (%)",
            }
        )
        st.dataframe(
            display.style.format(
                {
                    "Receita (R$)": "R$ {:,.2f}",
                    "Nota Média": "{:.2f}",
                    "Taxa Atraso": "{:.1%}",
                    "Share (%)": "{:.1f}%",
                    "Acumulado (%)": "{:.1f}%",
                }
            ),
            use_container_width=True,
            height=440,
        )
    else:
        st.warning("Nenhum dado disponível com os filtros selecionados.")

    # ── Customer segments ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("Segmentos de Clientes")

    col_seg, col_chart = st.columns([3, 2])

    with col_seg:
        if not vw_segments.empty:
            display_seg = vw_segments.rename(
                columns={
                    "customer_segment": "Segmento",
                    "customers_count": "Clientes",
                    "revenue": "Receita (R$)",
                    "avg_customer_lifetime_value": "LTV Médio",
                    "avg_order_value": "Ticket Médio",
                    "avg_orders_per_customer": "Pedidos/Cliente",
                    "revenue_share": "Share Receita",
                }
            )
            st.dataframe(
                display_seg.style.format(
                    {
                        "Receita (R$)": "R$ {:,.2f}",
                        "LTV Médio": "R$ {:,.2f}",
                        "Ticket Médio": "R$ {:,.2f}",
                        "Pedidos/Cliente": "{:.2f}",
                        "Share Receita": "{:.1%}",
                    }
                ),
                use_container_width=True,
            )
        else:
            st.warning("View `vw_customer_segments` indisponível.")

    with col_chart:
        st.plotly_chart(customer_segments_donut(vw_segments), use_container_width=True)

    # ── Seller performance ─────────────────────────────────────────────────────
    st.divider()
    st.subheader("Performance de Vendedores")

    col_sell_a, col_sell_b = st.columns([2, 3])

    with col_sell_a:
        st.plotly_chart(seller_risk_bars(vw_sellers), use_container_width=True)

    with col_sell_b:
        if not vw_sellers.empty:
            display_sell = (
                vw_sellers.sort_values("revenue", ascending=False)
                .head(20)
                .rename(
                    columns={
                        "seller_id": "Vendedor",
                        "orders_count": "Pedidos",
                        "items_sold": "Itens",
                        "revenue": "Receita (R$)",
                        "avg_review_score": "Nota Média",
                        "late_rate": "Taxa Atraso",
                        "seller_health_score": "Health Score",
                        "seller_risk_level": "Risco",
                    }
                )[
                    [
                        "Vendedor", "Receita (R$)", "Pedidos",
                        "Nota Média", "Taxa Atraso", "Health Score", "Risco",
                    ]
                ]
            )
            st.caption("Top 20 vendedores por receita")
            st.dataframe(
                display_sell.style.format(
                    {
                        "Receita (R$)": "R$ {:,.2f}",
                        "Nota Média": "{:.2f}",
                        "Taxa Atraso": "{:.1%}",
                        "Health Score": "{:.3f}",
                    }
                ),
                use_container_width=True,
                height=380,
            )
        else:
            st.warning("View `vw_seller_performance` indisponível.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 · AI Business Analyst
# ══════════════════════════════════════════════════════════════════════════════

elif page == "AI Business Analyst":
    st.title("🤖 AI Business Analyst")
    st.markdown(
        "> **Persona:** Analista sênior especializado em e-commerce brasileiro.  \n"
        "> Cita evidências numéricas dos dados Olist e sugere ações concretas."
    )
    st.divider()

    with st.expander("💡 Exemplos de perguntas", expanded=False):
        st.markdown(
            "- *Quais categorias têm maior potencial de crescimento?*\n"
            "- *Qual é a relação entre atraso de entrega e nota do cliente?*\n"
            "- *Qual segmento de cliente concentra mais receita e como retê-los?*\n"
            "- *Quais estados têm o maior ticket médio?*\n"
            "- *Quantos vendedores estão em situação de risco?*\n"
            "- *Dê um panorama geral do negócio.*"
        )

    question = st.text_area(
        "Sua pergunta",
        placeholder="Ex: Qual a categoria com maior receita e qual o risco de entrega nela?",
        height=120,
    )

    col_btn, col_opt = st.columns([2, 3])
    with col_btn:
        submit = st.button(
            "Analisar",
            type="primary",
            disabled=not (question or "").strip(),
        )
    with col_opt:
        show_tools = st.checkbox("Mostrar tools chamadas e evidências", value=False)

    if submit and question.strip():
        with st.spinner("Consultando dados e gerando análise…"):
            try:
                from src.ai_agent import ask as ai_ask
                result = ai_ask(question.strip())
                error_msg = None
            except ValueError as exc:
                result = None
                error_msg = f"Configuração: {exc}"
            except RuntimeError as exc:
                result = None
                error_msg = f"Erro no agente: {exc}"
            except Exception as exc:
                result = None
                error_msg = f"Erro inesperado: {exc}"

        if error_msg:
            st.error(error_msg)
        elif result:
            st.divider()
            st.markdown("### Análise")
            st.markdown(result["answer"])

            if show_tools and result.get("tools_called"):
                st.divider()
                st.markdown("#### Tools chamadas")
                for i, call in enumerate(result["tools_called"], 1):
                    label = f"`{call['name']}`"
                    if call["args"]:
                        label += f" — args: `{call['args']}`"
                    with st.expander(f"{i}. {label}"):
                        st.json(call["result_preview"])
