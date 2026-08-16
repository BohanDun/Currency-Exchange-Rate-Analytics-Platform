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
