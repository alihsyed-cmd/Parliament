"""
Load federal cabinet members as role-based representations.

Unlike the Ontario loader, federal cabinet members already exist in the
representatives table as MPs (with their parl_gc_ca Person ID stored in
external_ids). This script joins to those existing records and adds a
role-scoped representation alongside their existing district-scoped MP
representation.

Net effect per minister:
  - 1 representative row (already exists from MP migration)
  - 2 representation rows: scope='district' (MP for their riding) +
                           scope='role' (cabinet position)

Idempotent: deletes existing role-scoped reps for Canada before re-inserting.

Usage:
    python3 scripts/load_federal_cabinet.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json

import sys
sys.path.insert(0, str(Path(__file__).parent))
from translations import role_to_jsonb_dict

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def make_jsonb(value, lang="en"):
    """Wrap a string in a {en, fr} jsonb structure."""
    if value is None or value == "":
        return None
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    return Json({lang: s, "fr": s})


def main():
    db_url = os.getenv("SUPABASE_DB_URL")
    csv_path = os.getenv("FEDERAL_CABINET_CSV")
    if not db_url or not csv_path:
        print("ERROR: SUPABASE_DB_URL and FEDERAL_CABINET_CSV must be set in .env")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    print(f"Loaded {len(df)} cabinet rows from CSV")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Get Canada's jurisdiction_id
        cur.execute("SELECT id FROM jurisdictions WHERE slug = %s;", ("ca_federal",))
        row = cur.fetchone()
        if row is None:
            print("ERROR: Federal jurisdiction not found in database")
            sys.exit(1)
        federal_id = row[0]

        # Idempotency: delete only role-scoped representations for Canada.
        # We keep the underlying representative rows (those are the MP records)
        # and only remove the cabinet linkages.
        cur.execute(
            """
            DELETE FROM representations
            WHERE jurisdiction_id = %s AND scope = 'role';
            """,
            (federal_id,),
        )
        deleted = cur.rowcount
        if deleted:
            print(f"Cleared {deleted} existing role-scoped representation(s) for Canada")

        # Track what happens to each cabinet member
        roles_inserted = 0
        unmatched = []
        pm_inserted = False  # Special flag for the PM (no Person ID match expected? we'll see)

        for _, row in df.iterrows():
            person_id = str(row.get("Person ID", "")).strip()
            first = str(row.get("First Name", "")).strip()
            last = str(row.get("Last Name", "")).strip()
            honorific = str(row.get("Honorific Title", "")).strip()
            title = str(row.get("Title", "")).strip()
            full_name = f"{honorific} {first} {last}".strip()

            if not person_id or not title:
                continue

            # Find the existing MP representative by Person ID
            cur.execute(
                """
                SELECT id FROM representatives
                WHERE external_ids->>'parl_gc_ca' = %s;
                """,
                (person_id,),
            )
            result = cur.fetchone()

            if result is None:
                unmatched.append((person_id, full_name, title))
                continue

            rep_id = result[0]

            # Insert role-scoped representation
            cur.execute(
                """
                INSERT INTO representations
                    (representative_id, district_id, jurisdiction_id, role, scope)
                VALUES (%s, NULL, %s, %s, 'role');
                """,
                (rep_id, federal_id, Json(role_to_jsonb_dict(title))),
            )
            roles_inserted += 1

            if title == "Prime Minister":
                pm_inserted = True
                print(f"  Linked PM: {full_name} (Person ID {person_id})")

        conn.commit()
        print(f"\nInserted {roles_inserted} cabinet role(s)")
        if not pm_inserted:
            print("WARNING: Prime Minister role not inserted — verify CSV data")

        if unmatched:
            print(f"\n{len(unmatched)} unmatched cabinet members (Person ID not in MP records):")
            for pid, name, title in unmatched:
                print(f"  Person ID {pid}: {name} ({title})")
        else:
            print("All cabinet members successfully linked to existing MP records.")

        print("\nFederal cabinet loaded successfully.")

    except Exception as e:
        conn.rollback()
        print(f"\nFAILED: {type(e).__name__}: {e}")
        print("Transaction rolled back. No changes made.")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
