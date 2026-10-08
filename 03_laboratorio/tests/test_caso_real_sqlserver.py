"""Pruebas locales del caso real, sin conectarse a SQL Server ni al modelo."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from caso_real_sqlserver.catalog import Column, SchemaCatalog  # noqa: E402
from caso_real_sqlserver.config import EXAMPLE_QUESTIONS, WEB_HTML  # noqa: E402
from caso_real_sqlserver.mlflow_server import build_environment  # noqa: E402
from caso_real_sqlserver.security import validate_readonly_sql  # noqa: E402
from caso_real_sqlserver.web import public_config, validate_request  # noqa: E402


class RealSqlServerTests(unittest.TestCase):
    allowed = {"personnel", "rank", "projection", "personnelrequest"}

    def test_allows_aggregate_personnel_query(self):
        result = validate_readonly_sql(
            """
            SELECT p.EmploymentStatus, COUNT(*) AS total
            FROM dbo.Personnel p
            GROUP BY p.EmploymentStatus
            ORDER BY total DESC
            """,
            allowed_tables=self.allowed,
        )
        self.assertEqual(result.tables, ("personnel",))

    def test_rejects_writes_pii_raw_people_and_wildcards(self):
        denied = (
            "DELETE FROM dbo.Personnel",
            "SELECT Identification, COUNT(*) FROM dbo.Personnel GROUP BY Identification",
            "SELECT COUNT(*) FROM dbo.Personnel WHERE Identification='123'",
            "SELECT EmploymentStatus FROM dbo.Personnel",
            "SELECT * FROM dbo.Rank",
            "SELECT COUNT(*) FROM otra.dbo.Personnel",
            "SELECT DB_NAME(), COUNT(*) FROM dbo.Personnel",
        )
        for sql in denied:
            with self.subTest(sql=sql), self.assertRaisesRegex(ValueError, "SQL_DENEGADO"):
                validate_readonly_sql(sql, allowed_tables=self.allowed)

    def test_catalog_search_understands_spanish_and_hides_pii(self):
        catalog = SchemaCatalog.__new__(SchemaCatalog)
        catalog.tables = {
            "personnel": [
                Column("PersonnelId", "int", False, True),
                Column("EmploymentStatus", "varchar", True, False),
                Column("Identification", "varchar", False, False),
            ],
            "rank": [Column("RankName", "varchar", False, False)],
        }
        catalog.relationships = []
        result = catalog.search("personas estado laboral")
        self.assertEqual(result["tables"][0]["table"], "personnel")
        names = {column["name"] for column in result["tables"][0]["columns"]}
        self.assertNotIn("Identification", names)

    def test_web_contract(self):
        config = public_config()
        self.assertEqual(config["database"], "MilitaryResAllocDB")
        self.assertEqual(config["questions"], list(EXAMPLE_QUESTIONS))
        request = validate_request({
            "question": EXAMPLE_QUESTIONS[0],
            "requested_by": "ana.perez",
            "backend": "groq",
            "mlflow": True,
            "mlflow_level": "metrics",
        })
        self.assertTrue(request["mlflow_enabled"])
        self.assertEqual(request["requested_by"], "ana.perez")
        html = WEB_HTML.read_text(encoding="utf-8")
        self.assertIn("--cp-accent", html)
        self.assertIn("/api/ask", html)
        self.assertIn("/api/runs", html)
        self.assertIn('id="requestedBy"', html)

    def test_mlflow_server_does_not_inherit_database_or_model_secrets(self):
        values = {
            "GROQ_API_KEY": "secret",
            "MILITARY_SQLSERVER_CONNECTION_STRING": "secret",
            "MLFLOW_TRACKING_PASSWORD": "auth-password",
        }
        with patch.dict(os.environ, values, clear=True):
            environment = build_environment(
                Path("auth.ini"),
                "auth-password",
                bootstrap=True,
            )
        self.assertNotIn("GROQ_API_KEY", environment)
        self.assertNotIn("MILITARY_SQLSERVER_CONNECTION_STRING", environment)
        self.assertNotIn("MLFLOW_TRACKING_PASSWORD", environment)
        self.assertEqual(
            environment["MLFLOW_AUTH_ADMIN_PASSWORD"],
            "auth-password",
        )


if __name__ == "__main__":
    unittest.main()
