// lib/reminders.ts — election-reminder opt-in, stored locally for now.
//
// ⚠️ V1 STUB. This persists the user's consent + postal code to localStorage so
// the UI works today. It does NOT send notifications — web push is unreliable on
// iOS and real reminders belong to the native (Capacitor/RN) build.
//
// NATIVE HANDOFF: when wrapping for the app stores, replace saveReminder() with a
// call that (1) requests OS notification permission, (2) registers for APNs/FCM,
// and (3) POSTs { postal_code, push_token, locale } to your backend so a scheduled
// job can fire reminders ahead of each level's next_election. Everything else in
// the UI can stay as-is.

const KEY = "parliament.reminder.v1";

export interface ReminderPrefs {
  enabled: boolean;
  postalCode: string;        // normalized, e.g. "M5V3A8"
  savedAt: string;           // ISO timestamp
  // Filled in during the native phase:
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
  // NATIVE TODO: request permission + register push token here.
  return prefs;
}

export function clearReminder(): void {
  if (typeof window !== "undefined") {
    try { window.localStorage.removeItem(KEY); } catch { /* ignore */ }
  }
  // NATIVE TODO: also unregister the push token on the backend.
}

export function isReminderOn(postalCode: string): boolean {
  const r = getReminder();
  return !!r?.enabled && r.postalCode === postalCode;
}
