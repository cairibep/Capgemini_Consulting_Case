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
    get_sales_by_state,
    get_seller_performance,
)

load_dotenv()

# ── Function registry ──────────────────────────────────────────────────────────

_TOOL_REGISTRY: dict[str, Any] = {
    "get_sales_by_category":    get_sales_by_category,
    "get_sales_by_state":       get_sales_by_state,
    "get_customer_segments":    get_customer_segments,
    "get_seller_performance":   get_seller_performance,
    "get_delivery_performance": get_delivery_performance,
    "get_business_overview":    get_business_overview,
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

_SYSTEM_INSTRUCTION = get_system_instruction_from_file("prompt.txt")

# ── Public API ─────────────────────────────────────────────────────────────────

def ask(question: str) -> dict:
    """
    Send a question to the Gemini agent and return a result dict:

        {
            "answer":       str,         # final natural-language response
            "tools_called": list[dict],  # [{name, args, result_preview}, ...]
        }

    Raises:
        ValueError: if GEMINI_API_KEY is not set.
        RuntimeError: if the model returns an unexpected finish reason.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY não encontrado. "
            "Adicione-o ao arquivo .env na raiz do projeto."
        )

    client = genai.Client(api_key=api_key)

    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=question)])
    ]
    tools_called: list[dict] = []

    # ── Function Calling loop ──────────────────────────────────────────────────
    for _ in range(10):  # safety cap: at most 10 model turns
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                tools=[_TOOLS],
                temperature=0.2,
            ),
            contents=contents,
        )

        candidate = response.candidates[0]

        fn_calls = [
            part.function_call
            for part in candidate.content.parts
            if part.function_call is not None
        ]

        if not fn_calls:
            # No more function calls — extract the final text answer
            answer = "".join(
                part.text
                for part in candidate.content.parts
                if hasattr(part, "text") and part.text
            ).strip()

            if not answer:
                answer = (
                    "Esta análise ainda não está disponível com segurança "
                    "com os dados atuais."
                )

            return {"answer": answer, "tools_called": tools_called}

        # Append the model's turn (with function calls) to the conversation
        contents.append(candidate.content)

        # Execute each function call and collect responses
        function_response_parts: list[types.Part] = []

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

            # Record for UI display (preview = first 3 rows if list)
            preview = result[:3] if isinstance(result, list) else result
            tools_called.append({
                "name":           fn_name,
                "args":           fn_args,
                "result_preview": preview,
            })

            function_response_parts.append(
                types.Part.from_function_response(
                    name=fn_name,
                    response={"result": json.dumps(result, default=str)},
                )
            )

        # Append tool results to the conversation
        contents.append(
            types.Content(role="user", parts=function_response_parts)
        )

    # Exceeded safety cap
    raise RuntimeError(
        "O agente excedeu o número máximo de chamadas de ferramentas "
        "sem produzir uma resposta final."
    )
