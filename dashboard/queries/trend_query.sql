SELECT
    rate_date,
    currency_pair,
    rate,
    source,
    ingested_at
FROM clean_exchange_rates
WHERE currency_pair = :currency_pair
  AND rate_date BETWEEN :start_date AND :end_date
ORDER BY rate_date;
