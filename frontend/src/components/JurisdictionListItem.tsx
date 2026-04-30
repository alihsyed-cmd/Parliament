import Link from "next/link";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import type { JurisdictionSummary } from "@/lib/types";

const LEVEL_ROUTE: Record<JurisdictionSummary["level"], string> = {
  municipal: "/municipalities",
  provincial: "/provinces",
  federal: "/federal",
};

type Props = {
  jurisdiction: JurisdictionSummary;
};

/**
 * One row on the /municipalities or /provinces index pages.
 * Shows the jurisdiction name and a hint of context (province for cities,
 * country for provinces).
 */
export function JurisdictionListItem({ jurisdiction }: Props) {
  const href = `${LEVEL_ROUTE[jurisdiction.level]}/${jurisdiction.slug}`;
  const subtitle =
    jurisdiction.level === "municipal"
      ? `${jurisdiction.province_code ?? ""}, ${jurisdiction.country_code}`
      : jurisdiction.country_code;

  return (
    <Link
      href={href}
      className="block transition-opacity hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-lg"
    >
      <Card>
        <CardHeader>
          <CardTitle>{jurisdiction.name}</CardTitle>
          <CardDescription>{subtitle}</CardDescription>
        </CardHeader>
      </Card>
    </Link>
  );
}
