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
