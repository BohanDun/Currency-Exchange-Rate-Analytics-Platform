"""Command-line entry point for the complete exchange-rate data pipeline."""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta

from src.database.connection import create_database_engine
from src.ingestion.fetch_exchange_rates import fetch_exchange_rates
from src.ingestion.load_raw_data import load_raw_exchange_rates
from src.transformation.run_transformations import run_transformations
from src.utils.config import load_config
from src.utils.logger import configure_logging

LOGGER = logging.getLogger(__name__)


def run_pipeline(start_date: str, end_date: str | None = None) -> int:
    """Fetch, validate, load, and transform one requested date range."""
    config = load_config()
    engine = create_database_engine()
    try:
        rates = fetch_exchange_rates(
            start_date=start_date,
            end_date=end_date,
            base_currency=config.base_currency,
            quote_currencies=config.quote_currencies,
            base_url=config.frankfurter_base_url,
        )
        loaded_rows = load_raw_exchange_rates(rates, engine)
        run_transformations(engine)
    finally:
        engine.dispose()

    LOGGER.info("Pipeline completed successfully; submitted_rows=%d", loaded_rows)
    return loaded_rows


def main() -> None:
    yesterday = date.today() - timedelta(days=1)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-date",
        default=yesterday.isoformat(),
        help="Single date or range start in YYYY-MM-DD format (default: yesterday)",
    )
    parser.add_argument("--end-date", help="Optional range end in YYYY-MM-DD format")
    args = parser.parse_args()

    configure_logging()
    run_pipeline(args.start_date, args.end_date)


if __name__ == "__main__":
    main()
