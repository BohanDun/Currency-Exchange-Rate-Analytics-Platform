"""Run the project's SQL transformations in dependency order."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import Engine

from src.transformation.sql_runner import execute_sql_file

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYTICS_DDL = PROJECT_ROOT / "sql" / "ddl" / "create_analytics_tables.sql"
TRANSFORMATION_FILES = (
    PROJECT_ROOT / "sql" / "transformations" / "transform_clean_exchange_rates.sql",
    PROJECT_ROOT / "sql" / "transformations" / "transform_daily_returns.sql",
    PROJECT_ROOT / "sql" / "transformations" / "transform_rolling_volatility.sql",
    PROJECT_ROOT / "sql" / "transformations" / "transform_anomaly_flags.sql",
)


def run_transformations(
    engine: Engine,
    *,
    ddl_path: Path = ANALYTICS_DDL,
    transformation_paths: Sequence[Path] = TRANSFORMATION_FILES,
) -> None:
    """Create and refresh every analytics table in one transaction."""
    with engine.begin() as connection:
        execute_sql_file(connection, ddl_path)
        for path in transformation_paths:
            execute_sql_file(connection, path)
