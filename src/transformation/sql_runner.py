"""Execute SQL files against PostgreSQL."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Connection


def read_sql_file(path: str | Path) -> str:
    """Read a non-empty UTF-8 SQL file."""
    sql_path = Path(path)
    sql = sql_path.read_text(encoding="utf-8").strip()
    if not sql:
        raise ValueError(f"SQL file is empty: {sql_path}")
    return sql


def execute_sql_file(connection: Connection, path: str | Path) -> None:
    """Execute one SQL file using an existing transaction connection."""
    connection.exec_driver_sql(read_sql_file(path))
