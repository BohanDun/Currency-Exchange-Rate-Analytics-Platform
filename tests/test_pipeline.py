"""Tests for shared configuration and the end-to-end pipeline runner."""

from unittest.mock import Mock, patch

import pytest

from src.pipeline import run_pipeline
from src.utils.config import load_config
from src.utils.logger import configure_logging


def test_loads_and_normalises_application_config() -> None:
    config = load_config(
        {
            "FRANKFURTER_BASE_URL": "https://example.test/",
            "BASE_CURRENCY": "eur",
            "QUOTE_CURRENCIES": "usd, GBP,usd",
        }
    )

    assert config.frankfurter_base_url == "https://example.test"
    assert config.base_currency == "EUR"
    assert config.quote_currencies == ("USD", "GBP")


@pytest.mark.parametrize(
    "environment",
    [
        {"FRANKFURTER_BASE_URL": "http://insecure.test"},
        {"BASE_CURRENCY": "EURO"},
        {"QUOTE_CURRENCIES": ""},
        {"BASE_CURRENCY": "EUR", "QUOTE_CURRENCIES": "USD,EUR"},
    ],
)
def test_rejects_invalid_application_config(environment: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        load_config(environment)


def test_rejects_invalid_log_level() -> None:
    with pytest.raises(ValueError, match="Invalid log level"):
        configure_logging("LOUD")


@patch("src.pipeline.run_transformations")
@patch("src.pipeline.load_raw_exchange_rates", return_value=2)
@patch("src.pipeline.fetch_exchange_rates")
@patch("src.pipeline.create_database_engine")
@patch("src.pipeline.load_config")
def test_pipeline_runs_each_stage_and_disposes_engine(
    mock_config: Mock,
    mock_create_engine: Mock,
    mock_fetch: Mock,
    mock_load: Mock,
    mock_transform: Mock,
) -> None:
    mock_config.return_value.base_currency = "EUR"
    mock_config.return_value.quote_currencies = ("USD", "GBP")
    mock_config.return_value.frankfurter_base_url = "https://api.example.test"
    engine = mock_create_engine.return_value
    frame = mock_fetch.return_value

    result = run_pipeline("2025-01-01", "2025-01-31")

    assert result == 2
    mock_fetch.assert_called_once_with(
        start_date="2025-01-01",
        end_date="2025-01-31",
        base_currency="EUR",
        quote_currencies=("USD", "GBP"),
        base_url="https://api.example.test",
    )
    mock_load.assert_called_once_with(frame, engine)
    mock_transform.assert_called_once_with(engine)
    engine.dispose.assert_called_once_with()


@patch("src.pipeline.run_transformations", side_effect=RuntimeError("failed"))
@patch("src.pipeline.load_raw_exchange_rates", return_value=2)
@patch("src.pipeline.fetch_exchange_rates")
@patch("src.pipeline.create_database_engine")
@patch("src.pipeline.load_config")
def test_pipeline_disposes_engine_after_failure(
    mock_config: Mock,
    mock_create_engine: Mock,
    _mock_fetch: Mock,
    _mock_load: Mock,
    _mock_transform: Mock,
) -> None:
    mock_config.return_value.base_currency = "EUR"
    mock_config.return_value.quote_currencies = ("USD",)
    mock_config.return_value.frankfurter_base_url = "https://api.example.test"
    engine = mock_create_engine.return_value

    with pytest.raises(RuntimeError, match="failed"):
        run_pipeline("2025-01-01")

    engine.dispose.assert_called_once_with()
