import geopandas as gpd
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import time
import re
import os
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# ── File paths ───────────────────────────────────────────────────────
FEDERAL_SHP   = "/Users/alisyed/Desktop/Parliament/data/federal/FED_CA_2025_EN.shp"
ONTARIO_SHP   = "/Users/alisyed/Desktop/Parliament/data/provincial/ontario/ELECTORAL_DISTRICT.shp"
TORONTO_JSON  = "/Users/alisyed/Desktop/Parliament/data/municipal/toronto/Ward and Elected Councillor - 4326.geojson"

FEDERAL_XML   = "/Users/alisyed/Desktop/Parliament/data/federal/Members' information.xml"
ONTARIO_CSV   = "/Users/alisyed/Desktop/Parliament/data/provincial/ontario/Contacts of all Ontario members.csv"
TORONTO_CSV   = "/Users/alisyed/Desktop/Parliament/data/municipal/toronto/Elected Officials' Contact Information.csv"

# ── Load boundary files ──────────────────────────────────────────────
print("Loading boundary files...")
federal  = gpd.read_file(FEDERAL_SHP).to_crs(epsg=4326)
ontario  = gpd.read_file(ONTARIO_SHP).to_crs(epsg=4326)
toronto  = gpd.read_file(TORONTO_JSON).to_crs(epsg=4326)
print("Boundary files loaded successfully.\n")

# ── Load representative data files ──────────────────────────────────
print("Loading representative data...")

# Federal: parse XML into a dict keyed by riding name
fed_tree = ET.parse(FEDERAL_XML)
fed_members = {}
for mp in fed_tree.getroot():
    riding     = mp.findtext("ConstituencyName", "").strip()
    first      = mp.findtext("PersonOfficialFirstName", "").strip()
    last       = mp.findtext("PersonOfficialLastName", "").strip()
    honorific  = mp.findtext("PersonShortHonorific", "").strip()
    party      = mp.findtext("CaucusShortName", "").strip()
    elected    = mp.findtext("FromDateTime", "").strip()[:10]  # YYYY-MM-DD
    person_id  = mp.findtext("PersonId", "").strip()
    full_name  = f"{honorific} {first} {last}".strip()
    photo_url  = f"https://www.ourcommons.ca/Content/Parliamentarians/Images/OfficialMPPhotos/45/{person_id}_Original.jpg"
    fed_members[riding] = {
        "name":      full_name,
        "party":     party,
        "elected":   elected,
        "photo_url": photo_url,
    }

# Ontario: load CSV, keep only constituency offices, key by riding name
ont_df = pd.read_csv(ONTARIO_CSV)
ont_df.columns = ont_df.columns.str.strip().str.replace('"', '')
# Keep one row per riding (constituency office preferred)
ont_members = {}
for _, row in ont_df.iterrows():
    riding = str(row.get("Riding name", "")).strip()
    if not riding or riding == "nan":
        continue
    if riding not in ont_members:
        first  = str(row.get("First name", "")).strip()
        last   = str(row.get("Last name", "")).strip()
        hon    = str(row.get("Honorific", "")).strip()
        party  = str(row.get("Party", "")).strip()
        email  = str(row.get("Email", "")).strip()
        phone  = str(row.get("Telephone", "")).strip()
        name   = f"{hon} {first} {last}".strip() if hon and hon != "nan" else f"{first} {last}".strip()
        ont_members[riding] = {
            "name":  name,
            "party": party,
            "email": email if email != "nan" else "Not available",
            "phone": phone if phone != "nan" else "Not available",
        }

# Toronto: load CSV, key by district name
tor_df = pd.read_csv(TORONTO_CSV)
tor_members = {}
for _, row in tor_df.iterrows():
    district = str(row.get("District name", "")).strip()
    if not district or district == "nan":
        continue
    first     = str(row.get("First name", "")).strip()
    last      = str(row.get("Last name", "")).strip()
    role      = str(row.get("Primary role", "")).strip()
    email     = str(row.get("Email", "")).strip()
    phone     = str(row.get("Phone", "")).strip()
    photo_url = str(row.get("Photo URL", "")).strip()
    website   = str(row.get("Website", "")).strip()
    tor_members[district] = {
        "name":      f"{first} {last}".strip(),
        "role":      role,
        "email":     email if email != "nan" else "Not available",
        "phone":     phone if phone != "nan" else "Not available",
        "photo_url": photo_url if photo_url != "nan" else None,
        "website":   website if website != "nan" else None,
    }

print("Representative data loaded successfully.\n")

# ── Input validation ─────────────────────────────────────────────────
def validate_postal_code(code):
    pattern = r'^[A-Z]\d[A-Z]\d[A-Z]\d$'
    return bool(re.match(pattern, code.replace(" ", "").upper()))


def geocode(postal_code):
    clean = postal_code.replace(" ", "").upper()
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address":    clean + ", Canada",
        "components": "country:CA",
        "key":        GOOGLE_API_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if data["status"] == "OK":
            location = data["results"][0]["geometry"]["location"]
            return location["lat"], location["lng"]
        print(f"Google geocoding error: {data['status']}")
        return None, None
    except Exception as e:
        print(f"Geocoding failed: {e}")
        return None, None

# ── Point-in-polygon lookup ──────────────────────────────────────────
def find_district(lat, lon, boundaries, name_field):
    from shapely.geometry import Point
    point = Point(lon, lat)
    indices = boundaries.sindex.query(point, predicate="within")
    if len(indices) > 0:
        return boundaries.iloc[indices[0]][name_field]
    return None

# ── Display helpers ──────────────────────────────────────────────────
def print_section(title):
    print("\n" + "=" * 50)
    print(f"  {title}")
    print("=" * 50)

def print_field(label, value):
    if value and value not in ("Not available", "nan", "None", ""):
        print(f"  {label:<20} {value}")

# ── Main lookup ──────────────────────────────────────────────────────
def lookup(postal_code):
    if not validate_postal_code(postal_code):
        print("Invalid postal code format. Expected format: A1A1A1 or A1A 1A1")
        return
    print(f"\nLooking up: {postal_code}")
    lat, lon = geocode(postal_code)
    if lat is None:
        print("Could not geocode that postal code.")
        return
    print(f"Coordinates: {lat:.6f}, {lon:.6f}")

    # ── Federal ──────────────────────────────────────────────────────
    fed_riding = find_district(lat, lon, federal, "ED_NAMEE")
    print_section(f"FEDERAL — {fed_riding or 'Riding not found'}")
    if fed_riding and fed_riding in fed_members:
        mp = fed_members[fed_riding]
        print_field("Member of Parliament:", mp["name"])
        print_field("Party:", mp["party"])
        print_field("Elected:", mp["elected"])
        print_field("Next election:", "On or before October 2029")
        print_field("Photo:", mp["photo_url"])
    else:
        print("  No MP data found for this riding.")

    # ── Provincial ───────────────────────────────────────────────────
    ont_riding = find_district(lat, lon, ontario, "ENGLISH_NA")
    print_section(f"PROVINCIAL (Ontario) — {ont_riding or 'Riding not found'}")
    if ont_riding and ont_riding in ont_members:
        mpp = ont_members[ont_riding]
        print_field("MPP:", mpp["name"])
        print_field("Party:", mpp["party"])
        print_field("Next election:", "On or before June 2026")
        print_field("Email:", mpp["email"])
        print_field("Phone:", mpp["phone"])
    else:
        print("  No MPP data found for this riding.")

    # ── Municipal ────────────────────────────────────────────────────
    tor_ward = find_district(lat, lon, toronto, "AREA_NAME")
    print_section(f"MUNICIPAL (Toronto) — {tor_ward or 'Outside Toronto'}")
    if tor_ward:
        # Match ward name to Toronto CSV district name
        match = None
        for district, data in tor_members.items():
            if tor_ward.lower() in district.lower() or district.lower() in tor_ward.lower():
                match = data
                break
        if match:
            print_field("Councillor:", match["name"])
            print_field("Role:", match["role"])
            print_field("Email:", match["email"])
            print_field("Phone:", match["phone"])
            print_field("Website:", match["website"])
            print_field("Photo:", match["photo_url"])
        else:
            print("  Ward found but no councillor data matched.")
    else:
        print("  This postal code is outside Toronto.")

    print("\n" + "=" * 50 + "\n")

# ── Run ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    while True:
        try:
            postal_code = input("Enter a Canadian postal code (or 'q' to quit): ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if postal_code.strip().lower() in ("q", "quit", "exit"):
            break
        lookup(postal_code.strip().upper())