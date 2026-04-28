"""
Language selection tests.

Verifies that the ?lang= parameter correctly returns French translations
for standard role labels, and that English remains the default and fallback.
"""

import pytest

TORONTO_POINT = (43.766062, -79.4992999)


def test_default_lang_is_english(registry):
    results = registry.lookup_all(*TORONTO_POINT)
    assert results["federal"]["representatives"][0]["role"] == "MP"
    assert results["municipal"]["representatives"][0]["role"] == "Councillor"


def test_french_translates_district_role_labels(registry):
    results = registry.lookup_all(*TORONTO_POINT, lang="fr")
    assert results["federal"]["representatives"][0]["role"] == "député"
    assert results["provincial"]["representatives"][0]["role"] == "député provincial"
    assert results["municipal"]["representatives"][0]["role"] == "Conseiller"


def test_french_translates_leadership_role_labels(registry):
    results = registry.lookup_all(*TORONTO_POINT, lang="fr")

    pm = next((l for l in results["federal"]["leadership"] if "Carney" in l["name"]), None)
    assert pm is not None and pm["role"] == "Premier ministre"

    premier = next((l for l in results["provincial"]["leadership"] if l["role"] == "Premier ministre"), None)
    assert premier is not None and "Ford" in premier["name"]

    mayor = results["municipal"]["leadership"][0]
    assert mayor["role"] == "Maire" and "Chow" in mayor["name"]


def test_english_falls_back_when_french_missing(registry):
    """Cabinet titles like 'Minister of Foreign Affairs' aren't translated; should fall back to English."""
    results = registry.lookup_all(*TORONTO_POINT, lang="fr")
    foreign_affairs = next(
        (l for l in results["federal"]["leadership"] if "Anand" in l["name"]),
        None,
    )
    assert foreign_affairs is not None
    assert foreign_affairs["role"] == "Minister of Foreign Affairs"
