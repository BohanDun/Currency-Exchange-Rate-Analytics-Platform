"""Tests for Airflow DAG contracts and persisted data-quality checks."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.validation.quality_checks import DataQualityError, run_data_quality_checks

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeEngine:
    def __init__(self, row: dict[str, int]) -> None:
        self.connection = Mock()
        self.connection.execute.return_value.mappings.return_value.one.return_value = (
            row
        )

    @contextmanager
    def connect(self):
        yield self.connection


def quality_row(**overrides: int) -> dict[str, int]:
    row = {
        "daily_raw_rows": 5,
        "raw_rows": 3655,
        "clean_rows": 3655,
        "return_rows": 3655,
        "volatility_rows": 3655,
        "anomaly_rows": 3655,
        "invalid_raw_rows": 0,
    }
    row.update(overrides)
    return row


def test_quality_checks_return_a_small_airflow_result() -> None:
    result = run_data_quality_checks(
        FakeEngine(quality_row()),
        expected_date="2025-01-02",
        expected_quote_count=5,
    )

    assert result == {
        "checked_date": "2025-01-02",
        "daily_raw_rows": 5,
        "total_rows_per_layer": 3655,
    }


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"daily_raw_rows": 4}, "expected 5 raw rows"),
        ({"anomaly_rows": 3654}, "layer row counts differ"),
        ({"invalid_raw_rows": 1}, "invalid raw row"),
    ],
)
def test_quality_checks_reject_bad_persisted_data(
    overrides: dict[str, int], message: str
) -> None:
    with pytest.raises(DataQualityError, match=message):
        run_data_quality_checks(
            FakeEngine(quality_row(**overrides)),
            expected_date="2025-01-02",
            expected_quote_count=5,
        )


def test_dag_uses_airflow_3_sdk_and_expected_task_order() -> None:
    dag_source = (PROJECT_ROOT / "dags" / "exchange_rate_pipeline_dag.py").read_text(
        encoding="utf-8"
    )

    assert "from airflow.sdk import dag, get_current_context, task" in dag_source
    assert "from airflow.exceptions import AirflowSkipException" in dag_source
    assert 'schedule="0 6 * * *"' in dag_source
    assert "catchup=False" in dag_source
    assert '"retries": 2' in dag_source
    assert "ingestion >> transformation >> quality" in dag_source
    assert "ingest_daily_rates" in dag_source
    assert "refresh_analytics" in dag_source
    assert "check_data_quality" in dag_source
    assert "if rates.empty:" in dag_source
    assert "raise AirflowSkipException" in dag_source
