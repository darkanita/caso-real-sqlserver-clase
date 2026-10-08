"""CLI del agente real de asignación de recursos."""
from __future__ import annotations

import argparse
import getpass
import json
import os

from .config import BACKEND_NAMES, EXAMPLE_QUESTIONS, load_config
from .service import execute


def main() -> int:
    load_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default=EXAMPLE_QUESTIONS[0])
    parser.add_argument(
        "--user",
        default=os.environ.get("AGENT_USER") or getpass.getuser(),
        help="Usuario solicitante registrado en MLflow.",
    )
    parser.add_argument(
        "--backend",
        choices=BACKEND_NAMES,
        default=os.environ.get("LLM_BACKEND", "groq"),
    )
    parser.add_argument("--no-mlflow", action="store_true")
    parser.add_argument(
        "--mlflow-level",
        choices=("metrics", "traces"),
        default="metrics",
    )
    args = parser.parse_args()
    try:
        result = execute(
            args.question,
            requested_by=args.user,
            backend_name=args.backend,
            mlflow_enabled=not args.no_mlflow,
            mlflow_level=args.mlflow_level,
        )
    except Exception as exc:
        parser.exit(2, f"ERROR: {type(exc).__name__}: {exc}\n")
    print(result["answer"])
    print("\nSQL:")
    print(result["sql"] or "Sin consulta SQL.")
    print("\nMétricas:")
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    if result["mlflow"]:
        print(f"\nMLflow: {result['mlflow']['url']}")
    return 0
