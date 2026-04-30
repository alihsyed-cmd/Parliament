#!/usr/bin/env python3
"""
One-time backfill: populate the `slug` column on every existing
representative based on their name.

Slugs are URL-safe lowercase strings: "Tom Rakocevic" -> "tom-rakocevic",
"Right Hon. Mark Carney" -> "mark-carney" (honorifics stripped).

Collisions within a jurisdiction get a numeric suffix: if two MPPs are
both named "Mike Smith", the second becomes "mike-smith-2".

The script reads name from the JSONB language map (English version) and
writes the slug as a plain TEXT column.

Usage:
    python3 scripts/backfill_representative_slugs.py

Idempotent: safe to re-run. Only updates rows where slug IS NULL or
where the existing slug doesn't match what we'd generate now.
"""
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

sys.path.insert(0, str(Path(__file__).parent))
import db


HONORIFICS = {
    "right hon.",
    "right honourable",
    "hon.",
    "honourable",
    "the hon.",
    "mr.",
    "ms.",
    "mrs.",
    "dr.",
}


def slugify(name: str) -> str:
    """Convert a name to a URL slug.

    - Strip honorifics
    - Normalize unicode (Frans-Henri -> frans-henri, accented chars handled)
    - Lowercase
    - Replace whitespace and punctuation with single hyphens
    - Strip leading/trailing hyphens
    """
    if not name:
        return ""

    # Strip honorifics from the start (case-insensitive)
    lower = name.lower().strip()
    for honorific in sorted(HONORIFICS, key=len, reverse=True):
        if lower.startswith(honorific + " "):
            lower = lower[len(honorific):].strip()
            break

    # Normalize unicode (NFKD splits accented chars into base + combining marks)
    normalized = unicodedata.normalize("NFKD", lower)
    # Drop combining marks (the accents)
    ascii_form = "".join(c for c in normalized if not unicodedata.combining(c))

    # Replace anything not alphanumeric with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_form)
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")

    return slug


def get_english_name(name_field) -> str:
    """Extract the English name from a JSONB language map.

    Representatives store `name` as JSONB like {"en": "Tom Rakocevic"}.
    psycopg2 deserializes this to a dict.
    """
    if isinstance(name_field, dict):
        return name_field.get("en", "")
    if isinstance(name_field, str):
        # Some legacy rows might be plain strings
        try:
            parsed = json.loads(name_field)
            return parsed.get("en", "") if isinstance(parsed, dict) else name_field
        except (json.JSONDecodeError, TypeError):
            return name_field
    return ""


def main():
    print("Fetching all representatives...")
    rows = db.query("SELECT id, name FROM representatives ORDER BY id;")
    print(f"  {len(rows)} representatives found\n")

    # Generate slugs and detect collisions
    print("Generating slugs and resolving collisions...")
    slug_to_ids = defaultdict(list)
    rep_slugs = {}  # rep_id -> base_slug

    for rep_id, name_jsonb in rows:
        english_name = get_english_name(name_jsonb)
        if not english_name:
            print(f"  WARN  {rep_id}: no English name, skipping")
            continue

        base_slug = slugify(english_name)
        if not base_slug:
            print(f"  WARN  {rep_id}: name {english_name!r} produced empty slug")
            continue

        rep_slugs[rep_id] = base_slug
        slug_to_ids[base_slug].append(rep_id)

    # Resolve collisions
    final_slugs = {}
    collision_count = 0
    for base_slug, ids in slug_to_ids.items():
        if len(ids) == 1:
            final_slugs[ids[0]] = base_slug
        else:
            collision_count += len(ids) - 1
            print(f"  COLL  {base_slug}: {len(ids)} reps")
            # First gets the bare slug; rest get -2, -3, ...
            final_slugs[ids[0]] = base_slug
            for i, rep_id in enumerate(ids[1:], start=2):
                final_slugs[rep_id] = f"{base_slug}-{i}"

    print(f"\n  {len(final_slugs)} slugs generated, {collision_count} collisions resolved\n")

    # Write to database
    print("Writing slugs to database...")
    updated = 0
    for rep_id, slug in final_slugs.items():
        db.execute(
            "UPDATE representatives SET slug = %s WHERE id = %s;",
            (slug, rep_id),
        )
        updated += 1

    print(f"  Updated {updated} rows\n")

    # Verify a sample
    print("Sample of generated slugs:")
    sample = db.query("""
        SELECT name->>'en' AS name, slug
        FROM representatives
        WHERE slug IS NOT NULL
        ORDER BY name->>'en'
        LIMIT 10;
    """)
    for name, slug in sample:
        print(f"  {name!r:50} -> {slug}")

    print("\nDone.")


if __name__ == "__main__":
    main()
