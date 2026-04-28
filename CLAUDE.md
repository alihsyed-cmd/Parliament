# Parliament Project Summary for Claude Code

## What is Parliament?
A civic technology application for Canadian voters. Users enter their postal code and see their elected representatives at every level of government — federal, provincial, and municipal.

## Architecture
- **Adapter-based architecture**: New jurisdictions can be registered without changing core code. Adapters handle different governance types (ward-based, at-large, etc.).
- **Four-table Supabase schema**: `jurisdictions`, `districts`, `representatives`, `representations` — supports many-to-many representation, historical tracking via start/end dates, and i18n-ready jsonb language maps.
- **Flask thin-wrapper philosophy**: The API is a minimal wrapper over the registry, with adapters querying Supabase directly using parameterized PostGIS spatial queries.

## Current State
- Phase 2 complete
- 38 tests passing
- Tagged through v0.2.5

## Tech Stack
- Python 3
- Flask
- PostGIS (spatial database extension)
- Supabase (PostgreSQL with PostGIS)
- Google Maps Geocoding API

## Key Concepts
- **Adapter contract**: Every adapter inherits from `JurisdictionAdapter` in `scripts/adapters/base.py` and implements a `lookup` method that returns a rep dict or `None`; new governance types require new adapter classes registered in `registry.py`'s `ADAPTER_TYPES` map.
- **Leadership data**: Alongside district-based reps, the API returns role-based leadership (PM + federal cabinet for every Canadian, Premier + Ontario cabinet for Ontario users, Mayor for Toronto users), jurisdiction-wide rather than point-dependent; the `representations` table supports multi-role ministers.
- **Internationalization**: The API accepts `?lang=en|fr` and returns translated content via jsonb language maps; SQL uses `COALESCE` to fall back to English; standard role labels are translated, cabinet titles English-only pending Phase 4 bilingual sources.
- **Governance metadata**: Each jurisdiction declares metadata (partisan vs non-partisan, role labels, district terminology, election cycle, `has_mayor`) so the frontend renders any jurisdiction without conditionals.

## Environment Variables
- `SUPABASE_DB_URL` (Supabase session pooler connection string)
- `GOOGLE_MAPS_API_KEY` (for postal code geocoding)
- `JURISDICTIONS_CONFIG_DIR` (absolute path to `config/jurisdictions/`)
- File paths for each registered jurisdiction's boundary and representative data (e.g., `CA_FEDERAL_BOUNDARY_FILE`, `CA_FEDERAL_REP_DATA_FILE`, etc.)

## Coding Conventions
- Python 3 standard library where possible
- Flask routes stay thin with logic in adapters/registry
- Errors return structured JSON with appropriate HTTP status
- All PostGIS spatial queries use parameterized statements (never string interpolation)
- Tests must pass before any commit

## What Not To Modify Without Care
- `tests/baseline/` files (these are regression fixtures)
- `migrations/001_initial_schema.sql` (never edit in place — create new numbered migration files for schema changes)
- Any hardcoded `/Users/alisyed/...` path must become an environment variable before production deploy

## Directory Layout
- `config/jurisdictions/`: JSON configs for each registered jurisdiction (e.g., ca_federal.json, ca_on.json, ca_on_toronto.json)
- `scripts/adapters/`: Adapter classes (`base.py` for abstract base, `ward_based.py` for ward/riding-based jurisdictions)
- `data/`: Boundary files (.shp, .geojson) and representative data (.csv, .xml) organized by level (federal/, provincial/, municipal/)
- `tests/`: Test files (`conftest.py`, `test_*.py`), fixtures, and baseline captured responses
- `migrations/`: SQL schema files for database setup

## Running the API Locally
1. Ensure `.env` file with required variables (SUPABASE_DB_URL, GOOGLE_MAPS_API_KEY, etc.)
2. `python3 scripts/api.py`
3. Query: `curl "http://127.0.0.1:5000/lookup?postal_code=M3J3R2"`

## Running Tests
`pytest tests/ -v`

## Active Branch Context
- Currently in Phase 3 — Frontend development. Backend feature-complete for Canada/Ontario/Toronto. Frontend will validate UX before backend expansion resumes (Phase 4).