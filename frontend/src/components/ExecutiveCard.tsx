"use client";

/**
 * Compact card for the head of government at one level: Mayor, Premier,
 * or Prime Minister. Smaller than RepresentativeCard so the user's own
 * rep retains visual primacy. Click opens detail modal.
 *
 * Renders nothing if the leader is not present (e.g., a province with
 * no equivalent role, though all currently registered jurisdictions
 * have one).
 */

import { useState } from "react";
import type { LeadershipMember } from "@/lib/types";
import { RepresentativeModal } from "./RepresentativeModal";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";

type ExecutiveCardProps = {
  leader: LeadershipMember;
};

export function ExecutiveCard({ leader }: ExecutiveCardProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-left block w-full transition-opacity hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-lg"
        aria-label={`View details for ${leader.name}, ${leader.role}`}
      >
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              {leader.photo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={leader.photo_url}
                  alt=""
                  className="w-14 h-14 rounded-md object-cover flex-shrink-0"
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                    const placeholder = e.currentTarget.nextElementSibling as HTMLElement | null;
                    if (placeholder) placeholder.style.display = "block";
                  }}
                />
              ) : null}
              <div
                className="w-14 h-14 rounded-md bg-muted flex-shrink-0"
                style={leader.photo_url ? { display: "none" } : {}}
                aria-hidden="true"
              />
              <div className="min-w-0">
                <CardTitle className="text-base">{leader.name}</CardTitle>
                <CardDescription>{leader.role}</CardDescription>
              </div>
            </div>
          </CardHeader>
        </Card>
      </button>

      <RepresentativeModal
        member={open ? leader : null}
        onClose={() => setOpen(false)}
      />
    </>
  );
}
