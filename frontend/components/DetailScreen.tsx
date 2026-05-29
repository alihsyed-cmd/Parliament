"use client";

import React from "react";
import type { Level, Politician, Representation, RepresentativeResponse } from "@/lib/types";
import { Icon } from "./Icon";
import { Avatar, PartyChip } from "./ui";
import { formatDate, daysUntil, levelMeta } from "@/lib/format";

const ROLE_BLURB: Record<string, Record<string, string>> = {
  representative: {
    municipal: "Your councillor sits at City Hall, voting on by-laws, the city budget, transit, and zoning that affect your block.",
    provincial: "Your MPP represents you at the legislature — voting on provincial laws covering health, education, housing, and transit.",
    federal: "Your MP represents your riding in the House of Commons — voting on federal laws, the budget, and treaties.",
  },
  executive: {
    municipal: "The Mayor chairs council and represents the city to the province and the public.",
    provincial: "The Premier leads the provincial government and cabinet, and sets the legislative agenda.",
    federal: "The Prime Minister leads the federal government, chairs cabinet, and heads the executive branch.",
  },
};

function blurbFor(rep: Politician, level: string) {
  if (rep.standard_role === "executive") return ROLE_BLURB.executive[level];
  if (rep.standard_role === "cabinet") return "A cabinet minister leads a portfolio of government — proposing laws, setting policy, and answering to the legislature.";
  if (rep.standard_role === "misc") return "A leadership role — opposition, party leader, critic, or speaker. Not your direct representative, but a key voice in the chamber.";
  return ROLE_BLURB.representative[level] ?? "";
}

export function DetailScreen({
  rep, level, detail, onBack, onSeeJurisdiction,
}: {
  rep: Politician;
  level: Level;
  detail: RepresentativeResponse | null;
  onBack: () => void;
  onSeeJurisdiction: (l: Level) => void;
}) {
  const meta = levelMeta[level.level];
  const gov = level.jurisdiction.governance;
  const representations: Representation[] = detail?.representations ?? [];
  const multiRole = representations.length > 1 || (rep.roles?.length ?? 0) > 1;

  const electedIso = rep.date_elected || gov?.last_election || "";
  const nextIso = rep.next_election || (gov?.election_date_set ? gov?.next_election : "");
  const daysOut = nextIso ? daysUntil(nextIso) : null;
  const verified = detail?.representative.last_verified;

  return (
    <div className="container fade-in">
      <div className="row row-gap-4" style={{ marginBottom: 18, alignItems: "flex-start" }}>
        <Avatar pol={rep} size="xl" />
        <div className="fill">
          <div className="eyebrow accent" style={{ marginBottom: 6 }}>{meta.tag}</div>
          <h1 className="h-1" style={{ fontSize: 30 }}>{rep.full_name}</h1>
          <p className="t-sm" style={{ marginTop: 6 }}>{rep.display_title}</p>
          <div className="row row-gap-2 wrap" style={{ marginTop: 10 }}>
            {rep.party_name ? <PartyChip pol={rep} /> : <span className="chip">Non-partisan</span>}
            {rep.district_name ? <span className="chip outline"><Icon name="map_pin" size={11} /> {rep.district_name}</span> : null}
          </div>
        </div>
      </div>

      <div className="detail-grid">
        <div className="stack stack-4">
          <div className="stack stack-3">
            <div className="eyebrow accent">Get in touch</div>
            <div className="contact-row">
              {rep.phone ? (
                <a className="contact-btn primary" href={`tel:${rep.phone.replace(/[^\d+]/g, "")}`}>
                  <Icon name="phone" size={22} stroke={1.8} /><span className="lbl">Call</span><span className="val" style={{ opacity: .85 }}>{rep.phone}</span>
                </a>
              ) : null}
              {rep.email ? (
                <a className="contact-btn" href={`mailto:${rep.email}`}>
                  <Icon name="mail" size={22} /><span className="lbl">Email</span><span className="val">{rep.email}</span>
                </a>
              ) : null}
              {rep.website ? (
                <a className="contact-btn" href={/^https?:/.test(rep.website) ? rep.website : `https://${rep.website}`} target="_blank" rel="noreferrer">
                  <Icon name="link" size={22} /><span className="lbl">Website</span><span className="val">{rep.website.replace(/^https?:\/\//, "").replace(/^www\./, "").split("/")[0]}</span>
                </a>
              ) : null}
            </div>
            <p className="t-xs" style={{ textAlign: "center", color: "var(--ink-3)" }}>
              Calling or writing is the single most effective thing you can do.
            </p>
          </div>

          {multiRole ? (
            <div className="card">
              <div className="eyebrow" style={{ marginBottom: 10 }}>Roles held</div>
              <div className="stack stack-3">
                {(representations.length ? representations.map((r) => r.specific_title) : rep.roles ?? []).map((title, i) => (
                  <div className="row row-gap-3" key={i}>
                    <span className="party" style={{ position: "static", width: 8, height: 8, borderRadius: 4, background: "var(--accent)", minWidth: 0, minHeight: 0, border: 0 }} />
                    <span className="t-body">{title}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="card">
            <div className="eyebrow" style={{ marginBottom: 8 }}>What this role does</div>
            <p className="t-body">{blurbFor(rep, level.level)}</p>
          </div>
        </div>

        <div className="stack stack-4">
          <div className="card">
            <div className="eyebrow" style={{ marginBottom: 12 }}>Term &amp; elections</div>
            <div className="stack stack-3">
              {electedIso ? (
                <div className="row row-gap-3">
                  <span style={{ width: 32, height: 32, borderRadius: 8, background: "var(--paper-2)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><Icon name="star" size={15} /></span>
                  <span><span className="t-xs" style={{ display: "block" }}>First elected</span><span className="t-body" style={{ fontWeight: 500 }}>{formatDate(electedIso)}</span></span>
                </div>
              ) : null}
              {nextIso ? (
                <div className="row row-gap-3">
                  <span style={{ width: 32, height: 32, borderRadius: 8, background: "var(--accent-soft)", color: "var(--accent-ink)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><Icon name="cal" size={15} /></span>
                  <span>
                    <span className="t-xs" style={{ display: "block" }}>Next election</span>
                    <span className="t-body" style={{ fontWeight: 500 }}>
                      {formatDate(nextIso)}
                      {daysOut != null && daysOut > 0 && daysOut < 365 ? <span className="accent mono" style={{ fontSize: 12, marginLeft: 8 }}>· in {daysOut} days</span> : null}
                    </span>
                  </span>
                </div>
              ) : (
                gov?.last_election ? (
                  <p className="t-sm" style={{ color: "var(--ink-3)" }}>No date set. Last election: {formatDate(gov.last_election)}.</p>
                ) : null
              )}
            </div>
          </div>

          <button type="button" className="card button" onClick={() => onSeeJurisdiction(level)}>
            <div className="row between">
              <span>
                <span className="eyebrow" style={{ display: "block", marginBottom: 4 }}>{meta.tag}</span>
                <span className="h-3">{level.jurisdiction.name}</span>
                <span className="t-xs" style={{ display: "block", marginTop: 4 }}>See all {gov?.role_label_plural} &amp; leadership →</span>
              </span>
              <Icon name="chevron_right" size={20} className="chevron" />
            </div>
          </button>
        </div>
      </div>

      <div className="trust-footer">
        <span><span className="pill"><Icon name="check" size={10} /> VERIFIED</span> {verified ? formatDate(verified) : "from official sources"}</span>
        {detail?.representative.source_url ? <a href={detail.representative.source_url} target="_blank" rel="noreferrer">Source →</a> : null}
      </div>
    </div>
  );
}
