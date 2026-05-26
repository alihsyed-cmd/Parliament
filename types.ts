/**
 * Parliament API types — redesigned contract (v2 data model).
 *
 * Source of truth shared between the API rewrite and the frontend rewrite.
 * If the API shape changes, change it HERE first; the compiler then flags
 * every component that needs updating.
 *
 * Data model summary (see docs/schemas.md):
 *   - Three tables: jurisdictions, districts, politicians.
 *   - Plain-text fields (no bilingual maps). English only for now;
 *     the `lang` field on responses is reserved for future i18n so the
 *     envelope won't change when translations return.
 *   - Every politician carries `standard_role`
 *     ("representative" | "executive" | "cabinet" | "misc"), which is the
 *     SINGLE key the frontend uses to categorize. No string-matching on
 *     titles anywhere.
 *
 * Key shape decisions (and the awkwardness in the old contract they fix):
 *   1. `levels` is an ARRAY (was a {federal,provincial,municipal} object).
 *      Future-proof for regional/borough/school-board levels.
 *   2. `executive` is a SINGLE object separate from `cabinet[]` (was buried
 *      as leadership[0] / filtered out by a hardcoded role-name Set).
 *   3. `representatives` is a TRUE ARRAY rendered with .map() (was assumed
 *      single via representatives[0]). Brampton wards have two councillors.
 *   4. District is `district_id` + `district_name` (was riding|ward split).
 *      `governance.district_term` supplies the label ("Riding"/"Ward").
 *   5. Dates are RAW; the frontend resolves the fallback chain (see
 *      resolveNextElection / resolveElected helpers at the bottom).
 */

/* ─────────────────────────── Enums ─────────────────────────── */

export type Lang = "en"; // reserved for future "fr"

export type JurisdictionLevel = "federal" | "provincial" | "municipal";

/** The single categorization key. Mirrors politicians.csv `standard_role`. */
export type StandardRole = "representative" | "executive" | "cabinet" | "misc";

export type GovernanceType =
  | "ward_based"
  | "at_large"
  | "nested_borough"
  | "consensus";

/* ────────────────────────── Politician ─────────────────────── */

/**
 * One politician in one role. The API composes `full_name` and sets
 * `display_title` so the frontend never concatenates or branches on titles.
 *
 * district_id / district_name are populated only for role_scope "district"
 * (i.e. standard_role "representative"); empty/omitted for role-scoped
 * politicians (executive, cabinet, misc).
 */
export type Politician = {
  uuid: string;
  /** URL slug for /representative/<jur>/<slug>. Server-generated. */
  slug: string;

  /** Server-composed from honorific + first + last. Ready to print. */
  full_name: string;

  /** The single categorization key. */
  standard_role: StandardRole;
  /** Full official title, e.g. "Member of Parliament", "Premier",
   *  "Minister of Finance", "Leader of the Official Opposition". */
  specific_title: string;
  /** What the UI prints. Equals specific_title; named separately so the
   *  display contract is explicit and stable. */
  display_title: string;

  /** Empty string when non-partisan (governance.partisan === false) or
   *  independent. Never null. */
  party_name: string;

  /** District context — present for representatives, empty otherwise. */
  district_id: string;
  district_name: string;

  /** Raw dates (YYYY-MM-DD) or empty string. Frontend resolves fallbacks. */
  date_elected: string;
  next_election: string;

  /** Contact — any may be empty string. */
  phone: string;
  email: string;
  website: string;
  photo_url: string;
};

/* ────────────────────────── Governance ─────────────────────── */

/**
 * Per-jurisdiction metadata. `null` at a level means COVERAGE GAP — the
 * frontend renders the "Coverage coming soon" state for that level.
 *
 * The four election fields are the FALLBACK inputs for date display; the
 * frontend prefers a politician's own date_elected/next_election and falls
 * back to these. See helpers at the bottom of this file.
 */
export type Governance = {
  governance_type: GovernanceType;
  partisan: boolean;

  /** Label for a district at this level: "Riding", "Ward", "Borough". */
  district_term: string;
  role_label_singular: string; // "MP", "MPP", "Councillor"
  role_label_plural: string; // "MPs", "MPPs", "Councillors"

  /** 1-3 sentence plain-English description of how this gov't is organized. */
  governance_summary: string;

  /** Date-fallback inputs (raw). */
  last_election: string; // YYYY-MM-DD or ""
  next_election: string; // YYYY-MM-DD or "" (only meaningful if election_date_set)
  election_date_set: boolean; // true => next_election is a hard scheduled date
  term_duration_years: number; // used to estimate next election when not set
};

export type JurisdictionSummary = {
  slug: string;
  name: string;
  level: JurisdictionLevel;
  country_code: string;
  province_code: string; // "" for federal
};

/* ─────────────────────── /lookup response ──────────────────── */

/**
 * One level the user belongs to (their municipality, province, country).
 * Always present for all three known levels; `governance: null` signals a
 * coverage gap rather than omitting the entry, preserving the frontend's
 * clean "is governance null?" check.
 */
export type LevelResult = {
  level: JurisdictionLevel;
  jurisdiction: {
    slug: string;
    name: string;
    level: JurisdictionLevel;
    governance: Governance | null; // null => coverage gap
  };

  /** The user's district representative(s). 0..N — Brampton wards = 2.
   *  Render ALL of them (.map), never [0]. */
  representatives: Politician[];

  /** The single head of government (Mayor/Premier/PM), or null.
   *  standard_role === "executive". */
  executive: Politician | null;

  /** Cabinet ministers. EXCLUDES the executive already (no filtering needed).
   *  standard_role === "cabinet". */
  cabinet: Politician[];

  /** Party leaders, opposition leaders, critics, Speakers, etc.
   *  standard_role === "misc". Empty for most municipalities. */
  other_leadership: Politician[];
};

export type LookupResponse = {
  postal_code: string;
  lang: Lang;
  coordinates: { lat: number; lon: number };
  /** Ordered municipal → provincial → federal. */
  levels: LevelResult[];
};

export type ApiErrorBody = {
  error: string;
};

/* ─────────────────────── Browse endpoints ──────────────────── */

/** GET /jurisdictions */
export type JurisdictionsIndexResponse = {
  lang: Lang;
  jurisdictions: JurisdictionSummary[];
};

/**
 * GET /jurisdiction/<slug>
 * Same per-level shape as a LevelResult entry, for one jurisdiction's full
 * roster. Roster page groups by standard_role: representatives in the big
 * filterable list; executive + cabinet + other_leadership under "Leadership".
 */
export type JurisdictionDetailResponse = {
  lang: Lang;
  jurisdiction: JurisdictionSummary & { governance: Governance | null };
  representatives: Politician[];
  executive: Politician | null;
  cabinet: Politician[];
  other_leadership: Politician[];
};

/**
 * GET /representative/<jurisdiction_slug>/<slug>
 * The one endpoint that exposes audit metadata (source_url, last_verified)
 * — usable for a "data last verified on…" trust signal.
 * `representations` lists every role the person holds in this jurisdiction,
 * so a multi-role person (Ford: MPP + Premier + minister + party leader)
 * shows all of them on their detail page.
 */
export type RepresentationLink = {
  standard_role: StandardRole;
  specific_title: string;
  district_id: string;
  district_name: string;
};

export type RepresentativeDetailResponse = {
  lang: Lang;
  representative: Politician & {
    source_url: string;
    last_verified: string; // YYYY-MM-DD
  };
  jurisdiction: JurisdictionSummary;
  representations: RepresentationLink[];
};

/* ─────────────── Date-fallback display helpers ─────────────── */
/**
 * The API sends raw dates; these resolve the display value. Kept in the
 * types file so both ends agree on the contract, but they are pure frontend
 * presentation logic — the API must NOT pre-compute these.
 */

/** Estimate next election as last_election + term_duration_years. */
function estimateNextElection(
  lastElection: string,
  termYears: number
): string | null {
  if (!lastElection || !termYears) return null;
  const d = new Date(lastElection);
  const t = d.getTime();
  if (t !== t) return null; // NaN check without Number.isNaN (lib-independent)
  d.setFullYear(d.getFullYear() + termYears);
  return d.toISOString().slice(0, 10);
}

/**
 * Resolution order:
 *   1. politician.next_election (if present)
 *   2. governance.next_election (if election_date_set)
 *   3. estimate(last_election + term_duration_years)
 *   4. null (show nothing)
 */
export function resolveNextElection(
  politician: Pick<Politician, "next_election">,
  governance: Governance | null
): string | null {
  if (politician.next_election) return politician.next_election;
  if (!governance) return null;
  if (governance.election_date_set && governance.next_election) {
    return governance.next_election;
  }
  return estimateNextElection(
    governance.last_election,
    governance.term_duration_years
  );
}

/**
 * Resolution order:
 *   1. politician.date_elected (if present)
 *   2. governance.last_election
 *   3. null
 */
export function resolveElected(
  politician: Pick<Politician, "date_elected">,
  governance: Governance | null
): string | null {
  if (politician.date_elected) return politician.date_elected;
  if (governance?.last_election) return governance.last_election;
  return null;
}
