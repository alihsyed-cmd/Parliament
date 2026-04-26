-- Parliament — Initial Schema (Milestone 2.3)
--
-- Four-table relational schema with PostGIS geometry, i18n-ready jsonb fields,
-- and external_ids for future bill/voting integration.
--
-- Run this once on a fresh Supabase project that has PostGIS enabled.

-- ── Extensions ───────────────────────────────────────────────────────
-- PostGIS should already be enabled at the project level, but this is idempotent
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ── Jurisdictions ────────────────────────────────────────────────────
-- Every government we cover. One row per jurisdiction.
CREATE TABLE jurisdictions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug            TEXT NOT NULL UNIQUE,           -- 'ca_federal', 'ca_on', 'ca_on_toronto'
    name            JSONB NOT NULL,                 -- {"en": "Canada", "fr": "Canada"}
    level           TEXT NOT NULL,                  -- 'federal', 'provincial', 'municipal'
    country_code    TEXT NOT NULL,                  -- 'CA'
    province_code   TEXT,                           -- 'ON', 'BC', NULL for federal
    parent_id       UUID REFERENCES jurisdictions(id) ON DELETE CASCADE,  -- For nested (Montreal boroughs)
    governance      JSONB,                          -- Populated in milestone 2.4
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT level_check CHECK (level IN ('federal', 'provincial', 'municipal'))
);

CREATE INDEX idx_jurisdictions_level ON jurisdictions(level);
CREATE INDEX idx_jurisdictions_country_province ON jurisdictions(country_code, province_code);


-- ── Districts ────────────────────────────────────────────────────────
-- Geographic sub-units. Federal ridings, provincial ridings, wards, boroughs.
-- For at-large jurisdictions (Vancouver), the district IS the whole jurisdiction.
CREATE TABLE districts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    jurisdiction_id UUID NOT NULL REFERENCES jurisdictions(id) ON DELETE CASCADE,
    external_id     TEXT,                           -- WARD_NUMBER, riding number from source
    name            JSONB NOT NULL,                 -- {"en": "Humber River-Black Creek", "fr": "..."}
    boundary        GEOMETRY(Geometry, 4326) NOT NULL,  -- Polygon or MultiPolygon
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (jurisdiction_id, external_id)
);

-- Spatial index — critical for fast point-in-polygon lookups
CREATE INDEX idx_districts_boundary ON districts USING GIST (boundary);
CREATE INDEX idx_districts_jurisdiction ON districts(jurisdiction_id);


-- ── Representatives ──────────────────────────────────────────────────
-- One row per person. Their representations (roles, districts) live in the
-- representations table.
CREATE TABLE representatives (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            JSONB NOT NULL,                 -- {"en": "Hon. Judy A. Sgro", "fr": "..."}
    party           JSONB,                          -- {"en": "Liberal", "fr": "Libéral"}
    email           TEXT,
    phone           TEXT,
    photo_url       TEXT,
    website_url     JSONB,                          -- {"en": "https://...en", "fr": "https://...fr"}
    external_ids    JSONB DEFAULT '{}'::jsonb,      -- {"parl_gc_ca": "1787", ...}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ── Representations ──────────────────────────────────────────────────
-- The join: this representative represents this district, in this role, for this period.
-- A representative can have multiple representations (e.g., MP + Prime Minister).
CREATE TABLE representations (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    representative_id UUID NOT NULL REFERENCES representatives(id) ON DELETE CASCADE,
    district_id       UUID REFERENCES districts(id) ON DELETE CASCADE,  -- NULL for at-large leadership
    role              JSONB NOT NULL,               -- {"en": "MP", "fr": "député"}
    start_date        DATE,
    end_date          DATE,                         -- NULL = currently active
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_representations_rep ON representations(representative_id);
CREATE INDEX idx_representations_district ON representations(district_id);
CREATE INDEX idx_representations_active ON representations(district_id) WHERE end_date IS NULL;


-- ── Updated-at triggers ──────────────────────────────────────────────
-- Automatically maintain updated_at on row changes.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER jurisdictions_updated_at BEFORE UPDATE ON jurisdictions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER districts_updated_at BEFORE UPDATE ON districts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER representatives_updated_at BEFORE UPDATE ON representatives
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER representations_updated_at BEFORE UPDATE ON representations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
