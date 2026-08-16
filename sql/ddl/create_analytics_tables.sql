CREATE TABLE IF NOT EXISTS clean_exchange_rates (
    rate_date DATE NOT NULL,
    base_currency CHAR(3) NOT NULL,
    quote_currency CHAR(3) NOT NULL,
    currency_pair VARCHAR(7) NOT NULL,
    rate NUMERIC(20, 10) NOT NULL CHECK (rate > 0),
    source VARCHAR(50) NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT clean_exchange_rates_pk PRIMARY KEY (
        rate_date,
        base_currency,
        quote_currency,
        source
    )
);

CREATE TABLE IF NOT EXISTS fact_daily_returns (
    rate_date DATE NOT NULL,
    base_currency CHAR(3) NOT NULL,
    quote_currency CHAR(3) NOT NULL,
    currency_pair VARCHAR(7) NOT NULL,
    rate NUMERIC(20, 10) NOT NULL,
    previous_rate NUMERIC(20, 10),
    daily_return DOUBLE PRECISION,
    daily_pct_change DOUBLE PRECISION,
    source VARCHAR(50) NOT NULL,
    CONSTRAINT fact_daily_returns_pk PRIMARY KEY (
        rate_date,
        base_currency,
        quote_currency,
        source
    )
);

CREATE TABLE IF NOT EXISTS fact_rolling_volatility (
    rate_date DATE NOT NULL,
    base_currency CHAR(3) NOT NULL,
    quote_currency CHAR(3) NOT NULL,
    currency_pair VARCHAR(7) NOT NULL,
    daily_return DOUBLE PRECISION,
    rolling_volatility_7 DOUBLE PRECISION,
    rolling_volatility_30 DOUBLE PRECISION,
    observations_7 INTEGER NOT NULL,
    observations_30 INTEGER NOT NULL,
    source VARCHAR(50) NOT NULL,
    CONSTRAINT fact_rolling_volatility_pk PRIMARY KEY (
        rate_date,
        base_currency,
        quote_currency,
        source
    )
);

CREATE TABLE IF NOT EXISTS fact_anomaly_flags (
    rate_date DATE NOT NULL,
    base_currency CHAR(3) NOT NULL,
    quote_currency CHAR(3) NOT NULL,
    currency_pair VARCHAR(7) NOT NULL,
    daily_return DOUBLE PRECISION,
    prior_mean_30 DOUBLE PRECISION,
    prior_volatility_30 DOUBLE PRECISION,
    anomaly_score DOUBLE PRECISION,
    is_anomaly BOOLEAN NOT NULL,
    anomaly_reason VARCHAR(100),
    source VARCHAR(50) NOT NULL,
    CONSTRAINT fact_anomaly_flags_pk PRIMARY KEY (
        rate_date,
        base_currency,
        quote_currency,
        source
    )
);

CREATE INDEX IF NOT EXISTS clean_exchange_rates_pair_date_idx
    ON clean_exchange_rates (currency_pair, rate_date DESC);
CREATE INDEX IF NOT EXISTS fact_daily_returns_pair_date_idx
    ON fact_daily_returns (currency_pair, rate_date DESC);
CREATE INDEX IF NOT EXISTS fact_rolling_volatility_pair_date_idx
    ON fact_rolling_volatility (currency_pair, rate_date DESC);
CREATE INDEX IF NOT EXISTS fact_anomaly_flags_pair_date_idx
    ON fact_anomaly_flags (currency_pair, rate_date DESC);
CREATE INDEX IF NOT EXISTS fact_anomaly_flags_true_idx
    ON fact_anomaly_flags (currency_pair, rate_date DESC)
    WHERE is_anomaly;
