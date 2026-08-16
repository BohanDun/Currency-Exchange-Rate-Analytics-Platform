TRUNCATE TABLE clean_exchange_rates;

INSERT INTO clean_exchange_rates (
    rate_date,
    base_currency,
    quote_currency,
    currency_pair,
    rate,
    source,
    ingested_at
)
SELECT
    rate_date,
    UPPER(TRIM(base_currency)),
    UPPER(TRIM(quote_currency)),
    UPPER(TRIM(base_currency)) || '/' || UPPER(TRIM(quote_currency)),
    rate,
    LOWER(TRIM(source)),
    ingested_at
FROM raw_exchange_rates
WHERE rate > 0
  AND base_currency <> quote_currency;
