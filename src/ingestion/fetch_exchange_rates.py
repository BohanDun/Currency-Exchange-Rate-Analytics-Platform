"""Fetch and normalise exchange-rate data from Frankfurter API v2."""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Sequence
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOGGER = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.frankfurter.dev"
DEFAULT_BASE_CURRENCY = "EUR"
DEFAULT_QUOTES = ("USD", "GBP", "NZD", "AUD", "JPY")
OUTPUT_COLUMNS = (
    "rate_date",
    "base_currency",
    "quote_currency",
    "rate",
    "source",
    "ingested_at",
)


class FrankfurterAPIError(RuntimeError):
    """Raised when Frankfurter returns an invalid or unsuccessful response."""


def _normalise_currency(code: str) -> str:
    normalised = code.strip().upper()
    if len(normalised) != 3 or not normalised.isalpha():
        raise ValueError(f"Invalid ISO currency code: {code!r}")
    return normalised


def _normalise_date(value: str | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid date {value!r}; expected YYYY-MM-DD") from exc


def create_retry_session(total_retries: int = 3) -> requests.Session:
    """Create an HTTP session that retries temporary upstream failures."""
    retry = Retry(
        total=total_retries,
        connect=total_retries,
        read=total_retries,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _build_params(
    base_currency: str,
    quote_currencies: Sequence[str],
    start_date: str | date | None,
    end_date: str | date | None,
) -> dict[str, str]:
    base = _normalise_currency(base_currency)
    quotes = tuple(dict.fromkeys(_normalise_currency(code) for code in quote_currencies))

    if not quotes:
        raise ValueError("At least one quote currency is required")
    if base in quotes:
        raise ValueError("Base currency cannot also be a quote currency")

    start = _normalise_date(start_date)
    end = _normalise_date(end_date)
    if end and not start:
        raise ValueError("end_date requires start_date")
    if start and end and start > end:
        raise ValueError("start_date cannot be after end_date")

    params = {"base": base, "quotes": ",".join(quotes)}
    if start and end:
        params.update({"from": start, "to": end})
    elif start:
        params["date"] = start
    return params


def _normalise_response(payload: Any, ingested_at: datetime) -> pd.DataFrame:
    if not isinstance(payload, list):
        raise FrankfurterAPIError("Expected the API response to be a JSON array")

    records: list[dict[str, Any]] = []
    required = {"date", "base", "quote", "rate"}
    for index, row in enumerate(payload):
        if not isinstance(row, dict) or not required.issubset(row):
            raise FrankfurterAPIError(f"Malformed rate record at index {index}")
        records.append(
            {
                "rate_date": row["date"],
                "base_currency": row["base"],
                "quote_currency": row["quote"],
                "rate": row["rate"],
                "source": "frankfurter",
                "ingested_at": ingested_at,
            }
        )

    frame = pd.DataFrame.from_records(records, columns=OUTPUT_COLUMNS)
    if frame.empty:
        return frame

    frame["rate_date"] = pd.to_datetime(frame["rate_date"], errors="raise").dt.date
    frame["rate"] = pd.to_numeric(frame["rate"], errors="raise")
    if frame["rate"].isna().any() or (frame["rate"] <= 0).any():
        raise FrankfurterAPIError("API returned a missing or non-positive rate")

    return frame.sort_values(["rate_date", "quote_currency"], ignore_index=True)


def fetch_exchange_rates(
    *,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    base_currency: str = DEFAULT_BASE_CURRENCY,
    quote_currencies: Sequence[str] = DEFAULT_QUOTES,
    base_url: str | None = None,
    timeout_seconds: float = 20,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Fetch latest, single-day, or date-range rates as a tidy DataFrame.

    With no dates, the latest available rates are returned. Supplying only
    ``start_date`` fetches one historical date. Supplying both dates fetches a
    time series, inclusive of the requested bounds where rates are available.
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    params = _build_params(base_currency, quote_currencies, start_date, end_date)
    api_root = (base_url or os.getenv("FRANKFURTER_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
    client = session or create_retry_session()
    url = f"{api_root}/v2/rates"

    LOGGER.info("Fetching exchange rates from %s with params=%s", url, params)
    try:
        response = client.get(url, params=params, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise FrankfurterAPIError(f"Frankfurter request failed: {exc}") from exc
    except ValueError as exc:
        raise FrankfurterAPIError("Frankfurter returned invalid JSON") from exc

    ingested_at = datetime.now(timezone.utc)
    frame = _normalise_response(payload, ingested_at)
    LOGGER.info("Fetched %d exchange-rate records", len(frame))
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", help="Single date or range start (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Range end (YYYY-MM-DD)")
    parser.add_argument("--base", default=DEFAULT_BASE_CURRENCY)
    parser.add_argument("--quotes", default=",".join(DEFAULT_QUOTES))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    frame = fetch_exchange_rates(
        start_date=args.start_date,
        end_date=args.end_date,
        base_currency=args.base,
        quote_currencies=args.quotes.split(","),
    )
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
