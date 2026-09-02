"use client";

// components/StaticPages.tsx — SearchPlaces (entry-screen sidekick to the
// postal lookup), About, Contact, For candidates.

import React from "react";
import { PLACE_INDEX, type Place } from "@/lib/browse-data";
import { CLAIM_AFFORDANCE_VISIBLE, SUBMISSIONS_ENABLED, candidateApi } from "@/lib/candidates";
import { Icon } from "./Icon";

export function SearchPlaces({ onSelect }: { onSelect: (p: Place) => void }) {
  const [q, setQ] = React.useState("");
  const [focused, setFocused] = React.useState(false);
  const results = q.trim().length
    ? PLACE_INDEX.filter((p) => p.name.toLowerCase().includes(q.trim().toLowerCase())).slice(0, 6)
    : [];
  const kindLabel = { municipal: "City", provincial: "Province", federal: "Riding" } as const;

  return (
    <div style={{ position: "relative" }}>
      <div className="search" style={{ background: "var(--paper)", border: "1px solid var(--line)" }}>
        <Icon name="search" size={16} />
        <input value={q} onChange={(e) => setQ(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 120)}
          placeholder="Or search a riding, city, or province" aria-label="Search places" />
      </div>
      {focused && results.length ? (
        <div className="card" style={{ position: "absolute", top: "calc(100% + 6px)", left: 0, right: 0, zIndex: 10, padding: 6, boxShadow: "var(--shadow-2)" }}>
          {results.map((r) => (
            <button key={r.kind + r.name} type="button" className="rep" style={{ padding: "9px 8px", gap: 10 }} onClick={() => onSelect(r)}>
              <span className="fill row between">
                <span className="t-body">{r.name}</span>
                <span className="t-xs mono" style={{ color: "var(--ink-3)" }}>
                  {kindLabel[r.kind]}{r.covered ? "" : " · soon"}
                </span>
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function StaticHeader({ eyebrow, title, lead }: { eyebrow: string; title: string; lead?: string }) {
  return (
    <div className="stack stack-3" style={{ marginBottom: 28, maxWidth: 640 }}>
      <div className="eyebrow accent">{eyebrow}</div>
      <h1 className="h-1">{title}</h1>
      {lead ? <p className="t-lead">{lead}</p> : null}
    </div>
  );
}

export function AboutPage() {
  return (
    <div className="container fade-in">
      <StaticHeader eyebrow="About" title="A parliament for the rest of us." />
      <div className="stack stack-5" style={{ maxWidth: 640 }}>
        <p className="t-body">
          Parliament is an independent, nonpartisan platform built to make civic engagement easier.
          Most Canadians can name a handful of politicians nationally — far fewer can name the people
          representing them at every level, from city hall to Queen&apos;s Park to Parliament Hill.
        </p>
        <p className="t-body">
          Enter a postal code and the Lookup Tool matches it to your municipal, provincial, and
          federal representatives — no account, no signup, nothing stored. Every entry links directly
          to a way to call, email, or write to that person.
        </p>
        <div className="card tint" style={{ padding: 18 }}>
          <div className="h-3" style={{ fontSize: 18, marginBottom: 6 }}>Coming soon</div>
          <p className="t-sm" style={{ margin: 0 }}>
            Candidate profiles. Ahead of upcoming elections, voters will be able to see everyone
            running in their ward or riding — not just the incumbents — making it easier to decide who
            to vote for.
          </p>
        </div>
        <div>
          <div className="section-label" style={{ marginBottom: 6 }}>Where the data comes from</div>
          <p className="t-body">
            Representative details are drawn from official government and legislature sources and
            re-verified on a rolling basis. Coverage is expanding level by level — Ontario and the
            federal Parliament are live today; more provinces and municipalities are being added.
          </p>
        </div>
      </div>
    </div>
  );
}

/** POST /contact. `website` is a honeypot: hidden, always empty, silently
 *  discarded server-side if filled. `candidate_uuid` is what makes a claim
 *  message actionable, so it rides along whenever we have one. */
export function ContactPage({
  candidateUuid = null, reason = null,
}: { candidateUuid?: string | null; reason?: "claim" | null }) {
  const [sent, setSent] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [form, setForm] = React.useState({ name: "", email: "", message: "", website: "" });
  const set = (k: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm({ ...form, [k]: e.target.value });

  const CAPS = { name: 200, email: 320, message: 5000 };
  const valid = form.name.trim() && form.email.trim() && form.message.trim();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    try {
      await candidateApi.contact({ candidate_uuid: candidateUuid, ...form });
      setSent(true);
    } catch {
      setSent(true); // nothing actionable to show the user; don't strand them
    } finally {
      setBusy(false);
    }
  };

  if (sent) {
    return (
      <div className="container fade-in" style={{ maxWidth: 480, textAlign: "center" }}>
        <div className="confirm-mark"><Icon name="check" size={26} stroke={2} /></div>
        <h1 className="h-1" style={{ marginTop: 18 }}>Message sent</h1>
        <p className="t-lead" style={{ marginTop: 10 }}>We read everything, and we&apos;ll reply by email.</p>
      </div>
    );
  }

  return (
    <div className="container fade-in">
      <StaticHeader
        eyebrow="Contact"
        title={reason === "claim" ? "Claim help." : "Get in touch."}
        lead={reason === "claim"
          ? "Tell us who you are and we'll verify your candidacy manually."
          : "Corrections, coverage requests, or anything else — we read everything."}
      />
      <form className="stack stack-3" style={{ maxWidth: 480 }} onSubmit={submit}>
        <div>
          <div className="field-label">Your name</div>
          <div className="field"><input value={form.name} onChange={set("name")} maxLength={CAPS.name} aria-label="Your name" /></div>
        </div>
        <div>
          <div className="field-label">Email</div>
          <div className="field"><input type="email" value={form.email} onChange={set("email")} maxLength={CAPS.email} placeholder="you@example.ca" aria-label="Email" /></div>
        </div>
        <div>
          <div className="field-label">Message</div>
          <div className="field" style={{ height: "auto", padding: "10px 14px" }}>
            <textarea value={form.message} onChange={set("message")} maxLength={CAPS.message} rows={5}
              style={{ width: "100%", border: 0, background: "transparent", font: "inherit", color: "inherit", resize: "vertical", outline: "none" }}
              aria-label="Message" />
          </div>
        </div>
        <div aria-hidden="true" style={{ position: "absolute", left: -9999, width: 1, height: 1, overflow: "hidden" }}>
          <label>Website
            <input type="text" name="website" tabIndex={-1} autoComplete="off" value={form.website} onChange={set("website")} />
          </label>
        </div>
        <button type="submit" className="act-btn primary" style={{ padding: 14, width: "100%" }} disabled={!valid || busy}>
          {busy ? "Sending…" : "Send message"}
        </button>
        {candidateUuid ? (
          <p className="t-xs" style={{ textAlign: "center" }}>
            Sent with your candidate page attached, so we can verify it faster.
          </p>
        ) : null}
      </form>
    </div>
  );
}

export function ForCandidatesPage({ onClaim }: { onClaim?: () => void }) {
  return (
    <div className="container fade-in">
      <StaticHeader
        eyebrow="For candidates"
        title="Your profile, ready for voters."
        lead="Every candidate certified for the October 26 municipal elections already has a page. Claim yours to add your website and a short pitch video."
      />
      <div className="stack stack-5" style={{ maxWidth: 640 }}>
        <p className="t-body">
          If you&apos;re running in the October 26 municipal elections, your race page already lists
          you alongside every other certified candidate. Claiming it lets you add a link to your
          campaign website and a self-recorded pitch video of up to sixty seconds.
        </p>
        <div className="card tint" style={{ padding: 18 }}>
          <div className="h-3" style={{ fontSize: 18, marginBottom: 6 }}>
            {CLAIM_AFFORDANCE_VISIBLE ? "Claim your page" : "Opening soon"}
          </div>
          <p className="t-sm" style={{ margin: 0, lineHeight: 1.55 }}>
            {CLAIM_AFFORDANCE_VISIBLE
              ? "Every certified candidate already has a page built from their municipality's official nomination filing. Find yours by name and add your website and pitch video."
              : "Candidate pages are live and every certified candidate is listed. Claiming opens before the October 26 election."}
          </p>
          {onClaim && CLAIM_AFFORDANCE_VISIBLE && SUBMISSIONS_ENABLED ? (
            <button type="button" className="act-btn primary" style={{ padding: 13, marginTop: 14, width: "100%" }} onClick={onClaim}>
              Find my page
            </button>
          ) : null}
        </div>
        <p className="t-sm">
          Can&apos;t find your name, or no email on file?{" "}
          <a href="mailto:candidates@parliament.example">Reach out</a> and we&apos;ll verify manually.
        </p>
      </div>
    </div>
  );
}
