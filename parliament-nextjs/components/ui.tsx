"use client";

// components/ui.tsx — shared presentational primitives.
import React from "react";
import type { Politician } from "@/lib/types";
import { photoSrc } from "@/lib/derived";
import { Icon } from "./Icon";

// ── Contact resolution ──────────────────────────────────────────────────────
// The API ships two separate fields, either / both / neither populated:
//   email            — a mailto-style address
//   contact_form_url — an https URL to the official's government contact form
// The UI shows ONE button labelled "Email" regardless of which is present.
// Precedence: a direct email wins over a contact form. If neither exists this
// returns null and callers hide the affordance entirely.
export type ContactAction = { href: string; external: boolean; hint: string };

export function getContactAction(
  pol: Pick<Politician, "email"> & { contact_form_url?: string | null },
): ContactAction | null {
  if (!pol) return null;
  if (pol.email) {
    return { href: `mailto:${pol.email}`, external: false, hint: pol.email };
  }
  if (pol.contact_form_url) {
    return { href: pol.contact_form_url, external: true, hint: "Contact form" };
  }
  return null;
}

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

// RepRow + inline quick-contact actions. Used on the lookup results page so a
// user can call or email a representative without first opening the profile.
// The identity area still opens the full detail view; the action bar stops
// propagation so a tap on "Call"/"Email" never also navigates.
export function RepContactCard({
  pol, eyebrow, onOpen,
}: {
  pol: Politician; eyebrow?: string; onOpen?: () => void;
}) {
  const email = getContactAction(pol);
  const tel = pol.phone ? `tel:${pol.phone.replace(/[^\d+]/g, "")}` : null;
  const hasActions = Boolean(tel || email);
  return (
    <div className="rep-card">
      <button type="button" className="rep" style={{ width: "100%", padding: 0 }} onClick={onOpen}>
        <Avatar pol={pol} size="sm" />
        <span className="fill">
          {eyebrow ? <span className="section-label" style={{ display: "block", marginBottom: 3 }}>{eyebrow}</span> : null}
          <span className="rep-name" style={{ fontSize: 19, display: "block" }}>{pol.full_name}</span>
          <span className="rep-sub">
            <span>{pol.display_title}</span>
            {pol.party_name ? <><span className="sep" /><span className="accent" style={{ fontWeight: 500 }}>{pol.party_name}</span></> : null}
          </span>
        </span>
        <Icon name="chevron_right" size={18} className="chevron" />
      </button>
      {hasActions ? (
        <div className="rep-actions">
          {tel ? (
            <a className="act-btn primary" href={tel}>
              <Icon name="phone" size={15} stroke={1.8} /> Call
            </a>
          ) : null}
          {email ? (
            <a
              className="act-btn"
              href={email.href}
              {...(email.external ? { target: "_blank", rel: "noreferrer" } : {})}
            >
              <Icon name="mail" size={15} /> Email
            </a>
          ) : null}
        </div>
      ) : null}
    </div>
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
