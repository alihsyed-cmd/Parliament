"use client";

// components/BrowseScreens.tsx — Browse tree (municipal / provincial / federal)
// and the Ontario province roll-up. Mock data until /jurisdictions exists.

import React from "react";
import {
  FEDERAL_RIDINGS, ON_MPPS, ON_MUNICIPALITIES, PROVINCES, type BrowseItem,
} from "@/lib/browse-data";
import { Icon } from "./Icon";

function StatusChip({ covered }: { covered: boolean }) {
  return covered
    ? <span className="chip accent">Live</span>
    : <span className="chip outline" style={{ color: "var(--ink-3)" }}>Coming soon</span>;
}

function ComingSoonNote({ noun }: { noun: string }) {
  return (
    <div className="card hatch ghost" style={{ padding: 14 }}>
      <p className="t-sm" style={{ margin: 0 }}>
        We haven&apos;t verified this {noun}&apos;s representatives yet. It&apos;s in our mapping queue.
      </p>
    </div>
  );
}

function PersonRow({ name, sub, initials }: { name: string; sub: string; initials: string }) {
  return (
    <div className="rep" style={{ cursor: "default" }}>
      <span className="avatar sm"><span>{initials}</span></span>
      <span className="fill">
        <span className="rep-name" style={{ fontSize: 17, display: "block" }}>{name}</span>
        <span className="rep-sub"><span>{sub}</span></span>
      </span>
    </div>
  );
}

function BrowseSection({
  title, subtitle, count, items, expandedName, setExpandedName, renderExpanded,
}: {
  title: string; subtitle: string; count: number; items: BrowseItem[];
  expandedName: string | null;
  setExpandedName: (n: string | null) => void;
  renderExpanded: (item: BrowseItem) => React.ReactNode;
}) {
  return (
    <section className="stack stack-3">
      <div className="row between" style={{ alignItems: "baseline" }}>
        <div>
          <div className="eyebrow accent">{title}</div>
          <div className="t-xs" style={{ marginTop: 2 }}>{subtitle}</div>
        </div>
        <span className="t-xs mono">{count} listed</span>
      </div>
      <div className="stack stack-2">
        {items.map((item) => {
          const open = expandedName === item.name;
          return (
            <div key={item.name} className={`acc ${open ? "open" : ""}`} style={{ borderRadius: "var(--r-md)" }}>
              <button type="button" className="acc-head" style={{ padding: "14px 16px" }}
                onClick={() => setExpandedName(open ? null : item.name)} aria-expanded={open}>
                <span className="fill row between">
                  <span className="level-name" style={{ fontSize: 17 }}>{item.name}</span>
                  <span className="row row-gap-3">
                    <StatusChip covered={item.covered} />
                    <Icon name="chevron_down" size={15} stroke={2}
                      style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .2s", color: "var(--ink-3)" }} />
                  </span>
                </span>
              </button>
              {open ? <div className="acc-body" style={{ padding: "0 16px 16px" }}>{renderExpanded(item)}</div> : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function BrowsePage({
  focus, onOpenProvince,
}: {
  focus?: { section: string; name: string } | null;
  onOpenProvince: (slug: string) => void;
}) {
  const [expanded, setExpanded] = React.useState<Record<string, string | null>>({
    municipal: focus?.section === "municipal" ? focus.name : null,
    provincial: focus?.section === "provincial" ? focus.name : null,
    federal: focus?.section === "federal" ? focus.name : null,
  });
  const setFor = (section: string) => (name: string | null) =>
    setExpanded((e) => ({ ...e, [section]: name }));

  return (
    <div className="container fade-in">
      <div className="stack stack-3" style={{ marginBottom: 28, maxWidth: 640 }}>
        <div className="eyebrow accent">Browse</div>
        <h1 className="h-1">Every government, <span className="h-italic serif">one list at a time.</span></h1>
        <p className="t-lead">Municipal, provincial, federal — alphabetical, and growing. Tap any name to preview who&apos;s there.</p>
      </div>

      <div className="stack stack-6">
        <BrowseSection
          title="Municipal" subtitle="Cities &amp; towns, starting with Ontario"
          count={ON_MUNICIPALITIES.length} items={ON_MUNICIPALITIES}
          expandedName={expanded.municipal} setExpandedName={setFor("municipal")}
          renderExpanded={(item) => item.covered && item.mayor
            ? <div className="card" style={{ padding: "4px 14px" }}>
                <PersonRow name={item.mayor.full_name} sub={item.mayor.display_title} initials={item.mayor.initials} />
              </div>
            : <ComingSoonNote noun="municipality" />}
        />
        <BrowseSection
          title="Provincial" subtitle="All 13 provinces &amp; territories"
          count={PROVINCES.length} items={PROVINCES}
          expandedName={expanded.provincial} setExpandedName={setFor("provincial")}
          renderExpanded={(item) => item.covered ? (
            <div className="stack stack-3">
              <button className="btn outline sm" onClick={() => onOpenProvince(item.slug!)}>
                View all of Ontario <Icon name="chevron_right" size={14} />
              </button>
            </div>
          ) : <ComingSoonNote noun="province" />}
        />
        <BrowseSection
          title="Federal" subtitle={`Showing ${FEDERAL_RIDINGS.length} of 343 ridings`}
          count={FEDERAL_RIDINGS.length} items={FEDERAL_RIDINGS}
          expandedName={expanded.federal} setExpandedName={setFor("federal")}
          renderExpanded={(item) => item.mp
            ? <div className="card" style={{ padding: "4px 14px" }}>
                <PersonRow name={item.mp} sub={`MP, ${item.name}`}
                  initials={item.mp.split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase()} />
              </div>
            : <ComingSoonNote noun="riding" />}
        />
      </div>
    </div>
  );
}

export function ProvincePage() {
  return (
    <div className="container wide fade-in">
      <div className="stack stack-3" style={{ marginBottom: 28, maxWidth: 640 }}>
        <div className="eyebrow accent">Provincial · Live</div>
        <h1 className="h-1">Ontario</h1>
        <p className="t-lead">Queen&apos;s Park, and every municipality we&apos;ve mapped so far.</p>
      </div>
      <div className="detail-grid">
        <div className="stack stack-5">
          <div>
            <div className="section-label" style={{ marginBottom: 8 }}>MPPs · {ON_MPPS.length}</div>
            <div className="card" style={{ padding: "4px 14px" }}>
              {ON_MPPS.map((m, i) => (
                <React.Fragment key={m.uuid}>
                  {i > 0 ? <hr className="divider" /> : null}
                  <PersonRow name={m.full_name} sub={`${m.district_name} · ${m.party_name}`} initials={m.initials} />
                </React.Fragment>
              ))}
            </div>
          </div>
        </div>
        <div>
          <div className="section-label" style={{ marginBottom: 8 }}>Municipalities · {ON_MUNICIPALITIES.length}</div>
          <div className="card" style={{ padding: "4px 14px" }}>
            {ON_MUNICIPALITIES.map((m, i) => (
              <React.Fragment key={m.name}>
                {i > 0 ? <hr className="divider" /> : null}
                <div className="row between" style={{ padding: "12px 0" }}>
                  <span className="t-body" style={{ fontWeight: 500 }}>{m.name}</span>
                  {m.covered && m.mayor
                    ? <span className="t-sm accent" style={{ fontWeight: 500 }}>{m.mayor.full_name}</span>
                    : <span className="t-xs">Coming soon</span>}
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
