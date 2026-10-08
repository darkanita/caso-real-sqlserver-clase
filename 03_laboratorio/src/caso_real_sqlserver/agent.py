"""Agente LangChain con descubrimiento progresivo y SQL de solo lectura."""
from __future__ import annotations

import json

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from .config import SYSTEM_PROMPT

MAX_MODEL_CALLS = 8
MAX_TOOL_CALLS = 7


def create_tools(database):
    @tool("search_schema")
    def search_schema(term: str) -> dict:
        """Busca tablas y columnas por concepto; úsala antes de escribir SQL."""
        return {"ok": True, **database.catalog.search(term)}

    @tool("describe_table")
    def describe_table(table_name: str) -> dict:
        """Describe columnas seguras y relaciones de una tabla."""
        try:
            return {"ok": True, **database.catalog.describe(table_name)}
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

    @tool("run_readonly_sql")
    def run_readonly_sql(sql: str) -> dict:
        """Ejecuta un SELECT validado; devuelve máximo 50 filas agregadas."""
        try:
            return database.query(sql)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

    return [search_schema, describe_table, run_readonly_sql]


def create_sql_agent(llm, database):
    return create_agent(
        llm,
        create_tools(database),
        system_prompt=SYSTEM_PROMPT,
        middleware=[
            ToolCallLimitMiddleware(run_limit=MAX_TOOL_CALLS, exit_behavior="end"),
            ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS, exit_behavior="end"),
        ],
    )


def ask(agent, question: str, callbacks=()) -> dict:
    final = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        {"recursion_limit": 60, "callbacks": list(callbacks)},
    )
    messages = final["messages"]
    sql_queries: list[str] = []
    tool_results: list[dict] = []
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls or []:
                if call["name"] == "run_readonly_sql":
                    sql_queries.append(call["args"].get("sql", ""))
        if isinstance(message, ToolMessage):
            try:
                content = json.loads(message.content)
            except (TypeError, ValueError):
                content = {"ok": False, "error": str(message.content)}
            tool_results.append({"name": message.name, **content})
    successful = [
        item
        for item in tool_results
        if item["name"] == "run_readonly_sql" and item.get("ok")
    ]
    content = messages[-1].content if messages else ""
    return {
        "answer": content if isinstance(content, str) else str(content),
        "sql": sql_queries[-1] if sql_queries else None,
        "rows": successful[-1]["rows"] if successful else [],
        "tables": successful[-1].get("tables", []) if successful else [],
        "tool_results": tool_results,
        "model_calls": sum(isinstance(message, AIMessage) for message in messages),
    }

