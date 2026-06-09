#!/usr/bin/env python3
"""Build a human-readable data-gaps report across all registered jurisdictions.

Scans every data/<slug>/politicians.csv and reports, per jurisdiction, which
must-fill contact fields (phone, email, website, photo_url) are empty — both as
fill-rate summaries and as a per-person detail listing. Read-only and offline;
run it after a tranche of jurisdictions has been registered or backfilled.

Usage:  python3 build_data_gaps_report.py
Output: DATA_GAPS.md  (overwritten each run)
"""
import csv
import glob
import os
from datetime import date

JURISDICTIONS = "data/jurisdictions.csv"
OUT = "DATA_GAPS.md"

# Contact-completeness fields we track as gaps. (Identity/role fields are
# effectively always present and are not interesting to a gaps report.)
GAP_FIELDS = ["phone", "email", "website", "photo_url"]


def juris_names():
    """slug -> human-readable name, from jurisdictions.csv (best-effort)."""
    names = {}
    if os.path.exists(JURISDICTIONS):
        with open(JURISDICTIONS, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                names[r["slug"]] = r.get("name", r["slug"])
    return names


def scan():
    names = juris_names()
    report = []  # list of per-jurisdiction dicts
    for f in sorted(glob.glob("data/*/politicians.csv")):
        slug = f.split(os.sep)[1]
        with open(f, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        counts = {fld: 0 for fld in GAP_FIELDS}
        detail = []  # (name, role/title, [missing fields])
        for r in rows:
            missing = [fld for fld in GAP_FIELDS if not (r.get(fld) or "").strip()]
            for fld in missing:
                counts[fld] += 1
            if missing:
                nm = f"{r.get('first_name','')} {r.get('last_name','')}".strip()
                role = f"{r.get('standard_role','')}/{r.get('specific_title','')}".strip("/")
                detail.append((nm, role, missing))
        report.append({
            "slug": slug,
            "name": names.get(slug, slug),
            "rows": len(rows),
            "counts": counts,
            "detail": detail,
        })
    return report


def pct(filled, total):
    return f"{filled}/{total}" + (f" ({100*filled//total}%)" if total else "")


def main():
    report = scan()
    total_rows = sum(j["rows"] for j in report)
    totals = {fld: sum(j["counts"][fld] for j in report) for fld in GAP_FIELDS}

    out = []
    out.append("# Parliament — Data Gaps Report")
    out.append("")
    out.append(f"_Generated {date.today().isoformat()} · {len(report)} jurisdictions · {total_rows} politician rows_")
    out.append("")
    out.append("Gaps are **empty** must-fill contact fields. An empty cell may be a genuine "
               "absence at the official source (no action possible) or an extraction gap "
               "(worth a backfill). `email` may legitimately hold a published address *or* an "
               "official contact-form URL; only a truly empty cell counts as a gap.")
    out.append("")

    # ---- Overall ----
    out.append("## Overall")
    out.append("")
    out.append("| Field | Filled | Empty |")
    out.append("|---|---|---|")
    for fld in GAP_FIELDS:
        empty = totals[fld]
        out.append(f"| `{fld}` | {pct(total_rows - empty, total_rows)} | {empty} |")
    out.append("")

    # ---- Per-jurisdiction summary (only those with at least one gap) ----
    with_gaps = [j for j in report if any(j["counts"].values())]
    clean = [j for j in report if not any(j["counts"].values())]
    out.append("## Per-jurisdiction summary")
    out.append("")
    out.append("Jurisdictions with no contact-field gaps are listed at the end.")
    out.append("")
    out.append("| Jurisdiction | Slug | Rows | phone | email | website | photo_url |")
    out.append("|---|---|---|---|---|---|---|")
    for j in sorted(with_gaps, key=lambda x: -sum(x["counts"].values())):
        c = j["counts"]; n = j["rows"]
        out.append(f"| {j['name']} | `{j['slug']}` | {n} | "
                   f"{c['phone']} | {c['email']} | {c['website']} | {c['photo_url']} |")
    out.append("")
    if clean:
        out.append("**No gaps:** " + ", ".join(f"`{j['slug']}`" for j in clean))
        out.append("")

    # ---- Detail ----
    out.append("## Detail")
    out.append("")
    for j in sorted(with_gaps, key=lambda x: x["slug"]):
        out.append(f"### {j['name']} (`{j['slug']}`)")
        out.append("")
        for nm, role, missing in j["detail"]:
            out.append(f"- **{nm}** — {role} — missing: {', '.join(missing)}")
        out.append("")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")

    print(f"Wrote {OUT}: {len(report)} jurisdictions, {total_rows} rows")
    for fld in GAP_FIELDS:
        print(f"  {fld}: {totals[fld]} empty")


if __name__ == "__main__":
    main()
