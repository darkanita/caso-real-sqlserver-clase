"""Servidor web local del agente SQL real."""
from __future__ import annotations

import json
import os
import sys
import threading
import webbrowser
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .config import (
    BACKEND_NAMES,
    EXAMPLE_QUESTIONS,
    MAX_QUESTION_LENGTH,
    WEB_HTML,
    load_config,
)
from .service import execute

MAX_REQUEST_BYTES = 16_384
RUN_LOCK = threading.Lock()
HISTORY: deque[dict] = deque(maxlen=30)


def public_config() -> dict:
    return {
        "backends": list(BACKEND_NAMES),
        "default_backend": os.environ.get("LLM_BACKEND", "groq"),
        "questions": list(EXAMPLE_QUESTIONS),
        "database": "MilitaryResAllocDB",
        "schema": "dbo",
        "mlflow_default": True,
    }


def validate_request(value) -> dict:
    if not isinstance(value, dict):
        raise ValueError("La solicitud debe ser un objeto JSON.")
    question = value.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("La pregunta no puede estar vacía.")
    if len(question) > MAX_QUESTION_LENGTH:
        raise ValueError("La pregunta supera 2.000 caracteres.")
    requested_by = value.get("requested_by")
    if not isinstance(requested_by, str):
        raise ValueError("Debes indicar el usuario solicitante.")
    backend = value.get("backend")
    if backend not in BACKEND_NAMES:
        raise ValueError("Modelo no permitido.")
    mlflow = value.get("mlflow", True)
    if not isinstance(mlflow, bool):
        raise ValueError("mlflow debe ser verdadero o falso.")
    level = value.get("mlflow_level", "metrics")
    if level not in ("metrics", "traces"):
        raise ValueError("Nivel MLflow no permitido.")
    return {
        "question": question.strip(),
        "requested_by": requested_by,
        "backend_name": backend,
        "mlflow_enabled": mlflow,
        "mlflow_level": level,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "MilitarySqlAgent/1.0"

    def send_json(self, status: HTTPStatus, payload) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            data = WEB_HTML.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/config":
            self.send_json(HTTPStatus.OK, public_config())
        elif path == "/api/runs":
            self.send_json(HTTPStatus.OK, list(HISTORY))
        else:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Ruta no encontrada."})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/ask":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Ruta no encontrada."})
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                {"error": "Usa application/json."},
            )
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Content-Length inválido."})
            return
        if not 0 < length <= MAX_REQUEST_BYTES:
            self.send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": "Solicitud demasiado grande."},
            )
            return
        if not RUN_LOCK.acquire(blocking=False):
            self.send_json(
                HTTPStatus.CONFLICT,
                {"error": "Ya hay una pregunta ejecutándose."},
            )
            return
        try:
            request = validate_request(json.loads(self.rfile.read(length)))
            result = execute(**request)
            HISTORY.appendleft({
                "question": request["question"],
                "requested_by": result["requested_by"],
                "model": result["model"],
                "duration_seconds": result["metrics"]["duration_seconds"],
                "tokens": result["metrics"]["total_tokens"],
                "tables": result["tables"],
                "mlflow_run_id": (
                    result["mlflow"]["run_id"] if result["mlflow"] else None
                ),
            })
            self.send_json(HTTPStatus.OK, result)
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            print(f"ERROR {type(exc).__name__}", file=sys.stderr)
            self.send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"No se pudo ejecutar: {type(exc).__name__}."},
            )
        finally:
            RUN_LOCK.release()

    def log_message(self, format: str, *args) -> None:
        return


def main() -> int:
    load_config()
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65_535:
        parser.error("--port debe estar entre 1 y 65535.")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Agente MilitaryResAllocDB: {url}")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()
    return 0
