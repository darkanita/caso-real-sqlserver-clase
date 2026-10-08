"""Política SQL: solo lectura, sin PII y con agregación para personas."""
from __future__ import annotations

from dataclasses import dataclass

from sqlglot import exp, parse
from sqlglot.errors import ParseError

PERSON_TABLES = frozenset({
    "aspirantintake",
    "pendingwithdrawalpersonnel",
    "pendingwithdrawalschool",
    "personnel",
    "personnelfamilymember",
    "retirementpersonnel",
})

BLOCKED_TABLES = frozenset({
    "audit_event",
    "audit_simple_event",
    "databasechangelog",
    "databasechangeloglock",
    "document",
    "documentasset",
    "folder",
    "profile",
    "transfersrequestattachment",
})

SENSITIVE_COLUMNS = frozenset({
    "address",
    "birthdate",
    "createdby",
    "factsaddress",
    "filename",
    "firstname",
    "firstsurname",
    "fullname",
    "full_name",
    "identification",
    "identificationnumber",
    "institutionalmail",
    "militarycode",
    "name",
    "originalfilename",
    "personnelfamilymemberid",
    "personalmail",
    "phone",
    "placebirth",
    "placeissue",
    "secondsurname",
    "secondname",
    "storageDocumentId".lower(),
    "surname",
    "typeidentification",
    "updatedby",
    "user_event",
})

FORBIDDEN_NODE_KEYS = frozenset({
    "alter",
    "command",
    "copy",
    "create",
    "delete",
    "drop",
    "execute",
    "grant",
    "insert",
    "into",
    "merge",
    "revoke",
    "transaction",
    "truncate",
    "update",
    "use",
})

FORBIDDEN_FUNCTIONS = frozenset({
    "app_name",
    "current_user",
    "db_name",
    "host_name",
    "openquery",
    "openrowset",
    "opendatasource",
    "session_user",
    "suser_sname",
    "system_user",
})


@dataclass(frozen=True)
class ValidatedQuery:
    sql: str
    tables: tuple[str, ...]


def validate_readonly_sql(
    sql: str,
    *,
    allowed_tables: set[str],
    schema_name: str = "dbo",
) -> ValidatedQuery:
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 12_000:
        raise ValueError("SQL_INVALIDO: consulta vacía o demasiado larga.")
    try:
        statements = parse(sql, read="tsql")
    except ParseError as exc:
        raise ValueError("SQL_INVALIDO: SQL Server no pudo interpretar la consulta.") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise ValueError("SQL_DENEGADO: solo se permite una consulta SELECT.")

    statement = statements[0]
    if any(node.key.lower() in FORBIDDEN_NODE_KEYS for node in statement.walk()):
        raise ValueError("SQL_DENEGADO: operación de escritura o administración.")

    table_nodes = list(statement.find_all(exp.Table))
    if not table_nodes:
        raise ValueError("SQL_DENEGADO: la consulta debe leer una tabla autorizada.")
    tables: set[str] = set()
    for table in table_nodes:
        if table.catalog or (table.db and table.db.lower() != schema_name.lower()):
            raise ValueError("SQL_DENEGADO: no se permiten otras bases o esquemas.")
        tables.add(table.name.lower())
    unknown = tables - allowed_tables
    if unknown:
        raise ValueError(f"SQL_DENEGADO: tabla no autorizada: {sorted(unknown)[0]}.")
    blocked = tables & BLOCKED_TABLES
    if blocked:
        raise ValueError(f"SQL_DENEGADO: tabla sensible: {sorted(blocked)[0]}.")

    for star in statement.find_all(exp.Star):
        if not isinstance(star.parent, exp.Count):
            raise ValueError("SQL_DENEGADO: usa columnas explícitas, no SELECT *.")

    sensitive = {
        column.name.lower() for column in statement.find_all(exp.Column)
    } & SENSITIVE_COLUMNS
    if sensitive:
        raise ValueError(
            f"SQL_DENEGADO: columna sensible: {sorted(sensitive)[0]}."
        )
    functions = {
        (
            function.name
            if isinstance(function, exp.Anonymous)
            else function.sql_name()
        ).lower()
        for function in statement.find_all(exp.Func)
    }
    forbidden_functions = functions & FORBIDDEN_FUNCTIONS
    if forbidden_functions:
        raise ValueError(
            f"SQL_DENEGADO: función no permitida: {sorted(forbidden_functions)[0]}."
        )
    if tables & PERSON_TABLES and not any(
        isinstance(node, exp.AggFunc) for node in statement.walk()
    ):
        raise ValueError(
            "SQL_DENEGADO: las tablas de personas solo permiten resultados agregados."
        )
    return ValidatedQuery(sql=sql.strip(), tables=tuple(sorted(tables)))
