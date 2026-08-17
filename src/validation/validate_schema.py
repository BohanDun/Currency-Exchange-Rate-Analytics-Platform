"""Validate exchange-rate records before loading them into PostgreSQL."""

from __future__ import annotations

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = (
    "rate_date",
    "base_currency",
    "quote_currency",
    "rate",
    "source",
    "ingested_at",
)
BUSINESS_KEY = ("rate_date", "base_currency", "quote_currency", "source")


class SchemaValidationError(ValueError):
    """Raised when exchange-rate data violates one or more quality rules."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Exchange-rate validation failed: " + "; ".join(errors))


def current_pipeline_date(timezone_name: str | None = None) -> date:
    """Return today's date in the pipeline's configured business timezone."""
    name = timezone_name or os.getenv("PIPELINE_TIMEZONE", "UTC")
    try:
        return datetime.now(ZoneInfo(name)).date()
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown PIPELINE_TIMEZONE: {name}") from exc


def _invalid_currency_values(series: pd.Series) -> list[str]:
    values = series.astype("string").str.strip().str.upper()
    invalid = values[~values.str.fullmatch(r"[A-Z]{3}", na=False)]
    return sorted(invalid.dropna().unique().tolist())


def validate_exchange_rates(
    frame: pd.DataFrame,
    *,
    allow_empty: bool = False,
    today: date | None = None,
) -> pd.DataFrame:
    """Validate and normalise exchange-rate data.

    A validated copy is returned; the caller's DataFrame is never mutated.
    All detectable problems are collected into one exception so a failed
    pipeline run gives a useful diagnostic instead of revealing errors one at
    a time.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")

    errors: list[str] = []
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise SchemaValidationError([f"missing columns: {', '.join(missing_columns)}"])

    validated = frame.loc[:, REQUIRED_COLUMNS].copy()
    if validated.empty:
        if allow_empty:
            return validated
        raise SchemaValidationError(["dataset is empty"])

    null_counts = validated.isna().sum()
    for column, count in null_counts[null_counts > 0].items():
        errors.append(f"{column} contains {count} null value(s)")

    # Convert types on the copy. Conversion failures are reported alongside
    # other validation failures rather than leaking low-level pandas errors.
    parsed_date_times = pd.to_datetime(validated["rate_date"], errors="coerce")
    invalid_date_count = int(parsed_date_times.isna().sum())
    if invalid_date_count:
        errors.append(f"rate_date contains {invalid_date_count} invalid value(s)")
    validated["rate_date"] = parsed_date_times.dt.date

    parsed_ingested_at = pd.to_datetime(
        validated["ingested_at"], errors="coerce", utc=True
    )
    invalid_timestamp_count = int(parsed_ingested_at.isna().sum())
    if invalid_timestamp_count:
        errors.append(f"ingested_at contains {invalid_timestamp_count} invalid value(s)")
    validated["ingested_at"] = parsed_ingested_at

    for column in ("base_currency", "quote_currency"):
        invalid_values = _invalid_currency_values(validated[column])
        if invalid_values:
            errors.append(f"{column} has invalid ISO codes: {invalid_values}")
        validated[column] = validated[column].astype("string").str.strip().str.upper()

    same_currency = validated["base_currency"] == validated["quote_currency"]
    if same_currency.any():
        errors.append(f"base and quote currencies match in {int(same_currency.sum())} row(s)")

    parsed_rates = pd.to_numeric(validated["rate"], errors="coerce")
    invalid_rate = parsed_rates.isna() | ~np.isfinite(parsed_rates) | (parsed_rates <= 0)
    if invalid_rate.any():
        errors.append(f"rate is non-numeric, non-finite, or non-positive in {int(invalid_rate.sum())} row(s)")
    validated["rate"] = parsed_rates.astype("float64")

    validated["source"] = validated["source"].astype("string").str.strip().str.lower()
    blank_source = validated["source"].eq("")
    if blank_source.any():
        errors.append(f"source is blank in {int(blank_source.sum())} row(s)")

    comparison_date = pd.Timestamp(today or current_pipeline_date())
    future_dates = parsed_date_times.notna() & (parsed_date_times > comparison_date)
    if future_dates.any():
        errors.append(f"rate_date is in the future in {int(future_dates.sum())} row(s)")

    duplicate_rows = validated.duplicated(subset=list(BUSINESS_KEY), keep=False)
    if duplicate_rows.any():
        errors.append(
            f"business key {BUSINESS_KEY} is duplicated in {int(duplicate_rows.sum())} row(s)"
        )

    if errors:
        raise SchemaValidationError(errors)

    return validated.sort_values(
        ["rate_date", "base_currency", "quote_currency"], ignore_index=True
    )
