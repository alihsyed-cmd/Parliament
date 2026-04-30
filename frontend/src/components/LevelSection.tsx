"use client";

/**
 * One section of the lookup results page (municipal, provincial, federal).
 *
 * Composes:
 *   - Section heading: "Your <role>" derived from API governance data
 *   - User's representative card (RepresentativeCard) — primary
 *   - Executive leader card (ExecutiveCard) — Mayor/Premier/PM, secondary
 *   - Cabinet (federal/provincial only)
 *   - Coverage gap message — if no data
 *
 * The user's rep + executive leader sit side by side on desktop, stacked
 * on mobile. The user's rep comes first in the DOM (so it appears first
 * on mobile and is read first by screen readers).
 */

import { useState } from "react";
import type { LevelResult, LeadershipMember, Language } from "@/lib/types";
import { RepresentativeCard } from "./RepresentativeCard";
import { ExecutiveCard } from "./ExecutiveCard";
import { Cabinet } from "./Cabinet";
import { CoverageGap } from "./CoverageGap";
import { RepresentativeModal } from "./RepresentativeModal";

const HEAD_OF_GOVERNMENT_ROLES = new Set([
  "Prime Minister",
  "Premier ministre",
  "Premier",
  "Mayor",
]);

type LevelSectionProps = {
  level: "municipal" | "provincial" | "federal";
  data: LevelResult | undefined;
  lang?: Language;
};

function buildHeading(
  role: { en: { singular: string }; fr?: { singular: string } } | undefined,
  lang: Language,
  fallback: string
): string {
  if (!role) return fallback;
  const label = role[lang]?.singular ?? role.en.singular;
  return lang === "fr" ? `Votre ${label}` : `Your ${label}`;
}

const FALLBACK_HEADING: Record<LevelSectionProps["level"], string> = {
  municipal: "Municipal",
  provincial: "Provincial",
  federal: "Federal",
};

export function LevelSection({ level, data, lang = "en" }: LevelSectionProps) {
  const [selectedMember, setSelectedMember] = useState<LeadershipMember | null>(null);

  // No data → coverage gap
  if (!data || !data.governance) {
    return (
      <section aria-labelledby={`${level}-heading`}>
        <h2 id={`${level}-heading`} className="text-2xl font-semibold mb-6">
          {FALLBACK_HEADING[level]}
        </h2>
        <CoverageGap level={level} />
      </section>
    );
  }

  const userRep = data.representatives[0];
  const showParty = data.governance.partisan;
  const heading = buildHeading(
    data.governance.rep_role_labels,
    lang,
    FALLBACK_HEADING[level]
  );

  // Find the head-of-government leader (Mayor/Premier/PM) for this level
  const executive = data.leadership.find((m) =>
    HEAD_OF_GOVERNMENT_ROLES.has(m.role)
  );

  // Cabinet excludes the executive (they get their own card)
  const cabinetMembers = data.leadership.filter(
    (m) => !HEAD_OF_GOVERNMENT_ROLES.has(m.role)
  );

  return (
    <section aria-labelledby={`${level}-heading`}>
      <h2 id={`${level}-heading`} className="text-2xl font-semibold mb-6">
        {heading}
      </h2>

      <div className="grid gap-6 md:grid-cols-2 items-start">
        {userRep && (
          <RepresentativeCard
            representative={userRep}
            showParty={showParty}
          />
        )}
        {executive && <ExecutiveCard leader={executive} />}
      </div>

      {level !== "municipal" && cabinetMembers.length > 0 && (
        <Cabinet
          level={level as "provincial" | "federal"}
          members={cabinetMembers}
          onMemberClick={setSelectedMember}
        />
      )}

      <RepresentativeModal
        member={selectedMember}
        onClose={() => setSelectedMember(null)}
      />
    </section>
  );
}
