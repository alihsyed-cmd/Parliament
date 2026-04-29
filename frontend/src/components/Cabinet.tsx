"use client";

/**
 * Collapsible cabinet/leadership list with progressive disclosure.
 *
 * Behavior:
 *   - Sorted: head-of-government first (PM/Premier/Mayor), then alphabetical by name
 *   - Initially collapsed; "Show cabinet" expands to first 5
 *   - "Show more" reveals up to 20 total
 *   - "Show all" reveals everything
 *   - Clicking a member name calls onMemberClick (parent renders modal)
 *
 * Focus management:
 *   - On first expand: focus moves to the first member row
 *   - On collapse: focus returns to the toggle button
 *   - "Show more" / "Show all" do NOT move focus (user is already reading)
 */

import { useRef, useState } from "react";
import type { LeadershipMember } from "@/lib/types";
import { CabinetMemberRow } from "./CabinetMemberRow";
import { Button } from "@/components/ui/button";

const HEAD_OF_GOVERNMENT_ROLES = new Set([
  "Prime Minister",
  "Premier ministre",
  "Premier",
  "Mayor",
]);

function sortMembers(members: LeadershipMember[]): LeadershipMember[] {
  return [...members].sort((a, b) => {
    const aHead = HEAD_OF_GOVERNMENT_ROLES.has(a.role);
    const bHead = HEAD_OF_GOVERNMENT_ROLES.has(b.role);
    if (aHead && !bHead) return -1;
    if (!aHead && bHead) return 1;
    return a.name.localeCompare(b.name);
  });
}

type CabinetProps = {
  level: "provincial" | "federal";
  members: LeadershipMember[];
  onMemberClick: (member: LeadershipMember) => void;
};

const LEVEL_LABEL: Record<CabinetProps["level"], string> = {
  provincial: "provincial cabinet",
  federal: "federal cabinet",
};

const CABINET_EXPLANATION =
  "Cabinet ministers are elected representatives the head of government has appointed to lead specific areas of policy, like health, finance, or transportation. They make day-to-day decisions about how government runs.";

export function Cabinet({ level, members, onMemberClick }: CabinetProps) {
  const [visibleCount, setVisibleCount] = useState(0);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const firstMemberRef = useRef<HTMLDivElement>(null);

  const sorted = sortMembers(members);
  const total = sorted.length;
  const expanded = visibleCount > 0;

  function toggle() {
    if (expanded) {
      setVisibleCount(0);
      // Focus returns to toggle button after collapse
      requestAnimationFrame(() => toggleRef.current?.focus());
    } else {
      setVisibleCount(Math.min(5, total));
      // Focus moves to first member after expand
      requestAnimationFrame(() => {
        const firstButton = firstMemberRef.current?.querySelector("button");
        firstButton?.focus();
      });
    }
  }

  function showMore() {
    setVisibleCount(Math.min(20, total));
  }

  function showAll() {
    setVisibleCount(total);
  }

  if (total === 0) return null;

  return (
    <section className="mt-6">
      <Button
        ref={toggleRef}
        variant="outline"
        onClick={toggle}
        aria-expanded={expanded}
        aria-controls={`${level}-cabinet-list`}
      >
        {expanded ? `Hide ${LEVEL_LABEL[level]}` : `Show ${LEVEL_LABEL[level]} (${total} members)`}
      </Button>

      {expanded && (
        <div id={`${level}-cabinet-list`} className="mt-4">
          <p className="text-sm text-gray-700 mb-4 max-w-prose">
            {CABINET_EXPLANATION}
          </p>

          <div ref={firstMemberRef} className="grid gap-1 md:grid-cols-2">
            {sorted.slice(0, visibleCount).map((member) => (
              <CabinetMemberRow
                key={`${member.name}-${member.role}`}
                member={member}
                onClick={onMemberClick}
              />
            ))}
          </div>

          <div className="mt-4 flex gap-2">
            {visibleCount < 20 && total > 5 && (
              <Button variant="ghost" onClick={showMore}>
                Show more
              </Button>
            )}
            {visibleCount < total && total > 20 && (
              <Button variant="ghost" onClick={showAll}>
                Show all ({total})
              </Button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
