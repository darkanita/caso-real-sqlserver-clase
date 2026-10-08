"""Acceso SQL Server con permisos verificados, timeout y rollback."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pyodbc

from .catalog import SchemaCatalog
from .config import (
    DATABASE_NAME,
    MAX_ROWS,
    QUERY_TIMEOUT_SECONDS,
    SCHEMA_NAME,
    connection_string,
)
from .security import validate_readonly_sql


def json_value(value):
    if isinstance(value, (date, datetime, Decimal)):
        return str(value)
    if isinstance(value, bytes):
        return "<binario>"
    return value


class MilitaryDatabase:
    def __init__(self):
        self._connection_string = connection_string()
        self._catalog: SchemaCatalog | None = None
        self._permissions_checked = False

    def connect(self):
        try:
            connection = pyodbc.connect(
                self._connection_string,
                timeout=8,
                autocommit=False,
            )
            connection.timeout = QUERY_TIMEOUT_SECONDS
            return connection
        except pyodbc.Error as exc:
            raise ValueError(
                "No fue posible conectar con MilitaryResAllocDB."
            ) from exc

    def initialize(self) -> None:
        connection = self.connect()
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT DB_NAME()")
            if cursor.fetchone()[0] != DATABASE_NAME:
                raise ValueError(f"La conexión debe apuntar a {DATABASE_NAME}.")
            cursor.execute(
                """
                SELECT
                  SUM(CASE WHEN HAS_PERMS_BY_NAME(
                    QUOTENAME(s.name)+'.'+QUOTENAME(t.name),'OBJECT','SELECT')=1
                    THEN 1 ELSE 0 END),
                  SUM(CASE WHEN
                    HAS_PERMS_BY_NAME(QUOTENAME(s.name)+'.'+QUOTENAME(t.name),'OBJECT','INSERT')=1 OR
                    HAS_PERMS_BY_NAME(QUOTENAME(s.name)+'.'+QUOTENAME(t.name),'OBJECT','UPDATE')=1 OR
                    HAS_PERMS_BY_NAME(QUOTENAME(s.name)+'.'+QUOTENAME(t.name),'OBJECT','DELETE')=1 OR
                    HAS_PERMS_BY_NAME(QUOTENAME(s.name)+'.'+QUOTENAME(t.name),'OBJECT','ALTER')=1
                    THEN 1 ELSE 0 END)
                FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
                WHERE s.name=?
                """,
                SCHEMA_NAME,
            )
            readable, writable = cursor.fetchone()
            if not readable:
                raise ValueError("La cuenta no tiene tablas legibles.")
            if writable:
                raise ValueError(
                    "La cuenta tiene permisos de escritura; usa un usuario de solo lectura."
                )
            self._catalog = SchemaCatalog(connection)
            self._permissions_checked = True
        finally:
            connection.rollback()
            connection.close()

    @property
    def catalog(self) -> SchemaCatalog:
        if self._catalog is None:
            self.initialize()
        return self._catalog

    def query(self, sql: str) -> dict:
        validated = validate_readonly_sql(
            sql,
            allowed_tables=self.catalog.allowed_tables,
            schema_name=SCHEMA_NAME,
        )
        connection = self.connect()
        try:
            cursor = connection.cursor()
            cursor.execute(validated.sql)
            if cursor.description is None:
                raise ValueError("SQL_DENEGADO: la consulta no produjo resultados.")
            columns = [item[0] for item in cursor.description]
            values = cursor.fetchmany(MAX_ROWS + 1)
            rows = [
                {
                    column: json_value(value)
                    for column, value in zip(columns, row)
                }
                for row in values[:MAX_ROWS]
            ]
            return {
                "ok": True,
                "rows": rows,
                "truncated": len(values) > MAX_ROWS,
                "tables": list(validated.tables),
            }
        except pyodbc.Error as exc:
            return {
                "ok": False,
                "error": "SQL_INVALIDO: SQL Server rechazó la consulta.",
                "detail": type(exc).__name__,
            }
        finally:
            connection.rollback()
            connection.close()
