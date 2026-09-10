// lib/reminders.ts — election-reminder opt-in.
//
// Replaces the localStorage-only stub. A subscription now lives on the server:
// the voter gives an email address and a postal code, gets a confirmation link,
// and once they click it we mail them seven days before and on the morning of
// every future election at that address.
//
// localStorage still has a job, but a much smaller one. It remembers which
// postal codes THIS DEVICE has submitted, purely so the form can show "check
// your email" instead of an empty form when someone taps back into the same
// lookup. It is a UI convenience and nothing depends on it: it is not consent,
// not a subscription, and losing it costs the user nothing but a second submit,
// which the server treats as idempotent.

const KEY = "parliament.reminder.v2";

const API_BASE =
  process.env.NEXT_PUBLIC_PARLIAMENT_API ??
  "https://parliament-api-staging.onrender.com";

export interface UpcomingElection {
  id: string;
  jurisdiction_slug: string;
  jurisdiction_name: string;
  level: string;
  election_date: string;
  election_type: string;
  name: string | null;
  advance_voting_starts: string | null;
  info_url: string | null;
}

export interface SubscriptionInfo {
  status: "pending" | "active" | "unsubscribed" | "bounced" | "complained";
  email: string;          // masked by the server: a***@example.com
  postal_code: string;
  confirmed_at: string | null;
  upcoming: UpcomingElection[];
}

export class ReminderError extends Error {
  status: number;
  kind: string;
  constructor(message: string, status: number, kind: string) {
    super(message);
    this.name = "ReminderError";
    this.status = status;
    this.kind = kind;
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (e) {
    throw new ReminderError((e as Error).message || "Network error", 0, "network");
  }
  const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) {
    throw new ReminderError(
      (body.message as string) || (body.error as string) || res.statusText,
      res.status,
      (body.error as string) || "server_error",
    );
  }
  return body as T;
}

/** What a postal code would be reminded about. Lets the form name the actual
 *  elections instead of promising in the abstract. */
export function preview(postalCode: string): Promise<{ upcoming: UpcomingElection[] }> {
  return call(`/reminders/preview?postal_code=${encodeURIComponent(postalCode)}`);
}

/** Start a subscription. The response is deliberately identical whether this is
 *  a new address, an already-pending one, or one already subscribed — so the
 *  UI must say "check your email", never "you are subscribed". */
export function subscribe(
  email: string, postalCode: string, website = "",
): Promise<{ status: string; message: string }> {
  return call("/reminders/subscribe", {
    method: "POST",
    body: JSON.stringify({ email, postal_code: postalCode, website }),
  });
}

export function confirm(token: string): Promise<{
  status: string; postal_code: string; manage_token: string; upcoming: UpcomingElection[];
}> {
  return call("/reminders/confirm", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function getSubscription(token: string): Promise<SubscriptionInfo> {
  return call(`/reminders/subscription?token=${encodeURIComponent(token)}`);
}

export function updatePostalCode(
  token: string, postalCode: string,
): Promise<{ status: string; postal_code: string; upcoming: UpcomingElection[] }> {
  return call("/reminders/subscription", {
    method: "POST",
    body: JSON.stringify({ token, postal_code: postalCode }),
  });
}

export function unsubscribe(token: string): Promise<{ status: string; message: string }> {
  return call("/reminders/unsubscribe", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

// ── Local "already asked on this device" memory ──────────────────────────────

type LocalState = { submitted: string[] };   // normalized postal codes

function read(): LocalState {
  if (typeof window === "undefined") return { submitted: [] };
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? (JSON.parse(raw) as Partial<LocalState>) : null;
    return { submitted: Array.isArray(parsed?.submitted) ? parsed!.submitted! : [] };
  } catch {
    return { submitted: [] };
  }
}

function write(state: LocalState): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* private mode, quota, blocked storage — the form still works without it */
  }
}

export function markSubmitted(postalCode: string): void {
  const state = read();
  if (!state.submitted.includes(postalCode)) {
    state.submitted = [...state.submitted, postalCode].slice(-10);
    write(state);
  }
}

export function wasSubmitted(postalCode: string): boolean {
  return read().submitted.includes(postalCode);
}

export function clearSubmitted(postalCode: string): void {
  const state = read();
  write({ submitted: state.submitted.filter((p) => p !== postalCode) });
}

// ── Formatting ───────────────────────────────────────────────────────────────

const LEVEL_LABEL: Record<string, string> = {
  municipal: "Municipal", provincial: "Provincial",
  territorial: "Territorial", federal: "Federal", state: "State",
};

export function levelLabel(level: string): string {
  return LEVEL_LABEL[level] ?? level;
}

/** "Monday, 26 October 2026". Parsed as a local date rather than through
 *  Date(string), which reads a bare YYYY-MM-DD as UTC and can show the day
 *  before for anyone west of Greenwich — every Canadian, that is. */
export function formatElectionDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(y, m - 1, d).toLocaleDateString("en-CA", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
}

export function electionLabel(e: UpcomingElection): string {
  if (e.name) return e.name;
  const kind = e.election_type === "by_election" ? "by-election" : "election";
  return `${e.election_date.slice(0, 4)} ${e.jurisdiction_name} ${kind}`;
}
