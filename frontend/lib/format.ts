// lib/format.ts — small display helpers shared across components.

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

export function formatDate(iso?: string): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  const mi = Number(m) - 1;
  if (Number.isNaN(mi) || !MONTHS[mi]) return iso;
  return `${MONTHS[mi]} ${Number(d)}, ${y}`;
}

const MONTHS_LONG = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday",
  "Friday", "Saturday"];

/** "Monday, October 26, 2026" — for prose, where the terse form reads clipped. */
export function formatDateLong(iso?: string): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d || !MONTHS_LONG[m - 1]) return formatDate(iso);
  // Built in UTC and read back in UTC: a date-only string is midnight GMT, and
  // reading the weekday locally would name the day before across the Atlantic.
  const weekday = WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
  return `${weekday}, ${MONTHS_LONG[m - 1]} ${d}, ${y}`;
}

export function daysUntil(iso?: string): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime() - Date.now();
  if (Number.isNaN(t)) return null;
  return Math.round(t / 86_400_000);
}

export const levelMeta: Record<string, { tag: string; badge: string; brand: string; execTitle: string }> = {
  municipal:  { tag: "MUNICIPAL",  badge: "M", brand: "City Hall",    execTitle: "Mayor" },
  provincial: { tag: "PROVINCIAL", badge: "P", brand: "Queen's Park", execTitle: "Premier" },
  federal:    { tag: "FEDERAL",    badge: "F", brand: "Parliament",   execTitle: "Prime Minister" },
};
