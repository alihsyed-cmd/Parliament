"use client";

import { useState, useMemo, useId } from "react";
import Link from "next/link";
import type { RepresentativeSummary } from "@/lib/types";

type Props = {
  reps: RepresentativeSummary[];
  jurisdictionSlug: string;
  showParty: boolean;
  /** Heading shown above the list, e.g., "Leadership" or "Representatives". */
  heading: string;
};

/**
 * Filterable list of representatives, collapsible by default. Renders as
 * dense text rows in two columns at md+ breakpoint.
 *
 * The filter input lives inside the disclosure body, so it appears only
 * when the section is expanded. This keeps the closed state clean.
 *
 * Filter matches against name, role, district name, and party
 * (case-insensitive substring).
 */
export function RosterFilter({ reps, jurisdictionSlug, showParty, heading }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const headingId = useId();
  const bodyId = useId();

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return reps;
    return reps.filter((r) => {
      const haystack = [
        r.name,
        r.role,
        r.district_name ?? "",
        r.party ?? "",
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [query, reps]);

  return (
    <section aria-labelledby={headingId}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={bodyId}
        className="flex items-center justify-between w-full text-left py-3 border-b border-border focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-md"
      >
        <h2 id={headingId} className="text-2xl font-semibold">
          {heading} ({reps.length})
        </h2>
        <span aria-hidden="true" className="text-2xl text-muted-foreground">
          {open ? "−" : "+"}
        </span>
      </button>

      {open && (
        <div id={bodyId} className="pt-4">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by name, role, or district…"
            aria-label={`Filter ${heading.toLowerCase()}`}
            className="w-full px-4 py-2 border border-border rounded-md bg-card focus:outline-none focus:ring-2 focus:ring-ring mb-4"
          />

          {filtered.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No matches for &ldquo;{query}&rdquo;.
            </p>
          ) : (
            <ul className="grid gap-x-6 md:grid-cols-2 divide-y divide-border md:divide-y-0 border-y border-border md:border-y-0">
              {filtered.map((rep) => {
                const districtLabel =
                  rep.district_external_id &&
                  rep.district_external_id !== rep.district_name
                    ? `Ward ${rep.district_external_id}`
                    : rep.district_name;
                return (
                  <li key={rep.id + "-" + rep.role} className="md:border-b md:border-border">
                    <Link
                      href={`/representative/${jurisdictionSlug}/${rep.slug}`}
                      className="block py-3 px-2 hover:bg-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-md transition-colors"
                    >
                      <div className="font-medium truncate">{rep.name}</div>
                      <div className="text-sm text-muted-foreground truncate">
                        {rep.role}
                        {districtLabel ? ` · ${districtLabel}` : ""}
                        {showParty && rep.party ? ` · ${rep.party}` : ""}
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
