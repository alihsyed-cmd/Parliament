// lib/candidate-data.ts
//
// PLACEHOLDER ROWS, in the real `raw_candidates` shape. Replace CANDIDATE_ROWS
// with a Supabase export and re-key MUNICIPALITY_NAME to match — nothing else
// changes. Slug format is the live one (`ca_on_toronto`), which must equal what
// /lookup returns for that municipality or the ward card silently won't render.
//
// `office` is null for jurisdiction-wide candidates: the column was declined,
// so mayoral and at-large are indistinguishable in the data.
//
// email/phone are outreach-only and never rendered to voters.

import type { CandidateRow, Submission } from "./candidate-types";

const ward = (
  uuid: string, slug: string, district_id: string, district_name: string,
  first_name: string, last_name: string, email = "",
): CandidateRow => ({
  uuid, jurisdiction_slug: slug, district_id, district_name,
  role_scope: "district", office: "Councillor", first_name, last_name, email, phone: "",
});

const citywide = (
  uuid: string, slug: string, first_name: string, last_name: string, email = "",
): CandidateRow => ({
  uuid, jurisdiction_slug: slug, district_id: "", district_name: "",
  role_scope: "role", office: null, first_name, last_name, email, phone: "",
});

export const CANDIDATE_ROWS: CandidateRow[] = [
  // INTENTIONALLY EMPTY. This file previously held invented people (fake names
  // with fake wards). Rendered on a live civic site they read as real certified
  // candidates, which is misinformation — so they must never ship again.
  //
  // Populate ONLY from the certified roster, via the read endpoints or a bulk
  // export of `raw_candidates`. Never hand-write rows.
  //
  // While empty every candidate surface degrades to nothing: the "who's running
  // in your ward" card is withheld, races are unreachable, and name search
  // returns no results. That is the correct state until real data exists.
];

/** Empty = every candidate renders unclaimed, which is the true state until the
 *  gate opens. Shape mirrors GET /candidates/<uuid>/portal. */
export const CANDIDATE_SUBMISSIONS: Record<string, Submission> = {};

export const MUNICIPALITY_NAME: Record<string, string> = {
  ca_on_toronto: "Toronto",
  ca_on_guelph: "Guelph",
  ca_on_ajax: "Ajax",
};
