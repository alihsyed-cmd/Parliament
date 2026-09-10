"""
Postal-code geocoding and jurisdiction resolution.

Extracted from api.py so that non-Flask callers — principally the reminder
cron in scripts/send_election_reminders.py — can turn a postal code into the
set of jurisdictions that govern it without importing the web app, Sentry,
and CORS along the way.

api.py imports validate_postal_code() and geocode() from here, so the /lookup
endpoint and the reminder cron resolve a postal code through exactly the same
code path. That identity matters: a subscriber must be reminded about the same
elections the app showed them when they signed up.
"""

import logging
import os
import re

import requests as req

import db

logger = logging.getLogger(__name__)

POSTAL_CODE_REGEX = re.compile(r"^[A-Z]\d[A-Z]\d[A-Z]\d$")

GOOGLE_ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json"

MATCHED_DISTRICTS_SQL = """
    SELECT jurisdiction_slug, external_id, name
    FROM districts
    WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint(%s, %s), 4326));
"""


def normalize_postal_code(raw: str) -> str:
    """Uppercase and strip whitespace. 'k1a 0b1' -> 'K1A0B1'."""
    return (raw or "").strip().upper().replace(" ", "")


def validate_postal_code(postal_code: str) -> bool:
    """Validate Canadian postal code format (A1A1A1, no spaces)."""
    return bool(POSTAL_CODE_REGEX.match(postal_code))


def geocode(postal_code: str, allow_remote: bool = True):
    """
    Convert a postal code to (lat, lon) via Google Maps, cache-first.

    allow_remote=False restricts the lookup to the geocode_cache table. The
    reminder cron passes False on purpose: it may iterate thousands of
    subscriptions unattended, and an uncached postal code should be logged and
    skipped rather than silently billed to the Maps account. In practice every
    subscriber's postal code is already cached, because looking it up in the
    app is how they reached the reminder form.
    """
    cache_row = db.query_one(
        "SELECT latitude, longitude FROM geocode_cache WHERE postal_code = %s;",
        (postal_code,),
    )
    if cache_row:
        logger.info("Geocode cache HIT for postal_code=%s", postal_code)
        return cache_row[0], cache_row[1]

    if not allow_remote:
        logger.warning("Geocode cache MISS for postal_code=%s and remote lookup disabled", postal_code)
        return None, None

    google_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not google_api_key:
        logger.error("GOOGLE_MAPS_API_KEY is not set; cannot geocode postal_code=%s", postal_code)
        return None, None

    logger.info("Geocode cache MISS for postal_code=%s, calling Google", postal_code)
    params = {
        "address": postal_code + ", Canada",
        "components": "country:CA",
        "key": google_api_key,
    }
    try:
        response = req.get(GOOGLE_ENDPOINT, params=params, timeout=10)
        data = response.json()
        if data["status"] == "OK":
            loc = data["results"][0]["geometry"]["location"]
            lat, lon = loc["lat"], loc["lng"]
            try:
                db.execute(
                    "INSERT INTO geocode_cache (postal_code, latitude, longitude) "
                    "VALUES (%s, %s, %s) ON CONFLICT (postal_code) DO NOTHING;",
                    (postal_code, lat, lon),
                )
            except Exception:
                logger.exception("Failed to write geocode cache for postal_code=%s", postal_code)
            return lat, lon
        return None, None
    except Exception:
        logger.exception("Geocoding failed for postal_code=%s", postal_code)
        return None, None


def resolve_districts(postal_code: str, allow_remote: bool = True) -> dict[str, set]:
    """
    {jurisdiction_slug: {district external_id, ...}} for every registered
    jurisdiction whose boundaries contain this postal code.

    The district detail exists for by-elections, which fill one seat: their
    reminder cohort is the subscribers inside that one district, not everyone in
    the province. A set per jurisdiction rather than a single value because a
    point can land in two overlapping districts of one jurisdiction, exactly as
    /lookup already allows for.
    """
    lat, lon = geocode(postal_code, allow_remote=allow_remote)
    if lat is None:
        return {}

    matched: dict[str, set] = {}
    for slug, ext_id, _name in db.query(MATCHED_DISTRICTS_SQL, (lon, lat)):
        matched.setdefault(slug, set()).add(ext_id)
    return matched


def resolve_jurisdiction_slugs(postal_code: str, allow_remote: bool = True) -> list[str]:
    """
    The slugs of every registered jurisdiction whose boundaries contain this
    postal code — typically three (municipal, provincial, federal), fewer where
    a level is not yet registered.

    Resolved live rather than snapshotted at subscribe time, and that is the
    whole reason a subscription stores a postal code instead of a slug list:
    someone in a city we have not registered yet subscribes today and starts
    receiving that city's reminders the moment its boundaries load, with no
    backfill step.

    Returns [] when the postal code cannot be geocoded or lands outside every
    registered boundary. Both are ordinary conditions, not errors.
    """
    return list(resolve_districts(postal_code, allow_remote=allow_remote).keys())
