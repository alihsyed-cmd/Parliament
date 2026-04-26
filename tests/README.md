# Parliament Test Suite

## Fixture-Based Regression Testing

The Parliament test suite uses **fixtures** — known-correct postal code lookups verified against official government sources — as its primary regression check. Every change to the codebase or data must keep all fixtures passing.

## Running Tests

From the project root:

```bash
pytest tests/ -v
```

The first run takes ~2 seconds (loads all jurisdictions); subsequent assertions are near-instant.

## Fixture File Format

Fixtures live in `tests/fixtures/` as CSV files, one per jurisdiction. Schema:

| Column | Description | Example |
|---|---|---|
| `postal_code` | Canadian postal code (no spaces) | `M3J3R2` |
| `lat` | Pre-computed latitude (avoids hitting Google API per test) | `43.766062` |
| `lon` | Pre-computed longitude | `-79.4992999` |
| `level` | `federal`, `provincial`, or `municipal` | `federal` |
| `expected_name_contains` | Substring of representative's name | `Sgro` |
| `expected_role` | Role label (`MP`, `MPP`, `Councillor`) | `MP` |
| `expected_district` | Substring of district/riding/ward name | `Humber River` |
| `source_url` | Official source for verification | `https://www.ourcommons.ca/...` |
| `verified_date` | When ground truth was last confirmed | `2026-04-26` |
| `notes` | Free-text context | `Toronto urban` |

## Why Substring Matching

Fixtures use substring matching (e.g., `"Sgro" in rep_name`) rather than exact equality. This intentionally tolerates formatting drift in source data: `"Hon. Judy A. Sgro"` and `"Judy Sgro"` both match the fixture `"Sgro"`. The fixture's job is to assert "the right person is being returned," not "the exact string formatting is preserved."

## Adding a New Fixture

1. Verify the postal code exists via [Canada Post lookup](https://www.canadapost-postescanada.ca/info/mc/personal/postalcode/fpc.jsf)
2. Run the API and capture the candidate rep + lat/lon
3. Cross-verify the rep against the official source (`ourcommons.ca`, `ola.org`, `toronto.ca`, etc.)
4. Add a row to the appropriate fixture CSV
5. Run `pytest tests/ -v` and confirm the new fixture passes

## Adding a New Jurisdiction's Fixture File

Drop a new CSV in `tests/fixtures/` following the naming convention `<country>_<region>_<city>.csv`. Pytest discovers all `*.csv` files automatically — no test code changes required.

## Failure Isolation

If one jurisdiction's adapter is broken, only that jurisdiction's fixtures fail. Other jurisdictions' tests continue passing. This is enforced by the registry's per-adapter exception handling in `lookup_all()` and the load-time validation in `WardBasedAdapter.validate()`.

To verify isolation works, deliberately break a config field (e.g., set `district_name_field` to a nonexistent column) and confirm only that jurisdiction's tests fail.

## Baseline vs Fixtures

Two parallel safety nets exist:

- **`tests/baseline/`** — full JSON snapshots of API responses, captured during architectural changes. Used to detect *any* shape change in the API output.
- **`tests/fixtures/`** — targeted assertions that specific reps are returned for specific postal codes. Used to detect *data correctness* regressions.

Both are committed to the repo. Both should pass on every commit.
