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
  /** Tailwind WIDTH class, e.g., "w-14" or "w-20". Height is auto so the
   *  photo renders at its native aspect ratio. The placeholder for a
   *  missing photo uses the width as a square so the layout doesn't
   *  collapse to zero height. */
  widthClass?: string;
};

export function PhotoWithFallback({ photoUrl, alt, widthClass = "w-14" }: Props) {
  // Derive a height class equal to the width so the placeholder stays
  // square. e.g. "w-14" -> "h-14".
  const placeholderSizeClass = `${widthClass} ${widthClass.replace("w-", "h-")}`;

  if (!photoUrl) {
    return (
      <div
        className={`${placeholderSizeClass} rounded-md bg-muted flex-shrink-0`}
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
        className={`${widthClass} h-auto rounded-md flex-shrink-0`}
        onError={(e) => {
          e.currentTarget.style.display = "none";
          const ph = e.currentTarget.nextElementSibling as HTMLElement | null;
          if (ph) ph.style.display = "block";
        }}
      />
      <div
        className={`${placeholderSizeClass} rounded-md bg-muted flex-shrink-0`}
        style={{ display: "none" }}
        aria-hidden="true"
      />
    </>
  );
}
