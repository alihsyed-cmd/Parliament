/**
 * Lookup results page.
 *
 * Server Component — fetches data on the server before sending HTML to
 * the browser. This means search engines see real content, users on slow
 * connections see content immediately, and the API URL is called
 * server-to-server (faster, no CORS overhead).
 */

import { lookupPostalCode, ApiError } from "@/lib/api";
import type { LookupResponse } from "@/lib/types";
import { notFound } from "next/navigation";
import Link from "next/link";
import { LevelSection } from "@/components/LevelSection";

const POSTAL_CODE_REGEX = /^[A-Z]\d[A-Z]\d[A-Z]\d$/;

type PageProps = {
  params: Promise<{ postal_code: string }>;
};

export default async function LookupPage({ params }: PageProps) {
  const { postal_code } = await params;

  if (!POSTAL_CODE_REGEX.test(postal_code)) {
    notFound();
  }

  let data: LookupResponse;
  try {
    data = await lookupPostalCode(postal_code);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return (
        <main className="min-h-screen p-8 max-w-3xl mx-auto">
          <h1 className="text-2xl font-semibold mb-4">No results</h1>
          <p>We couldn&rsquo;t find representatives for postal code {postal_code}.</p>
          <Link href="/" className="text-blue-600 underline mt-4 inline-block">
            Try another postal code
          </Link>
        </main>
      );
    }
    throw err;
  }

  // Format postal code for display: "M3J3R2" -> "M3J 3R2"
  const displayPostalCode = `${data.postal_code.slice(0, 3)} ${data.postal_code.slice(3)}`;

  return (
    <main className="min-h-screen p-8 max-w-3xl mx-auto">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold mb-2">
          Results for {displayPostalCode}
        </h1>
        <Link href="/" className="text-blue-600 underline text-sm">
          &larr; New search
        </Link>
      </header>

      <div className="space-y-12">
        <LevelSection level="municipal" data={data.results.municipal} />
        <LevelSection level="provincial" data={data.results.provincial} />
        <LevelSection level="federal" data={data.results.federal} />
      </div>
    </main>
  );
}
