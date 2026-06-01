CREATE TABLE IF NOT EXISTS stg_rejects (
    id SERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    raw_payload JSONB NOT NULL,
    reason TEXT NOT NULL,
    rejected_at TIMESTAMP NOT NULL DEFAULT NOW()
);