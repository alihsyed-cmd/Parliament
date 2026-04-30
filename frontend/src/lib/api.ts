/**
 * Parliament API client.
 *
 * Single entry point for talking to the Flask /lookup endpoint.
 * Components import { lookupPostalCode } and never construct URLs
 * or handle fetch directly.
 */

import type { Language, LookupResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

if (!API_URL) {
  // Fail fast at module load if misconfigured. The error surfaces in the
  // build log on Vercel or on first import in dev — easier to debug than
  // a silent "fetch returned undefined" later.
  throw new Error(
    "NEXT_PUBLIC_API_URL is not set. " +
    "Add it to .env.local (dev) or Vercel project env vars (production)."
  );
}

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Look up representatives for a Canadian postal code.
 *
 * @param postalCode - Six-character postal code, with or without space (e.g., "M3J3R2" or "M3J 3R2").
 * @param lang - Response language ("en" or "fr"). Defaults to "en".
 * @returns Parsed LookupResponse on success.
 * @throws ApiError if the API returns a non-2xx status, with the error message from the server.
 * @throws Error for network failures or invalid JSON.
 */
export async function lookupPostalCode(
  postalCode: string,
  lang: Language = "en"
): Promise<LookupResponse> {
  const normalized = postalCode.replace(/\s+/g, "").toUpperCase();
  const url = `${API_URL}/lookup?postal_code=${encodeURIComponent(normalized)}&lang=${lang}`;

  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    // Cache responses on the Next.js server side. Postal codes don't move,
    // and our backend has its own cache; layering Next.js cache on top
    // means a hot postal code can be served entirely from the edge.
    next: { revalidate: 3600 },
  });

  if (!response.ok) {
    let message = `API request failed with status ${response.status}`;
    try {
      const body = (await response.json()) as { error?: string };
      if (body.error) message = body.error;
    } catch {
      // Response body wasn't JSON. Stick with the default message.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as LookupResponse;
}


/* ─── Browse-flow client functions ──────────────────────────────────── */

import type {
  JurisdictionsIndexResponse,
  JurisdictionDetailResponse,
  RepresentativeDetailResponse,
} from "./types";

/**
 * List all registered jurisdictions, grouped by level on the consumer side.
 */
export async function listJurisdictions(
  lang: Language = "en"
): Promise<JurisdictionsIndexResponse> {
  const url = `${API_URL}/jurisdictions?lang=${lang}`;
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    next: { revalidate: 3600 },
  });
  if (!response.ok) {
    throw new ApiError(`Failed to list jurisdictions: ${response.status}`, response.status);
  }
  return (await response.json()) as JurisdictionsIndexResponse;
}

/**
 * Full roster for one jurisdiction.
 */
export async function getJurisdiction(
  slug: string,
  lang: Language = "en"
): Promise<JurisdictionDetailResponse> {
  const url = `${API_URL}/jurisdiction/${encodeURIComponent(slug)}?lang=${lang}`;
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    next: { revalidate: 3600 },
  });
  if (!response.ok) {
    let message = `Jurisdiction not found: ${slug}`;
    try {
      const body = (await response.json()) as { error?: string };
      if (body.error) message = body.error;
    } catch {}
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as JurisdictionDetailResponse;
}

/**
 * Full details for one representative within a jurisdiction.
 */
export async function getRepresentative(
  jurisdictionSlug: string,
  repSlug: string,
  lang: Language = "en"
): Promise<RepresentativeDetailResponse> {
  const url = `${API_URL}/representative/${encodeURIComponent(jurisdictionSlug)}/${encodeURIComponent(repSlug)}?lang=${lang}`;
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    next: { revalidate: 3600 },
  });
  if (!response.ok) {
    let message = `Representative not found: ${jurisdictionSlug}/${repSlug}`;
    try {
      const body = (await response.json()) as { error?: string };
      if (body.error) message = body.error;
    } catch {}
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as RepresentativeDetailResponse;
}
