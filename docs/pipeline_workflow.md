# Pipeline workflow

```text
Frankfurter API v2
        ↓
fetch_exchange_rates
        ↓
validate_exchange_rates
        ↓
raw_exchange_rates (idempotent upsert)
        ↓
clean_exchange_rates
        ↓
fact_daily_returns
        ↓
fact_rolling_volatility
        ↓
fact_anomaly_flags
```

API loading and the analytics refresh use database transactions. The four
analytics transformations execute in one transaction and in dependency order,
so a failure rolls back the complete refresh.

## Airflow orchestration

The `exchange_rate_analytics_daily` DAG runs at 06:00 in the
`Pacific/Auckland` timezone with catchup disabled and a maximum of one active
run. Each task retries twice with a five-minute delay.

```text
ingest_daily_rates
        ↓
refresh_analytics
        ↓
check_data_quality
```

The ingestion task fetches, validates, and upserts one day's rates. The
transformation task refreshes all analytics tables transactionally. The final
task checks expected daily currency coverage, equal row counts across layers,
and the absence of invalid raw rates. A manual `run_date` parameter supports
controlled historical reprocessing.
