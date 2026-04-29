/**
 * Lookup results page.
 *
 * Server Component — fetches data on the server before sending HTML to
 * the browser. This means search engines see real content (good for SEO),
 * users on slow connections see content immediately, and the API URL
 * is called server-to-server (faster, no preflight CORS overhead).
 *
 * Steps 5–7 will replace the current pre/JSON dump with real components.
 */

import { lookupPostalCode, ApiError } from "@/lib/api";
import type { LookupResponse } from "@/lib/types";
import { notFound } from "next/navigation";

const POSTAL_CODE_REGEX = /^[A-Z]\d[A-Z]\d[A-Z]\d$/;

type PageProps = {
  params: Promise<{ postal_code: string }>;
};

export default async function LookupPage({ params }: PageProps) {
  const { postal_code } = await params;

  // Defense-in-depth: the home page validates, but anyone can hit this
  // URL directly. Reject malformed input before calling the API.
  if (!POSTAL_CODE_REGEX.test(postal_code)) {
    notFound();
  }

  let data: LookupResponse;
  try {
    data = await lookupPostalCode(postal_code);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      // Geocoding failure or coverage gap. For now, render a minimal
      // message; Step 8 builds proper empty / error states.
      return (
        <main className="min-h-screen p-8">
          <h1 className="text-2xl font-semibold mb-4">No results</h1>
          <p>We couldn&rsquo;t find representatives for postal code {postal_code}.</p>
          <a href="/" className="text-blue-600 underline mt-4 inline-block">
            Try another postal code
          </a>
        </main>
      );
    }
    // Anything else — network error, 500, etc. — re-throw so Next.js shows
    // its error boundary. We'll add a custom error page in Step 8.
    throw err;
  }

  return (
    <main className="min-h-screen p-8">
      <h1 className="text-2xl font-semibold mb-4">
        Results for {data.postal_code}
      </h1>
      <a href="/" className="text-blue-600 underline mb-6 inline-block">
        ← New search
      </a>
      <pre className="bg-gray-900 text-gray-100 p-4 rounded overflow-auto text-sm font-mono">
        {JSON.stringify(data, null, 2)}
      </pre>
    </main>
  );
}
