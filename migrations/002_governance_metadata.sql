-- Parliament — Governance Metadata (Milestone 2.4)
--
-- Populates jurisdictions.governance with declarative metadata describing
-- how each jurisdiction is governed. The frontend consumes this to render
-- jurisdictions correctly without jurisdiction-specific conditionals.
--
-- This script is idempotent — re-running it overwrites the governance
-- field with the latest values defined here.

-- ── Canada (federal) ─────────────────────────────────────────────────
UPDATE jurisdictions
SET governance = jsonb_build_object(
    'type', 'ward_based',
    'partisan', true,
    'rep_count_expected', 1,
    'rep_role_labels', jsonb_build_object(
        'en', jsonb_build_object('singular', 'MP', 'plural', 'MPs'),
        'fr', jsonb_build_object('singular', 'député', 'plural', 'députés')
    ),
    'district_term', jsonb_build_object(
        'en', 'Riding',
        'fr', 'Circonscription'
    ),
    'election_cycle_years', 4,
    'max_term_years', 5
)
WHERE slug = 'ca_federal';


-- ── Ontario (provincial) ─────────────────────────────────────────────
UPDATE jurisdictions
SET governance = jsonb_build_object(
    'type', 'ward_based',
    'partisan', true,
    'rep_count_expected', 1,
    'rep_role_labels', jsonb_build_object(
        'en', jsonb_build_object('singular', 'MPP', 'plural', 'MPPs'),
        'fr', jsonb_build_object('singular', 'député provincial', 'plural', 'députés provinciaux')
    ),
    'district_term', jsonb_build_object(
        'en', 'Riding',
        'fr', 'Circonscription'
    ),
    'election_cycle_years', 4
)
WHERE slug = 'ca_on';


-- ── Toronto (municipal) ──────────────────────────────────────────────
UPDATE jurisdictions
SET governance = jsonb_build_object(
    'type', 'ward_based',
    'partisan', false,
    'rep_count_expected', 1,
    'rep_role_labels', jsonb_build_object(
        'en', jsonb_build_object('singular', 'Councillor', 'plural', 'Councillors'),
        'fr', jsonb_build_object('singular', 'Conseiller', 'plural', 'Conseillers')
    ),
    'district_term', jsonb_build_object(
        'en', 'Ward',
        'fr', 'Quartier'
    ),
    'has_mayor', true,
    'election_cycle_years', 4
)
WHERE slug = 'ca_on_toronto';
