-- Parliament — Schema v2 (post-pipeline refactor)
--
-- Three tables, all populated from the agentic pipeline's standardized output:
--   jurisdictions  ← data/jurisdictions.csv (one row per jurisdiction)
--   districts      ← each data/<slug>/<boundary_file> (polygons, via load script)
--   politicians    ← each data/<slug>/politicians.csv (one row per person per role)
--
-- All three are single shared tables; every jurisdiction's rows coexist,
-- distinguished by jurisdiction_slug. register/export operations are scoped
-- to one slug and never touch other jurisdictions' rows.
--
-- De-bilingualized: all text columns are plain text (no jsonb language maps).
-- Bilingual support is deferred to a future schema revision.

-- ── Extensions ───────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS postgis;


-- ── Jurisdictions ────────────────────────────────────────────────────
-- One row per registered jurisdiction. slug is the natural primary key and
-- the join key used by districts and politicians.
CREATE TABLE jurisdictions (
    slug                          TEXT PRIMARY KEY,
    name                          TEXT NOT NULL,
    level                         TEXT NOT NULL,
    country_code                  TEXT NOT NULL,
    province_code                 TEXT,
    parent_slug                   TEXT REFERENCES jurisdictions(slug) ON DELETE SET NULL,
    governance_type               TEXT NOT NULL,
    partisan                      BOOLEAN NOT NULL DEFAULT false,
    district_term                 TEXT,
    role_label_singular           TEXT,
    role_label_plural             TEXT,
    expected_district_count       INTEGER,
    last_election                 DATE,
    election_date_set             BOOLEAN NOT NULL DEFAULT false,
    next_election                 DATE,
    term_duration_years           INTEGER,
    governance_summary            TEXT,
    boundary_file                 TEXT,
    boundary_district_id_column   TEXT,
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT level_check CHECK (level IN ('federal', 'provincial', 'municipal', 'state', 'territorial')),
    CONSTRAINT governance_type_check CHECK (governance_type IN ('ward_based', 'at_large', 'nested_borough', 'consensus'))
);

CREATE INDEX idx_jurisdictions_level ON jurisdictions(level);
CREATE INDEX idx_jurisdictions_country_province ON jurisdictions(country_code, province_code);


-- ── Districts ────────────────────────────────────────────────────────
-- One row per geographic district (ward, riding, borough). Populated from
-- boundary files by the export agent's load script. external_id is the
-- byte-exact value from the boundary file's identifier column, and is the
-- join key to politicians.district_id.
CREATE TABLE districts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction_slug   TEXT NOT NULL REFERENCES jurisdictions(slug) ON DELETE CASCADE,
    external_id         TEXT NOT NULL,
    name                TEXT,
    boundary            GEOMETRY(Geometry, 4326) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (jurisdiction_slug, external_id)
);

-- Spatial index — critical for fast point-in-polygon lookups
CREATE INDEX idx_districts_boundary ON districts USING GIST (boundary);
CREATE INDEX idx_districts_jurisdiction ON districts(jurisdiction_slug);


-- ── Politicians ──────────────────────────────────────────────────────
-- One row per politician per role. A person holding multiple roles within a
-- jurisdiction appears in multiple rows sharing one uuid. The uuid is
-- jurisdiction-scoped (UUID5 of <slug>|<first_name>|<last_name>), so the same
-- uuid can legitimately recur across the role rows of one person. Therefore
-- uuid is NOT a primary key — a surrogate id is.
CREATE TABLE politicians (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uuid                UUID NOT NULL,
    jurisdiction_slug   TEXT NOT NULL REFERENCES jurisdictions(slug) ON DELETE CASCADE,
    role_scope          TEXT NOT NULL,
    district_id         TEXT,
    district_name       TEXT,
    honorific           TEXT,
    first_name          TEXT NOT NULL,
    last_name           TEXT NOT NULL,
    standard_role       TEXT NOT NULL,
    specific_title      TEXT NOT NULL,
    party_name          TEXT,
    date_elected        DATE,
    next_election       DATE,
    phone               TEXT,
    email               TEXT,
    website             TEXT,
    photo_url           TEXT,
    source_url          TEXT,
    last_verified       DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT role_scope_check CHECK (role_scope IN ('district', 'role')),
    CONSTRAINT standard_role_check CHECK (standard_role IN ('representative', 'executive', 'cabinet', 'misc')),
    -- district-scoped rows must carry a district_id; role-scoped rows must not
    CONSTRAINT scope_district_consistency CHECK (
        (role_scope = 'district' AND district_id IS NOT NULL)
        OR (role_scope = 'role' AND district_id IS NULL)
    )
);

CREATE INDEX idx_politicians_jurisdiction ON politicians(jurisdiction_slug);
CREATE INDEX idx_politicians_uuid ON politicians(uuid);
CREATE INDEX idx_politicians_scope ON politicians(role_scope);
-- Composite index for the core district lookup: politicians in a jurisdiction
-- matching a district external_id.
CREATE INDEX idx_politicians_juris_district ON politicians(jurisdiction_slug, district_id);


-- ── updated_at triggers ──────────────────────────────────────────────
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

CREATE TRIGGER politicians_updated_at BEFORE UPDATE ON politicians
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
