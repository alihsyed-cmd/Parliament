"use client";

/**
 * Photo with graceful fallback to a gray placeholder when the URL fails
 * to load (404, network error, etc.). Lives as a client component because
 * onError is an event handler, which can't be passed across the
 * server/client boundary.
 *
 * Sized via the `size` prop (Tailwind classes for width and height).
 */

type Props = {
  photoUrl: string | null | undefined;
  alt: string;
  /** Tailwind size classes, e.g., "w-14 h-14" or "w-20 h-20". */
  sizeClass?: string;
};

export function PhotoWithFallback({ photoUrl, alt, sizeClass = "w-14 h-14" }: Props) {
  if (!photoUrl) {
    return (
      <div
        className={`${sizeClass} rounded-md bg-muted flex-shrink-0`}
        aria-hidden="true"
      />
    );
  }

  return (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={photoUrl}
        alt={alt}
        className={`${sizeClass} rounded-md object-cover flex-shrink-0`}
        onError={(e) => {
          e.currentTarget.style.display = "none";
          const ph = e.currentTarget.nextElementSibling as HTMLElement | null;
          if (ph) ph.style.display = "block";
        }}
      />
      <div
        className={`${sizeClass} rounded-md bg-muted flex-shrink-0`}
        style={{ display: "none" }}
        aria-hidden="true"
      />
    </>
  );
}
