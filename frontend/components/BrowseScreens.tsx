"use client";

// components/BrowseScreens.tsx — the browse tree, built from the live
// jurisdiction index. Every row here is a jurisdiction the API serves, so
// there is no "coming soon" state left to render: what isn't loaded isn't
// listed. Expanding a row previews its head of government, fetched on demand.

import React from "react";
import {
  groupJurisdictions, useJurisdictions, type BrowseGroups,
} from "@/lib/browse-data";
import type { JurisdictionIndexEntry, JurisdictionResponse } from "@/lib/types";
import { api } from "@/lib/api";
import { metaFor } from "@/lib/format";
import { Avatar, Skeleton } from "./ui";
import { Icon } from "./Icon";

/** One preview fetch per jurisdiction per page load, shared across expansions. */
const previews = new Map<string, Promise<JurisdictionResponse>>();

function usePreview(slug: string, enabled: boolean) {
  const [data, setData] = React.useState<JurisdictionResponse | null>(null);
  const [failed, setFailed] = React.useState(false);

  React.useEffect(() => {
    if (!enabled) return;
    let live = true;
    let p = previews.get(slug);
    if (!p) {
      p = api.jurisdiction(slug);
      previews.set(slug, p);
      p.catch(() => previews.delete(slug));
    }
    p.then((d) => { if (live) setData(d); }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [slug, enabled]);

  return { data, failed, loading: enabled && !data && !failed };
}

function PreviewBody({
  entry, onOpen,
}: {
  entry: JurisdictionIndexEntry;
  onOpen: (j: JurisdictionIndexEntry) => void;
}) {
  const { data, failed, loading } = usePreview(entry.slug, true);
  const meta = metaFor(entry.level);
  const gov = data?.jurisdiction.governance;
  const label = gov?.role_label_plural || "representatives";

  if (loading) {
    return (
      <div className="card" style={{ padding: 14 }}>
        <div className="row row-gap-3">
          <Skeleton w={40} h={40} r={20} />
          <div className="stack stack-2 fill"><Skeleton w="55%" h={12} /><Skeleton w="35%" h={16} /></div>
        </div>
      </div>
    );
  }

  if (failed || !data) {
    return (
      <div className="card hatch ghost" style={{ padding: 14 }}>
        <p className="t-sm" style={{ margin: 0 }}>
          We couldn&apos;t load {entry.name} just now. Try again in a moment.
        </p>
      </div>
    );
  }

  const exec = data.executive;
  return (
    <div className="stack stack-3">
      {exec ? (
        <div className="card" style={{ padding: "10px 14px" }}>
          <div className="eyebrow accent" style={{ marginBottom: 6 }}>{meta.execTitle}</div>
          <div className="rep" style={{ cursor: "default", padding: 0 }}>
            <Avatar pol={exec} size="sm" />
            <span className="fill">
              <span className="rep-name" style={{ fontSize: 17, display: "block" }}>{exec.full_name}</span>
              <span className="rep-sub"><span>{exec.display_title}</span></span>
            </span>
          </div>
        </div>
      ) : null}
      <button type="button" className="btn outline sm" onClick={() => onOpen(entry)}>
        View all {data.representatives.length} {label.toLowerCase()} <Icon name="chevron_right" size={14} />
      </button>
    </div>
  );
}

function JurisdictionRow({
  entry, open, onToggle, onOpen, hint,
}: {
  entry: JurisdictionIndexEntry;
  open: boolean;
  onToggle: () => void;
  onOpen: (j: JurisdictionIndexEntry) => void;
  hint?: string;
}) {
  return (
    <div className={`acc ${open ? "open" : ""}`} style={{ borderRadius: "var(--r-md)" }}>
      <button type="button" className="acc-head" style={{ padding: "14px 16px" }}
        onClick={onToggle} aria-expanded={open}>
        <span className="fill row between">
          <span className="level-name" style={{ fontSize: 17 }}>{entry.name}</span>
          <span className="row row-gap-3">
            {hint ? <span className="t-xs mono" style={{ color: "var(--ink-3)" }}>{hint}</span> : null}
            <Icon name="chevron_down" size={15} stroke={2}
              style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .2s", color: "var(--ink-3)" }} />
          </span>
        </span>
      </button>
      {open ? (
        <div className="acc-body" style={{ padding: "0 16px 16px" }}>
          <PreviewBody entry={entry} onOpen={onOpen} />
        </div>
      ) : null}
    </div>
  );
}

function SectionHead({ title, subtitle, count }: { title: string; subtitle: string; count?: number }) {
  return (
    <div className="row between" style={{ alignItems: "baseline" }}>
      <div>
        <div className="eyebrow accent">{title}</div>
        <div className="t-xs" style={{ marginTop: 2 }}>{subtitle}</div>
      </div>
      {count === undefined ? null : <span className="t-xs mono">{count} listed</span>}
    </div>
  );
}

export function BrowsePage({
  focus, onOpenJurisdiction,
}: {
  focus?: { section: string; name: string } | null;
  onOpenJurisdiction: (j: JurisdictionIndexEntry) => void;
}) {
  const { data, error, loading } = useJurisdictions();
  const [expanded, setExpanded] = React.useState<string | null>(null);

  const groups: BrowseGroups | null = React.useMemo(
    () => (data ? groupJurisdictions(data) : null), [data],
  );

  // A place picked from search arrives as a name; open that row once the index
  // that contains it has loaded.
  React.useEffect(() => {
    if (!focus || !data) return;
    const hit = data.find((j) => j.name === focus.name);
    if (hit) setExpanded(hit.slug);
  }, [focus, data]);

  const rowProps = (entry: JurisdictionIndexEntry) => ({
    entry,
    open: expanded === entry.slug,
    onToggle: () => setExpanded(expanded === entry.slug ? null : entry.slug),
    onOpen: onOpenJurisdiction,
  });

  return (
    <div className="container fade-in">
      <div className="stack stack-3" style={{ marginBottom: 28, maxWidth: 640 }}>
        <div className="eyebrow accent">Browse</div>
        <h1 className="h-1">Every government, <span className="h-italic serif">one list at a time.</span></h1>
        <p className="t-lead">
          Municipal, provincial, federal — every government we&apos;ve mapped, and growing.
          Tap any name to see who&apos;s there.
        </p>
      </div>

      {loading ? (
        <div className="stack stack-2">
          {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} h={52} r={12} />)}
        </div>
      ) : error || !groups ? (
        <div className="card hatch ghost" style={{ padding: 16 }}>
          <p className="t-sm" style={{ margin: 0 }}>
            We couldn&apos;t load the list of governments just now. Please refresh in a moment.
          </p>
        </div>
      ) : (
        <div className="stack stack-6">
          <section className="stack stack-3">
            <SectionHead
              title="Municipal"
              subtitle={`Cities & towns across ${groups.municipalByProvince.length} provinces`}
              count={groups.municipalCount}
            />
            {groups.municipalByProvince.map((prov) => (
              <div key={prov.code} className="stack stack-2">
                <div className="section-label">{prov.name} · {prov.items.length}</div>
                {prov.items.map((m) => <JurisdictionRow key={m.slug} {...rowProps(m)} />)}
              </div>
            ))}
          </section>

          <section className="stack stack-3">
            <SectionHead
              title="Provincial & territorial"
              subtitle="Legislatures and legislative assemblies"
              count={groups.provincial.length}
            />
            <div className="stack stack-2">
              {groups.provincial.map((p) => (
                <JurisdictionRow key={p.slug} {...rowProps(p)}
                  hint={metaFor(p.level).tag === "TERRITORIAL" ? "Territory" : undefined} />
              ))}
            </div>
          </section>

          <section className="stack stack-3">
            <SectionHead title="Federal" subtitle="The House of Commons" />
            <div className="stack stack-2">
              {groups.federal.map((f) => <JurisdictionRow key={f.slug} {...rowProps(f)} />)}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
