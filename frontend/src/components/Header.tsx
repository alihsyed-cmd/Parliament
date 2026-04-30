import Link from "next/link";

/**
 * Site-wide header. Present on every page (home, lookup, browse).
 *
 * Wordmark on the left links to home. Three nav links on the right
 * lead to the browse-flow indexes.
 *
 * Designed to be lightweight: no client-side interactivity, no
 * hamburger menu yet (mobile nav stacks; we accept the slight visual
 * trade-off for v1 in exchange for simplicity).
 */
export function Header() {
  return (
    <header className="border-b border-border bg-background">
      <div className="max-w-5xl mx-auto px-6 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <Link href="/" className="inline-block">
          <span className="text-2xl font-semibold tracking-tight">
            Parliament
          </span>
        </Link>
        <nav aria-label="Main navigation" className="flex gap-6 text-sm">
          <Link
            href="/municipalities"
            className="text-foreground hover:text-primary transition-colors"
          >
            Municipalities
          </Link>
          <Link
            href="/provinces"
            className="text-foreground hover:text-primary transition-colors"
          >
            Provinces
          </Link>
          <Link
            href="/federal"
            className="text-foreground hover:text-primary transition-colors"
          >
            Federal
          </Link>
        </nav>
      </div>
    </header>
  );
}
