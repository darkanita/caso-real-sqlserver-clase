"""Orquestación reutilizable por CLI y web."""
from __future__ import annotations

import time

from trazas_lc import Trace, TraceCallback

import comun

from .agent import ask, create_sql_agent
from .config import MAX_QUESTION_LENGTH, make_backend, validate_actor
from .database import MilitaryDatabase
from .tracking import MlflowTracker


def execute(
    question: str,
    *,
    requested_by: str,
    backend_name: str,
    mlflow_enabled: bool = True,
    mlflow_level: str = "metrics",
) -> dict:
    question = question.strip()
    if not question or len(question) > MAX_QUESTION_LENGTH:
        raise ValueError("La pregunta está vacía o supera 2.000 caracteres.")
    requested_by = validate_actor(requested_by)
    backend = make_backend(backend_name)
    database = MilitaryDatabase()
    database.initialize()
    trace = Trace("caso_real_sqlserver", backend.name, backend.model)
    callback = TraceCallback(trace, "military-sql")
    tracker = MlflowTracker(mlflow_enabled, mlflow_level)
    started = time.perf_counter()
    try:
        tracker.start(
            question=question,
            backend=backend,
            requested_by=requested_by,
        )
        result = ask(
            create_sql_agent(comun.chat_model(backend), database),
            question,
            callbacks=[callback],
        )
        metrics = {
            "duration_seconds": round(time.perf_counter() - started, 3),
            "model_seconds": round(callback.model_seconds, 3),
            "model_calls": result["model_calls"],
            "tool_calls": callback.tool_calls,
            "input_tokens": callback.tokens["entrada"],
            "output_tokens": callback.tokens["salida"],
            "total_tokens": callback.tokens["total"],
            "rows": len(result["rows"]),
            "tables": len(result["tables"]),
        }
        output = {
            **result,
            "backend": backend.name,
            "model": backend.model,
            "requested_by": requested_by,
            "metrics": metrics,
        }
        trace.end(completed=True, tables=result["tables"])
        tracker.finish(output)
        output["mlflow"] = tracker.metadata()
        return output
    except Exception as exc:
        trace.end(completed=False, reason=type(exc).__name__)
        tracker.fail(exc)
        raise
