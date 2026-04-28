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

from typing import Any, Dict, List

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json
from shapely.geometry import mapping
from shapely import wkt

# Load environment and import project modules
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from legacy_loader import LegacySourceLoader
from translations import role_to_jsonb_dict


def make_jsonb(value, lang="en"):
    """Wrap a string in a {lang: value} jsonb structure for translatable fields."""
    if value is None or value == "":
        return None
    return Json({lang: str(value), "fr": str(value)})  # Same value in both for now


def migrate_jurisdiction(cur, config, slug):
    """Migrate a single jurisdiction's data into Supabase."""
    name = config["name"]
    level = config["level"]
    print(f"\n=== Migrating {name} ({slug}) ===")

    loader = LegacySourceLoader(config)
    loader.load()

    # Determine country/province from slug (ca_federal, ca_on, ca_on_toronto)
    parts = slug.split("_")
    country_code = parts[0].upper()
    province_code = parts[1].upper() if len(parts) > 1 and level != "federal" else None

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
        (slug, make_jsonb(name), level, country_code, province_code),
    )
    jurisdiction_id = cur.fetchone()[0]
    print(f"  Inserted jurisdiction: {jurisdiction_id}")

    # ── Step 3: Insert districts with PostGIS geometry ──
    # Some districts are represented by multiple polygons (e.g., a riding that
    # includes both a mainland section and an offshore island). We group all
    # polygons by join_key and union them into a single MultiPolygon per district.
    from shapely.ops import unary_union

    boundary_field = loader.district_field
    district_id_map = {}

    # Group geometries by join_key
    grouped: Dict[Any, List[Any]] = {}
    grouped_names: Dict[Any, str] = {}
    for _, row in loader.boundaries.iterrows():
        district_value = row[boundary_field]
        if district_value is None or row.geometry is None:
            continue

        join_key = loader._normalize_join_key(district_value)
        if join_key is None:
            continue

        grouped.setdefault(join_key, []).append(row.geometry)
        grouped_names.setdefault(join_key, str(district_value))

    rows_inserted = 0
    for join_key, geoms in grouped.items():
        # Merge multi-polygon districts into a single (Multi)Polygon
        if len(geoms) == 1:
            merged = geoms[0]
        else:
            merged = unary_union(geoms)

        cur.execute(
            """
            INSERT INTO districts (jurisdiction_id, external_id, name, boundary)
            VALUES (%s, %s, %s, ST_GeomFromText(%s, 4326))
            RETURNING id;
            """,
            (
                jurisdiction_id,
                str(join_key),
                make_jsonb(grouped_names[join_key]),
                merged.wkt,
            ),
        )
        district_id_map[join_key] = cur.fetchone()[0]
        rows_inserted += 1

    print(f"  Inserted {rows_inserted} districts")

    # ── Step 4: Insert representatives + representations ──
    role_label = config.get("output_role_label", "representative")
    role_label_formatted = role_label.upper() if len(role_label) <= 3 else role_label.capitalize()

    reps_inserted = 0
    representations_inserted = 0

    for join_key, rep_data in loader.representatives.items():
        # Build the full name from honorific + first + last
        full_name = LegacySourceLoader.build_full_name(rep_data) or ""
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
                (representative_id, district_id, jurisdiction_id, role, start_date, scope)
            VALUES (%s, %s, %s, %s, %s, 'district');
            """,
            (
                rep_id,
                district_id,
                jurisdiction_id,
                Json(role_to_jsonb_dict(role_label_formatted)),
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

    print("Connecting to Supabase...")
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        config_dir = Path(os.getenv("JURISDICTIONS_CONFIG_DIR"))
        results = []
        for config_file in sorted(config_dir.glob("*.json")):
            with open(config_file) as f:
                config = json.load(f)
            slug = config_file.stem
            result = migrate_jurisdiction(cur, config, slug)
            results.append((config["name"], result))

        # Apply governance metadata from migrations/002 to populate the
        # governance jsonb column on every jurisdiction. Idempotent SQL.
        governance_path = PROJECT_ROOT / "migrations" / "002_governance_metadata.sql"
        if governance_path.exists():
            print("\nApplying governance metadata...")
            with open(governance_path) as f:
                cur.execute(f.read())

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
