#!/usr/bin/env python3
"""
One-time backfill: set photo_url on federal MPs to /mp-photos/{filename}
where filename matches a file in frontend/public/mp-photos/.

The match strategy:
  1. Get all federal MPs from the database (those with parl_gc_ca external_id)
  2. For each MP, derive expected filename: lowercase firstname_lastname,
     unicode preserved, special chars handled
  3. Check if the file exists in frontend/public/mp-photos/
  4. If yes, set photo_url = "/mp-photos/{filename}"
  5. If no, log the miss; we'll patch by hand

Path-only URLs (no domain). The API prepends FRONTEND_BASE_URL at
response time so we can deploy to different domains without re-running
this script.

Usage:
    python3 scripts/populate_federal_photos.py
"""
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

sys.path.insert(0, str(Path(__file__).parent))
import db


PHOTOS_DIR = PROJECT_ROOT / "frontend" / "public" / "mp-photos"


def derive_filename(name: str) -> str:
    """Convert "Hon. Mark Carney" or "Right Hon. Mark Carney" to mark_carney.jpg"""
    n = name.strip()
    # Strip honorifics
    for prefix in ["Right Hon. ", "Hon. ", "Mr. ", "Ms. ", "Mrs. ", "Dr. "]:
        if n.startswith(prefix):
            n = n[len(prefix):]
            break

    # Lowercase, replace whitespace runs with single underscore
    n = n.lower()
    n = re.sub(r"\s+", "_", n)

    return f"{n}.jpg"


def main():
    if not PHOTOS_DIR.exists():
        print(f"ERROR: photo directory not found: {PHOTOS_DIR}")
        sys.exit(1)

    available = {f.name for f in PHOTOS_DIR.iterdir() if f.suffix == ".jpg"}
    print(f"Found {len(available)} photo files in {PHOTOS_DIR}\n")

    print("Fetching federal MPs from database...")
    rows = db.query("""
        SELECT DISTINCT r.id, r.name->>'en' AS name
        FROM representatives r
        JOIN representations rep ON rep.representative_id = r.id
        JOIN jurisdictions j ON j.id = rep.jurisdiction_id
        WHERE j.slug = 'ca_federal'
        ORDER BY r.name->>'en';
    """)
    print(f"  {len(rows)} federal representatives\n")

    updated = 0
    misses = []
    for rep_id, name in rows:
        if not name:
            continue
        filename = derive_filename(name)
        if filename in available:
            db.execute(
                "UPDATE representatives SET photo_url = %s WHERE id = %s;",
                (f"/mp-photos/{filename}", rep_id),
            )
            updated += 1
        else:
            misses.append((name, filename))

    print(f"Updated photo_url on {updated} federal MPs\n")

    if misses:
        print(f"{len(misses)} MPs without matching photo files:")
        for name, expected in misses[:30]:
            print(f"  {name!r:40} -> expected {expected}")
        if len(misses) > 30:
            print(f"  ... and {len(misses) - 30} more")
    else:
        print("All MPs matched a photo file.")


if __name__ == "__main__":
    main()
