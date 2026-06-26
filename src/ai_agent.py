"""
Gemini Function Calling agent — AI Business Analyst persona.

Uses google-genai SDK (>=2.x) with a manual function-calling loop so the model
can call multiple tools in a single conversation turn before giving its final answer.
"""
from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from src.ai_tools import (
    get_business_overview,
    get_customer_segments,
    get_delivery_performance,
    get_sales_by_category,
    get_sales_by_city,
    get_sales_by_state,
    get_sales_by_state_category,
    get_sales_over_time,
    get_seller_performance,
    get_top_products,
)

load_dotenv()

# ── Function registry ──────────────────────────────────────────────────────────

_TOOL_REGISTRY: dict[str, Any] = {
    "get_sales_by_category":      get_sales_by_category,
    "get_sales_by_state":         get_sales_by_state,
    "get_customer_segments":      get_customer_segments,
    "get_seller_performance":     get_seller_performance,
    "get_delivery_performance":   get_delivery_performance,
    "get_business_overview":      get_business_overview,
    "get_sales_over_time":        get_sales_over_time,
    "get_sales_by_city":          get_sales_by_city,
    "get_sales_by_state_category": get_sales_by_state_category,
    "get_top_products":           get_top_products,
}

# ── Tool declarations (Gemini function schema) ─────────────────────────────────

_TOOLS = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="get_sales_by_category",
        description=(
            "Returns sales metrics aggregated by product category: "
            "revenue, orders count, items sold, average item value, "
            "average review score and late delivery rate. "
            "Use this for questions about which categories perform best or worst."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "limit": types.Schema(
                    type=types.Type.INTEGER,
                    description="Number of rows to return (1–50). Default 10.",
                ),
                "order_by": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Column to sort by, descending. "
                        "Allowed: revenue, orders_count, items_sold, "
                        "avg_review_score, late_rate."
                    ),
                ),
            },
        ),
    ),
    types.FunctionDeclaration(
        name="get_sales_by_state",
        description=(
            "Returns sales metrics aggregated by Brazilian state (UF): "
            "revenue, orders count, average order value, average review score "
            "and late delivery rate. "
            "Use this for geographical or regional analysis questions."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "limit": types.Schema(
                    type=types.Type.INTEGER,
                    description="Number of rows to return (1–50). Default 10.",
                ),
                "order_by": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Column to sort by, descending. "
                        "Allowed: revenue, orders_count, avg_order_value, "
                        "avg_review_score, late_rate."
                    ),
                ),
            },
        ),
    ),
    types.FunctionDeclaration(
        name="get_customer_segments",
        description=(
            "Returns all customer segments (VIP, High Value, Regular, Low Value) "
            "with headcount, total revenue, average LTV, average ticket, "
            "orders per customer and revenue share. "
            "Use this for questions about customer value, retention or segmentation."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={},
        ),
    ),
    types.FunctionDeclaration(
        name="get_seller_performance",
        description=(
            "Returns seller-level performance data including orders, revenue, "
            "review score, average delivery delay, late rate, health score "
            "and risk classification (At Risk / Watch / Healthy). "
            "Use this for questions about seller quality, risk or concentration."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "limit": types.Schema(
                    type=types.Type.INTEGER,
                    description="Number of sellers to return (1–50). Default 10.",
                ),
                "risk_level": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Optional filter by risk level. "
                        "Allowed: 'At Risk', 'Watch', 'Healthy'. "
                        "Omit to return top sellers regardless of risk."
                    ),
                ),
            },
        ),
    ),
    types.FunctionDeclaration(
        name="get_delivery_performance",
        description=(
            "Returns delivery performance split into on-time vs late orders: "
            "order count, average review score, average delay days, "
            "average delivery time and average order value per group. "
            "Use this for questions about logistics, delivery quality or "
            "the impact of delays on customer satisfaction."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={},
        ),
    ),
    types.FunctionDeclaration(
        name="get_sales_over_time",
        description=(
            "Returns monthly sales metrics in chronological order: "
            "revenue, orders, unique customers, average ticket, review score and late rate. "
            "Use this for questions about trends, seasonality, growth over time, "
            "or how the business evolved month by month."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "limit": types.Schema(
                    type=types.Type.INTEGER,
                    description="Number of months to return (1–50). Default 24.",
                ),
            },
        ),
    ),
    types.FunctionDeclaration(
        name="get_sales_by_city",
        description=(
            "Returns sales metrics aggregated by city, optionally filtered by state. "
            "Includes revenue, orders, average ticket, review score and late rate. "
            "Use this for city-level or intra-state geographic analysis."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "limit": types.Schema(
                    type=types.Type.INTEGER,
                    description="Number of cities to return (1–50). Default 15.",
                ),
                "order_by": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Column to sort by, descending. "
                        "Allowed: revenue, orders_count, avg_order_value, "
                        "avg_review_score, late_rate."
                    ),
                ),
                "state": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Optional 2-letter Brazilian state code to filter by "
                        "(e.g. 'SP', 'RJ', 'MG'). Omit for all states."
                    ),
                ),
            },
        ),
    ),
    types.FunctionDeclaration(
        name="get_sales_by_state_category",
        description=(
            "Returns sales metrics broken down by (state, category) pairs. "
            "When a state is provided, returns the top categories within that state. "
            "Use this for questions like 'which categories sell most in SP?' or "
            "'how do categories differ across regions?'"
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "state": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Optional 2-letter Brazilian state code to filter by "
                        "(e.g. 'SP', 'RJ', 'MG'). Omit for top pairs globally."
                    ),
                ),
                "limit": types.Schema(
                    type=types.Type.INTEGER,
                    description="Number of rows to return (1–50). Default 10.",
                ),
                "order_by": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Column to sort by, descending. "
                        "Allowed: revenue, orders_count, items_sold, "
                        "avg_review_score, late_rate."
                    ),
                ),
            },
        ),
    ),
    types.FunctionDeclaration(
        name="get_top_products",
        description=(
            "Returns top individual products by sales metrics, "
            "optionally filtered by category. "
            "Includes product_id, category, orders, items sold, revenue, "
            "average item value, review score and late rate. "
            "Use this for product-level analysis or to find star products within a category."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "limit": types.Schema(
                    type=types.Type.INTEGER,
                    description="Number of products to return (1–50). Default 10.",
                ),
                "order_by": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Column to sort by, descending. "
                        "Allowed: revenue, orders_count, items_sold, "
                        "avg_review_score, late_rate."
                    ),
                ),
                "category": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "Optional category name to filter (exact match, case-insensitive). "
                        "Omit to return top products across all categories."
                    ),
                ),
            },
        ),
    ),
    types.FunctionDeclaration(
        name="get_business_overview",
        description=(
            "Returns a high-level business snapshot across all views: "
            "total revenue, total orders, top category, top state, "
            "overall late delivery rate, count of at-risk sellers "
            "and VIP customer revenue share. "
            "Use this first for broad executive-level questions or "
            "when you need a general picture before diving deeper."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={},
        ),
    ),
])

# ── Persona / system instruction ───────────────────────────────────────────────
def get_system_instruction_from_file(file_path: str) -> str:
    with open(file_path, "r") as file:
        return file.read()

_SYSTEM_INSTRUCTION = get_system_instruction_from_file("./src/prompt.txt")

_BRIEF_INSTRUCTION = """
You are a data analyst. Call exactly one tool, then respond in 1-2 sentences only.
State the single most important finding: one specific number and its direct implication.
No section headers. No bullet points. No recommendations section.
Use the same language as the question (Portuguese or English).
"""

# ── Shared helpers ─────────────────────────────────────────────────────────────

def _make_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY não encontrado. "
            "Adicione-o ao arquivo .env na raiz do projeto."
        )
    return genai.Client(api_key=api_key)


def _gen_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=_SYSTEM_INSTRUCTION,
        tools=[_TOOLS],
        temperature=0.2,
    )


def _dispatch_fn_calls(
    fn_calls: list,
    tools_called: list[dict],
) -> list[types.Part]:
    """Execute all function calls and return a list of FunctionResponse Parts."""
    parts: list[types.Part] = []
    for fn_call in fn_calls:
        fn_name = fn_call.name
        fn_args = dict(fn_call.args) if fn_call.args else {}
        fn_impl = _TOOL_REGISTRY.get(fn_name)

        if fn_impl is None:
            result: Any = {"error": f"Unknown tool: {fn_name}"}
        else:
            try:
                result = fn_impl(**fn_args)
            except TypeError as exc:
                result = {"error": f"Bad arguments for {fn_name}: {exc}"}
            except Exception as exc:
                result = {"error": str(exc)}

        preview = result[:3] if isinstance(result, list) else result
        tools_called.append({"name": fn_name, "args": fn_args, "result_preview": preview})

        parts.append(
            types.Part.from_function_response(
                name=fn_name,
                response={"result": json.dumps(result, default=str)},
            )
        )
    return parts


# ── Public API ─────────────────────────────────────────────────────────────────

def ask_brief(question: str) -> dict:
    """
    One-shot agent call optimised for compact chart insight cards.
    Returns the same dict as ask() but uses a minimal system instruction
    that instructs the model to respond in 1-2 sentences with no section headers.
    """
    client = _make_client()
    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=question)])
    ]
    tools_called: list[dict] = []

    for _ in range(5):
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=_BRIEF_INSTRUCTION,
                tools=[_TOOLS],
                temperature=0.1,
            ),
            contents=contents,
        )
        candidate = response.candidates[0]

        fn_calls = [
            p.function_call
            for p in candidate.content.parts
            if p.function_call is not None
        ]

        if not fn_calls:
            answer = "".join(
                p.text for p in candidate.content.parts
                if hasattr(p, "text") and p.text
            ).strip() or "Dados insuficientes para gerar um insight."
            contents.append(candidate.content)
            return {"answer": answer, "tools_called": tools_called, "new_contents": contents}

        contents.append(candidate.content)
        fn_parts = _dispatch_fn_calls(fn_calls, tools_called)
        contents.append(types.Content(role="user", parts=fn_parts))

    return {"answer": "Dados insuficientes para gerar um insight.", "tools_called": tools_called, "new_contents": contents}


def ask(
    question: str,
    history: list[types.Content] | None = None,
) -> dict:
    """
    Send a question to the Gemini agent and return a result dict:

        {
            "answer":       str,
            "tools_called": list[dict],
            "new_contents": list[types.Content],  # full conversation for next turn
        }

    Pass ``history`` (the ``new_contents`` from a previous call) to enable
    multi-turn conversation.

    Raises:
        ValueError:  if GEMINI_API_KEY is not set.
        RuntimeError: if the safety cap of 10 turns is exceeded.
    """
    client = _make_client()
    contents: list[types.Content] = list(history) if history else []
    contents.append(types.Content(role="user", parts=[types.Part(text=question)]))
    tools_called: list[dict] = []

    for _ in range(10):
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=_gen_config(),
            contents=contents,
        )
        candidate = response.candidates[0]

        fn_calls = [
            p.function_call
            for p in candidate.content.parts
            if p.function_call is not None
        ]

        if not fn_calls:
            answer = "".join(
                p.text for p in candidate.content.parts
                if hasattr(p, "text") and p.text
            ).strip() or (
                "Esta análise ainda não está disponível com segurança "
                "com os dados atuais."
            )
            contents.append(candidate.content)
            return {"answer": answer, "tools_called": tools_called, "new_contents": contents}

        contents.append(candidate.content)
        fn_parts = _dispatch_fn_calls(fn_calls, tools_called)
        contents.append(types.Content(role="user", parts=fn_parts))

    raise RuntimeError(
        "O agente excedeu o número máximo de chamadas de ferramentas "
        "sem produzir uma resposta final."
    )


def ask_stream(
    question: str,
    history: list[types.Content] | None = None,
    metadata: dict | None = None,
):
    """
    Streaming variant. Yields text chunks from the final answer turn so the
    caller can pass this generator directly to ``st.write_stream()``.

    After the generator is exhausted, the ``metadata`` dict (if provided) will
    contain:
        - ``tools_called``: list of tool call records
        - ``new_contents``: full conversation list for the next turn
        - ``answer``:       complete answer text

    All intermediate function-calling turns are executed synchronously before
    streaming begins — streaming only applies to the final text response.

    Raises:
        ValueError:  if GEMINI_API_KEY is not set.
        RuntimeError: if the safety cap of 10 turns is exceeded.
    """
    if metadata is None:
        metadata = {}

    client = _make_client()
    contents: list[types.Content] = list(history) if history else []
    contents.append(types.Content(role="user", parts=[types.Part(text=question)]))
    tools_called: list[dict] = []

    # ── Function-calling turns (blocking) ─────────────────────────────────────
    for _ in range(10):
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=_gen_config(),
            contents=contents,
        )
        candidate = response.candidates[0]

        fn_calls = [
            p.function_call
            for p in candidate.content.parts
            if p.function_call is not None
        ]

        if not fn_calls:
            # This was the final turn — but arrived via generate_content, not
            # streaming. Yield its text and finish.
            answer = "".join(
                p.text for p in candidate.content.parts
                if hasattr(p, "text") and p.text
            ).strip() or (
                "Esta análise ainda não está disponível com segurança "
                "com os dados atuais."
            )
            contents.append(candidate.content)
            metadata["tools_called"]  = tools_called
            metadata["new_contents"]  = contents
            metadata["answer"]        = answer
            yield answer
            return

        contents.append(candidate.content)
        fn_parts = _dispatch_fn_calls(fn_calls, tools_called)
        contents.append(types.Content(role="user", parts=fn_parts))

        # Peek at the next turn: if it will have no more function calls, switch
        # to streaming for that final response.
        next_response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=_gen_config(),
            contents=contents,
        )
        next_candidate = next_response.candidates[0]
        next_fn_calls = [
            p.function_call
            for p in next_candidate.content.parts
            if p.function_call is not None
        ]

        if next_fn_calls:
            # Still more function calls — loop continues
            contents.append(next_candidate.content)
            fn_parts2 = _dispatch_fn_calls(next_fn_calls, tools_called)
            contents.append(types.Content(role="user", parts=fn_parts2))
            continue

        # Next turn is the final text response — stream it
        text_chunks: list[str] = []
        for chunk in client.models.generate_content_stream(
            model="gemini-2.5-flash",
            config=_gen_config(),
            contents=contents,
        ):
            for part in chunk.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    text_chunks.append(part.text)
                    yield part.text

        full_answer = "".join(text_chunks).strip() or (
            "Esta análise ainda não está disponível com segurança "
            "com os dados atuais."
        )
        contents.append(
            types.Content(role="model", parts=[types.Part(text=full_answer)])
        )
        metadata["tools_called"] = tools_called
        metadata["new_contents"] = contents
        metadata["answer"]       = full_answer
        return

    raise RuntimeError(
        "O agente excedeu o número máximo de chamadas de ferramentas "
        "sem produzir uma resposta final."
    )
