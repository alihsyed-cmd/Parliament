import geopandas as gpd
import requests

# ── Path configuration ──────────────────────────────────────────────
# Update these paths to match where your files are located on your machine
FEDERAL_SHP  = "/Users/alisyed/Desktop/Parliament/data/federal/FED_CA_2025_EN.shp"
ONTARIO_SHP  = "/Users/alisyed/Desktop/Parliament/data/provincial/ontario/ELECTORAL_DISTRICT.shp"
TORONTO_JSON = "/Users/alisyed/Desktop/Parliament/data/municipal/toronto/toronto_wards.geojson"

# ── Load boundary files ─────────────────────────────────────────────
print("Loading boundary files...")
federal  = gpd.read_file(FEDERAL_SHP)
ontario  = gpd.read_file(ONTARIO_SHP)
toronto  = gpd.read_file(TORONTO_JSON)

# Ensure all layers use the same coordinate system (WGS84)
federal = federal.to_crs(epsg=4326)
ontario = ontario.to_crs(epsg=4326)
toronto = toronto.to_crs(epsg=4326)
print("Boundary files loaded successfully.\n")

# ── Geocode postal code via Nominatim ───────────────────────────────
def geocode(postal_code):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": postal_code + ", Canada",
        "format": "json",
        "limit": 1
    }
    headers = {"User-Agent": "ParliamentApp/1.0"}
    response = requests.get(url, params=params, headers=headers)
    results = response.json()
    if not results:
        return None, None
    lat = float(results[0]["lat"])
    lon = float(results[0]["lon"])
    return lat, lon

# ── Point-in-polygon lookup ─────────────────────────────────────────
def find_district(lat, lon, boundaries, name_field):
    from shapely.geometry import Point
    point = Point(lon, lat)  # Note: shapely uses (longitude, latitude) order
    for _, row in boundaries.iterrows():
        if row.geometry.contains(point):
            return row[name_field]
    return "Not found"

# ── Main lookup function ────────────────────────────────────────────
def lookup(postal_code):
    print(f"Looking up: {postal_code}")
    lat, lon = geocode(postal_code)
    if lat is None:
        print("Could not geocode that postal code. Check spelling and try again.")
        return
    print(f"Coordinates: {lat}, {lon}\n")

    # Look up each layer
    # Note: you may need to update the name_field values below after
    # inspecting your files — we will confirm these in the next step
    fed_riding  = find_district(lat, lon, federal, "ENNAME")
    ont_riding  = find_district(lat, lon, ontario, "ENGLISH_NA")
    tor_ward    = find_district(lat, lon, toronto, "AREA_NAME")

    print(f"Federal Riding:      {fed_riding}")
    print(f"Ontario Riding:      {ont_riding}")
    print(f"Toronto Ward:        {tor_ward}")

# ── Run ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    postal_code = input("Enter a Canadian postal code: ")
    lookup(postal_code.strip().upper())