-- Parliament — Migration 002: readable per-jurisdiction politician slugs
--
-- Adds a human-readable URL slug to politicians, used by the API route
--   /representative/<jurisdiction_slug>/<slug>
-- e.g. /representative/ca_on/tom-rakocevic   (shareable, readable, SEO-legible)
--
-- INVARIANT (NOT a row-level UNIQUE constraint — see note):
--   Within a jurisdiction, slug <-> uuid is a bijection:
--     * every row sharing a (jurisdiction_slug, uuid) carries the SAME slug
--     * two DISTINCT uuids in the same jurisdiction never share a slug
--
--   politicians has one row PER ROLE, so a single person (uuid) owns multiple
--   rows (e.g. an MPP who is also Premier; a Brampton councillor who sits for
--   two wards). A UNIQUE(jurisdiction_slug, slug) would reject the second
--   role-row of every such person. The bijection is therefore guaranteed by
--   the slug-generation logic (backfill_politician_slugs.py + the pipeline
--   writer going forward), NOT by a row-level constraint. A DB-enforced
--   guarantee would require slug to live on a per-person table — the future
--   `persons` identity layer noted in docs/schemas.md — which is out of scope
--   for this pass.
--
-- Uniqueness scope: per-jurisdiction only. The route is
-- /<jurisdiction_slug>/<slug>, so slug needs to resolve uniquely *alongside*
-- the jurisdiction slug, not globally.

ALTER TABLE politicians ADD COLUMN IF NOT EXISTS slug TEXT;

-- Resolution index for /representative/<jurisdiction_slug>/<slug>.
-- Non-unique BY DESIGN (see note above).
CREATE INDEX IF NOT EXISTS idx_politicians_juris_slug
    ON politicians (jurisdiction_slug, slug);

-- NOTE: slug is left nullable here so the column can be added before the
-- backfill runs. After backfill_politician_slugs.py has populated every row
-- AND the pipeline writer sets slug on insert, this can be tightened:
--   ALTER TABLE politicians ALTER COLUMN slug SET NOT NULL;
