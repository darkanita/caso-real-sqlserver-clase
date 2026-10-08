"""MLflow autenticado: métricas mínimas o trazas completas."""
from __future__ import annotations

import hashlib
import importlib
import os

from .agent import MAX_MODEL_CALLS, MAX_TOOL_CALLS
from .config import OUTPUT_DIR, SYSTEM_PROMPT, validate_mlflow_auth

EXPERIMENT = "military-resource-allocation-agent"


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class MlflowTracker:
    def __init__(self, enabled: bool, level: str):
        if level not in ("metrics", "traces"):
            raise ValueError("Nivel MLflow inválido.")
        self.enabled = enabled
        self.level = level
        self.mlflow = None
        self.langchain = None
        self.active = False
        self.run_id = None
        self.experiment_id = None
        self.tracking_uri = None

    def _end_run(self, status: str) -> None:
        try:
            self.mlflow.end_run(status=status)
        except UnicodeEncodeError:
            # MLflow ya cerró el run; solo falló al imprimir su emoji en cp1252.
            pass

    def start(self, *, question: str, backend, requested_by: str) -> None:
        if not self.enabled:
            return
        self.tracking_uri = validate_mlflow_auth()
        try:
            self.mlflow = importlib.import_module("mlflow")
            tracking = importlib.import_module("mlflow.tracking")
        except ModuleNotFoundError as exc:
            raise ValueError("MLflow no está instalado.") from exc
        self.mlflow.set_tracking_uri(self.tracking_uri)
        client = tracking.MlflowClient(tracking_uri=self.tracking_uri)
        experiment = client.get_experiment_by_name(EXPERIMENT)
        experiment_id = (
            experiment.experiment_id
            if experiment
            else client.create_experiment(EXPERIMENT)
        )
        run = self.mlflow.start_run(
            experiment_id=experiment_id,
            run_name=f"{backend.name}-{backend.model}",
        )
        self.run_id = run.info.run_id
        self.experiment_id = run.info.experiment_id
        self.active = True
        self.mlflow.log_params({
            "provider": backend.name,
            "model": backend.model,
            "database": "MilitaryResAllocDB",
            "schema": "dbo",
            "observability": self.level,
            "max_model_calls": MAX_MODEL_CALLS,
            "max_tool_calls": MAX_TOOL_CALLS,
            "question_sha256": sha256(question),
            "prompt_sha256": sha256(SYSTEM_PROMPT),
            "requested_by": requested_by,
        })
        self.mlflow.set_tags({
            "use_case": "military-resource-allocation",
            "data.classification": "synthetic-real-schema",
            "security.read_only": "true",
            "security.pii_policy": "aggregate-and-deny",
            "trace.created_by": requested_by,
            "trace.identity_assurance": "self-declared",
            "trace.mlflow_writer": os.environ["MLFLOW_TRACKING_USERNAME"],
        })
        self.mlflow.log_text(SYSTEM_PROMPT, "configuration/system-prompt.txt")
        if self.level == "traces":
            self.mlflow.log_text(question, "inputs/question.txt")
            self.langchain = importlib.import_module("mlflow.langchain")
            self.langchain.autolog(
                log_traces=True,
                run_tracer_inline=True,
                silent=True,
            )

    def finish(self, result: dict) -> None:
        if not self.enabled:
            return
        self.mlflow.log_metrics(result["metrics"])
        self.mlflow.set_tags({
            "tables_used": ",".join(result["tables"]),
            "run_status": "completed",
        })
        summary = {
            "model": result["model"],
            "metrics": result["metrics"],
            "tables": result["tables"],
            "requested_by": result["requested_by"],
            "mlflow_writer": os.environ["MLFLOW_TRACKING_USERNAME"],
        }
        if self.level == "traces":
            summary.update(answer=result["answer"], sql=result["sql"], rows=result["rows"])
            self.langchain.autolog(disable=True, silent=True)
        self.mlflow.log_dict(summary, "results/summary.json")
        self._end_run("FINISHED")
        self.active = False

    def fail(self, exc: BaseException) -> None:
        if not self.enabled or not self.active:
            return
        self.mlflow.set_tag("error_type", type(exc).__name__)
        if self.langchain is not None:
            self.langchain.autolog(disable=True, silent=True)
        self._end_run("FAILED")
        self.active = False

    def metadata(self) -> dict | None:
        if not self.run_id:
            return None
        return {
            "run_id": self.run_id,
            "experiment": EXPERIMENT,
            "url": (
                f"{self.tracking_uri}/#/experiments/"
                f"{self.experiment_id}/runs/{self.run_id}"
            ),
            "level": self.level,
        }
