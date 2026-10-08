"""Lanzador directo: python ...\\run_cli.py."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from caso_real_sqlserver.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
