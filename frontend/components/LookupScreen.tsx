"use client";

import React from "react";
import type { Level, LookupResponse, Politician } from "@/lib/types";
import { Icon } from "./Icon";
import { RepRow, Countdown } from "./ui";
import { ReminderToggle } from "./ReminderToggle";
import { formatDate, daysUntil, levelMeta } from "@/lib/format";

function CoverageGap({ level }: { level: string }) {
  const who = level === "municipal" ? "your municipality" : level === "provincial" ? "your province" : "Canada";
  return (
    <div className="card hatch ghost" style={{ background: "var(--paper-2)" }}>
      <div className="row row-gap-3" style={{ alignItems: "flex-start", marginBottom: 12 }}>
        <div style={{ width: 36, height: 36, borderRadius: 10, background: "var(--paper)", border: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <Icon name="info" size={18} />
        </div>
        <div>
          <div className="h-3" style={{ fontSize: 18 }}>We&apos;re still mapping {who}.</div>
          <p className="t-sm" style={{ marginTop: 2 }}>
            Some {level} jurisdictions aren&apos;t in our database yet — smaller ones take longer to verify.
          </p>
        </div>
      </div>
      <div className="row row-gap-2 wrap">
        <button className="btn primary sm"><Icon name="bell" size={14} /> Notify me</button>
        <button className="btn outline sm">Help map it</button>
      </div>
    </div>
  );
}

function LevelPanel({
  level, open, wide, onToggle, onRep, onSeeAll,
}: {
  level: Level; open: boolean; wide: boolean;
  onToggle: () => void; onRep: (p: Politician, l: Level) => void; onSeeAll: (l: Level) => void;
}) {
  const meta = levelMeta[level.level];
  const gov = level.jurisdiction.governance;
  const isGap = !gov || level._gap;
  const people = (level.executive ? 1 : 0) + level.representatives.length;
  const others = level.cabinet.length + level.other_leadership.length;
  const days = gov?.next_election && gov.election_date_set ? daysUntil(gov.next_election) : null;
  const showBody = wide || open;

  return (
    <div className={`acc ${showBody ? "open" : ""}`}>
      <button type="button" className="acc-head" onClick={onToggle} aria-expanded={showBody}>
        <span className="badge">{meta.badge}</span>
        <span className="fill">
          <span className="eyebrow" style={{ display: "block", marginBottom: 2 }}>{meta.tag}</span>
          <span className="level-name" style={{ display: "block" }}>{level.jurisdiction.name}</span>
          <span className="level-sub" style={{ display: "block" }}>
            {isGap ? <span className="accent">Coverage coming soon</span>
              : <>{people} {people === 1 ? "person" : "people"} · {others} more in cabinet &amp; leadership</>}
          </span>
        </span>
        <span className="toggle"><Icon name="chevron_down" size={16} stroke={2} /></span>
      </button>

      {showBody ? (
        <div className="acc-body">
          {isGap ? <CoverageGap level={level.level} /> : (
            <>
              {level.executive ? (
                <div>
                  <div className="section-label" style={{ marginBottom: 4 }}>{meta.execTitle}</div>
                  <RepRow pol={level.executive} onClick={() => onRep(level.executive!, level)} />
                </div>
              ) : null}

              {level.representatives.length ? (
                <div>
                  <div className="section-label" style={{ marginBottom: 4 }}>
                    Your {level.representatives.length > 1 ? gov!.role_label_plural : gov!.role_label_singular}
                  </div>
                  {level.representatives.map((r) => (
                    <RepRow key={r.uuid} pol={r} onClick={() => onRep(r, level)} />
                  ))}
                </div>
              ) : null}

              {others > 0 ? (
                <div className="card tint" style={{ padding: 14 }}>
                  <div className="row between" style={{ marginBottom: 10 }}>
                    <span className="section-label">Cabinet &amp; leadership · {others}</span>
                    <button className="btn ghost sm" onClick={() => onSeeAll(level)}>See all <Icon name="chevron_right" size={14} /></button>
                  </div>
                  <div className="row row-gap-2 wrap">
                    {level.cabinet.slice(0, 3).map((c) => <span key={c.uuid} className="chip outline">{c.display_title}</span>)}
                    {level.cabinet.length > 3 ? <span className="chip outline" style={{ color: "var(--ink-3)" }}>+{level.cabinet.length - 3}</span> : null}
                  </div>
                </div>
              ) : null}

              {gov ? (
                <div className="row between" style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--ink-3)", paddingTop: 2 }}>
                  <span>{gov.election_date_set ? `NEXT · ${formatDate(gov.next_election)}` : `LAST · ${formatDate(gov.last_election)}`}</span>
                  {days != null && days < 365 ? <Countdown days={days} /> : null}
                </div>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function LookupScreen({
  data, postal, onRep, onSeeAll,
}: {
  data: LookupResponse; postal: string;
  onRep: (p: Politician, l: Level) => void; onSeeAll: (l: Level) => void;
}) {
  const firstCovered = data.levels.findIndex((l) => !l._gap && l.jurisdiction.governance);
  const [openIdx, setOpenIdx] = React.useState(firstCovered === -1 ? 0 : firstCovered);
  const [wide, setWide] = React.useState(false);

  React.useEffect(() => {
    const mq = window.matchMedia("(min-width: 920px)");
    const update = () => setWide(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  const totalPeople = data.levels.reduce((n, l) => n + (l.executive ? 1 : 0) + l.representatives.length, 0);
  const totalOther = data.levels.reduce((n, l) => n + l.cabinet.length + l.other_leadership.length, 0);
  const covered = data.levels.filter((l) => !l._gap).length;
  const allGaps = data.levels.every((l) => l._gap);

  if (allGaps) {
    return (
      <div className="container fade-in">
        <div className="stack stack-4" style={{ maxWidth: 480 }}>
          <div className="eyebrow accent">No coverage yet</div>
          <h1 className="h-1">We haven&apos;t mapped <span className="h-italic serif">{postal}</span> yet.</h1>
          <p className="t-lead">We&apos;re working to cover every postal code in Canada. Turn on a reminder and we&apos;ll let you know when this area is live.</p>
          <ReminderToggle postalCode={postal.replace(/\s/g, "")} />
        </div>
      </div>
    );
  }

  return (
    <div className="container wide fade-in">
      <div className="stack stack-3" style={{ marginBottom: 24, maxWidth: 640 }}>
        <div className="eyebrow accent">Your government</div>
        <h1 className="h-1"><span className="h-italic serif">{totalPeople} {totalPeople === 1 ? "person" : "people"}</span> represent you.</h1>
        <p className="t-lead">Plus {totalOther} more in cabinet, opposition &amp; leadership across {covered} levels.</p>
      </div>

      <div className="levels-grid">
        {data.levels.map((lvl, i) => (
          <LevelPanel
            key={lvl.level}
            level={lvl} open={openIdx === i} wide={wide}
            onToggle={() => setOpenIdx(openIdx === i ? -1 : i)}
            onRep={onRep} onSeeAll={onSeeAll}
          />
        ))}
      </div>

      <div style={{ marginTop: 28, maxWidth: 640 }}>
        <ReminderToggle postalCode={postal.replace(/\s/g, "")} />
      </div>

      <div className="trust-footer" style={{ maxWidth: 640 }}>
        <span><span className="pill"><Icon name="check" size={10} /> VERIFIED</span> Last checked from official sources</span>
        <a href="#">Sources →</a>
      </div>
    </div>
  );
}
