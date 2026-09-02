// lib/candidates.ts — candidate/claim API surface + derivation helpers.
//
// Every session-guarded call sends `credentials: "include"`. The cookie is
// httpOnly and scoped to .parliamentapp.ca; without the flag it is silently
// omitted and the call 401s.

import type {
  CandidateRow, ClaimInfo, PortalInfo, ExchangeResult, Submission, Race,
} from "./candidate-types";
import { CANDIDATE_ROWS, CANDIDATE_SUBMISSIONS, MUNICIPALITY_NAME } from "./candidate-data";

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

/* ─────────── derivation (no races table; everything comes off the row) ───────────
 * NOTE: there is no public endpoint yet for race listings, candidate profiles,
 * or name search. Those surfaces read CANDIDATE_ROWS until one exists. */

export const streamThumb = (uid: string) =>
  `https://videodelivery.net/${uid}/thumbnails/thumbnail.jpg?time=3s`;

export function municipalityName(slug: string) {
  return MUNICIPALITY_NAME[slug] ?? slug;
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
  return CANDIDATE_SUBMISSIONS[row.uuid] ?? null;
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

export function allRaces(): Race[] {
  const map = new Map<string, Race>();
  CANDIDATE_ROWS.forEach((row) => {
    const key = raceKey(row);
    if (!map.has(key)) {
      const label = officeLabel(row);
      const muni = municipalityName(row.jurisdiction_slug);
      map.set(key, {
        key,
        path: racePath(row),
        jurisdiction_slug: row.jurisdiction_slug,
        office: row.office,
        district_name: row.district_name,
        title: row.district_name
          ? (label ? `${row.district_name} ${label}` : row.district_name)
          : (label ? `${label} of ${muni}` : `${muni} — citywide`),
        candidates: [],
      });
    }
    map.get(key)!.candidates.push(row);
  });
  return [...map.values()];
}

export function racesFor(slug: string) {
  return allRaces().filter((r) => r.jurisdiction_slug === slug);
}

export function raceByKey(key: string) {
  return allRaces().find((r) => r.key === key) ?? null;
}

export function candidateByUuid(uuid: string) {
  return CANDIDATE_ROWS.find((r) => r.uuid === uuid) ?? null;
}

export function searchCandidates(q: string) {
  const t = q.trim().toLowerCase();
  if (!t) return [];
  return CANDIDATE_ROWS.filter((r) => fullName(r).toLowerCase().includes(t)).slice(0, 8);
}

export function daysToElection() {
  return Math.max(0, Math.ceil((+new Date(ELECTION_DATE) - Date.now()) / 86400000));
}
