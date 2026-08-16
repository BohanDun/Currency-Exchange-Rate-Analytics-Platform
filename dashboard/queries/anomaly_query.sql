SELECT
    rate_date,
    currency_pair,
    daily_return,
    anomaly_score,
    is_anomaly,
    anomaly_reason
FROM fact_anomaly_flags
WHERE currency_pair = :currency_pair
  AND rate_date BETWEEN :start_date AND :end_date
ORDER BY rate_date;
