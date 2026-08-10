-- Parliament — Migration 002: raw_candidates
--
-- The raw candidate roster: one row per person running for mayor or council in a
-- municipality's election, produced by the candidate pipeline (intake → source-
-- discovery → acquisition → extraction → consolidation → validation → writer →
-- export) and loaded here by candidate-export.
--
-- This is the "who is on the ballot / who to invite" table. It is the source the
-- frontend reads to show every candidate in a race — responders and non-responders
-- alike — and the table the forthcoming `invitations` table foreign-keys, via the
-- primary-key `uuid`. It is cleared/archived after the election; winners are
-- promoted into `politicians` with a fresh politician uuid at term start.
--
-- Parallel to `politicians` (001) but deliberately distinct: candidates are a
-- separate identity space (not yet elected, no party/portfolio, campaign-only
-- lifespan), so they get their own table rather than overloading `politicians`.
--
-- One structural difference from `politicians` that everything downstream turns on:
-- here `uuid` is the PRIMARY KEY. A politician holds several role-rows sharing one
-- uuid, so politicians.uuid cannot be a key and that table carries a surrogate id.
-- A candidate holds exactly one nomination — one candidate is one row is one uuid —
-- so uuid is the natural key, with no surrogate. That singular identity is what lets
-- candidate-export UPSERT on uuid (preserving the row so an attached invitation stays
-- valid) instead of the delete-then-insert the incumbent export uses, and it is the
-- key the invitations table will reference.

-- ── Raw candidates ───────────────────────────────────────────────────
-- `uuid` is the deterministic candidate identity (UUID5 of
-- slug|first|last|role_scope|district_id, generated at consolidation) and the
-- primary key. `jurisdiction_slug` + `district_id` join to districts.external_id
-- for a voter's ward lookup, exactly as politicians do.
CREATE TABLE raw_candidates (
    uuid                UUID PRIMARY KEY,
    jurisdiction_slug   TEXT NOT NULL REFERENCES jurisdictions(slug) ON DELETE CASCADE,
    first_name          TEXT NOT NULL,
    last_name           TEXT NOT NULL,
    email               TEXT,
    phone               TEXT,
    role_scope          TEXT NOT NULL,
    district_id         TEXT,
    district_name       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Vocabulary matches politicians: `district` for ward-bound council candidates,
    -- `role` for jurisdiction-wide ones (mayors, and at-large councillors with no ward).
    CONSTRAINT raw_candidates_role_scope_check CHECK (role_scope IN ('district', 'role')),

    -- District-scoped rows carry a district_id; role-scoped rows must not. Mirrors
    -- politicians' scope_district_consistency. Enforced at load by candidate-export
    -- (empty CSV cell → NULL) and pre-checked by candidate-validation.
    CONSTRAINT raw_candidates_scope_district_consistency CHECK (
        (role_scope = 'district' AND district_id IS NOT NULL)
        OR (role_scope = 'role' AND district_id IS NULL)
    )
);

-- Core lookup: candidates in a ward, and — via the leftmost prefix — candidates in a
-- jurisdiction. One composite covers both, so no separate jurisdiction_slug index is
-- needed (this is where the candidate table is leaner than politicians). uuid already
-- has a unique index as the primary key, which serves both the export UPSERT's
-- ON CONFLICT (uuid) lookup and the invitations foreign key.
CREATE INDEX idx_raw_candidates_juris_district ON raw_candidates(jurisdiction_slug, district_id);


-- ── updated_at trigger ───────────────────────────────────────────────
-- Reuses set_updated_at() from migration 001. Stamps updated_at = NOW() on every
-- UPDATE, including export's upserts.
CREATE TRIGGER raw_candidates_updated_at BEFORE UPDATE ON raw_candidates
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
