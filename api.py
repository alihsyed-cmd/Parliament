"""
Parliament API — v2 (three-table Supabase schema).

Queries jurisdictions / districts / politicians directly. All jurisdiction
logic is data-driven (governance metadata lives in the jurisdictions row), so
adding a jurisdiction needs no changes here — only new rows in the three tables.

Endpoints
  GET /lookup?postal_code=A1A1A1
      Validate -> geocode (Google, cached) -> PostGIS point-in-polygon to find
      the district at each level -> return reps for the matched district plus
      jurisdiction-wide leadership plus governance context, one entry per level.
  GET /jurisdictions                              list all registered jurisdictions
  GET /jurisdiction/<slug>                        full roster for one jurisdiction
  GET /representative/<jurisdiction_slug>/<slug>  one politician's detail
  GET /health

Preserved from v1: Flask app + CORS, Sentry init, postal-code regex/validation,
and the geocode-with-cache function (geocode_cache table assumed to exist).

Removed in v2: registry/adapters/photo_urls/translations; all jsonb name->>'en'
access (schema is plain text now); the representations/representatives tables;
and the ?lang= input param (English-only). Responses still carry a constant
lang:"en" so the envelope is stable when i18n returns.

Response shape follows the frontend contract in types.ts.
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
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
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

app = Flask(__name__)

allowed_origins = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
]
CORS(app, origins=allowed_origins, methods=["GET"], allow_headers=["Content-Type"])
logger.info("CORS origins: %s", allowed_origins)

POSTAL_CODE_REGEX = re.compile(r"^[A-Z]\d[A-Z]\d[A-Z]\d$")

# English-only for now. Sent on every response so the envelope is stable when
# i18n returns; there is no ?lang= input param anymore.
LANG = "en"

# Display ordering: municipal -> provincial/(state/territorial) -> federal.
# Widened to the full schema enum; extra levels simply won't appear until
# there is data for them.
LEVEL_ORDER = {
    "municipal": 0,
    "provincial": 1,
    "state": 1,
    "territorial": 1,
    "federal": 2,
}


# ── Column orders (db.py cursors return tuples; we zip by these) ─────────────
JURISDICTION_COLS = (
    "slug", "name", "level", "country_code", "province_code", "parent_slug",
    "governance_type", "partisan", "district_term", "role_label_singular",
    "role_label_plural", "expected_district_count", "last_election",
    "election_date_set", "next_election", "term_duration_years",
    "governance_summary", "boundary_file", "boundary_district_id_column",
)
JURISDICTION_SELECT = ", ".join(JURISDICTION_COLS)

# jurisdiction_slug leads so /lookup can group multi-level results; the shaper
# ignores it (and source_url/last_verified) for the base Politician object.
POLITICIAN_COLS = (
    "jurisdiction_slug", "uuid", "slug", "role_scope", "district_id",
    "district_name", "honorific", "first_name", "last_name", "standard_role",
    "specific_title", "party_name", "date_elected", "next_election", "phone",
    "email", "website", "photo_url", "source_url", "last_verified",
)
POLITICIAN_SELECT = ", ".join(POLITICIAN_COLS)


# ── SQL ──────────────────────────────────────────────────────────────────────
# Point-in-polygon. ST_MakePoint takes (x=lon, y=lat); SRID 4326 matches the
# districts.boundary column. Returns one district per covering jurisdiction
# (federal riding, provincial riding, municipal ward — overlapping geographies).
MATCHED_DISTRICTS_SQL = """
    SELECT jurisdiction_slug, external_id, name
    FROM districts
    WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint(%s, %s), 4326));
"""

POLITICIANS_BY_SLUGS_SQL = f"""
    SELECT {POLITICIAN_SELECT}
    FROM politicians
    WHERE jurisdiction_slug = ANY(%s)
    ORDER BY last_name, first_name;
"""

POLITICIANS_BY_SLUG_SQL = f"""
    SELECT {POLITICIAN_SELECT}
    FROM politicians
    WHERE jurisdiction_slug = %s
    ORDER BY last_name, first_name;
"""

POLITICIAN_ROWS_BY_SLUG_SQL = f"""
    SELECT {POLITICIAN_SELECT}
    FROM politicians
    WHERE jurisdiction_slug = %s AND slug = %s
    ORDER BY role_scope, standard_role;
"""

JURISDICTIONS_BY_SLUGS_SQL = f"""
    SELECT {JURISDICTION_SELECT}
    FROM jurisdictions
    WHERE slug = ANY(%s);
"""

JURISDICTION_BY_SLUG_SQL = f"""
    SELECT {JURISDICTION_SELECT}
    FROM jurisdictions
    WHERE slug = %s;
"""

JURISDICTIONS_INDEX_SQL = """
    SELECT slug, name, level, country_code, province_code
    FROM jurisdictions
    ORDER BY level, name;
"""


# ── Shapers ──────────────────────────────────────────────────────────────────
def _iso(d) -> str:
    """psycopg2 returns DATE as datetime.date; emit ISO string or ''."""
    return d.isoformat() if d is not None else ""


def _politician(d: dict) -> dict:
    """Shape one politicians row (as a dict) into the frontend Politician type.

    Composes full_name, mirrors specific_title into display_title, coalesces
    every nullable field to "". slug falls back to uuid as a temporary shim if
    the slug column hasn't been backfilled yet (TECH DEBT: uuid URLs are a
    downgrade; run backfill_politician_slugs.py before launch).
    """
    full_name = " ".join(
        p for p in (d["honorific"], d["first_name"], d["last_name"]) if p
    ).strip()
    return {
        "uuid": str(d["uuid"]),
        "slug": d["slug"] or str(d["uuid"]),
        "full_name": full_name,
        "standard_role": d["standard_role"],
        "specific_title": d["specific_title"],
        "display_title": d["specific_title"],
        "party_name": d["party_name"] or "",
        "district_id": d["district_id"] or "",
        "district_name": d["district_name"] or "",
        "date_elected": _iso(d["date_elected"]),
        "next_election": _iso(d["next_election"]),
        "phone": d["phone"] or "",
        "email": d["email"] or "",
        "website": d["website"] or "",
        "photo_url": d["photo_url"] or "",
    }


def _governance(j: dict) -> dict:
    """Per-jurisdiction governance metadata (the frontend's date-fallback inputs)."""
    return {
        "governance_type": j["governance_type"],
        "partisan": bool(j["partisan"]),
        "district_term": j["district_term"] or "",
        "role_label_singular": j["role_label_singular"] or "",
        "role_label_plural": j["role_label_plural"] or "",
        "governance_summary": j["governance_summary"] or "",
        "last_election": _iso(j["last_election"]),
        "next_election": _iso(j["next_election"]),
        "election_date_set": bool(j["election_date_set"]),
        "term_duration_years": j["term_duration_years"] or 0,
    }


def _jurisdiction_summary(j: dict) -> dict:
    return {
        "slug": j["slug"],
        "name": j["name"],
        "level": j["level"],
        "country_code": j["country_code"],
        "province_code": j["province_code"] or "",
    }


def _split_leadership(role_politicians: list[dict]):
    """Partition role-scoped politicians into (executive, cabinet[], misc[]).

    executive is a single object (or None). One row per role means a misc-heavy
    person (e.g. party leader + opposition leader + critic) yields multiple misc
    entries by design; the frontend decides how to render them.
    """
    execs = [p for p in role_politicians if p["standard_role"] == "executive"]
    if len(execs) > 1:
        logger.warning(
            "Multiple executive rows found (%d); using first: %s",
            len(execs), [p["full_name"] for p in execs],
        )
    return (
        execs[0] if execs else None,
        [p for p in role_politicians if p["standard_role"] == "cabinet"],
        [p for p in role_politicians if p["standard_role"] == "misc"],
    )


# ── Geocoding (preserved from v1; uses the existing geocode_cache table) ─────
def validate_postal_code(postal_code: str) -> bool:
    """Validate Canadian postal code format (A1A1A1, no spaces)."""
    return bool(POSTAL_CODE_REGEX.match(postal_code))


def geocode(postal_code: str):
    """Convert a postal code to (lat, lon) via Google Maps, cache-first."""
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


# ── /lookup ──────────────────────────────────────────────────────────────────
@app.route("/lookup", methods=["GET"])
def lookup():
    raw = request.args.get("postal_code", "").strip().upper().replace(" ", "")
    if not raw:
        return jsonify({"error": "postal_code parameter is required"}), 400
    if not validate_postal_code(raw):
        return jsonify({"error": "Invalid postal code format. Expected: A1A1A1"}), 400

    lat, lon = geocode(raw)
    if lat is None:
        return jsonify({"error": "Could not geocode postal code"}), 404

    # 1. Which district contains the point, at each level we have data for.
    district_rows = db.query(MATCHED_DISTRICTS_SQL, (lon, lat))
    if not district_rows:
        # No registered jurisdiction's boundary covers this point.
        return jsonify({
            "postal_code": raw,
            "lang": LANG,
            "coordinates": {"lat": lat, "lon": lon},
            "levels": [],
        })

    # slug -> set of matched external_ids (usually one; a set guards against a
    # point landing in two overlapping districts of the same jurisdiction).
    matched_ext: dict[str, set] = {}
    for jslug, ext_id, _dname in district_rows:
        matched_ext.setdefault(jslug, set()).add(ext_id)

    slugs = list(matched_ext.keys())

    # 2. All politicians and 3. governance for the matched jurisdictions.
    pol_rows = db.query(POLITICIANS_BY_SLUGS_SQL, (slugs,))
    jur_rows = db.query(JURISDICTIONS_BY_SLUGS_SQL, (slugs,))

    pols_by_slug: dict[str, list[dict]] = {s: [] for s in slugs}
    for row in pol_rows:
        d = dict(zip(POLITICIAN_COLS, row))
        pols_by_slug.setdefault(d["jurisdiction_slug"], []).append(d)

    jur_by_slug = {row[0]: dict(zip(JURISDICTION_COLS, row)) for row in jur_rows}

    levels = []
    for slug in slugs:
        j = jur_by_slug.get(slug)
        if j is None:
            logger.warning("District matched slug=%s with no jurisdictions row", slug)
            continue

        people = pols_by_slug.get(slug, [])
        reps = [
            _politician(p)
            for p in people
            if p["role_scope"] == "district" and p["district_id"] in matched_ext[slug]
        ]
        role_politicians = [_politician(p) for p in people if p["role_scope"] == "role"]
        executive, cabinet, other = _split_leadership(role_politicians)

        levels.append({
            "level": j["level"],
            "jurisdiction": {
                "slug": j["slug"],
                "name": j["name"],
                "level": j["level"],
                "governance": _governance(j),
            },
            "representatives": reps,
            "executive": executive,
            "cabinet": cabinet,
            "other_leadership": other,
        })

    levels.sort(key=lambda lv: (LEVEL_ORDER.get(lv["level"], 99), lv["jurisdiction"]["name"]))

    return jsonify({
        "postal_code": raw,
        "lang": LANG,
        "coordinates": {"lat": lat, "lon": lon},
        "levels": levels,
    })


# ── /jurisdictions ───────────────────────────────────────────────────────────
@app.route("/jurisdictions", methods=["GET"])
def jurisdictions_index():
    rows = db.query(JURISDICTIONS_INDEX_SQL)
    jurisdictions = [
        {
            "slug": r[0],
            "name": r[1],
            "level": r[2],
            "country_code": r[3],
            "province_code": r[4] or "",
        }
        for r in rows
    ]
    return jsonify({"lang": LANG, "jurisdictions": jurisdictions})


# ── /jurisdiction/<slug> ─────────────────────────────────────────────────────
@app.route("/jurisdiction/<slug>", methods=["GET"])
def jurisdiction_detail(slug: str):
    """Full roster for one jurisdiction: governance + all reps + leadership."""
    j_rows = db.query(JURISDICTION_BY_SLUG_SQL, (slug,))
    if not j_rows:
        return jsonify({"error": f"Jurisdiction not found: {slug}"}), 404
    j = dict(zip(JURISDICTION_COLS, j_rows[0]))

    people = [dict(zip(POLITICIAN_COLS, r)) for r in db.query(POLITICIANS_BY_SLUG_SQL, (slug,))]
    reps = [_politician(p) for p in people if p["role_scope"] == "district"]
    role_politicians = [_politician(p) for p in people if p["role_scope"] == "role"]
    executive, cabinet, other = _split_leadership(role_politicians)

    return jsonify({
        "lang": LANG,
        "jurisdiction": {**_jurisdiction_summary(j), "governance": _governance(j)},
        "representatives": reps,
        "executive": executive,
        "cabinet": cabinet,
        "other_leadership": other,
    })


# ── /representative/<jurisdiction_slug>/<slug> ───────────────────────────────
@app.route("/representative/<jurisdiction_slug>/<slug>", methods=["GET"])
def representative_detail(jurisdiction_slug: str, slug: str):
    """One politician within a jurisdiction: identity + every role they hold.

    Routes on the readable slug (per-jurisdiction unique). Requires the slug
    column to be backfilled; the uuid shim in _politician() is display-only and
    will NOT resolve here until backfill_politician_slugs.py has run.
    """
    rows = db.query(POLITICIAN_ROWS_BY_SLUG_SQL, (jurisdiction_slug, slug))
    if not rows:
        return jsonify({
            "error": f"Representative not found: {jurisdiction_slug}/{slug}"
        }), 404

    people = [dict(zip(POLITICIAN_COLS, r)) for r in rows]

    # Canonical identity row: prefer the district representative row, else the
    # executive, else the first row. All rows share identity fields + uuid.
    canonical = next((p for p in people if p["role_scope"] == "district"), None)
    if canonical is None:
        canonical = next((p for p in people if p["standard_role"] == "executive"), people[0])

    representative = {
        **_politician(canonical),
        "source_url": canonical["source_url"] or "",
        "last_verified": _iso(canonical["last_verified"]),
    }

    j_rows = db.query(JURISDICTION_BY_SLUG_SQL, (jurisdiction_slug,))
    jurisdiction = (
        _jurisdiction_summary(dict(zip(JURISDICTION_COLS, j_rows[0]))) if j_rows else None
    )

    representations = [
        {
            "standard_role": p["standard_role"],
            "specific_title": p["specific_title"],
            "district_id": p["district_id"] or "",
            "district_name": p["district_name"] or "",
        }
        for p in people
    ]

    return jsonify({
        "lang": LANG,
        "representative": representative,
        "jurisdiction": jurisdiction,
        "representations": representations,
    })


# ── /health ──────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    try:
        db.query_one("SELECT 1;")
        database = "connected"
    except Exception:
        logger.exception("Health check DB query failed")
        database = "unavailable"
    return jsonify({
        "status": "ok" if database == "connected" else "degraded",
        "message": "Parliament API is running",
        "database": database,
    })


# ── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        port=int(os.getenv("PORT", "5000")),
        host="0.0.0.0",
    )
