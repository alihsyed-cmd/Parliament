#!/usr/bin/env bash
#
# create_known_sources.sh
#
# Seeds data/_registry/known_sources.yaml with confirmed government
# sources for the three already-registered Parliament jurisdictions
# (ca_federal, ca_on, ca_on_toronto).
#
# Usage (from the Parliament project root):
#   chmod +x create_known_sources.sh
#   ./create_known_sources.sh
#
# Will refuse to overwrite an existing registry file. Move or remove
# data/_registry/known_sources.yaml first if you want to re-seed.

set -euo pipefail

REGISTRY_DIR="data/_registry"
REGISTRY_FILE="${REGISTRY_DIR}/known_sources.yaml"

if [[ -f "${REGISTRY_FILE}" ]]; then
  echo "ERROR: ${REGISTRY_FILE} already exists." >&2
  echo "Move or remove it first, then re-run this script." >&2
  exit 1
fi

mkdir -p "${REGISTRY_DIR}"

cat > "${REGISTRY_FILE}" <<'EOF'
# Parliament — Known Sources Registry
#
# One entry per (slug, source_type) pair. Used by the agentic pipeline's
# source discovery stage as ground truth, and grown over time as new
# jurisdictions are registered.
#
# Schema
# ------
#   slug            jurisdiction slug, matches jurisdictions.csv
#   source_type     boundaries | representatives | executive | cabinet | misc | metadata
#   url             direct URL to the source (page or download)
#   authority       human-readable name of the issuing government body
#   format          shapefile | geojson | csv | xml | html | json
#   notes           free-text context
#   last_confirmed  YYYY-MM-DD, date this URL was last verified to work
#
# Conventions
# -----------
# - Prefer the most specific authoritative URL available.
# - Verify any URL marked "# TODO: verify" by hand before relying on it.
# - When a URL changes, update last_confirmed.
# - When a source is retired, move the entry to known_sources_retired.yaml
#   rather than deleting (audit trail).

sources:

  # ─────────────────────────────────────────────────────────────────────
  # Federal — Canada
  # ─────────────────────────────────────────────────────────────────────

  - slug: ca_federal
    source_type: boundaries
    url: https://www.elections.ca/content.aspx?section=res&dir=cir/maps2&document=index&lang=e
    authority: Elections Canada
    format: shapefile
    notes: Federal electoral district boundaries. 343-seat model (2023 redistribution). Confirmed working in lookup.py.
    last_confirmed: 2026-05-15  # TODO: confirm direct shapefile download URL

  - slug: ca_federal
    source_type: representatives
    url: https://www.ourcommons.ca/Members/en/search/xml
    authority: House of Commons of Canada
    format: xml
    notes: Current MPs roster including riding, party, contact info. Confirmed working in lookup.py.
    last_confirmed: 2026-05-15

  - slug: ca_federal
    source_type: executive
    url: https://www.pm.gc.ca/en
    authority: Office of the Prime Minister
    format: html
    notes: Prime Minister page. Extract name, photo, contact via HTML parsing.
    last_confirmed: 2026-05-15  # TODO: verify

  - slug: ca_federal
    source_type: cabinet
    url: https://www.pm.gc.ca/en/cabinet
    authority: Office of the Prime Minister
    format: html
    notes: Current federal cabinet ministers and portfolios.
    last_confirmed: 2026-05-15  # TODO: verify

  - slug: ca_federal
    source_type: misc
    url: https://www.ourcommons.ca/Parliamentarians/en/HouseOfficers
    authority: House of Commons of Canada
    format: html
    notes: House officers including Speaker, Government and Opposition House Leaders.
    last_confirmed: 2026-05-15  # TODO: verify

  - slug: ca_federal
    source_type: metadata
    url: https://www.elections.ca/content.aspx?section=ele&dir=turn&document=index&lang=e
    authority: Elections Canada
    format: html
    notes: Election dates and term information. Fixed-date election framework (Canada Elections Act s.56.1).
    last_confirmed: 2026-05-15  # TODO: verify

  # ─────────────────────────────────────────────────────────────────────
  # Provincial — Ontario
  # ─────────────────────────────────────────────────────────────────────

  - slug: ca_on
    source_type: boundaries
    url: https://www.elections.on.ca/en/voting-in-ontario/electoral-district-information.html
    authority: Elections Ontario
    format: shapefile
    notes: Provincial electoral district boundaries. 124-seat model. Confirmed working in lookup.py.
    last_confirmed: 2026-05-15  # TODO: confirm direct shapefile download URL

  - slug: ca_on
    source_type: representatives
    url: https://www.ola.org/en/members/current
    authority: Legislative Assembly of Ontario
    format: html
    notes: Current MPPs. Roster also available via member search export.
    last_confirmed: 2026-05-15

  - slug: ca_on
    source_type: executive
    url: https://www.ontario.ca/page/premier-of-ontario
    authority: Government of Ontario
    format: html
    notes: Premier page. URL may change between Premiers; pipeline should treat ontario.ca/page/premier-* as the canonical pattern.
    last_confirmed: 2026-05-15  # TODO: verify

  - slug: ca_on
    source_type: cabinet
    url: https://www.ola.org/en/members/current/ministers
    authority: Legislative Assembly of Ontario
    format: html
    notes: Current Ontario cabinet ministers. Confirmed working — source for ontario_ministers.csv retrieved 2026-04-27.
    last_confirmed: 2026-04-27

  - slug: ca_on
    source_type: misc
    url: https://www.ola.org/en/members/parliamentary-roles
    authority: Legislative Assembly of Ontario
    format: html
    notes: Opposition leader, critics, party leaders, parliamentary roles.
    last_confirmed: 2026-05-15  # TODO: verify

  - slug: ca_on
    source_type: metadata
    url: https://www.elections.on.ca/
    authority: Elections Ontario
    format: html
    notes: Election dates and term information. Ontario operates on fixed 4-year terms.
    last_confirmed: 2026-05-15  # TODO: verify

  # ─────────────────────────────────────────────────────────────────────
  # Municipal — Toronto
  # ─────────────────────────────────────────────────────────────────────

  - slug: ca_on_toronto
    source_type: boundaries
    url: https://open.toronto.ca/dataset/city-wards/
    authority: City of Toronto Open Data Portal
    format: geojson
    notes: Ward boundaries. 25-ward model effective since 2018. Confirmed working in lookup.py.
    last_confirmed: 2026-05-15

  - slug: ca_on_toronto
    source_type: representatives
    url: https://open.toronto.ca/dataset/members-of-toronto-city-council-contact-information/
    authority: City of Toronto Open Data Portal
    format: csv
    notes: Current 25 city councillors with contact info. Confirmed working in lookup.py (WARD_NUMBER integer join key).
    last_confirmed: 2026-05-15

  - slug: ca_on_toronto
    source_type: executive
    url: https://www.toronto.ca/city-government/council/mayor/
    authority: City of Toronto
    format: html
    notes: Mayor page.
    last_confirmed: 2026-05-15  # TODO: verify

  - slug: ca_on_toronto
    source_type: metadata
    url: https://www.toronto.ca/city-government/elections/
    authority: City of Toronto
    format: html
    notes: Municipal election dates. Toronto operates on 4-year terms.
    last_confirmed: 2026-05-15  # TODO: verify
EOF

echo "Created ${REGISTRY_FILE}"
echo ""
echo "16 source entries seeded across ca_federal, ca_on, ca_on_toronto."
echo ""
echo "Next steps:"
echo "  1. Open the file and verify URLs marked '# TODO: verify'."
echo "  2. For shapefile sources, replace landing-page URLs with direct"
echo "     download URLs (check lookup.py for the paths you already use)."
echo "  3. Commit to git when you're satisfied."
