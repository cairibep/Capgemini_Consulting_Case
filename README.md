Dataset: Brazilian E-Commerce Public Dataset by Olist
Link: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

python --version

python -m venv .venv

.\.venv\Scripts\Activate.ps1 (Windows)

streamlit run app.py

http://localhost:8501

# Olist Consulting ETL

ETL em Python para carregar o dataset público da Olist em PostgreSQL via Docker, criar métricas derivadas e publicar views analíticas prontas para dashboard ou consultas por IA.

## Estrutura

```text
etl/
├── config.py          # caminhos, conexão e schema
├── extract.py         # leitura dos CSVs
├── transform.py       # limpeza, métricas e agregações
├── load.py            # carga das tabelas no PostgreSQL
├── create_views.py    # views analíticas
└── run_etl.py         # orquestração
```

## Transformações implementadas

- Conversão de `order_purchase_timestamp`, `order_delivered_customer_date` e `order_estimated_delivery_date` para `datetime`.
- Preservação de nulos em entregas não concluídas, com `is_delivered = delivered_date.notnull()`.
- Categoria final com lógica de `COALESCE(product_category_name_english, product_category_name)`.
- Métricas de entrega: `delivery_delay_days`, `delivery_time_days`, `is_late`.
- Valor total por pedido usando pagamentos e valor por item usando `price + freight_value`.
- Segmentação de clientes por `customer_lifetime_value`: `VIP`, `High Value`, `Regular`, `Low Value`.
- `seller_health_score` combinando receita, avaliação e atraso.
- Métricas geográficas por estado via view.
- Relação entre atraso e satisfação via view.

## Como rodar

1. Copie o exemplo de ambiente:

```powershell
Copy-Item .env.example .env
```

2. Suba o PostgreSQL:

```powershell
docker compose up -d
```

3. Crie e ative o ambiente Python:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

4. Rode o ETL:

```powershell
python -m etl.run_etl
```

O projeto usa `psycopg` v3 com SQLAlchemy e `COPY FROM STDIN` para carregar os DataFrames com boa performance.

Por padrão, `DATA_DIR` aponta para a pasta extraída neste workspace:

```text
../../work/consulting_case/Consulting_Case/data
```

Se mover o projeto, ajuste `DATA_DIR` no `.env` para o diretório que contém os CSVs.

## Tabelas carregadas

- `analytics.orders_enriched`
- `analytics.order_items_enriched`
- `analytics.customer_segments`
- `analytics.seller_performance`

## Views para IA e dashboard

- `analytics.vw_sales_by_category`
- `analytics.vw_sales_by_state`
- `analytics.vw_seller_performance`
- `analytics.vw_customer_segments`
- `analytics.vw_delivery_performance`

## Exemplos de perguntas

```sql
SELECT * FROM analytics.vw_delivery_performance;

SELECT *
FROM analytics.vw_seller_performance
WHERE seller_risk_level = 'At Risk'
ORDER BY seller_health_score ASC;

SELECT *
FROM analytics.vw_customer_segments
ORDER BY revenue DESC;
```

---

## Dashboard Streamlit

### Pré-requisitos

O ETL já deve ter sido executado e o banco PostgreSQL deve estar rodando (`docker compose up -d`).

### Execução

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

O dashboard abre em `http://localhost:8501`.

### Estrutura do dashboard

```text
app.py              # ponto de entrada
src/
├── __init__.py
├── db.py           # conexão, queries e cache
├── charts.py       # gráficos Plotly
└── utils.py        # formatação e agregações
```

### Páginas

| Página | Conteúdo |
|---|---|
| **Executive Overview** | KPIs (receita, pedidos, ticket médio, clientes), receita mensal, top categorias, receita por estado, segmentos de clientes, pedidos no prazo vs atrasados, risco de vendedores |
| **Produtos & Clientes** | Treemap de participação por categoria, tabela detalhada filtrável com análise de Pareto, segmentos de clientes, top 20 vendedores por receita |
| **AI Business Analyst** | Interface preparada para integração com LLM (Text-to-SQL + RAG) |

### Filtros disponíveis (sidebar)

| Filtro | Campo base |
|---|---|
| Período | `orders_enriched.order_purchase_timestamp` |
| Estado (UF) | `orders_enriched.customer_state` |
| Categoria | `order_items_enriched.category_name` |

Quando filtros estão ativos, as consultas são direcionadas às tabelas base para precisão.
Sem filtros, as views pré-agregadas são usadas para melhor performance.