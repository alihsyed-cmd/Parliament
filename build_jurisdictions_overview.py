#!/usr/bin/env python3
"""Build a human-readable, grouped overview spreadsheet from data/jurisdictions.csv."""
import csv
from datetime import date

SRC = "data/jurisdictions.csv"
OUT = "jurisdictions_overview.csv"

# Statistics Canada 2021 Census populations (official, single consistent source).
POP = {
    # Federal
    "ca_federal": 36991981,
    # Provinces & territories
    "ca_on": 14223942, "ca_qc": 8501833, "ca_bc": 5000879, "ca_ab": 4262635,
    "ca_mb": 1342153, "ca_sk": 1132505, "ca_ns": 969383, "ca_nb": 775610,
    "ca_nl": 510550, "ca_pe": 154331, "ca_nt": 41070, "ca_yt": 40232, "ca_nu": 36858,
    # Municipalities
    "ca_on_toronto": 2794356, "ca_on_ottawa": 1017449, "ca_on_mississauga": 717961,
    "ca_on_brampton": 656480, "ca_on_hamilton": 569353, "ca_on_london": 422324,
    "ca_on_markham": 338503, "ca_on_vaughan": 323103, "ca_on_kitchener": 256885,
    "ca_on_windsor": 229660, "ca_on_oakville": 213759, "ca_on_richmond_hill": 202022,
    "ca_on_burlington": 186948, "ca_on_oshawa": 175383, "ca_on_greater_sudbury": 166004,
    "ca_on_barrie": 147829, "ca_on_guelph": 143740, "ca_on_whitby": 138501,
    "ca_on_cambridge": 138479, "ca_on_st_catharines": 136803, "ca_on_milton": 132979,
    "ca_on_kingston": 132485, "ca_on_ajax": 126666, "ca_on_waterloo": 121436,
    "ca_on_thunder_bay": 108843, "ca_on_brantford": 104688, "ca_on_chatham_kent": 103988,
    "ca_on_peterborough": 83651, "ca_on_norfolk_county": 67490, "ca_on_brant": 39474,
    "ca_qc_quebec_city": 549459,
    "ca_ab_calgary": 1306784, "ca_ab_edmonton": 1010899,
    "ca_bc_vancouver": 662248, "ca_bc_victoria": 91867,
    "ca_sk_regina": 226404,
    "ca_mb_winnipeg": 749607,
}

PROV_NAME = {
    "ON": "Ontario", "QC": "Quebec", "BC": "British Columbia", "AB": "Alberta",
    "MB": "Manitoba", "SK": "Saskatchewan", "NS": "Nova Scotia", "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador", "PE": "Prince Edward Island",
    "NT": "Northwest Territories", "YT": "Yukon", "NU": "Nunavut",
}

GOV = {
    "ward_based": "Ward / district-based",
    "at_large": "At-large",
    "consensus": "Consensus (non-partisan)",
}


def fpop(slug):
    p = POP.get(slug)
    return str(p) if p else ""


def main():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
    by_slug = {r["slug"]: r for r in rows}

    federal = [r for r in rows if r["level"] == "federal"]
    prov = [r for r in rows if r["level"] in ("provincial", "territorial")]
    muni = [r for r in rows if r["level"] == "municipal"]

    prov.sort(key=lambda r: r["name"])
    muni.sort(key=lambda r: (PROV_NAME.get(r["province_code"], r["province_code"]), r["name"]))

    header = ["Jurisdiction", "Level", "Districts/Wards", "District Type",
              "Population (2021 Census)", "Governance", "Last Election", "Next Election"]

    def line(r):
        return [
            r["name"],
            r["level"].capitalize(),
            r["expected_district_count"],
            r["role_label_plural"],
            fpop(r["slug"]),
            GOV.get(r["governance_type"], r["governance_type"]),
            r["last_election"],
            r["next_election"] or "TBD",
        ]

    out = []
    out.append([f"REGISTERED JURISDICTIONS — high-level overview (generated {date.today().isoformat()})"])
    out.append([f"{len(rows)} jurisdictions registered  |  Population figures: Statistics Canada 2021 Census"])
    out.append([])

    # Federal
    out.append(["=== FEDERAL ==="])
    out.append(header)
    for r in federal:
        out.append(line(r))
    out.append([])

    # Provinces & territories
    out.append(["=== PROVINCES & TERRITORIES ==="])
    out.append(header)
    for r in prov:
        out.append(line(r))
    out.append([])

    # Municipalities grouped by province
    out.append(["=== MUNICIPALITIES (grouped by province/territory) ==="])
    current = None
    for r in muni:
        pn = PROV_NAME.get(r["province_code"], r["province_code"])
        if pn != current:
            current = pn
            out.append([])
            out.append([f"-- {pn} ({sum(1 for m in muni if m['province_code']==r['province_code'])} municipalities) --"])
            out.append(header)
        out.append(line(r))

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for row in out:
            w.writerow(row)

    print(f"Wrote {OUT}: {len(rows)} jurisdictions "
          f"({len(federal)} federal, {len(prov)} provincial/territorial, {len(muni)} municipal)")
    missing = [r["slug"] for r in rows if not POP.get(r["slug"])]
    print("Missing population:", missing or "none")


if __name__ == "__main__":
    main()
