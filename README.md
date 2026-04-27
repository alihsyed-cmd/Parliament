# Parliament

A civic technology application for Canadian voters. Users enter their postal code and see their elected representatives at every level of government — federal, provincial, and municipal.

## Architecture

Parliament uses an **adapter-based architecture** so new jurisdictions can be registered without changing core code.

scripts/
├── api.py                    # Flask API — thin wrapper over the registry
├── registry.py               # Loads all jurisdiction configs at startup
└── adapters/
├── base.py               # Abstract JurisdictionAdapter class
└── ward_based.py         # Adapter for ward/riding-based jurisdictions
config/
└── jurisdictions/            # One JSON config per registered jurisdiction
├── ca_federal.json
├── ca_on.json
└── ca_on_toronto.json
data/                         # Boundary files (.shp, .geojson) and rep data (.csv, .xml)
tests/
└── baseline/                 # Captured API responses for parity testing
## Adding a New Jurisdiction

For ward-based jurisdictions (most cities, all provinces):
1. Drop boundary file (`.shp` or `.geojson`) and representative data (`.csv` or `.xml`) into `data/`
2. Add file paths to `.env`
3. Write a config JSON in `config/jurisdictions/` (see existing configs for examples)
4. Restart the API — the new jurisdiction loads automatically

For novel governance types (at-large, nested borough, consensus): write a new adapter class in `scripts/adapters/`, register it in `registry.py`'s `ADAPTER_TYPES` map, then proceed as above.

## Running

```bash
python3 scripts/api.py
```

Then query:

```bash
curl "http://127.0.0.1:5000/lookup?postal_code=M3J3R2"
curl "http://127.0.0.1:5000/health"
```

## Database

Parliament uses **Supabase (PostgreSQL with PostGIS)** for representative and boundary data. The four-table schema (`jurisdictions`, `districts`, `representatives`, `representations`) supports many-to-many representation, time-bounded historical tracking via start/end dates, and i18n-ready jsonb language maps for translatable fields.

To set up the database:

1. Create a Supabase project and enable the PostGIS extension via Database → Extensions in the dashboard.
2. Add `SUPABASE_DB_URL` to `.env` with the session pooler connection string.
3. Apply the schema:
```bash
   python3 -c "import psycopg2, os; from dotenv import load_dotenv; load_dotenv('.env'); psycopg2.connect(os.getenv('SUPABASE_DB_URL')).cursor().execute(open('migrations/001_initial_schema.sql').read())"
```
4. Migrate source data into Supabase:
```bash
   python3 scripts/migrate_to_supabase.py
```

Adapters then query Supabase directly using parameterized PostGIS spatial queries.

Each jurisdiction also declares **governance metadata** (in `jurisdictions.governance`) describing how it's governed: partisan vs non-partisan, role labels, district terminology, election cycle, and special flags like `has_mayor`. The API surfaces this metadata per level so the frontend renders different jurisdictions correctly without conditionals.

The API also returns **leadership data** alongside district-based representatives — the Prime Minister and federal cabinet at the federal level, the Premier and provincial cabinet at the provincial level, and the Mayor at the municipal level. Leadership is jurisdiction-wide rather than point-dependent: every Canadian sees the same federal cabinet regardless of postal code.

## Testing

The project uses fixture-based regression tests. Run them with:

```bash
pytest tests/ -v
```

See `tests/README.md` for details on the fixture format and how to add new test cases.

## Environment

Requires a `.env` file with:
- `GOOGLE_MAPS_API_KEY` — for postal code geocoding
- `JURISDICTIONS_CONFIG_DIR` — path to `config/jurisdictions/`
- File paths for each registered jurisdiction's boundary and representative data
