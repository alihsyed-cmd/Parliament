from flask import Flask, jsonify, request
import geopandas as gpd
import requests as req
import xml.etree.ElementTree as ET
import pandas as pd
import os
import time
from dotenv import load_dotenv

load_dotenv('/Users/alisyed/Desktop/Parliament/.env')
GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

app = Flask(__name__)

# ── File paths ───────────────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
FEDERAL_SHP    = os.getenv("FEDERAL_SHP")
ONTARIO_SHP    = os.getenv("ONTARIO_SHP")
TORONTO_JSON   = os.getenv("TORONTO_JSON")
FEDERAL_XML    = os.getenv("FEDERAL_XML")
ONTARIO_CSV    = os.getenv("ONTARIO_CSV")
TORONTO_CSV    = os.getenv("TORONTO_CSV")

# ── Load boundary files ──────────────────────────────────────────────
print("Loading boundary files...")
federal = gpd.read_file(FEDERAL_SHP).to_crs(epsg=4326)
ontario = gpd.read_file(ONTARIO_SHP).to_crs(epsg=4326)
toronto = gpd.read_file(TORONTO_JSON).to_crs(epsg=4326)
print("Boundary files loaded.")

# ── Load representative data ─────────────────────────────────────────
print("Loading representative data...")

fed_tree = ET.parse(FEDERAL_XML)
fed_members = {}
for mp in fed_tree.getroot():
    riding    = mp.findtext("ConstituencyName", "").strip()
    first     = mp.findtext("PersonOfficialFirstName", "").strip()
    last      = mp.findtext("PersonOfficialLastName", "").strip()
    honorific = mp.findtext("PersonShortHonorific", "").strip()
    party     = mp.findtext("CaucusShortName", "").strip()
    elected   = mp.findtext("FromDateTime", "").strip()[:10]
    person_id = mp.findtext("PersonId", "").strip()
    full_name = f"{honorific} {first} {last}".strip() if honorific else f"{first} {last}".strip()
    fed_members[riding] = {
        "name":          full_name,
        "party":         party,
        "elected":       elected,
        "next_election": "On or before October 2029",
        "photo_url":     f"https://www.ourcommons.ca/Content/Parliamentarians/Images/OfficialMPPhotos/45/{person_id}_Original.jpg"
    }

ont_df = pd.read_csv(ONTARIO_CSV)
ont_df.columns = ont_df.columns.str.strip().str.replace('"', '')
ont_members = {}
for _, row in ont_df.iterrows():
    riding = str(row.get("Riding name", "")).strip()
    if not riding or riding == "nan" or riding in ont_members:
        continue
    first = str(row.get("First name", "")).strip()
    last  = str(row.get("Last name", "")).strip()
    hon   = str(row.get("Honorific", "")).strip()
    ont_members[riding] = {
        "name":          f"{hon} {first} {last}".strip() if hon and hon != "nan" else f"{first} {last}".strip(),
        "party":         str(row.get("Party", "")).strip(),
        "next_election": "On or before April 11, 2030",
        "email":         str(row.get("Email", "")).strip(),
        "phone":         str(row.get("Telephone", "")).strip(),
    }

tor_df = pd.read_csv(TORONTO_CSV)
tor_members = {}
for _, row in tor_df.iterrows():
    district = str(row.get("District name", "")).strip()
    if not district or district == "nan":
        continue
    tor_members[district] = {
        "name":      f"{str(row.get('First name','')).strip()} {str(row.get('Last name','')).strip()}".strip(),
        "role":      str(row.get("Primary role", "")).strip(),
        "email":     str(row.get("Email", "")).strip(),
        "phone":     str(row.get("Phone", "")).strip(),
        "photo_url": str(row.get("Photo URL", "")).strip(),
        "website":   str(row.get("Website", "")).strip(),
    }

print("All data loaded. API ready.\n")

# ── Helpers ──────────────────────────────────────────────────────────
def geocode(postal_code):
    clean = postal_code.replace(" ", "").upper()
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address":    clean + ", Canada",
        "components": "country:CA",
        "key":        GOOGLE_API_KEY
    }
    try:
        response = req.get(url, params=params, timeout=10)
        data = response.json()
        if data["status"] == "OK":
            loc = data["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
        return None, None
    except Exception:
        return None, None

def find_district(lat, lon, boundaries, name_field):
    from shapely.geometry import Point
    point = Point(lon, lat)
    for _, row in boundaries.iterrows():
        if row.geometry and row.geometry.contains(point):
            return row[name_field]
    return None

def clean(value):
    if not value or str(value).strip() in ("nan", "None", ""):
        return None
    return str(value).strip()

# ── API endpoint ─────────────────────────────────────────────────────
@app.route("/lookup", methods=["GET"])
def lookup():
    postal_code = request.args.get("postal_code", "").strip().upper()
    if not postal_code:
        return jsonify({"error": "postal_code parameter is required"}), 400

    lat, lon = geocode(postal_code)
    if lat is None:
        return jsonify({"error": "Could not geocode postal code"}), 404

    # Federal
    fed_riding = find_district(lat, lon, federal, "ED_NAMEE")
    fed_data   = fed_members.get(fed_riding, {})

    # Provincial
    ont_riding = find_district(lat, lon, ontario, "ENGLISH_NA")
    ont_data   = ont_members.get(ont_riding, {})

    # Municipal
    tor_ward  = find_district(lat, lon, toronto, "AREA_NAME")
    tor_data  = {}
    if tor_ward:
        for district, data in tor_members.items():
            if tor_ward.lower() in district.lower() or district.lower() in tor_ward.lower():
                tor_data = data
                break

    result = {
        "postal_code": postal_code,
        "coordinates": {"lat": lat, "lon": lon},
        "federal": {
            "riding":        clean(fed_riding),
            "mp":            clean(fed_data.get("name")),
            "party":         clean(fed_data.get("party")),
            "elected":       clean(fed_data.get("elected")),
            "next_election": clean(fed_data.get("next_election")),
            "photo_url":     clean(fed_data.get("photo_url")),
        },
        "provincial": {
            "riding":        clean(ont_riding),
            "mpp":           clean(ont_data.get("name")),
            "party":         clean(ont_data.get("party")),
            "next_election": clean(ont_data.get("next_election")),
            "email":         clean(ont_data.get("email")),
            "phone":         clean(ont_data.get("phone")),
        },
        "municipal": {
            "ward":          clean(tor_ward),
            "councillor":    clean(tor_data.get("name")),
            "role":          clean(tor_data.get("role")),
            "email":         clean(tor_data.get("email")),
            "phone":         clean(tor_data.get("phone")),
            "photo_url":     clean(tor_data.get("photo_url")),
            "website":       clean(tor_data.get("website")),
        }
    }

    return jsonify(result)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "Parliament API is running"})

# ── Run ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)