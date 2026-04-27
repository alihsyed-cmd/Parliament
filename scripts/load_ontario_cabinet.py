"""
Load Ontario cabinet members as role-based representations.

Reads the Ontario cabinet CSV (one row per role, so multi-role ministers
appear multiple times — Doug Ford has 2 rows: Premier + Minister of
Intergovernmental Affairs). The script groups rows by full_name, inserts
one representative per unique person, and one representation per role.

Idempotent: deletes existing role-scoped reps for Ontario before re-inserting.

Usage:
    python3 scripts/load_ontario_cabinet.py
"""

import os
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json

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
    csv_path = os.getenv("ONTARIO_CABINET_CSV")
    if not db_url or not csv_path:
        print("ERROR: SUPABASE_DB_URL and ONTARIO_CABINET_CSV must be set in .env")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    # Group rows by full_name (some ministers hold multiple roles)
    by_person = defaultdict(list)
    for _, row in df.iterrows():
        full_name = str(row.get("full_name", "")).strip()
        if not full_name or full_name.lower() == "nan":
            continue
        by_person[full_name].append(row)

    print(f"Loaded {len(df)} cabinet rows representing {len(by_person)} unique people")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Get Ontario's jurisdiction_id
        cur.execute("SELECT id FROM jurisdictions WHERE slug = %s;", ("ca_on",))
        row = cur.fetchone()
        if row is None:
            print("ERROR: Ontario jurisdiction not found in database")
            sys.exit(1)
        ontario_id = row[0]

        # Idempotency: delete any existing role-scoped reps for Ontario
        cur.execute(
            """
            DELETE FROM representatives
            WHERE id IN (
                SELECT representative_id FROM representations
                WHERE jurisdiction_id = %s AND scope = 'role'
            );
            """,
            (ontario_id,),
        )
        deleted = cur.rowcount
        if deleted:
            print(f"Cleared {deleted} existing role-scoped representative(s) for Ontario")

        people_inserted = 0
        roles_inserted = 0

        for full_name, rows in sorted(by_person.items()):
            # Use the first row for personal info (all rows for the same person
            # have identical first/last/honorific)
            first_row = rows[0]
            profile_url = str(first_row.get("profile_url", "")).strip()

            cur.execute(
                """
                INSERT INTO representatives
                    (name, website_url, external_ids)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (
                    make_jsonb(full_name),
                    make_jsonb(profile_url) if profile_url and profile_url.lower() != "nan" else None,
                    Json({"ola_slug": str(first_row.get("profile_slug", "")).strip()}),
                ),
            )
            rep_id = cur.fetchone()[0]
            people_inserted += 1

            # Insert one representation per role this person holds
            for r in rows:
                role = str(r.get("role", "")).strip()
                if not role or role.lower() == "nan":
                    continue
                cur.execute(
                    """
                    INSERT INTO representations
                        (representative_id, district_id, jurisdiction_id, role, scope)
                    VALUES (%s, NULL, %s, %s, 'role');
                    """,
                    (rep_id, ontario_id, make_jsonb(role)),
                )
                roles_inserted += 1

        conn.commit()
        print(f"\nInserted {people_inserted} cabinet members holding {roles_inserted} roles")
        print("Ontario cabinet loaded successfully.")

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
