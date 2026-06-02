"""
Export script for jurisdiction: ca_bc
Reads canonical data and upserts/delete-then-inserts into Supabase.
One transaction: jurisdictions (upsert) -> politicians (delete+insert) -> districts (delete+insert).
"""

import csv
import os
import sys

import geopandas as gpd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# ── Constants ────────────────────────────────────────────────────────────────
SLUG = "ca_bc"
BASE_DIR = "/Users/alisyed/Desktop/Parliament"
DATA_DIR = f"{BASE_DIR}/data"
JURISDICTIONS_CSV = f"{DATA_DIR}/jurisdictions.csv"
POLITICIANS_CSV   = f"{DATA_DIR}/{SLUG}/politicians.csv"
ENV_FILE          = f"{BASE_DIR}/.env"

EXPECTED_POLITICIANS_HEADER = [
    "uuid", "role_scope", "district_id", "district_name", "honorific",
    "first_name", "last_name", "standard_role", "specific_title", "party_name",
    "date_elected", "next_election", "phone", "email", "website",
    "photo_url", "source_url", "last_verified", "slug",
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def or_none(val):
    """Convert empty string to None; leave all other values unchanged."""
    if val == "" or val is None:
        return None
    return val

def bool_or_none(val):
    """Convert 'true'/'false' strings to Python bool; empty -> None."""
    if val == "true":
        return True
    if val == "false":
        return False
    return None

def coerce_external_id(raw):
    """
    Coerce a boundary file district-id value to the verbatim string form
    that matches politicians.district_id.
    Integral floats (1.0) -> "1"; ints -> plain string; else str(x).strip().
    """
    if isinstance(raw, float):
        if raw == int(raw):
            return str(int(raw))
        return str(raw).strip()
    return str(raw).strip()


# ── Self-checks ──────────────────────────────────────────────────────────────

def self_check_header():
    """Check 1: politicians.csv header is exactly the expected 19 columns."""
    with open(POLITICIANS_CSV, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
    if header != EXPECTED_POLITICIANS_HEADER:
        raise ValueError(
            f"REFUSED (check 1): politicians.csv header mismatch.\n"
            f"  Got ({len(header)} cols):      {header}\n"
            f"  Expected ({len(EXPECTED_POLITICIANS_HEADER)} cols): {EXPECTED_POLITICIANS_HEADER}"
        )
    print(f"[check 1] Header OK: {len(header)} columns, correct names and order.")


def self_check_jurisdiction():
    """Check 2: jurisdictions.csv has exactly one row for SLUG; boundary file exists."""
    rows = []
    with open(JURISDICTIONS_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["slug"] == SLUG:
                rows.append(row)
    if len(rows) != 1:
        raise ValueError(
            f"REFUSED (check 2): expected exactly 1 row for slug '{SLUG}' in "
            f"jurisdictions.csv; found {len(rows)}."
        )
    jrow = rows[0]
    boundary_path = f"{DATA_DIR}/{SLUG}/{jrow['boundary_file']}"
    if not os.path.exists(boundary_path):
        raise ValueError(
            f"REFUSED (check 2): boundary_file '{jrow['boundary_file']}' listed in "
            f"jurisdictions.csv does not exist at {boundary_path}."
        )
    print(f"[check 2] Jurisdiction row found; boundary file exists at {boundary_path}.")
    return jrow


def self_check_crs(gdf, boundary_path):
    """
    Check 3: CRS must be present and resolvable.
    GeoJSON with no declared CRS -> assume 4326 (RFC 7946).
    Any other CRS -> reproject to 4326.
    Shapefile with no .prj -> refused.
    Returns gdf (reprojected if needed) and a crs_label string.
    """
    is_shapefile = boundary_path.lower().endswith(".shp")
    if gdf.crs is None:
        if is_shapefile:
            raise ValueError(
                "REFUSED (check 3): shapefile has no .prj file; projection cannot be "
                "safely determined. Regenerate the boundary file before exporting."
            )
        # GeoJSON with no CRS -> RFC 7946 EPSG:4326
        gdf = gdf.set_crs(4326)
        crs_label = "GeoJSON (no declared CRS, assumed EPSG:4326)"
        print(f"[check 3] No CRS declared (GeoJSON); assuming EPSG:4326 per RFC 7946.")
    else:
        crs_label = gdf.crs.to_string()
        if gdf.crs.to_epsg() != 4326:
            print(f"[check 3] CRS is {crs_label}; reprojecting to EPSG:4326.")
            gdf = gdf.to_crs(4326)
            crs_label = f"{crs_label} -> EPSG:4326"
        else:
            print(f"[check 3] CRS is already EPSG:4326.")
            crs_label = "EPSG:4326"
    return gdf, crs_label


def self_check_join_keys(gdf, id_column):
    """
    Check 4: every district_id on a 'district' role_scope politician row
    must appear in the boundary's external_id set.
    """
    boundary_ids = set(
        coerce_external_id(feat) for feat in gdf[id_column]
    )

    politician_district_ids = set()
    with open(POLITICIANS_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["role_scope"] == "district" and row["district_id"]:
                politician_district_ids.add(row["district_id"])

    missing = politician_district_ids - boundary_ids
    if missing:
        raise ValueError(
            f"REFUSED (check 4): {len(missing)} politician district_id(s) have no "
            f"matching boundary feature. Missing: {sorted(missing)}"
        )
    print(
        f"[check 4] Join-key subset OK: {len(politician_district_ids)} politician "
        f"district_ids all present in {len(boundary_ids)} boundary features."
    )
    return boundary_ids


# ── Data loaders ─────────────────────────────────────────────────────────────

def load_jurisdiction_row():
    """Return the single jurisdiction dict for SLUG from jurisdictions.csv."""
    with open(JURISDICTIONS_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["slug"] == SLUG:
                return row
    raise RuntimeError(f"Jurisdiction row for '{SLUG}' not found (should have been caught in check 2).")


def load_politicians():
    """Return list of 20-tuples for bulk insert, mapping CSV columns to DB columns."""
    rows = []
    with open(POLITICIANS_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append((
                SLUG,                          # jurisdiction_slug (from context)
                or_none(r["uuid"]),            # uuid
                or_none(r["role_scope"]),      # role_scope
                or_none(r["district_id"]),     # district_id
                or_none(r["district_name"]),   # district_name
                or_none(r["honorific"]),       # honorific
                or_none(r["first_name"]),      # first_name
                or_none(r["last_name"]),       # last_name
                or_none(r["standard_role"]),   # standard_role
                or_none(r["specific_title"]),  # specific_title
                or_none(r["party_name"]),      # party_name
                or_none(r["date_elected"]),    # date_elected
                or_none(r["next_election"]),   # next_election
                or_none(r["phone"]),           # phone
                or_none(r["email"]),           # email
                or_none(r["website"]),         # website
                or_none(r["photo_url"]),       # photo_url
                or_none(r["source_url"]),      # source_url
                or_none(r["last_verified"]),   # last_verified
                or_none(r["slug"]),            # slug (per-person URL key)
            ))
    return rows


def load_districts(gdf, id_column):
    """
    Return list of 4-tuples (jurisdiction_slug, external_id, name, wkt)
    for bulk insert. Builds district_id -> name map from politicians.csv.
    """
    # Build name map from politicians.csv
    name_map = {}
    with open(POLITICIANS_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r["role_scope"] == "district" and r["district_id"] and r["district_name"]:
                did = r["district_id"]
                if did not in name_map:
                    name_map[did] = r["district_name"]

    districts = []
    for _, row in gdf.iterrows():
        ext_id = coerce_external_id(row[id_column])
        name   = name_map.get(ext_id)  # None if no politician row names this district
        wkt    = row.geometry.wkt
        districts.append((SLUG, ext_id, name, wkt))
    return districts


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    load_dotenv(ENV_FILE)
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        print("REFUSED: SUPABASE_DB_URL not found in .env. Nothing written.")
        sys.exit(1)

    # ── Self-checks ──────────────────────────────────────────────────────────
    print("Running self-checks...")
    self_check_header()
    jrow = self_check_jurisdiction()

    boundary_path = f"{DATA_DIR}/{SLUG}/{jrow['boundary_file']}"
    id_column = jrow["boundary_district_id_column"]

    gdf = gpd.read_file(boundary_path)
    gdf, crs_label = self_check_crs(gdf, boundary_path)
    boundary_ids = self_check_join_keys(gdf, id_column)

    print(f"All self-checks passed. Proceeding with export.")
    print(f"  Boundary: {len(gdf)} features | CRS: {crs_label}")

    # ── Load data ─────────────────────────────────────────────────────────────
    politicians = load_politicians()
    districts   = load_districts(gdf, id_column)
    names_matched = sum(1 for _, _, name, _ in districts if name is not None)

    # ── Build jurisdiction upsert values ──────────────────────────────────────
    j = jrow
    juris_values = (
        or_none(j["slug"]),
        or_none(j["name"]),
        or_none(j["level"]),
        or_none(j["country_code"]),
        or_none(j["province_code"]),
        or_none(j["parent_slug"]),
        or_none(j["governance_type"]),
        bool_or_none(j["partisan"]),
        or_none(j["district_term"]),
        or_none(j["role_label_singular"]),
        or_none(j["role_label_plural"]),
        or_none(j["expected_district_count"]) and int(j["expected_district_count"]),
        or_none(j["last_election"]),
        bool_or_none(j["election_date_set"]),
        or_none(j["next_election"]),
        or_none(j["term_duration_years"]) and int(j["term_duration_years"]),
        or_none(j["governance_summary"]),
        or_none(j["boundary_file"]),
        or_none(j["boundary_district_id_column"]),
    )

    # ── Transaction ───────────────────────────────────────────────────────────
    conn = None
    prior_politicians = 0
    prior_districts   = 0

    try:
        conn = psycopg2.connect(db_url)
        with conn:
            cur = conn.cursor()

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
            print("Step 1: jurisdiction row upserted.")

            # 2. Replace politicians
            cur.execute(
                "SELECT COUNT(*) FROM politicians WHERE jurisdiction_slug = %s",
                (SLUG,)
            )
            prior_politicians = cur.fetchone()[0]

            cur.execute(
                "DELETE FROM politicians WHERE jurisdiction_slug = %s",
                (SLUG,)
            )
            execute_values(
                cur,
                """
                INSERT INTO politicians (
                    jurisdiction_slug, uuid, role_scope, district_id, district_name,
                    honorific, first_name, last_name, standard_role, specific_title,
                    party_name, date_elected, next_election, phone, email,
                    website, photo_url, source_url, last_verified, slug
                ) VALUES %s
                """,
                politicians,
            )
            print(f"Step 2: {prior_politicians} politicians deleted, {len(politicians)} inserted.")

            # 3. Replace districts
            cur.execute(
                "SELECT COUNT(*) FROM districts WHERE jurisdiction_slug = %s",
                (SLUG,)
            )
            prior_districts = cur.fetchone()[0]

            cur.execute(
                "DELETE FROM districts WHERE jurisdiction_slug = %s",
                (SLUG,)
            )
            execute_values(
                cur,
                """
                INSERT INTO districts (jurisdiction_slug, external_id, name, boundary)
                VALUES %s
                """,
                [
                    (SLUG, ext_id, name, wkt)
                    for (_, ext_id, name, wkt) in districts
                ],
                template="(%s, %s, %s, ST_GeomFromText(%s, 4326))",
            )
            print(f"Step 3: {prior_districts} districts deleted, {len(districts)} inserted.")

        # conn.__exit__ committed the transaction
        print("Transaction committed.")

        # ── Summary ───────────────────────────────────────────────────────────
        net_politicians = len(politicians) - prior_politicians
        net_districts   = len(districts) - prior_districts

        print("\n" + "=" * 60)
        print(f"## Export — {SLUG}")
        print()
        print(f"Target: Supabase (jurisdictions, politicians, districts)")
        print()
        print(f"jurisdictions: upserted (slug {SLUG})")
        print(f"politicians:   {prior_politicians} deleted, {len(politicians)} inserted   "
              f"(net {net_politicians:+d} vs prior)")
        print(f"districts:     {prior_districts} deleted, {len(districts)} inserted   "
              f"(geometry CRS: {crs_label}; {len(districts)} features)")
        print(f"  district names matched from politicians.csv: "
              f"{names_matched}/{len(districts)}   (unmatched = vacancies, NULL name)")
        print()
        print("Empty -> NULL conversions applied. Transaction committed.")
        print("=" * 60)

    except Exception as e:
        print(f"\nERROR: {e}")
        print("Transaction rolled back. Database is unchanged.")
        sys.exit(1)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
