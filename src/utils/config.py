"""Load and validate non-secret application configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppConfig:
    """Runtime settings shared by ingestion and orchestration."""

    frankfurter_base_url: str
    base_currency: str
    quote_currencies: tuple[str, ...]


def load_config(
    environment: Mapping[str, str] | None = None,
    *,
    env_file: str | Path | None = None,
) -> AppConfig:
    """Load application settings from an optional .env file and environment."""
    if environment is None:
        load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)
        env = os.environ
    else:
        env = environment

    base_url = env.get("FRANKFURTER_BASE_URL", "https://api.frankfurter.dev").rstrip(
        "/"
    )
    if not base_url.startswith("https://"):
        raise ValueError("FRANKFURTER_BASE_URL must use HTTPS")

    base_currency = env.get("BASE_CURRENCY", "EUR").strip().upper()
    if len(base_currency) != 3 or not base_currency.isalpha():
        raise ValueError("BASE_CURRENCY must be a three-letter currency code")

    raw_quotes = env.get("QUOTE_CURRENCIES", "USD,GBP,NZD,AUD,JPY")
    quote_currencies = tuple(
        dict.fromkeys(
            code.strip().upper() for code in raw_quotes.split(",") if code.strip()
        )
    )
    if not quote_currencies:
        raise ValueError("QUOTE_CURRENCIES must contain at least one currency")
    invalid_quotes = [
        code for code in quote_currencies if len(code) != 3 or not code.isalpha()
    ]
    if invalid_quotes:
        raise ValueError(f"Invalid quote currency codes: {invalid_quotes}")
    if base_currency in quote_currencies:
        raise ValueError("BASE_CURRENCY cannot appear in QUOTE_CURRENCIES")

    return AppConfig(
        frankfurter_base_url=base_url,
        base_currency=base_currency,
        quote_currencies=quote_currencies,
    )
