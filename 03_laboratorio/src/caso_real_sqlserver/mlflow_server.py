"""Inicia el MLflow del caso real con autenticación básica."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from urllib.parse import urlparse

from .config import OUTPUT_DIR, load_config, validate_mlflow_auth

SECRETS_NOT_NEEDED_BY_SERVER = (
    "GROQ_API_KEY",
    "OPENAI_API_KEY",
    "MILITARY_SQLSERVER_CONNECTION_STRING",
    "SQLSERVER_CONNECTION_STRING",
    "MLFLOW_TRACKING_PASSWORD",
    "MLFLOW_AUTH_ADMIN_PASSWORD",
)


def build_environment(config_path, password: str, bootstrap: bool) -> dict[str, str]:
    environment = os.environ.copy()
    for name in SECRETS_NOT_NEEDED_BY_SERVER:
        environment.pop(name, None)
    environment["MLFLOW_AUTH_CONFIG_PATH"] = str(config_path.resolve())
    if bootstrap:
        environment["MLFLOW_AUTH_ADMIN_PASSWORD"] = password
    return environment


def main() -> int:
    load_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    uri = validate_mlflow_auth()
    parsed = urlparse(uri)
    if parsed.hostname not in ("127.0.0.1", "localhost"):
        parser.error("Este lanzador solo inicia MLflow local.")
    port = args.port or parsed.port or 5000
    if uri not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
        parser.error("El puerto no coincide con MLFLOW_TRACKING_URI.")
    secret = os.environ.get("MLFLOW_FLASK_SERVER_SECRET_KEY", "")
    if len(secret) < 32:
        parser.error("MLFLOW_FLASK_SERVER_SECRET_KEY requiere 32 caracteres.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    auth_db = OUTPUT_DIR / "basic_auth.db"
    tracking_db = OUTPUT_DIR / "mlflow.db"
    artifacts = OUTPUT_DIR / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    username = os.environ["MLFLOW_TRACKING_USERNAME"]
    password = os.environ["MLFLOW_TRACKING_PASSWORD"]
    config_path = OUTPUT_DIR / "mlflow-auth.ini"
    config_path.write_text(
        "[mlflow]\n"
        f"database_uri = sqlite:///{auth_db.resolve().as_posix()}\n"
        f"admin_username = {username}\n"
        "default_permission = READ\n",
        encoding="utf-8",
    )
    environment = build_environment(config_path, password, not auth_db.exists())
    command = [
        sys.executable,
        "-m",
        "mlflow",
        "server",
        "--app-name",
        "basic-auth",
        "--backend-store-uri",
        f"sqlite:///{tracking_db.resolve().as_posix()}",
        "--default-artifact-root",
        artifacts.resolve().as_uri(),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--workers",
        "1",
        "--allowed-hosts",
        f"127.0.0.1:{port},localhost:{port}",
    ]
    print(f"MLflow autenticado: {uri}")
    return subprocess.run(command, env=environment, check=False).returncode

