// lib/election-context.ts — the few facts that describe a whole election,
// rather than any one jurisdiction's race.
//
// The lookup screen already tells a voter that an election is coming and who is
// on their ballot. What it could not tell them is how big the thing they are
// voting in actually is. These entries carry that: a handful of headline
// figures about the election as a whole, plus the source they came from so a
// reader can go further.
//
// Deliberately a static file, for the same reason wardwatch-beta.ts is one.
// These are published figures about an election, not facts about a
// jurisdiction, so they belong to neither `jurisdictions` nor `districts`, and
// a province-wide count would have to be duplicated across every city row to
// live in either. It also lives under frontend/ because Vercel's Root
// Directory is `frontend` and .vercelignore excludes data/ from the upload.
//
// Every figure below was read off the cited page and is quoted as that page
// states it. Nothing here is computed from our own tables: if our candidate
// count and the association's disagree, the source is what a reader would find
// if they followed the link, so the source is what we print.

import type { LevelName } from "./types";

/** One headline figure. `stat` leads the bullet; `detail` finishes the clause. */
export interface ElectionFact {
  stat: string;
  detail: string;
}

export interface ElectionContext {
  /** Which jurisdictions this election covers. */
  level: LevelName;
  /** Slug prefix the jurisdiction must match — province-scoped, so `ca_on_`. */
  slug_prefix: string;
  /**
   * The election these figures describe, as the confirmed date the API serves.
   * Matching on it is what makes the entry self-expiring: once a jurisdiction's
   * next_election rolls past this day, the entry stops applying on its own and
   * no stale 2026 count can attach itself to a 2030 ballot.
   */
  election_date: string;
  /** One line naming the election, above the figures. */
  headline: string;
  facts: ElectionFact[];
  source: {
    name: string;
    url: string;
    /** When the cited page was published, ISO 8601. */
    published: string;
  };
}

const CONTEXTS: ElectionContext[] = [
  {
    level: "municipal",
    slug_prefix: "ca_on_",
    election_date: "2026-10-26",
    headline: "Ontario is electing its municipal governments on the same day.",
    facts: [
      { stat: "6,663 candidates", detail: "are running for 2,800 elected offices province-wide" },
      { stat: "414 of Ontario's 444 municipalities", detail: "are holding an election" },
      { stat: "4,502 candidates", detail: "have never held the seat they are running for; 2,161 incumbents are running again" },
      { stat: "2,103 candidates", detail: "are women — 32% of the field" },
      { stat: "400 candidates", detail: "were acclaimed without a contest, including 104 heads of council and 19 councils acclaimed in full" },
      { stat: "272 municipalities", detail: "are offering internet voting; 87 are paper-ballot only" },
    ],
    source: {
      name: "Association of Municipalities of Ontario",
      url: "https://www.amo.on.ca/2026-municipal-election-analysis",
      published: "2026-09-09",
    },
  },
];

/**
 * The published context for the election this jurisdiction is holding, or null.
 *
 * `electionDate` must be the jurisdiction's *confirmed* next election date —
 * the caller has already established that an election is actually active. An
 * estimated date must never reach here: it would attach real figures to a day
 * nobody has called.
 *
 * Returns null whenever there is no entry for the election, which is the
 * ordinary case. Callers must then render nothing at all — no heading, no
 * empty state — so a jurisdiction we have no figures for reads exactly as it
 * does today.
 */
export function electionContextFor(
  slug: string | undefined,
  level: LevelName,
  electionDate: string | undefined,
): ElectionContext | null {
  if (!slug || !electionDate) return null;
  return (
    CONTEXTS.find(
      (c) =>
        c.level === level &&
        c.election_date === electionDate &&
        slug.startsWith(c.slug_prefix),
    ) ?? null
  );
}
