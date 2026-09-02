"use client";

// components/ClaimScreens.tsx — claim entry, masked-hint challenge, and the
// three terminal states (sent / invalid token / gate closed).

import React from "react";
import type { ClaimInfo } from "@/lib/candidate-types";
import {
  SUBMISSIONS_ENABLED, candidateApi, candidateByUuid, fullName, initialsOf,
  maskEmail, officeLine, searchCandidates,
} from "@/lib/candidates";
import { Icon } from "./Icon";

/** Public entry point (/claim). The only door in — no candidate is emailed a
 *  link unprompted, so this URL is what outreach prints and says aloud. */
export function ClaimSearchScreen({ onPick }: { onPick: (uuid: string) => void }) {
  const [q, setQ] = React.useState("");
  const results = searchCandidates(q);

  return (
    <div className="container fade-in" style={{ maxWidth: 560 }}>
      <div className="stack stack-3" style={{ marginBottom: 22 }}>
        <div className="eyebrow accent">Claim your page</div>
        <h1 className="h-1">Find your name on the ballot</h1>
        <p className="t-lead">Search using the name filed with your municipality.</p>
      </div>
      <div className="search">
        <Icon name="search" size={16} />
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Type your name…" aria-label="Search candidates by name" />
      </div>
      {results.length ? (
        <div className="card" style={{ marginTop: 12, padding: "4px 14px" }}>
          {results.map((r, i) => (
            <React.Fragment key={r.uuid}>
              {i > 0 ? <hr className="divider" /> : null}
              <button type="button" className="rep" style={{ padding: "12px 0" }} onClick={() => onPick(r.uuid)}>
                <span className="avatar sm"><span>{initialsOf(r)}</span></span>
                <span className="fill">
                  <span className="rep-name" style={{ fontSize: 17, display: "block" }}>{fullName(r)}</span>
                  <span className="rep-sub"><span>{officeLine(r)}</span></span>
                </span>
                <Icon name="chevron_right" size={16} className="chevron" />
              </button>
            </React.Fragment>
          ))}
        </div>
      ) : q.trim() ? (
        <p className="t-sm" style={{ textAlign: "center", padding: 24, color: "var(--ink-3)" }}>
          No candidate by that name. New nomination filings take a few days to appear.
        </p>
      ) : null}
    </div>
  );
}

/** Masked-hint challenge. The typed address is compared server-side and
 *  discarded — it is never a delivery destination. A correct guess only causes
 *  mail to reach the real candidate's inbox. */
export function ClaimChallengeScreen({
  uuid, info, onSent, onContact,
}: {
  uuid: string;
  /** From GET /candidates/<uuid>/claim; falls back to local rows pre-wiring. */
  info?: ClaimInfo | null;
  onSent: (typed: string) => void;
  onContact: () => void;
}) {
  const row = candidateByUuid(uuid);
  const [val, setVal] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  if (!row && !info) return null;

  const name = info?.name ?? fullName(row!);
  const where = info ? [info.district || info.office, info.jurisdiction].filter(Boolean).join(", ") : officeLine(row!);
  const claimable = info ? info.claimable : !!row!.email;
  const claimed = info ? info.claim_status === "claimed" : false;
  const hint = info ? info.masked_hint : maskEmail(row!.email);

  if (!claimable) {
    return (
      <div className="container fade-in" style={{ maxWidth: 560 }}>
        <h1 className="h-1" style={{ fontSize: 32, lineHeight: 1.05 }}>{name}</h1>
        <p className="t-lead" style={{ marginTop: 10 }}>Candidate for {where}</p>
        <div className="card ghost" style={{ padding: 18, marginTop: 20 }}>
          <div className="eyebrow">This page hasn&apos;t been claimed</div>
          <p className="t-body" style={{ marginTop: 8, lineHeight: 1.5 }}>
            We don&apos;t have a verified email on file for this candidate, so we can&apos;t send an
            automatic claim link.
          </p>
        </div>
        <button type="button" className="act-btn primary" style={{ padding: 14, width: "100%", marginTop: 14 }} onClick={onContact}>
          Contact us to claim this page
        </button>
        <p className="t-xs" style={{ textAlign: "center", marginTop: 10 }}>
          We&apos;ll verify manually and follow up by email.
        </p>
      </div>
    );
  }

  const submit = async () => {
    setBusy(true);
    try {
      if (SUBMISSIONS_ENABLED) await candidateApi.requestClaim(uuid, val);
    } catch {
      /* Response is uniform by contract; a failure here must not leak either. */
    } finally {
      setBusy(false);
      onSent(val);
    }
  };

  return (
    <div className="container fade-in" style={{ maxWidth: 560 }}>
      <div className="stack stack-3" style={{ marginBottom: 20 }}>
        <div className="eyebrow accent">{claimed ? "Manage this page" : "Is this your page?"}</div>
        <h1 className="h-1" style={{ fontSize: 30 }}>{name}</h1>
        <p className="t-lead">{where}</p>
      </div>
      <div className="card tint" style={{ padding: 16 }}>
        <p className="t-sm" style={{ margin: 0, lineHeight: 1.55 }}>
          Parliament is an independent, non-commercial project — not affiliated with any party or
          campaign. It&apos;s free. We&apos;ll never post anything on your behalf.
        </p>
      </div>
      <div style={{ marginTop: 18 }}>
        <div className="field-label">Confirm the email on file</div>
        <p className="t-xs" style={{ marginTop: 2, marginBottom: 8 }}>
          We have a record on file ending in <span className="mono">{hint}</span>. Type it in full to continue.
        </p>
        <div className="field">
          <input type="email" value={val} onChange={(e) => setVal(e.target.value)}
            placeholder="you@yourcampaign.ca" aria-label="Email on file" />
        </div>
      </div>
      <button type="button" className="act-btn primary" style={{ padding: 14, marginTop: 14, width: "100%" }}
        onClick={submit} disabled={busy || !val.trim()}>
        {busy ? "Checking…" : "Continue"}
      </button>
      <p className="t-xs" style={{ textAlign: "center", marginTop: 10 }}>
        If that matches our records, we&apos;ll send a link. Nothing is sent otherwise — and this screen
        looks the same either way.
      </p>
    </div>
  );
}

/** Rendered identically for every 200 — match or not. */
export function ClaimSentScreen({
  typed, onContact,
}: { typed: string; onContact: () => void }) {
  return (
    <div className="container fade-in" style={{ maxWidth: 480, textAlign: "center" }}>
      <div className="confirm-mark"><Icon name="check" size={26} stroke={2} /></div>
      <h1 className="h-1" style={{ marginTop: 18 }}>Check your email</h1>
      <p className="t-lead" style={{ marginTop: 10 }}>
        We sent an access link to<br />
        <span className="mono" style={{ fontSize: 14, color: "var(--ink)" }}>{typed || "the address on file"}</span>
      </p>
      <p className="t-sm" style={{ marginTop: 16, color: "var(--ink-3)" }}>
        Your link stays valid through election day — you can come back and change your video any
        time. Once you open it, you&apos;ll have 30 minutes in each editing session. Didn&apos;t get
        it? Check your spam folder.
      </p>
      <p className="t-xs" style={{ marginTop: 10 }}>
        Still nothing? <a href="#" onClick={(e) => { e.preventDefault(); onContact(); }}>Contact us</a>
      </p>
    </div>
  );
}

/** Any 400 from /claim/exchange — expired, forged, malformed are not
 *  distinguished by the API, so they are not distinguished here. */
export function ClaimTokenInvalid({ onSearch }: { onSearch: () => void }) {
  return (
    <div className="container fade-in" style={{ maxWidth: 480, textAlign: "center" }}>
      <div className="err-mark"><Icon name="info" size={22} /></div>
      <h1 className="h-1" style={{ marginTop: 18, fontSize: 30 }}>This link isn&apos;t valid</h1>
      <p className="t-lead" style={{ marginTop: 10 }}>
        It may have been mistyped, or copied incompletely from your email.
      </p>
      <p className="t-sm" style={{ marginTop: 14, color: "var(--ink-3)" }}>
        You can request a new one from your candidate page — nothing about your profile has changed.
      </p>
      <button type="button" className="act-btn primary" style={{ padding: 14, marginTop: 18, width: "100%" }} onClick={onSearch}>
        Find my page
      </button>
    </div>
  );
}

/** Backend gate closed: endpoints 503 and no email is sent, so never show a
 *  "check your email" screen here. */
export function ClaimUnavailable({ onBack }: { onBack: () => void }) {
  return (
    <div className="container fade-in" style={{ maxWidth: 480, textAlign: "center" }}>
      <div className="err-mark"><Icon name="info" size={22} /></div>
      <h1 className="h-1" style={{ marginTop: 18, fontSize: 30 }}>Profile submissions aren&apos;t open yet</h1>
      <p className="t-lead" style={{ marginTop: 10 }}>
        Candidate pages are live, but the submission system isn&apos;t finished. Nothing has been sent.
      </p>
      <p className="t-sm" style={{ marginTop: 14, color: "var(--ink-3)" }}>
        Every certified candidate is already listed on their race page. Claiming opens before the
        October 26 election.
      </p>
      <button type="button" className="act-btn" style={{ padding: 14, marginTop: 18, width: "100%" }} onClick={onBack}>
        Back
      </button>
    </div>
  );
}
