SELECT
    rate_date,
    currency_pair,
    daily_return,
    rolling_volatility_7,
    rolling_volatility_30,
    observations_7,
    observations_30
FROM fact_rolling_volatility
WHERE currency_pair = :currency_pair
  AND rate_date BETWEEN :start_date AND :end_date
ORDER BY rate_date;
