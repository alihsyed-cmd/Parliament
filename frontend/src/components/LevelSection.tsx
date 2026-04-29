"use client";

/**
 * One section of the lookup results page (municipal, provincial, or federal).
 *
 * Composes:
 *   - Section heading
 *   - User's representative (RepresentativeCard) — if present
 *   - Cabinet (federal/provincial) or single mayor card (municipal)
 *   - Coverage gap message — if no data
 *
 * Receives a level identifier and the LevelResult from the API.
 * Owns the modal state for cabinet member detail views, since the modal
 * scope is per-section (clicking a federal minister and a provincial
 * minister are independent interactions).
 */

import { useState } from "react";
import type { LevelResult, LeadershipMember } from "@/lib/types";
import { RepresentativeCard } from "./RepresentativeCard";
import { Cabinet } from "./Cabinet";
import { CoverageGap } from "./CoverageGap";
import { RepresentativeModal } from "./RepresentativeModal";

const LEVEL_HEADING: Record<LevelSectionProps["level"], string> = {
  municipal: "Municipal",
  provincial: "Provincial",
  federal: "Federal",
};

type LevelSectionProps = {
  level: "municipal" | "provincial" | "federal";
  data: LevelResult | undefined;
};

export function LevelSection({ level, data }: LevelSectionProps) {
  const [selectedMember, setSelectedMember] = useState<LeadershipMember | null>(null);

  // No data for this level — show coverage gap
  if (!data || !data.governance) {
    return (
      <section aria-labelledby={`${level}-heading`}>
        <h2 id={`${level}-heading`} className="text-xl font-semibold mb-4">
          {LEVEL_HEADING[level]}
        </h2>
        <CoverageGap level={level} />
      </section>
    );
  }

  const userRep = data.representatives[0];
  const showParty = data.governance.partisan;

  // Municipal: single mayor (if present), no cabinet concept
  // Federal/Provincial: cabinet of multiple members
  const isMunicipal = level === "municipal";
  const mayor = isMunicipal ? data.leadership[0] : null;

  return (
    <section aria-labelledby={`${level}-heading`}>
      <h2 id={`${level}-heading`} className="text-xl font-semibold mb-4">
        {LEVEL_HEADING[level]}
      </h2>

      {userRep && (
        <RepresentativeCard
          representative={userRep}
          showParty={showParty}
        />
      )}

      {mayor && (
        <div className="mt-6">
          <h3 className="text-lg font-medium mb-3">Mayor</h3>
          <RepresentativeCard
            representative={mayor}
            showParty={false}
          />
        </div>
      )}

      {!isMunicipal && data.leadership.length > 0 && (
        <Cabinet
          level={level as "provincial" | "federal"}
          members={data.leadership}
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
