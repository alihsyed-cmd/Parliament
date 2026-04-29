/**
 * TypeScript types mirroring the Parliament API /lookup response.
 * Source of truth: scripts/api.py and scripts/adapters/ward_based.py.
 *
 * If the API response shape changes, update this file and the
 * compiler will tell you every component that needs adjustment.
 */

export type Language = "en" | "fr";

export type LocalizedString = {
  en: string;
  fr?: string;
};

export type RoleLabels = {
  en: { singular: string; plural: string };
  fr?: { singular: string; plural: string };
};

export type Governance = {
  type: string;
  district_term: LocalizedString;
  rep_role_labels: RoleLabels;
  partisan: boolean;
  rep_count_expected: number;
  election_cycle_years: number;
  max_term_years?: number;
  has_mayor?: boolean;
};

/** Federal/provincial cabinet members and PM/Premier/Mayor. */
export type LeadershipMember = {
  name: string;
  role: string;
  party?: string;
  photo_url?: string;
  email?: string;
  phone?: string;
  website?: string;
};

/** A user's elected representative at one level. */
export type Representative = {
  name: string;
  role: string;
  party?: string;
  photo_url?: string;
  email?: string;
  phone?: string;
  website?: string;
  riding?: string;
  ward?: string;
  elected?: string;
  next_election?: string;
};

export type LevelResult = {
  governance: Governance | null;
  leadership: LeadershipMember[];
  representatives: Representative[];
};

export type LookupResponse = {
  postal_code: string;
  language: Language;
  coordinates: { lat: number; lon: number };
  results: {
    federal?: LevelResult;
    provincial?: LevelResult;
    municipal?: LevelResult;
  };
};

export type LookupError = {
  error: string;
};
