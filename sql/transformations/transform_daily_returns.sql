TRUNCATE TABLE fact_daily_returns;

WITH rates_with_previous AS (
    SELECT
        rate_date,
        base_currency,
        quote_currency,
        currency_pair,
        rate,
        LAG(rate) OVER (
            PARTITION BY base_currency, quote_currency, source
            ORDER BY rate_date
        ) AS previous_rate,
        source
    FROM clean_exchange_rates
)
INSERT INTO fact_daily_returns (
    rate_date,
    base_currency,
    quote_currency,
    currency_pair,
    rate,
    previous_rate,
    daily_return,
    daily_pct_change,
    source
)
SELECT
    rate_date,
    base_currency,
    quote_currency,
    currency_pair,
    rate,
    previous_rate,
    CASE
        WHEN previous_rate IS NULL THEN NULL
        ELSE (rate / previous_rate)::DOUBLE PRECISION - 1.0
    END,
    CASE
        WHEN previous_rate IS NULL THEN NULL
        ELSE ((rate / previous_rate)::DOUBLE PRECISION - 1.0) * 100.0
    END,
    source
FROM rates_with_previous;
