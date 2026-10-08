"""Configuración del caso real sin credenciales en el código."""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

import reuso  # noqa: F401
from model import BACKEND_NAMES, load_local_env, make_backend
from settings import OUTPUTS

DATABASE_NAME = "MilitaryResAllocDB"
SCHEMA_NAME = "dbo"
PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = OUTPUTS / "caso_real_sqlserver"
WEB_HTML = PROJECT_DIR / "web.html"
MAX_ROWS = 50
QUERY_TIMEOUT_SECONDS = 10
MAX_QUESTION_LENGTH = 2_000

EXAMPLE_QUESTIONS = (
    "¿Cuántas personas hay por estado laboral?",
    "Muéstrame los 10 grados con más personal.",
    "¿Cuántos hombres y mujeres hay por grado?",
    "¿Cuál es el total solicitado en las solicitudes de personal?",
    "¿Cuántas proyecciones existen por año?",
)

SYSTEM_PROMPT = """Eres un analista de planeación y asignación de personal militar.

La base tiene más de 100 tablas. Trabaja de forma progresiva:
1. Usa search_schema con conceptos de la pregunta; no inventes tablas ni columnas.
2. Usa describe_table cuando necesites relaciones o tipos.
3. Usa run_readonly_sql únicamente con una consulta SELECT para SQL Server.
4. Para Personnel y otras tablas de personas, entrega solo resultados agregados.
5. Nunca solicites ni muestres identificación, nombres personales, teléfonos, correos,
   direcciones, fechas de nacimiento ni documentos.
6. Usa nombres explícitos de columnas y alias claros; evita SELECT *.
7. Responde en español, cita el resultado numérico y explica brevemente el criterio.
8. Si la política rechaza una consulta, no intentes eludirla.
"""


def load_config() -> None:
    load_local_env()


def connection_string() -> str:
    value = os.environ.get("MILITARY_SQLSERVER_CONNECTION_STRING", "").strip()
    if not value:
        raise ValueError(
            "Falta MILITARY_SQLSERVER_CONNECTION_STRING en 03_laboratorio\\.env."
        )
    return value


def validate_mlflow_auth() -> str:
    uri = os.environ.get("MLFLOW_TRACKING_URI", "").rstrip("/")
    username = os.environ.get("MLFLOW_TRACKING_USERNAME", "").strip()
    password = os.environ.get("MLFLOW_TRACKING_PASSWORD", "")
    parsed = urlparse(uri)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("MLFLOW_TRACKING_URI debe apuntar al servidor autenticado.")
    if not username or not password:
        raise ValueError(
            "Faltan MLFLOW_TRACKING_USERNAME o MLFLOW_TRACKING_PASSWORD."
        )
    return uri


def validate_actor(value: str) -> str:
    actor = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9._@-]{2,80}", actor):
        raise ValueError(
            "El usuario debe tener entre 2 y 80 caracteres: letras, números, . _ @ o -."
        )
    return actor


__all__ = [
    "BACKEND_NAMES",
    "DATABASE_NAME",
    "EXAMPLE_QUESTIONS",
    "MAX_QUESTION_LENGTH",
    "MAX_ROWS",
    "OUTPUT_DIR",
    "PROJECT_DIR",
    "QUERY_TIMEOUT_SECONDS",
    "SCHEMA_NAME",
    "SYSTEM_PROMPT",
    "WEB_HTML",
    "connection_string",
    "load_config",
    "make_backend",
    "validate_actor",
    "validate_mlflow_auth",
]
