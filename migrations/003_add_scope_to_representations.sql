-- Parliament — Add scope and jurisdiction_id to representations (Milestone 2.4.5)
--
-- scope distinguishes district-based reps from role-based reps (PM, Premier,
-- Mayor, cabinet members). jurisdiction_id is added as a denormalized field
-- so role-based representations (which have NULL district_id) can still be
-- queried by jurisdiction efficiently.
--
-- This migration is idempotent — uses IF NOT EXISTS where supported.

-- ── Scope column (idempotent: skip if already present) ───────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'representations' AND column_name = 'scope'
    ) THEN
        ALTER TABLE representations
        ADD COLUMN scope TEXT NOT NULL DEFAULT 'district';

        ALTER TABLE representations
        ADD CONSTRAINT scope_check CHECK (scope IN ('district', 'role'));

        CREATE INDEX idx_representations_scope ON representations(scope);
    END IF;
END $$;

-- ── jurisdiction_id column (idempotent) ──────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'representations' AND column_name = 'jurisdiction_id'
    ) THEN
        -- Add nullable first so we can backfill
        ALTER TABLE representations
        ADD COLUMN jurisdiction_id UUID REFERENCES jurisdictions(id) ON DELETE CASCADE;

        -- Backfill from existing district links
        UPDATE representations rep
        SET jurisdiction_id = (
            SELECT d.jurisdiction_id FROM districts d WHERE d.id = rep.district_id
        )
        WHERE jurisdiction_id IS NULL
          AND district_id IS NOT NULL;

        -- Now make NOT NULL (every rep must belong to a jurisdiction)
        ALTER TABLE representations
        ALTER COLUMN jurisdiction_id SET NOT NULL;

        CREATE INDEX idx_representations_jurisdiction ON representations(jurisdiction_id);
    END IF;
END $$;

-- ── Constraint: district-scoped reps must have a district_id ─────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_name = 'representations'
          AND constraint_name = 'scope_district_consistency'
    ) THEN
        ALTER TABLE representations
        ADD CONSTRAINT scope_district_consistency
        CHECK (
            (scope = 'district' AND district_id IS NOT NULL)
            OR scope = 'role'
        );
    END IF;
END $$;
