"""Post-load quality checks for the complete analytics pipeline."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Engine, text


class DataQualityError(RuntimeError):
    """Raised when persisted pipeline data violates an expected invariant."""


def run_data_quality_checks(
    engine: Engine,
    *,
    expected_date: str | date,
    expected_quote_count: int,
) -> dict[str, int | str]:
    """Check daily coverage and row consistency across all pipeline layers."""
    if expected_quote_count <= 0:
        raise ValueError("expected_quote_count must be positive")

    sql = text(
        """
        SELECT
            (SELECT COUNT(*) FROM raw_exchange_rates
             WHERE rate_date = :expected_date) AS daily_raw_rows,
            (SELECT COUNT(*) FROM raw_exchange_rates) AS raw_rows,
            (SELECT COUNT(*) FROM clean_exchange_rates) AS clean_rows,
            (SELECT COUNT(*) FROM fact_daily_returns) AS return_rows,
            (SELECT COUNT(*) FROM fact_rolling_volatility) AS volatility_rows,
            (SELECT COUNT(*) FROM fact_anomaly_flags) AS anomaly_rows,
            (SELECT COUNT(*) FROM raw_exchange_rates
             WHERE rate <= 0 OR base_currency = quote_currency) AS invalid_raw_rows
        """
    )
    with engine.connect() as connection:
        row = connection.execute(sql, {"expected_date": expected_date}).mappings().one()

    daily_rows = int(row["daily_raw_rows"])
    layer_counts = {
        "raw": int(row["raw_rows"]),
        "clean": int(row["clean_rows"]),
        "returns": int(row["return_rows"]),
        "volatility": int(row["volatility_rows"]),
        "anomalies": int(row["anomaly_rows"]),
    }
    errors: list[str] = []
    if daily_rows != expected_quote_count:
        errors.append(
            f"expected {expected_quote_count} raw rows for {expected_date}, found {daily_rows}"
        )
    if len(set(layer_counts.values())) != 1:
        errors.append(f"pipeline layer row counts differ: {layer_counts}")
    if int(row["invalid_raw_rows"]) != 0:
        errors.append(f"found {int(row['invalid_raw_rows'])} invalid raw row(s)")
    if errors:
        raise DataQualityError("; ".join(errors))

    return {
        "checked_date": str(expected_date),
        "daily_raw_rows": daily_rows,
        "total_rows_per_layer": layer_counts["raw"],
    }
