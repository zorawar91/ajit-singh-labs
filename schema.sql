-- Papa Lab Tracker schema for Neon (Postgres)
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS parameters (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    unit            TEXT,
    reference_range TEXT,
    panel           TEXT,
    lo              NUMERIC,
    hi              NUMERIC
);

CREATE TABLE IF NOT EXISTS readings (
    parameter_id  INT NOT NULL REFERENCES parameters(id) ON DELETE CASCADE,
    test_date     DATE NOT NULL,
    value         NUMERIC,
    text_value    TEXT,
    PRIMARY KEY (parameter_id, test_date)
);

CREATE INDEX IF NOT EXISTS idx_readings_date ON readings(test_date);

CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT
);
