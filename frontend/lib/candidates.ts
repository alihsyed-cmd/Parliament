// lib/candidates.ts — candidate/claim API surface + derivation helpers.
//
// Every session-guarded call sends `credentials: "include"`. The cookie is
// httpOnly and scoped to .parliamentapp.ca; without the flag it is silently
// omitted and the call 401s.

import React from "react";
import type {
  CandidateRow, ClaimInfo, PortalInfo, ExchangeResult, Submission, Race,
} from "./candidate-types";
import { MUNICIPALITY_NAME } from "./candidate-data";

export const CANDIDATE_API_BASE =
  process.env.NEXT_PUBLIC_CANDIDATE_API ?? "https://api.parliamentapp.ca";

/** Mirrors the backend env var. While false the claim path must terminate in
 *  the "not open yet" screen — the API returns 503 / sends nothing. */
export const SUBMISSIONS_ENABLED =
  process.env.NEXT_PUBLIC_SUBMISSIONS_ENABLED === "true";

/** Publish-sequence gate: vacant profiles ship first with the claim link
 *  hidden, then this flips true in the SAME change that opens the backend
 *  gate. Revealing it earlier means a candidate passes the challenge and never
 *  receives an email. */
export const CLAIM_AFFORDANCE_VISIBLE =
  process.env.NEXT_PUBLIC_CLAIM_AFFORDANCE === "true";

export const ELECTION_DATE = "2026-10-26";

export class CandidateApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "CandidateApiError";
    this.status = status;
  }
}

async function call<T>(path: string, init?: RequestInit & { auth?: boolean }): Promise<T> {
  const { auth, ...rest } = init ?? {};
  let res: Response;
  try {
    res = await fetch(`${CANDIDATE_API_BASE}${path}`, {
      ...rest,
      credentials: auth ? "include" : "same-origin",
      headers: { "Content-Type": "application/json", ...(rest.headers ?? {}) },
    });
  } catch (e) {
    throw new CandidateApiError((e as Error).message || "Network error", 0);
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new CandidateApiError(
      (body as { error?: string }).error || res.statusText, res.status,
    );
  }
  return body as T;
}

export const candidateApi = {
  /** Public. Selects which claim screen to render. */
  claimInfo(uuid: string) {
    return call<ClaimInfo>(`/candidates/${encodeURIComponent(uuid)}/claim`);
  },

  /** Always resolves 200 — match, no match, rate-limited and unknown are
   *  indistinguishable by design. Never branch on the response. */
  requestClaim(uuid: string, email: string) {
    return call<{ status: string }>(`/candidates/${encodeURIComponent(uuid)}/claim`, {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  /** Same-site POST from /claim/<token>. Sets the session cookie. Does not
   *  consume the token — it stays valid through election day. Any 400 is an
   *  undifferentiated invalid_token. */
  exchange(token: string) {
    return call<ExchangeResult>("/claim/exchange", {
      method: "POST",
      body: JSON.stringify({ token }),
      auth: true,
    });
  },

  contact(payload: {
    candidate_uuid?: string | null;
    name: string; email: string; message: string;
    /** Honeypot — rendered hidden, must always be empty. */
    website: string;
  }) {
    return call<{ status: string }>("/contact", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  portal(uuid: string) {
    return call<PortalInfo>(`/candidates/${encodeURIComponent(uuid)}/portal`, { auth: true });
  },

  /** Requesting a second URL while one is pending replaces the first. */
  uploadUrl(uuid: string) {
    return call<{ upload_url: string; video_uid: string }>(
      `/candidates/${encodeURIComponent(uuid)}/upload-url`,
      { method: "POST", auth: true },
    );
  },

  /** Bytes go browser → Cloudflare. Never through our API, no credentials.
   *  The 60s cap is enforced at the edge, so no client-side duration check. */
  async uploadToCloudflare(uploadUrl: string, file: File) {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(uploadUrl, { method: "POST", body: form });
    if (!res.ok) throw new CandidateApiError("Upload failed", res.status);
  },

  /** Publishes immediately, independent of video status. */
  saveWebsite(uuid: string, website: string) {
    return call<PortalInfo>(`/candidates/${encodeURIComponent(uuid)}`, {
      method: "PATCH",
      body: JSON.stringify({ website }),
      auth: true,
    });
  },

  /** Deletes from Cloudflare, not merely unlinked. Website and claim survive. */
  removeVideo(uuid: string) {
    return call<PortalInfo>(`/candidates/${encodeURIComponent(uuid)}/video`, {
      method: "DELETE",
      auth: true,
    });
  },
};

/* ─────────── live reads ───────────
 * Race listings and candidate profiles come from the public read endpoints.
 * Name search has no endpoint yet, so searchCandidates() still resolves against
 * whatever is cached and returns nothing until one exists — it only feeds the
 * claim page, which is gated shut regardless.
 *
 * Responses land in a module-level cache so the synchronous derivation helpers
 * below keep working unchanged. Screens trigger a load with useRaces(); every
 * other lookup reads the warm cache. */

const raceCache = new Map<string, Race[]>();
const candidateCache = new Map<string, CandidateRow>();
const jurisdictionNames = new Map<string, string>();

interface RaceResponse {
  jurisdiction: string;
  jurisdiction_slug: string;
  races: {
    key: string; office: string | null; role_scope: "district" | "role";
    district_id: string; district_name: string; title: string;
    candidates: {
      uuid: string; first_name: string; last_name: string;
      submission: Submission | null;
    }[];
  }[];
}

function cacheCandidate(row: CandidateRow) {
  candidateCache.set(row.uuid, row);
  return row;
}

/** GET /jurisdictions/<slug>/races — every race in one municipality, with its
 *  certified candidates. Public: no credentials, by design. */
export async function fetchRaces(slug: string): Promise<Race[]> {
  const cached = raceCache.get(slug);
  if (cached) return cached;

  const data = await call<RaceResponse>(
    `/jurisdictions/${encodeURIComponent(slug)}/races`,
  );
  jurisdictionNames.set(slug, data.jurisdiction);

  const races: Race[] = data.races.map((r) => {
    const candidates: CandidateRow[] = r.candidates.map((c) => cacheCandidate({
      uuid: c.uuid,
      jurisdiction_slug: slug,
      district_id: r.district_id,
      district_name: r.district_name,
      role_scope: r.role_scope,
      office: r.office,
      first_name: c.first_name,
      last_name: c.last_name,
      submission: c.submission,
    }));
    return {
      key: r.key,
      path: candidates.length ? racePath(candidates[0]) : `/on/${slug}`,
      jurisdiction_slug: slug,
      office: r.office,
      district_id: r.district_id,
      district_name: r.district_name,
      title: r.title,
      candidates,
    };
  });

  raceCache.set(slug, races);
  return races;
}

/** GET /candidates/<uuid> — one certified candidate. Public: no credentials. */
export async function fetchCandidate(uuid: string): Promise<CandidateRow> {
  const cached = candidateCache.get(uuid);
  if (cached) return cached;

  const c = await call<{
    uuid: string; jurisdiction_slug: string; jurisdiction: string;
    district_id: string; district_name: string; role_scope: "district" | "role";
    office: string | null; first_name: string; last_name: string;
    submission: Submission | null;
  }>(`/candidates/${encodeURIComponent(uuid)}`);

  jurisdictionNames.set(c.jurisdiction_slug, c.jurisdiction);
  return cacheCandidate({
    uuid: c.uuid,
    jurisdiction_slug: c.jurisdiction_slug,
    district_id: c.district_id,
    district_name: c.district_name,
    role_scope: c.role_scope,
    office: c.office,
    first_name: c.first_name,
    last_name: c.last_name,
    submission: c.submission,
  });
}

/**
 * Load a municipality's races. Returns `null` while in flight so a screen can
 * tell "still loading" from "no races", which otherwise render the same and
 * would flash a wrong count.
 */
export function useRaces(slug: string | null | undefined) {
  const [races, setRaces] = React.useState<Race[] | null>(
    slug ? raceCache.get(slug) ?? null : [],
  );

  React.useEffect(() => {
    if (!slug) { setRaces([]); return; }
    const warm = raceCache.get(slug);
    if (warm) { setRaces(warm); return; }

    let live = true;
    setRaces(null);
    fetchRaces(slug)
      .then((r) => { if (live) setRaces(r); })
      // A municipality with no roster 404s; that is "no races", not an error
      // worth surfacing to a voter mid-lookup.
      .catch(() => { if (live) setRaces([]); });
    return () => { live = false; };
  }, [slug]);

  return races;
}

export const streamThumb = (uid: string) =>
  `https://videodelivery.net/${uid}/thumbnails/thumbnail.jpg?time=3s`;

export function municipalityName(slug: string) {
  // Server-supplied name first: it covers every registered municipality, where
  // the static map only ever held a handful.
  return jurisdictionNames.get(slug) ?? MUNICIPALITY_NAME[slug] ?? slug;
}

/** `office` is null for mayoral and at-large candidates. Screens fall back to
 *  the jurisdiction alone rather than inventing a label. */
export function officeLabel(row: Pick<CandidateRow, "office">) {
  return row.office || null;
}

export function officeLine(row: CandidateRow) {
  const muni = municipalityName(row.jurisdiction_slug);
  const where = row.district_name || officeLabel(row);
  return where ? `${where}, ${muni}` : muni;
}

export function fullName(row: Pick<CandidateRow, "first_name" | "last_name">) {
  return `${row.first_name} ${row.last_name}`;
}

export function initialsOf(row: Pick<CandidateRow, "first_name" | "last_name">) {
  return `${(row.first_name || " ")[0]}${(row.last_name || " ")[0]}`.toUpperCase();
}

export function submissionFor(row: CandidateRow): Submission | null {
  // Decided server-side: present only when publicly visible. A mid-encode or
  // unpublished video arrives as null, identical to having none.
  return row.submission ?? null;
}

/** Hard mask: first char of local part, first char of domain. */
export function maskEmail(email: string) {
  if (!email) return "";
  const [local, domain] = email.split("@");
  if (!domain) return "";
  return `${local[0]}•••@${domain[0]}•••${domain.slice(domain.indexOf("."))}`;
}

export function raceKey(row: CandidateRow) {
  return row.role_scope === "district"
    ? `${row.jurisdiction_slug}|${row.office || "district"}|${row.district_id}`
    : `${row.jurisdiction_slug}|${row.office || "citywide"}|`;
}

export function racePath(row: CandidateRow) {
  const base = `/on/${row.jurisdiction_slug}`;
  if (row.office === "mayor") return `${base}/mayor`;
  if (row.role_scope === "district") {
    return `${base}/${(row.district_name || "").toLowerCase().replace(/\s+/g, "-")}`;
  }
  return `${base}/citywide`;
}

/** Grid list: pure alphabetical by surname. */
export function sortAlphabetical(rows: CandidateRow[]) {
  return [...rows].sort(
    (a, b) => a.last_name.localeCompare(b.last_name) || a.first_name.localeCompare(b.first_name),
  );
}

/** Feed view: two silent groups (video first, then rest), each A–Z. Written
 *  for the deferred feed race view; unused while the grid ships. */
export function sortVideoFirst(rows: CandidateRow[]) {
  const withVideo = sortAlphabetical(rows.filter((r) => submissionFor(r)?.video_uid));
  const rest = sortAlphabetical(rows.filter((r) => !submissionFor(r)?.video_uid));
  return [...withVideo, ...rest];
}

/** Every race currently loaded, across all fetched municipalities. */
export function allRaces(): Race[] {
  return [...raceCache.values()].flat();
}

/** Warm-cache read. Screens call useRaces(slug) to populate it first. */
export function racesFor(slug: string) {
  return raceCache.get(slug) ?? [];
}

export function raceByKey(key: string) {
  return allRaces().find((r) => r.key === key) ?? null;
}

export function candidateByUuid(uuid: string) {
  return candidateCache.get(uuid) ?? null;
}

/**
 * Name search. There is no /candidates/search endpoint yet, so this resolves
 * against whatever the cache already holds rather than the full roster — which
 * means it finds nothing until a municipality has been loaded. It feeds only
 * the claim page, and that path is gated shut, so an empty result is the
 * correct outcome rather than a broken one.
 */
export function searchCandidates(q: string) {
  const t = q.trim().toLowerCase();
  if (!t) return [];
  return [...candidateCache.values()]
    .filter((r) => fullName(r).toLowerCase().includes(t))
    .slice(0, 8);
}

export function daysToElection() {
  return Math.max(0, Math.ceil((+new Date(ELECTION_DATE) - Date.now()) / 86400000));
}
