// lib/candidate-types.ts — candidate/claim contract (api.parliamentapp.ca, task 4).

export type VideoStatus = "none" | "processing" | "ready" | "failed";
export type ClaimStatus = "unclaimed" | "claimed";

/** A row as exported from `raw_candidates`. */
export interface CandidateRow {
  uuid: string;
  jurisdiction_slug: string;   // real format: ca_on_ajax
  district_id: string;
  district_name: string;
  role_scope: "district" | "role";
  /** null for jurisdiction-wide candidates (mayoral + at-large are indistinguishable). */
  office: string | null;
  first_name: string;
  last_name: string;
  /**
   * Outreach only, and absent from every voter-facing API response — the public
   * read endpoints select an allowlist that omits both columns server-side.
   * Optional so the compiler refuses any attempt to render a value the server
   * never sends.
   */
  email?: string;
  phone?: string;
}

/** GET /candidates/<uuid>/claim */
export interface ClaimInfo {
  candidate_uuid: string;
  name: string;
  office: string | null;
  jurisdiction: string;
  jurisdiction_slug: string;
  district: string;
  claimable: boolean;
  masked_hint: string | null;
  claim_status: ClaimStatus;
}

/** GET /candidates/<uuid>/portal (session-guarded) */
export interface PortalInfo {
  name: string;
  office: string | null;
  jurisdiction: string;
  district: string;
  website: string | null;
  has_video: boolean;
  video_status: VideoStatus;
  /** true + has_video = replacement encoding; the old video is still live. */
  pending: boolean;
  thumbnail_url: string | null;
}

/** POST /claim/exchange */
export interface ExchangeResult {
  candidate_uuid: string;
  name: string;
}

/** What a voter-facing surface knows about a submission. */
export interface Submission {
  website?: string;
  video_uid?: string;
  video_status?: VideoStatus;
  pending?: boolean;
}

export interface Race {
  key: string;
  path: string;
  jurisdiction_slug: string;
  office: string | null;
  district_name: string;
  title: string;
  candidates: CandidateRow[];
}
