"""
Parliament API — Flask wrapper around the JurisdictionRegistry.

This file is intentionally thin. It does three things:
  1. Validates the postal code input
  2. Geocodes via Google Maps API
  3. Delegates to the registry for representative lookups

All jurisdiction-specific logic lives in the adapters, not here. To add a
new jurisdiction, write a config file in config/jurisdictions/ — no changes
to this file are needed.
"""

import logging
import os
import re

import requests as req
import db
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from flask_cors import CORS

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FlaskIntegration()],
        traces_sample_rate=0.0,
        send_default_pii=False,
        environment=os.getenv("SENTRY_ENVIRONMENT", "staging"),
    )
    logger.info("Sentry initialized for environment=%s", os.getenv("SENTRY_ENVIRONMENT", "staging"))
else:
    logger.info("SENTRY_DSN not set; Sentry disabled")

GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if not GOOGLE_API_KEY:
    logger.critical("GOOGLE_MAPS_API_KEY is not set")
    raise RuntimeError("GOOGLE_MAPS_API_KEY is required")

from photo_urls import resolve_photo_url
from registry import JurisdictionRegistry

app = Flask(__name__)

allowed_origins = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
]
CORS(app, origins=allowed_origins, methods=["GET"], allow_headers=["Content-Type"])
logger.info("CORS origins: %s", allowed_origins)

POSTAL_CODE_REGEX = re.compile(r'^[A-Z]\d[A-Z]\d[A-Z]\d$')

# Initialize the registry once at startup. Every Flask request uses this instance.
logger.info("Initializing jurisdiction registry...")
registry = JurisdictionRegistry()
logger.info("Registry ready: %s", registry)


# ── Helpers ──────────────────────────────────────────────────────────
def validate_postal_code(postal_code: str) -> bool:
    """Validate Canadian postal code format (A1A1A1, no spaces)."""
    return bool(POSTAL_CODE_REGEX.match(postal_code))


def geocode(postal_code: str):
    """Convert a postal code to (lat, lon) via Google Maps Geocoding API."""
    # Try cache first
    cache_row = db.query_one(
        "SELECT latitude, longitude FROM geocode_cache WHERE postal_code = %s;",
        (postal_code,),
    )
    if cache_row:
        logger.info("Geocode cache HIT for postal_code=%s", postal_code)
        return cache_row[0], cache_row[1]

    logger.info("Geocode cache MISS for postal_code=%s, calling Google", postal_code)

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": postal_code + ", Canada",
        "components": "country:CA",
        "key": GOOGLE_API_KEY,
    }
    try:
        response = req.get(url, params=params, timeout=10)
        data = response.json()
        if data["status"] == "OK":
            loc = data["results"][0]["geometry"]["location"]
            lat, lon = loc["lat"], loc["lng"]
            # Write to cache (idempotent; on conflict do nothing)
            try:
                db.execute(
                    "INSERT INTO geocode_cache (postal_code, latitude, longitude) VALUES (%s, %s, %s) ON CONFLICT (postal_code) DO NOTHING;",
                    (postal_code, lat, lon),
                )
            except Exception as e:
                logger.exception("Failed to write geocode cache for postal_code=%s", postal_code)
            return lat, lon
        return None, None
    except Exception:
        logger.exception("Geocoding failed for postal_code=%s", postal_code)
        return None, None


# ── Endpoints ────────────────────────────────────────────────────────
@app.route("/lookup", methods=["GET"])
def lookup():
    raw = request.args.get("postal_code", "").strip().upper().replace(" ", "")
    if not raw:
        return jsonify({"error": "postal_code parameter is required"}), 400
    if not validate_postal_code(raw):
        return jsonify({"error": "Invalid postal code format. Expected: A1A1A1"}), 400

    # Language selection. Accepts 'en' or 'fr'; defaults to 'en'.
    # Unknown languages are silently coerced to 'en' rather than rejected.
    lang = request.args.get("lang", "en").strip().lower()
    if lang not in ("en", "fr"):
        lang = "en"

    lat, lon = geocode(raw)
    if lat is None:
        return jsonify({"error": "Could not geocode postal code"}), 404

    results = registry.lookup_all(lat, lon, lang=lang)

    return jsonify({
        "postal_code": raw,
        "coordinates": {"lat": lat, "lon": lon},
        "language": lang,
        "results": results,
    })


# ── Browse endpoints ────────────────────────────────────────────────
# Non-spatial: list and detail views that bypass the registry/adapter path
# in favour of direct SQL.

JURISDICTIONS_INDEX_SQL = """
    SELECT
        slug,
        COALESCE(name->>%s, name->>'en') AS name,
        level,
        country_code,
        province_code
    FROM jurisdictions
    ORDER BY level, COALESCE(name->>%s, name->>'en');
"""

JURISDICTION_DETAIL_SQL = """
    SELECT
        id,
        COALESCE(name->>%s, name->>'en') AS name,
        level,
        country_code,
        province_code,
        governance
    FROM jurisdictions
    WHERE slug = %s;
"""

JURISDICTION_REPS_SQL = """
    SELECT
        r.id::text                                         AS id,
        r.slug                                             AS slug,
        COALESCE(r.name->>%s, r.name->>'en')              AS name,
        COALESCE(r.party->>%s, r.party->>'en')            AS party,
        r.photo_url                                        AS photo_url,
        COALESCE(rep.role->>%s, rep.role->>'en')           AS role,
        COALESCE(d.name->>%s, d.name->>'en')               AS district_name,
        d.external_id                                      AS district_external_id
    FROM representations rep
    JOIN representatives r ON r.id = rep.representative_id
    LEFT JOIN districts d ON d.id = rep.district_id
    WHERE rep.jurisdiction_id = %s
      AND rep.end_date IS NULL
      AND rep.scope = %s
    ORDER BY COALESCE(r.name->>'en', '');
"""

REPRESENTATIVE_DETAIL_SQL = """
    SELECT
        r.id::text                                         AS id,
        r.slug                                             AS slug,
        COALESCE(r.name->>%s, r.name->>'en')              AS name,
        COALESCE(r.party->>%s, r.party->>'en')            AS party,
        r.email                                            AS email,
        r.phone                                            AS phone,
        r.photo_url                                        AS photo_url,
        COALESCE(r.website_url->>%s, r.website_url->>'en') AS website_url,
        r.external_ids                                     AS external_ids
    FROM representatives r
    JOIN representations rep ON rep.representative_id = r.id
    JOIN jurisdictions j ON j.id = rep.jurisdiction_id
    WHERE j.slug = %s
      AND r.slug = %s
    LIMIT 1;
"""

REPRESENTATIVE_REPRESENTATIONS_SQL = """
    SELECT
        COALESCE(rep.role->>%s, rep.role->>'en')           AS role,
        rep.scope                                          AS scope,
        rep.start_date                                     AS start_date,
        rep.end_date                                       AS end_date,
        COALESCE(d.name->>%s, d.name->>'en')               AS district_name,
        d.external_id                                      AS district_external_id,
        j.slug                                             AS jurisdiction_slug,
        COALESCE(j.name->>%s, j.name->>'en')              AS jurisdiction_name,
        j.level                                            AS jurisdiction_level
    FROM representatives r
    JOIN representations rep ON rep.representative_id = r.id
    JOIN jurisdictions j ON j.id = rep.jurisdiction_id
    LEFT JOIN districts d ON d.id = rep.district_id
    WHERE r.slug = %s AND j.slug = %s
    ORDER BY rep.scope, rep.start_date DESC NULLS LAST;
"""


def _resolve_lang() -> str:
    """Read ?lang=en|fr from query string; default 'en'."""
    lang = request.args.get("lang", "en").strip().lower()
    return lang if lang in ("en", "fr") else "en"


@app.route("/jurisdictions", methods=["GET"])
def jurisdictions_index():
    """List all registered jurisdictions."""
    lang = _resolve_lang()
    rows = db.query(JURISDICTIONS_INDEX_SQL, (lang, lang))
    jurisdictions = [
        {
            "slug": row[0],
            "name": row[1],
            "level": row[2],
            "country_code": row[3],
            "province_code": row[4],
        }
        for row in rows
    ]
    return jsonify({"language": lang, "jurisdictions": jurisdictions})


@app.route("/jurisdiction/<slug>", methods=["GET"])
def jurisdiction_detail(slug: str):
    """Full roster for one jurisdiction: governance + reps + leadership."""
    lang = _resolve_lang()

    j_rows = db.query(JURISDICTION_DETAIL_SQL, (lang, slug))
    if not j_rows:
        return jsonify({"error": f"Jurisdiction not found: {slug}"}), 404

    j_id, j_name, j_level, j_country, j_province, j_governance = j_rows[0]

    district_reps = db.query(
        JURISDICTION_REPS_SQL, (lang, lang, lang, lang, j_id, "district")
    )
    role_reps = db.query(
        JURISDICTION_REPS_SQL, (lang, lang, lang, lang, j_id, "role")
    )

    def shape_rep(row):
        return {
            "id": row[0],
            "slug": row[1],
            "name": row[2],
            "party": row[3],
            "photo_url": resolve_photo_url(row[4]),
            "role": row[5],
            "district_name": row[6],
            "district_external_id": row[7],
        }

    return jsonify({
        "language": lang,
        "jurisdiction": {
            "slug": slug,
            "name": j_name,
            "level": j_level,
            "country_code": j_country,
            "province_code": j_province,
            "governance": j_governance,
        },
        "representatives": [shape_rep(r) for r in district_reps],
        "leadership": [shape_rep(r) for r in role_reps],
    })


@app.route("/representative/<jurisdiction_slug>/<rep_slug>", methods=["GET"])
def representative_detail(jurisdiction_slug: str, rep_slug: str):
    """Full details for one representative within a jurisdiction context."""
    lang = _resolve_lang()

    detail_rows = db.query(
        REPRESENTATIVE_DETAIL_SQL, (lang, lang, lang, jurisdiction_slug, rep_slug)
    )
    if not detail_rows:
        return jsonify({
            "error": f"Representative not found: {jurisdiction_slug}/{rep_slug}"
        }), 404

    row = detail_rows[0]
    representative = {
        "id": row[0],
        "slug": row[1],
        "name": row[2],
        "party": row[3],
        "email": row[4],
        "phone": row[5],
        "photo_url": resolve_photo_url(row[6]),
        "website_url": row[7],
        "external_ids": row[8],
    }

    rep_rows = db.query(
        REPRESENTATIVE_REPRESENTATIONS_SQL,
        (lang, lang, lang, rep_slug, jurisdiction_slug),
    )
    representations = [
        {
            "role": r[0],
            "scope": r[1],
            "start_date": r[2].isoformat() if r[2] else None,
            "end_date": r[3].isoformat() if r[3] else None,
            "district_name": r[4],
            "district_external_id": r[5],
            "jurisdiction_slug": r[6],
            "jurisdiction_name": r[7],
            "jurisdiction_level": r[8],
        }
        for r in rep_rows
    ]

    return jsonify({
        "language": lang,
        "representative": representative,
        "representations": representations,
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "message": "Parliament API is running",
        "jurisdictions_loaded": len(registry.adapters),
    })


# ── Run ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        port=int(os.getenv("PORT", "5000")),
        host="0.0.0.0",
    )
