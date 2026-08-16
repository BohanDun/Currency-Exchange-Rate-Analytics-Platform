"""Tests for analytical transformation orchestration and SQL contracts."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.transformation.run_transformations import run_transformations
from src.transformation.sql_runner import execute_sql_file, read_sql_file

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeEngine:
    def __init__(self) -> None:
        self.connection = Mock()

    @contextmanager
    def begin(self):
        yield self.connection


def test_rejects_an_empty_sql_file(tmp_path) -> None:
    path = tmp_path / "empty.sql"
    path.write_text("  \n", encoding="utf-8")

    with pytest.raises(ValueError, match="SQL file is empty"):
        read_sql_file(path)


def test_executes_a_sql_file(tmp_path) -> None:
    path = tmp_path / "query.sql"
    path.write_text("SELECT 1;\n", encoding="utf-8")
    connection = Mock()

    execute_sql_file(connection, path)

    connection.exec_driver_sql.assert_called_once_with("SELECT 1;")


def test_runs_ddl_then_transformations_in_order(tmp_path) -> None:
    paths = []
    for index, sql in enumerate(("SELECT 0;", "SELECT 1;", "SELECT 2;")):
        path = tmp_path / f"{index}.sql"
        path.write_text(sql, encoding="utf-8")
        paths.append(path)
    engine = FakeEngine()

    run_transformations(engine, ddl_path=paths[0], transformation_paths=paths[1:])

    assert [call.args[0] for call in engine.connection.exec_driver_sql.call_args_list] == [
        "SELECT 0;",
        "SELECT 1;",
        "SELECT 2;",
    ]


def test_daily_return_sql_uses_pair_partition_and_lag() -> None:
    sql = read_sql_file(
        PROJECT_ROOT / "sql" / "transformations" / "transform_daily_returns.sql"
    ).upper()

    assert "LAG(RATE)" in sql
    assert "PARTITION BY BASE_CURRENCY, QUOTE_CURRENCY, SOURCE" in sql
    assert "RATE / PREVIOUS_RATE" in sql


def test_volatility_requires_complete_windows() -> None:
    sql = read_sql_file(
        PROJECT_ROOT
        / "sql"
        / "transformations"
        / "transform_rolling_volatility.sql"
    ).upper()

    assert "STDDEV_SAMP" in sql
    assert "OBSERVATIONS_7 = 7" in sql
    assert "OBSERVATIONS_30 = 30" in sql


def test_anomaly_baseline_excludes_current_observation() -> None:
    sql = read_sql_file(
        PROJECT_ROOT / "sql" / "transformations" / "transform_anomaly_flags.sql"
    ).upper()

    assert "ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING" in sql
    assert "ABS(ANOMALY_SCORE) > 2.0" in sql
