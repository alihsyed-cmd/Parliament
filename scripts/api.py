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

GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if not GOOGLE_API_KEY:
    logger.critical("GOOGLE_MAPS_API_KEY is not set")
    raise RuntimeError("GOOGLE_MAPS_API_KEY is required")

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
