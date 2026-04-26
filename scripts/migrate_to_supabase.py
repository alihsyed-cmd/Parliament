"""
One-time migration script: populate Supabase from in-memory adapter data.

Reuses existing adapter loading logic to read source files (shapefiles, CSVs,
XML), then inserts the data into the four-table Supabase schema.

The script is idempotent — running it again deletes existing data for each
jurisdiction and re-inserts. Safe to re-run during development.

Usage:
    python3 scripts/migrate_to_supabase.py
"""

import json
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json
from shapely.geometry import mapping
from shapely import wkt

# Load environment and import project modules
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from registry import JurisdictionRegistry


def make_jsonb(value, lang="en"):
    """Wrap a string in a {lang: value} jsonb structure for translatable fields."""
    if value is None or value == "":
        return None
    return Json({lang: str(value), "fr": str(value)})  # Same value in both for now


def migrate_jurisdiction(cur, adapter, slug):
    """Migrate a single jurisdiction's data into Supabase."""
    print(f"\n=== Migrating {adapter.name} ({slug}) ===")

    # Determine country/province from slug (ca_federal, ca_on, ca_on_toronto)
    parts = slug.split("_")
    country_code = parts[0].upper()
    province_code = parts[1].upper() if len(parts) > 1 and adapter.level != "federal" else None

    # ── Step 1: Delete existing rows for this jurisdiction (idempotency) ──
    cur.execute("DELETE FROM jurisdictions WHERE slug = %s;", (slug,))
    deleted = cur.rowcount
    if deleted:
        print(f"  Cleared {deleted} existing jurisdiction row (cascade deletes its data)")

    # ── Step 2: Insert the jurisdiction row ──
    cur.execute(
        """
        INSERT INTO jurisdictions (slug, name, level, country_code, province_code)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
        """,
        (slug, make_jsonb(adapter.name), adapter.level, country_code, province_code),
    )
    jurisdiction_id = cur.fetchone()[0]
    print(f"  Inserted jurisdiction: {jurisdiction_id}")

    # ── Step 3: Insert districts with PostGIS geometry ──
    boundary_field = adapter.district_field
    district_id_map = {}  # Maps join_key (riding name or ward number) -> district UUID

    rows_inserted = 0
    for _, row in adapter.boundaries.iterrows():
        district_value = row[boundary_field]
        if district_value is None:
            continue

        join_key = adapter._normalize_join_key(district_value)
        if join_key is None:
            continue

        # Skip duplicates (some shapefiles have multiple polygons per district)
        if join_key in district_id_map:
            continue

        # Convert shapely geometry to WKT for PostGIS
        geom_wkt = row.geometry.wkt

        cur.execute(
            """
            INSERT INTO districts (jurisdiction_id, external_id, name, boundary)
            VALUES (%s, %s, %s, ST_GeomFromText(%s, 4326))
            RETURNING id;
            """,
            (
                jurisdiction_id,
                str(join_key),
                make_jsonb(str(district_value)),
                geom_wkt,
            ),
        )
        district_id_map[join_key] = cur.fetchone()[0]
        rows_inserted += 1

    print(f"  Inserted {rows_inserted} districts")

    # ── Step 4: Insert representatives + representations ──
    role_label = adapter.config.get("output_role_label", "representative")
    role_label_formatted = role_label.upper() if len(role_label) <= 3 else role_label.capitalize()

    reps_inserted = 0
    representations_inserted = 0

    for join_key, rep_data in adapter.representatives.items():
        # Build the full name from honorific + first + last
        full_name = adapter._build_full_name(rep_data) or ""
        if not full_name:
            continue

        # External IDs (federal has person_id from ourcommons.ca)
        external_ids = {}
        if "person_id" in rep_data and rep_data["person_id"]:
            external_ids["parl_gc_ca"] = rep_data["person_id"]

        # Insert the representative
        cur.execute(
            """
            INSERT INTO representatives
                (name, party, email, phone, photo_url, website_url, external_ids)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                make_jsonb(full_name),
                make_jsonb(rep_data.get("party")),
                rep_data.get("email") or None,
                rep_data.get("phone") or None,
                rep_data.get("photo_url") or None,
                make_jsonb(rep_data.get("website")) if rep_data.get("website") else None,
                Json(external_ids),
            ),
        )
        rep_id = cur.fetchone()[0]
        reps_inserted += 1

        # Insert the representation linking rep to district
        district_id = district_id_map.get(join_key)
        if district_id is None:
            # Rep exists but no matching district — skip the representation
            continue

        # Parse elected date if present (federal data has it)
        start_date = rep_data.get("elected") or None

        cur.execute(
            """
            INSERT INTO representations
                (representative_id, district_id, role, start_date)
            VALUES (%s, %s, %s, %s);
            """,
            (
                rep_id,
                district_id,
                make_jsonb(role_label_formatted),
                start_date,
            ),
        )
        representations_inserted += 1

    print(f"  Inserted {reps_inserted} representatives")
    print(f"  Inserted {representations_inserted} representations")

    return {
        "jurisdiction_id": jurisdiction_id,
        "districts": rows_inserted,
        "representatives": reps_inserted,
        "representations": representations_inserted,
    }


def main():
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        print("ERROR: SUPABASE_DB_URL not set in .env")
        sys.exit(1)

    print("Loading registry...")
    registry = JurisdictionRegistry()
    print(f"Loaded {len(registry.adapters)} adapters\n")

    print("Connecting to Supabase...")
    conn = psycopg2.connect(db_url)
    conn.autocommit = False  # Wrap migration in a transaction
    cur = conn.cursor()

    try:
        # Map adapter to its slug (we need to find the config that was used)
        config_dir = Path(os.getenv("JURISDICTIONS_CONFIG_DIR"))
        adapter_slugs = {}
        for config_file in sorted(config_dir.glob("*.json")):
            with open(config_file) as f:
                config = json.load(f)
            slug = config_file.stem  # filename without .json
            adapter_slugs[config["name"]] = slug

        # Migrate each adapter
        results = []
        for adapter in registry.adapters:
            slug = adapter_slugs.get(adapter.name)
            if not slug:
                print(f"WARNING: No slug found for {adapter.name}, skipping")
                continue
            result = migrate_jurisdiction(cur, adapter, slug)
            results.append((adapter.name, result))

        conn.commit()
        print("\n" + "=" * 60)
        print("Migration complete. Summary:")
        for name, r in results:
            print(f"  {name}: {r['districts']} districts, {r['representatives']} reps, {r['representations']} representations")
        print("=" * 60)

    except Exception as e:
        conn.rollback()
        print(f"\nFAILED: {type(e).__name__}: {e}")
        print("Transaction rolled back. Database unchanged.")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
