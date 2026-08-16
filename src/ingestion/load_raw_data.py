"""Load validated exchange-rate records into the raw PostgreSQL table."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import Engine, text

from src.validation.validate_schema import validate_exchange_rates

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_TABLE_DDL_PATH = PROJECT_ROOT / "sql" / "ddl" / "create_raw_tables.sql"

UPSERT_SQL = text(
    """
    INSERT INTO raw_exchange_rates (
        rate_date,
        base_currency,
        quote_currency,
        rate,
        source,
        ingested_at
    ) VALUES (
        :rate_date,
        :base_currency,
        :quote_currency,
        :rate,
        :source,
        :ingested_at
    )
    ON CONFLICT (rate_date, base_currency, quote_currency, source)
    DO UPDATE SET
        rate = EXCLUDED.rate,
        ingested_at = EXCLUDED.ingested_at
    """
)


def create_raw_tables(engine: Engine, ddl_path: Path = RAW_TABLE_DDL_PATH) -> None:
    """Create the raw schema objects inside a transaction."""
    ddl = ddl_path.read_text(encoding="utf-8").strip()
    if not ddl:
        raise ValueError(f"DDL file is empty: {ddl_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(ddl)


def _to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        ingested_at = row["ingested_at"]
        if isinstance(ingested_at, pd.Timestamp):
            ingested_at = ingested_at.to_pydatetime()
        records.append({**row, "rate": float(row["rate"]), "ingested_at": ingested_at})
    return records


def load_raw_exchange_rates(
    frame: pd.DataFrame,
    engine: Engine,
    *,
    ensure_table: bool = True,
) -> int:
    """Validate and upsert exchange rates, returning the submitted row count.

    The business key makes this function idempotent: rerunning the same date and
    currency pair updates the value instead of inserting a duplicate.
    """
    validated = validate_exchange_rates(frame)
    records = _to_records(validated)

    if ensure_table:
        create_raw_tables(engine)
    if not records:
        return 0

    with engine.begin() as connection:
        connection.execute(UPSERT_SQL, records)
    return len(records)
