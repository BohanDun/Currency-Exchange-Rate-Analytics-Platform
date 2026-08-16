SELECT
    rate_date,
    currency_pair,
    rate,
    previous_rate,
    daily_return,
    daily_pct_change
FROM fact_daily_returns
WHERE currency_pair = :currency_pair
  AND rate_date BETWEEN :start_date AND :end_date
ORDER BY rate_date;
