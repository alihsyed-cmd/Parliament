// lib/reminders.ts — election-reminder opt-in, stored locally for now.
// V1 STUB: persists consent to localStorage. Does NOT send notifications.
// NATIVE HANDOFF: replace saveReminder() with OS permission request + push token registration.

const KEY = "parliament.reminder.v1";

export interface ReminderPrefs {
  enabled: boolean;
  postalCode: string;
  savedAt: string;
  pushToken?: string | null;
}

export function getReminder(): ReminderPrefs | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as ReminderPrefs) : null;
  } catch {
    return null;
  }
}

export function saveReminder(postalCode: string): ReminderPrefs {
  const prefs: ReminderPrefs = {
    enabled: true,
    postalCode,
    savedAt: new Date().toISOString(),
    pushToken: null,
  };
  if (typeof window !== "undefined") {
    try { window.localStorage.setItem(KEY, JSON.stringify(prefs)); } catch { /* ignore */ }
  }
  return prefs;
}

export function clearReminder(): void {
  if (typeof window !== "undefined") {
    try { window.localStorage.removeItem(KEY); } catch { /* ignore */ }
  }
}

export function isReminderOn(postalCode: string): boolean {
  const r = getReminder();
  return !!r?.enabled && r.postalCode === postalCode;
}
