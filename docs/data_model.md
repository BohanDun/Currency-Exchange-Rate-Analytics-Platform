# Data model

## Raw layer

`raw_exchange_rates` preserves the validated API observations. Its business key
is `(rate_date, base_currency, quote_currency, source)`, which makes ingestion
idempotent.

## Analytics layer

| Table | Grain | Purpose |
| --- | --- | --- |
| `clean_exchange_rates` | One rate per date, pair, and source | Standardised analytical source |
| `fact_daily_returns` | One rate per date, pair, and source | Previous rate, decimal return, and percentage change |
| `fact_rolling_volatility` | One return per date, pair, and source | Sample standard deviation over 7 and 30 observations |
| `fact_anomaly_flags` | One return per date, pair, and source | Prior-30-observation z-score and explainable anomaly flag |

The first observation for a pair has no daily return. Rolling volatility is
reported only when its complete 7- or 30-observation window is available.
Anomalies require 30 prior non-null returns and are flagged when the absolute
z-score exceeds `2.0`. The current observation is excluded from its baseline.

The current pipeline performs a transactional full refresh of the analytics
layer. This is intentionally simple and reliable for the MVP-sized dataset;
incremental transformations can be introduced if volume later requires them.
