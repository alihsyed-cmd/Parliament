import { getRepresentative, ApiError } from "@/lib/api";
import { PhotoWithFallback } from "@/components/PhotoWithFallback";
import { notFound } from "next/navigation";
import Link from "next/link";

type PageProps = {
  params: Promise<{ jurisdiction_slug: string; rep_slug: string }>;
};

export async function generateMetadata({ params }: PageProps) {
  const { jurisdiction_slug, rep_slug } = await params;
  try {
    const data = await getRepresentative(jurisdiction_slug, rep_slug);
    return {
      title: `${data.representative.name} · Parliament`,
      description: `${data.representative.name} — details and current roles.`,
    };
  } catch {
    return { title: "Not found · Parliament" };
  }
}

export default async function RepresentativePage({ params }: PageProps) {
  const { jurisdiction_slug, rep_slug } = await params;

  try {
    const data = await getRepresentative(jurisdiction_slug, rep_slug);
    const { representative: rep, representations } = data;

    // Build the "back to" link based on the jurisdiction level of the
    // first representation. (A rep's representations all link back to the
    // same jurisdiction since this page is scoped to one.)
    const firstRepn = representations[0];
    const backHref =
      firstRepn?.jurisdiction_level === "municipal"
        ? `/municipalities/${jurisdiction_slug}`
        : firstRepn?.jurisdiction_level === "provincial"
        ? `/provinces/${jurisdiction_slug}`
        : firstRepn?.jurisdiction_level === "federal"
        ? "/federal"
        : "/";

    return (
      <main className="min-h-screen px-6 py-12 max-w-3xl mx-auto">
        <Link href={backHref} className="text-primary underline text-sm mb-8 inline-block">
          &larr; Back
        </Link>

        <header className="mb-12">
          <div className="flex items-start gap-6">
            <PhotoWithFallback
              photoUrl={rep.photo_url}
              alt={`Photo of ${rep.name}`}
              widthClass="w-32"
            />
            <div className="min-w-0 flex-1">
              <h1 className="text-3xl font-semibold tracking-tight mb-2">
                {rep.name}
              </h1>
              {rep.party && (
                <p className="text-muted-foreground mb-1">{rep.party}</p>
              )}
            </div>
          </div>
        </header>

        {representations.length > 0 && (
          <section className="mb-12" aria-labelledby="roles-heading">
            <h2 id="roles-heading" className="text-2xl font-semibold mb-6">
              Current roles
            </h2>
            <ul className="divide-y divide-border border-y border-border">
              {representations.map((r, idx) => {
                const districtLabel =
                  r.district_external_id &&
                  r.district_external_id !== r.district_name
                    ? `Ward ${r.district_external_id}`
                    : r.district_name;
                return (
                  <li key={idx} className="py-3">
                    <div className="font-medium">{r.role}</div>
                    <div className="text-sm text-muted-foreground">
                      {r.jurisdiction_name}
                      {districtLabel ? ` · ${districtLabel}` : ""}
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {(rep.email || rep.phone || rep.website_url) && (
          <section aria-labelledby="contact-heading">
            <h2 id="contact-heading" className="text-2xl font-semibold mb-6">
              Contact
            </h2>
            <dl className="space-y-2 text-sm">
              {rep.email && (
                <div>
                  <dt className="font-medium inline">Email: </dt>
                  <dd className="inline">
                    <a href={`mailto:${rep.email}`} className="text-primary underline">
                      {rep.email}
                    </a>
                  </dd>
                </div>
              )}
              {rep.phone && (
                <div>
                  <dt className="font-medium inline">Phone: </dt>
                  <dd className="inline">
                    <a href={`tel:${rep.phone}`} className="text-primary underline">
                      {rep.phone}
                    </a>
                  </dd>
                </div>
              )}
              {rep.website_url && (
                <div>
                  <dt className="font-medium inline">Website: </dt>
                  <dd className="inline">
                    <a
                      href={rep.website_url}
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
          </section>
        )}
      </main>
    );
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    throw err;
  }
}
