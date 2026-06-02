// lib/types.ts — Parliament API contract (mirrors the live /lookup, /jurisdiction, /representative responses)

export type LevelName = "municipal" | "provincial" | "federal";

/** A stable color slug derived client-side from party_name (see lib/derived.ts). */
export type PartyClass =
  | "lib" | "con" | "ndp" | "bloc" | "green" | "ppc"
  | "npp" | "ind" | "none";

/** Raw politician as returned by the API. */
export interface ApiPolitician {
  uuid: string;
  slug: string;
  full_name: string;
  standard_role: "executive" | "representative" | "cabinet" | "misc" | string;
  specific_title: string;
  display_title: string;
  party_name: string;
  district_id: string;
  district_name: string;
  date_elected: string;   // ISO date or ""
  next_election: string;  // ISO date or ""
  phone: string;
  email: string;
  website: string;
  photo_url: string;
  // present only on /representative/<j>/<slug>
  source_url?: string;
  last_verified?: string;
}

/** Politician enriched with client-derived fields. */
export interface Politician extends ApiPolitician {
  initials: string;
  party_class: PartyClass;
  /** When several cabinet rows share a uuid, their specific_titles are merged here. */
  roles?: string[];
}

export interface Governance {
  governance_type: string;            // e.g. "ward_based"
  partisan: boolean;
  district_term: string;              // "Ward" | "Riding"
  role_label_singular: string;        // "Councillor" | "MPP" | "MP"
  role_label_plural: string;
  governance_summary: string;
  last_election: string;
  next_election: string;
  election_date_set: boolean;
  term_duration_years: number;
}

export interface Jurisdiction {
  slug: string;
  name: string;
  level: LevelName;
  governance: Governance | null;      // null ⇒ coverage gap
  country_code?: string;
  province_code?: string;
}

export interface Level {
  level: LevelName;
  jurisdiction: Jurisdiction;
  executive: Politician | null;
  representatives: Politician[];
  cabinet: Politician[];
  other_leadership: Politician[];
  /** Frontend-only flag: this level was padded in because the API omitted it. */
  _gap?: boolean;
}

export interface LookupResponse {
  postal_code: string;
  lang: string;
  coordinates: { lat: number; lon: number };
  levels: Level[];
}

export interface JurisdictionResponse {
  lang: string;
  jurisdiction: Jurisdiction;
  executive: Politician | null;
  representatives: Politician[];
  cabinet: Politician[];
  other_leadership: Politician[];
}

export interface Representation {
  standard_role: string;
  specific_title: string;
  district_id: string;
  district_name: string;
}

export interface RepresentativeResponse {
  lang: string;
  representative: Politician;
  jurisdiction: Jurisdiction;
  representations: Representation[];
}

export type ErrorKind = "network" | "invalid" | "not_found" | "server";
