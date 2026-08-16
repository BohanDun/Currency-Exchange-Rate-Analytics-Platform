CREATE TABLE IF NOT EXISTS raw_exchange_rates (
    rate_date DATE NOT NULL,
    base_currency CHAR(3) NOT NULL,
    quote_currency CHAR(3) NOT NULL,
    rate NUMERIC(20, 10) NOT NULL CHECK (rate > 0),
    source VARCHAR(50) NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT raw_exchange_rates_pk PRIMARY KEY (
        rate_date,
        base_currency,
        quote_currency,
        source
    ),
    CONSTRAINT raw_exchange_rates_different_currencies_ck CHECK (
        base_currency <> quote_currency
    )
);

CREATE INDEX IF NOT EXISTS raw_exchange_rates_pair_date_idx
    ON raw_exchange_rates (base_currency, quote_currency, rate_date DESC);
