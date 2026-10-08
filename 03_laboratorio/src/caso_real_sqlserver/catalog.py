"""Catálogo vivo del esquema para buscar solo el contexto necesario."""
from __future__ import annotations

from dataclasses import dataclass

from .security import BLOCKED_TABLES, SENSITIVE_COLUMNS

SEARCH_SYNONYMS = {
    "carrera": "career",
    "dependencia": "dependencies",
    "especialidad": "specialty",
    "estado": "status employmentstatus",
    "grado": "rank",
    "laboral": "employmentstatus",
    "personal": "personnel",
    "persona": "personnel",
    "personas": "personnel",
    "proyeccion": "projection",
    "rango": "rank",
    "solicitud": "request",
    "unidad": "unit",
}


@dataclass(frozen=True)
class Column:
    name: str
    data_type: str
    nullable: bool
    primary_key: bool


class SchemaCatalog:
    def __init__(self, connection):
        self.tables: dict[str, list[Column]] = {}
        self.relationships: list[dict] = []
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT t.name, c.column_id, c.name, ty.name, c.is_nullable,
                   CASE WHEN pk.column_id IS NULL THEN 0 ELSE 1 END
            FROM sys.tables t
            JOIN sys.schemas s ON s.schema_id=t.schema_id
            JOIN sys.columns c ON c.object_id=t.object_id
            JOIN sys.types ty ON ty.user_type_id=c.user_type_id
            LEFT JOIN (
                SELECT ic.object_id,ic.column_id
                FROM sys.indexes i
                JOIN sys.index_columns ic
                  ON ic.object_id=i.object_id AND ic.index_id=i.index_id
                WHERE i.is_primary_key=1
            ) pk ON pk.object_id=c.object_id AND pk.column_id=c.column_id
            WHERE s.name='dbo'
            ORDER BY t.name,c.column_id
            """
        )
        for table, _, name, data_type, nullable, primary_key in cursor.fetchall():
            self.tables.setdefault(table.lower(), []).append(
                Column(name, data_type, bool(nullable), bool(primary_key))
            )
        cursor.execute(
            """
            SELECT OBJECT_NAME(fk.parent_object_id), pc.name,
                   OBJECT_NAME(fk.referenced_object_id), rc.name
            FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id=fk.object_id
            JOIN sys.columns pc
              ON pc.object_id=fkc.parent_object_id AND pc.column_id=fkc.parent_column_id
            JOIN sys.columns rc
              ON rc.object_id=fkc.referenced_object_id AND rc.column_id=fkc.referenced_column_id
            WHERE OBJECT_SCHEMA_NAME(fk.parent_object_id)='dbo'
            """
        )
        self.relationships = [
            {
                "from_table": row[0],
                "from_column": row[1],
                "to_table": row[2],
                "to_column": row[3],
            }
            for row in cursor.fetchall()
        ]

    @property
    def allowed_tables(self) -> set[str]:
        return set(self.tables) - BLOCKED_TABLES

    def search(self, term: str, limit: int = 8) -> dict:
        words = {part.lower() for part in term.split() if len(part) >= 2}
        words.update(
            synonym
            for word in tuple(words)
            for synonym in SEARCH_SYNONYMS.get(word, "").split()
        )
        scored = []
        for key, columns in self.tables.items():
            if key in BLOCKED_TABLES:
                continue
            haystack = " ".join([key, *(column.name.lower() for column in columns)])
            score = sum(
                6 if word == key else 3 if word in key else 1
                for word in words
                if word in haystack
            )
            if score:
                scored.append((score, key))
        selected = [key for _, key in sorted(scored, reverse=True)[:limit]]
        return {
            "tables": [self.describe(key, include_relationships=False) for key in selected],
            "matches": len(scored),
        }

    def describe(self, table_name: str, *, include_relationships: bool = True) -> dict:
        key = table_name.lower()
        if key not in self.allowed_tables:
            raise ValueError("Tabla inexistente o no autorizada.")
        columns = [
            {
                "name": column.name,
                "type": column.data_type,
                "nullable": column.nullable,
                "primary_key": column.primary_key,
            }
            for column in self.tables[key]
            if column.name.lower() not in SENSITIVE_COLUMNS
        ]
        result = {"table": key, "columns": columns}
        if include_relationships:
            result["relationships"] = [
                relation
                for relation in self.relationships
                if relation["from_table"].lower() == key
                or relation["to_table"].lower() == key
            ][:30]
        return result
