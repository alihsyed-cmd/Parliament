#!/usr/bin/env python3
"""
Export agent — ca_bc_vancouver
Upserts jurisdiction row, deletes+inserts politicians, deletes+inserts districts.
All in one transaction. Reads canonical data; writes only to Supabase.
"""

import csv
import os
import sys
from pathlib import Path

import geopandas as gpd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from shapely.wkt import dumps as wkt_dumps

# ── Configuration ─────────────────────────────────────────────────────────────
SLUG = "ca_bc_vancouver"
REPO_ROOT = Path("/Users/alisyed/Desktop/Parliament")
JURISDICTIONS_CSV = REPO_ROOT / "data" / "jurisdictions.csv"
POLITICIANS_CSV = REPO_ROOT / "data" / SLUG / "politicians.csv"

# Expected politicians.csv header (18 schema columns + slug)
EXPECTED_POLITICIANS_HEADER = [
    "uuid", "role_scope", "district_id", "district_name", "honorific",
    "first_name", "last_name", "standard_role", "specific_title", "party_name",
    "date_elected", "next_election", "phone", "email", "website",
    "photo_url", "source_url", "last_verified", "slug"
]

def or_none(val):
    """Convert empty string to None; leave other values as-is."""
    if val == "" or val is None:
        return None
    return val

def parse_bool(val):
    """Convert 'true'/'false' strings to Python bool; empty to None."""
    if val == "true":
        return True
    if val == "false":
        return False
    return None

def coerce_external_id(val):
    """
    Coerce boundary district-id value to the verbatim string form that matches
    politicians.district_id: integral floats like 1.0 become "1", ints become
    plain strings, otherwise str(value).strip().
    """
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
        return str(val).strip()
    return str(val).strip()

def run_self_checks(jur_row, boundary_file_path):
    """Run all self-checks. Raises ValueError with a descriptive message on failure."""

    # Check 1: politicians.csv header
    with open(POLITICIANS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
    if header != EXPECTED_POLITICIANS_HEADER:
        raise ValueError(
            f"Self-check 1 FAILED — politicians.csv header mismatch.\n"
            f"  Got    ({len(header)} cols): {header}\n"
            f"  Expected ({len(EXPECTED_POLITICIANS_HEADER)} cols): {EXPECTED_POLITICIANS_HEADER}"
        )

    # Check 2: jurisdiction presence and boundary file existence (already confirmed above,
    # but re-verify boundary file on disk)
    if not boundary_file_path.exists():
        raise ValueError(
            f"Self-check 2 FAILED — boundary file not found: {boundary_file_path}"
        )

    # Check 3: CRS resolvable
    gdf = gpd.read_file(boundary_file_path)
    # GeoJSON with no declared CRS → assume EPSG:4326 per RFC 7946 (pass)
    # If CRS is set and not 4326 → reproject (handled at load time, not a failure)
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        pass  # will reproject at load time, not a self-check failure
    # (shapefile with no .prj would be gdf.crs is None for shapefiles, but this is GeoJSON)

    # Build external_id set from boundary
    id_col = jur_row["boundary_district_id_column"]
    boundary_external_ids = set()
    for val in gdf[id_col]:
        boundary_external_ids.add(coerce_external_id(val))

    # Check 4: join-key subset — every district_id on a district-scoped politician
    # must be in the boundary external_id set
    politician_district_ids = set()
    with open(POLITICIANS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["role_scope"] == "district" and row["district_id"]:
                politician_district_ids.add(row["district_id"])

    missing = politician_district_ids - boundary_external_ids
    if missing:
        raise ValueError(
            f"Self-check 4 FAILED — district_id values in politicians.csv not found in "
            f"boundary file's '{id_col}' column: {missing}\n"
            f"  Boundary external_ids: {boundary_external_ids}"
        )

    return gdf, boundary_external_ids

def main():
    # Load credentials
    load_dotenv(REPO_ROOT / ".env")
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        print("REFUSED: SUPABASE_DB_URL not found in .env. Nothing written.")
        sys.exit(1)

    # ── Read jurisdiction row ─────────────────────────────────────────────────
    jur_row = None
    with open(JURISDICTIONS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["slug"] == SLUG:
                jur_row = row
                break
    if jur_row is None:
        print(f"REFUSED: Self-check 2 FAILED — slug '{SLUG}' not found in data/jurisdictions.csv. Nothing written.")
        sys.exit(1)

    boundary_file_path = REPO_ROOT / "data" / SLUG / jur_row["boundary_file"]

    # ── Self-checks ───────────────────────────────────────────────────────────
    try:
        gdf, boundary_external_ids = run_self_checks(jur_row, boundary_file_path)
    except ValueError as e:
        print(f"REFUSED: {e}\nNothing written.")
        sys.exit(1)

    # ── Reproject if needed ───────────────────────────────────────────────────
    source_crs_desc = "EPSG:4326 (GeoJSON assumed)"
    if gdf.crs is None:
        # GeoJSON with no declared CRS → EPSG:4326 per RFC 7946
        gdf = gdf.set_crs(4326)
        source_crs_desc = "None (GeoJSON → assumed EPSG:4326)"
    elif gdf.crs.to_epsg() != 4326:
        source_crs_desc = str(gdf.crs)
        gdf = gdf.to_crs(4326)

    # ── Build district rows ───────────────────────────────────────────────────
    id_col = jur_row["boundary_district_id_column"]

    # Build district_id → district_name map from politicians.csv (district-scoped rows)
    district_name_map = {}
    with open(POLITICIANS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["role_scope"] == "district" and row["district_id"] and row["district_name"]:
                did = row["district_id"]
                if did not in district_name_map:
                    district_name_map[did] = row["district_name"]

    district_rows = []
    for _, feature in gdf.iterrows():
        ext_id = coerce_external_id(feature[id_col])
        name = district_name_map.get(ext_id, None)
        geom_wkt = wkt_dumps(feature.geometry)
        district_rows.append((SLUG, ext_id, name, geom_wkt))

    names_matched = sum(1 for _, ext_id, name, _ in district_rows if name is not None)

    # ── Read politicians ──────────────────────────────────────────────────────
    politician_rows = []
    with open(POLITICIANS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            politician_rows.append((
                SLUG,                          # jurisdiction_slug (from context)
                row["uuid"],
                row["role_scope"],
                or_none(row["district_id"]),
                or_none(row["district_name"]),
                or_none(row["honorific"]),
                row["first_name"],
                row["last_name"],
                row["standard_role"],
                row["specific_title"],
                or_none(row["party_name"]),
                or_none(row["date_elected"]),
                or_none(row["next_election"]),
                or_none(row["phone"]),
                or_none(row["email"]),
                or_none(row["website"]),
                or_none(row["photo_url"]),
                or_none(row["source_url"]),
                or_none(row["last_verified"]),
                row["slug"],                   # per-person URL key → politicians.slug
            ))

    # ── Build jurisdiction upsert values ──────────────────────────────────────
    j = jur_row
    jur_values = (
        j["slug"],
        j["name"],
        j["level"],
        j["country_code"],
        or_none(j["province_code"]),
        or_none(j["parent_slug"]),
        j["governance_type"],
        parse_bool(j["partisan"]),
        or_none(j["district_term"]),
        or_none(j["role_label_singular"]),
        or_none(j["role_label_plural"]),
        int(j["expected_district_count"]) if j["expected_district_count"] else None,
        or_none(j["last_election"]),
        parse_bool(j["election_date_set"]),
        or_none(j["next_election"]),
        int(j["term_duration_years"]) if j["term_duration_years"] else None,
        or_none(j["governance_summary"]),
        or_none(j["boundary_file"]),
        or_none(j["boundary_district_id_column"]),
    )

    # ── Execute transaction ───────────────────────────────────────────────────
    conn = None
    try:
        conn = psycopg2.connect(db_url)
        with conn:
            with conn.cursor() as cur:
                # 1. Upsert jurisdiction
                cur.execute("""
                    INSERT INTO jurisdictions (
                        slug, name, level, country_code, province_code, parent_slug,
                        governance_type, partisan, district_term,
                        role_label_singular, role_label_plural,
                        expected_district_count, last_election, election_date_set,
                        next_election, term_duration_years, governance_summary,
                        boundary_file, boundary_district_id_column
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s
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
                """, jur_values)

                # 2. Count existing politicians before delete
                cur.execute("SELECT COUNT(*) FROM politicians WHERE jurisdiction_slug = %s", (SLUG,))
                prior_politician_count = cur.fetchone()[0]

                # Delete politicians
                cur.execute("DELETE FROM politicians WHERE jurisdiction_slug = %s", (SLUG,))
                deleted_politicians = cur.rowcount

                # Insert politicians (20 columns: jurisdiction_slug + 18 schema + slug)
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO politicians (
                        jurisdiction_slug, uuid, role_scope,
                        district_id, district_name, honorific,
                        first_name, last_name, standard_role, specific_title,
                        party_name, date_elected, next_election,
                        phone, email, website, photo_url, source_url,
                        last_verified, slug
                    ) VALUES %s
                    """,
                    politician_rows,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                )
                inserted_politicians = len(politician_rows)

                # 3. Count existing districts before delete
                cur.execute("SELECT COUNT(*) FROM districts WHERE jurisdiction_slug = %s", (SLUG,))
                prior_district_count = cur.fetchone()[0]

                # Delete districts
                cur.execute("DELETE FROM districts WHERE jurisdiction_slug = %s", (SLUG,))
                deleted_districts = cur.rowcount

                # Insert districts
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO districts (jurisdiction_slug, external_id, name, boundary)
                    VALUES %s
                    """,
                    district_rows,
                    template="(%s, %s, %s, ST_GeomFromText(%s, 4326))"
                )
                inserted_districts = len(district_rows)

        # Transaction committed (with conn: block exited cleanly)
        net_politicians = inserted_politicians - prior_politician_count
        net_districts = inserted_districts - prior_district_count

        print(f"## Export — {SLUG}")
        print()
        print(f"Target: Supabase (jurisdictions, politicians, districts)")
        print()
        print(f"jurisdictions: upserted (slug {SLUG})")
        print(f"politicians:   {deleted_politicians} deleted, {inserted_politicians} inserted   (net {net_politicians:+d} vs prior)")
        print(f"districts:     {deleted_districts} deleted, {inserted_districts} inserted   (geometry CRS: {source_crs_desc}; {inserted_districts} features)")
        print(f"  district names matched from politicians.csv: {names_matched}/{inserted_districts}   (unmatched = vacancies, NULL name)")
        print()
        print("Empty → NULL conversions applied. Transaction committed.")

    except Exception as e:
        print(f"ERROR — transaction rolled back. Database unchanged.")
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    main()
