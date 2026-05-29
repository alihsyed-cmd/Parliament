// lib/format.ts — small display helpers shared across components.

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

export function formatDate(iso?: string): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  const mi = Number(m) - 1;
  if (Number.isNaN(mi) || !MONTHS[mi]) return iso;
  return `${MONTHS[mi]} ${Number(d)}, ${y}`;
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
