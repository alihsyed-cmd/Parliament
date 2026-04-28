-- Geocoding cache: postal codes are immutable, so cached results never expire.
-- retrieved_at exists for optional future invalidation if Google improves geocoding accuracy.
CREATE TABLE IF NOT EXISTS geocode_cache (
    postal_code TEXT PRIMARY KEY,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_geocode_cache_retrieved_at ON geocode_cache (retrieved_at);
