"""
backfill_politician_slugs.py

One-time (re-runnable) backfill that populates politicians.slug with readable
`first-last` slugs, unique within each jurisdiction, with -2/-3/... collision
suffixes. Carries forward the scheme used by the old
backfill_representative_slugs.py, adapted to the v2 politicians schema.

Key adaptation to the v2 model: politicians has one row PER ROLE, and a person
(uuid) may own several rows. A slug is assigned per (jurisdiction_slug, uuid)
— NOT per row — and then written to every row that person owns in that
jurisdiction. This preserves the slug <-> uuid bijection that the API's
/representative/<jurisdiction_slug>/<slug> route depends on.

Determinism: within a jurisdiction, people are processed in a stable order
(slug-base, then uuid), so collision suffixes are reproducible across runs.

Usage:
    SUPABASE_DB_URL=postgres://... python backfill_politician_slugs.py
    SUPABASE_DB_URL=postgres://... python backfill_politician_slugs.py --dry-run

Idempotency caveat: a full re-run recomputes every slug. If new people were
added to a jurisdiction since the last run and their base slug collides with an
existing one, suffix numbering could shift for that collision group. For steady
state, the pipeline writer should assign slugs on insert; this script is for the
initial backfill and bulk repairs.

The slugify_name() function below is the ONLY normalization logic. If the old
004 backfill used different rules (apostrophe / accent / multi-word handling,
or a different suffix scheme), swap this one function to match — nothing else
needs to change.
"""

import argparse
import re
import sys
import unicodedata
from collections import defaultdict

import db


def slugify_name(first: str, last: str) -> str:
    """`First O'Brien` -> `first-obrien`. ASCII, lowercase, hyphen-separated."""
    raw = f"{first or ''} {last or ''}".strip()
    # Strip accents/diacritics: Montréal-style -> ascii.
    ascii_str = (
        unicodedata.normalize("NFKD", raw)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    # Drop apostrophes so O'Brien -> obrien (not o-brien).
    ascii_str = ascii_str.replace("'", "")
    # Any run of non-alphanumerics becomes a single hyphen.
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_str).strip("-")
    return slug or "unknown"


def build_assignments() -> dict[tuple[str, str], str]:
    """Return {(jurisdiction_slug, uuid): slug} for every distinct person."""
    rows = db.query(
        """
        SELECT DISTINCT jurisdiction_slug, uuid, first_name, last_name
        FROM politicians
        ORDER BY jurisdiction_slug, last_name, first_name, uuid;
        """
    )

    people_by_jur: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for jslug, uuid, first, last in rows:
        people_by_jur[jslug].append((str(uuid), first, last))

    assignments: dict[tuple[str, str], str] = {}
    for jslug, people in people_by_jur.items():
        counts: dict[str, int] = {}
        # Stable order so suffix assignment is reproducible.
        for uuid, first, last in sorted(
            people, key=lambda p: (slugify_name(p[1], p[2]), p[0])
        ):
            base = slugify_name(first, last)
            counts[base] = counts.get(base, 0) + 1
            slug = base if counts[base] == 1 else f"{base}-{counts[base]}"
            assignments[(jslug, uuid)] = slug
    return assignments


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run", action="store_true", help="Print assignments, write nothing."
    )
    args = parser.parse_args()

    assignments = build_assignments()
    print(f"Computed slugs for {len(assignments)} people.")

    if args.dry_run:
        for (jslug, uuid), slug in sorted(assignments.items()):
            print(f"  {jslug:20} {uuid}  ->  {slug}")
        print("Dry run — no rows written.")
        return 0

    total_rows = 0
    for (jslug, uuid), slug in assignments.items():
        total_rows += db.execute(
            "UPDATE politicians SET slug = %s WHERE jurisdiction_slug = %s AND uuid = %s;",
            (slug, jslug, uuid),
        )
    print(f"Updated {total_rows} rows across {len(assignments)} people.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
