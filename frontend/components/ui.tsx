"use client";

import React from "react";
import type { Politician } from "@/lib/types";
import { photoSrc } from "@/lib/derived";
import { Icon } from "./Icon";

type Size = "sm" | "md" | "lg" | "xl";

export function Avatar({ pol, size = "md" }: { pol: Pick<Politician, "initials" | "party_class" | "photo_url" | "full_name">; size?: Size }) {
  const src = photoSrc(pol);
  const [broken, setBroken] = React.useState(false);
  return (
    <span className={`avatar ${size}`}>
      {src && !broken ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={pol.full_name} onError={() => setBroken(true)} loading="lazy" />
      ) : (
        <span>{pol.initials}</span>
      )}
      <span className={`party ${pol.party_class}`} />
    </span>
  );
}

export function PartyChip({ pol }: { pol: Pick<Politician, "party_name" | "party_class"> }) {
  if (!pol.party_name) return null;
  return (
    <span className="chip">
      <span className={`party ${pol.party_class}`} style={{ position: "static", width: 8, height: 8, minWidth: 0, minHeight: 0, border: 0, borderRadius: 4 }} />
      {pol.party_name}
    </span>
  );
}

export function RepRow({
  pol, eyebrow, nameSize = 19, onClick,
}: {
  pol: Politician; eyebrow?: string; nameSize?: number; onClick?: () => void;
}) {
  return (
    <button type="button" className="rep" onClick={onClick}>
      <Avatar pol={pol} size="sm" />
      <span className="fill">
        {eyebrow ? <span className="section-label" style={{ display: "block", marginBottom: 3 }}>{eyebrow}</span> : null}
        <span className="rep-name" style={{ fontSize: nameSize, display: "block" }}>{pol.full_name}</span>
        <span className="rep-sub">
          <span>{pol.display_title}</span>
          {pol.party_name ? <><span className="sep" /><span className="accent" style={{ fontWeight: 500 }}>{pol.party_name}</span></> : null}
        </span>
      </span>
      <Icon name="chevron_right" size={18} className="chevron" />
    </button>
  );
}

export function Countdown({ days }: { days: number | null }) {
  if (days == null || days < 0) return null;
  return <span className="countdown"><span className="num">{days}</span> days until election</span>;
}

export function Skeleton({ w = "100%", h = 14, r = 6, style }: { w?: number | string; h?: number; r?: number; style?: React.CSSProperties }) {
  return <span className="skel" style={{ width: w, height: h, borderRadius: r, ...style }} />;
}

export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <svg className="spin" width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2" strokeOpacity=".2" />
      <path d="M21 12a9 9 0 00-9-9" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function BrandMark({ onClick, showDot = true }: { onClick?: () => void; showDot?: boolean }) {
  return (
    <span className="brand-mark" onClick={onClick} role={onClick ? "button" : undefined}>
      {showDot ? <span className="dot" /> : null}
      <span className="name">parliament</span>
    </span>
  );
}
