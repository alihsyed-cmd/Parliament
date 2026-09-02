"use client";

// components/CandidateScreens.tsx — voter-facing candidate surfaces.
// RaceChooser → RaceListScreen (two-column name grid) → CandidateProfileScreen.

import React from "react";
import type { CandidateRow } from "@/lib/candidate-types";
import {
  CLAIM_AFFORDANCE_VISIBLE, fullName, municipalityName, officeLine, raceByKey,
  racesFor, sortAlphabetical, streamThumb, submissionFor,
} from "@/lib/candidates";
import { Icon } from "./Icon";

function ElectionFooterNote() {
  return (
    <p className="t-xs" style={{ textAlign: "center", color: "var(--ink-3)" }}>
      Municipal election · Monday, October 26, 2026
    </p>
  );
}

export function RaceChooser({
  slug, onOpenRace,
}: { slug: string; onOpenRace: (key: string) => void }) {
  const races = racesFor(slug);
  const name = municipalityName(slug);
  return (
    <div className="container fade-in">
      <div className="stack stack-3" style={{ marginBottom: 26, maxWidth: 620 }}>
        <div className="eyebrow accent">
          {races.length === 1 ? "One race" : `${races.length} races`} on your ballot
        </div>
        <h1 className="h-1">Who&apos;s running in {name}</h1>
        <p className="t-lead">Pick a race to see every certified candidate on that ballot line.</p>
      </div>
      <div className="stack stack-3" style={{ maxWidth: 620 }}>
        {races.map((r) => (
          <button type="button" className="card button race-card" key={r.key} onClick={() => onOpenRace(r.key)}>
            <span className="row between">
              <span>
                <span className="h-3" style={{ display: "block" }}>{r.title}</span>
                <span className="t-xs" style={{ display: "block", marginTop: 4 }}>
                  {r.candidates.length} candidate{r.candidates.length === 1 ? "" : "s"} certified
                </span>
              </span>
              <Icon name="chevron_right" size={20} className="chevron" />
            </span>
          </button>
        ))}
      </div>
      <div style={{ marginTop: 24 }}><ElectionFooterNote /></div>
    </div>
  );
}

function CandidateCell({ row, onOpen }: { row: CandidateRow; onOpen: (uuid: string) => void }) {
  const sub = submissionFor(row);
  return (
    <button type="button" className="cand-cell" onClick={() => onOpen(row.uuid)}>
      <span className="nm">{fullName(row)}</span>
      <span className="mt">
        {sub?.video_uid ? (
          <>
            <span className="playdot" aria-hidden><svg viewBox="0 0 8 8"><path d="M0 0l8 4-8 4z" /></svg></span>
            <span className="url">{sub.website || "Video"}</span>
          </>
        ) : sub?.website ? (
          <span className="url">{sub.website}</span>
        ) : (
          <span>No profile yet</span>
        )}
      </span>
    </button>
  );
}

export function RaceListScreen({
  raceKey: key, onOpenCandidate,
}: { raceKey: string; onOpenCandidate: (uuid: string) => void }) {
  const race = raceByKey(key);
  if (!race) return null;
  const rows = sortAlphabetical(race.candidates);
  const submitted = rows.filter((r) => submissionFor(r)).length;

  return (
    <div className="container fade-in">
      <div className="stack stack-3" style={{ marginBottom: 22, maxWidth: 620 }}>
        <div className="eyebrow accent">
          {municipalityName(race.jurisdiction_slug)} · {race.title}
        </div>
        <h1 className="h-1">{rows.length} candidates on your ballot</h1>
        <div className="card tint" style={{ padding: "12px 15px" }}>
          <p className="t-sm" style={{ margin: 0, lineHeight: 1.5 }}>
            Listed alphabetically by surname. Parliament doesn&apos;t rank, feature, or recommend candidates.
          </p>
        </div>
      </div>
      <div className="cand-grid">
        {rows.map((r) => <CandidateCell key={r.uuid} row={r} onOpen={onOpenCandidate} />)}
      </div>
      <div className="stack stack-3" style={{ marginTop: 22, maxWidth: 620 }}>
        <div className="notlisted-box">
          <p className="t-sm" style={{ margin: 0, lineHeight: 1.5 }}>
            {submitted === 0
              ? "None of these candidates have submitted a profile yet. Profiles open as candidates claim their pages — every certified candidate is listed here either way."
              : `${submitted} of ${rows.length} have submitted a profile. The rest are still on your ballot.`}
          </p>
        </div>
        <ElectionFooterNote />
      </div>
    </div>
  );
}

export function CandidateProfileScreen({
  row, onClaim,
}: { row: CandidateRow; onClaim: (uuid: string) => void }) {
  const sub = submissionFor(row);
  const claimed = !!sub;
  const muni = municipalityName(row.jurisdiction_slug);
  const href = sub?.website
    ? (/^https?:/.test(sub.website) ? sub.website : `https://${sub.website}`)
    : null;

  return (
    <div className="container fade-in" style={{ maxWidth: 620 }}>
      <div className="src-tag" style={{ marginBottom: 18 }}>
        <Icon name="check" size={12} />{" "}
        {claimed ? "Submitted by the candidate" : "From the official nomination filing"}
      </div>
      <h1 className="h-1" style={{ fontSize: 40, lineHeight: 1.04 }}>
        {row.first_name}<br />{row.last_name}
      </h1>
      <p className="t-lead" style={{ marginTop: 12 }}>Candidate for {officeLine(row)}</p>

      {claimed ? (
        <div className="stack stack-3" style={{ marginTop: 22 }}>
          {sub!.video_uid ? (
            <div className="vid-thumb">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={streamThumb(sub!.video_uid!)} alt=""
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
              <div className="play"><span><Icon name="play" size={15} /></span></div>
            </div>
          ) : null}
          {href ? (
            <a className="act-btn primary" href={href} target="_blank" rel="noreferrer" style={{ padding: 14 }}>
              Visit website <span className="mono" style={{ fontSize: 13, opacity: 0.85 }}>{sub!.website}</span> ↗
            </a>
          ) : null}
        </div>
      ) : (
        <div className="card ghost" style={{ padding: 18, marginTop: 22 }}>
          <div className="eyebrow">On your ballot, October 26</div>
          <p className="t-body" style={{ marginTop: 8, lineHeight: 1.5 }}>
            This is the complete record Parliament has for this candidate: name, office, and ward, as
            certified by the City of {muni}. No website or campaign video has been submitted.
          </p>
        </div>
      )}

      {CLAIM_AFFORDANCE_VISIBLE ? (
        <div className="claim-quiet">
          <span>{claimed ? "This is your page?" : "Is this your page?"}</span>
          <a href="#" onClick={(e) => { e.preventDefault(); onClaim(row.uuid); }}>
            {claimed ? "Manage it" : "Claim it"}
          </a>
        </div>
      ) : null}
      <div style={{ marginTop: 20 }}><ElectionFooterNote /></div>
    </div>
  );
}
