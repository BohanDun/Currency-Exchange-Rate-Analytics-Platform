TRUNCATE TABLE fact_rolling_volatility;

WITH rolling_metrics AS (
    SELECT
        rate_date,
        base_currency,
        quote_currency,
        currency_pair,
        daily_return,
        source,
        COUNT(daily_return) OVER window_7 AS observations_7,
        COUNT(daily_return) OVER window_30 AS observations_30,
        STDDEV_SAMP(daily_return) OVER window_7 AS stddev_7,
        STDDEV_SAMP(daily_return) OVER window_30 AS stddev_30
    FROM fact_daily_returns
    WINDOW
        window_7 AS (
            PARTITION BY base_currency, quote_currency, source
            ORDER BY rate_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ),
        window_30 AS (
            PARTITION BY base_currency, quote_currency, source
            ORDER BY rate_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        )
)
INSERT INTO fact_rolling_volatility (
    rate_date,
    base_currency,
    quote_currency,
    currency_pair,
    daily_return,
    rolling_volatility_7,
    rolling_volatility_30,
    observations_7,
    observations_30,
    source
)
SELECT
    rate_date,
    base_currency,
    quote_currency,
    currency_pair,
    daily_return,
    CASE WHEN observations_7 = 7 THEN stddev_7 END,
    CASE WHEN observations_30 = 30 THEN stddev_30 END,
    observations_7,
    observations_30,
    source
FROM rolling_metrics;
