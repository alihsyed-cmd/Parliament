// lib/wardwatch-beta.ts — SCOPED BETA. Delete this file and its two call sites
// in CandidateScreens.tsx to remove the feature entirely.
//
// An outbound link to each candidate's WardWatch.ca profile, for ONE ward:
// Toronto Ward 17, Don Valley North. WardWatch is a third-party non-partisan
// site covering Toronto's 2026 municipal election; it is not a Parliament
// property and not a government source.
//
// Deliberately a static file rather than a column on `submissions` or
// `raw_candidates`. A one-ward trial should not migrate a table that 1,617
// candidates and every other jurisdiction share, and reverting is a file
// deletion rather than a migration. If the beta generalizes, that is when the
// mapping earns a real home.
//
// It lives under frontend/ because Vercel's Root Directory is `frontend` and
// .vercelignore excludes `data/` from the upload — a mapping in data/ would
// work locally and ship nothing.
//
// Matching was done by hand against wardwatch.ca/ward/17 and every URL below
// was fetched and confirmed to return that candidate's page. All seven Don
// Valley North candidates matched; there is no unmatched case in this ward
// today, but the lookup still returns null for anyone absent.

import type { CandidateRow } from "./candidate-types";

/** The one jurisdiction and ward this beta covers. */
const BETA_SLUG = "ca_on_toronto";
const BETA_DISTRICT_ID = "17";

/**
 * Candidate uuid → WardWatch profile URL.
 *
 * Keyed on uuid, which is deterministic from `<slug>|<first>|<last>`, so these
 * survive the certified-list rerun that re-imports the same people.
 */
const WARDWATCH_URLS: Record<string, string> = {
  // Jeffery Adamson
  "bc5665e6-0036-5ed6-8a24-6670b067f406":
    "https://wardwatch.ca/candidates/jeffery-adamson-councillor-17",
  // Shelley Carroll (incumbent)
  "57a3d1af-36c9-564f-8b06-1a24e019d8dc":
    "https://wardwatch.ca/candidates/shelley-carroll-councillor-17",
  // Jethro Adir Kavod
  "cd875d4f-3f5c-5c28-87d2-fc4ee615085f":
    "https://wardwatch.ca/candidates/jethro-adir-kavod-councillor-17",
  // Hassan Mubarak Noor Mohamed
  "7c4f548b-767a-5c4e-8e65-cece1808087a":
    "https://wardwatch.ca/candidates/hassan-mubarak-noor-mohamed-councillor-17",
  // Roy Samathanam
  "bbe9838a-c7d3-51b7-8b2a-c265cb55028e":
    "https://wardwatch.ca/candidates/roy-samathanam-councillor-17",
  // Hong Xiao
  "cc2e2553-174f-5264-86da-035617d2102d":
    "https://wardwatch.ca/candidates/hong-xiao-councillor-17",
  // Sabrina Zuniga
  "a2577805-88cf-5538-a574-282854ff54ea":
    "https://wardwatch.ca/candidates/sabrina-zuniga-councillor-17",
};

/**
 * The candidate's WardWatch profile URL, or null.
 *
 * Null for every candidate outside Don Valley North and for any Don Valley
 * North candidate without a confirmed match. Callers must render nothing at
 * all on null — no placeholder, no empty state — so an unmatched page reads
 * exactly as it does today.
 *
 * The ward is re-checked rather than trusted to the uuid map alone: a bad key
 * pasted in here can then only ever be inert, never light up another ward.
 */
export function wardWatchUrl(row: CandidateRow): string | null {
  if (row.jurisdiction_slug !== BETA_SLUG) return null;
  if (row.district_id !== BETA_DISTRICT_ID) return null;
  return WARDWATCH_URLS[row.uuid] ?? null;
}
