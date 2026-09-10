// lib/types.ts — Parliament API contract (mirrors the live /lookup, /jurisdiction, /representative responses)

// The API's own level vocabulary. "territorial" is a first-class level for
// Yukon, the Northwest Territories and Nunavut; it occupies the same slot as
// "provincial" in the three-level display but keeps its own label.
export type LevelName = "municipal" | "provincial" | "territorial" | "federal";

/** The display slot a level occupies: territories sit in the provincial row. */
export type LevelSlot = "municipal" | "provincial" | "federal";

export type PartyClass =
  | "lib" | "con" | "ndp" | "bloc" | "green" | "ppc"
  | "npp" | "ind" | "none";

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
  date_elected: string;
  next_election: string;
  phone: string;
  email: string;
  contact_form_url?: string | null;
  website: string;
  photo_url: string;
  source_url?: string;
  last_verified?: string;
}

export interface Politician extends ApiPolitician {
  initials: string;
  party_class: PartyClass;
  roles?: string[];
}

export interface Governance {
  governance_type: string;
  partisan: boolean;
  district_term: string;
  role_label_singular: string;
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
  governance: Governance | null;
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

/** One row of GET /jurisdictions — every jurisdiction the API actually serves. */
export interface JurisdictionIndexEntry {
  slug: string;
  name: string;
  level: LevelName;
  country_code: string;
  province_code: string;
}

export interface JurisdictionsResponse {
  lang: string;
  jurisdictions: JurisdictionIndexEntry[];
}
