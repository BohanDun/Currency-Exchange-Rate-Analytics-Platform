"""Tests for Frankfurter API ingestion."""

from datetime import date
from unittest.mock import Mock

import pandas as pd
import pytest
import requests

from src.ingestion.fetch_exchange_rates import (
    FrankfurterAPIError,
    fetch_exchange_rates,
)


def _response(payload: object, status_code: int = 200) -> Mock:
    response = Mock()
    response.json.return_value = payload
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(str(status_code))
    return response


def test_fetches_and_normalises_a_date_range() -> None:
    session = Mock()
    session.get.return_value = _response(
        [
            {"date": "2025-01-03", "base": "EUR", "quote": "USD", "rate": 1.03},
            {"date": "2025-01-02", "base": "EUR", "quote": "USD", "rate": 1.02},
        ]
    )

    result = fetch_exchange_rates(
        start_date="2025-01-02",
        end_date=date(2025, 1, 3),
        quote_currencies=["usd"],
        session=session,
    )

    session.get.assert_called_once_with(
        "https://api.frankfurter.dev/v2/rates",
        params={
            "base": "EUR",
            "quotes": "USD",
            "from": "2025-01-02",
            "to": "2025-01-03",
        },
        timeout=20,
    )
    assert list(result.columns) == [
        "rate_date",
        "base_currency",
        "quote_currency",
        "rate",
        "source",
        "ingested_at",
    ]
    assert result["rate_date"].tolist() == [date(2025, 1, 2), date(2025, 1, 3)]
    assert pd.api.types.is_datetime64_any_dtype(result["ingested_at"])


def test_single_date_uses_date_parameter() -> None:
    session = Mock()
    session.get.return_value = _response([])

    fetch_exchange_rates(start_date="2025-01-02", session=session)

    assert session.get.call_args.kwargs["params"]["date"] == "2025-01-02"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"base_currency": "EURO"}, "Invalid ISO currency code"),
        ({"quote_currencies": []}, "At least one quote currency"),
        ({"start_date": "2025-02-01", "end_date": "2025-01-01"}, "cannot be after"),
        ({"end_date": "2025-01-01"}, "requires start_date"),
    ],
)
def test_rejects_invalid_arguments(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        fetch_exchange_rates(**kwargs)


def test_wraps_http_errors() -> None:
    session = Mock()
    session.get.return_value = _response({}, status_code=422)

    with pytest.raises(FrankfurterAPIError, match="request failed"):
        fetch_exchange_rates(session=session)


def test_rejects_malformed_records() -> None:
    session = Mock()
    session.get.return_value = _response([{"date": "2025-01-02"}])

    with pytest.raises(FrankfurterAPIError, match="Malformed rate record"):
        fetch_exchange_rates(session=session)
