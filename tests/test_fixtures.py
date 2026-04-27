"""
Fixture-based tests for the Parliament lookup system.

Each row in tests/fixtures/*.csv is a separate test case. A row asserts
that for a given (postal_code, level), the lookup returns a representative
whose name and district contain the expected substrings.

Substring matching is intentional — fixtures should not break due to
formatting drift in source data (e.g., "Hon. Judy A. Sgro" vs "Judy Sgro").

To add fixtures: drop a CSV file into tests/fixtures/ following the schema:
    postal_code,lat,lon,level,expected_name_contains,expected_role,
    expected_district,source_url,verified_date,notes

To run: pytest tests/test_fixtures.py
"""

import csv
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_all_fixtures():
    """Read every CSV in tests/fixtures/ and yield (file, row) tuples."""
    cases = []
    if not FIXTURES_DIR.exists():
        return cases

    for csv_path in sorted(FIXTURES_DIR.glob("*.csv")):
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):  # start=2 because row 1 is header
                # Build a test ID like "ca_federal.csv:row3:M3J3R2:federal"
                test_id = f"{csv_path.name}:row{row_num}:{row['postal_code']}:{row['level']}"
                cases.append(pytest.param(row, id=test_id))
    return cases


FIXTURE_CASES = _load_all_fixtures()


@pytest.mark.skipif(
    not FIXTURE_CASES,
    reason="No fixture files found in tests/fixtures/"
)
@pytest.mark.parametrize("fixture", FIXTURE_CASES)
def test_fixture(fixture, registry):
    """
    Assert that looking up a fixture's coordinates returns the expected rep.
    """
    lat = float(fixture["lat"])
    lon = float(fixture["lon"])
    level = fixture["level"].strip().lower()
    expected_name = fixture["expected_name_contains"].strip()
    expected_role = fixture["expected_role"].strip()
    expected_district = fixture["expected_district"].strip()

    # Run the lookup
    results = registry.lookup_all(lat, lon)
    level_data = results.get(level, {})
    reps_at_level = level_data.get("representatives", []) if isinstance(level_data, dict) else level_data

    # Build a helpful failure message
    actual_summary = "\n".join(
        f"  - {r.get('name', '?')} ({r.get('role', '?')}) "
        f"in {r.get(_district_key(r), '?')}"
        for r in reps_at_level
    ) or "  (no representatives returned)"

    failure_context = (
        f"\nFixture: {fixture['postal_code']} @ {level}\n"
        f"Expected: name contains '{expected_name}', "
        f"role='{expected_role}', district contains '{expected_district}'\n"
        f"Got {len(reps_at_level)} reps at this level:\n{actual_summary}\n"
        f"Source: {fixture.get('source_url', 'n/a')}"
    )

    assert reps_at_level, f"No reps returned at level '{level}'.{failure_context}"

    # Check that at least one rep matches all three criteria
    match = any(
        expected_name.lower() in (r.get("name") or "").lower()
        and expected_role.lower() in (r.get("role") or "").lower()
        and expected_district.lower() in str(_district_value(r)).lower()
        for r in reps_at_level
    )

    assert match, f"No matching rep found.{failure_context}"


def _district_key(rep: dict) -> str:
    """Find the district field name in a rep dict (riding, ward, district, etc.)."""
    for key in ("riding", "ward", "district", "borough"):
        if key in rep:
            return key
    return "(unknown)"


def _district_value(rep: dict) -> str:
    """Get the district value from a rep dict, regardless of which key it's under."""
    return rep.get(_district_key(rep), "")
