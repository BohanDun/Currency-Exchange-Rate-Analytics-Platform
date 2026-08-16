TRUNCATE TABLE fact_anomaly_flags;

WITH prior_statistics AS (
    SELECT
        rate_date,
        base_currency,
        quote_currency,
        currency_pair,
        daily_return,
        source,
        COUNT(daily_return) OVER prior_window AS prior_observations_30,
        AVG(daily_return) OVER prior_window AS prior_mean_30,
        STDDEV_SAMP(daily_return) OVER prior_window AS prior_volatility_30
    FROM fact_daily_returns
    WINDOW prior_window AS (
        PARTITION BY base_currency, quote_currency, source
        ORDER BY rate_date ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING
    )
), scored AS (
    SELECT
        *,
        CASE
            WHEN prior_observations_30 = 30 AND prior_volatility_30 > 0
            THEN (daily_return - prior_mean_30) / prior_volatility_30
        END AS anomaly_score
    FROM prior_statistics
)
INSERT INTO fact_anomaly_flags (
    rate_date,
    base_currency,
    quote_currency,
    currency_pair,
    daily_return,
    prior_mean_30,
    prior_volatility_30,
    anomaly_score,
    is_anomaly,
    anomaly_reason,
    source
)
SELECT
    rate_date,
    base_currency,
    quote_currency,
    currency_pair,
    daily_return,
    prior_mean_30,
    prior_volatility_30,
    anomaly_score,
    COALESCE(ABS(anomaly_score) > 2.0, FALSE),
    CASE
        WHEN ABS(anomaly_score) > 2.0
        THEN 'Absolute z-score exceeded 2.0 versus prior 30 observations'
    END,
    source
FROM scored;
