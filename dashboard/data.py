"""Database access helpers for the analytics dashboard."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

QUERY_DIR = Path(__file__).resolve().parent / "queries"


def read_query(name: str) -> str:
    """Read a named dashboard query without allowing arbitrary paths."""
    if not name.replace("_", "").isalnum():
        raise ValueError(f"Invalid query name: {name!r}")
    path = QUERY_DIR / f"{name}.sql"
    sql = path.read_text(encoding="utf-8").strip()
    if not sql:
        raise ValueError(f"Dashboard query is empty: {path}")
    return sql


def get_filter_options(engine: Engine) -> tuple[list[str], date, date]:
    """Return available currency pairs and the overall supported date range."""
    sql = text(
        """
        SELECT
            currency_pair,
            MIN(MIN(rate_date)) OVER () AS minimum_date,
            MAX(MAX(rate_date)) OVER () AS maximum_date
        FROM clean_exchange_rates
        GROUP BY currency_pair
        ORDER BY currency_pair
        """
    )
    frame = pd.read_sql_query(sql, engine)
    if frame.empty:
        raise ValueError("No analytics data is available. Run the pipeline first.")
    pairs = sorted(frame["currency_pair"].drop_duplicates().tolist())
    return pairs, pd.Timestamp(frame["minimum_date"].iloc[0]).date(), pd.Timestamp(
        frame["maximum_date"].iloc[0]
    ).date()


def load_dashboard_data(
    engine: Engine,
    currency_pair: str,
    start_date: date,
    end_date: date,
) -> dict[str, pd.DataFrame]:
    """Load all dashboard datasets using bound SQL parameters."""
    if start_date > end_date:
        raise ValueError("start_date cannot be after end_date")
    parameters = {
        "currency_pair": currency_pair,
        "start_date": start_date,
        "end_date": end_date,
    }
    return {
        name: pd.read_sql_query(text(read_query(name)), engine, params=parameters)
        for name in ("trend_query", "returns_query", "volatility_query", "anomaly_query")
    }
