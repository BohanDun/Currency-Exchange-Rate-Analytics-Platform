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

## Processing guarantees

- Schema checks reject missing columns, malformed currency codes, non-positive
  rates, duplicates, blank sources, and future dates.
- Future-date validation uses the configured `PIPELINE_TIMEZONE`, so the
  business date remains correct around UTC day boundaries.
- Raw records use an upsert on their business key, making retries idempotent.
- Analytics tables refresh in a single transaction to prevent partial results.
- Configuration and secrets come from environment variables; `.env` remains
  local and `.env.example` documents the required settings.

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
controlled historical reprocessing. If Frankfurter returns no observations for
a weekend or public holiday, ingestion raises Airflow's skip signal; downstream
tasks are skipped and the expected non-publication date does not become a
failed run.

Airflow's API server, scheduler, and DAG processor share the same JWT secret.
This allows the scheduler to authenticate task execution requests consistently
across containers. The DAG limits active runs to one, so a manually triggered
run waits safely when a scheduled run is already active.

## Failure and retry behaviour

1. A transient API or task failure is retried twice at five-minute intervals.
2. Validation fails before invalid observations reach PostgreSQL.
3. A failed SQL statement rolls back the complete analytics refresh.
4. The data-quality task prevents a run from being marked successful when
   expected currencies or row-count invariants are missing.
