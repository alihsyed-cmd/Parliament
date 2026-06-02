#!/usr/bin/env python3
"""
Export script: ca_on_greater_sudbury → Supabase
Upserts jurisdiction, delete-then-inserts politicians and districts,
all in one transaction.
"""

import csv
import os
import sys
import math

import geopandas as gpd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

SLUG = "ca_on_greater_sudbury"
REPO_ROOT = "/Users/alisyed/Desktop/Parliament"
DATA_DIR = os.path.join(REPO_ROOT, "data")
JURIS_CSV = os.path.join(DATA_DIR, "jurisdictions.csv")
POLITICIANS_CSV = os.path.join(DATA_DIR, SLUG, "politicians.csv")

# The 18 canonical politicians columns + slug (19th)
EXPECTED_POLITICIANS_HEADER = [
    "uuid", "role_scope", "district_id", "district_name",
    "honorific", "first_name", "last_name", "standard_role",
    "specific_title", "party_name", "date_elected", "next_election",
    "phone", "email", "website", "photo_url", "source_url",
    "last_verified", "slug"
]

# The 19 jurisdictions columns (matching schema)
JURIS_COLUMNS = [
    "slug", "name", "level", "country_code", "province_code",
    "parent_slug", "governance_type", "partisan", "district_term",
    "role_label_singular", "role_label_plural", "expected_district_count",
    "last_election", "election_date_set", "next_election",
    "term_duration_years", "governance_summary", "boundary_file",
    "boundary_district_id_column"
]

BOOLEAN_JURIS_COLS = {"partisan", "election_date_set"}
INTEGER_JURIS_COLS = {"expected_district_count", "term_duration_years"}


def empty_to_none(val):
    """Convert empty string to None."""
    if val == "" or val is None:
        return None
    return val


def coerce_juris_value(col, val):
    """Apply type coercions to jurisdiction row values."""
    val = empty_to_none(val)
    if val is None:
        return None
    if col in BOOLEAN_JURIS_COLS:
        if val.lower() == "true":
            return True
        elif val.lower() == "false":
            return False
        return None
    if col in INTEGER_JURIS_COLS:
        return int(val)
    return val


def coerce_external_id(raw_val):
    """
    Coerce boundary WardNumber float64 → verbatim politician-matching string.
    1.0 → "1", 12.0 → "12", NaN → None (Mayor/city-wide polygon).
    """
    if raw_val is None:
        return None
    try:
        f = float(raw_val)
    except (ValueError, TypeError):
        return str(raw_val).strip()
    if math.isnan(f):
        return None
    # integral float → plain integer string
    if f == int(f):
        return str(int(f))
    return str(f)


def normalize_politician_district_id(did_str):
    """
    Normalize politician district_id from CSV to match boundary external_id.
    "1.0" → "1", "12.0" → "12", plain "1" → "1", None → None.
    Handles both plain integers and float-string forms stored in the CSV.
    """
    if did_str is None or did_str == "":
        return None
    # Try parsing as float to detect integral-float strings like "1.0"
    try:
        f = float(did_str)
        if not math.isnan(f) and f == int(f):
            return str(int(f))
    except (ValueError, TypeError):
        pass
    return did_str.strip()


# ── Self-checks ───────────────────────────────────────────────────────────────

def check_politicians_header():
    """Self-check 1: header gate."""
    with open(POLITICIANS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
    if header != EXPECTED_POLITICIANS_HEADER:
        raise ValueError(
            f"Self-check 1 FAILED: politicians.csv header mismatch.\n"
            f"  Expected: {EXPECTED_POLITICIANS_HEADER}\n"
            f"  Got:      {header}"
        )
    print("Self-check 1 PASSED: politicians.csv header is correct (19 columns).")


def check_jurisdiction_presence():
    """Self-check 2: jurisdiction row + boundary file presence."""
    juris_row = None
    with open(JURIS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["slug"] == SLUG:
                if juris_row is not None:
                    raise ValueError(
                        f"Self-check 2 FAILED: multiple rows for slug '{SLUG}' in jurisdictions.csv"
                    )
                juris_row = row
    if juris_row is None:
        raise ValueError(
            f"Self-check 2 FAILED: no row for slug '{SLUG}' in jurisdictions.csv"
        )
    boundary_file = juris_row["boundary_file"]
    boundary_path = os.path.join(DATA_DIR, SLUG, boundary_file)
    if not os.path.exists(boundary_path):
        raise ValueError(
            f"Self-check 2 FAILED: boundary_file '{boundary_file}' not found at {boundary_path}"
        )
    print(f"Self-check 2 PASSED: jurisdiction row found, boundary_file '{boundary_file}' exists.")
    return juris_row


def check_crs(gdf, boundary_path):
    """Self-check 3: CRS resolvable."""
    ext = os.path.splitext(boundary_path)[1].lower()
    if gdf.crs is None:
        if ext in (".geojson", ".json"):
            # RFC 7946: assume EPSG:4326
            print("Self-check 3 PASSED: GeoJSON with no declared CRS — assuming EPSG:4326.")
            return gdf.set_crs(4326)
        else:
            raise ValueError(
                "Self-check 3 FAILED: shapefile has no .prj — CRS cannot be determined safely."
            )
    if gdf.crs.to_epsg() != 4326:
        source_crs = str(gdf.crs)
        print(f"Self-check 3: CRS is {source_crs} — reprojecting to EPSG:4326.")
        gdf = gdf.to_crs(4326)
        return gdf, source_crs
    print(f"Self-check 3 PASSED: CRS is already EPSG:4326.")
    return gdf


def check_join_keys(gdf, boundary_id_col, politicians_rows):
    """
    Self-check 4: every district-scoped politician district_id (normalized)
    is a member of the boundary's external_id set.
    """
    # Build set of external_ids from boundary (already normalized)
    external_ids = set()
    for _, feat in gdf.iterrows():
        eid = coerce_external_id(feat[boundary_id_col])
        if eid is not None:
            external_ids.add(eid)

    missing = []
    for row in politicians_rows:
        if row["role_scope"] == "district":
            raw_did = empty_to_none(row["district_id"])
            if raw_did is not None:
                normalized = normalize_politician_district_id(raw_did)
                if normalized not in external_ids:
                    missing.append(raw_did)

    if missing:
        raise ValueError(
            f"Self-check 4 FAILED: district_id values in politicians.csv not found in boundary "
            f"external_ids (after normalization): {missing}\n"
            f"  Boundary external_ids: {sorted(external_ids)}"
        )
    print(
        f"Self-check 4 PASSED: all district-scoped politician district_ids match boundary "
        f"({len(external_ids)} boundary districts)."
    )
    return external_ids


# ── Main export ───────────────────────────────────────────────────────────────

def main():
    load_dotenv(os.path.join(REPO_ROOT, ".env"))
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("ERROR: SUPABASE_DB_URL not found in .env")
        sys.exit(1)

    # --- Self-check 1: header gate ---
    check_politicians_header()

    # --- Self-check 2: jurisdiction presence ---
    juris_row = check_jurisdiction_presence()
    boundary_file = juris_row["boundary_file"]
    boundary_id_col = juris_row["boundary_district_id_column"]
    boundary_path = os.path.join(DATA_DIR, SLUG, boundary_file)

    # --- Load politicians CSV ---
    politicians_rows = []
    with open(POLITICIANS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            politicians_rows.append(row)

    # --- Load boundary file ---
    gdf = gpd.read_file(boundary_path)

    # --- Self-check 3: CRS ---
    source_crs = "EPSG:4326"
    result = check_crs(gdf, boundary_path)
    if isinstance(result, tuple):
        gdf, source_crs = result
    else:
        gdf = result

    # --- Self-check 4: join keys ---
    external_ids = check_join_keys(gdf, boundary_id_col, politicians_rows)

    # --- Build name lookup: normalized_district_id → district_name ---
    district_name_map = {}
    for row in politicians_rows:
        if row["role_scope"] == "district":
            raw_did = empty_to_none(row["district_id"])
            dname = empty_to_none(row["district_name"])
            if raw_did is not None and dname is not None:
                normalized = normalize_politician_district_id(raw_did)
                if normalized not in district_name_map:
                    district_name_map[normalized] = dname

    # --- Prepare jurisdiction upsert values ---
    juris_values = []
    for col in JURIS_COLUMNS:
        juris_values.append(coerce_juris_value(col, juris_row.get(col, "")))

    # --- Prepare politician insert rows ---
    # Normalize district_id to match boundary external_id (plain integer string)
    politician_insert_rows = []
    for row in politicians_rows:
        raw_did = empty_to_none(row["district_id"])
        normalized_did = normalize_politician_district_id(raw_did) if raw_did is not None else None

        pol_row = (
            SLUG,                                              # jurisdiction_slug
            empty_to_none(row["uuid"]),                       # uuid
            empty_to_none(row["role_scope"]),                 # role_scope
            normalized_did,                                   # district_id (normalized)
            empty_to_none(row["district_name"]),              # district_name
            empty_to_none(row["honorific"]),                  # honorific
            empty_to_none(row["first_name"]),                 # first_name
            empty_to_none(row["last_name"]),                  # last_name
            empty_to_none(row["standard_role"]),              # standard_role
            empty_to_none(row["specific_title"]),             # specific_title
            empty_to_none(row["party_name"]),                 # party_name
            empty_to_none(row["date_elected"]),               # date_elected
            empty_to_none(row["next_election"]),              # next_election
            empty_to_none(row["phone"]),                      # phone
            empty_to_none(row["email"]),                      # email
            empty_to_none(row["website"]),                    # website
            empty_to_none(row["photo_url"]),                  # photo_url
            empty_to_none(row["source_url"]),                 # source_url
            empty_to_none(row["last_verified"]),              # last_verified
            empty_to_none(row["slug"]),                       # slug (per-person URL key)
        )
        politician_insert_rows.append(pol_row)

    # --- Prepare district insert rows ---
    district_insert_rows = []
    names_matched = 0
    for _, feat in gdf.iterrows():
        raw_val = feat[boundary_id_col]
        eid = coerce_external_id(raw_val)
        if eid is None:
            # Mayor/city-wide polygon (WardNumber=NaN): use "mayor" as external_id, NULL name
            eid_db = "mayor"
            dname = None
        else:
            eid_db = eid
            dname = district_name_map.get(eid, None)
            if dname is not None:
                names_matched += 1
        wkt = feat.geometry.wkt
        district_insert_rows.append((SLUG, eid_db, dname, wkt))

    total_features = len(district_insert_rows)

    # --- Connect and run transaction ---
    conn = None
    try:
        conn = psycopg2.connect(db_url)

        # Count prior rows for reporting
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM politicians WHERE jurisdiction_slug = %s", (SLUG,))
            prior_politicians = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM districts WHERE jurisdiction_slug = %s", (SLUG,))
            prior_districts = cur.fetchone()[0]

        with conn:  # transaction: commits on success, rolls back on exception
            with conn.cursor() as cur:

                # 1. Upsert jurisdiction
                non_key_cols = JURIS_COLUMNS[1:]  # everything except slug
                set_clause = ", ".join(f"{col} = EXCLUDED.{col}" for col in non_key_cols)
                upsert_sql = (
                    f"INSERT INTO jurisdictions ({', '.join(JURIS_COLUMNS)}) "
                    f"VALUES ({', '.join(['%s'] * len(JURIS_COLUMNS))}) "
                    f"ON CONFLICT (slug) DO UPDATE SET {set_clause}"
                )
                cur.execute(upsert_sql, juris_values)
                print(f"Jurisdiction upserted: {SLUG}")

                # 2. Delete + insert politicians
                cur.execute("DELETE FROM politicians WHERE jurisdiction_slug = %s", (SLUG,))
                deleted_politicians = cur.rowcount
                print(f"Deleted {deleted_politicians} prior politician rows.")

                politician_sql = (
                    "INSERT INTO politicians ("
                    "jurisdiction_slug, uuid, role_scope, district_id, district_name, "
                    "honorific, first_name, last_name, standard_role, specific_title, "
                    "party_name, date_elected, next_election, phone, email, website, "
                    "photo_url, source_url, last_verified, slug"
                    ") VALUES %s"
                )
                execute_values(cur, politician_sql, politician_insert_rows)
                print(f"Inserted {len(politician_insert_rows)} politician rows.")

                # 3. Delete + insert districts
                cur.execute("DELETE FROM districts WHERE jurisdiction_slug = %s", (SLUG,))
                deleted_districts = cur.rowcount
                print(f"Deleted {deleted_districts} prior district rows.")

                execute_values(
                    cur,
                    "INSERT INTO districts (jurisdiction_slug, external_id, name, boundary) VALUES %s",
                    district_insert_rows,
                    template="(%s, %s, %s, ST_GeomFromText(%s, 4326))"
                )
                print(f"Inserted {total_features} district rows.")

        # Report
        net_politicians = len(politician_insert_rows) - prior_politicians
        net_districts = total_features - prior_districts
        net_p_str = f"+{net_politicians}" if net_politicians >= 0 else str(net_politicians)
        net_d_str = f"+{net_districts}" if net_districts >= 0 else str(net_districts)

        print("\n" + "=" * 60)
        print(f"## Export — {SLUG}")
        print()
        print(f"Target: Supabase (jurisdictions, politicians, districts)")
        print()
        print(f"jurisdictions: upserted (slug {SLUG})")
        print(f"politicians:   {deleted_politicians} deleted, {len(politician_insert_rows)} inserted   (net {net_p_str} vs prior)")
        print(f"districts:     {deleted_districts} deleted, {total_features} inserted   (geometry CRS: {source_crs} → 4326; {total_features} features)")
        print(f"  district names matched from politicians.csv: {names_matched}/{total_features}   "
              f"(unmatched = vacancies or Mayor city-wide polygon, NULL name)")
        print()
        print(f"Empty → NULL conversions applied. Transaction committed.")

    except Exception as e:
        print(f"\nERROR during export: {e}")
        print("Transaction rolled back. Database unchanged.")
        sys.exit(1)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
