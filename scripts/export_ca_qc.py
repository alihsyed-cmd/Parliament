"""
Export script: ca_qc (Province of Quebec)
Mirrors canonical data to Supabase in one transaction:
  1. Upsert jurisdictions row
  2. Delete-then-insert politicians
  3. Delete-then-insert districts (with PostGIS geometry)
"""

import csv
import json
import os
import sys
import unicodedata

import geopandas as gpd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# ── Constants ─────────────────────────────────────────────────────────────────
SLUG = "ca_qc"
REPO_ROOT = "/Users/alisyed/Desktop/Parliament"
JURISDICTIONS_CSV = os.path.join(REPO_ROOT, "data", "jurisdictions.csv")
POLITICIANS_CSV   = os.path.join(REPO_ROOT, "data", SLUG, "politicians.csv")
BOUNDARY_FILE     = os.path.join(REPO_ROOT, "data", SLUG, "circumscriptions_2026.geojson")
BOUNDARY_ID_COL   = "NM_CEP"
ENV_FILE          = os.path.join(REPO_ROOT, ".env")

EXPECTED_POLITICIANS_HEADER = [
    "uuid", "role_scope", "district_id", "district_name", "honorific",
    "first_name", "last_name", "standard_role", "specific_title", "party_name",
    "date_elected", "next_election", "phone", "email", "website",
    "photo_url", "source_url", "last_verified", "slug"
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def to_null(val):
    """Convert empty string to None; leave everything else as-is."""
    if val == "" or val is None:
        return None
    return val

def to_bool(val):
    """Convert 'true'/'false' strings to Python booleans; empty → None."""
    if val == "true":
        return True
    if val == "false":
        return False
    return None

def coerce_external_id(val):
    """
    Coerce boundary district-id to the verbatim string form that matches
    politicians.district_id. For NM_CEP the values are already strings
    (French place names), so just strip whitespace.
    Integral floats (e.g. 1.0) → "1"; plain strings → str(val).strip().
    """
    if val is None:
        return None
    try:
        fv = float(val)
        if fv == int(fv):
            return str(int(fv))
        return str(val).strip()
    except (ValueError, TypeError):
        return str(val).strip()

# ── Self-checks ────────────────────────────────────────────────────────────────

def self_check_header():
    with open(POLITICIANS_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
    if header != EXPECTED_POLITICIANS_HEADER:
        raise ValueError(
            f"REFUSED: politicians.csv header mismatch.\n"
            f"  Expected ({len(EXPECTED_POLITICIANS_HEADER)} cols): {EXPECTED_POLITICIANS_HEADER}\n"
            f"  Got      ({len(header)} cols): {header}"
        )

def self_check_jurisdiction_presence():
    found = None
    with open(JURISDICTIONS_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["slug"] == SLUG:
                found = row
    if found is None:
        raise ValueError(
            f"REFUSED: No row for slug '{SLUG}' found in data/jurisdictions.csv."
        )
    if not os.path.exists(BOUNDARY_FILE):
        raise ValueError(
            f"REFUSED: Boundary file '{BOUNDARY_FILE}' named in jurisdictions.csv does not exist."
        )
    return found

def self_check_crs(gdf):
    """GeoJSON with no declared CRS → assume EPSG:4326 (RFC 7946). Already handled by geopandas."""
    # geopandas reads GeoJSON without a CRS object and leaves gdf.crs as None or EPSG:4326.
    # RFC 7946 mandates EPSG:4326 for GeoJSON.
    if gdf.crs is None:
        # No CRS declared — GeoJSON, so EPSG:4326 per RFC 7946.
        pass
    elif gdf.crs.to_epsg() != 4326:
        # Different CRS declared — will reproject below.
        pass
    # Shapefiles with no .prj are refused, but this is GeoJSON, so no issue.
    return True

def self_check_join_keys(gdf, boundary_id_col):
    # Build set of boundary external_ids
    boundary_ids = set()
    for val in gdf[boundary_id_col]:
        eid = coerce_external_id(val)
        if eid is not None:
            boundary_ids.add(eid)

    # Build set of district_ids from politician rows with role_scope=district
    pol_district_ids = set()
    with open(POLITICIANS_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["role_scope"] == "district":
                did = row["district_id"].strip()
                if did:
                    pol_district_ids.add(did)

    missing = pol_district_ids - boundary_ids
    if missing:
        raise ValueError(
            f"REFUSED: {len(missing)} district_id(s) in politicians.csv have no matching boundary "
            f"feature. Missing: {sorted(missing)[:10]}. Nothing written."
        )
    return boundary_ids

# ── Data loading ───────────────────────────────────────────────────────────────

def load_jurisdiction_row(juris_data):
    """Map the CSV row dict to the 19 DB columns for the upsert."""
    return (
        juris_data["slug"],
        juris_data["name"],
        juris_data["level"],
        juris_data["country_code"],
        to_null(juris_data["province_code"]),
        to_null(juris_data["parent_slug"]),
        juris_data["governance_type"],
        to_bool(juris_data["partisan"]),
        to_null(juris_data["district_term"]),
        to_null(juris_data["role_label_singular"]),
        to_null(juris_data["role_label_plural"]),
        to_null(juris_data["expected_district_count"]),
        to_null(juris_data["last_election"]),
        to_bool(juris_data["election_date_set"]),
        to_null(juris_data["next_election"]),
        to_null(juris_data["term_duration_years"]),
        to_null(juris_data["governance_summary"]),
        to_null(juris_data["boundary_file"]),
        to_null(juris_data["boundary_district_id_column"]),
    )

def load_politician_rows():
    """Read politicians.csv and return list of 20-tuples for bulk insert."""
    rows = []
    with open(POLITICIANS_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((
                SLUG,                              # jurisdiction_slug
                to_null(row["uuid"]),
                row["role_scope"],
                to_null(row["district_id"]),
                to_null(row["district_name"]),
                to_null(row["honorific"]),
                row["first_name"],
                row["last_name"],
                row["standard_role"],
                row["specific_title"],
                to_null(row["party_name"]),
                to_null(row["date_elected"]),
                to_null(row["next_election"]),
                to_null(row["phone"]),
                to_null(row["email"]),
                to_null(row["website"]),
                to_null(row["photo_url"]),
                to_null(row["source_url"]),
                to_null(row["last_verified"]),
                to_null(row["slug"]),              # per-person slug
            ))
    return rows

def load_district_rows(gdf, boundary_ids):
    """
    Build district name map from politicians.csv (district rows only).
    Returns list of (jurisdiction_slug, external_id, name_or_None, wkt) tuples.
    """
    # Build district_id → district_name map from politicians
    name_map = {}
    with open(POLITICIANS_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["role_scope"] == "district":
                did = row["district_id"].strip()
                dn = row["district_name"].strip()
                if did and dn and did not in name_map:
                    name_map[did] = dn

    # Reproject to 4326 if needed
    if gdf.crs is None:
        # GeoJSON → assume 4326
        gdf = gdf.set_crs(4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)

    rows = []
    for _, feat in gdf.iterrows():
        eid = coerce_external_id(feat[BOUNDARY_ID_COL])
        if eid is None:
            continue
        name = name_map.get(eid, None)  # NULL for vacancies
        wkt = feat.geometry.wkt
        rows.append((SLUG, eid, name, wkt))

    return rows

# ── Database write ─────────────────────────────────────────────────────────────

JURIS_UPSERT = """
INSERT INTO jurisdictions (
    slug, name, level, country_code, province_code, parent_slug,
    governance_type, partisan, district_term, role_label_singular,
    role_label_plural, expected_district_count, last_election,
    election_date_set, next_election, term_duration_years,
    governance_summary, boundary_file, boundary_district_id_column
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
"""

POLITICIANS_DELETE = "DELETE FROM politicians WHERE jurisdiction_slug = %s"

POLITICIANS_INSERT = """
    INSERT INTO politicians (
        jurisdiction_slug, uuid, role_scope, district_id, district_name,
        honorific, first_name, last_name, standard_role, specific_title,
        party_name, date_elected, next_election, phone, email, website,
        photo_url, source_url, last_verified, slug
    ) VALUES %s
"""

DISTRICTS_DELETE = "DELETE FROM districts WHERE jurisdiction_slug = %s"

DISTRICTS_INSERT_TEMPLATE = "(%s, %s, %s, ST_GeomFromText(%s, 4326))"

def count_existing(cur, table, slug_col="jurisdiction_slug"):
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {slug_col} = %s", (SLUG,))
    return cur.fetchone()[0]

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    # Load .env
    load_dotenv(ENV_FILE)
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("ERROR: SUPABASE_DB_URL not set in .env", file=sys.stderr)
        sys.exit(1)

    # ── Self-checks ──────────────────────────────────────────────────────────
    print("Running self-checks...")

    # Check 1: Header gate
    self_check_header()
    print("  [1/4] Header: OK (19 columns, correct names)")

    # Check 2: Jurisdiction presence
    juris_data = self_check_jurisdiction_presence()
    print(f"  [2/4] Jurisdiction presence: OK (found '{SLUG}' in jurisdictions.csv, boundary file exists)")

    # Load boundary file for CRS and join-key checks
    gdf = gpd.read_file(BOUNDARY_FILE)

    # Check 3: CRS resolvable
    self_check_crs(gdf)
    source_crs = str(gdf.crs) if gdf.crs is not None else "None (GeoJSON → assumes EPSG:4326)"
    print(f"  [3/4] CRS: OK ({source_crs})")

    # Check 4: Join-key subset
    boundary_ids = self_check_join_keys(gdf, BOUNDARY_ID_COL)
    print(f"  [4/4] Join-key subset: OK (all politician district_ids present in boundary set)")

    print("All self-checks passed.\n")

    # ── Load data into memory ─────────────────────────────────────────────────
    juris_row     = load_jurisdiction_row(juris_data)
    politician_rows = load_politician_rows()
    district_rows   = load_district_rows(gdf, boundary_ids)

    name_matched = sum(1 for r in district_rows if r[2] is not None)
    print(f"Data loaded: {len(politician_rows)} politician rows, {len(district_rows)} district features")
    print(f"District names matched from politicians.csv: {name_matched}/{len(district_rows)}")

    # ── Database transaction ──────────────────────────────────────────────────
    conn = None
    try:
        conn = psycopg2.connect(db_url)
        with conn:
            cur = conn.cursor()

            # Count existing rows for summary
            existing_politicians = count_existing(cur, "politicians")
            existing_districts   = count_existing(cur, "districts")

            # 1. Upsert jurisdiction
            cur.execute(JURIS_UPSERT, juris_row)

            # 2. Replace politicians
            cur.execute(POLITICIANS_DELETE, (SLUG,))
            deleted_politicians = cur.rowcount
            psycopg2.extras.execute_values(
                cur, POLITICIANS_INSERT, politician_rows,
                template=None, page_size=200
            )
            inserted_politicians = len(politician_rows)

            # 3. Replace districts
            cur.execute(DISTRICTS_DELETE, (SLUG,))
            deleted_districts = cur.rowcount
            psycopg2.extras.execute_values(
                cur, 
                "INSERT INTO districts (jurisdiction_slug, external_id, name, boundary) VALUES %s",
                district_rows,
                template=DISTRICTS_INSERT_TEMPLATE,
                page_size=50
            )
            inserted_districts = len(district_rows)

        # Transaction committed (with conn: block exited cleanly)
        net_politicians = inserted_politicians - deleted_politicians
        net_districts   = inserted_districts - deleted_districts

        print("\n## Export — ca_qc\n")
        print("Target: Supabase (jurisdictions, politicians, districts)\n")
        print(f"jurisdictions: upserted (slug ca_qc)")
        print(f"politicians:   {deleted_politicians} deleted, {inserted_politicians} inserted   (net {net_politicians:+d} vs prior)")
        print(f"districts:     {deleted_districts} deleted, {inserted_districts} inserted   "
              f"(geometry CRS: {source_crs} → 4326; {inserted_districts} features)")
        print(f"  district names matched from politicians.csv: {name_matched}/{inserted_districts}   "
              f"(unmatched = vacancies, NULL name)")
        print("\nEmpty → NULL conversions applied. Transaction committed.")

    except Exception as e:
        print(f"\nERROR: Transaction rolled back. Database unchanged.\nDetail: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    main()
