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
    category_quality_scatter,
    category_share_treemap,
    customer_segments_donut,
    delivery_kpi_bars,
    revenue_by_category,
    revenue_by_state,
    revenue_over_time,
    seller_risk_bars,
    state_category_heatmap,
)
from src.utils import fmt_currency, fmt_number, fmt_pct, revenue_by_month

# ── Global styles ──────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    [data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
    [data-testid="stMetricLabel"] { font-size: 0.85rem; color: #666; }

    /* AI insight icon buttons — emoji in the narrow rightmost column */
    div[data-testid="stColumn"]:last-of-type div[data-testid="stButton"] > button > p {
        font-size: 1.55rem !important;
        line-height: 1.1  !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

_PAGES = ["Executive Overview", "Produtos & Clientes", "AI Business Analyst"]

# Navigate programmatically when a chart insight "Aprofundar" button is clicked
if "navigate_to" in st.session_state:
    st.session_state["_page_radio"] = st.session_state.pop("navigate_to")

with st.sidebar:
    st.markdown("## 📊 Olist Analytics")
    st.caption("Consulting Case · Data & AI")
    st.divider()

    page = st.radio(
        "Página",
        _PAGES,
        key="_page_radio",
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
vw_category        = load_view("vw_sales_by_category")
vw_state           = load_view("vw_sales_by_state")
vw_segments        = load_view("vw_customer_segments")
vw_delivery        = load_view("vw_delivery_performance")
vw_sellers         = load_view("vw_seller_performance")
vw_state_category  = load_view("vw_sales_by_state_category")


# ── AI chart insight helpers ───────────────────────────────────────────────────

@st.dialog("💡 Insight IA")
def _show_insight_dialog(key: str, question: str) -> None:
    """
    Modal dialog — executes only when called explicitly (never on page load).
    Generates the insight on first call; shows cached result on subsequent calls.
    Closes when the user clicks outside (native Streamlit dialog behavior).
    """
    cache_key = f"_insight_{key}"
    if cache_key not in st.session_state:
        with st.spinner("Analisando…"):
            try:
                from src.ai_agent import ask_brief as _ai_brief
                st.session_state[cache_key] = _ai_brief(question)
            except Exception as exc:
                st.session_state[cache_key] = {
                    "answer": f"Erro ao gerar insight: {exc}",
                    "tools_called": [],
                }

    st.markdown(st.session_state[cache_key]["answer"])
    st.divider()
    if st.button("💬 Aprofundar no AI Business Analyst →", use_container_width=True):
        st.session_state["navigate_to"] = "AI Business Analyst"
        st.session_state["ai_prefill"]  = question
        st.rerun()


def _insight_header(key: str, question: str, title: str = "") -> None:
    """Render [section title] + [🤖 button] on the same row."""
    col_t, col_b = st.columns([11, 1])
    with col_t:
        if title:
            st.subheader(title)
    with col_b:
        if st.button("🤖", key=f"_ibtn_{key}", help="Insight IA", use_container_width=True):
            _show_insight_dialog(key, question)


def _insight_result(key: str) -> None:
    """No-op — kept for call-site compatibility."""
    pass


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
    _insight_header(
        "p1_trend",
        "Como foi a evolução da receita ao longo do tempo? Há sazonalidade ou tendência de crescimento clara?",
        title="Receita ao Longo do Tempo",
    )
    monthly = revenue_by_month(orders)
    st.plotly_chart(revenue_over_time(monthly), use_container_width=True)
    _insight_result("p1_trend")

    st.divider()

    # ── Category + State ───────────────────────────────────────────────────────
    _insight_header(
        "p1_cat_state",
        "Quais categorias e estados lideram em receita? Onde há maior oportunidade de crescimento geográfico ou por categoria?",
        title="Vendas por Categoria e Estado",
    )
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

    _insight_result("p1_cat_state")

    st.divider()

    # ── State × Category heatmap ───────────────────────────────────────────────
    _insight_header(
        "p1_heatmap",
        "Há padrões regionais de preferência de categoria? Quais combinações estado-categoria têm maior potencial inexplorado?",
        title="Receita por Estado × Categoria",
    )
    hm_col1, hm_col2, hm_col3 = st.columns([2, 2, 3])
    with hm_col1:
        hm_top_cats = st.slider("Top categorias", 5, 20, 12, key="hm_cats")
    with hm_col2:
        hm_top_states = st.slider("Top estados", 5, 27, 15, key="hm_states")
    with hm_col3:
        hm_normalize = st.toggle(
            "Normalizar por estado (% da receita do estado)",
            value=False,
            key="hm_norm",
            help="Ativado: cor mostra participação de cada categoria na receita do estado — remove efeito SP. "
                 "Desativado: cor em escala log da receita absoluta.",
        )
    st.plotly_chart(
        state_category_heatmap(
            vw_state_category,
            top_n_cats=hm_top_cats,
            top_n_states=hm_top_states,
            normalize=hm_normalize,
        ),
        use_container_width=True,
    )
    _insight_result("p1_heatmap")

    st.divider()

    # ── Customer segments + Delivery + Sellers ─────────────────────────────────
    _insight_header(
        "p1_operations",
        "Qual é o impacto dos atrasos de entrega na satisfação dos clientes e como está a saúde geral da base de vendedores?",
        title="Clientes · Entregas · Vendedores",
    )
    col_c, col_d, col_e = st.columns(3)
    with col_c:
        st.plotly_chart(customer_segments_donut(vw_segments), use_container_width=True)
    with col_d:
        st.plotly_chart(delivery_kpi_bars(vw_delivery), use_container_width=True)
    with col_e:
        st.plotly_chart(seller_risk_bars(vw_sellers), use_container_width=True)

    _insight_result("p1_operations")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 · Produtos & Clientes
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Produtos & Clientes":
    st.title("Produtos & Clientes")

    # ── Category ranking ───────────────────────────────────────────────────────
    _insight_header(
        "p2_categories",
        "Quais categorias têm maior receita e qual a relação entre volume de vendas e qualidade de entrega em cada uma?",
        title="Ranking de Categorias por Receita",
    )

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

        _insight_result("p2_categories")

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

    # ── Operational quality scatter ────────────────────────────────────────────
    st.divider()
    _insight_header(
        "p2_scatter",
        "Quais categorias têm ao mesmo tempo alta taxa de atraso e baixa satisfação? O que esses gargalos operacionais têm em comum?",
        title="Qualidade Operacional — Nota Média vs Taxa de Atraso",
    )
    st.plotly_chart(category_quality_scatter(vw_category), use_container_width=True)
    st.caption(
        "Cada bolha é uma categoria. Tamanho = receita. "
        "Linhas tracejadas indicam a mediana de cada eixo. "
        "Quadrante inferior direito = alertas operacionais prioritários."
    )
    _insight_result("p2_scatter")

    # ── Customer segments ──────────────────────────────────────────────────────
    st.divider()
    _insight_header(
        "p2_segments",
        "O que a segmentação de clientes revela sobre concentração de receita? Quais estratégias de retenção são mais urgentes?",
        title="Segmentos de Clientes",
    )

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

    _insight_result("p2_segments")

    # ── Seller performance ─────────────────────────────────────────────────────
    st.divider()
    _insight_header(
        "p2_sellers",
        "Quantos vendedores estão em risco e o que o health score revela sobre a qualidade da base de parceiros?",
        title="Performance de Vendedores",
    )

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

    _insight_result("p2_sellers")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 · AI Business Analyst
# ══════════════════════════════════════════════════════════════════════════════

elif page == "AI Business Analyst":
    from src.ai_agent import ask_stream as _ask_stream

    st.title("🤖 AI Business Analyst")

    # ── Session state ──────────────────────────────────────────────────────────
    if "ai_messages" not in st.session_state:
        # Each entry: {"role": "user"|"assistant", "content": str, "tools_called": list}
        st.session_state.ai_messages = []
    if "ai_history" not in st.session_state:
        # List of types.Content objects — passed to ask_stream for multi-turn
        st.session_state.ai_history = []

    # ── Toolbar ────────────────────────────────────────────────────────────────
    col_info, col_opt, col_clear = st.columns([4, 2, 2])
    with col_info:
        st.caption("Analista sênior de e-commerce · cita evidências numéricas · sugere ações")
    with col_opt:
        show_tools = st.checkbox("Mostrar tools", value=False)
    with col_clear:
        if st.button("Limpar conversa", use_container_width=True):
            st.session_state.ai_messages = []
            st.session_state.ai_history  = []
            st.rerun()

    # ── Example prompts (hidden when conversation has messages or prefill pending) ─
    if not st.session_state.ai_messages and "ai_prefill" not in st.session_state:
        with st.expander("💡 Exemplos de perguntas", expanded=True):
            st.markdown(
                "- *Dê um panorama geral do negócio.*\n"
                "- *Quais categorias têm maior potencial de crescimento?*\n"
                "- *Qual é a relação entre atraso de entrega e nota do cliente?*\n"
                "- *Qual segmento concentra mais receita e como retê-los?*\n"
                "- *Quais estados têm o maior ticket médio?*\n"
                "- *Quantos vendedores estão em situação de risco?*"
            )

    st.divider()

    # ── Render conversation history ────────────────────────────────────────────
    def _render_tools(tools_called: list) -> None:
        with st.expander(f"🔧 {len(tools_called)} tool(s) chamada(s)"):
            for i, call in enumerate(tools_called, 1):
                label = f"`{call['name']}`"
                if call["args"]:
                    label += f" — `{call['args']}`"
                with st.expander(f"{i}. {label}"):
                    st.json(call["result_preview"])

    for msg in st.session_state.ai_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if show_tools and msg["role"] == "assistant" and msg.get("tools_called"):
                _render_tools(msg["tools_called"])

    # ── Chat input (or auto-execute prefill from chart insights) ───────────────
    # ai_prefill is set when the user clicks "Aprofundar" on a chart insight card.
    # It is consumed here exactly once so subsequent reruns don't re-execute it.
    prefill = st.session_state.pop("ai_prefill", None)
    typed   = st.chat_input("Pergunte sobre o negócio Olist…")
    question_to_process = typed or prefill

    if question_to_process:

        # Show user bubble immediately
        st.session_state.ai_messages.append(
            {"role": "user", "content": question_to_process, "tools_called": []}
        )
        with st.chat_message("user"):
            st.markdown(question_to_process)

        # Stream assistant response
        with st.chat_message("assistant"):
            metadata: dict = {}
            try:
                response_text = st.write_stream(
                    _ask_stream(
                        question_to_process,
                        history=st.session_state.ai_history,
                        metadata=metadata,
                    )
                )
            except ValueError as exc:
                st.error(f"Configuração: {exc}")
                response_text = None
            except RuntimeError as exc:
                st.error(f"Erro no agente: {exc}")
                response_text = None
            except Exception as exc:
                st.error(f"Erro inesperado: {exc}")
                response_text = None

            if response_text:
                # Persist to session state
                st.session_state.ai_history = metadata.get(
                    "new_contents", st.session_state.ai_history
                )
                st.session_state.ai_messages.append({
                    "role":         "assistant",
                    "content":      response_text,
                    "tools_called": metadata.get("tools_called", []),
                })
                if show_tools and metadata.get("tools_called"):
                    _render_tools(metadata["tools_called"])
