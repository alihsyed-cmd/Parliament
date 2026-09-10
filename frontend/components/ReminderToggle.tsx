"use client";

// ReminderToggle — the signup form for election reminders.
//
// Was a switch that wrote to localStorage and sent nothing. Now it collects an
// email address and starts a real double opt-in: the server mails a
// confirmation link, and only a click on that link turns reminders on.
//
// The screen after submitting says "check your email" and never "you're
// subscribed", because the API returns one identical response for a new
// address, an already-pending one, and one already subscribed. That is
// deliberate on the server's side — a response that varied would let anyone
// test whether an address is on the list — and this component must not invent a
// certainty the response does not carry.

import React from "react";
import { Icon } from "./Icon";
import {
  electionLabel, formatElectionDate, levelLabel, markSubmitted, preview,
  ReminderError, subscribe, wasSubmitted, type UpcomingElection,
} from "@/lib/reminders";

type Phase = "closed" | "form" | "sent";

export function ReminderToggle({ postalCode }: { postalCode: string }) {
  const [phase, setPhase] = React.useState<Phase>("closed");
  const [email, setEmail] = React.useState("");
  const [website, setWebsite] = React.useState("");   // honeypot
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [upcoming, setUpcoming] = React.useState<UpcomingElection[] | null>(null);

  // Reset when the voter looks up a different postal code: the open form
  // belongs to the address it was opened for.
  React.useEffect(() => {
    setPhase(wasSubmitted(postalCode) ? "sent" : "closed");
    setError(null);
    setUpcoming(null);
  }, [postalCode]);

  // Load what this postal code would actually be reminded about, so the form
  // can name the elections rather than promising in the abstract. Failure is
  // silent — the copy below works without it.
  React.useEffect(() => {
    if (phase === "closed" || upcoming !== null) return;
    let live = true;
    preview(postalCode)
      .then((r) => { if (live) setUpcoming(r.upcoming); })
      .catch(() => { if (live) setUpcoming([]); });
    return () => { live = false; };
  }, [phase, postalCode, upcoming]);

  const submit = async () => {
    const trimmed = email.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    try {
      await subscribe(trimmed, postalCode, website);
      markSubmitted(postalCode);
      setPhase("sent");
    } catch (e) {
      const err = e as ReminderError;
      setError(
        err.kind === "network"
          ? "We could not reach the server. Please try again."
          : err.message || "Something went wrong. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  const next = upcoming?.[0];

  return (
    <div className={`reminder ${phase !== "closed" ? "on" : ""}`}>
      <div className="row row-gap-3 between">
        <div className="row row-gap-3" style={{ alignItems: "flex-start" }}>
          <div style={{
            width: 38, height: 38, borderRadius: 10, background: "var(--paper)",
            border: "1px solid var(--line)", display: "flex", alignItems: "center",
            justifyContent: "center", flexShrink: 0, color: "var(--accent-ink)",
          }}>
            <Icon name="bell" size={18} />
          </div>
          <div>
            <div className="h-3" style={{ fontSize: 17 }}>Remind me before elections</div>
            <p className="t-sm" style={{ marginTop: 3 }}>
              A week before each election and again on voting day — municipal,
              provincial, and federal.
            </p>
          </div>
        </div>
        {phase === "closed" ? (
          <button
            type="button"
            className="switch"
            role="switch"
            aria-checked={false}
            aria-label="Turn on election reminders"
            onClick={() => setPhase("form")}
          >
            <span className="knob" />
          </button>
        ) : null}
      </div>

      {phase === "form" ? (
        <div style={{ marginTop: 14 }}>
          {next ? (
            <p className="t-sm" style={{ marginBottom: 10 }}>
              Next where you live: <strong>{electionLabel(next)}</strong> on{" "}
              {formatElectionDate(next.election_date)}.
              {upcoming && upcoming.length > 1
                ? ` Plus ${upcoming.length - 1} more after that.`
                : ""}
            </p>
          ) : null}
          {upcoming !== null && upcoming.length === 0 ? (
            <p className="t-sm" style={{ marginBottom: 10 }}>
              We do not have a confirmed election date here yet. Sign up now and
              we will tell you as soon as one is called.
            </p>
          ) : null}

          <div className="field">
            <input
              type="email"
              inputMode="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
              placeholder="you@example.ca"
              aria-label="Your email address"
            />
          </div>

          {/* Honeypot. Hidden from people, filled by bots. */}
          <input
            type="text"
            name="website"
            tabIndex={-1}
            autoComplete="off"
            aria-hidden="true"
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
            style={{ position: "absolute", left: "-9999px", width: 1, height: 1, opacity: 0 }}
          />

          {error ? (
            <p className="t-xs" style={{ marginTop: 8, color: "var(--danger, #b3261e)" }} role="alert">
              {error}
            </p>
          ) : null}

          <div className="row row-gap-2" style={{ marginTop: 12 }}>
            <button
              type="button"
              className="act-btn primary"
              style={{ padding: 13, flex: 1 }}
              onClick={submit}
              disabled={busy || !email.trim()}
            >
              {busy ? "Sending…" : "Send me reminders"}
            </button>
            <button
              type="button"
              className="btn ghost"
              onClick={() => { setPhase("closed"); setError(null); }}
              disabled={busy}
            >
              Cancel
            </button>
          </div>

          <p className="t-xs" style={{ marginTop: 10 }}>
            We use your address only for these reminders. Every email has a
            one-click unsubscribe link.
          </p>
        </div>
      ) : null}

      {phase === "sent" ? (
        <div style={{ marginTop: 14 }}>
          <div className="row row-gap-2" style={{ alignItems: "flex-start" }}>
            <Icon name="mail" size={18} />
            <div>
              <div className="h-3" style={{ fontSize: 15 }}>Check your email</div>
              <p className="t-sm" style={{ marginTop: 3 }}>
                We sent a link to confirm. Reminders start once you open it —
                until then we will not send you anything else.
              </p>
            </div>
          </div>
          <button
            type="button"
            className="btn ghost"
            style={{ marginTop: 10 }}
            onClick={() => { setPhase("form"); setError(null); }}
          >
            Use a different address
          </button>
        </div>
      ) : null}

      {phase === "closed" && upcoming && upcoming.length > 0 ? (
        <p className="t-xs" style={{ marginTop: 12 }}>
          {upcoming.length === 1
            ? `1 upcoming election here: ${formatElectionDate(upcoming[0].election_date)}.`
            : `${upcoming.length} upcoming elections here, starting ${formatElectionDate(upcoming[0].election_date)}.`}
        </p>
      ) : null}
    </div>
  );
}

/** Shared by the confirm and manage pages: the list of what someone is
 *  subscribed to. Kept here so all three surfaces render an election the same
 *  way. */
export function UpcomingList({ elections }: { elections: UpcomingElection[] }) {
  if (elections.length === 0) {
    return (
      <p className="t-sm">
        No confirmed election dates where you live yet. We will email you as soon
        as one is called.
      </p>
    );
  }
  return (
    <div className="stack-2">
      {elections.map((e) => (
        <div key={e.id} className="row row-gap-3 between" style={{ alignItems: "flex-start" }}>
          <div>
            <div className="h-3" style={{ fontSize: 15 }}>{electionLabel(e)}</div>
            <p className="t-xs" style={{ marginTop: 2 }}>
              {e.jurisdiction_name} — {levelLabel(e.level)}
            </p>
          </div>
          <div className="t-sm mono" style={{ whiteSpace: "nowrap" }}>
            {formatElectionDate(e.election_date)}
          </div>
        </div>
      ))}
    </div>
  );
}
