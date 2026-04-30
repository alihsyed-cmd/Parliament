import { RosterFilter } from "@/components/RosterFilter";
import type { JurisdictionDetailResponse } from "@/lib/types";

type Props = {
  data: JurisdictionDetailResponse;
};

/**
 * Full roster view for one jurisdiction. Server Component — composes
 * the RosterFilter (client) for each section.
 *
 * Two filterable lists: leadership (cabinet, mayor, premier, PM) and
 * representatives (MPs, MPPs, councillors). Either may be empty; we
 * skip empty sections.
 */
export function JurisdictionRoster({ data }: Props) {
  const { jurisdiction, representatives, leadership } = data;
  const showParty = jurisdiction.governance?.partisan ?? false;

  return (
    <main className="min-h-screen px-6 py-12 max-w-3xl mx-auto">
      <header className="mb-12">
        <h1 className="text-3xl font-semibold tracking-tight mb-2">
          {jurisdiction.name}
        </h1>
        <p className="text-muted-foreground capitalize">
          {jurisdiction.level} jurisdiction
        </p>
      </header>

      <div className="space-y-12">
        {leadership.length > 0 && (
          <RosterFilter
            heading="Leadership"
            reps={leadership}
            jurisdictionSlug={jurisdiction.slug}
            showParty={showParty}
          />
        )}

        {representatives.length > 0 && (
          <RosterFilter
            heading="Representatives"
            reps={representatives}
            jurisdictionSlug={jurisdiction.slug}
            showParty={showParty}
          />
        )}

        {leadership.length === 0 && representatives.length === 0 && (
          <p className="text-muted-foreground">
            No representatives available for this jurisdiction yet.
          </p>
        )}
      </div>
    </main>
  );
}
