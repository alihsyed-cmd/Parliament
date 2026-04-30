-- Slug for stable, readable URLs (e.g., /representative/ca_on/tom-rakocevic)
-- Unique within a jurisdiction; we resolve collisions in the backfill script.

ALTER TABLE representatives ADD COLUMN IF NOT EXISTS slug TEXT;

-- A composite uniqueness constraint per jurisdiction would be ideal, but
-- representatives don't have a direct jurisdiction column — they're linked
-- via the representations table. So we enforce uniqueness in application
-- code (the backfill script + future inserts), not at the DB layer.

CREATE INDEX IF NOT EXISTS idx_representatives_slug ON representatives (slug);
