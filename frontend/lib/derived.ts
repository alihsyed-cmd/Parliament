// lib/derived.ts — client-side derivations the API doesn't ship.

import type {
  ApiPolitician, Politician, PartyClass,
  Level, LevelName, LookupResponse, JurisdictionResponse,
} from "./types";

const HONORIFICS =
  /^(the\s+)?(rt\.?\s+)?(right\s+)?(hon\.?|dr\.?|mr\.?|ms\.?|mrs\.?|mx\.?|sir|dame)\s+/i;

export function getInitials(fullName: string): string {
  if (!fullName) return "?";
  const cleaned = fullName.replace(HONORIFICS, "").trim();
  const parts = cleaned.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

const PARTY_MAP: [RegExp, PartyClass][] = [
  [/\bliberal|parti libéral/i, "lib"],
  [/\bprogressive conservative|\bpc\b/i, "con"],
  [/\bconservative|conservateur/i, "con"],
  [/\bndp\b|new democrat|néo-démocrate/i, "ndp"],
  [/\bbloc|québécois/i, "bloc"],
  [/\bgreen|parti vert/i, "green"],
  [/people'?s party|\bppc\b/i, "ppc"],
  [/\bcaq|coalition avenir/i, "con"],
  [/united conservative|\bucp\b/i, "con"],
  [/saskatchewan party/i, "con"],
];

export function getPartyClass(partyName: string): PartyClass {
  if (!partyName) return "none";
  for (const [re, slug] of PARTY_MAP) if (re.test(partyName)) return slug;
  return "ind";
}

export function enrichPolitician(p: ApiPolitician | null): Politician | null {
  if (!p) return null;
  return { ...p, initials: getInitials(p.full_name), party_class: getPartyClass(p.party_name) };
}

export function dedupeByUuid(list: Politician[]): Politician[] {
  const byUuid = new Map<string, Politician>();
  for (const p of list) {
    const key = p.uuid || p.slug || p.full_name;
    const existing = byUuid.get(key);
    if (existing) {
      const roles = existing.roles ?? [existing.specific_title].filter(Boolean);
      if (p.specific_title && !roles.includes(p.specific_title)) roles.push(p.specific_title);
      existing.roles = roles;
    } else {
      byUuid.set(key, { ...p, roles: p.specific_title ? [p.specific_title] : [] });
    }
  }
  return [...byUuid.values()];
}

function enrichLevelArrays<T extends {
  executive: ApiPolitician | null;
  representatives: ApiPolitician[];
  cabinet: ApiPolitician[];
  other_leadership: ApiPolitician[];
}>(src: T) {
  return {
    executive: enrichPolitician(src.executive),
    representatives: (src.representatives ?? []).map((p) => enrichPolitician(p)!),
    cabinet: dedupeByUuid((src.cabinet ?? []).map((p) => enrichPolitician(p)!)),
    other_leadership: dedupeByUuid((src.other_leadership ?? []).map((p) => enrichPolitician(p)!)),
  };
}

const EXPECTED_LEVELS: LevelName[] = ["municipal", "provincial", "federal"];

const GAP_NAME: Record<LevelName, string> = {
  municipal: "Your municipality",
  provincial: "Your province",
  federal: "Canada",
};

export function normalizeLookup(resp: LookupResponse): LookupResponse {
  const byLevel = new Map<string, Level>();
  for (const lvl of resp.levels ?? []) {
    byLevel.set(lvl.level, { ...lvl, ...enrichLevelArrays(lvl) });
  }
  const levels: Level[] = EXPECTED_LEVELS.map((level) =>
    byLevel.get(level) ?? {
      level,
      jurisdiction: { slug: "", name: GAP_NAME[level], level, governance: null },
      executive: null,
      representatives: [],
      cabinet: [],
      other_leadership: [],
      _gap: true,
    }
  );
  return { ...resp, levels };
}

export function normalizeJurisdiction(resp: JurisdictionResponse): JurisdictionResponse {
  return { ...resp, ...enrichLevelArrays(resp) };
}

export function photoSrc(p: { photo_url?: string }): string | null {
  const u = p.photo_url?.trim();
  if (!u) return null;
  return u;
}
