"""Tests for parameterised dashboard data access."""

from datetime import date
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from dashboard.data import get_filter_options, load_dashboard_data, read_query


def test_all_dashboard_queries_are_parameterised_and_ordered() -> None:
    for name in ("trend_query", "returns_query", "volatility_query", "anomaly_query"):
        sql = read_query(name)
        assert ":currency_pair" in sql
        assert ":start_date" in sql
        assert ":end_date" in sql
        assert "ORDER BY rate_date" in sql


def test_query_name_cannot_escape_query_directory() -> None:
    with pytest.raises(ValueError, match="Invalid query name"):
        read_query("../secret")


@patch("dashboard.data.pd.read_sql_query")
def test_returns_filter_options(mock_read_sql: Mock) -> None:
    mock_read_sql.return_value = pd.DataFrame(
        {
            "currency_pair": ["EUR/USD", "EUR/GBP"],
            "minimum_date": ["2024-01-01", "2024-01-01"],
            "maximum_date": ["2025-12-31", "2025-12-31"],
        }
    )

    pairs, minimum_date, maximum_date = get_filter_options(Mock())

    assert pairs == ["EUR/GBP", "EUR/USD"]
    assert minimum_date == date(2024, 1, 1)
    assert maximum_date == date(2025, 12, 31)


@patch("dashboard.data.pd.read_sql_query")
def test_loads_four_datasets_with_bound_parameters(mock_read_sql: Mock) -> None:
    mock_read_sql.return_value = pd.DataFrame()
    engine = Mock()

    result = load_dashboard_data(engine, "EUR/USD", date(2025, 1, 1), date(2025, 1, 31))

    assert set(result) == {
        "trend_query",
        "returns_query",
        "volatility_query",
        "anomaly_query",
    }
    assert mock_read_sql.call_count == 4
    for call in mock_read_sql.call_args_list:
        assert call.kwargs["params"] == {
            "currency_pair": "EUR/USD",
            "start_date": date(2025, 1, 1),
            "end_date": date(2025, 1, 31),
        }


def test_rejects_reversed_dashboard_dates() -> None:
    with pytest.raises(ValueError, match="start_date cannot be after end_date"):
        load_dashboard_data(Mock(), "EUR/USD", date(2025, 2, 1), date(2025, 1, 1))
