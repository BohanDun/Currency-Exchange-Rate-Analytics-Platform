"""Tests for exchange-rate schema validation."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from src.validation.validate_schema import (
    SchemaValidationError,
    current_pipeline_date,
    validate_exchange_rates,
)


def valid_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "rate_date": "2025-01-03",
                "base_currency": " eur ",
                "quote_currency": "usd",
                "rate": "1.03",
                "source": "Frankfurter",
                "ingested_at": "2025-01-03T17:00:00Z",
            },
            {
                "rate_date": "2025-01-02",
                "base_currency": "EUR",
                "quote_currency": "GBP",
                "rate": 0.83,
                "source": "frankfurter",
                "ingested_at": "2025-01-02T17:00:00Z",
            },
        ]
    )


def test_returns_a_normalised_sorted_copy() -> None:
    original = valid_frame()

    result = validate_exchange_rates(original, today=date(2025, 1, 4))

    assert result["rate_date"].tolist() == [date(2025, 1, 2), date(2025, 1, 3)]
    assert result["base_currency"].tolist() == ["EUR", "EUR"]
    assert result["source"].tolist() == ["frankfurter", "frankfurter"]
    assert result["rate"].dtype == "float64"
    assert original.loc[0, "base_currency"] == " eur "


def test_rejects_missing_columns() -> None:
    with pytest.raises(SchemaValidationError, match="missing columns: source"):
        validate_exchange_rates(valid_frame().drop(columns="source"))


def test_rejects_empty_data_by_default() -> None:
    with pytest.raises(SchemaValidationError, match="dataset is empty"):
        validate_exchange_rates(valid_frame().iloc[0:0])


def test_can_allow_an_empty_dataset() -> None:
    result = validate_exchange_rates(valid_frame().iloc[0:0], allow_empty=True)
    assert result.empty


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("quote_currency", "US", "invalid ISO codes"),
        ("rate", 0, "non-positive"),
        ("rate", float("inf"), "non-finite"),
        ("rate_date", "not-a-date", "invalid value"),
        ("ingested_at", "not-a-time", "invalid value"),
        ("source", " ", "source is blank"),
    ],
)
def test_rejects_invalid_values(column: str, value: object, message: str) -> None:
    frame = valid_frame().iloc[[0]].copy()
    frame.loc[frame.index[0], column] = value

    with pytest.raises(SchemaValidationError, match=message):
        validate_exchange_rates(frame, today=date(2025, 1, 4))


def test_rejects_matching_base_and_quote_currency() -> None:
    frame = valid_frame().iloc[[0]].copy()
    frame.loc[frame.index[0], "quote_currency"] = "EUR"

    with pytest.raises(SchemaValidationError, match="base and quote currencies match"):
        validate_exchange_rates(frame, today=date(2025, 1, 4))


def test_rejects_future_rates() -> None:
    with pytest.raises(SchemaValidationError, match="in the future"):
        validate_exchange_rates(valid_frame(), today=date(2025, 1, 2))


def test_rejects_duplicate_business_keys() -> None:
    frame = pd.concat(
        [valid_frame().iloc[[0]], valid_frame().iloc[[0]]], ignore_index=True
    )

    with pytest.raises(SchemaValidationError, match="business key.*duplicated"):
        validate_exchange_rates(frame, today=date(2025, 1, 4))


def test_collects_multiple_errors() -> None:
    frame = valid_frame().iloc[[0]].copy()
    frame.loc[frame.index[0], "quote_currency"] = "BAD!"
    frame.loc[frame.index[0], "rate"] = -1

    with pytest.raises(SchemaValidationError) as exc_info:
        validate_exchange_rates(frame, today=date(2025, 1, 4))

    assert len(exc_info.value.errors) == 2


def test_current_pipeline_date_uses_business_timezone() -> None:
    assert (
        current_pipeline_date("Pacific/Auckland")
        == datetime.now(ZoneInfo("Pacific/Auckland")).date()
    )


def test_rejects_unknown_pipeline_timezone() -> None:
    with pytest.raises(ValueError, match="Unknown PIPELINE_TIMEZONE"):
        current_pipeline_date("Not/A-Timezone")
