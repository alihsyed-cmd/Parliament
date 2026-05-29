"use client";

import React from "react";
import type { JurisdictionResponse, Level, Politician } from "@/lib/types";
import { Icon } from "./Icon";
import { Avatar, PartyChip, RepRow, Skeleton } from "./ui";
import { levelMeta } from "@/lib/format";

function CollapsibleGroup({
  title, people, defaultOpen, onRep,
}: {
  title: string; people: Politician[]; defaultOpen?: boolean; onRep: (p: Politician) => void;
}) {
  const [open, setOpen] = React.useState(!!defaultOpen);
  if (!people.length) return null;
  return (
    <div className={`card ${open ? "" : "tint"}`}>
      <button type="button" className="sub-head" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className="label">{title} <span className="chip outline" style={{ padding: "2px 8px", fontSize: 11 }}>{people.length}</span></span>
        <Icon name={open ? "minus" : "plus"} size={16} stroke={2} />
      </button>
      {open ? (
        <div className="stack" style={{ marginTop: 8 }}>
          {people.map((m, i) => (
            <React.Fragment key={m.uuid || i}>
              {i > 0 ? <hr className="divider" /> : null}
              <RepRow pol={m} nameSize={16} onClick={() => onRep(m)} />
            </React.Fragment>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function RosterScreen({
  level, data, loading, onRep,
}: {
  level: Level;
  data: JurisdictionResponse | null;
  loading: boolean;
  onRep: (p: Politician, l: Level) => void;
}) {
  const meta = levelMeta[level.level];
  const gov = level.jurisdiction.governance;
  const src = data ?? level;
  const executive = src.executive;
  const cabinet = src.cabinet ?? [];
  const otherLeadership = src.other_leadership ?? [];
  const reps = src.representatives ?? [];

  const [query, setQuery] = React.useState("");
  const filtered = reps.filter((r) =>
    !query ||
    r.full_name.toLowerCase().includes(query.toLowerCase()) ||
    (r.district_name || "").toLowerCase().includes(query.toLowerCase()) ||
    (r.party_name || "").toLowerCase().includes(query.toLowerCase())
  );

  const handleRep = (p: Politician) => onRep(p, level);

  return (
    <div className="container fade-in">
      <div className="stack stack-3" style={{ marginBottom: 24 }}>
        <div className="eyebrow accent">{meta.tag} · {meta.brand}</div>
        <h1 className="h-1">{level.jurisdiction.name}</h1>
        {gov?.governance_summary ? <p className="t-lead">{gov.governance_summary}</p> : null}
      </div>

      {loading && !data ? (
        <div className="stack stack-3">
          {[0, 1, 2, 3].map((i) => (
            <div className="card" key={i}>
              <div className="row row-gap-3">
                <Skeleton w={44} h={44} r={22} />
                <div className="stack stack-2 fill"><Skeleton w="60%" h={13} /><Skeleton w="40%" h={18} /></div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="stack stack-3" style={{ marginBottom: 28 }}>
            <div className="row between" style={{ alignItems: "baseline" }}>
              <h2 className="h-2">Leadership</h2>
              <span className="t-xs">{(executive ? 1 : 0) + cabinet.length + otherLeadership.length} people</span>
            </div>

            {executive ? (
              <div className="card accent">
                <div className="eyebrow accent" style={{ marginBottom: 8 }}>{meta.execTitle}</div>
                <button type="button" className="rep" style={{ padding: 0 }} onClick={() => handleRep(executive)}>
                  <Avatar pol={executive} size="lg" />
                  <span className="fill">
                    <span className="rep-name" style={{ fontSize: 22, display: "block" }}>{executive.full_name}</span>
                    <span className="rep-sub"><span>{executive.display_title}</span></span>
                    {executive.party_name ? <span style={{ display: "inline-block", marginTop: 8 }}><PartyChip pol={executive} /></span> : null}
                  </span>
                  <Icon name="chevron_right" size={20} className="chevron" />
                </button>
              </div>
            ) : null}

            <CollapsibleGroup title="Cabinet" people={cabinet} defaultOpen onRep={handleRep} />
            <CollapsibleGroup title="Opposition & Speakers" people={otherLeadership} onRep={handleRep} />
          </div>

          <div className="stack stack-3">
            <div className="row between" style={{ alignItems: "baseline" }}>
              <h2 className="h-2">All {gov?.role_label_plural || "representatives"}</h2>
              <span className="t-xs">{reps.length} total</span>
            </div>
            <div className="search">
              <Icon name="search" size={16} />
              <input
                placeholder={`Search by name, party, or ${gov?.district_term?.toLowerCase() || "district"}…`}
                value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search representatives"
              />
            </div>
            <div className="stack">
              {filtered.map((r, i) => (
                <React.Fragment key={r.uuid || i}>
                  {i > 0 ? <hr className="divider" /> : null}
                  <button type="button" className="rep" onClick={() => handleRep(r)}>
                    <Avatar pol={r} size="sm" />
                    <span className="fill">
                      <span className="rep-name" style={{ fontSize: 17, display: "block" }}>{r.full_name}</span>
                      <span className="rep-sub">
                        <span>{r.district_name}</span>
                        {r.party_name ? <><span className="sep" /><span className="accent">{r.party_name}</span></> : null}
                      </span>
                    </span>
                    <Icon name="chevron_right" size={16} className="chevron" />
                  </button>
                </React.Fragment>
              ))}
              {filtered.length === 0 && reps.length > 0 ? (
                <p className="t-sm" style={{ textAlign: "center", padding: 24, color: "var(--ink-3)" }}>No matches for &quot;{query}&quot;</p>
              ) : null}
              {reps.length === 0 ? (
                <p className="t-sm" style={{ textAlign: "center", padding: 24, color: "var(--ink-3)" }}>No representatives loaded yet.</p>
              ) : null}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
