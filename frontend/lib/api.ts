// lib/api.ts — single surface for talking to the Parliament API.

import type {
  LookupResponse, JurisdictionResponse, RepresentativeResponse, ErrorKind,
} from "./types";
import { normalizeLookup, normalizeJurisdiction, enrichPolitician } from "./derived";

const API_BASE =
  process.env.NEXT_PUBLIC_PARLIAMENT_API ??
  "https://parliament-api-staging.onrender.com";

export class ApiError extends Error {
  status: number;
  kind: ErrorKind;
  constructor(message: string, status: number, kind: ErrorKind) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
  }
}

export function normalizePostalCode(input: string): string {
  return (input || "").toUpperCase().replace(/[\s-]/g, "");
}

export function isValidPostalCode(input: string): boolean {
  return /^[A-Z]\d[A-Z]\d[A-Z]\d$/.test(normalizePostalCode(input));
}

export function formatPostalCode(input: string): string {
  const r = normalizePostalCode(input);
  return r.length === 6 ? `${r.slice(0, 3)} ${r.slice(3)}` : r;
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      signal,
    });
  } catch (e) {
    throw new ApiError((e as Error).message || "Network error", 0, "network");
  }
  const body = await res.json().catch(() => ({} as Record<string, unknown>));
  if (!res.ok) {
    const kind: ErrorKind =
      res.status === 400 ? "invalid" : res.status === 404 ? "not_found" : "server";
    throw new ApiError((body as { error?: string }).error || res.statusText, res.status, kind);
  }
  return body as T;
}

export const api = {
  base: API_BASE,
  isValidPostalCode,
  normalizePostalCode,
  formatPostalCode,

  async lookup(postal: string, signal?: AbortSignal): Promise<LookupResponse> {
    const code = normalizePostalCode(postal);
    if (!isValidPostalCode(code)) throw new ApiError("Invalid postal code", 400, "invalid");
    const resp = await getJson<LookupResponse>(
      `/lookup?postal_code=${encodeURIComponent(code)}`, signal,
    );
    return normalizeLookup(resp);
  },

  async jurisdiction(slug: string, signal?: AbortSignal): Promise<JurisdictionResponse> {
    const resp = await getJson<JurisdictionResponse>(
      `/jurisdiction/${encodeURIComponent(slug)}`, signal,
    );
    return normalizeJurisdiction(resp);
  },

  async representative(jurSlug: string, slug: string, signal?: AbortSignal): Promise<RepresentativeResponse> {
    const resp = await getJson<RepresentativeResponse>(
      `/representative/${encodeURIComponent(jurSlug)}/${encodeURIComponent(slug)}`, signal,
    );
    return { ...resp, representative: enrichPolitician(resp.representative)! };
  },

  async health(): Promise<{ status: string; database?: string; jurisdictions_loaded?: number }> {
    return getJson("/health");
  },
};
