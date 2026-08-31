#!/usr/bin/env python3
"""Stages 5-8 of the Parliament candidate pipeline, as one deterministic run.

consolidation -> validation -> writer -> export, for a single run_id + slug.

Each stage's rules come from .claude/agents/candidate-{consolidation,validation,
writer,export}.md. The stages are mechanical, so running them as one script
rather than four subagents keeps them byte-identical across jurisdictions and
lets the shared appends (known_sources.yaml, candidate_validation_log.md) be
serialized instead of raced by parallel city runs.

Usage:
    python3 scripts/candidate_tail.py <run_id> <slug> [--no-export]
"""

import csv
import os
import re
import shutil
import sys
import unicodedata
import uuid as uuidlib
from datetime import datetime, timezone

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

CANDIDATE_NS = uuidlib.UUID("c4a7d1e2-9f3b-5c6d-8e1a-2b3c4d5e6f7a")

HEADER = [
    "uuid", "jurisdiction_slug", "first_name", "last_name",
    "email", "phone", "role_scope", "district_id", "district_name",
]
EXTRACTED_HEADER = HEADER[1:]  # the eight columns extraction emits

PLACEHOLDERS = {"null", "n/a", "none", "unknown", "-", "na"}


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def p(*parts):
    return os.path.join(ROOT, *parts)


def coerce_id(v):
    """String-coerce a boundary value exactly the way export does."""
    if v is None:
        return ""
    if isinstance(v, float):
        if v != v:  # NaN — e.g. Sudbury's city-wide mayor polygon
            return ""
        if v.is_integer():
            return str(int(v))
    if isinstance(v, int):
        return str(v)
    s = str(v).strip()
    return "" if s.lower() in ("nan", "none") else s


# Some boundary files carry more than the jurisdiction's wards. Filtering here
# keeps the validation reference equal to the ward set a voter lookup can hit.
#
# Peterborough's wards.geojson holds 5 real wards (WARDTYPE=='WARD') plus 107
# polling subdivisions (WARDTYPE=='SUBWARD'); jurisdictions.csv points at
# WARDNAME, which without this filter yields the subdivision numbers instead of
# the ward names. Supabase has both loaded, so the 5 ward names are valid join
# keys — the subwards are noise, not targets.
BOUNDARY_FILTERS = {
    "ca_on_peterborough": lambda gdf: gdf[gdf["WARDTYPE"] == "WARD"],
}


# Jurisdictions whose stored candidate UUIDs were minted under a namespace that
# is NOT the pinned CANDIDATE_NS, and therefore cannot be reproduced by the
# formula above. Regenerating them on a rerun would silently change the primary
# key of every returning candidate, leaving the old rows stranded in Supabase
# (export upserts, it never deletes) and orphaning any invitation already issued
# against the old uuid.
#
# Hamilton is the only such jurisdiction: its first run predates the 2026-08-13
# namespace pin and that run's script was never saved, so its namespace is
# unrecoverable (UUID5 is not invertible; the pinned constant and all four
# uuid.NAMESPACE_* values were tested against several key formulas — zero
# matches).
#
# For these slugs we keep the stored uuid for anyone whose NAME appears in the
# prior canonical file, and mint a normal pinned-namespace uuid for genuinely
# new candidates. Matching is on name alone, deliberately: a candidate who
# withdrew in one ward and refiled in another is the same person and should keep
# the same identity and invitation.
REUSE_PRIOR_UUIDS = {"ca_on_hamilton"}


def _name_key(first, last):
    return unicodedata.normalize("NFC", f"{first}|{last}").casefold().strip()


def prior_uuid_by_name(slug):
    """Map name-key -> uuid from the jurisdiction's existing canonical roster."""
    path = p("data", slug, "raw_candidates.csv")
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            u = (r.get("uuid") or "").strip()
            if not u:
                continue
            out.setdefault(_name_key(r.get("first_name", ""), r.get("last_name", "")), u)
    return out


# --------------------------------------------------------------------------
# Stage 5 - consolidation
# --------------------------------------------------------------------------

def consolidate(run_id, slug):
    src = p("data", "_staging", run_id, "extracted", "candidates.csv")
    with open(src, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    missing = [c for c in EXTRACTED_HEADER if rows and c not in rows[0]]
    if missing:
        raise SystemExit(f"extracted/candidates.csv missing columns: {missing}")

    prior = prior_uuid_by_name(slug) if slug in REUSE_PRIOR_UUIDS else {}
    reused = 0
    for r in rows:
        carried = prior.get(_name_key(r.get("first_name", ""), r.get("last_name", "")))
        if carried:
            r["uuid"] = carried
            reused += 1
            continue
        key = "|".join([
            slug, r.get("first_name", ""), r.get("last_name", ""),
            r.get("role_scope", ""), r.get("district_id", ""),
        ])
        key = unicodedata.normalize("NFC", key).casefold().strip()
        r["uuid"] = str(uuidlib.uuid5(CANDIDATE_NS, key))
    if prior:
        print(f"      uuid reuse: {reused}/{len(rows)} carried from the prior "
              f"{slug} roster (unrecoverable legacy namespace)")

    groups = {}
    for r in rows:
        groups.setdefault(r["uuid"], []).append(r)

    def contact_rank(r):
        # most contact info first; lexicographic tiebreak for reproducibility
        return (
            0 if (r.get("email") or "").strip() else 1,
            0 if (r.get("phone") or "").strip() else 1,
            [(r.get(c) or "") for c in EXTRACTED_HEADER],
        )

    out, collapsed = [], []
    for u, grp in groups.items():
        if len(grp) == 1:
            out.append(grp[0])
            continue
        ordered = sorted(grp, key=contact_rank)
        keep, dropped = ordered[0], ordered[1:]
        conflicting = any(
            (d.get("email") or "").strip() != (keep.get("email") or "").strip()
            or (d.get("phone") or "").strip() != (keep.get("phone") or "").strip()
            for d in dropped
        )
        collapsed.append({
            "uuid": u,
            "type": "conflicting" if conflicting else "exact",
            "kept": {
                "name": f"{keep.get('first_name','')} {keep.get('last_name','')}".strip(),
                "district_id": keep.get("district_id", ""),
                "email": keep.get("email", ""),
                "phone": keep.get("phone", ""),
            },
            "dropped": [
                {"name": f"{d.get('first_name','')} {d.get('last_name','')}".strip(),
                 "email": d.get("email", ""), "phone": d.get("phone", "")}
                for d in dropped
            ],
            "note": ("rows share a uuid but disagree on email/phone - needs a human glance"
                     if conflicting else "clerk listed the same person twice"),
        })
        out.append(keep)

    # stable output order: mayors first, then by district, then by name
    out.sort(key=lambda r: (
        r.get("role_scope", ""), r.get("district_id", ""),
        r.get("last_name", ""), r.get("first_name", ""),
    ))

    dest_dir = p("data", "_staging", run_id, "consolidated")
    os.makedirs(dest_dir, exist_ok=True)
    with open(os.path.join(dest_dir, "candidates.csv"), "w",
              encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        for r in out:
            w.writerow([r.get(c, "") or "" for c in HEADER])

    report = {
        "run_id": run_id, "slug": slug, "consolidated": now_iso(),
        "input_rows": len(rows), "output_rows": len(out),
        "duplicates_collapsed": collapsed,
    }
    with open(p("data", "_staging", run_id, "consolidation_report.yaml"), "w",
              encoding="utf-8") as fh:
        yaml.safe_dump(report, fh, allow_unicode=True, sort_keys=False)

    assert len(out) == len(rows) - sum(len(c["dropped"]) for c in collapsed)
    assert len({r["uuid"] for r in out}) == len(out)
    return report


# --------------------------------------------------------------------------
# Stage 6 - validation
# --------------------------------------------------------------------------

def boundary_id_set(slug, jrow):
    bf = (jrow.get("boundary_file") or "").strip()
    col = (jrow.get("boundary_district_id_column") or "").strip()
    if not bf or not col:
        return None
    path = p("data", slug, bf)
    if not os.path.exists(path):
        return None
    import geopandas as gpd
    gdf = gpd.read_file(f"zip://{path}" if path.endswith(".zip") else path)
    if col not in gdf.columns:
        return None
    if slug in BOUNDARY_FILTERS:
        gdf = BOUNDARY_FILTERS[slug](gdf)
    return {coerce_id(v) for v in gdf[col].tolist() if coerce_id(v) != ""}


def validate(run_id, slug):
    path = p("data", "_staging", run_id, "consolidated", "candidates.csv")
    blocking, rowfails = [], []

    raw = open(path, "rb").read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        blocking.append(("utf8", f"file is not valid UTF-8: {e}"))
        text = raw.decode("utf-8", "replace")

    reader = list(csv.reader(text.splitlines()))
    if not reader or reader[0] != HEADER:
        blocking.append(("header", f"header is {reader[0] if reader else 'EMPTY'}, expected {HEADER}"))
    for i, rec in enumerate(reader[1:], start=2):
        if len(rec) != 9:
            blocking.append(("field_count", f"line {i} parses to {len(rec)} fields, expected 9"))

    rows = list(csv.DictReader(text.splitlines()))

    seen = {}
    for r in rows:
        u = (r.get("uuid") or "").strip()
        if not u:
            continue
        if u in seen:
            blocking.append(("uuid_unique", f"uuid {u} appears on more than one row"))
        seen[u] = True

    jrow = jurisdiction_row(slug)
    idset = boundary_id_set(slug, jrow)

    def label(r):
        return (r.get("district_name") or r.get("district_id") or "—")

    for r in rows:
        nm = f"{r.get('first_name','')} {r.get('last_name','')}".strip()
        if not (r.get("uuid") or "").strip():
            rowfails.append(("uuid_present", nm, label(r), "empty uuid"))
        for c in ("jurisdiction_slug", "first_name", "last_name", "role_scope"):
            if not (r.get(c) or "").strip():
                rowfails.append(("required_fields", nm, label(r), f"empty {c}"))
        scope = (r.get("role_scope") or "").strip()
        if scope not in ("district", "role"):
            rowfails.append(("enum", nm, label(r), f"role_scope={scope!r}"))
        did = (r.get("district_id") or "").strip()
        dnm = (r.get("district_name") or "").strip()
        if scope == "district" and not did:
            rowfails.append(("scope_consistency", nm, label(r), "role_scope=district with empty district_id"))
        if scope == "role" and (did or dnm):
            # district_name on a role row is tolerated by the DB CHECK (which only
            # constrains district_id) but flagged, per the stage definition.
            if did:
                rowfails.append(("scope_consistency", nm, label(r), "role_scope=role with non-empty district_id"))
        if scope == "district" and did and idset is not None and did not in idset:
            rowfails.append(("district_join", nm, label(r), f"district_id {did!r} not in boundary reference"))
        for c, v in r.items():
            if v and v.strip().lower() in PLACEHOLDERS:
                rowfails.append(("placeholder", nm, label(r), f"{c}={v!r}"))
        em = (r.get("email") or "").strip()
        if em and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", em):
            rowfails.append(("email_sanity", nm, label(r), f"email={em!r} is not an address"))

    roster_status = "unknown"
    man = p("data", "_staging", run_id, "acquisition_manifest.yaml")
    if os.path.exists(man):
        try:
            m = yaml.safe_load(open(man, encoding="utf-8")) or {}
            roster_status = find_roster_status(m) or "unknown"
        except Exception:
            pass

    n = len(rows)
    role_n = sum(1 for r in rows if (r.get("role_scope") or "").strip() == "role")
    dist_n = n - role_n
    wards = {(r.get("district_id") or "").strip() for r in rows if (r.get("district_id") or "").strip()}
    expected = (jrow.get("expected_district_count") or "?").strip()
    email_n = sum(1 for r in rows if (r.get("email") or "").strip())
    phone_n = sum(1 for r in rows if (r.get("phone") or "").strip())

    overall = "blocked" if blocking else ("pass_with_row_failures" if rowfails else "pass")

    log = p("data", "_registry", "candidate_validation_log.md")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    if not os.path.exists(log):
        with open(log, "w", encoding="utf-8") as fh:
            fh.write("# Candidate validation log\n")
    verdict_word = {"pass": "PASS", "pass_with_row_failures": "PASS WITH ROW FAILURES",
                    "blocked": "BLOCKED"}[overall]
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(f"\n## {run_id} — {slug} — {now_iso()}\n\n")
        fh.write(f"Roster status: {roster_status}\n")
        fh.write(f"Verdict: {verdict_word}\n")
        fh.write(f"Rows: {n}  (role-scoped {role_n}, district-scoped {dist_n})  ·  "
                 f"wards represented {len(wards)}/{expected}\n")
        fh.write(f"Contact coverage: email {email_n}/{n}, phone {phone_n}/{n}\n")
        fh.write(f"Blocking failures: {len(blocking)}   Row failures: {len(rowfails)}\n")
        if blocking:
            fh.write("\n### Blocking (file-level) — writer will refuse\n")
            for chk, det in blocking:
                fh.write(f"- [{chk}] {det}\n")
        if rowfails:
            fh.write("\n### Row failures (logged, non-blocking)\n")
            for chk, nm, lb, det in rowfails:
                fh.write(f"- [{chk}] {nm} — ward {lb} — {det}\n")

    verdict = {
        "run_id": run_id, "slug": slug, "validated": now_iso(),
        "overall": overall, "blocking_failures": len(blocking),
        "row_failures": len(rowfails),
    }
    with open(p("data", "_staging", run_id, "validation_verdict.yaml"), "w",
              encoding="utf-8") as fh:
        yaml.safe_dump(verdict, fh, allow_unicode=True, sort_keys=False)

    verdict["_stats"] = dict(rows=n, role=role_n, district=dist_n, wards=len(wards),
                             expected=expected, email=email_n, phone=phone_n,
                             roster_status=roster_status)
    verdict["_blocking"] = blocking
    verdict["_rowfails"] = rowfails
    return verdict


def find_roster_status(obj):
    if isinstance(obj, dict):
        if "roster_status" in obj and isinstance(obj["roster_status"], str):
            return obj["roster_status"]
        for v in obj.values():
            r = find_roster_status(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_roster_status(v)
            if r:
                return r
    return None


def jurisdiction_row(slug):
    with open(p("data", "jurisdictions.csv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["slug"] == slug:
                return r
    raise SystemExit(f"{slug} not in data/jurisdictions.csv")


# --------------------------------------------------------------------------
# Stage 7 - writer
# --------------------------------------------------------------------------

def write_canonical(run_id, slug):
    verdict_path = p("data", "_staging", run_id, "validation_verdict.yaml")
    if not os.path.exists(verdict_path):
        raise SystemExit("REFUSED: no validation_verdict.yaml — validation has not run.")
    verdict = yaml.safe_load(open(verdict_path, encoding="utf-8"))
    if verdict.get("blocking_failures", 0) > 0:
        raise SystemExit(f"REFUSED: {verdict['blocking_failures']} blocking failures. Nothing written.")

    src = p("data", "_staging", run_id, "consolidated", "candidates.csv")
    dest = p("data", slug, "raw_candidates.csv")
    mode, archived = "new", None

    if os.path.exists(dest):
        mode = "rerun"
        ts = run_id.rsplit("_", 1)[-1]
        adir = p("data", slug, "_archive", "candidates", ts)
        os.makedirs(adir, exist_ok=True)
        archived = os.path.join(adir, "raw_candidates.csv")
        shutil.move(dest, archived)

    with open(src, encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    tmp = dest + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)
    os.replace(tmp, dest)

    appended = append_registry(run_id, slug)
    return {"mode": mode, "archived": archived, "rows": len(rows) - 1,
            "registry": appended, "verdict": verdict.get("overall")}


def append_registry(run_id, slug):
    """Append newly-discovered candidate sources to known_sources.yaml.

    Preserve-never-rewrite: the file is text-appended, so existing entries keep
    their exact bytes and formatting (it is shared with the incumbent pipeline).
    """
    spath = p("data", "_staging", run_id, "sources.yaml")
    reg = p("data", "_registry", "known_sources.yaml")
    if not os.path.exists(spath):
        return "no sources.yaml — skipped"
    try:
        sdoc = yaml.safe_load(open(spath, encoding="utf-8")) or {}
    except Exception as e:
        return f"sources.yaml unparseable ({e.__class__.__name__}) — skipped"

    entries = collect_sources(sdoc)
    fresh = [e for e in entries
             if (e.get("origin") == "discovered" and e.get("status") == "found"
                 and e.get("url") and is_roster_source(e))]
    if not fresh:
        return "no newly-discovered roster source — skipped"

    existing = open(reg, encoding="utf-8").read() if os.path.exists(reg) else ""
    date = run_id.rsplit("_", 1)[-1][:8]
    date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"

    added = 0
    with open(reg, "a", encoding="utf-8") as fh:
        for e in fresh:
            url = e["url"]
            if url in existing:
                continue
            fh.write(f"\n- slug: {slug}\n")
            fh.write("  source_type: candidates\n")
            fh.write(f"  url: {yaml_scalar(url)}\n")
            fh.write(f"  authority: {yaml_scalar(e.get('authority', ''))}\n")
            fh.write(f"  format: {yaml_scalar(e.get('format', ''))}\n")
            fh.write(f"  covers: {e.get('covers', ['mayor', 'councillor'])}\n")
            fh.write(f"  notes: {yaml_scalar(e.get('notes', '2026 municipal election candidate roster'))}\n")
            fh.write(f"  last_confirmed: {date}\n")
            added += 1
    return f"{added} appended" if added else "already present, skipped"


def is_roster_source(e):
    """True if this sources.yaml entry is a roster we actually extract rows from.

    Discovery sometimes records neighbouring artifacts from the same official
    endpoint family — a withdrawal register, a school-board trustee list — as
    context. They are real official sources but not candidate rosters, so
    caching them under source_type: candidates would hand a later run a source
    that yields no mayor/council rows.
    """
    if (e.get("source_type") or "candidates") != "candidates":
        return False
    covers = {str(c).strip().lower() for c in (e.get("covers") or [])}
    if not covers & {"mayor", "councillor", "council"}:
        return False
    # Match on the path only. Query strings legitimately carry these words —
    # Mississauga's vendor roster endpoint ends in "&schoolcode=" while being
    # the mayor+council roster itself.
    path = (e.get("url") or "").lower().split("?", 1)[0]
    # Only the final path segment names the artifact. Matching the whole URL
    # produced false rejections: Sudbury's roster sits under a
    # ".../municipal-schoolboard-elections/..." path, and Mississauga's vendor
    # endpoint carries a "schoolcode" parameter.
    leaf = path.rstrip("/").rsplit("/", 1)[-1]
    if re.search(r"withdraw|trustee", leaf):
        return False
    # Archive mirrors are a fetch workaround, not a source of record. Caching a
    # Wayback snapshot would hand the next run a frozen copy of the roster.
    if re.search(r"web\.archive\.org|archive\.today|webcache\.googleusercontent", path):
        return False
    return True


def yaml_scalar(v):
    # Collapse to a single line: discovery notes arrive as folded multi-line
    # scalars, and re-emitting the newlines leaves a dangling quote line.
    v = " ".join(("" if v is None else str(v)).split())
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


def collect_sources(doc):
    out = []

    def walk(o):
        if isinstance(o, dict):
            if "url" in o and ("source_type" in o or "status" in o or "origin" in o):
                out.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(doc)
    return out


# --------------------------------------------------------------------------
# Stage 8 - export
# --------------------------------------------------------------------------

def export(slug):
    import psycopg2
    from psycopg2.extras import execute_values
    from dotenv import load_dotenv

    load_dotenv(p(".env"))
    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        raise SystemExit("REFUSED: SUPABASE_DB_URL not set in .env")

    path = p("data", slug, "raw_candidates.csv")
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if header != HEADER:
            raise SystemExit(f"REFUSED: header gate — {header} != {HEADER}. Nothing written.")
        rows = [r for r in reader]

    uuids = [r[0].strip() for r in rows]
    if any(not u for u in uuids):
        raise SystemExit("REFUSED: blank uuid in canonical file. Nothing written.")
    if len(set(uuids)) != len(uuids):
        raise SystemExit("REFUSED: duplicate uuid in canonical file. Nothing written.")

    values = [tuple((c.strip() or None) if isinstance(c, str) else c for c in r) for r in rows]

    conn = psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM jurisdictions WHERE slug = %s", (slug,))
                if not cur.fetchone():
                    raise SystemExit(
                        f"REFUSED: jurisdiction {slug} not present in Supabase. "
                        "Run the incumbent export for it first. Nothing written.")

                cur.execute("SELECT uuid FROM raw_candidates WHERE jurisdiction_slug = %s", (slug,))
                before = {str(r[0]) for r in cur.fetchall()}

                cols = ", ".join(HEADER)
                updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in HEADER if c != "uuid")
                execute_values(
                    cur,
                    f"INSERT INTO raw_candidates ({cols}) VALUES %s "
                    f"ON CONFLICT (uuid) DO UPDATE SET {updates}",
                    values,
                )

                incoming = set(uuids)
                cur.execute(
                    "SELECT uuid, first_name, last_name FROM raw_candidates "
                    "WHERE jurisdiction_slug = %s AND uuid <> ALL(%s::uuid[])",
                    (slug, list(incoming)),
                )
                stale = [(str(a), f"{b} {c}") for a, b, c in cur.fetchall()]
    finally:
        conn.close()

    inserted = len(incoming - before)
    updated = len(incoming & before)
    return {"inserted": inserted, "updated": updated, "rows": len(rows), "stale": stale}


# --------------------------------------------------------------------------

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_export = "--no-export" not in sys.argv
    if len(args) != 2:
        raise SystemExit(__doc__)
    run_id, slug = args

    c = consolidate(run_id, slug)
    print(f"[5/8] consolidation: {c['input_rows']} in -> {c['output_rows']} out, "
          f"{len(c['duplicates_collapsed'])} collapsed")
    for d in c["duplicates_collapsed"]:
        if d["type"] == "conflicting":
            print(f"      ! CONFLICTING dup {d['uuid']} kept={d['kept']}")

    v = validate(run_id, slug)
    s = v["_stats"]
    print(f"[6/8] validation: {v['overall'].upper()} — {v['blocking_failures']} blocking, "
          f"{v['row_failures']} row failures")
    print(f"      rows {s['rows']} (role {s['role']}, district {s['district']}) · "
          f"wards {s['wards']}/{s['expected']} · email {s['email']}/{s['rows']} · "
          f"phone {s['phone']}/{s['rows']} · roster {s['roster_status']}")
    for chk, det in v["_blocking"]:
        print(f"      BLOCKING [{chk}] {det}")
    seen_kinds = {}
    for chk, nm, lb, det in v["_rowfails"]:
        seen_kinds[chk] = seen_kinds.get(chk, 0) + 1
    if seen_kinds:
        print("      row failure kinds: " + ", ".join(f"{k}={n}" for k, n in sorted(seen_kinds.items())))
    for chk, nm, lb, det in v["_rowfails"]:
        if chk in ("district_join", "scope_consistency", "enum", "uuid_present"):
            print(f"      ROW [{chk}] {nm} — {lb} — {det}")

    w = write_canonical(run_id, slug)
    print(f"[7/8] writer: {w['mode']} — {w['rows']} rows -> data/{slug}/raw_candidates.csv"
          + (f" (archived {w['archived']})" if w["archived"] else ""))
    print(f"      registry: {w['registry']}")

    if not do_export:
        print("[8/8] export: skipped (--no-export)")
        return
    e = export(slug)
    print(f"[8/8] export: {e['inserted']} inserted, {e['updated']} updated "
          f"({e['rows']} rows in file)")
    print(f"      stale in DB (NOT deleted): {len(e['stale'])}"
          + (" — " + ", ".join(f"{n} [{u[:8]}]" for u, n in e["stale"][:10]) if e["stale"] else ""))


if __name__ == "__main__":
    main()
