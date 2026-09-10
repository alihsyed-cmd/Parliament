#!/usr/bin/env python3
"""
Export data/elections.csv to the Supabase `elections` table.

The elections analogue of candidate-export: a tracked CSV is the source of
truth, this script is the only thing that writes the table, and it upserts on
the primary key inside one transaction so a failure leaves the database
untouched.

    python3 scripts/export_elections.py            # load
    python3 scripts/export_elections.py --dry-run  # validate only, no write

Adding a newly-announced election is therefore: append a row to the CSV, run
this, commit. The row's `id` must be the UUID5 below of
<jurisdiction_slug>|<election_date>|<election_type>; --fix-ids rewrites the CSV
with correct ids so a hand-added row does not have to be computed by hand.

Why upsert rather than the delete-then-insert the incumbent export uses:
reminder_sends foreign-keys elections.id, and deleting an election would cascade
away the ledger recording who has already been reminded about it. The next cron
run would then re-send every one of those reminders. Correcting a date is a
normal editing operation and must not have that consequence.

Note the one case where an edit is NOT an update: the id is derived from the
date, so changing a date mints a new id and inserts a new row, leaving the old
one behind. That is intentional — it is indistinguishable at the data layer from
"a different election" — but it means a corrected date needs the stale row
deleted explicitly. --prune does that, reporting each deletion first.
"""

import argparse
import csv
import datetime as dt
import os
import sys
import uuid as uuidlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import db  # noqa: E402

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "elections.csv"

# Pinned once, 2026-09-10. Never change this: elections.id is derived from it and
# reminder_sends references those ids, so a new namespace would orphan the entire
# ledger and re-send every reminder already delivered.
ELECTION_NS = uuidlib.UUID("e1ec7104-0000-5000-9000-b0a1c2d3e4f5")

COLS = [
    "id", "jurisdiction_slug", "election_date", "election_type", "name",
    "district_id", "is_confirmed", "advance_voting_starts", "info_url",
    "source_url", "last_verified",
]

VALID_TYPES = {"general", "by_election", "referendum", "special"}

UPSERT_SQL = """
    INSERT INTO elections (
        id, jurisdiction_slug, election_date, election_type, name, district_id,
        is_confirmed, advance_voting_starts, info_url, source_url, last_verified
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        jurisdiction_slug     = EXCLUDED.jurisdiction_slug,
        election_date         = EXCLUDED.election_date,
        election_type         = EXCLUDED.election_type,
        name                  = EXCLUDED.name,
        district_id           = EXCLUDED.district_id,
        is_confirmed          = EXCLUDED.is_confirmed,
        advance_voting_starts = EXCLUDED.advance_voting_starts,
        info_url              = EXCLUDED.info_url,
        source_url            = EXCLUDED.source_url,
        last_verified         = EXCLUDED.last_verified;
"""


def election_id(slug: str, date: str, etype: str) -> str:
    return str(uuidlib.uuid5(ELECTION_NS, f"{slug}|{date}|{etype}"))


def _blank_to_none(value: str):
    """Empty CSV cell -> NULL. The repo's missing-data convention (CLAUDE.md)."""
    value = (value or "").strip()
    return value or None


def _parse_date(value: str, field: str, line: int, errors: list):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        errors.append(f"line {line}: {field} is not ISO 8601 (YYYY-MM-DD): {value!r}")
        return None


def _parse_bool(value: str, field: str, line: int, errors: list):
    value = (value or "").strip()
    if value in ("true", "false"):
        return value == "true"
    errors.append(f"line {line}: {field} must be lowercase 'true' or 'false', got {value!r}")
    return None


def read_rows(path: Path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLS:
            raise SystemExit(
                f"Header mismatch in {path}\n  expected: {COLS}\n  found:    {reader.fieldnames}"
            )
        return list(reader)


def validate(rows, known_slugs):
    """
    Every check is offline and total: collect all errors, then report. A single
    bad row aborts the whole load rather than being skipped, because a partially
    loaded elections table sends a partially correct set of reminders and nobody
    finds out until the wrong day.
    """
    errors, prepared, seen_ids, seen_natural = [], [], set(), set()

    for i, row in enumerate(rows, start=2):  # line 1 is the header
        slug = row["jurisdiction_slug"].strip()
        etype = row["election_type"].strip()
        date = _parse_date(row["election_date"], "election_date", i, errors)
        advance = _parse_date(row["advance_voting_starts"], "advance_voting_starts", i, errors)
        verified = _parse_date(row["last_verified"], "last_verified", i, errors)
        confirmed = _parse_bool(row["is_confirmed"], "is_confirmed", i, errors)
        district_id = _blank_to_none(row["district_id"])

        if slug not in known_slugs:
            errors.append(f"line {i}: jurisdiction_slug {slug!r} is not a registered jurisdiction")
        if etype not in VALID_TYPES:
            errors.append(f"line {i}: election_type {etype!r} not in {sorted(VALID_TYPES)}")
        if etype == "by_election" and district_id is None:
            errors.append(f"line {i}: by_election requires a district_id")
        if etype != "by_election" and district_id is not None:
            errors.append(f"line {i}: district_id is only valid on a by_election")
        if date and advance and advance > date:
            errors.append(f"line {i}: advance_voting_starts {advance} is after election_date {date}")

        if date:
            expected = election_id(slug, date.isoformat(), etype)
            if row["id"].strip() != expected:
                errors.append(
                    f"line {i}: id does not match UUID5 of {slug}|{date}|{etype} "
                    f"(expected {expected}). Run with --fix-ids."
                )
            natural = (slug, date.isoformat(), etype)
            if natural in seen_natural:
                errors.append(f"line {i}: duplicate election {natural}")
            seen_natural.add(natural)

        if row["id"].strip() in seen_ids:
            errors.append(f"line {i}: duplicate id {row['id']}")
        seen_ids.add(row["id"].strip())

        prepared.append((
            row["id"].strip(), slug, date, etype, _blank_to_none(row["name"]),
            district_id, confirmed, advance, _blank_to_none(row["info_url"]),
            _blank_to_none(row["source_url"]), verified,
        ))

    return prepared, errors


def fix_ids(path: Path, rows):
    changed = 0
    for row in rows:
        try:
            date = dt.date.fromisoformat(row["election_date"].strip()).isoformat()
        except ValueError:
            continue
        correct = election_id(row["jurisdiction_slug"].strip(), date, row["election_type"].strip())
        if row["id"].strip() != correct:
            row["id"] = correct
            changed += 1
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"--fix-ids: rewrote {changed} id(s) in {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="validate only; write nothing")
    ap.add_argument("--fix-ids", action="store_true", help="rewrite the CSV with derived ids, then exit")
    ap.add_argument("--prune", action="store_true",
                    help="delete elections rows whose id is absent from the CSV")
    args = ap.parse_args()

    rows = read_rows(CSV_PATH)

    if args.fix_ids:
        fix_ids(CSV_PATH, rows)
        return 0

    if not os.getenv("SUPABASE_DB_URL"):
        raise SystemExit("SUPABASE_DB_URL is not set.")

    known_slugs = {r[0] for r in db.query("SELECT slug FROM jurisdictions;")}
    prepared, errors = validate(rows, known_slugs)

    if errors:
        print(f"REFUSING TO LOAD — {len(errors)} validation error(s):\n", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    confirmed = sum(1 for p in prepared if p[6])
    print(f"{len(prepared)} election(s) validated — {confirmed} confirmed, "
          f"{len(prepared) - confirmed} projected.")

    if args.dry_run:
        print("--dry-run: nothing written.")
        return 0

    conn = db.get_connection()
    prev_autocommit = conn.autocommit
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, prepared)
            upserted = len(prepared)

            pruned = 0
            if args.prune:
                cur.execute(
                    "DELETE FROM elections WHERE NOT (id = ANY(%s)) RETURNING id, jurisdiction_slug, election_date;",
                    ([p[0] for p in prepared],),
                )
                gone = cur.fetchall()
                pruned = len(gone)
                for row in gone:
                    print(f"  pruned {row[1]} {row[2]} ({row[0]})")
        conn.commit()
    except Exception:
        conn.rollback()
        print("Load failed; transaction rolled back. Database unchanged.", file=sys.stderr)
        raise
    finally:
        conn.autocommit = prev_autocommit

    print(f"Upserted {upserted} election(s)" + (f", pruned {pruned}." if args.prune else "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
