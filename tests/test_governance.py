"""
Governance metadata tests.

Verifies that each registered jurisdiction has correct, complete governance
metadata in the API response. These tests catch regressions where governance
fields get dropped, mistyped, or set to wrong values.

These are separate from fixture tests because they assert different things:
- test_fixtures.py asserts "the correct rep is returned"
- test_governance.py asserts "the governance metadata is correctly shaped"
"""

import pytest


# A point that's known to lie inside Toronto (Ward 7)
TORONTO_POINT = (43.766062, -79.4992999)

# A point that's known to lie inside Ontario but outside Toronto (Sudbury)
ONTARIO_NON_TORONTO_POINT = (46.46771100000001, -80.99695559999999)

# A point that's federal-only (Halifax, Nova Scotia)
FEDERAL_ONLY_POINT = (44.6370436, -63.5956263)


def test_federal_governance_present(registry):
    """Federal jurisdiction must declare partisan governance with MP role."""
    results = registry.lookup_all(*TORONTO_POINT)
    gov = results["federal"]["governance"]

    assert gov is not None, "federal governance metadata missing"
    assert gov["type"] == "ward_based"
    assert gov["partisan"] is True
    assert gov["rep_role_labels"]["en"]["singular"] == "MP"
    assert gov["district_term"]["en"] == "Riding"


def test_ontario_governance_present(registry):
    """Ontario provincial jurisdiction must declare partisan governance with MPP role."""
    results = registry.lookup_all(*TORONTO_POINT)
    gov = results["provincial"]["governance"]

    assert gov is not None, "provincial governance metadata missing"
    assert gov["type"] == "ward_based"
    assert gov["partisan"] is True
    assert gov["rep_role_labels"]["en"]["singular"] == "MPP"


def test_toronto_governance_is_non_partisan(registry):
    """Toronto municipal politics are non-partisan; the metadata must reflect this."""
    results = registry.lookup_all(*TORONTO_POINT)
    gov = results["municipal"]["governance"]

    assert gov is not None, "municipal governance metadata missing for Toronto"
    assert gov["type"] == "ward_based"
    assert gov["partisan"] is False, (
        "Toronto must be partisan=false — Ontario municipal politics are non-partisan"
    )
    assert gov["rep_role_labels"]["en"]["singular"] == "Councillor"
    assert gov["district_term"]["en"] == "Ward"
    assert gov.get("has_mayor") is True


def test_governance_is_none_when_no_coverage(registry):
    """If no jurisdiction at a level covers the point, governance must be None."""
    # Halifax: federal coverage exists, but no provincial or municipal in our data
    results = registry.lookup_all(*FEDERAL_ONLY_POINT)

    assert results["federal"]["governance"] is not None, "Halifax should have federal governance"
    assert results["provincial"]["governance"] is None, "Halifax has no NS provincial coverage"
    assert results["municipal"]["governance"] is None, "Halifax has no municipal coverage"


def test_sudbury_has_no_municipal_governance(registry):
    """A point in Ontario but outside Toronto should have no municipal governance."""
    results = registry.lookup_all(*ONTARIO_NON_TORONTO_POINT)

    assert results["federal"]["governance"] is not None
    assert results["provincial"]["governance"] is not None
    assert results["municipal"]["governance"] is None, (
        "Sudbury is in Ontario but outside Toronto — should have no municipal governance"
    )


def test_governance_is_bilingual_ready(registry):
    """All translatable governance fields must have both en and fr keys."""
    results = registry.lookup_all(*TORONTO_POINT)

    for level in ("federal", "provincial", "municipal"):
        gov = results[level]["governance"]
        assert "en" in gov["rep_role_labels"], f"{level} missing English role labels"
        assert "fr" in gov["rep_role_labels"], f"{level} missing French role labels"
        assert "en" in gov["district_term"], f"{level} missing English district term"
        assert "fr" in gov["district_term"], f"{level} missing French district term"
