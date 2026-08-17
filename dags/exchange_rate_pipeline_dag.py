"""Daily Airflow DAG for the exchange-rate analytics pipeline."""

from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.exceptions import AirflowSkipException
from airflow.sdk import dag, get_current_context, task

from src.database.connection import create_database_engine
from src.ingestion.fetch_exchange_rates import fetch_exchange_rates
from src.ingestion.load_raw_data import load_raw_exchange_rates
from src.transformation.run_transformations import run_transformations
from src.utils.config import load_config
from src.validation.quality_checks import run_data_quality_checks


def _target_date() -> str:
    """Resolve an optional manual run_date or the scheduled data interval date."""
    context = get_current_context()
    configured_date = context["params"].get("run_date")
    if configured_date:
        return str(configured_date)
    return (
        context["data_interval_start"]
        .in_timezone("Pacific/Auckland")
        .date()
        .isoformat()
    )


@dag(
    dag_id="exchange_rate_analytics_daily",
    description="Ingest, transform, and quality-check daily FX rates",
    schedule="0 6 * * *",
    start_date=pendulum.datetime(2024, 1, 1, tz="Pacific/Auckland"),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "data-engineering",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    params={"run_date": None},
    tags=["exchange-rates", "analytics"],
)
def exchange_rate_pipeline():
    """Build the daily exchange-rate pipeline task graph."""

    @task
    def ingest_daily_rates() -> int:
        config = load_config()
        engine = create_database_engine()
        try:
            run_date = _target_date()
            rates = fetch_exchange_rates(
                start_date=run_date,
                base_currency=config.base_currency,
                quote_currencies=config.quote_currencies,
                base_url=config.frankfurter_base_url,
            )
            if rates.empty:
                raise AirflowSkipException(
                    f"No exchange rates were published for {run_date}; "
                    "skipping this non-publication date"
                )
            return load_raw_exchange_rates(rates, engine)
        finally:
            engine.dispose()

    @task
    def refresh_analytics() -> None:
        load_config()
        engine = create_database_engine()
        try:
            run_transformations(engine)
        finally:
            engine.dispose()

    @task
    def check_data_quality() -> dict[str, int | str]:
        config = load_config()
        engine = create_database_engine()
        try:
            return run_data_quality_checks(
                engine,
                expected_date=_target_date(),
                expected_quote_count=len(config.quote_currencies),
            )
        finally:
            engine.dispose()

    ingestion = ingest_daily_rates()
    transformation = refresh_analytics()
    quality = check_data_quality()
    ingestion >> transformation >> quality


exchange_rate_pipeline()
