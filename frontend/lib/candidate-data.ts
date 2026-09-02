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
  // ── Toronto, Ward 10 (matches the sample postal-code lookup) ──
  ward("c-to-w10-01", "ca_on_toronto", "10", "Ward 10 · Spadina–Fort York", "Renée", "Beaulieu", "r.beaulieu@example.ca"),
  ward("c-to-w10-02", "ca_on_toronto", "10", "Ward 10 · Spadina–Fort York", "Amara", "Eze", "a.eze@example.ca"),
  ward("c-to-w10-03", "ca_on_toronto", "10", "Ward 10 · Spadina–Fort York", "Hana", "Okada"),
  ward("c-to-w10-04", "ca_on_toronto", "10", "Ward 10 · Spadina–Fort York", "Diego", "Salas", "d.salas@example.ca"),
  ward("c-to-w10-05", "ca_on_toronto", "10", "Ward 10 · Spadina–Fort York", "Marc", "Tremblay", "m.tremblay@example.ca"),
  ward("c-to-w10-06", "ca_on_toronto", "10", "Ward 10 · Spadina–Fort York", "Yusuf", "Warsame", "y.warsame@example.ca"),

  // ── Toronto, citywide (mayoral — office is null) ──
  citywide("c-to-my-01", "ca_on_toronto", "Olivia", "Khan", "o.khan@example.ca"),
  citywide("c-to-my-02", "ca_on_toronto", "Elias", "Rosenthal", "e.rosenthal@example.ca"),
  citywide("c-to-my-03", "ca_on_toronto", "Devika", "Menon"),

  // ── Guelph, Ward 4 ──
  ward("c-gu-w4-01", "ca_on_guelph", "gu-4", "Ward 4", "Aisha", "Bello", "a.bello@example.ca"),
  ward("c-gu-w4-02", "ca_on_guelph", "gu-4", "Ward 4", "Daniela", "Costa", "d.costa@example.ca"),
  ward("c-gu-w4-03", "ca_on_guelph", "gu-4", "Ward 4", "Marcus", "Costa"),
  ward("c-gu-w4-04", "ca_on_guelph", "gu-4", "Ward 4", "Priya", "Dhaliwal", "p.dhaliwal@example.ca"),
  ward("c-gu-w4-05", "ca_on_guelph", "gu-4", "Ward 4", "Jonah", "Ferreira", "j.ferreira@example.ca"),
  ward("c-gu-w4-06", "ca_on_guelph", "gu-4", "Ward 4", "Marcus", "Ilesanmi", "m.ilesanmi@example.ca"),
  ward("c-gu-w4-07", "ca_on_guelph", "gu-4", "Ward 4", "Sana", "Khan"),
  ward("c-gu-w4-08", "ca_on_guelph", "gu-4", "Ward 4", "Priya", "Nandakumar", "p.nandakumar@example.ca"),
  ward("c-gu-w4-09", "ca_on_guelph", "gu-4", "Ward 4", "Owen", "Tremblay", "o.tremblay@example.ca"),

  // ── Guelph, Ward 5 ──
  ward("c-gu-w5-01", "ca_on_guelph", "gu-5", "Ward 5", "Grace", "Adeyemi", "g.adeyemi@example.ca"),
  ward("c-gu-w5-02", "ca_on_guelph", "gu-5", "Ward 5", "Cathy", "Downer", "c.downer@example.ca"),
  ward("c-gu-w5-03", "ca_on_guelph", "gu-5", "Ward 5", "Leah", "Mostowich"),
  ward("c-gu-w5-04", "ca_on_guelph", "gu-5", "Ward 5", "Devon", "Ricci", "d.ricci@example.ca"),

  // ── Guelph, citywide ──
  citywide("c-gu-my-01", "ca_on_guelph", "Cam", "Guthrie", "c.guthrie@example.ca"),
  citywide("c-gu-my-02", "ca_on_guelph", "Nadia", "Karam", "n.karam@example.ca"),
  citywide("c-gu-my-03", "ca_on_guelph", "Robert", "Nkemelu"),
  citywide("c-gu-my-04", "ca_on_guelph", "Simone", "Vachon", "s.vachon@example.ca"),
];

/** Empty = every candidate renders unclaimed, which is the true state until the
 *  gate opens. Shape mirrors GET /candidates/<uuid>/portal. */
export const CANDIDATE_SUBMISSIONS: Record<string, Submission> = {};

export const MUNICIPALITY_NAME: Record<string, string> = {
  ca_on_toronto: "Toronto",
  ca_on_guelph: "Guelph",
  ca_on_ajax: "Ajax",
};
