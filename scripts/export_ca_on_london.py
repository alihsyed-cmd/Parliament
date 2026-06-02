#!/usr/bin/env python3
"""
Export subagent — ca_on_london
Mirrors canonical data for the City of London, Ontario to Supabase in one transaction.
"""

import csv
import os
import sys

import geopandas as gpd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

SLUG = "ca_on_london"
BASE = "/Users/alisyed/Desktop/Parliament"

POLITICIANS_CSV   = f"{BASE}/data/{SLUG}/politicians.csv"
JURISDICTIONS_CSV = f"{BASE}/data/jurisdictions.csv"
BOUNDARY_FILE     = f"{BASE}/data/{SLUG}/wards_2026.geojson"
ENV_FILE          = f"{BASE}/.env"

EXPECTED_POLITICIANS_HEADER = [
    "uuid", "role_scope", "district_id", "district_name", "honorific",
    "first_name", "last_name", "standard_role", "specific_title", "party_name",
    "date_elected", "next_election", "phone", "email", "website",
    "photo_url", "source_url", "last_verified", "slug",
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def none_if_empty(v):
    """Convert empty string to None; otherwise return as-is."""
    if v == "" or v is None:
        return None
    return v

def to_bool(v):
    """Convert 'true'/'false' string to Python bool; empty → None."""
    if v == "" or v is None:
        return None
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    raise ValueError(f"Unexpected boolean value: {v!r}")

def coerce_external_id(val):
    """Coerce boundary district-id to verbatim politician-matching string."""
    s = str(val).strip()
    # Integral float like '1.0' → '1'
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
    except (ValueError, TypeError):
        pass
    return s

# ── Self-check 1: Header gate ────────────────────────────────────────────────

with open(POLITICIANS_CSV, encoding="utf-8", newline="") as f:
    reader = csv.reader(f)
    header = next(reader)

if header != EXPECTED_POLITICIANS_HEADER:
    print(f"REFUSED: politicians.csv header mismatch.")
    print(f"  Expected: {EXPECTED_POLITICIANS_HEADER}")
    print(f"  Got:      {header}")
    print("Nothing written. Regenerate this jurisdiction before exporting.")
    sys.exit(1)

print("Self-check 1 PASS — header is correct (19 columns).")

# ── Self-check 2: Jurisdiction presence ──────────────────────────────────────

juris_row = None
with open(JURISDICTIONS_CSV, encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row["slug"] == SLUG:
            if juris_row is not None:
                print(f"REFUSED: jurisdictions.csv has more than one row for slug '{SLUG}'.")
                sys.exit(1)
            juris_row = row

if juris_row is None:
    print(f"REFUSED: no row for slug '{SLUG}' in jurisdictions.csv.")
    sys.exit(1)

boundary_filename = juris_row["boundary_file"]
boundary_path = f"{BASE}/data/{SLUG}/{boundary_filename}"

if not os.path.exists(boundary_path):
    print(f"REFUSED: boundary file '{boundary_path}' not found.")
    sys.exit(1)

print(f"Self-check 2 PASS — jurisdiction row found; boundary file '{boundary_filename}' exists.")

# ── Self-check 3: CRS resolvable ─────────────────────────────────────────────

gdf = gpd.read_file(boundary_path)
source_crs = str(gdf.crs) if gdf.crs else "None"

if gdf.crs is None:
    # GeoJSON with no declared CRS → assume EPSG:4326 per RFC 7946
    print(f"Self-check 3 PASS — GeoJSON with no declared CRS; assuming EPSG:4326.")
elif gdf.crs.to_epsg() != 4326:
    print(f"Self-check 3 PASS — reprojecting from {source_crs} to EPSG:4326.")
    gdf = gdf.to_crs(4326)
    source_crs_label = source_crs
else:
    print(f"Self-check 3 PASS — CRS is already EPSG:4326.")
    source_crs_label = "EPSG:4326"

# ── Self-check 4: Join-key subset ────────────────────────────────────────────

id_col = juris_row["boundary_district_id_column"]  # "Ward"
boundary_external_ids = set(coerce_external_id(v) for v in gdf[id_col])

politician_district_ids = set()
with open(POLITICIANS_CSV, encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row["role_scope"] == "district" and row["district_id"]:
            politician_district_ids.add(row["district_id"])

missing = politician_district_ids - boundary_external_ids
if missing:
    print(f"REFUSED: join-key subset check failed. "
          f"Politician district_id values not in boundary: {sorted(missing)}")
    print("Nothing written.")
    sys.exit(1)

print(f"Self-check 4 PASS — all {len(politician_district_ids)} politician district_id(s) "
      f"found in boundary external_id set ({len(boundary_external_ids)} total).")

# ── Build geometry rows ──────────────────────────────────────────────────────

# Build district_id → district_name map from politicians.csv
dist_name_map = {}
with open(POLITICIANS_CSV, encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row["role_scope"] == "district" and row["district_id"]:
            eid = row["district_id"]
            name = none_if_empty(row["district_name"])
            if eid not in dist_name_map and name is not None:
                dist_name_map[eid] = name

district_rows = []
for _, feat in gdf.iterrows():
    eid = coerce_external_id(feat[id_col])
    dname = dist_name_map.get(eid)  # None if no match
    wkt = feat.geometry.wkt
    district_rows.append((SLUG, eid, dname, wkt))

names_matched = sum(1 for _, eid, dn, _ in district_rows if dn is not None)
print(f"Geometry prepared: {len(district_rows)} features; "
      f"{names_matched}/{len(district_rows)} district names matched.")

# ── Build politician rows ─────────────────────────────────────────────────────

politician_rows = []
with open(POLITICIANS_CSV, encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        politician_rows.append((
            SLUG,                                     # jurisdiction_slug
            none_if_empty(row["uuid"]),               # uuid
            none_if_empty(row["role_scope"]),         # role_scope
            none_if_empty(row["district_id"]),        # district_id
            none_if_empty(row["district_name"]),      # district_name
            none_if_empty(row["honorific"]),          # honorific
            none_if_empty(row["first_name"]),         # first_name
            none_if_empty(row["last_name"]),          # last_name
            none_if_empty(row["standard_role"]),      # standard_role
            none_if_empty(row["specific_title"]),     # specific_title
            none_if_empty(row["party_name"]),         # party_name
            none_if_empty(row["date_elected"]),       # date_elected
            none_if_empty(row["next_election"]),      # next_election
            none_if_empty(row["phone"]),              # phone
            none_if_empty(row["email"]),              # email
            none_if_empty(row["website"]),            # website
            none_if_empty(row["photo_url"]),          # photo_url
            none_if_empty(row["source_url"]),         # source_url
            none_if_empty(row["last_verified"]),      # last_verified
            none_if_empty(row["slug"]),               # slug (per-person URL key)
        ))

print(f"Politicians prepared: {len(politician_rows)} rows.")

# ── Build jurisdiction upsert values ──────────────────────────────────────────

j = juris_row
juris_values = (
    none_if_empty(j["slug"]),
    none_if_empty(j["name"]),
    none_if_empty(j["level"]),
    none_if_empty(j["country_code"]),
    none_if_empty(j["province_code"]),
    none_if_empty(j["parent_slug"]),
    none_if_empty(j["governance_type"]),
    to_bool(j["partisan"]),
    none_if_empty(j["district_term"]),
    none_if_empty(j["role_label_singular"]),
    none_if_empty(j["role_label_plural"]),
    none_if_empty(j["expected_district_count"]) and int(j["expected_district_count"]) if j["expected_district_count"] else None,
    none_if_empty(j["last_election"]),
    to_bool(j["election_date_set"]),
    none_if_empty(j["next_election"]),
    none_if_empty(j["term_duration_years"]) and int(j["term_duration_years"]) if j["term_duration_years"] else None,
    none_if_empty(j["governance_summary"]),
    none_if_empty(j["boundary_file"]),
    none_if_empty(j["boundary_district_id_column"]),
)

# ── Load credentials ──────────────────────────────────────────────────────────

load_dotenv(ENV_FILE)
db_url = os.environ.get("SUPABASE_DB_URL")
if not db_url:
    print("REFUSED: SUPABASE_DB_URL not found in .env. Nothing written.")
    sys.exit(1)

# ── Execute transaction ───────────────────────────────────────────────────────

conn = None
prior_politician_count = 0
prior_district_count = 0

try:
    conn = psycopg2.connect(db_url)

    with conn:  # transaction: commit on success, rollback on exception
        with conn.cursor() as cur:

            # Count existing rows for the summary delta
            cur.execute("SELECT COUNT(*) FROM politicians WHERE jurisdiction_slug = %s", (SLUG,))
            prior_politician_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM districts WHERE jurisdiction_slug = %s", (SLUG,))
            prior_district_count = cur.fetchone()[0]

            # 1. Upsert jurisdiction
            cur.execute("""
                INSERT INTO jurisdictions (
                    slug, name, level, country_code, province_code, parent_slug,
                    governance_type, partisan, district_term, role_label_singular,
                    role_label_plural, expected_district_count, last_election,
                    election_date_set, next_election, term_duration_years,
                    governance_summary, boundary_file, boundary_district_id_column
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT (slug) DO UPDATE SET
                    name                        = EXCLUDED.name,
                    level                       = EXCLUDED.level,
                    country_code                = EXCLUDED.country_code,
                    province_code               = EXCLUDED.province_code,
                    parent_slug                 = EXCLUDED.parent_slug,
                    governance_type             = EXCLUDED.governance_type,
                    partisan                    = EXCLUDED.partisan,
                    district_term               = EXCLUDED.district_term,
                    role_label_singular         = EXCLUDED.role_label_singular,
                    role_label_plural           = EXCLUDED.role_label_plural,
                    expected_district_count     = EXCLUDED.expected_district_count,
                    last_election               = EXCLUDED.last_election,
                    election_date_set           = EXCLUDED.election_date_set,
                    next_election               = EXCLUDED.next_election,
                    term_duration_years         = EXCLUDED.term_duration_years,
                    governance_summary          = EXCLUDED.governance_summary,
                    boundary_file               = EXCLUDED.boundary_file,
                    boundary_district_id_column = EXCLUDED.boundary_district_id_column
            """, juris_values)
            print("Jurisdiction upserted.")

            # 2. Delete then insert politicians
            cur.execute("DELETE FROM politicians WHERE jurisdiction_slug = %s", (SLUG,))
            deleted_politicians = cur.rowcount
            print(f"Deleted {deleted_politicians} existing politician rows.")

            execute_values(cur, """
                INSERT INTO politicians (
                    jurisdiction_slug, uuid, role_scope, district_id, district_name,
                    honorific, first_name, last_name, standard_role, specific_title,
                    party_name, date_elected, next_election, phone, email, website,
                    photo_url, source_url, last_verified, slug
                ) VALUES %s
            """, politician_rows)
            print(f"Inserted {len(politician_rows)} politician rows.")

            # 3. Delete then insert districts
            cur.execute("DELETE FROM districts WHERE jurisdiction_slug = %s", (SLUG,))
            deleted_districts = cur.rowcount
            print(f"Deleted {deleted_districts} existing district rows.")

            execute_values(cur, """
                INSERT INTO districts (jurisdiction_slug, external_id, name, boundary)
                VALUES %s
            """, district_rows,
            template="(%s, %s, %s, ST_GeomFromText(%s, 4326))")
            print(f"Inserted {len(district_rows)} district rows.")

    # Transaction committed
    net_politicians = len(politician_rows) - prior_politician_count
    net_sign = f"+{net_politicians}" if net_politicians >= 0 else str(net_politicians)

    print()
    print("=" * 60)
    print(f"## Export — {SLUG}")
    print()
    print(f"Target: Supabase (jurisdictions, politicians, districts)")
    print()
    print(f"jurisdictions: upserted (slug {SLUG})")
    print(f"politicians:   {prior_politician_count} deleted, {len(politician_rows)} inserted"
          f"   (net {net_sign} vs prior)")
    print(f"districts:     {prior_district_count} deleted, {len(district_rows)} inserted"
          f"   (geometry CRS: EPSG:4326 → 4326; {len(district_rows)} features)")
    print(f"  district names matched from politicians.csv: "
          f"{names_matched}/{len(district_rows)}   (unmatched = vacancies, NULL name)")
    print()
    print("Empty → NULL conversions applied. Transaction committed.")

except Exception as e:
    print(f"\nERROR — transaction rolled back. Database is unchanged.")
    print(f"Exception: {e}")
    sys.exit(1)
finally:
    if conn:
        conn.close()
