"""
Leadership data tests.

Verifies that role-based representations (PM, Premier, Mayor, cabinet members)
are correctly returned in the API response. These tests complement:
- test_fixtures.py — asserts district-based reps for postal codes
- test_governance.py — asserts metadata structure
- test_leadership.py (this file) — asserts role-based reps for jurisdictions

Leadership data is jurisdiction-wide, not point-dependent: every Canadian sees
the same federal cabinet; every Ontarian sees the same Ontario cabinet;
every Toronto resident sees the same mayor.
"""

import pytest


# Test points known to lie inside each level of jurisdiction
TORONTO_POINT = (43.766062, -79.4992999)
ONTARIO_NON_TORONTO_POINT = (46.46771100000001, -80.99695559999999)  # Sudbury
FEDERAL_ONLY_POINT = (44.6370436, -63.5956263)  # Halifax


def test_federal_has_prime_minister(registry):
    """Federal leadership must include a Prime Minister."""
    results = registry.lookup_all(*TORONTO_POINT)
    leadership = results["federal"]["leadership"]

    assert leadership, "Federal leadership is empty"

    pm_reps = [l for l in leadership if l.get("role") == "Prime Minister"]
    assert len(pm_reps) == 1, (
        f"Expected exactly 1 Prime Minister, found {len(pm_reps)}: "
        f"{[l['name'] for l in pm_reps]}"
    )


def test_federal_cabinet_has_reasonable_size(registry):
    """Federal cabinet should be roughly 30-50 members. Catches accidental load failures."""
    results = registry.lookup_all(*TORONTO_POINT)
    leadership = results["federal"]["leadership"]

    assert 20 <= len(leadership) <= 60, (
        f"Federal leadership count ({len(leadership)}) outside expected range. "
        f"Possible loader failure or excessive duplication."
    )


def test_ontario_has_premier(registry):
    """Ontario leadership must include the Premier."""
    results = registry.lookup_all(*TORONTO_POINT)
    leadership = results["provincial"]["leadership"]

    assert leadership, "Ontario leadership is empty"

    premier_reps = [l for l in leadership if l.get("role") == "Premier"]
    assert len(premier_reps) == 1, (
        f"Expected exactly 1 Premier, found {len(premier_reps)}: "
        f"{[l['name'] for l in premier_reps]}"
    )


def test_ontario_cabinet_has_reasonable_size(registry):
    """Ontario cabinet should be roughly 30-50 roles."""
    results = registry.lookup_all(*TORONTO_POINT)
    leadership = results["provincial"]["leadership"]

    assert 20 <= len(leadership) <= 60, (
        f"Ontario leadership count ({len(leadership)}) outside expected range."
    )


def test_toronto_has_mayor(registry):
    """Toronto leadership must include exactly one Mayor."""
    results = registry.lookup_all(*TORONTO_POINT)
    leadership = results["municipal"]["leadership"]

    assert leadership, "Toronto leadership is empty"

    mayor_reps = [l for l in leadership if l.get("role") == "Mayor"]
    assert len(mayor_reps) == 1, (
        f"Expected exactly 1 Mayor, found {len(mayor_reps)}"
    )


def test_leadership_visible_outside_toronto(registry):
    """Federal cabinet and Ontario cabinet must be visible to Sudbury users.

    Leadership is jurisdiction-wide. A user outside Toronto should still see
    the federal cabinet and Ontario premier/cabinet — only the municipal
    leadership (Toronto Mayor) should be missing.
    """
    results = registry.lookup_all(*ONTARIO_NON_TORONTO_POINT)

    assert results["federal"]["leadership"], (
        "Federal leadership missing for Sudbury — leadership should be jurisdiction-wide"
    )
    assert results["provincial"]["leadership"], (
        "Ontario leadership missing for Sudbury"
    )
    # Sudbury isn't in Toronto, so no municipal leadership
    assert results["municipal"]["leadership"] == [], (
        "Sudbury should not have municipal leadership (no city coverage)"
    )


def test_only_federal_leadership_outside_ontario(registry):
    """Halifax users should see federal cabinet but no provincial or municipal leadership."""
    results = registry.lookup_all(*FEDERAL_ONLY_POINT)

    assert results["federal"]["leadership"], "Federal leadership missing for Halifax"
    assert results["provincial"]["leadership"] == [], (
        "Halifax should not have Ontario leadership"
    )
    assert results["municipal"]["leadership"] == [], (
        "Halifax should not have municipal leadership"
    )


def test_multi_role_ministers_appear_multiple_times(registry):
    """Ontario ministers holding multiple roles should appear once per role."""
    results = registry.lookup_all(*TORONTO_POINT)
    leadership = results["provincial"]["leadership"]

    # Doug Ford is Premier and Minister of Intergovernmental Affairs
    ford_entries = [l for l in leadership if "Doug Ford" in l.get("name", "")]
    assert len(ford_entries) >= 2, (
        f"Expected Doug Ford to appear at least twice (Premier + Minister), "
        f"got {len(ford_entries)}: {[l.get('role') for l in ford_entries]}"
    )

    roles = {l["role"] for l in ford_entries}
    assert "Premier" in roles, f"Premier role missing for Doug Ford: {roles}"


def test_federal_cabinet_includes_specific_ministers(registry):
    """Spot-check that specific known cabinet members are present."""
    results = registry.lookup_all(*TORONTO_POINT)
    leadership = results["federal"]["leadership"]

    role_lookup = {l["role"]: l["name"] for l in leadership}

    # Anita Anand — Minister of Foreign Affairs (a stable, recognizable role)
    assert "Minister of Foreign Affairs" in role_lookup, (
        f"Foreign Affairs minister missing. Roles present: {sorted(role_lookup.keys())}"
    )
    assert "Anand" in role_lookup["Minister of Foreign Affairs"]
