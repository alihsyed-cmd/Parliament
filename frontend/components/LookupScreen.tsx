"use client";

// components/LookupScreen.tsx — accordion / responsive level grid + coverage gaps.
import React from "react";
import type { Level, LookupResponse, Politician } from "@/lib/types";
import { Icon } from "./Icon";
import { RepContactCard, Countdown } from "./ui";
import { ReminderToggle } from "./ReminderToggle";
import { formatDate, daysUntil, levelMeta } from "@/lib/format";
import { fullName, sortAlphabetical, submissionFor, useRaces } from "@/lib/candidates";
import type { CandidateRow, Race } from "@/lib/candidate-types";

/** How many names a race shows in place before it defers to its own screen.
 *  A mayoral field can run past forty; the panel is not the place to scroll it. */
const INLINE_CANDIDATES = 6;

/** One name on the ballot. Deliberately not the card the race screen uses: a
 *  level panel is a column among three, and cards that wide turn two races
 *  into a page of scrolling. */
function BallotName({ row, onOpen }: { row: CandidateRow; onOpen: (uuid: string) => void }) {
  const sub = submissionFor(row);
  return (
    <button type="button" className="ballot-name" onClick={() => onOpen(row.uuid)}>
      {sub?.video_uid ? (
        <span className="playdot" aria-hidden><svg viewBox="0 0 8 8"><path d="M0 0l8 4-8 4z" /></svg></span>
      ) : null}
      <span className="nm">{fullName(row)}</span>
      {sub?.website ? <span className="url">{sub.website.replace(/^https?:\/\//, "")}</span> : null}
    </button>
  );
}

/** The certified candidates for the seats this level elects, shown inside the
 *  level's own panel alongside the people currently holding them. Which races
 *  belong here is decided by the jurisdiction slug, so a roster can only ever
 *  surface under the level that runs that election.
 *
 *  Every ballot line the viewer can vote on is listed: the head of government's
 *  race, their own ward, and any other jurisdiction-wide seat. Names are shown
 *  for the two that are unambiguously theirs. The rest are jurisdiction-wide
 *  seats that vary in kind by city — Markham elects Regional Councillors at
 *  large, Brampton runs five ward-pair races — so they get a line each and
 *  open on their own screen rather than turning the panel into a ballot. */
function LevelCandidates({
  slug, races, districtId, onSeeCandidates, onOpenRace, onOpenCandidate,
}: {
  slug: string;
  races: Race[];
  /** The viewer's own ward, straight off this level's representative. */
  districtId?: string;
  onSeeCandidates: (slug: string) => void;
  onOpenRace: (slug: string, raceKey: string) => void;
  onOpenCandidate: (uuid: string) => void;
}) {
  // An empty district_id is the contract for a jurisdiction-wide race, so it is
  // on everyone's ballot; a ward race is on one voter's. Among the
  // jurisdiction-wide races, the unlabelled one is the head of government's.
  const wide = races.filter((r) => !r.district_id);
  const head = wide.find((r) => !r.district_name);
  const ward = districtId ? races.find((r) => r.district_id === districtId) : undefined;
  const named = [head, ward].filter(Boolean) as Race[];
  const mine = [...named, ...wide.filter((r) => r !== head)];

  return (
    <div className="stack stack-2">
      <div className="row between" style={{ marginBottom: 4 }}>
        <span className="section-label">On the ballot</span>
        <button className="btn ghost sm" onClick={() => onSeeCandidates(slug)}>
          All {races.length} race{races.length === 1 ? "" : "s"} <Icon name="chevron_right" size={14} />
        </button>
      </div>

      {mine.length ? mine.map((r) => {
        const rows = sortAlphabetical(r.candidates);
        const shown = named.includes(r) ? rows.slice(0, INLINE_CANDIDATES) : [];
        return (
          <div key={r.key} className="stack stack-2">
            <button type="button" className="race-line" onClick={() => onOpenRace(slug, r.key)}>
              <span className="accent">{r.title}</span>
              <span className="ct">{rows.length} certified</span>
              <Icon name="chevron_right" size={13} />
            </button>
            {shown.length ? (
              <div className="ballot-list">
                {shown.map((c) => <BallotName key={c.uuid} row={c} onOpen={onOpenCandidate} />)}
                {rows.length > shown.length ? (
                  <button type="button" className="ballot-name more" onClick={() => onOpenRace(slug, r.key)}>
                    <span className="nm">+{rows.length - shown.length} more on this ballot line</span>
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        );
      }) : (
        // Nothing on this viewer's own ballot lines — an unmatched ward, or a
        // roster that is still only other wards. The chooser has all of it.
        <button type="button" className="card button cand-cta" onClick={() => onSeeCandidates(slug)}>
          <span className="row between">
            <span className="h-3">See who&apos;s running</span>
            <Icon name="chevron_right" size={20} className="chevron" />
          </span>
        </button>
      )}
    </div>
  );
}

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
  onSeeCandidates, onOpenRace, onOpenCandidate,
}: {
  level: Level; open: boolean; wide: boolean;
  onToggle: () => void; onRep: (p: Politician, l: Level) => void; onSeeAll: (l: Level) => void;
  onSeeCandidates?: (slug: string) => void;
  onOpenRace: (slug: string, raceKey: string) => void;
  onOpenCandidate: (uuid: string) => void;
}) {
  const meta = levelMeta[level.level];
  const gov = level.jurisdiction.governance;
  const isGap = !gov || level._gap;
  const others = level.cabinet.length + level.other_leadership.length;
  const days = gov?.next_election && gov.election_date_set ? daysUntil(gov.next_election) : null;
  const showBody = wide || open;

  // Asked for every level, not just the municipal one, so a roster shows up
  // wherever it exists. Levels with none 404 once and are remembered as empty.
  // Loading (null) and none ([]) both render nothing, so the block appears when
  // there is something to appear for rather than flashing an empty heading.
  const slug = level.jurisdiction.slug;
  const races = useRaces(isGap ? undefined : slug);
  const hasRaces = !!slug && !!races && races.length > 0;
  const runningCount = hasRaces ? races.reduce((n, r) => n + r.candidates.length, 0) : 0;
  const myWard = level.representatives?.[0]?.district_id;

  return (
    <div className={`acc ${showBody ? "open" : ""}`}>
      <button type="button" className="acc-head" onClick={onToggle} aria-expanded={showBody}>
        <span className="badge">{meta.badge}</span>
        <span className="fill">
          <span className="eyebrow" style={{ display: "block", marginBottom: 2 }}>{meta.tag}</span>
          <span className="level-name" style={{ display: "block" }}>{level.jurisdiction.name}</span>
          {isGap ? (
            <span className="level-sub" style={{ display: "block" }}>
              <span className="accent">Coverage coming soon</span>
            </span>
          ) : !showBody && hasRaces ? (
            <span className="level-sub" style={{ display: "block" }}>
              <span className="accent">{runningCount} candidates running</span>
            </span>
          ) : null}
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
                  <RepContactCard pol={level.executive} onOpen={() => onRep(level.executive!, level)} />
                </div>
              ) : null}

              {level.representatives.length ? (
                <div className="stack stack-2">
                  <div className="section-label" style={{ marginBottom: 4 }}>
                    Your {level.representatives.length > 1 ? gov!.role_label_plural : gov!.role_label_singular}
                  </div>
                  {level.representatives.map((r) => (
                    <RepContactCard key={r.uuid} pol={r} onOpen={() => onRep(r, level)} />
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

              {hasRaces && onSeeCandidates ? (
                <LevelCandidates
                  slug={slug!} races={races!} districtId={myWard}
                  onSeeCandidates={onSeeCandidates}
                  onOpenRace={onOpenRace} onOpenCandidate={onOpenCandidate}
                />
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
  data, postal, onRep, onSeeAll, onSeeCandidates, onOpenRace, onOpenCandidate,
}: {
  data: LookupResponse; postal: string;
  onRep: (p: Politician, l: Level) => void; onSeeAll: (l: Level) => void;
  onSeeCandidates?: (slug: string) => void;
  onOpenRace: (slug: string, raceKey: string) => void;
  onOpenCandidate: (uuid: string) => void;
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
        <p className="t-lead">Plus {totalOther} more in cabinet, opposition &amp; leadership across {covered} levels. Open a level to call or email yours — right here.</p>
      </div>

      <div className="levels-grid">
        {data.levels.map((lvl, i) => (
          <LevelPanel
            key={lvl.level}
            level={lvl} open={openIdx === i} wide={wide}
            onToggle={() => setOpenIdx(openIdx === i ? -1 : i)}
            onRep={onRep} onSeeAll={onSeeAll}
            onSeeCandidates={onSeeCandidates}
            onOpenRace={onOpenRace} onOpenCandidate={onOpenCandidate}
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
