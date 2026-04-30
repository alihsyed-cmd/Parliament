"use client";

/**
 * Modal showing full details for a cabinet member or representative.
 *
 * Uses shadcn/ui Dialog under the hood, which handles:
 *   - Focus trap (Tab cycles within modal)
 *   - Focus return (focus goes back to the trigger when closed)
 *   - Escape to close
 *   - Click outside to close
 *   - aria-modal and aria-labelledby semantics
 *
 * Renders nothing if `member` is null. Caller controls open state by
 * passing/clearing the member prop.
 */

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import type { LeadershipMember, Representative } from "@/lib/types";

type Person = LeadershipMember | Representative;

type RepresentativeModalProps = {
  member: Person | null;
  onClose: () => void;
};

export function RepresentativeModal({ member, onClose }: RepresentativeModalProps) {
  const open = member !== null;

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose(); }}>
      <DialogContent>
        {member && (
          <>
            <DialogHeader>
              <DialogTitle>{member.name}</DialogTitle>
              <DialogDescription>{member.role}</DialogDescription>
            </DialogHeader>

            {member.photo_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={member.photo_url}
                alt={`Photo of ${member.name}`}
                className="w-32 h-32 rounded-md object-cover"
                onError={(e) => { e.currentTarget.style.display = "none"; }}
              />
            )}

            <dl className="space-y-2 text-sm">
              {member.party && (
                <div>
                  <dt className="font-medium inline">Party: </dt>
                  <dd className="inline">{member.party}</dd>
                </div>
              )}
              {member.email && (
                <div>
                  <dt className="font-medium inline">Email: </dt>
                  <dd className="inline">
                    <a href={`mailto:${member.email}`} className="text-primary underline">
                      {member.email}
                    </a>
                  </dd>
                </div>
              )}
              {member.phone && (
                <div>
                  <dt className="font-medium inline">Phone: </dt>
                  <dd className="inline">
                    <a href={`tel:${member.phone}`} className="text-primary underline">
                      {member.phone}
                    </a>
                  </dd>
                </div>
              )}
              {member.website && (
                <div>
                  <dt className="font-medium inline">Website: </dt>
                  <dd className="inline">
                    <a
                      href={member.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary underline"
                    >
                      Official page
                    </a>
                  </dd>
                </div>
              )}
            </dl>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
