# Data model

## Raw layer

`raw_exchange_rates` preserves the validated API observations. Its business key
is `(rate_date, base_currency, quote_currency, source)`, which makes ingestion
idempotent.

| Column | Meaning |
| --- | --- |
| `rate_date` | Business date of the published exchange rate |
| `base_currency` | Three-letter source currency, currently `EUR` |
| `quote_currency` | Three-letter target currency |
| `rate` | Units of quote currency per one unit of base currency |
| `source` | Upstream provider identifier |
| `ingested_at` | Timestamp when the observation entered the platform |

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

## Analytical definitions

- Daily return: `(current_rate / previous_rate) - 1`.
- Percentage change: `daily_return * 100`.
- Rolling volatility: sample standard deviation of daily returns across the
  latest 7 or 30 observations.
- Anomaly score: z-score against the previous 30 non-null daily returns.
- Anomaly flag: `true` when the absolute anomaly score is greater than `2.0`.

All window calculations are partitioned by base currency, quote currency, and
source, then ordered by `rate_date`. This prevents observations from different
currency pairs from influencing one another.

The current pipeline performs a transactional full refresh of the analytics
layer. This is intentionally simple and reliable for the MVP-sized dataset;
incremental transformations can be introduced if volume later requires them.
