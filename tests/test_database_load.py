"""Tests for PostgreSQL configuration and raw-data loading."""

from contextlib import contextmanager
from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest

from src.database.connection import DatabaseConfigurationError, build_database_url
from src.ingestion.load_raw_data import create_raw_tables, load_raw_exchange_rates


def valid_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "rate_date": date(2025, 1, 2),
                "base_currency": "EUR",
                "quote_currency": "USD",
                "rate": 1.0364,
                "source": "frankfurter",
                "ingested_at": "2025-01-02T17:00:00Z",
            }
        ]
    )


class FakeEngine:
    def __init__(self) -> None:
        self.connection = Mock()

    @contextmanager
    def begin(self):
        yield self.connection


def test_builds_url_and_safely_escapes_password() -> None:
    url = build_database_url(
        {
            "POSTGRES_DB": "exchange_rates",
            "POSTGRES_USER": "exchange_user",
            "POSTGRES_PASSWORD": "p@ss/word",
            "POSTGRES_HOST": "db",
            "POSTGRES_PORT": "5433",
        }
    )

    assert url.host == "db"
    assert url.port == 5433
    assert url.password == "p@ss/word"
    assert url.render_as_string(hide_password=True).startswith(
        "postgresql+psycopg2://exchange_user:***@db:5433/"
    )


def test_requires_database_credentials() -> None:
    with pytest.raises(DatabaseConfigurationError, match="POSTGRES_PASSWORD"):
        build_database_url({"POSTGRES_DB": "db", "POSTGRES_USER": "user"})


@pytest.mark.parametrize("port", ["abc", "0", "65536"])
def test_rejects_invalid_port(port: str) -> None:
    environment = {
        "POSTGRES_DB": "db",
        "POSTGRES_USER": "user",
        "POSTGRES_PASSWORD": "secret",
        "POSTGRES_PORT": port,
    }
    with pytest.raises(DatabaseConfigurationError, match="POSTGRES_PORT"):
        build_database_url(environment)


def test_executes_non_empty_ddl(tmp_path) -> None:
    ddl_path = tmp_path / "schema.sql"
    ddl_path.write_text("CREATE TABLE example (id INTEGER);", encoding="utf-8")
    engine = FakeEngine()

    create_raw_tables(engine, ddl_path=ddl_path)

    engine.connection.exec_driver_sql.assert_called_once_with(
        "CREATE TABLE example (id INTEGER);"
    )


def test_validates_and_executes_upsert() -> None:
    engine = FakeEngine()

    loaded = load_raw_exchange_rates(valid_frame(), engine, ensure_table=False)

    assert loaded == 1
    statement, records = engine.connection.execute.call_args.args
    assert "ON CONFLICT" in str(statement)
    assert records[0]["quote_currency"] == "USD"
    assert records[0]["rate"] == 1.0364
    assert records[0]["ingested_at"].tzinfo is not None


def test_invalid_data_is_not_written() -> None:
    engine = FakeEngine()
    frame = valid_frame()
    frame.loc[0, "rate"] = -1

    with pytest.raises(ValueError, match="non-positive"):
        load_raw_exchange_rates(frame, engine, ensure_table=False)

    engine.connection.execute.assert_not_called()
