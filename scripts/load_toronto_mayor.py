"""
Load Toronto Mayor as a role-based representation.

Reads the existing Toronto Elected Officials CSV, finds the Mayor row
(skipped during the district-based migration because the Mayor has no
District ID), and inserts her into Supabase as a role-scoped rep.

Idempotent: deletes any existing Mayor representation for Toronto before
inserting fresh data.

Usage:
    python3 scripts/load_toronto_mayor.py
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
    csv_path = os.getenv("TORONTO_CSV")
    if not db_url or not csv_path:
        print("ERROR: SUPABASE_DB_URL and TORONTO_CSV must be set in .env")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    # Find rows where Primary role is "Mayor"
    mayor_rows = df[df["Primary role"].str.strip().str.lower() == "mayor"]
    if mayor_rows.empty:
        print("ERROR: no Mayor row found in Toronto CSV")
        sys.exit(1)

    print(f"Found {len(mayor_rows)} mayor row(s) in Toronto CSV")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Get Toronto's jurisdiction_id
        cur.execute("SELECT id FROM jurisdictions WHERE slug = %s;", ("ca_on_toronto",))
        row = cur.fetchone()
        if row is None:
            print("ERROR: Toronto jurisdiction not found in database")
            sys.exit(1)
        toronto_id = row[0]

        # Idempotency: delete any existing role-scoped reps for Toronto
        cur.execute(
            """
            DELETE FROM representatives
            WHERE id IN (
                SELECT representative_id FROM representations
                WHERE jurisdiction_id = %s AND scope = 'role'
            );
            """,
            (toronto_id,),
        )
        deleted = cur.rowcount
        if deleted:
            print(f"Cleared {deleted} existing role-scoped representative(s) for Toronto")

        # Insert each mayor row
        for _, row in mayor_rows.iterrows():
            first = str(row.get("First name", "")).strip()
            last = str(row.get("Last name", "")).strip()
            full_name = f"{first} {last}".strip()
            role = str(row.get("Primary role", "")).strip()
            email = str(row.get("Email", "")).strip()
            phone = str(row.get("Phone", "")).strip()
            photo_url = str(row.get("Photo URL", "")).strip()
            website = str(row.get("Website", "")).strip()

            cur.execute(
                """
                INSERT INTO representatives
                    (name, email, phone, photo_url, website_url, external_ids)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    make_jsonb(full_name),
                    email if email and email.lower() != "nan" else None,
                    phone if phone and phone.lower() != "nan" else None,
                    photo_url if photo_url and photo_url.lower() != "nan" else None,
                    make_jsonb(website),
                    Json({}),
                ),
            )
            rep_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO representations
                    (representative_id, district_id, jurisdiction_id, role, scope)
                VALUES (%s, NULL, %s, %s, 'role');
                """,
                (rep_id, toronto_id, Json(role_to_jsonb_dict(role))),
            )

            print(f"Inserted: {full_name} ({role})")

        conn.commit()
        print("\nToronto Mayor loaded successfully.")

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
