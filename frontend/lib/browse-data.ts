"use client";

// lib/browse-data.ts — the browse tree and the place-search index.
//
// Everything here comes from GET /jurisdictions at runtime. It used to be a
// hand-written list with a `covered` flag, which is why live jurisdictions read
// "Coming soon": the flag was a guess frozen at authoring time. A jurisdiction
// is in this index if and only if the API serves it, so there is nothing left
// to guess and no place for invented officials to creep back in.

import React from "react";
import { api } from "./api";
import type { JurisdictionIndexEntry, LevelSlot } from "./types";

export interface Place {
  kind: LevelSlot;
  name: string;
  slug: string;
  entry: JurisdictionIndexEntry;
}

/** Which browse section a level belongs in. Territories share the provincial
 *  section; the row itself still carries its own level and label. */
export function sectionOf(level: string): LevelSlot {
  if (level === "municipal") return "municipal";
  if (level === "federal") return "federal";
  return "provincial";
}

// ── the index ────────────────────────────────────────────────────────────────

// One fetch per page load, shared by the browse tree and the entry-screen
// search. A failure clears the cache so the next mount retries.
let indexPromise: Promise<JurisdictionIndexEntry[]> | null = null;

export function loadJurisdictions(): Promise<JurisdictionIndexEntry[]> {
  if (!indexPromise) {
    indexPromise = api.jurisdictions()
      .then((r) => r.jurisdictions ?? [])
      .catch((e) => { indexPromise = null; throw e; });
  }
  return indexPromise;
}

export interface BrowseGroups {
  /** Municipalities grouped by province, provinces in alphabetical order. */
  municipalByProvince: { code: string; name: string; items: JurisdictionIndexEntry[] }[];
  municipalCount: number;
  /** Provinces and territories, alphabetical. */
  provincial: JurisdictionIndexEntry[];
  /** Canada, or null if the federal jurisdiction is not loaded yet. */
  federal: JurisdictionIndexEntry[];
}

const byName = (a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name);

export function groupJurisdictions(entries: JurisdictionIndexEntry[]): BrowseGroups {
  const provincial = entries.filter((j) => sectionOf(j.level) === "provincial").sort(byName);
  const federal = entries.filter((j) => j.level === "federal").sort(byName);
  const municipal = entries.filter((j) => j.level === "municipal");

  // The province rows name themselves, so the group headings need no lookup
  // table: "ON" becomes "Ontario" because Ontario is in the same index.
  const provinceName = new Map(provincial.map((p) => [p.province_code, p.name]));
  const groups = new Map<string, JurisdictionIndexEntry[]>();
  for (const m of municipal) {
    const code = m.province_code || "";
    (groups.get(code) ?? groups.set(code, []).get(code)!).push(m);
  }

  const municipalByProvince = [...groups.entries()]
    .map(([code, items]) => ({
      code,
      name: provinceName.get(code) ?? code,
      items: items.sort(byName),
    }))
    .sort(byName);

  return { municipalByProvince, municipalCount: municipal.length, provincial, federal };
}

// ── hooks ────────────────────────────────────────────────────────────────────

export function useJurisdictions() {
  const [data, setData] = React.useState<JurisdictionIndexEntry[] | null>(null);
  const [error, setError] = React.useState<Error | null>(null);

  React.useEffect(() => {
    let live = true;
    loadJurisdictions()
      .then((j) => { if (live) setData(j); })
      .catch((e: Error) => { if (live) setError(e); });
    return () => { live = false; };
  }, []);

  return { data, error, loading: !data && !error };
}

/** The place-search index: every jurisdiction, searchable by name. */
export function usePlaces(): Place[] {
  const { data } = useJurisdictions();
  return React.useMemo(
    () => (data ?? []).map((entry) => ({
      kind: sectionOf(entry.level), name: entry.name, slug: entry.slug, entry,
    })).sort(byName),
    [data],
  );
}
