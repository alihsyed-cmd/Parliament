/**
 * Card showing the user's elected representative at one level.
 *
 * Displays full details directly — name, role, photo, party, riding/ward,
 * contact info, election dates. Fields render only if present, so the same
 * component works across federal/provincial/municipal despite their
 * different field availability.
 *
 * Distinct from cabinet members (who are shown as compact rows that open
 * a modal). The user's own rep is the most important info on the page,
 * so we show everything inline.
 */

import type { Representative } from "@/lib/types";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";

type RepresentativeCardProps = {
  representative: Representative;
  showParty: boolean;
};

function formatDistrict(rep: Representative): string | null {
  if (rep.ward) {
    // Toronto-style: "Ward 7"
    return `Ward ${rep.ward}`;
  }
  if (rep.riding) {
    return rep.riding;
  }
  return null;
}

export function RepresentativeCard({ representative, showParty }: RepresentativeCardProps) {
  const district = formatDistrict(representative);
  const hasContact =
    representative.email || representative.phone || representative.website;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start gap-4">
          {representative.photo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={representative.photo_url}
              alt={`Photo of ${representative.name}`}
              className="w-20 h-20 rounded-md object-cover flex-shrink-0"
              onError={(e) => {
                e.currentTarget.style.display = "none";
                const placeholder = e.currentTarget.nextElementSibling as HTMLElement | null;
                if (placeholder) placeholder.style.display = "block";
              }}
            />
          ) : null}
          {/* Placeholder shown when no photo OR when photo fails to load */}
          <div
            className="w-20 h-20 rounded-md bg-gray-200 flex-shrink-0"
            style={representative.photo_url ? { display: "none" } : {}}
            aria-hidden="true"
          />

          <div className="min-w-0">
            <CardTitle>{representative.name}</CardTitle>
            <CardDescription>
              {representative.role}
              {district && <span> &middot; {district}</span>}
            </CardDescription>
            {showParty && representative.party && (
              <p className="text-sm mt-1">{representative.party}</p>
            )}
          </div>
        </div>
      </CardHeader>

      {(hasContact || representative.next_election || representative.elected) && (
        <CardContent>
          <dl className="text-sm space-y-1">
            {representative.email && (
              <div>
                <dt className="font-medium inline">Email: </dt>
                <dd className="inline">
                  <a href={`mailto:${representative.email}`} className="text-primary underline">
                    {representative.email}
                  </a>
                </dd>
              </div>
            )}
            {representative.phone && (
              <div>
                <dt className="font-medium inline">Phone: </dt>
                <dd className="inline">
                  <a href={`tel:${representative.phone}`} className="text-primary underline">
                    {representative.phone}
                  </a>
                </dd>
              </div>
            )}
            {representative.website && (
              <div>
                <dt className="font-medium inline">Website: </dt>
                <dd className="inline">
                  <a
                    href={representative.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary underline"
                  >
                    Official page
                  </a>
                </dd>
              </div>
            )}
            {representative.elected && (
              <div>
                <dt className="font-medium inline">Elected: </dt>
                <dd className="inline">{representative.elected}</dd>
              </div>
            )}
            {representative.next_election && (
              <div>
                <dt className="font-medium inline">Next election: </dt>
                <dd className="inline">{representative.next_election}</dd>
              </div>
            )}
          </dl>
        </CardContent>
      )}
    </Card>
  );
}
